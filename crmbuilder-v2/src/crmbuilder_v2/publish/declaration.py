"""Reading and checking a declaration before it reaches a live CRM system
(REQ-606 / PI-519).

A declaration that is wrong must be refused before it can be applied, because
a half-applied design is worse than an unapplied one: the instance is left in
a state no document describes.

**This accepts the dialect version 2 emits, and says so when it meets
anything else.** Version 1's parser accepts two blocks version 2 cannot
produce — saved views and automations — and their writers exist but are
called by nothing. Rather than port several hundred lines of rules for
blocks that cannot arrive, a declaration carrying one is refused by name,
with the reason, so a hand-written file gets a sentence instead of an
unhelpful "unknown key". A test holds the two sides together: if the emitter
ever starts producing a block this does not know, it fails.

**The one trap nothing used to catch.** The file format reads ``yes``, ``no``,
``on``, ``off``, ``true`` and ``false`` as true-or-false values in every
capitalisation, so an option list written ``[Yes, No]`` arrives as two
booleans and deploys a field whose choices are ``True`` and ``False``. The
emitter quotes those words on the way out; a hand-written file has no such
protection, and version 1 reported success while the instance was wrong.
Here it is an error that names the fix.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

import yaml

#: The blocks an object type may carry.
ENTITY_BLOCKS = frozenset(
    {
        "description",
        "fields",
        "layout",
        "settings",
        "emailTemplates",
        "duplicateChecks",
        "filteredTabs",
        "action",
        "type",
        "labelSingular",
        "labelPlural",
        "stream",
        "disabled",
    }
)

#: The blocks a declaration may carry beside its object types.
TOP_LEVEL_BLOCKS = frozenset(
    {
        "version",
        "description",
        "content_version",
        "entities",
        "relationships",
        "fieldPermissions",
        "fieldVisibility",
        "roles",
        "teams",
    }
)

#: Blocks version 1 accepted that version 2 cannot produce, and why.
UNSUPPORTED_BLOCKS: dict[str, str] = {
    "savedViews": (
        "saved views are captured in the design but never applied, so a "
        "declaration cannot carry them. Remove the block; the views stay "
        "recorded in the design."
    ),
    "workflows": (
        "automations are compared but never applied, so a declaration cannot "
        "carry them. Remove the block and set the automation by hand, or "
        "record it in the design where it will be compared."
    ),
}

#: What the file format reads as true-or-false whatever the capitalisation.
BOOLEAN_WORDS = frozenset({"yes", "no", "on", "off", "true", "false"})

#: Field kinds that carry a list of allowed values.
ENUM_KINDS = frozenset({"enum", "multiEnum"})


class DeclarationError(Exception):
    """The declaration could not be read at all."""


@dataclass
class Declaration:
    """One parsed declaration.

    :ivar filename: Where it came from, for messages.
    :ivar content: The declaration itself.
    """

    filename: str
    content: Mapping[str, Any]

    @property
    def entities(self) -> Mapping[str, Any]:
        entities = self.content.get("entities")
        return entities if isinstance(entities, Mapping) else {}

    @property
    def relationships(self) -> Sequence[Mapping[str, Any]]:
        rels = self.content.get("relationships")
        return [r for r in rels if isinstance(r, Mapping)] if isinstance(rels, list) else []

    def field_names(self) -> dict[str, set[str]]:
        """Every field this declaration declares, by object type."""
        names: dict[str, set[str]] = {}
        for entity_name, block in self.entities.items():
            if not isinstance(block, Mapping):
                continue
            declared = set()
            for field in block.get("fields") or []:
                if isinstance(field, Mapping) and field.get("name"):
                    declared.add(str(field["name"]))
            names[str(entity_name)] = declared
        return names


@dataclass
class Batch:
    """What a set of declarations knows between them.

    A declaration may name a field another declaration declares, or one the
    instance already has. Checking one file alone would reject both, which is
    why the check is made against the batch and the target together.

    :ivar declared: Field names by object type, across every declaration.
    :ivar on_instance: Field names by object type, as read from the target.
    """

    declared: dict[str, set[str]] = dataclass_field(default_factory=dict)
    on_instance: Mapping[str, Iterable[str]] = dataclass_field(default_factory=dict)

    @classmethod
    def of(
        cls,
        declarations: Iterable[Declaration],
        on_instance: Mapping[str, Iterable[str]] | None = None,
    ) -> Batch:
        declared: dict[str, set[str]] = {}
        for declaration in declarations:
            for entity, names in declaration.field_names().items():
                declared.setdefault(entity, set()).update(names)
        return cls(declared=declared, on_instance=on_instance or {})

    def knows(self, entity: str, field: str) -> bool:
        """Whether this field exists anywhere the declaration may rely on."""
        if field in self.declared.get(entity, set()):
            return True
        return field in set(self.on_instance.get(entity, ()))


def parse(text: str, filename: str = "<declaration>") -> Declaration:
    """Read one declaration.

    :param text: The declaration as written.
    :param filename: Where it came from, for messages.
    :raises DeclarationError: If the text is not a declaration at all.
    """
    try:
        content = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise DeclarationError(f"{filename}: could not be read — {exc}") from exc
    if content is None:
        raise DeclarationError(f"{filename}: is empty")
    if not isinstance(content, Mapping):
        raise DeclarationError(
            f"{filename}: should be a set of named blocks, but reads as "
            f"{type(content).__name__}"
        )
    return Declaration(filename, content)


def _boolean_words_in(values: Any) -> list[Any]:
    """Values that the file format turned into true-or-false."""
    if not isinstance(values, (list, tuple)):
        return []
    return [value for value in values if isinstance(value, bool)]


def _check_field(
    declaration: Declaration,
    entity: str,
    field: Mapping[str, Any],
    errors: list[str],
) -> None:
    where = f"{declaration.filename}: {entity}"
    name = field.get("name")
    if not name:
        errors.append(f"{where}: a field has no name")
        return
    where = f"{where}.{name}"

    kind = field.get("type")
    if not kind:
        errors.append(f"{where}: has no type")
        return

    if kind == "link":
        errors.append(
            f"{where}: a link is not a field. Declare it in the "
            f"relationships block instead — the platform creates the field "
            f"itself, and declaring both makes the link creation fail."
        )
        return

    if kind in ENUM_KINDS:
        options = field.get("options")
        booleans = _boolean_words_in(options)
        if booleans:
            errors.append(
                f"{where}: its choices include {booleans!r}, which the file "
                f"format turned into true-or-false values. Words like Yes, "
                f"No, On and Off must be quoted, or the field deploys with "
                f"the wrong choices."
            )
        if not options and not field.get("optionsDeferred"):
            errors.append(
                f"{where}: is a list of choices but declares none. Give it "
                f"options, or mark the options as deferred if somebody will "
                f"set them on the instance."
            )

    if kind == "foreign":
        if not field.get("link"):
            errors.append(
                f"{where}: mirrors a field from a linked object type but does "
                f"not say which link to follow."
            )
        if not field.get("field"):
            errors.append(
                f"{where}: mirrors a field from a linked object type but does "
                f"not say which field."
            )
        if field.get("required"):
            errors.append(
                f"{where}: is a mirror of another field, so it cannot be "
                f"required — nobody fills it in."
            )
        if field.get("formula"):
            errors.append(
                f"{where}: cannot both mirror another field and compute its "
                f"own value."
            )
    else:
        for key in ("link", "field"):
            if field.get(key):
                errors.append(
                    f"{where}: only a mirrored field may declare {key!r}."
                )


def _check_layout(
    declaration: Declaration,
    entity: str,
    layout: Any,
    batch: Batch,
    errors: list[str],
) -> None:
    if not isinstance(layout, Mapping):
        errors.append(
            f"{declaration.filename}: {entity}: its layout block should be a "
            f"set of named layouts"
        )
        return
    for layout_type, body in layout.items():
        for field_name in _layout_field_names(body):
            if not batch.knows(entity, field_name):
                errors.append(
                    f"{declaration.filename}: {entity}: the {layout_type} "
                    f"layout places {field_name!r}, which no declaration "
                    f"declares and the instance does not have. It would show "
                    f"as an empty cell."
                )


def _layout_field_names(body: Any) -> list[str]:
    """Every field a layout places, whatever shape the layout takes."""
    names: list[str] = []
    if isinstance(body, Mapping):
        for key, value in body.items():
            if key in {"panels", "rows", "columns"}:
                names.extend(_layout_field_names(value))
            elif key == "name" and isinstance(value, str):
                names.append(value)
            elif isinstance(value, (list, Mapping)):
                names.extend(_layout_field_names(value))
    elif isinstance(body, (list, tuple)):
        for item in body:
            if isinstance(item, str):
                names.append(item)
            else:
                names.extend(_layout_field_names(item))
    return names


def _check_relationship(
    declaration: Declaration, relationship: Mapping[str, Any], errors: list[str]
) -> None:
    where = f"{declaration.filename}: a relationship"
    for key in ("entity", "entityForeign", "link", "linkType"):
        if not relationship.get(key):
            errors.append(f"{where} does not say its {key}")
    link_type = relationship.get("linkType")
    if link_type and link_type not in {
        "oneToMany",
        "manyToOne",
        "manyToMany",
        "oneToOne",
    }:
        errors.append(
            f"{where} declares an unknown kind {link_type!r}. The platform "
            f"knows oneToMany, manyToOne, manyToMany and oneToOne."
        )


def validate(
    declaration: Declaration, batch: Batch | None = None
) -> list[str]:
    """Check one declaration, and say everything that is wrong with it.

    Every problem is reported, not just the first: an operator fixing a file
    is better served by the whole list.

    :param declaration: The declaration to check.
    :param batch: What the other declarations and the target instance
        between them already provide. Without it, a declaration is checked
        against itself alone.
    :returns: The problems, in the order found. Empty means it may be
        applied.
    """
    batch = batch or Batch.of([declaration])
    errors: list[str] = []

    for block, reason in UNSUPPORTED_BLOCKS.items():
        if block in declaration.content:
            errors.append(f"{declaration.filename}: {reason}")
        for entity_name, entity_block in declaration.entities.items():
            if isinstance(entity_block, Mapping) and block in entity_block:
                errors.append(
                    f"{declaration.filename}: {entity_name}: {reason}"
                )

    unknown_top = sorted(
        set(declaration.content)
        - TOP_LEVEL_BLOCKS
        - set(UNSUPPORTED_BLOCKS)
    )
    for block in unknown_top:
        errors.append(
            f"{declaration.filename}: does not know the block {block!r}"
        )

    if not declaration.entities and not declaration.content.get("roles"):
        errors.append(
            f"{declaration.filename}: declares neither an object type nor "
            f"any access, so there is nothing to apply"
        )

    for entity_name, entity_block in declaration.entities.items():
        entity = str(entity_name)
        if not isinstance(entity_block, Mapping):
            errors.append(
                f"{declaration.filename}: {entity}: should be a set of named "
                f"blocks"
            )
            continue
        for block in sorted(
            set(entity_block) - ENTITY_BLOCKS - set(UNSUPPORTED_BLOCKS)
        ):
            errors.append(
                f"{declaration.filename}: {entity}: does not know the block "
                f"{block!r}"
            )
        for field in entity_block.get("fields") or []:
            if isinstance(field, Mapping):
                _check_field(declaration, entity, field, errors)
            else:
                errors.append(
                    f"{declaration.filename}: {entity}: a field should be a "
                    f"set of properties"
                )
        if "layout" in entity_block:
            _check_layout(
                declaration, entity, entity_block["layout"], batch, errors
            )

    for relationship in declaration.relationships:
        _check_relationship(declaration, relationship, errors)

    return errors


def validate_batch(
    declarations: Sequence[Declaration],
    on_instance: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, list[str]]:
    """Check a whole set of declarations against each other and the target.

    :param declarations: Every declaration about to be applied.
    :param on_instance: Field names the target already has, by object type.
    :returns: The problems, by declaration filename. A declaration with no
        problems is absent from the result.
    """
    batch = Batch.of(declarations, on_instance)
    problems: dict[str, list[str]] = {}
    for declaration in declarations:
        errors = validate(declaration, batch)
        if errors:
            problems[declaration.filename] = errors
    return problems
