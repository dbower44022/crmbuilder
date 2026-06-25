"""Entity-option write-back tests (PI-313 / REQ-351).

Covers the document primitive ``set_entity_option`` (create the settings block,
append to it, replace a value, quote a ``#`` colour) and the reconciler path that
adopts a CRM-ahead value into the YAML while leaving a design-ahead (YAML_ONLY)
option as deploy-direction report-only.
"""
from __future__ import annotations

from ruamel.yaml import YAML

from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.locators import EntityOptionLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory, Difference
from espo_impl.core.reconcile.reconciler import apply_reconciliation


def _reparse(text):
    return YAML().load(text)


_NO_SETTINGS = """\
entities:
  Account:
    type: Base
    fields:
      - name: foo        # keep me
        type: varchar
"""

_WITH_SETTINGS = """\
entities:
  Account:
    settings:
      orderBy: name
    fields:
      - name: foo
        type: varchar
"""


def test_create_settings_block_when_absent():
    doc = YamlDocument(_NO_SETTINGS)
    doc.set_entity_option("Account", "iconClass", "fas fa-truck")
    out = doc.render()

    data = _reparse(out)
    assert data["entities"]["Account"]["settings"]["iconClass"] == "fas fa-truck"
    # unrelated content untouched
    assert data["entities"]["Account"]["fields"][0]["name"] == "foo"
    assert "# keep me" in out


def test_append_to_existing_settings_block():
    doc = YamlDocument(_WITH_SETTINGS)
    doc.set_entity_option("Account", "iconClass", "fas fa-truck")
    out = doc.render()

    s = _reparse(out)["entities"]["Account"]["settings"]
    assert s["orderBy"] == "name"          # existing preserved
    assert s["iconClass"] == "fas fa-truck"  # appended


def test_replace_existing_option_value():
    doc = YamlDocument(
        "entities:\n  Account:\n    settings:\n      iconClass: fas fa-old\n"
    )
    doc.set_entity_option("Account", "iconClass", "fas fa-new")
    out = doc.render()
    assert _reparse(out)["entities"]["Account"]["settings"]["iconClass"] == "fas fa-new"


def test_color_hash_string_is_quoted_not_a_comment():
    # The exact hazard: an unquoted '#f01010' would be read as a comment.
    doc = YamlDocument(_NO_SETTINGS)
    doc.set_entity_option("Account", "color", "#f01010")
    out = doc.render()
    assert _reparse(out)["entities"]["Account"]["settings"]["color"] == "#f01010"


def test_boolean_option_round_trips():
    doc = YamlDocument(_NO_SETTINGS)
    doc.set_entity_option("Account", "optimisticConcurrencyControl", True)
    out = doc.render()
    assert (
        _reparse(out)["entities"]["Account"]["settings"][
            "optimisticConcurrencyControl"
        ]
        is True
    )


# --- reconciler path -------------------------------------------------------


def _opt_diff(category, option, crm_value, src, yaml_value=None):
    return Difference(
        config_type=ConfigType.ENTITY_OPTION,
        category=category,
        entity="Account",
        locator=EntityOptionLocator("Account", option),
        property=option,
        yaml_value=yaml_value,
        crm_value=crm_value,
        source_file=src,
    )


def test_reconciler_writes_crm_ahead_option(tmp_path):
    f = tmp_path / "CR-Account.yaml"
    f.write_text(_NO_SETTINGS)
    diff = _opt_diff(DiffCategory.CRM_ONLY, "color", "#f01010", f)

    result = apply_reconciliation([diff])

    assert result.applied_count == 1
    data = _reparse(f.read_text())
    assert data["entities"]["Account"]["settings"]["color"] == "#f01010"


def test_reconciler_changed_option_adopts_crm_value(tmp_path):
    f = tmp_path / "CR-Account.yaml"
    f.write_text(_WITH_SETTINGS.replace("orderBy: name", "iconClass: fas fa-old"))
    diff = _opt_diff(
        DiffCategory.CHANGED, "iconClass", "fas fa-new", f, yaml_value="fas fa-old"
    )

    result = apply_reconciliation([diff])

    assert result.applied_count == 1
    assert (
        _reparse(f.read_text())["entities"]["Account"]["settings"]["iconClass"]
        == "fas fa-new"
    )


def test_reconciler_design_ahead_option_is_report_only(tmp_path):
    f = tmp_path / "CR-Account.yaml"
    original = _WITH_SETTINGS
    f.write_text(original)
    # YAML_ONLY = the design declares it; reconciling means deploy, not write-back.
    diff = _opt_diff(
        DiffCategory.YAML_ONLY, "multipleAssignedUsers", None, f, yaml_value=True
    )

    result = apply_reconciliation([diff])

    assert result.applied_count == 0
    assert result.not_applied_count == 1
    assert f.read_text() == original  # untouched
