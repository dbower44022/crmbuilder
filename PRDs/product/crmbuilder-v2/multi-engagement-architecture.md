# Multi-Engagement Architecture — v0.5

**Last Updated:** 05-16-26 19:00
**Status:** Draft v1.0 — produced by v0.5 Conversation 1
**Position in workstream:** Sole architecture+schema conversation of the v0.5 engagement-management workstream
**Predecessor conversation:** SES-025 (v0.5 orientation; produced the workstream plan)
**Companion document:** `methodology-schema-specs/engagement.md` (this conversation's other deliverable)
**Successor conversation:** v0.5 Conversation 2 — build planning

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-16-26 19:00 | Doug Bower / Claude (SES-026) | Initial draft. Produced by v0.5 Conversation 1, which combined multi-engagement architecture design with engagement schema design because the two were tightly coupled. Settles the ten architectural questions catalogued in the v0.5 workstream plan §6. |

---

## Change Log

**Version 1.0 (05-16-26 19:00):** Initial creation. Operationalises DEC-039's "one v2 instance per engagement" finding into a designed feature: a bootstrap meta DB hosts engagement records and serves as the registry; per-engagement SQLite files live in the engine repo under a `data/engagements/{code}.db` convention; active state persists via a small JSON file plus an in-memory `ActiveEngagementContext`; the API and MCP servers run one-process-per-engagement at v0.5, with a committed migration to multi-tenant when v2 transitions from prototype to production; governance and methodology identifiers scope per-engagement (CBM's first session is `SES-001`, not `SES-026`); migrations apply lazily at engagement-open; the existing `crmbuilder-v2/data/v2.db` retrofits cleanly into `data/engagements/CRMBUILDER.db` via a one-shot explicit migration; exports split (dogfood in engine repo, client engagements in client repo) via an `engagement_export_dir` field on the engagement record; the engagement record lives as a row in the meta DB. Nine decisions produced; one new planning item (multi-tenant migration) authored.

---

## 1. Purpose

This document specifies the multi-engagement routing architecture v2 ships in v0.5. It is the operational mechanism that DEC-039's "one v2 instance per engagement, separate SQLite, separate API port" finding was explicitly framed as needing — a finding rather than a designed feature — plus the dogfood-migration path that retrofits v0.4's existing `crmbuilder-v2/data/v2.db` cleanly into the new model.

It is not a build plan. The build planning conversation (v0.5 Conversation 2) takes this document and its companion (`methodology-schema-specs/engagement.md`) as inputs and produces the v0.5 PRD, the implementation plan, and the slice build prompts.

It is not a styling design pass. The PI-001 styling workstream runs in parallel per DEC-076. The one coupling point — the engagement panel's visual treatment — inherits whatever design tokens are current when v0.5's Slice B lands. This document specifies the engagement panel's information architecture and behavior, not its visual treatment.

---

## 2. Position in workstream

This document and `methodology-schema-specs/engagement.md` are the two deliverables produced by v0.5 Conversation 1. They are combined into one conversation because architecture and schema are tightly coupled: whether the engagement record carries explicit path fields depends on routing decisions, and whether routing decisions need engagement-level metadata depends on the schema shape. Splitting them creates a circular dependency on the first design question.

The workstream is governed by `v0.5-engagement-management-workstream-plan.md`. The next conversation in the workstream (v0.5 Conversation 2) opens against a build-planning kickoff and produces:

- `ui-PRD-v0.5.md` — release PRD, same shape as `ui-PRD-v0.4.md`
- `ui-v0.5-implementation-plan.md` — slice breakdown
- Slice build prompts at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-{A..*}-*.md`

Strawman slices from the workstream plan (final count decided in Conversation 2):

- **Slice A — Foundation.** Multi-engagement config layer, `ActiveEngagementContext`, bootstrap discovery, alembic-per-engagement application logic, dogfood migration (`v2.db` → `engagements/CRMBUILDER.db`).
- **Slice B — `engagement` entity panel.** CRUD via v0.4's ListDetailPanel pattern; switching UI affordance.
- **Slice C — Engagement switching.** Desktop picker UI, switching mechanism, API server reconnection, signals when active engagement changes.
- **Slice D — Closeout.** Version bump to 0.5.0, README release note, session record drafts.

---

## 3. Architectural decisions

The ten architectural questions from the workstream plan §6 are each settled below. Each subsection records the question, the chosen option, the rationale in summary, and the implementation implications. Detailed rationales and alternatives-considered notes for each are recorded as DEC-NNN records at this conversation's close.

### 3.1 Engagement discovery model — bootstrap meta DB (Q1)

**Decision.** A small separate SQLite file at a fixed path (`crmbuilder-v2/data/engagements.db`) hosts an `engagements` registry table. Creating a new engagement does two writes: INSERT into the meta DB and create the corresponding per-engagement DB file. Discovery is a SELECT against the meta DB. (See DEC-078.)

**Why.** Separates routing metadata ("what engagements exist on this machine") from methodology content ("what's inside an engagement"). Mirrors v1's master-DB pattern, which has held up across two years of v1 evolution. Carries metadata outside any single engagement's DB so engagement records remain focused on the engagement itself rather than mixing in routing fields. Supports operations on inactive engagements (list, rename, archive) without opening each DB.

**Sub-question resolved.** The engagement record IS the meta DB row. The meta DB is not a lightweight pointer to engagement records that live inside each per-engagement DB; it is the canonical home. Reasons: simpler; routing metadata belongs at the v2-install level; avoids the awkward self-referential case of "the engagement record about engagement X lives inside engagement X's DB."

**Implementation implications.**

- Meta DB path: `crmbuilder-v2/data/engagements.db` (fixed, gitignored).
- Meta DB has its own Alembic chain, separate from per-engagement chains.
- Engagement CRUD endpoints (`/engagements/*`) read and write the meta DB exclusively.
- Drift mode (a per-engagement DB file moved or deleted out-of-band): handled by a reachability check at activation time, mirroring v1's `automation/core/client_reachability.py` pattern.

### 3.2 Per-engagement DB file location — engine repo, conventional paths (Q2)

**Decision.** All per-engagement DB files live at `crmbuilder-v2/data/engagements/{engagement_code}.db` in the engine repo, gitignored. The engagement record carries no path field. Dogfood DB after migration is `crmbuilder-v2/data/engagements/CRMBUILDER.db`; CBM's will be `crmbuilder-v2/data/engagements/CBM.db`. (See DEC-079.)

**Why.** Minimum viable for v0.5; handles both dogfood and CBM cleanly. v1's split (engine DB in engine repo, per-client DBs in `{project_folder}/.crmbuilder/{code}.db`) is real precedent worth respecting, but adopting it now adds an engagement-record path field and a coupling to client-repo structure that v0.5's known use cases don't require.

**Implementation implications.**

- `.gitignore` gains `crmbuilder-v2/data/engagements/`.
- Filename derived from `engagement_code` (uppercase per the constraint inherited from v1's `Client.code`).
- No `engagement_db_path` field on the engagement record in v0.5.
- Future migration (v0.6+ candidate, not committed) adds nullable `engagement_db_path` if/when an engagement needs to travel with a client repo. Nullable means convention; set means the override path is used. Existing rows stay null.

### 3.3 Active-engagement state persistence — JSON file plus in-memory context (Q3)

**Decision.** Two distinct facts are persisted in two distinct places:

- **Live state — "what is the engine pointing at right now."** A small JSON file at `crmbuilder-v2/data/current_engagement.json` holds `{"engagement_identifier": "<ENG-NNN>", "engagement_code": "<CODE>", "set_at": "<ISO 8601 UTC>"}`. The desktop app maintains an in-memory `ActiveEngagementContext` (QObject with an `active_engagement_changed(object)` Qt signal) mirroring v1's `ActiveClientContext`. The file is the cross-restart persistence; the in-memory context is the live state during desktop runtime.
- **Ordering — "when was each engagement last opened."** A `last_opened_at` DATETIME column on the meta DB `engagements` table, updated on activation. Used by the picker UX to surface recent engagements first and as the source for "restore last-active" on app launch.

(See DEC-080.)

**Why.** Mirrors v1's hybrid pattern (`Client.last_opened_at` for ordering plus `last_selected_client_id` in preferences for the live pointer) which has held up over two years. JSON file affords external peek/curl access without an extra API endpoint. Separation of concerns matches the underlying reality: ordering is per-engagement metadata; live pointer is a singleton at the v2-install level.

**Implementation implications.**

- `crmbuilder-v2/data/current_engagement.json` added to `.gitignore`.
- `engagements.last_opened_at` column added to the meta DB schema (DATETIME, nullable).
- Activation sequence (described fully in §5):
  1. Reachability check on the engagement's DB file.
  2. Close API/MCP subprocess connections.
  3. Write `current_engagement.json`.
  4. PATCH `engagement_last_opened_at` via the meta DB.
  5. Update in-memory `ActiveEngagementContext`.
  6. Emit `active_engagement_changed` Qt signal.
  7. Launch new API/MCP subprocesses with `CRMBUILDER_V2_DB_PATH` set to the new engagement's path.
- Drift recovery on app launch: if `current_engagement.json` references an engagement that doesn't exist in the meta DB or whose DB file is missing, the context starts empty and the picker UX prompts for selection. No silent fallback to a different engagement.

### 3.4 API and MCP server model — one process per engagement at v0.5; multi-tenant target (Q4, Q9)

**Decision for v0.5.** One API subprocess per engagement, bound at spawn via `CRMBUILDER_V2_DB_PATH`. Switching engagements is a kill-and-relaunch dance owned by the desktop app. The API server's code is unchanged from v0.4 — no concept of engagement, no request-routing layer, no per-request DB selection. The MCP server has the same lifecycle: one MCP subprocess per engagement, killed and relaunched on switch.

**Decision for the longer term.** Multi-tenant single-process server is the target architecture. The migration from one-process-per-engagement to multi-tenant is committed; it lands when v2 transitions from prototype to production (anchoring PI-017). The trigger is the prototype-to-production transition, not a friction signal — this is a planned transition, not a deferred-with-friction-trigger pattern.

(See DEC-081.)

**Why for v0.5.** v0.5's scope is "make multiple engagements possible," not "redesign the API layer." One-process-per-engagement delivers the former without doing the latter. The API server code stays as-shipped in v0.4; all engagement-routing complexity lives in the desktop's launcher and switcher logic, which is where new code is going anyway. Consistent with DEC-039's original framing.

**Why a committed migration rather than open-ended deferral.** The kill-relaunch dance is intentional for the v0.x prototype phase but inappropriate for production. Cross-engagement queries, dashboards across engagements, and mid-flight switching all become desirable as v2 stabilises. Committing to the migration at the prototype-to-production transition avoids the PI-001 anti-pattern (friction triggers that never fire) while keeping the v0.5 scope bounded.

**Implementation implications for v0.5.**

- Port assignment: stays at 8765. Only one engagement reachable at a time means only one port is needed.
- Desktop owns the API and MCP subprocess lifecycle (already true for the API per DEC-023). On engagement switch, the desktop:
  1. Sends SIGTERM to both subprocesses.
  2. Waits for port 8765 release (with timeout).
  3. Launches new subprocesses with the new env.
  4. Polls `/health` with backoff until 200 OK (or timeout).
  5. Refreshes panels (they re-fetch from the API against the new engagement).
- During the switch, the desktop shows a "Switching engagement..." indicator or disabled state; gestures are either queued or rejected (Conversation 2's Slice C call).
- The env-var override in `config.py` stays put. External tools can still set `CRMBUILDER_V2_DB_PATH` and `CRMBUILDER_V2_API_PORT` to point at a specific engagement without going through the desktop launcher.

**Implementation implications for the future migration (PI-017).**

- Refactor every endpoint to accept engagement context via header (`X-Engagement: ENG-NNN`) or path-prefix (`/v1/engagements/ENG-NNN/sessions`).
- Refactor access-layer connection management to hold per-engagement connections.
- Refactor tests for engagement-context fixtures.
- Reshape MCP server to mirror the API's multi-tenant shape (engagement context in tool inputs or a per-tool engagement selector).
- Remove the kill-relaunch dance from the desktop's engagement-switch path.

### 3.5 Identifier scope — per-engagement governance and methodology; engagement identifiers scoped to meta DB (Q5)

**Decision.** Governance and methodology identifiers (`SES-NNN`, `DEC-NNN`, `PI-NNN`, `RSK-NNN`, `TOP-NNN`, `REF-NNN`, `CHR-NNN`, `STA-NNN`, `DOM-NNN`, `ENT-NNN`, `PROC-NNN`, `CRMC-NNN`) scope per-engagement. Each engagement's DB has its own identifier sequences; CBM's first session is `SES-001` within the CBM engagement, independent of the dogfood's `SES-025+`. Engagement identifiers (`ENG-NNN`) scope to the meta DB — one sequence per v2 install. (See DEC-082.)

**Why.** Per-engagement scope for governance/methodology identifiers is the only sane choice for review/auditability: CBM Phase 1 starting at `SES-025` because the dogfood happened to have 24 prior sessions is absurd. Engagement identifiers naturally scope to the meta DB because that is where engagement records live. No v0.5 helper changes needed — the v0.4 next-identifier helpers query the active DB connection, so the helpers naturally return per-engagement sequences once each engagement is a separate connection target.

**Implementation implications.**

- The meta DB has its own next-identifier helper (`GET /engagements/next-identifier`) following the v0.4 pattern.
- All other next-identifier helpers (per the v0.4 retrofit from DEC-068 slice A) continue to query the active DB connection without modification.
- Identifier collisions across engagements don't matter: engagement A's `DEC-001` and engagement B's `DEC-001` are distinct decisions in distinct engagements, related only by external context (which engagement was active).

### 3.6 Migrations across engagements — lazy at engagement-open (Q6)

**Decision.** When an engagement is activated, the desktop launcher runs `alembic upgrade head` against that engagement's DB before spawning the API subprocess. Engagements that are never opened never get migrated; engagements that are opened after a long pause apply pending migrations at activation. Mirrors v1's `run_client_migrations` pattern. (See DEC-083.)

**Why.** Matches v1's proven pattern. Defers work to when it's actually needed; never-opened engagements pay no cost. Failure modes are scoped to one engagement at a time — a broken migration affects activation of one engagement, not the entire v2 install or all engagements at startup. Eager-at-launch would create correlated failure risk and pay cost for engagements the user isn't using.

**Implementation implications.**

- A helper analogous to v1's `run_client_migrations` lives at the engine entrypoint and runs at engagement activation.
- The activation UX shows a "Upgrading engagement database..." indicator when migrations are running; for a current engagement, activation is nearly free.
- Each engagement's `alembic_version` table tracks its own head; no cross-engagement coupling.
- Forward-only migrations: same posture as v0.4. Rollback exists as emergency lever, not a normal-operation tool.
- The meta DB has its own Alembic chain. Meta-DB migrations apply at desktop launch (before any engagement is listable). Failure to migrate the meta DB is a hard-fail UX — the engine can't operate without the registry.
- Acceptance criterion shape (Conversation 2 to translate to test cases): "Open a stale engagement DB with a newer codebase; activation applies pending migrations; engagement opens with schema at head."

### 3.7 Dogfood migration — one-shot explicit (Q7)

**Decision.** A one-shot explicit migration runs at v0.5 first launch (when the engine detects an existing `crmbuilder-v2/data/v2.db` and a missing or empty meta DB). The migration is idempotent on rerun. Operations:

1. Backup `v2.db` to `crmbuilder-v2/data/v2.db.pre-v0.5-backup` (left in place; user can delete manually after confirming v0.5 works).
2. Create the meta DB at `crmbuilder-v2/data/engagements.db` and run its initial Alembic migration to head.
3. INSERT the CRMBUILDER engagement row (field values per §3.10 / `engagement.md`).
4. Copy `v2.db` to `crmbuilder-v2/data/engagements/CRMBUILDER.db`.
5. Open the new path; verify by querying expected row counts (`sessions`, `decisions`, `planning_items`, `refs`, `change_log`, `charter`, `status`, `base_entity_catalog`); each count must match the source.
6. Delete the original `v2.db` (the `.pre-v0.5-backup` copy remains).
7. Refresh the JSON snapshots at `PRDs/product/crmbuilder-v2/db-export/` from the new path.

(See DEC-084.)

**Why.** Q2 chose convention; Q7 respects Q2's choice rather than carve out a permanent exception. The dogfood deserves the same convention every future engagement gets — both for consistency and because every line of "is this the dogfood path or the new path?" logic is debt the codebase pays forever. The migration is a one-time cost; the alternative special-case paths are a forever cost.

**Implementation implications.**

- The migration lives as a self-contained module in the engine, invoked by the launcher at first-launch detection of the migration-needed state.
- Slice placement (Slice A foundation versus a dedicated migration slice) is explicitly a Conversation 2 question per the workstream plan §10.
- Failure recovery: if any step fails, the `.pre-v0.5-backup` file is the recovery point. The user is told to revert by deleting the new files and reverting code to the prior v2 release.
- Three install scenarios:
  - **Existing v2 install (has `v2.db`):** migration runs as described above.
  - **Fresh install (no `v2.db`):** no migration; the meta DB is created empty and the first-launch UX guides creating engagements explicitly.
  - **Rerun after successful migration:** the migration detects the already-migrated state (meta DB exists with a CRMBUILDER row pointing at an existing `engagements/CRMBUILDER.db`, and no `v2.db` at old path) and exits cleanly.

### 3.8 Per-engagement exports — split via `engagement_export_dir` (Q8)

**Decision.** Exports for each engagement land where the engagement's other documents live. The engagement record carries a nullable `engagement_export_dir` column (absolute filesystem path) on the meta DB. Dogfood's value is set by the v0.5 migration to the absolute path of `PRDs/product/crmbuilder-v2/db-export/` (computed from the engine repo root). Client engagements set theirs at creation time via the New-Engagement dialog. Export-refresh writes to the active engagement's `engagement_export_dir`; null disables auto-export with a log warning. (See DEC-085.)

**Why.** Each engagement's git-tracked lineage belongs with the engagement's other documents, where reviewers will naturally look. Forcing all exports into a centralised engine-repo location would split each client engagement's documentation between two repos. Acknowledged asymmetry with Q2 (DB files all in engine repo) is defensible because DB files are gitignored data and exports are git-tracked documents — different concerns, different homes.

**Implementation implications.**

- One nullable column on the meta DB `engagements` table; one validation rule (path exists and is writable when set).
- The dogfood migration step in §3.7 sets this field for the CRMBUILDER row.
- The New-Engagement dialog includes a `engagement_export_dir` field (optional; user can leave blank and set later via Edit).
- Refresh trigger: the existing v0.4 export hook (whichever path currently refreshes `db-export/` after writes) is rebound to read the active engagement's `engagement_export_dir`. Conversation 2's build planning handles the specific code path.
- Drift handling: if the path is set but doesn't exist or isn't writable, the export attempt logs a warning and skips. The user fixes via Edit Engagement.

### 3.9 Engagement entity schema (Q10, Q10b)

**Decision.** Specified in detail in `methodology-schema-specs/engagement.md` (this conversation's companion deliverable). Summary:

- Identifier prefix: `ENG`. Format: `ENG-NNN`. Server-assigned on POST omission per the standard pattern.
- Field set: `engagement_identifier`, `engagement_code`, `engagement_name`, `engagement_purpose`, `engagement_status`, `engagement_last_opened_at`, `engagement_export_dir`, `engagement_created_at`, `engagement_updated_at`, `engagement_deleted_at`. All prefixed `engagement_` per DEC-046.
- `engagement_code` constraint mirrors v1's `Client.code` exactly: regex `^[A-Z][A-Z0-9]{1,9}$` (length 2–10, first char uppercase letter, all chars uppercase letters or digits), case-insensitive unique within the meta DB.
- Status lifecycle: `active` / `paused` / `archived` with free transitions. Default starter `active`. (See DEC-086.)
- Soft-delete via `engagement_deleted_at`, independent of status.
- No relationships in v0.5 (engagement record stands alone in the meta DB).
- Standard endpoint set served from the meta DB (engagement endpoints don't depend on the active engagement). No `activate` endpoint — activation is desktop-side orchestration (§5).

### 3.10 Two-database API server (architectural detail)

The v0.5 API server connects to **two SQLite databases simultaneously**:

- **Meta DB** at `crmbuilder-v2/data/engagements.db`. Engagement endpoints (`/engagements/*`) read and write this database. Connection path is fixed; recreated by each new API subprocess at startup.
- **Active engagement DB** at the path implied by `CRMBUILDER_V2_DB_PATH`. All other endpoints (sessions, decisions, planning items, risks, topics, references, charter, status, change_log, domains, entities, processes, crm_candidates) read and write this database. Path is set by the desktop launcher when spawning the API subprocess.

This is a small but real shape change from v0.4's single-database API server. The API server's code grows: an additional database-connection module for the meta DB; engagement-endpoint handlers that route to the meta-DB connection; no changes to existing endpoint handlers (they continue using the existing connection pattern, which now happens to be the active engagement's DB).

The two databases share no schema-level coupling. The meta DB has its own Alembic chain; each per-engagement DB has the existing v0.4 Alembic chain. Cross-database queries are not supported and not needed in v0.5.

---

## 4. Activation sequence

The "switch to engagement X" operation is a desktop-side orchestration in v0.5, not an API operation. The sequence:

1. **User action.** User selects engagement X in the picker UI and confirms (or, on app launch, the desktop reads `current_engagement.json` and activates the named engagement automatically).
2. **Pre-check — reachability.** Desktop reads the engagement record from the meta DB (via the currently-running API's `GET /engagements/X`); confirms the engagement is not soft-deleted; computes the expected DB path (`crmbuilder-v2/data/engagements/{X.engagement_code}.db`); confirms the file exists and is readable. If any check fails, abort with a UX message; do not proceed.
3. **Pre-check — migrations.** Desktop opens the engagement's DB directly (bypassing the API), runs `alembic upgrade head` against it, closes the direct connection. If migrations fail, abort with a UX message naming the failed migration; do not proceed.
4. **Quiesce — kill API subprocess.** Desktop sends SIGTERM to the API subprocess; waits up to 5 seconds for graceful shutdown and port 8765 release. If the port is not released within timeout, escalate to SIGKILL; if still not released, abort with a UX message.
5. **Quiesce — kill MCP subprocess.** Same pattern as the API subprocess, on the MCP server's port.
6. **Persist live state.** Write the new engagement identifier and code to `crmbuilder-v2/data/current_engagement.json` (atomic write: write to `.tmp` then rename).
7. **Persist ordering state.** PATCH `engagement_last_opened_at` on the engagement record. (Note: at this moment, no API server is running, so the desktop opens the meta DB directly to perform this update, then closes. Alternative: defer the PATCH until step 9 below and do it through the new API. Either is correct; Conversation 2 picks one.)
8. **Update in-memory context.** Set `ActiveEngagementContext` to the new engagement.
9. **Launch new API subprocess.** Spawn with `CRMBUILDER_V2_DB_PATH={engagements/{code}.db}` and `CRMBUILDER_V2_API_PORT=8765`. Poll `/health` with exponential backoff (initial 100ms, max 5 seconds) until 200 OK. If the API does not come up within timeout, abort with a UX message.
10. **Launch new MCP subprocess.** Same pattern; subprocess wired to the new API.
11. **Emit signal.** `ActiveEngagementContext.active_engagement_changed(new_engagement)` fires. Panels listening for this signal re-fetch from the API against the new engagement.
12. **UI restore.** "Switching engagement..." indicator dismisses; UI returns to normal interactive state.

Total elapsed time for a typical switch: a few seconds (dominated by API subprocess startup time). For an engagement with pending migrations, longer — proportional to migration count and complexity.

External clients (curl, MCP clients, scripts) connect to port 8765 throughout. During steps 4–9, the API is not reachable; external clients see connection-refused or timeout. v0.5 does not provide a "switching now" status to external clients beyond the port being temporarily unreachable.

---

## 5. Acceptance criteria

Architecture-level acceptance criteria. Conversation 2's build planning translates these into specific test cases for the per-slice acceptance criteria.

1. **Meta DB schema migration applies cleanly.** Alembic creates the `engagements` table with all ten columns (`engagement_identifier`, `engagement_code`, `engagement_name`, `engagement_purpose`, `engagement_status`, `engagement_last_opened_at`, `engagement_export_dir`, `engagement_created_at`, `engagement_updated_at`, `engagement_deleted_at`); runs forward and backward without error.
2. **Discovery returns expected results.** `GET /engagements` returns the CRMBUILDER row (and any user-created engagements) from the meta DB. Soft-deleted engagements excluded by default; `?include_deleted=true` includes them.
3. **Dogfood migration runs cleanly on a fresh v0.5 launch against a v0.4 database.** All eight tracked tables (`sessions`, `decisions`, `planning_items`, `refs`, `change_log`, `charter`, `status`, `base_entity_catalog`) plus the `topics` and `risks` tables have row counts in the new path matching the source. The `.pre-v0.5-backup` file exists. The original `v2.db` is removed.
4. **Idempotent migration.** Rerunning the migration after a successful first run is a no-op; the engine reports "already migrated" and exits cleanly.
5. **Active state round-trips.** Switching to engagement X writes `current_engagement.json` and updates `engagement_last_opened_at`; restarting the desktop app reads the file and activates engagement X automatically.
6. **Lazy migrations apply on activation.** A stale engagement DB (one with `alembic_version` behind the codebase) has its migrations applied when activated. The "Upgrading engagement database..." indicator shows. Activation succeeds.
7. **Identifier scope works.** Creating a session in engagement A and then a session in engagement B assigns `SES-001` in each (assuming both engagements are empty of sessions). The meta-DB engagement-identifier sequence is independent: `ENG-001`, `ENG-002`, etc.
8. **API server connects to both databases.** Engagement endpoints query the meta DB; other endpoints query the active engagement's DB. No cross-database leakage.
9. **MCP server lifecycle mirrors API.** MCP subprocess is killed and relaunched on engagement switch; MCP tools operate against the active engagement.
10. **Exports land in the engagement's export_dir.** Writes to the active engagement's DB trigger the export refresh. Dogfood exports continue to land at `PRDs/product/crmbuilder-v2/db-export/`. Client engagement exports land at their configured path. Null `engagement_export_dir` produces a log warning and no file writes.
11. **Drift recovery on unreachable engagement.** If `current_engagement.json` references an engagement whose DB file is missing, the desktop launches with no active engagement and the picker UI prompts for selection.
12. **Engagement CRUD round-trips.** Creating an engagement creates the per-engagement DB file (with Alembic migrations applied to head). Soft-deleting an engagement removes it from the default picker but preserves the row and the file. Restoring an engagement returns it to the default picker.
13. **Switch UX shows progress.** Engagement switch presents a clear "Switching..." indicator; UI gestures during the switch are either queued or rejected; switch completes within a few seconds (or longer if migrations are pending) and panels refresh.

---

## 6. Open questions and deferred decisions

Categorised. Each entry is one paragraph.

### 6.1 For Conversation 2 (v0.5 build planning) to settle

**Slice placement of the dogfood migration.** Slice A (foundation) versus a dedicated migration slice. The workstream plan §10 flags this as a Conversation 2 question. Conversation 1 settles the *what*; Conversation 2 settles the *when within build*.

**Exact UI shape for engagement picker and management.** Engagement is structurally different from the four v0.4 methodology entity types (it's v2-install-level routing metadata, not domain-scope content), so it doesn't fit the "Methodology" sidebar group. Conversation 1 names two needed affordances (a switching UI and a management/CRUD UI) without prescribing the visual shape (top-bar picker, status-bar dropdown, sidebar group, dedicated dialog). Conversation 2 picks the layout in coordination with the styling workstream (PI-001) per the boundary discipline established in DEC-076.

**The `engagement_last_opened_at` update path during activation.** Step 7 of the activation sequence (§4) needs to update `engagement_last_opened_at` while no API is running. Two paths work: (a) desktop opens the meta DB directly to perform the update; (b) defer the update to after the new API subprocess is up, then PATCH through the API. Either is correct. Conversation 2 picks one consistent with the implementation pattern.

**Exact retry/timeout values in the activation sequence.** Step 4's 5-second timeout for port release; step 9's exponential-backoff parameters for API health-check polling. Numbers are reasonable starting points; Conversation 2 may tune based on observed latencies.

**Whether the New-Engagement dialog should default `engagement_export_dir` to anything for client engagements.** Conversation 1 says null is the default; Conversation 2 may choose a smart default (e.g., a sibling-of-engine-repo path inferred from common patterns) if there's a sensible one. Defaulting to null is the conservative choice.

### 6.2 For CBM redo to surface

**Whether `engagement_purpose` plain text suffices.** The field is plain text in v0.5. If real engagement-management use surfaces a need for markdown or richer content, v0.6+ migration adds support. Same posture as `domain.md`'s text fields.

**Whether `engagement_export_dir` configurability suffices for the actual client-repo storage use case.** If CBM's exports landing in `ClevelandBusinessMentors/v2-db-export/` works smoothly, the design holds. If not — e.g., the user wants a smarter path resolution that follows the client repo when it moves — a v0.6+ enhancement is on the table.

**Whether the kill-relaunch switch UX is acceptable in practice.** A few seconds of unavailability per switch is the model. If real use shows this is too disruptive (e.g., users switch frequently), the multi-tenant migration (PI-017) becomes higher priority.

### 6.3 For v0.5+ tracked separately

**[v0.6+, PI-017] Multi-tenant API + MCP migration.** Anchored by DEC-081. Trigger: v2 prototype-to-production transition. Scope: refactor every endpoint to accept engagement context via header or path-prefix; refactor access-layer connection management; refactor tests; reshape MCP server; remove kill-relaunch dance from desktop's switch path.

**[v0.6+, candidate, not yet a PI] Optional `engagement_db_path` field.** Nullable column allowing per-engagement override of the conventional `crmbuilder-v2/data/engagements/{code}.db` path. Mirrors v1's split (per-client DBs in `{project_folder}/.crmbuilder/{code}.db`). Migration is small (add nullable column); behaviour is "null means convention, set means override." Triggered if/when an engagement needs to travel with a client repo across machines. Not a planning item yet because the use case is hypothetical for v0.5.

**[v0.6+, candidate] Engagement-aware MCP tools.** When the API migrates to multi-tenant (PI-017), MCP tools gain engagement-context arguments or a per-tool engagement selector. Scope is bundled with PI-017.

**[v0.6+, candidate] Cross-engagement reporting.** Workstream plan §3.2 deferred this. If/when real use surfaces a need (e.g., a dashboard showing decisions across all engagements), the design depends on PI-017 having shipped first.

---

## 7. Cross-references

### 7.1 Decisions produced by this conversation

The following nine decisions are authored at conversation close via the standard `apply_close_out.py` script reading `PRDs/product/crmbuilder-v2/close-out-payloads/ses_026.json`. Each is linked to SES-026 via a `decided_in` reference recorded in the same payload.

- **DEC-078 — Engagement discovery model: bootstrap meta DB.** §3.1 above.
- **DEC-079 — Per-engagement DB file location: engine repo, conventional paths.** §3.2 above.
- **DEC-080 — Active-engagement state persistence: JSON file + in-memory context + `last_opened_at` column.** §3.3 above.
- **DEC-081 — v0.5 API + MCP server model (one process per engagement); commitment to multi-tenant migration at prototype-to-production transition.** §3.4 above. Anchors PI-017.
- **DEC-082 — Identifier scope: per-engagement governance and methodology; engagement identifiers scoped to meta DB.** §3.5 above.
- **DEC-083 — Migrations across engagements: lazy at engagement-open.** §3.6 above.
- **DEC-084 — Dogfood migration: one-shot explicit.** §3.7 above.
- **DEC-085 — Per-engagement exports: split via `engagement_export_dir` field.** §3.8 above.
- **DEC-086 — Engagement entity schema and lifecycle.** §3.9 above. Details in `methodology-schema-specs/engagement.md`.

### 7.2 Planning items produced or amended

- **PI-017 — Multi-tenant API + MCP migration.** New. Anchored by DEC-081. Trigger: prototype-to-production transition.

### 7.3 Prior decisions informing this conversation

- **DEC-001** — v2 charter framing (next major iteration; v1 functionality migrating onto v2's foundation). This document operationalises that framing for the engagement-management migration item.
- **DEC-023** — Process model: UI process spawns/attaches to the API subprocess. The activation sequence in §4 builds on this lifecycle.
- **DEC-039** — Multi-tenancy posture: "one v2 instance per engagement; separate SQLite; separate API port." This document operationalises DEC-039's finding rather than superseding it. Q4's chosen v0.5 model (Option A) is consistent with DEC-039's framing.
- **DEC-046** — Parent-prefix field-naming convention for methodology entities. Engagement entity adopts this convention (all fields prefixed `engagement_`).
- **DEC-068** — Spec guide section 6 amendment establishing the methodology-entity conventions including parent-prefix naming. Engagement is a methodology entity type in the workstream sense (registered under the workstream that also produced `domain`, `entity`, `process`, `crm_candidate`) even though it differs structurally (routing metadata, lives in meta DB rather than per-engagement DB).
- **DEC-075** — v0.5 release scope: build engagement management in v2 as the next migration item from v1. This document delivers the architecture half of that scope.
- **DEC-076** — PI-001 reopens as parallel workstream alongside v0.5; boundary discipline (styling owns visual; v0.5 owns data/routing).
- **DEC-077** — Paper-test deferred until v0.5 ships and a CBM engagement is created. This document is a prerequisite for the paper-test.

### 7.4 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry.
- `PRDs/product/crmbuilder-v2/v0.5-engagement-management-workstream-plan.md` — workstream master plan.
- `PRDs/product/crmbuilder-v2/v0.5-conversation-1-kickoff.md` — this conversation's seed prompt.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template informing the companion deliverable.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/engagement.md` — the schema spec produced by this conversation.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — foundational schema spec setting the conventions this conversation inherits.
- `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` — v0.4 release PRD informing the shape of Conversation 2's v0.5 PRD.
- `crmbuilder-v2/src/crmbuilder_v2/config.py` — existing runtime configuration; the env-var override mechanism this design layers on top of.
- `automation/db/master_schema.py` — v1 Client master schema; precedent for the `engagement_code` constraint and the master-DB pattern.
- `automation/ui/active_client_context.py` — v1 active-client context; precedent for the in-memory + signal + persistence pattern adopted for `ActiveEngagementContext`.

### 7.5 Predecessor and successor conversations

- **Predecessor:** SES-025 — v0.5-orientation conversation. Produced the workstream plan, the styling workstream plan, and the paper-test deferral. Authored DEC-075, DEC-076, DEC-077.
- **Successor:** v0.5 Conversation 2 — build planning. Kickoff at (to be authored at SES-026 close, or by Doug separately). Takes this document and `engagement.md` as inputs; produces `ui-PRD-v0.5.md`, `ui-v0.5-implementation-plan.md`, and slice build prompts.

---

*End of document.*
