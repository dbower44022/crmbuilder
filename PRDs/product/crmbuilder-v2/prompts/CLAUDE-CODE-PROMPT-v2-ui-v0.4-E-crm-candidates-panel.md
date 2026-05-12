# CLAUDE-CODE-PROMPT-v2-ui-v0.4-E-crm-candidates-panel

**Last Updated:** 05-12-26 10:30
**Series:** v2-ui-v0.4
**Slice:** E (5 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md`
**Companion schema spec:** `PRDs/product/crmbuilder-v2/methodology-schema-specs/crm_candidate.md`
**Predecessor slice:** v2-ui-v0.4-D (Processes panel — three methodology panels in place; the Methodology sidebar group is three-quarters populated)

## Purpose

This is the fifth of six slices in v0.4. This prompt builds slice **E — CRM Candidates panel end-to-end**.

Slice E implements the `crm_candidate` entity type fully per `crm_candidate.md` — schema migration, access-layer methods, REST endpoints, desktop panel with master and detail views, CRUD dialogs, and tests covering all 12 acceptance criteria from `crm_candidate.md` section 3.7.

Three slice-specific aspects worth highlighting:

1. **Four-status terminal-state lifecycle.** Status enum has four values: `active`, `selected`, `declined`, `removed`. Three of those (`selected`, `declined`, `removed`) are terminal — no successors permitted. `active → {selected, declined, removed}` are the only valid transitions per spec 3.4.1. The status combo on the detail pane restricts available choices to valid successors of the current status; for terminal-state records, the combo effectively shows only the current value (read-only).

2. **Singleton-`selected` constraint.** At most one record in the engagement may carry `crm_candidate_status = 'selected'` at any time per spec 3.4.2. The constraint is enforced at the access layer on three write paths: POST `/crm_candidates`, PATCH `/crm_candidates/{id}` (including PUT), and POST `/crm_candidates/{id}/restore`. Violations return HTTP 422 with `{"error": "selected_candidate_already_exists", "existing": "<CRM-NNN>"}`. The dialog surfaces the error inline.

3. **Delete dialog clarifying note.** The delete path soft-deletes (authoring-error correction); the `removed` status transition pulls a CRM legitimately from further iterations. The two paths are different and easy to confuse. The delete dialog includes a note distinguishing them per PRD section 4.6.

After slice E, all four methodology entity types are live in the desktop app. The Methodology sidebar group is fully populated. Slice F is mechanical closeout.

## Project context

Slices B, C, D each shipped one methodology entity type and progressed the Methodology sidebar group. Slice E completes the four-entity scope. `crm_candidate` differs structurally from the other three — it is engagement-scoped methodology output (the Phase 5 Initial CRM Candidate Set), not a domain or entity in the methodology graph sense. It does not affiliate to domains, it is not the source of any v0.4 vocab kind, and its only references are inbound citations from governance entities (decisions, sessions, etc.) recording the deliberation history.

The spec is authoritative.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity:
   - `git config user.name` → `Doug Bower`
   - `git config user.email` → `dbower44022@users.noreply.github.com`
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice D is at HEAD or recently committed.
6. API health: `curl -sf http://127.0.0.1:8765/health` returns 200; start via `uv run crmbuilder-v2-api &` if not.
7. Confirm slices A, B, C, D tests pass: `uv run pytest tests/crmbuilder_v2/ -v`.

## Reading order

Before producing any code, read:

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` section 4.6 (CRM Candidates panel) — note the proposed wording for the delete-dialog clarifying note.
3. `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md` section 4 Step E.
4. `PRDs/product/crmbuilder-v2/methodology-schema-specs/crm_candidate.md` — authoritative for this slice. All 12 acceptance criteria in section 3.7 are the gate. Pay particular attention to section 3.4.1 (status enum with three terminal states), section 3.4.2 (singleton-selected constraint), and section 3.5.4 (enforcement on three operations).
5. Slice B's domain panel implementation — the most direct template for slice E's panel structure since `crm_candidate` has no required FK and no outgoing references.

## Step 1 — Alembic migration: create the `crm_candidates` table

Create a revision named like `0NNN_v0_4_create_crm_candidates_table.py`. The migration creates the `crm_candidates` table per `crm_candidate.md` section 3.2:

| Column | Type | Constraints |
|--------|------|-------------|
| `crm_candidate_identifier` | TEXT | PRIMARY KEY, format `^CRM-\d{3}$` (CHECK), unique |
| `crm_candidate_name` | TEXT | NOT NULL; case-insensitive uniqueness enforced at access layer |
| `crm_candidate_status` | TEXT | NOT NULL, default `'active'`, CHECK in `('active', 'selected', 'declined', 'removed')` |
| `crm_candidate_fit_reason` | TEXT | NOT NULL |
| `crm_candidate_notes` | TEXT | NULL allowed |
| `crm_candidate_created_at` | DATETIME | NOT NULL, default current_timestamp |
| `crm_candidate_updated_at` | DATETIME | NOT NULL, default current_timestamp |
| `crm_candidate_deleted_at` | DATETIME | NULL allowed |

Mirror prior slices' table-migration patterns. Forward and backward reversible.

## Step 2 — Access-layer repository: `access/crm_candidate.py`

Eight standard methods. Mirror slice B's domain repository with crm_candidate-specific adjustments:

- **Identifier format:** `^CRM-\d{3}$`
- **Name uniqueness:** case-insensitive, engagement-global
- **Status enum:** `{active, selected, declined, removed}`
- **Status-transition validation per spec 3.4.1:**
  - From `active` → any of `selected`, `declined`, `removed` permitted.
  - From `selected`, `declined`, `removed` → no successors permitted (terminal states).
  - Invalid transitions raise `{"error": "invalid_status_transition", "from": ..., "to": ...}`.
- **Singleton-`selected` constraint per spec 3.4.2 and 3.5.4:**
  - On POST `create_crm_candidate` with `status='selected'`: query for any existing record with `crm_candidate_status='selected'` AND `crm_candidate_deleted_at IS NULL`; if one exists, raise `{"error": "selected_candidate_already_exists", "existing": "<CRM-NNN>"}`.
  - On PATCH/PUT updating status to `selected`: same check, excluding the record being updated (i.e., transitioning a record to selected is fine as long as the same record being updated isn't already counted; but no other live record may be selected).
  - On POST `/restore` of a soft-deleted record whose `crm_candidate_status='selected'`: same check; if another live record is already selected, the restore fails and the dialog surfaces the error inline.
- **Soft-delete semantics:** standard pattern. Soft-deleting a record removes it from the singleton-selected pool, so soft-deleting a `selected` record permits another record to take `selected` status.

JSON-export hook regenerates `db-export/crm_candidates.json` after any DB-changing operation.

## Step 3 — REST API router: `api/routers/crm_candidates.py`

Eight standard endpoints per `crm_candidate.md` section 3.5.1. Mirror prior slices' router patterns. Error responses:

- `invalid_status_transition` → HTTP 422
- `selected_candidate_already_exists` → HTTP 422 with `existing` field naming the already-selected record

## Step 4 — Desktop UI panel: `ui/panels/crm_candidates.py`

### 4.1 Sidebar registration

Methodology sidebar group, position #4 (last entry).

### 4.2 Master pane

Columns: Identifier / Name / Status / Updated.

**Default sort: Identifier ascending per DEC-069.** Terminal-state records (`selected`, `declined`, `removed`) interleave with `active` by identifier. Status-then-identifier ordering (Option B in the planning conversation) is reserved as a v0.5+ candidate gated on CBM-redo signal.

Context menu: New / Edit / Delete / Restore.

### 4.3 Detail pane

Vertical layout per spec section 3.6.3:

1. `crm_candidate_identifier` — read-only label
2. `crm_candidate_name` — single-line text editor
3. `crm_candidate_fit_reason` — multi-line text editor, placeholder "What about this CRM made it worth considering for the engagement"
4. `crm_candidate_notes` — multi-line text editor under collapsible "Internal notes" section header, collapsed by default
5. `crm_candidate_status` — combo box with the four enum values. **Restricted to valid successors of the current status:** for an `active` record, all four values appear (including `active` itself as the current). For a `selected`/`declined`/`removed` record, the combo shows only the current value (effectively read-only post-transition).
6. `ReferencesSection` widget — renders inbound governance-entity citations only (e.g., `(decision, crm_candidate, is_about)` references recording "DEC-NNN cited CRM-NNN as part of the deliberation"). No outgoing references in v0.4.

### 4.4 CRUD dialogs

Create `ui/dialogs/crm_candidate_crud.py`.

**Create dialog:** required fields are `crm_candidate_name`, `crm_candidate_fit_reason`. Optional: `crm_candidate_notes`. Status combo shows all four values; defaults to `active`. If user selects `selected` at create time, the singleton check fires on submit — if violated, the dialog renders an inline error: `"CRM-NNN is already selected — change its status first."`

**Edit dialog:** same shape; identifier read-only; status combo restricted to valid successors of the current value. Singleton check on submit if transitioning to `selected`.

**Delete dialog:** standard edge-text confirmation (user types `CRM-NNN`) plus the **clarifying note** distinguishing the two paths per PRD section 4.6. Proposed wording (revise during slice execution if it reads awkwardly in the actual dialog layout):

```
Delete soft-deletes this record as an authoring-error correction.

If this CRM was legitimately in the candidate set and you want to
pull it from further iterations, change its Status to Removed instead.
```

Place the note above the edge-text input or in a callout box; the slice picks the cleanest layout.

### 4.5 File-watch wiring

Connect to the `crm_candidates_changed` signal slice A wired in `ui/refresh.py`.

## Step 5 — Storage client extensions

Add eight methods for crm_candidates in `ui/client.py`.

## Step 6 — Tests

Three test modules covering all 12 acceptance criteria from `crm_candidate.md` section 3.7.

### 6.1 `tests/crmbuilder_v2/access/test_crm_candidate.py`

Cover criteria 1–8 with crm_candidate-specific adjustments.

Critical slice-specific assertions:

- **Criterion 4 (status enum + terminal-state transitions):**
  - `active → selected/declined/removed` all permitted.
  - `selected → active/declined/removed` all rejected with `invalid_status_transition`. Same for `declined → ...` and `removed → ...`.
- **Criterion 5 (singleton-`selected` constraint on three operations):**
  - POST with `status='selected'` when another live record is `selected`: rejected with `selected_candidate_already_exists`.
  - PATCH transitioning a record to `selected` when another live record is `selected`: rejected.
  - POST `/restore` on a soft-deleted record with `status='selected'` when another live record is `selected`: rejected.
  - Soft-deleting a `selected` record then creating a new record with `status='selected'`: permitted (soft-deleted records don't count against the singleton).
  - Restoring a soft-deleted `selected` record when no other live record is `selected`: permitted.
- **Criterion 8 (soft-delete + restore round-trip):** standard plus the singleton-blocked-restore case above.

### 6.2 `tests/crmbuilder_v2/api/test_crm_candidates_api.py`

Cover criterion 6 (REST endpoints) and criterion 7 (identifier auto-assignment). Standard patterns.

### 6.3 `tests/crmbuilder_v2/ui/test_crm_candidates_panel.py`

Cover criteria 9–12 with critical slice-specific tests:

**Criterion 9 (vocab and cascading dialog correctness):**

- `crm_candidate` appears in `ENTITY_TYPES` (verifies slice A's foundation).
- The cascading `ReferenceCreateDialog` opened from a governance-entity panel (e.g., Decisions) admits universal kinds for `(decision, crm_candidate)` source-target combination: `is_about`, `references` (and `supersedes` is NOT present because the types don't match). 
- Same check for `(session, crm_candidate)`: universal kinds plus `decided_in` (universal target=session rule applies).
- POST `/references` with `{source_type: "decision", source_id: "DEC-NNN", target_type: "crm_candidate", target_id: "CRM-NNN", relationship_kind: "is_about"}` succeeds and creates a reference row.
- The reference appears on the crm_candidate detail pane under inbound references.

**Criterion 12 (sample CBM-redo Phase 5 selection round-trip):**

- Author 3 `active` CRM candidates (e.g., "CRM A", "CRM B", "CRM C") via the New dialog.
- Transition CRM A to `removed` (e.g., scope drifted away from CRM A during deliberation).
- Transition CRM B to `selected`.
- Attempt to transition CRM C to `selected` — verify the singleton-blocked error appears inline in the dialog.
- Transition CRM C to `declined` instead.
- Simulate app restart by reloading from REST.
- Confirm records and statuses persist correctly.
- Soft-delete CRM B (authoring-error correction simulation); confirm the singleton pool is now empty.
- Restore CRM B; confirm `selected` returns; verify dialog confirmation.

## Acceptance verification

1. **Slice E tests pass.** `uv run pytest tests/crmbuilder_v2/access/test_crm_candidate.py tests/crmbuilder_v2/api/test_crm_candidates_api.py tests/crmbuilder_v2/ui/test_crm_candidates_panel.py -v` — all 12 acceptance criteria green.
2. **Slices A–D tests still pass.** `uv run pytest tests/crmbuilder_v2/ -v`.
3. **Migration applies forward and backward.**
4. **Manual smoke.** Open the desktop app; navigate to CRM Candidates; create three records; transition one to `selected`; attempt to transition a second — confirm the inline error; confirm the delete dialog renders the clarifying note clearly.

If any step fails, stop and report.

## Commit

```bash
git add crmbuilder-v2/migrations/0NNN_v0_4_create_crm_candidates_table.py \
        crmbuilder-v2/src/crmbuilder_v2/access/crm_candidate.py \
        crmbuilder-v2/src/crmbuilder_v2/api/routers/crm_candidates.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/panels/crm_candidates.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/crm_candidate_crud.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/app.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/client.py \
        tests/crmbuilder_v2/access/test_crm_candidate.py \
        tests/crmbuilder_v2/api/test_crm_candidates_api.py \
        tests/crmbuilder_v2/ui/test_crm_candidates_panel.py
git commit -m "v2: v0.4 slice E — CRM Candidates panel end-to-end + singleton-selected enforcement"
```

Doug pushes. Do NOT push.

## What NOT to do

- Do NOT add an `entity_scopes_to_domain`-like vocab kind sourcing from `crm_candidate`. The entity type has no outgoing references in v0.4 per DEC-064.
- Do NOT add structured-metadata enum fields (vendor URL, hosting type, license type, price tier). Deferred to v0.5+ per PI-012.
- Do NOT implement Option B (status-then-identifier sort) on the master pane. v0.4 ships Option A (simple identifier-ascending) per DEC-069; Option B is reserved for v0.5+ gated on CBM-redo signal.
- Do NOT allow transitions from `selected`/`declined`/`removed` to any other status. Terminal states have no successors.
- Do NOT permit two live records to both carry `crm_candidate_status='selected'`. The singleton check fires on all three write operations.
- Do NOT remove the singleton check from POST `/restore`. A soft-deleted `selected` record cannot be restored if another `selected` record is now live.
- Do NOT omit the clarifying note on the delete dialog. The note is required per PRD section 4.6; revise the wording if it reads awkwardly but don't drop it.
- Do NOT write SES-016 or any DEC-NNN records.
- Do NOT bump `__version__` or update the README — those land in slice F.

---

*End of prompt.*
