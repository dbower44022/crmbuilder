"""Field schema for the decisions CRUD dialogs.

Slice A migrates v0.1's ``_decision_form.py`` into a declarative
``FieldSchema`` list consumed by ``EntityCrudDialog``. The five
long-text body fields, the four required header fields, and the two
optional foreign-key fields all map cleanly onto schema entries; the
visible behavior is unchanged from v0.1 except for the calendar widget
on Decision Date.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import DECISION_STATUSES
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^DEC-\d{3,}$")
SUPERSEDES_RE = IDENTIFIER_RE
IDENTIFIER_HINT = "Identifier must be in the format DEC-NNN (e.g., DEC-018)."
SUPERSEDES_HINT = (
    "Must be in the format DEC-NNN (e.g., DEC-005), or empty to clear."
)


_DECISION_FIELDS_TEMPLATE: list[FieldSchema] = [
    FieldSchema(
        key="identifier",
        label="Identifier",
        widget="line",
        required=True,
        placeholder="DEC-NNN",
        regex=IDENTIFIER_RE,
        regex_hint=IDENTIFIER_HINT,
        read_only_on_edit=True,
    ),
    FieldSchema(key="title", label="Title", widget="line", required=True),
    FieldSchema(
        key="decision_date",
        label="Decision Date",
        widget="date",
        required=True,
    ),
    FieldSchema(
        key="status",
        label="Status",
        widget="combo",
        required=True,
        vocab=DECISION_STATUSES,
        default="Active",
    ),
    FieldSchema(
        key="executive_summary",
        label="Executive Summary",
        widget="text",
        # Required since PI-075 (migration 0023): the column is NOT NULL.
        required=True,
        min_length=200,
        max_length=800,
        placeholder=(
            "200-800 character audience-facing summary for non-technical "
            "reviewers."
        ),
    ),
    FieldSchema(key="context", label="Context", widget="text"),
    FieldSchema(key="decision", label="Decision", widget="text"),
    FieldSchema(key="rationale", label="Rationale", widget="text"),
    FieldSchema(
        key="alternatives_considered",
        label="Alternatives Considered",
        widget="text",
    ),
    FieldSchema(key="consequences", label="Consequences", widget="text"),
    FieldSchema(
        key="supersedes",
        label="Supersedes",
        widget="line",
        placeholder="DEC-NNN or empty",
        regex=SUPERSEDES_RE,
        regex_hint=SUPERSEDES_HINT,
        record_field_for_edit="supersedes_identifier",
        omit_when_empty_in_create=True,
    ),
    FieldSchema(
        key="superseded_by",
        label="Superseded By",
        widget="line",
        placeholder="DEC-NNN or empty",
        regex=SUPERSEDES_RE,
        regex_hint=SUPERSEDES_HINT,
        record_field_for_edit="superseded_by_identifier",
        omit_when_empty_in_create=True,
    ),
]


def decision_fields() -> list[FieldSchema]:
    """Return a fresh copy of the decision field schema.

    A copy is returned so callers (e.g., the edit dialog overriding
    ``read_only_on_edit``) can mutate without affecting other consumers.
    """
    return deepcopy(_DECISION_FIELDS_TEMPLATE)
