"""Design-side mapping staleness — PI-345 (REQ-304 / DEC-652, PRJ-027).

The design-changed half of mapping staleness. PI-255 shipped the source-side half
(a re-audit finds a mapped *source* object changed → the mapping goes stale,
``source_changed``). This is the mirror: when a canonical *design* object that a
**resolved** mapping targets is edited in a meaning-bearing way (an entity rename,
a field type/name change, an association cardinality/name change), the targeting
``source_mapping`` / ``field_mapping`` / ``association_mapping`` is flipped
``stale, design_changed`` with a graded severity, so the human re-resolves it (in
the candidate-review panel, PI-256). Only ``resolved`` mappings are flagged —
already-stale ones are left (their transition is human-driven), which makes the
hooks idempotent.

The canonical-edit repositories call the ``on_*_updated`` helpers right after
emitting their change_log, passing the before/after dicts so this module decides
whether the change is meaning-bearing.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.models import SourceMappingTarget
from crmbuilder_v2.access.repositories import association_mapping as amap
from crmbuilder_v2.access.repositories import field_mapping as fmap
from crmbuilder_v2.access.repositories import source_mapping as smg


def flag_entity_design_changed(
    session: Session, entity_identifier: str, *, severity: str = "low"
) -> int:
    """Flag every resolved source mapping targeting ``entity_identifier`` stale."""
    mids = set(session.scalars(
        select(SourceMappingTarget.source_mapping_identifier).where(
            SourceMappingTarget.entity_identifier == entity_identifier
        )
    ).all())
    flagged = 0
    for mid in mids:
        row = smg.get_source_mapping(session, mid)
        if row is not None and row["status"] == "resolved":
            smg.mark_stale(session, mid, reason="design_changed", severity=severity)
            flagged += 1
    return flagged


def flag_field_design_changed(
    session: Session, field_identifier: str, *, severity: str = "high"
) -> int:
    """Flag every resolved field mapping targeting ``field_identifier`` stale."""
    flagged = 0
    for fm in fmap.list_field_mappings(session, status="resolved"):
        if fm.get("target_field_identifier") == field_identifier:
            fmap.mark_stale(
                session, fm["field_mapping_identifier"],
                reason="design_changed", severity=severity,
            )
            flagged += 1
    return flagged


def flag_association_design_changed(
    session: Session, association_identifier: str, *, severity: str = "high"
) -> int:
    """Flag every resolved association mapping targeting the association stale."""
    flagged = 0
    for am in amap.list_association_mappings(session, status="resolved"):
        if am.get("target_association_identifier") == association_identifier:
            amap.mark_stale(
                session, am["association_mapping_identifier"],
                reason="design_changed", severity=severity,
            )
            flagged += 1
    return flagged


# --- canonical-edit hooks (called by the entity/field/association repos) -----


def on_entity_updated(
    session: Session, identifier: str, before: dict, after: dict
) -> int:
    """A rename changes the entity's meaning (low — the mapping likely holds)."""
    if (before or {}).get("entity_name") != (after or {}).get("entity_name"):
        return flag_entity_design_changed(session, identifier, severity="low")
    return 0


def on_field_updated(
    session: Session, identifier: str, before: dict, after: dict
) -> int:
    """A field type change is high (translation may break); a rename is low."""
    b, a = before or {}, after or {}
    if b.get("field_type") != a.get("field_type"):
        return flag_field_design_changed(session, identifier, severity="high")
    if b.get("field_name") != a.get("field_name"):
        return flag_field_design_changed(session, identifier, severity="low")
    return 0


def on_association_updated(
    session: Session, identifier: str, before: dict, after: dict
) -> int:
    """A cardinality change is high; a rename is low."""
    b, a = before or {}, after or {}
    if b.get("association_cardinality") != a.get("association_cardinality"):
        return flag_association_design_changed(session, identifier, severity="high")
    if b.get("association_name") != a.get("association_name"):
        return flag_association_design_changed(session, identifier, severity="low")
    return 0
