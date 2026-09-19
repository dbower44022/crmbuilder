"""Tests for reading and checking a declaration (REQ-606 / PI-519).

The last test is the important one: it holds this parser and version 2's
emitter together, so the two cannot drift apart silently.
"""

from __future__ import annotations

import pathlib

import pytest
from crmbuilder_v2.publish.declaration import (
    ENTITY_BLOCKS,
    TOP_LEVEL_BLOCKS,
    UNSUPPORTED_BLOCKS,
    Batch,
    DeclarationError,
    parse,
    validate,
    validate_batch,
)


def _emitter_source() -> str:
    """The emitter's own source, found from the package rather than the
    working directory, so these hold wherever the tests are run from."""
    from crmbuilder_v2.adapters.espocrm import model

    return pathlib.Path(model.__file__).read_text(encoding="utf-8")


_MINIMAL = """
version: "1.0.0"
entities:
  Engagement:
    fields:
      - name: stage
        type: enum
        label: Stage
        options: ["Active", "Closed"]
"""


def _declaration(text: str = _MINIMAL, filename: str = "Engagement.yaml"):
    return parse(text, filename)


# --- reading ----------------------------------------------------------------


def test_a_well_formed_declaration_reads() -> None:
    declaration = _declaration()
    assert "Engagement" in declaration.entities


def test_something_that_is_not_a_declaration_is_refused() -> None:
    with pytest.raises(DeclarationError, match="named blocks"):
        parse("- just\n- a list\n", "odd.yaml")


def test_an_empty_file_is_refused() -> None:
    with pytest.raises(DeclarationError, match="empty"):
        parse("", "empty.yaml")


def test_a_file_that_is_not_readable_says_so_with_the_reason() -> None:
    with pytest.raises(DeclarationError, match="could not be read"):
        parse("entities: [unclosed\n", "broken.yaml")


# --- the two blocks version 2 cannot produce --------------------------------


def test_a_declaration_carrying_automations_is_refused_by_name() -> None:
    text = _MINIMAL + """
    workflows:
      - id: notify
        trigger: onCreate
"""
    errors = validate(_declaration(text))
    assert any("automations are compared but never applied" in e for e in errors)


def test_a_declaration_carrying_saved_views_is_refused_by_name() -> None:
    text = _MINIMAL + """
    savedViews:
      - id: mine
        name: Mine
"""
    errors = validate(_declaration(text))
    assert any("saved views are captured in the design" in e for e in errors)


def test_an_unsupported_block_is_not_reported_as_merely_unknown() -> None:
    """A hand-written file deserves a sentence, not a shrug."""
    text = _MINIMAL + """
    workflows: []
"""
    errors = validate(_declaration(text))
    assert not any("does not know the block" in e for e in errors)


# --- what the parser does not know ------------------------------------------


def test_an_unknown_top_level_block_is_reported() -> None:
    errors = validate(_declaration("version: '1'\nnonsense: true\nentities: {}\n"))
    assert any("does not know the block 'nonsense'" in e for e in errors)


def test_an_unknown_block_on_an_object_type_is_reported() -> None:
    text = """
entities:
  Engagement:
    nonsense: true
"""
    errors = validate(_declaration(text))
    assert any("does not know the block 'nonsense'" in e for e in errors)


def test_a_declaration_that_asks_for_nothing_is_reported() -> None:
    errors = validate(_declaration("version: '1'\nentities: {}\n"))
    assert any("nothing to apply" in e for e in errors)


# --- fields -----------------------------------------------------------------


def test_a_link_declared_as_a_field_is_refused_with_the_reason() -> None:
    text = """
entities:
  Engagement:
    fields:
      - name: account
        type: link
"""
    errors = validate(_declaration(text))
    assert any("a link is not a field" in e for e in errors)
    assert any("relationships block" in e for e in errors)


def test_the_words_the_file_format_turns_into_true_or_false_are_caught() -> None:
    """Version 1 reported success and deployed the wrong choices."""
    text = """
entities:
  Engagement:
    fields:
      - name: confirmed
        type: enum
        options: [Yes, No]
"""
    errors = validate(_declaration(text))
    assert any("turned into true-or-false" in e for e in errors)
    assert any("must be quoted" in e for e in errors)


def test_quoted_words_are_fine() -> None:
    text = """
entities:
  Engagement:
    fields:
      - name: confirmed
        type: enum
        options: ["Yes", "No"]
"""
    assert validate(_declaration(text)) == []


def test_a_list_of_choices_with_no_choices_is_reported() -> None:
    text = """
entities:
  Engagement:
    fields:
      - name: stage
        type: enum
"""
    errors = validate(_declaration(text))
    assert any("declares none" in e for e in errors)


def test_deferred_choices_are_allowed_to_be_empty() -> None:
    text = """
entities:
  Engagement:
    fields:
      - name: stage
        type: enum
        optionsDeferred: true
"""
    assert validate(_declaration(text)) == []


def test_a_mirrored_field_must_say_what_it_mirrors() -> None:
    text = """
entities:
  Engagement:
    fields:
      - name: accountName
        type: foreign
"""
    errors = validate(_declaration(text))
    assert any("which link to follow" in e for e in errors)
    assert any("which field" in e for e in errors)


def test_a_mirrored_field_cannot_be_required_or_computed() -> None:
    text = """
entities:
  Engagement:
    fields:
      - name: accountName
        type: foreign
        link: account
        field: name
        required: true
        formula: {kind: concat}
"""
    errors = validate(_declaration(text))
    assert any("nobody fills it in" in e for e in errors)
    assert any("cannot both mirror" in e for e in errors)


def test_only_a_mirrored_field_may_name_a_link() -> None:
    text = """
entities:
  Engagement:
    fields:
      - name: stage
        type: varchar
        link: account
"""
    errors = validate(_declaration(text))
    assert any("only a mirrored field" in e for e in errors)


def test_a_field_without_a_name_or_a_type_is_reported() -> None:
    text = """
entities:
  Engagement:
    fields:
      - type: varchar
      - name: stage
"""
    errors = validate(_declaration(text))
    assert any("has no name" in e for e in errors)
    assert any("has no type" in e for e in errors)


# --- layouts and the rest of the batch --------------------------------------


def test_a_layout_placing_an_undeclared_field_is_reported() -> None:
    text = """
entities:
  Engagement:
    fields:
      - name: stage
        type: varchar
    layout:
      detail:
        panels:
          - rows: [[{name: nowhere}]]
"""
    errors = validate(_declaration(text))
    assert any("would show as an empty cell" in e for e in errors)


def test_a_layout_may_place_a_field_another_declaration_declares() -> None:
    first = parse(
        """
entities:
  Engagement:
    layout:
      detail:
        panels:
          - rows: [[{name: stage}]]
""",
        "layout.yaml",
    )
    second = parse(
        """
entities:
  Engagement:
    fields:
      - name: stage
        type: varchar
""",
        "fields.yaml",
    )
    assert validate_batch([first, second]) == {}


def test_a_layout_may_place_a_field_the_instance_already_has() -> None:
    declaration = parse(
        """
entities:
  Contact:
    layout:
      detail:
        panels:
          - rows: [[{name: lastName}]]
""",
        "contact.yaml",
    )
    problems = validate_batch([declaration], {"Contact": ["lastName"]})
    assert problems == {}


def test_the_batch_knows_what_it_and_the_instance_hold() -> None:
    batch = Batch.of([_declaration()], {"Engagement": ["createdAt"]})
    assert batch.knows("Engagement", "stage")
    assert batch.knows("Engagement", "createdAt")
    assert not batch.knows("Engagement", "nowhere")


# --- relationships ----------------------------------------------------------


def test_a_relationship_missing_its_parts_is_reported() -> None:
    text = """
entities:
  Engagement: {}
relationships:
  - entity: Engagement
"""
    errors = validate(_declaration(text))
    assert any("entityForeign" in e for e in errors)
    assert any("linkType" in e for e in errors)


def test_a_relationship_of_an_unknown_kind_is_reported() -> None:
    text = """
entities:
  Engagement: {}
relationships:
  - entity: Engagement
    entityForeign: Account
    link: account
    linkType: someToSome
"""
    errors = validate(_declaration(text))
    assert any("unknown kind" in e for e in errors)


# --- every problem, not just the first --------------------------------------


def test_everything_wrong_is_reported_at_once() -> None:
    text = """
entities:
  Engagement:
    fields:
      - name: account
        type: link
      - name: stage
        type: enum
        options: [Yes, No]
"""
    errors = validate(_declaration(text))
    assert len(errors) >= 2


def test_a_batch_reports_by_file() -> None:
    good = parse(_MINIMAL, "good.yaml")
    bad = parse("version: '1'\nentities: {}\n", "bad.yaml")
    problems = validate_batch([good, bad])
    assert list(problems) == ["bad.yaml"]


# --- the boundary this parser promises to hold ------------------------------


def test_the_parser_knows_every_block_the_emitter_can_produce() -> None:
    """If the emitter starts producing something this does not know, fail
    here rather than against a live instance.

    The emitted dialect is read off the emitter itself: the blocks it writes
    onto an object type, and the blocks it writes at the top of a file.
    """
    import re

    source = _emitter_source()

    emitted_entity_blocks = set(
        re.findall(r'entity_block\[\s*"([a-zA-Z_]+)"\s*\]', source)
    )
    emitted_entity_blocks |= set(
        re.findall(r'entity_block\.setdefault\(\s*"([a-zA-Z_]+)"', source)
    )
    # The block the emitter builds as a literal, which the two patterns above
    # cannot see. Missing it let the parser reject every generated
    # declaration over its description key.
    literal = re.search(r"entity_block: dict = \{(.*?)\n    \}", source, re.S)
    assert literal, "the emitter no longer builds its entity block as a literal"
    emitted_entity_blocks |= set(re.findall(r'"([a-zA-Z_]+)":', literal.group(1)))
    # Blocks whose writer exists but which nothing calls are not emitted; the
    # two unsupported ones are exactly those.
    emitted_entity_blocks -= set(UNSUPPORTED_BLOCKS)
    unknown = emitted_entity_blocks - ENTITY_BLOCKS
    assert not unknown, (
        f"the emitter writes {sorted(unknown)} onto an object type and the "
        f"declaration parser does not know it"
    )

    emitted_top = set(re.findall(r'program\.setdefault\(\s*"([a-zA-Z_]+)"', source))
    unknown_top = emitted_top - TOP_LEVEL_BLOCKS
    assert not unknown_top, (
        f"the emitter writes {sorted(unknown_top)} at the top of a "
        f"declaration and the parser does not know it"
    )


def test_the_two_unsupported_blocks_are_still_the_ones_nothing_calls() -> None:
    """Their writers exist for the day the platform grows a way to apply
    them. If one gains a caller, this parser must stop refusing it."""
    source = _emitter_source()
    for writer in ("_apply_views(", "_apply_automations("):
        assert source.count(writer) == 1, (
            f"{writer} now has a caller — the emitter can produce a block "
            f"the declaration parser refuses"
        )
