"""Planning items recorded as unstarted while merged — PI-458 (REQ-556)."""

from __future__ import annotations

from crmbuilder_v2.record_drift import (
    UNSTARTED,
    Drift,
    drifted,
    planning_items_in,
)


def _msg(subject: str, *trailers: str) -> str:
    return subject + "\n\n" + "\n".join(trailers) + "\n"


def test_a_governing_trailer_attributes_a_commit_to_its_item():
    commits = {"aaa1111": _msg("v2: a thing", "Governed-By: PI-406")}
    assert planning_items_in(commits) == {"PI-406": ("aaa1111",)}


def test_every_commit_naming_an_item_is_collected():
    commits = {
        "aaa1111": _msg("first", "Governed-By: PI-406"),
        "bbb2222": _msg("second", "Governed-By: PI-406"),
        "ccc3333": _msg("other", "Governed-By: PI-411"),
    }
    assert planning_items_in(commits) == {
        "PI-406": ("aaa1111", "bbb2222"),
        "PI-411": ("ccc3333",),
    }


def test_the_trivial_exemption_is_evidence_about_no_item():
    """A trivial commit names no planning item — it is exempt from the trailer
    gate, not a statement that some item has begun."""
    commits = {
        "aaa1111": _msg("label fix", "Governed-By: trivial",
                        "Exemption-Reason: wording only"),
    }
    assert planning_items_in(commits) == {}


def test_a_commit_with_no_trailer_contributes_nothing():
    assert planning_items_in({"aaa1111": "v2: no trailer at all\n"}) == {}


def test_a_trailer_mentioned_in_prose_is_not_a_trailer():
    """Only a real trailer line attributes a commit. A message discussing
    PI-406 in its body has not declared itself governed by it."""
    body = "v2: a thing\n\nThis follows the approach PI-406 took.\n"
    assert planning_items_in({"aaa1111": body}) == {}


# --- the contradiction itself ----------------------------------------------

def test_an_item_recorded_unstarted_with_merged_work_is_reported():
    items = {"PI-409": ("aaa1111", "bbb2222")}
    out = drifted(items, {"PI-409": UNSTARTED})
    assert out == [Drift("PI-409", UNSTARTED, ("aaa1111", "bbb2222"))]
    assert "recorded 'Draft'" in out[0].describe()
    assert "aaa1111" in out[0].describe()


def test_an_item_in_progress_is_not_a_contradiction():
    """Merged work on an item still being built is the normal case — a slice
    landing early is exactly how a multi-slice item proceeds."""
    assert drifted({"PI-409": ("aaa1111",)}, {"PI-409": "In Progress"}) == []


def test_a_resolved_item_is_not_reported():
    assert drifted({"PI-409": ("aaa1111",)}, {"PI-409": "Resolved"}) == []


def test_an_unstarted_item_with_no_merged_work_is_not_reported():
    """The check reads from commits outward. An item nobody has begun is simply
    an item nobody has begun."""
    assert drifted({}, {"PI-409": UNSTARTED}) == []


def test_an_unknown_identifier_is_left_to_the_trailer_gate():
    """A trailer naming an item the store does not have is a different defect,
    and reporting it here would blame a status that does not exist."""
    assert drifted({"PI-999": ("aaa1111",)}, {}) == []


def test_only_the_contradicting_items_are_reported():
    items = {
        "PI-406": ("aaa1111",),
        "PI-409": ("bbb2222",),
        "PI-411": ("ccc3333",),
    }
    statuses = {"PI-406": "Resolved", "PI-409": UNSTARTED, "PI-411": "In Progress"}
    assert [d.planning_item for d in drifted(items, statuses)] == ["PI-409"]


def test_the_report_names_the_commits_that_contradict_the_record():
    """REQ-556: the report names each planning item and the commits that
    contradict its status — a bare count would leave someone grepping."""
    d = Drift("PI-409", UNSTARTED, tuple(f"sha{i}" for i in range(8)))
    text = d.describe()
    assert "PI-409" in text and "sha0" in text and "+3 more" in text
