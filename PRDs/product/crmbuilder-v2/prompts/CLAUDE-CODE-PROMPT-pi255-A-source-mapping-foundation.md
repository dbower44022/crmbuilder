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

## Step 0 — Governance pre-step (REQUIRED before any code)

Per CLAUDE.md: confirmed requirements + implementing PI must exist before any code is written.

PI-255 and PI-256 exist in the governance DB (created by SES-230 apply). Requirements do not yet exist. Create and approve them now via the live API before touching any source files.

### 0a. Verify API is running and check heads

```python
import json, urllib.request, urllib.error

BASE = "http://127.0.0.1:8765"
ENG = "CRMBUILDER"
HEADERS = {"Content-Type": "application/json", "X-Engagement": ENG}

def api(method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["data"]

# Check heads
reqs = api("GET", "/requirements?sort=requirement_identifier&order=desc&limit=1")
decs = api("GET", "/decisions?sort=identifier&order=desc&limit=1")
print("Last REQ:", reqs[0]["requirement_identifier"] if reqs else "none")
print("Last DEC:", decs[0]["identifier"] if decs else "none")

# Confirm PI-255 exists
pi = api("GET", "/planning-items/PI-255")
print("PI-255:", pi["planning_item_title"])
```

### 0b. Find the right topic for source mapping requirements

```python
# List topics to find the correct parent for PRJ-027 / instance work
# Try the most likely candidates
for tid in ["TOP-063", "TOP-013", "TOP-079"]:
    try:
        t = api("GET", f"/topics/{tid}")
        print(f"{tid}: {t.get('topic_name') or t.get('topic_title') or t}")
    except Exception as e:
        print(f"{tid}: not found ({e})")
```

Use whichever topic is the correct home for PRJ-027 / instance mapping work. If none are right, list all topics: `api("GET", "/topics?limit=100")` and pick the correct one. Set `TOPIC_ID` to the correct identifier before proceeding.

### 0c. Create the three requirements

```python
from datetime import date
TODAY = date.today().isoformat()
TOPIC_ID = "TOP-063"  # UPDATE if the topic check above shows a different ID

REQ_SPECS = [
    {
        "requirement_title": "Source mapping foundation — vocab, schema, and repositories",
        "requirement_description": (
            "The V2 application must provide a candidate-gated source instance mapping "
            "layer governing how objects discovered during a source CRM audit relate to "
            "the canonical design. Required: (1) extended vocab for mapping decision "
            "types, statuses, staleness, and candidate confidence; (2) two new "
            "instance_membership states (candidate_pending, mapping_stale); (3) seven "
            "ORM models and migration 0079 for source_mappings, source_mapping_targets, "
            "source_mapping_joins, field_mappings, field_mapping_translations, "
            "value_mappings, mapping_candidates; (4) five access-layer repositories. "
            "No source object may influence the canonical design without an explicit "
            "human mapping decision (DEC-575)."
        ),
        "requirement_origin": "human_defined",
        "requirement_priority": "should",
        "requirement_status": "candidate",
    },
    {
        "requirement_title": "Source mapping REST API — endpoints for all mapping tables",
        "requirement_description": (
            "The V2 REST API must expose endpoints for the source mapping layer: "
            "/source-mappings (CRUD + mark_stale), /source-mapping-targets "
            "(set/add/remove), /field-mappings (CRUD + mark_stale), /value-mappings "
            "(CRUD + supersede), and /mapping-candidates (create, list, resolve, "
            "bulk-create). All endpoints follow the existing {data, meta, errors} "
            "envelope pattern and are covered by integration tests."
        ),
        "requirement_origin": "human_defined",
        "requirement_priority": "should",
        "requirement_status": "candidate",
    },
    {
        "requirement_title": "Source mapping reconciler — candidates not auto-promotion",
        "requirement_description": (
            "When a source instance audit discovers objects not matched by an existing "
            "source mapping, the reconciler must write mapping_candidate records rather "
            "than auto-promoting to canonical design objects. Instance membership for "
            "unmatched source objects must be set to candidate_pending. Existing mappings "
            "that become stale due to source or design changes must transition membership "
            "state to mapping_stale. Prior source mapping decisions must be surfaced as "
            "suggestions when generating candidates for a new source (DEC-580)."
        ),
        "requirement_origin": "human_defined",
        "requirement_priority": "should",
        "requirement_status": "candidate",
    },
]

created_reqs = []
for spec in REQ_SPECS:
    r = api("POST", "/requirements", spec)
    print(f"Created {r['requirement_identifier']}: {r['requirement_title'][:55]}")
    created_reqs.append(r["requirement_identifier"])

print("Requirements:", created_reqs)
```

### 0d. Create the approving decision

```python
dec = api("POST", "/decisions", {
    "title": "Approve source instance mapping requirements (PI-255)",
    "context": (
        "SES-230 established the source mapping model design (DEC-575..580): "
        "candidate-gated human-decision layer, fractal decision structure at "
        "entity/field/value levels, join mapping inherited by field mappings, "
        "staleness signals, rejection lifecycle chains, and per-(source instance, "
        "design) pair scoping. PI-255 implements the foundation and API/reconciler. "
        "Requirements authored as human_defined per ENG-001 provenance model."
    ),
    "decision": (
        "Approve three requirements covering: (1) source mapping vocab/schema/"
        "repositories, (2) REST API endpoints, (3) reconciler behavior change "
        "from auto-promotion to candidate-gating. All three implement PI-255."
    ),
    "rationale": (
        "The source mapping model was designed in SES-230 and governed as "
        "DEC-575..580. Human review and approval is required per ENG-001 "
        "before any code is written."
    ),
    "status": "Active",
    "decision_date": TODAY,
})
DEC_ID = dec["identifier"]
print(f"Created {DEC_ID}: {dec['title'][:55]}")
```

### 0e. Wire all governance edges

```python
# decided_in: decision -> session
api("POST", "/references", {
    "source_type": "decision", "source_id": DEC_ID,
    "target_type": "session", "target_id": "SES-230",
    "relationship": "decided_in",
})
print(f"{DEC_ID} -> SES-230 (decided_in)")

for rid in created_reqs:
    # requirement -> topic
    api("POST", "/references", {
        "source_type": "requirement", "source_id": rid,
        "target_type": "topic", "target_id": TOPIC_ID,
        "relationship": "requirement_belongs_to_topic",
    })
    # requirement -> conversation (provenance: CNV-155 is SES-230's conversation)
    api("POST", "/references", {
        "source_type": "requirement", "source_id": rid,
        "target_type": "conversation", "target_id": "CNV-155",
        "relationship": "requirement_defined_in_conversation",
    })
    # requirement_approved_by_decision edge
    api("POST", "/references", {
        "source_type": "requirement", "source_id": rid,
        "target_type": "decision", "target_id": DEC_ID,
        "relationship": "requirement_approved_by_decision",
    })
    # Activate the requirement (transition candidate -> confirmed)
    # Try activate-by-decision endpoint first; fall back to PATCH
    try:
        api("POST", f"/requirements/{rid}/activate-by-decision",
            {"decision_identifier": DEC_ID})
        print(f"{rid}: confirmed via activate-by-decision")
    except Exception:
        api("PATCH", f"/requirements/{rid}", {"requirement_status": "confirmed"})
        print(f"{rid}: confirmed via PATCH")
    # planning_item_implements_requirement: PI-255 -> requirement
    api("POST", "/references", {
        "source_type": "planning_item", "source_id": "PI-255",
        "target_type": "requirement", "target_id": rid,
        "relationship": "planning_item_implements_requirement",
    })
    print(f"PI-255 -> {rid} (planning_item_implements_requirement)")

print("\nGovernance pre-step complete.")
print(f"Requirements: {created_reqs}")
print(f"Approving decision: {DEC_ID}")
print("Proceeding to build steps...")
```

Verify all requirements show `requirement_status: confirmed` before continuing:

```python
for rid in created_reqs:
    r = api("GET", f"/requirements/{rid}")
    print(f"{rid}: {r['requirement_status']} -- {r['requirement_title'][:50]}")
```

Only proceed to Step 1 when all three show `confirmed`.

---

## Step 1 -- Extend `vocab.py`

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
# Source instance mapping model (PI-255, SES-230 -- PRJ-027). The
# candidate-gated human-decision layer that governs how objects discovered
# in a source CRM instance relate to objects in the canonical design.
# Source instances are design inputs, not design authorities. Every discovered
# object requires an explicit mapping decision before it influences the design.
# See source-mapping-design.md for the full model.
# ---------------------------------------------------------------------------

# Entity-level mapping decision types (DEC-575, DEC-576). A source entity may
# map directly to one design entity, decompose into multiple design entities,
# map referentially (different surface, same intent), or be explicitly rejected.
SOURCE_MAPPING_DECISION_TYPES: frozenset[str] = frozenset(
    {"direct", "decomposition", "referential", "rejected"}
)

# Mapping record lifecycle states (DEC-578). A mapping is unresolved until a
# human makes the decision, resolved once confirmed, stale when either the
# source or design changed, and superseded when replaced by a newer decision.
SOURCE_MAPPING_STATUSES: frozenset[str] = frozenset(
    {"unresolved", "resolved", "stale", "superseded"}
)

# Graduated staleness severity (DEC-578). Low = likely still valid (rename);
# high = translation logic may be wrong (type change, structural change).
SOURCE_MAPPING_STALE_SEVERITIES: frozenset[str] = frozenset({"low", "high"})

# Why a mapping went stale (DEC-578).
SOURCE_MAPPING_STALE_REASONS: frozenset[str] = frozenset(
    {"source_changed", "design_changed"}
)

# Field-level mapping decision types (DEC-576). Finer than entity-level:
# direct (same field, identity), referential_exact (same intent, different name),
# referential_interpreted (requires translation logic), rejected.
FIELD_MAPPING_DECISION_TYPES: frozenset[str] = frozenset(
    {"direct", "referential_exact", "referential_interpreted", "rejected"}
)

# Value-level mapping decision types (DEC-576). Applied to individual enum
# values when field_mapping.decision_type is referential_interpreted.
VALUE_MAPPING_DECISION_TYPES: frozenset[str] = frozenset(
    {"direct", "interpreted", "rejected"}
)

# Translation types for field_mapping_translation (DEC-576). value_map applies
# per-value substitution; expression applies a formula/transformation.
FIELD_MAPPING_TRANSLATION_TYPES: frozenset[str] = frozenset(
    {"value_map", "expression"}
)

# Candidate types surfaced by the reconciler (DEC-575). Entity-level candidates
# are unmatched source entities; field-level are unmatched source fields; value-
# level are unmatched enum values on an already-mapped field.
MAPPING_CANDIDATE_TYPES: frozenset[str] = frozenset({"entity", "field", "value"})

# Confidence levels for reconciler-generated mapping suggestions (DEC-580).
MAPPING_SUGGESTION_CONFIDENCES: frozenset[str] = frozenset(
    {"high", "medium", "low"}
)
```

**1c. Add `source_mapping` and related types to `ENTITY_TYPES`.**

`source_mapping`, `field_mapping`, and `mapping_candidate` participate in change_log. Add to `ENTITY_TYPES` before the closing brace:

```python
        # PI-255 source instance mapping model (PRJ-027 / SES-230). The
        # candidate-gated human-decision layer between audit discovery and the
        # canonical design. source_mapping = entity-level decision (SMG-);
        # field_mapping = field-level decision (FMP-);
        # mapping_candidate = pre-decision reconciler output (no prefix -- auto-id).
        "source_mapping",
        "field_mapping",
        "mapping_candidate",
```

`source_mapping_target`, `source_mapping_join`, `field_mapping_translation`, and `value_mapping` are child/support tables with no prefixed identifier and no `change_log` participation. Do NOT add them to `ENTITY_TYPES`.

---

## Step 2 -- Add ORM models to `models.py`

Read the full `models.py` first. Add seven model classes after `InstanceMembership`, following its exact patterns for naming, column declarations, constraint naming, and `__tablename__` / `__table_args__` style.

**Naming conventions:**
- Table names: `source_mappings`, `source_mapping_targets`, `source_mapping_joins`, `field_mappings`, `field_mapping_translations`, `value_mappings`, `mapping_candidates`
- Column prefix matches table singular
- All string columns use `Text` (not `String(n)`)
- Datetimes: `DateTime(timezone=True)`, nullable, no server default
- All seven tables get `engagement_id` (Text, nullable, same FK pattern as `InstanceMembership`)
- No prefixed identifier on `source_mapping_target`, `source_mapping_join`, `field_mapping_translation`, `value_mapping` -- use plain integer PK
- `source_mapping` gets prefix `SMG-NNN`; `field_mapping` gets `FMP-NNN`; `mapping_candidate` uses auto-increment int PK

**Model 1: `SourceMapping`** (`source_mappings`)
- `id`, `engagement_id` (FK engagements, nullable, CASCADE), `source_mapping_identifier` (UNIQUE), `instance_identifier`, `source_entity_name`, `decision_type` (CHECK SOURCE_MAPPING_DECISION_TYPES), `status` (CHECK SOURCE_MAPPING_STATUSES, default 'unresolved'), `stale_reason` (nullable, CHECK SOURCE_MAPPING_STALE_REASONS allow NULL), `stale_severity` (nullable, CHECK SOURCE_MAPPING_STALE_SEVERITIES allow NULL), `superseded_by` (nullable Text), `notes` (nullable), `resolved_at`, `created_at`, `updated_at`, `deleted_at`

**Model 2: `SourceMappingTarget`** (`source_mapping_targets`)
- `id`, `engagement_id`, `source_mapping_identifier`, `entity_identifier`
- UNIQUE on `(source_mapping_identifier, entity_identifier)`

**Model 3: `SourceMappingJoin`** (`source_mapping_joins`)
- `id`, `engagement_id`, `source_mapping_identifier` (UNIQUE), `source_field_name`, `design_entity_identifier`, `design_field_identifier`

**Model 4: `FieldMapping`** (`field_mappings`)
- `id`, `engagement_id`, `field_mapping_identifier` (UNIQUE), `source_mapping_identifier`, `source_field_name`, `decision_type` (CHECK FIELD_MAPPING_DECISION_TYPES), `status` (CHECK SOURCE_MAPPING_STATUSES, default 'unresolved'), `stale_reason` (nullable, allow NULL), `stale_severity` (nullable, allow NULL), `target_entity_identifier` (nullable), `target_field_identifier` (nullable), `superseded_by` (nullable Text), `notes` (nullable), `resolved_at`, `created_at`, `updated_at`, `deleted_at`

**Model 5: `FieldMappingTranslation`** (`field_mapping_translations`)
- `id`, `engagement_id`, `field_mapping_identifier` (UNIQUE), `translation_type` (CHECK FIELD_MAPPING_TRANSLATION_TYPES), `expression` (nullable)

**Model 6: `ValueMapping`** (`value_mappings`)
- `id`, `engagement_id`, `field_mapping_identifier`, `source_value`, `decision_type` (CHECK VALUE_MAPPING_DECISION_TYPES), `target_value` (nullable), `status` (CHECK SOURCE_MAPPING_STATUSES, default 'unresolved'), `superseded_by` (nullable Integer, self-ref FK to `value_mappings.id`), `notes` (nullable), `created_at`, `updated_at`

**Model 7: `MappingCandidate`** (`mapping_candidates`)
- `id`, `engagement_id`, `instance_identifier`, `audit_event_identifier` (nullable), `candidate_type` (CHECK MAPPING_CANDIDATE_TYPES), `source_entity_name`, `source_field_name` (nullable), `source_value` (nullable), `suggested_source_mapping_identifier` (nullable), `suggested_field_mapping_identifier` (nullable), `suggestion_confidence` (nullable, CHECK MAPPING_SUGGESTION_CONFIDENCES allow NULL), `suggestion_basis` (nullable Text), `resolved` (Integer NOT NULL default 0), `resolved_at` (nullable), `resolved_to_source_mapping_identifier` (nullable), `resolved_to_field_mapping_identifier` (nullable), `created_at`

---

## Step 3 -- Write migration `0079_pi_255_source_mapping_tables.py`

Location: `migrations/versions/0079_pi_255_source_mapping_tables.py`

Follow the pattern of `0059_pi_185_instance_membership.py`. Key points:
- `revision = "0079_pi_255_source_mapping_tables"`
- `down_revision = "0078_pi_249_release_back_half"`
- Create all seven tables via `Model.__table__.create(op.get_bind(), checkfirst=True)`
- Rebuild the `instance_memberships` state CHECK (SQLite batch mode) to add `candidate_pending` and `mapping_stale` -- check the actual constraint name in migration 0059 first
- Downgrade drops all seven tables and reverts the CHECK to the original three states

---

## Step 4 -- Write repository modules

Create five files in `src/crmbuilder_v2/access/repositories/`:

### 4a. `source_mapping.py` (prefix `SMG`)
- `_ENTITY_TYPE`, `_IDENTIFIER_PREFIX`, `_IDENTIFIER_RE`, `_PATCHABLE_FIELDS`
- `list_source_mappings(session, *, instance_identifier=None, status=None, include_deleted=False)`
- `get_source_mapping`, `next_source_mapping_identifier`
- `create_source_mapping(*, instance_identifier, source_entity_name, decision_type, notes=None, identifier=None)` -- status='unresolved', emits change_log
- `update_source_mapping` -- validates transitions: `unresolved->{resolved,stale,superseded}`, `resolved->{stale,superseded}`, `stale->{resolved,superseded}`, `superseded->{}`
- `patch_source_mapping`, `delete_source_mapping`, `restore_source_mapping`
- `mark_stale(session, identifier, *, reason, severity)` -- sets status=stale, stale_reason, stale_severity

### 4b. `source_mapping_targets.py` (no prefix, no change_log)
- `list_targets(session, *, source_mapping_identifier)`
- `add_target` (idempotent), `remove_target` (hard delete), `set_targets` (atomic replace)

### 4c. `field_mapping.py` (prefix `FMP`)
Same shape as `source_mapping.py`. Same status transition rules.
- `list_field_mappings(session, *, source_mapping_identifier=None, status=None, include_deleted=False)`
- `get_field_mapping`, `next_field_mapping_identifier`
- `create_field_mapping(*, source_mapping_identifier, source_field_name, decision_type, target_entity_identifier=None, target_field_identifier=None, notes=None, identifier=None)`
- `update_field_mapping`, `patch_field_mapping`, `delete_field_mapping`, `restore_field_mapping`, `mark_stale`

### 4d. `value_mapping.py` (integer PK, no change_log)
- `list_value_mappings(session, *, field_mapping_identifier, include_superseded=False)` -- active only by default (superseded_by IS NULL)
- `get_value_mapping(session, id_)`
- `create_value_mapping(*, field_mapping_identifier, source_value, decision_type, target_value=None, notes=None)` -- validates no active duplicate on (field_mapping_identifier, source_value)
- `update_value_mapping(session, id_, *, decision_type, target_value=None, notes=None, status=None)`
- `supersede_value_mapping(session, id_, *, replacement_id)` -- sets superseded_by

### 4e. `mapping_candidate.py` (integer PK)
- `list_candidates(session, *, instance_identifier=None, candidate_type=None, resolved=None)`
- `get_candidate(session, id_)`
- `create_candidate(*, instance_identifier, candidate_type, source_entity_name, source_field_name=None, source_value=None, audit_event_identifier=None, suggested_source_mapping_identifier=None, suggested_field_mapping_identifier=None, suggestion_confidence=None, suggestion_basis=None)`
- `resolve_candidate(session, id_, *, resolved_to_source_mapping_identifier=None, resolved_to_field_mapping_identifier=None)` -- sets resolved=True, resolved_at
- `bulk_create_candidates(session, candidates: list[dict])` -- batch insert

---

## Step 5 -- Write tests

Create `tests/test_source_mapping_foundation.py`.

**Vocab:** INSTANCE_MEMBERSHIP_STATES contains 'candidate_pending' and 'mapping_stale'; all new frozensets non-empty.

**Migration:** 0079 creates all seven tables; downgrade/upgrade round-trip succeeds.

**source_mapping repo:** create (status='unresolved'), list by instance_identifier, patch notes, mark_stale, soft-delete/restore, invalid decision_type raises UnprocessableError, invalid status transition raises StatusTransitionError.

**source_mapping_targets repo:** add_target idempotent, set_targets atomic, remove_target removes one.

**field_mapping repo:** create, list by source_mapping_identifier, mark_stale, soft-delete.

**value_mapping repo:** create, list (active only), supersede round-trip, duplicate active raises conflict.

**mapping_candidate repo:** create entity/field candidates, resolve_candidate, bulk_create_candidates.

---

## Step 6 -- Run tests and verify

```bash
uv run pytest tests/test_source_mapping_foundation.py -v
uv run pytest tests/ -x -q
uv run alembic -c migrations/alembic.ini heads
```

---

## Step 7 -- Commit

```bash
git add -A
git commit -m "v2: PI-255 slice 1 -- source mapping foundation (governance pre-step, vocab, models, migration 0079, repositories)"
```

Do NOT push. Doug pushes.

---

## Done

Reply with:
- Governance pre-step result (requirements created, DEC identifier, all confirmed)
- Test results summary (passed/failed counts)
- Migration head after upgrade
- Any deviations from this spec and why
- Confirmation that the full suite is green
