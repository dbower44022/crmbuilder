"""Candidate Review panel tests — PI-256 (PRJ-027 / REQ-341) slice 1.

Covers the read surface: the "Candidate Review" sidebar entry in the Governance
group, the master-pane columns, and ``fetch_records`` grouping candidates into
confidence buckets (high → medium → low → unranked) with open candidates above
resolved ones, plus the derived display fields the detail pane reads.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import mapping_candidate as candidate_repo
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.panels.candidate_review import CandidateReviewPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS
from fastapi.testclient import TestClient


@pytest.fixture
def review_client(v2_env) -> StorageClient:
    sc = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    sc.set_active_engagement("ENG-001")
    return sc


def _seed(**kw) -> None:
    with session_scope() as s:
        candidate_repo.create_candidate(s, instance_identifier="INST-001", **kw)


def test_candidate_review_in_governance_group():
    gov = dict(SIDEBAR_GROUPS)["Governance"]
    assert "Candidate Review" in gov


def test_fetch_records_groups_by_confidence(qapp, review_client):
    # Three open candidates with different confidence + one resolved.
    _seed(candidate_type="entity", source_entity_name="CLow",
          suggestion_confidence="low", suggestion_basis="weak name match")
    _seed(candidate_type="entity", source_entity_name="CHigh",
          suggestion_confidence="high", suggestion_basis="exact name match")
    _seed(candidate_type="field", source_entity_name="CMid",
          source_field_name="status", suggestion_confidence="medium")
    # A resolved one (sorts to the bottom, and is filtered out by default).
    with session_scope() as s:
        c = candidate_repo.create_candidate(
            s, instance_identifier="INST-001", candidate_type="entity",
            source_entity_name="CDone", suggestion_confidence="high",
        )
        candidate_repo.resolve_candidate(s, c["id"])

    panel = CandidateReviewPanel(review_client)
    try:
        # Default hides resolved -> only the three open candidates, ordered
        # high, medium, low.
        records = panel.fetch_records()
        confidences = [r["suggestion_confidence"] for r in records]
        assert confidences == ["high", "medium", "low"]
        # Derived display fields the detail/list panes read.
        first = records[0]
        assert first["confidence_display"] == "High"
        assert first["type_display"] == "Entity"
        assert first["source_display"] == "CHigh"
        assert first["resolved_display"] == "Open"
        # The field candidate renders entity.field.
        field_row = next(r for r in records if r["candidate_type"] == "field")
        assert field_row["source_display"] == "CMid.status"

        # Toggling "show resolved" includes the resolved candidate, last.
        panel._show_resolved = True
        with_resolved = panel.fetch_records()
        assert any(r["source_entity_name"] == "CDone" for r in with_resolved)
        assert with_resolved[-1]["source_entity_name"] == "CDone"
    finally:
        panel.deleteLater()


def test_list_columns_and_title(qapp, review_client):
    panel = CandidateReviewPanel(review_client)
    try:
        assert panel.entity_title() == "Candidate Review"
        fields = [c.field for c in panel.list_columns()]
        assert fields == [
            "confidence_display", "type_display", "source_display",
            "resolved_display",
        ]
    finally:
        panel.deleteLater()


# --- slice 2: resolve workflow (entity candidate -> source_mapping) ---------


def _seed_entity_candidate(source_name: str) -> int:
    with session_scope() as s:
        c = candidate_repo.create_candidate(
            s, instance_identifier="INST-001", candidate_type="entity",
            source_entity_name=source_name, suggestion_confidence="high",
        )
        return c["id"]


def _seed_canonical_entity(name: str) -> str:
    from crmbuilder_v2.access.repositories import entity as entity_repo
    with session_scope() as s:
        return entity_repo.create_entity(
            s, name=name, description="x")["entity_identifier"]


def test_resolve_dialog_maps_entity_candidate(qapp, review_client):
    from crmbuilder_v2.ui.dialogs.candidate_resolve import (
        ResolveEntityCandidateDialog,
    )
    cid = _seed_entity_candidate("CMentorProfile")
    eid = _seed_canonical_entity("MentorProfile")
    candidate = review_client.get_mapping_candidate(cid)

    dialog = ResolveEntityCandidateDialog(review_client, candidate)
    try:
        # Decision 0 = direct map; point at the seeded design entity.
        dialog._decision_combo.setCurrentIndex(0)
        idx = dialog._target_combo.findData(eid)
        assert idx >= 0, "seeded entity not offered as a target"
        dialog._target_combo.setCurrentIndex(idx)
        dialog._on_ok()
    finally:
        dialog.deleteLater()

    # A resolved, direct source_mapping now exists, targeted at the entity.
    mappings = review_client.list_source_mappings(instance_identifier="INST-001")
    assert len(mappings) == 1
    m = mappings[0]
    assert m["status"] == "resolved" and m["decision_type"] == "direct"
    # The candidate is resolved and points at the mapping.
    resolved = review_client.get_mapping_candidate(cid)
    assert resolved["resolved"] is True
    assert resolved["resolved_to_source_mapping_identifier"] == (
        m["source_mapping_identifier"]
    )


def test_resolve_dialog_rejects_entity_candidate(qapp, review_client):
    from crmbuilder_v2.ui.dialogs.candidate_resolve import (
        ResolveEntityCandidateDialog,
    )
    cid = _seed_entity_candidate("CLegacyThing")
    candidate = review_client.get_mapping_candidate(cid)

    dialog = ResolveEntityCandidateDialog(review_client, candidate)
    try:
        # Last decision = Reject; the target combo is disabled.
        dialog._decision_combo.setCurrentIndex(dialog._decision_combo.count() - 1)
        assert not dialog._target_combo.isEnabled()
        dialog._on_ok()
    finally:
        dialog.deleteLater()

    m = review_client.list_source_mappings(instance_identifier="INST-001")[0]
    assert m["status"] == "resolved" and m["decision_type"] == "rejected"
    assert review_client.get_mapping_candidate(cid)["resolved"] is True


# --- slice 2b: field + association candidate resolve ------------------------


def _seed_resolved_entity_mapping(source_name: str, target_entity_id: str) -> str:
    """A resolved, targeted entity source_mapping a field candidate hangs off."""
    from crmbuilder_v2.access.repositories import source_mapping as smg
    from crmbuilder_v2.access.repositories import source_mapping_targets as smt
    with session_scope() as s:
        m = smg.create_source_mapping(
            s, instance_identifier="INST-001", source_entity_name=source_name,
            decision_type="direct",
        )
        mid = m["source_mapping_identifier"]
        smt.add_target(
            s, source_mapping_identifier=mid, entity_identifier=target_entity_id)
        smg.update_source_mapping(
            s, mid, source_entity_name=source_name, decision_type="direct",
            status="resolved")
        return mid


def test_resolve_field_candidate(qapp, review_client):
    from crmbuilder_v2.access.repositories import field as field_repo
    from crmbuilder_v2.ui.dialogs.candidate_resolve import (
        ResolveFieldCandidateDialog,
    )
    eid = _seed_canonical_entity("MentorProfile")
    with session_scope() as s:
        fid = field_repo.create_field(
            s, field_belongs_to_entity_identifier=eid, name="cStatus",
            description="x", type="enum", required=False)["field_identifier"]
        cid = candidate_repo.create_candidate(
            s, instance_identifier="INST-001", candidate_type="field",
            source_entity_name="CMentorProfile", source_field_name="cStatus",
        )["id"]
    _seed_resolved_entity_mapping("CMentorProfile", eid)

    candidate = review_client.get_mapping_candidate(cid)
    dialog = ResolveFieldCandidateDialog(review_client, candidate)
    try:
        idx = dialog._target_combo.findData(fid)
        assert idx >= 0, "seeded field not offered as a target"
        dialog._target_combo.setCurrentIndex(idx)
        dialog._on_ok()
    finally:
        dialog.deleteLater()

    fms = review_client._request("GET", "/field-mappings")
    assert len(fms) == 1
    assert fms[0]["status"] == "resolved"
    assert fms[0]["target_field_identifier"] == fid
    assert review_client.get_mapping_candidate(cid)["resolved"] is True


def test_resolve_association_candidate(qapp, review_client):
    from crmbuilder_v2.access.repositories import association as assoc_repo
    from crmbuilder_v2.ui.dialogs.candidate_resolve import (
        ResolveAssociationCandidateDialog,
    )
    eid = _seed_canonical_entity("Engagement")
    did = _seed_canonical_entity("Dues")
    with session_scope() as s:
        aid = assoc_repo.create_association(
            s, name="dueses", source_entity=eid, target_entity=did,
            cardinality="one_to_many")["association_identifier"]
        cid = candidate_repo.create_candidate(
            s, instance_identifier="INST-001", candidate_type="association",
            source_entity_name="CEngagement", source_field_name="dueses",
        )["id"]

    candidate = review_client.get_mapping_candidate(cid)
    dialog = ResolveAssociationCandidateDialog(review_client, candidate)
    try:
        idx = dialog._target_combo.findData(aid)
        assert idx >= 0, "seeded association not offered as a target"
        dialog._target_combo.setCurrentIndex(idx)
        dialog._on_ok()
    finally:
        dialog.deleteLater()

    ams = review_client.list_association_mappings(instance_identifier="INST-001")
    assert len(ams) == 1
    assert ams[0]["status"] == "resolved"
    assert ams[0]["target_association_identifier"] == aid
    assert review_client.get_mapping_candidate(cid)["resolved"] is True
