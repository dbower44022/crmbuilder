"""Per-(release, area) implementation + testable spec store — the matrix back
half's design artifact (PI-244 / PRJ-041, REQ-295).

The area's Architect authors an implementation spec (the Developer builds to it)
and a testable spec (the Tester implements blind). It is **append-only /
versioned**: ``author_spec`` writes the next ``spec_version`` for a ``(release,
area)``, recording the ``change_reason`` + ``trigger_kind`` (+ optional finding)
that caused the revision, so the chain is a logbook of what changed and why. The
**current** spec is the highest version; older rows are never erased. A content
``fingerprint`` over the two specs drives the Design-Review freshness gate (a new
revision voids the prior sign-off). Authored judgment, not a recomputable
derivation — so, unlike ``release_change_sets``, it keeps history.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import AreaSpec, Release
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import AREA_SPEC_TRIGGER_KINDS


def _require_release(session: Session, release_identifier: str) -> None:
    row = session.scalars(
        select(Release).where(Release.release_identifier == release_identifier)
    ).first()
    if row is None:
        raise NotFoundError("release", release_identifier)


def fingerprint(implementation: str, testable: str) -> str:
    """A stable content hash of the two specs (the freshness-gate key)."""
    blob = json.dumps(
        {"implementation": implementation, "testable": testable},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _next_version(session: Session, release_identifier: str, area: str) -> int:
    current = session.scalar(
        select(func.max(AreaSpec.spec_version)).where(
            AreaSpec.release_identifier == release_identifier,
            AreaSpec.area == area,
        )
    )
    return (current or 0) + 1


def author_spec(
    session: Session,
    release_identifier: str,
    area: str,
    *,
    implementation: str,
    testable: str,
    change_reason: str = "",
    trigger_kind: str = "initial",
    trigger_finding_identifier: str | None = None,
) -> dict:
    """Append the next version of an area's spec (never overwrites a prior one)."""
    _require_release(session, release_identifier)
    area = gov.require_nonempty(area, field="area")
    implementation = gov.require_nonempty(implementation, field="implementation")
    testable = gov.require_nonempty(testable, field="testable")
    if trigger_kind not in AREA_SPEC_TRIGGER_KINDS:
        raise UnprocessableError(
            [FieldError("trigger_kind", "invalid",
                        f"{trigger_kind!r} is not one of {sorted(AREA_SPEC_TRIGGER_KINDS)}")]
        )
    row = AreaSpec(
        release_identifier=release_identifier,
        area=area,
        spec_version=_next_version(session, release_identifier, area),
        spec_implementation=implementation,
        spec_testable=testable,
        spec_change_reason=change_reason or "",
        spec_trigger_kind=trigger_kind,
        spec_trigger_finding_identifier=trigger_finding_identifier or None,
        spec_fingerprint=fingerprint(implementation, testable),
    )
    session.add(row)
    session.flush()
    return to_dict(row)


def current_spec(
    session: Session, release_identifier: str, area: str
) -> dict | None:
    """The latest (highest-version) spec for an area, or ``None``."""
    _require_release(session, release_identifier)
    row = session.scalars(
        select(AreaSpec)
        .where(
            AreaSpec.release_identifier == release_identifier,
            AreaSpec.area == area,
        )
        .order_by(AreaSpec.spec_version.desc())
    ).first()
    return to_dict(row) if row is not None else None


def current_specs(session: Session, release_identifier: str) -> list[dict]:
    """The current (latest) spec for every area the release has one — the set the
    Design Review consolidates over."""
    _require_release(session, release_identifier)
    rows = session.scalars(
        select(AreaSpec).where(
            AreaSpec.release_identifier == release_identifier
        )
    ).all()
    latest: dict[str, dict] = {}
    for r in rows:
        d = to_dict(r)
        keep = latest.get(d["area"])
        if keep is None or d["spec_version"] > keep["spec_version"]:
            latest[d["area"]] = d
    return [latest[a] for a in sorted(latest)]


def spec_history(
    session: Session, release_identifier: str, area: str
) -> list[dict]:
    """An area's full revision chain, oldest → newest (the what-changed-and-why log)."""
    _require_release(session, release_identifier)
    rows = session.scalars(
        select(AreaSpec)
        .where(
            AreaSpec.release_identifier == release_identifier,
            AreaSpec.area == area,
        )
        .order_by(AreaSpec.spec_version.asc())
    ).all()
    return [to_dict(r) for r in rows]
