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
