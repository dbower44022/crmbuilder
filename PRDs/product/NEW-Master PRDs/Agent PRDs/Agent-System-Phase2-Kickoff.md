# Agent System Redesign — Phase 2 Kickoff (Release Scheduler monitor + Ship Approval)

> **For a fresh Claude Code session.** This is a self-contained kickoff. Read the
> orientation, settle the design decisions with Doug **one at a time**, author the
> governance, then build. Today is the continuation of the Agent System Redesign
> (project **PRJ-041**). Phases 0, 1, 3, 4 are **done**; this is **Phase 2**.

---

## 0. Orient first (read these)

- `PRDs/product/NEW-Master PRDs/Agent PRDs/Agent-System-Implementation-Plan.md` §3 **Phase 2** (the sketch) + §6 (governance mapping).
- `Agent-System-Target-Model.md` §3 (Release Scheduler monitor / single-occupancy), §4.11 (**Ship Approval**, decision D13 — "the final human commit, symmetric to freeze").
- The CLAUDE.md "Governance is a precondition" + "Branch-work protocol (Model A)" sections.
- The DB is the source of truth: the v2 API is at `http://127.0.0.1:8765`, header `X-Engagement: CRMBUILDER`, envelope `{data, meta, errors}` (unwrap `.data`). `jq`/`sqlite3` are NOT installed — use `python3`.

**Verify state before starting:** `git log --oneline -1 origin/main`, and confirm Phase 4 landed: `PI-244..249` Resolved, `REQ-295` confirmed, and `crmbuilder-v2/src/crmbuilder_v2/access/release_orchestration.py` has `run_per_area_development` + `run_area_design`. The per-area back half (the model to mirror) is in `release_orchestration.py`, `release_signoffs.py`, and `scheduler/release_scheduler.py`.

---

## 1. What Phase 2 is

Two capabilities (per the implementation plan + target §3/§4.11):

1. **Release Scheduler monitor + single-occupancy arbitration** (EXTEND). Today the
   release scheduler (`crmbuilder_v2/scheduler/release_scheduler.py`,
   `ReleaseSchedulerConfig.release_identifier`) is pointed at **one** release. Phase 2
   adds a **monitor** that scans for **frozen** releases (those past freeze, ready to
   process) and runs each end-to-end; when several compete for the single dev lane it
   **arbitrates** (by `release_lane_order`, else raise `needs_human` rather than
   guess). The **single-occupancy gate already exists** —
   `releases._check_single_occupancy` (ready→development) + the partial unique index
   `uq_releases_one_in_lane` + `releases.lane_holder` / `coordination.lane_holder`.
   This PI adds the **scan + arbitration loop**, not a new gate.

2. **Ship Approval** (NEW). A human gate before `deployment → shipped`, **symmetric to
   freeze** (a human commits at both ends). Today `deployment → shipped` is gated only
   by `_check_revalidations_complete` (the reopen-cascade gate, PI-213). Add a human
   **ship sign-off** that the transition also requires.

**Mirror what already exists** — Ship Approval is the **same freshness-checked sign-off
pattern** used by Phase 1 (`PI-238`) and Phase 4c (`PI-246`):
`crmbuilder_v2/access/repositories/release_signoffs.py` + the
`RELEASE_SIGNOFF_STAGES` vocab. Adding a stage is: (a) add `"ship"` to
`RELEASE_SIGNOFF_STAGES`; (b) add a `"ship"` branch to `release_signoffs.stage_fingerprint`
(fingerprint the shippable state — e.g. the release's `qa_passed_at` + `test_passed_at`
+ the set of `artifact_versions` it introduced); (c) gate `deployment → shipped` on a
**fresh** ship sign-off (extend `_check_revalidations_complete` or add a composed gate
predicate in `releases._GATE_PREDICATES`); (d) record via the existing
`POST /releases/{id}/signoffs` (`stage=ship`) + `signoff-status` routes. This is
exactly how PI-246 added the `"design"` stage — read that commit (`ae06b73a`) as the
template.

For the scheduler monitor, study how `release_scheduler.main` / `anthropic_providers`
wire a single release today, and add a monitor entry point that lists candidates
(`releases.list_releases(status=...)`), orders by `release_lane_order`, and drives each
through `ReleaseScheduler(...).run()` honoring single-occupancy.

---

## 2. Proposed decomposition (settle with Doug, then author)

One requirement — **"frozen-release monitor + human Ship Approval"** — under topic
**TOP-012 "Scheduling"** (the monitor is scheduling) or split (Ship Approval could sit
under TOP-009 "Delivery Passes"); **ask Doug which topic(s)**. Implementing PIs under
**PRJ-041**:

- **PI (2a) — Ship Approval gate.** The `"ship"` sign-off stage + the
  `deployment → shipped` gate on a fresh ship sign-off. Small; mirrors PI-246. Add
  `POST /releases/{id}/signoffs stage=ship` already works once the stage is in vocab.
- **PI (2b) — Release Scheduler monitor + single-occupancy arbitration.** The scan +
  arbitration loop driving multiple frozen releases through the lane one at a time.

**Design decisions to settle with Doug (one at a time, before coding):**
1. **Topic(s)** for the requirement (Scheduling vs split Scheduling + Delivery Passes).
2. **What the Ship Approval reviews** (the fingerprint): the assembled release at
   `deployment` (qa+test passed + shipped artifact set)? Confirm the fingerprint inputs
   so a post-approval change re-opens approval (freshness, like PI-238/246).
3. **Monitor arbitration policy** when multiple frozen releases compete: strictly by
   `release_lane_order`; tie / no order → `needs_human` (don't guess). Confirm.
4. **Monitor scope**: does it also run the *front half* (reconciliation/arch-planning,
   which pause for human review) or only pick up releases already `ready`/in-lane?
   (Likely: monitor scans `ready` + lane releases and drives the lane; the front-half
   reviews are human-paced.) Confirm with Doug.

---

## 3. Governance — the binding precondition (do this BEFORE any code)

Per CLAUDE.md, no code until a **confirmed requirement** + an **implementing PI** exist.
Author via **direct API POST** (real-time governance, DEC-383 — Claude Code does NOT
batch into close-out JSON). Mechanics (all gotchas hit this session):

1. **Conversation** under the session: `POST /conversations` needs an **explicit
   `conversation_identifier`** (get `GET /conversations/next-identifier`) **and inline
   `references`** for `conversation_belongs_to_session` (+ optionally
   `conversation_belongs_to_topic`). Use the current session `SES-217` or create a new
   `session` (medium `chat`, with an inline `session_belongs_to_project → PRJ-041` edge).
2. **Requirement**: `POST /requirements` — **omit the identifier** (server-assigns; it
   *rejects* an identifier field). Fields: `requirement_name` (the statement),
   `requirement_description`, `requirement_acceptance_summary`, `requirement_origin:
   "human_defined"`, `requirement_priority: "should"`. **Readability gate (enforced at
   approval):** `requirement_description` must be **≤ 75 words, ≤ 4 sentences**, no
   embedded identifiers (no `PI-`/`DEC-`…), no history words. Validate BEFORE asking
   Doug to approve: run `crmbuilder_v2.access.readability.validate_requirement_readability`.
   Then attach provenance via `POST /references`:
   `requirement_belongs_to_topic` + `requirement_defined_in_conversation`.
3. **PIs**: `POST /planning-items` — omit identifier; **`status:"Draft"`**,
   **`executive_summary` 200–800 chars** (both required), `item_type:"pending_work"`,
   `execution_mode:"interactive"` (hand-built, keeps the autonomous fleet off them).
   Then `POST /references`: `planning_item_belongs_to_project → PRJ-041` +
   `planning_item_implements_requirement → REQ-NNN`.
4. **Doug approves the requirement** in the desktop **Requirements Review** panel (he
   refreshes first — the panel doesn't auto-refresh). **KNOWN GOTCHA:** the stale
   running API sometimes records the approving decision (`requirement_approved_by_decision`
   edge + `DEC-NNN` "Approve REQ-NNN") but **does not flip the status to `confirmed`**.
   If `requirement_status` stays `candidate` with the edge present, apply the recorded
   decision via the current code (NOT a status edit):
   ```
   CRMBUILDER_V2_DB_PATH=$PWD/crmbuilder-v2/data/v2-unified.db uv run python3 -c "
   from crmbuilder_v2.access.db import session_scope
   from crmbuilder_v2.access.engagement_scope import active_engagement
   from crmbuilder_v2.access.repositories import requirement
   with active_engagement('ENG-001'), session_scope() as s:
       print(requirement.activate_by_decision(s, 'REQ-NNN'))"
   ```
   (Legit: the edge is the human's authorization; `activate_by_decision` re-checks all
   gates.) Only build once `requirement_status == "confirmed"`.

---

## 4. Build conventions + hard-won gotchas (READ — they will bite you)

- **A parallel agent is active on the shared working tree** and repeatedly hijacks
  HEAD (it has built `pi-243/252/253` — publish service, WAL mode, etc.). It can
  `reset` and discard uncommitted work. **Build each PI in a DEDICATED git worktree**,
  never on the main checkout:
  ```
  git fetch origin
  git worktree add /home/doug/crmbuilder-<pi> -b pi-<n> origin/main
  cd /home/doug/crmbuilder-<pi> && uv sync   # own venv, warm cache = seconds
  # ...edit/test/commit ALL in the worktree (its HEAD can't be hijacked)...
  ```
- **Reconcile to main without touching the contested tree:** in the worktree,
  `git fetch origin`, `git rebase origin/main` (the parallel agent's work is V1/
  infra — disjoint from `crmbuilder_v2`, so rebases are clean), then
  `git push origin pi-<n>:main` (FF push to the main ref — **do NOT `git checkout
  main`** in the shared tree; `git branch -f main` fails when it's checked out).
  Then `git worktree remove --force` + `git branch -d`.
- **Commit with explicit pathspec** (`git commit -F msg -- <files>`), `git add` new
  files first. Never a bare `git commit` (the parallel agent stages junk on the tree).
  Commit-message footer (per CLAUDE.md):
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` + the
  `Claude-Session:` line.
- **The access layer must NOT import the scheduler** (layering). The per-area drivers
  pass run-status as plain strings (`"succeeded"`/`"needs_human"`/`"failed"`) for this
  reason — keep that.
- **Dual-head migrations** if you add schema: SQLite chain `crmbuilder-v2/migrations/
  versions/00NN_*` (current head ~`0078`) + PG `crmbuilder-v2/migrations/pg/versions/
  00MM_*` (head ~`0035`). **Tables are created model-based** (`X.__table__.create(...,
  checkfirst=True)`), so a new column on an existing table that the model owns means
  the table-create migration already has it on the chain — a back-fill `ADD COLUMN`
  migration must be **guarded** (skip if column exists) with a **NO-OP downgrade**
  (SQLite can't DROP a CHECK'd column). Ship Approval likely needs **no schema** (it
  reuses `release_signoffs`); the monitor needs none. If you add a `release_signoffs`
  stage, that's vocab-only (no migration).
- **Live DB:** after merge, apply any schema delta directly to
  `crmbuilder-v2/data/v2-unified.db` (it's create_all/delta-managed). Seeding/inserts
  that touch `change_log` need an engagement context — wrap in
  `active_engagement('ENG-001')`.
- **Resolve a PI** when its delivering work merges: `POST /references`
  `{source_type:"conversation", source_id:"CNV-NNN", target_type:"planning_item",
  target_id:"PI-NNN", relationship:"resolves"}` (atomic flip to Resolved). The API
  occasionally returns an empty body (transient) — **retry**.
- **Tests:** `QT_QPA_PLATFORM=offscreen uv run pytest <paths> -q`. Run the blast
  radius + `tests/crmbuilder_v2/migration` if you touch schema. `ruff check --fix`
  for import-sort; `UP042` (str+Enum) is a pre-existing project pattern — ignore it.
  Mirror the test style of `tests/crmbuilder_v2/access/test_design_review.py` (Ship
  Approval) and `tests/crmbuilder_v2/scheduler/test_release_scheduler*.py` (monitor).

---

## 5. Verification (per the plan)

- **Ship Approval:** `deployment → shipped` is blocked until a fresh ship sign-off
  exists; a change after sign-off re-opens approval (freshness); record + advance works.
- **Monitor:** two frozen releases → only one enters the lane (single-occupancy);
  the other waits; ambiguous order → `needs_human`. A monitor pass drives an eligible
  release through the lane.
- Full suite stays green: `QT_QPA_PLATFORM=offscreen uv run pytest tests/crmbuilder_v2 -q`
  (~35 min; the baseline is all-green — if you see failures in `migration/test_0038`
  or `scripts/test_orchestrator_*`, check they're not pre-existing/unrelated before
  blaming your change).

---

## 6. Working style (Doug's standing preferences)

- **One issue at a time** in design — bring each decision singly and discuss; don't
  batch. When Doug asks a question, answer it — don't make edits unless asked.
- Record governance in **real time** via API as it happens.
- Update the memory file `project_agent_system_target_model.md` as Phase 2 progresses
  (and `MEMORY.md` index if adding new memories).
- Keep terminology in the glossary; no new term without Doug's approval (it's
  "scheduler", never "runtime").

When done: both PIs Resolved, the requirement confirmed, merged to `origin/main`.
The remaining redesign work after Phase 2 is **Phase 5** (cutover: flip the
`release_back_half` default to `per_area`, retire the per-PI path, drop the flag) +
the operator-run live real-agent `per_area` release validation.
