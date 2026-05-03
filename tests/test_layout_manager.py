"""Tests for the layout manager."""

from unittest.mock import MagicMock

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.layout_manager import LayoutManager
from espo_impl.core.models import (
    ColumnSpec,
    EntityDefinition,
    EntityLayoutStatus,
    FieldDefinition,
    LayoutSpec,
    PanelSpec,
    TabSpec,
)


def make_manager(client=None) -> tuple[LayoutManager, list]:
    if client is None:
        client = MagicMock(spec=EspoAdminClient)
    output_log: list[tuple[str, str]] = []

    def output_fn(msg, color):
        output_log.append((msg, color))

    manager = LayoutManager(client, output_fn)
    return manager, output_log


def make_fields(*specs) -> list[FieldDefinition]:
    """Create field definitions from (name, type, category) tuples."""
    return [
        FieldDefinition(name=n, type=t, label=n.title(), category=c)
        for n, t, c in specs
    ]


# --- Payload building tests ---


def test_build_list_payload():
    manager, _ = make_manager()
    layout = LayoutSpec(
        layout_type="list",
        columns=[
            ColumnSpec(field="name", width=30),
            ColumnSpec(field="contactType"),
        ],
    )
    custom_fields = {"contactType"}
    payload = manager._build_payload(layout, [], custom_fields)

    assert payload == [
        {"name": "name", "width": 30},
        {"name": "cContactType"},
    ]


def test_build_detail_payload_explicit_rows():
    manager, _ = make_manager()
    layout = LayoutSpec(
        layout_type="detail",
        panels=[
            PanelSpec(
                label="General",
                rows=[["name", "emailAddress"], ["contactType", None]],
            )
        ],
    )
    custom_fields = {"contactType"}
    payload = manager._build_payload(layout, [], custom_fields)

    assert len(payload) == 1
    panel = payload[0]
    assert panel["customLabel"] == "General"
    assert panel["rows"] == [
        [{"name": "name"}, {"name": "emailAddress"}],
        [{"name": "cContactType"}, False],
    ]


def test_build_detail_payload_tab_expansion():
    manager, _ = make_manager()
    fields = make_fields(
        ("isMentor", "bool", "mentor"),
        ("mentorStatus", "enum", "mentor"),
    )
    layout = LayoutSpec(
        layout_type="detail",
        panels=[
            PanelSpec(
                label="Mentor Info",
                tabBreak=True,
                tabLabel="Mentor",
                tabs=[
                    TabSpec(label="Details", category="mentor"),
                ],
            )
        ],
    )
    custom_fields = {"isMentor", "mentorStatus"}
    payload = manager._build_payload(layout, fields, custom_fields)

    assert len(payload) == 1
    panel = payload[0]
    assert panel["customLabel"] == "Details"
    assert panel["tabBreak"] is True
    assert panel["tabLabel"] == "Mentor"
    # 2 fields → 1 row of 2
    assert panel["rows"] == [
        [{"name": "cIsMentor"}, {"name": "cMentorStatus"}],
    ]


def test_tab_expansion_multiple_tabs():
    manager, _ = make_manager()
    fields = make_fields(
        ("field1", "varchar", "cat_a"),
        ("field2", "varchar", "cat_b"),
    )
    layout = LayoutSpec(
        layout_type="detail",
        panels=[
            PanelSpec(
                label="Parent",
                tabBreak=True,
                tabLabel="MyTab",
                tabs=[
                    TabSpec(label="Tab A", category="cat_a"),
                    TabSpec(label="Tab B", category="cat_b"),
                ],
            )
        ],
    )
    custom_fields = {"field1", "field2"}
    payload = manager._build_payload(layout, fields, custom_fields)

    # Should expand to 2 panels
    assert len(payload) == 2
    # First tab inherits tabBreak and tabLabel
    assert payload[0]["tabBreak"] is True
    assert payload[0]["tabLabel"] == "MyTab"
    assert payload[0]["customLabel"] == "Tab A"
    # Second tab does not
    assert payload[1]["tabBreak"] is False
    assert payload[1]["tabLabel"] is None
    assert payload[1]["customLabel"] == "Tab B"


def test_auto_row_wysiwyg_full_width():
    manager, _ = make_manager()
    fields = make_fields(
        ("title", "varchar", "info"),
        ("notes", "wysiwyg", "info"),
        ("status", "enum", "info"),
    )
    custom_fields = {"title", "notes", "status"}
    rows = manager._auto_generate_rows("info", fields, custom_fields)

    # title is normal (flushed before wysiwyg, padded), notes full-width, status padded
    assert rows == [
        ["title", None],    # single normal field padded
        ["notes"],          # full-width wysiwyg
        ["status", None],   # remaining normal field padded
    ]


def test_auto_row_padding():
    manager, _ = make_manager()
    fields = make_fields(
        ("field1", "varchar", "cat"),
        ("field2", "varchar", "cat"),
        ("field3", "varchar", "cat"),
    )
    custom_fields = {"field1", "field2", "field3"}
    rows = manager._auto_generate_rows("cat", fields, custom_fields)

    # 3 fields → row of 2 + row of 1 (padded with None)
    assert rows == [
        ["field1", "field2"],
        ["field3", None],
    ]


def test_dynamic_logic_translation():
    manager, _ = make_manager()
    custom_fields = {"contactType"}
    result = manager._build_dynamic_logic(
        {"attribute": "contactType", "value": "Mentor"},
        custom_fields,
    )

    assert result == {
        "conditionGroup": [
            {
                "type": "equals",
                "attribute": "cContactType",
                "value": "Mentor",
            }
        ]
    }


def test_dynamic_logic_none():
    manager, _ = make_manager()
    assert manager._build_dynamic_logic(None, set()) is None


def test_field_name_c_prefix_in_rows():
    manager, _ = make_manager()
    custom_fields = {"contactType", "isMentor"}
    rows = [["name", "contactType"], ["isMentor", None]]
    api_rows = manager._build_rows(rows, custom_fields)

    assert api_rows == [
        [{"name": "name"}, {"name": "cContactType"}],
        [{"name": "cIsMentor"}, False],
    ]


def test_native_field_no_prefix():
    """Native fields like 'name' and 'emailAddress' pass through."""
    assert LayoutManager._resolve_field_name("name", {"contactType"}) == "name"
    assert LayoutManager._resolve_field_name(
        "emailAddress", {"contactType"}
    ) == "emailAddress"


def test_custom_field_gets_prefix():
    assert LayoutManager._resolve_field_name(
        "contactType", {"contactType"}
    ) == "cContactType"


# --- Process tests ---


def test_layout_matches_skips():
    client = MagicMock(spec=EspoAdminClient)
    # Return a layout that matches what we'd build
    client.get_layout.return_value = (200, [
        {
            "customLabel": "General",
            "tabBreak": False,
            "tabLabel": None,
            "rows": [[{"name": "name"}]],
        }
    ])

    manager, output_log = make_manager(client)
    entity = EntityDefinition(
        name="Contact",
        fields=[],
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(label="General", rows=[["name"]]),
                ],
            )
        },
    )
    results = manager.process_layouts(entity, [])

    assert len(results) == 1
    assert results[0].status == EntityLayoutStatus.SKIPPED
    client.save_layout.assert_not_called()


def test_layout_differs_updates():
    client = MagicMock(spec=EspoAdminClient)
    # Return a different layout
    client.get_layout.return_value = (200, [
        {"customLabel": "Old Panel", "tabBreak": False, "tabLabel": None, "rows": []}
    ])
    client.save_layout.return_value = (200, {})

    manager, output_log = make_manager(client)
    entity = EntityDefinition(
        name="Contact",
        fields=[],
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(label="New Panel", rows=[["name"]]),
                ],
            )
        },
    )
    results = manager.process_layouts(entity, [])

    assert len(results) == 1
    assert results[0].status == EntityLayoutStatus.UPDATED
    client.save_layout.assert_called_once()


def test_401_raises_error():
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (401, None)

    manager, output_log = make_manager(client)
    entity = EntityDefinition(
        name="Contact",
        fields=[],
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[PanelSpec(label="Test")],
            )
        },
    )
    results = manager.process_layouts(entity, [])

    assert len(results) == 1
    assert results[0].status == EntityLayoutStatus.ERROR
    assert "401" in results[0].error


def test_403_continues():
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (403, None)

    manager, output_log = make_manager(client)
    entity = EntityDefinition(
        name="Contact",
        fields=[],
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[PanelSpec(label="Test")],
            )
        },
    )
    results = manager.process_layouts(entity, [])

    assert len(results) == 1
    assert results[0].status == EntityLayoutStatus.ERROR
    messages = [m for m, _ in output_log]
    assert any("403" in m for m in messages)


def test_dynamic_logic_inherited_by_tabs():
    """All expanded tab panels inherit dynamicLogicVisible from parent."""
    manager, _ = make_manager()
    fields = make_fields(
        ("f1", "varchar", "a"),
        ("f2", "varchar", "b"),
    )
    layout = LayoutSpec(
        layout_type="detail",
        panels=[
            PanelSpec(
                label="Parent",
                dynamicLogicVisible={
                    "attribute": "contactType",
                    "value": "Mentor",
                },
                tabs=[
                    TabSpec(label="Tab A", category="a"),
                    TabSpec(label="Tab B", category="b"),
                ],
            )
        ],
    )
    custom_fields = {"f1", "f2", "contactType"}
    payload = manager._build_payload(layout, fields, custom_fields)

    # Both tabs should have the dynamic logic
    for panel in payload:
        assert panel["dynamicLogicVisible"] is not None
        assert panel["dynamicLogicVisible"]["conditionGroup"][0]["attribute"] == "cContactType"


def test_save_layout_non_json_failure_surfaces_raw_text():
    """Parse-failed sentinel from save_layout surfaces raw text."""
    client = MagicMock(spec=EspoAdminClient)
    # Differing layout — manager will try to save
    client.get_layout.return_value = (200, [
        {"customLabel": "Old", "tabBreak": False, "tabLabel": None, "rows": []}
    ])
    client.save_layout.return_value = (
        500,
        {
            "_parse_failed": True,
            "_raw_text": "<html>500 server error</html>",
            "_status_code": 500,
        },
    )

    manager, output_log = make_manager(client)
    fields = [FieldDefinition(name="name", type="varchar", label="Name")]
    entity = EntityDefinition(
        name="Contact",
        fields=fields,
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[PanelSpec(label="New", rows=[["name"]])],
            )
        },
    )
    results = manager.process_layouts(entity, fields)

    assert results[0].status == EntityLayoutStatus.ERROR
    messages = [msg for msg, _ in output_log]
    assert any("non-JSON response" in msg for msg in messages)
    assert any("500 server error" in msg for msg in messages)
