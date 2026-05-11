"""
Prescription-photo extraction goal: Claude vision + JSON schema output.

Keeps prompts, schema, model defaults together so additional goals can mirror this
pattern without duplicating orchestration logic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.apps.base.resources.ai.providers.base import VisionStructuredRequest

# Default Claude model for this goal (balanced quality/cost).
PRESCRIPTION_EXTRACTION_MODEL_ID_DEFAULT = 'claude-sonnet-4-6'

# Allow headroom for structured JSON output (streaming avoids SDK timeouts).
_PRESCRIPTION_EXTRACTION_MAX_TOKENS = 64000

_STRING_OR_NULL = {'anyOf': [{'type': 'string'}, {'type': 'null'}]}

_DIAGNOSTICO = {
    'type': 'object',
    'properties': {
        'Codigo': {'type': 'string'},
        'Descripcion': {'type': 'string'},
    },
    'required': ['Codigo', 'Descripcion'],
    'additionalProperties': False,
}

_DURACION_TRATAMIENTO = {
    'type': 'object',
    'properties': {
        'Valor': {'type': 'integer'},
        'Unidad': {'type': 'string'},
    },
    'required': ['Valor', 'Unidad'],
    'additionalProperties': False,
}

_CANTIDAD_PRESCRITA = {
    'type': 'object',
    'properties': {
        'Valor': {'type': 'integer'},
        'Descripcion': _STRING_OR_NULL,
    },
    'required': ['Valor', 'Descripcion'],
    'additionalProperties': False,
}

_ARTICULO = {
    'type': 'object',
    'properties': {
        'Numero': {
            'type': 'integer',
            'description': '1-based row index as printed or reading order',
        },
        'Nombre': {
            'type': 'string',
            'description': 'Commercial or ordered product description as on the form',
        },
        'Concentracion': {'type': 'string', 'description': 'Strength, e.g. 262 mg'},
        'FormaFarmaceutica': {
            'type': 'string',
            'description': 'Dosage form, e.g. Tableta',
        },
        'Via': {'type': 'string', 'description': 'Route, e.g. Oral'},
        'Dosis': {
            'type': 'string',
            'description': 'Per-administration dose as printed (e.g. "2.00 Dosis")',
        },
        'Frecuencia': {
            'type': 'string',
            'description': 'Interval, e.g. Cada 12 horas',
        },
        'Duracion': _DURACION_TRATAMIENTO,
        'Cantidad': _CANTIDAD_PRESCRITA,
        'Indicaciones': _STRING_OR_NULL,
        'PrincipioActivo': _STRING_OR_NULL,
    },
    'required': [
        'Numero',
        'Nombre',
        'Concentracion',
        'FormaFarmaceutica',
        'Via',
        'Dosis',
        'Frecuencia',
        'Duracion',
        'Cantidad',
        'Indicaciones',
        'PrincipioActivo',
    ],
    'additionalProperties': False,
}

PRESCRIPTION_OCR_OUTPUT_SCHEMA: dict[str, Any] = {
    'type': 'object',
    'properties': {
        'IPS': {'type': 'string'},
        'NitIPS': {'type': 'string'},
        'FechaFormula': {'type': 'string'},
        'TipoDocumentoPaciente': {'type': 'string'},
        'NumeroDocumentoPaciente': {'type': 'string'},
        'NombrePaciente': {'type': 'string'},
        'NombreMedico': {'type': 'string'},
        'DiagnosticoPrincipal': _DIAGNOSTICO,
        'OtrosDiagnosticos': {'type': 'array', 'items': _DIAGNOSTICO},
        'Articulos': {'type': 'array', 'items': _ARTICULO},
    },
    'required': [
        'IPS',
        'NitIPS',
        'FechaFormula',
        'TipoDocumentoPaciente',
        'NumeroDocumentoPaciente',
        'NombrePaciente',
        'NombreMedico',
        'DiagnosticoPrincipal',
        'OtrosDiagnosticos',
        'Articulos',
    ],
    'additionalProperties': False,
}

SYSTEM_PROMPT = """You are an expert at reading Latin American medical prescription documents from photographs.

The image may be rotated (landscape/portrait) or photographed from an angle. Infer the correct reading order.
Text may be left-to-right; some headers or stamps may differ — still extract the best-effort values.

Rules:
- Output MUST be a single JSON object matching the required schema exactly. No markdown, no code fences, no commentary.
- Use empty string "" for any field you cannot read with confidence.
- Preserve Spanish labels' meaning in the values (do not translate medical product names).
- For lists (OtrosDiagnosticos, Articulos), include every distinct line item visible; if none, use empty arrays.
- Each item in Articulos uses CamelCase keys: Numero (1-based line order), Nombre, Concentracion, FormaFarmaceutica, Via, Dosis, Frecuencia, Duracion { Valor integer, Unidad string e.g. dias }, Cantidad { Valor integer, Descripcion string or null }, Indicaciones string or null, PrincipioActivo string or null. Use null only for optional nullable fields when absent; otherwise use "" for unknown strings and 0 for unknown integer amounts if you cannot read them.
- IPS = issuing institution or health provider name on the form when present. "".
- NitIPS = issuing institution or health provider nit on the form when present; This number is like the identification number of the institution or health provider. Usually starts with a number 9 and it is closer to the IPS text or logo"".
- NombreMedico = doctor's name as printed (string, as on the form), this is usually diferrent from the NombrePaciente.
- NombrePaciente = patient's name as printed (string, as on the form), this is usually diferrent from the NombreMedico.
- FechaFormula = service or prescription date as printed (string, as on the form) converted into format DD-MM-YYYY. For instance, if the date is "23/abr./2026", the output should be "23-04-2026".


### Guidelines:

#### Guidelines for names in articles:

- Names for articles should start with a name, instead of a number. 
    For instance, if the name is "7000742597 - Etoricoxib 90 mg", the output should be "Etoricoxib 90 mg".
    For instance, if the name is "19973237-1", this is wrong because in the image there is a name for the article.
- Names for articles shouldn't contains the dosis.
    For instance, if the name is "Esomeprazol 20MG Cápsulas", the output should be "Esomeprazol 20MG".

#### Guidelines for dosis in articles:
- Dosis for articles should be standarized order to be easier to read.
    For instance, if the dosis is "28 Unidades" the output should be "28 UND". If the dosis is "1 Tableta" the output should be "1 TAB". If the dosis is "1 U" the output should be "1 UND". 

#### Guidelines for Cantidad in articles:
- The value for Descripcion in Cantidad should be different than Dosis.
    For instance, if the dosis is "1 SOBRE" and the Descripcion is "SOBRES", the output for Descripcion should be null
    For instance, if the dosis is "1 Gota" and the Descripcion is "Frasco", the output for Descripcion should be null
    For instance, if the dosis is "1 FRASCO" and the Descripcion is "FRASCO", the output for Descripcion should be null
    For instance, if the dosis is "1 TAB" and the Descripcion is "CAJA X 30 TABLETAS", the output for Descripcion should be null

- The value for Descripcion in Cantidad should not contains the word "TUBO" o "TUBOS"
- The value for Descripcion in Cantidad should not contains the word "FRASCO" or "FRASCOS"
- The value for Descripcion in Cantidad should not contains the word "SOBRES" or "SOBRE"
- The value for Descripcion in Cantidad should not contains the word "CAJA" or "CAJAS"
"""


def prescription_extraction_user_prompt() -> str:
    """User message paired with the image in the multi-modal request."""
    return (
        'Extract all visible prescription data from this image into the required JSON structure. '
        'If the form shows multiple diagnosis lines, put the main one in DiagnosticoPrincipal '
        'and additional codes/descriptions in OtrosDiagnosticos.'
    )


@dataclass(frozen=True, slots=True)
class StructuredVisionGoal:
    """Portable definition for one vision + JSON-schema extraction task."""

    task_id: str
    provider: str
    model_id: str
    system_prompt: str
    user_prompt_builder: Callable[[], str]
    output_json_schema: dict[str, Any]
    max_tokens: int

    def build_request(
        self,
        image_bytes: bytes,
        image_media_type: str,
        *,
        model_id: str | None = None,
    ) -> VisionStructuredRequest:
        return VisionStructuredRequest(
            model_id=model_id or self.model_id,
            system_prompt=self.system_prompt,
            user_text=self.user_prompt_builder(),
            image_bytes=image_bytes,
            image_media_type=image_media_type,
            output_json_schema=self.output_json_schema,
            max_tokens=self.max_tokens,
        )


PRESCRIPTION_EXTRACTION_GOAL = StructuredVisionGoal(
    task_id='prescription_image_extraction_v1',
    provider='anthropic',
    model_id=PRESCRIPTION_EXTRACTION_MODEL_ID_DEFAULT,
    system_prompt=SYSTEM_PROMPT,
    user_prompt_builder=prescription_extraction_user_prompt,
    output_json_schema=PRESCRIPTION_OCR_OUTPUT_SCHEMA,
    max_tokens=_PRESCRIPTION_EXTRACTION_MAX_TOKENS,
)
 