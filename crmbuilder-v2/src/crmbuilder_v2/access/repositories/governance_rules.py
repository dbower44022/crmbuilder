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
from crmbuilder_v2.access.models import GovernanceRuleRow
from crmbuilder_v2.access.repositories import references
from crmbuilder_v2.access.repositories._registry import resolve_scope, with_scope
from crmbuilder_v2.access.vocab import (
    REGISTRY_STATUSES,
    RULE_AUDIENCES,
    RULE_ENFORCEMENT_MODES,
    RULE_MOMENTS,
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
) -> dict:
    require_string(body, field="body")
    _require_vocab("enforcement", enforcement, RULE_ENFORCEMENT_MODES)
    _require_vocab("status", status, REGISTRY_STATUSES)
    _require_vocab("applies_to", applies_to, RULE_AUDIENCES)
    _require_vocab("applies_when", applies_when, RULE_MOMENTS)
    engagement_id = resolve_scope(session, scope)
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
    if supersedes:
        after["supersedes"] = supersedes
    return after


def update(session: Session, identifier: str, *, scope: str | None = None, **fields) -> dict:
    row = session.scalar(select(GovernanceRuleRow).where(GovernanceRuleRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
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
