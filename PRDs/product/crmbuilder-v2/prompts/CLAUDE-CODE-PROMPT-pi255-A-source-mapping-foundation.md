# CLAUDE-CODE-PROMPT-pi255-A-source-mapping-foundation.md

## Operating mode: DETAIL

## Purpose

Build the foundation layer of the source instance mapping model (PI-255, SES-230, PRJ-027). This is Slice 1 of 2.

**Scope of this prompt:**
- Extend `vocab.py` with source mapping vocabulary and two new `instance_membership` states
- Add seven ORM models to `models.py`
- Write migration `0079_pi_255_source_mapping_tables.py`
- Write five repository modules in `access/repositories/`
- Write access-layer tests
- No REST endpoints (those are Slice 2)

---

## Pre-flight

```bash
cd ~/Dropbox/Projects/CRMBuilder/crmbuilder-v2
pwd
git status          # must be clean on main
git pull --rebase origin main
git log --oneline -3
# Confirm migration head: the last file in migrations/versions/ should be 0078_*
ls migrations/versions/ | sort | tail -3
```

Read `CLAUDE.md` at the repo root before making any changes. Read `src/crmbuilder_v2/access/vocab.py` and `src/crmbuilder_v2/access/models.py` (full files) before writing anything.

---

## Step 1 — Extend `vocab.py`

Add the following constants. Insert each block adjacent to the related existing constants as noted.

**1a. Two new `INSTANCE_MEMBERSHIP_STATES` values.**

Find the existing constant:
```python
INSTANCE_MEMBERSHIP_STATES: frozenset[str] = frozenset(
    {"present", "drifted", "absent"}
)
```

Replace it with:
```python
# present = exists and matches the canonical design; drifted = exists but at
# least one attribute differs (captured in the override); absent = a canonical
# object not found in this instance's last audit; candidate_pending = discovered
# in a source audit, awaiting a human mapping decision before influencing the
# canonical design; mapping_stale = an existing mapping became stale due to a
# change on either the source or the design side (SES-230, DEC-454).
INSTANCE_MEMBERSHIP_STATES: frozenset[str] = frozenset(
    {"present", "drifted", "absent", "candidate_pending", "mapping_stale"}
)
```

**1b. Source mapping vocabulary.** Add after the `INSTANCE_MEMBERSHIP_MEMBER_TYPES` block (after line containing `"filtered_tab"`), before the `# Filtered-tab design family` comment:

```python
# ---------------------------------------------------------------------------
# Source instance mapping model (PI-255, SES-230 — PRJ-027). The
# candidate-gated human-decision layer that governs how objects discovered
# in a source CRM instance relate to objects in the canonical design.
# Source instances are design inputs, not design authorities. Every discovered
# object requires an explicit mapping decision before it influences the design.
# See source-mapping-design.md for the full model.
# ---------------------------------------------------------------------------

# Entity-level mapping decision types (DEC-451, DEC-452). A source entity may
# map directly to one design entity, decompose into multiple design entities,
# map referentially (different surface, same intent), or be explicitly rejected.
SOURCE_MAPPING_DECISION_TYPES: frozenset[str] = frozenset(
    {"direct", "decomposition", "referential", "rejected"}
)

# Mapping record lifecycle states (DEC-454). A mapping is unresolved until a
# human makes the decision, resolved once confirmed, stale when either the
# source or design changed, and superseded when replaced by a newer decision.
SOURCE_MAPPING_STATUSES: frozenset[str] = frozenset(
    {"unresolved", "resolved", "stale", "superseded"}
)

# Graduated staleness severity (DEC-454). Low = likely still valid (rename);
# high = translation logic may be wrong (type change, structural change).
SOURCE_MAPPING_STALE_SEVERITIES: frozenset[str] = frozenset({"low", "high"})

# Why a mapping went stale (DEC-454).
SOURCE_MAPPING_STALE_REASONS: frozenset[str] = frozenset(
    {"source_changed", "design_changed"}
)

# Field-level mapping decision types (DEC-452). Finer than entity-level:
# direct (same field, identity), referential_exact (same intent, different name),
# referential_interpreted (requires translation logic), rejected.
FIELD_MAPPING_DECISION_TYPES: frozenset[str] = frozenset(
    {"direct", "referential_exact", "referential_interpreted", "rejected"}
)

# Value-level mapping decision types (DEC-452). Applied to individual enum
# values when field_mapping.decision_type is referential_interpreted.
VALUE_MAPPING_DECISION_TYPES: frozenset[str] = frozenset(
    {"direct", "interpreted", "rejected"}
)

# Translation types for field_mapping_translation (DEC-452). value_map applies
# per-value substitution; expression applies a formula/transformation.
FIELD_MAPPING_TRANSLATION_TYPES: frozenset[str] = frozenset(
    {"value_map", "expression"}
)

# Candidate types surfaced by the reconciler (DEC-451). Entity-level candidates
# are unmatched source entities; field-level are unmatched source fields; value-
# level are unmatched enum values on an already-mapped field.
MAPPING_CANDIDATE_TYPES: frozenset[str] = frozenset({"entity", "field", "value"})

# Confidence levels for reconciler-generated mapping suggestions (DEC-456).
MAPPING_SUGGESTION_CONFIDENCES: frozenset[str] = frozenset(
    {"high", "medium", "low"}
)
```

**1c. Add `source_mapping` and related types to `ENTITY_TYPES` and `CHANGE_LOG_ENTITY_TYPES`.**

`source_mapping`, `field_mapping`, and `mapping_candidate` are engagement-scoped methodology records that participate in the change_log. Add them to `ENTITY_TYPES`:

Find the block ending with:
```python
        "release",
    }
)
```

Add before the closing brace:
```python
        # PI-255 source instance mapping model (PRJ-027 / SES-230). The
        # candidate-gated human-decision layer between audit discovery and the
        # canonical design. source_mapping = entity-level decision (SMG-);
        # field_mapping = field-level decision (FMP-);
        # mapping_candidate = pre-decision reconciler output (no prefix — auto-id).
        "source_mapping",
        "field_mapping",
        "mapping_candidate",
```

`source_mapping_target`, `source_mapping_join`, `field_mapping_translation`, and `value_mapping` are child/support tables with no prefixed identifier and no `change_log` participation (same pattern as `instance_membership`, `field_options`). Do NOT add them to `ENTITY_TYPES`.

---

## Step 2 — Add ORM models to `models.py`

Read the full `models.py` first. Add the following seven model classes after the `InstanceMembership` model. Follow the exact patterns in that model for naming, column declarations, constraint naming, and the `__tablename__` / `__table_args__` style.

**Naming conventions:**
- Table names: `source_mappings`, `source_mapping_targets`, `source_mapping_joins`, `field_mappings`, `field_mapping_translations`, `value_mappings`, `mapping_candidates`
- Column prefix matches table singular: `source_mapping_*`, `field_mapping_*`, `value_mapping_*`, `mapping_candidate_*`
- All string columns use `Text` (not `String(n)`) per the codebase pattern
- Datetimes: `DateTime(timezone=True)`, nullable, no server default
- Engagement-scoped: all seven tables get `engagement_id` (Text, nullable, same FK pattern as `InstanceMembership`)
- No prefixed identifier on `source_mapping_target`, `source_mapping_join`, `field_mapping_translation`, `value_mapping` — use plain integer PK
- `source_mapping` and `field_mapping` and `mapping_candidate` get prefixed identifiers (`SMG-NNN`, `FMP-NNN`, no prefix on candidate — use auto-increment int PK)

**Model 1: `SourceMapping`** (`source_mappings` table)

Columns:
- `id` — Integer PK autoincrement
- `engagement_id` — Text FK → engagements.engagement_identifier, nullable, ON DELETE CASCADE
- `source_mapping_identifier` — Text, NOT NULL, UNIQUE (e.g. `SMG-001`)
- `instance_identifier` — Text, NOT NULL (FK to instances table)
- `source_entity_name` — Text, NOT NULL
- `decision_type` — Text, NOT NULL, CHECK in `SOURCE_MAPPING_DECISION_TYPES`
- `status` — Text, NOT NULL, default `'unresolved'`, CHECK in `SOURCE_MAPPING_STATUSES`
- `stale_reason` — Text, nullable, CHECK in `SOURCE_MAPPING_STALE_REASONS` (allow NULL)
- `stale_severity` — Text, nullable, CHECK in `SOURCE_MAPPING_STALE_SEVERITIES` (allow NULL)
- `superseded_by` — Text, nullable (self-referential: identifier of the superseding SMG)
- `notes` — Text, nullable
- `resolved_at` — DateTime(timezone=True), nullable
- `created_at` — DateTime(timezone=True), nullable
- `updated_at` — DateTime(timezone=True), nullable
- `deleted_at` — DateTime(timezone=True), nullable

Constraints: UNIQUE on `source_mapping_identifier`, CHECK on `decision_type`, CHECK on `status`.

**Model 2: `SourceMappingTarget`** (`source_mapping_targets` table)

Join table: one source_mapping → one or more design entities (decomposition support).

Columns:
- `id` — Integer PK autoincrement
- `engagement_id` — Text, nullable
- `source_mapping_identifier` — Text, NOT NULL (FK to source_mappings.source_mapping_identifier)
- `entity_identifier` — Text, NOT NULL (the design entity ENT-NNN this mapping targets)

Constraints: UNIQUE on `(source_mapping_identifier, entity_identifier)`.

**Model 3: `SourceMappingJoin`** (`source_mapping_joins` table)

The join key declared at entity-mapping level (inherited by all field mappings).

Columns:
- `id` — Integer PK autoincrement
- `engagement_id` — Text, nullable
- `source_mapping_identifier` — Text, NOT NULL UNIQUE (one join per source_mapping)
- `source_field_name` — Text, NOT NULL
- `design_entity_identifier` — Text, NOT NULL (ENT-NNN — which design entity holds the join field)
- `design_field_identifier` — Text, NOT NULL (FLD-NNN — the join field on the design entity)

Constraints: UNIQUE on `source_mapping_identifier` (one join per entity mapping).

**Model 4: `FieldMapping`** (`field_mappings` table)

Columns:
- `id` — Integer PK autoincrement
- `engagement_id` — Text, nullable
- `field_mapping_identifier` — Text, NOT NULL, UNIQUE (e.g. `FMP-001`)
- `source_mapping_identifier` — Text, NOT NULL (FK to source_mappings.source_mapping_identifier)
- `source_field_name` — Text, NOT NULL
- `decision_type` — Text, NOT NULL, CHECK in `FIELD_MAPPING_DECISION_TYPES`
- `status` — Text, NOT NULL, default `'unresolved'`, CHECK in `SOURCE_MAPPING_STATUSES`
- `stale_reason` — Text, nullable, CHECK in `SOURCE_MAPPING_STALE_REASONS` (allow NULL)
- `stale_severity` — Text, nullable, CHECK in `SOURCE_MAPPING_STALE_SEVERITIES` (allow NULL)
- `target_entity_identifier` — Text, nullable (ENT-NNN — which design entity this field lands on)
- `target_field_identifier` — Text, nullable (FLD-NNN — the design field)
- `superseded_by` — Text, nullable (identifier of the superseding FMP)
- `notes` — Text, nullable
- `resolved_at` — DateTime(timezone=True), nullable
- `created_at` — DateTime(timezone=True), nullable
- `updated_at` — DateTime(timezone=True), nullable
- `deleted_at` — DateTime(timezone=True), nullable

**Model 5: `FieldMappingTranslation`** (`field_mapping_translations` table)

Only present when `field_mapping.decision_type = 'referential_interpreted'`.

Columns:
- `id` — Integer PK autoincrement
- `engagement_id` — Text, nullable
- `field_mapping_identifier` — Text, NOT NULL UNIQUE (one translation per field_mapping)
- `translation_type` — Text, NOT NULL, CHECK in `FIELD_MAPPING_TRANSLATION_TYPES`
- `expression` — Text, nullable (for expression-based translations)

**Model 6: `ValueMapping`** (`value_mappings` table)

Value-level mapping decision for individual enum values.

Columns:
- `id` — Integer PK autoincrement
- `engagement_id` — Text, nullable
- `field_mapping_identifier` — Text, NOT NULL (FK to field_mappings.field_mapping_identifier)
- `source_value` — Text, NOT NULL
- `decision_type` — Text, NOT NULL, CHECK in `VALUE_MAPPING_DECISION_TYPES`
- `target_value` — Text, nullable (null when rejected)
- `status` — Text, NOT NULL, default `'unresolved'`, CHECK in `SOURCE_MAPPING_STATUSES`
- `superseded_by` — Integer, nullable (FK to value_mappings.id — self-referential by PK since no prefix)
- `notes` — Text, nullable
- `created_at` — DateTime(timezone=True), nullable
- `updated_at` — DateTime(timezone=True), nullable

Constraints: UNIQUE on `(field_mapping_identifier, source_value)` where `superseded_by IS NULL` — enforced at the access layer, not as a DB constraint (partial unique indexes not portable).

**Model 7: `MappingCandidate`** (`mapping_candidates` table)

Pre-decision reconciler output. Auto-increment PK, no SMG/FMP prefix.

Columns:
- `id` — Integer PK autoincrement
- `engagement_id` — Text, nullable
- `instance_identifier` — Text, NOT NULL
- `audit_event_identifier` — Text, nullable (the deposit_event identifier that surfaced this)
- `candidate_type` — Text, NOT NULL, CHECK in `MAPPING_CANDIDATE_TYPES`
- `source_entity_name` — Text, NOT NULL
- `source_field_name` — Text, nullable (null for entity-level candidates)
- `source_value` — Text, nullable (null for entity/field candidates)
- `suggested_source_mapping_identifier` — Text, nullable (SMG-NNN suggestion)
- `suggested_field_mapping_identifier` — Text, nullable (FMP-NNN suggestion)
- `suggestion_confidence` — Text, nullable, CHECK in `MAPPING_SUGGESTION_CONFIDENCES` (allow NULL)
- `suggestion_basis` — Text, nullable (free text: "identical_to_INST-001", "name_similarity", etc.)
- `resolved` — Boolean (stored as Integer 0/1 per SQLite pattern), NOT NULL, default 0
- `resolved_at` — DateTime(timezone=True), nullable
- `resolved_to_source_mapping_identifier` — Text, nullable
- `resolved_to_field_mapping_identifier` — Text, nullable
- `created_at` — DateTime(timezone=True), nullable

---

## Step 3 — Write migration `0079_pi_255_source_mapping_tables.py`

Location: `migrations/versions/0079_pi_255_source_mapping_tables.py`

Follow the exact pattern of `0059_pi_185_instance_membership.py`:

```python
"""PI-255 (PRJ-027/SES-230) — source instance mapping model tables.

Creates seven new tables for the candidate-gated source mapping layer:
source_mappings, source_mapping_targets, source_mapping_joins,
field_mappings, field_mapping_translations, value_mappings,
mapping_candidates.

Also rebuilds the instance_memberships state CHECK to add
'candidate_pending' and 'mapping_stale' (via batch ALTER on SQLite).

SQLite chain head 0078 -> 0079.
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import (
    SourceMapping,
    SourceMappingTarget,
    SourceMappingJoin,
    FieldMapping,
    FieldMappingTranslation,
    ValueMapping,
    MappingCandidate,
    InstanceMembership,
)
from crmbuilder_v2.access.vocab import INSTANCE_MEMBERSHIP_STATES

revision: str = "0079_pi_255_source_mapping_tables"
down_revision: str | None = "0078_pi_249_release_back_half"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    # Create the seven new tables from ORM __table__ definitions.
    for model in (
        SourceMapping,
        SourceMappingTarget,
        SourceMappingJoin,
        FieldMapping,
        FieldMappingTranslation,
        ValueMapping,
        MappingCandidate,
    ):
        model.__table__.create(op.get_bind(), checkfirst=True)

    # Rebuild the instance_memberships state CHECK to include the two new states.
    # SQLite requires batch mode for CHECK constraint changes.
    existing = _tables()
    if InstanceMembership.__tablename__ in existing:
        states_check = ", ".join(f"'{s}'" for s in sorted(INSTANCE_MEMBERSHIP_STATES))
        with op.batch_alter_table(InstanceMembership.__tablename__) as batch_op:
            batch_op.drop_constraint("ck_instance_memberships_state", type_="check")
            batch_op.create_check_constraint(
                "ck_instance_memberships_state",
                f"state IN ({states_check})",
            )


def downgrade() -> None:
    existing = _tables()
    for model in reversed((
        SourceMapping,
        SourceMappingTarget,
        SourceMappingJoin,
        FieldMapping,
        FieldMappingTranslation,
        ValueMapping,
        MappingCandidate,
    )):
        if model.__tablename__ in existing:
            model.__table__.drop(op.get_bind())
    # Revert the instance_memberships state CHECK to the original three states.
    if InstanceMembership.__tablename__ in existing:
        original = frozenset({"present", "drifted", "absent"})
        states_check = ", ".join(f"'{s}'" for s in sorted(original))
        with op.batch_alter_table(InstanceMembership.__tablename__) as batch_op:
            batch_op.drop_constraint("ck_instance_memberships_state", type_="check")
            batch_op.create_check_constraint(
                "ck_instance_memberships_state",
                f"state IN ({states_check})",
            )
```

**Important:** Check the actual constraint name for the instance_memberships state CHECK by reading the existing migration `0059_pi_185_instance_membership.py` and confirming the constraint name used. Use whatever name is actually in the existing migration — do not assume `ck_instance_memberships_state` if it differs.

---

## Step 4 — Write repository modules

Create five files in `src/crmbuilder_v2/access/repositories/`:

### 4a. `source_mapping.py`

Module-level docstring: PI-255 source mapping entity-level repository. Backs `/source-mappings` REST endpoints (Slice 2). Follows the `instances.py` and `migration_mapping.py` patterns.

Provide:
- `_ENTITY_TYPE = "source_mapping"`, `_IDENTIFIER_PREFIX = "SMG"`, `_IDENTIFIER_RE`
- `_PATCHABLE_FIELDS` frozenset
- `_require_decision_type`, `_require_status`, `_require_stale_reason`, `_require_stale_severity` helpers (using `gov.require_in`)
- `_get_row(session, identifier) -> SourceMapping`
- `list_source_mappings(session, *, instance_identifier=None, status=None, include_deleted=False) -> list[dict]`
- `get_source_mapping(session, identifier, *, include_deleted=False) -> dict | None`
- `next_source_mapping_identifier(session) -> str`
- `create_source_mapping(session, *, instance_identifier, source_entity_name, decision_type, notes=None, identifier=None) -> dict` — creates with `status='unresolved'`, emits change_log
- `update_source_mapping(session, identifier, *, source_entity_name, decision_type, status, notes=None, stale_reason=None, stale_severity=None, superseded_by=None, resolved_at=None) -> dict` — validates status transitions (unresolved→resolved, any→stale, resolved→superseded), emits change_log
- `patch_source_mapping(session, identifier, **fields) -> dict` — patches patchable fields
- `delete_source_mapping(session, identifier) -> dict` — soft-delete
- `restore_source_mapping(session, identifier) -> dict` — clears deleted_at
- `mark_stale(session, identifier, *, reason, severity) -> dict` — convenience: sets status=stale, stale_reason, stale_severity

Status transition rules: `unresolved → {resolved, stale, superseded}`, `resolved → {stale, superseded}`, `stale → {resolved, superseded}`, `superseded → {}`.

### 4b. `source_mapping_targets.py`

Simple child-table repository for `SourceMappingTarget`. No prefixed identifier, no change_log.

Provide:
- `list_targets(session, *, source_mapping_identifier) -> list[dict]`
- `add_target(session, *, source_mapping_identifier, entity_identifier) -> dict` — idempotent (no-op if already exists)
- `remove_target(session, *, source_mapping_identifier, entity_identifier) -> None` — hard delete (child table, no soft-delete)
- `set_targets(session, *, source_mapping_identifier, entity_identifiers: list[str]) -> list[dict]` — replace all targets atomically (delete old, add new)

### 4c. `field_mapping.py`

Same pattern as `source_mapping.py` but for `FieldMapping`. Prefix `FMP`.

Provide:
- `list_field_mappings(session, *, source_mapping_identifier=None, status=None, include_deleted=False) -> list[dict]`
- `get_field_mapping(session, identifier, *, include_deleted=False) -> dict | None`
- `next_field_mapping_identifier(session) -> str`
- `create_field_mapping(session, *, source_mapping_identifier, source_field_name, decision_type, target_entity_identifier=None, target_field_identifier=None, notes=None, identifier=None) -> dict`
- `update_field_mapping(session, identifier, *, source_field_name, decision_type, status, target_entity_identifier=None, target_field_identifier=None, notes=None, stale_reason=None, stale_severity=None, superseded_by=None, resolved_at=None) -> dict`
- `patch_field_mapping(session, identifier, **fields) -> dict`
- `delete_field_mapping(session, identifier) -> dict`
- `restore_field_mapping(session, identifier) -> dict`
- `mark_stale(session, identifier, *, reason, severity) -> dict`

Same status transition rules as source_mapping.

### 4d. `value_mapping.py`

Simple repository for `ValueMapping`. No prefixed identifier; uses integer PK. No change_log (same pattern as `instance_membership`).

Provide:
- `list_value_mappings(session, *, field_mapping_identifier) -> list[dict]` — returns only active (superseded_by IS NULL) unless `include_superseded=True`
- `get_value_mapping(session, id_: int) -> dict | None`
- `create_value_mapping(session, *, field_mapping_identifier, source_value, decision_type, target_value=None, notes=None) -> dict` — validates no existing active mapping for (field_mapping_identifier, source_value)
- `update_value_mapping(session, id_: int, *, decision_type, target_value=None, notes=None, status=None) -> dict`
- `supersede_value_mapping(session, id_: int, *, replacement_id: int) -> dict` — sets superseded_by on the old row

### 4e. `mapping_candidate.py`

Repository for `MappingCandidate`. Auto-increment PK.

Provide:
- `list_candidates(session, *, instance_identifier=None, candidate_type=None, resolved=None) -> list[dict]`
- `get_candidate(session, id_: int) -> dict | None`
- `create_candidate(session, *, instance_identifier, candidate_type, source_entity_name, source_field_name=None, source_value=None, audit_event_identifier=None, suggested_source_mapping_identifier=None, suggested_field_mapping_identifier=None, suggestion_confidence=None, suggestion_basis=None) -> dict`
- `resolve_candidate(session, id_: int, *, resolved_to_source_mapping_identifier=None, resolved_to_field_mapping_identifier=None) -> dict` — sets resolved=True, resolved_at, resolved_to_*
- `bulk_create_candidates(session, candidates: list[dict]) -> list[dict]` — batch insert for reconciler use

---

## Step 5 — Write tests

Create `tests/test_source_mapping_foundation.py`.

Test coverage required:

**Vocab:**
- `INSTANCE_MEMBERSHIP_STATES` contains `'candidate_pending'` and `'mapping_stale'`
- `SOURCE_MAPPING_DECISION_TYPES`, `SOURCE_MAPPING_STATUSES`, `FIELD_MAPPING_DECISION_TYPES`, `VALUE_MAPPING_DECISION_TYPES`, `MAPPING_CANDIDATE_TYPES` all non-empty frozensets

**Migration:**
- Migration `0079` creates all seven tables (use the standard migration round-trip pattern from existing tests)
- All seven tables survive a downgrade and re-upgrade cycle

**Repository — source_mapping:**
- Create with `decision_type='direct'`, verify `status='unresolved'`
- List by `instance_identifier` filter
- Patch `notes` field
- `mark_stale` transitions status to `'stale'` with reason and severity
- Soft-delete and restore round-trip
- Invalid `decision_type` raises `UnprocessableError`
- Invalid status transition raises `StatusTransitionError`

**Repository — source_mapping_targets:**
- `add_target` is idempotent
- `set_targets` replaces atomically
- `remove_target` removes one without affecting others

**Repository — field_mapping:**
- Create, list by `source_mapping_identifier`, mark_stale, soft-delete

**Repository — value_mapping:**
- Create, list (active only by default), supersede round-trip
- Duplicate (field_mapping_identifier, source_value) on active rows raises conflict

**Repository — mapping_candidate:**
- Create entity-level candidate, field-level candidate
- `resolve_candidate` sets `resolved=True` and `resolved_to_*`
- `bulk_create_candidates` inserts multiple records

---

## Step 6 — Run tests, verify migration

```bash
# Run just the new test file
uv run pytest tests/test_source_mapping_foundation.py -v

# Run the full suite to check for regressions
uv run pytest tests/ -x -q

# Verify migration head
uv run alembic -c migrations/alembic.ini heads
```

---

## Step 7 — Commit

```bash
git add -A
git commit -m "v2: PI-255 slice 1 — source mapping foundation (vocab, models, migration 0079, repositories)"
```

Do NOT push. Doug pushes.

---

## Done

Reply with:
- Test results summary (passed/failed counts)
- Migration head after upgrade
- Any deviations from this spec and why
- Confirmation that the full suite is green
