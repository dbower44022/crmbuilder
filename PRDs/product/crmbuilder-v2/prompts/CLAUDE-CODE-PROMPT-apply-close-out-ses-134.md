# Apply close-out — SES-134 / CNV-036 (PI-112 build closure)

**Session:** SES-134 (Claude Code, implementation). **Conversation:** CNV-036.
**Parent Project:** PRJ-014 (Governance & Delivery Redesign — renamed from WS-014
in Phase 1). **Opened against:** WT-063 (consumed by this close-out).
**Follows from:** SES-133.

## What this close-out records

The build closure for **PI-112** — the governance & delivery model migration.
Ingests the **12 phase commits** (Phase 0 plan through Phase 4b), **resolves
PI-112** (Draft → Resolved), and **consumes WT-063**
(`session_opens_against_work_ticket`, ready → consumed). **No new decisions** —
DEC-340..349 were recorded in SES-132 / SES-133.

Phases delivered (each test-green with a reversible Alembic migration validated
on a copy of the live engagement DB, then applied to it):

- **1a/1b** — rename `workstream` → Project, `WS-` → `PRJ-` (code + migration `0027`)
- **2** — two-tier area model: System areas + layer ranks, per-engagement
  Engagement areas (migration `0028`)
- **3** — Planning Item six-state lifecycle (migration `0029`)
- **4a** — delivery-phase **Workstream** entity `WSK-` (migration `0031`)
- **4b** — single-area **Work Task** entity `WTK-` + relocated `area`
  (migration `0032`)

A concurrent session added `0030_changelog` (a Phase-1 follow-on migrating
`change_log` `workstream`→`project`) mid-run; ours chained as `0031`/`0032`.

**Deferred:** dropping the now-redundant `planning_item.area` column — its only
reader is the shelved WS-012 orchestrator (DEC-344); that cleanup belongs to the
orchestrator's retirement (target-model §9 step 6).

## Pre-flight / environment

- Live engagement DB: `crmbuilder-v2/data/engagements/CRMBUILDER.db`
  (`CRMBUILDER_V2_DB_PATH`), at migration `0032`.
- The API must run **branch code** (it serves `/workstreams`, `/work-tasks`).
  The stale Phase-1 API was restarted before applying.
- Heads at author time: next SES-134, CNV-036, DEC-350 (no new decisions used).

## One pre-step fix

`apply_close_out.py` hoists the mandatory session-membership edge by kind. Phase 1
renamed `session_belongs_to_workstream` → `session_belongs_to_project`; the script
(in `scripts/`, untouched by the Phase-1 src rename) was updated to the new kind
in this commit, else the SES-134 POST fails `missing_project_membership_edge`.

## Apply command

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_134.json
```

## Post-apply verification (observed)

- 18 operations: CNV-036, SES-134, 12 commits, 3 references, resolve PI-112.
- `PI-112` status → **Resolved**; `WT-063` → **consumed**;
  `SES-134 --session_belongs_to_project--> PRJ-014`.
- Recorded as **deposit_event DEP-127**; log `deposit-event-logs/dep_127.log`.
- db-export snapshots regenerated; committed with the payload, this prompt, the
  `dep_127.log`, and the `apply_close_out.py` kind fix.
