# CLAUDE-CODE-PROMPT-build-process-v2

**Last Updated:** 05-25-26
**Operating mode:** DETAIL
**Series:** PI-005 (process entity v2 schema growth)
**Slice:** single-prompt build (column growth + vocab kinds + UI extensions + tests in one execution)
**Status:** Ready to execute. Recommended ordering: after persona (PI-003) and field (PI-004 — field portion) land. Safe to execute earlier — the migration extends the `refs.relationship_kind` CHECK unconditionally; the `_kinds_for_pair` clauses for `(process, persona)` and `(process, field)` are no-ops until those source/target types land in `ENTITY_TYPES`, so the prompt does not need to gate on them.

**Companions:**
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/process-v2.md` v2.0 — authoritative growth spec.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` v1.0 — v0.4 predecessor (preserved verbatim by this build).
- `crmbuilder-v2/migrations/versions/0009_v0_4_create_processes_table.py` — the table being grown.
- `crmbuilder-v2/migrations/versions/0011_v0_7_governance_entities.py` — closest CHECK-extension pattern (`batch_alter_table` recopy with `drop_constraint` + `create_check_constraint`).
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — vocab registration site.
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/process.py` — repository to extend.
- `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` — schemas to extend (lines 233–279).
- `crmbuilder-v2/src/crmbuilder_v2/api/routers/processes.py` — router (no body changes; verify pass-through).
- `crmbuilder-v2/src/crmbuilder_v2/ui/panels/processes.py` — panel detail pane to extend.
- `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/process_crud.py` and `_process_schema.py` — Edit dialog to extend; Create dialog left alone for the new fields per spec §3.6.4.

**Hard dependency note.** Recommended sequence: build `persona` (PI-003) and `field` (PI-004 — field portion) BEFORE running this prompt, so the new `process_performed_by_persona` and `process_touches_field` edges are exercisable end-to-end. This build prompt is safe to run earlier — the migration extends the `refs.relationship_kind` CHECK constraint without breaking anything — but the new relationship kinds cannot have real targets until the `persona` and `field` tables exist. The pre-flight detects whether they exist; the reference-roundtrip tests skip with a clear marker rather than failing when either table is absent. If `personas` lands later, re-run the relevant test target to exercise the round-trip.

---

## Purpose

Land the v2 schema-growth of the existing `process` methodology entity per `process-v2.md` v2.0, satisfying **PI-005**. Six additive plain-TEXT content columns plus three new references-vocabulary kinds, with detail-pane and Edit-dialog UI surfaces for the new content. No new entity type, no new table, no data backfill, no behavioral change to v0.4 fields or to the four-value `process_classification` lifecycle. Every existing v0.4 record continues to validate as a legal v2 record with NULL values in the six new columns.

After this prompt lands:

- The `processes` table carries six new TEXT NULL columns: `process_steps`, `process_triggers`, `process_outcomes`, `process_edge_cases`, `process_frequency`, `process_duration_estimate` (spec §3.2.2).
- `REFERENCE_RELATIONSHIPS` admits three new kinds: `process_performed_by_persona`, `process_touches_field`, `process_touches_entity` (spec §3.3.2).
- `_kinds_for_pair` returns the new kinds for `(process, persona)`, `(process, field)`, `(process, entity)` (spec §3.3.2). The `(process, entity)` clause activates immediately (entity is in ENTITY_TYPES as of v0.4); the `(process, persona)` and `(process, field)` clauses activate the moment persona/field land.
- `refs.relationship_kind` CHECK admits the three new kinds.
- The `Process` model carries six new `Mapped[str | None]` columns.
- The eight existing `/processes/*` REST endpoints round-trip the new fields via the schema additions; no new endpoints.
- The Processes detail pane in the desktop UI renders the six new fields in a collapsible Phase-3-sections group below the existing Classification rationale field, above Internal notes (spec §3.6.3).
- The Edit dialog includes editors for the six new fields (Create dialog does not — spec §3.6.4 defers new-field authoring to post-create).
- Existing v0.4 records survive intact with NULL values; PI-005 atomically resolves on close-out.

This prompt does NOT introduce:

- New REST endpoints. The existing 8 endpoints carry through.
- New top-level Mermaid/architecture diagrams.
- A `process_definition_level` lifecycle field (spec §3.4 explicitly defers).
- Structured JSON shapes for the six new fields (spec §3.2.2 explicitly defers to v0.7+).
- A persona or field entity (their dependency is conditional and handled by PI-003 and PI-004).
- A master-pane Domain column (spec §3.6.2 explicitly defers to v0.7+).

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts.

5. **Read the companion documents:**

   - `CLAUDE.md` (root) — review the "Reference relationship vocabulary lives in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`" note and the "Adding a new relationship kind requires updating both" rule. This prompt registers three.
   - `PRDs/product/crmbuilder-v2/methodology-schema-specs/process-v2.md` end-to-end — §3.2 (new field inventory), §3.3.2 (three new vocab kinds + mechanism rationale), §3.6.3 (detail-pane Phase-3-sections group), §3.6.4 (Create dialog omits new fields), §3.7 (12 acceptance criteria), §4.1–§4.5 (migration story).
   - `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` v1.0 — confirm what is preserved verbatim (§3.1 identity, §3.2.1 + §3.2.3 + §3.2.4 + §3.2.5 fields, §3.3.1 outgoing relationships, §3.4 lifecycle, §3.5.1 endpoint set, §3.6.2 master pane).
   - `crmbuilder-v2/migrations/versions/0011_v0_7_governance_entities.py` — the closest pattern. The current migration extends `refs.source_type`, `refs.target_type`, `refs.relationship_kind` CHECK constraints in one `batch_alter_table` recopy. The new migration extends `refs.relationship_kind` again (the source/target type sets already admit `process`, `persona`, `field`, `entity`).
   - `crmbuilder-v2/migrations/versions/0012_v0_8_commits_and_blocked_by_rename.py` — the current head; this prompt's new migration revises onto it (or onto whatever is head at execution time — verify via `alembic current`).

6. **Verify the v2 codebase is in place.** Confirm these files exist:

   ```bash
   ls -la crmbuilder-v2/src/crmbuilder_v2/access/vocab.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/access/models.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/access/repositories/process.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/api/routers/processes.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/api/schemas.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/ui/panels/processes.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/process_crud.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_process_schema.py
   ls -la crmbuilder-v2/migrations/versions/
   ls -la tests/crmbuilder_v2/access/test_process.py
   ls -la tests/crmbuilder_v2/api/test_processes_api.py
   ```

7. **Check whether the `personas` and `fields` tables already exist** (informational; this prompt is safe to run either way):

   ```bash
   uv run python - <<'PY'
   from sqlalchemy import inspect
   from crmbuilder_v2.access.db import engine
   insp = inspect(engine())
   tables = set(insp.get_table_names())
   for t in ("personas", "fields", "entities"):
       present = t in tables
       print(f"{t}: {'present' if present else 'MISSING'}")
   PY
   ```

   - `entities` must be present (it lands in v0.4 slice C; this prompt assumes that baseline).
   - `personas` and `fields` may or may not be present. If absent, log a warning that the reference-roundtrip tests for `process_performed_by_persona` and `process_touches_field` will skip with a guard marker — but do **not** abort. The migration and vocab additions are correct regardless.

8. **Confirm sparse-checkout includes the v2 source and migrations.** `git sparse-checkout list` should include `crmbuilder-v2/` and `PRDs/` and `tests/`. Stop and report if restricting visibility.

9. **Confirm the test suite is currently green.** Baseline before any changes:

   ```bash
   uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -30
   ```

   Note the pass count for comparison after the build lands.

10. **Capture pre-build Alembic head:**

    ```bash
    cd crmbuilder-v2
    uv run alembic current 2>&1
    cd ..
    ```

    Expected: `0012_v0_8_commits_and_blocked_by_rename (head)` (or whatever the current head is — record it; the new migration uses that as `down_revision`).

11. **Capture the first existing process record's identifier.** The "v0.4 records survive intact" verification requires a real record to GET against:

    ```bash
    curl -sS 'http://127.0.0.1:8765/processes' \
      | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(f'process count: {len(d)}'); print(f'first identifier: {d[0][\"process_identifier\"]}' if d else 'no processes yet')"
    ```

    If there are zero processes, the post-apply v0.4-record verification will create a throwaway v0.4-shape record (POST with only the four required v0.4 fields) and verify the new columns return as `null`.

12. **Capture the current planning_item status of PI-005:**

    ```bash
    curl -sS 'http://127.0.0.1:8765/planning-items/PI-005' \
      | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(f'PI-005 status: {d.get(\"status\")}'); print(f'PI-005 title: {d.get(\"title\")}')"
    ```

    Expected: `status: Open`. The close-out at the end of this prompt flips it to `Resolved` atomically via the `resolves_planning_items` section.

---

## Implementation

### Step 1 — Author the new Alembic migration

Create `crmbuilder-v2/migrations/versions/0013_v0_8_process_v2_growth.py` modeled on the `batch_alter_table` recopy pattern from `0011_v0_7_governance_entities.py` and the column-add idioms from `0009_v0_4_create_processes_table.py`. Header docstring should cite `process-v2.md` §3.2 and §3.3.2, name the satisfying planning item (PI-005), and document the reversibility posture.

Revision wires:

```python
revision: str = "0013_v0_8_process_v2_growth"
down_revision: Union[str, None] = "0012_v0_8_commits_and_blocked_by_rename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

(If pre-flight step 10 shows a head other than `0012_v0_8_commits_and_blocked_by_rename`, use the actual head as `down_revision`.)

**Module-level CHECK-constraint string constants** following the `0011` convention. Use sorted alphabetical order in the IN-list so future diffs are easy to read:

```python
# refs.relationship_kind CHECK — v0.8 process v2 additions per process-v2.md §3.3.2.
# Adds 'process_performed_by_persona', 'process_touches_field', 'process_touches_entity'.
# Carries forward every kind admitted by the prior head (the v0.8 commits/blocked_by
# rename). Re-stating the full set here matches the 0011 / 0012 pattern — the migration
# is a complete CHECK replacement, not an additive ALTER.
_NEW_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', 'is_about', "
    "'process_hands_off_to_process', 'process_performed_by_persona', "
    "'process_touches_entity', 'process_touches_field', 'references', "
    "'resolves', 'supersedes', 'workstream_planned_in_reference_book')"
)

# Prior CHECK (from 0012). Used by downgrade().
_OLD_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', 'is_about', "
    "'process_hands_off_to_process', 'references', 'resolves', 'supersedes', "
    "'workstream_planned_in_reference_book')"
)
```

**Inspect the actual head's CHECK before authoring the constants.** The v0.8 commit-lifecycle migration (`0012`) modified the `refs.relationship_kind` CHECK — open `0012_v0_8_commits_and_blocked_by_rename.py` and copy the FINAL CHECK expression verbatim as the new migration's `_OLD_REF_RELATIONSHIP_CHECK`, then add `'process_performed_by_persona'`, `'process_touches_field'`, `'process_touches_entity'` (sorted) to produce `_NEW_REF_RELATIONSHIP_CHECK`. The exact set of admitted kinds at the head moment is what matters; if the constants above and the head's actual CHECK diverge, the head's CHECK wins.

**Confirm the existing CHECK-constraint name.** Per `0011`, the CHECK constraint is named `ck_ref_relationship` (line 127 of `0011`). Use the same name in the `drop_constraint` / `create_check_constraint` calls.

**The `upgrade()` function:**

```python
def upgrade() -> None:
    # 1. Add the six new TEXT NULL columns to the processes table.
    #    Plain TEXT, no DEFAULT, no length cap, no CHECK constraints —
    #    the columns are Phase 3 content per process-v2.md §3.2.2 and
    #    deliberately unconstrained at the storage layer.
    with op.batch_alter_table("processes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("process_steps", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("process_triggers", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("process_outcomes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("process_edge_cases", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("process_frequency", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("process_duration_estimate", sa.Text(), nullable=True)
        )

    # 2. Extend refs.relationship_kind CHECK to admit the three new kinds.
    #    refs.source_type and refs.target_type already admit process,
    #    persona, field, entity from prior migrations (the v0.7 governance
    #    work extended source/target sets aggressively; v0.4 already had
    #    process and entity). No source/target CHECK change needed here.
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _NEW_REF_RELATIONSHIP_CHECK
        )
```

**Important — verify whether `refs.source_type` / `refs.target_type` CHECKs admit `'persona'` and `'field'`.** Inspect the current head's constants. If `'persona'` and/or `'field'` are NOT in the admitted set, extend those CHECKs as well in the same `batch_alter_table` block. (Both are likely already added by PI-003 and PI-004 — that's the recommended sequencing. If they have not yet landed, this migration extends `refs.relationship_kind` only and adds a code comment noting that the source/target CHECKs need to be extended when PI-003 / PI-004 ship. Adding `process_performed_by_persona` to `relationship_kind` is safe even before `persona` is an admitted source/target type — the CHECK just admits the kind value; no row can use it yet because the access layer's pair validation rejects it.)

**The `downgrade()` function** reverses the operations:

```python
def downgrade() -> None:
    # 1. Reverse the refs.relationship_kind CHECK extension. Any rows
    #    that hold one of the three new kinds must be deleted first, or
    #    the CHECK rebuild fails on the recopy. The downgrade is a
    #    recovery operation, not a routine reversal; rows lost here are
    #    documented behavior, not a regression.
    bind = op.get_bind()
    bind.execute(sa.text(
        "DELETE FROM refs WHERE relationship_kind IN "
        "('process_performed_by_persona', 'process_touches_field', "
        "'process_touches_entity')"
    ))
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _OLD_REF_RELATIONSHIP_CHECK
        )

    # 2. Drop the six new columns from the processes table. The columns
    #    are TEXT NULL with no FKs and no indexes — drop is straight.
    with op.batch_alter_table("processes", schema=None) as batch_op:
        batch_op.drop_column("process_duration_estimate")
        batch_op.drop_column("process_frequency")
        batch_op.drop_column("process_edge_cases")
        batch_op.drop_column("process_outcomes")
        batch_op.drop_column("process_triggers")
        batch_op.drop_column("process_steps")
```

The drop order is the reverse of the add order. The `batch_alter_table` recopies the table, so individual column drops are atomic within the recopy regardless of order, but matching reverse-of-add reads cleanest.

### Step 2 — Extend the `Process` ORM model

Edit `crmbuilder-v2/src/crmbuilder_v2/access/models.py`. Locate `class Process(Base)` (around line 355) and add six new `Mapped[str | None]` columns after `process_notes` (around line 388) and before the timestamp columns:

```python
# Phase 3 content fields (v0.8, PI-005, process-v2.md §3.2.2). All
# six are plain TEXT, nullable, default NULL; existing v0.4 records
# acquire NULL on migration. No CHECK constraints — the methodology
# defers structured representations to v0.7+ per spec §3.2.2.
process_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
process_triggers: Mapped[str | None] = mapped_column(Text, nullable=True)
process_outcomes: Mapped[str | None] = mapped_column(Text, nullable=True)
process_edge_cases: Mapped[str | None] = mapped_column(Text, nullable=True)
process_frequency: Mapped[str | None] = mapped_column(Text, nullable=True)
process_duration_estimate: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Update the class docstring's "Two structural deviations…" paragraph with a sentence noting that as of v0.8 the schema also carries the six Phase 3 content fields per `process-v2.md` §3.2.2.

Do NOT add any new entries to `__table_args__` — the six new columns have no CHECK constraints, no indexes, and no other table-level metadata.

### Step 3 — Extend `vocab.py`

Edit `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`. Two surgical edits:

**3a. Add the three new kinds to `REFERENCE_RELATIONSHIPS`.** Insert in the existing frozenset literal (around lines 211–246). Add a section comment block above the additions naming PI-005 and `process-v2.md` §3.3.2:

```python
# v0.8 process v2 schema growth (PI-005, process-v2.md §3.3.2). Three
# new outgoing kinds from process to other methodology entity types:
#   - 'process_performed_by_persona' (process → persona; conditional
#     on PI-003 having added 'persona' to ENTITY_TYPES).
#   - 'process_touches_field' (process → field; conditional on PI-004
#     having added 'field' to ENTITY_TYPES).
#   - 'process_touches_entity' (process → entity; entity already in
#     ENTITY_TYPES since v0.4 — this promotes the kind from
#     process.md §3.3.2's v0.5+ anticipation to live registration).
"process_performed_by_persona",
"process_touches_field",
"process_touches_entity",
```

**3b. Extend `_kinds_for_pair` with three new clauses.** Insert in the existing function (around lines 292–375), placed after the v0.8 Code Change Lifecycle additions block (around lines 367–374). Update the function docstring's semantic-rules bullet list with three new entries naming the new kinds. The clauses themselves:

```python
# v0.8 process v2 schema growth additions (PI-005, process-v2.md §3.3.2).
# Three new outgoing kinds from process. All three clauses ship now so
# the vocabulary is forward-aware; the (process, persona) and
# (process, field) clauses are no-ops until PI-003 and PI-004 add
# 'persona' and 'field' to ENTITY_TYPES (the references repository's
# pair validation requires both source and target types to be in
# ENTITY_TYPES, so the clauses don't emit invalid kinds — they just
# don't activate until the targets exist).
if source_type == "process" and target_type == "persona":
    kinds.add("process_performed_by_persona")
if source_type == "process" and target_type == "field":
    kinds.add("process_touches_field")
if source_type == "process" and target_type == "entity":
    kinds.add("process_touches_entity")
```

Place the new docstring rules in the existing bullet list (alphabetical or category-grouped — match the existing style):

```text
* ``process_performed_by_persona`` — source must be a process, target
  must be a persona (v0.8, process-v2.md §3.3.2; conditional on PI-003).
* ``process_touches_field`` — source must be a process, target must be
  a field (v0.8, process-v2.md §3.3.2; conditional on PI-004).
* ``process_touches_entity`` — source must be a process, target must
  be an entity (v0.8, process-v2.md §3.3.2; promotes the v0.5+
  anticipation from process.md §3.3.2).
```

Do NOT modify `ENTITY_TYPES` in this prompt. `process` and `entity` are already present; `persona` and `field` are added by PI-003 and PI-004 respectively.

### Step 4 — Extend the process repository

Edit `crmbuilder-v2/src/crmbuilder_v2/access/repositories/process.py`. Three surgical edits:

**4a. Extend `_PATCHABLE_FIELDS`** (around lines 79–88) with the six new field names:

```python
_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "domain_identifier",
        "purpose",
        "classification",
        "classification_rationale",
        "notes",
        # v0.8 process v2 schema growth (PI-005, process-v2.md §3.2.2).
        "steps",
        "triggers",
        "outcomes",
        "edge_cases",
        "frequency",
        "duration_estimate",
    }
)
```

**4b. Extend `_new_process_row`, `_insert_with_autoassign`, and `create_process`** to accept and persist the six new fields. All six are optional (`str | None = None`), default `None` (which stores NULL). No validation logic — they are unconstrained TEXT per spec §3.2.2. Apply each new value via `setattr(row, f"process_{field}", value)` after the existing fields are set, or — preferable — pass them positionally / by keyword through the helper chain. Pseudocode for `_new_process_row`:

```python
def _new_process_row(
    identifier: str,
    name: str,
    domain_identifier: str,
    purpose: str,
    classification: str,
    classification_rationale: str | None,
    notes: str | None,
    *,
    steps: str | None = None,
    triggers: str | None = None,
    outcomes: str | None = None,
    edge_cases: str | None = None,
    frequency: str | None = None,
    duration_estimate: str | None = None,
) -> Process:
    return Process(
        process_identifier=identifier,
        process_name=name,
        process_domain_identifier=domain_identifier,
        process_purpose=purpose,
        process_classification=classification,
        process_classification_rationale=classification_rationale,
        process_notes=notes,
        process_steps=steps,
        process_triggers=triggers,
        process_outcomes=outcomes,
        process_edge_cases=edge_cases,
        process_frequency=frequency,
        process_duration_estimate=duration_estimate,
    )
```

Mirror the keyword additions through `_insert_with_autoassign` and `create_process`. The new keyword arguments are placed after the existing positional args, all keyword-only (`*,`), all defaulting to `None`.

**4c. Extend `update_process` (PUT — full replace) and `patch_process` (PATCH — partial).**

For `update_process`: add the six new keyword args (all `str | None = None`, all keyword-only). Full-replace semantics: an omitted-from-body new field is set to `None` (clears it) per spec §3.5.2. Apply with `row.process_steps = steps` etc. after the existing field assignments. Update the docstring with a sentence noting the v2 fields are replaced wholesale per PUT semantics.

For `patch_process`: the existing `**fields` dispatch already handles this. The `_PATCHABLE_FIELDS` extension in 4a above is sufficient — add a per-field `if "steps" in fields: row.process_steps = fields["steps"]` block for each of the six. Update the docstring's "Recognised keys" list with the six new entries. PATCH-to-`None` clears the field; PATCH-to-`""` stores empty string; PATCH-to-non-empty stores the value (spec §3.5.2).

No validation logic. The six fields are unconstrained TEXT. No `_require_nonempty` calls.

### Step 5 — Extend the API schemas

Edit `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py`. Three surgical edits to the three Process Pydantic models (lines 233–279):

**5a. `ProcessCreateIn`** — add six optional fields at the bottom (before `process_identifier`):

```python
process_steps: str | None = None
process_triggers: str | None = None
process_outcomes: str | None = None
process_edge_cases: str | None = None
process_frequency: str | None = None
process_duration_estimate: str | None = None
```

Update the docstring with a paragraph noting that the six Phase 3 content fields are optional at create time per spec §3.6.4 (the UI Create dialog omits them; the API accepts them).

**5b. `ProcessReplaceIn`** — add the same six fields at the bottom (after `process_notes`):

```python
process_steps: str | None = None
process_triggers: str | None = None
process_outcomes: str | None = None
process_edge_cases: str | None = None
process_frequency: str | None = None
process_duration_estimate: str | None = None
```

Update the docstring with a sentence noting PUT semantics for the new fields (omitting them from the body clears them per spec §3.5.2).

**5c. `ProcessPatchIn`** — add the same six fields:

```python
process_steps: str | None = None
process_triggers: str | None = None
process_outcomes: str | None = None
process_edge_cases: str | None = None
process_frequency: str | None = None
process_duration_estimate: str | None = None
```

Update the docstring with the PATCH semantics for the new fields per spec §3.5.2 (explicit `null` clears, omission leaves unchanged, empty string stores empty string).

### Step 6 — Update the API router pass-through

Edit `crmbuilder-v2/src/crmbuilder_v2/api/routers/processes.py`. Two surgical edits in the `create` and `replace` handlers — pass the six new fields through to the repository calls.

**6a. `create`** (lines 72–86) — pass the new fields through:

```python
return ok(
    process.create_process(
        s,
        name=body.process_name,
        domain_identifier=body.process_domain_identifier,
        purpose=body.process_purpose,
        classification=body.process_classification,
        classification_rationale=body.process_classification_rationale,
        notes=body.process_notes,
        identifier=body.process_identifier,
        steps=body.process_steps,
        triggers=body.process_triggers,
        outcomes=body.process_outcomes,
        edge_cases=body.process_edge_cases,
        frequency=body.process_frequency,
        duration_estimate=body.process_duration_estimate,
    )
)
```

**6b. `replace`** (lines 89–104) — pass the new fields through identically. The PATCH handler (lines 107–116) needs NO change — its body-to-fields mapping already strips the `process_` prefix from any provided key, and the `_PATCHABLE_FIELDS` set in the repository (extended in step 4a) admits the new field names.

No new endpoint added. The eight existing endpoints from `process.md` §3.5.1 carry through verbatim.

### Step 7 — Update the UI client

Inspect `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` for the `create_process`, `update_process`, and `patch_process` methods (or their equivalent — function names follow the v0.4 pattern). The desktop client wraps the REST calls; the new fields need to round-trip through it.

If the client methods take a typed kwargs envelope (Pydantic / dataclass), extend it with the six new fields. If they take `**kwargs` and pass through to the JSON body verbatim, no change is needed — verify by reading the relevant client method and confirming the body is constructed via `dict(...)`/`json.dumps(...)` without enumerated fields.

Mirror the same pattern used by domain/entity panels for their content fields. The change is minimal — the client is a thin wrapper.

### Step 8 — No sidebar / main-window change

The sidebar position (Methodology #3) and the main-window registration are unchanged per spec §3.6.1 and §3.6.2. No edits to `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` or the sidebar configuration.

### Step 9 — Extend the Processes detail pane

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/panels/processes.py`. The detail pane lives in `render_detail` (lines 193–383). Add six new `CollapsibleSection` widgets between the classification-rationale row (line 348) and the notes section (line 360), implementing the spec §3.6.3 Phase-3-sections group.

**9a. Add a group header label** above the six sub-sections:

```python
outer.addWidget(_separator())

phase3_header = QLabel("Phase 3 — Detailed Process Definition")
phase3_header.setObjectName("phase3_sections_header")
phase3_font = QFont(phase3_header.font())
phase3_font.setBold(True)
phase3_header.setFont(phase3_font)
outer.addWidget(phase3_header)
```

**9b. Add the six collapsible sub-sections.** Each sub-section binds to one of the six new fields. Default collapse state: collapsed if the field is NULL or empty (after `strip()`); expanded if it has non-whitespace content. The body widget is a read-only `QPlainTextEdit` rendered via `_read_only_text(value)` (the existing helper).

```python
_PHASE3_SECTION_SPECS: list[tuple[str, str, str]] = [
    # (field_key, label, placeholder)
    (
        "process_steps",
        "Steps",
        "Numbered or bulleted list of process steps in execution order",
    ),
    (
        "process_triggers",
        "Triggers",
        "What initiates this process",
    ),
    (
        "process_outcomes",
        "Outcomes",
        "What success looks like — state changes, records created, "
        "communications sent",
    ),
    (
        "process_edge_cases",
        "Edge Cases",
        "Known exceptions, error paths, retry semantics",
    ),
    (
        "process_frequency",
        "Frequency",
        "How often this process runs",
    ),
    (
        "process_duration_estimate",
        "Duration",
        "Typical wall-clock duration",
    ),
]

for field_key, label, placeholder in _PHASE3_SECTION_SPECS:
    value = record.get(field_key) or ""
    body = _read_only_text(value, placeholder=placeholder)
    body.setObjectName(f"{field_key}_value")
    section = CollapsibleSection(
        label, body, expanded=bool(value.strip())
    )
    section.setObjectName(f"{field_key}_section")
    outer.addWidget(section)
```

The constant `_PHASE3_SECTION_SPECS` lives at module scope (above `class ProcessesPanel`) so both the panel and the dialog can import it if they share specs. Per spec §3.6.3 the section header is always visible (even when the underlying column is NULL/empty); the body is hidden by collapse-state, not removed from the widget tree.

**Optional bundling refactor (spec §3.6.3 recommendation).** Instead of inlining the six sub-sections in `render_detail`, factor them into a `ProcessExecutionContextSection` composite widget. This is recommended but not required by the spec — implement only if it does not bloat the prompt's scope materially. If skipped, the inline form above is correct.

### Step 10 — Extend the Edit dialog (Create dialog left alone)

Per spec §3.6.4 the Create dialog omits the six new fields (Phase 3 content is post-create work). Only the Edit dialog grows.

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_process_schema.py`. The `_content_fields` function (lines 114–155) returns the field schema both dialogs consume. The cleanest extension keeps the v0.4 schema intact and adds the new fields conditionally:

**10a.** Add a new private function `_phase3_fields()` returning the six new `FieldSchema` entries (label + `widget="text"` multi-line editor, with placeholder strings matching spec §3.6.3):

```python
_PHASE3_FIELDS_SPECS: list[tuple[str, str, str]] = [
    ("process_steps", "Steps",
     "Numbered or bulleted list of process steps in execution order"),
    ("process_triggers", "Triggers",
     "What initiates this process"),
    ("process_outcomes", "Outcomes",
     "What success looks like — state changes, records created, "
     "communications sent"),
    ("process_edge_cases", "Edge Cases",
     "Known exceptions, error paths, retry semantics"),
    ("process_frequency", "Frequency",
     "How often this process runs"),
    ("process_duration_estimate", "Duration",
     "Typical wall-clock duration"),
]


def _phase3_fields() -> list[FieldSchema]:
    """Phase 3 detailed-process fields (v0.8, PI-005, process-v2.md §3.6.4).

    Included in the Edit dialog only; the Create dialog omits these per
    spec §3.6.4 — Phase 3 content is post-create work.
    """
    return [
        FieldSchema(
            key=key,
            label=label,
            widget="text",
            placeholder=placeholder,
        )
        for key, label, placeholder in _PHASE3_FIELDS_SPECS
    ]
```

**10b.** Extend `process_fields()` (lines 158–173) with a new keyword `include_phase3: bool = False`. When True, the function appends `_phase3_fields()` to the returned schema:

```python
def process_fields(
    client: StorageClient,
    *,
    include_identifier: bool,
    include_phase3: bool = False,
) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(_content_fields(client))
    if include_phase3:
        fields.extend(_phase3_fields())
    return fields
```

**10c.** Update `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/process_crud.py`. The `ProcessEditDialog` (line 113) should call `process_fields(client, include_identifier=True, include_phase3=True)`. The `ProcessCreateDialog` (line 89) calls `process_fields(client, include_identifier=False)` — unchanged, preserving the spec §3.6.4 exclusion.

**10d.** Verify the Edit dialog's submit handler passes the six new field values through to `patch_process` (or `update_process` if the dialog uses PUT). The existing dispatch is field-name-driven; the new fields ride along automatically because they share the `process_` prefix the dispatcher already strips.

### Step 11 — Tests

The v2 build adds at least 10 new tests across two files. The two existing test files to extend:

- `tests/crmbuilder_v2/access/test_process.py` — repository-level tests.
- `tests/crmbuilder_v2/api/test_processes_api.py` — REST-level tests.

Place migration-mechanics tests in `tests/crmbuilder_v2/access/test_process.py` (the codebase does not have a separate `migrations/` test directory — verify the existing layout via `find tests/crmbuilder_v2 -name "test_*.py" | head` and mirror that structure).

**Required new test coverage (minimum 10 tests):**

1. **`test_migration_applies_forward_adds_six_columns`** — apply head migration; assert the `processes` table has all six new columns (`process_steps`, `process_triggers`, `process_outcomes`, `process_edge_cases`, `process_frequency`, `process_duration_estimate`), each NULLable, no DEFAULT.

2. **`test_migration_reversible`** — apply head, then downgrade one step; assert the six columns are gone. Re-upgrade; assert they return.

3. **`test_v04_records_survive_intact_with_null_new_columns`** — create a process with only the v0.4-required fields (name, domain_identifier, purpose); GET it; assert all six new fields return as `None`. Spec acceptance criterion 3.

4. **`test_create_with_phase3_fields_persists`** — POST a process with all six new fields populated; GET it; assert each field round-trips with the exact value supplied. Spec acceptance criterion 5.

5. **`test_patch_individual_phase3_fields`** — for each of the six new fields, PATCH only that field on an existing record; assert that field updates, the other five new fields are untouched, all v0.4 fields are untouched. Spec acceptance criterion 4. (One test parametrized across the six fields, or six small tests — either form is fine.)

6. **`test_patch_phase3_field_to_null_clears`** — PATCH `process_steps` to JSON `null` on a record where it had a value; assert subsequent GET returns `None`. Spec §3.5.2.

7. **`test_patch_phase3_field_to_empty_string_preserves_empty`** — PATCH `process_steps` to `""` on a record where it had a value; assert subsequent GET returns `""` (not `None`). Spec §3.5.2 storage-vs-render distinction.

8. **`test_put_omitting_phase3_fields_clears_them`** — PUT a record with the six new fields previously populated, omitting the new fields from the PUT body; assert they are cleared (PUT semantics — full replace). Spec §3.5.2.

9. **`test_vocab_admits_new_kinds`** — import `vocab.py`; assert all three new kinds are in `REFERENCE_RELATIONSHIPS`. Assert `_kinds_for_pair("process", "entity")` includes `process_touches_entity`. Conditional on persona/field landing: assert `_kinds_for_pair("process", "persona")` includes `process_performed_by_persona` and `_kinds_for_pair("process", "field")` includes `process_touches_field` — gate these behind `if "persona" in ENTITY_TYPES:` and `if "field" in ENTITY_TYPES:` so the tests skip cleanly when those entity types are not yet registered.

10. **`test_refs_check_admits_new_kinds`** — direct DB insert into `refs` with `relationship_kind='process_touches_entity'`, source=an existing process, target=an existing entity; assert success. Direct DB insert with `relationship_kind='process_eats_persona'` (an invented kind); assert the CHECK rejects it.

11. **`test_process_touches_entity_roundtrip`** — POST `/references` with `source_type=process, source_id=<existing PROC>, target_type=entity, target_id=<existing ENT>, relationship_kind=process_touches_entity`; assert 201; GET the process; assert the reference renders in `references_section` outbound; GET the entity; assert the reference renders inbound. Spec acceptance criterion 8.

12. **`test_process_performed_by_persona_roundtrip_or_skip`** — guard with `if "personas" not in inspect(engine).get_table_names(): pytest.skip("persona entity not yet built")`. When skipped, the test logs a clear marker; when active, it round-trips a `process_performed_by_persona` reference end-to-end. Spec acceptance criterion 6.

13. **`test_process_touches_field_roundtrip_or_skip`** — same guard pattern but for `field`. Spec acceptance criterion 7.

14. **`test_requirement_realized_by_process_inbound_or_skip`** — guard on the existence of a `requirements` table and the `requirement_realized_by_process` kind (both ship under PI-004). When active, create the inbound reference and assert the process's detail data surfaces it. When skipped, log a clear marker. Spec acceptance criterion 9.

Use the existing test fixtures and patterns from `tests/crmbuilder_v2/access/test_process.py` and `test_processes_api.py`. Mirror their setup/teardown and helper-import style. Each new test gets a docstring naming the spec acceptance criterion it validates.

### Step 12 — Run the test suite

```bash
uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -60
```

Expected: the baseline pass count from pre-flight step 9, plus the ≥10 new tests passing (or skipping with markers when persona/field tables are absent). Halt and report if any previously-passing test now fails.

Also run the targeted process tests in isolation as a sanity check:

```bash
uv run pytest tests/crmbuilder_v2/access/test_process.py tests/crmbuilder_v2/api/test_processes_api.py -v --tb=short 2>&1 | tail -40
```

### Step 13 — Apply the migration to the running CRMBUILDER engagement database

```bash
cd crmbuilder-v2
uv run alembic upgrade head 2>&1
uv run alembic current 2>&1
# Expected: 0013_v0_8_process_v2_growth (head)
cd ..
```

### Step 14 — Restart the API server

Stop and restart the local API so the grown SQLAlchemy model loads:

```bash
# Find and stop the running API:
pkill -f crmbuilder-v2-api || true
sleep 1
# Restart in background:
nohup uv run crmbuilder-v2-api > /tmp/crmbuilder-v2-api.log 2>&1 &
sleep 2
curl -sS http://127.0.0.1:8765/healthz | python3 -c "import sys, json; print(json.load(sys.stdin))"
```

If the health check fails, tail `/tmp/crmbuilder-v2-api.log` and report.

### Step 15 — Verification — v0.4 records survive intact

Use the first-existing-process identifier captured in pre-flight step 11. GET it via the API and unwrap `.data`:

```bash
FIRST_PROC=$(curl -sS 'http://127.0.0.1:8765/processes' \
  | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(d[0]['process_identifier'] if d else '')")
echo "FIRST_PROC=${FIRST_PROC}"

curl -sS "http://127.0.0.1:8765/processes/${FIRST_PROC}" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
for f in ('process_steps', 'process_triggers', 'process_outcomes',
          'process_edge_cases', 'process_frequency', 'process_duration_estimate'):
    print(f'{f}: {d.get(f)!r}')
"
```

Expected: every new field prints as `None`. This satisfies spec acceptance criterion 3 (v0.4 records reach v2 schema state by acquiring NULL values for the new columns).

### Step 16 — Verification — PATCH a new field

```bash
curl -sS -X PATCH "http://127.0.0.1:8765/processes/${FIRST_PROC}" \
  -H 'Content-Type: application/json' \
  -d '{"process_steps": "1. Receive trigger. 2. Validate inputs. 3. Execute. 4. Notify outcome."}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
print(f'process_steps after PATCH: {d.get(\"process_steps\")!r}')
print(f'process_triggers (other new field, should still be None): {d.get(\"process_triggers\")!r}')
"
```

Expected: `process_steps` shows the patched value; `process_triggers` remains `None`. Then revert the patch so the record is restored:

```bash
curl -sS -X PATCH "http://127.0.0.1:8765/processes/${FIRST_PROC}" \
  -H 'Content-Type: application/json' \
  -d '{"process_steps": null}' \
  | python3 -c "import sys, json; print('process_steps after revert:', json.load(sys.stdin)['data'].get('process_steps'))"
```

Expected: `None`. (This is verification only; the close-out's `apply_close_out.py` does not depend on the FIRST_PROC's state.)

### Step 17 — Verification — references CHECK admits the new kinds

```bash
# Direct DB check via the API's vocab endpoint or a small Python script.
uv run python - <<'PY'
from sqlalchemy import inspect, text
from crmbuilder_v2.access.db import engine

with engine().connect() as conn:
    # Inspect refs table CHECK definitions (SQLite stores them in sqlite_master).
    rows = list(conn.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='refs'"
    )))
    ddl = rows[0][0]
    for kind in (
        "process_performed_by_persona",
        "process_touches_field",
        "process_touches_entity",
    ):
        present = kind in ddl
        print(f"refs.relationship_kind admits {kind}: {present}")
PY
```

Expected: all three print `True`.

---

## Close-out

### Author the close-out artifacts

Per the v2 session lifecycle (CLAUDE.md), the close-out is a triple: content deliverable, close-out payload JSON, apply prompt.

**Content deliverable.** This prompt's execution IS the content deliverable — the migration, model/vocab/repo/schema/router/UI/test additions. No separate design doc needed; the spec at `process-v2.md` is the design.

**Close-out payload.** Author `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` where `NNN` is the next free session identifier. Capture before writing:

```bash
curl -sS http://127.0.0.1:8765/sessions \
  | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(f'latest SES: {max(s[\"identifier\"] for s in d)}')"
```

Use the next integer after the captured maximum. Re-key if a parallel session has claimed it in the meantime (the identifier-collision contingency per CLAUDE.md "v2 session lifecycle — planning item resolution").

The payload follows the v0.8 nine-section shape. Minimum content per section:

```json
{
  "session": {
    "identifier": "SES-NNN",
    "started_at": "<ISO 8601 UTC>",
    "ended_at": "<ISO 8601 UTC>",
    "status": "Complete",
    "summary": "PI-005 — grow the existing process methodology entity per process-v2.md v2.0. Six new TEXT NULL columns (process_steps, process_triggers, process_outcomes, process_edge_cases, process_frequency, process_duration_estimate); three new references vocabulary kinds (process_performed_by_persona, process_touches_field, process_touches_entity); detail-pane Phase-3-sections group; Edit-dialog editors for the six new fields; ≥10 new tests; no behavioral change to v0.4 fields, classification lifecycle, master pane, or endpoint set.",
    "transcript_summary": "<one-paragraph summary of the build sequence>"
  },
  "conversation": {
    "identifier": "CONV-NNN",
    "kind": "build",
    "title": "Build process v2 (PI-005)",
    "summary": "..."
  },
  "work_tickets": [],
  "planning_items": [],
  "commits": [
    {
      "sha": "<sha>",
      "message_first_line": "v2: PI-005 — process v2 schema growth (six TEXT columns + three vocab kinds + UI)",
      "files_changed_count": <n>
    }
  ],
  "decisions": [],
  "references": [],
  "resolves_planning_items": [
    {"planning_item_identifier": "PI-005"}
  ],
  "addresses_planning_items": []
}
```

Every section must be present even when empty. The single `resolves_planning_items` entry atomically flips `PI-005` from `Open` to `Resolved` when `apply_close_out.py` runs (per slice A of PI-030).

**Apply prompt.** Author `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md` modeled on `CLAUDE-CODE-PROMPT-apply-close-out-ses-077.md` (the most recent worked example for this pattern). The apply prompt documents:

- Pre-flight checks (git clean, on `main`, head equals the build commit's parent, PI-005 status currently `Open`).
- The apply command: `cd crmbuilder-v2 && uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`.
- Post-apply verification (PI-005 now `Resolved`, SES-NNN exists, deposit_event_log written at `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`).
- The final commit: regenerated `db-export/*.json` snapshots + new `deposit-event-logs/dep_NNN.log` + the close-out payload + the apply prompt itself in one commit, message starts with `v2: SES-NNN — apply close-out for PI-005`.

### Single build commit

Stage the build artifacts and commit. Use a single commit covering the migration, model, vocab, repo, schemas, router, UI, and tests:

```bash
git add crmbuilder-v2/migrations/versions/0013_v0_8_process_v2_growth.py
git add crmbuilder-v2/src/crmbuilder_v2/access/models.py
git add crmbuilder-v2/src/crmbuilder_v2/access/vocab.py
git add crmbuilder-v2/src/crmbuilder_v2/access/repositories/process.py
git add crmbuilder-v2/src/crmbuilder_v2/api/schemas.py
git add crmbuilder-v2/src/crmbuilder_v2/api/routers/processes.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/panels/processes.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/process_crud.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_process_schema.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/client.py  # if changed
git add tests/crmbuilder_v2/access/test_process.py
git add tests/crmbuilder_v2/api/test_processes_api.py

git commit -m "$(cat <<'EOF'
v2: PI-005 — process v2 schema growth (six TEXT columns + three vocab kinds + UI)

Grows the existing process methodology entity per
methodology-schema-specs/process-v2.md v2.0. Additive; preserves every
v0.4 field, the four-value process_classification lifecycle, the eight
endpoints, and the master pane verbatim.

Migration 0013:
- Adds six new TEXT NULL columns to processes: process_steps,
  process_triggers, process_outcomes, process_edge_cases,
  process_frequency, process_duration_estimate.
- Extends refs.relationship_kind CHECK to admit
  process_performed_by_persona, process_touches_field, and
  process_touches_entity.
- Reversible: downgrade drops the six columns and reverts the CHECK
  (with a guarded DELETE of any rows holding the new kinds — lossy
  recovery posture documented in the function docstring).

vocab.py:
- Adds the three new kinds to REFERENCE_RELATIONSHIPS.
- Adds _kinds_for_pair clauses for (process, persona),
  (process, field), (process, entity). The (process, entity) clause
  activates immediately; the (process, persona) and (process, field)
  clauses ship forward-aware and activate the moment PI-003 and
  PI-004 add their target entity types to ENTITY_TYPES.

Model, repo, schemas, router:
- Process model gains six Mapped[str | None] columns.
- create_process / update_process accept the new optional kwargs.
- patch_process accepts patches for each new field via the extended
  _PATCHABLE_FIELDS frozenset.
- ProcessCreateIn / ReplaceIn / PatchIn schemas accept the six new
  optional fields.
- /processes router passes the new fields through; no new endpoints.

UI:
- Detail pane gains a "Phase 3 — Detailed Process Definition" group
  with six CollapsibleSections (Steps, Triggers, Outcomes, Edge
  Cases, Frequency, Duration). Each collapses when its underlying
  field is NULL/empty.
- Edit dialog includes editors for the six new fields. Create dialog
  unchanged per spec §3.6.4 (Phase 3 content is post-create work).

Tests at tests/crmbuilder_v2/access/test_process.py and
tests/crmbuilder_v2/api/test_processes_api.py cover migration
mechanics, v0.4-record survival, individual PATCH-ability, PATCH-null
clear, PATCH-empty-string preserves, PUT-omit clears, vocab admits
new kinds, refs CHECK admits new kinds, process_touches_entity
round-trip, and process_performed_by_persona /
process_touches_field round-trips (skipped when persona/field tables
are absent).

PI-005 resolves on close-out apply.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git pull --rebase origin main
git push
```

Doug pushes per CLAUDE.md's working-conventions Claude-Code-commits-Doug-pushes rule for the local-clone surface.

### Apply the close-out

After the build commit lands on origin, run the apply prompt's command (or invoke it manually):

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json
cd ..
```

The apply script atomically:
- Writes SES-NNN, CONV-NNN, the commit record, any references, the resolves edge.
- Flips PI-005 from `Open` to `Resolved` via the `resolves_planning_items` section's atomic edge+flip transaction (per slice A of PI-030).
- Lazy-creates the `close_out_payload` and POSTs a `deposit_event` capturing the apply (per v0.7 governance integration).
- Tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` (per DEC-164).

Verify the apply:

```bash
curl -sS http://127.0.0.1:8765/planning-items/PI-005 \
  | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(f'PI-005 status: {d.get(\"status\")}')"
```

Expected: `Resolved`.

### Apply-commit

Stage and commit the regenerated DB-export snapshots, deposit-event log, close-out payload, and apply prompt:

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git add PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json
git add PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md

git commit -m "$(cat <<'EOF'
v2: SES-NNN — apply close-out for PI-005 (process v2 schema growth)

Atomically: writes SES-NNN, CONV-NNN, the build commit record, the
resolves edge from CONV-NNN to PI-005, the close_out_payload record,
and the deposit_event capturing the apply. Flips PI-005 from Open to
Resolved via the resolves_planning_items section.

PI-005 (full process schema growth beyond Phase 1 thin shape) resolves
on the build artifact at process-v2.md v2.0 plus the migration,
model, vocab, repo, schema, router, UI, and test additions landed in
the preceding commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-build Alembic head: `<head>`
- Post-build Alembic head: `0013_v0_8_process_v2_growth`
- Six new columns present on processes: True / False
- refs.relationship_kind CHECK admits the three new kinds: True / False
- PI-005 status pre-close-out: `Open`
- PI-005 status post-close-out: `Resolved`
- Tests baseline pass count → post-build pass count (+≥10 new)
- Whether `personas` / `fields` tables were present (informs which guarded tests ran vs skipped)
- Build commit SHA: `<sha>`
- Apply commit SHA: `<sha>`
- Session identifier authored: `SES-NNN`
- Conversation identifier authored: `CONV-NNN`
- Deposit-event log path: `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`
- Next prompt: none for this PI — PI-005 is fully resolved by this build. Follow-on planning items (per spec §3.8.3 — structured `process_steps`, process variants, step as first-class record, `process_definition_level` lifecycle field, master-pane growth) are deferred to v0.7+ and surface only if the CBM redo confirms the demand.
