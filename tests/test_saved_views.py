"""Tests for saved-view parsing, validation, and CHECK->ACT manager."""

from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.models import SavedViewStatus
from espo_impl.core.saved_view_manager import (
    SavedViewManager,
    SavedViewManagerError,
)


@pytest.fixture
def loader():
    return ConfigLoader()


# ─── Parsing Tests ───────────────────────────────────────────────


def test_parse_saved_views_absent(loader, tmp_path):
    """Entity without savedViews: block has empty saved_views list."""
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
    path = tmp_path / "no_views.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.entities[0].saved_views == []


def test_parse_saved_views_shorthand_filter(loader, tmp_path):
    """Shorthand filter (flat list) parses via parse_condition."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: active
                name: "Active Contacts"
                columns: [email, status]
                filter:
                  - { field: status, op: equals, value: "Active" }
                orderBy: { field: email, direction: asc }
            fields:
              - name: email
                type: varchar
                label: "Email"
              - name: status
                type: enum
                label: "Status"
                options: ["Active", "Inactive"]
    """)
    path = tmp_path / "shorthand.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    views = program.entities[0].saved_views
    assert len(views) == 1
    view = views[0]
    assert view.id == "active"
    assert view.name == "Active Contacts"
    assert view.columns == ["email", "status"]
    assert view.filter is not None  # AllNode
    assert len(view.order_by) == 1
    assert view.order_by[0].field == "email"
    assert view.order_by[0].direction == "asc"


def test_parse_saved_views_structured_filter(loader, tmp_path):
    """Structured filter (all/any blocks) parses via parse_condition."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: complex-view
                name: "Complex View"
                filter:
                  all:
                    - { field: status, op: equals, value: "Active" }
                    - any:
                        - { field: role, op: equals, value: "Admin" }
                        - { field: role, op: equals, value: "Manager" }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Active", "Inactive"]
              - name: role
                type: enum
                label: "Role"
                options: ["Admin", "Manager", "User"]
    """)
    path = tmp_path / "structured.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    views = program.entities[0].saved_views
    assert len(views) == 1
    assert views[0].filter is not None


def test_parse_orderby_list(loader, tmp_path):
    """orderBy as a list of objects parses correctly."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: multi-sort
                name: "Multi Sort"
                filter:
                  - { field: status, op: equals, value: "Active" }
                orderBy:
                  - { field: lastName, direction: asc }
                  - { field: firstName, direction: desc }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Active"]
              - name: lastName
                type: varchar
                label: "Last Name"
              - name: firstName
                type: varchar
                label: "First Name"
    """)
    path = tmp_path / "multi_sort.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    view = program.entities[0].saved_views[0]
    assert len(view.order_by) == 2
    assert view.order_by[0].field == "lastName"
    assert view.order_by[0].direction == "asc"
    assert view.order_by[1].field == "firstName"
    assert view.order_by[1].direction == "desc"


def test_parse_orderby_direction_defaults_to_asc(loader, tmp_path):
    """direction defaults to 'asc' when omitted."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: default-dir
                name: "Default Direction"
                filter:
                  - { field: status, op: equals, value: "Active" }
                orderBy: { field: email }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Active"]
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "default_dir.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    view = program.entities[0].saved_views[0]
    assert view.order_by[0].direction == "asc"


# ─── Validation Tests ────────────────────────────────────────────


def test_validate_duplicate_id(loader, tmp_path):
    """Duplicate id within entity produces validation error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: view-1
                name: "View One"
                filter:
                  - { field: status, op: equals, value: "Active" }
              - id: view-1
                name: "View Two"
                filter:
                  - { field: status, op: equals, value: "Inactive" }
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Active", "Inactive"]
    """)
    path = tmp_path / "dup_id.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("duplicate id 'view-1'" in e for e in errors)


def test_validate_unknown_column_field(loader, tmp_path):
    """Unknown field in columns: produces validation error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: bad-col
                name: "Bad Column"
                columns: [email, nonExistent]
                filter:
                  - { field: email, op: isNotNull }
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "bad_col.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("nonExistent" in e and "columns" in e for e in errors)


def test_validate_unknown_filter_field(loader, tmp_path):
    """Unknown field in filter leaf clause produces validation error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: bad-filter
                name: "Bad Filter"
                filter:
                  - { field: ghostField, op: equals, value: "x" }
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "bad_filter.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("ghostField" in e for e in errors)


def test_validate_unknown_orderby_field(loader, tmp_path):
    """Unknown field in orderBy produces validation error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: bad-order
                name: "Bad Order"
                filter:
                  - { field: email, op: isNotNull }
                orderBy: { field: missingField, direction: asc }
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "bad_order.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("missingField" in e and "orderBy" in e for e in errors)


def test_validate_invalid_direction(loader, tmp_path):
    """Invalid direction value produces validation error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: bad-dir
                name: "Bad Direction"
                filter:
                  - { field: email, op: isNotNull }
                orderBy: { field: email, direction: upward }
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "bad_dir.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("upward" in e and "direction" in e for e in errors)


def test_validate_missing_name(loader, tmp_path):
    """Missing name produces validation error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: no-name
                filter:
                  - { field: email, op: isNotNull }
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "no_name.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("missing required property 'name'" in e for e in errors)


def test_validate_missing_filter(loader, tmp_path):
    """Missing filter produces validation error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: no-filter
                name: "No Filter"
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "no_filter.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("missing required property 'filter'" in e for e in errors)


def test_validate_invalid_filter_shape(loader, tmp_path):
    """Invalid filter shape produces a clear error tied to the view id."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: bad-shape
                name: "Bad Shape"
                filter:
                  all: []
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "bad_shape.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("bad-shape" in e and "filter" in e for e in errors)


def test_validate_valid_saved_views(loader, tmp_path):
    """Valid saved views produce no validation errors."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            savedViews:
              - id: active
                name: "Active"
                columns: [email, status]
                filter:
                  - { field: status, op: equals, value: "Active" }
                orderBy: { field: email, direction: asc }
              - id: inactive
                name: "Inactive"
                filter:
                  - { field: status, op: equals, value: "Inactive" }
            fields:
              - name: email
                type: varchar
                label: "Email"
              - name: status
                type: enum
                label: "Status"
                options: ["Active", "Inactive"]
    """)
    path = tmp_path / "valid.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    # Filter out any errors not related to saved views
    sv_errors = [e for e in errors if "savedViews" in e]
    assert sv_errors == []


# ─── Manager CHECK->ACT Tests ───────────────────────────────────


def _make_program(saved_views_data):
    """Build a minimal ProgramFile with saved views for manager testing."""
    from espo_impl.core.condition_expression import parse_condition
    from espo_impl.core.models import (
        EntityDefinition,
        FieldDefinition,
        OrderByClause,
        ProgramFile,
        SavedView,
    )

    views = []
    for vd in saved_views_data:
        parsed_filter = None
        if "filter" in vd:
            parsed_filter = parse_condition(vd["filter"])
        order_by = []
        if "orderBy" in vd:
            raw_ob = vd["orderBy"]
            if isinstance(raw_ob, dict):
                order_by = [OrderByClause(
                    field=raw_ob.get("field", ""),
                    direction=raw_ob.get("direction", "asc"),
                )]
        views.append(SavedView(
            id=vd["id"],
            name=vd["name"],
            filter=parsed_filter,
            filter_raw=vd.get("filter"),
            columns=vd.get("columns"),
            order_by=order_by,
        ))

    entity = EntityDefinition(
        name="Contact",
        fields=[
            FieldDefinition(name="email", type="varchar", label="Email"),
            FieldDefinition(
                name="status", type="enum", label="Status",
                options=["Active", "Inactive"],
            ),
        ],
        saved_views=views,
    )
    return ProgramFile(
        version="1.1",
        description="Test",
        entities=[entity],
    )


def _mock_client(client_defs_response=None):
    """Create a mock API client."""
    client = MagicMock()
    if client_defs_response is None:
        client.get_client_defs.return_value = (200, {})
    else:
        client.get_client_defs.return_value = (200, client_defs_response)
    client.put_metadata.return_value = (200, {})
    return client


def test_manager_create_new_views():
    """Views absent on CRM are created."""
    program = _make_program([{
        "id": "active",
        "name": "Active",
        "filter": [{"field": "status", "op": "equals", "value": "Active"}],
    }])
    client = _mock_client()
    output = []
    mgr = SavedViewManager(client, lambda msg, color: output.append(msg))
    results = mgr.process_saved_views(program)

    assert len(results) == 1
    assert results[0].status == SavedViewStatus.CREATED
    assert results[0].view_id == "active"
    assert client.put_metadata.called


def test_manager_skip_matching_views():
    """Views matching CRM state are skipped."""
    from espo_impl.core.condition_expression import parse_condition, render_condition

    filter_raw = [{"field": "status", "op": "equals", "value": "Active"}]
    rendered = render_condition(parse_condition(filter_raw))

    existing = {
        "savedViews": [{
            "id": "active",
            "name": "Active",
            "filter": rendered,
        }],
    }
    program = _make_program([{
        "id": "active",
        "name": "Active",
        "filter": filter_raw,
    }])
    client = _mock_client(existing)
    output = []
    mgr = SavedViewManager(client, lambda msg, color: output.append(msg))
    results = mgr.process_saved_views(program)

    assert len(results) == 1
    assert results[0].status == SavedViewStatus.SKIPPED
    assert not client.put_metadata.called


def test_manager_update_differing_views():
    """Views differing from CRM state are updated."""
    existing = {
        "savedViews": [{
            "id": "active",
            "name": "Old Name",
            "filter": {"all": [{"field": "status", "op": "equals", "value": "Active"}]},
        }],
    }
    program = _make_program([{
        "id": "active",
        "name": "New Name",
        "filter": [{"field": "status", "op": "equals", "value": "Active"}],
    }])
    client = _mock_client(existing)
    output = []
    mgr = SavedViewManager(client, lambda msg, color: output.append(msg))
    results = mgr.process_saved_views(program)

    assert len(results) == 1
    assert results[0].status == SavedViewStatus.UPDATED
    assert client.put_metadata.called


def test_manager_drift_detection():
    """Views on CRM not in YAML are flagged as drift."""
    existing = {
        "savedViews": [
            {"id": "active", "name": "Active",
             "filter": {"all": [{"field": "status", "op": "equals", "value": "Active"}]}},
            {"id": "orphan", "name": "Orphan View",
             "filter": {"all": [{"field": "status", "op": "equals", "value": "X"}]}},
        ],
    }
    program = _make_program([{
        "id": "active",
        "name": "Active",
        "filter": [{"field": "status", "op": "equals", "value": "Active"}],
    }])
    client = _mock_client(existing)
    output = []
    mgr = SavedViewManager(client, lambda msg, color: output.append(msg))
    results = mgr.process_saved_views(program)

    statuses = {r.view_id: r.status for r in results}
    assert statuses.get("orphan") == SavedViewStatus.DRIFT
    assert any("DRIFT" in msg for msg in output)


def test_manager_auth_failure():
    """401 from API raises SavedViewManagerError."""
    program = _make_program([{
        "id": "active",
        "name": "Active",
        "filter": [{"field": "status", "op": "equals", "value": "Active"}],
    }])
    client = MagicMock()
    client.get_client_defs.return_value = (401, None)
    mgr = SavedViewManager(client, lambda msg, color: None)

    with pytest.raises(SavedViewManagerError, match="401"):
        mgr.process_saved_views(program)


def test_manager_connection_error():
    """Connection error results in ERROR status for all views."""
    program = _make_program([{
        "id": "active",
        "name": "Active",
        "filter": [{"field": "status", "op": "equals", "value": "Active"}],
    }])
    client = MagicMock()
    client.get_client_defs.return_value = (-1, None)
    output = []
    mgr = SavedViewManager(client, lambda msg, color: output.append(msg))
    results = mgr.process_saved_views(program)

    assert len(results) == 1
    assert results[0].status == SavedViewStatus.ERROR


def test_manager_write_failure_marks_error():
    """Failed metadata write marks created/updated views as errors."""
    program = _make_program([{
        "id": "active",
        "name": "Active",
        "filter": [{"field": "status", "op": "equals", "value": "Active"}],
    }])
    client = _mock_client()
    client.put_metadata.return_value = (500, None)
    output = []
    mgr = SavedViewManager(client, lambda msg, color: output.append(msg))
    results = mgr.process_saved_views(program)

    assert results[0].status == SavedViewStatus.ERROR
    assert results[0].error == "Failed to write metadata"


def test_manager_idempotency():
    """Running twice with identical state produces skip on second run."""
    from espo_impl.core.condition_expression import parse_condition, render_condition

    filter_raw = [{"field": "status", "op": "equals", "value": "Active"}]
    rendered = render_condition(parse_condition(filter_raw))

    # Simulate CRM state matching desired
    existing = {
        "savedViews": [{
            "id": "active",
            "name": "Active",
            "filter": rendered,
        }],
    }
    program = _make_program([{
        "id": "active",
        "name": "Active",
        "filter": filter_raw,
    }])

    # First run
    client = _mock_client(existing)
    mgr = SavedViewManager(client, lambda msg, color: None)
    results1 = mgr.process_saved_views(program)
    assert results1[0].status == SavedViewStatus.SKIPPED

    # Second run (same state)
    client2 = _mock_client(existing)
    mgr2 = SavedViewManager(client2, lambda msg, color: None)
    results2 = mgr2.process_saved_views(program)
    assert results2[0].status == SavedViewStatus.SKIPPED
