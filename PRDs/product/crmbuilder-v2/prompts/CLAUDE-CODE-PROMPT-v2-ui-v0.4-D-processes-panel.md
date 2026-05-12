# CLAUDE-CODE-PROMPT-v2-ui-v0.4-D-processes-panel

**Last Updated:** 05-12-26 10:30
**Series:** v2-ui-v0.4
**Slice:** D (4 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md`
**Companion schema spec:** `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md`
**Predecessor slice:** v2-ui-v0.4-C (Entities panel — `entity_scopes_to_domain` exercised end-to-end; create-then-attach flow established)

## Purpose

This is the fourth of six slices in v0.4. This prompt builds slice **D — Processes panel end-to-end**.

Slice D implements the `process` entity type fully per `process.md` — schema migration, access-layer methods, REST endpoints, desktop panel with master and detail views, CRUD dialogs, and tests covering all 15 acceptance criteria from `process.md` section 3.7.

Three slice-specific aspects diverge from the slice B/C template:

1. **No `status` field; `process_classification` enum carries the priority taxonomy.** Per spec deviation in DEC-056, `process` lacks a `process_status` field. The four-value `process_classification` enum (`unclassified`, `mission_critical`, `supporting`, `deferred`) implements the methodology's Principle 3 priority distinction. Transition gate is one-way out of `unclassified`; free movement among the three classified values.

2. **Required FK `process_domain_identifier` as a direct scalar column.** Each process belongs to exactly one domain per spec section 3.4.5. The FK is a required scalar field in the create dialog (not a reference attachment); a process cannot be created without a domain. This contrasts with slice C where domain affiliations are references attached after creation.

3. **Bidirectional `process_hands_off_to_process` references with directional rendering.** Process-to-process handoffs use the references entity per spec 3.3.2. The detail pane renders them in two distinct sub-sections within the `ReferencesSection` widget: "Hands off to" (this process is the source) and "Receives from" (this process is the target). The cascading vocab dialog from v0.3 admits the kind automatically via `RELATIONSHIP_RULES`; this slice verifies the bidirectional rendering UX.

## Project context

Slices B and C established the methodology entity panel pattern. Slice D follows the pattern with process-specific adjustments. Live `domain` records from slice B back the required FK; live `process` records from this slice back outbound handoff references. After slice D, the Methodology sidebar group has three entries (Domains, Entities, Processes); slice E completes the four with CRM Candidates.

The spec is authoritative. This prompt cites the spec's section numbers rather than restating content.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity:
   - `git config user.name` → `Doug Bower`
   - `git config user.email` → `dbower44022@users.noreply.github.com`
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice C is at HEAD or recently committed.
6. API health: `curl -sf http://127.0.0.1:8765/health` returns 200; start via `uv run crmbuilder-v2-api &` if not.
7. Confirm slices A, B, C tests pass: `uv run pytest tests/crmbuilder_v2/ -v`.

## Reading order

Before producing any code, read:

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` section 4.5 (Processes panel) and section 4.7 (coordinated create-then-attach flow).
3. `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md` section 4 Step D.
4. `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` — authoritative for this slice. All 15 acceptance criteria in section 3.7 are the gate. Pay particular attention to section 3.4.2 (classification lifecycle), section 3.4.5 (domain re-affiliation), and section 3.5.4 (decomposed handoff handling).
5. `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` section 3.5 — `GET /domains` is the backing for the FK combo in the process create dialog.
6. Slice B's domain panel and slice C's entity panel implementations — slice D mirrors the pattern with process-specific adjustments.
7. The existing `ReferencesSection` widget at `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py` (or wherever it lives in v0.3) — slice D may need a small extension to support the two-sub-section split for "Hands off to" / "Receives from"; assess on first contact.

## Step 1 — Alembic migration: create the `processes` table

Create a revision named like `0NNN_v0_4_create_processes_table.py`. The migration creates the `processes` table per `process.md` section 3.2:

| Column | Type | Constraints |
|--------|------|-------------|
| `process_identifier` | TEXT | PRIMARY KEY, format `^PROC-\d{3}$` (CHECK), unique |
| `process_name` | TEXT | NOT NULL; case-insensitive engagement-global uniqueness enforced at access layer |
| `process_domain_identifier` | TEXT | NOT NULL, format `^DOM-\d{3}$` (CHECK); FK existence validated at access layer (not via SQL FOREIGN KEY constraint, matching v2's existing soft-FK convention) |
| `process_purpose` | TEXT | NOT NULL |
| `process_classification` | TEXT | NOT NULL, default `'unclassified'`, CHECK in `('unclassified', 'mission_critical', 'supporting', 'deferred')` |
| `process_classification_rationale` | TEXT | NULL allowed |
| `process_notes` | TEXT | NULL allowed |
| `process_created_at` | DATETIME | NOT NULL, default current_timestamp |
| `process_updated_at` | DATETIME | NOT NULL, default current_timestamp |
| `process_deleted_at` | DATETIME | NULL allowed |

**No `process_status` column** per the documented deviation in DEC-056. Classification carries the lifecycle.

**Identifier prefix is `PROC`** (four letters) per the documented deviation in DEC-055.

Mirror prior slices' table-migration patterns. Forward and backward reversible.

## Step 2 — Access-layer repository: `access/process.py`

Eight standard methods. Mirror slice B/C patterns with process-specific adjustments:

- **Identifier format:** `^PROC-\d{3}$`
- **Name uniqueness:** case-insensitive, engagement-global (no domain-scoping)
- **Classification enum:** `{unclassified, mission_critical, supporting, deferred}`
- **Classification-transition validation per spec 3.4.2:**
  - From `unclassified` → any of the three classified values permitted.
  - From any classified value → any other classified value permitted (free movement among the three).
  - No transition from any classified value back to `unclassified` (one-way out).
  - Invalid transitions raise `{"error": "invalid_classification_transition", "from": ..., "to": ...}`.
- **Domain-FK validation:** on `create_process` and any update that touches `process_domain_identifier`, query the `domains` repository for a live record matching the identifier; if not found (or soft-deleted at the time of the call), raise `{"error": "invalid_domain_reference", "domain_identifier": ...}`.
- **Domain re-affiliation per spec 3.4.5:** PATCH and PUT may modify `process_domain_identifier`. If the new value is missing or soft-deleted, the same `invalid_domain_reference` error fires. Re-affiliation does not cascade to inbound handoff references — those remain attached to the process by `process_identifier`, not by domain.
- **Soft-delete semantics:** standard pattern; outbound and inbound `process_hands_off_to_process` references are NOT cascade-deleted per spec 3.4.7.

JSON-export hook regenerates `db-export/processes.json` after any DB-changing operation.

## Step 3 — REST API router: `api/routers/processes.py`

Eight standard endpoints per `process.md` section 3.5.1. Mirror slice B/C router patterns with process-specific paths and validation. Error responses follow the v2 envelope:

- `invalid_classification_transition` → HTTP 422
- `invalid_domain_reference` → HTTP 422
- Standard identifier/name/format errors → HTTP 422 with v2 envelope

**Decomposed handoff handling per spec 3.5.4.** No `/processes/{id}/handoffs` shortcut endpoint, no inline-handoff field in POST/PUT/PATCH bodies. Handoffs attach via `POST /references` with:

```json
{
  "source_type": "process",
  "source_id": "PROC-NNN",
  "target_type": "process",
  "target_id": "PROC-NNN",
  "relationship_kind": "process_hands_off_to_process"
}
```

## Step 4 — Desktop UI panel: `ui/panels/processes.py`

### 4.1 Sidebar registration

Methodology sidebar group, position #3 (after Entities).

### 4.2 Master pane

Columns: Identifier / Name / Classification / Updated. **Column #3 is `process_classification`, not `process_status`** — the column header reads "Classification" and the cell values render the enum strings as-is (or with light human-readable formatting; "Mission Critical" vs "mission_critical" is a slice-execution call).

**No Domain column in v0.4** per the same posture as Entities — the column would render bare `DOM-NNN` identifiers without `domain.short_code`. Deferred to v0.5+ paired with PI-007 / PI-009.

Sort: Identifier ascending. Context menu: New / Edit / Delete / Restore.

### 4.3 Detail pane

Vertical layout per spec section 3.6.3:

1. `process_identifier` — read-only label
2. `process_name` — single-line text editor
3. `process_domain_identifier` — combo box backed by `GET /domains` (live records only); default selection per Open Question 3 of the PRD (alphabetical first or per-session memory)
4. `process_purpose` — multi-line text editor, placeholder "Brief description of what this process accomplishes"
5. `process_classification` — combo box with the four enum values; restrict available choices to valid successors of the current classification (one-way out of `unclassified`)
6. `process_classification_rationale` — multi-line text editor with **dynamic placeholder per classification**:
   - When classification is `mission_critical`: "Why this process is mission-critical — what mission failure looks like if it stops"
   - When classification is `supporting`: "Why this process supports rather than drives the mission"
   - When classification is `deferred`: "Why this process is deferred — what conditions would un-defer it"
   - When classification is `unclassified`: "(Classification not yet assigned)"
7. `process_notes` — multi-line text editor under collapsible "Internal notes" section header, collapsed by default
8. `ReferencesSection` widget — **two distinct sub-sections per spec 3.6.3**:
   - **"Hands off to"**: outgoing `process_hands_off_to_process` references where the current process is the source
   - **"Receives from"**: incoming `process_hands_off_to_process` references where the current process is the target
   - Other inbound/outbound kinds (none in v0.4 from spec-side; widget present for v0.5+ future kinds)

If the existing v0.3 `ReferencesSection` widget renders a single flat list, slice D either extends the widget to support sub-section labels keyed by `(kind, direction)` or implements the sub-section split at the panel layer (panel renders two `ReferencesSection` instances with pre-filtered content). The choice is a slice-execution implementation detail; either is acceptable.

### 4.4 Domain re-affiliation warning

Per spec section 3.4.5 and PRD section 4.5, if `process_domain_identifier` is changed via PATCH or PUT and the new domain has been soft-deleted between fetch and submit (rare race condition), display an inline warning on the detail pane and offer either to restore the domain or pick a different one. Implementation: inline warning text rendered above the FK combo when validation detects a stale soft-deleted target. No separate dialog.

### 4.5 CRUD dialogs

Create `ui/dialogs/process_crud.py`. Per DEC-067 create-then-attach flow:

- **Create dialog:** required scalar fields including `process_domain_identifier` (combo backed by `GET /domains` live records only) PLUS `process_name`, `process_purpose`, `process_classification` (defaults to `unclassified`), `process_classification_rationale` (optional unless classification ≠ `unclassified`), `process_notes`. Submit creates the process record only. Handoff references attach from the detail pane after creation.
- **Edit dialog:** same shape; identifier read-only; classification combo restricted to valid successors.
- **Delete dialog:** standard edge-text confirmation (user types `PROC-NNN`); soft-deletes the record; handoff references persist per spec 3.4.7.

### 4.6 File-watch wiring

Connect to the `processes_changed` signal slice A wired in `ui/refresh.py`.

## Step 5 — Storage client extensions

Add eight methods for processes in `ui/client.py` mirroring prior slices.

## Step 6 — Tests

Three test modules covering all 15 acceptance criteria from `process.md` section 3.7.

### 6.1 `tests/crmbuilder_v2/access/test_process.py`

Cover criteria 1–8 mirroring prior slices' access tests with process-specific adjustments.

Critical process-specific assertions:

- **Criterion 4 (classification enum + transitions):**
  - `unclassified → mission_critical/supporting/deferred` all permitted.
  - `mission_critical → supporting/deferred` permitted; `supporting → mission_critical/deferred` permitted; `deferred → mission_critical/supporting` permitted.
  - `mission_critical → unclassified` rejected with `invalid_classification_transition`. Same for `supporting → unclassified` and `deferred → unclassified`.
- **Criterion 5 (domain-FK validation):**
  - POST with non-existent `process_domain_identifier` returns `invalid_domain_reference`.
  - POST with a soft-deleted domain reference returns `invalid_domain_reference`.
  - PATCH with the same conditions returns the same error.
  - POST with a live domain reference succeeds.
- **Criterion 7 (soft-delete on process does not cascade handoff references):** Create two processes with a handoff between them; soft-delete one; verify the handoff persists in the `refs` table and appears under `?include_deleted=true` on either side.

### 6.2 `tests/crmbuilder_v2/api/test_processes_api.py`

Cover REST endpoints (criterion 6) and identifier auto-assignment (criterion 8). Standard pattern with process-specific adjustments.

### 6.3 `tests/crmbuilder_v2/ui/test_processes_panel.py`

Cover criteria 9–15. Critical slice-specific tests:

**Criterion 14: `process_hands_off_to_process` registered + bidirectional round-trip.**

- POST `/references` with `{source_type: "process", source_id: "PROC-001", target_type: "process", target_id: "PROC-002", relationship_kind: "process_hands_off_to_process"}` succeeds.
- POST with `(process, process)` and an unsupported kind returns HTTP 422.
- Open the source process's detail pane: confirm the reference appears under "Hands off to".
- Open the target process's detail pane: confirm the reference appears under "Receives from".
- Verify the cascading `ReferenceCreateDialog` opened from a Processes-panel "Add reference" affordance correctly enumerates `process_hands_off_to_process` when source=`process` and target=`process` are selected.

**Criterion 15: sample CBM-redo Phase 1 Prioritized Backbone with handoffs.**

- Programmatically author ~8 process records across the 4 domain records from slice B (e.g., 2 processes per domain).
- Set classifications: mix of mission_critical, supporting, deferred. Leave 1–2 as unclassified to verify the transition gate is enforced in tests.
- Create ~5 `process_hands_off_to_process` references modeling real handoff patterns.
- Re-affiliate one process to a different domain via PATCH — verify the record updates without losing its handoff references.
- Simulate app restart by reloading from REST.
- Confirm records, classifications, and handoffs persist correctly.

## Acceptance verification

1. **Slice D tests pass.** `uv run pytest tests/crmbuilder_v2/access/test_process.py tests/crmbuilder_v2/api/test_processes_api.py tests/crmbuilder_v2/ui/test_processes_panel.py -v` — all 15 acceptance criteria green.
2. **Slices A, B, C tests still pass.** `uv run pytest tests/crmbuilder_v2/ -v` returns no failures.
3. **Migration applies forward and backward.**
4. **Manual smoke.** Open the desktop app; click Processes in the Methodology sidebar group; create a process through the New dialog selecting a live domain; open detail pane; classify it; add a handoff reference to another process; verify rendering in both "Hands off to" and the target's "Receives from".

If any step fails, stop and report.

## Commit

```bash
git add crmbuilder-v2/migrations/0NNN_v0_4_create_processes_table.py \
        crmbuilder-v2/src/crmbuilder_v2/access/process.py \
        crmbuilder-v2/src/crmbuilder_v2/api/routers/processes.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/panels/processes.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/process_crud.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/app.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/client.py \
        tests/crmbuilder_v2/access/test_process.py \
        tests/crmbuilder_v2/api/test_processes_api.py \
        tests/crmbuilder_v2/ui/test_processes_panel.py
git commit -m "v2: v0.4 slice D — Processes panel end-to-end + classification + process_hands_off_to_process bidirectional"
```

Include `references_section.py` in the commit only if the widget was extended for the two-sub-section split; omit if the split is implemented at the panel layer.

Doug pushes. Do NOT push.

## What NOT to do

- Do NOT add a `process_status` field or any field semantically equivalent to status. Classification carries the lifecycle per DEC-056.
- Do NOT use `PRO-NNN` for the identifier prefix. The prefix is `PROC-NNN` (four letters) per DEC-055.
- Do NOT model `process_domain_identifier` as a reference instead of a scalar FK column. Affiliation is required and exactly-one per spec 3.4.5; the FK is a scalar.
- Do NOT include a multi-select for handoffs in the New Process dialog. Handoffs attach from the detail pane after creation per DEC-067.
- Do NOT cascade-delete handoff references when a process is soft-deleted. References persist per spec 3.4.7.
- Do NOT allow transitions from any classified value back to `unclassified`. One-way out per spec 3.4.2.
- Do NOT add a master-pane Domain column. Deferred per PI-007 / PI-009.
- Do NOT add fields beyond the section-3.2 column inventory (no steps, actors, fields-touched, triggers, outcomes, cycle time, frequency, volume, sub-process hierarchy). Deferred to v0.5+ per PI-005.
- Do NOT introduce a separate scalar implementation-priority field alongside classification. Deferred per PI-011.
- Do NOT write SES-016 or any DEC-NNN records.
- Do NOT bump `__version__` or update the README.

---

*End of prompt.*
