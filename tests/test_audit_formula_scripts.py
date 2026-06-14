"""Tests for entity formula-script audit capture (REQ-122 / Option A).

EspoCRM stores entity formulas as free-text scripts at
``formula.{Entity}`` (beforeSaveCustomScript / beforeSaveApiScript) and
exposes no REST write path for them, so the audit captures them verbatim
into a ``formulaScript:`` block (re-apply is manual). These tests cover
capture, sentinel/empty filtering, YAML emission, and that the emitted
YAML still loads and validates cleanly (the loader ignores the block).
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import yaml

from espo_impl.core.audit_manager import (
    AuditManager,
    AuditOptions,
    AuditReport,
    EntityAuditResult,
)
from espo_impl.core.audit_utils import EntityClass
from espo_impl.core.config_loader import ConfigLoader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(**method_returns: Any) -> MagicMock:
    client = MagicMock()
    profile = MagicMock()
    profile.url = "https://example.test"
    profile.name = "audit-test"
    client.profile = profile
    for name, value in method_returns.items():
        getattr(client, name).return_value = value
    return client


def _manager(client: MagicMock) -> tuple[AuditManager, list[tuple[str, str]]]:
    log: list[tuple[str, str]] = []
    mgr = AuditManager(client, AuditOptions(), lambda m, c: log.append((m, c)))
    return mgr, log


def _report() -> AuditReport:
    return AuditReport(
        source_url="https://example.test", source_name="audit-test",
        timestamp="2026-06-13T00:00:00Z", output_dir="",
    )


def _entity() -> EntityAuditResult:
    return EntityAuditResult(
        yaml_name="MentorProfile", espo_name="CMentorProfile",
        entity_class=EntityClass.CUSTOM, entity_type="Base",
    )


_SCRIPT = "availableCapacity = maximumClientCapacity - currentActiveClients;"


# ---------------------------------------------------------------------------
# _apply_formula_scripts
# ---------------------------------------------------------------------------


def test_captures_non_empty_scripts():
    client = _client(get_entity_formula=(200, {
        "beforeSaveCustomScript": _SCRIPT,
        "beforeSaveApiScript": "name = 'x';",
    }))
    mgr, log = _manager(client)
    entity = _entity()

    mgr._apply_formula_scripts(entity, _report())

    assert entity.formula_scripts == {
        "beforeSaveCustomScript": _SCRIPT,
        "beforeSaveApiScript": "name = 'x';",
    }
    assert any("formula script" in m for m, _ in log)
    client.get_entity_formula.assert_called_once_with("CMentorProfile")


def test_ignores_sentinel_and_empty_values():
    client = _client(get_entity_formula=(200, {
        "_parse_failed": True,            # sentinel (non-str) → dropped
        "beforeSaveCustomScript": "   ",  # whitespace → dropped
        "beforeSaveApiScript": _SCRIPT,   # real → kept
    }))
    mgr, _ = _manager(client)
    entity = _entity()

    mgr._apply_formula_scripts(entity, _report())

    assert entity.formula_scripts == {"beforeSaveApiScript": _SCRIPT}


def test_no_formula_is_noop():
    client = _client(get_entity_formula=(200, {"_parse_failed": True}))
    mgr, log = _manager(client)
    entity = _entity()

    mgr._apply_formula_scripts(entity, _report())

    assert entity.formula_scripts == {}
    assert log == []


def test_non_200_is_noop():
    client = _client(get_entity_formula=(404, None))
    mgr, _ = _manager(client)
    entity = _entity()

    mgr._apply_formula_scripts(entity, _report())

    assert entity.formula_scripts == {}


# ---------------------------------------------------------------------------
# YAML emission
# ---------------------------------------------------------------------------


def test_build_entity_yaml_emits_formula_script():
    mgr, _ = _manager(_client())
    entity = _entity()
    entity.formula_scripts = {"beforeSaveCustomScript": _SCRIPT}

    block = mgr._build_entity_yaml(entity)["entities"]["MentorProfile"]

    assert block["formulaScript"] == {"beforeSaveCustomScript": _SCRIPT}


def test_entity_with_only_formula_is_written(tmp_path: Path):
    mgr, _ = _manager(_client())
    entity = _entity()
    entity.formula_scripts = {"beforeSaveCustomScript": _SCRIPT}
    report = _report()

    count = mgr._write_yaml_files([entity], [], tmp_path, report)

    assert count == 1
    written = yaml.safe_load((tmp_path / "MentorProfile.yaml").read_text())
    assert written["entities"]["MentorProfile"]["formulaScript"] == {
        "beforeSaveCustomScript": _SCRIPT,
    }


# ---------------------------------------------------------------------------
# Round-trip: emitted YAML loads + validates cleanly (block is ignored)
# ---------------------------------------------------------------------------


def test_audited_yaml_with_formula_script_validates(tmp_path: Path):
    client = _client(
        get_entity_field_list=(200, {"cNote": {"type": "varchar"}}),
        get_i18n=(200, {}),
        get_entity_formula=(200, {"beforeSaveCustomScript": _SCRIPT}),
    )
    mgr, _ = _manager(client)
    # Native Contact so no entity-create validation is required.
    entity = EntityAuditResult(
        yaml_name="Contact", espo_name="Contact",
        entity_class=EntityClass.NATIVE, entity_type="Person",
    )
    report = _report()

    mgr._extract_fields(entity, report)
    mgr._apply_formula_scripts(entity, report)
    mgr._write_yaml_files([entity], [], tmp_path, report)
    assert report.errors == []

    loader = ConfigLoader()
    program = loader.load_program(tmp_path / "Contact.yaml")
    errors = loader.validate_program(program)
    assert errors == [], errors

    # The block is present in the file even though the loader ignores it.
    raw = yaml.safe_load((tmp_path / "Contact.yaml").read_text())
    assert "formulaScript" in raw["entities"]["Contact"]
