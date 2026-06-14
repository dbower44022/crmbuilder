"""Pure, deterministic build of the EspoCRM program model (design §6/§7).

``build_program_model`` is a pure function of the neutral design records
(+ injected ``rendered_at``): it filters to ``confirmed`` records, maps
entity/field intent to the EspoCRM YAML shape, merges the sparse
engine-scoped override layer, and routes everything it cannot emit in
slice 1 (reference/derived fields, entity default-sort, tooltip/unique
attributes, composite constructs) to deferral records. No I/O, no clock,
no engine writes — every ordering is total so two builds compare equal.

The emit (``emit.py``) turns this model into YAML + Markdown text; the
adapter (``adapter.py``) runs that YAML through ``validate_program`` as
a self-check. The mapping tables here are the §6/§7 dual-engine rows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from crmbuilder_v2.adapters.base import Deferral
from crmbuilder_v2.adapters.espocrm.conditions import (
    CompileError,
    compile_condition,
)

ENGINE = "espocrm"

# §8 neutral ``association_cardinality`` → EspoCRM relationship ``linkType``.
# The neutral model expresses a relationship from the source's perspective,
# so ``one_to_many`` means "one source relates to many targets". EspoCRM's
# inverse ``manyToOne`` is captured by the same single declaration (the
# ``linkForeign`` names the foreign side) — no separate inverse row is
# emitted (schema §8.2).
_CARDINALITY_TO_LINK_TYPE: dict[str, str] = {
    "one_to_one": "oneToOne",
    "one_to_many": "oneToMany",
    "many_to_many": "manyToMany",
}

# §6 entity-kind → EspoCRM base ``type``. NULL/transaction/other → Base.
_KIND_TO_TYPE: dict[str, str] = {
    "person": "Person",
    "organization": "Company",
    "event": "Event",
    "transaction": "Base",
    "other": "Base",
}

# §7 neutral ``field_type`` → EspoCRM platform type. ``number`` resolves
# to int/float by numeric scale at map time; ``reference``/``derived`` are
# not in this table — they route to deferrals.
_TYPE_MAP: dict[str, str] = {
    "text": "varchar",
    "long_text": "text",
    "enum": "enum",
    "multi_enum": "multiEnum",
    "date": "date",
    "datetime": "datetime",
    "money": "currency",
    "boolean": "bool",
}

# §7 ``field_format`` tokens that refine a string field to a richer
# EspoCRM platform type the schema supports. Other formats (percent,
# multiline, time, …) have no first-class EspoCRM type and are left as
# the base type (the format intent is documentation-only here).
_FORMAT_REFINEMENT: dict[str, str] = {
    "email": "email",
    "phone": "phone",
    "url": "url",
}

_ENUM_TYPES = frozenset({"enum", "multiEnum"})


# ---------------------------------------------------------------------------
# Model dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FieldBlock:
    """One emitted field's ordered key/value payload (a plain dict the
    emitter dumps verbatim) plus its source identifier for ordering."""

    field_identifier: str
    payload: dict


@dataclass
class EntityProgram:
    """One generated program file's content model.

    ``program`` is the full top-level YAML mapping (version/description/
    entities); ``filename`` is the V1-convention per-entity file name.
    """

    entity_identifier: str
    entity_name: str
    filename: str
    program: dict


@dataclass
class GenerationModel:
    """The pure result of :func:`build_program_model`."""

    engine: str
    rendered_at: str
    engagement: str | None
    programs: list[EntityProgram] = field(default_factory=list)
    deferrals: list[Deferral] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Name derivation (§6/§7 "derive, don't store")
# ---------------------------------------------------------------------------


def _words(raw: str) -> list[str]:
    """Split a business name into alphanumeric words (drop punctuation)."""
    return [w for w in re.split(r"[^A-Za-z0-9]+", raw or "") if w]


def derive_internal_name(field_name: str) -> str:
    """lowerCamelCase EspoCRM field name (no ``c-`` prefix — the deploy
    engine adds it). Deterministic; first char forced to a lowercase
    letter so it matches the ``^[a-z][a-zA-Z0-9]*$`` field-name rule."""
    words = _words(field_name)
    if not words:
        return "field"
    head = words[0].lower()
    rest = [w[:1].upper() + w[1:].lower() for w in words[1:]]
    name = head + "".join(rest)
    if not name[0].isalpha():
        name = "f" + name
    return name


def derive_label(name: str) -> str:
    """Title-case display label from a business name."""
    words = _words(name)
    if not words:
        return name or ""
    return " ".join(w[:1].upper() + w[1:].lower() for w in words)


def pluralize(name: str) -> str:
    """Naive pluralization for the default plural label (design §6)."""
    return f"{name}s"


def camel_singular(entity_name: str) -> str:
    """lowerCamelCase singular link-name stem from an entity name
    (``Mentor Application`` → ``mentorApplication``)."""
    return derive_internal_name(entity_name)


def camel_plural(entity_name: str) -> str:
    """lowerCamelCase plural link-name from an entity name
    (``Mentor Application`` → ``mentorApplications``). The trailing ``s``
    keeps the ``^[a-z][a-zA-Z0-9]*$`` field-name rule."""
    return f"{camel_singular(entity_name)}s"


def _role_link_name(role: str) -> str:
    """lowerCamelCase a declared association role into a link name."""
    return derive_internal_name(role)


def _filename_for(entity_name: str, entity_identifier: str, taken: set[str]) -> str:
    """A deterministic, filesystem-safe per-entity YAML file name
    (V1 convention, e.g. ``MN-Account.yaml``). Collisions disambiguate
    with the entity identifier."""
    slug = "-".join(_words(entity_name)) or entity_identifier
    candidate = f"{slug}.yaml"
    if candidate in taken:
        candidate = f"{slug}-{entity_identifier}.yaml"
    taken.add(candidate)
    return candidate


# ---------------------------------------------------------------------------
# Override merge
# ---------------------------------------------------------------------------


def _override_index(overrides: list[dict]) -> dict[tuple[str, str, str], object]:
    """``(subject_type, subject_identifier, attribute) -> value`` for the
    EspoCRM-scoped overrides only (design §9: scoped to one engine)."""
    index: dict[tuple[str, str, str], object] = {}
    for ovr in overrides:
        if ovr.get("override_target_engine") != ENGINE:
            continue
        key = (
            ovr.get("override_subject_type", ""),
            ovr.get("override_subject_identifier", ""),
            ovr.get("override_attribute", ""),
        )
        index[key] = ovr.get("override_value")
    return index


def _override(
    index: dict[tuple[str, str, str], object],
    subject_type: str,
    subject_identifier: str,
    attribute: str,
    derived: object,
) -> object:
    """Return the override value for ``(subject, attribute)`` if present,
    else the derived default (§9: absent override → neutral default)."""
    key = (subject_type, subject_identifier, attribute)
    if key in index:
        value = index[key]
        if value is not None:
            return value
    return derived


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------


def _to_number(raw: object) -> int | float | None:
    """Parse a stored neutral bound/value to int (preferred) or float."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return None


def _coerce_default(raw: object, espo_type: str) -> object | None:
    """Coerce a stored default value to the YAML shape for the field type."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return None
    if espo_type == "bool":
        low = text.lower()
        if low in ("true", "1", "yes"):
            return True
        if low in ("false", "0", "no"):
            return False
        return None
    if espo_type in ("int", "float", "currency"):
        num = _to_number(text)
        return num if num is not None else text
    return text


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


def _map_field_type(field_row: dict) -> str | None:
    """Map a neutral field record to its EspoCRM platform ``type``.

    Returns ``None`` for ``reference``/``derived`` (deferred) and any
    unknown semantic type. ``number`` resolves to int/float by neutral
    scale (default int); a string ``field_format`` of email/phone/url
    refines the base ``varchar``.
    """
    semantic = field_row.get("field_type")
    if semantic == "number":
        scale = field_row.get("field_numeric_scale")
        return "float" if scale == "decimal" else "int"
    espo_type = _TYPE_MAP.get(semantic)
    if espo_type is None:
        return None
    if espo_type == "varchar":
        refined = _FORMAT_REFINEMENT.get(field_row.get("field_format"))
        if refined is not None:
            return refined
    return espo_type


def _field_options(field_row: dict) -> list[str]:
    """Ordered option *values* for an enum/multiEnum field."""
    opts = list(field_row.get("field_options") or [])
    opts.sort(
        key=lambda o: (
            o.get("option_order") if o.get("option_order") is not None else 0,
            str(o.get("option_value") or ""),
        )
    )
    return [str(o.get("option_value")) for o in opts if o.get("option_value")]


def _build_field(
    field_row: dict,
    index: dict[tuple[str, str, str], object],
    deferrals: list[Deferral],
    parent_name: str,
) -> FieldBlock | None:
    """Map one confirmed field to its EspoCRM field block, or route it
    to a deferral and return ``None``."""
    fid = field_row["field_identifier"]
    fname = field_row.get("field_name", "")
    semantic = field_row.get("field_type")

    if semantic == "reference":
        deferrals.append(
            Deferral(
                kind="reference_field",
                identifier=fid,
                name=fname,
                parent=parent_name,
                detail=(
                    "reference field — relationship links are generated from "
                    "association records (slice 2). This field is covered if "
                    "an association exists for its entity pair; if none does, "
                    "create the association or configure the link manually"
                ),
            )
        )
        return None
    if semantic == "derived":
        deferrals.append(
            Deferral(
                kind="derived_field",
                identifier=fid,
                name=fname,
                parent=parent_name,
                detail=(
                    "derived/formula field — neutral model carries no "
                    "result value-type to map to an EspoCRM field type; "
                    "formula capture is a later slice"
                ),
            )
        )
        return None

    espo_type = _map_field_type(field_row)
    if espo_type is None:
        deferrals.append(
            Deferral(
                kind="unmapped_field",
                identifier=fid,
                name=fname,
                parent=parent_name,
                detail=f"field_type {semantic!r} has no EspoCRM mapping",
            )
        )
        return None

    internal_name = str(
        _override(index, "field", fid, "internal_name", derive_internal_name(fname))
    )
    label = str(_override(index, "field", fid, "label", derive_label(fname)))

    payload: dict = {"name": internal_name, "type": espo_type, "label": label}

    description = field_row.get("field_description")
    if description:
        payload["description"] = str(description)

    if field_row.get("field_required"):
        payload["required"] = True

    default = _coerce_default(field_row.get("field_default_value"), espo_type)
    if default is not None:
        payload["default"] = default

    if field_row.get("field_read_only"):
        payload["readOnly"] = True

    if espo_type == "varchar":
        max_length = field_row.get("field_max_length")
        if isinstance(max_length, int):
            payload["maxLength"] = max_length

    if espo_type in ("int", "float", "currency"):
        low = _to_number(field_row.get("field_min"))
        high = _to_number(field_row.get("field_max"))
        if low is not None:
            payload["min"] = low
        if high is not None:
            payload["max"] = high

    if field_row.get("field_externally_populated"):
        payload["externallyPopulated"] = True

    if espo_type in _ENUM_TYPES:
        options = _field_options(field_row)
        if options:
            payload["options"] = options
        else:
            payload["optionsDeferred"] = True

    # Neutral attributes with no first-class, deploy-validated EspoCRM
    # field key in scope → deferred (never emitted into the YAML).
    if field_row.get("field_tooltip"):
        deferrals.append(
            Deferral(
                kind="field_attribute",
                identifier=fid,
                name=fname,
                parent=parent_name,
                detail="tooltip — configure via the EspoCRM admin UI",
            )
        )
    if field_row.get("field_unique"):
        deferrals.append(
            Deferral(
                kind="field_attribute",
                identifier=fid,
                name=fname,
                parent=parent_name,
                detail="unique constraint — configure via the EspoCRM admin UI",
            )
        )
    if field_row.get("field_usage_summary"):
        deferrals.append(
            Deferral(
                kind="field_attribute",
                identifier=fid,
                name=fname,
                parent=parent_name,
                detail="usage_summary — documentation intent (renders to PRD)",
            )
        )

    return FieldBlock(field_identifier=fid, payload=payload)


# ---------------------------------------------------------------------------
# Entity mapping
# ---------------------------------------------------------------------------


def _entity_type(entity_row: dict) -> str:
    return _KIND_TO_TYPE.get(entity_row.get("entity_kind"), "Base")


@dataclass
class _EntityBuild:
    """Internal: an :class:`EntityProgram` plus the lookups slice-2
    post-processing needs — the live field-payload dicts (so rules can be
    attached in place) and the condition field-reference resolver map."""

    program: EntityProgram
    payload_by_field_id: dict[str, dict]
    ref_map: dict[str, str]


def _build_entity_program(
    entity_row: dict,
    field_rows: list[dict],
    index: dict[tuple[str, str, str], object],
    deferrals: list[Deferral],
    taken_filenames: set[str],
) -> _EntityBuild:
    eid = entity_row["entity_identifier"]
    ename = entity_row.get("entity_name", "")

    label_singular = str(
        _override(index, "entity", eid, "label_singular", ename)
    )
    label_plural = str(
        _override(index, "entity", eid, "label_plural", pluralize(ename))
    )

    settings: dict = {
        "labelSingular": label_singular,
        "labelPlural": label_plural,
    }
    if entity_row.get("entity_track_activity"):
        settings["stream"] = True

    entity_block: dict = {
        "action": "create",
        "type": _entity_type(entity_row),
        "description": str(entity_row.get("entity_description") or ""),
        "settings": settings,
    }

    field_blocks: list[FieldBlock] = []
    payload_by_field_id: dict[str, dict] = {}
    ref_map: dict[str, str] = {}
    for field_row in sorted(field_rows, key=lambda f: f["field_identifier"]):
        block = _build_field(field_row, index, deferrals, ename)
        if block is not None:
            field_blocks.append(block)
            payload_by_field_id[block.field_identifier] = block.payload
            internal_name = block.payload["name"]
            # Resolve a condition reference by FLD-NNN or by business name.
            ref_map[block.field_identifier] = internal_name
            fname = field_row.get("field_name")
            if fname:
                ref_map[fname] = internal_name
    if field_blocks:
        entity_block["fields"] = [b.payload for b in field_blocks]

    # Entity default-sort intent has no EspoCRM entity-level YAML key in
    # the v1.x schema (settings: carries no sort) → deferred.
    if entity_row.get("entity_default_sort_field"):
        direction = entity_row.get("entity_default_sort_direction") or "asc"
        deferrals.append(
            Deferral(
                kind="entity_default_sort",
                identifier=eid,
                name=ename,
                parent=None,
                detail=(
                    f"default sort {entity_row['entity_default_sort_field']} "
                    f"{direction} — no entity-level sort key in the EspoCRM "
                    "YAML schema; configure via the admin UI"
                ),
            )
        )

    program = {
        "version": "1.0.0",
        "description": (
            f"Generated EspoCRM program for {ename} "
            "(engine-neutral export, PI-191)"
        ),
        "content_version": "1.0.0",
        "entities": {ename: entity_block},
    }
    return _EntityBuild(
        program=EntityProgram(
            entity_identifier=eid,
            entity_name=ename,
            filename=_filename_for(ename, eid, taken_filenames),
            program=program,
        ),
        payload_by_field_id=payload_by_field_id,
        ref_map=ref_map,
    )


# ---------------------------------------------------------------------------
# Rules → requiredWhen / visibleWhen (design §8, schema §6.1.1 / §11)
# ---------------------------------------------------------------------------

# Field-effect → the EspoCRM field-level YAML key it maps to. ``valid_when``
# has no field-level deploy-validated key → it is deferred to MANUAL-CONFIG.
_RULE_EFFECT_TO_KEY: dict[str, str] = {
    "required_when": "requiredWhen",
    "visible_when": "visibleWhen",
}


def _apply_field_rules(
    rules: list[dict],
    builds: dict[str, _EntityBuild],
    field_entity: dict[str, str],
    deferrals: list[Deferral],
) -> None:
    """Compile each confirmed field ``rule`` to ``requiredWhen`` /
    ``visibleWhen`` and attach it to its subject field's payload.

    Routes to a deferral (never emits invalid YAML) when: the effect has no
    field-level key (``valid_when``); the subject is an entity, not a field;
    the subject field was not emitted (deferred/unmapped, or its parent
    entity is not confirmed); or the condition cannot be compiled.
    """
    for rule in sorted(rules, key=lambda r: r["rule_identifier"]):
        if rule.get("rule_status") != "confirmed":
            continue
        rid = rule["rule_identifier"]
        rname = rule.get("rule_name", "")
        subject_type = rule.get("rule_subject_type")
        effect = rule.get("rule_effect")

        if subject_type == "entity":
            deferrals.append(
                Deferral(
                    kind="entity_rule",
                    identifier=rid,
                    name=rname,
                    parent=rule.get("rule_subject_identifier"),
                    detail=(
                        f"entity-subject rule (effect {effect}) — no clean "
                        "entity-level YAML mapping; configure via the EspoCRM "
                        "admin UI"
                    ),
                )
            )
            continue

        key = _RULE_EFFECT_TO_KEY.get(effect)
        if key is None:
            deferrals.append(
                Deferral(
                    kind="field_rule",
                    identifier=rid,
                    name=rname,
                    parent=rule.get("rule_subject_identifier"),
                    detail=(
                        f"rule effect {effect!r} has no field-level EspoCRM "
                        "YAML key (valid_when is a record-validation "
                        "invariant) — configure via the EspoCRM admin UI"
                    ),
                )
            )
            continue

        subject_fid = rule.get("rule_subject_identifier")
        eid = field_entity.get(subject_fid)
        build = builds.get(eid) if eid is not None else None
        payload = (
            build.payload_by_field_id.get(subject_fid)
            if build is not None
            else None
        )
        if payload is None:
            deferrals.append(
                Deferral(
                    kind="field_rule",
                    identifier=rid,
                    name=rname,
                    parent=subject_fid,
                    detail=(
                        f"{key} target field {subject_fid} was not emitted "
                        "(deferred/unmapped field or non-confirmed entity) — "
                        "rule not attached"
                    ),
                )
            )
            continue

        def _resolve(ref: str, _map: dict[str, str] = build.ref_map) -> str:
            return _map.get(ref) or derive_internal_name(ref)

        try:
            compiled = compile_condition(rule.get("rule_condition"), _resolve)
        except CompileError as exc:
            deferrals.append(
                Deferral(
                    kind="field_rule",
                    identifier=rid,
                    name=rname,
                    parent=subject_fid,
                    detail=f"condition not compilable to EspoCRM form: {exc}",
                )
            )
            continue

        # ``required: true`` is mutually exclusive with both requiredWhen and
        # visibleWhen at deploy validation — a conditional gate supersedes the
        # unconditional flag, so drop it when a condition is attached.
        payload.pop("required", None)
        payload[key] = compiled


# ---------------------------------------------------------------------------
# Associations → relationships: block (design §8, schema §8)
# ---------------------------------------------------------------------------


def _link_names(
    assoc: dict,
    source_name: str,
    target_name: str,
    cardinality: str,
    index: dict[tuple[str, str, str], object],
) -> tuple[str, str]:
    """Derive the (``link``, ``linkForeign``) names for one association.

    A declared role wins; otherwise the link is named after the entity it
    reaches, plural when it reaches many and singular when it reaches one
    (schema §8.2 — e.g. ``Dues → mentor`` / ``Contact → duesRecords``).
    Both are overridable via ``engine_override`` (``link_name_source`` /
    ``link_name_target``).
    """
    source_role = assoc.get("association_source_role")
    target_role = assoc.get("association_target_role")

    # The source-side link reaches the target; the target-side link reaches
    # the source. "Many" reached → plural; "one" reached → singular.
    if cardinality == "many_to_many":
        link_default = camel_plural(target_name)
        foreign_default = camel_plural(source_name)
    elif cardinality == "one_to_many":
        # source is the "one" → reaches many targets; target reaches one source
        link_default = camel_plural(target_name)
        foreign_default = camel_singular(source_name)
    else:  # one_to_one
        link_default = camel_singular(target_name)
        foreign_default = camel_singular(source_name)

    if source_role:
        link_default = _role_link_name(source_role)
    if target_role:
        foreign_default = _role_link_name(target_role)

    aid = assoc["association_identifier"]
    link = str(_override(index, "association", aid, "link_name_source", link_default))
    foreign = str(
        _override(index, "association", aid, "link_name_target", foreign_default)
    )
    return link, foreign


def _build_relationship(
    assoc: dict,
    entity_name_by_id: dict[str, str],
    index: dict[tuple[str, str, str], object],
    deferrals: list[Deferral],
) -> tuple[str, dict] | None:
    """Build one EspoCRM ``relationships:`` entry from an ``association``.

    Returns ``(source_entity_identifier, relationship_dict)`` so the caller
    can place the entry in the source entity's program file, or ``None`` if
    the cardinality has no EspoCRM mapping (routed to a deferral).
    """
    aid = assoc["association_identifier"]
    aname = assoc.get("association_name", "")
    source_id = assoc.get("association_source_entity")
    target_id = assoc.get("association_target_entity")
    source_name = entity_name_by_id[source_id]
    target_name = entity_name_by_id[target_id]

    cardinality = assoc.get("association_cardinality")
    link_type_default = _CARDINALITY_TO_LINK_TYPE.get(cardinality)
    if link_type_default is None:
        deferrals.append(
            Deferral(
                kind="association",
                identifier=aid,
                name=aname,
                parent=source_name,
                detail=(
                    f"cardinality {cardinality!r} has no EspoCRM linkType "
                    "mapping — configure the relationship via the admin UI"
                ),
            )
        )
        return None
    link_type = str(
        _override(index, "association", aid, "link_type", link_type_default)
    )

    link, foreign = _link_names(assoc, source_name, target_name, cardinality, index)

    rel: dict = {
        "name": derive_internal_name(aname),
        "description": str(
            assoc.get("association_description")
            or f"{source_name} ↔ {target_name} ({aid})"
        ),
        "entity": source_name,
        "entityForeign": target_name,
        "linkType": link_type,
        "link": link,
        "linkForeign": foreign,
        "label": derive_label(target_name),
        "labelForeign": derive_label(source_name),
    }
    if link_type == "manyToMany":
        rel["relationName"] = derive_internal_name(f"{source_name} {target_name}")
    return source_id, rel


def _apply_associations(
    associations: list[dict],
    builds: dict[str, _EntityBuild],
    entity_name_by_id: dict[str, str],
    confirmed_entity_ids: set[str],
    index: dict[tuple[str, str, str], object],
    deferrals: list[Deferral],
) -> set[str]:
    """Attach a ``relationships:`` block to each source entity's program.

    Only confirmed associations whose *both* endpoints are confirmed (and so
    emitted) are rendered. Returns the set of entity identifiers that take
    part in at least one emitted relationship (used to annotate deferred
    reference fields).
    """
    participating: set[str] = set()
    for assoc in sorted(associations, key=lambda a: a["association_identifier"]):
        if assoc.get("association_status") != "confirmed":
            continue
        source_id = assoc.get("association_source_entity")
        target_id = assoc.get("association_target_entity")
        if source_id not in confirmed_entity_ids or (
            target_id not in confirmed_entity_ids
        ):
            # An endpoint is not in the emitted set → no home program.
            deferrals.append(
                Deferral(
                    kind="association",
                    identifier=assoc["association_identifier"],
                    name=assoc.get("association_name", ""),
                    parent=entity_name_by_id.get(source_id, source_id),
                    detail=(
                        "an endpoint entity is not confirmed/emitted — "
                        "relationship not rendered"
                    ),
                )
            )
            continue
        built = _build_relationship(assoc, entity_name_by_id, index, deferrals)
        if built is None:
            continue
        owner_id, rel = built
        program = builds[owner_id].program.program
        program.setdefault("relationships", []).append(rel)
        participating.add(source_id)
        participating.add(target_id)
    return participating


# ---------------------------------------------------------------------------
# Top-level build
# ---------------------------------------------------------------------------


def build_program_model(
    entities: list[dict],
    fields: list[dict],
    overrides: list[dict],
    *,
    associations: list[dict] | None = None,
    rules: list[dict] | None = None,
    rendered_at: str,
    engagement: str | None = None,
) -> GenerationModel:
    """Assemble the full EspoCRM generation model — pure, deterministic.

    Scope filter (design noise must not reach a deploy artifact): only
    ``confirmed`` entities and their ``confirmed`` fields are emitted;
    every candidate/deferred/rejected record is skipped silently (it is
    not a deferral — it is unfinished design).

    Slice 2 adds the ``relationships:`` block (from ``confirmed``
    ``association`` records whose both endpoints are emitted) and field-level
    ``requiredWhen`` / ``visibleWhen`` (from ``confirmed`` field ``rule``
    records). ``valid_when`` and entity-subject rules route to deferrals.
    """
    associations = associations or []
    rules = rules or []
    index = _override_index(overrides)

    confirmed_entities = sorted(
        (e for e in entities if e.get("entity_status") == "confirmed"),
        key=lambda e: e["entity_identifier"],
    )
    confirmed_entity_ids = {e["entity_identifier"] for e in confirmed_entities}
    entity_name_by_id = {
        e["entity_identifier"]: e.get("entity_name", "")
        for e in confirmed_entities
    }

    fields_by_parent: dict[str, list[dict]] = {}
    field_entity: dict[str, str] = {}
    for field_row in fields:
        if field_row.get("field_status") != "confirmed":
            continue
        parent = field_row.get("parent_entity_identifier")
        if parent not in confirmed_entity_ids:
            # A confirmed field whose parent is not a confirmed entity has
            # no home program — skip with the parent (not a deferral).
            continue
        fields_by_parent.setdefault(parent, []).append(field_row)
        field_entity[field_row["field_identifier"]] = parent

    deferrals: list[Deferral] = []
    taken_filenames: set[str] = set()
    builds: dict[str, _EntityBuild] = {}
    for entity_row in confirmed_entities:
        build = _build_entity_program(
            entity_row,
            fields_by_parent.get(entity_row["entity_identifier"], []),
            index,
            deferrals,
            taken_filenames,
        )
        builds[entity_row["entity_identifier"]] = build

    # Slice 2: field rules → requiredWhen/visibleWhen (mutate field payloads),
    # then associations → relationships: blocks on the source programs.
    _apply_field_rules(rules, builds, field_entity, deferrals)
    _apply_associations(
        associations,
        builds,
        entity_name_by_id,
        confirmed_entity_ids,
        index,
        deferrals,
    )

    programs = [builds[e["entity_identifier"]].program for e in confirmed_entities]

    # Remaining composite constructs are still out of scope (slices 2-3) —
    # one standing deferral keeps the companion honest about the gap.
    deferrals.append(
        Deferral(
            kind="composite_constructs",
            identifier="-",
            name="views, automations, dedup, templates",
            parent=None,
            detail=(
                "the savedViews:/duplicateChecks:/workflows:/emailTemplates: "
                "blocks are generated by later adapter slices; relationships: "
                "and requiredWhen/visibleWhen are emitted in this slice"
            ),
        )
    )

    return GenerationModel(
        engine=ENGINE,
        rendered_at=rendered_at,
        engagement=engagement,
        programs=programs,
        deferrals=deferrals,
    )
