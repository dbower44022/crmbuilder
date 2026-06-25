"""Apply accepted differences back into the source YAML files.

This is the orchestration core the reconcile worker drives: given the list of
differences the user ticked, group them by owning file, apply each via the right
patcher, bump that file's ``content_version`` once, and write it back — surgically,
so untouched content stays byte-for-byte. Capture and diffing happen upstream
(they need the live CRM); this step is pure file I/O over the proven patchers and
is fully testable offline.

v1 auto-applies the changed-in-both and CRM-only-field cases; everything else is
report-only (carried through so the report lists it, never silently dropped):

* FIELD CHANGED        -> set_field_property
* FIELD CRM_ONLY       -> insert_field (full_crm_block must be YAML-shaped)
* LAYOUT CHANGED       -> replace_block_body (crm_value must be the YAML body)
* ROLE/TEAM CHANGED    -> apply_role_change / apply_team_change
* anything YAML_ONLY, a CRM-only layout/role/team, unsupported types -> report-only

The write value per difference is expected to be YAML-ready: scalars for
field/security CHANGED are already so; the live-capture glue reverse-maps the
layout body and the CRM-only field block before they reach here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.models import ConfigType, DiffCategory, Difference
from espo_impl.core.reconcile.patcher import (
    apply_relationship_change,
    apply_role_change,
    apply_team_change,
    insert_field,
    set_field_property,
)

_REPORT_ONLY = "report-only (not auto-applied in v1)"
_REPORT_ONLY_LAYOUT = (
    "report-only: layout write-back needs payload->YAML reverse-mapping "
    "(not yet wired); detected but not applied"
)
_REPORT_ONLY_ENTITY_OPTION = (
    "report-only: entity-option apply (write-back / deploy) is a follow-on "
    "slice; detected and surfaced but not applied"
)


@dataclass
class FileReconcileResult:
    """Outcome of reconciling one file."""

    path: Path
    applied: list[Difference] = field(default_factory=list)
    #: ``(difference, reason)`` for differences not written (report-only or error).
    not_applied: list[tuple[Difference, str]] = field(default_factory=list)
    old_version: str | None = None
    new_version: str | None = None
    rendered: str = ""


@dataclass
class ReconcileResult:
    """Aggregate outcome across all files."""

    files: list[FileReconcileResult] = field(default_factory=list)

    @property
    def applied_count(self) -> int:
        return sum(len(f.applied) for f in self.files)

    @property
    def not_applied_count(self) -> int:
        return sum(len(f.not_applied) for f in self.files)


def _apply_one(doc: YamlDocument, diff: Difference) -> str | None:
    """Apply one difference to ``doc``; return ``None`` if written, else a reason."""
    ct, cat = diff.config_type, diff.category

    if ct is ConfigType.FIELD:
        if cat is DiffCategory.CHANGED:
            set_field_property(doc, diff.entity, diff.locator.field_name, diff.property, diff.crm_value)
            return None
        if cat is DiffCategory.CRM_ONLY:
            insert_field(doc, diff.entity, diff.full_crm_block)
            return None
        return _REPORT_ONLY  # YAML_ONLY: never auto-delete

    if ct is ConfigType.LAYOUT:
        if cat is DiffCategory.CHANGED:
            # full_crm_block is the YAML body shape (panels:/columns: with natural
            # names), reverse-mapped from the live payload by the engine. crm_value
            # itself is the raw API payload and must NOT be written. If the body is
            # absent (engine reverse-map not run), stay report-only rather than
            # write a wrong shape.
            if diff.full_crm_block is None:
                return _REPORT_ONLY_LAYOUT
            layout_map = doc.data["entities"][diff.entity]["layout"]
            doc.replace_block_body(
                layout_map, diff.locator.layout_type, diff.full_crm_block
            )
            return None
        return _REPORT_ONLY  # CRM-only layout add / YAML_ONLY

    if ct is ConfigType.RELATIONSHIP:
        if cat is DiffCategory.CHANGED:
            apply_relationship_change(doc, diff.locator, diff.property, diff.crm_value)
            return None
        return _REPORT_ONLY  # CRM-only / YAML_ONLY relationship

    if ct is ConfigType.ROLE:
        if cat is DiffCategory.CHANGED:
            apply_role_change(doc, diff.locator, diff.crm_value)
            return None
        return _REPORT_ONLY

    if ct is ConfigType.TEAM:
        if cat is DiffCategory.CHANGED:
            apply_team_change(doc, diff.locator, diff.crm_value)
            return None
        return _REPORT_ONLY

    if ct is ConfigType.ENTITY_OPTION:
        return _REPORT_ONLY_ENTITY_OPTION  # PI-312: detection slice, apply deferred

    return f"unsupported config_type {ct.value}"


def apply_reconciliation(
    accepted: list[Difference], *, write: bool = True
) -> ReconcileResult:
    """Apply the accepted differences, grouped by owning file.

    Each touched file gets a single ``content_version`` bump and is written back
    (when ``write`` and at least one difference applied). ``write=False`` renders
    without touching disk (preview). A difference whose patcher errors is recorded
    in ``not_applied`` with the error rather than aborting the file.

    :raises ValueError: if any accepted difference has no ``source_file`` — the
        ask-per-addition target must be chosen before applying.
    """
    missing = [d for d in accepted if d.source_file is None]
    if missing:
        raise ValueError(
            f"{len(missing)} accepted difference(s) have no target file; "
            "choose a target (ask-per-addition) before applying"
        )

    by_file: dict[Path, list[Difference]] = {}
    for diff in accepted:
        by_file.setdefault(Path(diff.source_file), []).append(diff)

    result = ReconcileResult()
    for path, diffs in by_file.items():
        doc = YamlDocument(path.read_text())
        fr = FileReconcileResult(path=path)

        # Whole-item insertions into a top-level list (CRM-only roles/teams) are
        # batched per block: all items go in one splice (per-item appends would
        # collide on the same end-of-block offset, and a missing block must be
        # created exactly once). Handled here, ahead of the per-diff pass.
        handled: set[int] = set()
        for block_key, ct in (
            ("roles", ConfigType.ROLE),
            ("teams", ConfigType.TEAM),
            ("relationships", ConfigType.RELATIONSHIP),
        ):
            group = [
                d for d in diffs
                if d.config_type is ct
                and d.category is DiffCategory.CRM_ONLY
                and d.full_crm_block is not None
            ]
            if not group:
                continue
            try:
                doc.insert_or_create_top_level_block(
                    block_key, [d.full_crm_block for d in group]
                )
            except (KeyError, ValueError) as exc:
                fr.not_applied += [(d, f"error: {exc}") for d in group]
            else:
                fr.applied += group
            handled.update(id(d) for d in group)

        # CRM-only layout types: insert under each entity's layout: map (batched
        # per entity, creating layout: if absent).
        layout_co = [
            d for d in diffs
            if d.config_type is ConfigType.LAYOUT
            and d.category is DiffCategory.CRM_ONLY
            and d.full_crm_block is not None
        ]
        by_entity: dict[str, dict] = {}
        for d in layout_co:
            by_entity.setdefault(d.entity, {})[d.locator.layout_type] = d.full_crm_block
        for entity, bodies in by_entity.items():
            group = [d for d in layout_co if d.entity == entity]
            try:
                doc.insert_layout_blocks(entity, bodies)
            except (KeyError, ValueError) as exc:
                fr.not_applied += [(d, f"error: {exc}") for d in group]
            else:
                fr.applied += group
            handled.update(id(d) for d in group)

        for diff in diffs:
            if id(diff) in handled:
                continue
            try:
                reason = _apply_one(doc, diff)
            except (KeyError, ValueError) as exc:
                fr.not_applied.append((diff, f"error: {exc}"))
                continue
            if reason is None:
                fr.applied.append(diff)
            else:
                fr.not_applied.append((diff, reason))

        if fr.applied:
            bump = doc.bump_content_version()
            if bump:
                fr.old_version, fr.new_version = bump

        fr.rendered = doc.render()
        if write and fr.applied:
            path.write_text(fr.rendered)
        result.files.append(fr)

    return result
