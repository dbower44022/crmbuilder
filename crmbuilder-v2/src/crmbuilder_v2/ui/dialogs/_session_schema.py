"""Field schema for the Sessions create dialog (v0.3 slice D).

Per DEC-013 / DEC-034, sessions are append-only and user-authorable
through the UI. The nine-field schema mirrors PRD §2.4. The identifier
is auto-assigned at dialog-open time by ``SessionCreateDialog`` and
read-only at the field level. ``topics_covered`` and
``conversation_reference`` carry placeholder hints aligned with the
DEC-025 conventions.
"""

from __future__ import annotations

from datetime import date

from crmbuilder_v2.access.vocab import SESSION_STATUSES
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

SESSION_TOPICS_PLACEHOLDER = (
    'Seed prompt: "..."\n\n'
    "Followed by structured discussion summary "
    "(per DEC-025 conventions)."
)

SESSION_CONVERSATION_REF_PLACEHOLDER = (
    "Descriptive text identifying the conversation by its outputs "
    "(PRDs, prompts, decisions). No transcript URL "
    "(per DEC-025)."
)


def session_fields_create(
    *, identifier: str, today_text: str | None = None
) -> list[FieldSchema]:
    """Return a fresh nine-field schema for ``SessionCreateDialog``.

    Computed per dialog-open: ``identifier`` is the auto-assigned
    next ``SES-NNN`` and ``today_text`` is the default for
    ``session_date``. ``today_text`` defaults to the current date
    in MM-DD-YY format when omitted.
    """
    if today_text is None:
        today_text = date.today().strftime("%m-%d-%y")

    return [
        FieldSchema(
            key="identifier",
            label="Identifier",
            widget="line",
            required=True,
            read_only=True,
            default=identifier,
        ),
        FieldSchema(
            key="session_date",
            label="Session Date",
            widget="date",
            required=True,
        ),
        FieldSchema(
            key="status",
            label="Status",
            widget="combo",
            required=True,
            vocab=SESSION_STATUSES,
            default="Complete",
        ),
        FieldSchema(
            key="title",
            label="Title",
            widget="line",
            required=True,
        ),
        FieldSchema(
            key="summary",
            label="Summary",
            widget="text",
            required=True,
        ),
        FieldSchema(
            key="topics_covered",
            label="Topics Covered",
            widget="text",
            required=True,
            placeholder=SESSION_TOPICS_PLACEHOLDER,
        ),
        FieldSchema(
            key="artifacts_produced",
            label="Artifacts Produced",
            widget="text",
            required=True,
        ),
        FieldSchema(
            key="in_flight_at_end",
            label="In-Flight at End",
            widget="text",
            required=False,
        ),
        FieldSchema(
            key="conversation_reference",
            label="Conversation Reference",
            widget="text",
            required=True,
            placeholder=SESSION_CONVERSATION_REF_PLACEHOLDER,
        ),
    ]
