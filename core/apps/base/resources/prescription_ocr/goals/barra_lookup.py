"""Claude text + MCP (Postgres) goal: resolve SAP barcode for one OCR article name."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

from core.apps.base.resources.ai.providers.base import BarraMcpLookupRequest

BARRA_LOOKUP_MODEL_ID_DEFAULT = 'claude-sonnet-4-6'

_BARRA_LOOKUP_MAX_TOKENS = 16_000

BARRA_LOOKUP_USER_PROMPT = """You are a pharmaceutical specialist with deep knowledge of drug nomenclature, INN naming conventions, salt forms, and dosage notation.
Query the sap_articulos table in the postgres MCP to find the best matching article for: "[NOMBRE ARTICULO]".
Run a single SQL query that fetches all plausible candidates at once. Before writing it, mentally deconstruct the input name into:
Active ingredient stems (strip salt descriptors like "clorhidrato de", "hidrocloruro", "besilato", etc. The DB rarely stores them)
- Dosage numbers only (ignore units like "MG" in the WHERE clause; just match the numeric values)
- Combination notation (the DB may use /, +, or spaces between molecules and doses)
- Build the query targeting these columns: id, external_id, barra, descripcion, forma_farmaceutica, cum, invima, nombre_molecula, atc, fabricante, marca, regulado, valor_regulado, inactivo, ultima_compra
- Use ILIKE '%stem%' with AND for each keyword. Keep it broad enough to catch spelling variants (e.g. Empagliflozina vs Empaglifozina), but specific enough to avoid noise.
- Once you have the result set, apply your pharmaceutical judgment to select the single best record based on this clinical and operational criteria hierarchy:
- Active record (inactivo = 'N') — never recommend an inactive article
- Correct pharmaceutical form — prefer the form that matches the input or the clinically standard one for that drug class
- Price-regulated (regulado = 'S') — indicates official recognition in the formulary
- Most recent purchase activity (ultima_compra) — signals real inventory movement
Complete commercial identity — valid barcode, known brand (marca ≠ 'NA') Present the winning record with a concise justification of why it outscored the others.
Do not return the entire record, only the "barra" value which is usually an integer with more than 5 ditigs.
Return the value of the "barra" and no more than that. Avoid explanations and additional information besides than "barra"
"""


def build_barra_lookup_user_prompt(*, nombre_articulo: str) -> str:
    safe = (nombre_articulo or '').strip()
    return BARRA_LOOKUP_USER_PROMPT.replace('[NOMBRE ARTICULO]', safe)


def build_barra_mcp_request(
    *,
    nombre_articulo: str,
    model_id: str | None = None,
    mcp_server_url: str | None = None,
    mcp_server_name: str | None = None,
    mcp_authorization_token: str | None = None,
) -> BarraMcpLookupRequest:
    """Build a lookup request using Django settings fallbacks."""
    return BarraMcpLookupRequest(
        model_id=model_id or BARRA_LOOKUP_MODEL_ID_DEFAULT,
        user_text=build_barra_lookup_user_prompt(nombre_articulo=nombre_articulo),
        mcp_server_url=mcp_server_url or settings.ANTHROPIC_MCP_POSTGRES_URL,
        mcp_server_name=mcp_server_name or 'postgres-mcp',
        mcp_authorization_token=mcp_authorization_token or settings.ANTHROPIC_MCP_POSTGRES_TOKEN,
        max_tokens=_BARRA_LOOKUP_MAX_TOKENS,
        system_prompt=None,
    )


@dataclass(frozen=True, slots=True)
class BarraLookupGoal:
    """Portable definition for barcode MCP lookup (mirrors StructuredVisionGoal pattern)."""

    task_id: str
    provider: str
    model_id: str

    def build_request(self, nombre_articulo: str, **kwargs: Any) -> BarraMcpLookupRequest:
        return build_barra_mcp_request(
            nombre_articulo=nombre_articulo,
            model_id=kwargs.get('model_id') or self.model_id,
            mcp_server_url=kwargs.get('mcp_server_url'),
            mcp_server_name=kwargs.get('mcp_server_name'),
            mcp_authorization_token=kwargs.get('mcp_authorization_token'),
        )


BARRA_LOOKUP_GOAL = BarraLookupGoal(
    task_id='prescription_barra_mcp_v1',
    provider='anthropic',
    model_id=BARRA_LOOKUP_MODEL_ID_DEFAULT,
)
