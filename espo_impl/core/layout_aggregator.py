"""Aggregate cross-file layout contributions before deploy (PI-020 / REQ-403).

EspoCRM stores ONE detail layout per entity and the save-layout call *replaces*
the whole layout. The deploy engine processes program files one at a time and
writes each file's layout independently, so when two files target the same entity
only the last one's panels survive — the earlier file's are clobbered.

This module merges the layout blocks that multiple batched files contribute to the
same entity into a single layout per (entity, layout_type), so the deployed layout
contains **every** file's panels. It runs once over the whole batch, before the
per-file deploy loop:

* Panels are ordered deterministically — **by contributing file (alphabetical),
  then by declaration order within a file** (Option A).
* Two files declaring a panel with the **same label** on the same entity is a
  **conflict** (a deploy error), not a silent merge — the layouts are otherwise
  ambiguous.
* The merged layout is assigned to a single *canonical* entity_def (the first
  contributor, alphabetically) and cleared from the others, so exactly one
  save-layout call writes the complete layout.
* The canonical entity_def also carries ``layout_field_names`` — the union of
  custom field names across all contributors — so the writer can resolve
  c-prefixes for panels that reference fields declared in a sibling file.

Operates on plain :class:`EntityDefinition` objects so it unit-tests without a
live instance. The natural-name → EspoCRM-name mapping is injected to avoid a UI
import cycle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from espo_impl.core.models import EntityAction, EntityDefinition, LayoutSpec


@dataclass
class LayoutConflict:
    """A same-label panel collision between two files on one entity+layout."""

    entity: str
    layout_type: str
    label: str
    files: tuple[str, str]

    def message(self) -> str:
        a, b = self.files
        return (
            f"Layout conflict: {self.entity}.{self.layout_type} panel "
            f"{self.label!r} declared by both {a} and {b}"
        )


@dataclass
class AggregationResult:
    """Outcome of a batch layout aggregation."""

    #: file path/name -> the (possibly layout-stripped or -merged) entity_defs.
    programs: dict[str, list[EntityDefinition]]
    conflicts: list[LayoutConflict]

    @property
    def ok(self) -> bool:
        return not self.conflicts


def _panel_label(panel: object) -> str:
    return getattr(panel, "label", None) or ""


def aggregate_layouts(
    programs: list[tuple[str, list[EntityDefinition]]],
    espo_name_of: Callable[[str], str],
) -> AggregationResult:
    """Merge cross-file layout contributions across a deploy batch.

    :param programs: ``(file_name, entity_defs)`` for every file in the batch, in
        any order (the function sorts by ``file_name`` for deterministic output).
    :param espo_name_of: Maps a YAML entity name to its EspoCRM name, so two files
        naming the same native entity ("Account") are grouped even if one uses a
        variant spelling.
    :returns: An :class:`AggregationResult` with per-file entity_defs whose layouts
        have been merged onto one canonical contributor (and cleared on the rest),
        plus any label conflicts. On conflict the layouts are left **unmodified**
        so the caller can abort before deploying an ambiguous layout.
    """
    ordered = sorted(programs, key=lambda p: p[0])

    # entity espo-name -> layout_type -> list of (file_name, entity_def, LayoutSpec)
    contributions: dict[str, dict[str, list[tuple[str, EntityDefinition, LayoutSpec]]]] = {}
    for file_name, entity_defs in ordered:
        for ed in entity_defs:
            if ed.action == EntityAction.DELETE or not ed.layouts:
                continue
            espo = espo_name_of(ed.name)
            for layout_type, spec in ed.layouts.items():
                contributions.setdefault(espo, {}).setdefault(layout_type, []).append(
                    (file_name, ed, spec)
                )

    conflicts: list[LayoutConflict] = []
    # (id(entity_def)) -> {layout_type: merged LayoutSpec}; canonical only.
    merged_for: dict[int, dict[str, LayoutSpec]] = {}
    # id(entity_def) -> layout_types to strip (non-canonical contributors).
    strip_for: dict[int, set[str]] = {}
    # id(canonical entity_def) -> union of custom field names across contributors.
    field_union_for: dict[int, set[str]] = {}

    for espo, by_type in contributions.items():
        for layout_type, contribs in by_type.items():
            if len(contribs) == 1:
                continue  # single contributor — nothing to merge, write as-is.

            # Panels-class layouts only (detail/edit). A layout without a panel
            # list (e.g. list columns) can't be panel-merged; leave each as-is.
            if any(getattr(spec, "panels", None) is None for _, _, spec in contribs):
                continue

            canonical_file, canonical_ed, canonical_spec = contribs[0]
            merged_panels: list = []
            seen: dict[str, str] = {}  # label -> first file that declared it
            conflict_here = False
            for file_name, _ed, spec in contribs:
                for panel in spec.panels:
                    label = _panel_label(panel)
                    if label and label in seen and seen[label] != file_name:
                        conflicts.append(
                            LayoutConflict(
                                entity=espo, layout_type=layout_type, label=label,
                                files=(seen[label], file_name),
                            )
                        )
                        conflict_here = True
                    else:
                        if label:
                            seen.setdefault(label, file_name)
                        merged_panels.append(panel)
            if conflict_here:
                continue  # don't produce a merge for a conflicted layout

            merged_for.setdefault(id(canonical_ed), {})[layout_type] = replace(
                canonical_spec, panels=merged_panels
            )
            union = field_union_for.setdefault(id(canonical_ed), set())
            for _f, ed, _s in contribs:
                union.update(fd.name for fd in ed.fields)
            for _f, ed, _spec in contribs[1:]:
                strip_for.setdefault(id(ed), set()).add(layout_type)

    if conflicts:
        # Ambiguous — hand back the originals untouched so the caller aborts.
        return AggregationResult(programs=dict(ordered), conflicts=conflicts)

    # Apply the merges/strips, producing new entity_def objects (no mutation of
    # the caller's inputs beyond what we return).
    out: dict[str, list[EntityDefinition]] = {}
    for file_name, entity_defs in ordered:
        new_defs: list[EntityDefinition] = []
        for ed in entity_defs:
            merges = merged_for.get(id(ed))
            strips = strip_for.get(id(ed))
            if merges:
                layouts = dict(ed.layouts)
                layouts.update(merges)
                new_defs.append(
                    replace(
                        ed, layouts=layouts,
                        layout_field_names=field_union_for.get(id(ed)),
                    )
                )
            elif strips:
                layouts = {
                    lt: spec for lt, spec in ed.layouts.items() if lt not in strips
                }
                new_defs.append(replace(ed, layouts=layouts))
            else:
                new_defs.append(ed)
        out[file_name] = new_defs

    return AggregationResult(programs=out, conflicts=[])
