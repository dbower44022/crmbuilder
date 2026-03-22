"""Tests for the field manager orchestration logic."""

from unittest.mock import MagicMock

from espo_impl.core.comparator import ComparisonResult, FieldComparator
from espo_impl.core.field_manager import FieldManager
from espo_impl.core.models import (
    EntityDefinition,
    FieldDefinition,
    FieldStatus,
    ProgramFile,
)


def make_program(fields=None) -> ProgramFile:
    if fields is None:
        fields = [
            FieldDefinition(name="testField", type="varchar", label="Test"),
        ]
    return ProgramFile(
        version="1.0",
        description="Test",
        entities=[EntityDefinition(name="Contact", fields=fields)],
    )


def make_manager(client=None, comparator=None) -> tuple[FieldManager, list]:
    if client is None:
        client = MagicMock()
        client.profile.name = "Test Instance"
        client.profile.url = "https://test.espocloud.com"
    if comparator is None:
        comparator = MagicMock(spec=FieldComparator)
    output_log: list[tuple[str, str]] = []

    def output_fn(msg, color):
        output_log.append((msg, color))

    manager = FieldManager(client, comparator, output_fn)
    return manager, output_log


# --- _get_field_resolved tries c-prefix first, then raw name ---
# For all tests: get_field calls go: c-prefix, then raw (if c-prefix fails)


def test_field_does_not_exist_creates():
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.get_field.side_effect = [
        (404, None),  # CHECK c-prefix
        (404, None),  # CHECK raw
    ]
    client.create_field.return_value = (200, {"name": "cTestField"})

    manager, output_log = make_manager(client)
    report = manager.run(make_program())

    assert report.results[0].status == FieldStatus.CREATED
    assert report.results[0].verified is True
    assert report.summary.created == 1


def test_field_exists_via_c_prefix():
    """Field found via c-prefix lookup (first try)."""
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    # c-prefix found immediately — no raw name lookup needed
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    comparator = MagicMock(spec=FieldComparator)
    comparator.compare.return_value = ComparisonResult(matches=True)

    manager, output_log = make_manager(client, comparator)
    report = manager.run(make_program())

    assert report.results[0].status == FieldStatus.SKIPPED
    client.create_field.assert_not_called()


def test_field_exists_via_raw_name():
    """Field found via raw name (system field, not c-prefixed)."""
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.get_field.side_effect = [
        (404, None),  # c-prefix — not found
        (200, {"type": "varchar", "label": "Test"}),  # raw — found
    ]

    comparator = MagicMock(spec=FieldComparator)
    comparator.compare.return_value = ComparisonResult(matches=True)

    manager, output_log = make_manager(client, comparator)
    report = manager.run(make_program())

    assert report.results[0].status == FieldStatus.SKIPPED
    client.create_field.assert_not_called()


def test_field_exists_and_matches_skips():
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    comparator = MagicMock(spec=FieldComparator)
    comparator.compare.return_value = ComparisonResult(matches=True)

    manager, output_log = make_manager(client, comparator)
    report = manager.run(make_program())

    assert report.results[0].status == FieldStatus.SKIPPED
    assert report.summary.skipped == 1
    client.update_field.assert_not_called()
    client.create_field.assert_not_called()


def test_field_exists_and_differs_updates():
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    # c-prefix found on first try
    client.get_field.return_value = (200, {"type": "varchar", "label": "Old"})
    client.update_field.return_value = (200, {})

    comparator = MagicMock(spec=FieldComparator)
    comparator.compare.return_value = ComparisonResult(
        matches=False, differences=["label"]
    )

    manager, output_log = make_manager(client, comparator)
    report = manager.run(make_program())

    assert report.results[0].status == FieldStatus.UPDATED
    assert report.results[0].verified is True
    assert report.results[0].changes == ["label"]


def test_type_conflict_skips():
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.get_field.return_value = (200, {"type": "text", "label": "Test"})

    comparator = MagicMock(spec=FieldComparator)
    comparator.compare.return_value = ComparisonResult(
        matches=False, type_conflict=True, differences=["type"]
    )

    manager, output_log = make_manager(client, comparator)
    report = manager.run(make_program())

    assert report.results[0].status == FieldStatus.SKIPPED_TYPE_CONFLICT
    client.update_field.assert_not_called()


def test_401_aborts_run():
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    # 401 on first call (c-prefix) — aborts immediately
    client.get_field.return_value = (401, None)

    manager, output_log = make_manager(client)
    program = make_program([
        FieldDefinition(name="field1", type="varchar", label="F1"),
        FieldDefinition(name="field2", type="varchar", label="F2"),
    ])
    report = manager.run(program)

    assert report.summary.errors == 1
    assert len(report.results) == 1
    assert any("401" in msg for msg, _ in output_log)


def test_403_continues():
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.get_field.side_effect = [
        (403, None),  # field1 c-prefix
        (403, None),  # field1 raw
        (200, {"type": "varchar", "label": "F2"}),  # field2 c-prefix — found
    ]

    comparator = MagicMock(spec=FieldComparator)
    comparator.compare.return_value = ComparisonResult(matches=True)

    manager, output_log = make_manager(client, comparator)
    program = make_program([
        FieldDefinition(name="field1", type="varchar", label="F1"),
        FieldDefinition(name="field2", type="varchar", label="F2"),
    ])
    report = manager.run(program)

    assert len(report.results) == 2
    assert report.results[0].status == FieldStatus.ERROR
    assert report.results[1].status == FieldStatus.SKIPPED


def test_connection_error_continues():
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.get_field.side_effect = [
        (-1, None),  # field1 c-prefix
        (-1, None),  # field1 raw
        (200, {"type": "varchar", "label": "F2"}),  # field2 c-prefix — found
    ]

    comparator = MagicMock(spec=FieldComparator)
    comparator.compare.return_value = ComparisonResult(matches=True)

    manager, output_log = make_manager(client, comparator)
    program = make_program([
        FieldDefinition(name="field1", type="varchar", label="F1"),
        FieldDefinition(name="field2", type="varchar", label="F2"),
    ])
    report = manager.run(program)

    assert report.results[0].status == FieldStatus.ERROR
    assert report.results[1].status == FieldStatus.SKIPPED


def test_successful_create_is_verified():
    """A 200 response from create is treated as verified."""
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.get_field.side_effect = [
        (404, None),  # CHECK c-prefix
        (404, None),  # CHECK raw
    ]
    client.create_field.return_value = (200, {})

    manager, output_log = make_manager(client)
    report = manager.run(make_program())

    assert report.results[0].status == FieldStatus.CREATED
    assert report.results[0].verified is True


def test_409_falls_back_to_update():
    """409 on create extracts the actual name and updates instead."""
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.get_field.side_effect = [
        (404, None),  # CHECK c-prefix
        (404, None),  # CHECK raw
    ]
    client.create_field.return_value = (
        409,
        {
            "messageTranslation": {
                "label": "fieldAlreadyExists",
                "data": {"field": "cTestField"},
            }
        },
    )
    client.update_field.return_value = (200, {})

    manager, output_log = make_manager(client)
    report = manager.run(make_program())

    assert report.results[0].status == FieldStatus.UPDATED
    assert report.results[0].verified is True
    # Verify update was called with the c-prefixed name
    client.update_field.assert_called_once()
    call_args = client.update_field.call_args
    assert call_args[0][1] == "cTestField"


def test_verify_standalone():
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    # c-prefix found immediately
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    comparator = MagicMock(spec=FieldComparator)
    comparator.compare.return_value = ComparisonResult(matches=True)

    manager, output_log = make_manager(client, comparator)
    report = manager.verify(make_program())

    assert report.operation == "verify"
    assert report.results[0].status == FieldStatus.VERIFIED
    assert report.results[0].verified is True


def test_verify_field_not_found():
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.get_field.side_effect = [
        (404, None),  # c-prefix
        (404, None),  # raw
    ]

    manager, output_log = make_manager(client)
    report = manager.verify(make_program())

    assert report.results[0].status == FieldStatus.VERIFICATION_FAILED


def test_preview_shows_planned_changes():
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.get_field.side_effect = [
        (404, None),  # field1 c-prefix
        (404, None),  # field1 raw — not found
        (200, {"type": "varchar", "label": "Old"}),  # field2 c-prefix — found
        (200, {"type": "varchar", "label": "Test"}),  # field3 c-prefix — found
    ]

    comparator = MagicMock(spec=FieldComparator)
    comparator.compare.side_effect = [
        ComparisonResult(matches=False, differences=["label"]),  # field2
        ComparisonResult(matches=True),  # field3
    ]

    manager, output_log = make_manager(client, comparator)
    program = make_program([
        FieldDefinition(name="field1", type="varchar", label="F1"),
        FieldDefinition(name="field2", type="varchar", label="F2"),
        FieldDefinition(name="field3", type="varchar", label="Test"),
    ])
    report = manager.preview(program)

    assert report.operation == "preview"
    assert len(report.results) == 3
    assert report.results[0].status == FieldStatus.CREATED
    assert report.results[1].status == FieldStatus.UPDATED
    assert report.results[1].changes == ["label"]
    assert report.results[2].status == FieldStatus.SKIPPED

    client.create_field.assert_not_called()
    client.update_field.assert_not_called()

    messages = [msg for msg, _ in output_log]
    assert any("CREATE" in msg for msg in messages)
    assert any("UPDATE" in msg and "label" in msg for msg in messages)
    assert any("no changes" in msg for msg in messages)


def test_build_payload_includes_only_specified():
    manager, _ = make_manager()
    field_def = FieldDefinition(
        name="testField",
        type="varchar",
        label="Test",
        required=True,
    )
    payload = manager._build_payload(field_def)
    assert payload["name"] == "testField"
    assert payload["type"] == "varchar"
    assert payload["label"] == "Test"
    assert payload["required"] is True
    assert "readOnly" not in payload
    assert "audited" not in payload
    assert "options" not in payload


def test_custom_field_name():
    assert FieldManager._custom_field_name("contactType") == "cContactType"
    assert FieldManager._custom_field_name("isMentor") == "cIsMentor"
    assert FieldManager._custom_field_name("mentorStatus") == "cMentorStatus"
