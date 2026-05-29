"""Kickoff-template rendering for the orchestrator (PI-081 / PI-082).

Renders the child-agent kickoff template
(``PRDs/product/crmbuilder-v2/orchestrator/child-agent-kickoff-template.md``)
by substituting its ``{{placeholder}}`` markers, then validates that none
were left unsubstituted. Kept pure so it is unit-testable.
"""

from __future__ import annotations

import re

_PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")


def render_kickoff(template_text: str, substitutions: dict[str, str]) -> str:
    """Substitute every ``{{key}}`` in ``template_text`` from ``substitutions``.

    Raises ``KeyError`` if the template references a placeholder absent
    from ``substitutions``, and ``ValueError`` if any ``{{...}}`` marker
    survives substitution (a guard against silently shipping a half-filled
    kickoff to a child agent). Markers inside HTML comments count too — the
    template's contract block is a comment and is expected to be filled or
    removed by the caller; the driver strips that comment before rendering.
    """
    referenced = set(_PLACEHOLDER_RE.findall(template_text))
    missing = sorted(referenced - set(substitutions))
    if missing:
        raise KeyError(f"template references unknown placeholders: {missing}")

    def _sub(m: re.Match[str]) -> str:
        return str(substitutions[m.group(1)])

    rendered = _PLACEHOLDER_RE.sub(_sub, template_text)
    leftover = _PLACEHOLDER_RE.findall(rendered)
    if leftover:  # pragma: no cover - defensive; substitution covers all matches
        raise ValueError(f"unsubstituted placeholders remain: {sorted(set(leftover))}")
    return rendered


def strip_contract_comment(template_text: str) -> str:
    """Drop the leading ``<!-- ... -->`` placeholder-contract block.

    The template documents its placeholder contract in an HTML comment for
    template maintainers; that comment itself contains ``{{markers}}`` that
    are documentation, not substitution sites. The driver strips it before
    rendering so those markers don't trip the unknown-placeholder check.
    """
    return re.sub(r"<!--.*?-->\n?", "", template_text, count=1, flags=re.DOTALL)


def render_planning_items_block(items: list[dict]) -> str:
    """Render the ``{{planning_items}}`` body from ready-batches item dicts.

    One subsection per planning item with its identifier, title, areas,
    executive summary, and full description inlined so the child agent does
    not need to re-fetch.
    """
    chunks: list[str] = []
    for it in items:
        areas = ", ".join(it.get("area") or []) or "(none)"
        chunks.append(
            f"### {it['identifier']} — {it.get('title', '')}\n\n"
            f"- **Areas:** {areas}\n"
            f"- **Executive summary:** {it.get('executive_summary') or '(none)'}\n\n"
            f"{it.get('description', '').strip()}\n"
        )
    return "\n".join(chunks).strip()
