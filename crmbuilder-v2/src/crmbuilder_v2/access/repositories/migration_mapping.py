"""Migration-mapping repository (WTK-107, per the WTK-105 API design spec).

Per ``methodology-schema-specs/migration-mapping-api.md`` (wire semantics)
and ``migration_mapping.md`` (storage semantics). The module-level functions
back the ``/migration-mappings`` REST endpoints and any future access-layer
caller (the compiler, MCP tools):

* :func:`list_migration_mappings` / :func:`get_migration_mapping` — reads,
  every record carrying the always-embedded ``migration_mapping_links``
  block (the two mandatory edges are *constitutive*: the record has no name
  column, so the source → target pair is its label). Links assembly is
  batched — one edge query plus one summary query per target type per
  request, never one per row (the WTK-060 ``list_touching`` N+1 finding).
* :func:`create_migration_mapping` — atomic insert of the mapping row PLUS
  its ``migration_mapping_migrates_from_record`` edge (exactly one) and
  ``migration_mapping_migrates_to_record`` edges (≥ 1) in one transaction —
  the ``field_belongs_to_entity`` DEC-249/250 pattern extended to a
  two-kind edge set. Validation runs the deterministic nine-step sequence
  of spec §4.7 (first failure wins).
* :func:`update_migration_mapping` / :func:`patch_migration_mapping` —
  full / partial update. Neither accepts the edge keys; ``level`` and
  ``disposition`` are constitutive and immutable (a change is a different
  mapping — re-create). Rule-list changes re-validate well-formedness and
  the shape coupling against the record's *existing* edges.
* :func:`delete_migration_mapping` / :func:`restore_migration_mapping` —
  soft-delete round-trip. Restore re-checks invariant I3 (the candidate
  may have been re-mapped while this row was deleted) and refuses when an
  edge target is itself soft-deleted (422 ``restore_blocked`` naming the
  blocked side, the ``field.md`` §3.4.6 pattern).
* :func:`triage_completeness` — the REST form of WTK-104 Q1 and the Master
  PRD v0.2 §8 completeness rule ("a keep/transform without a recorded
  mapping is incomplete triage"): lists every keep/transform obligation
  with no live mapping. A gate, not a write-time constraint — mappings and
  dispositions are recorded in either order within a session (I8).
* :func:`compile_preflight` — the REST form of Q5 (merge-group coherence)
  + Q6 (field-level mappings without entity-level context), the gates the
  compiler runs before emitting batches.
* :func:`next_migration_mapping_identifier` — the ``MIG-NNN`` allocator.

**Edge liveness is derived, not stored.** The ``refs`` table carries no
soft-delete column and the mapping row carries no stash columns, so the
spec's "soft-deleting a mapping soft-deletes both outgoing edges" is
implemented as *derived* liveness: the edge rows stay physically in place
and an edge counts as live iff its source mapping row is live (``deleted_at
IS NULL``). This is what lets a soft-deleted mapping's
``migration_mapping_links`` block still resolve (spec §4.2 A6), releases
the candidate for re-mapping on soft-delete (I3 checks join mapping
liveness), and makes restore a pure row-level un-stamp plus re-checks.

Transform-rule well-formedness (invariant I9) validates here against the
published ``MIGRATION_TRANSFORM_RULE_SCHEMAS`` table in ``vocab.py`` —
repository-layer authoritative, pydantic boundary structurally loose (spec
§5.2's location decision), so REST, MCP, and future compiler callers get
identical enforcement.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access import entity_summary
from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    DuplicateMappingForCandidateError,
    FieldError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import (
    Entity,
    Field,
    MigrationMapping,
    Reference,
)
from crmbuilder_v2.access.repositories import _rejection
from crmbuilder_v2.access.vocab import (
    FIELD_TYPES,
    MIGRATION_ENUM_UNMAPPED_POLICIES,
    MIGRATION_MAPPING_DISPOSITIONS,
    MIGRATION_MAPPING_LEVELS,
    MIGRATION_MAPPING_STATUS_TRANSITIONS,
    MIGRATION_MAPPING_STATUSES,
    MIGRATION_MERGE_COMBINATORS,
    MIGRATION_SPLIT_FIELD_STRATEGIES,
    MIGRATION_SPLIT_UNROUTED_POLICIES,
    MIGRATION_TRANSFORM_RULE_SCHEMAS,
    MIGRATION_TYPE_CHANGE_ON_ERROR,
    MIGRATION_TYPE_CHANGE_STRATEGIES,
)

_ENTITY_TYPE = "migration_mapping"
_IDENTIFIER_PREFIX = "MIG"
_IDENTIFIER_RE = re.compile(r"^MIG-\d{3}$")

_FROM_KIND = "migration_mapping_migrates_from_record"
_TO_KIND = "migration_mapping_migrates_to_record"

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign` (the field.py posture).
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_migration_mapping`. ``level`` and
# ``disposition`` are constitutive (spec §4.9) — not patchable; the edge
# keys are POST-only (spec §3.5.4); identifier and timestamps are
# server-owned.
_PATCHABLE_FIELDS = frozenset(
    {
        "source_system_label",
        "source_entity_name",
        "source_attribute_name",
        "transform_rules",
        "notes",
        "status",
    }
)

# Per-level candidate model map: (model, identifier column name, status
# column name, deleted-at column name, title column name). The two
# data-bearing capture types only — persona/process/manual_config mappings
# are unrepresentable by the vocab pair rules (invariant I12).
_LEVEL_MODELS: dict[str, tuple[type, str, str, str, str]] = {
    "entity": (
        Entity,
        "entity_identifier",
        "entity_status",
        "entity_deleted_at",
        "entity_name",
    ),
    "field": (
        Field,
        "field_identifier",
        "field_status",
        "field_deleted_at",
        "field_name",
    ),
}

# The variant/supersession edge kind that marks a rejected baseline
# candidate as *transformed* (rather than dropped), per level. The rejected
# candidate is the edge's TARGET; the superseding record is the source.
_SUPERSESSION_KINDS: dict[str, str] = {
    "entity": "entity_variant_of_entity",
    "field": "supersedes",
}

# Deterministic problem-code order for compile-preflight merge groups
# (spec §4.5's closed vocabulary).
_MERGE_PROBLEM_ORDER = (
    "distinct_targets",
    "distinct_combinators",
    "distinct_separators",
    "duplicate_merge_order",
)


# ---------------------------------------------------------------------------
# Scalar validation helpers (POST step 2)
# ---------------------------------------------------------------------------


def _fail(field: str, code: str, message: str) -> None:
    raise UnprocessableError([FieldError(field, code, message)])


def _require_level(level: object) -> str:
    if level not in MIGRATION_MAPPING_LEVELS:
        _fail(
            "migration_mapping_level",
            "invalid_level",
            f"must be one of {sorted(MIGRATION_MAPPING_LEVELS)}",
        )
    return level  # type: ignore[return-value]


def _require_disposition(disposition: object) -> str:
    if disposition not in MIGRATION_MAPPING_DISPOSITIONS:
        _fail(
            "migration_mapping_disposition",
            "invalid_disposition",
            f"must be one of {sorted(MIGRATION_MAPPING_DISPOSITIONS)}",
        )
    return disposition  # type: ignore[return-value]


def _require_status(status: object, *, starter: bool = False) -> str:
    if status not in MIGRATION_MAPPING_STATUSES:
        _fail(
            "migration_mapping_status",
            "invalid_status",
            f"must be one of {sorted(MIGRATION_MAPPING_STATUSES)}",
        )
    if starter and status == "rejected":
        # Spec §4.7: explicit ``confirmed`` is the live-triage posture;
        # ``rejected`` is a governed exit (WTK-088), never a starter.
        _fail(
            "migration_mapping_status",
            "invalid_status",
            "'rejected' is not a valid starter status",
        )
    return status  # type: ignore[return-value]


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(field, "nonempty_required", "must be a non-empty string")
    return value.strip()  # type: ignore[union-attr]


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        _fail(
            "migration_mapping_identifier",
            "invalid_identifier_format",
            r"must match ^MIG-\d{3}$ (e.g. MIG-001)",
        )
    return identifier


def _check_attribute_per_level(
    level: str, source_attribute_name: str | None
) -> str | None:
    """Invariant I11 (POST step 3): attribute present iff field-level."""
    if level == "field":
        if (
            not isinstance(source_attribute_name, str)
            or not source_attribute_name.strip()
        ):
            _fail(
                "migration_mapping_source_attribute_name",
                "attribute_name_level_mismatch",
                "required (non-empty) when migration_mapping_level is 'field'",
            )
        return source_attribute_name.strip()  # type: ignore[union-attr]
    if source_attribute_name is not None:
        _fail(
            "migration_mapping_source_attribute_name",
            "attribute_name_level_mismatch",
            "must be absent/null when migration_mapping_level is 'entity'",
        )
    return None


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move."""
    if requested == current:
        return
    if requested not in MIGRATION_MAPPING_STATUS_TRANSITIONS.get(
        current, frozenset()
    ):
        raise StatusTransitionError(current, requested)


# ---------------------------------------------------------------------------
# Transform-rule well-formedness (invariant I9; POST step 4)
# ---------------------------------------------------------------------------


def _rule_fail(index: int, message: str) -> None:
    _fail(
        f"migration_mapping_transform_rules[{index}]",
        "invalid_transform_rule",
        message,
    )


def _validate_type_change(rule: dict, index: int) -> None:
    from_type = rule.get("from_type")
    to_type = rule.get("to_type")
    if from_type not in FIELD_TYPES:
        _rule_fail(index, f"from_type must be one of {sorted(FIELD_TYPES)}")
    if to_type not in FIELD_TYPES:
        _rule_fail(index, f"to_type must be one of {sorted(FIELD_TYPES)}")
    if to_type == from_type:
        _rule_fail(index, "to_type must differ from from_type")
    conversion = rule.get("conversion")
    if conversion is None:
        return
    if not isinstance(conversion, dict):
        _rule_fail(index, "conversion must be an object")
    unknown = set(conversion) - {"strategy", "format", "on_error", "description"}
    if unknown:
        _rule_fail(index, f"unknown conversion keys: {sorted(unknown)}")
    strategy = conversion.get("strategy")
    if strategy not in MIGRATION_TYPE_CHANGE_STRATEGIES:
        _rule_fail(
            index,
            "conversion.strategy must be one of "
            f"{sorted(MIGRATION_TYPE_CHANGE_STRATEGIES)}",
        )
    if "format" in conversion and strategy != "parse":
        _rule_fail(index, "conversion.format is only valid with strategy 'parse'")
    on_error = conversion.get("on_error")
    if on_error is not None and on_error not in MIGRATION_TYPE_CHANGE_ON_ERROR:
        _rule_fail(
            index,
            "conversion.on_error must be one of "
            f"{sorted(MIGRATION_TYPE_CHANGE_ON_ERROR)}",
        )
    if strategy == "custom" and not conversion.get("description"):
        _rule_fail(index, "conversion strategy 'custom' requires a description")


def _validate_enum_value_map(rule: dict, index: int) -> None:
    value_map = rule.get("value_map")
    if (
        not isinstance(value_map, dict)
        or not value_map
        or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in value_map.items()
        )
    ):
        _rule_fail(
            index, "value_map must be a non-empty object of string -> string"
        )
    policy = rule.get("unmapped_policy")
    if policy not in MIGRATION_ENUM_UNMAPPED_POLICIES:
        _rule_fail(
            index,
            "unmapped_policy must be one of "
            f"{sorted(MIGRATION_ENUM_UNMAPPED_POLICIES)}",
        )
    if (policy == "default") != ("default_value" in rule):
        _rule_fail(
            index,
            "default_value is required iff unmapped_policy is 'default'",
        )


def _validate_merge(rule: dict, index: int, level: str) -> None:
    merge_group = rule.get("merge_group")
    if not isinstance(merge_group, str) or not merge_group.strip():
        _rule_fail(index, "merge_group must be a non-empty string")
    combinator = rule.get("combinator")
    if combinator not in MIGRATION_MERGE_COMBINATORS:
        _rule_fail(
            index,
            "combinator must be one of "
            f"{sorted(MIGRATION_MERGE_COMBINATORS)}",
        )
    if level == "entity" and combinator != "coalesce":
        _rule_fail(
            index, "entity-level merge admits only combinator 'coalesce'"
        )
    merge_order = rule.get("merge_order")
    if (
        not isinstance(merge_order, int)
        or isinstance(merge_order, bool)
        or merge_order < 1
    ):
        _rule_fail(index, "merge_order must be an integer >= 1")
    if ("separator" in rule) != (combinator == "concat"):
        _rule_fail(
            index, "separator is required iff combinator is 'concat'"
        )


def _validate_split(rule: dict, index: int, level: str) -> None:
    assignments = rule.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        _rule_fail(index, "assignments must be a non-empty list")
    for assignment in assignments:
        if not isinstance(assignment, dict):
            _rule_fail(index, "each assignment must be an object")
        unknown = set(assignment) - {"target", "extractor"}
        if unknown:
            _rule_fail(index, f"unknown assignment keys: {sorted(unknown)}")
        target = assignment.get("target")
        if not isinstance(target, str) or not target.strip():
            _rule_fail(index, "each assignment requires a non-empty target")
        extractor = assignment.get("extractor")
        if not isinstance(extractor, dict):
            _rule_fail(index, "each assignment requires an extractor object")
        strategy = extractor.get("strategy")
        if level == "entity":
            if strategy != "value_router":
                _rule_fail(
                    index,
                    "entity-level split extractors must use strategy "
                    "'value_router'",
                )
            if not extractor.get("router_attribute") or not isinstance(
                extractor.get("router_values"), list
            ):
                _rule_fail(
                    index,
                    "value_router extractors require router_attribute and "
                    "router_values",
                )
        else:
            if strategy not in MIGRATION_SPLIT_FIELD_STRATEGIES:
                _rule_fail(
                    index,
                    "field-level split extractor strategy must be one of "
                    f"{sorted(MIGRATION_SPLIT_FIELD_STRATEGIES)}",
                )
            if strategy == "delimiter" and (
                "delimiter" not in extractor or "index" not in extractor
            ):
                _rule_fail(
                    index,
                    "delimiter extractors require delimiter and index",
                )
            if strategy == "pattern" and not extractor.get("pattern"):
                _rule_fail(index, "pattern extractors require a pattern")
            if strategy == "custom" and not extractor.get("description"):
                _rule_fail(index, "custom extractors require a description")
    unrouted_policy = rule.get("unrouted_policy")
    if level == "entity":
        if unrouted_policy not in MIGRATION_SPLIT_UNROUTED_POLICIES:
            _rule_fail(
                index,
                "entity-level split requires unrouted_policy in "
                f"{sorted(MIGRATION_SPLIT_UNROUTED_POLICIES)}",
            )
    elif "unrouted_policy" in rule:
        _rule_fail(index, "unrouted_policy is entity-level only")


_KIND_VALIDATORS = {
    "type_change": lambda rule, index, level: _validate_type_change(rule, index),
    "enum_value_map": lambda rule, index, level: _validate_enum_value_map(
        rule, index
    ),
    "merge": _validate_merge,
    "split": _validate_split,
}


def validate_transform_rules(rules: object, level: str) -> list[dict] | None:
    """Validate the rule list per the published schema table (I9).

    Each rule is checked in list order — first failure wins, rendered as
    422 ``invalid_transform_rule`` with ``field`` naming the offending
    index. Checks per rule: ``rule_kind`` membership, required keys
    present, unknown keys refused, kind admissible at ``level`` (§4.6),
    and the per-kind conditional couplings. Cross-rule-vs-edge coupling
    (split target set = edge target set) is the caller's step-8 concern.
    Returns the normalized list (``None`` for empty/null).
    """
    if rules is None:
        return None
    if not isinstance(rules, list):
        _fail(
            "migration_mapping_transform_rules",
            "invalid_transform_rule",
            "must be a list of rule objects",
        )
    if not rules:
        return None
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            _rule_fail(index, "each rule must be an object")
        kind = rule.get("rule_kind")
        schema = MIGRATION_TRANSFORM_RULE_SCHEMAS.get(kind)
        if schema is None:
            _rule_fail(
                index,
                "rule_kind must be one of "
                f"{sorted(MIGRATION_TRANSFORM_RULE_SCHEMAS)}",
            )
        if level not in schema["levels"]:
            _rule_fail(
                index,
                f"rule_kind {kind!r} is not applicable at level {level!r}",
            )
        missing = schema["required"] - set(rule)
        if missing:
            _rule_fail(index, f"missing required keys: {sorted(missing)}")
        unknown = set(rule) - schema["required"] - schema["optional"]
        if unknown:
            _rule_fail(index, f"unknown keys: {sorted(unknown)}")
        _KIND_VALIDATORS[kind](rule, index, level)
    return rules


# ---------------------------------------------------------------------------
# Edge / reference validation (POST steps 5–8)
# ---------------------------------------------------------------------------


def _is_baseline_candidate(
    session: Session, level: str, identifier: str
) -> bool:
    """True iff the record carries audit-deposit provenance (WTK-089)."""
    row = session.scalar(
        select(Reference.id).where(
            Reference.relationship_kind == "deposit_event_wrote_record",
            Reference.target_type == level,
            Reference.target_id == identifier,
        )
    )
    return row is not None


def _candidate_row(session: Session, level: str, identifier: str):
    model, id_col, _status, _deleted, _title = _LEVEL_MODELS[level]
    return get_by_identifier(
        session, model, getattr(model, id_col), identifier
    )


def _require_source_candidate(
    session: Session, level: str, identifier: object
) -> str:
    """POST step 5: the disposed baseline candidate the mapping migrates from."""
    if not isinstance(identifier, str) or not identifier.strip():
        _fail(
            "migration_mapping_migrates_from_identifier",
            "missing_source_candidate",
            "migration_mapping_migrates_from_identifier is required",
        )
    identifier = identifier.strip()  # type: ignore[union-attr]
    row = _candidate_row(session, level, identifier)
    if row is None:
        # Distinguish a level mismatch from a genuine miss for the message.
        other = "entity" if level == "field" else "field"
        condition = (
            f"is a {other}, not a {level} (level mismatch)"
            if _candidate_row(session, other, identifier) is not None
            else "not found"
        )
        _fail(
            "migration_mapping_migrates_from_identifier",
            "invalid_source_candidate",
            f"source candidate {identifier!r} {condition}",
        )
    _model, _id_col, _status, deleted_col, _title = _LEVEL_MODELS[level]
    if getattr(row, deleted_col) is not None:
        _fail(
            "migration_mapping_migrates_from_identifier",
            "invalid_source_candidate",
            f"source candidate {identifier!r} is soft-deleted",
        )
    if not _is_baseline_candidate(session, level, identifier):
        _fail(
            "migration_mapping_migrates_from_identifier",
            "invalid_source_candidate",
            f"source candidate {identifier!r} is not a baseline candidate "
            "(no deposit_event_wrote_record provenance)",
        )
    return identifier


def _live_mapping_for_candidate(
    session: Session, level: str, identifier: str
) -> str | None:
    """The identifier of the live, non-rejected mapping sourcing the
    candidate, or ``None`` (invariant I3). A rejected or soft-deleted
    mapping releases the candidate (WTK-104 §3.3.1: re-doing a mapping
    means soft-deleting or rejecting the old one first)."""
    return session.scalar(
        select(MigrationMapping.migration_mapping_identifier)
        .join(
            Reference,
            Reference.source_id
            == MigrationMapping.migration_mapping_identifier,
        )
        .where(
            Reference.source_type == _ENTITY_TYPE,
            Reference.relationship_kind == _FROM_KIND,
            Reference.target_type == level,
            Reference.target_id == identifier,
            MigrationMapping.migration_mapping_deleted_at.is_(None),
            MigrationMapping.migration_mapping_status != "rejected",
        )
    )


def _check_source_uniqueness(
    session: Session,
    level: str,
    identifier: str,
    *,
    exclude_mapping: str | None = None,
) -> None:
    """POST step 6 / restore re-check: one live mapping per candidate."""
    existing = _live_mapping_for_candidate(session, level, identifier)
    if existing is not None and existing != exclude_mapping:
        raise DuplicateMappingForCandidateError(identifier, existing)


def _require_target_records(
    session: Session, level: str, identifiers: object
) -> list[str]:
    """POST step 7: ≥ 1 confirmed, live, level-typed target records."""
    if not isinstance(identifiers, list) or not identifiers:
        _fail(
            "migration_mapping_migrates_to_identifiers",
            "missing_target_record",
            "migration_mapping_migrates_to_identifiers requires at least "
            "one target record",
        )
    cleaned: list[str] = []
    for raw in identifiers:  # type: ignore[union-attr]
        if not isinstance(raw, str) or not raw.strip():
            _fail(
                "migration_mapping_migrates_to_identifiers",
                "invalid_target_record",
                "each target must be a non-empty identifier",
            )
        identifier = raw.strip()
        if identifier in cleaned:
            _fail(
                "migration_mapping_migrates_to_identifiers",
                "invalid_target_record",
                f"duplicate target identifier {identifier!r}",
            )
        row = _candidate_row(session, level, identifier)
        if row is None:
            _fail(
                "migration_mapping_migrates_to_identifiers",
                "invalid_target_record",
                f"target record {identifier!r} not found as a {level}",
            )
        _model, _id_col, status_col, deleted_col, _title = _LEVEL_MODELS[level]
        if getattr(row, deleted_col) is not None:
            _fail(
                "migration_mapping_migrates_to_identifiers",
                "invalid_target_record",
                f"target record {identifier!r} is soft-deleted",
            )
        if getattr(row, status_col) != "confirmed":
            _fail(
                "migration_mapping_migrates_to_identifiers",
                "invalid_target_record",
                f"target record {identifier!r} is at "
                f"{getattr(row, status_col)!r}; targets must be confirmed",
            )
        cleaned.append(identifier)
    return cleaned


def _check_shape(
    disposition: str,
    source_identifier: str,
    target_identifiers: list[str],
    rules: list[dict] | None,
) -> None:
    """POST step 8: the keep/transform/split shape couplings (I6/I7).

    Run at create against the body's edge keys and at PUT/PATCH against
    the record's existing edges (the spec §4.8 "shape half").
    """
    if disposition == "keep":
        if (
            len(target_identifiers) != 1
            or target_identifiers[0] != source_identifier
            or rules
        ):
            _fail(
                "migration_mapping_disposition",
                "invalid_keep_shape",
                "keep requires exactly one target equal to the source and "
                "empty transform_rules",
            )
        return
    if source_identifier in target_identifiers:
        _fail(
            "migration_mapping_disposition",
            "invalid_transform_shape",
            "transform requires the source not to appear among the targets",
        )
    split_rules = [
        (index, rule)
        for index, rule in enumerate(rules or [])
        if rule.get("rule_kind") == "split"
    ]
    if len(target_identifiers) > 1:
        if not split_rules:
            _fail(
                "migration_mapping_transform_rules",
                "split_rule_required",
                "more than one target record requires a split rule whose "
                "assignments cover the target set exactly",
            )
    # I6 is a biconditional: a split rule exists iff the edge-target set
    # has more than one member and the two sets agree exactly.
    if split_rules and len(target_identifiers) <= 1:
        _rule_fail(
            split_rules[0][0],
            "a split rule requires more than one target record",
        )
    for index, rule in split_rules:
        assigned = {
            assignment.get("target")
            for assignment in rule.get("assignments", [])
        }
        if assigned != set(target_identifiers):
            _rule_fail(
                index,
                "split assignments target set must equal the mapping's "
                f"target records exactly (assignments={sorted(assigned)}, "
                f"targets={sorted(target_identifiers)})",
            )


def _existing_edges(
    session: Session, identifier: str
) -> tuple[str | None, list[str]]:
    """The mapping's physical from-target and to-target identifiers."""
    rows = session.scalars(
        select(Reference).where(
            Reference.source_type == _ENTITY_TYPE,
            Reference.source_id == identifier,
            Reference.relationship_kind.in_([_FROM_KIND, _TO_KIND]),
        )
    ).all()
    source: str | None = None
    targets: list[str] = []
    for row in rows:
        if row.relationship_kind == _FROM_KIND:
            source = row.target_id
        else:
            targets.append(row.target_id)
    return source, sorted(targets)


# ---------------------------------------------------------------------------
# Links assembly (batched — spec §4.1's N+1 guard)
# ---------------------------------------------------------------------------


def _links_for(
    session: Session, mapping_identifiers: list[str]
) -> dict[str, dict]:
    """Batch-assemble the ``migration_mapping_links`` block per mapping.

    One edge query for the whole identifier set plus one summary query per
    target *type* (≤ 2) — constant in row count. Summary columns reuse the
    :mod:`entity_summary` column map (title rendered as ``name``); a target
    whose row no longer resolves degrades to identifier-only.
    """
    links: dict[str, dict] = {
        identifier: {"migrates_from": None, "migrates_to": []}
        for identifier in mapping_identifiers
    }
    if not mapping_identifiers:
        return links
    edges = session.scalars(
        select(Reference).where(
            Reference.source_type == _ENTITY_TYPE,
            Reference.source_id.in_(mapping_identifiers),
            Reference.relationship_kind.in_([_FROM_KIND, _TO_KIND]),
        )
    ).all()
    wanted: dict[str, set[str]] = {}
    for edge in edges:
        wanted.setdefault(edge.target_type, set()).add(edge.target_id)
    summaries: dict[tuple[str, str], dict] = {}
    for target_type, identifiers in wanted.items():
        spec = entity_summary._SPECS[target_type]
        id_col = getattr(spec.model, spec.id_col)
        for row in session.scalars(
            select(spec.model).where(id_col.in_(identifiers))
        ):
            identifier = getattr(row, spec.id_col)
            summaries[(target_type, identifier)] = {
                "identifier": identifier,
                "entity_type": target_type,
                "name": getattr(row, spec.title_col),
                "status": (
                    getattr(row, spec.status_col) if spec.status_col else None
                ),
            }
    for edge in edges:
        summary = summaries.get((edge.target_type, edge.target_id)) or {
            "identifier": edge.target_id,
            "entity_type": edge.target_type,
            "name": None,
            "status": None,
        }
        block = links[edge.source_id]
        if edge.relationship_kind == _FROM_KIND:
            block["migrates_from"] = summary
        else:
            block["migrates_to"].append(summary)
    for block in links.values():
        block["migrates_to"].sort(key=lambda summary: summary["identifier"])
    return links


def _with_links(session: Session, rows: list[MigrationMapping]) -> list[dict]:
    identifiers = [row.migration_mapping_identifier for row in rows]
    links = _links_for(session, identifiers)
    out = []
    for row in rows:
        record = to_dict(row)
        record["migration_mapping_links"] = links[
            row.migration_mapping_identifier
        ]
        out.append(record)
    return out


def _record(session: Session, row: MigrationMapping) -> dict:
    return _with_links(session, [row])[0]


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_migration_mappings(
    session: Session,
    *,
    level: str | None = None,
    source_identifier: str | None = None,
    target_identifier: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return mappings ordered by identifier ascending, links embedded.

    ``level`` filters on the column (other values → 422 ``invalid_filter``);
    ``source_identifier`` / ``target_identifier`` filter through the live
    ``migrates_from_record`` / ``migrates_to_record`` edges (spec §3.5.5 —
    the disposition lookup and merge-group assembly reads). Soft-deleted
    rows are excluded unless ``include_deleted`` is True (their links still
    resolve through the physically-retained edges).
    """
    if level is not None and level not in MIGRATION_MAPPING_LEVELS:
        _fail(
            "level",
            "invalid_filter",
            f"must be one of {sorted(MIGRATION_MAPPING_LEVELS)}",
        )
    stmt = select(MigrationMapping).order_by(
        MigrationMapping.migration_mapping_identifier
    )
    if level is not None:
        stmt = stmt.where(MigrationMapping.migration_mapping_level == level)
    if source_identifier is not None:
        edge_ids = select(Reference.source_id).where(
            Reference.source_type == _ENTITY_TYPE,
            Reference.relationship_kind == _FROM_KIND,
            Reference.target_id == source_identifier,
        )
        stmt = stmt.where(
            MigrationMapping.migration_mapping_identifier.in_(edge_ids)
        )
    if target_identifier is not None:
        edge_ids = select(Reference.source_id).where(
            Reference.source_type == _ENTITY_TYPE,
            Reference.relationship_kind == _TO_KIND,
            Reference.target_id == target_identifier,
        )
        stmt = stmt.where(
            MigrationMapping.migration_mapping_identifier.in_(edge_ids)
        )
    if not include_deleted:
        stmt = stmt.where(MigrationMapping.migration_mapping_deleted_at.is_(None))
    return _with_links(session, list(session.scalars(stmt).all()))


def get_migration_mapping(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single mapping with links, or ``None`` if not visible."""
    row = get_by_identifier(
        session,
        MigrationMapping,
        MigrationMapping.migration_mapping_identifier,
        identifier,
    )
    if row is None:
        return None
    if row.migration_mapping_deleted_at is not None and not include_deleted:
        return None
    return _record(session, row)


def next_migration_mapping_identifier(session: Session) -> str:
    """Return the next available ``MIG-NNN`` (soft-deleted rows included)."""
    identifiers = session.scalars(
        select(MigrationMapping.migration_mapping_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Derived gate reads (E3 / E4)
# ---------------------------------------------------------------------------


def triage_completeness(session: Session, level: str | None = None) -> dict:
    """The PRD §8 completion gate (WTK-104 Q1) as a callable check.

    Lists every keep/transform migration obligation with no live mapping:

    * **keep** — a live *baseline* candidate (audit-deposited) at
      ``confirmed`` with no live inbound ``migrates_from_record`` edge
      from a live, non-rejected mapping.
    * **transform** — a live baseline candidate at ``rejected`` that is
      the target of a variant/supersession edge (``entity_variant_of_entity``
      at entity level, same-type ``supersedes`` at field level), with no
      live inbound ``migrates_from_record`` edge.

    Undisposed candidates (still ``candidate``) and drops (rejected with
    no supersession edge) are not migration obligations and never appear;
    non-baseline (interview-born) records never appear at any status.
    """
    if level is not None and level not in MIGRATION_MAPPING_LEVELS:
        _fail(
            "level",
            "invalid_filter",
            f"must be one of {sorted(MIGRATION_MAPPING_LEVELS)}",
        )
    levels = [level] if level is not None else ["entity", "field"]
    unmapped: list[dict] = []
    counts = {"keep_unmapped": 0, "transform_unmapped": 0}
    for lvl in levels:
        model, id_col_name, status_col_name, deleted_col_name, title_col_name = (
            _LEVEL_MODELS[lvl]
        )
        id_col = getattr(model, id_col_name)
        status_col = getattr(model, status_col_name)
        deleted_col = getattr(model, deleted_col_name)

        baseline = (
            select(Reference.id)
            .where(
                Reference.relationship_kind == "deposit_event_wrote_record",
                Reference.target_type == lvl,
                Reference.target_id == id_col,
            )
            .exists()
        )
        satisfied = (
            select(Reference.id)
            .join(
                MigrationMapping,
                MigrationMapping.migration_mapping_identifier
                == Reference.source_id,
            )
            .where(
                Reference.source_type == _ENTITY_TYPE,
                Reference.relationship_kind == _FROM_KIND,
                Reference.target_type == lvl,
                Reference.target_id == id_col,
                MigrationMapping.migration_mapping_deleted_at.is_(None),
                MigrationMapping.migration_mapping_status != "rejected",
            )
            .exists()
        )

        for row in session.scalars(
            select(model)
            .where(
                deleted_col.is_(None),
                status_col == "confirmed",
                baseline,
                ~satisfied,
            )
            .order_by(id_col)
        ):
            counts["keep_unmapped"] += 1
            unmapped.append(
                {
                    "identifier": getattr(row, id_col_name),
                    "entity_type": lvl,
                    "name": getattr(row, title_col_name),
                    "disposition": "keep",
                    "detail": (
                        "confirmed baseline candidate with no live mapping"
                    ),
                }
            )

        superseded = (
            select(Reference.id)
            .where(
                Reference.relationship_kind == _SUPERSESSION_KINDS[lvl],
                Reference.source_type == lvl,
                Reference.target_type == lvl,
                Reference.target_id == id_col,
            )
            .exists()
        )
        for row in session.scalars(
            select(model)
            .where(
                deleted_col.is_(None),
                status_col == "rejected",
                baseline,
                superseded,
                ~satisfied,
            )
            .order_by(id_col)
        ):
            identifier = getattr(row, id_col_name)
            superseder = session.scalar(
                select(Reference.source_id)
                .where(
                    Reference.relationship_kind == _SUPERSESSION_KINDS[lvl],
                    Reference.source_type == lvl,
                    Reference.target_type == lvl,
                    Reference.target_id == identifier,
                )
                .order_by(Reference.source_id)
            )
            counts["transform_unmapped"] += 1
            unmapped.append(
                {
                    "identifier": identifier,
                    "entity_type": lvl,
                    "name": getattr(row, title_col_name),
                    "disposition": "transform",
                    "detail": (
                        "rejected baseline candidate superseded by "
                        f"{superseder} with no live mapping"
                    ),
                }
            )

    mapped_stmt = select(MigrationMapping).where(
        MigrationMapping.migration_mapping_deleted_at.is_(None),
        MigrationMapping.migration_mapping_status != "rejected",
    )
    if level is not None:
        mapped_stmt = mapped_stmt.where(
            MigrationMapping.migration_mapping_level == level
        )
    mapped = len(session.scalars(mapped_stmt).all())

    unmapped.sort(key=lambda item: (item["entity_type"], item["identifier"]))
    return {
        "complete": not unmapped,
        "unmapped": unmapped,
        "counts": {**counts, "mapped": mapped},
    }


def compile_preflight(session: Session) -> dict:
    """The compile gates (WTK-104 Q5 + Q6) as a callable check.

    Two sections over live **confirmed** mappings, both empty for
    ``ready: true``: merge-group incoherence (more than one distinct
    target / combinator / separator, or non-distinct ``merge_order`` —
    I10) and confirmed field-level mappings without entity-level context
    (source field's parent entity not the source of a confirmed
    entity-level mapping, or target field's parent not that mapping's
    target — Q6). Triage completeness is deliberately a separate gate
    (E3); the compiler's full pre-flight is both.
    """
    rows = session.scalars(
        select(MigrationMapping)
        .where(
            MigrationMapping.migration_mapping_deleted_at.is_(None),
            MigrationMapping.migration_mapping_status == "confirmed",
        )
        .order_by(MigrationMapping.migration_mapping_identifier)
    ).all()
    by_id = {row.migration_mapping_identifier: row for row in rows}

    edges: list[Reference] = []
    if by_id:
        edges = list(
            session.scalars(
                select(Reference).where(
                    Reference.source_type == _ENTITY_TYPE,
                    Reference.source_id.in_(list(by_id)),
                    Reference.relationship_kind.in_([_FROM_KIND, _TO_KIND]),
                )
            ).all()
        )
    sources: dict[str, str] = {}
    targets: dict[str, list[str]] = {identifier: [] for identifier in by_id}
    for edge in edges:
        if edge.relationship_kind == _FROM_KIND:
            sources[edge.source_id] = edge.target_id
        else:
            targets[edge.source_id].append(edge.target_id)

    # --- Q5: merge-group coherence across live confirmed mappings.
    groups: dict[str, list[tuple[str, dict]]] = {}
    for identifier, row in by_id.items():
        for rule in row.migration_mapping_transform_rules or []:
            if rule.get("rule_kind") == "merge":
                groups.setdefault(rule["merge_group"], []).append(
                    (identifier, rule)
                )
    incoherent_merge_groups = []
    for group_name in sorted(groups):
        members = groups[group_name]
        problems = set()
        group_targets = {
            target for identifier, _rule in members for target in targets[identifier]
        }
        if len(group_targets) > 1:
            problems.add("distinct_targets")
        if len({rule.get("combinator") for _id, rule in members}) > 1:
            problems.add("distinct_combinators")
        if len({rule.get("separator") for _id, rule in members}) > 1:
            problems.add("distinct_separators")
        orders = [rule.get("merge_order") for _id, rule in members]
        if len(orders) != len(set(orders)):
            problems.add("duplicate_merge_order")
        if problems:
            incoherent_merge_groups.append(
                {
                    "merge_group": group_name,
                    "mappings": sorted(
                        identifier for identifier, _rule in members
                    ),
                    "problems": [
                        problem
                        for problem in _MERGE_PROBLEM_ORDER
                        if problem in problems
                    ],
                }
            )

    # --- Q6: confirmed field-level mappings without entity-level context.
    field_ids: set[str] = set()
    for identifier, row in by_id.items():
        if row.migration_mapping_level == "field":
            if identifier in sources:
                field_ids.add(sources[identifier])
            field_ids.update(targets[identifier])
    parent_of: dict[str, str] = {}
    if field_ids:
        for edge in session.scalars(
            select(Reference).where(
                Reference.source_type == "field",
                Reference.source_id.in_(field_ids),
                Reference.relationship_kind == "field_belongs_to_entity",
            )
        ):
            parent_of[edge.source_id] = edge.target_id
    entity_mappings_by_source = {
        sources[identifier]: identifier
        for identifier, row in by_id.items()
        if row.migration_mapping_level == "entity" and identifier in sources
    }
    fields_without_entity_context = []
    for identifier in sorted(by_id):
        row = by_id[identifier]
        if row.migration_mapping_level != "field":
            continue
        source_field = sources.get(identifier)
        source_entity = parent_of.get(source_field) if source_field else None
        if source_field is None or source_entity is None:
            continue
        entity_mapping = entity_mappings_by_source.get(source_entity)
        if entity_mapping is None:
            fields_without_entity_context.append(
                {
                    "mapping": identifier,
                    "source_field": source_field,
                    "source_entity": source_entity,
                    "problem": (
                        "no confirmed entity-level mapping migrates from "
                        f"{source_entity}"
                    ),
                }
            )
            continue
        entity_targets = set(targets[entity_mapping])
        for target_field in sorted(targets[identifier]):
            target_parent = parent_of.get(target_field)
            if target_parent is not None and target_parent not in entity_targets:
                fields_without_entity_context.append(
                    {
                        "mapping": identifier,
                        "source_field": source_field,
                        "source_entity": source_entity,
                        "problem": (
                            f"target field {target_field} parent entity "
                            f"{target_parent} is not a target of entity-level "
                            f"mapping {entity_mapping}"
                        ),
                    }
                )

    return {
        "ready": not incoherent_merge_groups
        and not fields_without_entity_context,
        "incoherent_merge_groups": incoherent_merge_groups,
        "fields_without_entity_context": fields_without_entity_context,
    }


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier: str,
    level: str,
    disposition: str,
    source_system_label: str,
    source_entity_name: str,
    source_attribute_name: str | None,
    transform_rules: list[dict] | None,
    notes: str | None,
    status: str,
) -> MigrationMapping:
    return MigrationMapping(
        migration_mapping_identifier=identifier,
        migration_mapping_level=level,
        migration_mapping_disposition=disposition,
        migration_mapping_source_system_label=source_system_label,
        migration_mapping_source_entity_name=source_entity_name,
        migration_mapping_source_attribute_name=source_attribute_name,
        migration_mapping_transform_rules=transform_rules,
        migration_mapping_notes=notes,
        migration_mapping_status=status,
    )


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _insert_with_autoassign(session: Session, **columns) -> MigrationMapping:
    """Insert with a server-assigned identifier, SAVEPOINT-collision-safe."""
    candidate = next_migration_mapping_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, **columns)
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique migration_mapping identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_migration_mapping(
    session: Session,
    *,
    level: str,
    disposition: str,
    source_system_label: str,
    source_entity_name: str,
    migrates_from_identifier: str,
    migrates_to_identifiers: list[str],
    source_attribute_name: str | None = None,
    transform_rules: list[dict] | None = None,
    notes: str | None = None,
    status: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Atomic create: row + both mandatory edges + change-log in one
    transaction, validated by the deterministic spec §4.7 sequence
    (steps 2–9 here; step 1 is the pydantic boundary). A failure at any
    step leaves no orphan row or edge.
    """
    # Step 2 — scalar domain.
    level = _require_level(level)
    disposition = _require_disposition(disposition)
    if status is None:
        status = "candidate"
    status = _require_status(status, starter=True)
    source_system_label = _require_nonempty(
        source_system_label, field="migration_mapping_source_system_label"
    )
    source_entity_name = _require_nonempty(
        source_entity_name, field="migration_mapping_source_entity_name"
    )
    if identifier is not None:
        _require_identifier_format(identifier)
    # Step 3 — I11 agreement.
    source_attribute_name = _check_attribute_per_level(
        level, source_attribute_name
    )
    # Step 4 — rule-list well-formedness.
    transform_rules = validate_transform_rules(transform_rules, level)
    # Step 5 — source edge.
    source = _require_source_candidate(session, level, migrates_from_identifier)
    # Step 6 — source uniqueness (I3).
    _check_source_uniqueness(session, level, source)
    # Step 7 — target edges.
    targets = _require_target_records(session, level, migrates_to_identifiers)
    # Step 8 — shape coupling.
    _check_shape(disposition, source, targets, transform_rules)
    # Step 9 — insert (server-assigned or explicit identifier).
    columns = {
        "level": level,
        "disposition": disposition,
        "source_system_label": source_system_label,
        "source_entity_name": source_entity_name,
        "source_attribute_name": source_attribute_name,
        "transform_rules": transform_rules,
        "notes": notes,
        "status": status,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **columns)
    else:
        if (
            get_by_identifier(
                session,
                MigrationMapping,
                MigrationMapping.migration_mapping_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(f"migration_mapping {identifier!r} already exists")
        row = _new_row(identifier, **columns)
        session.add(row)
        session.flush()

    # Both mandatory edges in the same transaction (imported locally to
    # avoid a module-load cycle, the field.py posture).
    from crmbuilder_v2.access.repositories import references

    references.create(
        session,
        source_type=_ENTITY_TYPE,
        source_id=row.migration_mapping_identifier,
        target_type=level,
        target_id=source,
        relationship=_FROM_KIND,
    )
    for target in targets:
        references.create(
            session,
            source_type=_ENTITY_TYPE,
            source_id=row.migration_mapping_identifier,
            target_type=level,
            target_id=target,
            relationship=_TO_KIND,
        )

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.migration_mapping_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return _record(session, row)


def _get_row(session: Session, identifier: str) -> MigrationMapping:
    row = get_by_identifier(
        session,
        MigrationMapping,
        MigrationMapping.migration_mapping_identifier,
        identifier,
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _apply_status_change(
    session: Session,
    row: MigrationMapping,
    requested: str,
    rejected_by_decision: str | None,
) -> str | None:
    """Transition-validate and apply a status change; returns the
    ``rejected_by_decision`` value still pending an :func:`attach_decision`
    (the field.py contract)."""
    if requested != row.migration_mapping_status:
        _check_transition(row.migration_mapping_status, requested)
        if requested == "rejected":
            _rejection.enforce_rejected_status(
                session,
                source_type=_ENTITY_TYPE,
                source_identifier=row.migration_mapping_identifier,
                decision_identifier=rejected_by_decision,
            )
            rejected_by_decision = None
        row.migration_mapping_status = requested
    return rejected_by_decision


def update_migration_mapping(
    session: Session,
    identifier: str,
    *,
    migration_mapping_identifier: str | None = None,
    level: str,
    disposition: str,
    source_system_label: str,
    source_entity_name: str,
    source_attribute_name: str | None = None,
    transform_rules: list[dict] | None = None,
    notes: str | None = None,
    status: str,
    rejected_by_decision: str | None = None,
) -> dict:
    """Full-replace update (PUT) of the scalar columns.

    Does NOT accept the edge keys — re-pointing is explicit reference
    management (normally soft-delete and re-create, spec §4.8). ``level``
    and ``disposition`` are constitutive: the supplied values must equal
    the record's current ones. Rule validation and the shape half of the
    step-8 coupling re-run against the record's *existing* edges. A
    ``status`` change is transition-validated.
    """
    row = _get_row(session, identifier)
    if (
        migration_mapping_identifier is not None
        and migration_mapping_identifier != identifier
    ):
        _fail(
            "migration_mapping_identifier",
            "path_mismatch",
            "identifier in body must match the path",
        )
    before = to_dict(row)

    level = _require_level(level)
    if level != row.migration_mapping_level:
        _fail(
            "migration_mapping_level",
            "immutable",
            "level is constitutive; a level change is a different mapping "
            "(soft-delete and re-create)",
        )
    disposition = _require_disposition(disposition)
    if disposition != row.migration_mapping_disposition:
        _fail(
            "migration_mapping_disposition",
            "immutable",
            "disposition is constitutive; a disposition change is a "
            "different mapping (soft-delete and re-create)",
        )
    source_system_label = _require_nonempty(
        source_system_label, field="migration_mapping_source_system_label"
    )
    source_entity_name = _require_nonempty(
        source_entity_name, field="migration_mapping_source_entity_name"
    )
    source_attribute_name = _check_attribute_per_level(
        level, source_attribute_name
    )
    transform_rules = validate_transform_rules(transform_rules, level)
    edge_source, edge_targets = _existing_edges(session, identifier)
    if edge_source is not None:
        _check_shape(disposition, edge_source, edge_targets, transform_rules)

    status_v = _require_status(status)
    rejected_by_decision = _apply_status_change(
        session, row, status_v, rejected_by_decision
    )
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.migration_mapping_status,
        )

    row.migration_mapping_source_system_label = source_system_label
    row.migration_mapping_source_entity_name = source_entity_name
    row.migration_mapping_source_attribute_name = source_attribute_name
    row.migration_mapping_transform_rules = transform_rules
    row.migration_mapping_notes = notes
    session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return _record(session, row)


def patch_migration_mapping(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``source_system_label``, ``source_entity_name``,
    ``source_attribute_name``, ``transform_rules``, ``notes``, ``status``,
    ``rejected_by_decision`` (the WTK-088 atomic edge-and-flip admission,
    exposed over REST for mappings per spec §4.9). Cross-field checks
    re-run where touched: rules re-validate well-formedness plus the edge
    coupling; ``source_attribute_name`` re-checks I11.
    """
    rejected_by_decision = fields.pop("rejected_by_decision", None)
    unknown = set(fields) - _PATCHABLE_FIELDS
    if unknown:
        _fail(
            "fields",
            "unknown_field",
            f"unknown patchable fields: {sorted(unknown)}",
        )
    row = _get_row(session, identifier)
    before = to_dict(row)

    if "source_system_label" in fields:
        row.migration_mapping_source_system_label = _require_nonempty(
            fields["source_system_label"],
            field="migration_mapping_source_system_label",
        )
    if "source_entity_name" in fields:
        row.migration_mapping_source_entity_name = _require_nonempty(
            fields["source_entity_name"],
            field="migration_mapping_source_entity_name",
        )
    if "source_attribute_name" in fields:
        row.migration_mapping_source_attribute_name = _check_attribute_per_level(
            row.migration_mapping_level, fields["source_attribute_name"]
        )
    if "transform_rules" in fields:
        rules = validate_transform_rules(
            fields["transform_rules"], row.migration_mapping_level
        )
        edge_source, edge_targets = _existing_edges(session, identifier)
        if edge_source is not None:
            _check_shape(
                row.migration_mapping_disposition,
                edge_source,
                edge_targets,
                rules,
            )
        row.migration_mapping_transform_rules = rules
    if "notes" in fields:
        row.migration_mapping_notes = fields["notes"]
    if "status" in fields:
        status_v = _require_status(fields["status"])
        rejected_by_decision = _apply_status_change(
            session, row, status_v, rejected_by_decision
        )
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.migration_mapping_status,
        )

    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return _record(session, row)


def delete_migration_mapping(session: Session, identifier: str) -> dict:
    """Soft-delete the mapping; both edges go non-live with it.

    Edge liveness is derived from the row (module docstring), so stamping
    ``deleted_at`` IS the atomic edge soft-delete: the candidate's I3 slot
    frees immediately, while the physical edge rows keep the soft-deleted
    record's links resolvable. Idempotent — deleting an already-deleted
    mapping returns the record unchanged.
    """
    row = _get_row(session, identifier)
    if row.migration_mapping_deleted_at is not None:
        return _record(session, row)
    before = to_dict(row)
    row.migration_mapping_deleted_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return _record(session, row)


def restore_migration_mapping(session: Session, identifier: str) -> dict:
    """Clear ``deleted_at``, bringing both edges back live with the row.

    Refuses when the row is live (422 ``not_deleted``), when any edge
    target is itself soft-deleted (422 ``restore_blocked`` naming the
    blocked side), or when the candidate acquired a new live mapping
    while this one was deleted (the I3 re-check, flat-shape
    ``duplicate_mapping_for_candidate``).
    """
    row = _get_row(session, identifier)
    if row.migration_mapping_deleted_at is None:
        _fail(
            "migration_mapping_deleted_at",
            "not_deleted",
            "migration_mapping is not soft-deleted",
        )
    level = row.migration_mapping_level
    edge_source, edge_targets = _existing_edges(session, identifier)
    _model, _id_col, _status, deleted_col_name, _title = _LEVEL_MODELS[level]
    sides = [("migrates_from", edge_source)] if edge_source else []
    sides += [("migrates_to", target) for target in edge_targets]
    for side, target_identifier in sides:
        target_row = _candidate_row(session, level, target_identifier)
        if target_row is None or getattr(target_row, deleted_col_name) is not None:
            _fail(
                f"{side}[{target_identifier}]",
                "restore_blocked",
                f"edge target {target_identifier!r} is "
                f"{'missing' if target_row is None else 'soft-deleted'}; "
                "restore it first",
            )
    if edge_source is not None:
        _check_source_uniqueness(
            session, level, edge_source, exclude_mapping=identifier
        )

    before = to_dict(row)
    row.migration_mapping_deleted_at = None
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return _record(session, row)
