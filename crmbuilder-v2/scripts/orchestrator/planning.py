"""Wave planning for the parallel-agent orchestrator (PI-081).

Pure, side-effect-free functions that turn a ready-batches wave into a set
of area-disjoint child clusters. Kept separate from ``run.py`` so the core
scheduling logic is unit-testable without an API, git, or subprocesses.

Conflict model (DEC-246 / DEC-247): two planning items conflict iff their
``area`` sets intersect. One child agent may own several items as long as
they form a connected component under "shares an area"; two *different*
clusters in the same wave must have disjoint area sets so their agents can
run concurrently without touching the same files.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Cluster:
    """One child agent's assignment: a set of planning items + the union of
    their areas (the areas the agent claims and must stay within)."""

    items: list[dict] = field(default_factory=list)
    areas: set[str] = field(default_factory=set)

    @property
    def identifiers(self) -> list[str]:
        return [it["identifier"] for it in self.items]


@dataclass
class WavePlan:
    """The dispatch plan for one wave."""

    depth: int
    clusters: list[Cluster]
    skipped_claimed: list[dict]
    unclustered: list[dict]  # items with no area set — cannot be parallelised


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self._parent.setdefault(x, x)

    def find(self, x: str) -> str:
        self.add(x)
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        # path compression
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        self._parent[self.find(a)] = self.find(b)


def partition_wave(items: list[dict], *, depth: int = 0) -> WavePlan:
    """Partition one wave's items into area-disjoint clusters.

    ``items`` are ready-batches item dicts (``identifier``, ``area``,
    ``claimed_by``, ...). Already-claimed items are set aside
    (``skipped_claimed`` — another agent owns them). Items with no
    ``area`` are set aside as ``unclustered`` because their file footprint
    is unknown and cannot be guaranteed disjoint. The remainder are grouped
    by connected components over shared areas: one ``Cluster`` per
    component, each owning the union of its items' areas.
    """
    skipped_claimed = [it for it in items if it.get("claimed_by")]
    live = [it for it in items if not it.get("claimed_by")]
    unclustered = [it for it in live if not it.get("area")]
    assignable = [it for it in live if it.get("area")]

    # Union items that share any area. Areas and item identifiers live in
    # the same union-find namespace (areas are unique strings; identifiers
    # are PI-NNN); union each item with each of its areas.
    uf = _UnionFind()
    for it in assignable:
        ident = it["identifier"]
        uf.add(ident)
        for area in it["area"]:
            uf.union(ident, f"area::{area}")

    groups: dict[str, Cluster] = {}
    for it in assignable:
        root = uf.find(it["identifier"])
        cluster = groups.setdefault(root, Cluster())
        cluster.items.append(it)
        cluster.areas.update(it["area"])

    # Deterministic ordering: by the lowest item identifier in each cluster.
    clusters = sorted(groups.values(), key=lambda c: min(c.identifiers))
    for c in clusters:
        c.items.sort(key=lambda it: it["identifier"])

    return WavePlan(
        depth=depth,
        clusters=clusters,
        skipped_claimed=skipped_claimed,
        unclustered=unclustered,
    )


def assert_clusters_disjoint(clusters: list[Cluster]) -> None:
    """Raise ``AssertionError`` if any two clusters share an area.

    A cheap invariant guard the driver runs before dispatching a wave —
    parallel safety depends on it.
    """
    seen: set[str] = set()
    for c in clusters:
        overlap = seen & c.areas
        if overlap:
            raise AssertionError(
                f"cluster {c.identifiers} overlaps areas {sorted(overlap)} "
                "with an earlier cluster — not safe to parallelise"
            )
        seen |= c.areas
