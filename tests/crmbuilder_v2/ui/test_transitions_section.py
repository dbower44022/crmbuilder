"""Desktop editing of a process's status moves — PI-471, REQ-585.

The acceptance test enters the thirteen approved Mentor Application rows
through the dialog without typing an identifier or a status value by hand, and
checks that reordering two rows changes the order the process returns.

The ``transition_client`` fixture wires a ``StorageClient`` over a real
FastAPI ``TestClient`` bound to the per-test database, so the section and the
dialog exercise the genuine desktop → REST → store path.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.transition_crud import (
    RECORD_CREATION_LABEL,
    TransitionDialog,
)
from crmbuilder_v2.ui.panels.processes import ProcessesPanel
from crmbuilder_v2.ui.widgets.transitions_section import (
    COLUMNS,
    NO_RECORD,
    TransitionsSection,
)
from fastapi.testclient import TestClient
from PySide6.QtCore import Qt

from tests.crmbuilder_v2.access._mentor_application import (
    MENTOR_STATUS_OPTIONS,
    PRE_ACTIVE,
)


@pytest.fixture
def transition_client(v2_env) -> StorageClient:
    client = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    client.set_active_engagement("ENG-001")
    return client


def _post(client: StorageClient, path: str, body: dict) -> dict:
    return client._request("POST", path, json_body=body)


@pytest.fixture
def seeded(transition_client) -> dict:
    client = transition_client
    dom = _post(
        client,
        "/domains",
        {
            "domain_name": "Mentor Recruiting",
            "domain_purpose": "Bring new mentors in.",
            "domain_description": "Recruiting and onboarding mentors.",
        },
    )["domain_identifier"]
    proc = _post(
        client,
        "/processes",
        {
            "process_name": "Mentor Application",
            "process_domain_identifier": dom,
            "process_purpose": "Application to active.",
        },
    )["process_identifier"]
    profile = _post(
        client,
        "/entities",
        {"entity_name": "MentorProfile", "entity_description": "A profile."},
    )["entity_identifier"]
    _post(
        client,
        "/references",
        {
            "source_type": "process",
            "source_id": proc,
            "target_type": "entity",
            "target_id": profile,
            "relationship": "process_touches_entity",
        },
    )
    status_field = _post(
        client,
        "/fields",
        {
            "field_belongs_to_entity_identifier": profile,
            "field_name": "mentorStatus",
            "field_description": "Where the mentor is.",
            "field_type": "enum",
            "field_options": [
                {"option_value": value, "option_order": index}
                for index, value in enumerate(MENTOR_STATUS_OPTIONS)
            ],
        },
    )["field_identifier"]
    decline_reason = _post(
        client,
        "/fields",
        {
            "field_belongs_to_entity_identifier": profile,
            "field_name": "declineReason",
            "field_description": "Why the applicant was declined.",
            "field_type": "text",
        },
    )["field_identifier"]
    team = _post(
        client,
        "/personas",
        {
            "persona_name": "Mentor Administration Team",
            "persona_role_summary": "Reviews and votes.",
        },
    )["persona_identifier"]
    _post(
        client,
        "/references",
        {
            "source_type": "process",
            "source_id": proc,
            "target_type": "persona",
            "target_id": team,
            "relationship": "process_performed_by_persona",
        },
    )
    return {
        "process": proc,
        "profile": profile,
        "status_field": status_field,
        "decline_reason": decline_reason,
        "team": team,
    }


def _tick(widget, values: list[str]) -> None:
    wanted = set(values)
    for row in range(widget.count()):
        item = widget.item(row)
        item.setCheckState(
            Qt.CheckState.Checked
            if item.data(Qt.ItemDataRole.UserRole) in wanted
            else Qt.CheckState.Unchecked
        )


def _enter_move(
    dialog: TransitionDialog,
    *,
    from_values: list[str] | None,
    to_value: str,
    actor: str,
    occasion: str = "",
    required_fields: list[str] | None = None,
) -> None:
    """Fill the form the way a user would — by choosing, not by typing."""
    dialog.status_field_combo.setCurrentIndex(0)
    dialog.from_creation_check.setChecked(from_values is None)
    if from_values is not None:
        _tick(dialog.from_values_list, from_values)
    dialog.to_value_combo.setCurrentIndex(
        dialog.to_value_combo.findData(to_value)
    )
    dialog.actor_combo.setCurrentIndex(dialog.actor_combo.findData(actor))
    dialog.occasion_edit.setText(occasion)
    _tick(dialog.required_fields_list, required_fields or [])


def test_dialog_offers_only_choices_drawn_from_the_store(
    transition_client, seeded, qtbot
):
    dialog = TransitionDialog(
        transition_client, process_identifier=seeded["process"]
    )
    qtbot.addWidget(dialog)
    # The status field list holds the process's choice fields, by name.
    assert dialog.status_field_combo.count() == 1
    assert dialog.status_field_combo.currentData() == seeded["status_field"]
    assert "mentorStatus" in dialog.status_field_combo.currentText()

    # Both value lists are the status field's options, nothing typed.
    values = [
        dialog.from_values_list.item(row).data(Qt.ItemDataRole.UserRole)
        for row in range(dialog.from_values_list.count())
    ]
    assert values == MENTOR_STATUS_OPTIONS
    assert dialog.to_value_combo.count() == len(MENTOR_STATUS_OPTIONS)

    # The actor list is the system plus the process's performing personas.
    actors = [
        dialog.actor_combo.itemData(row)
        for row in range(dialog.actor_combo.count())
    ]
    assert actors == ["system", seeded["team"]]

    # The required-field list is the fields on the entities this process
    # touches.
    required = [
        dialog.required_fields_list.item(row).data(Qt.ItemDataRole.UserRole)
        for row in range(dialog.required_fields_list.count())
    ]
    assert set(required) == {seeded["status_field"], seeded["decline_reason"]}


def test_ticking_the_creation_box_disables_the_from_values(
    transition_client, seeded, qtbot
):
    dialog = TransitionDialog(
        transition_client, process_identifier=seeded["process"]
    )
    qtbot.addWidget(dialog)
    assert RECORD_CREATION_LABEL in dialog.from_creation_check.text()
    assert dialog.from_values_list.isEnabled() is True
    dialog.from_creation_check.setChecked(True)
    assert dialog.from_values_list.isEnabled() is False
    assert dialog.body()["transition_from_kind"] == "record_creation"
    assert dialog.body()["transition_from_values"] == []


def test_a_refused_check_is_shown_in_plain_words(
    transition_client, seeded, qtbot
):
    """A move the store refuses leaves the form open with the reason shown,
    in the words the store gave, rather than a silent failure."""
    dialog = TransitionDialog(
        transition_client, process_identifier=seeded["process"]
    )
    qtbot.addWidget(dialog)
    _enter_move(
        dialog,
        from_values=["Candidate", "Under Review"],
        to_value="Under Review",
        actor=seeded["team"],
    )
    dialog._on_save()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert not dialog.message.isHidden()
    assert dialog.message.text() == (
        "'Under Review' is both the value moved to and a value moved from"
    )


def test_thirteen_rows_entered_through_the_dialog(
    transition_client, seeded, qtbot
):
    """REQ-585: the approved table goes in without typing an identifier or a
    status value by hand."""
    team = seeded["team"]
    decline_reason = [seeded["decline_reason"]]
    rows = [
        (None, "Candidate", "system", "the intake application", None),
        (["Prospect"], "Candidate", "system", "the intake application", None),
        (["Declined"], "Candidate", "system", "the intake application", None),
        (["Candidate"], "Under Review", team, "", None),
        (["Candidate"], "Declined", team, "", decline_reason),
        (["Under Review"], "Accepted-Provisional", team, "first vote", None),
        (["Under Review"], "Declined", team, "first vote", decline_reason),
        (["Accepted-Provisional"], "Provisional", "system", "the CRM", None),
        (["Provisional"], "Approved", team, "second vote", None),
        (["Provisional"], "Declined", team, "second vote", decline_reason),
        (["Approved"], "Active", team, "", None),
        (list(PRE_ACTIVE), "Dormant", team, "", None),
        (list(PRE_ACTIVE), "Declined", team, "withdrawal", decline_reason),
    ]
    for from_values, to_value, actor, occasion, required in rows:
        dialog = TransitionDialog(
            transition_client, process_identifier=seeded["process"]
        )
        qtbot.addWidget(dialog)
        _enter_move(
            dialog,
            from_values=from_values,
            to_value=to_value,
            actor=actor,
            occasion=occasion,
            required_fields=required,
        )
        dialog._on_save()
        assert dialog.saved_record is not None, (to_value, dialog.message.text())

    stored = transition_client.list_transitions(
        process_identifier=seeded["process"]
    )
    assert len(stored) == 13
    assert [r["transition_order"] for r in stored] == list(range(13))
    assert stored[0]["transition_from_kind"] == "record_creation"
    assert stored[11]["transition_from_values"] == PRE_ACTIVE


def test_section_shows_the_moves_and_reordering_changes_the_order(
    transition_client, seeded, qtbot
):
    for from_values, to_value in (
        (["Candidate"], "Under Review"),
        (["Under Review"], "Declined"),
    ):
        dialog = TransitionDialog(
            transition_client, process_identifier=seeded["process"]
        )
        qtbot.addWidget(dialog)
        _enter_move(
            dialog,
            from_values=from_values,
            to_value=to_value,
            actor=seeded["team"],
        )
        dialog._on_save()

    section = TransitionsSection(
        seeded["process"], client=transition_client
    )
    qtbot.addWidget(section)
    assert section.table.columnCount() == len(COLUMNS)
    assert section.table.rowCount() == 2
    assert section.table.item(0, 0).text() == "Candidate"
    assert section.table.item(0, 2).text() == "Mentor Administration Team"
    assert "2 moves" in section.summary.text()

    before = [r["transition_identifier"] for r in section._rows]
    section.table.selectRow(1)
    section.move_selected(-1)
    after = transition_client.list_transitions(
        process_identifier=seeded["process"]
    )
    assert [r["transition_identifier"] for r in after] == [
        before[1],
        before[0],
    ]
    assert section.table.item(0, 1).text() == "Declined"


def test_a_creation_move_reads_as_no_record_in_the_table(
    transition_client, seeded, qtbot
):
    dialog = TransitionDialog(
        transition_client, process_identifier=seeded["process"]
    )
    qtbot.addWidget(dialog)
    _enter_move(
        dialog,
        from_values=None,
        to_value="Candidate",
        actor="system",
        occasion="the intake application",
    )
    dialog._on_save()
    section = TransitionsSection(seeded["process"], client=transition_client)
    qtbot.addWidget(section)
    assert section.table.item(0, 0).text() == NO_RECORD
    assert section.table.item(0, 2).text() == "System, the intake application"


def test_an_incomplete_move_is_counted_in_the_summary(
    transition_client, seeded, qtbot
):
    dialog = TransitionDialog(
        transition_client, process_identifier=seeded["process"]
    )
    qtbot.addWidget(dialog)
    _enter_move(
        dialog,
        from_values=["Provisional"],
        to_value="Approved",
        actor=seeded["team"],
    )
    dialog.consequence_notes_edit.setPlainText(
        "Mentor login provisioning runs on the save."
    )
    dialog._on_save()
    section = TransitionsSection(seeded["process"], client=transition_client)
    qtbot.addWidget(section)
    assert "1 still" in section.summary.text()
    assert "no record yet" in section.table.item(0, 4).text()


def test_the_section_appears_on_the_process_detail_view(
    transition_client, seeded, qtbot
):
    panel = ProcessesPanel(transition_client)
    qtbot.addWidget(panel)
    panel.refresh()
    record = transition_client.get_process(seeded["process"])
    extras = panel.fetch_detail_extras(record)
    detail = panel.render_detail(record, extras)
    found = detail.findChild(TransitionsSection, "process_transitions_section")
    assert found is not None
