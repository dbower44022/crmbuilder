"""Best-effort cost capture at the spend surfaces (PI-264 / PRJ-041, REQ-307).

The two entry points record one ``cost_events`` row per model call:

* :func:`record_sdk_usage` — for in-process Anthropic SDK calls (the scheduler's
  demands / decomposition providers and the release-gate judge), reading the response
  ``usage`` object.
* :func:`record_cli_result` — for ``claude -p --output-format json`` coding-fleet
  invocations, reading the result's ``usage`` + ``total_cost_usd``.

**Recording a spend event must never block or fail the work it measures** (PI-264
acceptance): every entry point swallows its own errors and is side-band. Each opens its
own ``session_scope`` (the providers run outside the scheduler's session); the engagement
is taken from the explicit ``engagement`` arg when given (the fleet path passes
``cfg.engagement``), else from the ambient active-engagement context the scheduler sets
around its run (the SDK path).
"""

from __future__ import annotations

import contextlib
import json
import logging

log = logging.getLogger(__name__)


def _resolve_engagement(engagement: str) -> str | None:
    """Resolve an engagement identifier *or* code (e.g. ``CRMBUILDER``) to its
    canonical ``ENG-NNN`` identifier — the value the ``engagement_id`` FK expects.
    Returns ``None`` if nothing resolves. (The ADO runtime configs carry the code,
    not the identifier, so an unresolved value would fail the stamp's FK.)"""
    try:
        from crmbuilder_v2.access import engagement as engagement_repo

        candidate = (engagement or "").strip()
        upper = candidate.upper()
        for e in engagement_repo.list_engagements_unified(include_deleted=False):
            if e.engagement_identifier == candidate or e.engagement_code.upper() == upper:
                return e.engagement_identifier
    except Exception:  # noqa: BLE001 — resolution is best-effort like the capture
        return None
    return None


def _engagement_ctx(engagement: str | None):
    """The engagement context to record under. Prefers an ambient active engagement
    (already a resolved identifier — set by the scheduler around a release run), so the
    common in-process path just inherits it. Otherwise resolves the explicit engagement
    (identifier or code) to an ``ENG-NNN`` identifier; a no-op if neither resolves."""
    from crmbuilder_v2.access.engagement_scope import (
        active_engagement,
        get_active_engagement,
    )

    if get_active_engagement():
        return contextlib.nullcontext()
    if engagement:
        resolved = _resolve_engagement(engagement)
        if resolved:
            return active_engagement(resolved)
    return contextlib.nullcontext()


def _tokens_from(obj) -> dict:
    """Pull the four token components from an SDK ``usage`` object or a JSON dict."""
    def g(name: str) -> int:
        value = getattr(obj, name, None)
        if value is None and isinstance(obj, dict):
            value = obj.get(name)
        return int(value or 0)

    return {
        "input_tokens": g("input_tokens"),
        "output_tokens": g("output_tokens"),
        "cache_write_tokens": g("cache_creation_input_tokens"),
        "cache_read_tokens": g("cache_read_input_tokens"),
    }


def record_sdk_usage(
    usage, model: str, *, engagement: str | None = None, **attribution
) -> None:
    """Record one in-process SDK call's spend. Best-effort — never raises."""
    try:
        from crmbuilder_v2.access.db import session_scope
        from crmbuilder_v2.access.repositories import cost_events

        tokens = _tokens_from(usage)
        attribution = {k: v for k, v in attribution.items() if v is not None}
        with _engagement_ctx(engagement), session_scope() as s:
            cost_events.record(s, source="sdk", model=model or "", **tokens, **attribution)
    except Exception as exc:  # noqa: BLE001 — capture must never break the work
        log.warning("cost capture (sdk) skipped: %s", exc)


def record_cli_result(
    result, model: str | None = None, *, engagement: str | None = None, **attribution
) -> None:
    """Record one ``claude -p --output-format json`` invocation's spend.

    ``result`` may be the raw stdout string (parsed here) or an already-parsed dict.
    Uses the result's ``usage`` + ``total_cost_usd`` (the reported cost is the
    cross-check, and the fallback when the session's model is unpriced). Best-effort —
    never raises (a non-JSON / empty stdout from a crashed agent is simply skipped)."""
    try:
        from crmbuilder_v2.access.db import session_scope
        from crmbuilder_v2.access.repositories import cost_events

        data = result
        if isinstance(result, str):
            result = result.strip()
            if not result:
                return
            data = json.loads(result)
        if not isinstance(data, dict):
            return
        usage = data.get("usage") or {}
        tokens = _tokens_from(usage)
        reported = data.get("total_cost_usd")
        reported = float(reported) if reported is not None else None
        model = model or data.get("model") or ""
        attribution = {k: v for k, v in attribution.items() if v is not None}
        with _engagement_ctx(engagement), session_scope() as s:
            cost_events.record(
                s, source="claude_cli", model=model, reported_usd=reported,
                **tokens, **attribution,
            )
    except Exception as exc:  # noqa: BLE001 — capture must never break the work
        log.warning("cost capture (claude_cli) skipped: %s", exc)
