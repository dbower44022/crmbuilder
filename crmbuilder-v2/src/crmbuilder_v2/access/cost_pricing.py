"""Per-model price table → dollar cost from token usage (PI-263 / PRJ-041, REQ-307).

Decision 4 of the cost-control design: ``cost_usd`` is computed **uniformly** from token
counts via a configurable per-model price table, so in-process SDK calls and ``claude -p``
fleet agents are costed the same way (apples-to-apples across surfaces, models, and
areas). Rates are **USD per million tokens**.

The defaults below are kept current as Anthropic pricing / models change. An operator can
override or extend them **without a code change** via the ``CRMBUILDER_V2_COST_PRICES``
environment variable — a JSON object mapping a model id *or* family key to
``{"input", "output", "cache_write", "cache_read"}`` rates per million tokens, e.g.::

    CRMBUILDER_V2_COST_PRICES='{"opus": {"input": 15, "output": 75, "cache_write": 18.75, "cache_read": 1.5}}'

A model id is resolved against the table by exact match first, then by family substring
(``opus`` / ``sonnet`` / ``haiku``), so date-suffixed ids resolve without an exact entry.
An unpriced model yields ``0.0`` — the token counts are still recorded, so cost can be
recomputed later once a rate is added.
"""

from __future__ import annotations

import json
import os

_MILLION = 1_000_000

# USD per MILLION tokens. Family keys (matched as a substring of the model id).
_DEFAULT_PRICES: dict[str, dict[str, float]] = {
    "opus": {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.50},
    "sonnet": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.30},
    "haiku": {"input": 1.0, "output": 5.0, "cache_write": 1.25, "cache_read": 0.10},
}


def _table() -> dict[str, dict[str, float]]:
    """The effective price table — defaults merged with any env override."""
    table: dict[str, dict[str, float]] = {k: dict(v) for k, v in _DEFAULT_PRICES.items()}
    raw = os.environ.get("CRMBUILDER_V2_COST_PRICES")
    if raw:
        try:
            override = json.loads(raw)
        except (ValueError, TypeError):
            override = None  # malformed override → ignore, keep defaults
        if isinstance(override, dict):
            for key, rates in override.items():
                if isinstance(rates, dict):
                    table[key] = rates
    return table


def _resolve(model: str, table: dict[str, dict[str, float]]) -> dict[str, float] | None:
    if not model:
        return None
    if model in table:  # exact model id
        return table[model]
    low = model.lower()
    for key, rates in table.items():  # family substring (opus / sonnet / haiku)
        if key.lower() in low:
            return rates
    return None


def compute_cost_usd(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Dollar cost for one call's token usage, from the price table. ``0.0`` if the
    model has no rate (the tokens are still recorded for later recomputation)."""
    rates = _resolve(model or "", _table())
    if rates is None:
        return 0.0
    total = (
        (input_tokens or 0) * rates.get("input", 0.0)
        + (output_tokens or 0) * rates.get("output", 0.0)
        + (cache_write_tokens or 0) * rates.get("cache_write", 0.0)
        + (cache_read_tokens or 0) * rates.get("cache_read", 0.0)
    )
    return round(total / _MILLION, 6)


def is_priced(model: str) -> bool:
    """Whether a rate resolves for ``model`` (so an unpriced model can be flagged)."""
    return _resolve(model or "", _table()) is not None
