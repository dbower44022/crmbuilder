# CLAUDE-CODE-PROMPT-build-test_spec

**Last Updated:** 05-25-26
**Operating mode:** DETAIL
**Series:** PI-004 build tranche (methodology entities for v0.5+: `field`, `requirement`, `manual_config`, `test_spec`)
**Slice:** `test_spec` — the verification-specification methodology entity
**Status:** Ready to execute. Blocked by: nothing — `test_spec.md` spec is canonical.
**Companions:**
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/test_spec.md` v1.0 — authoritative entity schema. All numbered subsections cited inline (§3.1 identity, §3.2 fields, §3.3 relationships, §3.4 lifecycle including §3.4.3 dual-axis rationale and §3.4.4 cross-field invariant, §3.5 API surface, §3.6 UI, §3.7 sixteen acceptance criteria, §3.8 open questions).
- `crmbuilder-v2/migrations/versions/0008_v0_4_create_entities_table.py` — migration pattern for a methodology-entity table (parent-prefixed columns, GLOB identifier CHECK, status enum CHECK, base timestamps + soft-delete, two indexes).
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/entity.py` — repository pattern (eight standard functions + helpers; SAVEPOINT-retry identifier auto-assign; transition validation; case-insensitive name uniqueness; soft-delete that does NOT cascade references).
- `crmbuilder-v2/src/crmbuilder_v2/api/routers/entities.py` — router pattern (eight endpoints, `{data, meta, errors}` envelope via `ok(...)`, body-key-strip on PATCH).
- `crmbuilder-v2/src/crmbuilder_v2/ui/panels/entities.py` + `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/entity_crud.py` + `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_entity_schema.py` — UI pattern (`ListDetailPanel` master+detail, `EntityCrudDialog` create/edit, `EntityCrudDeleteDialog` with edge-text confirmation, declarative `FieldSchema` list).
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — vocabulary pattern (`*_STATUSES` + `*_STATUS_TRANSITIONS`, `ENTITY_TYPES`, `REFERENCE_RELATIONSHIPS`, `_kinds_for_pair` semantic-rule clauses).

---

## Purpose

Land the full `test_spec` methodology entity end-to-end per `test_spec.md` v1.0 — migration, ORM model, vocab, repository, schemas, REST endpoints, UI client, sidebar registration, main-window dispatch, panel + dialogs, tests, and the standard close-out artifacts. This is one of four PI-004 siblings; see the "PI-004 build-closure rule" at the bottom of this prompt for the close-out's resolves-vs-addresses decision.

After this slice lands:
- `test_specs` table exists with twelve substantive columns plus three base timestamps (`test_spec.md` §3.7 AC 1, fifteen total).
- REST endpoints `/test-specs` (eight standard + one convenience `record-run`) are reachable and pass the `{data, meta, errors}` envelope.
- Methodology-lifecycle status (`candidate` / `confirmed` / `deferred`) and execution-outcome (`not_run` / `passing` / `failing` / `skipped`) validate independently with the asymmetric transition rules per spec §3.4.
- Server enforces the cross-field invariant: `test_spec_last_run_at` auto-set when outcome moves to a run state, auto-cleared when outcome moves back to `not_run` (§3.4.4).
- Three new outgoing reference kinds (`test_spec_touches_entity`, `test_spec_touches_field`, `test_spec_exercises_process`) registered exactly once, in this spec, per the CLAUDE.md line 48 once-per-kind rule. The inbound `requirement_verified_by_test_spec` is NOT registered here (the requirement-side sibling spec registers it).
- The `Test Specs` sidebar entry sits in the Methodology group between Requirements and Manual Config (provisional ordering per §3.6.1 — see Pre-flight step 6).
- Master pane shows five columns with the color-cued Last Run column per §3.6.2 deviation. Detail pane organizes per §3.6.3 with three subsection headers (Test body, Last run, Internal notes collapsed).

This slice does NOT touch the sibling specs (`field`, `requirement`, `manual_config`, `persona`); the only cross-spec assumption is that `field` and `requirement` entity types exist as valid reference targets/sources before any reference rows are written. If the `field` entity type is not yet in `ENTITY_TYPES` at the time this prompt runs, the `test_spec_touches_field` clause in `_kinds_for_pair` is still authored, but cannot be exercised end-to-end until `field` lands. The migration's `refs.target_type` CHECK extension does not need to add `'field'` here — the field-side build prompt extends that CHECK.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes. (The build runs against a known-clean base; close-out commits are explicit at the end.)

3. **Confirm git identity:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if conflicts.

5. **Read the companion documents** in the order listed at the top of this prompt. The authoritative content choices (field inventory, status sets, transition maps, relationship kinds, UI grouping, color cues, acceptance criteria) come from `test_spec.md` — when this prompt and the spec disagree, the spec wins and this prompt should be flagged for correction.

   Also read:
   - `CLAUDE.md` (root) — note the `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair` / Alembic-migration triad rule (line 48) and the `{data, meta, errors}` envelope rule. Both apply to this slice.
   - `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` if present, for any cross-spec conventions not yet inlined into `test_spec.md`.

6. **Sidebar-ordering check.** §3.6.1 of `test_spec.md` proposes a position for "Test Specs" in the Methodology group between Requirements and Manual Config. Confirm whether the sibling specs have already landed:

   ```bash
   grep -n '"Test Specs"\|"Requirements"\|"Fields"\|"Personas"\|"Manual Config"' crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py || true
   ```

   - If `Requirements`, `Fields`, `Personas`, `Manual Config` are all absent, insert `"Test Specs"` after `"CRM Candidates"` at the tail of the Methodology group; leave a comment naming the PI-004 sibling ordering pending the other sibling builds.
   - If some siblings are present, insert at the §3.6.1 position relative to whichever siblings exist.
   - This is a soft choice; the v0.5 build conversation finalizes the ordering when all four PI-004 siblings land. Do not block on it.

7. **Verify the v2 source paths exist:**

   ```bash
   ls -la crmbuilder-v2/src/crmbuilder_v2/access/vocab.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/access/repositories/entity.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/api/routers/entities.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/ui/panels/entities.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/entity_crud.py
   ls -la crmbuilder-v2/migrations/versions/
   ```

8. **Confirm sparse-checkout includes the v2 source, migrations, and tests:**

   ```bash
   git sparse-checkout list 2>/dev/null || true
   ```

9. **Baseline pass count:** capture the pre-build test pass count for comparison:

   ```bash
   uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -30
   ```

   Note the pass count.

10. **Capture pre-migration Alembic head:**

    ```bash
    cd crmbuilder-v2
    uv run alembic current 2>&1
    cd ..
    ```

    Note the head revision. The new migration's `down_revision` must point to whatever the current head is at execution time (likely `0012_v0_8_commits_and_blocked_by_rename` or a later v0.8 revision if a sibling has already landed).

11. **Inventory existing identifier prefixes** to confirm `TST` is unclaimed (§3.1):

    ```bash
    grep -rEn '"[A-Z]{2,4}-[0-9]+"|GLOB '"'"'[A-Z]{2,4}-' crmbuilder-v2/src/crmbuilder_v2/access/ | grep -v __pycache__ | head -40
    ```

    Expected: no occurrences of `TST-`. Stop and report if any sibling spec has already claimed it.

---

## Implementation

### Step 1 — Migration

Create `crmbuilder-v2/migrations/versions/00XX_v0_5_create_test_specs_table.py` where `00XX` is the next sequence after the current head from pre-flight step 10. The migration is structurally similar to `0008_v0_4_create_entities_table.py` (single-table create) with three additions: extra columns for the dual-axis state and last-run snapshot; an additional CHECK on the second status field; and the `refs` CHECK extensions for the three new relationship kinds plus the new `'test_spec'` source/target value.

#### 1a — Module header

```python
"""v0.5+ — create the test_specs table; extend refs CHECK for test_spec and three new kinds.

Revision ID: 00XX_v0_5_create_test_specs_table
Revises: <current head>
Create Date: 2026-05-25

PI-004 sibling slice (test_spec). Adds the ``test_specs`` table per
``methodology-schema-specs/test_spec.md`` §3.2 — twelve substantive
columns plus three base timestamps. Extends ``refs.source_type`` and
``refs.target_type`` CHECK to admit ``'test_spec'``. Extends
``refs.relationship_kind`` CHECK to admit ``'test_spec_touches_entity'``,
``'test_spec_touches_field'``, ``'test_spec_exercises_process'``.
Extends ``change_log.entity_type`` CHECK to admit ``'test_spec'``.

The schema follows the parent-prefix field-naming convention (DEC-046):
every column is prefixed ``test_spec_``. The primary key is the
prefixed-string identifier ``test_spec_identifier`` (format
``TST-NNN``) — there is no integer surrogate ``id`` column.

Two enum columns carry CHECK constraints:

* ``test_spec_status`` — methodology lifecycle, three values
  (``candidate`` / ``confirmed`` / ``deferred``), default ``candidate``.
  Transition map mirrors ``domain`` and ``entity`` exactly per spec
  §3.4.1 (propose-verify gate, DEC-047).
* ``test_spec_last_run_outcome`` — execution outcome, four values
  (``not_run`` / ``passing`` / ``failing`` / ``skipped``), default
  ``not_run``. Transitions are unrestricted per spec §3.4.2 — no
  transition map; the database CHECK enforces enum membership only.

The cross-field invariant from spec §3.4.4 (``last_run_at`` must be
populated whenever outcome is a run state) is access-layer enforced,
not declared as a SQL CHECK — SQLite's CHECK expressions cannot reference
cross-row data and the rule is one a server-side trigger could enforce
but is more readable in Python.

Forward and backward reversible.
"""
```

#### 1b — Revision constants

```python
revision: str = "00XX_v0_5_create_test_specs_table"
down_revision: Union[str, None] = "<current head>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

#### 1c — refs CHECK constant strings

Pattern from `0006_v0_4_foundation_refs_check_extensions.py` and `0012_v0_8_commits_and_blocked_by_rename.py`. Three constants for the new/old `source_type`, `target_type`, `relationship_kind` CHECKs. Read the *current* head migration's CHECK strings, copy them as the `_OLD_*` constants, and add `'test_spec'` to the source/target sets and the three new kinds to the relationship set (alphabetical order for readable future diffs).

The new relationship kinds to add:
- `'test_spec_exercises_process'`
- `'test_spec_touches_entity'`
- `'test_spec_touches_field'`

#### 1d — change_log CHECK constant strings

Same pattern as `0011_v0_7_governance_entities.py`. Two constants for new and old `change_log.entity_type` CHECKs. Add `'test_spec'` to the new set.

#### 1e — `upgrade()`

Two phases. First, recopy `refs` and `change_log` to extend CHECKs. Then `op.create_table("test_specs", ...)`. Pseudocode:

```python
def upgrade() -> None:
    # Extend refs CHECKs.
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_source_type", type_="check")
        batch_op.drop_constraint("ck_ref_target_type", type_="check")
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_source_type", _NEW_REF_SOURCE_TYPE_CHECK
        )
        batch_op.create_check_constraint(
            "ck_ref_target_type", _NEW_REF_TARGET_TYPE_CHECK
        )
        batch_op.create_check_constraint(
            "ck_ref_relationship", _NEW_REF_RELATIONSHIP_CHECK
        )

    # Extend change_log CHECK.
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _NEW_CHANGELOG_ENTITY_TYPE_CHECK
        )

    # Create the test_specs table.
    op.create_table(
        "test_specs",
        sa.Column("test_spec_identifier", sa.String(length=32), nullable=False),
        sa.Column("test_spec_name", sa.String(length=255), nullable=False),
        sa.Column("test_spec_description", sa.Text(), nullable=False),
        sa.Column("test_spec_setup", sa.Text(), nullable=True),
        sa.Column("test_spec_steps", sa.Text(), nullable=False),
        sa.Column("test_spec_expected", sa.Text(), nullable=False),
        sa.Column("test_spec_notes", sa.Text(), nullable=True),
        sa.Column(
            "test_spec_status",
            sa.String(length=16),
            nullable=False,
            server_default="candidate",
        ),
        sa.Column(
            "test_spec_last_run_outcome",
            sa.String(length=16),
            nullable=False,
            server_default="not_run",
        ),
        sa.Column(
            "test_spec_last_run_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("test_spec_last_run_notes", sa.Text(), nullable=True),
        sa.Column(
            "test_spec_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "test_spec_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "test_spec_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "test_spec_identifier GLOB 'TST-[0-9][0-9][0-9]'",
            name="ck_test_spec_identifier_format",
        ),
        sa.CheckConstraint(
            "test_spec_status IN ('candidate', 'confirmed', 'deferred')",
            name="ck_test_spec_status",
        ),
        sa.CheckConstraint(
            "test_spec_last_run_outcome IN "
            "('failing', 'not_run', 'passing', 'skipped')",
            name="ck_test_spec_last_run_outcome",
        ),
        sa.PrimaryKeyConstraint("test_spec_identifier"),
    )
    with op.batch_alter_table("test_specs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_test_specs_test_spec_status",
            ["test_spec_status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_test_specs_test_spec_last_run_outcome",
            ["test_spec_last_run_outcome"],
            unique=False,
        )
        batch_op.create_index(
            "ix_test_specs_test_spec_deleted_at",
            ["test_spec_deleted_at"],
            unique=False,
        )
```

`server_default` is set on `test_spec_status` and `test_spec_last_run_outcome` so backfills and any direct-SQL INSERT (e.g. a future bulk-import path) get a sensible value; the ORM also sets them via `default=`.

#### 1f — `downgrade()`

Reverse in opposite order: drop `test_specs` table; restore old CHECKs on `change_log` then `refs`.

#### 1g — Verify the constraint names

Before authoring the migration, inspect the head's actual constraint names (some are `ck_ref_*`, others `ck_refs_*`; some are `ck_changelog_entity_type`, others `ck_change_log_entity_type`):

```bash
grep -nE 'drop_constraint.*type_="check"|create_check_constraint' crmbuilder-v2/migrations/versions/0012_v0_8_commits_and_blocked_by_rename.py
```

Use whatever the existing migrations use. Mismatched names cause `batch_alter_table` to fail silently in some Alembic versions or hard-fail in others.

### Step 2 — ORM model

Add a `TestSpec(Base)` class to `crmbuilder-v2/src/crmbuilder_v2/access/models.py` immediately after `CrmCandidate` (or wherever the methodology entities live). Pattern from `class Entity(Base)`:

```python
class TestSpec(Base):
    """Methodology entity — one verification specification.

    Verification specification for the v2 verification phase, paired
    with one or more requirements via the inbound
    ``requirement_verified_by_test_spec`` reference kind (registered by
    the requirement-side spec). Per ``test_spec.md`` §3.2 the schema
    follows the parent-prefix field-naming convention: every column is
    prefixed ``test_spec_``. The primary key is the prefixed-string
    identifier ``test_spec_identifier`` (format ``TST-NNN``) — there is
    no integer surrogate ``id`` column.

    Dual-axis state per §3.4.3: ``test_spec_status`` carries the
    methodology lifecycle (one-way propose-verify gate);
    ``test_spec_last_run_outcome`` carries the execution outcome
    (unrestricted transitions). Companion fields ``test_spec_last_run_at``
    and ``test_spec_last_run_notes`` hold the most-recent-run snapshot;
    historical run series deferred to v0.6+ per §3.8.3.
    """

    __tablename__ = "test_specs"

    test_spec_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    test_spec_name: Mapped[str] = mapped_column(String(255), nullable=False)
    test_spec_description: Mapped[str] = mapped_column(Text, nullable=False)
    test_spec_setup: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_spec_steps: Mapped[str] = mapped_column(Text, nullable=False)
    test_spec_expected: Mapped[str] = mapped_column(Text, nullable=False)
    test_spec_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_spec_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    test_spec_last_run_outcome: Mapped[str] = mapped_column(
        String(16), nullable=False, default="not_run"
    )
    test_spec_last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    test_spec_last_run_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    test_spec_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    test_spec_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    test_spec_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "test_spec_identifier GLOB 'TST-[0-9][0-9][0-9]'",
            name="ck_test_spec_identifier_format",
        ),
        CheckConstraint(
            _check_in("test_spec_status", TEST_SPEC_STATUSES),
            name="ck_test_spec_status",
        ),
        CheckConstraint(
            _check_in(
                "test_spec_last_run_outcome", TEST_SPEC_RUN_OUTCOMES
            ),
            name="ck_test_spec_last_run_outcome",
        ),
        Index(
            "ix_test_specs_test_spec_status", "test_spec_status"
        ),
        Index(
            "ix_test_specs_test_spec_last_run_outcome",
            "test_spec_last_run_outcome",
        ),
        Index(
            "ix_test_specs_test_spec_deleted_at",
            "test_spec_deleted_at",
        ),
    )
```

Import `TEST_SPEC_STATUSES` and `TEST_SPEC_RUN_OUTCOMES` from `crmbuilder_v2.access.vocab` at the top of `models.py` alongside the other vocab imports.

### Step 3 — Vocab

Edit `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`.

#### 3a — `TEST_SPEC_STATUSES` + `TEST_SPEC_STATUS_TRANSITIONS`

Insert immediately after `ENTITY_STATUS_TRANSITIONS`:

```python
# Methodology entity `test_spec` lifecycle (PI-004 sibling).
# Mirrors ``domain``'s and ``entity``'s three-status propose-verify
# lifecycle exactly per ``test_spec.md`` §3.4.1 — propose-verify gate
# (DEC-047): once out of ``candidate`` a record never regresses to it;
# ``confirmed`` and ``deferred`` move freely between each other.
TEST_SPEC_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred"}
)

TEST_SPEC_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred"}),
    "deferred": frozenset({"confirmed"}),
}
```

#### 3b — `TEST_SPEC_RUN_OUTCOMES`

Insert immediately after `TEST_SPEC_STATUS_TRANSITIONS`. Note: NO transitions dict — outcome transitions are unrestricted per §3.4.2. Document this in the comment so future readers do not invent one.

```python
# `test_spec` execution outcome (PI-004 sibling). Four values; all
# transitions are unrestricted — observational, not decisional. The
# access layer does NOT validate outcome → outcome transitions and does
# NOT carry a transition map. See ``test_spec.md`` §3.4.2 and §3.4.3
# (dual-axis-state justification) for why outcomes diverge from the
# methodology-status pattern.
TEST_SPEC_RUN_OUTCOMES: frozenset[str] = frozenset(
    {"not_run", "passing", "failing", "skipped"}
)
```

#### 3c — `ENTITY_TYPES`

Add `'test_spec'` to the `ENTITY_TYPES` frozenset. Place it in the Methodology block alongside `'domain'`, `'entity'`, `'process'`, `'crm_candidate'`, with an inline comment noting PI-004 and the sibling spec.

#### 3d — `REFERENCE_RELATIONSHIPS`

Add the three new outbound kinds. Insert in alphabetical order or in a clearly-labeled PI-004 block:

```python
        # v0.5+ methodology additions (PI-004 sibling — test_spec).
        # Three outbound kinds registered here. The inbound
        # ``requirement_verified_by_test_spec`` kind is registered by
        # the requirement-side spec, not here, per CLAUDE.md line 48's
        # once-per-kind rule.
        "test_spec_exercises_process",
        "test_spec_touches_entity",
        "test_spec_touches_field",
```

**Do NOT add `'requirement_verified_by_test_spec'` here** — that kind is registered exactly once by `requirement.md`'s build prompt (spec §3.3.2; CLAUDE.md line 48 once-per-kind rule).

#### 3e — `_kinds_for_pair`

Add three clauses. Pattern from the v0.4 entity-scopes-to-domain and process-hands-off-to-process clauses. Insert in the methodology block:

```python
    # v0.5+ methodology additions per ``test_spec.md`` §3.3.1:
    if source_type == "test_spec" and target_type == "entity":
        kinds.add("test_spec_touches_entity")
    if source_type == "test_spec" and target_type == "field":
        kinds.add("test_spec_touches_field")
    if source_type == "test_spec" and target_type == "process":
        kinds.add("test_spec_exercises_process")
```

The `test_spec → field` clause is authored even if the `field` entity type is not yet in `ENTITY_TYPES`; `RELATIONSHIP_RULES` is computed by iterating `sorted(ENTITY_TYPES)`, so the clause is dormant until the field-side build adds `'field'` to `ENTITY_TYPES`. Once present, the clause activates automatically without re-running `_kinds_for_pair`.

Update the function's docstring to add the three new semantic rules to the bullet list.

### Step 4 — Repository

Create `crmbuilder-v2/src/crmbuilder_v2/access/repositories/test_spec.py`. Mirror `entity.py` closely; the only structural deviations are (a) dual-axis status validation, (b) the cross-field invariant on outcome / last_run_at, and (c) the optional `record_run` convenience helper.

#### 4a — Module header

Docstring covering: the entity's role; the dual-axis status validation; the cross-field invariant; the `record_run` convenience helper that the API may expose; the soft-delete-does-not-cascade-references posture from §3.4.6.

#### 4b — Module constants

```python
_ENTITY_TYPE = "test_spec"
_IDENTIFIER_PREFIX = "TST"
_IDENTIFIER_RE = re.compile(r"^TST-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Patchable fields. ``identifier`` and timestamps are not patchable.
# ``last_run_outcome``, ``last_run_at``, ``last_run_notes`` are
# patchable individually; the convenience ``record_run`` helper bundles
# the typical three-field update for clients that prefer one call.
_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "description",
        "setup",
        "steps",
        "expected",
        "notes",
        "status",
        "last_run_outcome",
        "last_run_at",
        "last_run_notes",
    }
)

# Outcomes that require ``last_run_at`` to be populated. ``not_run`` is
# the only outcome for which ``last_run_at`` is permitted to be null;
# transitioning to ``not_run`` also clears ``last_run_at`` and
# ``last_run_notes`` per §3.4.4.
_RUN_OUTCOMES = frozenset({"passing", "failing", "skipped"})
```

#### 4c — Validation helpers

Same shape as `entity.py`'s `_require_identifier_format`, `_require_nonempty`, `_check_transition`, `_reject_duplicate_name`, `_get_row`, `_increment_identifier`. Two additional helpers:

```python
def _require_status(status: object) -> str:
    if status not in TEST_SPEC_STATUSES:
        raise UnprocessableError([
            FieldError(
                "test_spec_status",
                "invalid_value",
                f"must be one of {sorted(TEST_SPEC_STATUSES)}",
            )
        ])
    return status  # type: ignore[return-value]


def _require_outcome(outcome: object) -> str:
    if outcome not in TEST_SPEC_RUN_OUTCOMES:
        raise UnprocessableError([
            FieldError(
                "test_spec_last_run_outcome",
                "invalid_value",
                f"must be one of {sorted(TEST_SPEC_RUN_OUTCOMES)}",
            )
        ])
    return outcome  # type: ignore[return-value]
```

`_check_transition` reads from `TEST_SPEC_STATUS_TRANSITIONS` — no transition map for outcomes (the access layer accepts any outcome → outcome transition; CHECK enforces enum membership).

#### 4d — Cross-field invariant helper

```python
def _apply_outcome_invariant(
    row: TestSpec,
    *,
    requested_outcome: str | None,
    requested_last_run_at: datetime | None,
    last_run_at_supplied: bool,
) -> None:
    """Enforce the §3.4.4 cross-field invariant.

    Caller passes the requested outcome (after enum validation) and the
    requested ``last_run_at`` if any, plus a sentinel
    ``last_run_at_supplied`` distinguishing an explicit ``None`` (client
    requested clear) from an omitted value (client did not touch).

    Behavior:

    * Outcome moves to ``not_run`` — server clears ``last_run_at`` and
      ``last_run_notes`` regardless of what the client supplied.
    * Outcome moves to a run state (``passing`` / ``failing`` /
      ``skipped``) — if client supplied ``last_run_at`` explicitly as
      ``None`` while requesting a run-state outcome, raise 422; else if
      client supplied a non-null value use it; else server sets to
      ``datetime.now(UTC)``.
    * Outcome unchanged — no-op on ``last_run_at`` / ``last_run_notes``
      (caller's other update logic may still touch them).
    """
    if requested_outcome == "not_run":
        row.test_spec_last_run_outcome = "not_run"
        row.test_spec_last_run_at = None
        row.test_spec_last_run_notes = None
        return
    if requested_outcome in _RUN_OUTCOMES:
        row.test_spec_last_run_outcome = requested_outcome
        if last_run_at_supplied and requested_last_run_at is None:
            raise UnprocessableError([
                FieldError(
                    "test_spec_last_run_at",
                    "required_when_outcome_is_run_state",
                    "test_spec_last_run_at cannot be null when outcome "
                    "is passing/failing/skipped",
                )
            ])
        if requested_last_run_at is not None:
            row.test_spec_last_run_at = requested_last_run_at
        elif row.test_spec_last_run_at is None:
            row.test_spec_last_run_at = datetime.now(UTC)
```

This is the **load-bearing helper for §3.4.4**. Test it directly in the access tests.

#### 4e — Reads

`list_test_specs(session, *, include_deleted=False)`, `get_test_spec(session, identifier, *, include_deleted=False)`, `next_test_spec_identifier(session)`. Identical pattern to `entity.py`.

#### 4f — Writes

`create_test_spec(session, *, name, description, steps, expected, setup=None, notes=None, status="candidate", last_run_outcome="not_run", last_run_at=None, last_run_notes=None, identifier=None)`. Validation order:

1. `_require_nonempty(name, ...)`, `_require_nonempty(description, ...)`, `_require_nonempty(steps, ...)`, `_require_nonempty(expected, ...)`.
2. `_require_status(status)`, `_require_outcome(last_run_outcome)`.
3. `_reject_duplicate_name(session, name)`.
4. Identifier path: server-assigned via `_insert_with_autoassign(...)` if `identifier is None`; else `_require_identifier_format` + collision check + direct add.
5. After the row is added (with whatever the caller passed for outcome / last_run_at / last_run_notes), call `_apply_outcome_invariant(row, requested_outcome=last_run_outcome, requested_last_run_at=last_run_at, last_run_at_supplied=(last_run_at is not None or last_run_outcome != "not_run"))` to enforce the cross-field rule on create paths too — a POST that creates a test spec already in a run state must auto-populate `last_run_at`. Adjust the `last_run_at_supplied` flag semantics if the API layer needs richer "did the client explicitly set this" signaling (the cleanest path is for the API layer to pass `last_run_at=...` only when present in `model_dump(exclude_unset=True)`).
6. `emit(...)` change log.
7. Return `to_dict(row)`.

`update_test_spec(session, identifier, **all_replace_fields)` (full PUT). Same pattern as `entity.py`'s `update_entity`, plus the outcome / last_run handling. PUT carries the full record so all fields are replaced; the invariant helper runs at the end.

`patch_test_spec(session, identifier, **fields)`. Validate unknown keys against `_PATCHABLE_FIELDS`. Apply each known field; for status, run transition check; for outcome / last_run_at / last_run_notes, defer to the invariant helper at the end of the patch. The patch's "last_run_at supplied?" signal comes from whether `"last_run_at" in fields`.

`delete_test_spec(session, identifier)`, `restore_test_spec(session, identifier)`. Same pattern as `entity.py`. The delete does NOT cascade references.

#### 4g — Convenience helper `record_run`

```python
def record_run(
    session: Session,
    identifier: str,
    *,
    outcome: str,
    notes: str | None = None,
    at: datetime | None = None,
) -> dict:
    """Convenience: atomic update of outcome + last_run_at + last_run_notes.

    Per ``test_spec.md`` §3.8.1's open question. Recommendation from the
    spec: ship this in v0.5+ — the PATCH endpoint can already do the
    same three-field update, but the dedicated endpoint surfaces a
    clearer intent for automation callers and matches the
    methodology-vs-execution principle that ``test_spec.md`` §3.4.3
    articulates (outcome is observational; recording a run is one
    semantic operation, not a generic field-patch).

    If ``at`` is omitted, the server uses ``datetime.now(UTC)``. If
    ``outcome == "not_run"``, ``last_run_at`` and ``last_run_notes``
    are cleared regardless of supplied values, per the cross-field
    invariant in §3.4.4.
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
        row.test_spec_last_run_notes = notes  # may be None; that's fine
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after
```

### Step 5 — Pydantic schemas

Edit `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py`. Add four classes in a `# ---------- Test Specs ----------` block, mirroring the entity block at lines 186–227.

```python
class TestSpecCreateIn(_Base):
    """POST /test-specs body."""

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
    """PUT /test-specs/{identifier} body — full record replace."""

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
    """PATCH /test-specs/{identifier} body — partial update."""

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
    """POST /test-specs/{identifier}/record-run body — convenience.

    Atomic update of ``last_run_outcome``, ``last_run_at``,
    ``last_run_notes`` per ``test_spec.md`` §3.8.1. ``at`` is
    server-set to ``datetime.now(UTC)`` when omitted.
    """

    outcome: str
    notes: str | None = None
    at: datetime | None = None
```

Add `from datetime import datetime` near the top if not present.

### Step 6 — Router

Create `crmbuilder-v2/src/crmbuilder_v2/api/routers/test_specs.py`. Mirror `entities.py`. Endpoints:

- `GET /test-specs` (with `?include_deleted=true`)
- `GET /test-specs/next-identifier`
- `GET /test-specs/{identifier}`
- `POST /test-specs` (status 201)
- `PUT /test-specs/{identifier}`
- `PATCH /test-specs/{identifier}` — body-key-strip via the same `_FIELD_PREFIX = "test_spec_"` pattern, with `exclude_unset=True` to distinguish explicit-null from omitted (load-bearing for the §3.4.4 invariant)
- `DELETE /test-specs/{identifier}`
- `POST /test-specs/{identifier}/restore`
- `POST /test-specs/{identifier}/record-run` — the convenience endpoint

Use `crmbuilder_v2.access.repositories.test_spec` as the import; `readonly_session()` / `writable_session()` as in `entities.py`; `ok(...)` as the envelope wrapper.

The PATCH handler must distinguish `last_run_at` explicitly supplied as `null` from `last_run_at` omitted. Because `TestSpecPatchIn.test_spec_last_run_at` is `datetime | None = None`, the only signal is `model_dump(exclude_unset=True)`. The router's `provided` dict from `model_dump(exclude_unset=True)` correctly omits unset fields; the access layer then sees `"last_run_at" in fields` as the "supplied" signal. Document this in the router's docstring.

### Step 7 — main.py wiring

Edit `crmbuilder-v2/src/crmbuilder_v2/api/main.py`. Add `test_specs` to the router import list (alphabetical placement in the methodology group) and call `app.include_router(test_specs.router)` after `app.include_router(crm_candidates.router)` (preserving the v0.4 methodology block ordering).

### Step 8 — UI client

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/client.py`. Add a Test Specs section after the CRM Candidates section. Standard seven methods plus one convenience:

- `list_test_specs(self, *, include_deleted=False) -> list[dict]`
- `get_test_spec(self, identifier: str) -> dict`
- `create_test_spec(self, body: dict) -> dict`
- `update_test_spec(self, identifier: str, body: dict) -> dict`
- `patch_test_spec(self, identifier: str, body: dict) -> dict`
- `delete_test_spec(self, identifier: str) -> Any`
- `restore_test_spec(self, identifier: str) -> dict`
- `next_test_spec_identifier(self) -> str`
- `record_test_spec_run(self, identifier: str, body: dict) -> dict` — calls `POST /test-specs/{identifier}/record-run`. Body shape: `{"outcome": "passing", "notes": "...", "at": "2026-05-25T..."}`. The `at` field is optional.

Match the existing pattern: each method returns the unwrapped `data` from the `ok(...)` envelope per the `_request(...)` helper's existing behavior.

### Step 9 — Sidebar

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py`. Insert `"Test Specs"` into the Methodology group at the position resolved in Pre-flight step 6 (best-effort). Add a brief comment naming PI-004 sibling-ordering finalization as deferred.

### Step 10 — Main window dispatch

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py`:

1. Import the panel: `from crmbuilder_v2.ui.panels.test_spec import TestSpecsPanel`.
2. Add an `elif entry == "Test Specs":` branch in the sidebar-dispatch loop near line 152, mirroring the `Entities` branch.
3. Add `"test_spec": "Test Specs",` to `ENTITY_TYPE_TO_SIDEBAR_LABEL` in the Methodology block alongside `"entity": "Entities"`.

### Step 11 — Panel

Create `crmbuilder-v2/src/crmbuilder_v2/ui/panels/test_spec.py`. Mirror `entities.py` (the closest reference because it already renders an outgoing-edge `ReferencesSection`). Three deviations to attend to:

1. **Five columns** per §3.6.2:

   ```python
   def list_columns(self) -> list[ColumnSpec]:
       return [
           ColumnSpec(field="test_spec_identifier", title="Identifier", width=120),
           ColumnSpec(field="test_spec_name", title="Name"),
           ColumnSpec(field="test_spec_status", title="Status", width=110),
           ColumnSpec(
               field="test_spec_last_run_outcome",
               title="Last Run",
               width=110,
           ),
           ColumnSpec(field="test_spec_updated_at", title="Updated", width=180),
       ]
   ```

2. **Color-cued Last Run column — UI deviation per §3.6.2.** The label text is always shown; color is additive. Implementation hooks depend on the `ListDetailPanel` base — inspect the existing `ColumnSpec` shape and the table-model class it instantiates. If `ColumnSpec` supports a `cell_style_for_value` callback or similar, use it. If not, the cleanest path is a small `QStyledItemDelegate` subclass attached only to the Last Run column post-construction in `__init__`, after `super().__init__(...)` has built the master view. Color tokens:

   - `passing` → `t("color.success.default")` (or fallback `#1b7e1b` green)
   - `failing` → `t("color.danger.default")` (or fallback `#b41a1a` red)
   - `not_run` → `t("color.neutral.500")` (or fallback `#888888` gray)
   - `skipped` → `t("color.warning.default")` (or fallback `#c0830d` amber)

   If the design-token names differ, resolve via `crmbuilder_v2.ui.styling.t(...)` lookups; fall back to the hex literals above. Document the styling deviation inline.

3. **Three-section detail pane** per §3.6.3. The base pattern is `EntitiesPanel.render_detail`; extend it to three explicit subsection headers between groups of fields. Use `_separator()` between sections and a small bold label widget for each subsection header (`Test body`, `Last run`). Fields and layout:

   - **Identity-and-methodology block:** Identifier (read-only label), Name (read-only line), Description (read-only multiline, placeholder "What does this test verify?"), Status (combo, disabled — same hint-caption treatment as `EntitiesPanel`).
   - `_separator()` + bold "Test body" subsection label.
   - **Test body block:** Setup (read-only multiline, placeholder "Preconditions — what must be true before the test runs?"), Steps (read-only multiline, placeholder "Numbered steps to execute the test"), Expected (read-only multiline, placeholder "Expected results — what must be true after the steps execute?").
   - `_separator()` + bold "Last run" subsection label.
   - **Last run block:** Last Run Outcome (combo with the four outcome values; disabled because editing happens in the dialog), Last Run At (read-only display of the datetime or "—"), Last Run Notes (read-only multiline). Optionally also render a small color swatch beside the Last Run Outcome combo to mirror the master-pane cue.
   - **Internal notes block:** `CollapsibleSection("Internal notes", notes_value, expanded=False)` — same as `EntitiesPanel`.
   - **References section:** `ReferencesSection("test_spec", identifier, extras.get("references") or {}, client=self._client)`.

4. **Record Run button.** Append to the action strip (next to Edit/Delete) a "Record run" button visible when the test spec is not soft-deleted. Click handler opens a small modal — see Step 12c for the dialog shape.

The button strip and the master-pane delegate are the only structural deviations from `EntitiesPanel`. Right-click context menu, fetch hooks, refresh handling, navigation signals, and identifier addressing all carry forward unchanged.

### Step 12 — Dialogs

#### 12a — `_test_spec_schema.py`

Create `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_test_spec_schema.py`. Mirror `_entity_schema.py`. Two helper functions:

- `status_choices(current: str | None) -> list[str]` — restricts to current + valid successors per `TEST_SPEC_STATUS_TRANSITIONS`. Returns the three-value full set when `current` is `None` or unknown.
- `run_outcome_choices(current: str | None) -> list[str]` — returns the full four-value set always (no transition restrictions). Sorted alphabetically for stable UI order: `["failing", "not_run", "passing", "skipped"]`.

Field schema:

```python
_IDENTIFIER_FIELD = FieldSchema(
    key="test_spec_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(key="test_spec_name", label="Name", widget="line", required=True),
    FieldSchema(
        key="test_spec_description",
        label="Description",
        widget="text",
        required=True,
        placeholder="What does this test verify?",
    ),
    FieldSchema(
        key="test_spec_setup",
        label="Setup",
        widget="text",
        placeholder="Preconditions — what must be true before the test runs?",
    ),
    FieldSchema(
        key="test_spec_steps",
        label="Steps",
        widget="text",
        required=True,
        placeholder="Numbered steps to execute the test",
    ),
    FieldSchema(
        key="test_spec_expected",
        label="Expected results",
        widget="text",
        required=True,
        placeholder="Expected results — what must be true after the steps execute?",
    ),
    FieldSchema(key="test_spec_notes", label="Internal notes", widget="text"),
    FieldSchema(
        key="test_spec_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=TEST_SPEC_STATUSES,
        default="candidate",
        compute_options=lambda state: status_choices(state.get("test_spec_status")),
    ),
    FieldSchema(
        key="test_spec_last_run_outcome",
        label="Last run outcome",
        widget="combo",
        required=True,
        vocab=TEST_SPEC_RUN_OUTCOMES,
        default="not_run",
        compute_options=lambda state: run_outcome_choices(
            state.get("test_spec_last_run_outcome")
        ),
    ),
    FieldSchema(
        key="test_spec_last_run_at",
        label="Last run at",
        widget="datetime",  # if not supported by the base, fall back to "line"
                            # with a parseable ISO-8601 placeholder and a
                            # post-submit normalization step
    ),
    FieldSchema(
        key="test_spec_last_run_notes",
        label="Last run notes",
        widget="text",
    ),
]
```

`entity_fields(*, include_identifier: bool)` factory follows `_entity_schema.py`'s shape.

If the `crud_dialog` base does not support `widget="datetime"`, fall back to `widget="line"` and document the deferral. The §3.4.4 server-side invariant makes the UI's `last_run_at` field optional — if the user picks an outcome of `passing`/`failing`/`skipped` and leaves `last_run_at` blank, the server fills it in. The dialog should communicate this with a placeholder ("Auto-set to now when outcome moves to a run state").

#### 12b — `test_spec_crud.py`

Create `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/test_spec_crud.py`. Mirror `entity_crud.py`'s three classes:

- `TestSpecCreateDialog(EntityCrudDialog)` — passes `entity_fields(include_identifier=False)`, `create_method=client.create_test_spec`, `identifier_field="test_spec_identifier"`.
- `TestSpecEditDialog(EntityCrudDialog)` — passes `entity_fields(include_identifier=True)`, `update_method=client.patch_test_spec`, `record=record`.
- `TestSpecDeleteDialog(EntityCrudDeleteDialog)` — edge-text confirmation against the `TST-NNN` identifier, body text noting that outgoing references persist.

#### 12c — Record-run sub-dialog

Add a small `TestSpecRecordRunDialog(QDialog)` in `test_spec_crud.py` (or a sibling file). Fields:

- Outcome (combo, four values, default to whatever the current outcome is).
- Notes (multiline text).
- At (datetime picker, optional; placeholder "Leave blank to use now").

On accept, calls `client.record_test_spec_run(identifier, body={...})` and returns. Per project memory `project_qt_worker_widget_gc_hazard.md`, transient modal sub-dialogs opened from a parent need `deleteLater()` on close — pattern the dialog's cleanup accordingly.

The panel's "Record run" button click handler instantiates this dialog, exec's it, and refreshes the panel on accept.

### Step 13 — Tests

Add ≥20 tests across three locations. Mirror the existing entity-test files.

#### 13a — `tests/crmbuilder_v2/access/test_test_spec.py` (≥12 tests)

Cover (with one assertion-group per test, descriptive names):

1. `test_create_with_minimum_fields_assigns_identifier` — auto-assignment yields `TST-001`.
2. `test_create_with_explicit_identifier` — supplying `TST-005` succeeds; second call collides → 409.
3. `test_create_rejects_malformed_identifier` — `"tst-001"`, `"TST-1"`, `"TS-001"` → 422.
4. `test_create_rejects_duplicate_name_case_insensitive` — two creates with names `"Mentor app"` and `"MENTOR APP"` → 422 on the second.
5. `test_create_defaults_status_and_outcome` — omitting `status` → `candidate`; omitting `last_run_outcome` → `not_run`; `last_run_at` stays null.
6. `test_status_transition_valid` — `candidate → confirmed`, `confirmed → deferred`, `deferred → confirmed` all succeed.
7. `test_status_transition_invalid_rejected` — `confirmed → candidate` raises `StatusTransitionError` (mapping to HTTP 422).
8. `test_outcome_transitions_unrestricted` — `not_run → passing → failing → skipped → not_run` all succeed; the access layer does not raise on any outcome→outcome move.
9. `test_outcome_to_run_state_auto_sets_last_run_at` — patch `last_run_outcome=passing` without supplying `last_run_at`; row's `last_run_at` is now within 5 seconds of `datetime.now(UTC)`.
10. `test_outcome_to_run_state_with_explicit_last_run_at` — patch supplies both; the explicit value is honored.
11. `test_outcome_to_run_state_with_explicit_null_last_run_at_rejected` — patch `last_run_outcome=passing, last_run_at=None` raises 422.
12. `test_outcome_to_not_run_clears_last_run_fields` — set up a row with `passing` + `last_run_at` + `last_run_notes`, patch `last_run_outcome=not_run`; row's `last_run_at` and `last_run_notes` are both `None`.
13. `test_record_run_helper_success` — call `record_run(session, "TST-001", outcome="passing", notes="ok", at=None)`; row's outcome, last_run_at (auto-set), last_run_notes all reflect.
14. `test_record_run_helper_resets_to_not_run` — call `record_run(..., outcome="not_run", notes="re-staging")`; outcome is `not_run`, last_run_at and last_run_notes both cleared (the notes argument is ignored when transitioning to `not_run` because the invariant always clears).
15. `test_soft_delete_does_not_cascade_outgoing_refs` — create test spec + entity, attach `test_spec_touches_entity` reference, soft-delete the test spec; assert the references row still exists.

#### 13b — `tests/crmbuilder_v2/api/test_test_specs_api.py` (≥6 tests)

Cover the REST envelope shape and routing:

1. `test_post_minimum_returns_201_with_envelope` — POST body with name/description/steps/expected; assert response JSON has `data.test_spec_identifier == "TST-001"`, `errors` is null.
2. `test_post_with_status_transition_error_returns_422_with_transition_body` — create + PATCH `status=candidate` from `confirmed`; assert body is `{"error": "invalid_status_transition", "from": "confirmed", "to": "candidate"}`.
3. `test_patch_outcome_to_passing_auto_sets_last_run_at` — assert the returned row's `last_run_at` is present and non-null.
4. `test_patch_outcome_to_not_run_clears_fields` — assert the returned row's `last_run_at` and `last_run_notes` are null.
5. `test_record_run_endpoint_round_trip` — POST `/test-specs/TST-001/record-run` with `{"outcome": "passing", "notes": "ok"}`; assert 200 with the updated record envelope-wrapped.
6. `test_next_identifier_endpoint` — GET `/test-specs/next-identifier` returns `{"data": {"next": "TST-001"}, ...}` on an empty table.
7. `test_post_references_test_spec_touches_entity_round_trip` — create an entity + test spec, POST `/references` with `(test_spec, TST-001, entity, ENT-001, test_spec_touches_entity)`; assert 201; assert the reference is visible from both ends.

#### 13c — `tests/crmbuilder_v2/ui/test_test_specs_panel.py` (≥4 tests)

Use the existing UI test fixtures (Qt application, fake client). Smoke-test only — the panel patterns are well-trodden by `entities.py`.

1. `test_panel_lists_five_columns` — instantiate `TestSpecsPanel`, mock the client to return one row, assert the master-view model exposes five column headers including "Last Run".
2. `test_master_pane_color_cue_applied_for_each_outcome` — supply four rows with the four outcomes; assert the delegate / cell-style hook applies the corresponding color (use the delegate's helper directly rather than rendering pixels).
3. `test_detail_pane_shows_three_subsection_headers` — render detail for one row, assert the rendered widget contains labels "Test body" and "Last run" and a `CollapsibleSection` titled "Internal notes".
4. `test_record_run_button_opens_dialog_and_refreshes_on_accept` — click the Record Run button on the rendered detail, assert the dialog is shown, fake an accept, assert `client.record_test_spec_run` was called and `refresh` was invoked.

### Step 14 — Run the test suite

```bash
uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -50
```

Expected: baseline + 20-or-more new tests passing. Halt and report if any previously-passing test now fails.

### Step 15 — Apply the migration to the running engagement DB

```bash
cd crmbuilder-v2
uv run alembic upgrade head 2>&1
uv run alembic current 2>&1
# Expected: 00XX_v0_5_create_test_specs_table (head)
cd ..
```

Spot-check the schema via the v2 access layer (project memory notes Doug's local has no sqlite3 CLI):

```bash
uv run python -c "
from crmbuilder_v2.access.db import session_scope
from sqlalchemy import text
with session_scope() as s:
    rows = list(s.execute(text(\"SELECT name FROM sqlite_master WHERE type='table' AND name='test_specs'\")))
    print(f'test_specs table present: {len(rows) == 1}')
"
```

### Step 16 — End-to-end verification against the running API

Confirm the API is running (`crmbuilder-v2-api &` if not). All requests unwrap `.data` from the envelope per the CLAUDE.md convention.

```bash
# 1. POST a test spec.
curl -sS -X POST http://127.0.0.1:8765/test-specs \
  -H 'Content-Type: application/json' \
  -d '{"test_spec_name":"smoke test","test_spec_description":"smoke","test_spec_steps":"do it","test_spec_expected":"it works"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('identifier:', d['data']['test_spec_identifier']); print('status:', d['data']['test_spec_status']); print('outcome:', d['data']['test_spec_last_run_outcome']); print('last_run_at:', d['data']['test_spec_last_run_at'])"
# Expected: identifier: TST-001 ; status: candidate ; outcome: not_run ; last_run_at: None

# 2. PATCH outcome to passing without supplying last_run_at.
curl -sS -X PATCH http://127.0.0.1:8765/test-specs/TST-001 \
  -H 'Content-Type: application/json' \
  -d '{"test_spec_last_run_outcome":"passing"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('outcome:', d['data']['test_spec_last_run_outcome']); print('last_run_at:', d['data']['test_spec_last_run_at'])"
# Expected: outcome: passing ; last_run_at: 2026-05-... (non-null)

# 3. PATCH outcome back to not_run.
curl -sS -X PATCH http://127.0.0.1:8765/test-specs/TST-001 \
  -H 'Content-Type: application/json' \
  -d '{"test_spec_last_run_outcome":"not_run"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('outcome:', d['data']['test_spec_last_run_outcome']); print('last_run_at:', d['data']['test_spec_last_run_at']); print('notes:', d['data']['test_spec_last_run_notes'])"
# Expected: outcome: not_run ; last_run_at: None ; notes: None

# 4. Record-run convenience.
curl -sS -X POST http://127.0.0.1:8765/test-specs/TST-001/record-run \
  -H 'Content-Type: application/json' \
  -d '{"outcome":"failing","notes":"step 4 timeout"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('outcome:', d['data']['test_spec_last_run_outcome']); print('notes:', d['data']['test_spec_last_run_notes'])"
# Expected: outcome: failing ; notes: step 4 timeout

# 5. Disallowed status transition.
curl -sS -X PATCH http://127.0.0.1:8765/test-specs/TST-001 \
  -H 'Content-Type: application/json' \
  -d '{"test_spec_status":"confirmed"}'
curl -sS -X PATCH http://127.0.0.1:8765/test-specs/TST-001 \
  -H 'Content-Type: application/json' \
  -d '{"test_spec_status":"candidate"}'
# Expected on second: HTTP 422 with body {"error":"invalid_status_transition","from":"confirmed","to":"candidate"}.

# 6. Identifier helper.
curl -sS http://127.0.0.1:8765/test-specs/next-identifier \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['next'])"
# Expected: TST-002 (one test spec exists).
```

If any check fails, halt and report.

### Step 17 — Smoke-test the panel in the desktop app

`uv run crmbuilder-v2-ui` (or whatever the project's launcher is). Expected:

- "Test Specs" appears under the Methodology sidebar group at the position chosen in Pre-flight step 6.
- Master pane shows five columns; the Last Run column for `TST-001` shows the color cue (red because it was last set to `failing` in Step 16).
- Detail pane shows the three subsection headers; Internal notes section is collapsed by default.
- New / Edit / Delete / Record Run buttons appear; Edit dialog opens with `test_spec_identifier` read-only.

---

## Close-out

### PI-004 build-closure rule (read this carefully)

PI-004's resolution scope is four sibling methodology entity types: `field`, `requirement`, `manual_config`, `test_spec`. The PI resolves when the **last** sibling lands; intermediate sessions only address it. Determine which kind of close-out this session is doing **at close-out time** (not at build start, because parallel-sandbox work may shift the picture during the build).

#### Pre-close-out PI-004 status query

Run these queries against the live API (envelope-aware: unwrap `.data`):

```bash
# Inspect addresses_planning_items edges pointing at PI-004 from sessions.
curl -sS 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=addresses' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin).get('data') or []
print(f'Addressing references on PI-004: {len(data)}')
for r in data:
    print(f\"  {r['reference_identifier']}: {r['source_type']} {r['source_id']} -> PI-004\")
"

# Inspect resolves_planning_items edges (any conversation already resolved it?).
curl -sS 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=resolves' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin).get('data') or []
print(f'Resolving references on PI-004: {len(data)}')
for r in data:
    print(f\"  {r['reference_identifier']}: {r['source_type']} {r['source_id']} -> PI-004\")
"

# Inspect the addressing source sessions to see which sibling each represents.
# (Look at session names / topics for the field / requirement / manual_config /
# test_spec keyword.)
for ses in <session-identifiers-from-the-first-query>; do
    curl -sS "http://127.0.0.1:8765/sessions/${ses}" \
      | python3 -c "
import sys, json
d = json.load(sys.stdin).get('data') or {}
print(f\"  {d.get('identifier')}: {d.get('name')}\")
"
done
```

Decision tree:

- If `Resolving references on PI-004` is non-zero — PI-004 has already been resolved by a previous conversation. This session uses `addresses_planning_items` only.
- Else, count distinct sibling categories represented in the addressing sessions (look at session names — "field", "requirement", "manual_config" keywords). If the addressing sessions cover all three of the other siblings (FLD / REQ / MCF) — this session is the closer. Set `resolves_planning_items: [{"planning_item_identifier": "PI-004"}]` in the close-out payload.
- Else — this session is an intermediate. Set `addresses_planning_items: [{"planning_item_identifier": "PI-004"}]` and leave `resolves_planning_items: []`.

When in doubt (the address-vs-resolve signal is unclear from session naming or PI-004 has accreted extra addressing sessions from work outside the four-sibling scope), prefer `addresses` over `resolves`. A subsequent conversation can author a small close-out that adds the missing `resolves` edge; an erroneous early `resolves` is harder to retract because it auto-flips the PI status per PI-030 slice A.

### Close-out artifacts (the standard triple)

Per CLAUDE.md "v2 session lifecycle — closing a session":

1. **Content deliverable** — this slice's code commits.
2. **Close-out payload** at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` — nine-section v0.8 shape: `session`, `conversation`, `work_tickets`, `planning_items`, `commits`, `decisions`, `references`, `resolves_planning_items`, `addresses_planning_items`. Pick the next available SES-NNN by checking `list_recent_sessions(limit=3)` (parallel-sandbox identifier-collision contingency per CLAUDE.md).
3. **Apply prompt** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md` — pre-flight checks, the apply command, post-apply verification fingerprints (envelope-aware per CLAUDE.md note about the `{data, meta, errors}` envelope and the canonical post-fix example at `apply-close-out-ses-025.md`).

### Decisions to author

At least four DECs (numbered TBD at payload-generation time; placeholders are fine because `apply_close_out.py` will renumber if collisions appear):

1. **DEC-(TBD) — `test_spec` identifier prefix and format.** `TST` under the soft-3-letter posture per DEC-044.
2. **DEC-(TBD) — `test_spec` field inventory and dual-axis state.** Twelve substantive columns plus three timestamps. Three plain-text body fields (`setup`/`steps`/`expected`) rather than collapsed. Dual-axis state separating methodology lifecycle (`status`) from execution outcome (`last_run_outcome`), with the cross-field invariant requiring `last_run_at` whenever outcome is a run state.
3. **DEC-(TBD) — `test_spec` API surface choice on `record-run` convenience.** Shipped at first release rather than deferred — clearer intent for automation and matches the methodology-vs-execution principle.
4. **DEC-(TBD) — `test_spec` UI deviation: color-cued Last Run column.** Rationale per spec §3.6.2 — verification health changes on each run, drives immediate action, is the primary glance-level information from this panel.

The third and fourth decisions are the load-bearing ones from a methodology-precedent standpoint; the spec-referenced "open questions to settle" at §3.8.1 close on those choices.

### Commits

Bundle into two commits:

**Commit 1 — Migration + access layer + REST.** Stage and commit:

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

Lands the test_spec entity per test_spec.md v1.0:
- Migration 00XX: test_specs table (15 columns); refs CHECK extension for
  'test_spec' source/target and three new kinds (test_spec_touches_entity,
  test_spec_touches_field, test_spec_exercises_process); change_log CHECK
  extension for 'test_spec'.
- vocab.py: TEST_SPEC_STATUSES + TEST_SPEC_STATUS_TRANSITIONS (three-status
  propose-verify, mirrors entity/domain), TEST_SPEC_RUN_OUTCOMES (four
  values, unrestricted transitions), three kinds in REFERENCE_RELATIONSHIPS,
  three new _kinds_for_pair clauses.
- Access layer: dual-axis status validation, cross-field invariant on
  outcome / last_run_at (§3.4.4 — server auto-sets when moving to a run
  state, auto-clears when moving to not_run), record_run convenience
  helper.
- REST: eight standard endpoints + POST /test-specs/{id}/record-run for
  automation callers. {data, meta, errors} envelope throughout.
EOF
)"

git pull --rebase origin main
```

Wait for Doug's push approval.

**Commit 2 — UI panel + dialogs + sidebar wiring.** Stage and commit after Doug pushes commit 1:

```bash
git add crmbuilder-v2/src/crmbuilder_v2/ui/client.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/panels/test_spec.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_test_spec_schema.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/test_spec_crud.py
git add tests/crmbuilder_v2/ui/test_test_specs_panel.py

git commit -m "$(cat <<'EOF'
v2: PI-004 — test_spec UI panel, dialogs, sidebar wiring

Lands the Test Specs panel per test_spec.md §3.6:
- Sidebar: "Test Specs" added to Methodology group.
- Main-window dispatch: TestSpecsPanel for the new entry.
- Panel: five-column master pane (Identifier / Name / Status / Last Run
  / Updated) with color-cued Last Run column (passing green, failing
  red, not_run gray, skipped amber) per §3.6.2 UI deviation. Three-
  subsection detail pane (identity-and-methodology / test body / last
  run / collapsible internal notes / references) per §3.6.3.
- Dialogs: TestSpec{Create,Edit,Delete}Dialog + TestSpecRecordRunDialog
  for the convenience record-run path.
- UI client: nine methods including record_test_spec_run for the
  convenience endpoint.
- Tests: panel + delegate smoke tests.
EOF
)"

git pull --rebase origin main
```

Wait for Doug's push approval.

**Commit 3 — Close-out artifacts.** After both commits land:

```bash
# Apply the close-out payload (which records SES + conversation + work
# tickets + decisions + references + commits + addresses/resolves
# planning items in one atomic transaction).
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
db-export snapshots for the test_spec build conversation. {addresses
| resolves}_planning_items per the PI-004 build-closure rule (set at
close-out time based on sibling addressing-edge count).
EOF
)"

git pull --rebase origin main
```

Wait for Doug's push approval.

---

## Done

Reply with:

- Pre-build Alembic head: `<current head>`
- Post-migration Alembic head: `00XX_v0_5_create_test_specs_table`
- `test_specs` table present in engagement DB: True / False
- Test suite: pre-slice pass count vs post-slice pass count (+20 or more new tests expected)
- End-to-end verification (Step 16) all six checks passed: True / False
- Desktop smoke test (Step 17) all four expectations met: True / False
- PI-004 close-out rule decision: `resolves` or `addresses`, with the addressing-sibling count that drove it
- Commit SHAs: `<sha1>`, `<sha2>`, `<sha3>`
- Decisions authored: DEC-NNN through DEC-NNN (post-payload-renumber)
- Session identifier: SES-NNN
- Convenience endpoint shipped: `POST /test-specs/{id}/record-run` — Yes (per the spec-§3.8.1 recommendation)
- Sidebar position chosen for "Test Specs": `<position-name>` (after `<sibling-or-CRM-Candidates>`)
- Next prompt to run: whichever PI-004 sibling has not yet built (`field`, `requirement`, `manual_config`, or `persona` per PI-003), or — if this session was the closer — none; PI-004 is resolved.
