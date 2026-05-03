"""Tests for entity settings parsing, validation, and CHECK->ACT manager."""

from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.entity_settings_manager import (
    EntitySettingsManager,
    EntitySettingsManagerError,
)
from espo_impl.core.models import (
    EntityAction,
    EntitySettings,
    SettingsStatus,
)


@pytest.fixture
def loader():
    return ConfigLoader()


# ─── Parsing Tests ───────────────────────────────────────────────


def test_parse_settings_absent(loader, tmp_path):
    """Entity without settings: block has settings=None."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "no_settings.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.entities[0].settings is None


def test_parse_settings_empty(loader, tmp_path):
    """Empty settings: block parses to None (no keys)."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            settings: {}
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "empty_settings.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    # Empty dict produces None from _parse_settings
    assert program.entities[0].settings is None


def test_parse_settings_fully_populated(loader, tmp_path):
    """Fully-populated settings: block parses into EntitySettings."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Dues:
            action: create
            type: Base
            settings:
              labelSingular: "Dues"
              labelPlural: "Dues Records"
              stream: true
              disabled: false
            fields:
              - name: amount
                type: currency
                label: "Amount"
    """)
    path = tmp_path / "full_settings.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    s = program.entities[0].settings
    assert s is not None
    assert s.labelSingular == "Dues"
    assert s.labelPlural == "Dues Records"
    assert s.stream is True
    assert s.disabled is False


def test_parse_settings_partial(loader, tmp_path):
    """Partial settings: only stream specified."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            settings:
              stream: true
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "partial_settings.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    s = program.entities[0].settings
    assert s is not None
    assert s.stream is True
    assert s.labelSingular is None
    assert s.disabled is None


# ─── Validation Tests ────────────────────────────────────────────


def test_validate_unknown_settings_key(loader, tmp_path):
    """Unknown key in settings: produces an error."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            settings:
              stream: true
              bogusKey: "bad"
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "unknown_key.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("unknown key 'bogusKey'" in e for e in errors)


def test_validate_settings_stream_not_bool(loader, tmp_path):
    """stream must be boolean."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            settings:
              stream: "yes"
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "stream_not_bool.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("stream: must be a boolean" in e for e in errors)


def test_validate_settings_disabled_not_bool(loader, tmp_path):
    """disabled must be boolean."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            settings:
              disabled: 1
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "disabled_not_bool.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("disabled: must be a boolean" in e for e in errors)


def test_validate_create_requires_labels_via_settings(loader, tmp_path):
    """action: create requires labelSingular/labelPlural.

    The existing entity-level validator fires because neither
    settings: nor deprecated top-level labels provide the values.
    """
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Dues:
            action: create
            type: Base
            settings:
              stream: false
            fields:
              - name: amount
                type: currency
                label: "Amount"
    """)
    path = tmp_path / "create_no_labels.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("labelSingular" in e and "required" in e for e in errors)
    assert any("labelPlural" in e and "required" in e for e in errors)


def test_validate_create_labels_via_deprecated_top_level(loader, tmp_path):
    """Deprecated top-level labels satisfy the create requirement."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Dues:
            action: create
            type: Base
            labelSingular: "Dues"
            labelPlural: "Dues Records"
            fields:
              - name: amount
                type: currency
                label: "Amount"
    """)
    path = tmp_path / "create_deprecated_labels.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    label_errors = [
        e for e in errors
        if "labelSingular" in e and "required" in e
        or "labelPlural" in e and "required" in e
    ]
    assert label_errors == []


# ─── Deprecation Merge Tests ────────────────────────────────────


def test_deprecation_merge_top_level_to_settings(loader, tmp_path):
    """Top-level stream: true with no settings: populates settings.stream."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            stream: true
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "merge_top_to_settings.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    s = program.entities[0].settings
    assert s is not None
    assert s.stream is True
    # Should also emit deprecation warning
    assert any("stream" in w and "deprecated" in w for w in program.deprecation_warnings)


def test_deprecation_merge_settings_wins(loader, tmp_path):
    """settings.stream: false wins over top-level stream: true."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            stream: true
            settings:
              stream: false
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "settings_wins.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    s = program.entities[0].settings
    assert s is not None
    assert s.stream is False
    # Top-level field should also be synced to settings value
    assert program.entities[0].stream is False
    # Conflict warning should be emitted
    assert any("settings.stream" in w and "ignored" in w for w in program.deprecation_warnings)


def test_deprecation_merge_labels(loader, tmp_path):
    """Top-level labelSingular merges into settings when not set there."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Dues:
            action: create
            type: Base
            labelSingular: "Dues"
            labelPlural: "Dues Records"
            fields:
              - name: amount
                type: currency
                label: "Amount"
    """)
    path = tmp_path / "merge_labels.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    s = program.entities[0].settings
    assert s is not None
    assert s.labelSingular == "Dues"
    assert s.labelPlural == "Dues Records"


# ─── Manager CHECK->ACT Tests ───────────────────────────────────


def _make_settings_manager():
    """Create a settings manager with a mocked client and output."""
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.example.com"
    log = []

    def output_fn(msg, color):
        log.append((msg, color))

    mgr = EntitySettingsManager(client, output_fn)
    return mgr, client, log


def _make_program_with_settings(settings, action="none"):
    """Build a minimal ProgramFile with one entity that has settings."""
    from espo_impl.core.models import (
        EntityDefinition,
        FieldDefinition,
        ProgramFile,
    )

    entity = EntityDefinition(
        name="Contact",
        fields=[FieldDefinition(name="email", type="varchar", label="Email")],
        action=EntityAction(action) if action != "none" else EntityAction.NONE,
        settings=settings,
    )
    return ProgramFile(
        version="1.0",
        description="Test",
        entities=[entity],
    )


def test_manager_settings_match_skips():
    """When settings already match CRM metadata, no update is issued."""
    mgr, client, log = _make_settings_manager()
    client.get_entity_full_metadata.return_value = (
        200, {"stream": True, "disabled": False}
    )

    settings = EntitySettings(stream=True)
    program = _make_program_with_settings(settings)
    results = mgr.process_settings(program)

    assert len(results) == 1
    assert results[0].status == SettingsStatus.SKIPPED
    client.update_entity.assert_not_called()


def test_manager_settings_differ_updates():
    """When settings differ, an update is issued."""
    mgr, client, log = _make_settings_manager()
    client.get_entity_full_metadata.return_value = (
        200, {"stream": False, "disabled": False}
    )
    client.update_entity.return_value = (200, {})

    settings = EntitySettings(stream=True)
    program = _make_program_with_settings(settings)
    results = mgr.process_settings(program)

    assert len(results) == 1
    assert results[0].status == SettingsStatus.UPDATED
    assert "stream" in results[0].changes
    client.update_entity.assert_called_once()


def test_manager_settings_auth_error():
    """401 from API raises EntitySettingsManagerError."""
    mgr, client, log = _make_settings_manager()
    client.get_entity_full_metadata.return_value = (401, None)

    settings = EntitySettings(stream=True)
    program = _make_program_with_settings(settings)

    with pytest.raises(EntitySettingsManagerError):
        mgr.process_settings(program)


def test_manager_settings_connection_error():
    """Negative status code results in ERROR."""
    mgr, client, log = _make_settings_manager()
    client.get_entity_full_metadata.return_value = (-1, None)

    settings = EntitySettings(stream=True)
    program = _make_program_with_settings(settings)
    results = mgr.process_settings(program)

    assert len(results) == 1
    assert results[0].status == SettingsStatus.ERROR
    assert "Connection" in results[0].error


def test_manager_settings_update_fails():
    """When update_entity returns an error, result is ERROR."""
    mgr, client, log = _make_settings_manager()
    client.get_entity_full_metadata.return_value = (
        200, {"stream": False}
    )
    client.update_entity.return_value = (500, {"message": "Server error"})

    settings = EntitySettings(stream=True)
    program = _make_program_with_settings(settings)
    results = mgr.process_settings(program)

    assert len(results) == 1
    assert results[0].status == SettingsStatus.ERROR


def test_manager_settings_non_json_failure_surfaces_raw_text():
    """Parse-failed sentinel from update_entity surfaces raw text in output."""
    mgr, client, log = _make_settings_manager()
    client.get_entity_full_metadata.return_value = (
        200, {"stream": False}
    )
    client.update_entity.return_value = (
        500,
        {
            "_parse_failed": True,
            "_raw_text": "<html>nginx 500</html>",
            "_status_code": 500,
        },
    )

    settings = EntitySettings(stream=True)
    program = _make_program_with_settings(settings)
    results = mgr.process_settings(program)

    assert results[0].status == SettingsStatus.ERROR
    messages = [msg for msg, _ in log]
    assert any("non-JSON response" in msg for msg in messages)
    assert any("nginx 500" in msg for msg in messages)


def test_manager_idempotent_second_run():
    """Running twice with matching state results in skip on second run."""
    mgr, client, log = _make_settings_manager()
    # First run: differs
    client.get_entity_full_metadata.return_value = (
        200, {"stream": False}
    )
    client.update_entity.return_value = (200, {})

    settings = EntitySettings(stream=True)
    program = _make_program_with_settings(settings)
    results1 = mgr.process_settings(program)
    assert results1[0].status == SettingsStatus.UPDATED

    # Second run: now matches
    client.get_entity_full_metadata.return_value = (
        200, {"stream": True}
    )
    results2 = mgr.process_settings(program)
    assert results2[0].status == SettingsStatus.SKIPPED


def test_manager_skips_delete_entities():
    """Entities with action=DELETE are skipped."""
    from espo_impl.core.models import (
        EntityDefinition,
        ProgramFile,
    )

    mgr, client, log = _make_settings_manager()

    entity = EntityDefinition(
        name="OldEntity",
        fields=[],
        action=EntityAction.DELETE,
        settings=EntitySettings(stream=True),
    )
    program = ProgramFile(
        version="1.0", description="Test", entities=[entity]
    )
    results = mgr.process_settings(program)
    assert results == []


def test_manager_skips_no_settings():
    """Entities without settings are skipped."""
    from espo_impl.core.models import (
        EntityDefinition,
        FieldDefinition,
        ProgramFile,
    )

    mgr, client, log = _make_settings_manager()

    entity = EntityDefinition(
        name="Contact",
        fields=[FieldDefinition(name="email", type="varchar", label="Email")],
    )
    program = ProgramFile(
        version="1.0", description="Test", entities=[entity]
    )
    results = mgr.process_settings(program)
    assert results == []
