"""Session type variations for CRM Builder Automation prompts.

Implements L2 PRD Section 10.6:
- 10.6.1 Initial sessions — standard prompt
- 10.6.2 Revision sessions — includes revision reason and prior output
- 10.6.3 Clarification sessions — includes clarification topic, minimal instructions
"""

import sqlite3

VALID_SESSION_TYPES = frozenset({"initial", "revision", "clarification"})


def build_session_header(
    item_type: str,
    item_description: str,
    session_type: str,
    phase_number: int,
    phase_name: str,
    *,
    revision_reason: str | None = None,
    clarification_topic: str | None = None,
) -> str:
    """Build the Session Header text (Section 1 of the prompt).

    :param item_type: The work item's item_type.
    :param item_description: Human-readable description (e.g. "Contact Entity PRD").
    :param session_type: "initial", "revision", or "clarification".
    :param phase_number: The phase number (1-12).
    :param phase_name: The phase name (e.g. "Entity Definition").
    :param revision_reason: Required for revision sessions.
    :param clarification_topic: Required for clarification sessions.
    :returns: The header text.
    """
    lines = [
        "# Session Header",
        "",
        f"**Work Item Type:** {item_type}",
        f"**Work Item:** {item_description}",
        f"**Session Type:** {session_type}",
        f"**Phase:** {phase_number} — {phase_name}",
    ]

    if session_type == "revision" and revision_reason:
        lines.append("")
        lines.append(f"**Revision Reason:** {revision_reason}")

    if session_type == "clarification" and clarification_topic:
        lines.append("")
        lines.append(f"**Clarification Topic:** {clarification_topic}")

    return "\n".join(lines)


def get_session_instructions_preamble(session_type: str) -> str | None:
    """Return the preamble text to prepend to the interview guide.

    For initial sessions: None (use the guide as-is).
    For revision sessions: a preamble instructing the AI to treat existing
        data as baseline and focus on specified changes.
    For clarification sessions: minimal instructions replacing the full guide.

    :param session_type: "initial", "revision", or "clarification".
    :returns: Preamble text or None.
    """
    if session_type == "initial":
        return None

    if session_type == "revision":
        return (
            "**REVISION SESSION**\n\n"
            "This is a revision of a previously completed work item. The database "
            "already contains the results of the initial session. Treat the existing "
            "data as your baseline. Focus on the changes specified in the revision "
            "reason above rather than conducting a full session from scratch. Produce "
            "a complete structured output that reflects the revised state — the Import "
            "Processor will apply it as updates to existing records."
        )

    if session_type == "clarification":
        return (
            "**CLARIFICATION SESSION**\n\n"
            "The implementor has a follow-up question about a completed session. "
            "Answer based on the provided context. Do NOT conduct a full interview. "
            "If the clarification reveals an error or needed correction, produce a "
            "structured output block following the standard format. If no correction "
            "is needed, you may omit the JSON block entirely."
        )

    return None


def get_prior_output_for_revision(
    conn: sqlite3.Connection,
    work_item_id: int,
) -> str | None:
    """Fetch the most recent structured_output for a work item.

    For revision and clarification sessions, the prior output is included
    in the context so the AI can reference what was produced.

    :param conn: Open client database connection.
    :param work_item_id: The WorkItem.id.
    :returns: The structured_output text, or None if not available.
    """
    row = conn.execute(
        "SELECT structured_output FROM AISession "
        "WHERE work_item_id = ? AND structured_output IS NOT NULL "
        "ORDER BY id DESC LIMIT 1",
        (work_item_id,),
    ).fetchone()
    return row[0] if row else None


def validate_session_params(
    session_type: str,
    revision_reason: str | None = None,
    clarification_topic: str | None = None,
) -> None:
    """Validate session type parameters.

    :raises ValueError: If session_type is invalid or required params are missing.
    """
    if session_type not in VALID_SESSION_TYPES:
        raise ValueError(
            f"Invalid session_type '{session_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_SESSION_TYPES))}"
        )
    if session_type == "revision" and not revision_reason:
        raise ValueError(
            "revision_reason is required for revision sessions"
        )
    if session_type == "clarification" and not clarification_topic:
        raise ValueError(
            "clarification_topic is required for clarification sessions"
        )
