"""Relationship write-back: surgical property sets in the relationships: block."""
from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.locators import RelationshipLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory, Difference
from espo_impl.core.reconcile.patcher import apply_relationship_change
from espo_impl.core.reconcile.reconciler import apply_reconciliation

FIXTURE = '''\
content_version: "1.0.0"
relationships:

  - name: sessionMentorAttendees
    entity: Session
    entityForeign: Contact
    linkType: manyToMany
    link: mentorAttendees
    linkForeign: sessionsAsMentorAttendee
    label: "Mentor Attendees"
    labelForeign: "Sessions (as Mentor Attendee)"
    audited: false

  - name: sessionEngagement
    entity: Session
    entityForeign: Engagement
    linkType: manyToOne
    link: engagement
    linkForeign: sessions
    label: "Engagement"
    labelForeign: "Sessions"   # untouched
    audited: false
'''


def _reparse(t):
    return YAML().load(t)


def _changed(prop, new, link="mentorAttendees", entity="Session"):
    return Difference(
        config_type=ConfigType.RELATIONSHIP, category=DiffCategory.CHANGED, entity=entity,
        locator=RelationshipLocator(entity, link, prop), property=prop, crm_value=new,
    )


def test_label_change_surgical():
    doc = YamlDocument(FIXTURE)
    apply_relationship_change(doc, RelationshipLocator("Session", "mentorAttendees", "label"),
                              "label", "Mentors Present")
    out = doc.render()
    assert 'label: "Mentors Present"' in out
    assert 'labelForeign: "Sessions (as Mentor Attendee)"' in out  # sibling intact
    assert 'labelForeign: "Sessions"   # untouched' in out          # other rel intact


def test_attr_name_maps_to_yaml_key():
    doc = YamlDocument(FIXTURE)
    # entity_foreign -> entityForeign; link_type -> linkType.
    apply_relationship_change(doc, RelationshipLocator("Session", "mentorAttendees", "entity_foreign"),
                              "entity_foreign", "Account")
    apply_relationship_change(doc, RelationshipLocator("Session", "mentorAttendees", "link_type"),
                              "link_type", "oneToMany")
    rel = _reparse(doc.render())["relationships"][0]
    assert rel["entityForeign"] == "Account"
    assert rel["linkType"] == "oneToMany"


def test_audited_bool_spelling_preserved():
    doc = YamlDocument(FIXTURE)
    apply_relationship_change(doc, RelationshipLocator("Session", "mentorAttendees", "audited"),
                              "audited", True)
    out = doc.render()
    assert "    audited: true" in out
    assert "audited: True" not in out


def test_matches_correct_relationship_by_entity_and_link():
    doc = YamlDocument(FIXTURE)
    apply_relationship_change(doc, RelationshipLocator("Session", "engagement", "label"),
                              "label", "Parent Engagement")
    rels = _reparse(doc.render())["relationships"]
    assert rels[0]["label"] == "Mentor Attendees"      # first untouched
    assert rels[1]["label"] == "Parent Engagement"     # second changed


def test_missing_relationship_raises():
    doc = YamlDocument(FIXTURE)
    try:
        apply_relationship_change(doc, RelationshipLocator("Session", "ghostLink", "label"),
                                  "label", "x")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for missing relationship")


def test_reconciler_applies_relationship_change(tmp_path):
    f = tmp_path / "MN-Session.yaml"
    f.write_text(FIXTURE)
    diff = _changed("label", "Mentors Present")
    diff = Difference(**{**diff.__dict__, "source_file": f})

    result = apply_reconciliation([diff])
    fr = result.files[0]
    assert len(fr.applied) == 1
    assert fr.new_version == "1.1.0"
    rel = _reparse(f.read_text())["relationships"][0]
    assert rel["label"] == "Mentors Present"
