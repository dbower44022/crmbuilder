# CRMBuilder v2 — User Interface PRD

**Version:** 0.5
**Last Updated:** 05-16-26 21:00
**Status:** Draft — pending approval
**Predecessor:** `ui-PRD-v0.4.md` (shipped per SES-024 slice F closeout, 05-15-26)
**Companion documents:** `multi-engagement-architecture.md`, `methodology-schema-specs/engagement.md`, `ui-v0.5-implementation-plan.md`

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.5 | 05-16-26 | Fifth iteration of the v2 desktop UI. Adds engagement management — a single new methodology entity type (`engagement`) plus the multi-engagement routing infrastructure (bootstrap meta DB at `crmbuilder-v2/data/engagements.db`; per-engagement DB files at `crmbuilder-v2/data/engagements/{code}.db`; `ActiveEngagementContext`; two-database API server; 12-step activation sequence) that lets v2 host multiple engagements without mixing client data into the v2-build dogfood instance. Migrates the existing dogfood `v2.db` into the new model at first launch (one-shot explicit migration to `engagements/CRMBUILDER.db`). Introduces an "Engagements" sidebar group above Governance and Methodology with the engagement entity panel, plus an always-visible top-strip switching affordance with a picker that includes a "Manage engagements..." footer link. Engagement creation is single-gesture: one click creates the meta DB row, creates the per-engagement DB file with Alembic at head, and activates the new engagement. Five-slice build (A foundation+migration, B schema+API, C panel UI, D switching, E closeout). Captures seven architectural decisions for recording in the v2 database after PRD approval (numbering settled at approval — see Section 13). Coordinates with the parallel PI-001 styling workstream per DEC-076's boundary discipline: v0.5 owns data and routing; PI-001 owns visual. v0.5 inherits whatever styling tokens have shipped (`styling-design-pass.md` is committed as part of SES-027) by the time slice C lands. |

---

## 1. Overview

### Purpose

This document specifies the requirements for CRMBuilder v2 user interface (UI) v0.5. v0.4 closed the methodology-content gap by shipping the four methodology entity types CBM-redo Phase 1 needs (domain, entity, process, crm_candidate). v0.5 closes the **engagement-routing** gap: v0.4's methodology tables and v2's governance tables both live in a single SQLite file (`crmbuilder-v2/data/v2.db`) that hosts the v2-build's own dogfood content (24 sessions, 86 decisions, 17 planning items, 66 references, 222 change-log entries at v0.4 close). Running CBM Phase 1 against the dogfood instance would mix two unrelated bodies of data into one file with one identifier sequence. DEC-039's working answer to the multi-tenancy question — "one v2 instance per engagement, separate SQLite, separate API port" — was a finding rather than a designed feature; v0.5 operationalises it.

The release adds one new methodology entity type — `engagement` — plus the supporting routing infrastructure (bootstrap meta DB, per-engagement DB files, active-engagement state persistence, two-database API server, activation sequence, dogfood migration). After v0.5 ships, Doug creates a CBM engagement record, the paper-test conversation runs against the freshly-created CBM engagement, and CBM Phase 1 (or a v0.6 amendment workstream, depending on paper-test outcome) begins.

### Background

UI v0.4 shipped on 05-15-26 (SES-024 slice F closeout). The v0.5-orientation conversation (SES-025) surfaced the v1/v2 client-management overlap and committed v2 to building proper engagement management as v0.5 rather than bridging to v1's existing Client master DB. The orientation conversation produced `v0.5-engagement-management-workstream-plan.md`, the styling workstream plan (DEC-076 reopens PI-001 as a parallel workstream), and the paper-test deferral header (DEC-077).

v0.5 runs as a three-conversation workstream. **Conversation 1** (SES-026) combined multi-engagement architecture design with engagement schema design and produced two deliverables: `multi-engagement-architecture.md` and `methodology-schema-specs/engagement.md`. It settled the ten architectural questions catalogued in the workstream plan §6 and authored nine decisions (DEC-078 through DEC-086) plus one planning item (PI-017, multi-tenant API+MCP migration at the prototype-to-production transition). **Conversation 2** (this conversation) takes those two deliverables as input and produces this PRD, the companion implementation plan, and the slice build prompts. **Slice execution** runs after Conversation 2 closes, one slice at a time in Doug's local terminal via Claude Code.

### Source decisions

This PRD does not re-derive architectural decisions; it specifies requirements grounded in the following decision records.

Existing decisions still in force from prior releases:

- **DEC-019** — UI reaches the storage system exclusively through the REST API. v0.5 preserves this for normal operations; the dogfood migration in slice A and the optional direct-DB-access during the kill-relaunch dance are explicit exceptions.
- **DEC-022, DEC-008** — JSON snapshots under `db-export/` are renders, not authored copies; panels file-watch the snapshots for refresh. v0.5 extends this pattern to the meta DB at `db-export/meta/engagements.json`.
- **DEC-023** — UI process spawns or attaches to the API subprocess. v0.5's activation sequence builds on this lifecycle.
- **DEC-025** — `conversation_reference` is descriptive text; seed-prompt verbatim in `topics_covered`. This PRD's session record follows the convention.
- **DEC-035, DEC-036** — `ListDetailPanel` factory + uniform right-click context menus. The engagement panel inherits this base.
- **DEC-039** — Original multi-tenancy posture: "one v2 instance per engagement; separate SQLite; separate API port." This release operationalises the finding rather than superseding it.
- **DEC-046** — Parent-prefix field-naming convention for methodology entities. Engagement fields all prefixed `engagement_`.
- **DEC-068** — Spec guide section 6 amendment establishing the methodology-entity conventions. Engagement adopts these conventions with documented deviations for its routing-metadata structural distinction.
- **DEC-075** — v0.5 release scope: build engagement management in v2 as the next migration item from v1.
- **DEC-076** — PI-001 reopens as parallel workstream alongside v0.5; boundary discipline (styling owns visual; v0.5 owns data/routing).
- **DEC-077** — Paper-test deferred until v0.5 ships and a CBM engagement is created.
- **DEC-078 through DEC-086** — Conversation 1's nine architectural decisions: meta DB discovery model, conventional per-engagement DB paths, JSON-file + last_opened_at active state persistence, one-process-per-engagement API+MCP at v0.5 with committed multi-tenant migration, per-engagement identifier scope, lazy migrations at engagement-open, one-shot explicit dogfood migration, split exports via `engagement_export_dir`, and engagement entity schema and lifecycle.

Forthcoming decisions (to be recorded after this PRD is approved — see Section 13):

- **DEC-098** — v0.5 slice breakdown: five-slice structure (foundation+migration, schema+API, panel UI, switching, closeout) with the dogfood migration combined into slice A.
- **DEC-099** — Engagement UI affordance placement: top-strip switching above sidebar entries, "Engagements" sidebar group above Governance with one entry, dual paths to the management panel (sidebar entry plus "Manage engagements..." picker footer).
- **DEC-100** — Single-gesture engagement creation+activation: New Engagement dialog performs POST + file creation + activation in one user click, with graceful inline failure recovery for activation failures.
- **DEC-101** — Forbid soft-deleting the active engagement: delete dialog refuses with inline redirect to switch first.
- **DEC-102** — Null default for `engagement_export_dir` on new engagements: dialog field empty by default with "Optional — leave blank to disable auto-export" placeholder.
- **DEC-103** — Meta DB exports at `PRDs/product/crmbuilder-v2/db-export/meta/engagements.json`: subdirectory parallel to the dogfood's content exports, file-watch refresh per the standard v0.3+ pattern.
- **DEC-104** — v0.5 PRD approval. Records the PRD's transition from "Draft — pending approval" to "Approved."

**Renumbering note.** The draft of this PRD initially anticipated DEC-A through DEC-G mapping to DEC-095 through DEC-101. At PRD-closeout time the actual range available is DEC-098 through DEC-104, because the parallel PI-001 styling workstream's Conversation 1 (SES-027) close-out applied first (claiming DEC-087 through DEC-094) AND the styling Conversation 2 ran in parallel with this conversation and claimed SES-028 plus DEC-095 through DEC-097 for its v0.6 PRD authoring. The session identifier for this PRD's authoring conversation is therefore SES-029. The renumbering is mechanical bookkeeping — same pattern as v0.4's SES-016 → SES-017 collision-resolution.

---

## 2. Scope

### In Scope

The following are required deliverables for v0.5.

1. **Multi-engagement routing infrastructure.** Foundation work that lands ahead of engagement-management UI:
   - Bootstrap meta DB at `crmbuilder-v2/data/engagements.db` (gitignored) with its own Alembic migration chain, separate from per-engagement chains. Hosts the `engagements` registry table.
   - Per-engagement DB file convention at `crmbuilder-v2/data/engagements/{engagement_code}.db` (gitignored).
   - `ActiveEngagementContext` QObject in the desktop application with an `active_engagement_changed(object)` Qt signal, mirroring v1's `ActiveClientContext` pattern.
   - Cross-restart active-state persistence: JSON file at `crmbuilder-v2/data/current_engagement.json` (gitignored) holding `{"engagement_identifier", "engagement_code", "set_at"}`.
   - Lazy migration application: `alembic upgrade head` runs against an engagement's DB at activation time (mirrors v1's `run_client_migrations` pattern).
   - Two-database API server: the API subprocess connects to both the meta DB (for `/engagements/*` endpoints) and the active engagement's DB (for all other endpoints) simultaneously.

2. **Dogfood migration.** One-shot explicit migration from `crmbuilder-v2/data/v2.db` (v0.4's source-of-truth path) to `crmbuilder-v2/data/engagements/CRMBUILDER.db`. Backup-verify-delete discipline per DEC-084. Idempotent on rerun. Creates the meta DB, inserts the CRMBUILDER engagement record with `engagement_export_dir` set to the absolute path of `PRDs/product/crmbuilder-v2/db-export/` (computed from the engine repo root), copies the v0.4 database to the new location, verifies row counts, deletes the original. The `.pre-v0.5-backup` file is left in place for user-initiated cleanup after v0.5 verification.

3. **Engagement entity type.** Single new methodology entity per `methodology-schema-specs/engagement.md`:
   - Identifier prefix `ENG`, format `ENG-NNN`, server-assigned on POST omission, scoped to the meta DB (one sequence per v2 install).
   - Ten fields per spec §3.2: `engagement_identifier`, `engagement_code`, `engagement_name`, `engagement_purpose`, `engagement_status`, `engagement_last_opened_at`, `engagement_export_dir`, `engagement_created_at`, `engagement_updated_at`, `engagement_deleted_at`. All prefixed `engagement_` per DEC-046.
   - `engagement_code` regex `^[A-Z][A-Z0-9]{1,9}$`, case-insensitive unique within the meta DB; mirrors v1's `Client.code` constraint exactly.
   - Status lifecycle `active` / `paused` / `archived` with free transitions per spec §3.4; default starter `active`.
   - Standard endpoint set (eight endpoints) served from the meta DB per spec §3.5.1.
   - No relationships in v0.5 (engagement record stands alone in the meta DB; per-engagement DB entities don't reference engagement records).

4. **Activation sequence.** 12-step desktop-side orchestration per `multi-engagement-architecture.md` §4 with the question-6 amendment from this PRD (`engagement_last_opened_at` PATCH deferred until after new API subprocess is up): user gesture → reachability check → pre-flight Alembic on new engagement's DB → kill API subprocess → kill MCP subprocess → write `current_engagement.json` → update in-memory context → launch new API → launch new MCP → PATCH `engagement_last_opened_at` via new API → emit `active_engagement_changed` signal → UI restore.

5. **Engagements sidebar group and management panel.** A new sidebar group titled "Engagements" positioned above Governance and Methodology, with exactly one entry titled "Engagements" that opens the engagement management panel. The panel is a `ListDetailPanel` subclass per the v0.4 pattern: master pane columns Identifier / Code / Name / Status / Last Opened (sortable; default by Last Opened descending); detail pane per spec §3.6.3 (identifier read-only, code read-only on edit, name, purpose, status combo, export-dir field with directory-browser button, audit timestamps). Standard CRUD: New / Edit / Delete / Restore dialogs as `EntityCrudDialog` and `EntityCrudDeleteDialog` subclasses. References section is absent (engagement has no relationships in v0.5).

6. **Switching affordance.** An always-visible top-strip widget above the sidebar entries (inside the sidebar container, not a top-bar across the whole window) showing the active engagement's name with code in parentheses smaller, plus a Lucide chevron-down dropdown caret. Clicking the strip opens the engagement picker: live engagements ordered by `engagement_last_opened_at` descending; paused and archived engagements rendered in `color.neutral.500` and sorted to the bottom; active engagement marked with a Lucide check icon; soft-deleted hidden by default. Footer item "Manage engagements..." separated by a hairline divider, opening the same management panel as the sidebar entry. Empty state when no engagements exist: top-strip reads "No engagement selected"; picker contains only the "Manage engagements..." footer item.

7. **Single-gesture engagement creation.** The New Engagement dialog submits via three sequential operations behind one user click: POST `/engagements` (creates meta DB row) → desktop creates per-engagement DB file with Alembic at head → desktop initiates 12-step activation sequence. Progress indicator shows three labels in turn ("Creating engagement record..." → "Initializing database..." → "Switching to <name>..."). Activation failure after creation succeeds surfaces inline with "Try switching now" / "Stay in <previous engagement>" affordances; the engagement record persists. Validation errors at each stage roll back appropriately (meta DB POST fails: dialog stays open with inline error; file creation fails: meta DB row is DELETEd; activation fails: see above).

8. **Forbid soft-delete on active engagement.** The engagement panel's Delete dialog rejects when invoked on the currently-active engagement with the message "<engagement name> is currently active. Switch to a different engagement first, then soft-delete this one." Last-engagement case: "<engagement name> is the only engagement on this install. Create another engagement before soft-deleting this one." The next-launch drift-recovery path in spec §3.4.5 remains as a safety net for cross-restart desync.

9. **Meta DB JSON exports and engagement-panel file-watch.** Writes to the meta DB regenerate `PRDs/product/crmbuilder-v2/db-export/meta/engagements.json` via the standard access-layer hook. The engagement management panel registers with the refresh service and refreshes on file change, plus listens to `active_engagement_changed` signals to refresh the active-engagement marker.

10. **About-dialog version bump and README release note.** `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` set to `"0.5.0"`. README at `crmbuilder-v2/README.md` gets a v0.5 release note matching v0.4's format.

### Out of Scope

The following are explicitly deferred to v0.6+ or later.

- **Multi-tenant API and MCP server architecture (PI-017).** Anchored by DEC-081. v0.5 ships one process per engagement with kill-relaunch on switch; the migration to a single multi-tenant API serving all engagements via header or path-prefix routing is committed for when v2 transitions from prototype to production. Trigger is the planned transition, not a friction signal.
- **Engagement-level access control or authentication.** v2 remains a local-only desktop+API system in v0.5. Multi-user is out of scope per workstream plan §3.2.
- **v1 Client import.** v1 and v2 stay independent in v0.5. A separate small workstream can import v1's `master.db` `Client` rows into v2's `engagement` table later if there's value. Per workstream plan §3.2.
- **Cross-engagement queries or reporting.** Each engagement is isolated in v0.5. After PI-017 (multi-tenant API), cross-engagement queries become technically feasible; whether to expose them is a separate scope question.
- **Optional `engagement_db_path` override field.** Nullable column allowing per-engagement override of the conventional `crmbuilder-v2/data/engagements/{code}.db` path. Mirrors v1's split (per-client DBs in `{project_folder}/.crmbuilder/{code}.db`). Triggered if/when an engagement needs to travel with a client repo across machines. Candidate, not a PI yet.
- **Engagement rename (`engagement_code` mutation).** v0.5 has `engagement_code` read-only in the Edit dialog because changing the code requires moving the DB file. If real use surfaces a rename use case, a v0.6+ enhancement adds the operation.
- **Hard delete with file removal.** v0.5 soft-delete preserves the per-engagement DB file. If a "really delete this engagement and reclaim disk space" use case surfaces, v0.6+ adds the operation guarded by edge-text confirmation and only allowed on already-soft-deleted records.
- **Engagement-level fields beyond v0.5 MVS.** No `engagement_description`, no `engagement_notes`, no engagement-level relationships, no engagement renderers, no engagement-aware MCP tools. All deferred to real-use signal.
- **User Process Guide v0.2.** The current Engagement Playbook at `PRDs/process/v2-user-process-guide.md` v0.1 (committed at commit `7885cfe`) describes the data layer as "a SQLite database file `crmbuilder-v2/data/v2.db`" (§3), which is outdated after v0.5 ships. A v0.2 update folding in the multi-engagement routing model, the engagement management workflow, and the activation sequence is **deferred to v0.6**. v0.5's Slice E closeout flags the documentation drift in the release note and the README rather than rewriting the guide inline.
- **Auto-switch on active-engagement soft-delete.** v0.5 forbids the operation (DEC-101). v0.6+ may lift the restriction with an "auto-switch to next-most-recent" flow if real use shows friction.
- **Right-click "Activate" on engagement panel rows.** The picker is the switching gesture in v0.5; adding a context-menu activation would duplicate the affordance.
- **Full styling design pass execution.** PI-001 runs in parallel per DEC-076 and owns the visual layer end-to-end. v0.5 inherits whatever design tokens have shipped by slice C; no styling work is performed inside v0.5 slices.
- **Methodology entity types beyond v0.4's four (PI-003 persona, PI-004 field/requirement/manual_config/test_spec, PI-005 process_step, PI-013 Cross-Domain Service).** These remain v0.6+ candidates.
- **Methodology entity renderers (PI-015).** v0.5 does not produce Word/YAML/JSON-export generation for methodology entities.
- **Catalog FK integration for methodology entities (PI-014).** Same posture as v0.4.
- **Three NOT_SUPPORTED v1 reimplementation workstreams** (saved views, duplicate-check rules, workflow managers). v1 application work, not v2.

---

## 3. Architecture summary

This section summarises the routing architecture; `multi-engagement-architecture.md` is authoritative.

### Two-database API server

The v0.5 API subprocess connects to two SQLite databases simultaneously. The **meta DB** at `crmbuilder-v2/data/engagements.db` services `/engagements/*` endpoints exclusively. The **active engagement's DB** at the path implied by `CRMBUILDER_V2_DB_PATH` services all other endpoints (sessions, decisions, planning_items, risks, topics, references, charter, status, change_log, domains, entities, processes, crm_candidates). Connection paths are fixed at API subprocess startup; the meta DB path is hard-coded relative to the engine repo, and the active engagement path is read from the environment variable at process spawn. No cross-database queries; the two databases share no schema-level coupling. This is the only material API server code change in v0.5: the existing endpoint handlers remain unchanged (they continue to use the active engagement's DB connection, which is now scoped to one engagement instead of being v2-install-wide); engagement-endpoint handlers are new and route to the meta-DB connection.

### Engagement lifecycle (routing-level)

- **Creation.** POST `/engagements` writes the meta DB row only. The desktop then creates the per-engagement DB file at `crmbuilder-v2/data/engagements/{code}.db` and runs `alembic upgrade head` against it. Activation (the kill-relaunch dance) is a third step. Single-gesture creation runs all three behind one click per Section 5.3.
- **Activation.** Twelve-step desktop-side orchestration per `multi-engagement-architecture.md` §4 with the amendment from question 6 (`engagement_last_opened_at` PATCH deferred until after new API subprocess is up). Total elapsed time: a few seconds for a typical switch; longer for an engagement with pending migrations.
- **Switching.** Identical to activation; "switching" is the user-facing term, "activation" is the system-facing term.
- **Soft-delete.** DELETE sets `engagement_deleted_at` on the meta DB row. Per-engagement DB file remains on disk (recoverable via restore). Forbidden on the active engagement per Section 5.6.
- **Restore.** POST `/engagements/{id}/restore` clears `engagement_deleted_at`. Idempotent: restore on a record that is not soft-deleted returns 422.

### Active-engagement state persistence

Two channels, each canonical for one fact. **Live state** ("what is the engine pointing at right now") persists as a JSON file at `crmbuilder-v2/data/current_engagement.json` holding `{"engagement_identifier", "engagement_code", "set_at"}`. Atomically written by the desktop on engagement activation. The in-memory `ActiveEngagementContext` QObject mirrors v1's `ActiveClientContext` shape, emits `active_engagement_changed(object)` Qt signal on activation. **Ordering** ("when was each engagement last opened") persists as the `engagement_last_opened_at` DATETIME column on the meta DB `engagements` table. Picker uses this for ordering and for "restore last-active" UX on app launch.

### Drift recovery

On app launch, the desktop reads `current_engagement.json`. If the file is missing, the in-memory context starts empty and the picker UX prompts for selection. If the file references an engagement that doesn't exist in the meta DB or whose DB file is missing on disk, same outcome. No silent fallback to a different engagement. The 12-step activation sequence's pre-check steps 2 and 3 catch the same drift cases when activation is initiated.

### Migration model

The meta DB has its own Alembic chain that applies at desktop launch (hard-fail UX if migration fails). Per-engagement DB chains apply lazily at engagement-open per DEC-083, mirroring v1's `run_client_migrations` pattern. An engagement that is never opened never gets migrated; an engagement opened after a long pause applies pending migrations at activation with a "Upgrading engagement database..." indicator. Each engagement's `alembic_version` table tracks its own head independently.

### Identifier scope

Per DEC-082, governance and methodology identifiers (`SES-NNN`, `DEC-NNN`, `PI-NNN`, `RSK-NNN`, `TOP-NNN`, `REF-NNN`, `CHR-NNN`, `STA-NNN`, `DOM-NNN`, `ENT-NNN`, `PROC-NNN`, `CRMC-NNN`) scope per-engagement: each engagement's DB has its own identifier sequences. CBM's first session is `SES-001` within the CBM engagement, independent of the dogfood's `SES-027+`. The v0.4 next-identifier helpers query the active DB connection and naturally return per-engagement sequences with no code change required. Engagement identifiers (`ENG-NNN`) scope to the meta DB — one sequence per v2 install.

---

## 4. Schema summary

This section summarises the engagement entity schema; `methodology-schema-specs/engagement.md` is authoritative.

The `engagement` entity type carries ten fields, all prefixed `engagement_` per DEC-046. Identifier fields: `engagement_identifier` (TEXT, `^ENG-\d{3}$`, unique, server-assigned), `engagement_code` (TEXT, `^[A-Z][A-Z0-9]{1,9}$`, case-insensitive unique within meta DB; used as the per-engagement DB filename), `engagement_name` (TEXT, non-empty, case-insensitive unique). Content field: `engagement_purpose` (TEXT, non-empty, plain text 1-2 sentences). Classification field: `engagement_status` (TEXT, enum `active` | `paused` | `archived`, default `active`, free transitions). Operational fields: `engagement_last_opened_at` (DATETIME, nullable, ISO 8601 UTC), `engagement_export_dir` (TEXT, nullable, absolute filesystem path, validated as existing writable directory when set). Timestamp fields: `engagement_created_at`, `engagement_updated_at`, `engagement_deleted_at` (inherited base behavior).

No `engagement_description`, no `engagement_notes`, no `engagement_db_path` (path is conventional from `engagement_code` per DEC-079). No outgoing relationships in v0.5; no inbound relationships from per-engagement DB entities (engagement is implicit context for everything in the engagement's own DB).

Standard endpoint set served from the meta DB: GET `/engagements`, GET `/engagements/{id}`, POST `/engagements`, PUT, PATCH, DELETE (soft), POST `/engagements/{id}/restore`, GET `/engagements/next-identifier`. No activate endpoint — activation is desktop-side orchestration; API server cannot perform activation because activation requires killing and respawning the API process. When PI-017 (multi-tenant API) lands at the prototype-to-production transition, the API gains the ability to switch engagements without restart and an activation endpoint becomes possible.

Status-transition validation per spec §3.5.3: all three transitions (active ↔ paused ↔ archived) are valid; only enum violations return 422 (`invalid_enum_value`). Soft-delete semantics per spec §3.4.6 (standard v2 pattern): DELETE sets `engagement_deleted_at`; `?include_deleted=true` includes soft-deleted; POST `/restore` clears the timestamp.

---

## 5. Functional Requirements

### 5.1 Engagement management panel

The panel is a `ListDetailPanel` subclass registered as the only entry in the new "Engagements" sidebar group. Inherits the v0.4 panel pattern unchanged at the base level: `_create_master_widget` returning a configured `QTableView`; `_build_context_menu` returning a menu with New / Edit / Delete / Restore (Restore appears on soft-deleted rows when `?include_deleted=true` is active); detail pane composed of form fields plus an absent references section. Visual treatment inherits from `styling-design-pass.md` whatever tokens are current when slice C lands (see Section 9).

**Master pane.** Five columns: Identifier (mono font, `font.size.small`), Code (mono, `font.size.small`), Name (body), Status (body, with status-aware text color: active in normal text, paused in `color.warning.default` or equivalent neutral, archived in `color.neutral.500`), Last Opened (body, formatted as relative date "2 hours ago" / "3 days ago" / "—" when null). Default sort by Last Opened descending (matches picker order). Active engagement marked with a left accent bar matching the styling design pass's selected-state vocabulary, plus a Lucide check icon in the Identifier column. Soft-deleted rows render in `color.neutral.500` text with a leading Lucide trash-2 icon when `?include_deleted=true` is active.

**Detail pane.** Form fields in order: identifier (read-only, mono), code (read-only on Edit, editable on Create), name (text input), purpose (multi-line text input, 80px minimum), status (combo with three values), export-dir (text input with adjacent directory-browser button; placeholder "Optional — leave blank to disable auto-export"; tooltip "Where this engagement's JSON snapshots will be written. Recommend a path inside the client repo so exports travel with the engagement documents."), created_at (read-only, relative date), updated_at (read-only, relative date), deleted_at (visible only when soft-deleted, read-only). No references section.

**Empty state.** When the panel renders with no engagements present (fresh install before migration; or after soft-deleting every engagement, though §5.6 prevents that final state): centered message "No engagements yet" plus secondary hint "Create your first engagement to begin" plus a "Create Engagement" button that opens the New dialog.

### 5.2 Switching affordance

The top-strip widget renders inside the sidebar container, positioned above the sidebar group entries. Background `color.neutral.100` (matches sidebar container), padding `space.2 × space.3`, height 48px, 1px hairline `color.neutral.200` border below. Content row: active engagement's `engagement_name` at `font.size.body`, code in parentheses at `font.size.small color.neutral.500`, right-aligned Lucide chevron-down at 14px. Clicking anywhere on the strip opens the picker dropdown.

**Picker dropdown.** Anchored below the strip, width matches strip, rounded corners per `radius.subtle`, shadow per `shadow.dialog`. Rows: live engagements first, ordered by `engagement_last_opened_at` descending; paused and archived engagements next, rendered in `color.neutral.500` and sorted by last_opened_at descending within their bucket; active engagement marked with leading Lucide check icon at 14px in `color.accent.default`. Each row shows engagement name + code in parentheses; row height matches sidebar entry height. Hover row in `color.neutral.100`. Selected (clicked) row triggers activation. Footer item "Manage engagements..." separated by 1px `color.neutral.200` hairline divider, opens the management panel (same as sidebar entry).

**Empty state.** Top-strip when no engagements exist: text reads "No engagement selected" in `color.neutral.500`, caret still visible and operable. Picker dropdown in this state shows only the footer "Manage engagements..." item.

**Switching indicator.** When the user clicks a non-active engagement row, the picker closes and a centred overlay appears with text "Switching to <engagement name>..." plus a progress indicator. The 12-step activation sequence runs underneath. Indicator dismisses on completion. On failure, the indicator converts to an error message with a "Retry" affordance plus a "Stay in <previous engagement>" affordance; the previous engagement remains active.

### 5.3 Single-gesture engagement creation

The New Engagement dialog is an `EntityCrudDialog` subclass with form fields: code (with regex constraint hint visible — `2-10 characters, uppercase letters and digits, must start with a letter`), name, purpose, status (combo with three values, default `active`), export-dir (with directory-browser button). On Submit, the dialog runs three sequential operations behind one click:

1. POST `/engagements` to create the meta DB row. If this fails, dialog stays open with inline error per the v0.3 validation-error pattern.
2. Desktop creates the per-engagement DB file at `crmbuilder-v2/data/engagements/{code}.db` and runs `alembic upgrade head` against it. If this fails, the desktop sends DELETE `/engagements/{identifier}` to roll back the meta DB row, then shows an error in the dialog.
3. Desktop initiates the 12-step activation sequence per Section 3 / `multi-engagement-architecture.md` §4. If this fails after the engagement record and file exist, the dialog body converts to an error state with two affordances: "Try switching now" (retries activation only) and "Stay in <previous engagement>" (closes the dialog; engagement record persists; user can retry from the picker later).

During execution, the dialog shows three progress labels in turn — "Creating engagement record..." → "Initializing database..." → "Switching to <name>..." — each transitioning to a Lucide check icon on completion or a Lucide circle-x in `color.danger.default` on failure.

### 5.4 Dogfood migration at first launch

The v0.5 engine on first launch detects the migration-needed state: an existing `crmbuilder-v2/data/v2.db` plus a missing or empty meta DB at `crmbuilder-v2/data/engagements.db`. The migration runs through the standard launch sequence, with the desktop showing a "Upgrading to v0.5: migrating engagement..." indicator during the operation. Steps per DEC-084:

1. Backup `v2.db` to `v2.db.pre-v0.5-backup` (kept in place; user removes manually after confirming v0.5 works).
2. Create the meta DB at `crmbuilder-v2/data/engagements.db` and run its initial Alembic migration to head.
3. INSERT the CRMBUILDER engagement row with `engagement_code="CRMBUILDER"`, `engagement_name="CRMBuilder v2"`, `engagement_purpose="Dogfood instance hosting the v2 build's own governance content (sessions, decisions, planning items, methodology catalog)."`, `engagement_status="active"`, `engagement_export_dir` set to the absolute path of `PRDs/product/crmbuilder-v2/db-export/` (computed from the engine repo root).
4. Copy `v2.db` to `crmbuilder-v2/data/engagements/CRMBUILDER.db`.
5. Open the new path and verify by querying expected row counts: `sessions`, `decisions`, `planning_items`, `refs`, `change_log`, `charter`, `status`, plus the catalog tables. Each count must match the source.
6. Delete the original `v2.db` (the `.pre-v0.5-backup` copy remains).
7. Refresh the JSON snapshots at `db-export/` and `db-export/meta/` from the new paths.
8. Write `current_engagement.json` with CRMBUILDER as the active engagement; update in-memory context; launch the API and MCP subprocesses with `CRMBUILDER_V2_DB_PATH` set to the new location.

Three install scenarios handled:

- **Existing v2 install (`v2.db` present).** Migration runs as above. Doug's machine is this case.
- **Fresh install (no `v2.db`).** No migration; the meta DB is created empty by step 2 (followed by the meta DB's initial Alembic migration). The first-launch UX shows the engagement management panel with an empty state inviting the user to create their first engagement.
- **Rerun after successful migration.** Engine detects the already-migrated state (meta DB exists with a CRMBUILDER row pointing at an existing `engagements/CRMBUILDER.db`, and no `v2.db` at old path) and exits cleanly without modification.

**Failure recovery.** Any step failure leaves the `.pre-v0.5-backup` file as the recovery point. The user is instructed to revert by deleting the new files and reverting the engine to the prior v2 release.

### 5.5 Lazy migration at engagement-open

When the user activates an engagement whose DB has a stale `alembic_version` (newer engine, older DB), the activation sequence step 3 (pre-flight migration) runs `alembic upgrade head` against the engagement's DB before the new API subprocess is spawned. The desktop shows an "Upgrading engagement database..." indicator during the operation. On success, activation continues to step 4. On failure, activation aborts with an inline error naming the failed migration; the previous engagement remains active.

Engagements that are never opened never get migrated. The meta DB's own Alembic chain applies at desktop launch (one-time per launch, before any engagement is listable); failure to migrate the meta DB is a hard-fail UX — the engine cannot operate without the registry.

### 5.6 Forbid soft-delete on active engagement

The engagement panel's Delete dialog detects whether the target row is the currently-active engagement (via comparison against `ActiveEngagementContext.engagement_identifier`). When active:

- The standard edge-text confirmation field is replaced with an inline message: "**<engagement_name> is currently active.** Switch to a different engagement first, then soft-delete this one."
- The Delete button is replaced with a "Switch engagement" affordance that opens the picker.

Edge case: the active engagement is the only engagement on the install (no other engagements to switch to). Message changes to: "**<engagement_name> is the only engagement on this install.** Create another engagement before soft-deleting this one." The button changes to "Create engagement" opening the New Engagement dialog.

The drift-recovery path in engagement spec §3.4.5 stays in place as a safety net for cross-restart desync (the user deletes the active engagement via direct API call or external script, then restarts the desktop — `current_engagement.json` points at a soft-deleted engagement, in-memory context starts empty, picker prompts for selection).

---

## 6. Cross-Cutting Concerns

### 6.1 About-dialog version bump

Slice E sets `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` to `"0.5.0"`. The About dialog reads via `importlib.metadata` with `__version__` as fallback per the CLAUDE.md v2 version-source convention.

### 6.2 README release note

Slice E adds a v0.5 release-note entry to `crmbuilder-v2/README.md` matching v0.4's format: a one-paragraph summary plus a bullet list naming the engagement entity type, the multi-engagement routing infrastructure (meta DB, per-engagement DBs, ActiveEngagementContext, two-database API server, 12-step activation sequence), the dogfood migration with backup-verify-delete discipline, the Engagements sidebar group with top-strip switching, single-gesture engagement creation, and the new acceptance-criteria roll-up. A brief mention of the User Process Guide v0.2 deferral to v0.6.

### 6.3 Test target

`uv run pytest tests/crmbuilder_v2/ -v` continues as the test target across all five slices. The new test modules (`tests/crmbuilder_v2/access/test_engagement.py`, `tests/crmbuilder_v2/api/test_engagements_api.py`, `tests/crmbuilder_v2/migrations/test_v0_5_dogfood_migration.py`, `tests/crmbuilder_v2/ui/test_engagement_panel.py`, `tests/crmbuilder_v2/ui/test_switching_affordance.py`, `tests/crmbuilder_v2/ui/test_active_engagement_context.py`) are discovered automatically by pytest's collection.

### 6.4 Status update

Status (the governance entity) is updated from "v0.4 complete" to "v0.5 complete" after Slice E passes. The status update is authored through the desktop UI's versioned-replace pattern, not by Claude Code directly, because the status entity is governance content edited by the operator after build acceptance. The status entity update lives in the CRMBUILDER engagement's database (slice E runs against the post-migration CRMBUILDER engagement).

### 6.5 User Process Guide drift acknowledgement

`PRDs/process/v2-user-process-guide.md` v0.1 describes the data layer as "a SQLite database file `crmbuilder-v2/data/v2.db`" (§3). After v0.5 ships, this description is outdated. Slice E's README release note flags the guide as scheduled for v0.2 update in v0.6. No inline rewrite in v0.5; the guide remains operational at the conceptual level (the two-layer governance/methodology model, the engagement lifecycle, the recurring session pattern, the phase-by-phase walkthrough) — only the data-layer mechanics and the engagement-creation workflow need refreshing.

---

## 7. Acceptance Criteria

Cumulative acceptance criteria for v0.5 = the 13 architecture-level criteria from `multi-engagement-architecture.md` §5, the 12 entity-level criteria from `engagement.md` §3.7, plus the slice-specific UX criteria in this section. Criteria are assigned to slices in `ui-v0.5-implementation-plan.md`; this section captures release-level criteria and the closeout slice's criteria.

### Slice E closeout criteria

E1. `__version__` is `"0.5.0"`; About dialog shows v0.5.0.

E2. README at `crmbuilder-v2/README.md` has a v0.5 release-note entry matching v0.4's format, including the User Process Guide v0.2 deferral mention.

E3. `uv run pytest tests/crmbuilder_v2/ -v` passes green across the full suite (v0.4 tests + all new v0.5 tests).

E4. The Engagements sidebar group renders above Governance with one entry "Engagements"; the top-strip switching affordance renders above the sidebar entries; the picker opens, displays engagements in correct order, and triggers activation on row click.

E5. The 12-step activation sequence completes end-to-end with the question-6 amendment: `engagement_last_opened_at` is PATCHed through the new API after step 9, not during the kill-relaunch dance.

E6. The dogfood migration completed successfully on Doug's machine: `v2.db` is gone, `v2.db.pre-v0.5-backup` exists, `engagements.db` exists with the CRMBUILDER row, `engagements/CRMBUILDER.db` exists with matching row counts to the source, the dogfood is active on launch, and `db-export/` plus `db-export/meta/engagements.json` are refreshed.

E7. A CBM engagement record can be created via the New Engagement dialog (single-gesture creation+activation succeeds); the file at `engagements/CBM.db` is created with Alembic at head; activation switches to CBM; sessions table starts empty in CBM, ready for SES-001.

E8. Cumulative roll-up: all 13 architecture-level acceptance criteria plus all 12 entity-level acceptance criteria pass in the running application.

### Cross-slice acceptance criteria

All 25 criteria from Conversation 1 (13 architecture + 12 entity) are distributed across slices A–D per the implementation plan. The release-level summary:

- Slice A delivers the foundation: meta DB schema, discovery, per-engagement DB file convention, ActiveEngagementContext, two-database API server wiring, lazy migration mechanism, dogfood migration. Criteria 1, 3, 4, 6, 8, 11 from architecture; criteria 1, 2, 10 from entity (schema migration, identifier format, endpoints serve from meta DB).
- Slice B delivers schema correctness and API surface: engagement table migration, access-layer methods, REST endpoints, status-transition validation, identifier auto-assignment with concurrency safety, soft-delete and restore. Entity criteria 2-9.
- Slice C delivers panel UI: management panel, CRUD dialogs, edit-with-code-read-only, soft-delete confirmation with forbid-active behavior, file-watch refresh. Architecture criterion 10 (exports); entity criterion 6 (access-layer methods exercised via UI); entity criterion 12 (sample CBM record creation, though the actual CBM record creation gates on slice D switching).
- Slice D delivers switching: top-strip widget, picker dropdown, kill-relaunch dance, MCP lifecycle mirror, drift recovery on app launch, switch UX with progress indicator, single-gesture creation+activation flow. Architecture criteria 2, 5, 7, 9, 12, 13; entity criterion 11 (last_opened_at update on activation).
- Slice E closes out: version bump, README, status update, regression pass, end-to-end smoke including a CBM engagement creation.

---

## 8. Implementation Plan Reference

Slice breakdown, dependencies, and per-slice acceptance criteria are at `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md`. The implementation plan is the companion document to this PRD and is the source of truth for slice-level build sequencing and the Claude Code prompts that execute v0.5.

---

## 9. Coordination with PI-001 Styling Workstream

Per DEC-076, PI-001 runs as a parallel workstream alongside v0.5. The styling Conversation 1 (SES-027) committed `styling-design-pass.md`, settling the foundation tokens and component visual decisions in DEC-087 through DEC-094. The styling Conversation 2 (SES-028) committed `ui-PRD-v0.6.md` and `ui-v0.6-implementation-plan.md` on the same day this PRD was authored, settling DEC-095 through DEC-097 (release sequencing as v0.6 separate from v0.5; six-slice structure A–F; per-slice screenshot + closeout WCAG check acceptance pattern).

The release sequencing per DEC-095 (styling Conversation 2) makes the boundary discipline concrete: **v0.5 ships first with Qt-default styling on its new engagement-management surfaces; v0.6 retrofits the styling design pass across all panels including v0.5's engagement panel.** The two releases are independent — v0.5 does not block on v0.6, and v0.6 does not block on v0.5 except at v0.6's slice C (panel retrofits) which is gated on v0.5 shipping.

### What v0.5 ships visually

v0.5's slice prompts deliver the engagement management panel, the top-strip switching widget, the picker dropdown, the activation overlay, and the CRUD dialogs as functional surfaces using Qt-default styling plus whatever inline color and spacing constants are necessary for the routing-affordance work to make sense (e.g., the active-engagement marker needs a distinguishing color; the soft-deleted row treatment needs a muted color). These inline values are explicitly marked as TODO-for-v0.6-retrofit so v0.6's slice C can locate and replace them.

v0.5 does NOT author QSS, does NOT introduce a token system, does NOT bundle fonts or icons as application assets, does NOT add base-widget hooks for token consumption, and does NOT modify the existing twelve panels' styling. All of that is v0.6 work per v0.6's slice A (foundation + About dialog), slice B (sidebar + master-pane delegate), and slice C (panel retrofits + ReferencesSection).

### What v0.6 retrofits onto v0.5's engagement-management surfaces

v0.6 slice C (panel retrofits) names the engagement panel as the 13th panel covered by its `master_pane_delegate.py` registration, alongside the eight governance panels and four methodology panels. v0.6 slice B (sidebar + master-pane delegate) covers the new "Engagements" sidebar group introduced by v0.5 slice A — the styling treatment for group headers and entries applies uniformly across all three sidebar groups (Engagements, Governance, Methodology). The top-strip widget introduced by v0.5 slice D is a new surface not covered by v0.6's strawman; either v0.6's slice D adds it to scope or it ships at v0.5-state styling until a subsequent release retrofits.

### Icon usage

v0.5 references the Lucide icon names in its slice prompts (chevron-down, check, trash-2, plus, folder, circle-x, circle-alert) but does NOT bundle the icon files. The slice prompts use placeholder icon-loading code (e.g., Qt's `QIcon.fromTheme()` or unicode characters) that v0.6 slice A replaces with the real Lucide-bundled icon loader per DEC-092. If a slice C build prompt's manual smoke depends on an icon being visible to verify a behavior (e.g., "active engagement marked with check icon"), the v0.5 placeholder icon satisfies the test; v0.6's slice C replaces both the icon and the loader code.

### Coordination touchpoints during build

The two workstreams meet at three files: `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` (v0.5 slice A introduces the Engagements sidebar group container; v0.6 slice B restyles the sidebar uniformly); `crmbuilder-v2/src/crmbuilder_v2/ui/panels/engagement_panel.py` (v0.5 slice C creates; v0.6 slice C retrofits master-pane delegate); and the new `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/engagement_*.py` files (v0.5 slice C/D create; v0.6 slice D retrofits via the form-control token system). v0.5 ships ahead of v0.6's panel-retrofit slices per DEC-095's sequencing, so v0.6 always merges against the v0.5-shipped baseline; v0.6's retrofits are by design non-structural.

---

## 10. Constraints

### Storage layer additive for per-engagement DB schemas

v0.5 introduces a new meta DB with a new schema (the `engagements` table) but does not modify any per-engagement DB schema. The four v0.4 methodology entity tables (`domains`, `entities`, `processes`, `crm_candidates`) and the eight v0.3-or-earlier governance entity tables (`sessions`, `decisions`, `planning_items`, `risks`, `topics`, `references`, `charter`, `status`) continue with their v0.4 shapes. The CBM engagement's DB at `engagements/CBM.db` will have the same schema as the dogfood's `engagements/CRMBUILDER.db` after migration — identical Alembic chains.

### No changes to the v1 application

Unchanged from v0.1–v0.4. v2 work is strictly additive to v1. v0.5 does not touch `automation/`, `espo_impl/`, `tools/`, or the v1-shipped UI surfaces.

### Constraint: process model still assumes localhost

Unchanged from prior releases. v2 remains a local-only desktop+API system in v0.5. Multi-user / authentication / authorization is out of scope per workstream plan §3.2. PI-017's prototype-to-production transition is where multi-tenant and access control work begin.

### Constraint: foundation infrastructure must not regress v0.4 panel behavior

Slice A's foundation work (config layer, ActiveEngagementContext, bootstrap discovery, two-database API server wiring, lazy migration mechanism, dogfood migration) must not change v0.4's behavior on any existing entity panel after the dogfood is migrated. The v0.4 test suite is the regression net; slice A is acceptance-gated on every v0.4 test continuing to pass against the migrated CRMBUILDER engagement.

### Constraint: API-only access except at activation and migration boundaries

DEC-019 establishes that the UI reaches the storage system exclusively through the REST API. v0.5 preserves this principle for normal operations. Two explicit exceptions: (a) the dogfood migration at first launch (no API is running yet; the desktop opens both `v2.db` and `engagements.db` directly via the access layer); (b) the pre-flight Alembic migration in activation step 3 (the desktop opens the target engagement's DB directly, runs migrations, closes — before the new API subprocess is spawned). All other operations including the `engagement_last_opened_at` PATCH go through the API.

### Constraint: append-only on sessions stays strict

Unchanged from v0.3 and v0.4. No UI path edits or deletes a session record. The engagement entity has full CRUD per its spec; sessions remain create-only.

### Constraint: parent-prefix field naming on engagement

All engagement fields including identifier and timestamps are prefixed `engagement_` per DEC-046. The meta DB schema in slice A ships the prefixed column names directly; no rename migration follows. Governance-entity field names retain their pre-workstream conventions until PI-006 retrofit lands (not in v0.5 scope).

### Constraint: no engagement-aware MCP tools in v0.5

The MCP server lifecycle mirrors the API server's: one MCP subprocess per engagement, killed and relaunched on switch. MCP tools operate against the active engagement; there is no MCP tool for switching engagements, no MCP tool exposing engagement metadata across engagements, and no MCP tool for engagement CRUD. Engagement management is desktop-side in v0.5. PI-017 reshapes the MCP server's multi-tenant model at the prototype-to-production transition.

---

## 11. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The dogfood migration corrupts or loses data during the rehoming of `v2.db` to `engagements/CRMBUILDER.db` | Low | Severe | DEC-084's backup-first / verify-row-counts / delete-original discipline is the protective machinery. The `.pre-v0.5-backup` file is the explicit recovery point. Slice A's dogfood-migration tests cover row-count verification against the source for all eight tracked tables plus the catalog tables; failure in any count check aborts the migration with the backup preserved. |
| The 12-step activation sequence's kill-relaunch dance leaves the user in an indeterminate state (API subprocess killed, new one fails to come up) | Low | High | Slice D's tests cover the failure modes: API health-check timeout, port-not-released within step 4's 5-second window, MCP subprocess failure, in-flight migration failure on step 3. Each failure mode produces a clean UX error with the previous engagement remaining active. The `.pre-v0.5-backup` is not in play here because activation does not touch the source DB. |
| The two-database API server's connection management leaks (e.g., the meta DB connection is held across requests in a way that conflicts with engagement-DB connection lifecycle) | Medium | Medium | Slice B's tests assert connection isolation: a test that populates the meta DB with engagement A and the active engagement DB with engagement B's data confirms that GET `/engagements/A` returns A's record and GET `/sessions` returns B's sessions. Connection lifecycle follows the v0.4 pattern (per-request connection from a pool); the meta DB connection is a second pool with the same lifecycle. |
| The activation sequence's `engagement_last_opened_at` PATCH (deferred to after new API up per the question-6 amendment in §3) lands on a different DB than expected because the new API subprocess hadn't fully bootstrapped its meta DB connection | Low | Low | Slice D's activation tests include a regression case verifying the PATCH lands on the meta DB row, not on the active engagement's DB. The health-check polling in step 9 confirms the new API responds to `/health` before the PATCH is issued; the API's startup explicitly opens both DB connections before serving `/health`, so by the time `/health` returns 200 OK, the meta DB connection is live. |
| Engagement creation's single-gesture flow has an unhandled failure mode that leaves a meta DB row + DB file without an activated engagement | Medium | Low | The dialog explicitly handles the three sequential operations' failure modes per §5.3. Activation failure after both creates succeed is the only "partial success" state; the dialog's "Try switching now" / "Stay in <previous>" affordances make the recovery user-driven and explicit. The engagement record exists in either choice; no silent rollback. |
| Slice A's foundation work (config layer + ActiveEngagementContext + two-database API server + lazy migration + dogfood migration) bloats beyond one Claude Code run's comfortable size | Medium | Medium | Slice A is monitored at execution time; if the prompt exceeds healthy size or Claude Code shows degradation during slice A, the slice splits into A1 (foundation infrastructure, no migration) + A2 (dogfood migration), making v0.5 a six-slice release. The split decision is made when the slice-A prompt is drafted, not pre-committed in this PRD. |
| The "Engagements" sidebar group's introduction conflicts with PI-001's sidebar styling work because both touch `app.py` | Low | Medium | The boundary discipline in §9 isolates v0.5's contribution (introduce the new group; ship the engagement panel) from PI-001's contribution (style the sidebar container, group headers, entries, hover/selected states). Either workstream's slice can land first; the second merges against the first. PI-001's existing-group retrofits don't touch the new Engagements group; v0.5's group introduction doesn't restyle existing groups. |
| The dogfood migration leaves `db-export/` in a stale state (the old snapshots still reflect `v2.db` but the new path is `engagements/CRMBUILDER.db`) | Low | Low | DEC-084 step 7 explicitly regenerates the JSON snapshots from the new path. Slice A's tests assert the snapshot regeneration runs and produces files matching the pre-migration content (because the migration is a verified copy). |
| The forbid-active-delete behavior creates a confusing UX when the user attempts to delete the only engagement on the install | Low | Low | §5.6's edge-case wording handles this explicitly: the delete-dialog message changes to "<name> is the only engagement on this install. Create another engagement before soft-deleting this one." Slice C tests cover both the multi-engagement forbid case and the only-engagement forbid case. |
| The single-gesture creation flow's progress indicator confuses the user because three operations are described where they may have expected one | Low | Low | §5.3's three-label progression ("Creating engagement record..." → "Initializing database..." → "Switching to <name>...") gives a coherent narrative for the few-second sequence. The indicators advance fast enough that the user does not interpret them as a slow process — they read as confirmation of progress. Slice D tests verify the indicator transitions visibly. |

---

## 12. Open Questions

1. **Slice A size threshold for splitting into A1 + A2.** Slice A combines foundation infrastructure with the dogfood migration. If the slice's Claude Code prompt exceeds ~800 lines or shows other size-related signals during drafting, the slice splits into A1 (foundation infrastructure, no migration) and A2 (dogfood migration). The split decision is made at prompt-drafting time in the slice-A prompt commit; if the split happens, the implementation plan is updated to reflect six slices.

2. **Activation-failure-after-creation dialog wording.** §5.3's "Try switching now" / "Stay in <previous engagement>" affordances are proposed wording. Slice C's New Engagement dialog implementation may refine the wording if the proposed text reads awkwardly in the actual UI layout (e.g., if the engagement names are long enough that the button labels overflow).

3. **Top-strip widget's relative-date format for `engagement_last_opened_at`.** Working assumption: "2 hours ago" / "3 days ago" / "—" when null. If the format reads poorly in the master pane column or in the picker dropdown, slice C or slice D refines. Common alternative: ISO date when older than 7 days, relative when newer.

4. **Engagement panel's empty state when no engagements exist.** §5.1 describes a centred message plus a "Create Engagement" button. The actual visual placement (vertically centred? top-third aligned?) is a slice C / styling-workstream coordination detail.

5. **Whether the User Process Guide v0.2 deferral note in the README is sufficient drift acknowledgement.** §6.5 takes the position that the guide remains operational at the conceptual level and only the data-layer mechanics need refreshing. If a paper-test-conversation reader of the v0.1 guide is confused by the stale `v2.db` reference, v0.5.1 or v0.6 prioritises the v0.2 update.

---

## 13. Decisions to Be Recorded

Per DEC-014 (every v2 conversation produces a session record) and DEC-025 (`conversation_reference` convention + seed-prompt-in-`topics_covered`), the v0.5-Conversation-2 build-planning conversation that produced this PRD is captured in the v2 database at this PRD's closeout.

**Renumbering note.** The drafts in §1 initially anticipated DEC-A through DEC-G mapping to DEC-095 through DEC-101. At PRD-closeout time the actual range was DEC-098 through DEC-104 (the styling SES-027 apply consumed DEC-087–094; styling Conversation 2 ran in parallel and claimed SES-028 plus DEC-095–097 for its v0.6 PRD authoring). The session identifier is SES-029.

Records to write at PRD closeout:

- **SES-029** — UI v0.5 build planning. Status: Complete. `conversation_reference`: descriptive text per DEC-025 (Claude.ai conversation that opened against `v0.5-conversation-2-kickoff.md`, settled the ten questions in the kickoff §5.1, produced `ui-PRD-v0.5.md`, `ui-v0.5-implementation-plan.md`, and the five Claude Code prompts for slices A–E). `topics_covered` opens with the verbatim kickoff prompt followed by a structured summary of the seven decisions and the operational batch.
- **DEC-098** — v0.5 slice breakdown: five slices, foundation+migration in A, schema+API in B, panel UI in C, switching in D, closeout in E.
- **DEC-099** — Engagement UI affordance placement: top-strip switching above sidebar + Engagements sidebar group above Governance with one entry + dual paths to the management panel.
- **DEC-100** — Single-gesture engagement creation+activation: New Engagement dialog runs POST + file creation + activation in one click with graceful inline failure recovery.
- **DEC-101** — Forbid soft-delete on active engagement: delete dialog refuses with inline redirect to switch first; edge case wording for last-engagement install.
- **DEC-102** — Null default for `engagement_export_dir`: dialog field empty by default with "Optional — leave blank to disable auto-export" placeholder.
- **DEC-103** — Meta DB exports at `db-export/meta/engagements.json`: subdirectory parallel to dogfood content exports, file-watch refresh per the standard v0.3+ pattern.
- **DEC-104** — v0.5 PRD approval. Records the PRD's transition from "Draft — pending approval" to "Approved" — assigned at the approval pass.
- **References** — `decided_in` from SES-029 to each of DEC-098 through DEC-104.

No new planning items are authored at this PRD's closeout. PI-017 (multi-tenant API+MCP migration) was authored at SES-026's closeout. The User Process Guide v0.2 update is named as deferred work in §2 Out of Scope and §6.5 but is not a tracked PI yet; if real use shows the v0.1 drift is friction, a PI is authored in v0.5.1 or v0.6.

A status update reflecting that UI v0.5 is now in build (phase `"v0.5 in build"`, version label incremented from the v0.4-shipped value to the next sequence number) is also appropriate at the same time.

---

*End of document.*
