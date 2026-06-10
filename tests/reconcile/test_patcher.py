"""Phase 1 write-back proof: surgical, comment-preserving field edits.

The fixture mirrors the real CBM program-file shape — a name-keyed ``entities:``
map, a ``fields:`` sequence of block mappings, interspersed comments, a trailing
inline comment, and hand-aligned flow-style condition clauses (the exact thing a
whole-file ruamel re-dump would reformat). Every test asserts that *only* the
intended source line changes; everything else stays byte-for-byte identical.
"""
from __future__ import annotations

from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.patcher import set_field_property

# Note the deliberately mismatched column alignment in the flow clauses and the
# inner padding after "{" / before "}" — ruamel normalizes these on dump, so
# their survival proves we are splicing, not re-serializing.
FIXTURE = '''\
version: "1.0"
content_version: "1.0.0"

entities:

  # ---------------------------------------------------------------
  # Custom entity — Session
  # ---------------------------------------------------------------
  Session:
    fields:

      - name: sessionType
        type: enum
        label: "Session Type"
        required: false

      - name: meetingLocationType
        type: enum
        label: "Meeting Location Type"   # operator-facing label
        required: false
        requiredWhen:
          - { field: sessionType,    op: equals,   value: "In-Person" }
        visibleWhen:
          - { field: sessionType, op: equals, value: "In-Person" }
'''


def _changed_line_indices(before: str, after: str) -> list[int]:
    b = before.splitlines()
    a = after.splitlines()
    assert len(b) == len(a), "splice must not add or remove lines for a scalar set"
    return [i for i, (x, y) in enumerate(zip(b, a)) if x != y]


def test_set_label_changes_only_target_line():
    doc = YamlDocument(FIXTURE)
    set_field_property(doc, "Session", "meetingLocationType", "label", "Meeting Location")
    out = doc.render()

    changed = _changed_line_indices(FIXTURE, out)
    assert len(changed) == 1
    line = out.splitlines()[changed[0]]
    # New value, original double-quoting, leading indent AND trailing comment kept.
    assert line == '        label: "Meeting Location"   # operator-facing label'


def test_aligned_flow_clause_is_untouched():
    doc = YamlDocument(FIXTURE)
    set_field_property(doc, "Session", "sessionType", "label", "Type of Session")
    out = doc.render()

    # The hand-aligned, inner-padded flow clauses must survive verbatim — a
    # whole-file re-dump would have collapsed them to {field: ...}.
    assert "          - { field: sessionType,    op: equals,   value: \"In-Person\" }" in out
    assert "          - { field: sessionType, op: equals, value: \"In-Person\" }" in out


def test_set_bool_property():
    doc = YamlDocument(FIXTURE)
    set_field_property(doc, "Session", "sessionType", "required", True)
    out = doc.render()

    changed = _changed_line_indices(FIXTURE, out)
    assert len(changed) == 1
    assert out.splitlines()[changed[0]] == "        required: true"


def test_multiple_edits_one_file():
    doc = YamlDocument(FIXTURE)
    set_field_property(doc, "Session", "sessionType", "label", "Type")
    set_field_property(doc, "Session", "meetingLocationType", "required", True)
    out = doc.render()

    changed = set(_changed_line_indices(FIXTURE, out))
    assert len(changed) == 2
    lines = out.splitlines()
    assert lines[13] == '        label: "Type"'
    assert lines[19] == "        required: true"


def test_comments_and_structure_preserved():
    doc = YamlDocument(FIXTURE)
    set_field_property(doc, "Session", "sessionType", "label", "X")
    out = doc.render()

    assert "  # Custom entity — Session" in out
    assert "   # operator-facing label" in out
    assert out.count("\n") == FIXTURE.count("\n")  # no line added/removed


def test_render_without_edits_is_identity():
    doc = YamlDocument(FIXTURE)
    assert doc.render() == FIXTURE


def test_missing_field_raises():
    doc = YamlDocument(FIXTURE)
    try:
        set_field_property(doc, "Session", "noSuchField", "label", "x")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for missing field")
