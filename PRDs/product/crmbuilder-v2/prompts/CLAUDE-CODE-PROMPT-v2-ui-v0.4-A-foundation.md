# CLAUDE-CODE-PROMPT-v2-ui-v0.4-A-foundation

**Last Updated:** 05-14-26 14:00
**Series:** v2-ui-v0.4
**Slice:** A (1 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.3-E (UI v0.3 closeout — v0.3 test suite passing as of SES-009)

## Purpose

This is the first of six slices that build the CRMBuilder v2 desktop UI v0.4 per the companion PRD and implementation plan. This prompt builds slice **A — Foundation**.

Slice A lays the foundation infrastructure that the four entity-panel slices (B–E) depend on. Six categories of work, layered:

1. **Vocabulary additions in `vocab.py`.** Four new entity types (`domain`, `entity`, `process`, `crm_candidate`) admitted to `ENTITY_TYPES`. Two new relationship kinds (`entity_scopes_to_domain`, `process_hands_off_to_process`) admitted to `REFERENCE_RELATIONSHIPS`. Two new rules added to `_kinds_for_pair` for the registered pairs. `RELATIONSHIP_RULES` auto-recomputes at module load.

2. **Single Alembic migration extending three CHECK constraints on the `refs` table.** `refs.source_type` and `refs.target_type` admit the four new entity-type values. `refs.relationship_kind` admits the two new vocab values. One revision, atomic, forward and backward reversible.

3. **Methodology sidebar group container in the desktop UI.** New container in `ui/app.py` rendering below the existing Governance group. Initially empty; entries populate in slices B through E.

4. **File-watch refresh map extension.** `ui/refresh.py` extended so the four new entity-type JSON snapshot files (`domains.json`, `entities.json`, `processes.json`, `crm_candidates.json`) trigger panel refresh.

5. **`GET /<entity>/next-identifier` helper retrofit to the eight existing prefixed-identifier governance entity types** per DEC-043: decisions, sessions, risks, planning_items, topics, references, charter, status. Charter and status use versioned-identifier semantics.

6. **Spec guide section 6 amendment** per DEC-068 (renumbered from anticipatory DEC-065). Surgical edit applying the approved diff at `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md`. **The amendment text is already present in the spec guide as of v1.1** — slice A verifies it is in place and references the renumbered DEC-068 throughout; no further textual change to the spec guide should be required.

After this slice, the foundation is in place. Slice B builds the Domains panel; slices C, D, E build Entities, Processes, CRM Candidates respectively; slice F is closeout. This slice does NOT add any entity-table migration, any entity panel, any per-entity dialog, the README release note, or the `__version__` bump — those land in their own slices.

This slice does NOT write planning records (SES-017, SES-018, DEC-068 through DEC-074, PI-013, PI-014, PI-015) to the database. (Originally drafted referring to SES-016 and DEC-065 through DEC-070; renumbered at v0.4 PRD approval on 05-14-26 because the catalog ingestion build consumed those IDs.) Per the session-record-at-close pattern established after SES-008, those are authored by Doug through the desktop New Session dialog at the v0.4 build's closeout, not inside a Claude Code slice.

## Project context

UI v0.3 shipped as the most recent v2 release (SES-009). The v2 stack is end-to-end operational. v0.3 closed the testability gap for governance entities. v0.4 closes the corresponding gap for methodology content by introducing four new entity types — `domain`, `entity`, `process`, `crm_candidate` — under a new Methodology sidebar group. The v0.4-build-planning conversation (this prompt's predecessor) integrated four schema specs into a coherent six-slice release: `methodology-schema-specs/domain.md`, `entity.md`, `process.md`, `crm_candidate.md`.

The minimum-viable scope philosophy applies: each new entity type ships the thinnest shape that can faithfully host its Phase 1 output. v0.4's adoption pilot is the upcoming CBM redo, which will use the evolved methodology and v2 as its system of record for both governance (already supported in v0.3) and methodology content (this release).

Slice A is the only slice whose work is cross-cutting rather than scoped to one entity. Get the foundation right and the four feature slices follow cleanly; get it wrong and four downstream slices each carry the consequence.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set:
   - `git config user.name` should return `Doug Bower`
   - `git config user.email` should return `dbower44022@users.noreply.github.com`
4. Pull latest from origin: `git pull --rebase origin main`.
5. Confirm the storage system is operational. Verify-first, only start if not already running:
   - First check: `curl -sf http://127.0.0.1:8765/health` — if it returns 200, the API is already running; proceed to step 6.
   - If the health check fails (connection refused or no response), start the API in the background: `uv run crmbuilder-v2-api &`. Wait ~3 seconds, then re-run the health check. If the second check still fails, stop and report to Doug before proceeding.
6. Confirm the existing v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v`. Note the test count; this is the regression net for slice A.

## Reading order

Before producing any code, read the following in order:

1. `crmbuilder/CLAUDE.md` — universal entry. Pay particular attention to the "CRMBuilder v2 — Methodology Rearchitecture" section, especially line 48 (the `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair` / Alembic-migration triad) and line 52 (direct-API writes for prefixed-identifier entity types).
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` — the requirements you are implementing. All slices.
3. `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md` — the slice breakdown. Pay particular attention to **Step A** in section 4 and to section 5 (Migration Ordering).
4. `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — current version. The section 6 amendment lands as part of this slice; the existing section 6 is what you are editing.
5. The four schema specs at `PRDs/product/crmbuilder-v2/methodology-schema-specs/`: `domain.md`, `entity.md`, `process.md`, `crm_candidate.md`. The vocab and CHECK-constraint additions in this slice are scoped to what these specs require; verify alignment before coding.
6. v2 storage and UI surfaces you will modify:
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — `ENTITY_TYPES`, `REFERENCE_RELATIONSHIPS`, `_kinds_for_pair`, `RELATIONSHIP_RULES`
   - `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` — sidebar rendering; identify the Governance group construction pattern to mirror for the new Methodology group
   - `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` — `QFileSystemWatcher` and the entity-type → panel signal map
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/decisions.py`, `sessions.py`, `risks.py`, `planning_items.py`, `topics.py`, `references.py`, `charter.py`, `status.py` — read each to confirm the existing routing pattern for per-entity GET endpoints
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/` — each existing repository to confirm what next-identifier logic is already present (some may already have a `compute_next_identifier` method; if so, reuse it from the router; if not, add one)
   - `crmbuilder-v2/migrations/` — latest revision; identify the next revision number for the slice A migration

## Step 1 — Vocab additions in `access/vocab.py`

Modify `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` as follows.

### 1.1 `ENTITY_TYPES`

Extend the frozenset to include the four new entity-type strings. The resulting set should be:

```python
ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "charter",
        "status",
        "decision",
        "session",
        "risk",
        "planning_item",
        "topic",
        # v0.4 additions
        "domain",
        "entity",
        "process",
        "crm_candidate",
    }
)
```

### 1.2 `REFERENCE_RELATIONSHIPS`

Extend the frozenset to include the two new relationship-kind strings:

```python
REFERENCE_RELATIONSHIPS: frozenset[str] = frozenset(
    {
        "is_about",
        "supersedes",
        "decided_in",
        "affects",
        "covers",
        "blocks",
        "references",
        # v0.4 additions
        "entity_scopes_to_domain",
        "process_hands_off_to_process",
    }
)
```

### 1.3 `_kinds_for_pair`

Add two new conditional branches to the existing function. The complete updated function should read:

```python
def _kinds_for_pair(source_type: str, target_type: str) -> frozenset[str]:
    """Return the valid relationship kinds for a (source, target) pair.
    ... (existing docstring with one new bullet added describing the two new methodology kinds) ...
    """
    kinds = {"is_about", "references"}
    if target_type == "session":
        kinds.add("decided_in")
    if source_type == target_type:
        kinds.add("supersedes")
    if source_type == "risk":
        kinds.add("affects")
        kinds.add("blocks")
    if source_type == "planning_item":
        kinds.add("blocks")
    if source_type in ("charter", "status"):
        kinds.add("covers")
    # v0.4 additions per DEC-053 and DEC-058:
    if source_type == "entity" and target_type == "domain":
        kinds.add("entity_scopes_to_domain")
    if source_type == "process" and target_type == "process":
        kinds.add("process_hands_off_to_process")
    return frozenset(kinds)
```

`RELATIONSHIP_RULES` recomputes at module load from the expanded `ENTITY_TYPES` and the updated `_kinds_for_pair`, with no manual update needed — verify this in tests.

### 1.4 Update the docstring of `_kinds_for_pair`

Add a bullet item to the existing semantic-rules list naming the two new methodology rules:

```
    * ``entity_scopes_to_domain`` — source must be an entity, target must be
      a domain (v0.4, DEC-053).
    * ``process_hands_off_to_process`` — source and target must both be
      processes (v0.4, DEC-058; directional, source=producer, target=consumer).
```

## Step 2 — Alembic migration for refs CHECK constraint extensions

Create a new Alembic revision in `crmbuilder-v2/migrations/`. Identify the next revision number by looking at existing revision files; name the new file something like `0NNN_v0_4_foundation_refs_check_extensions.py` with `0NNN` being the appropriate next number.

The migration extends three CHECK constraints on the `refs` table:

- `refs.source_type` admits four new values: `domain`, `entity`, `process`, `crm_candidate`.
- `refs.target_type` admits the same four values.
- `refs.relationship_kind` admits two new values: `entity_scopes_to_domain`, `process_hands_off_to_process`.

SQLite does not support `ALTER TABLE ... DROP CONSTRAINT` or modifying CHECK constraints in place; the standard SQLite recipe is the table-recreation pattern via Alembic's `batch_alter_table` context manager. Use `op.batch_alter_table('refs', recreate='always')` to force table recreation, then drop the old constraints and add new ones.

The `upgrade()` function extends the constraints. The `downgrade()` function reverses to the v0.3 set. Both must run cleanly against the v0.3-shipped database.

Test the migration:

- `uv run alembic upgrade head` applies the migration cleanly.
- `uv run alembic downgrade -1` reverses cleanly.
- After the upgrade, direct DB insert into `refs` with `source_type='domain'` and a compatible kind succeeds.
- After the upgrade, direct DB insert with `source_type='entity'`, `target_type='domain'`, `relationship_kind='entity_scopes_to_domain'` succeeds.
- After the upgrade, direct DB insert with an unknown kind (`source_type='entity'`, `target_type='domain'`, `relationship_kind='foo'`) is rejected by the CHECK constraint.

## Step 3 — Methodology sidebar group container

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` to introduce the new Methodology sidebar group. Mirror the existing Governance group's construction pattern.

The Methodology group renders below the Governance group with title "Methodology". Initially empty (no panel entries). Each subsequent slice (B–E) adds its panel entry to this group; slice A only adds the container.

Pattern (illustrative; mirror the actual existing code):

```python
# After the Governance group is constructed
methodology_group = SidebarGroup(title="Methodology")
sidebar.add_group(methodology_group)
# Methodology group is intentionally empty in v0.4-A; entries populate in B-E.
```

The group container, even when empty, should render as a section header in the sidebar. Verify rendering with a manual smoke test or by checking the sidebar widget hierarchy in `qtbot`-based test.

## Step 4 — File-watch refresh map extension

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` so the file-watch service emits the appropriate per-entity-type signal when each of the four new snapshot files changes:

- `db-export/domains.json` → `domains_changed` signal
- `db-export/entities.json` → `entities_changed` signal
- `db-export/processes.json` → `processes_changed` signal
- `db-export/crm_candidates.json` → `crm_candidates_changed` signal

The signal names follow v0.3's convention. The file-watch service may not need new signal connections beyond expanding its internal entity-type → file path → signal map; verify against the existing v0.3 implementation.

The new entity-type panels (built in slices B-E) connect to these signals to refresh their master pane content on external changes. Slice A only wires the file-watch map; the signal consumers land in their respective slices.

## Step 5 — `GET /<entity>/next-identifier` helper retrofit

Add one helper endpoint per the eight existing prefixed-identifier governance entity types. Each endpoint returns `{"next": "<PREFIX>-<NNN>"}` for the next available identifier.

The endpoints to add:

| Router file | New endpoint | Identifier pattern |
|-------------|--------------|--------------------|
| `api/routers/decisions.py` | `GET /decisions/next-identifier` | `DEC-NNN` |
| `api/routers/sessions.py` | `GET /sessions/next-identifier` | `SES-NNN` |
| `api/routers/risks.py` | `GET /risks/next-identifier` | `RSK-NNN` |
| `api/routers/planning_items.py` | `GET /planning_items/next-identifier` | `PI-NNN` |
| `api/routers/topics.py` | `GET /topics/next-identifier` | `TOP-NNN` |
| `api/routers/references.py` | `GET /references/next-identifier` | `REF-NNN` |
| `api/routers/charter.py` | `GET /charter/next-identifier` | versioned, see below |
| `api/routers/status.py` | `GET /status/next-identifier` | versioned, see below |

For the six prefix-NNN entity types (decision through reference), the helper computes the next identifier by querying the access layer's existing logic for identifier assignment on POST omission, formatting as `{"next": "<PREFIX>-<NNN>"}`. If the access-layer method doesn't yet exist for a given entity type, add a thin wrapper called `compute_next_identifier()` on that repository — query the maximum existing identifier (including soft-deleted records, to avoid identifier reuse), increment the numeric suffix, zero-pad to three digits, prepend the prefix.

For charter and status, the identifier semantics are versioned: the entity uses version numbers (e.g., `charter v0.7`, `status v1.2`), not `CHR-NNN` or `STA-NNN`. The helper for these returns the next version per the access-layer's existing versioned-replace pattern. The exact response shape — whether `{"next": "0.8"}` or `{"next_version": "0.8"}` or `{"next": "v0.8"}` — depends on what the existing versioned-replace logic produces; mirror that.

Add tests in `tests/crmbuilder_v2/api/test_next_identifier_retrofit.py`. Cover:

- Happy path for each of the eight endpoints (response returns 200 and the expected `{"next": ...}` payload).
- Concurrent-fetch test (two concurrent calls return the same value but consuming the value via POST is atomic — the second POST that uses the same identifier returns a uniqueness error).
- Boundary test for empty-DB case (no existing records → returns `{"next": "<PREFIX>-001"}` for the prefix-NNN types).

## Step 6 — Spec guide section 6 amendment

Apply the surgical edit to `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` section 6. The diff is:

### 6.1 Add a scope-note paragraph immediately after the section header (before the existing "Conventions that all four..." sentence)

Insert:

```markdown
**Scope note (added at v0.4 build planning).** The conventions in this section apply to the four methodology entity types in the methodology-entity-schema-design workstream (`domain`, `entity`, `process`, `crm_candidate`) and to methodology entity types introduced in v0.5+. They do NOT apply retroactively to v2's existing governance entity types (`decision`, `session`, `risk`, `planning_item`, `topic`, `reference`, `charter`, `status`); governance entities retain their pre-workstream conventions until and unless **PI-006** retrofit lands. Rows marked "methodology only" below carry this forward-only scope explicitly.
```

### 6.2 Update the "Status field name" table row

From:

```markdown
| Status field name | `status` (not `state`, `lifecycle_status`, etc.) |
```

To:

```markdown
| Status field name (methodology only) | `{parent}_status` per parent-prefix convention (DEC-046). E.g., `domain_status`, `entity_status`, `crm_candidate_status`. Governance entities retain `status` until PI-006. |
```

### 6.3 Update the "Relationship-kind naming" table row

From:

```markdown
| Relationship-kind naming | `verb_phrase` style (e.g., `process_belongs_to_domain`, not `process_domain_membership`) |
```

To:

```markdown
| Relationship-kind naming (methodology only) | For new vocab entries involving methodology entities, `{source}_{verb}_{target}` source-first pattern per DEC-048. E.g., `entity_scopes_to_domain`, `process_hands_off_to_process`. Governance vocab (`is_about`, `references`, `decided_in`, `supersedes`, `affects`, `covers`, `blocks`) retains its pre-workstream naming. |
```

### 6.4 Update the "Field naming" table row

From:

```markdown
| Field naming | `snake_case`, singular nouns for scalar fields, plural nouns for collection/JSON fields |
```

To:

```markdown
| Field naming (methodology only) | `snake_case`, with all fields including identifier and timestamps prefixed with the parent entity name per DEC-046. E.g., `domain_identifier`, `domain_name`, `domain_created_at`. Singular nouns for scalar fields; plural for collection/JSON fields. Governance entities retain their pre-workstream conventions until PI-006. |
```

### 6.5 Append a sentence to the closing paragraph

The existing closing paragraph reads:

> A spec that deviates from any of these must explicitly call out the deviation and justify it in the relevant section.

Append:

> The methodology workstream produced three documented deviations across the four specs (cited by DEC-055, DEC-056, DEC-062), which the v0.4-build-planning conversation's cross-spec consistency check accepted as well-justified.

Update the spec guide's "Last Updated" header to `05-12-26 <HH:MM>` matching the commit timestamp, and add a Change Log entry recording the amendment.

## Step 7 — Tests

Add three new test modules:

### 7.1 `tests/crmbuilder_v2/access/test_vocab_v0_4.py`

Tests for the vocab additions:

- `ENTITY_TYPES` contains all four new strings: `domain`, `entity`, `process`, `crm_candidate`.
- `REFERENCE_RELATIONSHIPS` contains both new strings: `entity_scopes_to_domain`, `process_hands_off_to_process`.
- `_kinds_for_pair("entity", "domain")` returns a frozenset containing `entity_scopes_to_domain`, plus `is_about` and `references` (universal).
- `_kinds_for_pair("process", "process")` returns a frozenset containing `process_hands_off_to_process`, plus `is_about`, `references`, and `supersedes` (matched-type universal).
- `_kinds_for_pair("domain", "entity")` (reverse direction) does NOT contain `entity_scopes_to_domain` (the kind is directional from entity to domain only).
- `_kinds_for_pair("domain", "domain")` contains `supersedes` (matched type) but no methodology kinds.
- `_kinds_for_pair("crm_candidate", "session")` contains `decided_in` (universal rule applies).
- `RELATIONSHIP_RULES[("entity", "domain")]` matches `_kinds_for_pair("entity", "domain")` — verifies the recomputation at module load.
- `RELATIONSHIP_RULES[("crm_candidate", "decision")]` contains `is_about` and `references` (the universal kinds; verifies the new entity type participates in the auto-recomputation).

### 7.2 `tests/crmbuilder_v2/api/test_next_identifier_retrofit.py`

Tests for the eight retrofitted helper endpoints. Per the patterns in Step 5 above.

### 7.3 Existing tests should continue to pass

The slice A changes do not touch the access-layer or REST behavior of any existing entity type; the v0.3 regression test suite should pass unchanged. Verify by running `uv run pytest tests/crmbuilder_v2/ -v` and confirming all prior tests pass alongside the new ones.

## Acceptance verification

Before committing, run each of the following and confirm:

1. **Vocab tests pass.** `uv run pytest tests/crmbuilder_v2/access/test_vocab_v0_4.py -v` — all new tests green.
2. **Retrofit tests pass.** `uv run pytest tests/crmbuilder_v2/api/test_next_identifier_retrofit.py -v` — all new tests green.
3. **Alembic migration applies forward and backward.** `uv run alembic upgrade head` then `uv run alembic downgrade -1` then `uv run alembic upgrade head` again. All three operations succeed without errors.
4. **Full test suite green.** `uv run pytest tests/crmbuilder_v2/ -v` returns no failures.
5. **Cascading vocab dialog smoke (manual or via qtbot).** Open the desktop app; open the Reference Create dialog from any entity panel. Confirm that the source-type combo lists the four new entity types (`domain`, `entity`, `process`, `crm_candidate`). Select `entity` as source type, `domain` as target type — confirm `entity_scopes_to_domain` appears in the relationship-kind combo. Select `process` as source and target — confirm `process_hands_off_to_process` appears.
6. **Methodology sidebar group renders.** Open the desktop app; confirm a "Methodology" group header renders below the existing Governance group. The group is empty in slice A; just confirm the header is present.
7. **About dialog unchanged.** The About dialog shows the v0.3-shipped `__version__` (not yet `0.4.0`); the bump lands in slice F.

If any verification step fails, stop and report to Doug before committing.

## Commit

Single commit (or two if the spec guide amendment is meaningful on its own; one is preferred):

```bash
git add crmbuilder-v2/src/crmbuilder_v2/access/vocab.py \
        crmbuilder-v2/migrations/0NNN_v0_4_foundation_refs_check_extensions.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/app.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py \
        crmbuilder-v2/src/crmbuilder_v2/api/routers/*.py \
        crmbuilder-v2/src/crmbuilder_v2/access/repositories/*.py \
        PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md \
        tests/crmbuilder_v2/access/test_vocab_v0_4.py \
        tests/crmbuilder_v2/api/test_next_identifier_retrofit.py
git commit -m "v2: v0.4 slice A — foundation (vocab, refs CHECK migration, sidebar group, next-identifier retrofit, spec guide amendment)"
```

Doug pushes. Do NOT push.

## What NOT to do

- Do NOT create any new entity-table migrations (those land in slices B–E).
- Do NOT add any methodology entity panels (those land in slices B–E).
- Do NOT add any methodology entity dialogs (those land in slices B–E).
- Do NOT write any session or decision records (SES-017, SES-018, DEC-068 through DEC-074, PI-013/014/015). Per the session-record-at-close pattern, those are authored by Doug through the desktop dialog at conversation close.
- Do NOT bump `__version__` to `0.4.0` (that lands in slice F).
- Do NOT add the README v0.4 release note (that lands in slice F).
- Do NOT modify any existing entity type's schema, access-layer methods, REST endpoints, or UI behavior — slice A is strictly additive (the helper-endpoint retrofit is the one addition to existing entity types, and it adds a new endpoint without touching existing endpoints).
- Do NOT introduce new dialogs or new dialog framework features. v0.3's `EntityCrudDialog`, `EntityCrudDeleteDialog`, and `ReferenceCreateDialog` are reused unchanged.
- Do NOT change v0.3's governance-entity field naming. Governance entities retain `identifier`, `created_at`, etc. without parent-prefix until PI-006 retrofit lands (deferred to v0.5+ per DEC-073).

## If slice A bloats

If during execution this slice's prompt scope feels too large for one coherent Claude Code run, the slice can split into A1 (Steps 1–4 + Step 6 — methodology foundation) and A2 (Step 5 — helper retrofit). The decision is made at execution time, not pre-committed. If you split, name the second prompt file `CLAUDE-CODE-PROMPT-v2-ui-v0.4-A2-helper-retrofit.md` and rename the existing file to `CLAUDE-CODE-PROMPT-v2-ui-v0.4-A1-foundation.md`; update the slice count in both prompts and in the implementation plan.

---

*End of prompt.*
