"""Process transitions section tests — PI-471, REQ-584.

The acceptance test renders the approved thirteen-row Mentor Application table
from the stored transition records and checks the section against the content
the product owner approved.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import decisions, references, transition
from crmbuilder_v2.render.process_transitions import (
    COLUMNS,
    NO_RECORD,
    build_transitions_model,
    fetch_transition_inputs,
    render_process_transitions,
)

from tests.crmbuilder_v2.access._mentor_application import (
    PRE_ACTIVE,
    seed_mentor_application,
    thirteen_rows,
)


def _seed_with_thirteen(session) -> dict:
    seed = seed_mentor_application(session)
    seed["transitions"] = [
        transition.create_transition(session, **row)
        for row in thirteen_rows(seed)
    ]
    return seed


def test_section_has_thirteen_rows_in_the_approved_order(v2_env):
    with session_scope() as s:
        seed = _seed_with_thirteen(s)
        model = build_transitions_model(
            fetch_transition_inputs(s, seed["process"])
        )

    assert len(model.rows) == 13
    assert model.process_name == "Mentor Application"
    assert model.status_field_label == "mentorStatus"

    moves = [(row.from_cell, row.to_cell) for row in model.rows]
    assert moves == [
        (NO_RECORD, "Candidate"),
        ("Prospect", "Candidate"),
        ("Declined", "Candidate"),
        ("Candidate", "Under Review"),
        ("Candidate", "Declined"),
        ("Under Review", "Accepted-Provisional"),
        ("Under Review", "Declined"),
        ("Accepted-Provisional", "Provisional"),
        ("Provisional", "Approved"),
        ("Provisional", "Declined"),
        ("Approved", "Active"),
        (", ".join(PRE_ACTIVE), "Dormant"),
        (", ".join(PRE_ACTIVE), "Declined"),
    ]


def test_who_column_reads_as_the_approved_table_does(v2_env):
    with session_scope() as s:
        seed = _seed_with_thirteen(s)
        model = build_transitions_model(
            fetch_transition_inputs(s, seed["process"])
        )

    who = [row.who_cell for row in model.rows]
    assert who[0] == "System, the intake application"
    assert who[3] == "Mentor Administration Team"
    assert who[5] == "Mentor Administration Team, first vote"
    assert who[7] == "System, the CRM"
    assert who[8] == "Mentor Administration Team, second vote"


def test_before_and_after_columns_name_records_in_plain_words(v2_env):
    with session_scope() as s:
        seed = _seed_with_thirteen(s)
        model = build_transitions_model(
            fetch_transition_inputs(s, seed["process"])
        )

    # Row 5: the decline reason is the only thing required.
    assert model.rows[4].before_cell == "declineReason"
    # Row 4: nothing is required and no condition is stated.
    assert model.rows[3].before_cell.startswith("Nothing;")
    # Row 1: the view and the message template are named, not their
    # identifiers alone.
    after = model.rows[0].after_cell
    assert "the Mentor candidates view" in after
    assert "the Mentor application confirmation message" in after
    assert seed["candidates_view"] in after
    # Row 6: the automation that runs on the save.
    assert "the Mentor email provisioning routine" in model.rows[5].after_cell
    # Row 11: the hand-off to another process.
    assert "hand-off to the Mentor Application process" in (
        model.rows[10].after_cell
    )
    # Row 4 has no automatic consequence at all.
    assert model.rows[3].after_cell == "None."


def test_by_hand_follow_up_has_its_own_column(v2_env):
    with session_scope() as s:
        seed = _seed_with_thirteen(s)
        model = build_transitions_model(
            fetch_transition_inputs(s, seed["process"])
        )

    assert model.rows[7].by_hand_cell.startswith("A member arranges training")
    # And it is not counted among the automatic consequences.
    assert "arranges training" not in model.rows[7].after_cell
    assert model.rows[3].by_hand_cell == "—"


def test_the_one_incomplete_row_is_marked_and_counted(v2_env):
    with session_scope() as s:
        seed = _seed_with_thirteen(s)
        model = build_transitions_model(
            fetch_transition_inputs(s, seed["process"])
        )

    assert model.incomplete_count == 1
    assert model.rows[8].incomplete is True
    assert "no record for this yet" in model.rows[8].after_cell


def test_settling_decisions_appear_in_their_column(v2_env):
    with session_scope() as s:
        seed = _seed_with_thirteen(s)
        first = seed["transitions"][3]["transition_identifier"]
        decision = decisions.create(
            s,
            title="Preliminary review moves a candidate to Under Review",
            decision_date="2026-09-07",
            status="Active",
            context="The Mentor Application interview.",
            decision="A team member moves the candidate to Under Review.",
            rationale="The review is judgment, not a checklist.",
            executive_summary=(
                "The product owner ruled that a member of the Mentor "
                "Administration Team moves a candidate to Under Review after "
                "a quick legitimacy check, with nothing required to be "
                "recorded first, because the preliminary review is judgment "
                "rather than a checklist."
            ),
        )["identifier"]
        references.create(
            s,
            source_type="decision",
            source_id=decision,
            target_type="transition",
            target_id=first,
            relationship="is_about",
        )
        model = build_transitions_model(
            fetch_transition_inputs(s, seed["process"])
        )

    assert decision in model.rows[3].decisions_cell
    assert "Preliminary review" in model.rows[3].decisions_cell
    assert model.rows[0].decisions_cell == "—"


def test_rendered_markdown_is_one_table_with_the_seven_columns(v2_env):
    with session_scope() as s:
        seed = _seed_with_thirteen(s)
        markdown = render_process_transitions(s, seed["process"])

    lines = markdown.splitlines()
    assert lines[0] == "## Status transitions"
    header = next(line for line in lines if line.startswith("| From |"))
    assert header == "| " + " | ".join(COLUMNS) + " |"
    body = [
        line
        for line in lines
        if line.startswith("| ") and not line.startswith("| From |")
    ]
    assert len(body) == 13
    assert "1 of these moves still describe" in markdown


def test_a_process_with_no_transitions_says_so(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        markdown = render_process_transitions(s, seed["process"])
    assert "has no transitions recorded" in markdown
