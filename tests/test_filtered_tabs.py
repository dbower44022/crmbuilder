"""Tests for filtered-tab parsing, validation, and manager orchestration."""

import datetime
import json
from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.filtered_tab_manager import (
    FilteredTabManager,
    FilteredTabManagerError,
)
from espo_impl.core.models import (
    EntityAction,
    FilteredTabStatus,
    InstanceProfile,
    InstanceRole,
)

# ─── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def loader():
    return ConfigLoader()


def _profile(project_folder: str | None = None) -> InstanceProfile:
    return InstanceProfile(
        name="test",
        url="https://crm.example.com",
        api_key="key",
        project_folder=project_folder,
        role=InstanceRole.TARGET,
    )


def _make_manager(
    *,
    list_response=(200, {"total": 0, "list": []}),
    create_response=(200, {"id": "rf-new-id-12345"}),
    bundle_root=None,
    project_folder=None,
):
    """Build a manager with a mocked API client."""
    client = MagicMock()
    client.profile = _profile(project_folder)
    client.list_report_filters.return_value = list_response
    client.create_report_filter.return_value = create_response

    output = MagicMock()
    mgr = FilteredTabManager(
        client=client,
        output_fn=output,
        bundle_root=bundle_root,
        run_timestamp=datetime.datetime(2026, 5, 3, 12, 0, 0, tzinfo=datetime.UTC),
    )
    return mgr, client, output


def _basic_program(loader: ConfigLoader, tmp_path):
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            filteredTabs:
              - id: my_open
                scope: MyOpenEngagements
                label: "My Open Engagements"
                filter:
                  all:
                    - { field: status, op: equals, value: "Open" }
                    - { field: assignedUserId, op: equals, value: "$user" }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Open", "Closed"]
              - name: assignedUserId
                type: varchar
                label: "Assigned User"
    """)
    path = tmp_path / "program.yaml"
    path.write_text(content)
    return loader.load_program(path)


# ─── Parsing ─────────────────────────────────────────────────────


def test_parse_filtered_tabs_absent(loader, tmp_path):
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "no_tabs.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.entities[0].filtered_tabs == []
    assert program.entities[0].filtered_tabs_raw is None


def test_parse_filtered_tabs_basic(loader, tmp_path):
    program = _basic_program(loader, tmp_path)
    tabs = program.entities[0].filtered_tabs
    assert len(tabs) == 1
    tab = tabs[0]
    assert tab.id == "my_open"
    assert tab.scope == "MyOpenEngagements"
    assert tab.label == "My Open Engagements"
    assert tab.filter is not None  # AllNode
    assert tab.acl == "boolean"  # default
    assert tab.nav_order is None


def test_parse_filtered_tabs_explicit_acl_and_navorder(loader, tmp_path):
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            filteredTabs:
              - id: t1
                scope: TabOne
                label: "Tab One"
                acl: team
                navOrder: 3
                filter:
                  - { field: status, op: equals, value: "Open" }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Open", "Closed"]
    """)
    path = tmp_path / "p.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    tab = program.entities[0].filtered_tabs[0]
    assert tab.acl == "team"
    assert tab.nav_order == 3


# ─── Validation ──────────────────────────────────────────────────


def test_validate_missing_id(loader, tmp_path):
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            filteredTabs:
              - scope: NoId
                label: "No Id"
                filter:
                  - { field: status, op: equals, value: "Open" }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Open"]
    """)
    path = tmp_path / "p.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("missing required property 'id'" in e for e in errors)


def test_validate_invalid_scope(loader, tmp_path):
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            filteredTabs:
              - id: x
                scope: "lower-case bad"
                label: "Bad"
                filter:
                  - { field: status, op: equals, value: "Open" }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Open"]
    """)
    path = tmp_path / "p.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("PascalCase" in e for e in errors)


def test_validate_unknown_filter_field(loader, tmp_path):
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            filteredTabs:
              - id: x
                scope: MyTab
                label: "Bad"
                filter:
                  - { field: ghostField, op: equals, value: "Open" }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Open"]
    """)
    path = tmp_path / "p.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("ghostField" in e for e in errors)


def test_validate_duplicate_scope_across_entities(loader, tmp_path):
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            filteredTabs:
              - id: a
                scope: SharedScope
                label: "A"
                filter:
                  - { field: status, op: equals, value: "Open" }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Open"]
          Account:
            filteredTabs:
              - id: b
                scope: SharedScope
                label: "B"
                filter:
                  - { field: name, op: isNotNull }
            fields:
              - name: name
                type: varchar
                label: "Name"
    """)
    path = tmp_path / "p.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "duplicate scope 'SharedScope'" in e for e in errors
    )


def test_validate_invalid_acl(loader, tmp_path):
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            filteredTabs:
              - id: x
                scope: MyTab
                label: "Bad"
                acl: nonsense
                filter:
                  - { field: status, op: equals, value: "Open" }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Open"]
    """)
    path = tmp_path / "p.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("invalid value 'nonsense'" in e for e in errors)


# ─── Manager — Report Filter creation + bundle ──────────────────


def test_manager_creates_report_filter_and_bundle(
    loader, tmp_path,
):
    program = _basic_program(loader, tmp_path)
    bundle_root = tmp_path / "bundle"
    mgr, client, _ = _make_manager(bundle_root=bundle_root)

    results = mgr.process_filtered_tabs(program)

    assert len(results) == 1
    assert results[0].status == FilteredTabStatus.CREATED
    assert results[0].report_filter_id == "rf-new-id-12345"

    # Report Filter API was called with the right entity + name
    create_args, _kw = client.create_report_filter.call_args
    payload = create_args[0]
    # Engagement is custom -> CEngagement
    assert payload["entityType"] == "CEngagement"
    assert payload["name"] == "My Open Engagements"
    where = payload["data"]["where"]
    # Top level is AllNode -> single "and" group
    assert where == [{
        "type": "and",
        "value": [
            {"type": "equals", "attribute": "status", "value": "Open"},
            {"type": "currentUser", "attribute": "assignedUserId"},
        ],
    }]

    # Bundle was written
    scope_file = bundle_root / "scopes" / "MyOpenEngagements.json"
    client_def_file = bundle_root / "clientDefs" / "MyOpenEngagements.json"
    global_file = bundle_root / "i18n" / "en_US" / "Global.json"
    manifest_file = bundle_root / "manifest.json"
    readme_file = bundle_root / "README.txt"

    assert scope_file.exists()
    assert client_def_file.exists()
    assert global_file.exists()
    assert manifest_file.exists()
    assert readme_file.exists()

    scope = json.loads(scope_file.read_text())
    assert scope == {
        "entity": False,
        "tab": True,
        "acl": "boolean",
        "disabled": False,
        "module": "Custom",
        "isCustom": True,
    }

    client_def = json.loads(client_def_file.read_text())
    assert client_def == {
        "controller": "record",
        "entity": "CEngagement",
        "defaultFilter": "reportFilterrf-new-id-12345",
    }

    global_data = json.loads(global_file.read_text())
    assert global_data == {
        "scopeNames": {"MyOpenEngagements": "My Open Engagements"},
    }


def test_manager_advanced_pack_missing(loader, tmp_path):
    """404 from /ReportFilter -> NOT_SUPPORTED, bundle still emitted with placeholder."""
    program = _basic_program(loader, tmp_path)
    bundle_root = tmp_path / "bundle"
    mgr, client, _ = _make_manager(
        list_response=(404, {"message": "Not found"}),
        bundle_root=bundle_root,
    )

    results = mgr.process_filtered_tabs(program)

    assert len(results) == 1
    assert results[0].status == FilteredTabStatus.NOT_SUPPORTED
    assert results[0].report_filter_id is None
    # No create attempted
    client.create_report_filter.assert_not_called()

    # Bundle still written with placeholder defaultFilter
    client_def = json.loads(
        (bundle_root / "clientDefs" / "MyOpenEngagements.json").read_text()
    )
    assert client_def["defaultFilter"] == "REPLACE_WITH_reportFilter<id>"


def test_manager_existing_filter_skipped(loader, tmp_path):
    """A Report Filter with the same name already exists -> SKIPPED, id reused."""
    program = _basic_program(loader, tmp_path)
    bundle_root = tmp_path / "bundle"
    mgr, client, _ = _make_manager(
        list_response=(
            200,
            {
                "total": 1,
                "list": [
                    {"id": "rf-existing-001", "name": "My Open Engagements"},
                ],
            },
        ),
        bundle_root=bundle_root,
    )

    results = mgr.process_filtered_tabs(program)
    assert results[0].status == FilteredTabStatus.SKIPPED
    assert results[0].report_filter_id == "rf-existing-001"
    client.create_report_filter.assert_not_called()

    # Bundle uses the existing filter id
    client_def = json.loads(
        (bundle_root / "clientDefs" / "MyOpenEngagements.json").read_text()
    )
    assert client_def["defaultFilter"] == "reportFilterrf-existing-001"


def test_manager_skips_deleted_entities(loader, tmp_path):
    """Entity with action: delete is skipped entirely."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            action: delete
            filteredTabs:
              - id: x
                scope: MyTab
                label: "Tab"
                filter:
                  - { field: status, op: equals, value: "Open" }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Open"]
    """)
    path = tmp_path / "p.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.entities[0].action == EntityAction.DELETE

    bundle_root = tmp_path / "bundle"
    mgr, client, _ = _make_manager(bundle_root=bundle_root)
    results = mgr.process_filtered_tabs(program)

    assert results == []
    client.list_report_filters.assert_not_called()
    # No bundle directory created when there were no entries
    assert not bundle_root.exists()


def test_manager_401_raises(loader, tmp_path):
    program = _basic_program(loader, tmp_path)
    mgr, _, _ = _make_manager(
        list_response=(401, {"message": "Unauthorized"}),
        bundle_root=tmp_path / "bundle",
    )
    with pytest.raises(FilteredTabManagerError):
        mgr.process_filtered_tabs(program)


def test_manager_create_failure(loader, tmp_path):
    program = _basic_program(loader, tmp_path)
    bundle_root = tmp_path / "bundle"
    mgr, client, _ = _make_manager(
        list_response=(200, {"total": 0, "list": []}),
        create_response=(400, {"message": "validation failed"}),
        bundle_root=bundle_root,
    )
    results = mgr.process_filtered_tabs(program)
    assert results[0].status == FilteredTabStatus.ERROR
    # Bundle still written with placeholder
    client_def = json.loads(
        (bundle_root / "clientDefs" / "MyOpenEngagements.json").read_text()
    )
    assert client_def["defaultFilter"] == "REPLACE_WITH_reportFilter<id>"


def test_manager_in_operator_with_list_value(loader, tmp_path):
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            filteredTabs:
              - id: t
                scope: ActiveTab
                label: "Active"
                filter:
                  - { field: status, op: in, value: ["Open", "InProgress"] }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Open", "InProgress", "Closed"]
    """)
    path = tmp_path / "p.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    mgr, client, _ = _make_manager(bundle_root=tmp_path / "bundle")
    mgr.process_filtered_tabs(program)
    payload = client.create_report_filter.call_args[0][0]
    where = payload["data"]["where"]
    # Shorthand list filter parses as AllNode([Leaf]); the manager
    # renders that to a single "and" group, which is EspoCRM's
    # canonical top-level shape.
    assert where == [{
        "type": "and",
        "value": [
            {"type": "in", "attribute": "status",
             "value": ["Open", "InProgress"]},
        ],
    }]


def test_manager_isnull_emits_no_value(loader, tmp_path):
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            filteredTabs:
              - id: t
                scope: UnassignedTab
                label: "Unassigned"
                filter:
                  - { field: assignedUserId, op: isNull }
            fields:
              - name: assignedUserId
                type: varchar
                label: "Assigned User"
    """)
    path = tmp_path / "p.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    mgr, client, _ = _make_manager(bundle_root=tmp_path / "bundle")
    mgr.process_filtered_tabs(program)
    payload = client.create_report_filter.call_args[0][0]
    assert payload["data"]["where"] == [{
        "type": "and",
        "value": [{"type": "isNull", "attribute": "assignedUserId"}],
    }]
