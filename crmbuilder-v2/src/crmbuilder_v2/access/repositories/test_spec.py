"""Test Spec repository — PI-004 cohort closer (v0.5+).

Per ``methodology-schema-specs/test_spec.md`` v1.0. The eight standard
module-level functions back the ``/test-specs`` REST endpoints and the
desktop panel, plus a ninth :func:`record_run` convenience helper:

* :func:`list_test_specs` / :func:`get_test_spec` — reads.
* :func:`create_test_spec` — insert with server-side identifier
  auto-assignment (collision-safe retry, per spec acceptance criterion 9).
* :func:`update_test_spec` — full replace (PUT).
* :func:`patch_test_spec` — partial update (PATCH).
* :func:`delete_test_spec` / :func:`restore_test_spec` — soft-delete
  round-trip.
* :func:`next_test_spec_identifier` — the ``TST-NNN`` allocator helper.
* :func:`record_run` — atomic ``last_run_outcome`` + ``last_run_at`` +
  ``last_run_notes`` update; thin shape for automation callers per
  spec §3.8.1 open question.

Validation posture (``test_spec.md`` §3.5): identifier-format,
case-insensitive global name-uniqueness, status-enum, outcome-enum,
and PUT identifier/path mismatches raise :class:`UnprocessableError`
(HTTP 422); disallowed status transitions raise
:class:`StatusTransitionError` (HTTP 422 with the dedicated body
shape — methodology-lifecycle field only). Outcome transitions are
UNRESTRICTED per §3.4.2 — no transition map, no transition error.
Missing records raise :class:`NotFoundError` (404); an explicit-
identifier collision on create raises :class:`ConflictError` (409).

**Dual-axis state per §3.4.3.** Two enum fields on the row:

* ``test_spec_status`` — methodology lifecycle, restricted transitions
  per :data:`TEST_SPEC_STATUS_TRANSITIONS` (propose-verify gate).
* ``test_spec_last_run_outcome`` — execution outcome, unrestricted
  transitions per §3.4.2 (observational, not decisional).

The two move on independent cadences. The §3.4.4 cross-field invariant
binds them: ``last_run_at`` must be populated whenever outcome is one
of ``passing`` / ``failing`` / ``skipped``, cleared on move back to
``not_run``. Enforced exclusively at this layer (not in SQL CHECK,
since SQLite's conditional-CHECK story is brittle and the access-
layer surfaces richer error detail).

The repository mirrors ``entity.py`` exactly with test_spec-specific
adjustments:

* **Outcome-enum validation** parallels status-enum validation
  against the four-value :data:`TEST_SPEC_RUN_OUTCOMES` set.
* **Cross-field invariant on outcome / last_run_at / last_run_notes**
  per §3.4.4 — :func:`_apply_outcome_invariant` clears the run-only
  fields on transition to ``not_run`` and auto-sets ``last_run_at``
  on transition to a run state.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import TestSpec
from crmbuilder_v2.access.repositories import _rejection
from crmbuilder_v2.access.vocab import (
    TEST_SPEC_RUN_OUTCOMES,
    TEST_SPEC_STATUS_TRANSITIONS,
    TEST_SPEC_STATUSES,
)

_ENTITY_TYPE = "test_spec"
_IDENTIFIER_PREFIX = "TST"
_IDENTIFIER_RE = re.compile(r"^TST-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign`. Far above any plausible concurrent
# burst; exhausting it indicates a genuine fault, surfaced as a 409.
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_test_spec`. The identifier and the
# timestamps are not patchable.
_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "description",
        "setup",
        "steps",
        "expected",
        "notes",
        "status",
        "last_run_outcome",
        "last_run_at",
        "last_run_notes",
    }
)

# Outcomes that require ``last_run_at`` to be populated per §3.4.4.
# ``not_run`` is the only outcome that REJECTS ``last_run_at``.
_RUN_OUTCOMES = frozenset({"passing", "failing", "skipped"})


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "test_spec_identifier",
                    "invalid_format",
                    r"must match ^TST-\d{3}$ (e.g. TST-001)",
                )
            ]
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnprocessableError(
            [FieldError(field, "missing_or_empty", "must be a non-empty string")]
        )
    return value.strip()


def _require_status(status: object) -> str:
    if status not in TEST_SPEC_STATUSES:
        raise UnprocessableError(
            [
                FieldError(
                    "test_spec_status",
                    "invalid_value",
                    f"must be one of {sorted(TEST_SPEC_STATUSES)}",
                )
            ]
        )
    return status  # type: ignore[return-value]


def _require_outcome(outcome: object) -> str:
    """Validate ``test_spec_last_run_outcome`` against the four-value enum.

    Unlike :func:`_require_status` there is no corresponding transition
    check — outcomes are observational per §3.4.2 and transitions are
    unrestricted. The cross-field invariant on ``last_run_at`` is the
    only post-write rule on the outcome axis; it lives in
    :func:`_apply_outcome_invariant`.
    """
    if outcome not in TEST_SPEC_RUN_OUTCOMES:
        raise UnprocessableError(
            [
                FieldError(
                    "test_spec_last_run_outcome",
                    "invalid_value",
                    f"must be one of {sorted(TEST_SPEC_RUN_OUTCOMES)}",
                )
            ]
        )
    return outcome  # type: ignore[return-value]


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move.

    Methodology-lifecycle field only. Outcome transitions are
    unrestricted per §3.4.2 — no equivalent helper exists for
    ``test_spec_last_run_outcome``.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set per
    :data:`TEST_SPEC_STATUS_TRANSITIONS`. The propose-verify gate
    (DEC-047) means no value lists ``candidate`` as a successor.
    """
    if requested == current:
        return
    if requested not in TEST_SPEC_STATUS_TRANSITIONS.get(
        current, frozenset()
    ):
        raise StatusTransitionError(current, requested)


def _apply_outcome_invariant(
    row: TestSpec,
    *,
    requested_outcome: str,
    requested_last_run_at: datetime | None,
    last_run_at_supplied: bool,
) -> None:
    """Enforce the §3.4.4 cross-field invariant on outcome / last_run_at.

    ``last_run_at_supplied`` distinguishes an explicit ``None`` (client
    asked to clear) from an omitted value (client did not touch). The
    PATCH router computes this from
    ``"test_spec_last_run_at" in provided`` (where ``provided`` is
    ``body.model_dump(exclude_unset=True)``); POST uses the same
    pattern against the JSON body.

    Behavior matrix:

    * Outcome → ``not_run``: clear ``test_spec_last_run_at`` AND
      ``test_spec_last_run_notes`` regardless of what the client
      supplied. This matches §3.4.4's "cleared on move back to
      ``not_run``" rule.
    * Outcome → run state (passing/failing/skipped):

      - If the client supplied ``last_run_at`` explicitly as ``None``
        while requesting a run state, raise 422 (the invariant rejects
        an explicit null in a run state).
      - If the client supplied ``last_run_at`` non-null, honor it.
      - If the client did not supply ``last_run_at`` AND the row's
        existing value is null, server-default to ``datetime.now(UTC)``.
      - If the client did not supply ``last_run_at`` AND the row
        already has a non-null value (e.g. PATCH that only changes
        outcome), preserve the existing value.

    The function mutates the row in place. Caller is responsible for
    ``session.flush()``.
    """
    if requested_outcome == "not_run":
        row.test_spec_last_run_outcome = "not_run"
        row.test_spec_last_run_at = None
        row.test_spec_last_run_notes = None
        return
    if requested_outcome in _RUN_OUTCOMES:
        row.test_spec_last_run_outcome = requested_outcome
        if last_run_at_supplied and requested_last_run_at is None:
            raise UnprocessableError(
                [
                    FieldError(
                        "test_spec_last_run_at",
                        "required_when_outcome_is_run_state",
                        "test_spec_last_run_at cannot be null when "
                        "outcome is passing/failing/skipped",
                    )
                ]
            )
        if requested_last_run_at is not None:
            row.test_spec_last_run_at = requested_last_run_at
        elif row.test_spec_last_run_at is None:
            row.test_spec_last_run_at = datetime.now(UTC)


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    """Reject a case-insensitive ``test_spec_name`` collision.

    Only non-soft-deleted rows participate in the uniqueness check, per
    ``test_spec.md`` §3.2.1. Uniqueness is engagement-global.
    """
    stmt = select(TestSpec).where(
        func.lower(TestSpec.test_spec_name) == name.lower(),
        TestSpec.test_spec_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(TestSpec.test_spec_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "test_spec_name",
                    "duplicate",
                    f"a test_spec named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> TestSpec:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = get_by_identifier(session, TestSpec, TestSpec.test_spec_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    """Return the next ``TST-NNN`` after ``identifier`` (collision retry)."""
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_test_specs(
    session: Session, *, include_deleted: bool = False
) -> list[dict]:
    """Return all test_specs ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    """
    stmt = select(TestSpec).order_by(TestSpec.test_spec_identifier)
    if not include_deleted:
        stmt = stmt.where(TestSpec.test_spec_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_test_spec(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single test_spec by identifier, or ``None`` if not visible.

    A soft-deleted row reads as ``None`` unless ``include_deleted`` is
    True — the REST layer translates ``None`` to HTTP 404.
    """
    row = get_by_identifier(session, TestSpec, TestSpec.test_spec_identifier, identifier)
    if row is None:
        return None
    if row.test_spec_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_test_spec_identifier(session: Session) -> str:
    """Return the next available ``TST-NNN`` identifier.

    Scans every row including soft-deleted ones so a retired identifier
    is never reused.
    """
    identifiers = session.scalars(
        select(TestSpec.test_spec_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_test_spec_row(
    identifier: str,
    name: str,
    description: str,
    steps: str,
    expected: str,
    setup: str | None,
    notes: str | None,
    status: str,
    last_run_outcome: str,
    last_run_at: datetime | None,
    last_run_notes: str | None,
) -> TestSpec:
    return TestSpec(
        test_spec_identifier=identifier,
        test_spec_name=name,
        test_spec_description=description,
        test_spec_steps=steps,
        test_spec_expected=expected,
        test_spec_setup=setup,
        test_spec_notes=notes,
        test_spec_status=status,
        test_spec_last_run_outcome=last_run_outcome,
        test_spec_last_run_at=last_run_at,
        test_spec_last_run_notes=last_run_notes,
    )


def _insert_with_autoassign(
    session: Session,
    name: str,
    description: str,
    steps: str,
    expected: str,
    setup: str | None,
    notes: str | None,
    status: str,
    last_run_outcome: str,
    last_run_at: datetime | None,
    last_run_notes: str | None,
) -> TestSpec:
    """Insert a test_spec with a server-assigned identifier, collision-safe.

    Computes the next ``TST-NNN`` and attempts the INSERT inside a
    SAVEPOINT. A concurrent transaction that committed the same
    identifier first raises ``IntegrityError`` on flush; the savepoint
    rolls that INSERT back, the candidate is incremented, and the
    attempt repeats. Satisfies spec acceptance criterion 9 — two
    concurrent POSTs never share an identifier.
    """
    candidate = next_test_spec_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_test_spec_row(
            candidate,
            name,
            description,
            steps,
            expected,
            setup,
            notes,
            status,
            last_run_outcome,
            last_run_at,
            last_run_notes,
        )
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
        "could not assign a unique test_spec identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_test_spec(
    session: Session,
    *,
    name: str,
    description: str,
    steps: str,
    expected: str,
    setup: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    last_run_outcome: str | None = None,
    last_run_at: datetime | None = None,
    last_run_notes: str | None = None,
    identifier: str | None = None,
    last_run_at_supplied: bool = False,
) -> dict:
    """Create a test_spec.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^TST-\\d{3}$`` and not already exist.
    ``status`` defaults to ``candidate`` when None per spec §3.5.3;
    ``last_run_outcome`` defaults to ``not_run`` when None.

    The §3.4.4 cross-field invariant fires post-insert: a POST with
    ``last_run_outcome`` in ``{passing, failing, skipped}`` requires
    ``last_run_at`` (server-defaults to ``now()`` if omitted; raises if
    the client supplied ``last_run_at=None`` explicitly — the API layer
    signals "explicitly null" via ``last_run_at_supplied=True``).
    """
    name = _require_nonempty(name, field="test_spec_name")
    description = _require_nonempty(
        description, field="test_spec_description"
    )
    steps = _require_nonempty(steps, field="test_spec_steps")
    expected = _require_nonempty(expected, field="test_spec_expected")
    if status is None:
        status = "candidate"
    _require_status(status)
    if last_run_outcome is None:
        last_run_outcome = "not_run"
    _require_outcome(last_run_outcome)
    _reject_duplicate_name(session, name)

    if identifier is None:
        row = _insert_with_autoassign(
            session,
            name,
            description,
            steps,
            expected,
            setup,
            notes,
            status,
            last_run_outcome,
            last_run_at,
            last_run_notes,
        )
    else:
        _require_identifier_format(identifier)
        if get_by_identifier(session, TestSpec, TestSpec.test_spec_identifier, identifier) is not None:
            raise ConflictError(
                f"test_spec {identifier!r} already exists"
            )
        row = _new_test_spec_row(
            identifier,
            name,
            description,
            steps,
            expected,
            setup,
            notes,
            status,
            last_run_outcome,
            last_run_at,
            last_run_notes,
        )
        session.add(row)
        session.flush()

    # §3.4.4 cross-field invariant. Applied after the row exists so the
    # helper can clear / auto-set the last_run_at field consistently.
    _apply_outcome_invariant(
        row,
        requested_outcome=last_run_outcome,
        requested_last_run_at=last_run_at,
        last_run_at_supplied=last_run_at_supplied,
    )
    session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.test_spec_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_test_spec(
    session: Session,
    identifier: str,
    *,
    test_spec_identifier: str | None = None,
    name: str | None = None,
    description: str | None = None,
    steps: str | None = None,
    expected: str | None = None,
    setup: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    last_run_outcome: str | None = None,
    last_run_at: datetime | None = None,
    last_run_notes: str | None = None,
    last_run_at_supplied: bool = False,
    rejected_by_decision: str | None = None,
) -> dict:
    """Full-replace update (PUT).

    ``test_spec_identifier`` (the identifier echoed in the request
    body) must match the path ``identifier`` — a mismatch raises
    :class:`UnprocessableError`. ``name`` / ``description`` / ``steps``
    / ``expected`` / ``status`` / ``last_run_outcome`` are required (a
    full replace cannot blank them); ``setup`` / ``notes`` /
    ``last_run_notes`` are replaced wholesale (``None`` clears). A
    ``status`` change is transition-validated. The §3.4.4 cross-field
    invariant fires against the post-write outcome value.
    """
    row = _get_row(session, identifier)
    if (
        test_spec_identifier is not None
        and test_spec_identifier != identifier
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "test_spec_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="test_spec_name")
    description = _require_nonempty(
        description, field="test_spec_description"
    )
    steps = _require_nonempty(steps, field="test_spec_steps")
    expected = _require_nonempty(expected, field="test_spec_expected")
    if status is None or status not in TEST_SPEC_STATUSES:
        _require_status(status)
    if (
        last_run_outcome is None
        or last_run_outcome not in TEST_SPEC_RUN_OUTCOMES
    ):
        _require_outcome(last_run_outcome)
    if name.lower() != row.test_spec_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)
    if status != row.test_spec_status:
        _check_transition(row.test_spec_status, status)
        if status == "rejected":
            _rejection.enforce_rejected_status(
                session,
                source_type=_ENTITY_TYPE,
                source_identifier=identifier,
                decision_identifier=rejected_by_decision,
            )
            rejected_by_decision = None
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=status,
        )

    row.test_spec_name = name
    row.test_spec_description = description
    row.test_spec_steps = steps
    row.test_spec_expected = expected
    row.test_spec_setup = setup
    row.test_spec_notes = notes
    row.test_spec_status = status
    row.test_spec_last_run_notes = last_run_notes
    # Apply the §3.4.4 invariant — sets/clears outcome + last_run_at
    # consistently. last_run_notes is overwritten above; the invariant
    # also clears it on transition to not_run.
    _apply_outcome_invariant(
        row,
        requested_outcome=last_run_outcome,
        requested_last_run_at=last_run_at,
        last_run_at_supplied=last_run_at_supplied,
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
    return after


def patch_test_spec(
    session: Session, identifier: str, **fields
) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``description``, ``setup``, ``steps``,
    ``expected``, ``notes``, ``status``, ``last_run_outcome``,
    ``last_run_at``, ``last_run_notes``. A ``status`` change is
    transition-validated; the §3.4.4 cross-field invariant fires
    against the post-merge outcome value.

    The router passes the supplied-vs-omitted signal for the
    ``last_run_at`` field via the conventional pattern ``"last_run_at"
    in fields`` — a PATCH that explicitly clears ``last_run_at`` to
    null while leaving outcome as a run state raises 422.

    A move to ``rejected`` requires either the ``rejected_by_decision``
    key (atomic edge + flip, PI-153 §3.4) or a pre-existing
    ``rejected_by_decision`` edge.
    """
    rejected_by_decision = fields.pop("rejected_by_decision", None)
    unknown = set(fields) - _PATCHABLE_FIELDS
    if unknown:
        raise UnprocessableError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown patchable fields: {sorted(unknown)}",
                )
            ]
        )
    row = _get_row(session, identifier)
    before = to_dict(row)

    if "name" in fields:
        name = _require_nonempty(fields["name"], field="test_spec_name")
        if name.lower() != row.test_spec_name.lower():
            _reject_duplicate_name(
                session, name, exclude_identifier=identifier
            )
        row.test_spec_name = name
    if "description" in fields:
        row.test_spec_description = _require_nonempty(
            fields["description"], field="test_spec_description"
        )
    if "setup" in fields:
        row.test_spec_setup = fields["setup"]
    if "steps" in fields:
        row.test_spec_steps = _require_nonempty(
            fields["steps"], field="test_spec_steps"
        )
    if "expected" in fields:
        row.test_spec_expected = _require_nonempty(
            fields["expected"], field="test_spec_expected"
        )
    if "notes" in fields:
        row.test_spec_notes = fields["notes"]

    # Status transition (against the pre-write current status).
    if "status" in fields:
        status_after = _require_status(fields["status"])
        if status_after != row.test_spec_status:
            _check_transition(row.test_spec_status, status_after)
            if status_after == "rejected":
                _rejection.enforce_rejected_status(
                    session,
                    source_type=_ENTITY_TYPE,
                    source_identifier=identifier,
                    decision_identifier=rejected_by_decision,
                )
                rejected_by_decision = None
        row.test_spec_status = status_after
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.test_spec_status,
        )

    # Apply last_run_notes verbatim if supplied. The invariant helper
    # may clear it on transition to not_run; that runs after.
    if "last_run_notes" in fields:
        row.test_spec_last_run_notes = fields["last_run_notes"]

    # §3.4.4 cross-field invariant. The outcome may have been omitted
    # by the patch (in which case the existing row value is preserved
    # along with last_run_at), supplied as a run state (auto-set
    # last_run_at if needed), or supplied as not_run (clear both
    # last_run_at and last_run_notes).
    if "last_run_outcome" in fields:
        outcome_after = _require_outcome(fields["last_run_outcome"])
        _apply_outcome_invariant(
            row,
            requested_outcome=outcome_after,
            requested_last_run_at=fields.get("last_run_at"),
            last_run_at_supplied=("last_run_at" in fields),
        )
    elif "last_run_at" in fields:
        # Outcome unchanged but last_run_at supplied: validate against
        # the row's current outcome. If outcome is a run state and the
        # patch sets last_run_at to null, the invariant rejects.
        _apply_outcome_invariant(
            row,
            requested_outcome=row.test_spec_last_run_outcome,
            requested_last_run_at=fields["last_run_at"],
            last_run_at_supplied=True,
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
    return after


def delete_test_spec(session: Session, identifier: str) -> dict:
    """Soft-delete: set ``test_spec_deleted_at`` to now.

    Idempotent — DELETE on an already-soft-deleted row is a no-op that
    returns the record unchanged. Outbound references (all three
    kinds) are NOT cascade-deleted per spec §3.4.6: this function
    never touches the ``refs`` table.
    """
    row = _get_row(session, identifier)
    if row.test_spec_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.test_spec_deleted_at = datetime.now(UTC)
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
    return after


def restore_test_spec(session: Session, identifier: str) -> dict:
    """Clear ``test_spec_deleted_at``. Raises if the row is not soft-deleted."""
    row = _get_row(session, identifier)
    if row.test_spec_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "test_spec_deleted_at",
                    "not_deleted",
                    "test_spec is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.test_spec_deleted_at = None
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
    return after


def record_run(
    session: Session,
    identifier: str,
    *,
    outcome: str,
    notes: str | None = None,
    at: datetime | None = None,
) -> dict:
    """Atomic update of ``last_run_outcome`` + ``last_run_at`` + ``last_run_notes``.

    Per spec §3.8.1's open question — ship this in v0.5+ (resolves the
    open question in the affirmative). The PATCH endpoint can do the
    same three-field update; this dedicated path surfaces a clearer
    intent for automation callers and aligns with the methodology-
    vs-execution principle (§3.4.3 — outcome moves on its own cadence).

    Behavior:

    * ``outcome`` is required and must be one of the four enum values.
    * ``at`` is optional — server-defaults to ``datetime.now(UTC)`` per
      the §3.4.4 invariant when omitted (and outcome is a run state).
    * ``notes`` is optional. When ``outcome`` is ``not_run`` the
      invariant helper clears ``last_run_notes`` so the ``notes`` arg
      is effectively ignored — this is intentional per §3.4.4's "cleared
      on move back to ``not_run``" rule.

    The change_log emits a single ``update`` event for the row.
    """
    row = _get_row(session, identifier)
    before = to_dict(row)
    _require_outcome(outcome)
    # ``at`` is signalled as supplied only when non-None; an automation
    # caller that wants to reject a null last_run_at would use PATCH
    # directly. The helper signature here trades explicit-null
    # signalling for simplicity, which matches §3.8.1's "thinner
    # convenience shape" framing.
    _apply_outcome_invariant(
        row,
        requested_outcome=outcome,
        requested_last_run_at=at,
        last_run_at_supplied=(at is not None),
    )
    if outcome != "not_run":
        row.test_spec_last_run_notes = notes
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
    return after
