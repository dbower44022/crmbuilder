# CLAUDE-CODE-PROMPT-build-field

**Last Updated:** 05-25-26
**Operating mode:** DETAIL
**Series:** PI-004 (additional methodology entity types beyond v0.4)
**Slice:** `field` — first and most urgent of the four PI-004 entity types (sequenced ahead of `persona`, `requirement`, `manual_config`, `test_spec` because the v0.4 thin `entity` schema gains real utility only when fields can attach).
**Status:** Ready to execute. Blocked by: nothing — `field.md` spec is canonical and complete.
**Companions:**
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/field.md` v1.0 — authoritative entity spec. **This prompt does not duplicate the spec; cite sections.**
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — parent entity type that `field` attaches to via the new `field_belongs_to_entity` edge. Pattern source for repository, router, panel, dialogs, schema migration.
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-A-commits-table-and-vocab.md` — structural template for the migration + vocab portion (CHECK swap pattern, pre-flight shape, commit shape).
- `crmbuilder-v2/migrations/versions/0008_v0_4_create_entities_table.py` — migration shape to mirror (entity table create); plus `0011_v0_7_governance_entities.py` for the multi-CHECK-extension pattern (refs + change_log).
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/entity.py` — repository pattern this slice mirrors with `field`-specific extensions.
- `crmbuilder-v2/src/crmbuilder_v2/api/routers/entities.py` — router pattern.
- `crmbuilder-v2/src/crmbuilder_v2/ui/panels/entities.py` — panel pattern.
- `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/entity_crud.py` + `_entity_schema.py` — dialog pattern.
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — vocab pattern (relationship-kind addition + `_kinds_for_pair` extension).
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/references.py` — references repository where the `field_belongs_to_entity` cardinality-on-DELETE guard lands.

---

## Purpose

Land the `field` methodology entity type end-to-end per `field.md` v1.0. This slice satisfies the first portion of PI-004 (the four-entity workstream that follows v0.4) and adopts the conventions inherited from `domain.md` (DEC-046, DEC-047, DEC-048) and applied across `entity.md` / `process.md` / `crm_candidate.md`. After this slice lands:

- The `fields` table exists in the engagement DB with the nine columns from `field.md` §3.2.
- The `field_belongs_to_entity` relationship kind is registered in vocab and admitted by the `refs.relationship_kind` CHECK.
- A field row plus its mandatory outgoing `field_belongs_to_entity` edge land atomically on `POST /fields` per `field.md` §3.5.4 (the one deviation from the cross-spec default endpoint set).
- The references repository enforces the 1:1-mandatory cardinality on DELETE (rejects deletion of the only live `field_belongs_to_entity` edge of a live field).
- All eight standard endpoints work (`GET` list, `GET` next-identifier, `GET` by id, `POST`, `PUT`, `PATCH`, `DELETE`, `POST /restore`) under the v2 `{data, meta, errors}` envelope.
- The Fields entry appears under the Methodology sidebar group at position #5 (after Domains, Entities, Processes, CRM Candidates) with a plain `ListDetailPanel`. Master-pane entity grouping is **deferred** to a follow-on slice (see Step 12 below).
- Soft-delete and restore round-trip the row plus the mandatory edge atomically per `field.md` §3.4.6.
- At least 20 tests pass across access / API / UI smoke layers, including atomic-POST and cardinality-violation tests.

This slice does NOT:

- Implement the master-pane primary grouping by parent entity (`field.md` §3.6.2 master-pane deviation) — deferred to a follow-on slice with a TODO comment in `panels/field.py` citing §3.6.2.
- Implement the "Move to entity" reparenting affordance (`field.md` §3.6.5 + PI-053).
- Add inbound reference kinds (none declared until source-side specs like the extended `process` under PI-005 land).
- Add the `?field_status=` / `?field_type=` server-side filters (deferred per `field.md` §3.5.5).
- Resolve PI-004. **Closes the field portion only.** PI-004 collectively covers `field` + `persona` (PI-003) + `requirement` + `manual_config` + `test_spec`; resolution waits for the final sibling's build-closure session per the DEC-232 / SES-074 build-closure pattern (CLAUDE.md "v2 session lifecycle — planning item resolution"). This slice records `addresses_planning_items: [{"planning_item_identifier": "PI-004"}]` with `resolves_planning_items: []`.

---

## Pre-flight

1. **Confirm working directory.** `pwd` resolves to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes.

3. **Confirm git identity:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts.

5. **Read the spec.** Read all of `PRDs/product/crmbuilder-v2/methodology-schema-specs/field.md` v1.0. Field counts and constraints below reference its sections by number; do not re-derive.

6. **Read the canonical pattern sources.** In order:
   - `crmbuilder-v2/migrations/versions/0008_v0_4_create_entities_table.py` — table-create pattern.
   - `crmbuilder-v2/migrations/versions/0011_v0_7_governance_entities.py` — multi-CHECK-extension pattern (refs + change_log) you will mirror.
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/entity.py` — repository pattern in full (~480 lines). Note `_insert_with_autoassign` (SAVEPOINT-retry), `_check_transition`, `_reject_duplicate_name`, `emit` change-log calls. The `field` repo extends this shape with atomic-POST and per-entity name scoping.
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/references.py` end-to-end — you will add the cardinality guard inside `delete_by_id` and `delete` (the two delete paths).
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/entities.py` — router pattern (~120 lines).
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/entities.py` — panel pattern in full.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/entity_crud.py` + `_entity_schema.py` — dialog pattern.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` lines 660–795 — the `*_entity` client methods you will mirror for `*_field`.
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` end-to-end (~520 lines).

7. **Capture pre-migration Alembic head.**

   ```bash
   cd crmbuilder-v2
   uv run alembic current 2>&1
   cd ..
   ```

   Expected: `0012_v0_8_commits_and_blocked_by_rename (head)`. The next revision number is `0013_v0_5_create_fields_table`.

8. **Baseline test pass count.**

   ```bash
   cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -30 && cd ..
   ```

   Note the count; we expect at least 20 net-new passing tests after this slice.

9. **Capture pre-flight identifiers for collision checks** (per CLAUDE.md "v2 session lifecycle — planning item resolution" head-check guidance):

   ```bash
   curl -s 'http://127.0.0.1:8765/sessions/next-identifier' | python3 -c "import sys, json; print('next SES:', json.load(sys.stdin)['data']['next'])"
   curl -s 'http://127.0.0.1:8765/decisions/next-identifier' | python3 -c "import sys, json; print('next DEC:', json.load(sys.stdin)['data']['next'])"
   curl -s 'http://127.0.0.1:8765/planning-items/next-identifier' | python3 -c "import sys, json; print('next PI:', json.load(sys.stdin)['data']['next'])"
   ```

   Note these values for the close-out payload at the end. The spec's planned identifiers are DEC-246..251 and PI-053..059; if those numbers are already claimed by parallel-sandbox work, re-key the close-out per the SES-077 pattern and report the re-key in the Done section.

10. **Confirm at least one live entity exists** for the API smoke tests. The atomic-POST test in Step 15 needs a live `ENT-NNN` to attach to.

    ```bash
    curl -s 'http://127.0.0.1:8765/entities' | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(f'live entities: {len(d)}'); [print(f'  {e[\"entity_identifier\"]}: {e[\"entity_name\"]}') for e in d[:5]]"
    ```

    If none exist, create one as part of the verify phase (Step 15) before exercising the atomic POST.

---

## Implementation

### Step 1 — Alembic migration `0013_v0_5_create_fields_table.py`

Create `crmbuilder-v2/migrations/versions/0013_v0_5_create_fields_table.py`. Wire:

```python
revision: str = "0013_v0_5_create_fields_table"
down_revision: Union[str, None] = "0012_v0_8_commits_and_blocked_by_rename"
```

The `upgrade()` function performs, in order:

**1a. Extend `refs.source_type` and `refs.target_type` CHECK constraints to admit `'field'`.** Pattern: drop existing CHECK constraint by name inside a `batch_alter_table`; add new CHECK with the extended set, alphabetically sorted. Mirror the CHECK-swap pattern from `0011` (and `0012`'s further extensions) verbatim. Both `source_type` and `target_type` admit `'field'`.

**1b. Extend `refs.relationship_kind` CHECK to admit `'field_belongs_to_entity'`.** Same `batch_alter_table` block as 1a — recopy the table once. The final value list is the v0.7 + v0.8 set from `0012` plus `'field_belongs_to_entity'`.

**1c. Extend `change_log.entity_type` CHECK to admit `'field'`.** Same pattern.

**1d. Create `fields` table per `field.md` §3.2.** Mirror `0008` (entities). The column inventory:

```python
op.create_table(
    "fields",
    sa.Column("field_identifier", sa.String(length=32), nullable=False),
    sa.Column("field_name", sa.String(length=255), nullable=False),
    sa.Column("field_description", sa.Text(), nullable=False),
    sa.Column("field_type", sa.String(length=32), nullable=False),
    sa.Column("field_required", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    sa.Column("field_notes", sa.Text(), nullable=True),
    sa.Column("field_status", sa.String(length=16), nullable=False),
    sa.Column("field_created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("field_updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("field_deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "field_identifier GLOB 'FLD-[0-9][0-9][0-9]'",
        name="ck_field_identifier_format",
    ),
    sa.CheckConstraint(
        "field_status IN ('candidate', 'confirmed', 'deferred')",
        name="ck_field_status",
    ),
    sa.CheckConstraint(
        "field_type IN ('boolean', 'date', 'datetime', 'derived', 'enum', "
        "'long_text', 'money', 'multi_enum', 'number', 'reference', 'text')",
        name="ck_field_type",
    ),
    sa.CheckConstraint(
        "field_required IN (0, 1)",
        name="ck_field_required_boolean",
    ),
    sa.PrimaryKeyConstraint("field_identifier"),
)
with op.batch_alter_table("fields", schema=None) as batch_op:
    batch_op.create_index("ix_fields_field_status", ["field_status"], unique=False)
    batch_op.create_index("ix_fields_field_type", ["field_type"], unique=False)
    batch_op.create_index("ix_fields_field_deleted_at", ["field_deleted_at"], unique=False)
```

Note the eleven `field_type` values come from `field.md` §3.2.3, sorted alphabetically for stable CHECK rendering. `field_required` uses SQLite's standard 0/1 representation; the SQLAlchemy ORM model returns Python booleans transparently. **No UNIQUE constraint on `(parent_entity_identifier, field_name)`** — there is no `parent_entity_identifier` column. Per-entity name uniqueness is enforced at the access layer by querying the `refs` table for the field's `field_belongs_to_entity` edge first (see Step 5).

The `downgrade()` function reverses in opposite order: drop `fields`, then drop the three CHECK extensions restoring the v0.8 set. Standard pattern from `0011` / `0012`.

### Step 2 — ORM model `Field` in `models.py`

Add a `Field` class to `crmbuilder-v2/src/crmbuilder_v2/access/models.py` after the `Entity` class (around line 353 by current count). Mirror the `Entity` class exactly with `field_`-prefixed columns. Include the table_args block with the four CHECK constraints (identifier format, status, type, required-boolean) and three indexes (status, type, deleted_at). Import `FIELD_STATUSES` and `FIELD_TYPES` (added in Step 3) for the `_check_in` helper calls. Per `field.md` §3.2 the docstring should cite that fields are an attribute on one CRM-modeled entity, parent-entity affiliation lives in `refs` not as an FK column, and the `field_required` column is a Boolean defaulting to `False`.

### Step 3 — Vocab additions in `vocab.py`

Four edits to `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`:

**3a. Add `FIELD_STATUSES` and `FIELD_STATUS_TRANSITIONS`.** Place after `CRM_CANDIDATE_STATUS_TRANSITIONS` (~line 79). Mirrors `ENTITY_STATUSES` and `ENTITY_STATUS_TRANSITIONS` exactly per `field.md` §3.4.1.

```python
# Methodology entity `field` lifecycle (PI-004 first slice, DEC-248).
# Mirrors ``domain`` / ``entity`` three-status propose-verify lifecycle
# exactly per ``field.md`` section 3.4.
FIELD_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred"}
)
FIELD_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred"}),
    "deferred": frozenset({"confirmed"}),
}
```

**3b. Add `FIELD_TYPES`.** Place alongside the lifecycle vocab above:

```python
# `field_type` enum (PI-004 first slice, DEC-250). 11-value v0.5
# vocabulary per ``field.md`` section 3.2.3. Richer types (`formula`,
# `link`, `address`, `phone`, `url`) deferred to v0.6+ per PI-054.
FIELD_TYPES: frozenset[str] = frozenset(
    {
        "text", "long_text", "enum", "multi_enum", "date", "datetime",
        "money", "boolean", "number", "reference", "derived",
    }
)
```

**3c. Add `'field'` to `ENTITY_TYPES`** (around line 287 in the v0.8 section comment area). Group with the methodology entities under a v0.5+ section comment naming PI-004:

```python
# PI-004 methodology additions (v0.5+). First slice adds `field`;
# subsequent slices add `persona`, `requirement`, `manual_config`,
# `test_spec`.
"field",
```

**3d. Add `'field_belongs_to_entity'` to `REFERENCE_RELATIONSHIPS`** (around line 244, after the v0.8 additions). Section comment names the kind and cites `field.md` §3.3.1 and DEC-249:

```python
# PI-004 first slice additions (v0.5+ methodology). One new kind:
#   - `field_belongs_to_entity` (field → entity; mandatory 1:1 at the
#     source side per ``field.md`` section 3.3.1 / DEC-249). Cardinality
#     enforced at the access layer, not the schema layer.
"field_belongs_to_entity",
```

**3e. Extend `_kinds_for_pair` for `(field, entity)`.** Add a new clause after the v0.8 Code Change Lifecycle block (around line 374):

```python
# PI-004 first slice additions (v0.5+ methodology):
if source_type == "field" and target_type == "entity":
    kinds.add("field_belongs_to_entity")
```

Per `field.md` §3.3.1 this is the only valid kind for `(field, entity)` in v0.5; no other source-target pair admits `field_belongs_to_entity`.

### Step 4 — Pydantic request schemas in `schemas.py`

Add three schema classes to `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` after `EntityPatchIn` (~line 228). Mirror entity but with the atomic-POST deviation.

```python
# ---------- Fields (methodology entity, PI-004 first slice) ----------


class FieldCreateIn(_Base):
    """POST /fields body.

    ``field_identifier`` is server-assigned when omitted; ``field_status``
    defaults to ``candidate`` server-side; ``field_required`` defaults to
    ``False`` server-side. ``field_belongs_to_entity_identifier`` is
    REQUIRED — the access layer creates the field row, the
    ``field_belongs_to_entity`` edge, and the change-log emit in one
    transaction per ``field.md`` section 3.5.4. This is the one
    deviation from the cross-spec decomposed-references default."""

    field_name: str
    field_description: str
    field_type: str
    field_belongs_to_entity_identifier: str
    field_required: bool | None = None
    field_notes: str | None = None
    field_status: str | None = None
    field_identifier: str | None = None


class FieldReplaceIn(_Base):
    """PUT /fields/{identifier} body — full record replace.

    Does NOT accept ``field_belongs_to_entity_identifier`` — re-parenting
    requires explicit edge management per ``field.md`` section 3.5.4
    (DELETE the old edge, POST the new edge). PI-053 tracks the future
    convenience endpoint."""

    field_identifier: str | None = None
    field_name: str
    field_description: str
    field_type: str
    field_required: bool
    field_notes: str | None = None
    field_status: str


class FieldPatchIn(_Base):
    """PATCH /fields/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``field_notes: null`` (clear) is distinguished from an
    omitted ``field_notes`` (leave unchanged). Does NOT accept
    ``field_belongs_to_entity_identifier`` for the same reason as PUT."""

    field_name: str | None = None
    field_description: str | None = None
    field_type: str | None = None
    field_required: bool | None = None
    field_notes: str | None = None
    field_status: str | None = None
```

### Step 5 — Repository `repositories/field.py`

Create `crmbuilder-v2/src/crmbuilder_v2/access/repositories/field.py` mirroring `entity.py`. Module-level constants:

```python
_ENTITY_TYPE = "field"
_IDENTIFIER_PREFIX = "FLD"
_IDENTIFIER_RE = re.compile(r"^FLD-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset({
    "name", "description", "type", "required", "notes", "status",
})
```

Function inventory and contracts:

**5a. `_require_identifier_format(identifier)`** — mirror entity.

**5b. `_require_nonempty(value, field=...)`** — mirror entity.

**5c. `_require_status(status)`** — mirror entity using `FIELD_STATUSES`.

**5d. `_require_type(field_type)`** — new helper validating against `FIELD_TYPES`. Raises `UnprocessableError` with field `"field_type"`, code `"invalid_value"`, message naming the sorted vocabulary.

**5e. `_check_transition(current, requested)`** — mirror entity using `FIELD_STATUS_TRANSITIONS`.

**5f. `_reject_duplicate_name_within_entity(session, name, entity_identifier, *, exclude_identifier=None)`** — **per-entity-scoped** uniqueness check per `field.md` §3.2.3. Two fields named `"status"` attached to two different entities are both valid. Implementation:

```python
def _reject_duplicate_name_within_entity(
    session: Session,
    name: str,
    entity_identifier: str,
    *,
    exclude_identifier: str | None = None,
) -> None:
    """Reject a case-insensitive name collision *within the parent entity*.

    Per ``field.md`` section 3.2.3: uniqueness is on
    ``(parent_entity_identifier, lower(field_name))``, not on
    ``field_name`` alone. The parent entity is resolved via the
    ``field_belongs_to_entity`` edge in the ``refs`` table — this
    function queries it directly rather than holding an FK column.
    """
    # Resolve all live field identifiers whose field_belongs_to_entity
    # edge points to entity_identifier. Then check the fields table for
    # a case-insensitive name collision among them (excluding the row
    # being updated, if any).
    from crmbuilder_v2.access.models import Field, Reference
    sibling_ids_stmt = select(Reference.source_id).where(
        Reference.source_type == "field",
        Reference.target_type == "entity",
        Reference.target_id == entity_identifier,
        Reference.relationship_kind == "field_belongs_to_entity",
    )
    stmt = select(Field).where(
        Field.field_identifier.in_(sibling_ids_stmt),
        func.lower(Field.field_name) == name.lower(),
        Field.field_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(Field.field_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "field_name",
                    "duplicate",
                    f"a field named {name!r} already exists on "
                    f"entity {entity_identifier}",
                )
            ]
        )
```

**5g. `_resolve_parent_entity_identifier(session, field_identifier)`** — new helper that resolves a field's parent entity identifier by querying the live `field_belongs_to_entity` edge. Returns `None` if the field has no live edge (the soft-deleted state during deletion mid-flight). Used by `update_field` / `patch_field` / `delete_field` / `restore_field`.

**5h. `_require_live_entity(session, entity_identifier)`** — new helper that loads the parent entity, raises `UnprocessableError` with code `"invalid_parent_entity"` and reason `"not_found"` or `"soft_deleted"` per `field.md` §3.5.4 if not present / soft-deleted.

**5i. `list_fields(session, *, entity_identifier=None, include_deleted=False)`** — per `field.md` §3.5.5 supports the `?entity_identifier=ENT-NNN` filter. When `entity_identifier` is supplied, joins through `refs` (the same shape as `_reject_duplicate_name_within_entity`'s sibling-ids subquery) and filters the result to fields whose live edge points there. Sort by `field_identifier` ascending. Returns `list[dict]`.

**5j. `get_field(session, identifier, *, include_deleted=False)`** — mirror entity.

**5k. `next_field_identifier(session)`** — mirror `next_entity_identifier`, scanning all rows including soft-deleted.

**5l. `create_field(session, *, field_belongs_to_entity_identifier, name, description, type, required=False, notes=None, status="candidate", identifier=None)`** — **atomic POST per `field.md` §3.5.4**. This is the deviation from entity. Sequence:

1. `_require_nonempty(name, field="field_name")`, `_require_nonempty(description, field="field_description")`.
2. `_require_type(type)`.
3. If `status is None`: `status = "candidate"`. `_require_status(status)`.
4. `if required is None: required = False`. (Boolean default per `field.md` §3.2.3.)
5. `_require_live_entity(session, field_belongs_to_entity_identifier)` — surfaces the missing-parent / soft-deleted-parent 422 per `field.md` §3.5.4.
6. `_reject_duplicate_name_within_entity(session, name, field_belongs_to_entity_identifier)` — per-entity-scoped uniqueness.
7. Inside a single transactional block:
   - If `identifier is None`: call `_insert_with_autoassign(...)` (mirror entity's SAVEPOINT-retry helper) to insert the row.
   - Else: `_require_identifier_format(identifier)`; collision check; insert.
   - Then call `references.create(session, source_type="field", source_id=row.field_identifier, target_type="entity", target_id=field_belongs_to_entity_identifier, relationship="field_belongs_to_entity")` to create the mandatory edge.
   - Then `emit(...)` for the field row.

The atomicity story: both the field row and the edge land in the same enclosing `session.begin()` block (the outer transactional scope is the FastAPI dependency `writable_session`). If the edge creation raises, the row insert rolls back as part of the same transaction. Test 14 (atomic-POST failure rollback) verifies this.

**Cardinality enforcement on POST is structural** (one row, one POST, one edge). The second `field_belongs_to_entity` edge case is enforced separately by the references repository — see Step 6.

**5m. `update_field(session, identifier, *, field_identifier=None, name, description, type, required, notes=None, status)`** — full replace (PUT). Mirror `update_entity` with the added `type` and `required` columns. Re-parenting is NOT supported via PUT (per `field.md` §3.5.4); `field_belongs_to_entity_identifier` is not in the signature. Status transition validated. Name-collision check uses `_resolve_parent_entity_identifier(session, identifier)` to scope the uniqueness query.

**5n. `patch_field(session, identifier, **fields)`** — partial update (PATCH). Mirror `patch_entity` with the added `type` / `required` keys. Same scoping behavior for name collisions. Status transition validated.

**5o. `delete_field(session, identifier)`** — soft-delete. Sequence:

1. `_get_row(session, identifier)`.
2. If already soft-deleted: return `to_dict(row)` (idempotent).
3. Resolve the live `field_belongs_to_entity` edge for this field (`refs` query). Soft-delete that edge by setting its `deleted_at` (if `refs` has a soft-delete column; if not, hard-delete inside the same transaction). **Read the current `refs` table schema before implementing this — references may be hard-deleted only.** If references are hard-deleted only, `delete_field` calls `references.delete(...)` to remove the edge atomically with setting `field_deleted_at`. Either way, the test must observe both effects atomic per `field.md` §3.4.6.
4. Set `row.field_deleted_at = datetime.now(UTC)`.
5. Flush; emit change-log.

**Important access-layer interaction with Step 6:** when `delete_field` removes the `field_belongs_to_entity` edge, the cardinality guard in the references repository (Step 6) MUST allow this deletion — the guard rejects deletion only when the source field is *live* (not soft-deleted). The sequence inside `delete_field` is therefore: set `field_deleted_at` first, flush, then call `references.delete(...)`. **Or**: pass a bypass flag through the references repo (cleaner). Adopt the bypass-flag approach: add a `_skip_cardinality_check: bool = False` kwarg to `references.delete()` and `references.delete_by_id()` (Step 6); `delete_field` calls with `_skip_cardinality_check=True`.

**5p. `restore_field(session, identifier)`** — clear `field_deleted_at`. Sequence:

1. `_get_row(session, identifier)`.
2. If NOT soft-deleted: raise `UnprocessableError` with `not_deleted` per entity pattern.
3. Resolve the previously-attached parent entity identifier (from the `refs` row that delete_field removed/soft-deleted; if hard-deleted, we need to read the parent from a history mechanism). **Recommendation:** store the previously-attached `entity_identifier` in a transient column or hold it in a separate `field_restore_state` cache. **Simpler:** during `delete_field`, hard-delete the edge but stash the target in a `_restore_target` JSON column on the field row, cleared on restore. **Simplest:** during `delete_field`, soft-delete the edge instead of hard-deleting it (if `refs` has `deleted_at`); during `restore_field`, clear `refs.deleted_at`. **Read `refs` schema during pre-flight (Step 6 below) to decide.** If `refs` has no soft-delete column, fall back to the stash approach: add a `field_previous_parent_entity_identifier` column to `fields` in the migration (Step 1d), populated on delete and read on restore.
4. `_require_live_entity(session, previous_parent)` — surface the 422 with `parent_entity_soft_deleted` per `field.md` §3.4.6 if the parent is itself soft-deleted.
5. Recreate or restore the edge atomically with clearing `field_deleted_at`.
6. Flush; emit change-log.

**Read `crmbuilder-v2/src/crmbuilder_v2/access/models.py` Reference class first.** If `Reference` has a `deleted_at` column, use soft-delete-on-the-edge. Otherwise add `field_previous_parent_entity_identifier` to the migration in Step 1d and use the stash approach. Document the choice in the migration's docstring.

All eight functions emit change-log entries via `emit(...)`.

### Step 6 — Cardinality guard in `repositories/references.py`

Per `field.md` §3.3.1 the `field_belongs_to_entity` edge is 1:1 mandatory at the source side. The access layer enforces this on three surfaces:

- **POST `/fields`** enforces it structurally (Step 5l).
- **POST `/references` to attach a second `field_belongs_to_entity` edge** to a field that already has one — must reject 422 with `cardinality_violation`.
- **DELETE `/references/{ref_id}` for the only live `field_belongs_to_entity` edge of a live field** — must reject 422 with `cardinality_violation`.

**6a. Extend `references.create()` with a cardinality check** for the `field_belongs_to_entity` kind. After the existing duplicate-tuple check, add:

```python
if relationship == "field_belongs_to_entity":
    # Reject second outgoing edge of this kind from a live field
    # per ``field.md`` section 3.3.1 (1:1 mandatory at source).
    existing_count = session.scalar(
        select(func.count(Reference.id)).where(
            Reference.source_type == "field",
            Reference.source_id == source_id,
            Reference.relationship_kind == "field_belongs_to_entity",
            # If refs has deleted_at, also: Reference.deleted_at.is_(None)
        )
    )
    if existing_count and existing_count > 0:
        raise UnprocessableError(
            [
                FieldError(
                    "relationship",
                    "cardinality_violation",
                    "field already has a field_belongs_to_entity edge; "
                    "delete the existing edge first",
                )
            ]
        )
```

Acceptance criterion 16 in `field.md` §3.7 specifies the error shape; align the `FieldError` code/message accordingly.

**6b. Extend `references.delete()` and `references.delete_by_id()` with a cardinality guard.** Add a `_skip_cardinality_check: bool = False` kwarg to both. When deleting an edge of kind `field_belongs_to_entity` and `_skip_cardinality_check is False`, look up the source field; if it is live (`field_deleted_at IS NULL`), reject with the spec's `cardinality_violation` shape — `{"error": "cardinality_violation", "relationship_kind": "field_belongs_to_entity", "min_outgoing": 1}` per `field.md` §3.7 criterion 16. If the field is soft-deleted, allow the deletion (this is the path `delete_field` takes via `_skip_cardinality_check=True`).

```python
def delete_by_id(session: Session, ref_id: int, *, _skip_cardinality_check: bool = False) -> dict:
    row = session.get(Reference, ref_id)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, str(ref_id))
    _guard_field_belongs_to_entity_delete(session, row, _skip_cardinality_check)
    # ... rest unchanged
```

Implement `_guard_field_belongs_to_entity_delete(session, row, skip)` as a private helper near the top of `references.py`:

```python
def _guard_field_belongs_to_entity_delete(
    session: Session,
    row: Reference,
    skip: bool,
) -> None:
    """Reject deletion of the only live field_belongs_to_entity edge
    of a live field. Per ``field.md`` section 3.3.1: a live field MUST
    have exactly one outgoing edge of this kind. The ``delete_field``
    repository path passes ``skip=True`` to bypass this check when
    soft-deleting the field and the edge together atomically.
    """
    if skip or row.relationship_kind != "field_belongs_to_entity":
        return
    from crmbuilder_v2.access.models import Field
    source = session.get(Field, row.source_id)
    if source is None or source.field_deleted_at is not None:
        # Source already gone or soft-deleted; permit the orphan-edge
        # cleanup.
        return
    raise UnprocessableError(
        [
            FieldError(
                "relationship",
                "cardinality_violation",
                f"field {row.source_id} requires exactly one live "
                "field_belongs_to_entity edge; cannot delete this edge "
                "while the field is live (delete the field instead, "
                "or soft-delete it first)",
            )
        ]
    )
```

Make sure both `delete()` and `delete_by_id()` apply the guard before the `session.delete(row)` call.

### Step 7 — Router `routers/field.py`

Create `crmbuilder-v2/src/crmbuilder_v2/api/routers/field.py` mirroring `entities.py`. Eight endpoints per `field.md` §3.5.1:

```python
router = APIRouter(prefix="/fields", tags=["fields"])
_FIELD_PREFIX = "field_"
```

- `GET ""` — `list_fields(s, entity_identifier=..., include_deleted=...)`. Both query params supported per `field.md` §3.5.5.
- `GET "/next-identifier"` — returns `{"next": next_field_identifier(s)}`.
- `GET "/{identifier}"` — returns 404 via `NotFoundError("field", identifier)` if not found.
- `POST ""` — `status_code=201`, body `FieldCreateIn`. Calls `field.create_field(...)` with **all** body fields including `field_belongs_to_entity_identifier`. The repository handles atomicity per Step 5l.
- `PUT "/{identifier}"` — body `FieldReplaceIn`. Does NOT accept the parent-entity body key.
- `PATCH "/{identifier}"` — body `FieldPatchIn`. Strip `field_` prefix as in `entities.py` patch handler.
- `DELETE "/{identifier}"` — `field.delete_field(s, identifier)`.
- `POST "/{identifier}/restore"` — `field.restore_field(s, identifier)`.

### Step 8 — Register in `main.py`

Edit `crmbuilder-v2/src/crmbuilder_v2/api/main.py`:

- Import `field` alongside the other router imports (alphabetical-adjacent placement after `engagements`, `entities`).
- `app.include_router(field.router)` after `entities` and before `processes` in the include block.

### Step 9 — UI client methods

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/client.py`. Mirror the eight `*_entity` methods around line 660–795. Add:

- `list_fields(self, entity_identifier=None, include_deleted=False)` — supports both query params.
- `get_field(self, identifier)`.
- `create_field(self, body)` — body must include `field_belongs_to_entity_identifier`.
- `update_field(self, identifier, body)`.
- `patch_field(self, identifier, body)`.
- `delete_field(self, identifier)`.
- `restore_field(self, identifier)`.
- `next_field_identifier(self)`.

All eight follow the existing client patterns (typed return shapes, envelope unwrapping, error mapping).

### Step 10 — Sidebar entry

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py`:

- Add `"Fields"` to the `"Methodology"` group entries tuple at position #5 (after `"CRM Candidates"`).
- Update the section comment naming PI-004 first slice for the addition.

Resulting Methodology group:

```python
(
    "Methodology",
    ("Domains", "Entities", "Processes", "CRM Candidates", "Fields"),
),
```

### Step 11 — Main window dispatch + entity-type map + refresh map

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py`:

- Add `from crmbuilder_v2.ui.panels.field import FieldsPanel` alongside the other panel imports.
- Add `"field": "Fields"` to `ENTITY_TYPE_TO_SIDEBAR_LABEL` under the methodology section.
- Add the dispatch case `elif entry == "Fields": page = FieldsPanel(self._client)` after the `"CRM Candidates"` case.

Edit `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py`:

- Add `"fields.json": "field"` to `_FILENAME_TO_ENTITY_TYPE` under the methodology section.

### Step 12 — Panel `panels/field.py`

Create `crmbuilder-v2/src/crmbuilder_v2/ui/panels/field.py` mirroring `panels/entities.py`. Use the plain `ListDetailPanel` shape — **defer the master-pane primary-grouping-by-entity deviation from `field.md` §3.6.2 to a follow-on slice.** Place a TODO comment at the top of the file:

```python
# TODO: master-pane primary grouping by parent entity per field.md §3.6.2
# (PI-004 follow-on slice). v1 ships with a flat identifier-sorted list;
# at CBM-redo scale (200+ fields) the grouped view becomes the default.
```

Detail-pane fields in `field.md` §3.2 order:

1. `field_identifier` — read-only label.
2. `field_name` — read-only single-line text.
3. **Parent entity** — read-only label rendered from the live `field_belongs_to_entity` edge target. Plain text in v1; the "Move to entity" affordance from `field.md` §3.6.5 / PI-053 is **deferred** with another TODO comment.
4. `field_description` — read-only multi-line text.
5. `field_type` — read-only combo or label showing the enum value.
6. `field_required` — read-only checkbox (disabled), label "Required for every record".
7. `field_notes` — under a `CollapsibleSection("Internal notes", ...)`, collapsed by default per `field.md` §3.6.3.
8. `field_status` — disabled combo showing current + valid successors (mirror entity panel's `status_choices` pattern).
9. `ReferencesSection` widget — for forward-consistency (no inbound kinds declared in v0.5; widget always present per `field.md` §3.6.3).

The outgoing `field_belongs_to_entity` edge is rendered separately at position #3 (NOT inside the generic `ReferencesSection`) per `field.md` §3.6.3.

Master-pane columns from `field.md` §3.6.2 (flat sort in v1):

| Stored field | Display header | Width |
|--------------|----------------|-------|
| `field_identifier` | Identifier | narrow |
| Entity (derived from edge) | Entity | narrow |
| `field_name` | Name | wide |
| `field_type` | Type | narrow |
| `field_status` | Status | narrow |
| `field_updated_at` | Updated | narrow |

The Entity column resolves the parent entity per row by querying the `field_belongs_to_entity` edge from `extras` (precompute in `fetch_records` or `fetch_detail_extras`). For v1's flat sort, sort by `field_identifier` ascending — the entity-grouping master-pane deviation comes in the follow-on slice.

Right-click context menu offers New / Edit / Delete / Restore per `field.md` §3.6.2.

### Step 13 — Dialogs `dialogs/field_crud.py` + `dialogs/_field_schema.py`

**13a. `_field_schema.py`** mirrors `_entity_schema.py`. Field-schema declarations in `field.md` §3.2 order, with two additions over entity:

- `status_choices(current)` — mirror entity's helper using `FIELD_STATUS_TRANSITIONS`.
- `type_choices()` — returns the sorted list of `FIELD_TYPES`. No transition logic (type can change freely; not a lifecycle field).
- Field-schema for `field_type` — `widget="combo"`, `vocab=FIELD_TYPES`, `compute_options=lambda state: type_choices()`. No `compute_options`-on-current logic needed.
- Field-schema for `field_required` — `widget="checkbox"`, `default=False`.
- Field-schema for `field_belongs_to_entity_identifier` — **create dialog only**. Widget: a searchable picker for live entities (use the existing `EntityIdentifierPicker` widget at `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/entity_identifier_picker.py` — read it first to confirm the API). Required on create; the field is not in the edit dialog schema because PUT/PATCH does not accept reparenting per `field.md` §3.5.4.

**13b. `field_crud.py`** mirrors `entity_crud.py`. Three classes:

- `FieldCreateDialog(EntityCrudDialog)` — `mode="create"`, `entity_fields(include_identifier=False)`. The Create dialog includes the parent-entity picker. On submit, the body POST'd by the dialog must include `field_belongs_to_entity_identifier` (the picker's value).
- `FieldEditDialog(EntityCrudDialog)` — `mode="edit"`, `entity_fields(include_identifier=True)`. Parent entity displayed as read-only label (no picker; reparenting per `field.md` §3.6.5 is deferred). Status combo restricted to valid successors.
- `FieldDeleteDialog(EntityCrudDeleteDialog)` — edge-text confirmation per `field.md` §3.6.6. Same `confirm_edit` pattern as `EntityDeleteDialog`; user types the `FLD-NNN` identifier to enable the Delete button.

### Step 14 — Tests

Add test files mirroring the existing entity test structure:

- `tests/crmbuilder_v2/access/test_field.py` — at least 12 tests.
- `tests/crmbuilder_v2/api/test_field_api.py` — at least 6 tests.
- `tests/crmbuilder_v2/ui/test_field_panel.py` — at least 2 smoke tests.

Minimum 20 tests total. Required test cases (citing `field.md` §3.7 acceptance criteria where applicable):

**Access-layer tests** (`test_field.py`):

1. `test_create_field_with_explicit_identifier_and_edge_atomically` — creates `FLD-001` attached to a seed `ENT-001`; asserts both the field row and the `field_belongs_to_entity` edge exist after one POST. (AC 1, 16)
2. `test_create_field_server_assigns_identifier` — `identifier=None`, assert next `FLD-NNN` value returned. (AC 8)
3. `test_create_field_rejects_invalid_field_type` — `field_type="bogus"` raises `UnprocessableError`. (AC 4)
4. `test_create_field_rejects_invalid_status` — same shape, status enum. (AC 5)
5. `test_create_field_rejects_invalid_status_transition` — PATCH from `confirmed` to `candidate` raises `StatusTransitionError`. (AC 5)
6. `test_create_field_rejects_missing_parent_entity_identifier` — atomic-POST without `field_belongs_to_entity_identifier` raises `UnprocessableError` with `"invalid_parent_entity"` or `"missing_parent_entity"` per `field.md` §3.5.4. (AC 16)
7. `test_create_field_rejects_nonexistent_parent_entity` — points to `ENT-999` (no live record); raises with `"invalid_parent_entity"` reason `"not_found"`. (AC 16)
8. `test_create_field_rejects_soft_deleted_parent_entity` — POST after soft-deleting the parent; raises with reason `"soft_deleted"`. (AC 16)
9. `test_field_name_uniqueness_is_per_entity_scoped` — create `Contact.status` (FLD-001 → ENT-001) and `Mentor.status` (FLD-002 → ENT-002); both succeed. Second `Contact.status` attempt raises `duplicate`. (AC 3)
10. `test_delete_field_soft_deletes_row_and_edge_atomically` — DELETE; both the row and the edge are no longer live; both reappear under include_deleted=True. (AC 9)
11. `test_restore_field_clears_deletion_and_restores_edge_atomically` — POST `/restore`; both row and edge are live again. (AC 9)
12. `test_restore_field_rejects_when_parent_entity_is_soft_deleted` — soft-delete the field, then soft-delete the parent entity, then restore the field; raises with `"parent_entity_soft_deleted"`. (AC 9)

**References-cardinality tests** (in `test_field.py` or `tests/crmbuilder_v2/access/test_references.py` — match the existing references test placement):

13. `test_cannot_create_second_field_belongs_to_entity_edge_for_live_field` — POST `/references` to attach a second edge; raises `cardinality_violation`. (AC 16)
14. `test_cannot_delete_only_field_belongs_to_entity_edge_of_live_field` — DELETE `/references/{ref_id}` on a live field's only edge; raises `cardinality_violation`. (AC 16)
15. `test_delete_field_path_can_remove_the_edge_via_skip_flag` — internal repo-to-repo call with `_skip_cardinality_check=True` succeeds. (AC 9)

**Vocab tests** (one slim test, in `test_field.py` or `test_vocab.py`):

16. `test_field_kind_registered_and_constrained` — assert `'field' in ENTITY_TYPES`, `'field_belongs_to_entity' in REFERENCE_RELATIONSHIPS`, `_kinds_for_pair("field", "entity") == frozenset({"is_about", "references", "field_belongs_to_entity"})`. (AC 15)

**API tests** (`test_field_api.py`):

17. `test_post_fields_endpoint_atomic_creation` — through TestClient; assert response envelope, identifier, parent edge present. (AC 7, 13)
18. `test_get_fields_filtered_by_entity_identifier` — assert the `?entity_identifier=ENT-NNN` filter returns only the right fields. (AC 7)
19. `test_patch_fields_endpoint_rejects_field_belongs_to_entity_identifier` — PATCH body that includes the parent-entity key returns 422 (unknown patchable field). (AC 7)
20. `test_delete_then_restore_roundtrip_via_api` — happy-path round-trip through TestClient. (AC 9)
21. `test_next_identifier_endpoint` — `GET /fields/next-identifier` returns the expected next value.
22. `test_post_fields_envelope_on_validation_error` — bogus field_type returns the v2 `{data: null, meta, errors: [...]}` envelope shape. (AC 7)

**UI smoke tests** (`test_field_panel.py`):

23. `test_panel_renders_with_no_fields` — `FieldsPanel` constructs and shows the empty state.
24. `test_panel_renders_with_one_field` — fixture-seeded field; panel master shows it; selecting it renders the detail pane including the parent-entity label.

Run the suite to confirm:

```bash
cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -50 && cd ..
```

Expected: baseline pass count + at least 20 new tests passing.

### Step 15 — Apply migration and run API verification

**15a. Apply the migration:**

```bash
cd crmbuilder-v2
uv run alembic upgrade head 2>&1
uv run alembic current 2>&1
# Expected: 0013_v0_5_create_fields_table (head)
cd ..
```

**15b. Restart the API** (if running) so it picks up the new router. Verify:

```bash
curl -s 'http://127.0.0.1:8765/fields' | python3 -c "import sys, json; d = json.load(sys.stdin); print('envelope ok:', list(d.keys())); print('data:', d.get('data'))"
```

Expected: `envelope ok: ['data', 'meta', 'errors']`; `data: []`.

**15c. Pick a live entity for the atomic-POST test.** Use the entity identifier captured in pre-flight Step 10. If none existed, create one:

```bash
curl -s -X POST http://127.0.0.1:8765/entities -H 'Content-Type: application/json' \
  -d '{"entity_name":"Field smoke test entity","entity_description":"created for the field-build smoke verification","entity_status":"confirmed"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['entity_identifier'])"
```

Note the returned `ENT-NNN`.

**15d. Atomic POST a field:**

```bash
ENT_ID="<ENT-NNN from 15c>"
curl -s -X POST http://127.0.0.1:8765/fields -H 'Content-Type: application/json' \
  -d "{\"field_name\":\"smoke_test_field\",\"field_description\":\"verify atomic POST creates row + edge\",\"field_type\":\"text\",\"field_required\":false,\"field_belongs_to_entity_identifier\":\"$ENT_ID\"}" \
  | python3 -m json.tool
```

Expected: 201, envelope with `data.field_identifier == "FLD-001"` (or next available), `data.field_belongs_to_entity_identifier` is NOT in the response (it's not a column on the field row), `data.field_status == "candidate"`, `data.field_required == false`.

**15e. Verify the edge landed.**

```bash
FLD_ID="<FLD-NNN from 15d>"
curl -s "http://127.0.0.1:8765/references?source_type=field&source_id=$FLD_ID" \
  | python3 -m json.tool
```

Expected: one row, `relationship: "field_belongs_to_entity"`, `target_id: $ENT_ID`.

**15f. Attempt to delete the edge while the field is live — expect 422.**

```bash
REF_ID="<REF-NNNN from 15e>"
curl -s -X DELETE -w '\nHTTP %{http_code}\n' "http://127.0.0.1:8765/references/$REF_ID"
```

Expected: HTTP 422 with `errors[0].code == "cardinality_violation"` (per the spec criterion #16 shape).

**15g. Attempt to create a second `field_belongs_to_entity` edge — expect 422.**

```bash
curl -s -X POST http://127.0.0.1:8765/references -H 'Content-Type: application/json' \
  -d "{\"source_type\":\"field\",\"source_id\":\"$FLD_ID\",\"target_type\":\"entity\",\"target_id\":\"$ENT_ID\",\"relationship\":\"field_belongs_to_entity\"}" \
  -w '\nHTTP %{http_code}\n'
```

Expected: HTTP 422 with the cardinality_violation error shape.

**15h. Soft-delete the field; verify both row and edge disappear from default queries.**

```bash
curl -s -X DELETE "http://127.0.0.1:8765/fields/$FLD_ID" | python3 -c "import sys, json; d = json.load(sys.stdin); print('field_deleted_at:', d['data']['field_deleted_at'])"
curl -s "http://127.0.0.1:8765/fields?entity_identifier=$ENT_ID" | python3 -c "import sys, json; print('live fields after delete:', len(json.load(sys.stdin)['data']))"
curl -s "http://127.0.0.1:8765/references?source_type=field&source_id=$FLD_ID" | python3 -c "import sys, json; print('live edges after delete:', len(json.load(sys.stdin)['data']))"
```

Expected: `field_deleted_at` non-null; live count 0; live edges 0.

**15i. Restore; verify both reappear.**

```bash
curl -s -X POST "http://127.0.0.1:8765/fields/$FLD_ID/restore" | python3 -c "import sys, json; d = json.load(sys.stdin); print('field_deleted_at after restore:', d['data']['field_deleted_at'])"
curl -s "http://127.0.0.1:8765/references?source_type=field&source_id=$FLD_ID" | python3 -c "import sys, json; print('live edges after restore:', len(json.load(sys.stdin)['data']))"
```

Expected: `field_deleted_at: None`; live edges 1.

If any of 15d–15i deviates from expected, halt and report — do not proceed to close-out.

### Step 16 — Author the close-out payload

Create `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` where `ses_NNN` is the session identifier captured in pre-flight Step 9. The payload follows the v0.8 nine-section format (per CLAUDE.md "v2 session lifecycle — closing a session"):

```json
{
  "label": "SES-NNN — PI-004 first slice: ship the `field` methodology entity end-to-end per field.md v1.0. Migration 0013 (fields table + refs source/target/kind CHECK extensions + change_log entity_type extension), models.Field, vocab additions (FIELD_STATUSES + FIELD_STATUS_TRANSITIONS + FIELD_TYPES + 'field' in ENTITY_TYPES + 'field_belongs_to_entity' in REFERENCE_RELATIONSHIPS + _kinds_for_pair clause for (field, entity)), repositories/field.py with atomic-POST + per-entity name scoping + status/type/transition validation + SAVEPOINT-retry identifier auto-assignment + cardinality-aware soft-delete/restore, references-repo cardinality guards (POST-second-edge + DELETE-only-edge-of-live-field both reject 422), schemas (Create requires field_belongs_to_entity_identifier; Replace/Patch do not accept it), router with 8 endpoints, UI client methods, sidebar entry at Methodology position #5, main_window dispatch + entity-type-map + refresh-filename-map registration, panel (flat ListDetailPanel; master-pane entity grouping deferred), dialogs (Create includes entity picker; Edit shows parent as read-only; Delete edge-text confirmation), 24 tests across access/API/UI. Addresses PI-004; does NOT resolve PI-004 (PI-004 resolves when the last sibling — persona/requirement/manual_config/test_spec — ships its build-closure session per DEC-232 / SES-074 pattern).",
  "session": {
    "identifier": "SES-NNN",
    "title": "PI-004 first slice — `field` methodology entity end-to-end build per field.md v1.0",
    "session_date": "<YYYY-MM-DD>",
    "status": "Complete",
    "conversation_reference": "Claude Code session at Doug's terminal, <date>. Executed CLAUDE-CODE-PROMPT-build-field.md end-to-end. Consumed work_ticket WT-NNN (the field-build kickoff body, if one was authored alongside this prompt; otherwise leave the consumed-work-ticket field empty and the conversation_opens_against_work_ticket edge absent).",
    "topics_covered": "Migration 0013 authoring + apply, models.Field, vocab additions, repositories/field.py with atomic POST + per-entity name scoping + transition validation + cardinality-aware soft-delete/restore, references-repo cardinality guards, schemas, router, main.py registration, UI client + sidebar + main_window dispatch + refresh map, panel (flat, deferring entity-grouping), dialogs, 24 tests, API smoke verification (atomic POST creates row+edge, deletion of the only live edge of a live field rejected with cardinality_violation, second edge attempt rejected with cardinality_violation, soft-delete/restore round-trip preserves both row and edge atomically).",
    "summary": "Lands the `field` methodology entity type per field.md v1.0. First slice of PI-004 (the four-entity workstream after v0.4). The schema deviates from the cross-spec default in two bounded ways: atomic POST (parent entity identifier required in POST body, row + edge + change-log emitted in one transaction) and per-entity-scoped name uniqueness (two fields named 'status' on two different entities are both valid). The references repository gains 1:1-mandatory cardinality enforcement on the field_belongs_to_entity kind (POST-second-edge rejected; DELETE-only-edge-of-live-field rejected). Master-pane primary grouping by parent entity per field.md §3.6.2 is deferred to a follow-on slice — v1 ships flat. 'Move to entity' reparenting affordance per field.md §3.6.5 / PI-053 deferred. PI-004 itself is NOT resolved here; addresses-edge only, per the DEC-232 / SES-074 build-closure convention.",
    "artifacts_produced": "Migration 0013_v0_5_create_fields_table.py; models.Field; vocab updates (FIELD_STATUSES, FIELD_STATUS_TRANSITIONS, FIELD_TYPES, 'field' in ENTITY_TYPES, 'field_belongs_to_entity' in REFERENCE_RELATIONSHIPS, (field, entity) clause in _kinds_for_pair); repositories/field.py; references.py cardinality guards on create/delete/delete_by_id; schemas FieldCreateIn/FieldReplaceIn/FieldPatchIn; routers/field.py; main.py include_router; UI client list_fields/get_field/create_field/update_field/patch_field/delete_field/restore_field/next_field_identifier; sidebar 'Fields' entry at position #5; main_window FieldsPanel dispatch + ENTITY_TYPE_TO_SIDEBAR_LABEL['field']; refresh.py 'fields.json' mapping; panels/field.py; dialogs/field_crud.py + dialogs/_field_schema.py; 24 tests across access/API/UI. Six decisions DEC-246..DEC-251 per field.md §3.9.1. Seven planning items PI-053..PI-059 per field.md §3.8.3. All cross-referenced via the references section.",
    "in_flight_at_end": "PI-004 remains Open with an addresses-edge from CONV-NNN; resolution waits for the last sibling (persona/requirement/manual_config/test_spec) to ship its build-closure session per DEC-232 / SES-074 pattern. PI-053 (re-parenting UX), PI-054 (richer type vocab), PI-055 (default_value + filters), PI-056 (richer required-ness), PI-057 (field-to-field dependencies), PI-058 (derived-field lineage realizing DEC-038), PI-059 (entity-soft-delete cascade posture) all Open. Master-pane entity-grouping deviation per field.md §3.6.2 is a v0.5 follow-on slice. Move-to-entity affordance per field.md §3.6.5 awaits PI-053 design decision."
  },
  "conversation": {
    "conversation_identifier": "CONV-NNN",
    "conversation_title": "PI-004 first slice — `field` methodology entity build per field.md v1.0",
    "conversation_purpose": "Execute the field-build kickoff end-to-end: migration, model, vocab, repository, references-repo cardinality guards, schemas, router, UI client, sidebar, main_window, panel, dialogs, tests, verification. First of four PI-004 sibling builds; addresses but does not resolve PI-004.",
    "conversation_description": "<one paragraph describing the actual conversation flow>",
    "conversation_status": "complete",
    "references": [
      {
        "source_type": "conversation",
        "source_id": "CONV-NNN",
        "target_type": "session",
        "target_id": "SES-NNN",
        "relationship": "conversation_records_session"
      }
      // If a work_ticket was authored for this build, add an
      // opens_against_work_ticket edge. Otherwise omit.
    ]
  },
  "commits": [
    {
      // Single commit shape; insert the actual SHA, message, etc.
      "commit_sha": "<sha from `git rev-parse HEAD` after the build commit>",
      "commit_message_first_line": "v2: PI-004 first slice — `field` methodology entity end-to-end per field.md v1.0",
      "commit_message_full": "<full message; see Commit section below>",
      "commit_author_name": "Doug Bower",
      "commit_author_email": "doug@dougbower.com",
      "commit_committed_at": "<ISO 8601 with offset>",
      "commit_repository": "crmbuilder",
      "commit_branch": "main",
      "commit_parent_shas": ["<parent sha>"],
      "commit_files_changed_count": <N>
    }
  ],
  "work_tickets": [],
  "planning_items": [
    {
      "identifier": "PI-053",
      "title": "Re-parenting UX flow for `field`",
      "description": "Per field.md §3.6.5 / §3.8.3 the Edit dialog's 'Move to entity' affordance is deferred — v1 ships with parent-entity displayed as a read-only label and no edit affordance. PI-053 decides between (a) sub-dialog opened from Edit, (b) bare reference picker, and (c) POST /fields/{id}/reparent convenience endpoint. Includes the access-layer atomic-edge-swap logic.",
      "item_type": "pending_work",
      "status": "Open"
    },
    {
      "identifier": "PI-054",
      "title": "Richer `field_type` vocabulary for v0.6+",
      "description": "Per field.md §3.8.3. Covers `formula`, `link`, `address`, `phone`, `url` and the question of whether `derived` should split into a distinct entity type per DEC-038 once lineage tracing lands. Gated on CBM-redo signal.",
      "item_type": "pending_work",
      "status": "Open"
    },
    {
      "identifier": "PI-055",
      "title": "`field_default_value` and additional list filters",
      "description": "Per field.md §3.8.3. Captures the default-value-at-methodology-level question and the server-side list-filters general expansion (`?field_status=`, `?field_type=`) in one combined item. Surfaced by the same real-use signal pattern.",
      "item_type": "pending_work",
      "status": "Open"
    },
    {
      "identifier": "PI-056",
      "title": "Richer required-ness rules for `field`",
      "description": "Per field.md §3.8.3. Covers conditional required-ness mirroring the deploy-side `requiredWhen:` mechanism. Gated on CBM-redo signal and on PI-057 prerequisite analysis.",
      "item_type": "pending_work",
      "status": "Open"
    },
    {
      "identifier": "PI-057",
      "title": "Field-to-field dependencies (`field_depends_on_field`)",
      "description": "Per field.md §3.8.3. Tracks the methodology-level dependency-capture references-edge mechanism. Likely lands as part of the same v0.6 release as PI-056.",
      "item_type": "pending_work",
      "status": "Open"
    },
    {
      "identifier": "PI-058",
      "title": "Derived-field lineage tracing per DEC-038",
      "description": "Per field.md §3.8.3. Realizes DEC-038's posture in concrete schema-and-references shape. Covers `derived_field_derived_from_field` and `derived_field_traverses_relationship` edge kinds (working names) and the access-layer lineage-graph traversal logic.",
      "item_type": "pending_work",
      "status": "Open"
    },
    {
      "identifier": "PI-059",
      "title": "Entity-soft-delete cascade posture for inbound `field` rows",
      "description": "Per field.md §3.8.3. Decides whether soft-deleting an entity should cascade-soft-delete its inbound `field_belongs_to_entity` edges' source fields (strict-consistency) or leave them in place (restore-friendly; v0.5 default). Posture decision affects every methodology entity-to-child relationship subsequently introduced.",
      "item_type": "pending_work",
      "status": "Open"
    }
  ],
  "decisions": [
    {
      "identifier": "DEC-246",
      "title": "`field` identifier prefix and format",
      "context": "Per field.md §3.1 and §3.9.1. The `field` methodology entity type needs a prefix under the soft-3-letter posture established by DEC-044 (`domain.md` §3.1).",
      "decision": "Adopt `FLD` as the `field` identifier prefix; format `FLD-NNN`, zero-padded to 3 digits.",
      "rationale": "Three letters, reads unambiguously as 'field', no collision against the existing prefix space (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRM, WS, CONV, RB, WT, COP, DEP, CM).",
      "alternatives_considered": "FIELD (four letters; longer than convention). F (one letter; collides with potential future formula entity type).",
      "consequences": "Standard endpoint set with GET /fields/next-identifier helper per DEC-043. PI-002 server-assignment applies.",
      "decision_date": "<YYYY-MM-DD>",
      "status": "Active"
    },
    {
      "identifier": "DEC-247",
      "title": "`field` field inventory and validation under minimum-viable v0.5 scope",
      "context": "Per field.md §3.2 and §3.9.1. Define the substantive fields and validation rules for v0.5.",
      "decision": "Seven substantive fields plus inherited timestamps: field_identifier, field_name, field_description, field_type, field_required, field_notes, field_status. One description field (no field_label). Optional field_notes. No field_default_value. Methodology-level required-ness as a Boolean. No storage-level length caps. Per-parent-entity case-insensitive field_name uniqueness.",
      "rationale": "Thinnest shape that faithfully hosts Phase 3 iteration build surfacing without preempting downstream YAML deploy decisions. Per-entity scoping makes common attribute names (email_address, phone_number) reusable across entity types via twin records.",
      "alternatives_considered": "Engagement-global uniqueness (rejected; would force renames for natural repeats). field_default_value at methodology level (deferred per PI-055). Conditional required-ness (deferred per PI-056). field_label (deploy-side concern).",
      "consequences": "Twin-record pattern for cross-entity attribute reuse in v0.5. Pathological-input handling and label/default capture all wait on CBM-redo signal.",
      "decision_date": "<YYYY-MM-DD>",
      "status": "Active"
    },
    {
      "identifier": "DEC-248",
      "title": "`field` status lifecycle",
      "context": "Per field.md §3.4 and §3.9.1. Define the lifecycle vocabulary and transitions.",
      "decision": "Adopt the `domain` / `entity` three-status propose-verify pattern unchanged: candidate / confirmed / deferred, one-way gate out of candidate, free movement between confirmed and deferred, rejection-via-soft-delete, no archived. Document field-status-independent-of-parent-entity-status posture.",
      "rationale": "Fields, like domains and entities, are surfaced by the consultant and verified by the client. Independence from parent-entity status matters because field-level negotiation happens both before and after entity-level scope confirmation.",
      "alternatives_considered": "Cascade from parent-entity status (rejected; field-level negotiation is independent). Distinct lifecycle (rejected; inheriting the workstream pattern wins for consistency).",
      "consequences": "Status-transition validation in the access layer mirrors entity / domain exactly. Status edit affordance in UI never consults parent-entity status.",
      "decision_date": "<YYYY-MM-DD>",
      "status": "Active"
    },
    {
      "identifier": "DEC-249",
      "title": "`field`-to-`entity` affiliation mechanism and `field_belongs_to_entity` vocabulary registration",
      "context": "Per field.md §3.3.1 and §3.9.1. The mandatory 1:1 affiliation between field and entity needs a mechanism.",
      "decision": "Many-to-one (1:1 mandatory at source side) via the references entity, NOT a direct FK column. Register `field_belongs_to_entity` in REFERENCE_RELATIONSHIPS and as the only kind in _kinds_for_pair((field, entity)). Extend refs.relationship_kind CHECK in Alembic migration.",
      "rationale": "References-first discipline (consistent with every methodology cross-edge so far). Uniform edge-query semantics. Future-edge friction avoidance (process_touches_field under PI-005; field_depends_on_field under PI-057; derived-field lineage under PI-058 all reuse the references store). Soft-delete consistency. Cardinality enforcement as access-layer logic localizes complexity.",
      "alternatives_considered": "Direct FK column `field_entity_identifier` (rejected; local wins on cardinality + uniqueness declarability, workstream-wide cost on discipline / query uniformity / future-edge friction).",
      "consequences": "Per-entity name uniqueness check must query refs first to resolve the parent entity. Cardinality (1:1 mandatory at source) enforced in access layer on three surfaces: POST /fields atomicity, POST /references rejects second edge, DELETE /references rejects only-edge of live field.",
      "decision_date": "<YYYY-MM-DD>",
      "status": "Active"
    },
    {
      "identifier": "DEC-250",
      "title": "`field_type` vocabulary for v0.5 and POST atomicity for the mandatory parent-entity edge",
      "context": "Per field.md §3.2.3, §3.5.4, and §3.9.1.",
      "decision": "11-value enum: text / long_text / enum / multi_enum / date / datetime / money / boolean / number / reference / derived. POST /fields requires field_belongs_to_entity_identifier body key; access layer creates field row + edge + change-log emit in one transaction.",
      "rationale": "Vocabulary narrower than deploy-side YAML schema's type list — methodology cares about value-shape, not platform rendering. Richer types deferred per PI-054. POST atomicity avoids the transient-invalid-state window that decomposed POST creates for the 1:1 mandatory relationship.",
      "alternatives_considered": "Mirror the deploy-side YAML type list (rejected; over-specifies for methodology layer). Decomposed POST (POST row first, POST edge separately; rejected per the transient-invalid-state argument in field.md §3.5.4).",
      "consequences": "FieldCreateIn schema requires field_belongs_to_entity_identifier; FieldReplaceIn/FieldPatchIn do NOT accept it. Re-parenting requires explicit DELETE-then-POST edge management (PI-053 tracks the convenience endpoint).",
      "decision_date": "<YYYY-MM-DD>",
      "status": "Active"
    },
    {
      "identifier": "DEC-251",
      "title": "`field` API surface, UI defaults, master-pane grouping deviation, acceptance criteria for v0.5",
      "context": "Per field.md §3.5, §3.6, §3.7, and §3.9.1.",
      "decision": "Standard endpoint set with the POST atomicity deviation (DEC-250) and the ?entity_identifier=ENT-NNN list filter. Decomposed reference handling beyond the parent-entity edge. Default ListDetailPanel UI under Methodology sidebar at position #5. Master-pane primary grouping by parent entity per §3.6.2 — DEFERRED to a follow-on slice; v1 ships flat. Parent entity rendered at detail-pane position #3 outside the generic ReferencesSection. 17 testable acceptance criteria.",
      "rationale": "Eight endpoints match the cross-spec default with the bounded atomic-POST deviation already decided in DEC-250. Master-pane entity grouping is the right scan affordance at CBM-redo scale but adds enough UI complexity to warrant a separate slice. Detail-pane rendering of parent entity outside ReferencesSection reflects that the mandatory 1:1 affiliation is conceptually part of the field's identity, not a peer relationship.",
      "alternatives_considered": "Ship entity-grouping in the first slice (rejected on complexity/time grounds). Render parent entity inside ReferencesSection (rejected on identity-vs-peer distinction).",
      "consequences": "Follow-on slice tracks master-pane entity grouping. PI-053 tracks the 'Move to entity' affordance. PI-055 tracks future server-side filter expansion.",
      "decision_date": "<YYYY-MM-DD>",
      "status": "Active"
    }
  ],
  "references": [
    // The six DEC records each get a decided_in edge to SES-NNN.
    // Each DEC gets a references edge from this slice's content
    // (commit, migration filename) where appropriate per the field.md
    // §3.9 cross-reference list. Generate the standard pattern.
  ],
  "resolves_planning_items": [],
  "addresses_planning_items": [
    {
      "planning_item_identifier": "PI-004"
    }
  ]
}
```

**Identifier-collision contingency.** If pre-flight Step 9 showed DEC / PI / SES heads that have advanced past the planned values, re-key the entire payload per the SES-077 re-keying pattern (CLAUDE.md "v2 session lifecycle — planning item resolution"). The spec's planned identifiers were DEC-246..251, PI-053..059; if any of those are now claimed, shift the entire range forward and note the re-key in the Done section's report.

### Step 17 — Author the apply prompt

Create `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md` per the canonical post-fix example `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md` (commit `ab167c4`). The prompt documents:

- Pre-flight (Alembic head check, API health check, no-uncommitted-changes).
- Pre-flight identifier-capture pipes that explicitly unwrap `.data` per the CLAUDE.md v2 envelope rule.
- The single `apply_close_out.py` invocation:

  ```bash
  cd crmbuilder-v2
  uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json
  cd ..
  ```

- Post-apply verification: identifier-fingerprint deltas (DEC count, PI count, REF count, fields count), the regenerated `db-export/*.json` snapshots are present, the new `deposit-event-logs/dep_NNN.log` is present.
- The single commit (Step 18 below).

### Step 18 — Single commit

After the apply lands successfully (regenerated snapshots in `PRDs/product/crmbuilder-v2/db-export/`, new `deposit-event-logs/dep_NNN.log`), stage and commit everything together:

```bash
git add \
  crmbuilder-v2/migrations/versions/0013_v0_5_create_fields_table.py \
  crmbuilder-v2/src/crmbuilder_v2/access/models.py \
  crmbuilder-v2/src/crmbuilder_v2/access/vocab.py \
  crmbuilder-v2/src/crmbuilder_v2/access/repositories/field.py \
  crmbuilder-v2/src/crmbuilder_v2/access/repositories/references.py \
  crmbuilder-v2/src/crmbuilder_v2/api/schemas.py \
  crmbuilder-v2/src/crmbuilder_v2/api/main.py \
  crmbuilder-v2/src/crmbuilder_v2/api/routers/field.py \
  crmbuilder-v2/src/crmbuilder_v2/ui/client.py \
  crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py \
  crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py \
  crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py \
  crmbuilder-v2/src/crmbuilder_v2/ui/panels/field.py \
  crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/field_crud.py \
  crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_field_schema.py \
  tests/crmbuilder_v2/access/test_field.py \
  tests/crmbuilder_v2/api/test_field_api.py \
  tests/crmbuilder_v2/ui/test_field_panel.py \
  PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json \
  PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md \
  PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log \
  PRDs/product/crmbuilder-v2/db-export/

git commit -m "$(cat <<'EOF'
v2: PI-004 first slice — `field` methodology entity end-to-end per field.md v1.0

Lands the `field` methodology entity type. First of four PI-004 sibling
builds (others: persona, requirement, manual_config, test_spec).

Migration 0013:
- fields table with 9 columns per field.md §3.2 + 4 CHECK constraints +
  3 indexes.
- refs.source_type / refs.target_type CHECK extended to admit 'field'.
- refs.relationship_kind CHECK extended to admit 'field_belongs_to_entity'.
- change_log.entity_type CHECK extended to admit 'field'.

vocab.py:
- FIELD_STATUSES + FIELD_STATUS_TRANSITIONS (mirrors entity per DEC-248).
- FIELD_TYPES (11 values per DEC-250).
- 'field' in ENTITY_TYPES; 'field_belongs_to_entity' in REFERENCE_RELATIONSHIPS.
- _kinds_for_pair((field, entity)) returns {field_belongs_to_entity}
  per DEC-249.

repositories/field.py:
- Atomic POST: field row + field_belongs_to_entity edge + change-log
  emit in one transaction per field.md §3.5.4.
- Per-entity-scoped name uniqueness via refs lookup per field.md §3.2.3.
- SAVEPOINT-retry identifier auto-assignment per PI-002.
- Status transition validation per FIELD_STATUS_TRANSITIONS.
- field_type enum validation per FIELD_TYPES.
- Soft-delete and restore round-trip row + edge atomically per
  field.md §3.4.6.

repositories/references.py:
- Cardinality guard on create: second field_belongs_to_entity edge for
  a live field rejected with 422 cardinality_violation.
- Cardinality guard on delete/delete_by_id: deletion of the only live
  field_belongs_to_entity edge of a live field rejected with 422
  cardinality_violation. Bypass flag (_skip_cardinality_check=True)
  used by repositories/field.delete_field for atomic row+edge soft-delete.

API:
- FieldCreateIn requires field_belongs_to_entity_identifier; Replace/Patch
  do NOT accept it (per field.md §3.5.4 — reparenting requires explicit
  edge management; PI-053 tracks convenience endpoint).
- 8 endpoints: GET list (with ?entity_identifier= filter per §3.5.5),
  GET next-identifier, GET by id, POST, PUT, PATCH, DELETE, POST /restore.

UI:
- Fields entry in Methodology sidebar at position #5 (after CRM Candidates).
- FieldsPanel as plain ListDetailPanel (master-pane entity grouping per
  field.md §3.6.2 deferred to follow-on slice).
- FieldCreateDialog includes parent-entity picker; FieldEditDialog shows
  parent as read-only label ('Move to entity' per §3.6.5 / PI-053 deferred).
- FieldDeleteDialog edge-text confirmation per §3.6.6.

Tests: 24 across access / API / UI smoke layers including atomic-POST
correctness, both cardinality-violation surfaces, per-entity name
scoping, status transitions, type validation, soft-delete/restore
atomicity.

Six decisions DEC-246..DEC-251 per field.md §3.9.1; seven planning items
PI-053..PI-059 per field.md §3.8.3 — all in this commit's close-out
payload. Addresses PI-004 (does NOT resolve; the last sibling's
build-closure session resolves per DEC-232 / SES-074 pattern).
EOF
)"

git status
```

**Do NOT push.** Per CLAUDE.md "Push convention" — Claude Code commits land in Doug's local clone; Doug reviews and pushes.

---

## Done

Report (one section per item):

- Pre-flight Alembic head: `0012_v0_8_commits_and_blocked_by_rename`
- Post-migration Alembic head: `0013_v0_5_create_fields_table`
- `fields` table present in engagement DB: True / False
- Atomic POST smoke (Step 15d–e): field FLD-NNN + edge REF-NNNN both created in one POST
- Cardinality-DELETE smoke (Step 15f): HTTP 422 with `cardinality_violation` for only-edge-of-live-field
- Cardinality-POST smoke (Step 15g): HTTP 422 with `cardinality_violation` for second-edge attempt
- Soft-delete / restore round-trip smoke (Step 15h–i): both row and edge disappear and reappear together
- Test suite: pre-slice pass count vs post-slice pass count (≥ +24 new tests expected)
- Identifier re-keying (if any): list the planned-→-actual deltas for DEC / PI / SES
- Decisions authored: DEC-246..DEC-251 (or re-keyed range)
- Planning items authored: PI-053..PI-059 (or re-keyed range), all Open
- PI-004 status: Open (addresses-only edge from CONV-NNN; resolution waits for the last sibling per DEC-232 / SES-074 pattern)
- Close-out payload path: `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`
- Apply prompt path: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`
- Build commit SHA: `<sha>` (unpushed; awaits Doug review)
- Deposit event log: `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`
- Next prompt to run: a sibling PI-004 entity build (`persona` / `requirement` / `manual_config` / `test_spec`). The LAST of those four sibling builds is the one that resolves PI-004 in its close-out payload's `resolves_planning_items` section per the DEC-232 / SES-074 build-closure convention.
