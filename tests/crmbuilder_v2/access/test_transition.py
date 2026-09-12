"""Transition repository tests — PI-471, REQ-577 to REQ-586.

Covers the schema shape, the vocabulary registration, the checks of REQ-578 to
REQ-581 (each refusal naming its check), the actor rules, the lifecycle and
soft-delete round-trip of REQ-582, ordering and reordering, and the
incompleteness report. The acceptance test is the thirteen-row Mentor
Application table in ``_mentor_application``.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import field, transition
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    RELATIONSHIP_RULES,
    TRANSITION_ACTOR_KINDS,
    TRANSITION_CONSEQUENCE_PREFIXES,
    TRANSITION_FROM_KINDS,
    TRANSITION_STATUSES,
)
from sqlalchemy import inspect

from tests.crmbuilder_v2.access._mentor_application import (
    PRE_ACTIVE,
    seed_mentor_application,
    thirteen_rows,
)

_EXPECTED_COLUMNS = {
    "transition_identifier": "VARCHAR",
    "transition_process": "VARCHAR",
    "transition_field": "VARCHAR",
    "transition_from_kind": "VARCHAR",
    "transition_from_values": "JSON",
    "transition_to_value": "TEXT",
    "transition_actor_kind": "VARCHAR",
    "transition_actor_persona": "VARCHAR",
    "transition_actor_occasion": "TEXT",
    "transition_required_fields": "JSON",
    "transition_precondition": "TEXT",
    "transition_consequences": "JSON",
    "transition_consequence_notes": "TEXT",
    "transition_manual_follow_up": "TEXT",
    "transition_order": "INTEGER",
    "transition_description": "TEXT",
    "transition_notes": "TEXT",
    "transition_status": "VARCHAR",
    "transition_created_at": "DATETIME",
    "transition_updated_at": "DATETIME",
    "transition_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


def _error_codes(exc_info) -> set[str]:
    return {e.code for e in exc_info.value.errors}


# ---------------------------------------------------------------------------
# Schema and vocabulary
# ---------------------------------------------------------------------------


def test_transitions_table_has_expected_columns_with_correct_types(v2_env):
    insp = inspect(get_engine())
    assert "transitions" in insp.get_table_names()
    columns = {c["name"]: c for c in insp.get_columns("transitions")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("transitions")
    assert pk["constrained_columns"] == [
        "transition_identifier",
        "engagement_id",
    ]


def test_transition_registered_in_vocab():
    assert "transition" in ENTITY_TYPES
    assert "transition" in CHANGE_LOG_ENTITY_TYPES
    assert TRANSITION_FROM_KINDS == {"record_creation", "values"}
    assert TRANSITION_ACTOR_KINDS == {"persona", "system"}
    assert TRANSITION_STATUSES == {
        "candidate",
        "confirmed",
        "deferred",
        "rejected",
    }
    assert set(TRANSITION_CONSEQUENCE_PREFIXES) == {
        "AUT",
        "MSG",
        "VEW",
        "TRN",
        "PROC",
    }


def test_four_inbound_reference_kinds_are_admitted():
    """REQ-583: a view, an automation, a test specification and a requirement
    can each reference an individual transition."""
    expected = {
        "view": "view_offers_transition",
        "automation": "automation_triggered_by_transition",
        "test_spec": "test_spec_exercises_transition",
        "requirement": "requirement_touches_transition",
    }
    for source_type, kind in expected.items():
        assert kind in RELATIONSHIP_RULES[(source_type, "transition")]
    # The kinds are directional: a transition does not source them.
    for kind in expected.values():
        assert kind not in RELATIONSHIP_RULES[("transition", "view")]


# ---------------------------------------------------------------------------
# The acceptance test — the approved thirteen rows
# ---------------------------------------------------------------------------


def test_thirteen_mentor_application_rows_are_entered_and_read_back(v2_env):
    """REQ-577: the approved table is entered as transition records, and
    reading that process returns thirteen transitions matching it."""
    with session_scope() as s:
        seed = seed_mentor_application(s)
        rows = thirteen_rows(seed)
        created = [transition.create_transition(s, **row) for row in rows]

    assert len(created) == 13

    with session_scope() as s:
        stored = transition.list_transitions(s, process=seed["process"])

    assert len(stored) == 13
    # The process returns them as one ordered list, in the approved order.
    assert [r["transition_order"] for r in stored] == list(range(13))

    moves = [
        (r["transition_from_kind"], tuple(r["transition_from_values"]), r["transition_to_value"])
        for r in stored
    ]
    assert moves == [
        ("record_creation", (), "Candidate"),
        ("values", ("Prospect",), "Candidate"),
        ("values", ("Declined",), "Candidate"),
        ("values", ("Candidate",), "Under Review"),
        ("values", ("Candidate",), "Declined"),
        ("values", ("Under Review",), "Accepted-Provisional"),
        ("values", ("Under Review",), "Declined"),
        ("values", ("Accepted-Provisional",), "Provisional"),
        ("values", ("Provisional",), "Approved"),
        ("values", ("Provisional",), "Declined"),
        ("values", ("Approved",), "Active"),
        ("values", tuple(PRE_ACTIVE), "Dormant"),
        ("values", tuple(PRE_ACTIVE), "Declined"),
    ]

    # Who makes each move, as the approved Who column reads.
    team = seed["team_persona"]
    actors = [
        (r["transition_actor_kind"], r["transition_actor_persona"], r["transition_actor_occasion"])
        for r in stored
    ]
    assert actors[0] == ("system", None, "the intake application")
    assert actors[3] == ("persona", team, None)
    assert actors[5] == ("persona", team, "first vote")
    assert actors[7] == ("system", None, "the CRM")
    assert actors[8] == ("persona", team, "second vote")

    # The two set rows are stored as one rule each, with five members.
    assert stored[11]["transition_from_values"] == PRE_ACTIVE
    assert stored[12]["transition_from_values"] == PRE_ACTIVE

    # Every row names its rulings, as the approved Ruling column does.
    assert all(r["transition_notes"] for r in stored)


def test_thirteen_rows_carry_their_preconditions_and_consequences(v2_env):
    """REQ-580 and REQ-581 against the approved table's two right-hand
    columns."""
    with session_scope() as s:
        seed = seed_mentor_application(s)
        for row in thirteen_rows(seed):
            transition.create_transition(s, **row)
        stored = transition.list_transitions(s, process=seed["process"])

    f = seed["fields"]
    # Row 5: the decline reason is required before a preliminary decline.
    assert stored[4]["transition_required_fields"] == [f["decline_reason"]]
    # Row 11: three fields must be present before Active.
    assert stored[10]["transition_required_fields"] == [
        f["chapter_email"],
        f["crm_login"],
        f["contact_assignment"],
    ]
    # Row 8: the mailbox condition is stated in words.
    assert "chapter mailbox" in stored[7]["transition_precondition"]

    # Row 1 references a view and a message template; row 6 an automation;
    # row 11 hands off to a process.
    assert stored[0]["transition_consequences"] == [
        seed["candidates_view"],
        seed["confirmation_template"],
    ]
    assert stored[5]["transition_consequences"] == [
        seed["provisioning_automation"]
    ]
    assert stored[10]["transition_consequences"] == [seed["process"]]

    # By-hand follow-up is kept in its own text, separate from the automatic
    # consequences, and never counted as incomplete.
    assert stored[7]["transition_manual_follow_up"].startswith("A member")
    assert stored[7]["transition_consequence_notes"] is None


def test_incompleteness_report_names_only_the_row_still_owed_a_record(v2_env):
    """REQ-581: the report lists the transitions whose consequences are still
    words, and nothing else."""
    with session_scope() as s:
        seed = seed_mentor_application(s)
        for row in thirteen_rows(seed):
            transition.create_transition(s, **row)
        report = transition.incomplete_transitions(s, process=seed["process"])

    assert len(report) == 1
    entry = report[0]
    assert entry["transition_to_value"] == "Approved"
    assert "login provisioning" in entry["transition_consequence_notes"]
    assert set(entry) == {
        "transition_identifier",
        "transition_process",
        "transition_from_kind",
        "transition_from_values",
        "transition_to_value",
        "transition_consequence_notes",
    }


# ---------------------------------------------------------------------------
# The endpoint checks (REQ-578)
# ---------------------------------------------------------------------------


def _base_row(seed: dict, **overrides) -> dict:
    row = {
        "process": seed["process"],
        "field": seed["status_field"],
        "from_values": ["Candidate"],
        "to_value": "Under Review",
        "actor_kind": "system",
    }
    row.update(overrides)
    return row


def test_to_value_must_be_an_option_of_the_status_field(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s, **_base_row(seed, to_value="Retired")
            )
    assert "to_value_not_an_option" in _error_codes(exc)


def test_from_value_must_be_an_option_of_the_status_field(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s, **_base_row(seed, from_values=["Retired"])
            )
    assert "from_value_not_an_option" in _error_codes(exc)


def test_to_value_may_not_appear_among_the_from_values(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s,
                **_base_row(
                    seed,
                    from_values=["Candidate", "Under Review"],
                    to_value="Under Review",
                ),
            )
    assert "to_value_in_from_values" in _error_codes(exc)


def test_status_field_must_be_a_choice_field(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s, **_base_row(seed, field=seed["fields"]["decline_reason"])
            )
    assert "field_not_a_choice" in _error_codes(exc)


def test_status_field_entity_must_be_touched_by_the_process(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        other = field.create_field(
            s,
            field_belongs_to_entity_identifier=seed["unrelated_entity"],
            name="invoiceStage",
            description="Stage of an invoice.",
            type="enum",
            options=[{"option_value": "Draft", "option_order": 0}],
        )["field_identifier"]
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s,
                **_base_row(
                    seed,
                    field=other,
                    from_values=["Draft"],
                    to_value="Draft",
                ),
            )
    assert "field_entity_untouched" in _error_codes(exc)


def test_from_creation_move_takes_no_from_values(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s,
                **_base_row(
                    seed, from_kind="record_creation", from_values=["Candidate"]
                ),
            )
    assert "invalid_value" in _error_codes(exc)


def test_from_values_move_needs_at_least_one_value(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(s, **_base_row(seed, from_values=[]))
    assert "invalid_value" in _error_codes(exc)


def test_owning_process_must_exist_and_be_live(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(s, **_base_row(seed, process="PROC-999"))
    assert "invalid_process" in _error_codes(exc)


# ---------------------------------------------------------------------------
# The actor (REQ-579)
# ---------------------------------------------------------------------------


def test_persona_actor_must_name_a_live_persona(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s,
                **_base_row(
                    seed, actor_kind="persona", actor_persona="PER-999"
                ),
            )
    assert "invalid_persona" in _error_codes(exc)


def test_persona_actor_is_required_when_the_actor_is_a_persona(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s, **_base_row(seed, actor_kind="persona")
            )
    assert "missing_or_empty" in _error_codes(exc)


def test_system_actor_does_not_name_a_persona(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s,
                **_base_row(
                    seed,
                    actor_kind="system",
                    actor_persona=seed["team_persona"],
                ),
            )
    assert "forbidden_for_system_actor" in _error_codes(exc)


def test_actor_kind_must_be_in_vocab(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s, **_base_row(seed, actor_kind="committee")
            )
    assert "invalid_value" in _error_codes(exc)


# ---------------------------------------------------------------------------
# Preconditions and consequences (REQ-580, REQ-581)
# ---------------------------------------------------------------------------


def test_required_field_entity_must_be_touched_by_the_process(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s,
                **_base_row(
                    seed, required_fields=[seed["fields"]["unrelated"]]
                ),
            )
    assert "required_field_entity_untouched" in _error_codes(exc)


def test_a_required_field_on_another_touched_entity_is_accepted(v2_env):
    """REQ-580: the field may belong to the transition's entity or to another
    entity the process touches — the submission entity, here."""
    with session_scope() as s:
        seed = seed_mentor_application(s)
        row = transition.create_transition(
            s,
            **_base_row(
                seed, required_fields=[seed["fields"]["raw_form_content"]]
            ),
        )
    assert row["transition_required_fields"] == [
        seed["fields"]["raw_form_content"]
    ]


def test_consequence_must_name_a_referenceable_record_type(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s, **_base_row(seed, consequences=[seed["status_field"]])
            )
    assert "invalid_consequence" in _error_codes(exc)


def test_consequence_record_must_exist(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        with pytest.raises(UnprocessableError) as exc:
            transition.create_transition(
                s, **_base_row(seed, consequences=["AUT-999"])
            )
    assert "invalid_consequence" in _error_codes(exc)


def test_a_transition_may_be_the_consequence_of_another(v2_env):
    """REQ-581 / DEC-1070: row 6 of the approved table chains to row 8."""
    with session_scope() as s:
        seed = seed_mentor_application(s)
        chained = transition.create_transition(
            s,
            **_base_row(
                seed,
                from_values=["Accepted-Provisional"],
                to_value="Provisional",
            ),
        )
        first = transition.create_transition(
            s,
            **_base_row(
                seed,
                from_values=["Under Review"],
                to_value="Accepted-Provisional",
                consequences=[chained["transition_identifier"]],
            ),
        )
    assert first["transition_consequences"] == [
        chained["transition_identifier"]
    ]


# ---------------------------------------------------------------------------
# Lifecycle, ordering, soft-delete (REQ-582, REQ-585)
# ---------------------------------------------------------------------------


def test_new_transition_is_candidate_and_moves_as_a_design_record_does(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        row = transition.create_transition(s, **_base_row(seed))
        identifier = row["transition_identifier"]
        assert row["transition_status"] == "candidate"
        confirmed = transition.patch_transition(
            s, identifier, status="confirmed"
        )
        assert confirmed["transition_status"] == "confirmed"
        with pytest.raises(StatusTransitionError):
            transition.patch_transition(s, identifier, status="rejected")


def test_soft_delete_and_restore_round_trip(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        identifier = transition.create_transition(s, **_base_row(seed))[
            "transition_identifier"
        ]
        transition.delete_transition(s, identifier)
        assert transition.get_transition(s, identifier) is None
        assert (
            transition.get_transition(s, identifier, include_deleted=True)
            is not None
        )
        transition.restore_transition(s, identifier)
        assert transition.get_transition(s, identifier) is not None
        with pytest.raises(UnprocessableError):
            transition.restore_transition(s, identifier)


def test_order_defaults_to_the_end_of_the_process_list(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        first = transition.create_transition(s, **_base_row(seed))
        second = transition.create_transition(
            s, **_base_row(seed, to_value="Declined")
        )
    assert first["transition_order"] == 0
    assert second["transition_order"] == 1


def test_reordering_changes_the_order_the_process_returns(v2_env):
    """REQ-585: reordering two rows changes the order the process returns."""
    with session_scope() as s:
        seed = seed_mentor_application(s)
        for row in thirteen_rows(seed):
            transition.create_transition(s, **row)
        before = [
            r["transition_identifier"]
            for r in transition.list_transitions(s, process=seed["process"])
        ]
        swapped = [before[1], before[0], *before[2:]]
        after = transition.reorder_transitions(s, seed["process"], swapped)

    assert [r["transition_identifier"] for r in after] == swapped
    assert [r["transition_order"] for r in after] == list(range(13))


def test_reorder_refuses_a_partial_list(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        rows = [
            transition.create_transition(s, **_base_row(seed)),
            transition.create_transition(
                s, **_base_row(seed, to_value="Declined")
            ),
        ]
        with pytest.raises(UnprocessableError) as exc:
            transition.reorder_transitions(
                s, seed["process"], [rows[0]["transition_identifier"]]
            )
    assert "incomplete_order" in _error_codes(exc)


# ---------------------------------------------------------------------------
# Reads, updates, identifiers
# ---------------------------------------------------------------------------


def test_get_missing_raises_and_list_filters_by_process(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        transition.create_transition(s, **_base_row(seed))
        assert transition.get_transition(s, "TRN-999") is None
        assert transition.list_transitions(s, process="PROC-999") == []
        assert len(transition.list_transitions(s, process=seed["process"])) == 1
        with pytest.raises(NotFoundError):
            transition.delete_transition(s, "TRN-999")


def test_explicit_identifier_and_collision(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        row = transition.create_transition(
            s, **_base_row(seed), identifier="TRN-042"
        )
        assert row["transition_identifier"] == "TRN-042"
        with pytest.raises(ConflictError):
            transition.create_transition(
                s, **_base_row(seed, to_value="Declined"), identifier="TRN-042"
            )
        with pytest.raises(UnprocessableError):
            transition.create_transition(
                s, **_base_row(seed, to_value="Dormant"), identifier="TRN-1"
            )


def test_patch_revalidates_the_move_as_a_whole(v2_env):
    """A change to one end is checked against the other end as it will be."""
    with session_scope() as s:
        seed = seed_mentor_application(s)
        identifier = transition.create_transition(s, **_base_row(seed))[
            "transition_identifier"
        ]
        with pytest.raises(UnprocessableError) as exc:
            transition.patch_transition(s, identifier, to_value="Candidate")
        assert "to_value_in_from_values" in _error_codes(exc)
        moved = transition.patch_transition(s, identifier, to_value="Declined")
        assert moved["transition_to_value"] == "Declined"


def test_patch_to_a_creation_move_clears_the_from_values(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        identifier = transition.create_transition(s, **_base_row(seed))[
            "transition_identifier"
        ]
        moved = transition.patch_transition(
            s, identifier, from_kind="record_creation"
        )
    assert moved["transition_from_values"] == []


def test_patch_rejects_an_unknown_field(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        identifier = transition.create_transition(s, **_base_row(seed))[
            "transition_identifier"
        ]
        with pytest.raises(UnprocessableError) as exc:
            transition.patch_transition(s, identifier, colour="blue")
    assert "unknown_field" in _error_codes(exc)


def test_next_identifier_skips_used_numbers(v2_env):
    with session_scope() as s:
        seed = seed_mentor_application(s)
        assert transition.next_transition_identifier(s) == "TRN-001"
        transition.create_transition(s, **_base_row(seed))
        assert transition.next_transition_identifier(s) == "TRN-002"


def test_a_view_may_reference_a_transition_and_a_domain_may_not(v2_env):
    """REQ-583: the access layer enforces the pairs, not only the dialog."""
    from crmbuilder_v2.access.repositories import domain, references

    with session_scope() as s:
        seed = seed_mentor_application(s)
        identifier = transition.create_transition(s, **_base_row(seed))[
            "transition_identifier"
        ]
        edge = references.create(
            s,
            source_type="view",
            source_id=seed["candidates_view"],
            target_type="transition",
            target_id=identifier,
            relationship="view_offers_transition",
        )
        assert edge["relationship"] == "view_offers_transition"

        other = domain.create_domain(
            s,
            name="Finance",
            purpose="Money.",
            description="Not a view.",
        )["domain_identifier"]
        with pytest.raises(UnprocessableError) as exc:
            references.create(
                s,
                source_type="domain",
                source_id=other,
                target_type="transition",
                target_id=identifier,
                relationship="view_offers_transition",
            )
    assert "pair_not_allowed" in _error_codes(exc)


def test_the_reference_dialog_offers_the_four_kinds(v2_env):
    """REQ-583: the New Reference dialog's cascading filters are driven by the
    same rules, so the kinds appear there without a second registration."""
    from crmbuilder_v2.access.vocab import kinds_for_source, target_types_for

    for source_type, kind in (
        ("view", "view_offers_transition"),
        ("automation", "automation_triggered_by_transition"),
        ("test_spec", "test_spec_exercises_transition"),
        ("requirement", "requirement_touches_transition"),
    ):
        assert kind in kinds_for_source(source_type)
        assert "transition" in target_types_for(source_type, kind)
