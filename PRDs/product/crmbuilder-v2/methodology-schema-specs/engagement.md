# Methodology Entity Schema Spec — `engagement`

**Last Updated:** 05-16-26 19:00
**Status:** Draft v1.0 — produced by v0.5 Conversation 1
**Position in workstream:** Sole new methodology entity type in the v0.5 engagement-management workstream
**Predecessor conversation:** v0.5-orientation conversation (SES-025; close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_025.json`)
**Companion document:** `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` (this conversation's other deliverable)
**Successor conversation:** v0.5 Conversation 2 — build planning

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-16-26 19:00 | Doug Bower / Claude (SES-026) | Initial draft. Produced by v0.5 Conversation 1, which combined multi-engagement architecture design with engagement schema design because the two were tightly coupled. Establishes the `engagement` entity type for v2's storage layer at minimum-viable v0.5 scope: identifier (`ENG-NNN`), code (mirrors v1's `Client.code` constraint exactly), name, purpose, status (`active` / `paused` / `archived` with free transitions), audit timestamps, plus two operational fields (`engagement_last_opened_at` for picker ordering; `engagement_export_dir` for split exports). Engagement records live in a separate meta DB at `crmbuilder-v2/data/engagements.db`, distinct from per-engagement DBs at `crmbuilder-v2/data/engagements/{code}.db`. |

---

## Change Log

**Version 1.0 (05-16-26 19:00):** Initial creation. Defines `engagement` as the v2 methodology entity type that hosts the routing-level metadata for each engagement (one client implementation project plus the v2-build dogfood). Establishes ten fields (`engagement_identifier`, `engagement_code`, `engagement_name`, `engagement_purpose`, `engagement_status`, `engagement_last_opened_at`, `engagement_export_dir`, plus inherited timestamps), three-status lifecycle (`active` / `paused` / `archived`) with free transitions and rejection-via-soft-delete, no outgoing relationships in v0.5, standard endpoint set served from the meta DB (engagement endpoints do not depend on the active engagement), and a deliberately deferred UI shape (engagement is structurally different from the four v0.4 methodology entity types — it is v2-install-level routing metadata, not domain-scope content — so it does not fit the Methodology sidebar group; Conversation 2 picks the layout in coordination with the styling workstream). One decision (DEC-086, schema and lifecycle) plus eight prior decisions in this conversation that frame the engagement's surrounding architecture. Acceptance criteria captured as twelve testable statements.

---

## 1. Purpose and Position

This document specifies the `engagement` entity type for v2's storage layer. It is the sole new methodology entity type in the v0.5 engagement-management workstream. The companion document `multi-engagement-architecture.md` specifies the surrounding routing architecture (discovery, persistence, API server model, identifier scope, migrations, dogfood-migration mechanism, exports location) that the engagement entity sits within.

The workstream is governed by `v0.5-engagement-management-workstream-plan.md`. The engagement entity follows the conventions established in the methodology-entity-schema-design workstream (DEC-046 parent-prefix field naming; DEC-068 spec-guide section 6 amendment), though it differs structurally from the four v0.4 methodology entity types in three important ways:

- **Engagement records live in a separate meta DB**, not in each per-engagement DB. The meta DB at `crmbuilder-v2/data/engagements.db` hosts the `engagements` table and serves as the v2-install-level registry. Per-engagement DBs (`crmbuilder-v2/data/engagements/{code}.db`) host the v0.4 methodology entities (domain, entity, process, crm_candidate) plus governance entities (decision, session, planning_item, etc.) — but they do not host engagement records.
- **Engagement records are created intentionally, not propose-verified.** The domain pattern's `candidate` → `confirmed` lifecycle does not fit. Engagement records default to `active` and move through an operational lifecycle (`active` ↔ `paused` ↔ `archived`) with free transitions.
- **Engagement is routing metadata, not domain-scope content.** It carries no relationships to other entity types in v0.5; per-engagement DB entities (domain, entity, process, etc.) do not reference back to engagement records because engagement is implicit context for everything in the engagement's own DB.

The schema in v0.5 is intentionally minimum-viable. It captures what's needed to identify engagements, list them in a picker, route per-engagement DB connections, and track operational state. Cross-engagement reporting, access control, v1-Client import, and renderers are deliberately deferred.

---

## 2. Summary

An `engagement` record in v2 represents one engagement — one CRM implementation project (e.g., Cleveland Business Mentors) or the v2-build's own dogfood (CRMBUILDER). Each v2 install hosts a small number of engagement records (typically one dogfood plus zero or more client engagements; one to five total is the realistic working range). Engagement records carry:

- A v2-internal identifier (`ENG-NNN`) and a stable human-facing code (`CRMBUILDER`, `CBM`, etc., constrained to match v1's `Client.code` regex exactly so the same code can be used in both systems if useful later).
- A human-readable name and a short statement of the engagement's purpose.
- An operational status (`active` / `paused` / `archived`) capturing whether work is currently in scope, on hold, or wound up.
- Two operational columns supporting v0.5's routing architecture: `engagement_last_opened_at` (for picker ordering and "restore last-active" UX) and `engagement_export_dir` (the filesystem path where this engagement's git-tracked JSON snapshots land).
- Standard audit timestamps.

The schema does not in v0.5 carry: a path field for the engagement's own DB (per Q2, the path is conventional from `engagement_code`); access-control or auth metadata; relationships to v1's Client master table; foreign keys to anything else.

The engagement record's lifecycle is independent of its existence-in-the-record: an engagement may be soft-deleted (via `engagement_deleted_at`) regardless of its status, and restored to its pre-deletion status. The principle established by `domain.md` §3.4 — "status values track engagement-scope lifecycle; soft-delete tracks existence-in-the-record" — carries here, though the lifecycle vocabulary differs (engagement uses `active`/`paused`/`archived` rather than domain's `candidate`/`confirmed`/`deferred`).

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `engagement` |
| Display name (singular) | Engagement |
| Display name (plural) | Engagements |
| Identifier prefix | `ENG` |
| Identifier format | `ENG-NNN`, zero-padded to 3 digits (e.g., `ENG-001`, `ENG-042`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /engagements/next-identifier` |
| Storage location | Meta DB at `crmbuilder-v2/data/engagements.db`, `engagements` table |

**Identifier-prefix justification.** `ENG` is three letters, consistent with the v2 governance-entity norm and with the soft-3-letter posture established in `domain.md` §3.1. No collision with existing prefixes (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRMC). The `ENG` vs `ENT` (entity) distinction is unambiguous on the wire (different prefixes) and in conversation (different entity-type names).

**Identifier scope.** Per DEC-082, engagement identifiers scope to the meta DB — one sequence per v2 install. On Doug's laptop, the dogfood is `ENG-001`, CBM is `ENG-002`, and so on. Reinstalling v2 from scratch and recreating engagements resets the numeric sequence (the engagement_code values remain the stable handles).

### 3.2 Fields

Field naming follows the parent-prefix convention from DEC-046: all fields including identifier and timestamps are prefixed `engagement_`.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `engagement_identifier` | TEXT | yes | server-assigned | `^ENG-\d{3}$`, unique | The methodology-entity identifier in `ENG-NNN` format. Server-assigned when omitted from POST body. |
| `engagement_code` | TEXT | yes | — | `^[A-Z][A-Z0-9]{1,9}$` (length 2–10, first char uppercase letter, body uppercase letters or digits); case-insensitive unique within the meta DB | Stable human-facing handle. Used as the per-engagement DB filename (`crmbuilder-v2/data/engagements/{engagement_code}.db`). Mirrors v1's `Client.code` constraint exactly so the same code can be used in both systems if useful later. Examples: `CRMBUILDER`, `CBM`. |
| `engagement_name` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the meta DB | Human-readable engagement name. Examples: "CRM Builder v2", "Cleveland Business Mentors". |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `engagement_purpose` | TEXT | yes | — | non-empty trimmed | One- to two-sentence statement of what the engagement is for. Plain text in v0.5; markdown support deferred to real-use signal. Example: "Dogfood instance hosting the v2 build's own governance content (sessions, decisions, planning items, methodology catalog)." |

**Three deliberate omissions from the domain.md pattern.** Engagement does not carry `engagement_description` or `engagement_notes` fields. The reason: engagement is routing metadata, not methodology content. The single `engagement_purpose` field carries everything v0.5 needs; expanding to purpose + description + notes would be gratuitous scope. Internal-scratchpad notes (the domain-spec analog of `domain_notes`) belong inside the engagement's own DB (against the engagement's sessions and decisions), not on the engagement record itself. Engagement also does not carry an `engagement_db_path` field — per DEC-079, the DB path is derived from `engagement_code` conventionally; configurable per-engagement paths are a future enhancement.

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `engagement_status` | TEXT | yes | `active` | enum: `active` \| `paused` \| `archived`; valid transitions per §3.4 | Operational lifecycle status. See §3.4 for the transition map. |

#### 3.2.4 Relationship fields

None in v0.5. Engagement has no outgoing FK columns and no source-side use of the references entity. Per-engagement DB entities (domain, entity, process, crm_candidate, decision, session, etc.) do not carry inbound references to engagement records — engagement is implicit context for everything in the engagement's own DB. See §3.3.

#### 3.2.5 Operational fields (engagement-specific, supporting the routing architecture)

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `engagement_last_opened_at` | DATETIME | no | null | ISO 8601 UTC when set | Set by the desktop app at engagement activation. Used by the picker UX to order engagements by recency and to restore the last-active engagement on app launch. (See multi-engagement-architecture.md §3.3.) |
| `engagement_export_dir` | TEXT | no | null | when set: must be an existing writable directory; absolute filesystem path | Where this engagement's git-tracked JSON snapshots land. Dogfood's value is set by the v0.5 first-launch migration to the absolute path of `PRDs/product/crmbuilder-v2/db-export/` (computed from the engine repo root). Client engagements set their value at creation time via the New-Engagement dialog. Null disables auto-export with a log warning at activation. (See multi-engagement-architecture.md §3.8.) |

#### 3.2.6 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `engagement_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `engagement_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `engagement_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |

**No storage-level length caps.** Text fields are unconstrained at the storage layer in v0.5, consistent with `domain.md`'s posture. UI placeholder text provides soft guidance. Pathological-input handling deferred to real-use signal; length caps are easy to add via migration in v0.6+ if needed.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

None in v0.5. Engagement has no FK fields to other entity types, no self-referential hierarchy, and no source-side use of the references entity. The engagement record stands alone in the meta DB.

#### 3.3.2 Inbound relationships

None in v0.5. Per-engagement DB entities (domain, entity, process, crm_candidate, decision, session, etc.) do not reference engagement records. The reason: each per-engagement DB is itself implicitly scoped to one engagement, so an inbound `process_belongs_to_engagement` or `domain_belongs_to_engagement` reference would duplicate information that is already encoded by the engagement DB the record lives in.

No new `relationship_kind` vocabulary entries are introduced by this spec.

#### 3.3.3 Cross-spec relationship-kind naming convention — adopted, not established

This spec adopts the `{source}_{verb}_{target}` source-first naming pattern established by `domain.md` §3.3.3 (DEC-048). The pattern does not apply here because no relationships are declared.

#### 3.3.4 Hierarchy

Engagement does not use the self-referential parent-child hierarchy pattern. Engagements are top-level; sub-engagement structure is not part of v0.5's scope.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `active` | Currently in scope; work is happening (or pending). **Default starter status.** | (none — starter), `paused`, `archived` | `paused`, `archived` |
| `paused` | Temporarily not in active scope; engagement is on hold but not wound up. | `active`, `archived` | `active`, `archived` |
| `archived` | Wound up; kept for reference. May be reactivated. | `active`, `paused` | `active`, `paused` |

#### 3.4.2 Transition semantics

The engagement status lifecycle uses **free transitions** between all three values. No one-way gates, no propose-verify ceremony. The reason: engagement records are direct creations by the consultant (not proposed-then-verified by a client), so the domain pattern's one-way `candidate` → `confirmed` gate does not translate. Engagements legitimately move between `active`, `paused`, and `archived` in any direction as engagements pause, resume, wrap up, and reactivate.

The default starter status is `active`: a new engagement record (created via UI, via the dogfood migration, or via the New-Engagement dialog) starts active. Creating an engagement is an intentional act, not a propose-then-verify ceremony.

#### 3.4.3 Status independence from activation

Activating an engagement (the routing operation that makes it the live engagement — see multi-engagement-architecture.md §4) is **independent** of the engagement's status. A `paused` or `archived` engagement can still be activated, e.g., to view its historical data. Activation does not transition status; activation is descriptive routing, not lifecycle progression.

The desktop UI may render `paused` and `archived` engagements differently (greyed out, sorted to the bottom of the picker, etc.), but the engagement remains operable as long as the engagement's DB file is reachable.

#### 3.4.4 Rejection via soft-delete

When an engagement record is no longer wanted (created in error, duplicate, or otherwise abandoned), the right action is soft-delete (`DELETE /engagements/{identifier}`), not status transition. Soft-delete sets `engagement_deleted_at`; the row persists; the engagement disappears from the default picker; restore via POST `/restore` reverses the action. This mirrors `domain.md`'s rejection-via-soft-delete posture (DEC-047) and avoids introducing a `rejected` status that would duplicate the soft-delete mechanism.

Note that soft-delete on an engagement record does **not** delete the per-engagement DB file. The DB file remains at `crmbuilder-v2/data/engagements/{code}.db` and is recoverable via restore. Hard-delete-with-file is a separate operation the user explicitly requests (not part of v0.5's MVS scope; if needed, a v0.6+ enhancement).

#### 3.4.5 Soft-delete and active-engagement

If the currently-active engagement is soft-deleted, the active state is implicitly cleared: the next desktop launch finds `current_engagement.json` pointing at a soft-deleted engagement, treats it as unreachable, starts with no active engagement, and prompts the user via the picker UX. Conversation 2 may choose to forbid soft-deleting the active engagement (forcing the user to switch first), or to allow it and clean up the active-engagement state automatically. Either is correct; this spec records the default expectation but does not lock the behavior.

#### 3.4.6 Soft-delete semantics

Soft-delete inherits v2's standard behavior:

- DELETE sets `engagement_deleted_at` to the current ISO 8601 UTC timestamp.
- Soft-deleted engagements do not appear in `GET /engagements` by default.
- `GET /engagements?include_deleted=true` returns soft-deleted engagements alongside live ones.
- POST `/engagements/{identifier}/restore` clears `engagement_deleted_at` and reappears the record in the default list.
- Restore on a record that is not soft-deleted returns HTTP 422.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/engagements` | — | List endpoint. Returns active records by default. Supports `?include_deleted=true`. Reads from the meta DB. |
| GET | `/engagements/{engagement_identifier}` | — | Single fetch by identifier. Returns 404 if not found. Reads from the meta DB. |
| POST | `/engagements` | full record minus `engagement_identifier` (server-assigned) | Create. Returns 201 with the assigned identifier. Writes the engagement row to the meta DB. Does NOT create the per-engagement DB file in v0.5 — that is a separate desktop-side step (see §3.5.5). |
| PUT | `/engagements/{engagement_identifier}` | full record | Full replace. Engagement_identifier in body must match the path; mismatch returns 422. Writes the meta DB. |
| PATCH | `/engagements/{engagement_identifier}` | partial record | Partial update. Status-transition validation applied per §3.4.1. Writes the meta DB. |
| DELETE | `/engagements/{engagement_identifier}` | — | Soft-delete; sets `engagement_deleted_at` on the meta DB row. Does NOT delete the per-engagement DB file. Idempotent. |
| POST | `/engagements/{engagement_identifier}/restore` | — | Clears `engagement_deleted_at`. Returns 422 if not soft-deleted. |
| GET | `/engagements/next-identifier` | — | Returns `{"next": "ENG-NNN"}` for the next available identifier in the meta DB sequence. |

**Engagement endpoints serve from the meta DB, not the active engagement's DB.** This is the architectural detail flagged in `multi-engagement-architecture.md` §3.10: the API server connects to two databases simultaneously and routes engagement endpoints to the meta DB while routing all other endpoints to the active engagement's DB.

#### 3.5.2 Identifier auto-assignment

`engagement_identifier` is server-assigned on POST when omitted from the request body. Assignment queries the current maximum `engagement_identifier` in the meta DB (including soft-deleted records, to avoid identifier reuse) and increments the numeric suffix. The `GET /engagements/next-identifier` helper exposes the same logic.

Concurrent identifier-assignment behavior (locking, optimistic retry, etc.) is implementation-level and follows the v0.3-established pattern for governance entity identifier assignment.

#### 3.5.3 Status-transition validation

Status transitions are validated server-side at the access layer. PATCH or PUT requests that specify an `engagement_status` value that is not a valid successor of the current value (per §3.4.1) return HTTP 422 with:

```
{
  "error": "invalid_status_transition",
  "from": "<current status>",
  "to": "<requested status>"
}
```

Because the transition map has free transitions between all three values, the only invalid transition is "to an enum value not in `{active, paused, archived}`," which is rejected as `invalid_enum_value` (422) per standard v2 validation.

The default-`active` rule applies on POST: if `engagement_status` is omitted, the server assigns `active`. POST with `engagement_status` explicitly set to `paused` or `archived` is permitted (e.g., for bulk-importing engagements from another source in some future workflow).

#### 3.5.4 No activate endpoint

The "activate engagement X" operation is **not an API operation in v0.5**. Activation is a desktop-side orchestration (see `multi-engagement-architecture.md` §4) involving:

1. Reachability check on the engagement's DB file.
2. Pre-flight Alembic migration on the engagement's DB.
3. Kill the running API and MCP subprocesses.
4. Write `current_engagement.json`.
5. PATCH `engagement_last_opened_at`.
6. Update in-memory `ActiveEngagementContext`.
7. Launch new API/MCP subprocesses with the new env.
8. Emit `active_engagement_changed` signal; panels refresh.

The API server itself cannot perform activation because activation requires killing and respawning the API process. The desktop owns this orchestration. External clients (curl, MCP, scripts) do not have an activation primitive in v0.5; the env-var override (`CRMBUILDER_V2_DB_PATH`) remains the escape hatch.

When the multi-tenant migration (PI-017) lands, the API gains the ability to switch engagements without restart, and an activation endpoint becomes possible at that time.

#### 3.5.5 Engagement creation and per-engagement DB file creation

POST `/engagements` writes the engagement row to the meta DB but does **not** create the per-engagement DB file. Creating the DB file is a desktop-side step that follows engagement creation:

1. Desktop calls POST `/engagements` to insert the meta DB row.
2. On 201 success, the desktop computes the per-engagement DB path from `engagement_code`.
3. Desktop creates the DB file at that path (an empty SQLite file, then `alembic upgrade head` to bring it to the current schema).
4. Optionally, the desktop activates the new engagement (per §3.5.4).

This split is intentional. The API server is bound to one engagement DB at a time (Q4 = one-process-per-engagement); spawning new SQLite files is outside the API server's lifecycle. Conversation 2 details the exact code path; the v0.5 desktop UI likely presents engagement creation + activation as a single user gesture (clicking "Create Engagement" both creates the meta-DB row and activates the new engagement immediately).

#### 3.5.6 Other endpoint specifics

- All endpoints return JSON.
- 4xx error responses use the existing v2 error envelope shape.
- No additional list query parameters beyond `?include_deleted=true` in v0.5. Client-side filtering over the small expected engagement count (1–5 per install) is sufficient.

### 3.6 UI Considerations

This spec **deviates** from the spec guide's default ListDetailPanel-in-the-Methodology-sidebar-group layout. The deviation is justified because engagement is structurally different from the four v0.4 methodology entity types: it is v2-install-level routing metadata, not domain-scope content; it lives in the meta DB, not the active engagement's DB; and it needs two distinct affordances rather than one.

#### 3.6.1 Two needed affordances

1. **A switching UI** — always visible, shows the currently-active engagement, supports the kill-relaunch dance described in `multi-engagement-architecture.md` §4. Candidate placements: top-bar picker, status-bar dropdown, dedicated panel, or a combination.

2. **A management UI** — full CRUD on engagement records (create, edit, soft-delete, restore). Candidate placements: a dedicated sidebar entry under a new "Engagements" group (above Governance and Methodology), a settings-style modal, or a hybrid (the management UI is opened from the switching UI's "Manage..." affordance).

#### 3.6.2 Conversation 2 settles the visual shape

The exact placement and styling are a Conversation 2 / Slice B+C decision in coordination with the styling workstream (PI-001) per the boundary discipline established in DEC-076. This spec does not lock the visual shape because:

- Engagement does not fit the existing Methodology sidebar-group framing (where the four v0.4 methodology entities live as peers).
- The right answer depends on the styling workstream's emerging design tokens and sidebar visual treatment.
- The two affordances have different visibility needs (switching is always-visible; management is occasional-access).

#### 3.6.3 Behavioral requirements (independent of visual shape)

Regardless of the visual layout Conversation 2 picks, the engagement UI must support:

- **Picker.** Display engagements ordered by `engagement_last_opened_at` descending (most recently opened first). Visually distinguish the active engagement. Visually distinguish `paused` and `archived` engagements (e.g., greyed-out, sorted to the bottom).
- **Create.** Form with `engagement_code` (with the regex constraint hint visible), `engagement_name`, `engagement_purpose`, optional `engagement_export_dir` (with a directory-browser button). On submit: POST to create the meta-DB row; create the per-engagement DB file; activate the new engagement.
- **Edit.** Form with `engagement_code` read-only (the path depends on it; renaming requires a file move and is a v0.6+ enhancement), all other fields editable. On submit: PATCH the meta-DB row.
- **Soft-delete.** Confirmation dialog (edge-text per v0.3 patterns: user types the engagement_code). Soft-delete the row; if the deleted engagement was active, clear the active state and prompt for picker selection.
- **Restore.** Toggle "Show deleted" to include soft-deleted engagements in the picker; per-row Restore affordance.
- **Switch.** From the picker, clicking a non-active engagement initiates the kill-relaunch activation sequence with a "Switching engagement..." progress indicator.

#### 3.6.4 Refresh on file-watch

The engagement panel participates in the standard v0.3+ file-watch refresh pattern: changes to `db-export/engagements.json` (or wherever the meta-DB exports land — Conversation 2 may choose to export the meta DB to its own location) trigger a panel refresh.

### 3.7 Acceptance Criteria

The following twelve statements define what "the engagement entity type is correctly implemented in v0.5" looks like. Each is concrete and testable; v0.5 build planning translates these into specific test cases.

1. **Meta DB schema migration applies cleanly.** Alembic migration creates the `engagements` table with all ten columns (`engagement_identifier`, `engagement_code`, `engagement_name`, `engagement_purpose`, `engagement_status`, `engagement_last_opened_at`, `engagement_export_dir`, `engagement_created_at`, `engagement_updated_at`, `engagement_deleted_at`), correct types and constraints, and runs both forward and backward without error.

2. **`engagement_identifier` format constraint enforced.** Insertions with `engagement_identifier` not matching `^ENG-\d{3}$` raise a validation error at the access layer.

3. **`engagement_code` constraint enforced.** Insertions with `engagement_code` not matching `^[A-Z][A-Z0-9]{1,9}$` (or empty, or containing lowercase / special characters / leading digits) raise a validation error. Case-insensitive uniqueness within the meta DB is enforced; attempting to insert `cbm` when `CBM` exists fails.

4. **`engagement_status` enum and transition validation.** Insertions with `engagement_status` outside `{active, paused, archived}` are rejected with HTTP 422 `invalid_enum_value`. The default-on-omit (`active`) is applied. Transitions between any of the three values are accepted (free transitions); transitions to invalid values return 422.

5. **`engagement_export_dir` validation when set.** Insertions and updates with `engagement_export_dir` set to a non-existent directory, an existing file (not directory), or a non-writable path return HTTP 422. Null is accepted.

6. **Access-layer methods exist with expected signatures.** `client.list_engagements()`, `client.get_engagement(identifier)`, `client.create_engagement(...)`, `client.update_engagement(identifier, ...)`, `client.patch_engagement(identifier, ...)`, `client.delete_engagement(identifier)`, `client.restore_engagement(identifier)`, `client.next_engagement_identifier()` exist and pass unit tests covering happy path and at least one error case each.

7. **REST endpoints return expected responses.** All eight endpoints from §3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the v2 error envelope.

8. **Identifier auto-assignment helper.** `GET /engagements/next-identifier` returns `{"next": "ENG-NNN"}` for the next available number. POST with `engagement_identifier` omitted assigns the same value. Two concurrent POSTs do not assign the same identifier (concurrent-insert test required).

9. **Soft-delete and restore round-trip.** DELETE sets `engagement_deleted_at`; the record disappears from `GET /engagements`. `GET /engagements?include_deleted=true` shows it. POST `/restore` clears `engagement_deleted_at`; the record reappears in the default list. Restore on a record that is not soft-deleted returns 422. The per-engagement DB file is not touched by either operation.

10. **Engagement endpoints serve from the meta DB.** A test that has the meta DB populated with engagement A and the active engagement DB populated with engagement B's data confirms that `GET /engagements/A` returns A's record (not B's data, not "not found"). All other endpoints (e.g., `GET /sessions`) continue to read from the active engagement's DB.

11. **`engagement_last_opened_at` is updated on activation.** Activating an engagement (via the desktop's switch flow) PATCHes the engagement record's `engagement_last_opened_at` field. The meta DB row reflects the update; `GET /engagements/{id}` returns the new value.

12. **Sample dogfood and CBM engagement records.** Doug can run v0.5 first launch against an existing `v2.db`; the dogfood migration creates ENG-001 (CRMBUILDER) and rehomes `v2.db` to `engagements/CRMBUILDER.db`. Doug can then create ENG-002 (CBM) via the New-Engagement dialog; the meta DB row is inserted, the per-engagement DB file is created at `engagements/CBM.db` with Alembic at head, and activation switches to CBM successfully.

### 3.8 Open Questions and Deferred Decisions

Categorised per the spec guide §3.8 convention. Each entry is one paragraph.

#### 3.8.1 For v0.5 build (Conversation 2) to settle

**[v0.5 build] Visual shape of the engagement UI.** This spec specifies the behavioral requirements but not the visual layout (top-bar picker vs sidebar group vs hybrid). Conversation 2 picks the layout in coordination with the styling workstream per the §3.6.2 deviation rationale. The schema and API are not affected by the visual choice; only the panel/dialog modules differ.

**[v0.5 build] Whether engagement creation and activation are a single gesture or two.** The §3.5.5 split (POST creates the meta-DB row; the desktop creates the file; activation is separate) is correct at the API/access-layer level, but the user-facing affordance may collapse the three steps into one "Create + Activate" gesture or expose them separately. Conversation 2 picks.

**[v0.5 build] Whether to forbid soft-deleting the active engagement.** §3.4.5 names this as a Conversation 2 question — either forbid the operation (force switch first) or allow it and clean up the active state automatically. Either is correct; this spec does not lock the behavior.

**[v0.5 build] `engagement_last_opened_at` update path during the switch dance.** The activation sequence updates this field while the API is in the middle of being killed/restarted (step 7 of the architecture doc §4). Two implementation paths work: (a) desktop opens the meta DB directly during the dance; (b) defer the update until the new API is up. Either is correct.

**[v0.5 build] Refresh trigger for engagement-panel file-watch.** The engagement record lives in the meta DB; the meta DB may have its own JSON export (e.g., `db-export/engagements.json`) or may not (engagement records may only be accessible via the API). Conversation 2 picks; the panel's refresh mechanism depends on the choice.

#### 3.8.2 For real use to surface

**[real-use] Whether `engagement_purpose` plain text suffices.** Plain text in v0.5. If real engagement-management use surfaces a need for markdown or richer content, a v0.6+ migration adds support. Same posture as `domain.md`'s text fields.

**[real-use] Whether the engagement_code-derived DB filename suffices.** Per DEC-079, no `engagement_db_path` field in v0.5. If real use surfaces a need to override (e.g., a client engagement traveling with its repo), a v0.6+ migration adds nullable `engagement_db_path` and the move becomes a one-time operation.

**[real-use] Whether more than 5 engagements per install is realistic.** v0.5 assumes a small number (1–5). If real use shows substantially more (consultants managing 20+ engagements), the picker UX may need scroll/filter affordances; the API may need server-side filters; the meta DB may need indexed columns. None of this is anticipated in v0.5's MVS scope.

**[real-use] Whether `paused` is a useful state.** Three states (`active` / `paused` / `archived`) was chosen over two (`active` / `archived`) on the working assumption that "temporarily on hold" is distinct from "wound up." If real use shows `paused` is never used, a v0.6+ enum-narrowing migration drops it. (Enum narrowing requires data validation that no existing rows hold the dropped value.)

#### 3.8.3 For v0.5+ tracked separately

**[v0.6+] PI-017 — Multi-tenant API + MCP migration.** Anchored by DEC-081. When v2 transitions from prototype to production, the API and MCP servers refactor from one-process-per-engagement to multi-tenant. Engagement endpoints likely gain an activation API operation at that time.

**[v0.6+, candidate, not yet PI] Optional `engagement_db_path` field.** Nullable column allowing per-engagement override of the conventional path. Triggered if/when an engagement needs to travel with a client repo across machines.

**[v0.6+, candidate, not yet PI] Engagement rename support.** v0.5 has `engagement_code` read-only in the edit dialog because changing the code requires moving the DB file. If real use surfaces a rename use case, a v0.6+ enhancement adds a rename operation that updates the meta-DB row, moves the file, and re-points any external references.

**[v0.6+, candidate, not yet PI] Hard delete (record + file).** v0.5 soft-delete preserves the per-engagement DB file. If real use surfaces a need for "really delete this engagement and reclaim disk space," a v0.6+ enhancement adds a hard-delete operation that also deletes the file. Likely guarded by edge-text confirmation and only allowed on soft-deleted records.

**[v0.6+, candidate, not yet PI] Engagement-level access control.** Workstream plan §3.2 deferred this. v0.5 is single-user single-machine. Multi-user / authentication / authorization is a much larger workstream.

**[v0.6+, candidate, not yet PI] v1 Client import.** Workstream plan §3.2 deferred this. v1 and v2 stay independent in v0.5. A separate small workstream can import v1's `master.db` `Client` rows into v2's `engagement` table later if there's value.

**[v0.6+, candidate, not yet PI] Cross-engagement queries and reporting.** Workstream plan §3.2 deferred this. Each engagement is isolated in v0.5. After PI-017 (multi-tenant API), cross-engagement queries become technically feasible; whether to expose them is a separate scope question.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following decision is the spec's primary anchor. It is authored at conversation close via the standard `apply_close_out.py` script reading `PRDs/product/crmbuilder-v2/close-out-payloads/ses_026.json`.

- **DEC-086 — Engagement entity schema, lifecycle, and API surface.** Bundles Q10 (field set, identifier prefix `ENG`, API surface, UI deviation) and Q10b (status lifecycle: `active` / `paused` / `archived` with free transitions). Linked to SES-026 via a `decided_in` reference.

The eight prior decisions in this conversation frame the engagement's surrounding architecture and are cited by `multi-engagement-architecture.md` rather than by this spec directly:

- **DEC-078** — Engagement discovery model (meta DB).
- **DEC-079** — Per-engagement DB file location (engine repo, conventional paths). Justifies the no-`engagement_db_path`-field decision in §3.2.
- **DEC-080** — Active-engagement state persistence. Justifies the `engagement_last_opened_at` field in §3.2.
- **DEC-081** — API + MCP server model (one process per engagement, v0.5; multi-tenant target). Justifies the no-activate-endpoint posture in §3.5.4.
- **DEC-082** — Identifier scope. Justifies `engagement_identifier` scoping to the meta DB in §3.1.
- **DEC-083** — Migrations across engagements (lazy at engagement-open).
- **DEC-084** — Dogfood migration (one-shot explicit). Determines the initial CRMBUILDER engagement record values.
- **DEC-085** — Per-engagement exports (split via `engagement_export_dir` field). Justifies the `engagement_export_dir` field in §3.2.

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry.
- `PRDs/product/crmbuilder-v2/v0.5-engagement-management-workstream-plan.md` — workstream master plan.
- `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — companion deliverable specifying the routing architecture surrounding this entity type.
- `PRDs/product/crmbuilder-v2/v0.5-conversation-1-kickoff.md` — this conversation's seed prompt.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template this document follows (with the §3.6 UI-shape deviation justified above).
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — foundational schema spec setting the conventions this spec inherits.
- `automation/db/master_schema.py` — v1 Client master schema; source of the `engagement_code` regex constraint and the master-DB pattern precedent.
- `automation/ui/active_client_context.py` — v1 active-client context; precedent for the in-memory `ActiveEngagementContext` pattern.

#### 3.9.3 Related prior decisions informing this spec

- **DEC-001** — v2 charter framing. Engagement management is the next migration item from v1 in the planned sequence.
- **DEC-023** — Process model: UI process spawns the API subprocess. The activation sequence builds on this lifecycle.
- **DEC-039** — Multi-tenancy posture (one v2 instance per engagement). This spec operationalises that finding rather than superseding it.
- **DEC-046** — Parent-prefix field-naming convention. All engagement fields prefixed `engagement_`.
- **DEC-047** — Status-tracks-lifecycle / soft-delete-tracks-existence principle from `domain.md`. Carried here.
- **DEC-068** — Spec guide §6 amendment recording the methodology-entity conventions. Engagement adopts these conventions despite differing structurally from the four v0.4 methodology entities.
- **DEC-075** — v0.5 release scope. This spec delivers the schema half of that scope.

#### 3.9.4 Predecessor and successor conversations

- **Predecessor:** SES-025 — v0.5-orientation conversation. Produced the workstream plan, the styling workstream plan, and the paper-test deferral.
- **Successor:** v0.5 Conversation 2 — build planning. Takes this spec and `multi-engagement-architecture.md` as inputs; produces `ui-PRD-v0.5.md`, `ui-v0.5-implementation-plan.md`, and slice build prompts.

---

*End of document.*
