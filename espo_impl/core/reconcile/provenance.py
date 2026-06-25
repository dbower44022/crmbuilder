"""Index source YAML so each item knows which file owns it.

An entity is commonly extended across several domain files (e.g. ``Account`` by
both ``MN-Account.yaml`` and ``FU-Account.yaml``). The diff engine and the
write-back layer both need to know *which* file a given field lives in — to edit
the right file and to attribute the change in the report. This module builds that
index from the program files.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.layout_manager import LayoutManager
from espo_impl.core.models import (
    FieldDefinition,
    RelationshipDefinition,
    RoleDefinition,
    TeamDefinition,
)
from espo_impl.ui.confirm_delete_dialog import NATIVE_ENTITIES

#: ``{entity: {field_name: (FieldDefinition, source_file)}}`` — the "desired"
#: input to :func:`espo_impl.core.reconcile.diff_engine.diff_fields`.
FieldProvenance = dict[str, dict[str, tuple[FieldDefinition, Path]]]

#: ``{entity: {link_name: (RelationshipDefinition, source_file)}}`` — keyed by the
#: primary link name to match :meth:`LiveStateCapture.capture_relationships`.
RelationshipProvenance = dict[str, dict[str, tuple[RelationshipDefinition, Path]]]

# Path fragments that mark a file as not part of the canonical program set.
# "audit-" skips generated audit-snapshot directories (programs/audit-YYYYMMDD-.../).
_DEFAULT_EXCLUDES = ("/archive/", "audit-", "-test.", "-draft.", "-revised", "inventory")


@dataclass(frozen=True)
class FieldCollision:
    """The same field declared on the same entity by two files."""

    entity: str
    field_name: str
    first_file: Path
    duplicate_file: Path


def discover_program_files(
    programs_dir: Path, *, excludes: tuple[str, ...] = _DEFAULT_EXCLUDES
) -> list[Path]:
    """Return canonical ``*.yaml`` program files under ``programs_dir``.

    Best-effort helper: skips archived, TEST, draft, and inventory variants by
    path-fragment match (case-insensitive). Callers that select files explicitly
    (as the Configure flow does) should pass their own list instead.
    """
    out = []
    for path in sorted(programs_dir.rglob("*.yaml")):
        rel = str(path).lower()
        if any(frag in rel for frag in excludes):
            continue
        out.append(path)
    return out


def build_field_provenance(
    program_files: Iterable[Path], *, loader: ConfigLoader | None = None
) -> tuple[FieldProvenance, list[FieldCollision]]:
    """Build the field provenance index from the given program files.

    On a duplicate ``(entity, field)`` across files the first occurrence wins and
    the duplicate is reported as a :class:`FieldCollision` rather than silently
    overwritten — so reconciliation never edits an ambiguously-owned field
    without the caller being aware.
    """
    loader = loader or ConfigLoader()
    desired: FieldProvenance = {}
    collisions: list[FieldCollision] = []

    for raw_path in program_files:
        path = Path(raw_path)
        program = loader.load_program(path)
        for entity in program.entities:
            ent_map = desired.setdefault(entity.name, {})
            for fld in entity.fields:
                if fld.name in ent_map:
                    collisions.append(
                        FieldCollision(
                            entity=entity.name,
                            field_name=fld.name,
                            first_file=ent_map[fld.name][1],
                            duplicate_file=path,
                        )
                    )
                    continue
                ent_map[fld.name] = (fld, path)

    return desired, collisions


def build_relationship_provenance(
    program_files: Iterable[Path], *, loader: ConfigLoader | None = None
) -> tuple[RelationshipProvenance, list[FieldCollision]]:
    """Build the relationship provenance index, keyed ``{entity: {link: (def, file)}}``.

    Keyed by the primary link name (``RelationshipDefinition.link``) — the stable
    identity shared with the live side. First occurrence wins; a duplicate
    ``(entity, link)`` is reported as a :class:`FieldCollision` (``field_name``
    carries the link name).
    """
    loader = loader or ConfigLoader()
    desired: RelationshipProvenance = {}
    collisions: list[FieldCollision] = []

    for raw_path in program_files:
        path = Path(raw_path)
        program = loader.load_program(path)
        for rel in program.relationships:
            ent_map = desired.setdefault(rel.entity, {})
            if rel.link in ent_map:
                collisions.append(
                    FieldCollision(
                        entity=rel.entity,
                        field_name=rel.link,
                        first_file=ent_map[rel.link][1],
                        duplicate_file=path,
                    )
                )
                continue
            ent_map[rel.link] = (rel, path)

    return desired, collisions


def build_layout_desired(
    program_files: Iterable[Path], *, loader: ConfigLoader | None = None
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, Path]]]:
    """Build desired layout payloads + their owning files.

    Returns ``(desired, source_files)`` shaped for
    :func:`espo_impl.core.reconcile.diff_engine.diff_layouts` —
    ``{entity: {layout_type: payload}}`` and ``{entity: {layout_type: file}}``.
    Each payload is built exactly as the deploy path builds it (via
    :meth:`LayoutManager._build_payload`), so drift is judged identically.
    Variant-form layouts (NOT_SUPPORTED at deploy) are skipped. First occurrence
    of an ``(entity, layout_type)`` wins.
    """
    loader = loader or ConfigLoader()
    builder = LayoutManager(client=None, output_fn=lambda *a: None)
    desired: dict[str, dict[str, object]] = {}
    source_files: dict[str, dict[str, Path]] = {}

    for raw_path in program_files:
        path = Path(raw_path)
        program = loader.load_program(path)
        for entity in program.entities:
            if not entity.layouts:
                continue
            custom_field_names = (
                {f.name for f in entity.fields}
                if entity.name in NATIVE_ENTITIES
                else set()
            )
            auto_place_name = not (
                entity.settings is not None
                and entity.settings.autoPlaceName is False
            )
            ent_map = desired.setdefault(entity.name, {})
            src_map = source_files.setdefault(entity.name, {})
            for ltype, spec in entity.layouts.items():
                if ltype in ent_map or spec.has_variants():
                    continue
                ent_map[ltype] = builder._build_payload(
                    spec,
                    field_definitions=entity.fields,
                    custom_field_names=custom_field_names,
                    auto_place_name=auto_place_name,
                    entity_name=entity.name,
                )
                src_map[ltype] = path

    return desired, source_files


def build_security_provenance(
    program_files: Iterable[Path], *, loader: ConfigLoader | None = None
) -> tuple[
    dict[str, RoleDefinition], dict[str, Path],
    dict[str, TeamDefinition], dict[str, Path],
]:
    """Build desired role/team indexes + their owning files.

    Returns ``(roles, role_files, teams, team_files)`` shaped for
    :func:`...security_diff.diff_roles` / :func:`...security_diff.diff_teams`
    (``{name: definition}`` + ``{name: file}``). First occurrence of a name wins.
    """
    loader = loader or ConfigLoader()
    roles: dict[str, RoleDefinition] = {}
    role_files: dict[str, Path] = {}
    teams: dict[str, TeamDefinition] = {}
    team_files: dict[str, Path] = {}

    for raw_path in program_files:
        path = Path(raw_path)
        program = loader.load_program(path)
        for role in program.roles:
            if role.name not in roles:
                roles[role.name] = role
                role_files[role.name] = path
        for team in program.teams:
            if team.name not in teams:
                teams[team.name] = team
                team_files[team.name] = path

    return roles, role_files, teams, team_files


def build_entity_option_desired(
    program_files: Iterable[Path], *, loader: ConfigLoader | None = None
) -> dict[str, tuple[dict[str, object], Path]]:
    """Build the entity-option desired index (PI-312 / REQ-346).

    Returns ``{entity: ({option: value}, source_file)}`` shaped for
    :func:`...diff_engine.diff_entity_options`, reading each entity's typed
    ``settings`` for the :data:`...diff_engine.ENTITY_OPTION_KEYS` subset. Only
    keys the YAML actually sets (non-``None``) are included, so the comparator's
    absent-vs-default normalization governs drift. First entity occurrence wins.
    """
    from espo_impl.core.reconcile.diff_engine import ENTITY_OPTION_KEYS

    loader = loader or ConfigLoader()
    desired: dict[str, tuple[dict[str, object], Path]] = {}

    for raw_path in program_files:
        path = Path(raw_path)
        program = loader.load_program(path)
        for entity in program.entities:
            if entity.name in desired or entity.settings is None:
                continue
            opts = {
                key: getattr(entity.settings, key)
                for key in ENTITY_OPTION_KEYS
                if getattr(entity.settings, key, None) is not None
            }
            if opts:
                desired[entity.name] = (opts, path)

    return desired


def build_entity_file_index(
    program_files: Iterable[Path], *, loader: ConfigLoader | None = None
) -> dict[str, Path]:
    """Map each entity name to the first program file that declares it.

    Targets entity-option write-back for a CRM-ahead option on an entity that
    has no ``settings:`` block yet (so :func:`build_entity_option_desired`
    recorded no owning file). First occurrence wins, matching the other
    provenance builders.
    """
    loader = loader or ConfigLoader()
    index: dict[str, Path] = {}
    for raw_path in program_files:
        path = Path(raw_path)
        program = loader.load_program(path)
        for entity in program.entities:
            index.setdefault(entity.name, path)
    return index
