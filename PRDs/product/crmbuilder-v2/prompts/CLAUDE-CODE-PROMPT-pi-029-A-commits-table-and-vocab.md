# CLAUDE-CODE-PROMPT-pi-029-A-commits-table-and-vocab

**Last Updated:** 05-23-26 22:30
**Operating mode:** DETAIL
**Series:** pi-029 (commit entity schema migration and access layer)
**Slice:** A — Alembic migration (commits table + refs CHECK extension + blocks→blocked_by rename) and vocab.py update (ENTITY_TYPES + REFERENCE_RELATIONSHIPS + _kinds_for_pair clauses)
**Status:** Ready to execute
**Companions:**
- `PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md` v1.0 — entity schema (authoritative).
- `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` v1.0 — methodology authority; §3.1, §7.3 (consolidated migration scope) most relevant.
- `crmbuilder-v2/migrations/versions/0011_v0_7_governance_entities.py` — closest existing migration pattern (CHECK extensions + new tables in one revision; reversible).

---

## Purpose

Land the storage foundation for the `commit` entity type per `commit.md` v1.0 and methodology §7.3. One Alembic migration that:

1. Adds the `commits` table with the v0.8 fifteen-column field inventory from `commit.md` §3.2.
2. Extends `refs.source_type` and `refs.target_type` CHECK constraints to admit the new `'commit'` entity-type value.
3. Updates `refs.relationship_kind` CHECK constraint: adds `'resolves'`, `'addresses'`, `'blocked_by'`; removes `'blocks'`.
4. Data migration: `UPDATE refs SET relationship_kind='blocked_by' WHERE relationship_kind='blocks'`. Migrates the two existing rows (`REF-0357`, `REF-0358` per methodology §7.1).
5. Extends `change_log.entity_type` CHECK constraint to admit `'commit'`.

One `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` update that:

6. Adds `'commit'` to `ENTITY_TYPES`.
7. Adds `'resolves'`, `'addresses'`, `'blocked_by'` to `REFERENCE_RELATIONSHIPS`; removes `'blocks'`.
8. Adds new clauses to `_kinds_for_pair`:
   - `(conversation, planning_item)` admits `'resolves'` and `'addresses'`.
   - `(work_ticket, planning_item)` admits `'addresses'`.
   - `(planning_item, planning_item)` admits `'blocked_by'`.
9. Removes the existing `'blocks'`-emitting clauses for `risk` and `planning_item` source types (the kind is being retired, not just renamed).

After this slice lands:
- The `commits` table exists in CRMBUILDER's engagement database and is ready to accept POSTs (though no access layer or REST endpoints exist yet — those land in subsequent slices).
- The reference vocabulary admits commit-related and code-change-lifecycle-related relationship kinds.
- No data is lost: the two `blocks` rows migrate to `blocked_by` cleanly.

This slice does NOT add:
- The access-layer CRUD methods for commits (slice B).
- The REST endpoints (slice C).
- The `apply_close_out.py` integration for the new payload sections (PI-030 work, separate planning item).
- The Commits panel UI (PI-031 work, separate planning item).
- Tests for any of the above (test scaffolding lives with each slice; this slice's tests verify migration mechanics and vocab integrity only).

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

   - `CLAUDE.md` (root) — review the "Reference relationship vocabulary lives in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`" note at line 58 and the "Adding a new relationship kind requires updating both" rule. This slice does exactly that.
   - `PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md` — the spec this migration realizes. §3.2 is the field inventory; §3.3.4 names the vocab.py contributions; §3.4 is status-free (no status column, no transitions).
   - `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` — §3.1 (commit fields), §3.2 (`resolves` kind), §3.3 (`addresses` kind), §3.4 (`blocked_by` rename), §7.3 (consolidated migration scope).
   - `crmbuilder-v2/migrations/versions/0011_v0_7_governance_entities.py` — the closest pattern. The current migration extends `refs.source_type`, `refs.target_type`, `refs.relationship_kind`, and `change_log.entity_type` CHECK constraints in one `batch_alter_table`. This slice extends them again.

6. **Verify the v2 codebase is in place.** Confirm these files exist:

   ```bash
   ls -la crmbuilder-v2/src/crmbuilder_v2/access/vocab.py
   ls -la crmbuilder-v2/migrations/versions/
   ls -la crmbuilder-v2/alembic.ini
   ```

7. **Read the relevant code paths.** Read all of `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` (491 lines; the file is small enough to load whole). Read `crmbuilder-v2/migrations/versions/0011_v0_7_governance_entities.py` end-to-end for the `batch_alter_table` and CHECK-replacement pattern. Do not modify yet.

8. **Confirm sparse-checkout includes the v2 source and migrations.** `git sparse-checkout list` should include `crmbuilder-v2/` and `PRDs/`. Stop and report if restricting visibility.

9. **Confirm the test suite is currently green.** Baseline before any changes:

   ```bash
   cd crmbuilder-v2
   uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -30
   cd ..
   ```

   Note the pass count for comparison after the slice lands.

10. **Verify the two `blocks` rows the methodology names actually exist.** The methodology §7.1 names `REF-0357` and `REF-0358` as the two existing `blocks` rows. Confirm against the running API:

    ```bash
    curl -s 'http://127.0.0.1:8765/references?relationship_kind=blocks' \
      | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(f'blocks rows: {len(d)}'); [print(f\"  {r['reference_identifier']}: {r['source_type']} {r['source_id']} -> {r['target_type']} {r['target_id']}\") for r in d]"
    ```

    Expected: 2 rows, identifiers `REF-0357` and `REF-0358`. If the count differs, stop and report — the data migration is sized for the methodology's expectation; a deviation needs human review before the migration runs.

11. **Capture pre-migration Alembic head:**

    ```bash
    cd crmbuilder-v2
    uv run alembic current 2>&1
    cd ..
    ```

    Expected: `0011_v0_7_governance_entities (head)`.

---

## Implementation

### Step 1 — Author the new Alembic migration

Create `crmbuilder-v2/migrations/versions/0012_v0_8_commits_and_blocked_by_rename.py` modeled on `0011`. The revision wires:

```python
revision: str = "0012_v0_8_commits_and_blocked_by_rename"
down_revision: Union[str, None] = "0011_v0_7_governance_entities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

The migration's `upgrade()` function performs the following operations in order:

**1a. Extend `refs.source_type` and `refs.target_type` CHECK constraints.** Add `'commit'` to both. Pattern: drop existing CHECK constraint by name, add new CHECK constraint with the extended set. Use `batch_alter_table` for SQLite-safe recopy. Use sorted alphabetical order in the CHECK expression so future diffs are easy to read.

**1b. Update `refs.relationship_kind` CHECK constraint.** Three changes in one constraint replacement: add `'resolves'`, add `'addresses'`, add `'blocked_by'`, remove `'blocks'`. Same `batch_alter_table` block as 1a so the table is recopied once.

**1c. Data migration: `blocks` → `blocked_by`.** Inside the `upgrade()` function, after the CHECK changes are committed (the new CHECK admits `'blocked_by'` so the UPDATE doesn't trip the constraint):

```python
bind = op.get_bind()
result = bind.execute(
    sa.text("UPDATE refs SET relationship_kind = 'blocked_by' WHERE relationship_kind = 'blocks'")
)
# Verification (will assert against the methodology-named count of 2):
remaining = bind.execute(
    sa.text("SELECT COUNT(*) FROM refs WHERE relationship_kind = 'blocks'")
).scalar()
assert remaining == 0, f"After UPDATE, expected 0 'blocks' rows; found {remaining}"
```

The CHECK constraint replacement and the UPDATE must be in the same migration because the new CHECK removes `'blocks'` from the allowed set; after the CHECK change, any remaining `blocks` row would be an integrity violation. The order in this migration: replace the CHECK first (admitting `blocked_by`), then UPDATE the rows (migrating to `blocked_by`). The intermediate state — CHECK admits both `blocks` and `blocked_by` — does not occur because the CHECK replacement is atomic per the `batch_alter_table` recopy semantics.

Actually, reconsider the order: SQLite's `batch_alter_table` recopies the table, which means any row that does not satisfy the new CHECK during the recopy fails. So the order MUST be:
1. UPDATE the existing rows to `blocked_by` (under the OLD CHECK, which admits both `blocks` and `blocked_by` is not yet in the set — but the OLD CHECK only admits `blocks`, NOT `blocked_by`, so this fails).

Re-resolve: the order MUST be a single atomic `batch_alter_table` that admits BOTH the old and new values for the duration of the recopy, plus a separate UPDATE in a transaction-safe sequence. Two viable approaches:

- **Approach 1 (recommended):** Use TWO migration steps within one revision. First `batch_alter_table` replaces the CHECK with an EXPANDED set (admits both `blocks` and `blocked_by`). Then UPDATE the rows. Then a SECOND `batch_alter_table` replaces the CHECK with the FINAL set (removes `blocks`). Net effect across two recopies: one atomic migration that transitions cleanly.

- **Approach 2:** Drop the CHECK entirely (Alembic allows naming it for drop), UPDATE the rows, add the FINAL CHECK. Three operations, same single revision.

Adopt **Approach 1** for consistency with how `0011` structured its CHECK replacement (single named-CHECK swap). The expanded interim CHECK admits both values for the duration of the migration; the final CHECK removes `blocks`.

The migration's structure:

```python
def upgrade() -> None:
    # Step 1a/1b: refs CHECK extensions — interim values admit both 'blocks' and 'blocked_by'
    with op.batch_alter_table("refs", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_refs_source_type", type_="check")
        batch_op.drop_constraint("ck_refs_target_type", type_="check")
        batch_op.drop_constraint("ck_refs_relationship_kind", type_="check")
        batch_op.create_check_constraint("ck_refs_source_type", _INTERIM_REF_SOURCE_TYPE_CHECK)
        batch_op.create_check_constraint("ck_refs_target_type", _INTERIM_REF_TARGET_TYPE_CHECK)
        batch_op.create_check_constraint("ck_refs_relationship_kind", _INTERIM_REF_RELATIONSHIP_CHECK)

    # Step 1c: data migration — 'blocks' rows to 'blocked_by'
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE refs SET relationship_kind = 'blocked_by' WHERE relationship_kind = 'blocks'"))
    remaining = bind.execute(sa.text("SELECT COUNT(*) FROM refs WHERE relationship_kind = 'blocks'")).scalar()
    assert remaining == 0, f"After UPDATE, expected 0 'blocks' rows; found {remaining}"

    # Step 1d: refs CHECK finalization — final values remove 'blocks'
    with op.batch_alter_table("refs", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_refs_relationship_kind", type_="check")
        batch_op.create_check_constraint("ck_refs_relationship_kind", _FINAL_REF_RELATIONSHIP_CHECK)

    # Step 1e: change_log CHECK extension
    with op.batch_alter_table("change_log", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_change_log_entity_type", type_="check")
        batch_op.create_check_constraint("ck_change_log_entity_type", _NEW_CHANGELOG_ENTITY_TYPE_CHECK)

    # Step 2: create commits table
    op.create_table(
        "commits",
        # ... column definitions per commit.md §3.2
    )
```

Verify the actual CHECK constraint names in the v0.7 migration before using them — they may be `ck_refs_relationship_kind` per Alembic's auto-name convention, or they may be unnamed (in which case `batch_alter_table` recopies the table without a `drop_constraint` call and creates the new CHECK on the new table). Inspect `0011_v0_7_governance_entities.py` to confirm the actual approach used there and follow the same pattern.

**1e. Extend `change_log.entity_type` CHECK constraint.** Same pattern as `0011`. Add `'commit'` to the admitted set.

**2. Create `commits` table.** Schema per `commit.md` §3.2:

```python
op.create_table(
    "commits",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("commit_identifier", sa.Text, nullable=False),
    sa.Column("commit_sha", sa.Text, nullable=False),
    sa.Column("commit_message_first_line", sa.Text, nullable=False),
    sa.Column("commit_message_full", sa.Text, nullable=False),
    sa.Column("commit_author_name", sa.Text, nullable=False),
    sa.Column("commit_author_email", sa.Text, nullable=False),
    sa.Column("commit_committed_at", sa.Text, nullable=False),  # ISO 8601 with offset; stored as text per V2 convention
    sa.Column("commit_repository", sa.Text, nullable=False),
    sa.Column("commit_branch", sa.Text, nullable=False, server_default="main"),
    sa.Column("commit_parent_shas", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
    sa.Column("commit_files_changed_count", sa.Integer, nullable=False),
    sa.Column("commit_conversation_id", sa.Text, nullable=False),
    sa.Column("commit_created_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
    sa.Column("commit_updated_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
    sa.Column("commit_deleted_at", sa.DateTime, nullable=True),
    sa.UniqueConstraint("commit_identifier", name="uq_commits_commit_identifier"),
    sa.UniqueConstraint("commit_sha", name="uq_commits_commit_sha"),
    sa.CheckConstraint(
        "commit_identifier GLOB 'CM-[0-9][0-9][0-9][0-9]'",
        name="ck_commits_commit_identifier_format",
    ),
    sa.CheckConstraint(
        "LENGTH(commit_sha) = 40 AND commit_sha GLOB '[0-9a-f]*' AND commit_sha NOT GLOB '*[^0-9a-f]*'",
        name="ck_commits_commit_sha_format",
    ),
    sa.CheckConstraint(
        "commit_files_changed_count >= 0",
        name="ck_commits_files_changed_count_nonneg",
    ),
)

# Indexes for the dominant query patterns per commit.md §3.5:
op.create_index("ix_commits_commit_conversation_id", "commits", ["commit_conversation_id"])
op.create_index("ix_commits_commit_repository", "commits", ["commit_repository"])
op.create_index("ix_commits_commit_committed_at", "commits", ["commit_committed_at"])
```

Notes on the column types:

- `commit_committed_at` is `sa.Text` not `sa.DateTime` because the column preserves the ISO 8601 offset string verbatim (committer-local time with offset, e.g. `2026-05-23T20:45:12-04:00`); SQLAlchemy's `DateTime` would normalize to UTC. The `commit.md` §3.2.5 description documents this deviation from base timestamps.
- `commit_parent_shas` uses `sa.JSON` with server default `'[]'` for the empty-parent (initial commit) case. SQLAlchemy renders JSON as TEXT in SQLite.
- `commit_branch` defaults to `'main'` per `commit.md` §3.2.5.
- `commit_created_at`, `commit_updated_at`, `commit_deleted_at` follow the base-timestamps convention used by every other governance table.
- No SQL-level FOREIGN KEY constraint on `commit_conversation_id` — V2's soft-FK convention is that the access layer validates referent existence, not the database boundary. Consistent with how `refs.source_id` / `refs.target_id` are NOT declared as foreign keys despite holding identifier strings.

The `downgrade()` function reverses in opposite order:
1. Drop `commits` table.
2. Drop the `change_log.entity_type` extension.
3. Reverse the `blocks` → `blocked_by` data migration (`UPDATE refs SET relationship_kind = 'blocks' WHERE relationship_kind = 'blocked_by'`). Note: this is a lossy reversal — any new `blocked_by` rows authored between upgrade and downgrade are silently re-mapped to `blocks`. Document the lossy posture in the function's docstring; do not block on it (Alembic downgrades are operational rollback tools, not undo functions).
4. Drop the `refs.relationship_kind` final CHECK; restore the interim CHECK; UPDATE rows back (per above); drop the interim CHECK; restore the original CHECK.
5. Restore the original `refs.source_type` / `refs.target_type` CHECKs.

Keep the constants `_NEW_REF_SOURCE_TYPE_CHECK`, `_NEW_REF_TARGET_TYPE_CHECK`, `_FINAL_REF_RELATIONSHIP_CHECK`, `_INTERIM_REF_RELATIONSHIP_CHECK`, `_OLD_REF_*_CHECK` (from `0011`) at module scope so the constants are inspectable. Match `0011`'s convention.

### Step 2 — Update `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`

Three edits, all surgical:

**2a. Add `'commit'` to `ENTITY_TYPES`.** Insert after `"deposit_event"` and before the closing brace. Group comment update: amend the v0.8 section comment (or add one if not present) to name the commit entity-type addition under v0.8.

**2b. Update `REFERENCE_RELATIONSHIPS`.** Three changes:
- Add `'resolves'`, `'addresses'`, `'blocked_by'`.
- Remove `'blocks'`.
- Update the section comment block above the v0.7 additions to add a v0.8 sub-section comment naming the three new kinds plus the `'blocks'` → `'blocked_by'` rename (the methodology document references this).

**2c. Update `_kinds_for_pair`.** Four changes:

- Remove the existing two `'blocks'`-emitting clauses:
  ```python
  if source_type == "risk":
      kinds.add("affects")
      kinds.add("blocks")   # REMOVE THIS LINE
  if source_type == "planning_item":
      kinds.add("blocks")   # REMOVE THIS CLAUSE OR REPLACE
  ```
  The `risk` source remains valid for `affects`; only the `blocks` addition is removed. The `planning_item` source previously only contributed `blocks`; with that removed, the clause is replaced by the new `(planning_item, planning_item)` clause that adds `blocked_by`.

- Add three new clauses for the methodology's relationship kinds:

  ```python
  # v0.8 Code Change Lifecycle additions:
  if source_type == "conversation" and target_type == "planning_item":
      kinds.add("resolves")
      kinds.add("addresses")
  if source_type == "work_ticket" and target_type == "planning_item":
      kinds.add("addresses")
  if source_type == "planning_item" and target_type == "planning_item":
      kinds.add("blocked_by")
  ```

  Insert the v0.8 block after the existing v0.7 block, ordered consistently with the existing source-grouped style. The `(planning_item, planning_item)` clause replaces the prior `if source_type == "planning_item": kinds.add("blocks")` clause — same source type, refined to a directed kind targeting same-type and renamed to `blocked_by`.

Verify the section comment for the section header above each block is updated to reflect v0.8.

### Step 3 — Add migration-mechanics tests

Add `crmbuilder-v2/tests/crmbuilder_v2/migrations/test_0012_commits_and_blocked_by.py`. Three test functions:

**3a. `test_upgrade_creates_commits_table`.** Apply the migration; assert the `commits` table exists with the expected columns; assert the UNIQUE constraints on `commit_identifier` and `commit_sha` are present; assert the CHECK constraint on `commit_identifier`'s format rejects invalid identifiers.

**3b. `test_upgrade_renames_blocks_to_blocked_by`.** Apply the migration; assert the `refs.relationship_kind` CHECK constraint admits `'blocked_by'` and rejects `'blocks'`; if the test fixture seeds the two `blocks` rows the methodology names, assert they migrated to `blocked_by` with `source_id` and `target_id` preserved.

**3c. `test_vocab_admits_new_kinds`.** Import `vocab.py`; assert `'commit'` is in `ENTITY_TYPES`; assert `'resolves'`, `'addresses'`, `'blocked_by'` are in `REFERENCE_RELATIONSHIPS`; assert `'blocks'` is NOT in `REFERENCE_RELATIONSHIPS`; assert `_kinds_for_pair('conversation', 'planning_item')` includes `{'resolves', 'addresses'}` (plus the generic kinds); assert `_kinds_for_pair('work_ticket', 'planning_item')` includes `'addresses'`; assert `_kinds_for_pair('planning_item', 'planning_item')` includes `'blocked_by'`.

Follow the existing test patterns in `crmbuilder-v2/tests/crmbuilder_v2/migrations/`. Use the standard fixture that exposes an Alembic-applied test database.

### Step 4 — Run the test suite

```bash
cd crmbuilder-v2
uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -40
cd ..
```

Expected: the baseline pass count from pre-flight step 9, plus the three new tests passing. Halt and report if any previously-passing test now fails.

### Step 5 — Apply the migration to the running CRMBUILDER engagement database

The development pattern is to apply migrations to the running engagement DB so the API picks them up at next start. The migration is forward-only; running it against an already-migrated database is a no-op (Alembic skips the revision).

```bash
cd crmbuilder-v2
uv run alembic upgrade head 2>&1
uv run alembic current 2>&1
# Expected: 0012_v0_8_commits_and_blocked_by_rename (head)
cd ..
```

Verify the migration actually ran by spot-checking the schema:

```bash
# The CRMBUILDER engagement DB lives at crmbuilder-v2/data/v2.db per CLAUDE.md.
# Use the v2 API rather than sqlite3 CLI (per project memory: Doug's local has no sqlite3 CLI):
uv run python -c "
from crmbuilder_v2.access.db import session_scope
from sqlalchemy import text
with session_scope() as s:
    rows = list(s.execute(text(\"SELECT name FROM sqlite_master WHERE type='table' AND name='commits'\")))
    print(f'commits table present: {len(rows) == 1}')
    rows = list(s.execute(text(\"SELECT COUNT(*) FROM refs WHERE relationship_kind='blocks'\")))
    print(f'blocks rows remaining: {rows[0][0]}')
    rows = list(s.execute(text(\"SELECT COUNT(*) FROM refs WHERE relationship_kind='blocked_by'\")))
    print(f'blocked_by rows: {rows[0][0]}')
"
```

Expected output:
```
commits table present: True
blocks rows remaining: 0
blocked_by rows: 2
```

If `blocked_by rows` is not exactly 2, the migration's data migration did not match the methodology's expectation of two `REF-0357` and `REF-0358` rows. Stop and report.

---

## Commit

Two commits, in order:

**Commit 1 — Migration and vocab.** Stage and commit:

```bash
git add crmbuilder-v2/migrations/versions/0012_v0_8_commits_and_blocked_by_rename.py
git add crmbuilder-v2/src/crmbuilder_v2/access/vocab.py
git add crmbuilder-v2/tests/crmbuilder_v2/migrations/test_0012_commits_and_blocked_by.py

git commit -m "v2: PI-029 slice A — commits table, blocks→blocked_by rename, vocab update

Lands the storage foundation for the commit entity type per
governance-schema-specs/commit.md v1.0 and the renamed/added relationship
kinds per methodology-code-change-lifecycle.md §3.2-§3.4.

Migration 0012:
- Adds commits table with 15 columns per commit.md §3.2 (identity,
  content, relationship, git metadata, timestamp categories).
- Extends refs.source_type / refs.target_type CHECK to admit 'commit'.
- Two-step CHECK swap on refs.relationship_kind: interim CHECK admits
  both 'blocks' and 'blocked_by'; data migration UPDATEs the two
  REF-0357 / REF-0358 rows; final CHECK removes 'blocks'.
- Extends change_log.entity_type CHECK to admit 'commit'.

vocab.py:
- Adds 'commit' to ENTITY_TYPES under a v0.8 section comment.
- Adds 'resolves', 'addresses', 'blocked_by' to REFERENCE_RELATIONSHIPS;
  removes 'blocks'.
- Adds _kinds_for_pair clauses for (conversation, planning_item) →
  {resolves, addresses}, (work_ticket, planning_item) → {addresses},
  (planning_item, planning_item) → {blocked_by}.
- Removes legacy 'blocks'-emitting clauses for risk and planning_item
  source types.

Tests at tests/crmbuilder_v2/migrations/test_0012_commits_and_blocked_by.py
verify migration mechanics and vocab integrity. Access-layer CRUD,
REST endpoints, and the apply_close_out.py integration land in
subsequent slices."

git pull --rebase origin main
git push
```

Wait for Doug's review and push approval (per the working-conventions Claude-Code-commits-Doug-pushes rule for the local-clone surface).

---

## Done

Reply with:

- Pre-flight Alembic head: `0011_v0_7_governance_entities`
- Post-migration Alembic head: `0012_v0_8_commits_and_blocked_by_rename`
- `commits` table present in engagement DB: True / False
- `blocks` rows remaining after migration: 0 (expected)
- `blocked_by` rows after migration: 2 (expected)
- Test suite: pre-slice pass count vs post-slice pass count (+3 new tests expected)
- Commit SHA: `<sha>`
- Next prompt to run: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-B-commit-access-layer-and-rest.md` (not yet authored — emerges from this slice's review and from the PI-029 build-planning approach taken at the next planning conversation)
