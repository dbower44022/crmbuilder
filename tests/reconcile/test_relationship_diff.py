"""Relationship diff-engine tests — offline, no live CRM needed.

Exercises the three categories (CHANGED with old/new, CRM_ONLY, YAML_ONLY), the
forward asymmetry (a property the YAML leaves unset — ``relation_name=None`` — is
not flagged), and audit-flag drift. Mirrors ``test_diff_engine.py`` for fields.
"""
from __future__ import annotations

from pathlib import Path

from espo_impl.core.models import RelationshipDefinition
from espo_impl.core.reconcile.diff_engine import diff_relationships
from espo_impl.core.reconcile.locators import RelationshipLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory

SRC = Path("MN/MN-Engagement.yaml")


def _rel(name, **kw):
    """A RelationshipDefinition with sensible defaults for a manyToOne link."""
    base = {
        "entity": "Engagement",
        "entity_foreign": "Contact",
        "link_type": "manyToOne",
        "link": "mentor",
        "link_foreign": "engagementsAsMentor",
        "label": "Mentor",
        "label_foreign": "Engagements (Mentor)",
    }
    return RelationshipDefinition(name=name, **{**base, **kw})


def _live(**kw):
    """A RelationshipAuditResult-shaped live dict matching ``_rel`` defaults."""
    base = {
        "link_type": "manyToOne",
        "entity_foreign": "Contact",
        "link": "mentor",
        "link_foreign": "engagementsAsMentor",
        "label": "Mentor",
        "label_foreign": "Engagements (Mentor)",
        "relation_name": None,
        "audited": False,
        "audited_foreign": False,
    }
    return {**base, **kw}


def test_changed_label_carries_old_and_new():
    desired = {"Engagement": {"mentor": (_rel("mentor", label="Mentor"), SRC)}}
    live = {"Engagement": {"mentor": _live(label="Primary Mentor")}}

    diffs = diff_relationships(desired, live)

    assert len(diffs) == 1
    d = diffs[0]
    assert d.config_type is ConfigType.RELATIONSHIP
    assert d.category is DiffCategory.CHANGED
    assert d.property == "label"
    assert d.yaml_value == "Mentor"
    assert d.crm_value == "Primary Mentor"
    assert d.locator == RelationshipLocator("Engagement", "mentor", "label")
    assert d.source_file == SRC


def test_audited_flag_drift_is_flagged():
    # Audit toggled on in the UI is real drift worth surfacing.
    desired = {"Engagement": {"mentor": (_rel("mentor", audited=False), SRC)}}
    live = {"Engagement": {"mentor": _live(audited=True)}}

    diffs = diff_relationships(desired, live)

    assert len(diffs) == 1
    assert diffs[0].property == "audited"
    assert diffs[0].yaml_value is False
    assert diffs[0].crm_value is True


def test_crm_only_relationship_has_no_source_file_and_carries_block():
    desired = {"Engagement": {}}
    block = _live(link="sponsor", label="Sponsor")
    live = {"Engagement": {"sponsor": block}}

    diffs = diff_relationships(desired, live)

    assert len(diffs) == 1
    d = diffs[0]
    assert d.category is DiffCategory.CRM_ONLY
    assert d.source_file is None  # ask-per-addition
    assert d.full_crm_block["label"] == "Sponsor"
    assert d.locator == RelationshipLocator("Engagement", "sponsor", None)


def test_yaml_only_relationship_is_reported_with_source():
    desired = {"Engagement": {"legacyLink": (_rel("legacyLink"), SRC)}}
    live = {"Engagement": {}}

    diffs = diff_relationships(desired, live)

    assert len(diffs) == 1
    d = diffs[0]
    assert d.category is DiffCategory.YAML_ONLY
    assert d.crm_value is None
    assert d.source_file == SRC
    assert d.locator == RelationshipLocator("Engagement", "legacyLink", None)


def test_unset_relation_name_is_not_flagged():
    # YAML leaves relation_name unset (None); CRM has an auto-assigned one.
    # Forward asymmetry: not a changed-in-both diff.
    desired = {"Engagement": {"mentor": (_rel("mentor", relation_name=None), SRC)}}
    live = {"Engagement": {"mentor": _live(relation_name="engagementMentor")}}

    assert diff_relationships(desired, live) == []


def test_matching_relationship_yields_no_diffs():
    desired = {"Engagement": {"mentor": (_rel("mentor"), SRC)}}
    live = {"Engagement": {"mentor": _live()}}
    assert diff_relationships(desired, live) == []
