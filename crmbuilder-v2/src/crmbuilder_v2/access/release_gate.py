"""Release-scoped development gate (REQ-323 / REQ-324, PI-288).

REQ-323 — a planning item cannot be *developed* unless it is in a frozen
release's scope: ``planning_item --planning_item_belongs_to_project-->
project --project_belongs_to_release--> release``, where the release is frozen.
"Frozen" here means the release has passed its freeze (``reconciliation``) gate
and is still open for development — the ``amend_window`` and ``locked`` bands
(``reconciliation``, ``architecture_planning``, ``ready``, and the four lane
states). A pre-freeze release (``preliminary_planning`` / ``development_planning``)
or a terminal one (``shipped`` / ``cancelled`` / ``superseded``) is **not** a
developable scope. Freeze is the scope-closing gate (see ``access/freeze.py``
``band_for_status``).

REQ-324 — enforcement is controlled by ``Settings.release_scoped_gate_enabled``,
which defaults **off**, so in-flight work drains under the prior model before the
gate is turned on. While off, every call here is a no-op.

The gated development actions (the surface set REQ-323 left to the implementing
design) are: transitioning a planning item to **In Progress** (development
active) or **Resolved** (delivered) — wired in
``access/repositories/planning_items.update`` — and **decomposing** a planning
item for build — wired in ``access/repositories/decomposition``. The
conversation ``resolves`` edge flows through ``update(status="Resolved")`` and is
covered there. Claiming a work task is intentionally not separately gated: a work
task exists only once its planning item has been decomposed, which is itself
gated.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.freeze import band_for_status
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.config import get_settings

# A release is a developable (frozen) scope while it is frozen and still open for
# development — the amend-window and locked bands. The "open" band (pre-freeze)
# and ``None`` (terminal) do not count.
_FROZEN_BANDS = frozenset({"amend_window", "locked"})


def _releases_for_planning_item(session: Session, pi_identifier: str) -> set[str]:
    """The releases a planning item is scheduled into, via
    ``planning_item --planning_item_belongs_to_project--> project
    --project_belongs_to_release--> release``."""
    out: set[str] = set()
    for proj_edge in gov.outbound_edges(
        session,
        source_type="planning_item",
        source_id=pi_identifier,
        relationship="planning_item_belongs_to_project",
        target_type="project",
    ):
        for rel_edge in gov.outbound_edges(
            session,
            source_type="project",
            source_id=proj_edge.target_id,
            relationship="project_belongs_to_release",
            target_type="release",
        ):
            out.add(rel_edge.target_id)
    return out


def in_frozen_release_scope(session: Session, pi_identifier: str) -> bool:
    """``True`` iff ``pi_identifier`` belongs to a project bound to a frozen
    release (one whose status is in a frozen band)."""
    release_ids = _releases_for_planning_item(session, pi_identifier)
    if not release_ids:
        return False
    rows = session.scalars(
        select(Release).where(Release.release_identifier.in_(release_ids))
    ).all()
    return any(band_for_status(r.release_status) in _FROZEN_BANDS for r in rows)


def assert_developable(session: Session, pi_identifier: str, *, action: str) -> None:
    """Gate a development action on a planning item (REQ-323).

    A no-op when ``Settings.release_scoped_gate_enabled`` is off (REQ-324). When
    on, raises :class:`ConflictError` if the planning item is not in a frozen
    release's scope.

    :param session: open SQLAlchemy session.
    :param pi_identifier: the ``PI-NNN`` whose development is being attempted.
    :param action: a short present/past phrase naming the attempted action, used
        in the rejection message (e.g. ``"moved to In Progress"``, ``"resolved"``,
        ``"decomposed"``).
    :raises ConflictError: gate is on and the planning item is not in a frozen
        release's scope.
    """
    if not get_settings().release_scoped_gate_enabled:
        return
    if not in_frozen_release_scope(session, pi_identifier):
        raise ConflictError(
            f"planning_item {pi_identifier!r} cannot be {action}: it is not in a "
            f"frozen release's scope. All development goes through a release — "
            f"scope it into a release-scoped project and freeze the release "
            f"(reconciliation) before developing it."
        )
