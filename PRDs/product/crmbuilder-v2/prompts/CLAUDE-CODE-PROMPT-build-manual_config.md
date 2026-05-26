# CLAUDE-CODE-PROMPT-build-manual_config

**Last Updated:** 05-25-26
**Operating mode:** DETAIL
**Series:** PI-004 (additional methodology entity types for v0.5+)
**Slice:** manual_config — third PI-004 sibling alongside `field`, `requirement`, `test_spec`
**Status:** Ready to execute. Blocked by: nothing — `manual_config.md` spec is canonical.
**Companions:**
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/manual_config.md` v1.0 — authoritative spec.
- `crmbuilder-v2/migrations/versions/0008_v0_4_create_entities_table.py` — table-creation migration pattern.
- `crmbuilder-v2/migrations/versions/0011_v0_7_governance_entities.py` — `batch_alter_table` CHECK-extension pattern for refs/change_log.
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/entity.py` — standard transition-validated repository to mirror.
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/crm_candidate.py` — non-standard-lifecycle analogue (terminal states + cross-field invariant pattern via `_reject_second_selected`).

---

## Purpose

Land the `manual_config` methodology entity end-to-end per `manual_config.md` v1.0 — migration, ORM model, vocab, repository, FastAPI router + schemas, app wiring, UI client methods, sidebar entry, main-window dispatch, panel, CRUD dialogs, tests — and close the session per CLAUDE.md conventions applying the PI-004 build-closure rule below.

`manual_config` captures discrete CRM configuration items the deploy pipeline cannot apply automatically — saved views, duplicate checks, workflows, deferred-options enums, role/field permissions, role-conditioned dynamic logic — that a human operator performs in the live CRM after deploy. The methodology layer needs these as queryable records so verification specs target them, requirements are realized by them, and consultants produce stakeholder-facing manual-action lists.

Two posture points that shape the build:

- **Four-status lifecycle, not three** (`manual_config.md` §3.4). Cross-spec default (`domain.md`, `entity.md`) is `candidate` / `confirmed` / `deferred`. This spec adds terminal `completed` reachable only from `confirmed`. Treat the deviation as load-bearing — every place the pattern says "three statuses" or "no terminal", substitute the four-status shape.
- **Cross-field invariant on `completed`** (§3.5.3). Transition into `completed` requires both `manual_config_completed_at` and `manual_config_completed_by`. Access layer enforces with a dedicated error body shape `{"error": "completed_status_requires_completion_fields", "missing": [...]}`. The repository may server-default `manual_config_completed_at` to `now()` if omitted; it must reject if `manual_config_completed_by` is omitted. No analogue in the four prior methodology entities.

---

## PI-004 build-closure rule (READ FIRST)

PI-004 covers `field`, `requirement`, `manual_config`, `test_spec`. PI-004 is **resolved** when the **last sibling lands**, not the first or middle ones.

The session performs the closure check **at close-out drafting time, not at build start** — sibling sessions may land in parallel sandboxes between session-open and session-close, and the close-out posture must reflect the state at close-out.

The check (run at step 16, not pre-flight):

1. Enumerate `addresses` edges on PI-004:
   ```bash
   curl -s 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=addresses' \
     | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(f'addresses edges: {len(d)}'); [print(f\"  {r['reference_identifier']}: {r['source_type']} {r['source_id']}\") for r in d]"
   ```
2. Check which sibling entity types are present in `ENTITY_TYPES` (i.e. which sibling builds have landed):
   ```bash
   for et in fields requirements test-specs; do
     curl -sw "\n%{http_code}\n" "http://127.0.0.1:8765/${et}" 2>/dev/null | tail -1
   done
   ```

Decision:

- If **all three other siblings (`field`, `requirement`, `test_spec`) are delivered** — each with its own completed session carrying an `addresses` edge to PI-004 — this session is the **closer**. Set `resolves_planning_items: [{"planning_item_identifier": "PI-004"}]`. Slice A of PI-030 will atomically flip PI-004 Open → Resolved.
- Otherwise this session **advances** PI-004. Set `resolves_planning_items: []` with `addresses_planning_items: [{"planning_item_identifier": "PI-004"}]`.

When in doubt, prefer non-resolving — underclaiming is safe; overclaiming would prematurely Resolve PI-004 with siblings outstanding. A later wrap-up session can resolve once the genuine last sibling lands.

---

## Pre-flight

1. **Confirm working directory:** `pwd` resolves to the crmbuilder repo root. Stop if unexpected.
2. **Confirm `git status` is clean.** Stop and report if uncommitted changes.
3. **Confirm git identity:** `git config user.name "Doug Bower" && git config user.email "doug@dougbower.com"`.
4. **Pull latest:** `git pull --rebase origin main`. Stop on conflicts.
5. **Tier 1 read:** re-read `CLAUDE.md` end-to-end. Note the "v2 session lifecycle — opening / closing a session", "planning item resolution", the "Reference relationship vocabulary lives in vocab.py" rule, and the `{data, meta, errors}` envelope rule (every inlined `python3` snippet here unwraps `.data`).
6. **Tier 2 file-fallback read:** `PRDs/product/crmbuilder-v2/db-export/{status,charter,sessions,decisions,planning_items}.json`. Identify next free `SES-NNN` / `DEC-NNN` and locate PI-004 with its existing `addresses` neighbours.
7. **Read the spec end-to-end:** `manual_config.md` v1.0. Sections that shape the build:
   - §3.1 Identity — prefix `MCF`, justification.
   - §3.2 Fields — twelve columns (identifier + name + description + category + instructions + notes + status + two completion + three timestamps).
   - §3.3 Relationships — four outbound kinds; vocab + `_kinds_for_pair` + Alembic CHECK contributions.
   - §3.4 Lifecycle — four-status set, transition map, terminal `completed`.
   - §3.5.3 — the cross-field invariant unique to this spec.
   - §3.6 UI — 5-column master pane; detail-pane completion-field reveal rule.
   - §3.7 — 16 testable acceptance criteria.
8. **Read pattern references** in parallel: `0008` and `0011` migrations; `entity.py` and `crm_candidate.py` repositories; `vocab.py` end-to-end (the v0.8 Code Change Lifecycle additions at the tail are freshest precedent for bulk vocab additions).
9. **Read UI + API patterns:** `api/routers/entities.py`, `api/schemas.py` lines 189–227 (EntityCreateIn/ReplaceIn/PatchIn), `api/main.py` (router list + error-handler registration order), `ui/panels/entities.py`, `ui/dialogs/entity_crud.py` + `_entity_schema.py`, `ui/dialogs/crm_candidate_crud.py` + `_crm_candidate_schema.py` (non-standard lifecycle dialog precedent), `ui/sidebar.py`, `ui/main_window.py` (`_entry_to_entity_type` map + panel-construction chain), `ui/client.py` lines ~660–795 (entity client-method block to mirror).
10. **Verify the v2 codebase:** `ls crmbuilder-v2/migrations/versions/ | tail` — most recent head should be `0012_v0_8_commits_and_blocked_by_rename` (or higher). Next migration number is one more.
11. **API health:** `curl -s http://127.0.0.1:8765/health` returns healthy shape. If not, start with `uv run crmbuilder-v2-api &` from `crmbuilder-v2/`.
12. **Baseline tests:** `cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -30 && cd ..`. Note pass count.
13. **Pre-migration Alembic head:** `cd crmbuilder-v2 && uv run alembic current 2>&1 && cd ..`.
14. **Pre-build identifier head capture** (SES-077 re-keying contingency):
    ```bash
    for endpoint in sessions decisions; do
      curl -s "http://127.0.0.1:8765/$endpoint" \
        | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; ids = sorted(r['identifier'] for r in d if r.get('identifier')); print(f'$endpoint tail: {ids[-3:] if ids else []}')"
    done
    ```
    Note next free identifiers; verify nothing claimed by parallel sandbox work.

---

## Implementation

Sequenced so each step's artifacts feed the next — model imports migration columns; repository imports model; router imports repository; schemas feed router; UI client calls router; panel calls client; dialogs feed panel; tests run against the whole stack.

### Step 1 — Schema migration

Create `crmbuilder-v2/migrations/versions/NNNN_v0_5_create_manual_configs_table.py` (NNNN = next free four-digit number after current head; `0013` if head is `0012`). Combine `0008`'s `create_table` shape with `0011`'s `batch_alter_table` CHECK-extension shape.

Revision header `revision: str = "NNNN_v0_5_create_manual_configs_table"`, `down_revision = "<current head>"`.

`upgrade()` performs four operations in order:

**1a.** Extend `refs.source_type` and `refs.target_type` CHECK constraints to admit `'manual_config'`. `batch_alter_table("refs", recreate="always")`; drop existing CHECKs by name (verify names by inspecting `0011`); create new CHECKs with extended sorted-alphabetical sets.

**1b.** Extend `refs.relationship_kind` CHECK in the same `batch_alter_table` block to admit four new kinds: `'manual_config_scopes_to_domain'`, `'manual_config_touches_entity'`, `'manual_config_touches_field'`, `'manual_config_realizes_requirement'`. All four register up-front per §3.3.1 regardless of whether `field` / `requirement` entity types exist yet — only the `_kinds_for_pair` clauses are conditional. Keep existing kinds plus v0.7/v0.8 additions; sorted-alphabetical.

**1c.** Extend `change_log.entity_type` CHECK to admit `'manual_config'`. Same `batch_alter_table` pattern as `0011`.

**1d.** Create the `manual_configs` table per §3.2 — twelve columns:

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `manual_config_identifier` | `String(32)` PK | NO | CHECK `GLOB 'MCF-[0-9][0-9][0-9]'` |
| `manual_config_name` | `String(255)` | NO | |
| `manual_config_category` | `String(32)` | NO | CHECK in 7 values |
| `manual_config_description` | `Text` | NO | |
| `manual_config_instructions` | `Text` | NO | |
| `manual_config_notes` | `Text` | YES | |
| `manual_config_status` | `String(16)` | NO | CHECK in 4 values |
| `manual_config_completed_at` | `DateTime(tz=True)` | YES | Cross-field invariant at access layer |
| `manual_config_completed_by` | `Text` | YES | Cross-field invariant at access layer |
| `manual_config_created_at` | `DateTime(tz=True)` | NO | |
| `manual_config_updated_at` | `DateTime(tz=True)` | NO | |
| `manual_config_deleted_at` | `DateTime(tz=True)` | YES | |

Three indexes: `(manual_config_status)`, `(manual_config_category)`, `(manual_config_deleted_at)`.

Completion-field nullability at storage is deliberate; the conditional ("required when status = completed") is enforced at the access layer per §3.5.3, not by SQL — expressing the conditional in SQLite is brittle and the access-layer error body is richer. No SQL FOREIGN KEYs.

`downgrade()` reverses in opposite order: drop table → restore original change_log CHECK → restore original refs.relationship_kind CHECK → restore original refs.source_type / target_type CHECKs.

### Step 2 — ORM model

Edit `crmbuilder-v2/src/crmbuilder_v2/access/models.py`. Add `class ManualConfig(Base)` after the `Process` class, modeled on `Entity` with the wider field set. `__tablename__ = "manual_configs"`; primary key `manual_config_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)`. The two `completion_*` columns are `Mapped[datetime | None]` / `Mapped[str | None]` with `nullable=True`. `__table_args__` carries the three CheckConstraints (identifier format, status, category — the two enum CHECKs use `_check_in(...)` against the new vocab constants) and the three Indexes. Import `MANUAL_CONFIG_STATUSES` and `MANUAL_CONFIG_CATEGORIES` from `vocab` at module top.

### Step 3 — Vocab updates

Edit `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`. Six additions:

**3a.** After the `CRM_CANDIDATE_STATUS_TRANSITIONS` block, add the four-status vocab and transition map. Citation: `manual_config.md` §3.4.1.

```python
MANUAL_CONFIG_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred", "completed"}
)
MANUAL_CONFIG_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred", "completed"}),
    "deferred": frozenset({"confirmed"}),
    "completed": frozenset(),
}
```

**3b.** Add `MANUAL_CONFIG_CATEGORIES` — frozenset of seven values per §3.2.3 — directly after the lifecycle block.

**3c.** Add `"manual_config"` to `ENTITY_TYPES` in the methodology-entities section; update the section comment naming the PI-004 addition.

**3d.** Add the four outbound kinds to `REFERENCE_RELATIONSHIPS` under a PI-004 section comment. All four register unconditionally so the vocabulary surface is stable.

**3e.** Extend `_kinds_for_pair` with four new clauses. The first two emit unconditionally; the latter two are guarded on target-type presence in `ENTITY_TYPES` so they no-op until sibling builds register `'field'` / `'requirement'`:

```python
if source_type == "manual_config" and target_type == "domain":
    kinds.add("manual_config_scopes_to_domain")
if source_type == "manual_config" and target_type == "entity":
    kinds.add("manual_config_touches_entity")
if source_type == "manual_config" and target_type == "field" and "field" in ENTITY_TYPES:
    kinds.add("manual_config_touches_field")
if source_type == "manual_config" and target_type == "requirement" and "requirement" in ENTITY_TYPES:
    kinds.add("manual_config_realizes_requirement")
```

If sibling builds have already shipped at the time this build runs, the conditionals fire on their own. Forward-compatible without follow-up vocab edits.

**3f.** Update the `_kinds_for_pair` docstring with four bullets for the new kinds, matching the v0.4 / v0.8 bullet style.

### Step 4 — Repository

Create `crmbuilder-v2/src/crmbuilder_v2/access/repositories/manual_config.py`. Mirror `entity.py`'s shape; layer in `crm_candidate.py`-style additions for category validation and the completion-fields invariant.

Module constants:
- `_ENTITY_TYPE = "manual_config"`
- `_IDENTIFIER_PREFIX = "MCF"`
- `_IDENTIFIER_RE = re.compile(r"^MCF-\d{3}$")`
- `_MAX_AUTOASSIGN_ATTEMPTS = 50`
- `_PATCHABLE_FIELDS = frozenset({"name", "category", "description", "instructions", "notes", "status", "completed_at", "completed_by"})`

Helpers mirrored verbatim from `entity.py` with substitutions: `_require_identifier_format` (MCF), `_require_nonempty`, `_require_status` (against `MANUAL_CONFIG_STATUSES`), `_check_transition` (against `MANUAL_CONFIG_STATUS_TRANSITIONS`), `_reject_duplicate_name` (against `manual_config_name`), `_get_row`, `_increment_identifier`, `_new_manual_config_row`, `_insert_with_autoassign`.

New helpers unique to this entity:

- `_require_category(category) -> str` — same shape as `_require_status`; rejects values outside `MANUAL_CONFIG_CATEGORIES`.
- `_require_completion_fields_for_completed(*, status_after, completed_at, completed_by) -> tuple[datetime | None, str | None]` — the §3.5.3 cross-field invariant. When `status_after == "completed"`: server-defaults `completed_at` to `datetime.now(UTC)` if omitted; rejects if `completed_by` is omitted/empty with `CompletedStatusRequiresCompletionFieldsError([...])`. When `status_after != "completed"`: passes inputs through unchanged (setting completion fields on a non-completed record is permitted but discouraged per §3.5.3).

Add `CompletedStatusRequiresCompletionFieldsError` to `crmbuilder-v2/src/crmbuilder_v2/access/exceptions.py` following `SelectedCandidateConflictError`'s shape — carries `self.missing: list[str]`.

Add `completed_status_requires_completion_fields_handler` to `crmbuilder-v2/src/crmbuilder_v2/api/errors.py` following `selected_candidate_conflict_handler`'s shape, returning HTTP 422 with the v2 envelope body `{"data": null, "meta": {}, "errors": [{"error": "completed_status_requires_completion_fields", "missing": exc.missing}]}`.

Public functions (eight, standard set):

- `list_manual_configs(session, *, include_deleted=False)` — verbatim shape.
- `get_manual_config(session, identifier, *, include_deleted=False)` — verbatim shape.
- `next_manual_config_identifier(session)` — verbatim shape, MCF prefix.
- `create_manual_config(session, *, name, category, description, instructions, notes=None, status="candidate", completed_at=None, completed_by=None, identifier=None)` — validate; reject duplicate name; run `_require_completion_fields_for_completed` if `status == "completed"`; identifier auto-assign or explicit path; emit change_log "insert".
- `update_manual_config(session, identifier, *, manual_config_identifier=None, name, category, description, instructions, notes=None, status, completed_at=None, completed_by=None)` — full-replace PUT. Validate body/path identifier match; run `_check_transition` if status changes; run cross-field invariant against post-write status; emit change_log "update".
- `patch_manual_config(session, identifier, **fields)` — partial PATCH. Pre-filter against `_PATCHABLE_FIELDS`. Compute `status_after = fields.get("status", row.manual_config_status)`, `completed_at_after = fields.get("completed_at", row.manual_config_completed_at)`, `completed_by_after = fields.get("completed_by", row.manual_config_completed_by)`. Run cross-field invariant against the post-merge values — this handles "PATCH that only sets `status: completed` on a record whose completion fields are still null".
- `delete_manual_config(session, identifier)` — verbatim soft-delete.
- `restore_manual_config(session, identifier)` — verbatim restore. No cross-field invariant on restore (existing status and completion fields unchanged).

### Step 5 — FastAPI schemas

Edit `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py`. Insert after the `CrmCandidatePatchIn` block under a `# ---------- Manual Configs (methodology entity, PI-004) ----------` section header. Three classes mirroring the entity-schema shape:

- `ManualConfigCreateIn(_Base)` — `manual_config_name: str`, `manual_config_category: str`, `manual_config_description: str`, `manual_config_instructions: str`, `manual_config_notes: str | None = None`, `manual_config_status: str | None = None`, `manual_config_completed_at: datetime | None = None`, `manual_config_completed_by: str | None = None`, `manual_config_identifier: str | None = None`. Docstring cites §3.5.3 (server-side cross-field invariant) and §3.5.4 (references NOT inlined).
- `ManualConfigReplaceIn(_Base)` — same fields, with `manual_config_status: str` required and `manual_config_identifier: str | None = None`.
- `ManualConfigPatchIn(_Base)` — all fields `str | None = None` (and `datetime | None = None` for the timestamp). Router consumes with `model_dump(exclude_unset=True)` so explicit `null` vs omitted is distinguished.

Import `datetime` from `datetime` at module top if not already present.

### Step 6 — FastAPI router

Create `crmbuilder-v2/src/crmbuilder_v2/api/routers/manual_configs.py`. Mirror `entities.py` verbatim with `prefix="/manual-configs"`, `tags=["manual-configs"]`, `_FIELD_PREFIX = "manual_config_"`. Eight endpoints in order: GET `""`, GET `"/next-identifier"`, GET `"/{identifier}"`, POST `""` (status_code=201), PUT `"/{identifier}"`, PATCH `"/{identifier}"`, DELETE `"/{identifier}"`, POST `"/{identifier}/restore"`. URL plural is hyphenated per §3.5.1; storage entity-type name keeps the underscore.

The PATCH endpoint uses the standard `provided = body.model_dump(exclude_unset=True)` then `fields = {key[len(_FIELD_PREFIX):]: value for key, value in provided.items()}` pattern.

### Step 7 — Register router and error handler in `main.py`

Edit `crmbuilder-v2/src/crmbuilder_v2/api/main.py`:

- Add `manual_configs` to the routers-import tuple (alphabetical).
- Add `app.include_router(manual_configs.router)` in the methodology-entities cluster (after `crm_candidates.router`, before `references.router`).
- Import `CompletedStatusRequiresCompletionFieldsError` from `access.exceptions` and `completed_status_requires_completion_fields_handler` from `api.errors`.
- Register the handler **before** the `AccessLayerError` registration (same rule as `SelectedCandidateConflictError` per the comment at ~line 75).

### Step 8 — UI client methods

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/client.py`. Mirror the entity-method block (lines ~660–795) with seven `manual_config` methods: `list_manual_configs`, `get_manual_config`, `create_manual_config`, `update_manual_config`, `patch_manual_config`, `delete_manual_config`, `restore_manual_config`, `next_manual_config_identifier`. Match the existing error-handling and envelope-unwrapping idioms exactly (`response.get("data")`, `NotFoundError` on None from GET, etc.).

### Step 9 — Sidebar entry

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py`. In `SIDEBAR_GROUPS`, append `"Manual Configs"` to the Methodology group's entry tuple. Position is tail-most after the existing four methodology entries; if `field` / `requirement` / `test_spec` siblings have already shipped, position per §3.6.1 (between Fields and Test Specs if both exist).

### Step 10 — Main-window dispatch

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py`:

- `from crmbuilder_v2.ui.panels.manual_config import ManualConfigPanel` near other panel imports.
- Add `"manual_config": "Manual Configs"` to `_entry_to_entity_type`.
- Add an `elif entry == "Manual Configs": page = ManualConfigPanel(self._client)` branch alongside `EntitiesPanel` and `CrmCandidatesPanel`.

### Step 11 — Panel

Create `crmbuilder-v2/src/crmbuilder_v2/ui/panels/manual_config.py`. Mirror `entities.py`'s panel shape with §3.6.2 five-column master pane and §3.6.3 conditional completion-field reveal.

`ManualConfigPanel(ListDetailPanel)`:
- `entity_title()` → `"Manual Configs"`.
- `fetch_records()` → `self._client.list_manual_configs(include_deleted=self._include_deleted)`.
- `list_columns()` returns five `ColumnSpec` instances in order: Identifier (width 120) / Name / Category (width 160) / Status (width 110) / Updated (width 180). Category is the master-pane addition that distinguishes this panel from the entity panel — see §3.6.2 rationale (category is a single scalar field, no batched join required, and category-at-a-glance is high-value).

`render_detail(record, extras)` layout per §3.6.3:
1. Edit / Delete (or Restore / Edit) action strip.
2. Heading label — `manual_config_name`.
3. Form rows: Identifier (read-only label), Name, Category (read-only line), Description (read-only multi-line), Instructions (read-only multi-line, taller min-height than description).
4. `CollapsibleSection("Internal notes", notes_value, expanded=False)` — same posture as `entity_notes`.
5. Status row: read-only combo restricted to current status's valid successors; "Valid transitions" hint caption below.
6. **Conditional completion section.** If `record.get("manual_config_status") == "completed"`: render two read-only fields (Completed At, Completed By). If not completed: omit the section entirely (completion fields are null and not part of the active visual).
7. `ReferencesSection("manual_config", identifier, extras.get("references") or {}, client=self._client)` — surfaces the four outbound kinds plus inbound `test_spec_verifies_manual_config` once `test_spec` lands.

Click handlers (`_on_new_*`, `_on_edit_*`, `_on_delete_*`, `_on_restore_*`) follow `entity.py`'s pattern verbatim with the `ManualConfig` class names substituted. `_select_by_identifier` and `_currently_selected_identifier` key on `"manual_config_identifier"`.

### Step 12 — CRUD dialogs

Create two files:

**12a. `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_manual_config_schema.py`** — declarative `FieldSchema` list mirroring `_entity_schema.py` with the wider field set.

Two helpers:
- `status_choices(current)` — same shape as the entity helper. Returns current + valid successors per `MANUAL_CONFIG_STATUS_TRANSITIONS`. `candidate` → `[candidate, confirmed, deferred]` (NOT completed — that's invalid transition). `confirmed` → `[confirmed, deferred, completed]`. `deferred` → `[confirmed, deferred]`. `completed` → `[completed]` (terminal).
- `category_choices()` — sorted list of the seven `MANUAL_CONFIG_CATEGORIES` values.

`FieldSchema` list in §3.2 order: name (required line), category (required combo, `compute_options=lambda _state: category_choices()`), description (required text), instructions (required text), notes (text), status (required combo with `default="candidate"`, `compute_options=lambda state: status_choices(state.get("manual_config_status"))`), completed_at (datetime widget, visible/required only when status is `completed`), completed_by (line, visible/required only when status is `completed`).

If `FieldSchema` doesn't currently support `visible_when`/`required_when`/`widget="datetime"`, choose the lower-cost path: extend `ui/base/crud_dialog.py` minimally if cheap, otherwise fall back to always-show-but-conditionally-required (acceptance §3.7 item 14 says "inline" — both UX satisfy that). Ship the status-combo-driven Mark-Completed UX per §3.6.5 (the dedicated "Mark Completed" button alternative is open-question §3.8.1 deferred to v0.6+).

**12b. `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/manual_config_crud.py`** — three dialog classes: `ManualConfigCreateDialog`, `ManualConfigEditDialog`, `ManualConfigDeleteDialog`. Mirror `entity_crud.py`'s shapes. Delete uses edge-text confirmation (user types `MCF-NNN` to enable Delete).

### Step 13 — Per-panel stale-tracking

If `main_window.py` has per-panel sidebar-stale-flag plumbing keyed by entity type, extend it for `manual_config`. If no custom hookup exists, this step is a no-op.

### Step 14 — Tests (≥20)

Three test files. Pattern-match existing test scaffolding under `tests/crmbuilder_v2/access/` (e.g. `test_entity.py`) and `tests/crmbuilder_v2/api/`.

**14a. `tests/crmbuilder_v2/access/test_manual_config.py`** (≥12):
- `test_create_assigns_identifier_when_omitted` — POST no identifier; assigned next free MCF.
- `test_create_explicit_identifier_persists`.
- `test_create_explicit_identifier_format_validation` — `MC-001` → `UnprocessableError` with `invalid_format`.
- `test_create_explicit_identifier_collision` → `ConflictError`.
- `test_create_invalid_category` — `bogus` → `UnprocessableError` with `invalid_value`.
- `test_create_duplicate_name_case_insensitive` — second POST same name lowercased → `UnprocessableError` `duplicate`.
- `test_create_completed_without_completion_by` — POST `status="completed"` missing `completed_by` → `CompletedStatusRequiresCompletionFieldsError` with `missing=["manual_config_completed_by"]`.
- `test_create_completed_with_completion_fields_succeeds` — POST `status="completed"`, `completed_by="..."`, no `completed_at` → succeeds; `completed_at` server-set.
- `test_patch_candidate_to_completed_invalid_transition` → `StatusTransitionError` (candidate is not a valid predecessor of completed).
- `test_patch_confirmed_to_completed_succeeds_with_fields`.
- `test_patch_confirmed_to_completed_without_completion_by` → `CompletedStatusRequiresCompletionFieldsError`.
- `test_patch_completed_to_anything_terminal` → `StatusTransitionError` (no successors).
- `test_delete_and_restore_round_trip`.
- `test_concurrent_identifier_autoassign` — two concurrent POSTs assign distinct identifiers.

**14b. `tests/crmbuilder_v2/api/test_manual_configs_api.py`** (≥6):
- `test_get_list_default_excludes_deleted` and `?include_deleted=true` shows.
- `test_get_next_identifier_returns_envelope` — `{"data": {"next": "MCF-NNN"}}`.
- `test_post_create_returns_201_and_envelope`.
- `test_patch_to_completed_without_completion_by_returns_422` — body has `errors[0].error == "completed_status_requires_completion_fields"` and `errors[0].missing == ["manual_config_completed_by"]`.
- `test_invalid_status_transition_returns_422_with_dedicated_body` — `candidate → completed` direct → body has `errors[0].error == "invalid_status_transition"`.
- `test_put_path_identifier_mismatch_returns_422`.
- `test_reference_round_trip_for_each_outbound_kind` — POST a domain + entity + manual_config; POST `/references` for each of `manual_config_scopes_to_domain` and `manual_config_touches_entity` (the two unconditionally-active kinds at build time); GET `/references?source_id=MCF-NNN` round-trips both.

**14c. `tests/crmbuilder_v2/ui/test_manual_config_panel.py`** (≥2):
- `test_panel_master_pane_columns` — columns exactly `["Identifier", "Name", "Category", "Status", "Updated"]`.
- `test_detail_pane_reveals_completion_fields_when_status_completed` — completed record → completion widgets present; candidate record → completion widgets absent.

Total target: ≥20 tests.

### Step 15 — Migration + end-to-end smoke

```bash
cd crmbuilder-v2 && uv run alembic upgrade head 2>&1 && uv run alembic current 2>&1 && cd ..
# Expected head: NNNN_v0_5_create_manual_configs_table
```

Verify table presence:
```bash
uv run python -c "
from crmbuilder_v2.access.db import session_scope
from sqlalchemy import text
with session_scope() as s:
    rows = list(s.execute(text(\"SELECT name FROM sqlite_master WHERE type='table' AND name='manual_configs'\")))
    print(f'manual_configs table present: {len(rows) == 1}')
"
```

Restart the API process so the new router loads. Then smoke (every snippet unwraps `.data`):

```bash
# 1. POST candidate.
curl -sX POST http://127.0.0.1:8765/manual-configs \
  -H 'Content-Type: application/json' \
  -d '{
    "manual_config_name": "Saved view: Smoke test",
    "manual_config_category": "saved_view",
    "manual_config_description": "Smoke-test record.",
    "manual_config_instructions": "1. Open admin. 2. Add saved view."
  }' | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(d['manual_config_identifier'], d['manual_config_status'])"
# Expected: MCF-001 (or next free) candidate

# 2. PATCH candidate → confirmed → completed (with completion fields).
curl -sX PATCH http://127.0.0.1:8765/manual-configs/MCF-001 \
  -H 'Content-Type: application/json' \
  -d '{"manual_config_status": "confirmed"}' > /dev/null

curl -sX PATCH http://127.0.0.1:8765/manual-configs/MCF-001 \
  -H 'Content-Type: application/json' \
  -d '{"manual_config_status": "completed", "manual_config_completed_by": "doug@dougbower.com"}' \
  | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(d['manual_config_status'], d['manual_config_completed_at'], d['manual_config_completed_by'])"
# Expected: completed <iso-timestamp> doug@dougbower.com

# 3. Second record, PATCH to completed WITHOUT completion_by → 422.
curl -sX POST http://127.0.0.1:8765/manual-configs \
  -H 'Content-Type: application/json' \
  -d '{
    "manual_config_name": "Workflow: Smoke #2",
    "manual_config_category": "workflow",
    "manual_config_description": "Smoke #2.",
    "manual_config_instructions": "1. Open admin. 2. Add workflow."
  }' > /dev/null

curl -sX PATCH http://127.0.0.1:8765/manual-configs/MCF-002 \
  -H 'Content-Type: application/json' \
  -d '{"manual_config_status": "confirmed"}' > /dev/null

curl -sw "\n%{http_code}\n" -X PATCH http://127.0.0.1:8765/manual-configs/MCF-002 \
  -H 'Content-Type: application/json' \
  -d '{"manual_config_status": "completed"}'
# Expected: HTTP 422; body has "completed_status_requires_completion_fields" and missing=["manual_config_completed_by"]
```

Run full test suite: `cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -50 && cd ..`. Expected: baseline + ≥20 new tests; no regressions.

Soft-delete the smoke records to keep the engagement DB tidy (the records persist soft-deleted; that's fine for the close-out — they don't need to be physically gone).

### Step 16 — Close-out payload + apply prompt

**16a.** Re-run the pre-flight identifier head capture; verify SES-NNN / DEC-NNN are still free, re-key if not.

**16b.** Perform the PI-004 build-closure check per the rule at the top of this prompt. Two checks:

```bash
curl -s 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=addresses' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
print(f'addresses-edge count: {len(d)}')
for r in d:
    print(f\"  {r['reference_identifier']}: {r['source_type']} {r['source_id']}\")
"

for et in fields requirements test-specs; do
  curl -sw "$et %{http_code}\n" "http://127.0.0.1:8765/${et}" -o /dev/null 2>/dev/null
done
```

Decide closure posture per the rule. When in doubt, choose non-resolving.

**16c.** Author the close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`. Nine sections per v0.8:

```json
{
  "label": "build manual_config (PI-004 sibling)",
  "session": { "...": "summary references manual_config.md, PI-004, four-status lifecycle, cross-field invariant" },
  "conversation": { "...": "conversation metadata" },
  "work_tickets": [],
  "planning_items": [],
  "commits": [ "...": "build commit SHA(s) from step 17" ],
  "decisions": [
    { "...": "DEC-NNN — manual_config prefix / fields / four-status deviation / reference vocab / API surface, per manual_config.md §3.9.1 placeholders (may consolidate to one combined DEC or split per the §3.9.1 sketch)" }
  ],
  "references": [
    { "...": "edges from decisions to SES, conversation, spec reference_book if registered" }
  ],
  "resolves_planning_items": [],
  "addresses_planning_items": [{ "planning_item_identifier": "PI-004" }]
}
```

Populate `resolves_planning_items` per the §16b decision. Empty sections are still listed (v0.8 convention).

**16d.** Author the apply prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`. Mirror `CLAUDE-CODE-PROMPT-apply-close-out-ses-077.md` for standard pre-flight, apply command, post-apply verification. Include a specific PI-004 status check after apply: GET `/planning-items/PI-004` and verify status is Open (non-resolving posture) or Resolved (resolving posture).

### Step 17 — Commit

**Commit 1 — Build** (one atomic commit; the build is a coherent unit):

```bash
git add crmbuilder-v2/migrations/versions/NNNN_v0_5_create_manual_configs_table.py \
        crmbuilder-v2/src/crmbuilder_v2/access/models.py \
        crmbuilder-v2/src/crmbuilder_v2/access/vocab.py \
        crmbuilder-v2/src/crmbuilder_v2/access/exceptions.py \
        crmbuilder-v2/src/crmbuilder_v2/access/repositories/manual_config.py \
        crmbuilder-v2/src/crmbuilder_v2/api/errors.py \
        crmbuilder-v2/src/crmbuilder_v2/api/main.py \
        crmbuilder-v2/src/crmbuilder_v2/api/routers/manual_configs.py \
        crmbuilder-v2/src/crmbuilder_v2/api/schemas.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/client.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/panels/manual_config.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/manual_config_crud.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_manual_config_schema.py \
        tests/crmbuilder_v2/access/test_manual_config.py \
        tests/crmbuilder_v2/api/test_manual_configs_api.py \
        tests/crmbuilder_v2/ui/test_manual_config_panel.py

git commit -m "$(cat <<'EOF'
v2: PI-004 — build manual_config methodology entity

Lands the manual_config entity end-to-end per
methodology-schema-specs/manual_config.md v1.0. Third PI-004 sibling
alongside field, requirement, test_spec.

Schema (migration NNNN):
- New manual_configs table, 12 columns, CHECK on identifier (MCF-NNN),
  status (4 values), category (7 values).
- refs.source_type / target_type / relationship_kind CHECK extensions
  for 'manual_config' and the four outbound kinds.
- change_log.entity_type CHECK extension.

Access layer:
- repositories/manual_config.py — 8 functions following entity.py
  shape plus category validation and the §3.5.3 cross-field invariant
  (manual_config_completed_at + manual_config_completed_by required on
  transition into 'completed'; completed_at server-defaultable to now).
- New CompletedStatusRequiresCompletionFieldsError with dedicated
  handler rendering the {error, missing} body shape.
- vocab.py: MANUAL_CONFIG_STATUSES + STATUS_TRANSITIONS (4-status,
  terminal completed), MANUAL_CONFIG_CATEGORIES, ENTITY_TYPES +
  REFERENCE_RELATIONSHIPS + 4 _kinds_for_pair clauses (field /
  requirement clauses guarded on target-type presence for PI-004
  sibling sequencing).

API:
- routers/manual_configs.py — 8 endpoints under /manual-configs.
- ManualConfigCreateIn / ReplaceIn / PatchIn schemas with category +
  instructions + completion fields.
- main.py registers router + completed-fields handler.

UI:
- 7 client methods on UiClient.
- Sidebar 'Manual Configs' under Methodology.
- ManualConfigPanel with 5-column master pane (Identifier / Name /
  Category / Status / Updated) per §3.6.2 and detail pane that reveals
  completion fields only when status is 'completed' per §3.6.3.
- ManualConfigCreate/Edit/DeleteDialog with status-combo-driven
  Mark-Completed UX per §3.6.5.

Tests at tests/crmbuilder_v2/access/test_manual_config.py (≥12),
tests/crmbuilder_v2/api/test_manual_configs_api.py (≥6),
tests/crmbuilder_v2/ui/test_manual_config_panel.py (≥2). Covers the
4-status transition map, cross-field invariant on POST and PATCH
paths, soft-delete round-trip, identifier autoassign concurrency,
and reference round-trips for the two unconditionally-active outbound
kinds.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

**Commit 2 — Close-out apply.** Run the apply script then commit the regenerated snapshots:

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json
cd ..

git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md \
        PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log \
        PRDs/product/crmbuilder-v2/db-export/

git commit -m "$(cat <<'EOF'
v2: close out SES-NNN — manual_config build (PI-004 sibling)

Apply close-out payload for the manual_config build session. Writes
session, conversation, the DEC(s) authored at build close per
manual_config.md §3.9.1, and the addresses (or resolves) edge against
PI-004 per the PI-004 build-closure rule.

Regenerated db-export snapshots, new dep_NNN.log.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git pull --rebase origin main
```

Per the local-clone working convention: Claude commits, Doug pushes. Wait for Doug's review.

---

## Done

Reply with:

- Pre-build Alembic head: `<head>`
- Post-build Alembic head: `NNNN_v0_5_create_manual_configs_table`
- `manual_configs` table present in engagement DB: True / False
- Smoke PATCH to completed without completion fields returned 422: True / False (expected True)
- Smoke PATCH to completed with completion fields succeeded: True / False (expected True)
- Test suite: pre-build pass count vs post-build pass count (+≥20 new expected)
- PI-004 closure posture chosen: resolves / addresses
- Sibling status at close-out: which of field / requirement / test_spec are present in v2 DB
- Build commit SHA: `<sha>`
- Close-out commit SHA: `<sha>`
- Session identifier authored: `SES-NNN`
- Decision identifier(s) authored: `DEC-NNN`(`, DEC-NNN`...)
- Next prompt to run: if PI-004 resolved → whatever was queued post-PI-004; if non-resolving → one of the remaining PI-004 sibling builds (`field`, `requirement`, `test_spec`)
