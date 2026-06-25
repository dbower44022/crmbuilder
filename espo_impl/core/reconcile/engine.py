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
    diff_entity_options,
    diff_fields,
    diff_layouts,
    diff_relationships,
)
from espo_impl.core.reconcile.layout_reverse import reverse_layout_payload
from espo_impl.core.reconcile.live_state import (
    LiveStateCapture,
    build_label_resolver,
    map_entity_specs,
)
from espo_impl.core.reconcile.models import ConfigType, DiffCategory, Difference
from espo_impl.core.reconcile.provenance import (
    FieldCollision,
    build_entity_option_desired,
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
    option_desired = build_entity_option_desired(program_files)
    roles, role_files, teams, team_files = build_security_provenance(program_files)

    entity_names = (
        set(field_prov) | set(rel_prov) | set(layout_desired) | set(option_desired)
    )
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
    option_desired = {e: v for e, v in option_desired.items() if e in mapped}

    cap = LiveStateCapture(
        client,
        label_resolver=build_label_resolver(client),
        include_native=include_native_fields,
    )

    live_fields, w_fields = cap.capture_fields(specs)
    live_rels, w_rels = cap.capture_relationships(specs)
    live_layouts, w_layouts = cap.capture_layouts(specs)
    live_options, w_options = cap.capture_entity_options(specs)
    roles_live, teams_live, w_security = cap.capture_roles_teams()
    report.warnings += w_fields + w_rels + w_layouts + w_options + w_security

    # --- diff each type ---
    report.differences += diff_fields(field_prov, live_fields)
    rel_diffs = diff_relationships(rel_prov, live_rels)
    _attach_relationship_insert_bodies(rel_diffs)
    report.differences += rel_diffs
    layout_diffs = diff_layouts(
        layout_desired, live_layouts, source_files=layout_files
    )
    _attach_layout_write_bodies(layout_diffs, cap, specs)
    report.differences += layout_diffs
    report.differences += diff_entity_options(option_desired, live_options)
    role_diffs = diff_roles(roles, roles_live, source_files=role_files)
    team_diffs = diff_teams(teams, teams_live, source_files=team_files)
    _attach_security_insert_bodies(role_diffs, ConfigType.ROLE, report.warnings)
    _attach_security_insert_bodies(team_diffs, ConfigType.TEAM, report.warnings)
    report.differences += role_diffs
    report.differences += team_diffs

    return report


def _attach_relationship_insert_bodies(diffs: list[Difference]) -> None:
    """Reconstruct each CRM_ONLY relationship's captured dict into its YAML
    ``relationships:`` mapping (``full_crm_block``) so whole-item capture applies."""
    from dataclasses import replace

    from espo_impl.core.reconcile.reconstruct import relationship_to_yaml

    for i, diff in enumerate(diffs):
        if diff.category is DiffCategory.CRM_ONLY and diff.full_crm_block is not None:
            diffs[i] = replace(
                diff, full_crm_block=relationship_to_yaml(diff.full_crm_block)
            )


def _attach_security_insert_bodies(
    diffs: list[Difference], config_type, warnings: list[str]
) -> None:
    """Reconstruct each CRM_ONLY role/team's live view into the YAML mapping to
    insert (``full_crm_block``), so whole-item capture is applicable.

    The CRM_ONLY diff initially carries the live audit-result view; we replace it
    with the serialized ``roles:``/``teams:`` mapping. A role holding a value the
    schema can't represent (e.g. EspoCRM ``not-set``) is left uncaptured
    (``full_crm_block=None`` -> report-only) with a warning, rather than writing
    YAML that won't re-parse. ``Difference`` is frozen, so we swap in copies.
    """
    from dataclasses import replace

    from espo_impl.core.reconcile.reconstruct import (
        role_representability_issue,
        role_to_yaml,
        team_to_yaml,
    )

    for i, diff in enumerate(diffs):
        if diff.category is not DiffCategory.CRM_ONLY or diff.full_crm_block is None:
            continue
        if config_type is ConfigType.ROLE:
            block = role_to_yaml(diff.full_crm_block)
            issue = role_representability_issue(block)
            if issue:
                warnings.append(
                    f"Role {diff.entity!r}: {issue} is not representable in the "
                    "YAML role schema (only all/team/own/no); not captured — "
                    "capture manually or extend the schema to allow 'not-set'."
                )
                diffs[i] = replace(diff, full_crm_block=None)
                continue
        else:
            block = team_to_yaml(diff.full_crm_block)
        diffs[i] = replace(diff, full_crm_block=block)


def _attach_layout_write_bodies(layout_diffs, cap, specs) -> None:
    """Reverse-map each CHANGED layout's live payload to its YAML body in place.

    Both a CHANGED diff (drift in a declared layout) and a CRM_ONLY diff (a layout
    type the YAML never declared) carry the raw API payload as ``crm_value``; the
    reconciler writes ``full_crm_block``. We populate it with the YAML-shaped body
    (natural field names, panels:/columns: structure) so layout drift is applicable
    and a new layout type is captureable. YAML_ONLY layouts stay report-only.
    ``Difference`` is frozen, so we replace each entry with an updated copy.
    """
    from dataclasses import replace

    writeable = {DiffCategory.CHANGED, DiffCategory.CRM_ONLY}
    if not any(
        d.config_type is ConfigType.LAYOUT and d.category in writeable
        for d in layout_diffs
    ):
        return
    custom_names = cap.custom_field_api_names(specs)
    for i, diff in enumerate(layout_diffs):
        if not (
            diff.config_type is ConfigType.LAYOUT and diff.category in writeable
        ):
            continue
        body = reverse_layout_payload(
            diff.locator.layout_type,
            diff.crm_value,
            custom_names.get(diff.entity, set()),
        )
        layout_diffs[i] = replace(diff, full_crm_block=body)
