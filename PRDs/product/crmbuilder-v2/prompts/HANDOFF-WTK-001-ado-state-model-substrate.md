# Handoff — resume WTK-001 (ADO state-model substrate)

**For:** a fresh Claude Code session. **Engagement:** CRMBUILDER. **Author:** the
ADO design session (SES-137), 05-31-26.

You are resuming **WTK-001**, a single Work Task that is **`In Progress`** (claimed
by `CNV-039`). It is the first execution unit of **PI-114 "Build the Agent
Delivery Organization"** (chain: `PRJ-018 → PI-114 → WSK-001 (Development) →
WTK-001`). This is the *bootstrap* build — the ADO can't govern its own
construction yet, so you do this session-style, against the hand-made Work Task.

## 0. Orient first (read these)
- `CLAUDE.md` — the **PI-112 note** (the current Project/Workstream/Work-Task model).
- `specifications/governance-recording-rules.md` — the PI-112 banner + the rules.
- **`PRDs/product/crmbuilder-v2/agent-delivery-organization-design.md`** — the
  whole design; **§5 is the exact spec for this task**.
- Memory: the change_log-CHECK migration gotcha (`project_v2_changelog_check_migration_gotcha`).

## 1. Capture identifier heads FIRST
Two parallel-session identifier collisions happened this session (re-keyed at
cost). Before authoring any governance record, capture heads from the live API
(`/sessions`, `/conversations`, `/decisions`, `/planning-items`, `/work-tickets`,
`/workstreams`, `/work-tasks`, `/projects`) and re-key on any collision. Heads at
handoff (will advance — re-capture): SES-138, CNV-040, DEC-360, PI-115, WT-064,
PRJ-018, WSK-001, WTK-001, DEP-133.

## 2. The work (design §5 — substrate the ADO agents need)
All three in **one** Alembic migration (`0035`) + vocab + model + tests:

1. **Rename the Workstream phase `Design` → `Architecture`** —
   `WORKSTREAM_PHASE_TYPES` in `access/vocab.py`; rebuild `ck_workstream_phase_type`;
   data-rewrite any `workstream_phase_type='Design'` rows (none live now, but
   handle). Also update DEC-349's `Design` reference in the design doc/comments.
2. **Expand `WORKSTREAM_STATUSES`** from `{Planned, In Progress, Complete, Blocked}`
   to `{Planned, Scoping, Ready, In Progress, Complete, Not Applicable, Blocked}`;
   rebuild `ck_workstream_status`; update `WORKSTREAM_STATUS_TRANSITIONS`. Suggested
   transitions (refine per §5):
   - `Planned → {Scoping, Blocked}`; `Scoping → {Ready, Not Applicable, Blocked}`;
     `Ready → {In Progress, Blocked}`; `In Progress → {Complete, Blocked}`;
     `Blocked → {Scoping, Ready, In Progress, Planned}`; `Complete`/`Not Applicable` terminal.
   - Consider whether `Scoping`/`Ready`/`Not Applicable` need lifecycle timestamps
     in the repo's `_STATUS_TIMESTAMP` map (`access/repositories/workstreams.py`).
3. **Add `needs_attention` (bool, default false) + `needs_attention_reason` (text,
   nullable) to the `Workstream` model** (`access/models.py`) — the orthogonal
   human-escape flag (DEC-359), overlaying the status. Wire patch/update support
   in `access/repositories/workstreams.py` + the API schema/router.
   - **Open design call:** §5/DEC-359 says it "rolls up to the Planning Item."
     Decide: a *derived* rollup (a query / endpoint: "PIs with any needs_attention
     Workstream") vs a stored `needs_attention` column on the PI too. The derived
     route is lighter and avoids denormalization — recommend that unless you have
     a reason for a stored flag.

## 3. Migration + validation specifics
- Live DB: `crmbuilder-v2/data/engagements/CRMBUILDER.db` (`CRMBUILDER_V2_DB_PATH`),
  head **`0034`**. New migration is `0035`.
- This task does **not** add a new ENTITY_TYPE, so **no change_log CHECK rebuild**
  needed (unlike the 0034 gotcha). It rebuilds `ck_workstream_phase_type` +
  `ck_workstream_status` and adds two columns.
- Validate up/down on a **copy** of the live DB (catalog data is gitignored — the
  chain can't run from scratch), confirm schema parity with `create_all`, then
  apply to the live DB. The UI-supervised API holds the DB — stop it / let it
  respawn, or run alembic while it's idle (it worked idle for 0034).
- Existing `WSK-001` is `Development`/`In Progress` — unaffected by the rename
  (Development) or the status expansion (In Progress stays valid). No row-rewrite
  for it.
- Full v2 suite must stay green; add tests in
  `tests/crmbuilder_v2/access/test_workstream_phase.py` for the new statuses +
  transitions, the `Architecture` phase, and `needs_attention`.

## 4. Close out (the governed finish)
- Drive **WTK-001 → `Complete`** (and WSK-001 as appropriate; `In Progress` is fine
  until more of the Development phase lands).
- This is a **new session** (this design conversation was SES-137, already
  `complete`). Author a close-out recording the execution session + the commits,
  **addressing** PI-114 (NOT resolving — PI-114 has the decomposer, phase
  specialists, and PM/Lead orchestration still ahead). Belongs to **PRJ-018**.
- Re-claim WTK-001 under your conversation, or proceed noting `CNV-039`'s claim.

## 5. Environment / conventions
- Governance applies + snapshot commits happen **on `main`** (DEC-360, Model A).
  `main` is currently ~8 ahead of `origin/main` (Doug pushes; don't push unasked).
- A Work **Task** (`WTK-`) is resumed directly — its description *is* the kickoff;
  there is no `WT-` Work Ticket for it.
- After applying, regenerate db-export snapshots (`force_export`) and commit them
  with the code + migration + the close-out artifacts in the close-out commit.
