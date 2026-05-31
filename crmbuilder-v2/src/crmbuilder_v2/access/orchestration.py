"""Orchestration queries for the parallel-agent orchestrator (PI-079, WS-012).

The orchestrator calls :func:`compute_ready_batches` once at the start of
every run to learn what is safe to dispatch. It returns the open planning
items grouped by dependency depth — depth 0 has no unresolved
dependencies, depth 1 depends only on depth 0, and so on — with each
item's ``area`` set, ``claimed_by``, and ``executive_summary`` attached
so the driver can partition work (area-disjoint) and skip already-claimed
items without further round-trips.

Dependency edges come from ``blocked_by`` references
(``source_type = target_type = planning_item``); only edges whose target
is *also* an open item count as a blocker, so a ``blocked_by`` edge to an
already-resolved item is treated as satisfied. Cycles are surfaced in a
separate ``cyclic`` bucket with a warning rather than failing the call.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import validate_optional_value_list
from crmbuilder_v2.access.repositories import (
    engagement_areas,
    planning_items,
    references,
)

# Per-item projection returned in each batch.
_ITEM_FIELDS = ("identifier", "title", "executive_summary", "area", "claimed_by")

_READY = "Ready"  # PI-112/DEC-346: standing-agent dispatch trigger
_BLOCKED_BY = "blocked_by"


def _compute_depths(
    nodes: set[str], blockers: dict[str, set[str]]
) -> tuple[dict[str, int], set[str]]:
    """Longest-path dependency depth per node, plus the set of cyclic nodes.

    ``blockers[n]`` is the set of open items ``n`` is blocked by. A node's
    depth is ``0`` when it has no open blockers, else
    ``1 + max(depth(blocker))``. Any node on a cycle — or transitively
    depending on one — cannot be assigned a finite depth and is returned
    in the cyclic set instead (DFS with on-stack back-edge detection).
    """
    GRAY, BLACK = 1, 2
    state: dict[str, int] = {}
    depth: dict[str, int | None] = {}
    cyclic: set[str] = set()

    def visit(n: str) -> int | None:
        s = state.get(n)
        if s == BLACK:
            return depth.get(n)  # None if this node was marked cyclic
        if s == GRAY:
            return None  # back edge → cycle
        state[n] = GRAY
        d = 0
        tainted = False
        for b in blockers.get(n, ()):  # noqa: SIM118 — set membership iteration
            bd = visit(b)
            if bd is None:
                tainted = True
            else:
                d = max(d, bd + 1)
        state[n] = BLACK
        if tainted:
            cyclic.add(n)
            depth[n] = None
            return None
        depth[n] = d
        return d

    for n in nodes:
        visit(n)
    finite = {n: d for n, d in depth.items() if d is not None}
    return finite, cyclic


def compute_ready_batches(
    session: Session,
    *,
    areas: list[str] | None = None,
    max_depth: int | None = None,
) -> dict:
    """Return open planning items grouped by dependency depth.

    ``areas`` (optional) keeps only items whose area set intersects the
    requested areas; an item with no ``area`` is excluded under an area
    filter. ``max_depth`` (optional) drops batches deeper than the cutoff.
    Each requested area must be a valid area (System ∪ this engagement's
    Engagement areas; see ``engagement_areas.valid_area_names``).
    """
    if areas is not None:
        validate_optional_value_list(
            areas, field="area", allowed=engagement_areas.valid_area_names(session)
        )

    items = {
        pi["identifier"]: pi
        for pi in planning_items.list_all(session)
        if pi.get("status") == _READY
    }
    nodes = set(items)

    edges = references.list_references(
        session,
        source_type="planning_item",
        target_type="planning_item",
        relationship_kind=_BLOCKED_BY,
    )
    blockers: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        src, tgt = e["source_id"], e["target_id"]
        # Only an open blocker is unresolved; a blocked_by edge to a
        # resolved/absent item is treated as satisfied.
        if src in items and tgt in items:
            blockers[src].add(tgt)

    depth, cyclic = _compute_depths(nodes, blockers)

    def shaped(ident: str) -> dict:
        pi = items[ident]
        return {k: pi.get(k) for k in _ITEM_FIELDS}

    def keep(item: dict) -> bool:
        if areas is None:
            return True
        return item["area"] is not None and bool(set(item["area"]) & set(areas))

    by_depth: dict[int, list[dict]] = defaultdict(list)
    cyclic_items: list[dict] = []
    for ident in sorted(items):
        item = shaped(ident)
        if not keep(item):
            continue
        if ident in cyclic:
            cyclic_items.append(item)
        else:
            by_depth[depth[ident]].append(item)

    batches: list[dict] = []
    for d in sorted(by_depth):
        if max_depth is not None and d > max_depth:
            continue
        if not by_depth[d]:
            continue
        batches.append({"depth": d, "items": by_depth[d]})

    warnings: list[str] = []
    if cyclic_items:
        ids = ", ".join(sorted(it["identifier"] for it in cyclic_items))
        warnings.append(f"dependency cycle involves planning items: {ids}")

    return {"batches": batches, "cyclic": cyclic_items, "warnings": warnings}
