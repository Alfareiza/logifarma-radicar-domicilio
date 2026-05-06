"""Token usage normalization and approximate USD pricing per provider/model."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import anthropic

from core.apps.base.resources.ai.providers.base import LLMUsageMeta
log = logging.getLogger(__name__)

# Per-million token list rates (input, output); align with documented list pricing.
# Unknown models fall back to Sonnet 4.6 rates as a conservative default.
_ANTHROPIC_INPUT_OUTPUT_PER_M = {
    'claude-opus-4-7': (Decimal('5'), Decimal('25')),
    'claude-opus-4-6': (Decimal('5'), Decimal('25')),
    'claude-sonnet-4-6': (Decimal('3'), Decimal('15')),
    'claude-haiku-4-5': (Decimal('1'), Decimal('5')),
}

# Approximate per-million for cache-read tokens (pricing varies by tier).
_ANTHROPIC_CACHE_READ_PER_M = Decimal('0.10')


def anthropic_estimate_cost_usd(model_id: str, usage: Any) -> Decimal:
    """
    Approximate USD cost from Anthropic ``Message.usage``.

    Raises:
        AttributeError / TypeError: If usage is malformed (caller should guard).
    """
    inp_rates = _ANTHROPIC_INPUT_OUTPUT_PER_M.get(model_id)
    if inp_rates is None:
        inp_rates = _ANTHROPIC_INPUT_OUTPUT_PER_M['claude-sonnet-4-6']
        log.debug(
            'No explicit pricing for model_id=%s; using sonnet 4.6 rates.',
            model_id,
        )
    inp_rate, out_rate = inp_rates
    inp = Decimal(getattr(usage, 'input_tokens', 0) or 0)
    out = Decimal(getattr(usage, 'output_tokens', 0) or 0)
    cr = Decimal(getattr(usage, 'cache_read_input_tokens', 0) or 0)
    dollars = (
        inp / Decimal('1000000') * inp_rate
        + out / Decimal('1000000') * out_rate
        + cr / Decimal('1000000') * _ANTHROPIC_CACHE_READ_PER_M
    )
    return dollars.quantize(Decimal('0.000001'))


def anthropic_usage_to_dict(usage: anthropic.Usage | None) -> dict[str, Any]:
    """Return numeric usage fields suitable for JSON persistence."""
    if usage is None:
        return {}
    out: dict[str, Any] = {}
    for name in (
        'input_tokens',
        'output_tokens',
        'cache_read_input_tokens',
        'cache_creation_input_tokens',
    ):
        v = getattr(usage, name, None)
        if v is not None:
            out[name] = v
    return out


def anthropic_usage_meta(model_id: str, usage: Any | None) -> LLMUsageMeta:
    """Build ``cost_usd`` + token fields consumed by OCR persistence."""
    raw = anthropic_usage_to_dict(usage)
    cost_dec = anthropic_estimate_cost_usd(model_id, usage) if usage is not None else Decimal('0')
    return LLMUsageMeta(
            input_tokens=raw.get('input_tokens'),
            output_tokens=raw.get('output_tokens'),
            cache_read_input_tokens=raw.get('cache_read_input_tokens'),
            cost_usd=str(cost_dec.quantize(Decimal('0.000001'))),
            raw_usage=raw,
        )
    

