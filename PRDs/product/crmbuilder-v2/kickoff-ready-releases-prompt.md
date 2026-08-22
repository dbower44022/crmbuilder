# Kick-Off-All-Ready-Releases — new-session handoff prompt (BUILD BATCH)

**Purpose:** take every V2 release that is **ready to build** and *start its
development* — freeze it, drive it through the autonomous pipeline stages as far
as it can go on its own, and leave it either building, queued, or cleanly parked
at a human review gate. This is the build batch that follows the 2026-06-28 open-
release triage (see `open-release-triage-report-2026-06-28.md`). Engagement
`ENG-001` (`X-Engagement: CRMBUILDER`), API `127.0.0.1:8765`. Authored 2026-06-28.

---

## 0. The three hard rules

1. **Never sign a human review gate.** Reaching `shipped` requires *fresh human
   sign-offs* at **reconciliation** and **architecture_planning** (and a **ship**
   approval). Those are Doug's. The scheduler/driver must **stop** at each gate and
   surface it — **never auto-record a sign-off**, never hand-author one to get
   past the gate. (This is the exact line PI-361 was built to protect.)
2. **One release in the lane at a time.** The development→deployment lane is
   single-occupancy (REQ-189). You may *freeze and advance many* releases in
   parallel up to `ready`, but only one may hold the dev lane. Set
   `release_lane_order` to sequence the rest; don't force a second into the lane.
3. **Requirement-first is already satisfied** for every eligible release (all open
   PIs confirmed-req — that's what "ready" means). Do **not** build anything whose
   requirement isn't confirmed. If you find a "ready" release with an unconfirmed
   or missing requirement, it is **not** eligible — leave it for triage.

---

## 0.5 FIRST ACTION — sweep for stranded lane occupants

Before anything else, **sweep the single-occupancy dev lane for a done-but-stranded
release** and clear it, or the whole batch stays blocked behind it. An orchestrator
that builds a release's work but exits without driving the release out of the lane
leaves it parked in a lane state (`development`/`qa`/`testing`/`deployment`) holding
the lane — silently blocking every other release (REL-007 was exactly this on
2026-06-28: both PIs Resolved, no process running, parked at `development`).

Procedure: `GET /releases?limit=200`, find any release whose status is in
`{development, qa, testing, deployment}` with **no running scheduler/agent process**
(`ps`), **work delivered** (its PIs `Resolved`, commits on `main`), and a stale
`release_updated_at`. For each such release: run its tests, record the truthful
`qa-pass`/`test-pass`, advance it to `deployment`, and **stop at the human ship
sign-off** (never auto-sign — `deployment → shipped` is the operator's gate). Only
once the lane is **shipped** clear (terminal) can the next release enter it. Do
**not** force a second release into a held lane — the access layer 409s, by design.

## 1. Orient first

- Read this repo's `CLAUDE.md` Tier-2 (the v2 governance + release-pipeline +
  ADO + branch-protocol sections) and `open-release-triage-report-2026-06-28.md`.
- Read the driver you'll use: `crmbuilder-v2/src/crmbuilder_v2/scheduler/release_scheduler.py`
  (`ReleaseScheduler` walks a *frozen* release reconciliation→architecture→ready
  on LLM providers, pausing at gates), `release_monitor.py`, and the ADO runtime
  for the dev lane. Design: `PRDs/product/NEW-Master PRDs/Agent PRDs/Archive/`
  (release-pipeline + ADO docs) and `production... / multi-agent-release-pipeline`.
- **Check the live hot edge** (most-recently-updated PIs/releases) at start — the
  backlog churns by the minute (releases are created/shipped during a single
  session). Anything being actively worked by a parallel orchestrator is **read-
  only** to you.

## 2. Re-derive the eligible set LIVE (do not trust any snapshot)

`GET /releases?limit=200`, drop terminal (`shipped, cancelled, superseded,
delivered_off_pipeline`). A release is **eligible** iff **all** of:
- it has ≥1 **open** PI (`Draft/Ready/In Progress/In Review`), and
- **every** open PI has a **confirmed** requirement
  (`planning_item_implements_requirement → requirement.requirement_status == confirmed`), and
- it is **not** on the exclusion list below.

**Exclusions — do NOT build these even if they look "ready":**
- **REL-013** (Master CRMBuilder PRD consolidation + dogfood) — Doug's explicit
  decision: it stays a **human-led dogfood track**, out of the agent batch. Its
  requirements are confirmed, so the ready-heuristic *will* surface it — skip it.
- **Parked** releases — **REL-035** (role-aware security, no platform write path)
  and **REL-018** (upstream-blocked connector). Leave parked.
- Any release a parallel session is actively driving (hot edge).

**Snapshot at authoring time (RE-DERIVE — this will have changed):** eligible
automated ≈ REL-010, REL-011, REL-012, REL-016, REL-017, REL-021, REL-022,
REL-034, REL-038, REL-039, REL-040; eligible **manual** ≈ REL-036, REL-042.
REL-013 is in the ready-heuristic but **excluded** per above.

## 3. Procedure per release (branch by `release_execution_mode`)

**Automated releases** — drive via the release substrate, in this order:
1. **Freeze** if pre-freeze (`preliminary_planning → development_planning →
   reconciliation`). Freeze closes scope (REQ-226); only freeze when scope is
   final (true for eligible releases). Already-`reconciliation`/`ready` releases
   are past freeze.
2. **Advance** through `reconciliation → architecture_planning → ready` with the
   `ReleaseScheduler` (it authors demands + decomposition via providers and calls
   the deterministic stage drivers). It **pauses at the reconciliation and
   architecture human gates** — confirm it does, and **stop there**, recording the
   gate as awaiting-Doug. Do not advance past a gate yourself.
3. **Dev lane** (`ready → development → …`): the ADO runtime builds the work
   tasks under the release gates. Only the **single** lane-occupant runs; order
   the rest with `release_lane_order` and `blocked_by`. Agents **must** spawn from
   current `main` HEAD (stale-HEAD = building on old code).

**Manual releases** (`release_execution_mode == manual`) — these are hand-built by
a human/Claude-Code session (the PI-361 pattern: requirement→code→tests→commit→
merge→resolve), with decomposition + qa/test-on-driver-stamps skipped and auto-
ship when all in-scope PIs resolve. You may hand-drive a small one end-to-end, or
**list it for Doug to sequence** — don't push a manual release through the agent
scheduler.

## 4. Hard-won gotchas (from the PI-361 build — heed these)

- **A vocab value used in a DB CHECK needs a migration**, not just a vocab edit.
  Grep `models.py` `__table_args__`, not only the column def. Tests pass via
  `create_all` while the live DB 500s — the classic trap.
- **Always copy-verify a live-DB schema change first.** Copy `v2-unified.db`, run
  `crmbuilder-v2-bootstrap-db` against the copy, inspect (CHECKs, partial indexes'
  `WHERE`, row counts, `PRAGMA integrity_check`). SQLite batch reflection silently
  drops partial-index predicates and sibling CHECKs. Then back up live and apply.
- **Restart the API to load new code/vocab** (the standalone `crmbuilder-v2-api`
  caches code at startup); a schema change additionally needs `bootstrap-db`.
- **Shared working dir is volatile.** Parallel orchestrators switch HEAD out from
  under you. After **every** commit, verify `git branch --show-current` and check
  `git reflog`; commit with explicit pathspec. Branch per the Model A protocol; in
  Claude Code, **you commit, Doug pushes**.

## 5. Governance (real-time, DEC-383)

Open one session (`chat`, `session_belongs_to_project`) at start; record each
freeze/lane/gate decision in real time via direct API POST. Resolve a PI only via
its delivering conversation's `resolves` edge. Read `TOP-013` before authoring
governance records.

## 6. Deliverable — the status report

One markdown report, a row per eligible release:
1. **Building now** — the lane occupant(s) and what's dispatched.
2. **Frozen & queued** — advanced to `ready`/awaiting the lane, with lane order.
3. **Awaiting Doug** — parked at a reconciliation/architecture/ship **human gate**;
   name the exact sign-off needed.
4. **Manual track** — manual-mode releases, hand-driven or listed for sequencing.
5. **Skipped** — excluded (REL-013 human-led, parked, hot-parallel) with the reason.

The only things left on Doug's plate should be the **human review sign-offs** and
any genuine design fork you couldn't resolve. Build what's buildable; never fake a
gate.
