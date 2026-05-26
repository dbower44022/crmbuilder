"""Field schema for the process CRUD dialogs (UI v0.4 slice D).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``,
following the v0.3 governance-entity pattern and mirroring
``_domain_schema.py`` / ``_entity_schema.py`` with process-specific
adjustments. The fields are in ``process.md`` section 3.2 order; the
schema keys are the parent-prefixed ``process_*`` names the REST bodies
expect.

Two process-specific shapes:

* ``process_domain_identifier`` is a required ``identifier_picker``
  backed by ``GET /domains`` (live records only). The picker shows
  ``DOM-NNN — Domain Name`` and stores the bare ``DOM-NNN``. Because
  ``compute_options`` needs the storage client, the schema is built by
  :func:`process_fields`, which closes over the client — unlike the
  static domain/entity schemas.
* ``process_classification`` replaces the conventional status combo
  (``process`` has no status field per DEC-056). ``compute_options``
  restricts the combo to valid successors of the record's current
  classification per the one-way ``unclassified`` gate.

Per DEC-067's create-then-attach flow there is no handoff multi-select
in either dialog — ``process_hands_off_to_process`` references attach
from the detail pane's ``ReferencesSection`` after the record exists.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    PROCESS_CLASSIFICATION_TRANSITIONS,
    PROCESS_CLASSIFICATIONS,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema
from crmbuilder_v2.ui.client import StorageClient

IDENTIFIER_RE = re.compile(r"^PROC-\d{3}$")

_PURPOSE_PLACEHOLDER = "One sentence — what does this process do?"

# Per ``process.md`` section 3.6.3, the classification-rationale field's
# placeholder varies by the currently-selected classification.
CLASSIFICATION_RATIONALE_PLACEHOLDERS: dict[str, str] = {
    "unclassified": "Pending classification — populate after Session 2",
    "mission_critical": (
        "Why this process is mission-critical — what mission failure "
        "looks like if it stops"
    ),
    "supporting": (
        "Why this process supports rather than drives the mission"
    ),
    "deferred": (
        "Why this process is deferred — what conditions would un-defer it"
    ),
}


def classification_choices(current: str | None) -> list[str]:
    """Return the classification values selectable from ``current``.

    The current value plus its valid successors per
    :data:`PROCESS_CLASSIFICATION_TRANSITIONS`. ``unclassified`` (the
    create-dialog starting point) yields all four values; each
    classified value yields itself plus the two other classified
    values — never ``unclassified`` (the one-way gate).
    """
    current = current or "unclassified"
    if current not in PROCESS_CLASSIFICATIONS:
        return sorted(PROCESS_CLASSIFICATIONS)
    return sorted(
        {current}
        | set(PROCESS_CLASSIFICATION_TRANSITIONS.get(current, frozenset()))
    )


def _domain_options(client: StorageClient):
    """Build the ``compute_options`` callable for the domain FK picker.

    Returns ``(identifier, name)`` tuples for every live domain, sorted
    by name so the picker reads alphabetically (``process.md`` section
    3.6.4 — the create dialog defaults to the first live domain
    alphabetically). A fetch failure degrades to an empty list; the
    base dialog disables the field and the user sees no options rather
    than a crash.
    """

    def compute(_state: dict[str, str]) -> list[tuple[str, str]]:
        try:
            domains = client.list_domains()
        except Exception:  # noqa: BLE001 — UI affordance; degrade to empty
            return []
        rows = [
            (d.get("domain_identifier") or "", d.get("domain_name") or "")
            for d in domains
            if d.get("domain_identifier")
        ]
        rows.sort(key=lambda pair: pair[1].lower())
        return rows

    return compute


_IDENTIFIER_FIELD = FieldSchema(
    key="process_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)


def _content_fields(client: StorageClient) -> list[FieldSchema]:
    return [
        FieldSchema(
            key="process_name", label="Name", widget="line", required=True
        ),
        FieldSchema(
            key="process_domain_identifier",
            label="Domain",
            widget="identifier_picker",
            required=True,
            compute_options=_domain_options(client),
        ),
        FieldSchema(
            key="process_purpose",
            label="Purpose",
            widget="text",
            required=True,
            placeholder=_PURPOSE_PLACEHOLDER,
        ),
        FieldSchema(
            key="process_classification",
            label="Classification",
            widget="combo",
            required=True,
            vocab=PROCESS_CLASSIFICATIONS,
            default="unclassified",
            compute_options=lambda state: classification_choices(
                state.get("process_classification")
            ),
        ),
        FieldSchema(
            key="process_classification_rationale",
            label="Classification rationale",
            widget="text",
            placeholder=CLASSIFICATION_RATIONALE_PLACEHOLDERS["unclassified"],
        ),
        FieldSchema(
            key="process_notes",
            label="Internal notes",
            widget="text",
        ),
    ]


# Phase 3 detailed-process-definition fields (v0.8, PI-005,
# ``process-v2.md`` §3.2.2). Spec'd as multi-line plain-text editors;
# each carries a placeholder per spec §3.6.3.
_PHASE3_FIELDS_SPECS: list[tuple[str, str, str]] = [
    (
        "process_steps",
        "Steps",
        "Numbered or bulleted list of process steps in execution order",
    ),
    (
        "process_triggers",
        "Triggers",
        "What initiates this process",
    ),
    (
        "process_outcomes",
        "Outcomes",
        (
            "What success looks like — state changes, records created, "
            "communications sent"
        ),
    ),
    (
        "process_edge_cases",
        "Edge Cases",
        "Known exceptions, error paths, retry semantics",
    ),
    (
        "process_frequency",
        "Frequency",
        "How often this process runs",
    ),
    (
        "process_duration_estimate",
        "Duration",
        "Typical wall-clock duration",
    ),
]


def _phase3_fields() -> list[FieldSchema]:
    """Phase 3 detailed-process fields (v0.8, PI-005, process-v2.md §3.6.4).

    Included in the Edit dialog only; the Create dialog omits these per
    spec §3.6.4 — Phase 3 content is post-create work.
    """
    return [
        FieldSchema(
            key=key,
            label=label,
            widget="text",
            placeholder=placeholder,
        )
        for key, label, placeholder in _PHASE3_FIELDS_SPECS
    ]


def process_fields(
    client: StorageClient,
    *,
    include_identifier: bool,
    include_phase3: bool = False,
) -> list[FieldSchema]:
    """Return a fresh copy of the process field schema.

    ``include_identifier`` adds the read-only ``process_identifier``
    field at the top — used by the edit dialog; the create dialog omits
    it because the identifier is server-assigned. The schema is built
    per-call because the domain-FK picker's ``compute_options`` closes
    over ``client``.

    ``include_phase3`` appends the six Phase 3 content-field editors
    (v0.8, PI-005, ``process-v2.md`` §3.6.4) — used by the Edit
    dialog; the Create dialog omits them so Phase 3 content is authored
    post-create per spec §3.6.4.
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(_content_fields(client))
    if include_phase3:
        fields.extend(_phase3_fields())
    return fields
