"""Anthropic Messages API adapter: vision + structured JSON (streaming)."""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import anthropic
from django.conf import settings
from tenacity import retry

from core.apps.base.resources.ai.providers.base import (
    LLMUsageMeta,
    BarraMcpLookupRequest,
    BarraMcpLookupResult,
    AnthropicProvider,
    VisionStructuredRequest,
    VisionStructuredResult,
    PrescriptionOCRResult,
    Articulo,
    Diagnostico,
)
from core.apps.base.resources.ai.usage import anthropic_usage_meta
from core.apps.base.resources.ai.vision_preprocess import (
    prepare_image_bytes_for_anthropic_vision,
)

log = logging.getLogger(__name__)


class AnthropicStructuredVisionProvider(AnthropicProvider):
    """
    Run Claude vision + ``json_schema`` structured output via streaming.

    Streaming avoids SDK non-streaming timeouts on large vision + JSON responses.
    """

    def run_vision_json_schema(
        self, request: VisionStructuredRequest
    ) -> VisionStructuredResult:
        """Run Claude vision to extract prescription OCR."""
        image_bytes, mt = prepare_image_bytes_for_anthropic_vision(
            request.image_bytes, request.image_media_type
        )
        b64 = base64.standard_b64encode(image_bytes).decode('ascii')

        stream_kwargs: dict[str, Any] = {
            'model': request.model_id,
            'max_tokens': request.max_tokens,
            'output_config': {
                'format': {
                    'type': 'json_schema',
                    'schema': request.output_json_schema,
                },
            },
            'system': request.system_prompt,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': mt,
                                'data': b64,
                            },
                        },
                        {'type': 'text', 'text': request.user_text},
                    ],
                }
            ],
        }

        with self.client.messages.stream(**stream_kwargs) as stream:
            for _ in stream.text_stream:
                pass
            response = stream.get_final_message()

        if not (
            text := next((b.text for b in response.content if b.type == 'text'), None)
        ):
            raise ValueError('La respuesta del modelo no contiene texto JSON.')

        try:
            parsed: dict[str, Any] = json.loads(text)
            prescription_ocr_result = PrescriptionOCRResult(
                IPS=parsed['IPS'].upper().strip(),
                FechaFormula=parsed['FechaFormula'],
                TipoDocumentoPaciente=parsed['TipoDocumentoPaciente'],
                NumeroDocumentoPaciente=parsed['NumeroDocumentoPaciente'],
                NombrePaciente=parsed['NombrePaciente'],
                NombreMedico=parsed['NombreMedico'],
                Articulos=[Articulo(**articulo) for articulo in parsed['Articulos']],
                OtrosDiagnosticos=[Diagnostico(**diagnostico) for diagnostico in parsed['OtrosDiagnosticos']] if parsed['OtrosDiagnosticos'] else None,
                DiagnosticoPrincipal = Diagnostico(**parsed['DiagnosticoPrincipal']) if parsed['DiagnosticoPrincipal'] else None
            )
        except json.JSONDecodeError as e:
            log.warning('Structured vision JSON parse failed: %s', e)
            raise ValueError('El modelo devolvió JSON inválido.') from e
        except TypeError as e:
            log.error("Json inesperado por parte del LLM.")
            raise ValueError('El modelo devolvió JSON inválido o información incompleta.') from e

        usage = anthropic_usage_meta(request.model_id, response.usage)
        return VisionStructuredResult(prescription_ocr_result=prescription_ocr_result, usage=usage)


def _beta_final_text(response: Any) -> str:
    """Last text block from a beta message (after optional MCP / tool turns)."""
    texts: list[str] = []
    for block in getattr(response, 'content', []) or []:
        if getattr(block, 'type', None) == 'text':
            t = getattr(block, 'text', None)
            if t:
                texts.append(str(t))
    if not texts:
        return ''
    raw_text = texts[-1].strip()
    text = str(raw_text).strip().splitlines()[0].strip()
    text = re.sub(r'\D+', '', text)
    return text or ''


class AnthropicBarraMcpProvider(AnthropicProvider):
    """
    Claude Messages API with MCP connector: text prompt + remote Postgres MCP tools.
    """

    MCP_BETA = 'mcp-client-2025-11-20'
    
    def run_barra_mcp_lookup(self, request: BarraMcpLookupRequest) -> BarraMcpLookupResult:
        """Find out an article on the database using MCP."""
        if not (request.mcp_server_url or '').strip():
            raise ValueError(
                'ANTHROPIC_MCP_POSTGRES_URL no está configurada (URL del servidor MCP).'
            )
        server: dict[str, Any] = {
            'type': 'url',
            'url': request.mcp_server_url.strip(),
            'name': request.mcp_server_name.strip(),
        }
        if request.mcp_authorization_token:
            server['authorization_token'] = request.mcp_authorization_token

        kwargs: dict[str, Any] = {
            'model': request.model_id,
            'max_tokens': request.max_tokens,
            'messages': [{'role': 'user', 'content': request.user_text}],
            'mcp_servers': [server],
            'tools': [
                {'type': 'mcp_toolset', 'mcp_server_name': request.mcp_server_name.strip()}
            ],
            'betas': [self.MCP_BETA],
            # 'thinking': {'type': 'enabled', 'budget_tokens': 8000},
            # 'output_config': {'effort': 'high'},
        }
        if request.system_prompt:
            kwargs['system'] = request.system_prompt

        response = self.client.beta.messages.create(**kwargs)
        
        text = _beta_final_text(response)
        usage: LLMUsageMeta = anthropic_usage_meta(request.model_id, response.usage)
        return BarraMcpLookupResult(text=text, usage=usage, raw_response=response, input_raw=kwargs)
