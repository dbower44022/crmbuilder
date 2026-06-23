# CLAUDE-CODE-PROMPT-pi255-B-rest-and-reconciler.md

## Operating mode: DETAIL

## Purpose

Build slice 2 of the source instance mapping model (PI-255, SES-230, PRJ-027).
Slice 1 (vocab, ORM models, migration 0079, repositories) is already on `main`.

**Scope of this prompt:**
- REST endpoints for all five source mapping repository modules
- Integration tests for the REST layer
- `source_mapping_reconciler.py` — the audit reconciler that writes candidates
  instead of auto-promoting canonical objects
- Wire everything into the API router
- A single migration for any new `instance_membership` state column changes
  needed to support `candidate_pending` and `mapping_stale` at the API layer

---

## Pre-flight

```bash
cd ~/Dropbox/Projects/CRMBuilder
git status
git branch
git log --oneline -5

cd crmbuilder-v2

# Read the actual migration head — Prompt B's migration number depends on this
uv run alembic -c migrations/alembic.ini heads

# Confirm slice 1 is on main
ls src/crmbuilder_v2/access/repositories/ | grep -E "source_mapping|field_mapping|value_mapping|mapping_candidate"
python -c "from crmbuilder_v2.access.vocab import SOURCE_MAPPING_DECISION_TYPES; print('slice 1 present:', SOURCE_MAPPING_DECISION_TYPES)"

# Confirm the API router location
ls src/crmbuilder_v2/api/
```

Read `CLAUDE.md` at the repo root before making any changes. Read an existing
router module (e.g. `src/crmbuilder_v2/api/routers/instances.py`) in full before
writing any new router. Read `src/crmbuilder_v2/api/routers/__init__.py` (or
equivalent router registration file) to understand how routers are wired.

**Set the migration number** based on the `alembic heads` output above:
- If the current head is `0079_pi_255_source_mapping_tables` → new migration is **0080**
- If the current head is `0080_*` (PI-262 already landed) → new migration is **0081**
- Use whatever the actual head number is + 1. Never assume.

---

## Step 1 — Governance pre-step

Before writing any code, verify the requirements from slice 1 are still confirmed
and PI-255 is still in the implementing-PI position:

```python
import json, urllib.request
BASE = "http://127.0.0.1:8765"
HEADERS = {"Content-Type": "application/json", "X-Engagement": "CRMBUILDER"}

def api(method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["data"]

# Confirm PI-255 exists and is in-progress
pi = api("GET", "/planning-items/PI-255")
print(f"PI-255: {pi['planning_item_title']} — {pi['planning_item_status']}")

# List requirements linked to PI-255
refs = api("GET", "/references?source_id=PI-255&relationship=planning_item_implements_requirement")
for r in refs:
    req = api("GET", f"/requirements/{r['target_id']}")
    print(f"  {r['target_id']}: {req['requirement_status']} — {req['requirement_title'][:60]}")
```

All requirements must show `confirmed`. If any show `candidate`, stop and resolve
before proceeding.

The REST endpoints and reconciler are covered by the existing confirmed requirements
(source mapping REST API — endpoints for all mapping tables; source mapping
reconciler — candidates not auto-promotion). No new requirements are needed for
slice 2 — it implements the same approved scope as slice 1.

---

## Step 2 — Write REST router modules

Create five router files in `src/crmbuilder_v2/api/routers/`. Follow the exact
pattern of `src/crmbuilder_v2/api/routers/instances.py` for:
- Route naming (`/source-mappings`, `/field-mappings`, `/value-mappings`,
  `/mapping-candidates`, `/source-mapping-targets`)
- Pydantic request/response models
- `{data, meta, errors}` envelope via `envelope.py`
- Session dependency injection
- Error handler imports (`NotFoundError`, `UnprocessableError`, etc.)

### 2a. `source_mappings.py`

Routes:
- `GET /source-mappings` — list, query params: `instance_identifier`, `status`,
  `include_deleted` (bool, default false)
- `POST /source-mappings` — create; body: `instance_identifier`, `source_entity_name`,
  `decision_type`, `notes` (optional), `identifier` (optional)
- `GET /source-mappings/{identifier}` — get one; query: `include_deleted`
- `PUT /source-mappings/{identifier}` — full update
- `PATCH /source-mappings/{identifier}` — partial update
- `DELETE /source-mappings/{identifier}` — soft-delete
- `POST /source-mappings/{identifier}/restore` — restore
- `POST /source-mappings/{identifier}/mark-stale` — body: `reason`, `severity`
- `GET /source-mappings/next-identifier` — returns next SMG-NNN

### 2b. `source_mapping_targets.py`

Routes:
- `GET /source-mapping-targets` — list by `source_mapping_identifier` (required)
- `POST /source-mapping-targets` — add one target; body: `source_mapping_identifier`,
  `entity_identifier`
- `DELETE /source-mapping-targets` — remove one; body: same two fields
- `PUT /source-mapping-targets/{source_mapping_identifier}` — set (atomic replace);
  body: `entity_identifiers: list[str]`

### 2c. `field_mappings.py`

Routes mirror `source_mappings.py` with `FMP` prefix:
- `GET /field-mappings` — query: `source_mapping_identifier`, `status`,
  `include_deleted`
- `POST /field-mappings` — create
- `GET /field-mappings/{identifier}`
- `PUT /field-mappings/{identifier}`
- `PATCH /field-mappings/{identifier}`
- `DELETE /field-mappings/{identifier}`
- `POST /field-mappings/{identifier}/restore`
- `POST /field-mappings/{identifier}/mark-stale`
- `GET /field-mappings/next-identifier`

### 2d. `value_mappings.py`

Routes (integer PK, not identifier):
- `GET /value-mappings` — query: `field_mapping_identifier` (required),
  `include_superseded` (bool, default false)
- `POST /value-mappings` — create
- `GET /value-mappings/{id}` — integer id
- `PUT /value-mappings/{id}`
- `POST /value-mappings/{id}/supersede` — body: `replacement_id: int`

### 2e. `mapping_candidates.py`

Routes:
- `GET /mapping-candidates` — query: `instance_identifier`, `candidate_type`,
  `resolved` (bool, optional)
- `POST /mapping-candidates` — create one
- `POST /mapping-candidates/bulk` — bulk create; body: `candidates: list[dict]`
- `GET /mapping-candidates/{id}`
- `POST /mapping-candidates/{id}/resolve` — body: `resolved_to_source_mapping_identifier`
  (optional), `resolved_to_field_mapping_identifier` (optional)

---

## Step 3 — Register all five routers

Find the router registration file (likely `src/crmbuilder_v2/api/main.py` or
`src/crmbuilder_v2/api/__init__.py` or a dedicated `routers/__init__.py`).
Read it first to understand the exact pattern, then add the five new routers
following the same prefix and tag conventions as existing routers.

---

## Step 4 — Write the source mapping reconciler

Create `src/crmbuilder_v2/access/repositories/source_mapping_reconciler.py`.

This module is the bridge between an audit result and the mapping/membership layers.
It replaces the old auto-promotion behavior for source instance audits.

Module-level docstring: PI-255 source mapping reconciler. Called by the audit
pipeline when a source instance audit completes. Writes mapping_candidate records
for unmatched discovered objects instead of auto-promoting to canonical design
objects. Updates instance_membership states to candidate_pending for unmatched
objects and mapping_stale for objects whose existing mapping has become stale.
See source-mapping-design.md for the design model (SES-230, DEC-575..580).

### Core function: `reconcile_source_audit`

```python
def reconcile_source_audit(
    session,
    *,
    instance_identifier: str,
    audit_event_identifier: str | None,
    discovered_entities: list[dict],
) -> dict:
    """
    Reconcile a source instance audit against existing source mappings.

    discovered_entities: list of dicts, each with:
        - source_entity_name: str
        - source_fields: list[dict] with keys:
            - source_field_name: str
            - field_type: str (optional)
            - enum_values: list[str] (optional, for enum/multiEnum fields)

    Returns a summary dict:
        - candidates_created: int
        - membership_updated: int
        - mappings_marked_stale: int
        - details: list of per-entity result dicts
    """
```

**Algorithm (per discovered entity):**

1. Look up existing `source_mapping` records for this `instance_identifier` and
   `source_entity_name`.

2. **If no existing source mapping exists** → the entity is unmatched:
   - Check prior source mappings from *other* instances for the same
     `source_entity_name` to generate a suggestion (DEC-580 — prior mappings
     are the suggestion engine).
   - Call `create_candidate` with `candidate_type='entity'`, populated
     `suggestion_confidence` and `suggestion_basis` if a prior mapping was found.
   - Set `instance_membership` state to `candidate_pending` for this entity on
     this instance (call `upsert_membership` from `instance_membership.py`).

3. **If an existing source mapping exists with status `resolved`** → check
   staleness:
   - For each field in `discovered_entities`, check whether a `field_mapping`
     exists for that `source_field_name` under this `source_mapping`.
   - If a field has no `field_mapping` → create a `field`-level candidate.
   - If a field has a `field_mapping` but new enum values appeared → create
     `value`-level candidates for the new values and call `mark_stale` on the
     field_mapping (reason=`source_changed`, severity=`low`).
   - If the source field name is no longer present in `discovered_entities` but
     has a resolved `field_mapping` → call `mark_stale` on the field_mapping
     (reason=`source_changed`, severity=`low`).
   - Set `instance_membership` state to `mapping_stale` if any staleness was
     detected; otherwise `present`.

4. **If an existing source mapping exists with status `unresolved` or `stale`** →
   no new candidates needed (already queued); update `instance_membership` to
   `candidate_pending`.

5. **Return the summary dict** with counts of candidates created, membership
   rows updated, and mappings marked stale.

**Suggestion engine logic** (step 2, for new entity candidates):

```python
def _find_suggestion(session, source_entity_name: str, exclude_instance: str) -> dict | None:
    """
    Look for a resolved source_mapping for this entity_name on any other instance.
    Returns {'source_mapping_identifier': ..., 'confidence': 'high'|'medium',
             'basis': 'identical_to_INST-NNN'} or None.
    """
```

- Query `source_mappings` where `source_entity_name = X` and
  `instance_identifier != exclude_instance` and `status = 'resolved'`.
- If found: confidence = `high` if the resolved mapping has the same field names
  in its `field_mappings`; otherwise `medium`.
- `suggestion_basis` = `f"identical_to_{prior_instance_identifier}"` or
  `"name_match_from_{prior_instance_identifier}"`.

---

## Step 5 — Write integration tests

Create `tests/test_pi255_rest_and_reconciler.py`.

**REST — source_mappings:**
- `POST /source-mappings` creates with status `unresolved`
- `GET /source-mappings` lists; filter by `instance_identifier` works
- `POST /source-mappings/{id}/mark-stale` sets status=stale, reason, severity
- `DELETE /source-mappings/{id}` soft-deletes; `GET` with `include_deleted=true`
  returns it
- `POST /source-mappings/{id}/restore` clears deleted_at
- `GET /source-mappings/next-identifier` returns `SMG-NNN`

**REST — source_mapping_targets:**
- `POST /source-mapping-targets` adds target; idempotent second call returns 200
- `PUT /source-mapping-targets/{id}` replaces atomically
- `DELETE /source-mapping-targets` removes one

**REST — field_mappings:**
- `POST /field-mappings` creates; `GET` lists by source_mapping_identifier
- `POST /field-mappings/{id}/mark-stale`

**REST — value_mappings:**
- `POST /value-mappings` creates; `GET` returns active only by default
- `POST /value-mappings/{id}/supersede`

**REST — mapping_candidates:**
- `POST /mapping-candidates` creates entity-level candidate
- `POST /mapping-candidates/bulk` creates multiple
- `POST /mapping-candidates/{id}/resolve` marks resolved

**Reconciler:**
- Unmatched discovered entity → creates entity-level candidate,
  membership state = `candidate_pending`
- Matched resolved mapping + new field → creates field-level candidate
- Matched resolved mapping + new enum value → creates value-level candidate,
  field_mapping status = `stale`
- Matched resolved mapping + field no longer present → field_mapping status = `stale`
- Prior resolved mapping on different instance → suggestion populated on new candidate

---

## Step 6 — Run tests

```bash
# New test file only first
uv run pytest tests/test_pi255_rest_and_reconciler.py -v

# Full non-UI suite
uv run pytest tests/ -x -q --ignore=tests/ui

# Alembic head unchanged (no new migration in slice 2 unless needed)
uv run alembic -c migrations/alembic.ini heads
```

---

## Step 7 — Commit

```bash
git add -A
git commit -m "v2: PI-255 slice 2 — source mapping REST endpoints and reconciler"
```

Do NOT push. Doug pushes.

---

## Done

Reply with:
- Governance pre-step result (PI-255 status, requirement statuses)
- Migration head (should be unchanged from slice 1 unless a new migration was needed)
- Test results (pass/fail counts for new tests + full suite)
- Router registration confirmation (all five routers wired)
- Any deviations from this spec and why
- Confirmation that the full non-UI suite is green
