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
from espo_impl.core.models import FieldDefinition

#: ``{entity: {field_name: (FieldDefinition, source_file)}}`` — the "desired"
#: input to :func:`espo_impl.core.reconcile.diff_engine.diff_fields`.
FieldProvenance = dict[str, dict[str, tuple[FieldDefinition, Path]]]

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
