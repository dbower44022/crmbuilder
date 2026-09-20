"""Plan identity and the additive-only fence — PI-411 (REQ-496 / REQ-497)."""

from __future__ import annotations

from crmbuilder_v2.access.apply_plan import (
    ADDITIVE,
    NARROWING,
    REMOVAL,
    TYPE_CHANGE,
    automatic_apply_refused,
    classify_change,
    fingerprint_plan,
    plan_moved,
    screen_automatic,
)


def _opts(*values):
    return [{"option_value": v, "option_label": v.title()} for v in values]


# --- plan identity (REQ-496) ------------------------------------------------

def test_the_same_plan_fingerprints_the_same():
    plan = {"target_instance": "INST-001", "items": [{"a": 1}]}
    assert fingerprint_plan(plan) == fingerprint_plan(dict(plan))


def test_order_of_assembly_is_not_part_of_the_plan():
    """Two derivations of the same decisions are the same plan. A fingerprint
    that moved when a source list iterated differently would fire constantly and
    train an operator to ignore it."""
    a = {"target": "INST-001", "items": {"x": 1, "y": 2}}
    b = {"items": {"y": 2, "x": 1}, "target": "INST-001"}
    assert fingerprint_plan(a) == fingerprint_plan(b)


def test_any_change_to_what_would_be_written_moves_the_plan():
    shown = fingerprint_plan({"items": [{"member_identifier": "FLD-1", "reason": "absent"}]})
    assert plan_moved(shown, {"items": [{"member_identifier": "FLD-1", "reason": "drifted"}]})
    assert plan_moved(shown, {"items": [{"member_identifier": "FLD-2", "reason": "absent"}]})
    assert plan_moved(shown, {"items": []})


def test_an_unchanged_plan_has_not_moved():
    plan = {"items": [{"member_identifier": "FLD-1", "reason": "absent"}]}
    assert plan_moved(fingerprint_plan(plan), plan) is False


# --- the additive-only fence (REQ-497) --------------------------------------

def test_adding_an_option_is_a_widening_and_proceeds():
    change = {
        "attribute": "field_options",
        "design": _opts("a", "b", "c"),
        "instance": _opts("a", "b"),
    }
    assert classify_change(change) == ADDITIVE


def test_taking_an_option_away_is_a_narrowing():
    """The instance permits a value the design does not, so publishing removes
    it. An automatic apply changes the CRM before the new code is live, so a
    record still holding that value has its permitted set pulled out from under
    it for the width of the deploy."""
    change = {
        "attribute": "field_options",
        "design": _opts("a"),
        "instance": _opts("a", "b"),
    }
    assert classify_change(change) == NARROWING


def test_the_platform_blank_option_is_not_a_value_being_taken_away():
    """REQ-626, and the real case that found it.

    ``Contact.suffix`` on CBMTEST permits an empty string plus six titles; the
    design declares exactly those six. The empty option is how the platform
    says no value chosen on a field that need not be answered, and no design
    can declare it — so counting it refused a field on which the design and
    the instance agreed, and would have refused it for ever.

    Bare strings, because that is the shape both sides arrive in on the real
    path: the declared list off the generated program, the live list off the
    platform's own metadata.
    """
    change = {
        "attribute": "field_options",
        "design": ["Jr", "Sr", "PhD", "MD", "Esq", "CPA"],
        "instance": ["", "Jr", "Sr", "PhD", "MD", "Esq", "CPA"],
    }
    assert classify_change(change) == ADDITIVE


def test_a_real_value_is_still_a_narrowing_when_a_blank_is_also_present():
    """The blank is ignored; ``b`` is not. Ignoring the one must not blunt the
    fence on the other, which is the whole reason the refusal exists."""
    change = {
        "attribute": "field_options",
        "design": _opts("a"),
        "instance": _opts("", "a", "b"),
    }
    assert classify_change(change) == NARROWING


def test_a_design_that_alone_carries_a_blank_option_is_additive():
    """Symmetry: the empty value is dropped from both sides, so a design that
    somehow carries one does not read as widening the instance either."""
    change = {
        "attribute": "field_options",
        "design": _opts("", "a"),
        "instance": _opts("a"),
    }
    assert classify_change(change) == ADDITIVE


def test_changing_a_type_is_refused():
    change = {"attribute": "field_type", "design": "number", "instance": "text"}
    assert classify_change(change) == TYPE_CHANGE


def test_withdrawing_a_value_the_instance_holds_is_a_removal():
    change = {"attribute": "field_label", "design": None, "instance": "Phone"}
    assert classify_change(change) == REMOVAL


def test_a_construct_the_instance_lacks_is_an_addition_not_a_removal():
    """Publishing to an instance that does not carry the construct creates it.
    Reading that as a removal would refuse exactly the case automatic apply
    exists for."""
    change = {"attribute": "field_label", "design": "Phone", "instance": None}
    assert classify_change(change) == ADDITIVE


def test_an_ordinary_value_edit_proceeds():
    """REQ-497's refusal list is closed - removal, narrowing, type change. A
    gate that blocks more than it was asked to gets switched off."""
    change = {"attribute": "field_label", "design": "Mobile", "instance": "Phone"}
    assert classify_change(change) == ADDITIVE


def test_a_refusal_names_each_declined_change_and_why():
    changes = [
        {"attribute": "field_label", "design": "Mobile", "instance": "Phone"},
        {"attribute": "field_type", "design": "number", "instance": "text"},
        {"attribute": "field_options", "design": _opts("a"), "instance": _opts("a", "b")},
    ]
    permitted, declined = screen_automatic(changes)
    assert len(permitted) == 1
    assert [d["kind"] for d in declined] == [TYPE_CHANGE, NARROWING]
    assert all(d["reason"] for d in declined)


def test_one_refused_change_stops_the_whole_automatic_apply():
    """All-or-nothing: applying the additive half would leave the instance in a
    state neither the plan nor the operator ever described."""
    changes = [
        {"attribute": "field_label", "design": "Mobile", "instance": "Phone"},
        {"attribute": "field_type", "design": "number", "instance": "text"},
    ]
    assert automatic_apply_refused(changes) is True


def test_a_wholly_additive_plan_proceeds():
    changes = [
        {"attribute": "field_label", "design": "Mobile", "instance": "Phone"},
        {"attribute": "field_options", "design": _opts("a", "b"), "instance": _opts("a")},
    ]
    assert automatic_apply_refused(changes) is False
    permitted, declined = screen_automatic(changes)
    assert declined == [] and len(permitted) == 2


def test_no_flag_is_offered_to_let_an_automatic_run_remove():
    """DEC-924 rejected a mode flag explicitly: it gets set during an incident
    by whoever needs the deploy to pass, recreating the window the rule closes.
    The screen takes changes and nothing else."""
    import inspect
    assert list(inspect.signature(screen_automatic).parameters) == ["changes"]
    assert list(inspect.signature(automatic_apply_refused).parameters) == ["changes"]
