"""Provider-neutral contracts for structured vision completions."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import anthropic

from core import settings


@dataclass(frozen=True, slots=True)
class LLMUsageMeta:
    """Normalized usage + estimated cost suitable for persistence and APIs."""

    input_tokens: int | None
    output_tokens: int | None
    cache_read_input_tokens: int | None
    cost_usd: str
    raw_usage: dict[str, Any]


@dataclass(frozen=True, slots=True)
class VisionStructuredRequest:
    """One vision + structured JSON-schema completion request."""

    model_id: str
    system_prompt: str
    user_text: str
    image_bytes: bytes
    image_media_type: str
    output_json_schema: dict[str, Any]
    max_tokens: int = 64_000


@dataclass(frozen=True, slots=True)
class Articulo:
    """Articulo."""

    Numero: int
    Nombre: str
    Concentracion: str
    FormaFarmaceutica: str
    Via: str | None
    Dosis: str
    Frecuencia: str
    Duracion: Duracion | None
    Cantidad: Cantidad | None
    Indicaciones: str | None
    PrincipioActivo: str | None

@dataclass(frozen=True, slots=True)
class Duracion:
    """Duracion."""

    Valor: int
    Unidad: str


@dataclass(frozen=True, slots=True)
class Cantidad:
    """Cantidad."""

    Valor: int
    Descripcion: str | None


@dataclass(frozen=True, slots=True)
class Diagnostico:
    """Diagnostico."""

    Codigo: str
    Descripcion: str


@dataclass(frozen=True, slots=True)
class PrescriptionOCRResult:
    """Prescription OCR result."""

    IPS: str
    FechaFormula: str
    TipoDocumentoPaciente: str
    NumeroDocumentoPaciente: str
    NombrePaciente: str
    NombreMedico: str
    DiagnosticoPrincipal: Diagnostico | None
    OtrosDiagnosticos: list[Diagnostico] | None
    Articulos: list[Articulo]

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

@dataclass(frozen=True, slots=True)
class VisionStructuredResult:
    """Parsed JSON object plus usage metadata."""

    prescription_ocr_result: PrescriptionOCRResult
    usage: LLMUsageMeta


@dataclass(frozen=True, slots=True)
class BarraMcpLookupRequest:
    """Text completion with Anthropic MCP connector to Postgres."""

    model_id: str
    user_text: str
    mcp_server_url: str
    mcp_server_name: str
    mcp_authorization_token: str | None = None
    max_tokens: int = 16_000
    system_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class BarraMcpLookupResult:
    """Final assistant text (barcode) plus usage metadata."""

    text: str
    usage: LLMUsageMeta
    raw_response: Any
    input_raw: Any


@runtime_checkable
class AnthropicProvider(Protocol):
    """Protocol implemented by LLM SDK adapters."""

    def __init__(self, *, api_key: str | None = None, max_retries: int = 3) -> None:
        if not (key := settings.ANTHROPIC_API_KEY):
            raise ValueError('ANTHROPIC_API_KEY no está configurada.')
        self._client = anthropic.Anthropic(api_key=key, max_retries=max_retries)
