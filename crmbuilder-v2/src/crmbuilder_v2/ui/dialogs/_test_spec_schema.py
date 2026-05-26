"""Field schema for the test_spec CRUD dialogs (PI-004 cohort closer, v0.5+).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``,
following the v0.3 governance-entity pattern and mirroring
``_manual_config_schema.py``. Fields are in ``test_spec.md`` §3.2 order
within the three-section grouping; the schema keys are the parent-
prefixed ``test_spec_*`` names the REST bodies expect.

The create dialog omits ``test_spec_identifier`` (server-assigned);
the edit dialog includes it as a read-only field. Per spec §3.6.4's
create-then-attach flow there are no reference multi-selects in either
dialog — references attach from the detail pane's
``ReferencesSection`` after the test_spec record exists.

**Dual-axis state (§3.4.3) shaped into dialog widgets.**

* ``test_spec_status`` carries a ``compute_options`` callback that
  restricts the combo to the valid successors of the record's current
  status per :data:`TEST_SPEC_STATUS_TRANSITIONS` (propose-verify gate).
* ``test_spec_last_run_outcome`` carries a ``compute_options`` callback
  returning the full unconstrained four-value vocabulary — outcomes
  are unrestricted per §3.4.2; the user may freely re-record any
  outcome.

**Datetime widget deferral.** ``FieldSchema`` does not currently
support ``widget="datetime"``; the build prompt §12a's fallback —
``widget="line"`` with an ISO-8601 placeholder — is used here.
``test_spec_last_run_at`` is presented as a free-form line field with
guidance text explaining the cross-field invariant. The server enforces
the §3.4.4 cross-field invariant regardless of what the dialog allows
the user to type.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    TEST_SPEC_RUN_OUTCOMES,
    TEST_SPEC_STATUS_TRANSITIONS,
    TEST_SPEC_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^TST-\d{3}$")

_DESCRIPTION_PLACEHOLDER = "What does this test verify?"
_SETUP_PLACEHOLDER = (
    "Preconditions — what must be true before the test runs?"
)
_STEPS_PLACEHOLDER = "Numbered steps to execute the test"
_EXPECTED_PLACEHOLDER = (
    "Expected results — what must be true after the steps execute?"
)
_LAST_RUN_AT_PLACEHOLDER = (
    "ISO 8601 UTC timestamp; auto-set to now when outcome moves to a "
    "run state"
)
_LAST_RUN_NOTES_PLACEHOLDER = (
    "Notes from the most recent run; auto-cleared when outcome returns "
    "to not_run"
)


def status_choices(current: str | None) -> list[str]:
    """Return the methodology-lifecycle status values selectable from ``current``.

    The current value plus its valid successors per
    :data:`TEST_SPEC_STATUS_TRANSITIONS`. ``candidate`` (the create-
    dialog starting point) yields three values. The propose-verify
    gate means no successor list includes ``candidate``, so once out
    of ``candidate`` it is unreachable via the dialog.
    """
    current = current or "candidate"
    if current not in TEST_SPEC_STATUSES:
        return sorted(TEST_SPEC_STATUSES)
    return sorted(
        {current}
        | set(TEST_SPEC_STATUS_TRANSITIONS.get(current, frozenset()))
    )


def run_outcome_choices(current: str | None) -> list[str]:
    """Return the full four-value outcome vocabulary unconditionally.

    Per spec §3.4.2 outcome transitions are UNRESTRICTED — the combo
    always offers the full four-value set regardless of the current
    outcome value. Stable sort matches the alphabetical CHECK
    constraint order.
    """
    return sorted(TEST_SPEC_RUN_OUTCOMES)


_IDENTIFIER_FIELD = FieldSchema(
    key="test_spec_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    # Identity-and-methodology block (§3.6.3)
    FieldSchema(
        key="test_spec_name",
        label="Name",
        widget="line",
        required=True,
    ),
    FieldSchema(
        key="test_spec_description",
        label="Description",
        widget="text",
        required=True,
        placeholder=_DESCRIPTION_PLACEHOLDER,
    ),
    # Test body block (§3.6.3)
    FieldSchema(
        key="test_spec_setup",
        label="Setup",
        widget="text",
        placeholder=_SETUP_PLACEHOLDER,
    ),
    FieldSchema(
        key="test_spec_steps",
        label="Steps",
        widget="text",
        required=True,
        placeholder=_STEPS_PLACEHOLDER,
    ),
    FieldSchema(
        key="test_spec_expected",
        label="Expected results",
        widget="text",
        required=True,
        placeholder=_EXPECTED_PLACEHOLDER,
    ),
    # Internal notes (§3.6.3 — rendered as a collapsible section in
    # the detail pane; here in the dialog it is just another field).
    FieldSchema(
        key="test_spec_notes",
        label="Internal notes",
        widget="text",
    ),
    # Methodology lifecycle (restricted transitions)
    FieldSchema(
        key="test_spec_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=TEST_SPEC_STATUSES,
        default="candidate",
        compute_options=lambda state: status_choices(
            state.get("test_spec_status")
        ),
    ),
    # Last run block (§3.6.3) — outcome is unrestricted; last_run_at
    # and last_run_notes participate in the §3.4.4 cross-field invariant.
    FieldSchema(
        key="test_spec_last_run_outcome",
        label="Last run outcome",
        widget="combo",
        required=True,
        vocab=TEST_SPEC_RUN_OUTCOMES,
        default="not_run",
        compute_options=lambda state: run_outcome_choices(
            state.get("test_spec_last_run_outcome")
        ),
    ),
    FieldSchema(
        key="test_spec_last_run_at",
        label="Last run at",
        widget="line",
        placeholder=_LAST_RUN_AT_PLACEHOLDER,
        omit_when_empty_in_create=True,
    ),
    FieldSchema(
        key="test_spec_last_run_notes",
        label="Last run notes",
        widget="text",
    ),
]


def test_spec_fields(*, include_identifier: bool) -> list[FieldSchema]:
    """Return a fresh copy of the test_spec field schema.

    ``include_identifier`` adds the read-only ``test_spec_identifier``
    field at the top — used by the edit dialog; the create dialog omits
    it because the identifier is server-assigned.
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
