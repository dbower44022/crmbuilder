# CRMBuilder v2 — UI v0.4 Implementation Plan

**Version:** 0.1
**Last Updated:** 05-14-26 14:00
**Status:** Approved
**Companion PRD:** `ui-PRD-v0.4.md`
**Predecessor plan:** `ui-v0.3-implementation-plan.md` (shipped per SES-009)
**Executing prompt series:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-{A..F}-*.md`

---

## Change Log

**Version 0.1 (05-12-26 10:30):** Initial draft. Six-slice breakdown for v0.4 build: foundation, four entity panels (Domains, Entities, Processes, CRM Candidates), closeout. Migration ordering enforced through slice dependency chain.

**Version 0.1 (05-14-26 14:00):** Status transitions from "Draft — pending approval" to "Approved" alongside PRD v0.4 approval. Section 8 (Closeout Discipline) renumbered to reflect SES-016 → SES-017 collision-resolution (catalog ingestion build consumed SES-016 on 05-14-26) and the corresponding DEC renumbering from DEC-065 → DEC-068 through DEC-073, plus a new DEC-074 for the approval and a new SES-018 for the reconciliation conversation. Three new planning items (PI-013, PI-014, PI-015) added to the closeout records list per the PRD's matching addition.

---

## 1. Overview

This plan implements the v0.4 desktop UI specified in `ui-PRD-v0.4.md`. v0.4 is decomposed into six independently testable slices, each delivered as its own Claude Code prompt. Each prompt produces a working state of the application that exercises a coherent subset of the PRD's acceptance criteria.

Slice boundaries follow the hybrid pattern established by v0.3 — foundation + feature slices + dedicated closeout — adapted for v0.4's four-entity scope. Slice A delivers the foundation (vocabulary additions, CHECK-constraint migration, Methodology sidebar group container, eight retrofitted `GET /<entity>/next-identifier` helpers, spec guide section 6 amendment). Slices B through E each deliver one entity panel end-to-end in workstream order: Domain, Entity, Process, CRM Candidate. Slice F is mechanical closeout (version bump, README, regression pass, smoke verification).

After all six prompts execute cleanly, every acceptance criterion in PRD section 6 is satisfied. The application becomes incrementally usable: after Slice A the foundation infrastructure works but no methodology panels exist; after each of B through E, that entity's panel becomes fully operable; after Slice F the release is shippable.

```
Slice A (foundation)
    │
    ├──> Slice B (Domains panel)
    │       │
    │       ├──> Slice C (Entities panel — depends on Slice B for live domains to affiliate against)
    │       │       │
    │       │       └──> Slice D (Processes panel — depends on Slice B for the domain FK combo backing)
    │       │
    │       └──> Slice E (CRM Candidates panel — independent of B, C, D's content but ships
    │                     within the same Methodology group container introduced in Slice A)
    │
    └──> Slice F (closeout — depends on B, C, D, E all complete)
```

Slices B and E are technically independent of each other and could run in either order. The plan executes them in workstream order (B → C → D → E) for consistency with the schema-design workstream's ordering and to keep the build conversation's reading order matched to the artifacts.

---

## 2. Implementation Choices

### 2.1 Language and runtime

Unchanged from v0.1–v0.3. Python 3.12+, matching `pyproject.toml`'s `requires-python` pin.

### 2.2 Desktop framework — PySide6

Unchanged.

### 2.3 HTTP client — httpx (sync mode)

Unchanged.

### 2.4 Subprocess management — QProcess

Unchanged.

### 2.5 File watching — QFileSystemWatcher

Unchanged from v0.3. Slice A extends the refresh-service entity-type map to cover the four new methodology entity types' snapshot files (`domains.json`, `entities.json`, `processes.json`, `crm_candidates.json` under `db-export/`).

### 2.6 Test framework — pytest + pytest-qt

Unchanged. `qtbot` and `qapp` fixtures continue.

### 2.7 Logging — Python's standard `logging` module

Unchanged. RotatingFileHandler at `~/.crmbuilder-v2/ui.log`.

### 2.8 Threading model

Unchanged. Worker/object pattern; `run_in_thread` helper.

### 2.9 Error handling

Unchanged. Typed exceptions in the storage client; inline-on-field for validation errors with `field`; modal `ErrorDialog` for everything else. The new error envelopes specific to v0.4 (`invalid_status_transition`, `invalid_classification_transition`, `invalid_domain_reference`, `selected_candidate_already_exists`) follow the existing v2 4xx convention.

### 2.10 Existing dialog framework — `EntityCrudDialog`

v0.2's `EntityCrudDialog` and v0.3's extensions remain the base. Each of the four new entity panels uses `EntityCrudDialog` for create and edit dialogs and `EntityCrudDeleteDialog` for delete dialogs. No further extensions to the dialog framework are needed in v0.4; the new entity types map cleanly onto the v0.3 field-schema model.

### 2.11 Existing reference-create dialog — `ReferenceCreateDialog`

v0.3's cascading-vocab `ReferenceCreateDialog` (per DEC-033) is reused without modification for attaching references to v0.4's new entity types. The dialog reads `RELATIONSHIP_RULES` at dialog-open time; Slice A's `vocab.py` extensions cause the dialog to automatically support the new pairs and kinds.

### 2.12 New for v0.4 — methodology entity panel pattern

Each of the four new panels follows the same template, established by v0.3's pattern for governance entity panels and unchanged at the base level:

- Subclass `ListDetailPanel` (per DEC-035).
- Override `_create_master_widget` returning a configured `QTableView` (matches v0.3 default).
- Override `_build_context_menu` returning a menu with the standard four actions: New / Edit / Delete / Restore (Restore appears on soft-deleted rows when `?include_deleted=true` is active).
- Construct detail pane with `ReferencesSection` widget for references rendering.
- Use `EntityCrudDialog` and `EntityCrudDeleteDialog` for CRUD dialogs.

The four panels differ only in their entity-specific specifics — field set, status-vs-classification field, FK combo if applicable, master-pane column 3 label, validation error envelope strings. No new base-class additions to the panel framework are required.

### 2.13 New for v0.4 — vocab.py rule additions

`_kinds_for_pair` gains two source-target rules in slice A:

```python
def _kinds_for_pair(source_type: str, target_type: str) -> frozenset[str]:
    kinds = {"is_about", "references"}
    if target_type == "session":
        kinds.add("decided_in")
    if source_type == target_type:
        kinds.add("supersedes")
    if source_type == "risk":
        kinds.add("affects")
        kinds.add("blocks")
    if source_type == "planning_item":
        kinds.add("blocks")
    if source_type in ("charter", "status"):
        kinds.add("covers")
    # v0.4 additions:
    if source_type == "entity" and target_type == "domain":
        kinds.add("entity_scopes_to_domain")
    if source_type == "process" and target_type == "process":
        kinds.add("process_hands_off_to_process")
    return frozenset(kinds)
```

`ENTITY_TYPES` gains four new strings (`domain`, `entity`, `process`, `crm_candidate`). `REFERENCE_RELATIONSHIPS` gains two (`entity_scopes_to_domain`, `process_hands_off_to_process`). `RELATIONSHIP_RULES` recomputes at module load from the expanded sets.

### 2.14 New for v0.4 — `GET /<entity>/next-identifier` helper retrofit

Slice A adds the helper endpoint pattern to the eight existing prefixed-identifier governance entity types per DEC-043. The endpoint queries the access layer for the next available identifier (using whatever per-entity-type method the access layer already exposes for the implicit-during-POST path), wraps the result in `{"next": "<PREFIX>-<NNN>"}`, and returns 200.

Charter and status helpers follow their versioned-identifier semantics: rather than incrementing a numeric suffix on a `CHR-NNN` or `STA-NNN` prefix, they return the next version number per the access-layer's existing versioned-replace pattern.

Each helper is roughly ten lines of router code plus an access-layer wrapper if not already present.

---

## 3. Directory and File Layout

The UI lives under `crmbuilder-v2/src/crmbuilder_v2/ui/`. The storage layer lives under `crmbuilder-v2/src/crmbuilder_v2/access/` and `crmbuilder-v2/src/crmbuilder_v2/api/`. v0.4 adds four panels, four dialog modules, four access-layer repositories, four API router modules, and one new sidebar-group container. Existing modules are extended for vocab additions and helper-endpoint retrofit.

```
crmbuilder-v2/
└── src/crmbuilder_v2/
    ├── access/
    │   ├── vocab.py                              # MODIFIED (slice A) — ENTITY_TYPES, REFERENCE_RELATIONSHIPS, _kinds_for_pair
    │   ├── domain.py                             # NEW (slice B) — domain repository
    │   ├── entity.py                             # NEW (slice C) — entity repository
    │   ├── process.py                            # NEW (slice D) — process repository
    │   ├── crm_candidate.py                      # NEW (slice E) — crm_candidate repository
    │   └── repositories/                          # MODIFIED (slice A) — next_identifier methods added to eight existing
    │                                               (decision, session, risk, planning_item, topic, reference, charter, status)
    ├── api/
    │   └── routers/
    │       ├── decisions.py                       # MODIFIED (slice A) — GET /decisions/next-identifier
    │       ├── sessions.py                        # MODIFIED (slice A) — GET /sessions/next-identifier
    │       ├── risks.py                           # MODIFIED (slice A) — GET /risks/next-identifier
    │       ├── planning_items.py                  # MODIFIED (slice A) — GET /planning_items/next-identifier
    │       ├── topics.py                          # MODIFIED (slice A) — GET /topics/next-identifier
    │       ├── references.py                      # MODIFIED (slice A) — GET /references/next-identifier
    │       ├── charter.py                         # MODIFIED (slice A) — GET /charter/next-identifier
    │       ├── status.py                          # MODIFIED (slice A) — GET /status/next-identifier
    │       ├── domains.py                         # NEW (slice B) — eight standard endpoints
    │       ├── entities.py                        # NEW (slice C) — eight standard endpoints
    │       ├── processes.py                       # NEW (slice D) — eight standard endpoints + domain-FK validation
    │       └── crm_candidates.py                  # NEW (slice E) — eight standard endpoints + singleton-selected enforcement
    └── ui/
        ├── app.py                                 # MODIFIED (slice A) — Methodology sidebar group container introduced
        ├── client.py                              # MODIFIED across slices — methods added per slice for new entity types and helpers
        ├── refresh.py                             # MODIFIED (slice A) — file-watch map extended for the four new entity-type files
        ├── panels/
        │   ├── (existing panels)                  # UNCHANGED
        │   ├── domains.py                         # NEW (slice B)
        │   ├── entities.py                        # NEW (slice C)
        │   ├── processes.py                       # NEW (slice D)
        │   └── crm_candidates.py                  # NEW (slice E)
        └── dialogs/
            ├── (existing dialogs)                 # UNCHANGED
            ├── domain_crud.py                     # NEW (slice B) — create/edit/delete for Domains
            ├── entity_crud.py                     # NEW (slice C) — create/edit/delete for Entities
            ├── process_crud.py                    # NEW (slice D) — create/edit/delete for Processes (with domain FK combo)
            └── crm_candidate_crud.py              # NEW (slice E) — create/edit/delete for CRM Candidates (with delete-dialog clarifying note)

crmbuilder-v2/migrations/
├── (existing revisions)                          # UNCHANGED
├── 0NNN_v0_4_foundation_refs_check_extensions.py # NEW (slice A) — extends three refs CHECK constraints
├── 0NNN_v0_4_create_domains_table.py             # NEW (slice B)
├── 0NNN_v0_4_create_entities_table.py            # NEW (slice C)
├── 0NNN_v0_4_create_processes_table.py           # NEW (slice D) — includes process_domain_identifier FK column
└── 0NNN_v0_4_create_crm_candidates_table.py      # NEW (slice E)

tests/crmbuilder_v2/
├── access/
│   ├── test_vocab_v0_4.py                        # NEW (slice A) — ENTITY_TYPES, REFERENCE_RELATIONSHIPS, _kinds_for_pair, RELATIONSHIP_RULES
│   ├── test_domain.py                            # NEW (slice B)
│   ├── test_entity.py                            # NEW (slice C)
│   ├── test_process.py                           # NEW (slice D)
│   └── test_crm_candidate.py                     # NEW (slice E)
├── api/
│   ├── test_next_identifier_retrofit.py          # NEW (slice A) — eight retrofitted endpoints
│   ├── test_domains_api.py                       # NEW (slice B)
│   ├── test_entities_api.py                      # NEW (slice C)
│   ├── test_processes_api.py                     # NEW (slice D)
│   └── test_crm_candidates_api.py                # NEW (slice E)
└── ui/
    ├── test_domains_panel.py                     # NEW (slice B)
    ├── test_entities_panel.py                    # NEW (slice C)
    ├── test_processes_panel.py                   # NEW (slice D)
    └── test_crm_candidates_panel.py              # NEW (slice E)
```

Spec guide section 6 amendment lands at `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` in slice A (one surgical edit; no new file).

README release note lands at `crmbuilder-v2/README.md` in slice F.

Version bump lands at `crmbuilder-v2/src/crmbuilder_v2/__init__.py` in slice F.

---

## 4. Build Sequence

Each slice lands as one commit (or a small handful) prefixed `v2:` per the v2 convention and corresponds to one execution prompt. PRD acceptance criteria from section 6 are cross-referenced as `AC#N`.

### Step A — Foundation

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.4-A-foundation.md`

**Deliverables:**

- `access/vocab.py` extensions:
  - `ENTITY_TYPES` adds `domain`, `entity`, `process`, `crm_candidate`.
  - `REFERENCE_RELATIONSHIPS` adds `entity_scopes_to_domain`, `process_hands_off_to_process`.
  - `_kinds_for_pair` adds two new rules per section 2.13 above.
  - `RELATIONSHIP_RULES` auto-recomputes at module load with the expanded sets.
- Alembic migration `0NNN_v0_4_foundation_refs_check_extensions.py`:
  - Extends `refs.source_type` CHECK to admit `domain`, `entity`, `process`, `crm_candidate`.
  - Extends `refs.target_type` CHECK with the same four values.
  - Extends `refs.relationship_kind` CHECK to admit `entity_scopes_to_domain`, `process_hands_off_to_process`.
  - Forward and backward reversible.
- `ui/app.py` modification: new Methodology sidebar group container rendered below the existing Governance group. Initially empty; entries populate in subsequent slices.
- `ui/refresh.py` modification: file-watch map extended to cover `domains.json`, `entities.json`, `processes.json`, `crm_candidates.json` in `db-export/`.
- `GET /<entity>/next-identifier` retrofit to the eight existing governance entity types:
  - `api/routers/decisions.py`, `sessions.py`, `risks.py`, `planning_items.py`, `topics.py`, `references.py`, `charter.py`, `status.py` each gain one endpoint.
  - Access-layer wrappers added to corresponding repository methods where not already present.
  - Charter and status use versioned-identifier semantics.
- Spec guide section 6 amendment committed to `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` per the approved diff: scope-note paragraph at section head, three updated table rows with "(methodology only)" labels, closing-paragraph addendum acknowledging the three documented cross-spec deviations.
- Tests: `tests/crmbuilder_v2/access/test_vocab_v0_4.py` covering ENTITY_TYPES contents, REFERENCE_RELATIONSHIPS contents, `_kinds_for_pair` for `(entity, domain)` and `(process, process)`, and `RELATIONSHIP_RULES` correctness. `tests/crmbuilder_v2/api/test_next_identifier_retrofit.py` covering all eight retrofitted endpoints' happy path and concurrent-fetch behavior.

**Acceptance gates:**

- AC A1, A2, A3 (vocab additions and `RELATIONSHIP_RULES` correctness).
- AC A4 (Alembic migration forward + backward).
- AC A5 (eight retrofitted next-identifier endpoints).
- AC A6 (Methodology sidebar group renders below Governance, initially empty).
- AC A7 (spec guide amendment committed).
- AC A8 (v0.3 test suite green).
- Foundation work is internally consistent: the cascading-vocab dialog (`ReferenceCreateDialog`) opens correctly with the new entity types available in source/target combos (smoke check; full coverage in slice C).

**Out of slice:** any entity-table migration (slices B–E); any entity panel (slices B–E); any per-entity dialogs (slices B–E); the README release note (slice F); the version bump (slice F).

**Size note:** if the slice prompt exceeds ~800 lines or shows Claude Code degradation during execution, the slice splits into A1 (vocab additions + Alembic + sidebar group + spec guide amendment) and A2 (eight-endpoint helper retrofit), making v0.4 a seven-slice release. The split decision is made when the slice-A prompt is drafted, not pre-committed in this plan.

---

### Step B — Domains panel

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.4-B-domains-panel.md`

**Deliverables:**

- Alembic migration `0NNN_v0_4_create_domains_table.py`: creates the `domains` table per `domain.md` section 3.2 — nine columns (`domain_identifier`, `domain_name`, `domain_status`, `domain_purpose`, `domain_description`, `domain_notes`, `domain_created_at`, `domain_updated_at`, `domain_deleted_at`) with correct types, the `^DOM-\d{3}$` identifier format constraint, the case-insensitive `domain_name` uniqueness rule, and the three-value `domain_status` enum constraint. Forward and backward reversible.
- `access/domain.py`: repository with `list_domains`, `get_domain`, `create_domain`, `update_domain`, `patch_domain`, `delete_domain`, `restore_domain`, `next_domain_identifier`. Validation per spec section 3.5: identifier format, name uniqueness (case-insensitive), status enum, status-transition validation per the 3.4.1 propose-verify gate, soft-delete semantics, identifier auto-assignment.
- `api/routers/domains.py`: eight standard endpoints per spec section 3.5. Server-side status-transition validation returns `{"error": "invalid_status_transition", "from": ..., "to": ...}` on disallowed transitions.
- `ui/panels/domains.py`: `ListDetailPanel` subclass registered at Methodology sidebar position #1. Master pane columns Identifier / Name / Status / Updated, sort by Identifier ascending. Right-click context menu: New / Edit / Delete / Restore. Detail pane: identifier (read-only), name, purpose, description, notes (collapsed under "Internal notes"), status combo, `ReferencesSection` widget.
- `ui/dialogs/domain_crud.py`: `EntityCrudDialog` and `EntityCrudDeleteDialog` subclasses per spec section 3.6.4–3.6.6. Status defaults to `candidate` in create dialog. Edge-text confirmation in delete dialog.
- `ui/client.py` extensions: eight new methods for Domains.
- Tests: `tests/crmbuilder_v2/access/test_domain.py`, `tests/crmbuilder_v2/api/test_domains_api.py`, `tests/crmbuilder_v2/ui/test_domains_panel.py`. Cover all 14 acceptance criteria from `domain.md` section 3.7.

**Acceptance gates:**

- All 14 acceptance criteria from `domain.md` section 3.7 pass.
- Slice A's tests continue to pass.
- v0.3 regression test suite remains green.

**Out of slice:** entity, process, or crm_candidate work (slices C, D, E); inbound `entity_scopes_to_domain` references on domain detail pane (those land naturally in slice C).

---

### Step C — Entities panel

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.4-C-entities-panel.md`

**Deliverables:**

- Alembic migration `0NNN_v0_4_create_entities_table.py`: creates the `entities` table per `entity.md` section 3.2 — eight columns with constraints (identifier format `^ENT-\d{3}$`, name case-insensitive uniqueness, status enum). Forward and backward reversible.
- `access/entity.py`: repository with the eight standard methods. Validation per spec section 3.5: identifier format, name uniqueness, status enum, status-transition validation per the 3.4.1 propose-verify gate (mirrors domain's pattern), soft-delete semantics including non-cascading `entity_scopes_to_domain` references per spec 3.4.6. Status independence from affiliation status per spec 3.4.3.
- `api/routers/entities.py`: eight standard endpoints per spec section 3.5. Decomposed reference handling: no inline-affiliation convenience endpoints; affiliations attach via the existing `POST /references` route.
- `ui/panels/entities.py`: `ListDetailPanel` subclass registered at Methodology sidebar position #2. Master pane columns Identifier / Name / Status / Updated (no Domains column in v0.4 per spec 3.6.2 and DEC-072's structural parallel). Right-click context menu standard. Detail pane: identifier (read-only), name, description, notes (collapsed), status combo, `ReferencesSection` widget rendering outgoing `entity_scopes_to_domain` affiliations plus any inbound kinds (none in v0.4; widget is present for v0.5+ future kinds).
- `ui/dialogs/entity_crud.py`: `EntityCrudDialog` and `EntityCrudDeleteDialog` subclasses. Per DEC-070 create-then-attach flow: no domain multi-select in the New dialog; affiliations attach from the detail pane after creation via the existing v0.3 `ReferenceCreateDialog`.
- `ui/client.py` extensions: eight new methods for Entities.
- Tests: `tests/crmbuilder_v2/access/test_entity.py`, `tests/crmbuilder_v2/api/test_entities_api.py`, `tests/crmbuilder_v2/ui/test_entities_panel.py`. Cover all 16 acceptance criteria from `entity.md` section 3.7. Key slice-specific tests:
  - Acceptance #14: `entity_scopes_to_domain` registered, `_kinds_for_pair((entity, domain))` correct, POST `/references` with `(entity, domain)` and an unsupported kind returns 422, direct DB insert into `refs` with an unknown kind rejected.
  - Acceptance #15: bidirectional round-trip — POST `/references` creates the row; entity detail pane shows under outgoing; domain detail pane (built in slice B with an empty inbound) shows under inbound; soft-deleting either side leaves the reference in place.

**Acceptance gates:**

- All 16 acceptance criteria from `entity.md` section 3.7 pass.
- Slice A and B tests continue to pass.

**Out of slice:** process or crm_candidate work (slices D, E); inbound `process_touches_entity` references on entity detail pane (deferred to v0.5+ per PI-005); master-pane Domains column (deferred per PI-009).

---

### Step D — Processes panel

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.4-D-processes-panel.md`

**Deliverables:**

- Alembic migration `0NNN_v0_4_create_processes_table.py`: creates the `processes` table per `process.md` section 3.2 — ten columns including the `process_domain_identifier` FK column with format constraint `^DOM-\d{3}$`, engagement-global case-insensitive `process_name` uniqueness, four-value `process_classification` enum. Forward and backward reversible.
- `access/process.py`: repository with the eight standard methods. Validation per spec sections 3.5.3, 3.5.4: identifier format, name uniqueness (engagement-global, case-insensitive), classification enum, classification-transition validation per spec 3.4.2 (one-way out of `unclassified`; free movement among the three classified values), domain-FK existence validation against live `domain` records, soft-delete semantics including non-cascading handoff references.
- `api/routers/processes.py`: eight standard endpoints per spec section 3.5. Classification-transition errors return `{"error": "invalid_classification_transition", "from": ..., "to": ...}`. Domain-FK errors return `{"error": "invalid_domain_reference", "domain_identifier": ...}`. Decomposed handoff handling: no inline-handoff convenience endpoints.
- `ui/panels/processes.py`: `ListDetailPanel` subclass registered at Methodology sidebar position #3. Master pane columns Identifier / Name / Classification / Updated (no Domain column in v0.4). Detail pane: identifier (read-only), name, domain combo backed by `GET /domains` listing live records only, purpose, classification combo with the four enum values, classification-rationale with dynamic placeholder per classification, notes (collapsed), `ReferencesSection` widget with separate "Hands off to" and "Receives from" sub-sections rendering `process_hands_off_to_process` edges in each direction.
- `ui/dialogs/process_crud.py`: `EntityCrudDialog` and `EntityCrudDeleteDialog` subclasses. Per DEC-070 create-then-attach flow for handoffs; domain FK combo is a required scalar field IN the create dialog (record cannot be submitted without it). Default selection follows spec 3.6.4 (first live domain alphabetically, or per-session memory if implemented per Open Question 3 of the PRD).
- `ui/client.py` extensions: eight new methods for Processes.
- Tests: standard set covering all 15 acceptance criteria from `process.md` section 3.7. Key slice-specific tests:
  - Acceptance #4: classification enum + transition validation including the one-way-out-of-unclassified rule.
  - Acceptance #5: domain-FK validation rejecting non-existent or soft-deleted domain references.
  - Acceptance #14: `process_hands_off_to_process` registered, `_kinds_for_pair((process, process))` correct, bidirectional round-trip on the detail pane in both "Hands off to" and "Receives from" sub-sections.

**Acceptance gates:**

- All 15 acceptance criteria from `process.md` section 3.7 pass.
- Slice A, B, C tests continue to pass.

**Out of slice:** crm_candidate work (slice E); process-to-entity touches (deferred to v0.5+ per PI-005); sub-process hierarchy (PI-005).

---

### Step E — CRM Candidates panel

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.4-E-crm-candidates-panel.md`

**Deliverables:**

- Alembic migration `0NNN_v0_4_create_crm_candidates_table.py`: creates the `crm_candidates` table per `crm_candidate.md` section 3.2 — eight columns with constraints (identifier format `^CRM-\d{3}$`, name case-insensitive uniqueness, four-value `crm_candidate_status` enum). Forward and backward reversible.
- `access/crm_candidate.py`: repository with the eight standard methods. Validation per spec sections 3.5.3, 3.5.4: identifier format, name uniqueness, status enum, status-transition validation per spec 3.4.1 (no successors from terminal states), singleton-`selected` enforcement on POST, PATCH/PUT, and POST `/restore` per spec 3.5.4.
- `api/routers/crm_candidates.py`: eight standard endpoints per spec section 3.5. Status-transition errors return `{"error": "invalid_status_transition", "from": ..., "to": ...}`. Singleton-`selected` violations return `{"error": "selected_candidate_already_exists", "existing": "<CRM-NNN>"}`.
- `ui/panels/crm_candidates.py`: `ListDetailPanel` subclass registered at Methodology sidebar position #4. Master pane columns Identifier / Name / Status / Updated, default sort by Identifier ascending per DEC-072. Detail pane: identifier (read-only), name, fit-reason, notes (collapsed), status combo (restricted to valid successors of current status), `ReferencesSection` widget rendering inbound governance-entity citations only.
- `ui/dialogs/crm_candidate_crud.py`: `EntityCrudDialog` and `EntityCrudDeleteDialog` subclasses. Status combo offers all four enum values in create dialog (subject to singleton-`selected` check). Delete dialog includes the clarifying note distinguishing soft-delete-for-authoring-error from transition-to-removed per PRD section 4.6 (wording revisable during slice execution per PRD Open Question 2).
- `ui/client.py` extensions: eight new methods for CRM Candidates.
- Tests: standard set covering all 12 acceptance criteria from `crm_candidate.md` section 3.7. Key slice-specific tests:
  - Acceptance #4: status enum + no-successors-from-terminal rule.
  - Acceptance #5: singleton-`selected` constraint on all three operations including the soft-deleted-exclusion behavior.
  - Acceptance #8: soft-delete and restore round-trip including the singleton-blocked-restore case.
  - Acceptance #9: `crm_candidate` in `ENTITY_TYPES` (verifies slice A's work) and cascading vocab dialog correctly admits universal kinds for `(decision, crm_candidate)` and `(session, crm_candidate)`.
  - Acceptance #12: the full Phase 5 lifecycle smoke — 3 active records, one transitioned to removed, one to selected, one to declined, double-selected attempt blocked.

**Acceptance gates:**

- All 12 acceptance criteria from `crm_candidate.md` section 3.7 pass.
- Slice A, B, C, D tests continue to pass.

**Out of slice:** structured metadata fields (deferred to v0.5+ per PI-012); master-pane status-then-identifier sort (Option B reserved as v0.5+ candidate per DEC-072).

---

### Step F — Closeout

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.4-F-closeout.md`

**Deliverables:**

- `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` set to `"0.4.0"`.
- README at `crmbuilder-v2/README.md` extended with a v0.4 release-note entry matching v0.3's format: one-paragraph summary plus a bullet list of release highlights.
- Final regression test pass: `uv run pytest tests/crmbuilder_v2/ -v` returns green across the full suite (v0.3 tests + all new v0.4 tests from slices A–E).
- Final integration smoke: open the desktop app, confirm Methodology sidebar group renders with all four entries in workstream order, open each panel, confirm master + detail render, confirm About dialog shows v0.4.0.

**Acceptance gates:**

- AC F1, F2, F3, F4, F5 per PRD section 6.
- Cumulative acceptance — all foundation criteria (A1–A8), all per-entity criteria (14 + 16 + 15 + 12 = 57), and all closeout criteria (F1–F5) pass.

**Out of slice:** status-entity versioned-replace (authored through the desktop UI by the operator after slice F lands, not in Claude Code); session records for any of the build-execution conversations (authored through the desktop New Session dialog at conversation close per DEC-029); PI-006 or PI-008 work (deferred to v0.5+).

---

## 5. Migration Ordering

Six Alembic migrations land across the six slices, one per slice, each scoped to its slice's deliverables:

| Slice | Migration | Purpose |
|-------|-----------|---------|
| A | `0NNN_v0_4_foundation_refs_check_extensions.py` | Extends `refs.source_type`, `refs.target_type`, `refs.relationship_kind` CHECK constraints atomically |
| B | `0NNN_v0_4_create_domains_table.py` | Creates `domains` table with all constraints |
| C | `0NNN_v0_4_create_entities_table.py` | Creates `entities` table with all constraints |
| D | `0NNN_v0_4_create_processes_table.py` | Creates `processes` table including `process_domain_identifier` FK column |
| E | `0NNN_v0_4_create_crm_candidates_table.py` | Creates `crm_candidates` table |
| F | (none) | Closeout has no schema change |

Forward-and-backward reversibility is required for each migration. The CHECK-constraint extensions in slice A must precede any reference write involving the new entity types or new vocab kinds (which means any entity-panel slice would otherwise fail at `POST /references`); the per-entity-table migrations must precede their respective panel work. The ordering is enforced by the slice dependency chain: foundation must complete before any feature slice runs.

---

## 6. Test Target

`uv run pytest tests/crmbuilder_v2/ -v` continues as the test target across all six slices. Each slice's acceptance gate includes the requirement that the prior slices' tests continue to pass — every slice is acceptance-gated on the cumulative test suite.

Test counts per slice (estimates):

- Slice A: ~25-35 new tests (vocab, foundation Alembic, eight retrofitted helpers)
- Slice B: ~30-40 new tests (domain panel end-to-end + 14 acceptance criteria)
- Slice C: ~35-45 new tests (entity panel + bidirectional reference tests + 16 acceptance criteria)
- Slice D: ~35-45 new tests (process panel + FK validation + handoff round-trip + 15 acceptance criteria)
- Slice E: ~30-40 new tests (crm_candidate panel + singleton enforcement + Phase 5 lifecycle smoke + 12 acceptance criteria)
- Slice F: ~0 new tests; full regression pass

Estimated cumulative new tests for v0.4: ~155-205, on top of v0.3's existing suite. The numbers are rough; actual counts depend on test granularity choices made during slice execution.

---

## 7. Version Source

Per the CLAUDE.md v2 version-source convention (line 50), `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` is the single source of the version string. The About dialog reads via `importlib.metadata` with `__version__` as fallback.

Slice F sets `__version__` to `"0.4.0"`. No other file carries the version.

---

## 8. Closeout Discipline

After Slice F passes, the operator (Doug) writes:

- The session record for the v0.4-build-planning conversation (SES-017) through the v0.3 desktop New Session dialog per DEC-029. The kickoff prompt is captured verbatim in `topics_covered`; the conversation summary follows the seed prompt. **Renumbering note:** the draft anticipated SES-016 for this record; SES-016 was consumed by the catalog ingestion build executed 05-14-26, so this record claims SES-017 instead.
- The session record for the 05-14-26 reconciliation/approval conversation (SES-018) through the same dialog. Same convention.
- The status-entity versioned-replace update from "v0.3 complete" to "v0.4 complete" through the v0.3 desktop versioned-replace dialog.
- Each session record for any Claude Code execution conversation that contributed to v0.4 build, written at the close of that conversation through the desktop dialog.
- The seven DEC-NNN records (DEC-068 through DEC-074) authored via direct API per the PRD's section 11. **Renumbering note:** the draft anticipated DEC-065 through DEC-070; renumbered to DEC-068 through DEC-073 (the original six v0.4-build-planning decisions) plus DEC-074 (the 05-14-26 approval decision).
- Three new planning items (PI-013 Cross-Domain Service representation; PI-014 Catalog FK integration for methodology entities; PI-015 Methodology entity renderers) authored via direct API per the PRD's section 11.

None of the above are produced inside Claude Code slices; all are operator-authored after the slice work completes.

---

*End of document.*
