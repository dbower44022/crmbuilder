"""Apply-orchestrator tests — real writes to tmp files, mixed difference types."""
from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from espo_impl.core.reconcile.locators import FieldLocator, RoleLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory, Difference
from espo_impl.core.reconcile.reconciler import apply_reconciliation

_FIELDS_FILE = '''\
version: "1.0"
content_version: "1.0.0"
entities:
  Session:
    fields:

      - name: sessionType
        type: enum
        label: "Session Type"
'''

_SECURITY_FILE = '''\
version: "1.0"
content_version: "2.4.0"
roles:
  - name: "Mentor"
    scope_access:
      Contact:
        read: team
'''


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body)
    return p


def _field_changed(src):
    return Difference(
        config_type=ConfigType.FIELD, category=DiffCategory.CHANGED, entity="Session",
        locator=FieldLocator("Session", "sessionType", "label"), property="label",
        yaml_value="Session Type", crm_value="Type of Session", source_file=src,
    )


def _field_crm_only(src):
    block = {"name": "topic", "type": "varchar", "label": "Topic"}
    return Difference(
        config_type=ConfigType.FIELD, category=DiffCategory.CRM_ONLY, entity="Session",
        locator=FieldLocator("Session", "topic", None), crm_value=block,
        full_crm_block=block, source_file=src,
    )


def _role_changed(src):
    return Difference(
        config_type=ConfigType.ROLE, category=DiffCategory.CHANGED, entity="Mentor",
        locator=RoleLocator("Mentor", part="scope_access", entity="Contact", key="read"),
        property="scope_access.Contact.read", yaml_value="team", crm_value="all",
        source_file=src,
    )


def test_apply_field_change_and_insert_bumps_version_once(tmp_path):
    f = _write(tmp_path, "MN-Session.yaml", _FIELDS_FILE)

    result = apply_reconciliation([_field_changed(f), _field_crm_only(f)])

    fr = result.files[0]
    assert len(fr.applied) == 2
    assert (fr.old_version, fr.new_version) == ("1.0.0", "1.1.0")  # one bump for both

    data = YAML().load(f.read_text())
    fields = data["entities"]["Session"]["fields"]
    assert fields[0]["label"] == "Type of Session"
    assert [x["name"] for x in fields] == ["sessionType", "topic"]
    assert data["content_version"] == "1.1.0"


def test_apply_across_two_files(tmp_path):
    f1 = _write(tmp_path, "MN-Session.yaml", _FIELDS_FILE)
    f2 = _write(tmp_path, "security.yaml", _SECURITY_FILE)

    result = apply_reconciliation([_field_changed(f1), _role_changed(f2)])

    assert result.applied_count == 2
    assert {fr.new_version for fr in result.files} == {"1.1.0", "2.5.0"}
    assert YAML().load(f2.read_text())["roles"][0]["scope_access"]["Contact"]["read"] == "all"


def test_report_only_diff_not_written_no_bump(tmp_path):
    f = _write(tmp_path, "MN-Session.yaml", _FIELDS_FILE)
    yaml_only = Difference(
        config_type=ConfigType.FIELD, category=DiffCategory.YAML_ONLY, entity="Session",
        locator=FieldLocator("Session", "legacy", None), source_file=f,
    )

    result = apply_reconciliation([yaml_only])

    fr = result.files[0]
    assert fr.applied == []
    assert fr.not_applied and "report-only" in fr.not_applied[0][1]
    assert fr.new_version is None
    # File untouched (no bump, no change).
    assert f.read_text() == _FIELDS_FILE


def test_dry_run_does_not_write(tmp_path):
    f = _write(tmp_path, "MN-Session.yaml", _FIELDS_FILE)
    result = apply_reconciliation([_field_changed(f)], write=False)

    assert "Type of Session" in result.files[0].rendered
    assert f.read_text() == _FIELDS_FILE  # disk untouched


def test_missing_target_file_raises(tmp_path):
    no_target = _field_crm_only(None)
    try:
        apply_reconciliation([no_target])
    except ValueError as e:
        assert "target" in str(e)
    else:
        raise AssertionError("expected ValueError for missing target file")


def test_patcher_error_recorded_not_raised(tmp_path):
    f = _write(tmp_path, "MN-Session.yaml", _FIELDS_FILE)
    # Field that doesn't exist -> set_field_property raises KeyError -> recorded.
    bad = Difference(
        config_type=ConfigType.FIELD, category=DiffCategory.CHANGED, entity="Session",
        locator=FieldLocator("Session", "ghost", "label"), property="label",
        crm_value="x", source_file=f,
    )

    result = apply_reconciliation([bad])
    fr = result.files[0]
    assert fr.applied == []
    assert "error:" in fr.not_applied[0][1]
    assert f.read_text() == _FIELDS_FILE  # nothing written
