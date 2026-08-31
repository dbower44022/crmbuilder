"""Governance-rule repository (PI-122 — Agent Profile Registry, D-δ1).

A ``governance_rule`` (``GVR-NNN``) is a shared, reusable rule with a hybrid
``enforcement`` mode (advisory / enforced / enforced_with_override; PRD §5).
System/shared row with a nullable ``engagement_id`` scope.

Per-engagement overrides (REQ-529..533 / DEC-955 / PI-435). A system rule
(``engagement_id IS NULL``) is the inheritable default; an engagement-scoped
rule reshapes it for that engagement only:

* **Shadow by rule key** (REQ-530) — an engagement rule with the same non-null
  ``rule_type`` as a system rule replaces it. Resolution is *most specific
  scope wins, per rule_type*; see :func:`resolve_overlay` /
  :func:`list_effective`. The same resolver composes agent contracts
  (:mod:`registry_resolver`, REQ-533).
* **Disable** — an engagement rule whose ``rule_type`` is
  ``"disable:<identifier-or-rule_type>"`` suppresses the named system rule.
* **Supersedes provenance** (REQ-531) — creating an override records a
  ``governance_rule --supersedes--> governance_rule`` reference edge to every
  system rule it shadows or disables, so a client's deviations from the
  defaults are queryable.
* **Demand-driven keying** (REQ-532) — an override that targets a system rule
  *by identifier* (``disable:GVR-NNN``) is rejected while that rule has no
  ``rule_type``: key the default first, then override it. Shadowing by
  ``rule_type`` can never reach an untyped rule, so keying is the only path.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    next_prefixed_identifier,
    require_string,
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.models import GovernanceRuleRow, RuleEnforcementOverrideRow
from crmbuilder_v2.access.repositories import references
from crmbuilder_v2.access.repositories._registry import resolve_scope, with_scope
from crmbuilder_v2.access.vocab import (
    REGISTRY_STATUSES,
    RULE_AUDIENCES,
    RULE_CHANGE_KINDS,
    RULE_CHECK_KINDS,
    RULE_ENFORCED_MODES,
    RULE_ENFORCEMENT_MODES,
    RULE_MOMENTS,
    RULE_SEVERITIES,
)

_ENTITY_TYPE = "governance_rule"
_IDENTIFIER_PREFIX = "GVR"
_IDENTIFIER_RE = re.compile(r"^GVR-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_UPDATABLE_FIELDS = frozenset(
    {
        "rule_type", "enforcement", "severity", "body", "predicate", "version",
        "status", "applies_to", "applies_when",
    }
)
# Engagement-overlay vocabulary (WTK-001 / REQ-530..532).
DISABLE_PREFIX = "disable:"
SUPERSEDES = "supersedes"


def compute_next_identifier(session: Session) -> str:
    identifiers = session.scalars(select(GovernanceRuleRow.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [FieldError("identifier", "invalid_format", r"must match ^GVR-\d{3}$")]
        )
    return identifier


def _increment(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _require_vocab(field: str, value: str, allowed) -> str:
    if value not in allowed:
        raise UnprocessableError(
            [FieldError(field, "invalid", f"{field} must be one of {sorted(allowed)}")]
        )
    return value


def _enrich(row: GovernanceRuleRow) -> dict:
    return with_scope(to_dict(row), row.engagement_id)


def validate_predicate(
    enforcement: str, predicate: dict | None, applies_to: str = "all"
) -> None:
    """REQ-542: an enforced rule must carry a well-formed check.

    ``predicate`` is ``{"kind": <RULE_CHECK_KINDS>, "pattern": <regex>, ...}``;
    ``required_trailer`` also names the ``trailer``. A rule labelled enforced
    without a check is the false promise DEC-964 retires, so it is rejected.

    Scope (DEC-972): the obligation applies to the audiences the pre-action hook
    serves. An ``ado_agent`` rule's enforcement is the agent contract's hard-gates
    section verified by the Tester tier, not a machine check by this hook, so it
    may stay ``enforced`` without a predicate — the seeded self-verify gates
    depend on this. A supplied predicate is always validated whatever the
    audience.
    """
    if enforcement not in RULE_ENFORCED_MODES:
        return
    if predicate is None and applies_to == "ado_agent":
        return
    errors: list[FieldError] = []
    if not isinstance(predicate, dict) or not predicate:
        raise UnprocessableError(
            [FieldError("predicate", "enforced_requires_check",
                        f"a rule with enforcement {enforcement!r} must carry a check "
                        f"predicate {{kind, pattern}} — kinds: {sorted(RULE_CHECK_KINDS)}")]
        )
    kind = predicate.get("kind")
    if kind not in RULE_CHECK_KINDS:
        errors.append(FieldError("predicate", "invalid_check_kind",
                                 f"predicate.kind must be one of {sorted(RULE_CHECK_KINDS)}"))
    pattern = predicate.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        errors.append(FieldError("predicate", "missing_pattern",
                                 "predicate.pattern must be a non-empty regular expression"))
    else:
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(FieldError("predicate", "invalid_pattern",
                                     f"predicate.pattern does not compile: {exc}"))
    if kind == "required_trailer" and not predicate.get("trailer"):
        errors.append(FieldError("predicate", "missing_trailer",
                                 "a required_trailer check must name the trailer"))
    if errors:
        raise UnprocessableError(errors)


# --- lifecycle (REQ-543 / PI-440 / DEC-965) -----------------------------------

_DECISION_RE = re.compile(r"^DEC-\d{3,}$")
SOURCE_DECISION_RELATIONSHIP = "references"


def normalise_body(body: str) -> str:
    """The identity of a rule text: whitespace-collapsed, case-folded."""
    return " ".join((body or "").split()).casefold()


def find_duplicate(
    session: Session, body: str, engagement_id: str | None, *, exclude: str | None = None
) -> GovernanceRuleRow | None:
    """An active rule in the same scope whose text is the same rule (one rule per text)."""
    target = normalise_body(body)
    stmt = select(GovernanceRuleRow).where(
        GovernanceRuleRow.status == "active",
        GovernanceRuleRow.engagement_id.is_(None)
        if engagement_id is None
        else GovernanceRuleRow.engagement_id == engagement_id,
    )
    for row in session.scalars(stmt).all():
        if row.identifier != exclude and normalise_body(row.body) == target:
            return row
    return None


def _reject_duplicate(session: Session, body: str, engagement_id: str | None, *, exclude=None) -> None:
    dup = find_duplicate(session, body, engagement_id, exclude=exclude)
    if dup is not None:
        raise UnprocessableError(
            [FieldError("body", "duplicate_rule_text",
                        f"an active rule with this text already exists in scope: {dup.identifier} — "
                        "bind to it, or change its wording/meaning instead of adding a copy")]
        )


def _require_source_decision(session: Session, source_decision: str | None) -> str:
    """REQ-543: a new rule names the decision that made it, and that decision exists."""
    if not source_decision:
        raise UnprocessableError(
            [FieldError("source_decision", "source_decision_required",
                        "a governance rule names the decision (DEC-NNN) that ruled it")]
        )
    if not _DECISION_RE.match(source_decision):
        raise UnprocessableError(
            [FieldError("source_decision", "invalid_format", "must match ^DEC-\\d{3,}$")]
        )
    from crmbuilder_v2.access.repositories import decisions as _decisions

    _decisions.get(session, source_decision)  # NotFoundError if it does not exist
    return source_decision


def _link_source_decision(session: Session, rule_identifier: str, source_decision: str) -> None:
    from crmbuilder_v2.access.repositories import references as _references

    _references.upsert(
        session, source_type=_ENTITY_TYPE, source_id=rule_identifier,
        target_type="decision", target_id=source_decision,
        relationship=SOURCE_DECISION_RELATIONSHIP,
    )


def _profile_bindings(session: Session, rule_identifier: str) -> list[dict]:
    from crmbuilder_v2.access.repositories import references as _references

    return _references.list_references(
        session, target_type=_ENTITY_TYPE, target_id=rule_identifier,
        relationship_kind="agent_profile_governed_by_rule",
    )


def supersede(
    session: Session,
    identifier: str,
    *,
    body: str,
    source_decision: str,
    **fields,
) -> dict:
    """A change of meaning: a successor rule replaces ``identifier`` (REQ-543).

    The successor is a new rule (version 1) carrying the new text plus any other
    patched fields, linked ``successor --supersedes--> original``; every agent
    profile bound to the original is rebound to the successor; the original is
    retired, never deleted, so identifiers cited in decisions and lessons keep
    pointing at what they meant.
    """
    row = session.scalar(select(GovernanceRuleRow).where(GovernanceRuleRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    if row.status != "active":
        raise UnprocessableError(
            [FieldError("identifier", "not_active", f"{identifier} is {row.status!r}; only an active rule can be superseded")]
        )
    from crmbuilder_v2.access.repositories import references as _references

    successor = create(
        session,
        body=body,
        enforcement=fields.get("enforcement", row.enforcement),
        rule_type=fields.get("rule_type", row.rule_type),
        severity=fields.get("severity", row.severity),
        predicate=fields["predicate"] if "predicate" in fields else row.predicate,
        applies_to=fields.get("applies_to", row.applies_to),
        applies_when=fields.get("applies_when", row.applies_when),
        scope=fields.get("scope", "system" if row.engagement_id is None else row.engagement_id),
        source_decision=source_decision,
    )
    _references.create(
        session, source_type=_ENTITY_TYPE, source_id=successor["identifier"],
        target_type=_ENTITY_TYPE, target_id=identifier, relationship="supersedes",
    )
    for edge in _profile_bindings(session, identifier):
        _references.upsert(
            session, source_type="agent_profile", source_id=edge["source_id"],
            target_type=_ENTITY_TYPE, target_id=successor["identifier"],
            relationship="agent_profile_governed_by_rule",
        )
        _references.delete_by_id(session, edge["id"])
    before = _enrich(row)
    row.status = "retired"
    session.flush()
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=_enrich(row))
    successor["supersedes"] = [identifier]
    return successor


def record_enforcement_override(
    session: Session,
    rule_identifier: str,
    *,
    reason: str,
    command: str | None = None,
    session_ref: str | None = None,
    engagement_id: str | None = None,
) -> dict:
    """Log a waiver of an ``enforced_with_override`` rule (REQ-542 acceptance)."""
    rule = session.get(GovernanceRuleRow, rule_identifier)
    if rule is None:
        raise NotFoundError(_ENTITY_TYPE, rule_identifier)
    require_string(reason, field="reason")
    if rule.enforcement != "enforced_with_override":
        raise UnprocessableError(
            [FieldError("rule_identifier", "not_overridable",
                        f"{rule_identifier} is {rule.enforcement!r}; only an "
                        "enforced_with_override rule can be waved through")]
        )
    row = RuleEnforcementOverrideRow(
        engagement_id=engagement_id, rule_identifier=rule_identifier,
        reason=reason, command=command, session_ref=session_ref,
    )
    session.add(row)
    session.flush()
    return to_dict(row)


def list_enforcement_overrides(session: Session, rule_identifier: str) -> list[dict]:
    if session.get(GovernanceRuleRow, rule_identifier) is None:
        raise NotFoundError(_ENTITY_TYPE, rule_identifier)
    stmt = (
        select(RuleEnforcementOverrideRow)
        .where(RuleEnforcementOverrideRow.rule_identifier == rule_identifier)
        .order_by(RuleEnforcementOverrideRow.id)
    )
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(select(GovernanceRuleRow).where(GovernanceRuleRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return _enrich(row)


def list_all(
    session: Session,
    *,
    enforcement: str | None = None,
    status: str | None = None,
    scope: str | None = None,
    applies_to: str | None = None,
    applies_when: str | None = None,
) -> list[dict]:
    stmt = select(GovernanceRuleRow).order_by(GovernanceRuleRow.identifier)
    if enforcement is not None:
        stmt = stmt.where(GovernanceRuleRow.enforcement == enforcement)
    if status is not None:
        stmt = stmt.where(GovernanceRuleRow.status == status)
    if applies_to is not None:
        stmt = stmt.where(GovernanceRuleRow.applies_to == applies_to)
    if applies_when is not None:
        stmt = stmt.where(GovernanceRuleRow.applies_when == applies_when)
    if scope is not None:
        stmt = stmt.where(GovernanceRuleRow.engagement_id == resolve_scope(session, scope))
    return [_enrich(r) for r in session.scalars(stmt).all()]


# --------------------------------------------------------------------------
# Effective resolution (REQ-530): system defaults ∪ the engagement's overlay,
# most specific scope wins per rule_type.
# --------------------------------------------------------------------------


def is_visible(rule: dict, engagement_id: str | None) -> bool:
    """True if an active rule is in scope for ``engagement_id``.

    A system row (``engagement_id IS NULL``) is visible everywhere; an
    engagement row only to its own engagement.
    """
    if rule.get("status") != "active":
        return False
    row_engagement = rule.get("engagement_id")
    return row_engagement is None or row_engagement == engagement_id


def is_engagement_rule(rule: dict) -> bool:
    """True if a visible rule is an engagement overlay (not a system row)."""
    return rule.get("engagement_id") is not None


def resolve_overlay(visible_rules: list[dict]) -> list[dict]:
    """Apply engagement override + disable semantics to in-scope rules (WTK-001).

    ``visible_rules`` must already be scope-filtered and active-only (see
    :func:`is_visible`). Two overlay mechanisms shape the effective ruleset;
    both treat a system rule as the inheritable baseline:

    - **Override** (REQ-530). An engagement rule with the same non-null
      ``rule_type`` as a system rule wins: the system rule of that ``rule_type``
      is dropped and the engagement rule takes its place. Engagement rules with
      no ``rule_type`` (or a ``rule_type`` no system rule shares) add to the
      ruleset without displacing anything.
    - **Disable.** An engagement rule whose ``rule_type`` is
      ``"disable:<target>"`` suppresses a matching system rule and is itself
      never emitted. ``<target>`` matches a system rule by ``identifier``
      (``"disable:GVR-007"``) or by ``rule_type`` (``"disable:no_force_push"``).
      A disable that matches nothing is simply dropped (overlays are
      additive-by-intent).

    Every surviving engagement rule that displaced a system rule carries the
    displaced identifiers under ``"shadows"`` so callers can see the
    substitution. Order is preserved for every rule that survives, so
    downstream prompt/ruleset composition is stable.
    """
    disable_targets: set[str] = set()
    overlay_rule_types: set[str] = set()
    is_disable: dict[int, bool] = {}
    for rule in visible_rules:
        if not is_engagement_rule(rule):
            continue
        rule_type = rule.get("rule_type")
        if isinstance(rule_type, str) and rule_type.startswith(DISABLE_PREFIX):
            disable_targets.add(rule_type[len(DISABLE_PREFIX):].strip())
            is_disable[id(rule)] = True
        elif rule_type is not None:
            overlay_rule_types.add(rule_type)

    shadowed_by_type: dict[str, list[str]] = {}

    def _keep(rule: dict) -> bool:
        if is_engagement_rule(rule):
            return not is_disable.get(id(rule), False)
        rule_type = rule.get("rule_type")
        if rule_type is not None and rule_type in overlay_rule_types:
            shadowed_by_type.setdefault(rule_type, []).append(rule["identifier"])
            return False
        if rule["identifier"] in disable_targets:
            return False
        return not (rule_type is not None and rule_type in disable_targets)

    kept = [r for r in visible_rules if _keep(r)]
    for rule in kept:
        if is_engagement_rule(rule) and rule.get("rule_type") in shadowed_by_type:
            rule["shadows"] = list(shadowed_by_type[rule["rule_type"]])
    return kept


def list_effective(
    session: Session,
    *,
    engagement_id: str | None,
    enforcement: str | None = None,
    applies_to: str | None = None,
    applies_when: str | None = None,
) -> list[dict]:
    """The effective active ruleset for ``engagement_id`` (REQ-530).

    System defaults plus the engagement's overlay, with the overlay applied by
    :func:`resolve_overlay`. ``engagement_id=None`` yields the pure system
    baseline. Reads for an engagement the store does not know simply see the
    baseline (no overlay rows exist for it).
    """
    stmt = (
        select(GovernanceRuleRow)
        .where(GovernanceRuleRow.status == "active")
        .order_by(GovernanceRuleRow.identifier)
    )
    if enforcement is not None:
        stmt = stmt.where(GovernanceRuleRow.enforcement == enforcement)
    if applies_to is not None:
        stmt = stmt.where(GovernanceRuleRow.applies_to == applies_to)
    if applies_when is not None:
        stmt = stmt.where(GovernanceRuleRow.applies_when == applies_when)
    visible = [
        _enrich(r)
        for r in session.scalars(stmt).all()
        if r.engagement_id is None or r.engagement_id == engagement_id
    ]
    return resolve_overlay(visible)


def _active_system_rules(session: Session) -> list[GovernanceRuleRow]:
    stmt = (
        select(GovernanceRuleRow)
        .where(GovernanceRuleRow.status == "active")
        .where(GovernanceRuleRow.engagement_id.is_(None))
        .order_by(GovernanceRuleRow.identifier)
    )
    return list(session.scalars(stmt).all())


def _override_targets(session: Session, rule_type: str | None) -> list[GovernanceRuleRow]:
    """The active system rules an engagement rule with ``rule_type`` overrides.

    Raises ``demand_driven_keying`` (REQ-532) when a ``disable:<identifier>``
    directive names a system rule that has no ``rule_type`` yet.
    """
    if not rule_type:
        return []
    system_rules = _active_system_rules(session)
    if rule_type.startswith(DISABLE_PREFIX):
        target = rule_type[len(DISABLE_PREFIX):].strip()
        by_id = [r for r in system_rules if r.identifier == target]
        if by_id and by_id[0].rule_type is None:
            raise UnprocessableError(
                [
                    FieldError(
                        "rule_type",
                        "demand_driven_keying",
                        f"system rule {target} has no rule_type; assign one to the "
                        "default first (PATCH rule_type), then override it "
                        "(REQ-532)",
                    )
                ]
            )
        return by_id or [r for r in system_rules if r.rule_type == target]
    return [r for r in system_rules if r.rule_type == rule_type]


def _record_supersedes(session: Session, override_id: str, targets) -> list[str]:
    """Record one ``supersedes`` edge per shadowed/disabled system rule (REQ-531)."""
    recorded: list[str] = []
    for target in targets:
        references.create(
            session,
            source_type=_ENTITY_TYPE,
            source_id=override_id,
            target_type=_ENTITY_TYPE,
            target_id=target.identifier,
            relationship=SUPERSEDES,
        )
        recorded.append(target.identifier)
    return recorded


def _new_row(identifier, *, rule_type, enforcement, severity, body, predicate,
             version, status, engagement_id, applies_to, applies_when) -> GovernanceRuleRow:
    return GovernanceRuleRow(
        identifier=identifier,
        engagement_id=engagement_id,
        rule_type=rule_type,
        enforcement=enforcement,
        severity=severity,
        body=body,
        predicate=predicate,
        version=version,
        status=status,
        applies_to=applies_to,
        applies_when=applies_when,
    )


def _insert_with_autoassign(session: Session, **fields) -> GovernanceRuleRow:
    # REQ-446 / PI-384: serialize per-prefix assignment (PG advisory lock;
    # SQLite no-op) so concurrent writers don't race the read-then-probe loop.
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = compute_next_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, **fields)
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = _increment(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        f"could not assign a unique governance_rule identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    body: str,
    enforcement: str,
    rule_type: str | None = None,
    severity: str | None = None,
    predicate: dict | None = None,
    version: int = 1,
    status: str = "active",
    scope: str | None = None,
    applies_to: str = "all",
    applies_when: str = "always",
    source_decision: str | None = None,
    require_source_decision: bool = False,
) -> dict:
    require_string(body, field="body")
    _require_vocab("enforcement", enforcement, RULE_ENFORCEMENT_MODES)
    _require_vocab("status", status, REGISTRY_STATUSES)
    _require_vocab("applies_to", applies_to, RULE_AUDIENCES)
    _require_vocab("applies_when", applies_when, RULE_MOMENTS)
    if severity is not None:
        _require_vocab("severity", severity, RULE_SEVERITIES)
    validate_predicate(enforcement, predicate, applies_to)
    if require_source_decision or source_decision:
        source_decision = _require_source_decision(session, source_decision)
    engagement_id = resolve_scope(session, scope)
    if status == "active":
        _reject_duplicate(session, body, engagement_id)
    # An engagement override must name a keyed default (REQ-532) — resolve its
    # targets before the insert so a rejected override leaves no row behind.
    targets = _override_targets(session, rule_type) if engagement_id is not None else []
    fields = {
        "rule_type": rule_type,
        "enforcement": enforcement,
        "severity": severity,
        "body": body,
        "predicate": predicate,
        "version": version,
        "status": status,
        "engagement_id": engagement_id,
        "applies_to": applies_to,
        "applies_when": applies_when,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **fields)
    else:
        _require_identifier_format(identifier)
        if session.get(GovernanceRuleRow, identifier) is not None:
            raise ConflictError(f"governance_rule {identifier!r} already exists")
        row = _new_row(identifier, **fields)
        session.add(row)
        session.flush()
    supersedes = _record_supersedes(session, row.identifier, targets)
    after = _enrich(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=row.identifier,
         operation="insert", before=None, after=after)
    if source_decision:
        _link_source_decision(session, row.identifier, source_decision)
        after["source_decision"] = source_decision
    if supersedes:
        after["supersedes"] = supersedes
    return after


def update(
    session: Session,
    identifier: str,
    *,
    scope: str | None = None,
    change: str | None = None,
    source_decision: str | None = None,
    **fields,
) -> dict:
    """Patch a rule. A ``body`` change must say what kind it is (REQ-543):
    ``wording`` bumps the version in place; ``meaning`` creates a successor
    via :func:`supersede` and needs the ``source_decision`` that ruled it."""
    row = session.scalar(select(GovernanceRuleRow).where(GovernanceRuleRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    if change is not None:
        _require_vocab("change", change, RULE_CHANGE_KINDS)
    body_changes = "body" in fields and normalise_body(fields["body"]) != normalise_body(row.body)
    if body_changes and change is None:
        raise UnprocessableError(
            [FieldError("change", "change_kind_required",
                        "a change to the rule text must say whether it is 'wording' "
                        "(version bumps in place) or 'meaning' (a successor supersedes this rule)")]
        )
    if body_changes and change == "meaning":
        new_body = fields.pop("body")
        return supersede(
            session, identifier, body=new_body,
            source_decision=_require_source_decision(session, source_decision),
            **({"scope": scope} if scope is not None else {}), **fields,
        )
    if body_changes:
        _reject_duplicate(session, fields["body"], row.engagement_id, exclude=identifier)
        fields["version"] = int(fields.get("version") or row.version or 1) + 1
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValidationError(
            [FieldError("fields", "unknown_field", f"unknown updatable fields: {sorted(unknown)}")]
        )
    if "enforcement" in fields:
        _require_vocab("enforcement", fields["enforcement"], RULE_ENFORCEMENT_MODES)
    if "status" in fields:
        _require_vocab("status", fields["status"], REGISTRY_STATUSES)
    if "applies_to" in fields:
        _require_vocab("applies_to", fields["applies_to"], RULE_AUDIENCES)
    if "applies_when" in fields:
        _require_vocab("applies_when", fields["applies_when"], RULE_MOMENTS)
    if fields.get("severity") is not None:
        _require_vocab("severity", fields["severity"], RULE_SEVERITIES)
    if "enforcement" in fields or "predicate" in fields or "applies_to" in fields:
        validate_predicate(
            fields.get("enforcement", row.enforcement),
            fields["predicate"] if "predicate" in fields else row.predicate,
            fields.get("applies_to", row.applies_to),
        )
    before = _enrich(row)
    for k, v in fields.items():
        setattr(row, k, v)
    if scope is not None:
        row.engagement_id = resolve_scope(session, scope)
    session.flush()
    after = _enrich(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def delete(session: Session, identifier: str) -> dict:
    row = session.scalar(select(GovernanceRuleRow).where(GovernanceRuleRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = _enrich(row)
    session.delete(row)
    session.flush()
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="delete", before=before, after=None)
    return before
