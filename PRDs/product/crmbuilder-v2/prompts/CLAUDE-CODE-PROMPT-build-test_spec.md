# CLAUDE-CODE-PROMPT-build-test_spec

**Last Updated:** 05-25-26
**Operating mode:** DETAIL
**Series:** PI-004 build tranche (methodology entities for v0.5+: `field`, `requirement`, `manual_config`, `test_spec`)
**Slice:** `test_spec` — the verification-specification methodology entity
**Status:** Ready to execute. Blocked by: nothing — `test_spec.md` spec is canonical.
**Companions (read in order):**
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/test_spec.md` v1.0 — authoritative spec. Sections cited inline: §3.1 identity, §3.2 fields, §3.3 relationships, §3.4 lifecycle (§3.4.3 dual-axis rationale, §3.4.4 cross-field invariant), §3.5 API, §3.6 UI, §3.7 sixteen acceptance criteria, §3.8 open questions.
- `crmbuilder-v2/migrations/versions/0008_v0_4_create_entities_table.py` — methodology-entity migration pattern.
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/entity.py` — repository pattern (SAVEPOINT-retry auto-assign; transition validation; case-insensitive name uniqueness; soft-delete does NOT cascade refs).
- `crmbuilder-v2/src/crmbuilder_v2/api/routers/entities.py` — router pattern (eight endpoints, `{data,meta,errors}` envelope via `ok(...)`, body-key-strip on PATCH with `exclude_unset=True`).
- `crmbuilder-v2/src/crmbuilder_v2/ui/panels/entities.py` + `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/entity_crud.py` + `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_entity_schema.py` — UI pattern.
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — vocabulary pattern (`*_STATUSES` + `*_STATUS_TRANSITIONS`, `ENTITY_TYPES`, `REFERENCE_RELATIONSHIPS`, `_kinds_for_pair`).
- `CLAUDE.md` line 48 (vocab triad once-per-kind rule) and the `{data,meta,errors}` envelope note.

---

## Purpose

Land the full `test_spec` entity end-to-end per `test_spec.md` v1.0 — migration, ORM model, vocab, repository, schemas, REST, UI client, sidebar, main-window dispatch, panel + dialogs, tests, close-out artifacts. One of four PI-004 siblings; see "PI-004 build-closure rule" at the bottom.

After this slice lands:
- `test_specs` table exists with 12 substantive columns + 3 base timestamps (§3.7 AC1).
- REST `/test-specs` reachable: eight standard endpoints + one `POST /test-specs/{id}/record-run` convenience.
- Methodology lifecycle (`candidate`/`confirmed`/`deferred`) and execution outcome (`not_run`/`passing`/`failing`/`skipped`) validate independently per §3.4 — restricted transitions on status, unrestricted on outcome.
- Server enforces §3.4.4 cross-field invariant: `last_run_at` auto-set when outcome moves to a run state, auto-cleared on move back to `not_run`.
- Three new outgoing reference kinds (`test_spec_touches_entity`, `test_spec_touches_field`, `test_spec_exercises_process`) registered exactly once per the CLAUDE.md once-per-kind rule. **The inbound `requirement_verified_by_test_spec` kind is NOT registered here** — the requirement-side sibling spec registers it.
- "Test Specs" sidebar entry in the Methodology group; master pane shows the five-column layout with the color-cued Last Run column (§3.6.2 deviation); detail pane uses the three-section grouping per §3.6.3.

If `field` is not yet in `ENTITY_TYPES` when this prompt runs, the `(test_spec, field)` clause in `_kinds_for_pair` is still authored but dormant — it activates automatically when the field-side build adds `'field'` to `ENTITY_TYPES`.

---

## Pre-flight

1. `pwd` = `~/Dropbox/Projects/crmbuilder` and `git status` clean. Stop and report otherwise.
2. Confirm `git config user.name="Doug Bower"` / `git config user.email="doug@dougbower.com"`.
3. `git pull --rebase origin main` — stop on conflicts.
4. Read all companion documents listed above; the spec wins on any disagreement with this prompt.
5. **Sidebar-ordering check.** §3.6.1 puts "Test Specs" between Requirements and Manual Config. Verify what sibling entries exist now:

   ```bash
   grep -nE '"Test Specs"|"Requirements"|"Fields"|"Personas"|"Manual Config"' crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py || true
   ```

   Insert at the §3.6.1 position relative to whichever siblings exist; if none do yet, append after `"CRM Candidates"` with a comment noting the v0.5 build conversation finalizes ordering. Soft choice, do not block.

6. Inventory existing prefixes to confirm `TST` is unclaimed:

   ```bash
   grep -rEn '"[A-Z]{2,4}-[0-9]+"|GLOB '"'"'[A-Z]{2,4}-' crmbuilder-v2/src/crmbuilder_v2/access/ | grep -v __pycache__ | grep -E 'TST-' && echo "COLLISION" || echo "TST is free"
   ```

7. Capture pre-build Alembic head and pre-build test pass count:

   ```bash
   cd crmbuilder-v2 && uv run alembic current && cd ..
   uv run pytest tests/crmbuilder_v2/ --tb=short 2>&1 | tail -10
   ```

   The new migration's `down_revision` is whatever `alembic current` returns (likely `0012_v0_8_commits_and_blocked_by_rename` or a later v0.8 revision if a sibling already landed).

---

## Implementation

### Step 1 — Migration

Create `crmbuilder-v2/migrations/versions/00XX_v0_5_create_test_specs_table.py` where `00XX` is the next sequence after the current head. Pattern is `0008_v0_4_create_entities_table.py` for the table create plus `0006_v0_4_foundation_refs_check_extensions.py` for the CHECK extensions.

**Module docstring** must state: parent-prefix field naming per DEC-046; `TST-NNN` GLOB CHECK; `test_spec_status` enum CHECK with restricted transition map enforced at the access layer; `test_spec_last_run_outcome` enum CHECK with UNRESTRICTED transitions (no transition map — note explicitly so future readers do not invent one); the §3.4.4 cross-field invariant is access-layer enforced, NOT a SQL CHECK; reversible.

**`upgrade()` does three things in order:**

1. **Extend `refs` CHECKs.** Use `batch_alter_table("refs")` to drop and recreate `ck_ref_source_type`, `ck_ref_target_type`, `ck_ref_relationship` with `'test_spec'` added to source/target and these three kinds added to relationship (alphabetical, with previous-head values preserved): `'test_spec_exercises_process'`, `'test_spec_touches_entity'`, `'test_spec_touches_field'`. Read the current head migration's CHECK strings as the `_OLD_*` constants for `downgrade()`.
2. **Extend `change_log.entity_type` CHECK** to admit `'test_spec'`. Pattern from `0011`.
3. **Create `test_specs` table:**

   ```python
   op.create_table(
       "test_specs",
       sa.Column("test_spec_identifier", sa.String(length=32), nullable=False),
       sa.Column("test_spec_name", sa.String(length=255), nullable=False),
       sa.Column("test_spec_description", sa.Text(), nullable=False),
       sa.Column("test_spec_setup", sa.Text(), nullable=True),
       sa.Column("test_spec_steps", sa.Text(), nullable=False),
       sa.Column("test_spec_expected", sa.Text(), nullable=False),
       sa.Column("test_spec_notes", sa.Text(), nullable=True),
       sa.Column("test_spec_status", sa.String(length=16), nullable=False,
                 server_default="candidate"),
       sa.Column("test_spec_last_run_outcome", sa.String(length=16),
                 nullable=False, server_default="not_run"),
       sa.Column("test_spec_last_run_at", sa.DateTime(timezone=True), nullable=True),
       sa.Column("test_spec_last_run_notes", sa.Text(), nullable=True),
       sa.Column("test_spec_created_at", sa.DateTime(timezone=True), nullable=False),
       sa.Column("test_spec_updated_at", sa.DateTime(timezone=True), nullable=False),
       sa.Column("test_spec_deleted_at", sa.DateTime(timezone=True), nullable=True),
       sa.CheckConstraint("test_spec_identifier GLOB 'TST-[0-9][0-9][0-9]'",
                          name="ck_test_spec_identifier_format"),
       sa.CheckConstraint("test_spec_status IN ('candidate', 'confirmed', 'deferred')",
                          name="ck_test_spec_status"),
       sa.CheckConstraint(
           "test_spec_last_run_outcome IN ('failing', 'not_run', 'passing', 'skipped')",
           name="ck_test_spec_last_run_outcome"),
       sa.PrimaryKeyConstraint("test_spec_identifier"),
   )
   ```

   Then three indexes via `batch_alter_table("test_specs")`: `ix_test_specs_test_spec_status`, `ix_test_specs_test_spec_last_run_outcome`, `ix_test_specs_test_spec_deleted_at`.

**`downgrade()`** drops the table, then restores the prior `change_log` and `refs` CHECKs.

**Constraint-name verification.** Before authoring, inspect the head migration's actual names — some are `ck_ref_*` vs `ck_refs_*`, some are `ck_changelog_entity_type` vs `ck_change_log_entity_type`:

```bash
grep -nE 'drop_constraint.*type_="check"|create_check_constraint' \
  crmbuilder-v2/migrations/versions/0012_v0_8_commits_and_blocked_by_rename.py
```

Use whatever the existing migrations use.

### Step 2 — ORM model

Add `class TestSpec(Base)` to `crmbuilder-v2/src/crmbuilder_v2/access/models.py` after `CrmCandidate`. Mirror `class Entity(Base)` exactly with the test-spec column inventory from Step 1. CHECK constraints use the `_check_in` helper:

```python
CheckConstraint("test_spec_identifier GLOB 'TST-[0-9][0-9][0-9]'",
                name="ck_test_spec_identifier_format"),
CheckConstraint(_check_in("test_spec_status", TEST_SPEC_STATUSES),
                name="ck_test_spec_status"),
CheckConstraint(_check_in("test_spec_last_run_outcome", TEST_SPEC_RUN_OUTCOMES),
                name="ck_test_spec_last_run_outcome"),
```

Add `TEST_SPEC_STATUSES`, `TEST_SPEC_RUN_OUTCOMES` to the vocab imports at the top of `models.py`. Defaults: `test_spec_status` → `"candidate"`; `test_spec_last_run_outcome` → `"not_run"`. Class docstring should call out the dual-axis state pattern (§3.4.3) and the snapshot-only execution-outcome shape (history deferred per §3.8.3).

### Step 3 — Vocab

Edit `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`.

**3a. Add `TEST_SPEC_STATUSES` + `TEST_SPEC_STATUS_TRANSITIONS`** after `ENTITY_STATUS_TRANSITIONS` — mirror the `ENTITY_*` block exactly (three values, propose-verify gate per DEC-047). Comment that the shape mirrors `domain` and `entity`.

**3b. Add `TEST_SPEC_RUN_OUTCOMES`** after `TEST_SPEC_STATUS_TRANSITIONS`. **No transitions dict** — outcome transitions are unrestricted per §3.4.2. Comment explicitly that this is intentional and explains why per §3.4.3 (observational, not decisional).

```python
TEST_SPEC_RUN_OUTCOMES: frozenset[str] = frozenset(
    {"not_run", "passing", "failing", "skipped"}
)
```

**3c. Add `'test_spec'` to `ENTITY_TYPES`** alongside the methodology block. Inline comment noting PI-004 sibling.

**3d. Extend `REFERENCE_RELATIONSHIPS`** — three new kinds in a labeled PI-004 sub-block:

```python
        # v0.5+ methodology additions (PI-004 sibling — test_spec).
        # Three outbound kinds registered here. The inbound
        # ``requirement_verified_by_test_spec`` kind is registered by
        # ``requirement.md``'s build prompt, not here, per CLAUDE.md
        # line 48's once-per-kind rule.
        "test_spec_exercises_process",
        "test_spec_touches_entity",
        "test_spec_touches_field",
```

**Do NOT add `requirement_verified_by_test_spec` here.**

**3e. Extend `_kinds_for_pair`** with three clauses in the methodology block:

```python
    # v0.5+ methodology additions per ``test_spec.md`` §3.3.1:
    if source_type == "test_spec" and target_type == "entity":
        kinds.add("test_spec_touches_entity")
    if source_type == "test_spec" and target_type == "field":
        kinds.add("test_spec_touches_field")
    if source_type == "test_spec" and target_type == "process":
        kinds.add("test_spec_exercises_process")
```

The `(test_spec, field)` clause is dormant until `'field'` is added to `ENTITY_TYPES` by the field-side build — `RELATIONSHIP_RULES` re-evaluates at module load and the clause activates automatically.

Update the `_kinds_for_pair` docstring bullet list to include the three new rules.

### Step 4 — Repository

Create `crmbuilder-v2/src/crmbuilder_v2/access/repositories/test_spec.py`. Mirror `entity.py` closely. Deviations: dual-axis status validation; cross-field invariant on outcome / last_run_at; `record_run` convenience helper.

**Module constants:**

```python
_ENTITY_TYPE = "test_spec"
_IDENTIFIER_PREFIX = "TST"
_IDENTIFIER_RE = re.compile(r"^TST-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50

_PATCHABLE_FIELDS = frozenset({
    "name", "description", "setup", "steps", "expected", "notes",
    "status", "last_run_outcome", "last_run_at", "last_run_notes",
})

# Outcomes that require ``last_run_at`` to be populated per §3.4.4.
_RUN_OUTCOMES = frozenset({"passing", "failing", "skipped"})
```

**Validation helpers.** Same shape as `entity.py` plus two new ones: `_require_status` (against `TEST_SPEC_STATUSES`) and `_require_outcome` (against `TEST_SPEC_RUN_OUTCOMES`). `_check_transition` consults `TEST_SPEC_STATUS_TRANSITIONS`. **No `_check_outcome_transition` function** — outcomes are unrestricted.

**Cross-field invariant helper** — the load-bearing piece for §3.4.4:

```python
def _apply_outcome_invariant(
    row: TestSpec,
    *,
    requested_outcome: str | None,
    requested_last_run_at: datetime | None,
    last_run_at_supplied: bool,
) -> None:
    """Enforce the §3.4.4 cross-field invariant.

    ``last_run_at_supplied`` distinguishes an explicit ``None`` (client
    asked to clear) from an omitted value (client did not touch). The
    PATCH router passes ``"last_run_at" in fields`` for this signal.

    Behavior:

    * Outcome → ``not_run``: clear ``last_run_at`` AND ``last_run_notes``
      regardless of what the client supplied.
    * Outcome → run state (passing/failing/skipped): if client supplied
      ``last_run_at`` explicitly as ``None`` while requesting a run
      state, raise 422; else honor supplied value; else server sets
      ``datetime.now(UTC)`` if ``last_run_at`` is currently null.
    * Outcome unchanged: no-op (caller's other patch logic may still
      touch ``last_run_at`` / ``last_run_notes`` directly).
    """
    if requested_outcome == "not_run":
        row.test_spec_last_run_outcome = "not_run"
        row.test_spec_last_run_at = None
        row.test_spec_last_run_notes = None
        return
    if requested_outcome in _RUN_OUTCOMES:
        row.test_spec_last_run_outcome = requested_outcome
        if last_run_at_supplied and requested_last_run_at is None:
            raise UnprocessableError([FieldError(
                "test_spec_last_run_at",
                "required_when_outcome_is_run_state",
                "test_spec_last_run_at cannot be null when outcome is "
                "passing/failing/skipped",
            )])
        if requested_last_run_at is not None:
            row.test_spec_last_run_at = requested_last_run_at
        elif row.test_spec_last_run_at is None:
            row.test_spec_last_run_at = datetime.now(UTC)
```

**Public functions (mirror `entity.py`):**

- `list_test_specs(session, *, include_deleted=False)`, `get_test_spec(session, identifier, *, include_deleted=False)`, `next_test_spec_identifier(session)` — identical pattern.
- `create_test_spec(session, *, name, description, steps, expected, setup=None, notes=None, status="candidate", last_run_outcome="not_run", last_run_at=None, last_run_notes=None, identifier=None)` — validate, name-uniqueness check, server-assign or explicit-identifier, then `_apply_outcome_invariant(...)` so a POST with a non-default outcome auto-populates `last_run_at`. The API layer passes `last_run_at_supplied=("test_spec_last_run_at" in body_dict)`.
- `update_test_spec(session, identifier, **all_fields)` — full PUT replace, then invariant helper.
- `patch_test_spec(session, identifier, **fields)` — validate unknown keys against `_PATCHABLE_FIELDS`; apply each known field individually; the invariant helper runs at the end with `last_run_at_supplied=("last_run_at" in fields)`.
- `delete_test_spec(session, identifier)`, `restore_test_spec(session, identifier)` — same as `entity.py`. Delete does NOT cascade references (§3.4.6).

**Convenience helper:**

```python
def record_run(
    session: Session,
    identifier: str,
    *,
    outcome: str,
    notes: str | None = None,
    at: datetime | None = None,
) -> dict:
    """Atomic update of outcome + last_run_at + last_run_notes.

    Per §3.8.1's open question — ship this in v0.5+. The PATCH endpoint
    can do the same three-field update; this dedicated path surfaces a
    clearer intent for automation callers and aligns with the
    methodology-vs-execution principle (§3.4.3).
    """
    row = _get_row(session, identifier)
    before = to_dict(row)
    _require_outcome(outcome)
    _apply_outcome_invariant(
        row,
        requested_outcome=outcome,
        requested_last_run_at=at,
        last_run_at_supplied=(at is not None),
    )
    if outcome != "not_run":
        row.test_spec_last_run_notes = notes
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE,
         entity_identifier=identifier, operation="update",
         before=before, after=after)
    return after
```

When outcome is `not_run`, the invariant helper clears `last_run_notes` so the `notes` arg is ignored — document inline.

### Step 5 — Pydantic schemas

Edit `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py`. Add a `# ---------- Test Specs ----------` block. `from datetime import datetime` if not already imported.

```python
class TestSpecCreateIn(_Base):
    test_spec_name: str
    test_spec_description: str
    test_spec_steps: str
    test_spec_expected: str
    test_spec_setup: str | None = None
    test_spec_notes: str | None = None
    test_spec_status: str | None = None
    test_spec_last_run_outcome: str | None = None
    test_spec_last_run_at: datetime | None = None
    test_spec_last_run_notes: str | None = None
    test_spec_identifier: str | None = None


class TestSpecReplaceIn(_Base):
    test_spec_identifier: str | None = None
    test_spec_name: str
    test_spec_description: str
    test_spec_steps: str
    test_spec_expected: str
    test_spec_setup: str | None = None
    test_spec_notes: str | None = None
    test_spec_status: str
    test_spec_last_run_outcome: str
    test_spec_last_run_at: datetime | None = None
    test_spec_last_run_notes: str | None = None


class TestSpecPatchIn(_Base):
    test_spec_name: str | None = None
    test_spec_description: str | None = None
    test_spec_steps: str | None = None
    test_spec_expected: str | None = None
    test_spec_setup: str | None = None
    test_spec_notes: str | None = None
    test_spec_status: str | None = None
    test_spec_last_run_outcome: str | None = None
    test_spec_last_run_at: datetime | None = None
    test_spec_last_run_notes: str | None = None


class TestSpecRecordRunIn(_Base):
    """POST /test-specs/{id}/record-run body (§3.8.1)."""
    outcome: str
    notes: str | None = None
    at: datetime | None = None
```

### Step 6 — Router

Create `crmbuilder-v2/src/crmbuilder_v2/api/routers/test_specs.py`. Mirror `entities.py`. Nine endpoints:

- `GET /test-specs` (with `?include_deleted=true`)
- `GET /test-specs/next-identifier`
- `GET /test-specs/{identifier}`
- `POST /test-specs` (status 201)
- `PUT /test-specs/{identifier}`
- `PATCH /test-specs/{identifier}` — body-key-strip via `_FIELD_PREFIX = "test_spec_"`, `provided = body.model_dump(exclude_unset=True)`. **Load-bearing:** `exclude_unset` is what makes the `(supplied vs omitted)` signal work for the §3.4.4 invariant.
- `DELETE /test-specs/{identifier}`
- `POST /test-specs/{identifier}/restore`
- `POST /test-specs/{identifier}/record-run` — body is `TestSpecRecordRunIn`; calls `test_spec.record_run(s, identifier, outcome=body.outcome, notes=body.notes, at=body.at)`.

POST + record-run handlers must also pass the supplied-signal correctly: extract `provided = body.model_dump(exclude_unset=True)` and pass `last_run_at_supplied=("test_spec_last_run_at" in provided)` (or the equivalent) to the repository function.

### Step 7 — `main.py` wiring

Edit `crmbuilder-v2/src/crmbuilder_v2/api/main.py`. Add `test_specs` to the router imports and `app.include_router(test_specs.router)` after `app.include_router(crm_candidates.router)` (preserving the v0.4 methodology block order).

### Step 8 — UI client

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/client.py`. Add a Test Specs block after CRM Candidates. Standard seven methods plus one convenience — pattern from the entity methods at lines 661–791:

- `list_test_specs(self, *, include_deleted=False) -> list[dict]`
- `get_test_spec(self, identifier: str) -> dict`
- `create_test_spec(self, body: dict) -> dict`
- `update_test_spec(self, identifier: str, body: dict) -> dict`
- `patch_test_spec(self, identifier: str, body: dict) -> dict`
- `delete_test_spec(self, identifier: str) -> Any`
- `restore_test_spec(self, identifier: str) -> dict`
- `next_test_spec_identifier(self) -> str`
- `record_test_spec_run(self, identifier: str, body: dict) -> dict` — `POST /test-specs/{identifier}/record-run`. Body shape: `{"outcome": "passing", "notes": "...", "at": "2026-..."}` (notes/at optional).

### Step 9 — Sidebar

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py`. Insert `"Test Specs"` into the Methodology group at the position chosen in Pre-flight step 5. Inline comment noting PI-004 sibling-ordering finalization deferred to v0.5 build conversation.

### Step 10 — Main window dispatch

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py`:

1. `from crmbuilder_v2.ui.panels.test_spec import TestSpecsPanel`.
2. Add `elif entry == "Test Specs": page = TestSpecsPanel(self._client)` in the dispatch loop near line 152.
3. Add `"test_spec": "Test Specs",` to `ENTITY_TYPE_TO_SIDEBAR_LABEL` in the Methodology block.

### Step 11 — Panel

Create `crmbuilder-v2/src/crmbuilder_v2/ui/panels/test_spec.py`. Mirror `entities.py` (it already renders outgoing-edge `ReferencesSection`). Three deviations:

**Five columns per §3.6.2:**

```python
def list_columns(self) -> list[ColumnSpec]:
    return [
        ColumnSpec(field="test_spec_identifier", title="Identifier", width=120),
        ColumnSpec(field="test_spec_name", title="Name"),
        ColumnSpec(field="test_spec_status", title="Status", width=110),
        ColumnSpec(field="test_spec_last_run_outcome", title="Last Run", width=110),
        ColumnSpec(field="test_spec_updated_at", title="Updated", width=180),
    ]
```

**Color-cued Last Run column — UI deviation per §3.6.2.** Label text always shown; color is additive. Implementation: inspect `ColumnSpec` for a cell-style callback hook; if absent, attach a small `QStyledItemDelegate` subclass to the Last Run column post-construction in `__init__`. Color tokens (resolve via `crmbuilder_v2.ui.styling.t(...)`; fall back to hex):

| Outcome | Token | Fallback hex |
|---|---|---|
| `passing` | `color.success.default` | `#1b7e1b` |
| `failing` | `color.danger.default` | `#b41a1a` |
| `not_run` | `color.neutral.500` | `#888888` |
| `skipped` | `color.warning.default` | `#c0830d` |

**Document the deviation inline** — comment block at the top of the panel module naming §3.6.2 as authority and the styling-deviation flag in `test_spec.md` v1.0 changelog.

**Three-section detail pane per §3.6.3.** Extend `EntitiesPanel.render_detail`'s shape with explicit subsection headers:

- **Identity-and-methodology block:** Identifier (read-only label), Name (read-only line), Description (read-only multiline, placeholder "What does this test verify?"), Status (combo, disabled — same hint-caption treatment as `EntitiesPanel`).
- `_separator()` + bold `"Test body"` label.
- **Test body block:** Setup (multiline, placeholder "Preconditions — what must be true before the test runs?"), Steps (multiline, placeholder "Numbered steps to execute the test"), Expected (multiline, placeholder "Expected results — what must be true after the steps execute?").
- `_separator()` + bold `"Last run"` label.
- **Last run block:** Last Run Outcome (combo, disabled — editing through dialog/record-run), Last Run At (read-only display or "—"), Last Run Notes (read-only multiline). Optionally render a small color swatch beside the outcome combo to echo the master-pane cue.
- **Internal notes:** `CollapsibleSection("Internal notes", notes_value, expanded=False)`.
- **References:** `ReferencesSection("test_spec", identifier, extras.get("references") or {}, client=self._client)`.

**Record Run button** — append to the action strip (next to Edit/Delete) when not soft-deleted. Click opens `TestSpecRecordRunDialog` from Step 12.

Right-click context menu, fetch hooks, refresh handling, navigation signals, identifier addressing — all carry forward from `EntitiesPanel` unchanged.

### Step 12 — Dialogs

**12a. `_test_spec_schema.py`** — mirror `_entity_schema.py`.

Two helpers:

- `status_choices(current)` — restricts to current + valid successors per `TEST_SPEC_STATUS_TRANSITIONS`. Returns full three-value set when `current` is `None` or unknown.
- `run_outcome_choices(current)` — returns full four-value set always (no transition restrictions). Stable sort: `["failing", "not_run", "passing", "skipped"]`.

Field schema (parent-prefixed keys, mirroring `_CONTENT_FIELDS` in `_entity_schema.py`):

```python
_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(key="test_spec_name", label="Name", widget="line", required=True),
    FieldSchema(key="test_spec_description", label="Description", widget="text",
                required=True, placeholder="What does this test verify?"),
    FieldSchema(key="test_spec_setup", label="Setup", widget="text",
                placeholder="Preconditions — what must be true before the test runs?"),
    FieldSchema(key="test_spec_steps", label="Steps", widget="text", required=True,
                placeholder="Numbered steps to execute the test"),
    FieldSchema(key="test_spec_expected", label="Expected results", widget="text",
                required=True,
                placeholder="Expected results — what must be true after the steps execute?"),
    FieldSchema(key="test_spec_notes", label="Internal notes", widget="text"),
    FieldSchema(key="test_spec_status", label="Status", widget="combo",
                required=True, vocab=TEST_SPEC_STATUSES, default="candidate",
                compute_options=lambda s: status_choices(s.get("test_spec_status"))),
    FieldSchema(key="test_spec_last_run_outcome", label="Last run outcome",
                widget="combo", required=True, vocab=TEST_SPEC_RUN_OUTCOMES,
                default="not_run",
                compute_options=lambda s: run_outcome_choices(
                    s.get("test_spec_last_run_outcome"))),
    FieldSchema(key="test_spec_last_run_at", label="Last run at",
                widget="datetime",  # fall back to "line" if base lacks datetime
                placeholder="Auto-set to now when outcome moves to a run state"),
    FieldSchema(key="test_spec_last_run_notes", label="Last run notes", widget="text"),
]
```

`entity_fields(*, include_identifier)` factory mirrors `_entity_schema.py`'s pattern. If the `crud_dialog` base lacks `widget="datetime"`, fall back to `widget="line"` with an ISO-8601 placeholder and document the deferral.

**12b. `test_spec_crud.py`** — three subclasses mirroring `entity_crud.py`:

- `TestSpecCreateDialog(EntityCrudDialog)` — `entity_fields(include_identifier=False)`, `create_method=client.create_test_spec`, `identifier_field="test_spec_identifier"`.
- `TestSpecEditDialog(EntityCrudDialog)` — `entity_fields(include_identifier=True)`, `update_method=client.patch_test_spec`, `record=record`.
- `TestSpecDeleteDialog(EntityCrudDeleteDialog)` — edge-text confirmation against `TST-NNN`; body text notes that outgoing references persist (§3.4.6).

**12c. Record-run sub-dialog** — `TestSpecRecordRunDialog(QDialog)` in `test_spec_crud.py`:

- Fields: Outcome (combo, four values, defaults to current outcome); Notes (multiline); At (datetime picker, optional, placeholder "Leave blank to use now").
- On accept: `client.record_test_spec_run(identifier, body={...})`; close.
- Per project memory `project_qt_worker_widget_gc_hazard.md`: this is a transient modal sub-dialog opened from `TestSpecsPanel`, so call `deleteLater()` in the cleanup path.

The panel's Record-run button handler exec's this dialog and `refresh`es on accept.

### Step 13 — Tests (≥20 across three files)

**13a. `tests/crmbuilder_v2/access/test_test_spec.py` (≥12):**

1. `test_create_with_minimum_fields_assigns_identifier` → `TST-001`.
2. `test_create_with_explicit_identifier_then_collision` → second create with same id → 409.
3. `test_create_rejects_malformed_identifier` → `"tst-001"`, `"TST-1"`, `"TS-001"` all 422.
4. `test_create_rejects_duplicate_name_case_insensitive` → `"Mentor app"` vs `"MENTOR APP"`.
5. `test_create_defaults_status_and_outcome` → status `candidate`, outcome `not_run`, last_run_at null.
6. `test_status_transition_valid` → `candidate→confirmed`, `confirmed→deferred`, `deferred→confirmed`.
7. `test_status_transition_invalid_rejected` → `confirmed→candidate` raises `StatusTransitionError`.
8. `test_outcome_transitions_unrestricted` → `not_run→passing→failing→skipped→not_run` all succeed.
9. `test_outcome_to_run_state_auto_sets_last_run_at` → PATCH `last_run_outcome=passing` without `last_run_at`; row's `last_run_at` within 5 s of `now(UTC)`.
10. `test_outcome_to_run_state_with_explicit_last_run_at` → both supplied; explicit value honored.
11. `test_outcome_to_run_state_with_explicit_null_last_run_at_rejected` → PATCH `last_run_outcome=passing, last_run_at=None` → 422.
12. `test_outcome_to_not_run_clears_last_run_fields` → set up passing+at+notes; PATCH `outcome=not_run`; both fields null.
13. `test_record_run_helper_success` → `record_run(s, "TST-001", outcome="passing", notes="ok")`; outcome/at(auto-set)/notes reflect.
14. `test_record_run_helper_resets_to_not_run` → `record_run(..., outcome="not_run", notes="ignored")`; outcome `not_run`, at null, notes null (notes arg ignored).
15. `test_soft_delete_does_not_cascade_outgoing_refs` → create test spec + entity, attach `test_spec_touches_entity`, soft-delete test spec; reference row persists.

**13b. `tests/crmbuilder_v2/api/test_test_specs_api.py` (≥6):**

1. `test_post_minimum_returns_201_with_envelope` → `data.test_spec_identifier == "TST-001"`, `errors is None`.
2. `test_patch_invalid_status_transition_returns_422` → body shape `{"error":"invalid_status_transition","from":"confirmed","to":"candidate"}`.
3. `test_patch_outcome_to_passing_auto_sets_last_run_at` → returned `last_run_at` non-null.
4. `test_patch_outcome_to_not_run_clears_fields` → returned `last_run_at` and `last_run_notes` null.
5. `test_record_run_endpoint_round_trip` → `POST /test-specs/TST-001/record-run` with `{"outcome":"passing","notes":"ok"}`; 200 + envelope.
6. `test_next_identifier_endpoint` → empty table → `{"data":{"next":"TST-001"},...}`.
7. `test_post_references_test_spec_touches_entity_round_trip` → create entity + test spec, POST `/references` with `(test_spec, TST-001, entity, ENT-001, test_spec_touches_entity)` → 201, visible from both ends.

**13c. `tests/crmbuilder_v2/ui/test_test_specs_panel.py` (≥4):**

1. `test_panel_lists_five_columns` → master view exposes the five-column header set.
2. `test_master_pane_color_cue_applied_for_each_outcome` → with four rows, the delegate helper returns the matching color per outcome (call the helper directly rather than rendering pixels).
3. `test_detail_pane_shows_three_subsection_headers` → rendered widget contains labels "Test body", "Last run", and a `CollapsibleSection` titled "Internal notes".
4. `test_record_run_button_opens_dialog_and_refreshes` → click handler invoked → fake accept → `client.record_test_spec_run` called + `refresh` invoked.

### Step 14 — Run tests

```bash
uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -50
```

Expected: baseline + ≥20 new passing. Halt on any previously-passing regression.

### Step 15 — Apply the migration

```bash
cd crmbuilder-v2 && uv run alembic upgrade head && uv run alembic current && cd ..
```

Expected: `00XX_v0_5_create_test_specs_table (head)`. Verify the table:

```bash
uv run python -c "
from crmbuilder_v2.access.db import session_scope
from sqlalchemy import text
with session_scope() as s:
    rows = list(s.execute(text(\"SELECT name FROM sqlite_master WHERE type='table' AND name='test_specs'\")))
    print('test_specs present:', len(rows) == 1)
"
```

### Step 16 — End-to-end verification against the running API

API must be running (`crmbuilder-v2-api &`). All snippets unwrap `.data` per the envelope rule:

```bash
# 1. POST a test spec (omit identifier — server-assigned).
curl -sS -X POST http://127.0.0.1:8765/test-specs -H 'Content-Type: application/json' \
  -d '{"test_spec_name":"smoke","test_spec_description":"smoke","test_spec_steps":"do","test_spec_expected":"works"}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('id:',d['test_spec_identifier'],'status:',d['test_spec_status'],'outcome:',d['test_spec_last_run_outcome'],'at:',d['test_spec_last_run_at'])"
# Expected: id: TST-001 status: candidate outcome: not_run at: None

# 2. PATCH outcome=passing without last_run_at (server auto-sets).
curl -sS -X PATCH http://127.0.0.1:8765/test-specs/TST-001 -H 'Content-Type: application/json' \
  -d '{"test_spec_last_run_outcome":"passing"}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('outcome:',d['test_spec_last_run_outcome'],'at:',d['test_spec_last_run_at'])"
# Expected: outcome: passing at: 2026-... (non-null)

# 3. PATCH outcome back to not_run (server clears at + notes).
curl -sS -X PATCH http://127.0.0.1:8765/test-specs/TST-001 -H 'Content-Type: application/json' \
  -d '{"test_spec_last_run_outcome":"not_run"}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('outcome:',d['test_spec_last_run_outcome'],'at:',d['test_spec_last_run_at'],'notes:',d['test_spec_last_run_notes'])"
# Expected: outcome: not_run at: None notes: None

# 4. Record-run convenience.
curl -sS -X POST http://127.0.0.1:8765/test-specs/TST-001/record-run -H 'Content-Type: application/json' \
  -d '{"outcome":"failing","notes":"step 4 timeout"}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('outcome:',d['test_spec_last_run_outcome'],'notes:',d['test_spec_last_run_notes'])"
# Expected: outcome: failing notes: step 4 timeout

# 5. Status-transition violation (confirm, then attempt back to candidate).
curl -sS -X PATCH http://127.0.0.1:8765/test-specs/TST-001 -H 'Content-Type: application/json' \
  -d '{"test_spec_status":"confirmed"}' > /dev/null
curl -sS -i -X PATCH http://127.0.0.1:8765/test-specs/TST-001 -H 'Content-Type: application/json' \
  -d '{"test_spec_status":"candidate"}' | head -20
# Expected: HTTP/1.1 422 ; body {"error":"invalid_status_transition","from":"confirmed","to":"candidate"}

# 6. Identifier helper.
curl -sS http://127.0.0.1:8765/test-specs/next-identifier \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['next'])"
# Expected: TST-002
```

Halt and report on any divergence.

### Step 17 — Desktop smoke test

`uv run crmbuilder` (or the project's launcher). Expected:

- "Test Specs" appears under Methodology at the chosen position.
- Master pane shows five columns; Last Run cell for `TST-001` shows the red color cue (last set to `failing` in Step 16.4).
- Detail pane shows the three subsection headers; Internal notes collapsed.
- New / Edit / Delete / Record Run buttons present; Edit dialog opens with `test_spec_identifier` read-only.

---

## Close-out

### PI-004 build-closure rule

PI-004 covers four sibling methodology entities (`field`, `requirement`, `manual_config`, `test_spec`). The PI resolves when the **last** sibling lands; intermediate sessions only address it. **Determine which kind of close-out this session is doing at close-out time, not at build start** — parallel-sandbox work may shift the picture during the build.

**Pre-close-out PI-004 status query** (envelope-aware, unwrap `.data`):

```bash
# Has anyone resolved PI-004 already?
curl -sS 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=resolves' \
  | python3 -c "import sys,json;d=json.load(sys.stdin).get('data') or [];print('Resolving refs on PI-004:',len(d));[print(' ',r['reference_identifier'],r['source_type'],r['source_id']) for r in d]"

# Which sessions have addressed it, and which sibling does each represent?
curl -sS 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=addresses' \
  | python3 -c "import sys,json;d=json.load(sys.stdin).get('data') or [];print('Addressing refs on PI-004:',len(d));[print(' ',r['reference_identifier'],r['source_type'],r['source_id']) for r in d]"

# For each addressing session id, fetch its name to identify which sibling.
# (Substitute SES-XXX values from the query above.)
# for ses in SES-XXX SES-YYY ; do
#   curl -sS "http://127.0.0.1:8765/sessions/${ses}" \
#     | python3 -c "import sys,json;d=json.load(sys.stdin).get('data') or {};print(d.get('identifier'),'-',d.get('name'))"
# done
```

**Decision tree:**

- If resolving-refs count ≥ 1 → PI-004 already resolved by a prior session. This session uses `addresses_planning_items` only.
- Else, examine the addressing-session names for the sibling keywords (`field`, `requirement`, `manual_config`). If the addressing sessions cover all three OTHER siblings (FLD + REQ + MCF) → **this session is the closer.** Set `resolves_planning_items: [{"planning_item_identifier": "PI-004"}]`.
- Else (some siblings not yet addressed) → this session is intermediate. Set `addresses_planning_items: [{"planning_item_identifier": "PI-004"}]`, `resolves_planning_items: []`.
- When in doubt, prefer `addresses` over `resolves`. A subsequent small close-out can author the missing `resolves` edge; an erroneous `resolves` is harder to retract because PI-030 slice A auto-flips PI status atomically.

### Standard triple-artifact close-out (per CLAUDE.md "v2 session lifecycle — closing a session")

1. **Content deliverable:** the two build commits below.
2. **Close-out payload** at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` — v0.8 nine-section shape: `session`, `conversation`, `work_tickets`, `planning_items`, `commits`, `decisions`, `references`, `resolves_planning_items`, `addresses_planning_items`. Pick the next SES-NNN via `list_recent_sessions(limit=3)` (parallel-sandbox identifier-collision contingency).
3. **Apply prompt** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md` — pre-flight checks, the apply command, envelope-aware post-apply verification (canonical post-fix example: `apply-close-out-ses-025.md`, commit `ab167c4`).

**Decisions to author (numbered TBD at payload generation):**

1. `test_spec` identifier prefix `TST` (soft-3-letter per DEC-044).
2. Field inventory + dual-axis state (12 substantive + 3 timestamps; three plain-text body fields; cross-field invariant on `last_run_at` per §3.4.4).
3. `POST /test-specs/{id}/record-run` convenience endpoint shipped at first release (resolves §3.8.1 open question — clearer intent for automation, aligns with methodology-vs-execution principle).
4. Master-pane color-cued Last Run column shipped as a one-off UI deviation justified by verification-health-at-a-glance (§3.6.2).

### Commits

**Commit 1 — Migration, access layer, REST:**

```bash
git add crmbuilder-v2/migrations/versions/00XX_v0_5_create_test_specs_table.py
git add crmbuilder-v2/src/crmbuilder_v2/access/vocab.py
git add crmbuilder-v2/src/crmbuilder_v2/access/models.py
git add crmbuilder-v2/src/crmbuilder_v2/access/repositories/test_spec.py
git add crmbuilder-v2/src/crmbuilder_v2/api/schemas.py
git add crmbuilder-v2/src/crmbuilder_v2/api/routers/test_specs.py
git add crmbuilder-v2/src/crmbuilder_v2/api/main.py
git add tests/crmbuilder_v2/access/test_test_spec.py
git add tests/crmbuilder_v2/api/test_test_specs_api.py

git commit -m "$(cat <<'EOF'
v2: PI-004 — test_spec methodology entity (migration + access + REST)

Lands test_spec.md v1.0:
- Migration 00XX: test_specs table (15 columns); refs CHECK extended
  for 'test_spec' source/target and three new outbound kinds
  (test_spec_touches_entity, test_spec_touches_field,
  test_spec_exercises_process); change_log CHECK extended.
- vocab: TEST_SPEC_STATUSES + transitions (mirror entity/domain),
  TEST_SPEC_RUN_OUTCOMES (unrestricted transitions — explicit, no
  transitions dict), three new _kinds_for_pair clauses.
- Access: dual-axis status validation; cross-field invariant on
  outcome / last_run_at per §3.4.4 (server auto-sets when moving to
  run state, auto-clears on move to not_run); record_run convenience.
- REST: eight standard endpoints + POST /test-specs/{id}/record-run.
  {data, meta, errors} envelope throughout.
EOF
)"

git pull --rebase origin main
```

Wait for Doug's push approval.

**Commit 2 — UI panel, dialogs, sidebar:**

```bash
git add crmbuilder-v2/src/crmbuilder_v2/ui/client.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/panels/test_spec.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_test_spec_schema.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/test_spec_crud.py
git add tests/crmbuilder_v2/ui/test_test_specs_panel.py

git commit -m "$(cat <<'EOF'
v2: PI-004 — test_spec UI panel + dialogs + sidebar wiring

Per test_spec.md §3.6:
- Sidebar: "Test Specs" in Methodology group.
- Panel: five-column master pane with color-cued Last Run column
  (passing green, failing red, not_run gray, skipped amber per §3.6.2
  deviation). Three-section detail pane (identity-and-methodology /
  test body / last run / collapsible internal notes / references).
- Dialogs: TestSpec{Create,Edit,Delete}Dialog + TestSpecRecordRunDialog.
- UI client: nine methods including record_test_spec_run.
EOF
)"

git pull --rebase origin main
```

Wait for Doug's push approval.

**Commit 3 — Close-out artifacts** (after both build commits pushed):

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json
cd ..

git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json
git add PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md
git add PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log
git add PRDs/product/crmbuilder-v2/db-export/

git commit -m "$(cat <<'EOF'
v2: SES-NNN — test_spec build close-out (PI-004 sibling)

Close-out payload + apply prompt + deposit-event log + regenerated
db-export snapshots for the test_spec build conversation.
{addresses|resolves}_planning_items per the PI-004 build-closure rule
(set at close-out time based on sibling addressing-edge count).
EOF
)"

git pull --rebase origin main
```

Wait for Doug's push approval.

---

## Done

Reply with:

- Pre-build Alembic head and post-migration head
- `test_specs` table present in engagement DB: True / False
- Test suite: baseline pass count vs post-slice pass count (+≥20 expected)
- End-to-end verification (Step 16, all six checks): pass / fail
- Desktop smoke test (Step 17, all four expectations): pass / fail
- PI-004 closure decision: `resolves` or `addresses`, with the sibling-addressing count that drove it
- Commit SHAs (three: build × 2 + close-out × 1)
- Decisions authored: DEC-NNN through DEC-NNN (post-payload renumber)
- Session identifier: SES-NNN
- Sidebar position chosen for "Test Specs" (`<after-which-sibling-or-CRM-Candidates>`)
- Convenience endpoint shipped: `POST /test-specs/{id}/record-run` — Yes (per spec §3.8.1 recommendation)
- Next prompt to run: whichever PI-004 sibling has not yet built (`field`, `requirement`, `manual_config`), or — if this session was the closer — none; PI-004 is resolved.
