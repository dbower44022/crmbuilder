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

from crmbuilder_v2.adapters.base import Deferral, ProgramArtifact
from crmbuilder_v2.adapters.espocrm.conditions import (
    CompileError,
    compile_condition,
)
from crmbuilder_v2.adapters.espocrm.formulas import (
    FormulaCompileError,
    compile_formula,
)

ENGINE = "espocrm"

# §8 neutral ``automation_trigger`` → EspoCRM v1.1 workflow trigger event
# (schema §5.8). ``scheduled`` / ``manual`` have no v1.1 event value and route
# the whole automation to a deferral.
_TRIGGER_TO_EVENT: dict[str, str] = {
    "on_create": "onCreate",
    "on_update": "onUpdate",
    "on_delete": "onDelete",
}

# §8 neutral ``dedup_rule`` normalization token → EspoCRM ``normalize:`` value
# (schema §5.5: ``none`` / ``lowercase-trim`` / ``case-fold-trim`` / ``e164``).
# ``trim`` (no pure-trim value) and ``digits_only`` have no EspoCRM normalize
# value → the token is dropped to a deferral (the field stays a match field,
# unnormalized).
_NORMALIZE_TOKEN_TO_VALUE: dict[str, str] = {
    "case_fold": "case-fold-trim",
    "lowercase": "lowercase-trim",
    "e164": "e164",
}

# §8 neutral ``automation_actions[].type`` → EspoCRM v1.1 workflow action.
# Only ``set_field`` has a clean field+value v1.1 mapping (``setField``); the
# others (``send_notification`` needs a template+recipient the neutral record
# does not carry; ``create_record`` / ``update_related`` / ``webhook`` have no
# v1.1 action) route the individual action to a deferral.
_ACTION_TYPE_TO_WORKFLOW: dict[str, str] = {
    "set_field": "setField",
}

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
    companions: list[ProgramArtifact] = field(default_factory=list)


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


def _derived_field_type(field_row: dict) -> str | None:
    """Map a ``derived`` field's ``field_derived_result_type`` to the EspoCRM
    platform type the computed field carries (PI-197, design §7/§9).

    The result type is one of :data:`DERIVED_RESULT_TYPES` — the same value
    shapes ``_map_field_type`` handles for a regular field — so it reuses the
    ``_TYPE_MAP`` + numeric-scale + ``varchar``-format-refinement logic
    against the result type. Returns ``None`` if the result type is missing
    or unknown.
    """
    result_type = field_row.get("field_derived_result_type")
    if not result_type:
        return None
    return _map_field_type(
        {
            "field_type": result_type,
            "field_numeric_scale": field_row.get("field_numeric_scale"),
            "field_format": field_row.get("field_format"),
        }
    )


def _has_formula_source(
    field_row: dict, index: dict[tuple[str, str, str], object]
) -> bool:
    """True when a derived field has a formula to render — either a neutral
    ``field_formula`` AST or an ``engine_override`` carrying raw EspoCRM
    formula text (PI-197, design §9: absent override → adapter default)."""
    if field_row.get("field_formula"):
        return True
    fid = field_row["field_identifier"]
    override = index.get(("field", fid, "formula"))
    return override is not None


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


def _build_derived_field(
    field_row: dict,
    index: dict[tuple[str, str, str], object],
    deferrals: list[Deferral],
    parent_name: str,
) -> FieldBlock | None:
    """Emit a ``derived`` field's base block (type + ``readOnly: true``), or
    route it to a deferral (PI-197, design §7/§9, DEC-438).

    The ``formula:`` block itself is compiled and attached later by
    :func:`_apply_derived_formulas` (it needs the cross-entity ref map +
    association resolver). Here we only emit the read-only typed field when:

    * a formula source exists (a neutral ``field_formula`` AST **or** an
      ``engine_override`` carrying raw formula text), **and**
    * the ``field_derived_result_type`` maps to an EspoCRM platform type.

    With no formula source, or an unmappable result type, the field routes
    to MANUAL-CONFIG (the old pre-PI-197 behaviour, now the exception).
    """
    fid = field_row["field_identifier"]
    fname = field_row.get("field_name", "")

    if not _has_formula_source(field_row, index):
        deferrals.append(
            Deferral(
                kind="derived_field",
                identifier=fid,
                name=fname,
                parent=parent_name,
                detail=(
                    "derived/formula field — no neutral formula and no "
                    "engine_override formula text; configure the computed "
                    "field via the EspoCRM admin UI"
                ),
            )
        )
        return None

    espo_type = _derived_field_type(field_row)
    if espo_type is None:
        deferrals.append(
            Deferral(
                kind="derived_field",
                identifier=fid,
                name=fname,
                parent=parent_name,
                detail=(
                    "derived/formula field — field_derived_result_type "
                    f"{field_row.get('field_derived_result_type')!r} has no "
                    "EspoCRM platform-type mapping; configure via the admin UI"
                ),
            )
        )
        return None

    internal_name = str(
        _override(index, "field", fid, "internal_name", derive_internal_name(fname))
    )
    label = str(_override(index, "field", fid, "label", derive_label(fname)))
    payload: dict = {
        "name": internal_name,
        "type": espo_type,
        "label": label,
        "readOnly": True,
    }
    description = field_row.get("field_description")
    if description:
        payload["description"] = str(description)
    # An enum/multiEnum-typed derived field still carries its option set.
    if espo_type in _ENUM_TYPES:
        options = _field_options(field_row)
        if options:
            payload["options"] = options
        else:
            payload["optionsDeferred"] = True
    return FieldBlock(field_identifier=fid, payload=payload)


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
        return _build_derived_field(field_row, index, deferrals, parent_name)

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
    entity_block: dict


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
        entity_block=entity_block,
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
# Derived formulas → formula: block (design §7/§9, schema §6.1.3) — PI-197
# ---------------------------------------------------------------------------


def _apply_derived_formulas(
    fields: list[dict],
    builds: dict[str, _EntityBuild],
    field_entity: dict[str, str],
    associations: list[dict],
    entity_name_by_id: dict[str, str],
    index: dict[tuple[str, str, str], object],
    deferrals: list[Deferral],
) -> None:
    """Compile each emitted ``derived`` field's formula and attach it as the
    field's ``formula:`` block (PI-197, design §7/§9, DEC-438).

    For each confirmed derived field whose base block was emitted by
    :func:`_build_derived_field`:

    * an ``engine_override`` formula text wins (§9: hand-tuned override) and
      is attached verbatim;
    * otherwise the neutral ``field_formula`` AST is compiled via
      :func:`compile_formula` (concat/arithmetic resolve same-entity refs
      strictly; an aggregate resolves its ``association`` to ``relatedEntity``
      / ``via``).

    A formula that cannot be compiled (a dangling association, an
    unresolvable same-entity ref) routes to a deferral — the read-only field
    stays in the YAML (valid, just uncomputed). ``readOnly: true`` is already
    on the base block, so the attached ``formula:`` passes ``validate_program``.
    """
    assoc_by_id = {
        a["association_identifier"]: a for a in associations
    }
    for field_row in sorted(fields, key=lambda f: f["field_identifier"]):
        if field_row.get("field_type") != "derived":
            continue
        if field_row.get("field_status") != "confirmed":
            continue
        fid = field_row["field_identifier"]
        fname = field_row.get("field_name", "")
        eid = field_entity.get(fid)
        build = builds.get(eid) if eid is not None else None
        payload = (
            build.payload_by_field_id.get(fid) if build is not None else None
        )
        if payload is None:
            # The base block was deferred (no formula source / unmapped result
            # type) — _build_derived_field already recorded that deferral.
            continue

        # §9: a hand-tuned engine override formula wins, attached verbatim.
        # The override value carries the EspoCRM ``formula:`` block itself (a
        # mapping, the §6.1.3 shape) — the per-engine residue in the engine's
        # own form. A non-mapping override cannot satisfy validate_program, so
        # it routes to a deferral rather than emitting an invalid block.
        override_formula = index.get(("field", fid, "formula"))
        if override_formula is not None:
            if isinstance(override_formula, dict):
                payload["formula"] = override_formula
            else:
                deferrals.append(
                    Deferral(
                        kind="derived_field",
                        identifier=fid,
                        name=fname,
                        parent=entity_name_by_id.get(eid, eid),
                        detail=(
                            "engine_override formula is not a formula block "
                            "(mapping) — configure the computed field via the "
                            "EspoCRM admin UI"
                        ),
                    )
                )
            continue

        formula = field_row.get("field_formula")
        if not formula:  # pragma: no cover — _has_formula_source guards
            continue

        def _resolve(ref: str, _map: dict[str, str] = build.ref_map) -> str:
            internal = _map.get(ref)
            if internal is None:
                raise FormulaCompileError(
                    f"formula references field {ref!r} not emitted on the entity"
                )
            return internal

        def _resolve_association(
            asn_ref: str, _eid: str = eid
        ) -> tuple[str, str]:
            assoc = assoc_by_id.get(asn_ref)
            if assoc is None:
                raise FormulaCompileError(
                    f"aggregate references association {asn_ref!r} that does "
                    "not exist"
                )
            source_id = assoc.get("association_source_entity")
            target_id = assoc.get("association_target_entity")
            cardinality = assoc.get("association_cardinality")
            source_name = entity_name_by_id.get(source_id)
            target_name = entity_name_by_id.get(target_id)
            if source_name is None or target_name is None:
                raise FormulaCompileError(
                    f"aggregate association {asn_ref!r} has an endpoint that "
                    "is not a confirmed/emitted entity"
                )
            link, foreign = _link_names(
                assoc, source_name, target_name, cardinality, index
            )
            # The related entity is the *other* endpoint; ``via`` is the link
            # on the related entity that points back to this entity.
            if _eid == source_id:
                return target_name, foreign
            if _eid == target_id:
                return source_name, link
            raise FormulaCompileError(
                f"aggregate association {asn_ref!r} does not connect the "
                "derived field's entity"
            )

        # An aggregate's aggregated field lives on the *related* entity, so it
        # derives leniently — it is not one of this entity's emitted fields.
        def _resolve_related(ref: str) -> str:
            return derive_internal_name(ref)

        try:
            compiled = compile_formula(
                formula, _resolve, _resolve_association, _resolve_related
            )
        except FormulaCompileError as exc:
            deferrals.append(
                Deferral(
                    kind="derived_field",
                    identifier=fid,
                    name=fname,
                    parent=entity_name_by_id.get(eid, eid),
                    detail=f"formula not compilable to EspoCRM form: {exc}",
                )
            )
            continue
        payload["formula"] = compiled


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
# Composite constructs (design §8, schema §5.5–§5.8) — slice 3
# views → savedViews: / automations → workflows: / dedup_rules →
# duplicateChecks: / message_templates → emailTemplates:
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{\{.*?\}\}")


def _slug_id(identifier: str) -> str:
    """A stable, lower-case block ``id`` from a design identifier (unique by
    construction — identifiers are unique, and each block validates its ids
    only within its own block)."""
    return identifier.lower()


def _strict_resolver(ref_map: dict[str, str]):
    """A condition reference resolver that raises :class:`CompileError` when a
    referenced field was not emitted on the entity — so a condition touching a
    deferred/candidate field routes its owner to a deferral rather than
    emitting a field reference ``validate_program`` would reject."""

    def _resolve(ref: str) -> str:
        internal = ref_map.get(ref)
        if internal is None:
            raise CompileError(f"field reference {ref!r} not emitted on the entity")
        return internal

    return _resolve


def _resolve_all(refs: list, ref_map: dict[str, str]) -> list[str] | None:
    """Resolve every field reference to its emitted internal name, or ``None``
    if any reference is not an emitted field on the entity."""
    out: list[str] = []
    for ref in refs:
        internal = ref_map.get(ref)
        if internal is None:
            return None
        out.append(internal)
    return out


def _strip_placeholders(text: str) -> str:
    """Remove ``{{...}}`` merge placeholders from free text. The adapter
    regenerates a deterministic, validated merge-field section, so neutral
    placeholders (which need not match the emitted internal names) are dropped
    rather than risk an unvalidatable stray placeholder."""
    return _PLACEHOLDER_RE.sub("", text)


def _apply_views(
    views: list[dict],
    builds: dict[str, _EntityBuild],
    confirmed_entity_ids: set[str],
    entity_name_by_id: dict[str, str],
    index: dict[tuple[str, str, str], object],
    deferrals: list[Deferral],
) -> None:
    """Attach a ``savedViews:`` block to each owning entity's program.

    ``filter`` is required by the schema; a view with no neutral filter, a
    filter touching a non-emitted field, or an owning entity that is not
    emitted routes to a deferral. ``columns`` / ``orderBy`` are optional and
    omitted (with a note) when they reference a non-emitted field.
    """
    for view in sorted(views, key=lambda v: v["view_identifier"]):
        if view.get("view_status") != "confirmed":
            continue
        vid = view["view_identifier"]
        vname = view.get("view_name", "")
        eid = view.get("view_entity")
        if eid not in confirmed_entity_ids:
            deferrals.append(
                Deferral(
                    kind="view",
                    identifier=vid,
                    name=vname,
                    parent=entity_name_by_id.get(eid, eid),
                    detail=(
                        "owning entity is not confirmed/emitted — savedView "
                        "not rendered"
                    ),
                )
            )
            continue
        build = builds[eid]
        ename = build.program.entity_name

        raw_filter = view.get("view_filter")
        if raw_filter is None:
            deferrals.append(
                Deferral(
                    kind="view",
                    identifier=vid,
                    name=vname,
                    parent=ename,
                    detail=(
                        "savedViews requires a filter (schema §5.6); this view "
                        "carries no neutral filter — configure via the EspoCRM "
                        "admin UI"
                    ),
                )
            )
            continue
        try:
            compiled_filter = compile_condition(raw_filter, _strict_resolver(build.ref_map))
        except CompileError as exc:
            deferrals.append(
                Deferral(
                    kind="view",
                    identifier=vid,
                    name=vname,
                    parent=ename,
                    detail=f"filter not compilable to EspoCRM form: {exc}",
                )
            )
            continue

        item: dict = {
            "id": _slug_id(vid),
            "name": str(_override(index, "view", vid, "name", vname) or vid),
        }
        description = view.get("view_description")
        if description:
            item["description"] = str(description)

        columns = view.get("view_columns") or []
        resolved_cols = _resolve_all(columns, build.ref_map)
        if columns and resolved_cols is not None:
            item["columns"] = resolved_cols
        elif columns:
            deferrals.append(
                Deferral(
                    kind="view",
                    identifier=vid,
                    name=vname,
                    parent=ename,
                    detail=(
                        "one or more columns reference a field not emitted on "
                        "the entity — columns omitted (CRM defaults used)"
                    ),
                )
            )

        item["filter"] = compiled_filter

        sort_field = view.get("view_sort_field")
        if sort_field:
            internal = build.ref_map.get(sort_field)
            if internal is not None:
                direction = view.get("view_sort_direction") or "asc"
                item["orderBy"] = {"field": internal, "direction": direction}
            else:
                deferrals.append(
                    Deferral(
                        kind="view",
                        identifier=vid,
                        name=vname,
                        parent=ename,
                        detail=(
                            "sort field is not emitted on the entity — orderBy "
                            "omitted"
                        ),
                    )
                )

        build.entity_block.setdefault("savedViews", []).append(item)


def _build_workflow_action(
    action: dict,
    build: _EntityBuild,
    deferrals: list[Deferral],
    aid: str,
    aname: str,
    idx: int,
) -> dict | None:
    """Map one neutral automation action to a v1.1 workflow action, or route
    it to a deferral. Only ``set_field`` (→ ``setField``) maps cleanly."""
    atype = action.get("type")
    if _ACTION_TYPE_TO_WORKFLOW.get(atype) == "setField":
        field_ref = action.get("field")
        internal = build.ref_map.get(field_ref) if field_ref else None
        value = action.get("value")
        if internal is None or value is None:
            deferrals.append(
                Deferral(
                    kind="workflow_action",
                    identifier=aid,
                    name=aname,
                    parent=build.program.entity_name,
                    detail=(
                        f"action[{idx}] set_field not rendered (field not "
                        "emitted or value missing) — configure via the admin UI"
                    ),
                )
            )
            return None
        return {"type": "setField", "field": internal, "value": value}
    deferrals.append(
        Deferral(
            kind="workflow_action",
            identifier=aid,
            name=aname,
            parent=build.program.entity_name,
            detail=(
                f"action[{idx}] type {atype!r} has no EspoCRM v1.1 workflow "
                "action — configure via the admin UI"
            ),
        )
    )
    return None


def _apply_automations(
    automations: list[dict],
    builds: dict[str, _EntityBuild],
    confirmed_entity_ids: set[str],
    entity_name_by_id: dict[str, str],
    index: dict[tuple[str, str, str], object],
    deferrals: list[Deferral],
) -> None:
    """Attach a ``workflows:`` block to each owning entity's program.

    A ``scheduled`` / ``manual`` trigger (no v1.1 event), an automation whose
    actions all defer, or an owning entity that is not emitted routes to a
    deferral. The ``where`` gate is dropped (with a note) when it touches a
    non-emitted field, leaving the workflow rendered without the extra gate.
    """
    for auto in sorted(automations, key=lambda a: a["automation_identifier"]):
        if auto.get("automation_status") != "confirmed":
            continue
        aid = auto["automation_identifier"]
        aname = auto.get("automation_name", "")
        eid = auto.get("automation_entity")
        if eid not in confirmed_entity_ids:
            deferrals.append(
                Deferral(
                    kind="automation",
                    identifier=aid,
                    name=aname,
                    parent=entity_name_by_id.get(eid, eid),
                    detail=(
                        "owning entity is not confirmed/emitted — workflow not "
                        "rendered"
                    ),
                )
            )
            continue
        event = _TRIGGER_TO_EVENT.get(auto.get("automation_trigger"))
        if event is None:
            deferrals.append(
                Deferral(
                    kind="automation",
                    identifier=aid,
                    name=aname,
                    parent=builds[eid].program.entity_name,
                    detail=(
                        f"trigger {auto.get('automation_trigger')!r} has no "
                        "EspoCRM v1.1 workflow event (scheduled/manual) — "
                        "configure via the admin UI"
                    ),
                )
            )
            continue
        build = builds[eid]

        emitted_actions: list[dict] = []
        for idx, action in enumerate(auto.get("automation_actions") or []):
            built = _build_workflow_action(action, build, deferrals, aid, aname, idx)
            if built is not None:
                emitted_actions.append(built)
        if not emitted_actions:
            deferrals.append(
                Deferral(
                    kind="automation",
                    identifier=aid,
                    name=aname,
                    parent=build.program.entity_name,
                    detail=(
                        "no action maps to a v1.1 workflow action — workflow "
                        "not rendered"
                    ),
                )
            )
            continue

        item: dict = {
            "id": _slug_id(aid),
            "name": str(_override(index, "automation", aid, "name", aname) or aid),
        }
        description = auto.get("automation_description")
        if description:
            item["description"] = str(description)
        item["trigger"] = {"event": event}

        raw_cond = auto.get("automation_condition")
        if raw_cond is not None:
            try:
                item["where"] = compile_condition(raw_cond, _strict_resolver(build.ref_map))
            except CompileError as exc:
                deferrals.append(
                    Deferral(
                        kind="automation",
                        identifier=aid,
                        name=aname,
                        parent=build.program.entity_name,
                        detail=(
                            f"where gate not emitted ({exc}) — workflow fires "
                            "without the additional condition"
                        ),
                    )
                )

        item["actions"] = emitted_actions
        build.entity_block.setdefault("workflows", []).append(item)


def _apply_dedup_rules(
    dedup_rules: list[dict],
    builds: dict[str, _EntityBuild],
    confirmed_entity_ids: set[str],
    entity_name_by_id: dict[str, str],
    index: dict[tuple[str, str, str], object],
    deferrals: list[Deferral],
) -> None:
    """Attach a ``duplicateChecks:`` block to each owning entity's program.

    A rule whose match fields are not all emitted, or whose owning entity is
    not emitted, routes to a deferral. A normalization token with no EspoCRM
    value (``trim`` / ``digits_only``) is dropped (the field stays a match
    field, unnormalized) with a note.
    """
    for dr in sorted(dedup_rules, key=lambda d: d["dedup_rule_identifier"]):
        if dr.get("dedup_rule_status") != "confirmed":
            continue
        did = dr["dedup_rule_identifier"]
        dname = dr.get("dedup_rule_name", "")
        eid = dr.get("dedup_rule_entity")
        if eid not in confirmed_entity_ids:
            deferrals.append(
                Deferral(
                    kind="dedup_rule",
                    identifier=did,
                    name=dname,
                    parent=entity_name_by_id.get(eid, eid),
                    detail=(
                        "owning entity is not confirmed/emitted — "
                        "duplicateCheck not rendered"
                    ),
                )
            )
            continue
        build = builds[eid]
        ename = build.program.entity_name

        match_fields = dr.get("dedup_rule_match_fields") or []
        resolved = _resolve_all(match_fields, build.ref_map)
        if not match_fields or resolved is None:
            deferrals.append(
                Deferral(
                    kind="dedup_rule",
                    identifier=did,
                    name=dname,
                    parent=ename,
                    detail=(
                        "one or more match fields reference a field not emitted "
                        "on the entity — duplicateCheck not rendered"
                    ),
                )
            )
            continue
        resolved_set = set(resolved)

        item: dict = {"id": _slug_id(did), "fields": resolved}

        normalize = dr.get("dedup_rule_normalize") or {}
        norm_out: dict[str, str] = {}
        for fref, token in sorted(normalize.items()):
            internal = build.ref_map.get(fref)
            espo_value = _NORMALIZE_TOKEN_TO_VALUE.get(token)
            if internal is None or internal not in resolved_set or espo_value is None:
                deferrals.append(
                    Deferral(
                        kind="dedup_normalize",
                        identifier=did,
                        name=dname,
                        parent=ename,
                        detail=(
                            f"normalize {fref!r} -> {token!r} not expressible "
                            "in EspoCRM — that field is compared unnormalized"
                        ),
                    )
                )
                continue
            norm_out[internal] = espo_value
        if norm_out:
            item["normalize"] = norm_out

        on_match = dr.get("dedup_rule_on_match")
        item["onMatch"] = on_match
        message = dr.get("dedup_rule_message")
        if on_match == "block":
            item["message"] = (
                str(message)
                if message
                else f"A duplicate {ename} record already exists."
            )
        elif message:
            item["message"] = str(message)

        build.entity_block.setdefault("duplicateChecks", []).append(item)


def _apply_message_templates(
    message_templates: list[dict],
    builds: dict[str, _EntityBuild],
    confirmed_entity_ids: set[str],
    entity_name_by_id: dict[str, str],
    index: dict[tuple[str, str, str], object],
    deferrals: list[Deferral],
    companions: list[ProgramArtifact],
) -> None:
    """Attach an ``emailTemplates:`` block to each owning entity's program and
    collect each template's ``bodyFile`` companion.

    Only ``email``-channel templates with a confirmed owning entity and at
    least one merge field resolving to an emitted field are rendered (the
    schema requires a non-empty, fully-used ``mergeFields`` list); everything
    else routes to a deferral. The subject and body are sanitized of stray
    placeholders and a deterministic, validated merge-field section is
    regenerated, so the block passes ``validate_program``'s placeholder rules.
    """
    for mt in sorted(
        message_templates, key=lambda m: m["message_template_identifier"]
    ):
        if mt.get("message_template_status") != "confirmed":
            continue
        mid = mt["message_template_identifier"]
        mname = mt.get("message_template_name", "")
        channel = mt.get("message_template_channel")
        eid = mt.get("message_template_entity")

        if channel != "email":
            deferrals.append(
                Deferral(
                    kind="message_template",
                    identifier=mid,
                    name=mname,
                    parent=entity_name_by_id.get(eid, eid),
                    detail=(
                        f"channel {channel!r} does not map to emailTemplates "
                        "(only the email channel does) — configure via the "
                        "admin UI"
                    ),
                )
            )
            continue
        if eid is None or eid not in confirmed_entity_ids:
            deferrals.append(
                Deferral(
                    kind="message_template",
                    identifier=mid,
                    name=mname,
                    parent=entity_name_by_id.get(eid, eid),
                    detail=(
                        "no confirmed owning entity — an emailTemplate has no "
                        "home program; configure via the admin UI"
                    ),
                )
            )
            continue
        build = builds[eid]
        ename = build.program.entity_name

        merge_internal: list[str] = []
        for mf in mt.get("message_template_merge_fields") or []:
            internal = build.ref_map.get(mf)
            if internal is None:
                deferrals.append(
                    Deferral(
                        kind="message_template",
                        identifier=mid,
                        name=mname,
                        parent=ename,
                        detail=(
                            f"merge field {mf!r} is not an emitted field — "
                            "dropped from the template"
                        ),
                    )
                )
            elif internal not in merge_internal:
                merge_internal.append(internal)
        merge_internal.sort()
        if not merge_internal:
            deferrals.append(
                Deferral(
                    kind="message_template",
                    identifier=mid,
                    name=mname,
                    parent=ename,
                    detail=(
                        "no merge field resolves to an emitted field; "
                        "emailTemplates requires a non-empty, used mergeFields "
                        "list — configure via the admin UI"
                    ),
                )
            )
            continue

        tid = _slug_id(mid)
        name = str(_override(index, "message_template", mid, "name", mname) or mid)

        subject_raw = mt.get("message_template_subject")
        subject = _strip_placeholders(str(subject_raw)).strip() if subject_raw else ""
        if not subject:
            subject = _strip_placeholders(name).strip() or "Notification"

        body_clean = _strip_placeholders(
            str(mt.get("message_template_body") or "")
        ).rstrip()
        merge_lines = "\n".join(f"{{{{{m}}}}}" for m in merge_internal)
        merge_section = f"<!-- merge fields (generated) -->\n{merge_lines}\n"
        body_content = (
            f"{body_clean}\n\n{merge_section}" if body_clean else merge_section
        )
        body_file = f"templates/{tid}.html"

        item: dict = {"id": tid, "name": name}
        description = mt.get("message_template_description")
        if description:
            item["description"] = str(description)
        item["entity"] = ename
        item["subject"] = subject
        item["bodyFile"] = body_file
        item["mergeFields"] = merge_internal
        audience = mt.get("message_template_audience")
        if audience:
            item["audience"] = str(audience)

        build.entity_block.setdefault("emailTemplates", []).append(item)
        companions.append(ProgramArtifact(filename=body_file, content=body_content))


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
    views: list[dict] | None = None,
    automations: list[dict] | None = None,
    dedup_rules: list[dict] | None = None,
    message_templates: list[dict] | None = None,
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

    Slice 3 adds the four remaining composite constructs as entity-level
    blocks on each owning entity's program: ``view`` → ``savedViews:``,
    ``automation`` → ``workflows:``, ``dedup_rule`` → ``duplicateChecks:``
    (all three deploy-``NOT_SUPPORTED`` but schema-valid — captured in the
    artifact and noted in MANUAL-CONFIG), and ``message_template`` →
    ``emailTemplates:`` (deployable; its ``bodyFile`` body is emitted as a
    companion artifact). Only ``confirmed`` records whose owning entity is
    emitted are rendered; the rest route to deferrals.
    """
    associations = associations or []
    rules = rules or []
    views = views or []
    automations = automations or []
    dedup_rules = dedup_rules or []
    message_templates = message_templates or []
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

    # PI-197: derived fields → formula: blocks (concat/arithmetic resolve
    # same-entity refs; aggregate resolves its association to relatedEntity/via).
    _apply_derived_formulas(
        [f for f in fields if f.get("field_status") == "confirmed"],
        builds,
        field_entity,
        associations,
        entity_name_by_id,
        index,
        deferrals,
    )

    # Slice 3: the four remaining composite constructs as entity-level blocks.
    companions: list[ProgramArtifact] = []
    _apply_dedup_rules(
        dedup_rules, builds, confirmed_entity_ids, entity_name_by_id, index, deferrals
    )
    _apply_views(
        views, builds, confirmed_entity_ids, entity_name_by_id, index, deferrals
    )
    _apply_message_templates(
        message_templates,
        builds,
        confirmed_entity_ids,
        entity_name_by_id,
        index,
        deferrals,
        companions,
    )
    _apply_automations(
        automations, builds, confirmed_entity_ids, entity_name_by_id, index, deferrals
    )

    programs = [builds[e["entity_identifier"]].program for e in confirmed_entities]

    return GenerationModel(
        engine=ENGINE,
        rendered_at=rendered_at,
        engagement=engagement,
        programs=programs,
        companions=companions,
        deferrals=deferrals,
    )
