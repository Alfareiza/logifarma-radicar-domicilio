"""Provider-neutral contracts for structured vision completions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any

import anthropic
from pydantic import BaseModel, BeforeValidator, PlainSerializer, field_validator, model_validator

from core import settings
from core.apps.base.resources.tools import remove_accents


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


class Duracion(BaseModel):
    """Treatment duration with automatic day-normalization."""

    Valor: int
    Unidad: str

    @field_validator('Unidad', mode='after')
    @classmethod
    def capitalize_unidad(cls, v: str) -> str:
        return v.capitalize()

    @property
    def ValorEnDias(self) -> int:
        """Return duration expressed as a number of days."""
        match self.Unidad:
            case 'Dias':
                return self.Valor
            case 'Semanas':
                return self.Valor * 7
            case 'Mes':
                return 30
            case 'Meses':
                return self.Valor * 30
            case _:
                return 0


class CantidadDetalle(BaseModel):
    """Single quantity slot (value + human-readable label)."""

    Valor: int | None = None
    Descripcion: str | None = None


class Cantidad(BaseModel):
    """Prescribed vs. dispensed quantity pair."""

    Formulada: CantidadDetalle | None = None
    Dispensada: CantidadDetalle | None = None

    @model_validator(mode='before')
    @classmethod
    def accept_formulada_short_shape(cls, data: Any) -> Any:
        """Accept {"Valor": ..., "Descripcion": ...} as the formulated quantity."""
        if isinstance(data, dict) and 'Valor' in data and 'Formulada' not in data and 'Dispensada' not in data:
            return {'Formulada': data, 'Dispensada': None}
        return data


class Articulo(BaseModel):
    """Single prescription line item (one medication)."""

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

    @field_validator('FormaFarmaceutica', mode='after')
    @classmethod
    def normalize_forma_farmaceutica(cls, v: str) -> str:
        return v.capitalize().strip()


    @model_validator(mode='after')
    def cap_dispensed_to_monthly(self) -> 'Articulo':
        """Cap dispensed quantity to one month when treatment exceeds 30 days."""
        if (
            self.Duracion is not None
            and self.Duracion.ValorEnDias > 30
            and self.Cantidad is not None
            and self.Cantidad.Formulada is not None
            and self.Cantidad.Formulada.Valor is not None
        ):
            monthly = int(self.Cantidad.Formulada.Valor / (self.Duracion.ValorEnDias / 30))
            self.Cantidad.Dispensada = CantidadDetalle(Valor=monthly, Descripcion='Por mes')
        else:
            self.Cantidad.Dispensada = self.Cantidad.Formulada.model_copy()
        return self


class Diagnostico(BaseModel):
    """ICD-10 diagnosis code and description."""

    Codigo: str
    Descripcion: str


class PrescriptionOCRResult(BaseModel):
    """Structured output of a prescription OCR extraction."""

    IPS: str
    NitIPS: str | None = None
    FechaFormula: Annotated[
        datetime,
        BeforeValidator(lambda v: datetime.strptime(v, "%d-%m-%Y") if isinstance(v, str) else v),
        PlainSerializer(lambda v: v.strftime("%d-%m-%Y"), return_type=str)
    ]
    TipoDocumentoPaciente: str
    NumeroDocumentoPaciente: str
    NombrePaciente: str
    NombreMedico: str
    DiagnosticoPrincipal: Diagnostico | None
    OtrosDiagnosticos: list[Diagnostico] | None
    Articulos: list[Articulo]

    @field_validator('IPS', mode='after')
    @classmethod
    def normalize_ips(cls, v: str) -> str:
        return remove_accents(v.upper().strip())

    @property
    def diagnostico_principal(self) -> str:
        return ' '.join(self.DiagnosticoPrincipal.__dict__.values())


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


class AnthropicProvider:
    """Base class for Anthropic SDK adapters."""

    def __init__(self, *, api_key: str | None = None, max_retries: int = 3) -> None:
        if not (key := settings.ANTHROPIC_API_KEY):
            raise ValueError('ANTHROPIC_API_KEY no está configurada.')
        self.client = anthropic.Anthropic(api_key=key, max_retries=max_retries)
