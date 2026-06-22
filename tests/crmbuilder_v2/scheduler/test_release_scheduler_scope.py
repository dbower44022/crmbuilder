"""PI-269 / REQ-266 — decomposition input is scoped to a single planning item.

The release scheduler hands each planning item only the design delta-sets whose
artifact was demanded by that item's own requirements, so one item's plan can
never absorb sibling items' work (the REL-005 over-production mode).
"""

from __future__ import annotations

from crmbuilder_v2.scheduler.release_scheduler import _scope_designs_to_pi


def _delta(atype, aid):
    return {"artifact_type": atype, "artifact_identifier": aid, "merged": {}}


def test_scope_keeps_only_this_items_artifacts():
    deltas = [_delta("entity", "Account"), _delta("field", "phone"),
              _delta("entity", "Contact")]
    artifact_reqs = {
        ("entity", "Account"): {"REQ-1"},
        ("field", "phone"): {"REQ-1", "REQ-2"},
        ("entity", "Contact"): {"REQ-9"},   # a sibling item's requirement
    }
    scoped = _scope_designs_to_pi(deltas, artifact_reqs, {"REQ-1"})
    aids = {d["artifact_identifier"] for d in scoped}
    assert aids == {"Account", "phone"}        # REQ-1's artifacts only
    assert "Contact" not in aids               # sibling REQ-9's work excluded


def test_scope_empty_when_item_touches_nothing():
    deltas = [_delta("entity", "Account")]
    artifact_reqs = {("entity", "Account"): {"REQ-1"}}
    assert _scope_designs_to_pi(deltas, artifact_reqs, {"REQ-7"}) == []


def test_scope_artifact_shared_across_requirements_is_kept():
    # An artifact demanded by both this item's req and a sibling's is still in
    # scope for this item (it genuinely touches it).
    deltas = [_delta("field", "email")]
    artifact_reqs = {("field", "email"): {"REQ-1", "REQ-9"}}
    assert _scope_designs_to_pi(deltas, artifact_reqs, {"REQ-1"}) == deltas
