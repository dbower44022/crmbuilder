"""Top-level detect_drift composition test (offline, fake client + temp YAML).

Proves the engine assembles the desired side from real program files, captures
the live side for every config type, runs each comparator, and returns one flat
DriftReport. Per-comparator behaviour is covered by their own unit tests; this
asserts the wiring composes across FIELD / RELATIONSHIP / LAYOUT / ROLE / TEAM.
"""
from __future__ import annotations

from espo_impl.core.reconcile.engine import detect_drift
from espo_impl.core.reconcile.models import ConfigType, DiffCategory

_PROGRAM = """\
version: "1.0"
content_version: "1.0.0"
description: "engine test"
entities:
  Contact:
    fields:
      - name: title
        type: varchar
        label: "Title"
    layout:
      list:
        columns:
          - field: name
            width: 30
relationships:
  - name: contactManager
    entity: Contact
    entityForeign: User
    linkType: manyToOne
    link: manager
    linkForeign: managedContacts
    label: "Manager"
    labelForeign: "Managed Contacts"
    audited: false
roles:
  - name: Mentor
    description: "Original mentor desc"
teams:
  - name: Mentors
    description: "Original team desc"
"""


class _FakeClient:
    """A read-only fake covering every endpoint detect_drift touches."""

    def get_all_scopes(self):
        return (200, {"Contact": {"type": "Person", "entity": True}})

    def get_entity_field_list(self, espo_name):
        # entityDefs has no label; the i18n resolver supplies it.
        return (200, {"title": {"type": "varchar"}})

    def get_i18n(self):
        return (200, {
            "Contact": {
                "fields": {"title": "Account Title"},      # label drift
                "links": {"manager": "Manager"},           # matches YAML
            },
            "User": {"links": {"managedContacts": "Managed Contacts"}},
        })

    def get_all_links(self, espo_name):
        if espo_name == "Contact":
            return (200, {"manager": {
                "entity": "User", "foreign": "managedContacts",
                "type": "belongsTo", "audited": False,
            }})
        return (200, {})

    def get_layout(self, espo_name, layout_type):
        if (espo_name, layout_type) == ("Contact", "list"):
            return (200, [{"name": "name", "width": 40}])   # width drift 30->40
        return (200, False)

    def get_roles(self):
        return (200, {"list": [{"name": "Mentor", "description": "Changed mentor desc"}]})

    def get_teams(self):
        return (200, {"list": [{"name": "Mentors", "description": "Changed team desc"}]})


def test_detect_drift_composes_all_types(tmp_path):
    f = tmp_path / "MN-Contact.yaml"
    f.write_text(_PROGRAM)

    report = detect_drift(_FakeClient(), [f])

    assert report.unmapped_entities == []
    assert report.collisions == []

    by_type = {}
    for d in report.differences:
        by_type.setdefault(d.config_type, []).append(d)

    # Field label drift, surfaced with the owning file.
    field = by_type[ConfigType.FIELD]
    assert len(field) == 1
    assert field[0].category is DiffCategory.CHANGED
    assert field[0].property == "label"
    assert field[0].yaml_value == "Title"
    assert field[0].crm_value == "Account Title"
    assert field[0].source_file == f

    # Layout list width drift.
    layout = by_type[ConfigType.LAYOUT]
    assert len(layout) == 1
    assert layout[0].category is DiffCategory.CHANGED
    assert layout[0].locator.layout_type == "list"
    assert layout[0].source_file == f

    # Role + team description drift.
    assert [d.property for d in by_type[ConfigType.ROLE]] == ["description"]
    assert [d.property for d in by_type[ConfigType.TEAM]] == ["description"]

    # The matching relationship produces no drift (the path still ran).
    assert ConfigType.RELATIONSHIP not in by_type


def test_detect_drift_reports_unmapped_entity(tmp_path):
    f = tmp_path / "X.yaml"
    f.write_text(
        'version: "1.0"\ncontent_version: "1.0.0"\ndescription: "x"\n'
        "entities:\n  Ghost:\n    fields:\n      - name: foo\n        type: varchar\n"
        '        label: "Foo"\n'
    )

    # Ghost is not in the live scopes -> reported once as unmapped, not an error,
    # and its fields are NOT flooded into the diff as per-field YAML_ONLY rows.
    report = detect_drift(_FakeClient(), [f])

    assert "Ghost" in report.unmapped_entities
    assert not [d for d in report.differences if d.entity == "Ghost"]
