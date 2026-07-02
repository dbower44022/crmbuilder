"""REL-039 / PI-357 knowledge ingest (REQ-416, DEC-891).

Migrates the authored catalog (``rel039_knowledge_catalog.py``) into the DB:
governance_rules (GVR-), preferences (PRF-), lessons (LSN-, with
``lesson_derived_from`` provenance edges), and reference_pointers (RFP-, CBM
scoped to ENG-002). Uses the access layer directly (so it runs on the droplet
against the live cloud PG, where the API is auth-gated).

Idempotent: a record is keyed by (entity_type, scope, title); an existing title
is skipped, so re-running is safe. Provenance/edge creation tolerates the
duplicate (already-exists) case. ``--dry-run`` writes nothing.

The ingest runs under the ENG-001 active-engagement context (the acting
engagement for the change_log); a record's own ``scope`` field sets its
``engagement_id`` (system = NULL, ENG-002 = CBM overlay) independently.

Usage (on the droplet, against live cloud PG):
    cd /opt/crmbuilder && QT_QPA_PLATFORM=offscreen .venv/bin/python3 \
        crmbuilder-v2/scripts/ingest_rel039_knowledge.py --dry-run
    ... then without --dry-run to apply.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow "import rel039_knowledge_catalog" when run as a bare script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import rel039_knowledge_catalog as cat  # noqa: E402
from crmbuilder_v2.access import change_log  # noqa: E402
from crmbuilder_v2.access.db import session_scope  # noqa: E402
from crmbuilder_v2.access.engagement_scope import active_engagement  # noqa: E402
from crmbuilder_v2.access.exceptions import ConflictError  # noqa: E402
from crmbuilder_v2.access.repositories import (  # noqa: E402
    governance_rules,
    lessons,
    preferences,
    reference_pointers,
    references,
)

ACTING_ENGAGEMENT = "ENG-001"


def _existing_titles(rows: list[dict]) -> dict[tuple[str, str], str]:
    """Map (title, scope) -> identifier for the rows already present."""
    return {(r["title"], r.get("scope", "system")): r["identifier"] for r in rows}


def _safe_edge(session, *, source_type, source_id, target_type, target_id, relationship):
    """Create a reference edge, tolerating the already-exists (re-run) case."""
    try:
        references.create(
            session,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relationship=relationship,
        )
        return "created"
    except ConflictError:
        return "exists"


def run(*, dry_run: bool) -> int:
    counts = {"gvr": 0, "prf": 0, "lsn": 0, "rfp": 0, "edges": 0, "skipped": 0}

    with active_engagement(ACTING_ENGAGEMENT):
        change_log.set_actor("user")
        with session_scope() as s:
            # --- governance rules ---------------------------------------
            # governance_rule has no title column; the catalog title is prepended
            # to the body, so dedup by body-prefix within scope.
            gvr_bodies = [
                (row["body"], row.get("scope", "system"))
                for row in governance_rules.list_all(s)
            ]
            for r in cat.GOVERNANCE_RULES:
                scope = r.get("scope", "system")
                if any(
                    sc == scope and body.startswith(r["title"])
                    for body, sc in gvr_bodies
                ):
                    counts["skipped"] += 1
                    print(f"  GVR exists: {r['title']}")
                    continue
                if dry_run:
                    counts["gvr"] += 1
                    print(f"  + GVR (dry): {r['title']}  [{r['enforcement']}]")
                    continue
                row = governance_rules.create(
                    s, body=f"{r['title']}. {r['body']}",
                    enforcement=r["enforcement"], severity=r.get("severity"),
                    rule_type=r.get("rule_type"), scope=scope,
                )
                counts["gvr"] += 1
                print(f"  + {row['identifier']}: {r['title']}")
                for tgt_type, tgt_id in r.get("edges", []):
                    res = _safe_edge(
                        s, source_type="governance_rule", source_id=row["identifier"],
                        target_type=tgt_type, target_id=tgt_id, relationship="is_about",
                    )
                    if res == "created":
                        counts["edges"] += 1

            # --- preferences --------------------------------------------
            have = _existing_titles(preferences.list_all(s))
            for r in cat.PREFERENCES:
                scope = r.get("scope", "system")
                if (r["title"], scope) in have:
                    counts["skipped"] += 1
                    print(f"  PRF exists: {r['title']}")
                    continue
                if dry_run:
                    counts["prf"] += 1
                    print(f"  + PRF (dry): {r['title']}  [{r['category']}]")
                    continue
                row = preferences.create(
                    s, category=r["category"], title=r["title"], body=r["body"],
                    applies_to=r.get("applies_to", "all"), scope=scope,
                )
                counts["prf"] += 1
                print(f"  + {row['identifier']}: {r['title']}")

            # --- lessons (+ provenance edges) ---------------------------
            have = _existing_titles(lessons.list_all(s))
            for r in cat.LESSONS:
                scope = r.get("scope", "system")
                if (r["title"], scope) in have:
                    counts["skipped"] += 1
                    print(f"  LSN exists: {r['title']}")
                    continue
                if dry_run:
                    counts["lsn"] += 1
                    edges = len(r.get("derived_from", []))
                    print(f"  + LSN (dry): {r['title']}  [{r['signal']}] (+{edges} edges)")
                    continue
                row = lessons.create(
                    s, category=r["category"], title=r["title"], body=r["body"],
                    signal=r.get("signal", "guidance"), scope=scope,
                )
                counts["lsn"] += 1
                print(f"  + {row['identifier']}: {r['title']}")
                for tgt_type, tgt_id in r.get("derived_from", []):
                    res = _safe_edge(
                        s, source_type="lesson", source_id=row["identifier"],
                        target_type=tgt_type, target_id=tgt_id,
                        relationship="lesson_derived_from",
                    )
                    if res == "created":
                        counts["edges"] += 1

            # --- reference pointers -------------------------------------
            have = _existing_titles(reference_pointers.list_all(s))
            for r in cat.REFERENCE_POINTERS:
                scope = r.get("scope", "system")
                if (r["title"], scope) in have:
                    counts["skipped"] += 1
                    print(f"  RFP exists: {r['title']} [{scope}]")
                    continue
                if dry_run:
                    counts["rfp"] += 1
                    print(f"  + RFP (dry): {r['title']}  [{r['kind']}/{scope}]")
                    continue
                row = reference_pointers.create(
                    s, kind=r["kind"], title=r["title"], target=r["target"],
                    access_note=r.get("access_note"), body=r.get("body"), scope=scope,
                )
                counts["rfp"] += 1
                print(f"  + {row['identifier']}: {r['title']} [{scope}]")

            if dry_run:
                # Roll back any incidental state by raising out of the block would
                # abort; instead we simply never wrote (dry-run created nothing).
                print("\n(dry run — nothing written)")

    print(
        f"\n{'DRY-RUN would create' if dry_run else 'Created'}: "
        f"{counts['gvr']} GVR, {counts['prf']} PRF, {counts['lsn']} LSN, "
        f"{counts['rfp']} RFP, {counts['edges']} edges; "
        f"{counts['skipped']} already present."
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    args = ap.parse_args()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
