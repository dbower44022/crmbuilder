"""Top-level drift detection: live CRM vs. source YAML, across every type.

:func:`detect_drift` is the engine entry point the worker/UI call. It assembles
the desired side from the program files (with provenance), captures the live side
for every config type, runs each comparator, and returns one flat list of
:class:`Difference` plus the warnings/collisions/unmapped-entities to surface.

The result feeds straight into
:func:`espo_impl.core.reconcile.reconciler.apply_reconciliation` once the user
has ticked the subset to apply. This module performs only reads against the live
CRM (capture) and the YAML files (load); it never writes.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from espo_impl.core.reconcile.diff_engine import (
    diff_fields,
    diff_layouts,
    diff_relationships,
)
from espo_impl.core.reconcile.live_state import (
    LiveStateCapture,
    build_label_resolver,
    map_entity_specs,
)
from espo_impl.core.reconcile.models import Difference
from espo_impl.core.reconcile.provenance import (
    FieldCollision,
    build_field_provenance,
    build_layout_desired,
    build_relationship_provenance,
    build_security_provenance,
)
from espo_impl.core.reconcile.security_diff import diff_roles, diff_teams


@dataclass
class DriftReport:
    """The full drift picture for one reconcile run.

    :param differences: every detected difference across all config types.
    :param warnings: non-fatal issues (live fetch failures, empty role scopes,
        entities not present on the live instance, provenance collisions).
    :param collisions: ``(entity, item)`` declared by more than one file — the
        item is not reconciled to avoid editing an ambiguously-owned node.
    :param unmapped_entities: YAML entities absent from the live instance.
    """

    differences: list[Difference] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    collisions: list[FieldCollision] = field(default_factory=list)
    unmapped_entities: list[str] = field(default_factory=list)


def detect_drift(
    client,
    program_files: Iterable[Path],
    *,
    entities: Iterable[str] | None = None,
    include_native_fields: bool = True,
) -> DriftReport:
    """Detect drift between the live CRM (``client``) and the ``program_files``.

    :param entities: optional whitelist of YAML entity names to scope field /
        relationship / layout detection to; ``None`` covers every entity the
        program files declare. Roles and teams are global and always compared.
    :param include_native_fields: pass through to field capture (label/extra
        drift on native fields is visible when True).
    """
    program_files = list(program_files)

    # --- desired side (from YAML, with provenance) ---
    field_prov, field_collisions = build_field_provenance(program_files)
    rel_prov, rel_collisions = build_relationship_provenance(program_files)
    layout_desired, layout_files = build_layout_desired(program_files)
    roles, role_files, teams, team_files = build_security_provenance(program_files)

    entity_names = set(field_prov) | set(rel_prov) | set(layout_desired)
    if entities is not None:
        entity_names &= set(entities)

    report = DriftReport(collisions=[*field_collisions, *rel_collisions])

    # --- live side (capture) ---
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        report.warnings.append(
            f"failed to fetch entity scopes (HTTP {status}); "
            "entity-scoped detection skipped"
        )
        scopes = {}

    specs, unmapped = map_entity_specs(entity_names, scopes)
    report.unmapped_entities = unmapped

    # Restrict entity-scoped detection to entities that exist on the live
    # instance. A wholly-undeployed entity is surfaced once via
    # ``unmapped_entities`` rather than flooding the report with a YAML_ONLY row
    # per field/relationship/layout it declares.
    mapped = {s.yaml_name for s in specs}
    field_prov = {e: v for e, v in field_prov.items() if e in mapped}
    rel_prov = {e: v for e, v in rel_prov.items() if e in mapped}
    layout_desired = {e: v for e, v in layout_desired.items() if e in mapped}

    cap = LiveStateCapture(
        client,
        label_resolver=build_label_resolver(client),
        include_native=include_native_fields,
    )

    live_fields, w_fields = cap.capture_fields(specs)
    live_rels, w_rels = cap.capture_relationships(specs)
    live_layouts, w_layouts = cap.capture_layouts(specs)
    roles_live, teams_live, w_security = cap.capture_roles_teams()
    report.warnings += w_fields + w_rels + w_layouts + w_security

    # --- diff each type ---
    report.differences += diff_fields(field_prov, live_fields)
    report.differences += diff_relationships(rel_prov, live_rels)
    report.differences += diff_layouts(
        layout_desired, live_layouts, source_files=layout_files
    )
    report.differences += diff_roles(roles, roles_live, source_files=role_files)
    report.differences += diff_teams(teams, teams_live, source_files=team_files)

    return report
