"""Tests for the layout builder."""

from tools.docgen.builders.layout_builder import build_layout_sections
from tools.docgen.models import DocParagraph


def test_panel_description_rendered():
    entities = [
        ("Contact", {
            "fields": [
                {"name": "foo", "type": "varchar", "label": "Foo"}
            ],
            "layout": {
                "detail": {
                    "panels": [
                        {
                            "label": "General",
                            "description": "Core contact info",
                            "rows": [["foo"]],
                        }
                    ]
                }
            },
        })
    ]
    section = build_layout_sections(entities)
    entity_sec = section.content[0]
    detail_sec = entity_sec.content[0]
    # Should have panel header and description paragraph
    paragraphs = [
        c for c in detail_sec.content if isinstance(c, DocParagraph)
    ]
    assert any("Core contact info" in p.text for p in paragraphs)


def test_panel_with_explicit_rows():
    entities = [
        ("Contact", {
            "fields": [
                {"name": "foo", "type": "varchar", "label": "Foo"},
                {"name": "bar", "type": "varchar", "label": "Bar"},
            ],
            "layout": {
                "detail": {
                    "panels": [
                        {
                            "label": "General",
                            "rows": [["foo", "bar"]],
                        }
                    ]
                }
            },
        })
    ]
    section = build_layout_sections(entities)
    entity_sec = section.content[0]
    detail_sec = entity_sec.content[0]
    paragraphs = [
        c for c in detail_sec.content if isinstance(c, DocParagraph)
    ]
    field_text = [p.text for p in paragraphs if "Fields:" in p.text]
    assert len(field_text) == 1
    assert "foo" in field_text[0]
    assert "bar" in field_text[0]


def test_panel_with_tabs():
    entities = [
        ("Contact", {
            "fields": [
                {"name": "f1", "type": "varchar", "label": "Field One", "category": "cat_a"},
            ],
            "layout": {
                "detail": {
                    "panels": [
                        {
                            "label": "Info",
                            "tabs": [
                                {"label": "Tab A", "category": "cat_a"},
                            ],
                        }
                    ]
                }
            },
        })
    ]
    section = build_layout_sections(entities)
    entity_sec = section.content[0]
    detail_sec = entity_sec.content[0]
    paragraphs = [
        c for c in detail_sec.content if isinstance(c, DocParagraph)
    ]
    assert any("Tab A" in p.text and "Field One" in p.text for p in paragraphs)


def test_dynamic_logic_visible_rendered():
    entities = [
        ("Contact", {
            "fields": [],
            "layout": {
                "detail": {
                    "panels": [
                        {
                            "label": "Mentor",
                            "dynamicLogicVisible": {
                                "attribute": "contactType",
                                "value": "Mentor",
                            },
                            "rows": [],
                        }
                    ]
                }
            },
        })
    ]
    section = build_layout_sections(entities)
    entity_sec = section.content[0]
    detail_sec = entity_sec.content[0]
    paragraphs = [
        c for c in detail_sec.content if isinstance(c, DocParagraph)
    ]
    assert any("contactType = Mentor" in p.text for p in paragraphs)
