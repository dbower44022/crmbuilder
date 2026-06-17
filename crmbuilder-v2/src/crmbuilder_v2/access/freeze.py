"""Freeze enforcement — derived frozen-ness over the release pipeline (PI-216).

PRJ-031, §9A (DEC-488…493, REQ-224…229). PI-205 owns the freeze *transition* and
the ``release_frozen_at`` stamp; this module owns the *enforcement of derived
frozen-ness on other records*. Nothing is stored — a record's freeze band is
computed from its release's status + the membership edges (FE-2).

Bands (FE-2):
  * ``open``         — pre-freeze; edits free.
  * ``amend_window`` — frozen, but a governed amend is allowed (the
    ``[freeze, planned-completely)`` window = reconciliation + architecture_planning).
  * ``locked``       — past planned-completely; a demand change needs a new
    release (RW1).
``shipped`` / ``cancelled`` / ``superseded`` are terminal/abandoned and not gated.
"""

from __future__ import annotations

from sqlalchemy import select

from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import RELEASE_LANE_STATUSES

OPEN_STATUSES = frozenset({"preliminary_planning", "development_planning"})
AMEND_WINDOW_STATUSES = frozenset({"reconciliation", "architecture_planning"})
# past planned-completely: ready + the four lane states.
LOCKED_STATUSES = frozenset({"ready"}) | RELEASE_LANE_STATUSES

# Most-restrictive ordering for picking a requirement's effective band.
_BAND_RANK = {"open": 0, "amend_window": 1, "locked": 2}


def band_for_status(release_status: str) -> str | None:
    """Map a release status to its enforcement band, or ``None`` if not gated."""
    if release_status in OPEN_STATUSES:
        return "open"
    if release_status in AMEND_WINDOW_STATUSES:
        return "amend_window"
    if release_status in LOCKED_STATUSES:
        return "locked"
    return None  # shipped / cancelled / superseded — terminal, not gated.


def _release_status(session, release_id: str) -> str | None:
    # Release has a composite PK (engagement_id, release_identifier), so a
    # filtered query is used (the engagement read-filter scopes it to the active
    # engagement) rather than session.get().
    row = session.scalars(
        select(Release).where(Release.release_identifier == release_id)
    ).first()
    return row.release_status if row is not None else None


def releases_for_requirement(session, requirement_identifier: str) -> set[str]:
    """The releases a requirement is scheduled into, via
    requirement ← planning_item_implements_requirement →
    planning_item_belongs_to_project → project_belongs_to_release."""
    out: set[str] = set()
    pi_edges = gov.inbound_edges(
        session,
        target_type="requirement",
        target_id=requirement_identifier,
        relationship="planning_item_implements_requirement",
        source_type="planning_item",
    )
    for pe in pi_edges:
        proj_edges = gov.outbound_edges(
            session,
            source_type="planning_item",
            source_id=pe.source_id,
            relationship="planning_item_belongs_to_project",
            target_type="project",
        )
        for pr in proj_edges:
            rel_edges = gov.outbound_edges(
                session,
                source_type="project",
                source_id=pr.target_id,
                relationship="project_belongs_to_release",
                target_type="release",
            )
            out.update(re.target_id for re in rel_edges)
    return out


def requirement_band(session, requirement_identifier: str) -> str:
    """The most restrictive enforcement band across the requirement's releases.

    ``open`` when the requirement is unscheduled or only in non-gated (terminal)
    releases.
    """
    band = "open"
    for rel in releases_for_requirement(session, requirement_identifier):
        status = _release_status(session, rel)
        if status is None:
            continue
        b = band_for_status(status)
        if b is not None and _BAND_RANK[b] > _BAND_RANK[band]:
            band = b
    return band


def assert_requirement_amendable(
    session, requirement_identifier: str, *, review_state: str
) -> None:
    """Gate a substantive requirement edit against its freeze band (FE-3/FE-4).

    ``review_state`` is the requirement's *current* review state (a
    ``needs_review`` state means a ``requirement_changed_by_decision`` decision
    opened the amend gate). Raises :class:`ConflictError` when the edit is not
    permitted.
    """
    band = requirement_band(session, requirement_identifier)
    if band == "open":
        return
    if band == "amend_window":
        if review_state == "needs_review":
            return
        raise ConflictError(
            f"requirement {requirement_identifier!r} is in a frozen release; a "
            f"demand change requires a governing decision — reopen it via a "
            f"requirement_changed_by_decision decision (review_state must be "
            f"needs_review) before editing."
        )
    # locked — past planned-completely.
    raise ConflictError(
        f"requirement {requirement_identifier!r}'s release is past "
        f"planned-completely; a demand change requires a new release (RW1), not "
        f"an in-flight edit."
    )


_MEMBERSHIP_KINDS = frozenset(
    {
        "project_belongs_to_release",
        "planning_item_belongs_to_project",
        "planning_item_implements_requirement",
    }
)


def _release_for_membership(
    session, relationship: str, source_id: str, target_id: str
) -> str | None:
    """Resolve the release a membership edge would attach work into."""
    if relationship == "project_belongs_to_release":
        return target_id  # target IS the release
    if relationship == "planning_item_belongs_to_project":
        # the project's release
        edges = gov.outbound_edges(
            session,
            source_type="project",
            source_id=target_id,
            relationship="project_belongs_to_release",
            target_type="release",
        )
        return edges[0].target_id if edges else None
    if relationship == "planning_item_implements_requirement":
        # the PI's project's release (source is the PI)
        proj = gov.outbound_edges(
            session,
            source_type="planning_item",
            source_id=source_id,
            relationship="planning_item_belongs_to_project",
            target_type="project",
        )
        if not proj:
            return None
        rel = gov.outbound_edges(
            session,
            source_type="project",
            source_id=proj[0].target_id,
            relationship="project_belongs_to_release",
            target_type="release",
        )
        return rel[0].target_id if rel else None
    return None


def assert_membership_addable(
    session, relationship: str, source_id: str, target_id: str
) -> None:
    """Reject adding a scope-membership edge into a frozen release (FE-3).

    Called from ``references.create`` for the three membership kinds; a no-op for
    every other relationship.
    """
    if relationship not in _MEMBERSHIP_KINDS:
        return
    release_id = _release_for_membership(session, relationship, source_id, target_id)
    if release_id is None:
        return
    status = _release_status(session, release_id)
    if status is None:
        return
    band = band_for_status(status)
    if band in ("amend_window", "locked"):
        raise ConflictError(
            f"cannot add {relationship!r} into release {release_id!r}: its scope "
            f"is frozen (status {status!r}). Schedule the work into a new release."
        )
