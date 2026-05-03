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
    payload = manager._build_payload(
        layout, [], custom_fields, auto_place_name=False
    )

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
    payload = manager._build_payload(
        layout, [], custom_fields, auto_place_name=False
    )

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
    payload = manager._build_payload(
        layout, fields, custom_fields, auto_place_name=False
    )

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
    payload = manager._build_payload(
        layout, fields, custom_fields, auto_place_name=False
    )

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
    payload = manager._build_payload(
        layout, fields, custom_fields, auto_place_name=False
    )

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


# --- Custom-entity c-prefix entry-point tests ---


def test_native_entity_layout_uses_c_prefix():
    """Custom fields on a native entity (Contact) are c-prefixed in
    layout cells, matching EspoCRM's auto-prefix behavior."""
    client = MagicMock(spec=EspoAdminClient)
    # Force a non-match so save_layout is invoked.
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contact",
        fields=make_fields(("contactType", "enum", "info")),
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(label="General", rows=[["contactType"]]),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    # Auto-placement prepends a `name` row; the c-prefix assertion
    # focuses on the row authored by the YAML.
    assert saved_payload[0]["rows"] == [
        [{"name": "name"}],
        [{"name": "cContactType"}],
    ]


def test_custom_entity_layout_skips_c_prefix():
    """Custom fields on a custom entity (Contribution) are NOT
    c-prefixed — EspoCRM stores them under their natural names."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
            ("contributionType", "enum", "ident"),
            ("notes", "wysiwyg", "ack"),
        ),
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Identification",
                        rows=[["amount", "contributionType"]],
                    ),
                    PanelSpec(label="Acknowledgment", rows=[["notes"]]),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    # Auto-placement prepends a `name` row to the first panel.
    assert saved_payload[0]["rows"] == [
        [{"name": "name"}],
        [{"name": "amount"}, {"name": "contributionType"}],
    ]
    assert saved_payload[1]["rows"] == [[{"name": "notes"}]]


def test_custom_entity_list_layout_skips_c_prefix():
    """List layout columns on a custom entity use natural names."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
            ("status", "enum", "ident"),
        ),
        layouts={
            "list": LayoutSpec(
                layout_type="list",
                columns=[
                    ColumnSpec(field="name", width=30),
                    ColumnSpec(field="amount", width=20),
                    ColumnSpec(field="status", width=20),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    assert saved_payload == [
        {"name": "name", "width": 30},
        {"name": "amount", "width": 20},
        {"name": "status", "width": 20},
    ]


def test_custom_entity_dynamic_logic_skips_c_prefix():
    """visibleWhen / dynamicLogicVisible attribute references on a
    custom entity layout use natural field names, not c-prefixed."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("contributionType", "enum", "ident"),
            ("nextGrantDeadline", "date", "grant"),
        ),
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Grant Details",
                        rows=[["nextGrantDeadline"]],
                        dynamicLogicVisible={
                            "attribute": "contributionType",
                            "value": "Grant",
                        },
                    ),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    panel = saved_payload[0]
    assert panel["dynamicLogicVisible"] == {
        "conditionGroup": [
            {
                "type": "equals",
                "attribute": "contributionType",
                "value": "Grant",
            }
        ]
    }


# --- List-layout comparator tests ---


def test_layouts_match_list_detects_different_names():
    """Two list payloads with different column names must not match.

    Pre-fix, the comparator only inspected customLabel/rows/
    tabBreak/tabLabel — none of which exist on flat list-column
    dicts — so any list payloads of equal length compared as
    matching. This test guards against that regression.
    """
    desired = [{"name": "amount", "width": 20}]
    current = [{"name": "cAmount", "width": 20}]
    assert LayoutManager._layouts_match(desired, current) is False


def test_layouts_match_list_detects_different_widths():
    """Two list payloads with same names but different widths must
    not match."""
    desired = [{"name": "amount", "width": 20}]
    current = [{"name": "amount", "width": 30}]
    assert LayoutManager._layouts_match(desired, current) is False


def test_layouts_match_list_identical_payloads_match():
    """Two structurally identical list payloads must match."""
    desired = [
        {"name": "name", "width": 30},
        {"name": "amount", "width": 20},
        {"name": "status"},
    ]
    current = [
        {"name": "name", "width": 30},
        {"name": "amount", "width": 20},
        {"name": "status"},
    ]
    assert LayoutManager._layouts_match(desired, current) is True


def test_custom_entity_list_layout_overwrites_stale_c_prefixed_state():
    """When a custom entity's list layout on the server still has
    pre-fix c-prefixed column names, Configure must detect the
    mismatch against the natural-name desired payload and overwrite.
    """
    client = MagicMock(spec=EspoAdminClient)
    # Simulate the broken pre-fix state on the server.
    client.get_layout.return_value = (
        200,
        [
            {"name": "name", "width": 30},
            {"name": "cAmount", "width": 20},
            {"name": "cStatus", "width": 20},
        ],
    )
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
            ("status", "enum", "ident"),
        ),
        layouts={
            "list": LayoutSpec(
                layout_type="list",
                columns=[
                    ColumnSpec(field="name", width=30),
                    ColumnSpec(field="amount", width=20),
                    ColumnSpec(field="status", width=20),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    # Comparator must have detected the mismatch — writer must run.
    assert client.save_layout.call_count == 1
    saved_payload = client.save_layout.call_args.args[2]
    assert saved_payload == [
        {"name": "name", "width": 30},
        {"name": "amount", "width": 20},
        {"name": "status", "width": 20},
    ]


# --- Auto-placement of `name` on detail layouts ---


def _process_with_settings_for_name(client, entity_settings):
    """Helper: build a Contribution-like custom entity with a
    detail layout that does NOT place `name`, optionally with the
    given EntitySettings, and run process_layouts."""
    from espo_impl.core.models import EntitySettings

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
            ("status", "enum", "ident"),
        ),
        settings=entity_settings,
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Identification",
                        rows=[["amount", "status"]],
                    ),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)
    _ = EntitySettings  # silence linter on the import-only line
    return client


def test_auto_place_name_default_true_prepends_name():
    """When the YAML does not place `name`, the engine prepends a
    name row to the first panel by default."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    _process_with_settings_for_name(client, entity_settings=None)

    saved_payload = client.save_layout.call_args.args[2]
    assert saved_payload[0]["rows"][0] == [{"name": "name"}]
    # original row preserved as second row
    assert saved_payload[0]["rows"][1] == [
        {"name": "amount"},
        {"name": "status"},
    ]


def test_auto_place_name_explicit_placement_not_duplicated():
    """When the YAML already places `name` somewhere, the engine
    does not add another."""
    from espo_impl.core.models import EntitySettings

    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(("amount", "currency", "ident")),
        settings=None,
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Identification",
                        rows=[["name"], ["amount"]],
                    ),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)
    _ = EntitySettings

    saved_payload = client.save_layout.call_args.args[2]
    # Panel still has exactly the two YAML-authored rows.
    assert saved_payload[0]["rows"] == [
        [{"name": "name"}],
        [{"name": "amount"}],
    ]


def test_auto_place_name_opt_out_skips_placement():
    """settings.autoPlaceName=False suppresses auto-placement."""
    from espo_impl.core.models import EntitySettings

    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    _process_with_settings_for_name(
        client, entity_settings=EntitySettings(autoPlaceName=False)
    )

    saved_payload = client.save_layout.call_args.args[2]
    # Only the YAML-authored row remains.
    assert saved_payload[0]["rows"] == [
        [{"name": "amount"}, {"name": "status"}]
    ]


def test_auto_place_name_skips_conditional_panel():
    """When the first panel has dynamicLogicVisible, name is
    prepended to the first always-visible panel instead."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
            ("nextGrantDeadline", "date", "grant"),
        ),
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Grant Details",
                        rows=[["nextGrantDeadline"]],
                        dynamicLogicVisible={
                            "attribute": "contributionType",
                            "value": "Grant",
                        },
                    ),
                    PanelSpec(
                        label="Identification",
                        rows=[["amount"]],
                    ),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    # Panel index 0 (conditional) is untouched.
    assert saved_payload[0]["rows"] == [[{"name": "nextGrantDeadline"}]]
    # Panel index 1 (always-visible) has name prepended.
    assert saved_payload[1]["rows"][0] == [{"name": "name"}]
    assert saved_payload[1]["rows"][1] == [{"name": "amount"}]


def test_auto_place_name_all_panels_conditional_falls_back_to_first():
    """When every panel is conditional, fall back to the first
    panel rather than skipping placement entirely."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
        ),
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Conditional",
                        rows=[["amount"]],
                        dynamicLogicVisible={
                            "attribute": "contributionType",
                            "value": "Grant",
                        },
                    ),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    # Better placed conditionally than not at all.
    assert saved_payload[0]["rows"][0] == [{"name": "name"}]
    assert saved_payload[0]["rows"][1] == [{"name": "amount"}]
