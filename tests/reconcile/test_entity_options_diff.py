"""Entity-option diff-engine tests — offline, no live CRM needed (PI-312 / REQ-346).

Exercises both-way drift (CHANGED / CRM_ONLY = CRM-ahead / YAML_ONLY = design-ahead),
the absent-vs-platform-default normalization that suppresses false drift (the
dominant noise in the CBMTEST-vs-production scan: ``<absent>`` vs explicit
``false``), and the YAML ``settings:`` -> desired path via the provenance builder.
"""
from __future__ import annotations

from pathlib import Path

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.reconcile.diff_engine import (
    ENTITY_OPTION_DEFAULTS,
    diff_entity_options,
)
from espo_impl.core.reconcile.locators import EntityOptionLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory

SRC = Path("CR/CR-Account.yaml")


def _desired(opts):
    return {"Account": (opts, SRC)}


def test_no_drift_when_both_empty():
    assert diff_entity_options({}, {}) == []
    assert diff_entity_options(_desired({}), {"Account": {}}) == []


def test_changed_carries_both_values():
    diffs = diff_entity_options(
        _desired({"iconClass": "fas fa-anchor"}),
        {"Account": {"iconClass": "fas fa-person"}},
    )
    assert len(diffs) == 1
    d = diffs[0]
    assert d.config_type is ConfigType.ENTITY_OPTION
    assert d.category is DiffCategory.CHANGED
    assert d.property == "iconClass"
    assert d.yaml_value == "fas fa-anchor"
    assert d.crm_value == "fas fa-person"
    assert d.locator == EntityOptionLocator("Account", "iconClass")
    assert d.source_file == SRC


def test_crm_only_is_crm_ahead():
    # Production set an icon/color the design never declared (the prod-ahead case).
    diffs = diff_entity_options(
        _desired({}),
        {"Account": {"iconClass": "fas fa-truck", "color": "#f01010"}},
    )
    cats = {d.property: d.category for d in diffs}
    assert cats == {
        "iconClass": DiffCategory.CRM_ONLY,
        "color": DiffCategory.CRM_ONLY,
    }
    icon = next(d for d in diffs if d.property == "iconClass")
    assert icon.crm_value == "fas fa-truck"
    assert icon.yaml_value is None


def test_yaml_only_is_design_ahead():
    # Design (from a dev audit) enables multiple-assigned-users; prod has not.
    diffs = diff_entity_options(
        _desired({"multipleAssignedUsers": True}),
        {"Account": {"multipleAssignedUsers": False}},
    )
    assert len(diffs) == 1
    assert diffs[0].property == "multipleAssignedUsers"
    assert diffs[0].category is DiffCategory.YAML_ONLY
    assert diffs[0].yaml_value is True
    assert diffs[0].crm_value is False


def test_absent_vs_explicit_default_is_not_drift():
    # The exact false-positive the live scan produced: <absent> vs explicit false.
    diffs = diff_entity_options(
        _desired({}),
        {
            "Account": {
                "optimisticConcurrencyControl": False,
                "countDisabled": False,
                "kanbanViewMode": False,
                "multipleAssignedUsers": False,
            }
        },
    )
    assert diffs == []


def test_value_equal_to_default_counts_as_not_set():
    # Design declares the default explicitly; live is ahead with a real value.
    diffs = diff_entity_options(
        _desired({"multipleAssignedUsers": False}),
        {"Account": {"multipleAssignedUsers": True}},
    )
    assert len(diffs) == 1
    assert diffs[0].category is DiffCategory.CRM_ONLY


def test_stable_ordering_by_entity_then_canonical_option():
    diffs = diff_entity_options(
        {
            "Zeta": ({"color": "#111"}, SRC),
            "Alpha": ({"iconClass": "a", "color": "#222"}, SRC),
        },
        {"Zeta": {"color": "#999"}, "Alpha": {"iconClass": "b", "color": "#888"}},
    )
    seen = [(d.entity, d.property) for d in diffs]
    assert seen[0][0] == "Alpha" and seen[-1][0] == "Zeta"
    # iconClass precedes color (canonical ENTITY_OPTION_DEFAULTS order)
    alpha = [p for e, p in seen if e == "Alpha"]
    assert alpha == ["iconClass", "color"]


def test_defaults_cover_every_canonical_option():
    # Guard: every option the comparator iterates has a declared platform default.
    assert set(ENTITY_OPTION_DEFAULTS) == {
        "iconClass", "color", "kanbanViewMode", "statusField",
        "optimisticConcurrencyControl", "countDisabled", "multipleAssignedUsers",
    }


def test_yaml_settings_round_trip_to_desired(tmp_path):
    # The settings: block parses into the typed model and the provenance builder
    # projects exactly the entity-option subset (non-None) with its source file.
    from espo_impl.core.reconcile.provenance import build_entity_option_desired

    yaml_text = """\
version: '1.0'
content_version: 1.0.0
entities:
  Account:
    settings:
      orderBy: name
      iconClass: fas fa-truck
      color: '#f5b20c'
      optimisticConcurrencyControl: true
      multipleAssignedUsers: true
"""
    f = tmp_path / "CR-Account.yaml"
    f.write_text(yaml_text)

    # parse check
    program = ConfigLoader().load_program(f)
    s = program.entities[0].settings
    assert s.iconClass == "fas fa-truck"
    assert s.color == "#f5b20c"
    assert s.optimisticConcurrencyControl is True
    assert s.multipleAssignedUsers is True

    # desired projection check — orderBy is NOT an entity-option key, so excluded
    desired = build_entity_option_desired([f])
    opts, src = desired["Account"]
    assert src == f
    assert opts == {
        "iconClass": "fas fa-truck",
        "color": "#f5b20c",
        "optimisticConcurrencyControl": True,
        "multipleAssignedUsers": True,
    }


def test_invalid_option_types_are_rejected(tmp_path):
    yaml_text = """\
version: '1.0'
content_version: 1.0.0
entities:
  Account:
    settings:
      iconClass: 123
      multipleAssignedUsers: "yes"
"""
    f = tmp_path / "CR-Account.yaml"
    f.write_text(yaml_text)
    program = ConfigLoader().load_program(f)
    errors = ConfigLoader().validate_program(program)
    joined = " ".join(errors)
    assert "settings.iconClass: must be a string" in joined
    assert "settings.multipleAssignedUsers: must be a boolean" in joined
