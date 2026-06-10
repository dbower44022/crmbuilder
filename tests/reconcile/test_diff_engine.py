"""Field diff-engine tests — offline, no live CRM needed.

Exercises the three categories (CHANGED with old/new, CRM_ONLY, YAML_ONLY), the
forward-CHECK asymmetry inherited from FieldComparator (a property the YAML does
not set is not flagged), and the foreign-field key/attribute bridging.
"""
from __future__ import annotations

from pathlib import Path

from espo_impl.core.models import FieldDefinition
from espo_impl.core.reconcile.diff_engine import diff_fields
from espo_impl.core.reconcile.locators import FieldLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory

SRC = Path("MN/MN-Session.yaml")


def _spec(name, **kw):
    kw.setdefault("type", "varchar")
    kw.setdefault("label", name)
    return FieldDefinition(name=name, type=kw.pop("type"), label=kw.pop("label"), **kw)


def test_changed_property_carries_old_and_new():
    desired = {"Session": {"sessionType": (_spec("sessionType", type="enum",
                                                 label="Session Type"), SRC)}}
    live = {"Session": {"sessionType": {"type": "enum", "label": "Type of Session"}}}

    diffs = diff_fields(desired, live)

    assert len(diffs) == 1
    d = diffs[0]
    assert d.config_type is ConfigType.FIELD
    assert d.category is DiffCategory.CHANGED
    assert d.property == "label"
    assert d.yaml_value == "Session Type"
    assert d.crm_value == "Type of Session"
    assert d.locator == FieldLocator("Session", "sessionType", "label")
    assert d.source_file == SRC


def test_crm_only_field_has_no_source_file_and_carries_block():
    # A real UI addition is a custom field (isCustom).
    desired = {"Session": {}}
    live = {"Session": {"linkedinUrl": {"type": "url", "label": "LinkedIn", "isCustom": True}}}

    diffs = diff_fields(desired, live)

    assert len(diffs) == 1
    d = diffs[0]
    assert d.category is DiffCategory.CRM_ONLY
    assert d.source_file is None  # ask-per-addition
    assert d.full_crm_block["type"] == "url"
    assert d.locator == FieldLocator("Session", "linkedinUrl", None)


def test_native_live_only_field_not_flagged_crm_only():
    # A native field the YAML never declared is not a reconciliation concern.
    desired = {"Contact": {}}
    live = {"Contact": {"phoneNumber": {"type": "phone", "label": "Phone"}}}  # no isCustom
    assert diff_fields(desired, live) == []
    # ...unless the caller opts in.
    assert len(diff_fields(desired, live, crm_only_custom_only=False)) == 1


def test_yaml_only_field_is_reported_with_source():
    desired = {"Session": {"legacyFlag": (_spec("legacyFlag"), SRC)}}
    live = {"Session": {}}

    diffs = diff_fields(desired, live)

    assert len(diffs) == 1
    d = diffs[0]
    assert d.category is DiffCategory.YAML_ONLY
    assert d.crm_value is None
    assert d.source_file == SRC


def test_property_unset_in_yaml_is_not_flagged():
    # YAML doesn't set `required`; CRM has required=True. FieldComparator's
    # forward asymmetry means this is NOT a changed-in-both diff (it would be a
    # key-insertion, deferred). So no Difference is produced.
    desired = {"Session": {"sessionType": (_spec("sessionType", type="enum",
                                                 label="Session Type"), SRC)}}
    live = {"Session": {"sessionType": {"type": "enum", "label": "Session Type",
                                        "required": True}}}

    diffs = diff_fields(desired, live)
    assert diffs == []


def test_foreign_field_key_bridges_to_attribute():
    spec = _spec("mentorName", type="foreign", label="Mentor",
                 link="mentor", foreign_field="name")
    desired = {"Engagement": {"mentorName": (spec, SRC)}}
    # CRM mirrors a different linked field ("fullName") under the API key "field".
    live = {"Engagement": {"mentorName": {"type": "foreign", "link": "mentor",
                                          "field": "fullName"}}}

    diffs = diff_fields(desired, live)

    assert len(diffs) == 1
    d = diffs[0]
    assert d.property == "field"          # YAML key
    assert d.yaml_value == "name"         # read via foreign_field attribute
    assert d.crm_value == "fullName"
    assert d.locator == FieldLocator("Engagement", "mentorName", "field")


def test_matching_field_yields_no_diffs():
    desired = {"Session": {"sessionType": (_spec("sessionType", type="enum",
                                                 label="Session Type"), SRC)}}
    live = {"Session": {"sessionType": {"type": "enum", "label": "Session Type"}}}
    assert diff_fields(desired, live) == []
