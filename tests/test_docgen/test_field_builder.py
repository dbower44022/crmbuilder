"""Tests for the field builder."""

from tools.docgen.builders.field_builder import (
    _c_prefix,
    _get_display_type,
    _truncate,
    build_field_sections,
)


def test_c_prefix():
    assert _c_prefix("contactType") == "cContactType"
    assert _c_prefix("isMentor") == "cIsMentor"


def test_display_type_mapping():
    assert _get_display_type("varchar") == "Text"
    assert _get_display_type("wysiwyg") == "Rich Text"
    assert _get_display_type("bool") == "Boolean"
    assert _get_display_type("enum") == "Enum"
    assert _get_display_type("multiEnum") == "Multi-select"
    assert _get_display_type("int") == "Integer"
    assert _get_display_type("datetime") == "Date/Time"


def test_truncate_short():
    assert _truncate("short text") == "short text"


def test_truncate_long():
    long_text = "a" * 250
    result = _truncate(long_text)
    assert len(result) == 203  # 200 + "..."
    assert result.endswith("...")


def test_description_column_present():
    entities = [
        ("Contact", {
            "fields": [
                {
                    "name": "foo",
                    "type": "varchar",
                    "label": "Foo",
                    "description": "A test field",
                }
            ]
        })
    ]
    section = build_field_sections(entities)
    table = section.content[0].content[0]
    assert "Description" in table.headers
    # Find description column index
    desc_idx = table.headers.index("Description")
    assert table.rows[0][desc_idx] == "A test field"


def test_missing_description_shows_dash():
    entities = [
        ("Contact", {
            "fields": [
                {"name": "foo", "type": "varchar", "label": "Foo"}
            ]
        })
    ]
    section = build_field_sections(entities)
    table = section.content[0].content[0]
    desc_idx = table.headers.index("Description")
    assert table.rows[0][desc_idx] == "\u2014"


def test_internal_name_has_c_prefix():
    entities = [
        ("Contact", {
            "fields": [
                {"name": "contactType", "type": "enum", "label": "Type", "options": ["A"]}
            ]
        })
    ]
    section = build_field_sections(entities)
    table = section.content[0].content[0]
    name_idx = table.headers.index("Internal Name")
    assert "cContactType" in table.rows[0][name_idx]


def test_fields_grouped_by_category():
    entities = [
        ("Contact", {
            "fields": [
                {"name": "f1", "type": "varchar", "label": "F1", "category": "cat_a"},
                {"name": "f2", "type": "varchar", "label": "F2", "category": "cat_b"},
                {"name": "f3", "type": "varchar", "label": "F3", "category": "cat_a"},
            ]
        })
    ]
    section = build_field_sections(entities)
    table = section.content[0].content[0]
    # Should have category header rows
    first_col_values = [r[0] for r in table.rows]
    assert any("cat_a" in v for v in first_col_values)
    assert any("cat_b" in v for v in first_col_values)


def test_enum_notes_inline():
    entities = [
        ("Contact", {
            "fields": [
                {
                    "name": "status",
                    "type": "enum",
                    "label": "Status",
                    "options": ["A", "B", "C"],
                }
            ]
        })
    ]
    section = build_field_sections(entities)
    table = section.content[0].content[0]
    notes_idx = table.headers.index("Notes")
    assert "Values: A, B, C" in table.rows[0][notes_idx]


def test_enum_notes_appendix_reference():
    entities = [
        ("Contact", {
            "fields": [
                {
                    "name": "status",
                    "type": "enum",
                    "label": "Status",
                    "options": [f"opt{i}" for i in range(10)],
                }
            ]
        })
    ]
    section = build_field_sections(entities)
    table = section.content[0].content[0]
    notes_idx = table.headers.index("Notes")
    assert "Appendix A" in table.rows[0][notes_idx]
