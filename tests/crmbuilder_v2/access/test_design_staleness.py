"""Design-side staleness tests — PI-345 (REQ-304, DEC-652)."""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import association as assoc_repo
from crmbuilder_v2.access.repositories import association_mapping as amap
from crmbuilder_v2.access.repositories import entity as ent_repo
from crmbuilder_v2.access.repositories import field as fld_repo
from crmbuilder_v2.access.repositories import field_mapping as fmap
from crmbuilder_v2.access.repositories import source_mapping as smg
from crmbuilder_v2.access.repositories import source_mapping_targets as smt


def _resolved_entity_mapping(s, source_name, entity_id):
    m = smg.create_source_mapping(
        s, instance_identifier="INST-001", source_entity_name=source_name,
        decision_type="direct")
    mid = m["source_mapping_identifier"]
    smt.add_target(s, source_mapping_identifier=mid, entity_identifier=entity_id)
    smg.update_source_mapping(
        s, mid, source_entity_name=source_name, decision_type="direct",
        status="resolved")
    return mid


def test_entity_rename_flags_source_mapping_low(v2_env):
    with session_scope() as s:
        eid = ent_repo.create_entity(
            s, name="Account", description="x")["entity_identifier"]
        mid = _resolved_entity_mapping(s, "CAccount", eid)
        ent_repo.patch_entity(s, eid, name="Organization")
        m = smg.get_source_mapping(s, mid)
        assert m["status"] == "stale"
        assert m["stale_reason"] == "design_changed"
        assert m["stale_severity"] == "low"


def test_entity_description_change_does_not_flag(v2_env):
    with session_scope() as s:
        eid = ent_repo.create_entity(
            s, name="Account", description="x")["entity_identifier"]
        mid = _resolved_entity_mapping(s, "CAccount", eid)
        ent_repo.patch_entity(s, eid, description="a different description")
        assert smg.get_source_mapping(s, mid)["status"] == "resolved"


def test_field_type_change_flags_field_mapping_high(v2_env):
    with session_scope() as s:
        eid = ent_repo.create_entity(
            s, name="Account", description="x")["entity_identifier"]
        fid = fld_repo.create_field(
            s, field_belongs_to_entity_identifier=eid, name="status",
            description="x", type="text", required=False)["field_identifier"]
        mid = _resolved_entity_mapping(s, "CAccount", eid)
        fm = fmap.create_field_mapping(
            s, source_mapping_identifier=mid, source_field_name="cStatus",
            decision_type="direct", target_entity_identifier=eid,
            target_field_identifier=fid)
        fmid = fm["field_mapping_identifier"]
        fmap.update_field_mapping(
            s, fmid, source_field_name="cStatus", decision_type="direct",
            status="resolved", target_entity_identifier=eid,
            target_field_identifier=fid)
        fld_repo.patch_field(s, fid, type="enum")
        out = fmap.get_field_mapping(s, fmid)
        assert out["status"] == "stale"
        assert out["stale_reason"] == "design_changed"
        assert out["stale_severity"] == "high"


def test_association_cardinality_change_flags_high(v2_env):
    with session_scope() as s:
        eid = ent_repo.create_entity(
            s, name="Engagement", description="x")["entity_identifier"]
        did = ent_repo.create_entity(
            s, name="Dues", description="x")["entity_identifier"]
        aid = assoc_repo.create_association(
            s, name="dueses", source_entity=eid, target_entity=did,
            cardinality="one_to_many")["association_identifier"]
        am = amap.create_association_mapping(
            s, instance_identifier="INST-001", source_association_name="dueses",
            decision_type="direct")
        amid = am["association_mapping_identifier"]
        amap.update_association_mapping(
            s, amid, source_association_name="dueses", decision_type="direct",
            status="resolved", target_association_identifier=aid)
        assoc_repo.patch_association(s, aid, cardinality="many_to_many")
        out = amap.get_association_mapping(s, amid)
        assert out["status"] == "stale"
        assert out["stale_severity"] == "high"


def test_already_stale_not_reflagged(v2_env):
    with session_scope() as s:
        eid = ent_repo.create_entity(
            s, name="Account", description="x")["entity_identifier"]
        mid = _resolved_entity_mapping(s, "CAccount", eid)
        ent_repo.patch_entity(s, eid, name="Organization")  # -> stale
        # A second rename must not error (the mapping is already stale, so the
        # resolved-only guard skips it — the stale->stale transition is illegal).
        ent_repo.patch_entity(s, eid, name="Org2")
        assert smg.get_source_mapping(s, mid)["status"] == "stale"
