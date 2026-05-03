"""Tests for saved-view parsing, validation, and short-circuit manager."""

from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.models import SavedViewStatus
from espo_impl.core.saved_view_manager import SavedViewManager


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


# ─── Manager NOT_SUPPORTED Short-Circuit Tests (Prompt D) ──────


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


def test_manager_short_circuits_without_api_calls():
    """process_saved_views must not call any API method."""
    program = _make_program([
        {
            "id": "active",
            "name": "Active",
            "filter": [{"field": "status", "op": "equals", "value": "Active"}],
        },
        {
            "id": "inactive",
            "name": "Inactive",
            "filter": [{"field": "status", "op": "equals", "value": "Inactive"}],
        },
    ])
    client = MagicMock()
    output = []
    mgr = SavedViewManager(client, lambda msg, color: output.append((msg, color)))
    results = mgr.process_saved_views(program)

    assert len(results) == 2
    assert all(r.status == SavedViewStatus.NOT_SUPPORTED for r in results)
    client.put_metadata.assert_not_called()
    client.get_client_defs.assert_not_called()


def test_manager_emits_not_supported_lines():
    """Each saved view emits a yellow [NOT SUPPORTED] line in expected format."""
    program = _make_program([{
        "id": "active",
        "name": "Active",
        "filter": [{"field": "status", "op": "equals", "value": "Active"}],
    }])
    client = MagicMock()
    output: list[tuple[str, str]] = []
    mgr = SavedViewManager(client, lambda msg, color: output.append((msg, color)))
    mgr.process_saved_views(program)

    assert any(
        "[NOT SUPPORTED]" in msg
        and "Contact.savedViews[active]" in msg
        and "manual config required" in msg
        and "—" in msg
        for msg, _ in output
    )
    assert all(color == "yellow" for _, color in output)


def test_manager_skips_delete_entities():
    """Saved views on entities marked DELETE are not surfaced."""
    from espo_impl.core.models import (
        EntityAction,
        EntityDefinition,
        FieldDefinition,
        ProgramFile,
        SavedView,
    )

    entity = EntityDefinition(
        name="OldEntity",
        fields=[FieldDefinition(name="x", type="varchar", label="X")],
        action=EntityAction.DELETE,
        saved_views=[SavedView(id="v1", name="V1")],
    )
    program = ProgramFile(
        version="1.1", description="Test", entities=[entity],
    )
    client = MagicMock()
    output = []
    mgr = SavedViewManager(client, lambda msg, color: output.append(msg))
    results = mgr.process_saved_views(program)

    assert results == []
    client.put_metadata.assert_not_called()


def test_manager_no_views_returns_empty():
    """An entity with no saved views produces no results."""
    from espo_impl.core.models import (
        EntityDefinition,
        FieldDefinition,
        ProgramFile,
    )

    entity = EntityDefinition(
        name="Contact",
        fields=[FieldDefinition(name="email", type="varchar", label="Email")],
    )
    program = ProgramFile(
        version="1.1", description="Test", entities=[entity],
    )
    client = MagicMock()
    mgr = SavedViewManager(client, lambda msg, color: None)
    results = mgr.process_saved_views(program)

    assert results == []
    client.put_metadata.assert_not_called()
