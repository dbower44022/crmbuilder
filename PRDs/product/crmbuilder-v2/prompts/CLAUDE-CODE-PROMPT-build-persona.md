# CLAUDE-CODE-PROMPT-build-persona

**Last Updated:** 05-25-26
**Operating mode:** DETAIL
**Resolves:** PI-003 — `persona` methodology entity type
**Spec authority:** `PRDs/product/crmbuilder-v2/methodology-schema-specs/persona.md` v1.0
**Status:** Ready to execute. Blocked by: nothing — persona.md spec is canonical and complete.
**Companion build patterns (mirror these line-by-line):**
- Migration: `crmbuilder-v2/migrations/versions/0008_v0_4_create_entities_table.py`
- Model: `class Entity` in `crmbuilder-v2/src/crmbuilder_v2/access/models.py`
- Vocab triad: `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` (`ENTITY_STATUSES`, `ENTITY_STATUS_TRANSITIONS`, `ENTITY_TYPES`, `REFERENCE_RELATIONSHIPS`, `_kinds_for_pair`)
- Repository: `crmbuilder-v2/src/crmbuilder_v2/access/repositories/entity.py`
- Pydantic schemas: `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` (`EntityCreateIn`, `EntityReplaceIn`, `EntityPatchIn`)
- Router: `crmbuilder-v2/src/crmbuilder_v2/api/routers/entities.py`
- Router registration: `crmbuilder-v2/src/crmbuilder_v2/api/main.py` (`app.include_router(entities.router)`)
- UI client: `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` (`list_entities` … `next_entity_identifier`)
- Sidebar: `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py` (`SIDEBAR_GROUPS` "Methodology" tuple)
- Main window dispatch: `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` (entry → panel branch)
- Panel: `crmbuilder-v2/src/crmbuilder_v2/ui/panels/entities.py`
- Dialogs: `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/entity_crud.py` + `_entity_schema.py`
- Tests: `tests/crmbuilder_v2/access/test_entity.py`, `tests/crmbuilder_v2/api/test_entities_api.py`, `tests/crmbuilder_v2/ui/test_entities_panel.py`

---

## Purpose

Build the `persona` methodology entity type end-to-end per `persona.md` v1.0 — schema, access layer, REST API, UI panel, dialogs, and tests — and resolve PI-003 in the same close-out. After this session lands, a consultant can author Phase 2 / Phase 3 persona records through the desktop UI, attach `persona_scopes_to_domain` and `persona_realized_as_entity` references via the existing references infrastructure, and the records flow through to the v2 storage layer with full validation, soft-delete round-trip, and change-log audit.

The spec is the source of truth for *what* to build (fields, validation rules, lifecycle, endpoints, UI layout, acceptance criteria). This prompt is the source of truth for *how* to execute the build: which existing files to mirror, what the next-available identifiers are, the verification sequence, and the close-out shape. **Do not duplicate spec content in code comments — cite the spec section** (e.g. `# per persona.md §3.4.1`).

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes other than db-export snapshots from a just-applied close-out.

3. **Confirm git identity:**

   ```bash
   git config user.name
   git config user.email
   # Expect: Doug Bower / doug@dougbower.com
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts.

5. **Verify API health and start if absent:**

   ```bash
   curl -sf http://127.0.0.1:8765/health || (cd crmbuilder-v2 && uv run crmbuilder-v2-api &)
   sleep 2 && curl -sf http://127.0.0.1:8765/health
   ```

6. **Read these documents end-to-end before authoring any code.** All paths are repo-relative.

   - `CLAUDE.md` (root) — universal session-startup. Pay particular attention to the v2 CRMBuilder section, the `{data, meta, errors}` envelope rule, the PI-002 identifier-optional-on-POST rule, the v0.7 governance/v0.8 commit context, the "Reference relationship vocabulary lives in vocab.py" paragraph naming the `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair` / Alembic-migration triad, and the v2 session lifecycle close-out conventions.
   - `PRDs/product/crmbuilder-v2/methodology-schema-specs/persona.md` v1.0 — authoritative spec. Read all of §1 (purpose), §2 (summary), §3.1 (identity / prefix `PER`), §3.2 (fields), §3.3 (relationships — both `persona_scopes_to_domain` and `persona_realized_as_entity`), §3.4 (lifecycle and three-status propose-verify gate), §3.5 (API surface), §3.6 (UI), §3.7 (14 acceptance criteria), §3.8 (deferred decisions, including the create-dialog flow open question for v0.5+ build to settle), §3.9 (cross-references).

7. **Read the companion build-pattern files in full.** All eight files together form the template for this build; each one corresponds to one or more of the implementation steps below. Do not modify any of them in this build — they are read-only references.

   - `crmbuilder-v2/migrations/versions/0008_v0_4_create_entities_table.py` — migration shape (table create, CHECK constraints, indexes, reversible `downgrade`).
   - `crmbuilder-v2/src/crmbuilder_v2/access/models.py` — `class Entity` and its `__table_args__`, plus `class Domain` for direct comparison.
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/entity.py` — the eight module-level functions, the SAVEPOINT-retry helper, the validation helpers, the `emit()` change-log calls.
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — the existing `ENTITY_STATUSES` / `ENTITY_STATUS_TRANSITIONS` pair (this build adds a mirror), the `ENTITY_TYPES` set (this build adds `"persona"`), the `REFERENCE_RELATIONSHIPS` set (this build adds two new kinds), and the `_kinds_for_pair` function (this build adds two new clauses).
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/entities.py` — the eight endpoint patterns (`list_all`, `next_identifier`, `get`, `create`, `replace`, `patch`, `delete`, `restore`) and the `ok()` envelope discipline.
   - `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` — the `EntityCreateIn` / `EntityReplaceIn` / `EntityPatchIn` shapes (this build adds three persona-prefixed mirrors).
   - `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` lines ~657–795 — the eight `*_entity` methods.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/entities.py` — `EntitiesPanel` (master columns, detail pane, `ReferencesSection` wiring, context menu, click handlers).
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/entity_crud.py` + `_entity_schema.py` — the three CRUD dialogs and the `FieldSchema` declarative list with the `compute_options` callback for status-successor narrowing.

8. **Baseline the test suite.**

   ```bash
   cd crmbuilder-v2
   uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -5
   cd ..
   ```

   Note the pass count and skip count for comparison after the build lands (baseline ~1542 passed at draft time; verify the actual baseline). Stop and report if any baseline test is currently failing — surface that and ask whether to proceed.

9. **Verify sparse-checkout includes the v2 source and migrations:**

   ```bash
   git sparse-checkout list 2>/dev/null
   ```

   If sparse-checkout is active and doesn't include `crmbuilder-v2/` and `PRDs/`, stop and report.

10. **Capture pre-flight identifier heads from the running API** (will be needed for the close-out's identifier choices and for the apply prompt's pre-flight). Note: every list endpoint returns `{"data": [...], "meta": ..., "errors": null}` per the v2 envelope — unwrap `.data` first.

    ```bash
    echo "Sessions head:"
    curl -s 'http://127.0.0.1:8765/sessions?limit=2000' \
      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
    echo "Decisions head:"
    curl -s 'http://127.0.0.1:8765/decisions?limit=2000' \
      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
    echo "Conversations head:"
    curl -s 'http://127.0.0.1:8765/conversations?limit=2000' \
      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['conversation_identifier'] for r in d)[-1] if d else 'none')"
    echo "Planning items head:"
    curl -s 'http://127.0.0.1:8765/planning-items?limit=2000' \
      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
    echo "Workstreams head:"
    curl -s http://127.0.0.1:8765/workstreams \
      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['workstream_identifier'] for r in d)[-1] if d else 'none')"
    echo "Alembic head:"
    cd crmbuilder-v2 && uv run alembic current 2>&1 | tail -2 && cd ..
    ```

    Record these values; the close-out payload picks the next available identifiers for the SES, DEC, CONV, and PI it introduces. The Alembic head dictates this build's migration revision (next integer after the existing head — verify by listing the migrations directory; do not hard-code).

11. **Verify PI-003 is still Open** (this build resolves it):

    ```bash
    curl -s http://127.0.0.1:8765/planning-items/PI-003 \
      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-003 status:', d['status'])"
    ```

    Expect: `Open`. If already `Resolved`, a parallel session has shipped this work — stop and investigate.

12. **Confirm `persona` is not already in any v0.4+ surface.** Quick negative-presence check so a partially-landed parallel session doesn't get clobbered:

    ```bash
    grep -n '"persona"\|class Persona\b\|persona_identifier' crmbuilder-v2/src/crmbuilder_v2/access/models.py crmbuilder-v2/src/crmbuilder_v2/access/vocab.py crmbuilder-v2/src/crmbuilder_v2/api/schemas.py 2>/dev/null
    ```

    Expect: no matches. If matches, stop and inspect.

---

## Implementation

The work decomposes into 14 numbered steps. Execute them in order — later steps depend on earlier ones (the migration creates the table, the repository imports the model, the router imports the schema, the panel imports the dialogs, the tests exercise everything). All paths are repo-relative.

### Step 1 — Alembic migration

**Path:** `crmbuilder-v2/migrations/versions/00XX_v0_8_create_personas_table.py`

The next available revision number: inspect `crmbuilder-v2/migrations/versions/` and use the next integer after the current head (at draft time `0012` exists, so this is `0013` — verify rather than assuming). The migration's `down_revision` must point to the prior head; confirm with `cd crmbuilder-v2 && uv run alembic heads`.

The migration performs five operations in `upgrade()`, all in one revision. Mirror `0008_v0_4_create_entities_table.py`'s structure for the table create; mirror `0011_v0_7_governance_entities.py`'s `batch_alter_table` pattern for the refs/change_log CHECK extensions. All operations are reversible in `downgrade()`.

**1a. Create the `personas` table** per persona.md §3.2 (nine columns total — see §3.2.1, §3.2.2, §3.2.3, §3.2.5). Columns: `persona_identifier`, `persona_name`, `persona_role_summary`, `persona_responsibilities` (nullable), `persona_notes` (nullable), `persona_status`, `persona_created_at`, `persona_updated_at`, `persona_deleted_at` (nullable). Primary key is `persona_identifier` (string, no surrogate `id`). CHECK constraints: identifier format `persona_identifier GLOB 'PER-[0-9][0-9][0-9]'` and status enum `persona_status IN ('candidate', 'confirmed', 'deferred')`. Indexes on `persona_status` and `persona_deleted_at` (mirroring `0008`'s `ix_entities_entity_status` and `ix_entities_entity_deleted_at`).

**1b. Extend `refs.source_type` CHECK** to admit `'persona'`. Pattern from `0011_v0_7_governance_entities.py` — `batch_alter_table` with a constraint-replacement using the existing constraint name. Sorted alphabetical order in the CHECK expression.

**1c. Extend `refs.target_type` CHECK** to admit `'persona'`. Same pattern, same `batch_alter_table` block as 1b (one recopy).

**1d. Extend `refs.relationship_kind` CHECK** to admit `'persona_scopes_to_domain'` and `'persona_realized_as_entity'`. Same pattern, same `batch_alter_table` block. **Do not remove any existing kinds.**

**1e. Extend `change_log.entity_type` CHECK** to admit `'persona'`. Separate `batch_alter_table` on the `change_log` table.

**`downgrade()` reverses in opposite order:** drop the `personas` table; restore the original `change_log.entity_type` CHECK; restore the original `refs.relationship_kind` CHECK (removes the two persona kinds); restore the original `refs.source_type` and `refs.target_type` CHECKs (removes `'persona'`).

Inspect `0011_v0_7_governance_entities.py` for the precise CHECK-constraint-name conventions in use (e.g. `ck_refs_source_type`, `ck_refs_target_type`, `ck_refs_relationship_kind`, `ck_change_log_entity_type` — but verify; don't assume). Keep the new-CHECK constant strings at module scope so future diffs are inspectable, matching `0011`'s convention.

### Step 2 — SQLAlchemy model

**Path:** `crmbuilder-v2/src/crmbuilder_v2/access/models.py`

Add `class Persona(Base)` mirroring `class Entity(Base)` (lines ~304–352) with persona-prefixed fields. Module-level imports already include everything needed (`Mapped`, `mapped_column`, `String`, `Text`, `DateTime`, `CheckConstraint`, `Index`, `_utcnow`, `_check_in`). Add a sibling import for `PERSONA_STATUSES` from `access.vocab` once Step 4 lands; the order is fine because Python's class-body resolution is at definition time, not import time, and Step 4 lands before any code that imports models.

Class body:
- `__tablename__ = "personas"`.
- Nine columns matching the migration's column list, types, and nullability.
- `__table_args__`: identifier GLOB CHECK, status enum CHECK (using `_check_in("persona_status", PERSONA_STATUSES)`), two indexes.
- Docstring cites `persona.md` §3.2 and notes: "no FK column — `persona_scopes_to_domain` and `persona_realized_as_entity` live in the `refs` table".

### Step 3 — Pydantic schemas

**Path:** `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py`

Add three classes after `EntityPatchIn` (lines ~217–228), under a `# ---------- Personas (methodology entity, v0.5+) ----------` header comment:

- `PersonaCreateIn(_Base)`: `persona_name: str`, `persona_role_summary: str`, `persona_responsibilities: str | None = None`, `persona_notes: str | None = None`, `persona_status: str | None = None`, `persona_identifier: str | None = None`. Docstring cites `persona.md` §3.5 and notes the decomposed-references discipline (§3.5.4).
- `PersonaReplaceIn(_Base)`: same fields, `persona_status` required, `persona_identifier: str | None = None` (path-mismatch policed at access layer).
- `PersonaPatchIn(_Base)`: every field `str | None = None`. Docstring notes `model_dump(exclude_unset=True)` discipline so explicit `null` clears a field whereas omission leaves it unchanged.

### Step 4 — Vocab updates

**Path:** `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`

Four surgical edits:

**4a. Add the persona status lifecycle.** After `ENTITY_STATUS_TRANSITIONS` (line ~58), before `CRM_CANDIDATE_STATUSES` (line ~67), add:

```python
# Methodology entity `persona` lifecycle (v0.5+, persona.md §3.4).
# Mirrors `domain` / `entity` exactly — three-status propose-verify
# lifecycle with one-way gate out of `candidate`.
PERSONA_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred"}
)

PERSONA_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred"}),
    "deferred": frozenset({"confirmed"}),
}
```

**4b. Add `'persona'` to `ENTITY_TYPES`.** In the set literal (lines ~250–289), append after `"commit"`:

```python
        # v0.5+ methodology entity (PI-003). See persona.md.
        "persona",
```

**4c. Add the two new kinds to `REFERENCE_RELATIONSHIPS`.** In the set literal (lines ~211–246), append after `"blocked_by"`:

```python
        # v0.5+ persona additions (PI-003, persona.md §3.3.1):
        #   - `persona_scopes_to_domain` (persona → domain; many-to-many).
        #   - `persona_realized_as_entity` (persona → entity; conceptually
        #     optional and most often single-target, but the references
        #     mechanism permits multi-target).
        "persona_scopes_to_domain",
        "persona_realized_as_entity",
```

**4d. Add two clauses to `_kinds_for_pair`.** After the v0.8 Code Change Lifecycle clauses (lines ~367–374), append:

```python
    # v0.5+ persona additions (PI-003, persona.md §3.3.1):
    if source_type == "persona" and target_type == "domain":
        kinds.add("persona_scopes_to_domain")
    if source_type == "persona" and target_type == "entity":
        kinds.add("persona_realized_as_entity")
```

Also update the function's docstring (lines ~292–320) to add two bullet points for the new kinds, matching the existing per-kind one-liner format.

### Step 5 — Repository

**Path:** `crmbuilder-v2/src/crmbuilder_v2/access/repositories/persona.py`

New file mirroring `repositories/entity.py` line-by-line with persona-prefixed substitutions. Module-level constants: `_ENTITY_TYPE = "persona"`, `_IDENTIFIER_PREFIX = "PER"`, `_IDENTIFIER_RE = re.compile(r"^PER-\d{3}$")`, `_MAX_AUTOASSIGN_ATTEMPTS = 50`, `_PATCHABLE_FIELDS = frozenset({"name", "role_summary", "responsibilities", "notes", "status"})`.

Import `PERSONA_STATUS_TRANSITIONS` and `PERSONA_STATUSES` from `crmbuilder_v2.access.vocab`; import `Persona` from `crmbuilder_v2.access.models`.

The eight module-level functions match `entity.py`'s shapes:

- `list_personas(session, *, include_deleted=False) -> list[dict]`
- `get_persona(session, identifier, *, include_deleted=False) -> dict | None`
- `next_persona_identifier(session) -> str` — delegates to `next_prefixed_identifier`
- `create_persona(session, *, name, role_summary, responsibilities=None, notes=None, status="candidate", identifier=None) -> dict` — uses `_insert_with_autoassign` when `identifier is None`, otherwise validates explicit-identifier format and rejects collision; calls `emit("insert", ...)`
- `update_persona(session, identifier, *, persona_identifier=None, name=None, role_summary=None, responsibilities=None, notes=None, status=None) -> dict` — full replace; path-mismatch returns 422; required `name` / `role_summary`; status-transition validated; calls `emit("update", ...)`
- `patch_persona(session, identifier, **fields) -> dict` — partial; unknown fields → 422; status-transition validated; calls `emit("update", ...)`
- `delete_persona(session, identifier) -> dict` — soft-delete; idempotent on already-deleted; **never touches refs table** (per persona.md §3.4.6); calls `emit("update", ...)`
- `restore_persona(session, identifier) -> dict` — clears `persona_deleted_at`; 422 if not soft-deleted; calls `emit("update", ...)`

Helper functions mirror `entity.py` directly: `_require_identifier_format`, `_require_nonempty`, `_require_status` (uses `PERSONA_STATUSES`), `_check_transition` (uses `PERSONA_STATUS_TRANSITIONS`), `_reject_duplicate_name` (case-insensitive on `persona_name`, exclude-soft-deleted), `_get_row`, `_increment_identifier`, `_new_persona_row`, `_insert_with_autoassign`.

Add `persona` to the package's exposed name. Inspect `crmbuilder-v2/src/crmbuilder_v2/access/repositories/__init__.py` for the import pattern (the file may be empty or may re-export). If empty, the convention is to import `from crmbuilder_v2.access.repositories import persona` directly at call sites — which is what `routers/entities.py` does for `entity`.

Module docstring cites `persona.md` §3.5 (validation posture), §3.4.3 (status independence from affiliated-domains' and realization-entity's statuses — never consults related records), and §3.4.6 (soft-delete leaves outbound references intact).

### Step 6 — Router

**Path:** `crmbuilder-v2/src/crmbuilder_v2/api/routers/persona.py`

New file mirroring `routers/entities.py` (118 lines). Singular filename to match the repository file name (`persona.py`) and the existing `routers/` directory's mixed-convention precedent (e.g., `commits.py` is plural, `crm_candidates.py` is plural, but `references.py` is plural while the table is singular; verify by inspecting the directory and follow whichever convention reads better — recommend singular `persona.py` to match the repository file).

Module-level imports: `from fastapi import APIRouter`, `from crmbuilder_v2.access.exceptions import NotFoundError`, `from crmbuilder_v2.access.repositories import persona`, `from crmbuilder_v2.api.deps import readonly_session, writable_session`, `from crmbuilder_v2.api.envelope import ok`, `from crmbuilder_v2.api.schemas import PersonaCreateIn, PersonaPatchIn, PersonaReplaceIn`.

`router = APIRouter(prefix="/personas", tags=["personas"])`
`_FIELD_PREFIX = "persona_"`

Eight endpoint functions mirroring `entities.py`:

- `@router.get("")` → `list_all(include_deleted: bool = False)` returns `ok(persona.list_personas(...))`
- `@router.get("/next-identifier")` → `next_identifier()` returns `ok({"next": persona.next_persona_identifier(s)})`
- `@router.get("/{identifier}")` → `get(identifier, include_deleted: bool = False)` — `NotFoundError("persona", identifier)` if `None`
- `@router.post("", status_code=201)` → `create(body: PersonaCreateIn)` — pass through `name=body.persona_name`, `role_summary=body.persona_role_summary`, etc., `identifier=body.persona_identifier`
- `@router.put("/{identifier}")` → `replace(identifier, body: PersonaReplaceIn)`
- `@router.patch("/{identifier}")` → `patch(identifier, body: PersonaPatchIn)` — uses `model_dump(exclude_unset=True)` then strips `_FIELD_PREFIX`
- `@router.delete("/{identifier}")` → `delete(identifier)`
- `@router.post("/{identifier}/restore")` → `restore(identifier)`

Module docstring cites `persona.md` §3.5.1 (endpoint set), §3.5.4 (decomposed references — no inline-affiliation or inline-realization convenience endpoints), and the `{data, meta, errors}` envelope rule.

### Step 7 — Register the router in `api/main.py`

**Path:** `crmbuilder-v2/src/crmbuilder_v2/api/main.py`

Add `persona` (or `personas` — match Step 6's filename) to the existing methodology cluster `from crmbuilder_v2.api.routers import (...)` block on or near line 28 (it currently imports `domains`, `entities`, `processes`, `crm_candidates`, `engagements`). Insert `persona` after `crm_candidates` to preserve workstream-introduction order.

In `create_app()` around line 143, add `app.include_router(persona.router)` after the `crm_candidates` line (or `engagements` — verify the current order) and before `references`. The order is cosmetic but keeps the methodology cluster contiguous.

### Step 8 — UI client methods

**Path:** `crmbuilder-v2/src/crmbuilder_v2/ui/client.py`

Add an eight-method block after `next_entity_identifier` (line ~795), under a section header comment `# ----- Personas (methodology entity — v0.5+) -----`. Mirror the eight `*_entity` methods (lines ~661–795) exactly with persona-prefixed paths and field names:

- `list_personas(self, *, include_deleted: bool = False) -> list[dict[str, Any]]`
- `get_persona(self, identifier: str) -> dict[str, Any]`
- `create_persona(self, body: dict[str, Any]) -> dict[str, Any]` — POST `/personas`
- `update_persona(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]` — PUT
- `patch_persona(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]` — PATCH
- `delete_persona(self, identifier: str) -> Any` — DELETE
- `restore_persona(self, identifier: str) -> dict[str, Any]` — POST `/personas/{id}/restore`
- `next_persona_identifier(self) -> str` — GET `/personas/next-identifier`

Each docstring cites `persona.md` (sections as appropriate). Same `_request` calls and same `ServerError` raise-on-wrong-shape posture as the entity methods.

### Step 9 — Sidebar entry

**Path:** `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py`

In `SIDEBAR_GROUPS` (lines ~52–81), append `"Personas"` to the Methodology group's entries tuple. The current tuple is `("Domains", "Entities", "Processes", "CRM Candidates")`; after this build it becomes `("Domains", "Entities", "Processes", "CRM Candidates", "Personas")`.

Position rationale: persona.md §3.6.1 calls position #6 in the methodology group (after Engagements at #5), but the existing v0.4 layout has Engagements in its own sidebar group above Governance — so within the Methodology group itself this is position #5. Use position #5 (append). Update the comment on line ~50–51 to add a v0.5+ note about the persona entry.

### Step 10 — Main window dispatch

**Path:** `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py`

Two edits:

**10a.** Add to the entity-type → sidebar-label dict at the top of the file (lines ~80–86): `"persona": "Personas",`. Position after `"crm_candidate": "CRM Candidates",`.

**10b.** Add to the panel-dispatch chain around line 156. After the `elif entry == "CRM Candidates":` branch:

```python
elif entry == "Personas":
    page = PersonasPanel(self._client)
```

Add the matching import near line 47: `from crmbuilder_v2.ui.panels.persona import PersonasPanel` (singular module path; see Step 11). Maintain alphabetical order within the methodology-panels import block.

### Step 11 — Panel

**Path:** `crmbuilder-v2/src/crmbuilder_v2/ui/panels/persona.py`

Singular module name to match `repositories/persona.py` and `routers/persona.py`. Note the existing `panels/` directory uses mixed conventions (`entities.py` is plural, `crm_candidates.py` is plural, `domains.py` is plural). **Use singular `persona.py` to align with the spec's prefix convention** — the file name carries no semantic weight; the class name (`PersonasPanel`, plural) is what matters for naming consistency with `EntitiesPanel`, `DomainsPanel`. Verify your choice doesn't clash with anything by `ls crmbuilder-v2/src/crmbuilder_v2/ui/panels/ | grep -i persona` (expect no matches before the build).

New file mirroring `panels/entities.py` (455 lines). Class `PersonasPanel(ListDetailPanel)` with persona-specific adjustments:

- `entity_title()` returns `"Personas"`.
- `fetch_records()` returns `self._client.list_personas(include_deleted=self._include_deleted)`.
- `list_columns()` returns four `ColumnSpec` per persona.md §3.6.2: `persona_identifier` (Identifier, width 120, default sort ascending), `persona_name` (Name), `persona_status` (Status, width 110), `persona_updated_at` (Updated, width 180). **No Domains or Realized-as columns in v0.5+** per spec §3.6.2.
- `_strikethrough_for_record(record)` checks `persona_deleted_at`.
- `fetch_detail_extras(record)` returns the references touching the persona via `self._client.list_references_touching("persona", identifier)`.
- `render_detail(record, extras)` builds the detail pane per persona.md §3.6.3: identifier (read-only label), name (read-only line), role summary (read-only multi-line, with placeholder per spec), responsibilities under a `CollapsibleSection` **expanded by default** (per §3.6.3 because it is client-facing content when populated), notes under a `CollapsibleSection` **collapsed by default** (consultant scratchpad), status (disabled combo with transition hint caption), `ReferencesSection` widget for outgoing `persona_scopes_to_domain` and `persona_realized_as_entity` plus any inbound (which is nothing in v0.5+ but the widget is always present per §3.6.3).
- Identifier addressing helpers `_select_by_identifier` and `_currently_selected_identifier` use the `persona_identifier` key.
- Right-click context menu `_build_context_menu` offers New / Edit / Delete (or New / Edit / Restore for soft-deleted rows).
- Click handlers `_on_new_persona_clicked` / `_on_edit_clicked` / `_on_delete_clicked` / `_on_restore_clicked` instantiate the three dialogs from Step 12.

Module docstring cites `persona.md` §3.6.2 (master), §3.6.3 (detail), and notes that this is the **first methodology panel surfacing two outgoing reference kinds** (entities panel surfaces only `entity_scopes_to_domain`; persona surfaces both `persona_scopes_to_domain` and `persona_realized_as_entity`).

**Placeholder text:** "Brief description of what this role does in the organization" for `persona_role_summary` per spec §3.6.3. For `persona_responsibilities`, no placeholder needed when expanded by default; the section header "Responsibilities" carries the meaning.

### Step 12 — CRUD dialogs

**Paths:** `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/persona_crud.py` + `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/_persona_schema.py`

**12a. `_persona_schema.py`** mirrors `_entity_schema.py` (105 lines):

- Imports `PERSONA_STATUS_TRANSITIONS` and `PERSONA_STATUSES` from vocab.
- `IDENTIFIER_RE = re.compile(r"^PER-\d{3}$")`.
- `_ROLE_SUMMARY_PLACEHOLDER = "Brief description of what this role does in the organization"`.
- `status_choices(current: str | None) -> list[str]` mirrors entity's helper using `PERSONA_STATUS_TRANSITIONS`.
- `_IDENTIFIER_FIELD = FieldSchema(key="persona_identifier", label="Identifier", widget="line", read_only_on_edit=True)`.
- `_CONTENT_FIELDS` list:
  - `persona_name` (line, required)
  - `persona_role_summary` (text, required, placeholder set)
  - `persona_responsibilities` (text, **not required**)
  - `persona_notes` (text, label "Internal notes")
  - `persona_status` (combo, required, vocab `PERSONA_STATUSES`, default `"candidate"`, `compute_options=lambda state: status_choices(state.get("persona_status"))`)
- `persona_fields(*, include_identifier: bool) -> list[FieldSchema]` mirrors `entity_fields`.

**12b. `persona_crud.py`** mirrors `entity_crud.py` (128 lines):

- `PersonaCreateDialog(EntityCrudDialog)` — create mode, identifier hidden, title "New persona", `create_method=client.create_persona`, exposes `created_identifier()` via `saved_identifier()`.
- `PersonaEditDialog(EntityCrudDialog)` — edit mode, identifier read-only, title `f"Edit {identifier}"`, `update_method=client.patch_persona`.
- `PersonaDeleteDialog(EntityCrudDeleteDialog)` — edge-text confirmation per persona.md §3.6.6, body text: `f"Delete {identifier} — {title or '(untitled)'}?\n\nType the identifier below to confirm. This soft-deletes the persona; it can be restored from the Show-deleted view. Any domain affiliations and entity realizations are kept."` (note both reference kinds called out, not just affiliations).

**Create-dialog flow choice (per persona.md §3.8.1 — open question for v0.5+ build).** Two patterns are spec-equivalent: create-then-attach (the New dialog creates only; user adds affiliations and realization from the detail pane afterward) vs create-with-attach (multi-select for domains + single-select for entity realization). Adopt the same pattern the v0.4 entity build adopted, **which is create-then-attach** (per DEC-067 — see `entity_crud.py` docstring). Reasoning: cross-entity-type consistency and the v0.4 user already knows the affordance. The decision is in-build and surfaces as a one-line note in the close-out's decisions section.

### Step 13 — Tests

Three new test files. Mirror the existing entity tests directly — same fixture (`v2_env`, `client`), same structural pattern, same numbered-criterion organization. Use the actual file paths under `tests/crmbuilder_v2/` (not `crmbuilder-v2/tests/...` — verified at draft time).

**13a. `tests/crmbuilder_v2/access/test_persona.py`** mirrors `test_entity.py`. Cover persona.md §3.7 acceptance criteria 1–5 and 8 plus the two persona-specific assertions:

- Criterion 1: `_EXPECTED_COLUMNS` map of nine columns and affinities; primary key is `persona_identifier`; nullability of `persona_responsibilities`, `persona_notes`, `persona_deleted_at`.
- Criterion 2: format constraint; POST without identifier auto-assigns `PER-001` then `PER-002`; malformed explicit identifier raises `UnprocessableError`.
- Criterion 3: case-insensitive name uniqueness; second insert with same name in different case raises `UnprocessableError`.
- Criterion 4: status enum rejects invalid values; invalid transitions raise `StatusTransitionError` (`confirmed` → `candidate` is the canonical example).
- Criterion 5: each of the eight functions exercised happy-path plus at least one error case. Two persona-specific assertions in this section: (a) soft-deleting a persona with outbound `persona_scopes_to_domain` and `persona_realized_as_entity` references does NOT delete the references — verify by querying the refs table directly after the soft-delete; (b) status changes never consult any related records — verify by setting up a persona scoped to a `deferred` domain and then transitioning the persona's own status without error.
- Criterion 7: concurrent-insert test using `threading` mirroring `test_entity.py`'s pattern — two threads each POST without identifier; assert two distinct identifiers.
- Criterion 8: soft-delete sets `persona_deleted_at` and disappears from `list_personas()`; `include_deleted=True` includes it; `restore_persona` clears the timestamp; double-restore raises 422.

**13b. `tests/crmbuilder_v2/api/test_personas_api.py`** mirrors `test_entities_api.py`. Cover acceptance criteria 6, 7, and the vocab criterion (13):

- All eight endpoints return correct status + envelope-wrapped JSON for happy path and failure.
- POST without `persona_identifier` → 201 with `data.persona_identifier == "PER-001"`.
- POST with malformed `persona_identifier` → 422 with v2 error envelope.
- POST with colliding explicit `persona_identifier` → 409.
- PUT with `persona_identifier` mismatching the path → 422.
- PATCH with unknown field → 422.
- PATCH with invalid status transition → 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.
- DELETE / restore round-trip; double-restore → 422.
- GET `/personas/next-identifier` returns `{"data": {"next": "PER-NNN"}, ...}`.
- Concurrent-POST test (threading) verifies acceptance criterion 7's race-free identifier auto-assignment under the HTTP boundary.
- Criterion 13: POST `/references` with `(source_type=persona, target_type=domain, relationship_kind=persona_scopes_to_domain)` succeeds (after creating the persona and a domain); POST with `(persona, domain, persona_realized_as_entity)` returns 422 (wrong target type for that kind); POST with `(persona, entity, persona_realized_as_entity)` succeeds; POST with `(persona, domain, totally_made_up_kind)` returns 422. Verifies the vocab + `_kinds_for_pair` integration end-to-end.

**13c. `tests/crmbuilder_v2/ui/test_personas_panel.py`** — a smoke test mirroring `test_entities_panel.py`. Minimum scope: instantiate `PersonasPanel` against a `FakeStorageClient` exposing the eight persona methods plus `list_references_touching`; assert the panel renders without exception, the master columns match the spec, and the New button label is "New Persona". If `test_entities_panel.py` exercises detail-pane rendering, mirror that too with at least one persona record. Use the existing `pytestqt`/`qtbot` fixtures already in use in `tests/crmbuilder_v2/ui/`.

### Step 14 — Run the test suite

```bash
cd crmbuilder-v2
uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -30
cd ..
```

Expected: baseline pass count plus the new persona tests passing. The new test file count is three (test_persona.py + test_personas_api.py + test_personas_panel.py); count the individual test functions you authored and verify the same number pass. Halt and report if any previously-passing test now fails.

---

## Verification

After the migration, code, and tests are in place, integrate against the running engagement DB and verify end-to-end:

1. **Apply the migration:**

   ```bash
   cd crmbuilder-v2
   uv run alembic upgrade head 2>&1
   uv run alembic current 2>&1
   # Expected: 00XX_v0_8_create_personas_table (head)
   cd ..
   ```

2. **Restart the API server** so it picks up the new model, router, vocab, and schema:

   ```bash
   pkill -f crmbuilder-v2-api 2>/dev/null
   sleep 1
   cd crmbuilder-v2 && uv run crmbuilder-v2-api &
   sleep 2
   curl -sf http://127.0.0.1:8765/health
   cd ..
   ```

3. **Smoke-test the `/personas` surface:**

   ```bash
   # Empty list
   curl -s http://127.0.0.1:8765/personas
   # Expect: {"data":[],"meta":{},"errors":null}

   # Auto-assigned identifier
   curl -sX POST http://127.0.0.1:8765/personas \
     -H 'Content-Type: application/json' \
     -d '{"persona_name":"Test Persona","persona_role_summary":"Smoke test record — will be deleted"}'
   # Expect: 201, data.persona_identifier == "PER-001", data.persona_status == "candidate"

   # Next-identifier helper
   curl -s http://127.0.0.1:8765/personas/next-identifier
   # Expect: {"data":{"next":"PER-002"},...}

   # Single fetch
   curl -s http://127.0.0.1:8765/personas/PER-001 \
     | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(d['persona_name'], d['persona_status'])"

   # Vocab integration — create a domain, attach a persona_scopes_to_domain reference
   curl -sX POST http://127.0.0.1:8765/domains \
     -H 'Content-Type: application/json' \
     -d '{"domain_name":"Test Domain","domain_purpose":"Smoke test","domain_description":"Smoke"}' \
     | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('domain:', d['domain_identifier'])"
   # Note the returned DOM-NNN identifier — use it in the next call:
   DOM_ID=<the DOM-NNN from above>
   curl -sX POST http://127.0.0.1:8765/references \
     -H 'Content-Type: application/json' \
     -d "{\"source_type\":\"persona\",\"source_id\":\"PER-001\",\"target_type\":\"domain\",\"target_id\":\"$DOM_ID\",\"relationship_kind\":\"persona_scopes_to_domain\"}"
   # Expect: 201

   # Delete the smoke-test data so it doesn't clutter the engagement DB
   curl -sX DELETE http://127.0.0.1:8765/personas/PER-001
   curl -sX DELETE http://127.0.0.1:8765/domains/$DOM_ID
   ```

4. **UI smoke check (optional but recommended).** Launch the desktop app, navigate to Methodology → Personas, create a record through the dialog, attach a `persona_scopes_to_domain` reference from the detail pane's `ReferencesSection`, verify the record persists across an app restart. Delete the test record.

5. **Final test-suite re-run** after the migration and integration smoke tests have touched the engagement DB:

   ```bash
   cd crmbuilder-v2
   uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -10
   cd ..
   ```

   Same expectation as Step 14 — baseline pass count plus the new persona tests, no regressions.

---

## Close-out

This session resolves PI-003 in a v0.8-shape nine-section close-out payload. Mirror SES-078's close-out structure (`PRDs/product/crmbuilder-v2/close-out-payloads/ses_078.json` and `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-078.md`) for layout — they are the most recent worked example.

1. **Pick the next available SES, DEC, CONV, and PI identifiers.** Re-query the running API (pre-flight Step 10 captured the heads, but re-verify just before authoring the payload in case parallel-sandbox work has claimed identifiers in the meantime):

   ```bash
   for ep in sessions decisions; do
     echo "$ep head:"
     curl -s "http://127.0.0.1:8765/$ep?limit=2000" \
       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
   done
   echo "Conversations head:"
   curl -s 'http://127.0.0.1:8765/conversations?limit=2000' \
     | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['conversation_identifier'] for r in d)[-1] if d else 'none')"
   ```

   Use the next integer in each prefix. If a parallel session has claimed a higher number than was visible at pre-flight, re-key the payload accordingly (per the CLAUDE.md "identifier-collision contingency for parallel-sandbox work" pattern surfaced in SES-077). Inspect `PRDs/product/crmbuilder-v2/close-out-payloads/` for the highest already-staged-but-not-yet-applied `ses_NNN.json`; the next SES number must clear both the API head and the staged-payload set.

2. **Author `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`** (where `NNN` is the chosen SES number). The nine sections per CLAUDE.md "v2 session lifecycle — closing a session" and per `ses_078.json`'s shape:

   - **`session`** — session record (`identifier`, `title`, `session_date`, `status: "Complete"`, `conversation_reference`, `topics_covered`, `summary`, `artifacts_produced`, `in_flight_at_end`). Title: "PI-003 build — `persona` methodology entity type end-to-end (migration, access, REST, UI, tests)". `session_date`: today's date in `YYYY-MM-DD`.
   - **`conversation`** — `conversation_identifier`, `conversation_title`, `conversation_purpose`, `conversation_description`, `conversation_status: "complete"`, plus the two required references: `conversation_belongs_to_workstream` to a workstream covering PI-003's lineage (likely an existing v0.5+ methodology-entity workstream — query `/workstreams` to confirm; if none exists, add a pre-step to the apply prompt that creates one, mirroring SES-074's and SES-078's precedent), and `conversation_records_session` to the SES record.
   - **`work_tickets`** — empty list `[]` (no work_ticket is produced by this build; the spec authoring conversation that produced `persona.md` was the conversation that addressed PI-003's design, and the kickoff that opened *this* build session is a separate WT that lives elsewhere if at all).
   - **`planning_items`** — empty list (this build creates no new PIs; persona.md §3.8.3 names three deferred items for v0.6+ that will be authored by future spec / design sessions, not by this build).
   - **`commits`** — one or more entries for the commit(s) this build produces (typically one consolidated commit; see step 4 below for the commit subject). Each entry: `commit_sha`, `commit_message_first_line`, `commit_message_full`, `commit_author_name`, `commit_author_email`, `commit_committed_at` (ISO 8601 with offset), `commit_repository: "crmbuilder"`, `commit_branch: "main"`, `commit_parent_shas: [...]`, `commit_files_changed_count`. These fields populate the `commits` table per `governance-schema-specs/commit.md` §3.2 and the apply assigns `CM-NNNN`.
   - **`decisions`** — five decisions per persona.md §3.9.1, renumbered from the spec's `DEC-XXX-1` through `DEC-XXX-5` placeholders to concrete DEC numbers starting at the head + 1. Each entry: `identifier`, `title`, `body`, `decided_in` (the SES from this build), `status: "Active"`. Titles and bodies follow the spec's §3.9.1 wording (spec is the source of truth — copy verbatim, do not rephrase).
   - **`references`** — `is_about` references that surface this build's intellectual genealogy for future audit queries. At minimum: SES → PI-003 (the work resolves it), SES → `persona.md` (cite the spec as a reference — but only if `persona.md` is represented in v2 as a reference_book record; query `/reference-books` to check, and skip if not yet ingested). Also `is_about` from the new conversation to the design-conversation that produced `persona.md` (if that conversation is recorded). Inspect the predecessor specs' build sessions for analogous reference patterns (entity build close-out is the closest comparand).
   - **`resolves_planning_items`** — `[{"planning_item_identifier": "PI-003"}]`. This single entry atomically flips PI-003 from `Open` to `Resolved` via slice A's server-side atomic edge+flip on POST `/references` with `relationship=resolves`.
   - **`addresses_planning_items`** — empty list (this build resolves PI-003; nothing additionally addresses without resolving).

3. **Author the apply prompt** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`. Mirror `CLAUDE-CODE-PROMPT-apply-close-out-ses-078.md`'s shape (most recent example). Sections:

   - Header with `Last Updated`, `Purpose` (one-paragraph summary citing PI-003 resolution), `Payload file` path, `Predecessors` (the immediately-prior SES apply must have landed), `Successor` (none planned), and any `Pre-publication TODOs` (e.g., commit SHA to be filled in once the commit lands).
   - **Scope** — the nine-section payload contents enumerated.
   - **Pre-flight** — working-directory, git-status, git-pull, API-health, payload-file-exists, PI-003-still-Open check, pre-apply identifier-head capture.
   - **Pre-step: create workstream if absent** (only if Step 2's `conversation_belongs_to_workstream` target doesn't exist; mirror SES-078's `WS-011` pattern verbatim).
   - **Apply** — the single command: `cd crmbuilder-v2 && uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`. The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` automatically.
   - **Post-apply verification** — confirm the SES, CONV, DEC, PI flip, commits, references, deposit_event landed; spot-check `/personas` to confirm the new endpoints are reachable (which they will be regardless of this apply — the API surface landed in the code commit, not via the apply payload).
   - **Commit the apply artifacts** — db-export snapshots + new dep_NNN.log + (if not committed separately) the payload + apply prompt + code.

4. **Run the apply:**

   ```bash
   cd crmbuilder-v2
   uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json
   cd ..
   ```

   Expect: success line per the apply script's convention, with each section's row counts reported. The script atomically writes records, lazy-creates the `close_out_payload` and `deposit_event` entities, and creates the `dep_NNN.log` file. Re-running is idempotent (HTTP 409s are skipped).

5. **Regenerate the db-export snapshots.** The apply script regenerates these into `PRDs/product/crmbuilder-v2/db-export/`. Verify with `git status` that the expected files changed (`planning_items.json`, `sessions.json`, `change_log.json`, `conversations.json`, `references.json`, `close_out_payloads.json`, `deposit_events.json`, `commits.json`, plus the new `dep_NNN.log` under `deposit-event-logs/`).

6. **Commit everything in one commit.** Subject line begins with `v2: PI-003 —` per the established convention. Suggested commit subject:

   `v2: PI-003 — persona methodology entity type end-to-end (migration, access, REST, UI, tests)`

   Commit body summarizes what landed: migration `00XX`, model `Persona`, repository `access/repositories/persona.py`, three Pydantic schemas, router `api/routers/persona.py`, eight client methods, sidebar entry, main-window dispatch, panel `ui/panels/persona.py`, dialogs `ui/dialogs/persona_crud.py` + `_persona_schema.py`, three test files, two new vocab entries (`persona_scopes_to_domain`, `persona_realized_as_entity`), `'persona'` added to `ENTITY_TYPES` and the three CHECK extensions. Acceptance criteria 1–14 from persona.md §3.7 mapped to the test count. The five new decisions (`DEC-NNN-1` through `DEC-NNN-5`, with concrete numbers).

   Per CLAUDE.md's commit signature convention, end the message with:
   ```
   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```

   Use a HEREDOC for the commit message to preserve formatting. Stage explicitly — do not `git add -A` (the v2 storage layer's secret-free posture makes this safe, but the precedent across the repo is explicit staging).

7. **Doug pushes.** Per the local-clone working convention (CLAUDE.md "Push convention"): Claude Code commits, Doug pushes after reviewing. Halt and report after the commit lands locally; do not push.

---

## Done

Reply with:

- Pre-flight Alembic head: `<head_at_pre_flight>`
- Post-migration Alembic head: `00XX_v0_8_create_personas_table` (the new revision id)
- Baseline test pass count: `<baseline>`
- Post-build test pass count: `<baseline> + <new persona test count>`
- New tests authored: `<count>` across the three test files
- Endpoints reachable: GET `/personas` returns empty envelope, POST returns 201 with `PER-001`
- Vocab integration verified: `(persona, domain) → persona_scopes_to_domain` works; `(persona, entity) → persona_realized_as_entity` works
- PI-003 status post-apply: `Resolved`
- New SES identifier: `SES-NNN`
- New DEC identifiers: `DEC-NNN` through `DEC-NNN+4` (the five from persona.md §3.9.1)
- New CONV identifier: `CONV-NNN`
- Commit SHA: `<sha>`
- Apply success: deposit_event `DEP-NNN`, close_out_payload `COP-NNN`, log file `deposit-event-logs/dep_NNN.log`
- Open items for next session: typically none — PI-003 is resolved; the three v0.6+ planning items called out in persona.md §3.8.3 (persona authority / membership cardinality / realization-mechanism reconsideration) are deliberately deferred and authored by future sessions when CBM-redo signal motivates them.
