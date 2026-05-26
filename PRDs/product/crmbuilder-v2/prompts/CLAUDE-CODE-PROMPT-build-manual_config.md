# CLAUDE-CODE-PROMPT-build-manual_config

**Last Updated:** 05-25-26
**Operating mode:** DETAIL
**Series:** PI-004 (additional methodology entity types for v0.5+)
**Slice:** manual_config — the third PI-004 sibling (alongside `field`, `requirement`, `test_spec`)
**Status:** Ready to execute. Blocked by: nothing — `manual_config.md` spec is canonical.
**Companions:**
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/manual_config.md` v1.0 — authoritative spec.
- `crmbuilder-v2/migrations/versions/0008_v0_4_create_entities_table.py` — closest table-creation migration pattern.
- `crmbuilder-v2/migrations/versions/0011_v0_7_governance_entities.py` — CHECK-extension + new-table pattern for the refs/change_log surface.
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/entity.py` — repository scaffold to mirror for the standard transition-validated body.
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/crm_candidate.py` — closest analogue for a non-three-status lifecycle with a singleton-style cross-field invariant.

---

## Purpose

Land the `manual_config` methodology entity end-to-end per `manual_config.md` v1.0 — schema migration, ORM model, vocabulary registration, repository, FastAPI router, request schemas, FastAPI app wiring, UI client methods, sidebar entry, main-window dispatch, panel, CRUD dialogs, and tests — satisfying the third sibling of PI-004 (after `field`, `requirement`, `test_spec`). Then close the session per the conventions in CLAUDE.md, applying the PI-004 build-closure rule below.

`manual_config` captures discrete pieces of CRM configuration that the deploy pipeline cannot apply automatically — saved views, duplicate-check rules, workflows, deferred-options enum fields, role/field-level permission grants, role-conditioned dynamic logic — and that a human operator must perform in the live CRM after deploy. The methodology layer needs these as queryable records so verification specs can target them, requirements can be realized by them, and consultants can produce stakeholder-facing "what your operator must do" lists.

Two posture points worth flagging up front because they shape the build:

- **Four-status lifecycle, not three.** The cross-spec default established by `domain.md`/`entity.md` is `candidate` / `confirmed` / `deferred`. This spec adds a terminal fourth status `completed` reachable only from `confirmed`, justified at length in `manual_config.md` §3.4.2. Treat this as deliberate, documented, and load-bearing — every place the build pattern reads "three statuses" or "no terminal state" you must consciously substitute the four-status shape.
- **Cross-field invariant on `completed`.** A transition into `completed` requires both `manual_config_completed_at` and `manual_config_completed_by` to be populated in the same write. The access layer enforces this with a dedicated error body (`{"error": "completed_status_requires_completion_fields", "missing": [...]}`). The repository may server-set `manual_config_completed_at` to now() if omitted on the `completed` transition; it must reject if `manual_config_completed_by` is omitted. There is no analogue for this in the four prior methodology entities — see `manual_config.md` §3.5.3 for the canonical rule.

---

## PI-004 build-closure rule (READ FIRST)

PI-004 covers four sibling entity types: `field`, `requirement`, `manual_config`, `test_spec`. PI-004 is **resolved** when the **last sibling lands** — not when the first or middle ones do.

The session running this prompt should perform two PI-004 status queries:

1. **At close-out drafting time** (immediately before authoring `ses_NNN.json`), enumerate the sibling-addressing edges on PI-004:

   ```bash
   curl -s 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=addresses' \
     | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(f'addresses edges: {len(d)}'); [print(f\"  {r['reference_identifier']}: {r['source_type']} {r['source_id']}\") for r in d]"
   ```

2. **Tier-2 verify the sibling delivery state** by listing the recent sessions and inspecting which sibling identifiers landed:

   ```bash
   curl -s 'http://127.0.0.1:8765/sessions?limit=10' \
     | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; [print(f\"{r.get('identifier','?')}: {r.get('summary','')}\") for r in d[:10]]"
   ```

Decision rule:

- If **all three other PI-004 siblings (`field`, `requirement`, `test_spec`) are already delivered** — i.e. each sibling has its own completed session with an `addresses` edge to PI-004 — then this `manual_config` session is the **closer**. Set `resolves_planning_items: [{"planning_item_identifier": "PI-004"}]` in the close-out payload. The atomic edge+flip per slice A of PI-030 will transition PI-004 from Open to Resolved.
- Otherwise, this session merely **advances** PI-004. Set `resolves_planning_items: []`. Use `addresses_planning_items: [{"planning_item_identifier": "PI-004"}]` to record the non-resolving advance.

**Do not perform this check at build start.** Sibling sessions may land in parallel sandboxes between session-open and session-close; the close-out posture must reflect the state at close-out, not the state at open. The check belongs in the close-out drafting step (step 16 below), not pre-flight.

If the contemporaneous `field`, `requirement`, or `test_spec` siblings have not yet been built and there's no way to tell from the v2 DB which sibling is the last, default to the non-resolving posture (`addresses_planning_items` only). It is safe to underclaim: a later session can author a brief PI-004 wrap-up with a resolving edge once the genuine last sibling lands.

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

5. **Tier 1 orientation read.** Re-read `/home/doug/Dropbox/Projects/crmbuilder/CLAUDE.md` end-to-end. Pay particular attention to:
   - The "v2 session lifecycle — opening a session" / "closing a session" / "planning item resolution" sections.
   - The "Reference relationship vocabulary lives in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`" note and the "Adding a new relationship kind requires updating both" rule.
   - The "v2 API responses use a `{data, meta, errors}` envelope" rule — every inlined `python3` snippet in this prompt unwraps `.data`.

6. **Tier 2 orientation (file-fallback).** Read these JSON snapshots to ground the session:
   - `PRDs/product/crmbuilder-v2/db-export/status.json`
   - `PRDs/product/crmbuilder-v2/db-export/charter.json` (most-recent version)
   - `PRDs/product/crmbuilder-v2/db-export/sessions.json` (tail; identify the next free `SES-NNN`)
   - `PRDs/product/crmbuilder-v2/db-export/decisions.json` (tail; identify the next free `DEC-NNN`)
   - `PRDs/product/crmbuilder-v2/db-export/planning_items.json` (find PI-004 and its current `addresses` neighbours)

7. **Read the authoritative spec.** Read `PRDs/product/crmbuilder-v2/methodology-schema-specs/manual_config.md` v1.0 end-to-end. Sections that materially shape this build:
   - §3.1 Identity — prefix `MCF`, justification.
   - §3.2 Fields — twelve columns total (identifier + name + description + category + instructions + notes + status + two completion + three timestamps).
   - §3.3 Relationships — four outbound kinds, references-entity mechanism, vocab + `_kinds_for_pair` + Alembic CHECK contributions.
   - §3.4 Lifecycle — four-status set, transition map, terminal `completed`, soft-delete-for-rejection posture.
   - §3.5.3 Status-transition and completed-field validation — the cross-field invariant unique to this spec.
   - §3.6 UI considerations — 5-column master pane; detail pane reveal rule for completion fields.
   - §3.7 Acceptance criteria — 16 testable statements; the test plan (step 14 below) covers them.

8. **Read the pattern references.** All four in parallel:
   - `crmbuilder-v2/migrations/versions/0008_v0_4_create_entities_table.py` — closest table-creation migration shape.
   - `crmbuilder-v2/migrations/versions/0011_v0_7_governance_entities.py` — `batch_alter_table` CHECK extension pattern for `refs.source_type`, `refs.target_type`, `refs.relationship_kind`, `change_log.entity_type`.
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/entity.py` — standard transition-validated repository; mirror this for the basic shape.
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/crm_candidate.py` — closest analogue for a non-three-status lifecycle with a singleton-style cross-field invariant (the `_reject_second_selected` helper pattern maps cleanly onto the completion-field invariant pattern this build needs).
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — vocabulary registration shape; the v0.8 Code Change Lifecycle additions at the end (`'resolves'`, `'addresses'`, `'blocked_by'`) are the freshest precedent for adding new kinds in bulk.

9. **Read the router + UI pattern files:**
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/entities.py` — 8-endpoint router skeleton.
   - `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` lines 189–227 — `EntityCreateIn`/`EntityReplaceIn`/`EntityPatchIn` Pydantic schemas.
   - `crmbuilder-v2/src/crmbuilder_v2/api/main.py` — router-registration list.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/entities.py` — panel pattern (master columns, detail pane, dialog wiring).
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/entity_crud.py` and `_entity_schema.py` — CRUD dialog scaffolds.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/crm_candidate_crud.py` and `_crm_candidate_schema.py` — non-standard-lifecycle CRUD pattern; the `status_choices(current)` helper is the model for the four-status combo restriction.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py` — `SIDEBAR_GROUPS` declaration; add the Methodology entry there.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` — `_entry_to_entity_type` map and the `elif entry == "Entities":` dispatch chain.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` lines ~660–795 — the entity-client-method block to mirror for the seven `manual_config` methods.

10. **Verify the v2 codebase is in place.** Confirm these directories exist and contain the expected files:

    ```bash
    ls -la crmbuilder-v2/src/crmbuilder_v2/access/repositories/
    ls -la crmbuilder-v2/src/crmbuilder_v2/api/routers/
    ls -la crmbuilder-v2/src/crmbuilder_v2/ui/panels/
    ls -la crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/
    ls -la crmbuilder-v2/migrations/versions/ | tail
    ```

    The most recent migration head should be `0012_v0_8_commits_and_blocked_by_rename` (or higher, if subsequent slices have landed). The next free migration number is whatever follows that head.

11. **Confirm the v2 API + meta DB are operational.** Run:

    ```bash
    curl -s http://127.0.0.1:8765/health | python3 -c "import sys, json; print(json.load(sys.stdin))"
    ```

    Expected: `{"status": "ok", ...}` or equivalent healthy shape. If the API is not running, start it (`uv run crmbuilder-v2-api &` from `crmbuilder-v2/`) and retry.

12. **Baseline the test suite.**

    ```bash
    cd crmbuilder-v2
    uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -30
    cd ..
    ```

    Note the pass count. The build adds ≥20 new tests; the post-build run must show no previously-passing test failing.

13. **Capture pre-migration Alembic head:**

    ```bash
    cd crmbuilder-v2
    uv run alembic current 2>&1
    cd ..
    ```

    Record the head value; the migration in step 2 builds on it.

14. **Capture pre-build identifier heads in the v2 DB** (for identifier collision avoidance per the SES-077 re-keying contingency):

    ```bash
    for endpoint in sessions decisions; do
      curl -s "http://127.0.0.1:8765/$endpoint" \
        | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; ids = sorted(r['identifier'] for r in d if r.get('identifier')); print(f'$endpoint: count={len(ids)}, tail={ids[-3:] if ids else []}')"
    done
    ```

    Note the next free identifiers. Verify the planned `SES-NNN` and `DEC-NNN` values for the close-out are not already claimed by parallel sandbox work.

---

## Implementation

The build is sequenced so each step's artifacts feed the next. Do not skip ahead — the model imports the migration's columns; the repository imports the model; the router imports the repository; the schemas feed the router; the UI client calls the router; the panel calls the client; the dialogs feed the panel; tests run against the whole stack.

### Step 1 — Author the schema migration

Create `crmbuilder-v2/migrations/versions/NNNN_v0_5_create_manual_configs_table.py` (replace `NNNN` with the next free four-digit number after the current Alembic head — `0013` if the head is `0012`). Pattern: combine `0008`'s `create_table` shape with `0011`'s `batch_alter_table` CHECK-extension shape.

Revision header:

```python
revision: str = "NNNN_v0_5_create_manual_configs_table"
down_revision: Union[str, None] = "<current head revision>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

The `upgrade()` function performs four operations in order:

**1a. Extend `refs.source_type` and `refs.target_type` CHECK constraints** to admit `'manual_config'`. Use `batch_alter_table("refs", recreate="always")`. Drop the existing source-type and target-type CHECK constraints by name (verify names by inspecting `0011`); create new CHECK constraints with the extended sorted-alphabetical set.

**1b. Extend `refs.relationship_kind` CHECK constraint** to admit the four new kinds — `'manual_config_scopes_to_domain'`, `'manual_config_touches_entity'`, `'manual_config_touches_field'`, `'manual_config_realizes_requirement'` — in the same `batch_alter_table` block as 1a so the recopy happens once. Include all four kinds in the new CHECK set regardless of whether `field` and `requirement` entity types exist yet (per `manual_config.md` §3.3.1 the kinds register up-front; only the `_kinds_for_pair` clauses are deferred until the target types exist). Keep the existing kinds plus the v0.7 and v0.8 additions; sorted-alphabetical for diff readability.

**1c. Extend `change_log.entity_type` CHECK constraint** to admit `'manual_config'`. Same `batch_alter_table` pattern as `0011`.

**1d. Create the `manual_configs` table.** Per `manual_config.md` §3.2 — twelve columns total:

```python
op.create_table(
    "manual_configs",
    sa.Column("manual_config_identifier", sa.String(length=32), nullable=False),
    sa.Column("manual_config_name", sa.String(length=255), nullable=False),
    sa.Column("manual_config_category", sa.String(length=32), nullable=False),
    sa.Column("manual_config_description", sa.Text(), nullable=False),
    sa.Column("manual_config_instructions", sa.Text(), nullable=False),
    sa.Column("manual_config_notes", sa.Text(), nullable=True),
    sa.Column("manual_config_status", sa.String(length=16), nullable=False),
    sa.Column("manual_config_completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("manual_config_completed_by", sa.Text(), nullable=True),
    sa.Column("manual_config_created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("manual_config_updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("manual_config_deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "manual_config_identifier GLOB 'MCF-[0-9][0-9][0-9]'",
        name="ck_manual_config_identifier_format",
    ),
    sa.CheckConstraint(
        "manual_config_status IN ('candidate', 'confirmed', 'deferred', 'completed')",
        name="ck_manual_config_status",
    ),
    sa.CheckConstraint(
        "manual_config_category IN "
        "('deferred_options_enum', 'duplicate_check', 'dynamic_logic', "
        "'other', 'role_permission', 'saved_view', 'workflow')",
        name="ck_manual_config_category",
    ),
    sa.PrimaryKeyConstraint("manual_config_identifier"),
)
with op.batch_alter_table("manual_configs", schema=None) as batch_op:
    batch_op.create_index("ix_manual_configs_manual_config_status", ["manual_config_status"], unique=False)
    batch_op.create_index("ix_manual_configs_manual_config_category", ["manual_config_category"], unique=False)
    batch_op.create_index("ix_manual_configs_manual_config_deleted_at", ["manual_config_deleted_at"], unique=False)
```

Notes on the column choices:

- The CHECK on `manual_config_status` covers exactly the four values from §3.4.1 — `candidate`, `confirmed`, `deferred`, `completed` — in that sorted order inside the CHECK expression.
- The CHECK on `manual_config_category` lists the seven values from §3.2.3 in sorted alphabetical order.
- `manual_config_completed_at` and `manual_config_completed_by` are nullable at the storage layer; the cross-field invariant ("required when status = completed") is enforced at the access layer (§3.5.3), not by a CHECK constraint, because expressing the conditional in SQL is brittle across SQLite versions and the access-layer error body is richer.
- No SQL FOREIGN KEY constraints: no scalar FK columns to other entity types exist on this table (the four outbound relationships live in `refs`).

The `downgrade()` function reverses in opposite order:
1. Drop the `manual_configs` table (with indexes via `batch_alter_table`).
2. Restore the original `change_log.entity_type` CHECK (without `'manual_config'`).
3. Restore the original `refs.relationship_kind` CHECK (without the four new kinds).
4. Restore the original `refs.source_type` / `refs.target_type` CHECKs (without `'manual_config'`).

Keep the new and old CHECK constants at module scope as named tuples or strings (mirrors `0011`).

### Step 2 — Author the ORM model

Edit `crmbuilder-v2/src/crmbuilder_v2/access/models.py`. Add `ManualConfig` after the `Process` class (or wherever the other methodology entity classes cluster), modeled on the `Entity` class with the additional columns the spec requires:

```python
class ManualConfig(Base):
    """Methodology entity — one operator-performed CRM configuration item.

    Per ``manual_config.md``. Twelve-column schema following the
    parent-prefix field-naming convention; primary key is the prefixed
    string ``manual_config_identifier`` (format ``MCF-NNN``). Four-status
    lifecycle (``candidate`` / ``confirmed`` / ``deferred`` / ``completed``)
    with terminal ``completed`` enforced at the access layer. The cross-
    field invariant — ``manual_config_completed_at`` and
    ``manual_config_completed_by`` populated on any transition into
    ``completed`` — is enforced at the access layer per §3.5.3, not by a
    CHECK constraint.
    """

    __tablename__ = "manual_configs"

    manual_config_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    manual_config_name: Mapped[str] = mapped_column(String(255), nullable=False)
    manual_config_category: Mapped[str] = mapped_column(String(32), nullable=False)
    manual_config_description: Mapped[str] = mapped_column(Text, nullable=False)
    manual_config_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    manual_config_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_config_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    manual_config_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    manual_config_completed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_config_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    manual_config_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    manual_config_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "manual_config_identifier GLOB 'MCF-[0-9][0-9][0-9]'",
            name="ck_manual_config_identifier_format",
        ),
        CheckConstraint(
            _check_in("manual_config_status", MANUAL_CONFIG_STATUSES),
            name="ck_manual_config_status",
        ),
        CheckConstraint(
            _check_in("manual_config_category", MANUAL_CONFIG_CATEGORIES),
            name="ck_manual_config_category",
        ),
        Index("ix_manual_configs_manual_config_status", "manual_config_status"),
        Index("ix_manual_configs_manual_config_category", "manual_config_category"),
        Index("ix_manual_configs_manual_config_deleted_at", "manual_config_deleted_at"),
    )
```

Add `MANUAL_CONFIG_STATUSES` and `MANUAL_CONFIG_CATEGORIES` to the existing `from crmbuilder_v2.access.vocab import (...)` imports at the top of `models.py`. Both constants are defined in step 3.

### Step 3 — Update `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`

Six surgical additions, all under section comments naming PI-004 and `manual_config.md`:

**3a. Add `MANUAL_CONFIG_STATUSES` and `MANUAL_CONFIG_STATUS_TRANSITIONS`.** After the `CRM_CANDIDATE_STATUS_TRANSITIONS` block, add:

```python
# Methodology entity `manual_config` lifecycle (PI-004, manual_config.md
# §3.4). Four-status lifecycle: ``candidate`` is the starter status;
# ``confirmed`` and ``deferred`` mirror the cross-spec propose-verify
# gate (movable in both directions); ``completed`` is terminal and
# reachable only from ``confirmed``. The cross-field invariant on the
# ``completed`` transition is enforced at the access layer per §3.5.3.
MANUAL_CONFIG_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred", "completed"}
)

# Valid status successors per ``manual_config.md`` §3.4.1. ``completed``
# is terminal: empty successor set.
MANUAL_CONFIG_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred", "completed"}),
    "deferred": frozenset({"confirmed"}),
    "completed": frozenset(),
}
```

**3b. Add `MANUAL_CONFIG_CATEGORIES`.** After the lifecycle block:

```python
# `manual_config_category` closed enum per ``manual_config.md`` §3.2.3.
# Seven values; aligned with the historical NOT_SUPPORTED categories
# documented in CLAUDE.md ("Three features have no public REST API
# write path") plus the v1.1 schema's deferred-options pattern and the
# role/dynamic-logic items deferred from v1.0.
MANUAL_CONFIG_CATEGORIES: frozenset[str] = frozenset(
    {
        "saved_view",
        "duplicate_check",
        "workflow",
        "deferred_options_enum",
        "role_permission",
        "dynamic_logic",
        "other",
    }
)
```

**3c. Add `'manual_config'` to `ENTITY_TYPES`.** Insert into the methodology-entities section (alongside `'domain'`, `'entity'`, `'process'`, `'crm_candidate'`) — update the section comment to name `manual_config` as a PI-004 addition.

**3d. Add the four outbound relationship kinds to `REFERENCE_RELATIONSHIPS`.** After the existing v0.8 Code Change Lifecycle additions, add a new section:

```python
# PI-004 additions (methodology entity `manual_config`, manual_config.md
# §3.3.1). Four outbound kinds; all four register up-front so the
# vocabulary surface is stable. The `_kinds_for_pair` clauses for
# `(manual_config, field)` and `(manual_config, requirement)` are
# conditional on the target entity types existing — see §3.3.1 note
# on PI-004 sibling sequencing.
"manual_config_scopes_to_domain",
"manual_config_touches_entity",
"manual_config_touches_field",
"manual_config_realizes_requirement",
```

**3e. Extend `_kinds_for_pair` with four new clauses.** After the v0.8 Code Change Lifecycle additions:

```python
# PI-004 additions (manual_config.md §3.3.1):
if source_type == "manual_config" and target_type == "domain":
    kinds.add("manual_config_scopes_to_domain")
if source_type == "manual_config" and target_type == "entity":
    kinds.add("manual_config_touches_entity")
# The `(manual_config, field)` and `(manual_config, requirement)`
# clauses below are conditional: they only emit the kind if the target
# entity type is present in ENTITY_TYPES (registered by the sibling
# PI-004 specs `field.md` and `requirement.md`). The vocab kind itself
# is unconditionally listed in REFERENCE_RELATIONSHIPS so that POSTs
# attempting a (manual_config, field) edge fail with the helpful
# "invalid (source, target) for this kind" error rather than an
# unknown-kind error once the target type exists.
if (
    source_type == "manual_config"
    and target_type == "field"
    and "field" in ENTITY_TYPES
):
    kinds.add("manual_config_touches_field")
if (
    source_type == "manual_config"
    and target_type == "requirement"
    and "requirement" in ENTITY_TYPES
):
    kinds.add("manual_config_realizes_requirement")
```

The conditional check against `ENTITY_TYPES` is the mechanism the spec describes in §3.3.1 — if `field` and `requirement` already exist in `ENTITY_TYPES` (because the sibling PI-004 specs landed first), the clauses emit normally. If not, the clauses are no-ops at module load and become active once the sibling builds add those types. The `REFERENCE_RELATIONSHIPS` set always carries the kinds.

If the sibling builds have already shipped at the time this build runs (check `ENTITY_TYPES` for `'field'` and `'requirement'`), the conditionals will fire on their own. If only one sibling has shipped, only that conditional fires. The pattern is forward-compatible without a follow-up vocab edit.

**3f. Update the `_kinds_for_pair` docstring** to add four bullets for the new kinds, matching the style of the v0.4 and v0.8 bullets.

### Step 4 — Author the repository

Create `crmbuilder-v2/src/crmbuilder_v2/access/repositories/manual_config.py`. Mirror `entity.py`'s shape but layer in two `crm_candidate.py`-style additions: category validation alongside status validation, and a `_require_completion_fields_for_completed` helper that mirrors `_reject_second_selected`'s structural role for the singleton-selected invariant.

Module docstring should cite `manual_config.md` §§3.4, 3.5.3 and call out the cross-field invariant explicitly.

Constants:

```python
_ENTITY_TYPE = "manual_config"
_IDENTIFIER_PREFIX = "MCF"
_IDENTIFIER_RE = re.compile(r"^MCF-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "category",
        "description",
        "instructions",
        "notes",
        "status",
        "completed_at",
        "completed_by",
    }
)
```

Helpers to mirror from `entity.py`:

- `_require_identifier_format(identifier)` — same shape, MCF prefix, `manual_config_identifier` field name in the FieldError.
- `_require_nonempty(value, *, field)` — verbatim.
- `_require_status(status)` — same shape against `MANUAL_CONFIG_STATUSES`.
- `_check_transition(current, requested)` — same shape against `MANUAL_CONFIG_STATUS_TRANSITIONS`. Transition into `completed` is enforced here only as "is `completed` a valid successor of `current`?"; the cross-field invariant fires separately (next helper).
- `_reject_duplicate_name(...)` — verbatim against `manual_config_name`.
- `_get_row(...)`, `_increment_identifier(...)`, `_new_manual_config_row(...)` — verbatim shape adjusted for the wider field set.

New helpers unique to this entity:

```python
def _require_category(category: object) -> str:
    if category not in MANUAL_CONFIG_CATEGORIES:
        raise UnprocessableError(
            [
                FieldError(
                    "manual_config_category",
                    "invalid_value",
                    f"must be one of {sorted(MANUAL_CONFIG_CATEGORIES)}",
                )
            ]
        )
    return category  # type: ignore[return-value]


def _require_completion_fields_for_completed(
    *,
    status_after: str,
    completed_at: datetime | None,
    completed_by: str | None,
) -> tuple[datetime | None, str | None]:
    """Enforce the §3.5.3 cross-field invariant on a `completed` write.

    When ``status_after == "completed"``:
    - ``completed_at`` is server-set to ``datetime.now(UTC)`` if omitted
      (the spec permits server-side defaulting for the timestamp).
    - ``completed_by`` MUST be present and non-empty; missing → 422 with
      ``completed_status_requires_completion_fields``.

    Returns the (possibly server-defaulted) tuple to the caller.

    When ``status_after != "completed"``, the helper passes the inputs
    through unchanged — setting completion fields on a non-completed
    record is permitted but discouraged per §3.5.3.
    """
    if status_after != "completed":
        return completed_at, completed_by
    missing: list[str] = []
    if completed_by is None or (
        isinstance(completed_by, str) and not completed_by.strip()
    ):
        missing.append("manual_config_completed_by")
    if missing:
        raise CompletedStatusRequiresCompletionFieldsError(missing)
    if completed_at is None:
        completed_at = datetime.now(UTC)
    return completed_at, completed_by.strip() if isinstance(completed_by, str) else completed_by
```

The error type `CompletedStatusRequiresCompletionFieldsError` is new — add it to `crmbuilder-v2/src/crmbuilder_v2/access/exceptions.py` following the shape of `SelectedCandidateConflictError`:

```python
class CompletedStatusRequiresCompletionFieldsError(AccessLayerError):
    """Raised when a write transitions ``manual_config_status`` to
    ``completed`` without populating the required completion fields.

    Carries the list of missing field names so the API handler can
    render the spec-mandated body shape:
    ``{"error": "completed_status_requires_completion_fields",
        "missing": [...]}``
    """

    def __init__(self, missing: list[str]):
        self.missing = list(missing)
        super().__init__(
            f"missing required completion fields for status=completed: "
            f"{', '.join(self.missing)}"
        )
```

And register a dedicated handler in `crmbuilder-v2/src/crmbuilder_v2/api/errors.py` following the shape of `selected_candidate_conflict_handler`:

```python
def completed_status_requires_completion_fields_handler(
    request: Request, exc: CompletedStatusRequiresCompletionFieldsError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "data": None,
            "meta": {},
            "errors": [
                {
                    "error": "completed_status_requires_completion_fields",
                    "missing": exc.missing,
                }
            ],
        },
    )
```

Then register the handler in `main.py` between the `SelectedCandidateConflictError` handler and the `AccessLayerError` handler (same ordering rule — dedicated handlers before the base class so Starlette matches them by exact class).

Repository public functions, eight in total per the standard set:

- `list_manual_configs(session, *, include_deleted=False)` — verbatim shape against `ManualConfig.manual_config_deleted_at`.
- `get_manual_config(session, identifier, *, include_deleted=False)` — verbatim shape.
- `next_manual_config_identifier(session)` — verbatim shape.
- `create_manual_config(session, *, name, category, description, instructions, notes=None, status="candidate", completed_at=None, completed_by=None, identifier=None)` — validates name, category, description, instructions, status; rejects duplicate name; if status is `completed`, runs `_require_completion_fields_for_completed`; performs identifier auto-assign or explicit-identifier path; emits change_log "insert".
- `update_manual_config(session, identifier, *, manual_config_identifier=None, name, category, description, instructions, notes=None, status, completed_at=None, completed_by=None)` — full-replace PUT. Validates path/body identifier match; runs the same set of validators; runs `_check_transition` if status changes; runs the cross-field invariant against the **post-write** status; emits change_log "update".
- `patch_manual_config(session, identifier, **fields)` — partial PATCH. Pre-filter `unknown = set(fields) - _PATCHABLE_FIELDS`. For each supplied field, validate and apply. Compute `status_after` as `fields.get("status", row.manual_config_status)`. If `status_after == "completed"` (regardless of whether the patch changed status), run the cross-field invariant against the post-merge field values — i.e. take `completed_at_after = fields.get("completed_at", row.manual_config_completed_at)` and `completed_by_after = fields.get("completed_by", row.manual_config_completed_by)`. This handles the edge case "a PATCH that only sets `status: completed` on a record whose completion fields are still null".
- `delete_manual_config(session, identifier)` — verbatim soft-delete.
- `restore_manual_config(session, identifier)` — verbatim restore. No cross-field invariant on restore (the row's existing status and completion fields are unchanged).

The `_insert_with_autoassign(...)` helper mirrors entity's shape but takes the wider parameter list. Use SAVEPOINT-retry with `_MAX_AUTOASSIGN_ATTEMPTS = 50`.

### Step 5 — Author the FastAPI Pydantic schemas

Edit `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py`. Insert after the `CrmCandidatePatchIn` block (or wherever the methodology-entities cluster ends, before the governance section):

```python
# ---------- Manual Configs (methodology entity, PI-004) ----------


class ManualConfigCreateIn(_Base):
    """POST /manual-configs body. ``manual_config_identifier`` is server-
    assigned when omitted; ``manual_config_status`` defaults to
    ``candidate`` server-side. The cross-field invariant on ``completed``
    is enforced server-side per manual_config.md §3.5.3.

    Outbound references (scopes_to_domain, touches_entity, touches_field,
    realizes_requirement) are NOT inlined here — per §3.5.4 they attach
    via separate ``POST /references`` calls.
    """

    manual_config_name: str
    manual_config_category: str
    manual_config_description: str
    manual_config_instructions: str
    manual_config_notes: str | None = None
    manual_config_status: str | None = None
    manual_config_completed_at: datetime | None = None
    manual_config_completed_by: str | None = None
    manual_config_identifier: str | None = None


class ManualConfigReplaceIn(_Base):
    """PUT /manual-configs/{identifier} body — full record replace."""

    manual_config_identifier: str | None = None
    manual_config_name: str
    manual_config_category: str
    manual_config_description: str
    manual_config_instructions: str
    manual_config_notes: str | None = None
    manual_config_status: str
    manual_config_completed_at: datetime | None = None
    manual_config_completed_by: str | None = None


class ManualConfigPatchIn(_Base):
    """PATCH /manual-configs/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``manual_config_notes: null`` (clear the field) is
    distinguished from an omitted ``manual_config_notes`` (leave
    unchanged). The same applies to the two completion fields, which
    can be explicitly nulled when transitioning the record out of
    ``completed`` would otherwise be permitted (today: never, since
    ``completed`` is terminal — but the body schema accepts the shape).
    """

    manual_config_name: str | None = None
    manual_config_category: str | None = None
    manual_config_description: str | None = None
    manual_config_instructions: str | None = None
    manual_config_notes: str | None = None
    manual_config_status: str | None = None
    manual_config_completed_at: datetime | None = None
    manual_config_completed_by: str | None = None
```

Import `datetime` from `datetime` at the top of `schemas.py` if not already present.

### Step 6 — Author the FastAPI router

Create `crmbuilder-v2/src/crmbuilder_v2/api/routers/manual_configs.py`. Mirror `entities.py`'s eight-endpoint shape verbatim with the field-prefix string swapped:

```python
router = APIRouter(prefix="/manual-configs", tags=["manual-configs"])
_FIELD_PREFIX = "manual_config_"
```

Endpoints (in order):

- `GET ""` → `list_all(include_deleted: bool = False)` → `repo.list_manual_configs(...)`.
- `GET "/next-identifier"` → `next_identifier()` → `{"next": repo.next_manual_config_identifier(s)}`.
- `GET "/{identifier}"` → `get(identifier, include_deleted=False)` with NotFoundError on `None`.
- `POST ""` → `create(body: ManualConfigCreateIn)` → `repo.create_manual_config(...)` with every field stripped of the `manual_config_` prefix when passed to the repo.
- `PUT "/{identifier}"` → `replace(identifier, body: ManualConfigReplaceIn)` → `repo.update_manual_config(...)`.
- `PATCH "/{identifier}"` → `patch(identifier, body: ManualConfigPatchIn)` → strip the field prefix via `{key[len(_FIELD_PREFIX):]: value for key, value in provided.items()}`, pass to `repo.patch_manual_config(...)`.
- `DELETE "/{identifier}"` → `delete(identifier)`.
- `POST "/{identifier}/restore"` → `restore(identifier)`.

URL plural: hyphenated per §3.5.1 — `/manual-configs`, not `/manual_configs`.

### Step 7 — Register the router in `main.py`

Edit `crmbuilder-v2/src/crmbuilder_v2/api/main.py`:

1. Add `manual_configs` to the `from crmbuilder_v2.api.routers import (...)` list, alphabetically positioned.
2. Add `app.include_router(manual_configs.router)` to the methodology-entities cluster (after `crm_candidates.router`, before `references.router`).
3. Add the `CompletedStatusRequiresCompletionFieldsError` import to the top of `main.py` and register the handler:

```python
app.add_exception_handler(
    CompletedStatusRequiresCompletionFieldsError,
    completed_status_requires_completion_fields_handler,
)
```

Position the handler registration **before** the `AccessLayerError` registration (same rule as `SelectedCandidateConflictError` per the comment in `main.py` at line ~75).

### Step 8 — Add the seven UI client methods

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/client.py`. After the entity-method block (~lines 660–795), add a `manual_config` block mirroring the same shape:

```python
def list_manual_configs(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
    response = self._http_get("/manual-configs", params={"include_deleted": include_deleted})
    return response.get("data") or []

def get_manual_config(self, identifier: str) -> dict[str, Any]:
    response = self._http_get(f"/manual-configs/{identifier}")
    data = response.get("data")
    if data is None:
        raise NotFoundError(f"manual_config {identifier!r} not found")
    return data

def create_manual_config(self, body: dict[str, Any]) -> dict[str, Any]:
    response = self._http_post("/manual-configs", json=body)
    return response.get("data") or {}

def update_manual_config(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
    response = self._http_put(f"/manual-configs/{identifier}", json=body)
    return response.get("data") or {}

def patch_manual_config(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
    response = self._http_patch(f"/manual-configs/{identifier}", json=body)
    return response.get("data") or {}

def delete_manual_config(self, identifier: str) -> Any:
    return self._http_delete(f"/manual-configs/{identifier}")

def restore_manual_config(self, identifier: str) -> dict[str, Any]:
    response = self._http_post(f"/manual-configs/{identifier}/restore")
    return response.get("data") or {}

def next_manual_config_identifier(self) -> str:
    response = self._http_get("/manual-configs/next-identifier")
    return (response.get("data") or {}).get("next", "")
```

Match the exact method-naming, error-handling, and envelope-unwrapping idioms of the existing methods. If the existing methods use slightly different helpers (e.g. `self._http.request(...)` instead of `self._http_get(...)`), follow that pattern.

### Step 9 — Add the sidebar entry

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py`. In `SIDEBAR_GROUPS`, append `"Manual Configs"` to the Methodology group's entry tuple. Position depends on PI-004 sibling ship sequence; default position is after `"CRM Candidates"`:

```python
(
    "Methodology",
    ("Domains", "Entities", "Processes", "CRM Candidates", "Manual Configs"),
),
```

If the `field` / `requirement` / `test_spec` siblings have already shipped (check the current tuple), insert `"Manual Configs"` at the position the spec suggests in §3.6.1 (between Fields and Test Specs if both exist; after Requirements; otherwise as the tail-most Methodology entry).

### Step 10 — Wire the main-window dispatch

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py`:

1. Add `from crmbuilder_v2.ui.panels.manual_config import ManualConfigPanel` near the other panel imports.
2. Add `"manual_config": "Manual Configs"` to the `_entry_to_entity_type` map (used for cross-panel link resolution).
3. Add an `elif entry == "Manual Configs":` branch in the panel-construction chain (alongside `EntitiesPanel`, `CrmCandidatesPanel`):

```python
elif entry == "Manual Configs":
    page = ManualConfigPanel(self._client)
```

### Step 11 — Author the panel

Create `crmbuilder-v2/src/crmbuilder_v2/ui/panels/manual_config.py`. Mirror `entities.py`'s panel shape with five-column master pane per §3.6.2 and a detail pane that conditionally reveals the completion fields per §3.6.3.

Class shape:

```python
class ManualConfigPanel(ListDetailPanel):
    """Manual Configs panel with read + write surfaces (PI-004)."""

    def entity_title(self) -> str:
        return "Manual Configs"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_manual_configs(include_deleted=self._include_deleted)

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="manual_config_identifier", title="Identifier", width=120),
            ColumnSpec(field="manual_config_name", title="Name"),
            ColumnSpec(field="manual_config_category", title="Category", width=160),
            ColumnSpec(field="manual_config_status", title="Status", width=110),
            ColumnSpec(field="manual_config_updated_at", title="Updated", width=180),
        ]
```

The five-column master pane matches §3.6.2 exactly — Category is the master-pane addition that distinguishes this panel from the entity panel (Domains-deferred posture).

Detail pane (`render_detail`) layout per §3.6.3:

1. Edit / Delete (or Restore / Edit) action strip.
2. Heading label — `manual_config_name`.
3. Form layout with fields in section-3.2 order:
   - Identifier (read-only label).
   - Name (read-only line edit).
   - Category (read-only line edit; show the enum value verbatim).
   - Description (read-only multi-line).
   - Instructions (read-only multi-line, taller min-height than description).
4. Notes section under `CollapsibleSection("Internal notes", ...)`, collapsed by default.
5. Status row: read-only combo restricted to the current status's valid successors; "Valid transitions" hint caption below.
6. **Conditional completion section.** If the record's `manual_config_status == "completed"`, render a separate sub-section with two read-only fields (Completed At, Completed By). If status is anything other than `completed`, omit the section entirely — the fields are server-side null and not part of the active visual.
7. `ReferencesSection` widget with `entity_type="manual_config"`, surfacing the four outbound kinds plus any inbound `test_spec_verifies_manual_config` references once `test_spec` lands.

The conditional reveal in step 6 matches §3.6.3 item 8–9 ("visible only when status is `completed`").

Click handlers (`_on_new_*`, `_on_edit_*`, `_on_delete_*`, `_on_restore_*`) follow `entity.py`'s pattern verbatim with `ManualConfig` class names substituted.

### Step 12 — Author the CRUD dialogs

Create two files:

**12a. `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_manual_config_schema.py`** — declarative `FieldSchema` list. Mirror `_entity_schema.py` but with the wider field set and two helpers:

```python
def status_choices(current: str | None) -> list[str]:
    """Return the status values selectable from ``current``.

    For ``candidate`` (the create dialog's default): yields
    ``[candidate, confirmed, deferred]`` — completed is NOT shown
    because ``candidate → completed`` is an invalid transition.
    For ``confirmed``: yields ``[confirmed, deferred, completed]``.
    For ``deferred``: yields ``[confirmed, deferred]``.
    For ``completed`` (terminal): yields ``[completed]``.
    """
    current = current or "candidate"
    if current not in MANUAL_CONFIG_STATUSES:
        return sorted(MANUAL_CONFIG_STATUSES)
    return sorted(
        {current} | set(MANUAL_CONFIG_STATUS_TRANSITIONS.get(current, frozenset()))
    )


def category_choices() -> list[str]:
    """Return the seven category values in sorted order for the combo."""
    return sorted(MANUAL_CONFIG_CATEGORIES)
```

The FieldSchema list:

```python
_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(key="manual_config_name", label="Name", widget="line", required=True),
    FieldSchema(
        key="manual_config_category",
        label="Category",
        widget="combo",
        required=True,
        vocab=MANUAL_CONFIG_CATEGORIES,
        compute_options=lambda _state: category_choices(),
    ),
    FieldSchema(
        key="manual_config_description",
        label="Description",
        widget="text",
        required=True,
        placeholder="Brief description of what the manual config is and why it exists",
    ),
    FieldSchema(
        key="manual_config_instructions",
        label="Instructions",
        widget="text",
        required=True,
        placeholder="Step-by-step operator instructions for performing the configuration",
    ),
    FieldSchema(key="manual_config_notes", label="Internal notes", widget="text"),
    FieldSchema(
        key="manual_config_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=MANUAL_CONFIG_STATUSES,
        default="candidate",
        compute_options=lambda state: status_choices(state.get("manual_config_status")),
    ),
    FieldSchema(
        key="manual_config_completed_at",
        label="Completed at",
        widget="datetime",  # or "line" if no datetime widget exists; let the dialog accept ISO 8601
        visible_when=lambda state: state.get("manual_config_status") == "completed",
    ),
    FieldSchema(
        key="manual_config_completed_by",
        label="Completed by",
        widget="line",
        required_when=lambda state: state.get("manual_config_status") == "completed",
        visible_when=lambda state: state.get("manual_config_status") == "completed",
    ),
]
```

If the `FieldSchema` dataclass doesn't already support `visible_when` / `required_when` / `widget="datetime"`, extend `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py` minimally to support them. The visibility predicate should fire on every state change (status combo change) and reflow the dialog form layout. If extending the base is more work than warranted, fall back to a simpler approach: always show the two completion fields in the dialog, but only validate them as required when status is `completed`. The acceptance criteria (§3.7 item 14) say "inline" — both UX approaches satisfy that.

**12b. `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/manual_config_crud.py`** — the three dialog classes:

```python
class ManualConfigCreateDialog(EntityCrudDialog): ...
class ManualConfigEditDialog(EntityCrudDialog): ...
class ManualConfigDeleteDialog(EntityCrudDeleteDialog): ...
```

Mirror `entity_crud.py`'s shape. The delete dialog uses edge-text confirmation (user types the identifier to enable Delete).

For the Mark-Completed UX per §3.6.5: ship the **status-combo-driven** approach for v0.5 (open-question 3.8.1 second item explicitly defers the "dedicated Mark Completed button" alternative to v0.6+). The status combo offers `completed` when current is `confirmed`; selecting it reveals the completion fields; submitting validates them.

### Step 13 — Wire the panel into the main window's stale-set / select-record logic

If `main_window.py` has any per-panel stale-set tracking or sidebar-stale-flag plumbing keyed by entity type, extend it for `manual_config`. (Inspect the existing `Entities` / `CRM Candidates` paths; if no per-panel custom hookup is needed, this step is a no-op.)

### Step 14 — Author the tests

Three test files (≥20 tests total per the prompt scope):

**14a. `tests/crmbuilder_v2/access/test_manual_config.py`** (access layer; ≥12 tests):

- `test_create_assigns_identifier_when_omitted` — POST without identifier; assigned `MCF-001` (or next free); record present.
- `test_create_explicit_identifier_persists` — POST with `manual_config_identifier="MCF-099"`; record present at that identifier.
- `test_create_explicit_identifier_format_validation` — POST with `manual_config_identifier="MC-001"` → `UnprocessableError` with `invalid_format`.
- `test_create_explicit_identifier_collision` — POST with an already-taken identifier → `ConflictError`.
- `test_create_invalid_category` — POST with `manual_config_category="bogus"` → `UnprocessableError` with `invalid_value`.
- `test_create_duplicate_name_case_insensitive` — POST then POST with the same name lowercased → `UnprocessableError` with `duplicate`.
- `test_create_completed_without_completion_fields` — POST with `manual_config_status="completed"`, omitting `manual_config_completed_by` → `CompletedStatusRequiresCompletionFieldsError` with `missing=["manual_config_completed_by"]`.
- `test_create_completed_with_completion_fields_succeeds` — POST with `manual_config_status="completed"`, `manual_config_completed_by="doug@dougbower.com"`, no `manual_config_completed_at` → succeeds; `manual_config_completed_at` server-set to a recent timestamp.
- `test_patch_candidate_to_completed_invalid_transition` — PATCH `manual_config_status="completed"` on a `candidate` record → `StatusTransitionError`.
- `test_patch_confirmed_to_completed_succeeds_with_fields` — create-as-confirmed, PATCH `status="completed"` + completion fields → succeeds.
- `test_patch_confirmed_to_completed_without_completion_fields` — PATCH `status="completed"` without `manual_config_completed_by` → `CompletedStatusRequiresCompletionFieldsError`.
- `test_patch_completed_to_anything_terminal` — create-as-completed, PATCH `status="confirmed"` → `StatusTransitionError` (no transitions out of terminal `completed`).
- `test_delete_and_restore_round_trip` — DELETE then `?include_deleted=true` shows; POST `/restore` reappears.
- `test_concurrent_identifier_autoassign` — two simultaneous POSTs (via threadpool fixture or sequential same-savepoint pattern from existing concurrent tests) assign distinct identifiers.

**14b. `tests/crmbuilder_v2/api/test_manual_configs_api.py`** (REST surface; ≥6 tests):

- `test_get_list_default_excludes_deleted` — POST + DELETE + GET → record not present; GET `?include_deleted=true` → present.
- `test_get_next_identifier_returns_next_mcf` — GET `/manual-configs/next-identifier` → `{"data": {"next": "MCF-NNN"}}`.
- `test_post_create_returns_201_and_envelope` — POST → 201; body wraps `{data, meta, errors}` with `data.manual_config_identifier` populated.
- `test_patch_to_completed_without_completion_by_returns_422` — PATCH → 422; body has `errors[0].error == "completed_status_requires_completion_fields"` and `errors[0].missing == ["manual_config_completed_by"]`.
- `test_invalid_status_transition_returns_422_with_dedicated_body` — PATCH `candidate → completed` direct → 422; body has `errors[0].error == "invalid_status_transition"`.
- `test_put_path_identifier_mismatch_returns_422` — PUT `/manual-configs/MCF-001` with body `manual_config_identifier="MCF-002"` → 422.
- `test_reference_round_trip_for_each_outbound_kind` — POST a domain + entity record; POST a manual_config; POST `/references` for each of `manual_config_scopes_to_domain` and `manual_config_touches_entity` (the two unconditionally-active kinds at this build's time of writing); GET `/references?source_id=MCF-001` round-trips both.

**14c. `tests/crmbuilder_v2/ui/test_manual_config_panel.py`** (UI smoke; ≥2 tests):

- `test_panel_master_pane_columns` — instantiate `ManualConfigPanel` against a fake client returning one record; assert the column headers are exactly `["Identifier", "Name", "Category", "Status", "Updated"]`.
- `test_detail_pane_reveals_completion_fields_when_status_completed` — render_detail for a `completed` record → completion fields are present widgets; render_detail for a `candidate` record → completion fields are absent.

Total target: ≥20 tests. Pattern-match the existing test scaffolding (fixtures, helpers) under `tests/crmbuilder_v2/access/` for the access tests and `tests/crmbuilder_v2/api/` for the API tests. If those subdirectories don't yet exist for this build's purposes, place the tests where similar `entity` / `crm_candidate` tests live and follow the existing convention exactly.

### Step 15 — Run the migration and end-to-end verification

```bash
cd crmbuilder-v2
uv run alembic upgrade head 2>&1
uv run alembic current 2>&1
# Expected: NNNN_v0_5_create_manual_configs_table (head)
cd ..
```

Verify the table and CHECK extensions:

```bash
uv run python -c "
from crmbuilder_v2.access.db import session_scope
from sqlalchemy import text
with session_scope() as s:
    rows = list(s.execute(text(\"SELECT name FROM sqlite_master WHERE type='table' AND name='manual_configs'\")))
    print(f'manual_configs table present: {len(rows) == 1}')
"
```

Restart the API (if running) so the new router is loaded:

```bash
# Stop existing crmbuilder-v2-api process, then:
cd crmbuilder-v2 && uv run crmbuilder-v2-api &
cd ..
sleep 2
```

End-to-end smoke against the live API (every snippet unwraps `.data` per the v2 envelope rule):

```bash
# 1. Create a manual_config in candidate state.
curl -sX POST http://127.0.0.1:8765/manual-configs \
  -H 'Content-Type: application/json' \
  -d '{
    "manual_config_name": "Saved view: Smoke test",
    "manual_config_category": "saved_view",
    "manual_config_description": "Smoke-test record for the build.",
    "manual_config_instructions": "1. Open admin. 2. Add saved view."
  }' \
  | python3 -c "import sys, json; d = json.load(sys.stdin); print(json.dumps(d, indent=2))"
# Expected: data.manual_config_identifier = 'MCF-001' (or next free), status=candidate.

# 2. Patch to completed WITH completion fields → success.
curl -sX PATCH http://127.0.0.1:8765/manual-configs/MCF-001 \
  -H 'Content-Type: application/json' \
  -d '{"manual_config_status": "confirmed"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['manual_config_status'])"
# Expected: confirmed

curl -sX PATCH http://127.0.0.1:8765/manual-configs/MCF-001 \
  -H 'Content-Type: application/json' \
  -d '{"manual_config_status": "completed", "manual_config_completed_by": "doug@dougbower.com"}' \
  | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(d['manual_config_status'], d['manual_config_completed_at'], d['manual_config_completed_by'])"
# Expected: completed <iso-timestamp> doug@dougbower.com

# 3. Create another candidate and patch to completed WITHOUT completion fields → 422.
curl -sX POST http://127.0.0.1:8765/manual-configs \
  -H 'Content-Type: application/json' \
  -d '{
    "manual_config_name": "Workflow: Smoke test #2",
    "manual_config_category": "workflow",
    "manual_config_description": "Smoke-test record #2.",
    "manual_config_instructions": "1. Open admin. 2. Add workflow."
  }' | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['manual_config_identifier'])"
# Expected: MCF-002

curl -sX PATCH http://127.0.0.1:8765/manual-configs/MCF-002 \
  -H 'Content-Type: application/json' \
  -d '{"manual_config_status": "confirmed"}' > /dev/null

curl -sw "\n%{http_code}\n" -X PATCH http://127.0.0.1:8765/manual-configs/MCF-002 \
  -H 'Content-Type: application/json' \
  -d '{"manual_config_status": "completed"}'
# Expected: HTTP 422; body contains "completed_status_requires_completion_fields" and missing=["manual_config_completed_by"]
```

Run the full test suite:

```bash
cd crmbuilder-v2
uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -50
cd ..
```

Expected: baseline pass count from pre-flight step 12 plus ≥20 new tests. Halt and report if any previously-passing test fails.

Clean up the smoke-test records (do not leave them in the engagement DB):

```bash
curl -sX DELETE http://127.0.0.1:8765/manual-configs/MCF-001 > /dev/null
curl -sX DELETE http://127.0.0.1:8765/manual-configs/MCF-002 > /dev/null
```

(The records soft-delete; if you want them physically gone for a clean close-out, restore them and re-DELETE — but soft-delete is the expected operational shape, so leaving them in `deleted` state is fine.)

### Step 16 — Author the close-out payload and apply prompt

**16a. Identify session and decision identifiers.** Re-run the head capture from pre-flight step 14 to verify nothing has been claimed in parallel:

```bash
for endpoint in sessions decisions; do
  curl -s "http://127.0.0.1:8765/$endpoint" \
    | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; ids = sorted(r['identifier'] for r in d if r.get('identifier')); print(f'$endpoint: tail={ids[-3:] if ids else []}')"
done
```

If the pre-flight-captured values are still free, use them. Otherwise re-key.

**16b. Perform the PI-004 build-closure check.** Per the rule at the top of this prompt:

```bash
curl -s 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=addresses' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
print(f'addresses-edge count: {len(d)}')
for r in d:
    print(f\"  {r['reference_identifier']}: {r['source_type']} {r['source_id']}\")
"
```

Also enumerate which sibling identifiers exist in the v2 DB to confirm the delivery state:

```bash
for et in field requirement test_spec; do
  curl -s "http://127.0.0.1:8765/${et}s" 2>/dev/null \
    | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin).get('data') or []
    print(f'$et: count={len(d)}')
except Exception as e:
    print(f'$et: endpoint not present yet')
" 2>/dev/null
done
```

Decision:

- If all three siblings are present AND each has its own `addresses` edge to PI-004 from a completed session, this session is the closer. Set `resolves_planning_items: [{"planning_item_identifier": "PI-004"}]` AND `addresses_planning_items: []`.
- Otherwise this session merely advances PI-004. Set `resolves_planning_items: []` AND `addresses_planning_items: [{"planning_item_identifier": "PI-004"}]`.

When in doubt, prefer the non-resolving posture — underclaiming is safe; overclaiming would prematurely Resolve PI-004 with siblings outstanding.

**16c. Author the close-out payload** at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`. Nine sections per v0.8:

```json
{
  "label": "build manual_config (PI-004 sibling)",
  "session": { "...": "session metadata; summary references manual_config.md, PI-004, the four-status lifecycle, the cross-field invariant" },
  "conversation": { "...": "conversation metadata" },
  "work_tickets": [],
  "planning_items": [],
  "commits": [ "...": "the build commit SHA(s) from step 17" ],
  "decisions": [
    { "...": "DEC-NNN — manual_config prefix / fields / four-status lifecycle deviation / reference vocab / API surface, per manual_config.md §3.9.1" }
  ],
  "references": [
    { "...": "edges from the decisions to the SES, the conversation, the spec reference_book if registered, etc." }
  ],
  "resolves_planning_items": [],
  "addresses_planning_items": [{ "planning_item_identifier": "PI-004" }]
}
```

Populate `resolves_planning_items` per the §16b rule. The `decisions` section may consolidate to a single combined DEC entry (DEC-MCF-combined-per-§3.9.1) or split into multiple per the §3.9.1 placeholders — at session author discretion; the spec sketches both shapes.

**16d. Author the apply prompt** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`. Mirror the most recent apply prompt (e.g. `CLAUDE-CODE-PROMPT-apply-close-out-ses-077.md`) for the standard pre-flight, apply command, and post-apply verification structure. Include:

- Pre-flight identifier captures for the records about to be written.
- The apply command: `uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` (run from the `crmbuilder-v2/` directory).
- Post-apply fingerprint checks: GET each new DEC and SES, verify presence.
- A specific PI-004 status check: after the apply, GET `/planning-items/PI-004` and verify status is Open (if non-resolving) or Resolved (if resolving). Both are correct outcomes depending on which posture the close-out took.

### Step 17 — Commit

Commits in this order:

**Commit 1 — Migration + access layer + vocab + exceptions + API + UI + tests** (one atomic commit; the build is a coherent unit per CLAUDE.md slice precedent). Stage:

```bash
git add crmbuilder-v2/migrations/versions/NNNN_v0_5_create_manual_configs_table.py
git add crmbuilder-v2/src/crmbuilder_v2/access/models.py
git add crmbuilder-v2/src/crmbuilder_v2/access/vocab.py
git add crmbuilder-v2/src/crmbuilder_v2/access/exceptions.py
git add crmbuilder-v2/src/crmbuilder_v2/access/repositories/manual_config.py
git add crmbuilder-v2/src/crmbuilder_v2/api/errors.py
git add crmbuilder-v2/src/crmbuilder_v2/api/main.py
git add crmbuilder-v2/src/crmbuilder_v2/api/routers/manual_configs.py
git add crmbuilder-v2/src/crmbuilder_v2/api/schemas.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/client.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/panels/manual_config.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/manual_config_crud.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_manual_config_schema.py
git add tests/crmbuilder_v2/access/test_manual_config.py
git add tests/crmbuilder_v2/api/test_manual_configs_api.py
git add tests/crmbuilder_v2/ui/test_manual_config_panel.py

git commit -m "$(cat <<'EOF'
v2: PI-004 — build manual_config methodology entity

Lands the manual_config entity end-to-end per
methodology-schema-specs/manual_config.md v1.0. Third PI-004 sibling
alongside field, requirement, test_spec.

Schema (migration NNNN):
- New manual_configs table, 12 columns, CHECK on identifier (MCF-NNN),
  status (4 values), and category (7 values).
- refs.source_type / refs.target_type / refs.relationship_kind CHECK
  extensions for 'manual_config' and the four outbound kinds.
- change_log.entity_type CHECK extension.

Access layer:
- repositories/manual_config.py with 8 functions following entity.py's
  shape plus category validation and the §3.5.3 cross-field invariant
  (manual_config_completed_at + manual_config_completed_by required on
  transition into 'completed'; completed_at server-defaultable to now).
- New CompletedStatusRequiresCompletionFieldsError with dedicated
  handler rendering the {error, missing} body shape.
- vocab.py: MANUAL_CONFIG_STATUSES, MANUAL_CONFIG_STATUS_TRANSITIONS
  (4-status, terminal completed), MANUAL_CONFIG_CATEGORIES, ENTITY_TYPES
  + REFERENCE_RELATIONSHIPS + 4 _kinds_for_pair clauses (the field /
  requirement clauses guarded on target-type presence for PI-004 sibling
  sequencing).

API:
- routers/manual_configs.py — 8 endpoints under /manual-configs.
- ManualConfigCreateIn / ReplaceIn / PatchIn Pydantic schemas with
  category + instructions + completion fields.
- main.py registers the router and the completed-fields handler.

UI:
- 7 client methods on UiClient.
- Sidebar 'Manual Configs' entry under Methodology.
- ManualConfigPanel with 5-column master pane (Identifier / Name /
  Category / Status / Updated) per §3.6.2 and detail pane that reveals
  completion fields only when status is 'completed' per §3.6.3.
- ManualConfigCreate/Edit/DeleteDialog with status-combo-driven
  Mark-Completed UX per §3.6.5.

Tests at tests/crmbuilder_v2/access/test_manual_config.py (≥12),
tests/crmbuilder_v2/api/test_manual_configs_api.py (≥6),
tests/crmbuilder_v2/ui/test_manual_config_panel.py (≥2). Covers the
4-status transition map, the cross-field invariant on both POST and
PATCH paths, soft-delete round-trip, identifier auto-assign concurrency,
and reference round-trips for the two unconditionally-active outbound
kinds.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

**Commit 2 — Close-out apply** (after running `apply_close_out.py`):

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json
cd ..
```

The apply script tees its stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` (DEC-164) and authors a deposit_event. Then stage and commit:

```bash
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json
git add PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md
git add PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log
git add PRDs/product/crmbuilder-v2/db-export/

git commit -m "$(cat <<'EOF'
v2: close out SES-NNN — manual_config build (PI-004 sibling)

Apply close-out payload for the manual_config build session. Writes
the session record, conversation, the DEC(s) the spec authors at
build close per manual_config.md §3.9.1, and the addresses (or
resolves) edge against PI-004 per the PI-004 build-closure rule.

Regenerated db-export snapshots, new dep_NNN.log.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git pull --rebase origin main
```

Wait for Doug's review and push approval (per the local-clone working convention — Claude commits, Doug pushes).

---

## Done

Reply with:

- Pre-build Alembic head: `<head>`
- Post-build Alembic head: `NNNN_v0_5_create_manual_configs_table`
- `manual_configs` table present in engagement DB: True / False
- Smoke-test PATCH to completed without completion fields returned 422: True / False (expected True)
- Smoke-test PATCH to completed with completion fields succeeded: True / False (expected True)
- Test suite: pre-build pass count vs post-build pass count (+≥20 new tests expected)
- PI-004 closure posture chosen: resolves / addresses
- Sibling status at close-out time: which of field / requirement / test_spec are present in v2 DB
- Build commit SHA: `<sha>`
- Close-out commit SHA: `<sha>`
- Session identifier authored: `SES-NNN`
- Decision identifier(s) authored: `DEC-NNN`(`, DEC-NNN`...)
- Next prompt to run: depends on PI-004 closure posture — if resolving, the next prompt is whatever was queued post-PI-004; if non-resolving, the next prompt is one of the remaining PI-004 sibling builds (`field`, `requirement`, or `test_spec`)
