"""Tests for the YAML loader."""

from textwrap import dedent

from tools.docgen.yaml_loader import load_programs, ordered_entities


def test_loads_entity_with_description(tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            description: "Represents individuals"
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    (tmp_path / "test.yaml").write_text(content)
    entities = load_programs(tmp_path)
    assert "Contact" in entities
    assert entities["Contact"]["description"] == "Represents individuals"


def test_loads_entity_without_description(tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    (tmp_path / "test.yaml").write_text(content)
    entities = load_programs(tmp_path)
    assert entities["Contact"].get("description") is None


def test_preserves_field_order(tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: zebra
                type: varchar
                label: "Zebra"
              - name: alpha
                type: varchar
                label: "Alpha"
              - name: middle
                type: varchar
                label: "Middle"
    """)
    (tmp_path / "test.yaml").write_text(content)
    entities = load_programs(tmp_path)
    fields = entities["Contact"]["fields"]
    assert [f["name"] for f in fields] == ["zebra", "alpha", "middle"]


def test_ordered_entities_follows_canonical_order(tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Workshop:
            fields: []
          Contact:
            fields: []
          Account:
            fields: []
    """)
    (tmp_path / "test.yaml").write_text(content)
    entities = load_programs(tmp_path)
    ordered = ordered_entities(entities)
    names = [n for n, _ in ordered]
    assert names.index("Account") < names.index("Contact")
    assert names.index("Contact") < names.index("Workshop")
