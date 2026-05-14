# CRMBuilder v2 — User Interface PRD

**Version:** 0.4
**Last Updated:** 05-14-26 14:00
**Status:** Approved
**Predecessor:** `ui-PRD-v0.3.md` (shipped per SES-009)

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.4 | 05-12-26 | Fourth iteration of the v2 desktop UI. Ships four new methodology-entity panels (Domains, Entities, Processes, CRM Candidates) under a new Methodology sidebar group, completing the storage and UI surface needed for v2 to host Phase 1 methodology content for the upcoming CBM redo. Foundation infrastructure introduces the four entity types into `ENTITY_TYPES`, two new relationship kinds (`entity_scopes_to_domain`, `process_hands_off_to_process`) into `REFERENCE_RELATIONSHIPS`, and the corresponding `refs` CHECK-constraint extensions. The SES-010 identifier-asymmetry friction is resolved by retrofitting `GET /<entity>/next-identifier` helper endpoints to the eight existing prefixed-identifier governance entity types per DEC-043; the four new methodology entity types ship their helpers from the start. The methodology-entity-schema-spec guide section 6 is amended to capture the parent-prefix field-naming and source-first relationship-kind-naming conventions established by SES-012 and applied across SES-013/014/015. Captures six architectural decisions for recording in the v2 database after PRD approval (numbering settled at approval — see 05-14-26 entry). |
| 0.4 | 05-14-26 | Approval pass after reconciliation conversation. Status transitions from "Draft — pending approval" to "Approved." Anticipated SES-016 and DEC-065 through DEC-070 numbering renumbered to SES-017 and DEC-068 through DEC-073 because the catalog ingestion build (executed 05-14-26) consumed SES-016 and DEC-065/066/067 during the gap between v0.4-build-planning conversation and approval. Three new planning items added to Section 2 Out of Scope (PI-013 Cross-Domain Service representation; PI-014 Catalog FK integration for methodology entities; PI-015 Methodology entity renderers) — surfaced by the reconciliation conversation as previously-untracked v0.5+ work. No content changes to schema specs or slice deliverables; v0.4 build prompts unblocked. |

---

## 1. Overview

### Purpose

This document specifies the requirements for CRMBuilder v2 user interface (UI) v0.4. v0.3 shipped References full CRUD, Sessions create-only, the `ListDetailPanel` factory refactor, and the uniform right-click context-menu principle. With v0.3 in hand, every governance entity in v2 can be authored and connected entirely through the desktop application; the operational gap is closed for governance content.

v0.4 closes the corresponding gap for **methodology content**. The CBM-redo engagement, queued as the v0.4 adoption pilot, uses the evolved methodology (research/not-adopted at `PRDs/process/research/evolved-methodology/`) and depends on v2 as its system of record for both governance and methodology content. v0.3 has CRUD for governance entities only; v0.4 introduces the four methodology entity types that evolved-methodology Phase 1 produces — Domain Inventory, surfaced entity names, Prioritized Backbone, Initial CRM Candidate Set — so the redo can run on v2 without falling back to Word documents or a parallel authoring system. v0.4 is the build specification handed to Claude Code, which executes it through a six-prompt slice series.

### Background

UI v0.3 shipped on 05-10-26 (SES-009). The original v0.4 kickoff at `ui-v0.4-planning-prompt.md` framed v0.4 as deliberately open across four candidate buckets and explicitly suggested waiting for some weeks of real v0.3 use before opening planning. The planning conversation that opened against that kickoff (SES-011) redirected v0.4 entirely toward enabling CBM redo to use v2 as its system of record for methodology content — a redirect captured as DEC-038. The original kickoff is superseded in place; the workstream master plan at `methodology-schema-workstream-plan.md` governs the redirected effort.

The redirection produced a workstream of five conversations: one workstream-establishing planning conversation (SES-011), four per-entity schema-design conversations (SES-012 through SES-015 producing `domain.md`, `entity.md`, `process.md`, `crm_candidate.md`), and the v0.4-build-planning conversation that produced this PRD by integrating the four schema specs into a coherent release. The four schema specs are at `PRDs/product/crmbuilder-v2/methodology-schema-specs/`; this PRD cites them rather than restating their content.

### Source decisions

This PRD does not re-derive architectural decisions; it specifies requirements grounded in the following decision records.

Existing decisions still in force from prior releases:

- **DEC-006** — Universal references table as the cross-entity-type edge store. v0.4's two new relationship kinds extend this infrastructure additively.
- **DEC-013, DEC-014** — Session-and-conversation discipline; every v2 conversation produces a session record.
- **DEC-025** — `conversation_reference` is descriptive text; seed prompt verbatim in `topics_covered`.
- **DEC-033** — References create dialog with strict vocab compliance driven from `RELATIONSHIP_RULES`. v0.4's vocab additions extend the rule set; the dialog adapts automatically.
- **DEC-035, DEC-036** — `ListDetailPanel` factory + uniform right-click context menus. v0.4's four new panels inherit this base.
- **DEC-038** — v0.4 redirect: methodology entity schema design as primary frame.
- **DEC-039** — Minimum entity inventory (domain, entity, process, crm_candidate) plus one-v2-instance-per-engagement.
- **DEC-040** — Schema-design workstream structure: design-only conversations, sequential order, schema-spec methodology guide as the template.
- **DEC-043** — SES-010 identifier-asymmetry resolution via `GET /<entity>/next-identifier` helpers retrofitted to all twelve prefixed-identifier entity types in v0.4 build.
- **DEC-044 through DEC-049** — `domain` schema (identifier prefix, field inventory, parent-prefix field-naming convention, status lifecycle and rejection-via-soft-delete, source-first relationship-kind-naming convention, API/UI defaults).
- **DEC-050 through DEC-054** — `entity` schema (identifier prefix, field inventory, status lifecycle adoption, `entity_scopes_to_domain` via references entity, API/UI defaults, deferred Domains-column posture).
- **DEC-055 through DEC-059** — `process` schema (identifier prefix `PROC` with explicit deviation, field inventory with no-status-field deviation, `process_classification` enum, relationship architecture with direct FK and `process_hands_off_to_process` via references, API/UI defaults).
- **DEC-060 through DEC-064** — `crm_candidate` schema (identifier prefix `CRM`, field inventory, four-status terminal-state lifecycle with `removed`-status deviation, `ENTITY_TYPES` expansion only, singleton-`selected` enforcement and API/UI defaults).

Forthcoming decisions (to be recorded after this PRD is approved, see Section 11):

- **DEC-068** — Cross-spec consistency check accepted with three documented deviations as well-justified; spec guide section 6 amended to reflect parent-prefix field naming and source-first relationship-kind-naming conventions established by SES-012.
- **DEC-069** — v0.4 slice breakdown: hybrid six-slice structure (foundation, four entity panels, closeout) mirroring v0.3's shape.
- **DEC-070** — Coordinated create-then-attach reference-attachment flow for entity affiliations and process handoffs (Option A over create-with-attach Option B).
- **DEC-071** — Slice A scope including the SES-010 `GET /<entity>/next-identifier` retrofit folded into foundation rather than split into a separate slice.
- **DEC-072** — `crm_candidate` master-pane sort: simple identifier-ascending in v0.4 (Option A); status-then-identifier (Option B) reserved as v0.5+ candidate gated on CBM-redo signal.
- **DEC-073** — PI-006 (governance-entity parent-prefix retrofit) and PI-008 (inbox folder watcher for close-out payloads) both deferred to v0.5+ outside v0.4 scope.

**Renumbering note.** The draft of this PRD anticipated DEC-065 through DEC-070 for the six decisions above. The catalog ingestion build (SES-016, executed 05-14-26) consumed DEC-065/066/067 between the v0.4-build-planning conversation and PRD approval, so the six decisions shift to DEC-068 through DEC-073. The renumbering is bookkeeping; no content change.

---

## 2. Scope

### In Scope

The following are required deliverables for v0.4.

1. **Methodology sidebar group introduction.** A new container in the desktop UI sidebar positioned below the existing Governance group. Four entries within the group, in workstream order: Domains (#1), Entities (#2), Processes (#3), CRM Candidates (#4). The group container ships in slice A (initially empty); each panel populates in its respective entity slice. All four entries are present when v0.4 ships; intermediate slice states have a partially-populated group.

2. **Foundation infrastructure.** Vocabulary, migration, and helper-endpoint work that lands ahead of any per-entity panel work:
   - `ENTITY_TYPES` in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` expanded to admit `domain`, `entity`, `process`, `crm_candidate`.
   - `REFERENCE_RELATIONSHIPS` in `vocab.py` expanded to admit `entity_scopes_to_domain` and `process_hands_off_to_process`.
   - `_kinds_for_pair` extended with two source-target rules: `(entity, domain)` adds `entity_scopes_to_domain`; `(process, process)` adds `process_hands_off_to_process`. Universal kinds (`is_about`, `references`, `supersedes` for matched-type pairs, `decided_in` for session targets) apply automatically via the existing rule-based machinery.
   - Single Alembic migration extending three CHECK constraints on the `refs` table: `refs.source_type` and `refs.target_type` admit the four new entity-type values; `refs.relationship_kind` admits the two new vocabulary values.
   - The new Methodology sidebar group container (entries populate in subsequent slices).
   - `GET /<entity>/next-identifier` helper endpoints retrofitted to the eight existing prefixed-identifier governance entity types: `/decisions`, `/sessions`, `/risks`, `/planning_items`, `/topics`, `/references`, `/charter`, `/status`. Charter and status use version-numbered identifiers and the helper follows their access-layer increment pattern. Roughly ten lines per endpoint, mechanical.
   - Spec guide section 6 amendment per DEC-068 (renumbered from anticipatory DEC-065), committed to `methodology-entity-schema-spec-guide.md`.

3. **Domains panel — see Section 4.3 and `domain.md`.** Full CRUD on the `domain` entity type per `methodology-schema-specs/domain.md`. Master pane with columns Identifier / Name / Status / Updated; detail pane with identifier (read-only), name, purpose, description, notes (collapsed), status, `ReferencesSection`. Create/edit/delete dialogs as `EntityCrudDialog` and `EntityCrudDeleteDialog` subclasses. Status lifecycle and propose-verify gate enforced server-side. All eight standard endpoints (list, get, create, full replace, partial update, soft-delete, restore, next-identifier). 14 acceptance criteria from `domain.md` section 3.7.

4. **Entities panel — see Section 4.4 and `entity.md`.** Full CRUD on the `entity` entity type per `methodology-schema-specs/entity.md`. Master pane with columns Identifier / Name / Status / Updated (no Domains column in v0.4; deferred to v0.5+ paired with PI-007); detail pane includes `ReferencesSection` rendering outgoing `entity_scopes_to_domain` affiliations. Create-then-attach flow per DEC-070: domain affiliations attach from the detail pane after entity creation, not from within the New dialog. 16 acceptance criteria from `entity.md` section 3.7.

5. **Processes panel — see Section 4.5 and `process.md`.** Full CRUD on the `process` entity type per `methodology-schema-specs/process.md`. Master pane with columns Identifier / Name / Classification / Updated (no Domain column in v0.4; deferred per same posture as Entities). Detail pane includes the required `process_domain_identifier` FK combo (backed by `GET /domains`) and `ReferencesSection` rendering bidirectional `process_hands_off_to_process` references in separate "Hands off to" and "Receives from" sub-sections. `process_classification` carries the methodology's Principle 3 priority taxonomy (unclassified / mission_critical / supporting / deferred); no `status` field per the spec's deviation. Create-then-attach flow per DEC-070 for handoffs; the domain FK is a required scalar field in the create dialog because the record cannot be created without it. 15 acceptance criteria from `process.md` section 3.7.

6. **CRM Candidates panel — see Section 4.6 and `crm_candidate.md`.** Full CRUD on the `crm_candidate` entity type per `methodology-schema-specs/crm_candidate.md`. Master pane with columns Identifier / Name / Status / Updated, default sort identifier-ascending per DEC-072. Detail pane shows `ReferencesSection` rendering inbound governance-entity citations only (no outgoing relationships in v0.4). Four-status enum with three terminal states; singleton-`selected` constraint enforced at the access layer on POST, PATCH/PUT, and restore; delete dialog includes a clarifying note distinguishing the soft-delete-for-authoring-error path from the transition-to-`removed` path for legitimate mid-engagement drops. 12 acceptance criteria from `crm_candidate.md` section 3.7.

7. **About-dialog version bump and README release note.** `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` set to `"0.4.0"`. README at `crmbuilder-v2/README.md` gets a v0.4 release note matching v0.3's format.

### Out of Scope

The following are explicitly deferred to v0.5+ or later.

- **Full styling design pass per DEC-024.** Deferred for the fourth time per DEC-042 with the CBM-redo-friction trigger. PI-001 tracks the deferral and pulls to v0.5 ahead of other v0.5 candidates if CBM-redo Phase 1 surfaces visual friction on any of the four new panels.
- **Governance-entity retrofit to parent-prefix field-naming convention.** PI-006. The methodology entities ship with the new convention regardless; the retrofit is independent and substantial (eight existing tables plus all downstream surfaces) and warrants its own planning conversation.
- **In-app inbox folder watcher for close-out JSON payloads.** PI-008. Substantial UI addition with its own architectural questions (which folder to watch, duplicate handling, watcher error surfacing) deserving a dedicated planning conversation.
- **`persona` entity type.** PI-003. Phase 1 explicitly does not elicit personas in the evolved methodology; persona context is consultant background.
- **Additional methodology entity types: `field`, `requirement`, `manual_config`, `test_spec`.** PI-004. Late-phase methodology entity types deferred from the minimum-viable v0.4 scope.
- **Process schema growth beyond Phase 1 thin shape.** PI-005. Steps, actors, fields touched, triggers, outcomes, cycle time, frequency, volume, sub-process hierarchy — all Phase 3 territory.
- **`domain.short_code` field.** PI-007. Two-letter mnemonic codes (MN, MR, CR, FU in CBM's history) deferred pending CBM-redo signal on whether the evolved methodology continues to use mnemonic prefixes for downstream identifier construction.
- **Master-pane Domains column on the Entities panel.** PI-009. Paired with PI-007; the column has natural value once consultants are scanning 20+ entities but would render bare identifiers without short codes.
- **Entity-schema v0.5+ extensions (variants, base-type/kind).** PI-010.
- **Future scalar implementation-priority field on `process`.** PI-011.
- **`crm_candidate` structured-metadata enums (vendor URL, hosting type, license type, price tier).** PI-012.
- **Cross-Domain Service representation.** PI-013. The original methodology named Cross-Domain Service (Notes, Email, Calendar, Surveys) as a methodology entity type consumed across domains. The evolved methodology has not yet resolved whether Cross-Domain Service remains a distinct entity type, is subsumed into `process` once `process_kind` lands in v0.5+, or is dropped. Surfaced as untracked during the 05-14-26 reconciliation; placeholder PI pending CBM-redo signal.
- **Catalog FK integration for methodology entities.** PI-014. The catalog ingestion PRD's section 3.3 sketched a hybrid pattern (`primary_catalog_entity_id` FK on methodology entities + DEC-006 universal references for weak ties). The four v0.4 schemas don't implement it because their thin shape doesn't carry the field-level entity definitions that would need it; when PI-004's `field` lands, the catalog FK question must be answered (integer FK to `catalog_entity.id` vs text FK to `catalog_entity.catalog_id` per the catalog DEC-065; FK on `entity` vs on `field`; weak-tie interaction). Surfaced as untracked during the 05-14-26 reconciliation.
- **Methodology entity renderers.** PI-015. DEC-008 prescribes renders, not authored copies. v0.4 ships the storage and UI surface for methodology content but zero renderer work. .docx generation for Domain Inventory and Phase 1 Prioritized Backbone documents, YAML generation for the v1 deployment engine, and JSON exports for git-diff are all v0.5+ candidates. Likely a sizable workstream on its own. Surfaced as untracked during the 05-14-26 reconciliation.
- **Option (C) of SES-010 resolution: optional identifier in POST bodies with server-side auto-assignment on omission.** PI-002. v0.4 ships option (B) — the `GET /<entity>/next-identifier` helpers — and PI-002 tracks the ergonomic upgrade for later.
- **Three NOT_SUPPORTED v1 reimplementation workstreams** (saved views, duplicate-check rules, workflow managers). v1 application work, not v2.
- **Global search, exports, bulk operations, drag-to-reparent on Topics, optimistic concurrency control.** Out of v0.4 scope, same posture as v0.3.

---

## 3. Architecture

### Process model

Unchanged from v0.1, v0.2, and v0.3. The UI process spawns or attaches to the API subprocess (DEC-023), watches `db-export/` (DEC-022), and reaches the storage system exclusively through the REST API (DEC-019).

### Layer responsibilities

v0.4 keeps every v0.3 layer and adds four panel modules, four dialog modules, and one sidebar-group container. The storage client gains methods for the four new entity types and the eight retrofitted next-identifier helpers. No new top-level structural change.

| Layer | Module | Status | Responsibility |
|---|---|---|---|
| Application shell | `crmbuilder_v2.ui.app` | extended | Sidebar gains the new Methodology group container; group-aware sidebar rendering follows the existing Governance-group pattern |
| Storage client | `crmbuilder_v2.ui.client` | extended | Adds `list_domains`, `get_domain`, `create_domain`, `update_domain`, `patch_domain`, `delete_domain`, `restore_domain`, `next_domain_identifier` and the equivalent eight methods for each of `entity`, `process`, `crm_candidate`. Adds `next_<governance>_identifier` for the eight existing prefixed entity types. |
| Workers | `crmbuilder_v2.ui.workers` | unchanged | `QThread` wrappers around storage client calls |
| Server lifecycle | `crmbuilder_v2.ui.server_lifecycle` | unchanged |
| Refresh service | `crmbuilder_v2.ui.refresh` | extended | File-watch map extends to cover the four new entity types' snapshot files |
| Entity panels | `crmbuilder_v2.ui.panels.*` | extended | New `domains.py`, `entities.py`, `processes.py`, `crm_candidates.py` — each subclassing `ListDetailPanel`, each with its own context-menu and detail-pane configuration |
| Dialogs | `crmbuilder_v2.ui.dialogs.*` | extended | New `domain_crud.py`, `entity_crud.py`, `process_crud.py`, `crm_candidate_crud.py`, each carrying create/edit/delete dialogs as `EntityCrudDialog` and `EntityCrudDeleteDialog` subclasses |
| Base widgets | `crmbuilder_v2.ui.base` | unchanged | `ListDetailPanel`, `EntityCrudDialog`, `EntityCrudDeleteDialog` reused from v0.3 |
| Reusable widgets | `crmbuilder_v2.ui.widgets` | unchanged | `ReferencesSection`, `EntityIdentifierPicker`, `DateField` reused from v0.3 |
| Access layer | `crmbuilder_v2.access.*` | extended | New `domain.py`, `entity.py`, `process.py`, `crm_candidate.py` repositories. `vocab.py` extended with `ENTITY_TYPES` and `REFERENCE_RELATIONSHIPS` additions, two new `_kinds_for_pair` rules. Existing repositories extended with `next_identifier` methods. |
| REST API | `crmbuilder_v2.api.*` | extended | New `domain_routes.py`, `entity_routes.py`, `process_routes.py`, `crm_candidate_routes.py`. Existing routes extended with `GET /<entity>/next-identifier` endpoints. |
| Migrations | `crmbuilder-v2/migrations/` | extended | Six new revisions: one foundation revision (CHECK-constraint extensions on `refs`), four table-creation revisions (one per new entity type), no migration in slice F |

### Configuration

Unchanged from prior releases. No new environment variables, no config file additions.

---

## 4. Functional Requirements

### 4.1 Methodology sidebar group introduction

A new sidebar group container titled "Methodology" appears below the existing Governance group. The group container ships in slice A and is initially empty; each entity panel populates its position in its respective slice (Domains in B, Entities in C, Processes in D, CRM Candidates in E). The group container's rendering matches the existing Governance-group pattern — a header row and ordered entries below.

When v0.4 ships, the Methodology group has four entries in workstream order: Domains, Entities, Processes, CRM Candidates. Selecting any entry switches the content pane to the corresponding `ListDetailPanel`.

### 4.2 Foundation infrastructure

Section 2 "In Scope" item 2 lists the foundation deliverables. Slice A's Claude Code prompt implements them as a single coherent change. Key implementation points:

- **Vocabulary additions land in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`.** The four new entity-type strings (`domain`, `entity`, `process`, `crm_candidate`) join `ENTITY_TYPES`. The two new relationship-kind strings join `REFERENCE_RELATIONSHIPS`. The `_kinds_for_pair` function gains two new conditional branches matching the registered pairs. `RELATIONSHIP_RULES` auto-recomputes at module load and the cascading vocab dialog adapts without UI changes.

- **The Alembic migration is one revision** extending three CHECK constraints on the `refs` table atomically. Forward and backward reversible. Applied as the first slice-A migration; the four entity-table migrations follow one per slice in B through E.

- **The eight retrofitted `GET /<entity>/next-identifier` helpers** mirror the pattern already established for v0.3 governance entities' implicit identifier-assignment paths. Each returns `{"next": "<PREFIX>-<NNN>"}`. Charter and status helpers follow their versioned-identifier semantics rather than literal next-integer.

- **The spec guide section 6 amendment** commits the diff per DEC-068: scope-note paragraph at section head; three table rows updated to flag methodology-only scope for status field name, relationship-kind naming, and field naming; one sentence appended to the closing paragraph acknowledging the three documented cross-spec deviations.

### 4.3 Domains panel

Implements `methodology-schema-specs/domain.md` end-to-end. The spec is authoritative; this PRD does not restate field definitions, status semantics, or API contracts. Cross-cutting integration points:

- Panel registered at Methodology sidebar position #1.
- `ListDetailPanel` subclass with `_create_master_widget` returning a default-configured `QTableView` per the v0.3 factory pattern.
- Context menu via `_build_context_menu` factory: New / Edit / Delete / Restore (Restore on soft-deleted rows; surfaces under `?include_deleted=true` toggle per v0.3 patterns).
- Detail pane composes `EntityIdentifierPicker`-less form (identifier is auto-assigned and read-only), text editors per the field categorization in `domain.md` section 3.2, status combo, and `ReferencesSection` widget for the inbound side. The widget is empty in slice B and populates as Slices C and D bring entity and process records that reference domains.
- Status combo restricts to valid successors per the propose-verify gate; invalid selections are either prevented client-side or rejected by the server with the 422 envelope.

### 4.4 Entities panel

Implements `methodology-schema-specs/entity.md` end-to-end. Integration points beyond what the spec covers:

- Panel registered at Methodology sidebar position #2.
- The slice that builds this panel (Slice C) is the first end-to-end exercise of the `entity_scopes_to_domain` vocabulary kind registered in Slice A. The cascading vocab dialog (v0.3's `ReferenceCreateDialog`) correctly enumerates the new kind for the `(entity, domain)` source-target pair because `RELATIONSHIP_RULES` recomputed at module load.
- Create-then-attach flow per DEC-070: the New Entity dialog does not include a multi-select for domain affiliations. After the entity record is created, the user adds affiliations from the detail pane's `ReferencesSection` "Add reference" affordance, which opens the cascading vocab dialog with the source pre-populated to the just-created entity.
- Detail pane renders outgoing `entity_scopes_to_domain` references plus any inbound references (none registered in v0.4; the widget is present for v0.5+ future kinds).

### 4.5 Processes panel

Implements `methodology-schema-specs/process.md` end-to-end. Integration points beyond what the spec covers:

- Panel registered at Methodology sidebar position #3.
- Master pane column #3 is `process_classification` (not `process_status`; the spec deviates on status per DEC-056). Display values render as-is from the enum.
- Create dialog includes a required FK combo for `process_domain_identifier` backed by `GET /domains` enumerating live records only. The record cannot be submitted without a domain selection. Default selection is the first live domain alphabetically or the user's last-selected domain if a per-session memory exists.
- Create-then-attach flow per DEC-070: process-to-process handoffs attach from the detail pane after process creation. The cascading vocab dialog enumerates `process_hands_off_to_process` for the `(process, process)` source-target pair.
- Detail pane `ReferencesSection` widget renders two distinct sub-sections: "Hands off to" (this process is the source) and "Receives from" (this process is the target). Both render `process_hands_off_to_process` edges in their respective directions.
- Domain re-affiliation permitted via PATCH/PUT; the spec's section 3.5.4 describes the UI surface for this (warning + restore-or-re-affiliate offer if affiliated domain is soft-deleted; the v0.4 build implements the warning as inline text on the detail pane, with no separate dialog).

### 4.6 CRM Candidates panel

Implements `methodology-schema-specs/crm_candidate.md` end-to-end. Integration points beyond what the spec covers:

- Panel registered at Methodology sidebar position #4.
- Master pane columns Identifier / Name / Status / Updated; default sort by identifier ascending per DEC-072. Terminal-state records (`selected`, `declined`, `removed`) interleave with `active` by identifier in v0.4; status-then-identifier ordering reserved as a v0.5+ candidate.
- Status combo on detail pane and edit dialog restricts available choices to valid successors of the current status per the spec's 3.4.1 table. Terminal-state records show only the current value in their combo (effectively read-only post-transition).
- Singleton-`selected` enforcement surfaces inline on the dialog when a user attempts an action that violates the constraint. The 422 error envelope's `existing` field names the already-selected record; the dialog's inline error text reads "CRM-NNN is already selected — change its status first."
- Delete dialog includes a clarifying note distinguishing the two paths. Proposed wording (slice E refines as needed):
  > Delete soft-deletes this record as an authoring-error correction. If this CRM was legitimately in the candidate set and you want to pull it from further iterations, change its Status to **Removed** instead.

### 4.7 Coordinated create-then-attach reference-attachment flow

Per DEC-070, both the Entities panel (Slice C) and the Processes panel (Slice D) implement reference-attachment as a two-stage operation: (a) the New dialog creates the record only, with fields covering only scalar attributes (including required FK fields like `process_domain_identifier`, which are scalars not references); (b) after the record exists, the user attaches references from the detail pane via the existing "Add reference" affordance that opens v0.3's cascading vocab dialog.

The cascading vocab dialog's existing source-pre-population path (v0.3 slice C) supports the new vocab kinds without modification because `RELATIONSHIP_RULES` recomputes from `_kinds_for_pair` and `ENTITY_TYPES` at module load. No new dialog code is needed for the two new vocab kinds; the foundation work in Slice A makes them available everywhere the dialog renders.

The decision applies uniformly to both panels. Users do not need to learn two different patterns for "create a new methodology record."

---

## 5. Cross-Cutting Concerns

### 5.1 About-dialog version bump

Slice F sets `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` to `"0.4.0"`. The About dialog reads via `importlib.metadata` with `__version__` as fallback per the CLAUDE.md v2 version-source convention.

### 5.2 README release note

Slice F adds a v0.4 release-note entry to `crmbuilder-v2/README.md` matching v0.3's format: a one-paragraph summary plus a bullet list naming the four new panels, the two new vocab kinds, the Methodology sidebar group, and the SES-010 next-identifier helper retrofit.

### 5.3 Test target

`uv run pytest tests/crmbuilder_v2/ -v` continues as the test target. The new entity-type test modules (`tests/crmbuilder_v2/access/test_domain.py`, `test_entity.py`, `test_process.py`, `test_crm_candidate.py` plus their API and integration parallels) are discovered automatically by pytest's collection without changes to the test configuration.

### 5.4 Status update

Status (the governance entity) is updated from "v0.3 complete" to "v0.4 complete" after Slice F passes. The status update is authored through the desktop UI's versioned-replace pattern, not by Claude Code directly, because the status entity is governance content edited by the operator after build acceptance.

---

## 6. Acceptance Criteria

Cumulative acceptance criteria for v0.4 = foundation criteria (Slice A) + 14 (Domain, `domain.md` 3.7) + 16 (Entity, `entity.md` 3.7) + 15 (Process, `process.md` 3.7) + 12 (CRM Candidate, `crm_candidate.md` 3.7) + closeout criteria (Slice F).

### Slice A foundation criteria

A1. `ENTITY_TYPES` in `vocab.py` includes `domain`, `entity`, `process`, `crm_candidate` after slice A merges; introspection from any caller returns the expanded set.

A2. `REFERENCE_RELATIONSHIPS` in `vocab.py` includes `entity_scopes_to_domain` and `process_hands_off_to_process`.

A3. `_kinds_for_pair((entity, domain))` returns `{is_about, references, entity_scopes_to_domain}`. `_kinds_for_pair((process, process))` returns `{is_about, references, supersedes, process_hands_off_to_process}`. `RELATIONSHIP_RULES` reflects these mappings at module load.

A4. The Alembic migration extending the three `refs` CHECK constraints applies cleanly forward and backward against the v0.3-shipped database.

A5. The eight retrofitted `GET /<entity>/next-identifier` endpoints (`/decisions`, `/sessions`, `/risks`, `/planning_items`, `/topics`, `/references`, `/charter`, `/status`) return `{"next": "<PREFIX>-<NNN>"}` correctly. Charter and status return version-numbered next-values per their access-layer pattern. Concurrent calls do not return the same value (concurrent-fetch test required).

A6. The Methodology sidebar group container renders below the Governance group, initially empty, ready to receive panel entries.

A7. The spec guide section 6 amendment is committed; the section's structure matches the approved diff.

A8. v0.3's existing pytest suite remains green; no behavioral changes to existing entities.

### Per-entity acceptance criteria

Per `domain.md` section 3.7: criteria 1–14 (schema migration, identifier format, name uniqueness, status enum and transition, access-layer methods, REST endpoints, identifier auto-assignment + concurrency, soft-delete/restore, sidebar #1, master columns + context menu, detail pane fields in order, CRUD dialogs end-to-end, file-watch refresh, sample CBM-redo Phase 1 records).

Per `entity.md` section 3.7: criteria 1–16 (the domain pattern plus criteria 14 vocab registration + constraint enforcement, 15 bidirectional reference round-trip, 16 sample CBM-redo Phase 1 records with domain affiliations).

Per `process.md` section 3.7: criteria 1–15 (the domain pattern adapted for `process_classification` instead of `status`, plus criterion 5 domain-FK validation, criterion 14 `process_hands_off_to_process` registered and round-tripping, criterion 15 sample CBM-redo Phase 1 Prioritized Backbone with handoffs).

Per `crm_candidate.md` section 3.7: criteria 1–12 (the domain pattern adapted for four-status terminal-state lifecycle, plus criterion 5 singleton-`selected` enforcement on three operations, criterion 9 `crm_candidate` in `ENTITY_TYPES` and cascading-dialog correctness, criterion 12 sample CBM-redo Phase 5 selection round-trip).

### Slice F closeout criteria

F1. `__version__` is `"0.4.0"`; About dialog shows v0.4.0.

F2. README at `crmbuilder-v2/README.md` has a v0.4 release-note entry matching v0.3's format.

F3. `uv run pytest tests/crmbuilder_v2/ -v` passes green across the full suite (v0.3 tests + all new v0.4 tests).

F4. The Methodology sidebar group renders with all four panels in workstream order; each panel is operable end-to-end.

F5. Cumulative roll-up: A1–A8 plus all per-entity criteria pass in the running application.

---

## 7. Implementation Plan Reference

Slice breakdown, dependencies, and per-slice acceptance criteria are at `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md`. The implementation plan is the companion document to this PRD and is the source of truth for slice-level build sequencing and the Claude Code prompts that execute v0.4.

---

## 8. Constraints

### Storage layer additive only

v0.4 extends the storage layer additively: new tables, new endpoints, new access-layer methods, new vocabulary entries. No changes to existing entity types' shapes or behaviors. Reference vocabulary additions are extensions, not modifications. The cross-spec consistency check at the head of the v0.4-build-planning conversation confirmed this posture per the four schema specs' constraints.

### No changes to the v1 application

Unchanged from v0.1–v0.3. v2 work is strictly additive to v1.

### Constraint: process model still assumes localhost

Unchanged from prior releases.

### Constraint: foundation infrastructure must not regress v0.3 panel behavior

Slice A's vocab additions, Alembic migration, and helper-endpoint retrofit must not change v0.3's behavior on any existing entity. The v0.3 test suite is the regression net; slice A is acceptance-gated on every v0.3 test continuing to pass.

### Constraint: status independence on entities

Per `entity.md` section 3.4.3, an entity's `entity_status` is its own field and is not derived from the statuses of the domains it scopes to. Edit affordances on `entity_status` do not consult affiliated domains; changing a domain's status does not cascade to inbound `entity_scopes_to_domain` references' source-side records. Slice C must not introduce such cascade behavior.

### Constraint: append-only on sessions stays strict

Unchanged from v0.3. No UI path edits or deletes a session record. The four new methodology entity types have full CRUD per their specs; sessions remain create-only.

### Constraint: parent-prefix field naming on methodology entities

All methodology-entity fields including identifier and timestamps are prefixed with the parent entity name per DEC-046. The four entity-table migrations in slices B–E ship the prefixed column names directly; no rename migration follows. Governance-entity field names retain their pre-workstream conventions until PI-006 retrofit lands (not in v0.4 scope).

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Slice A's foundation work (vocab additions + Alembic migration + helper retrofit) bloats beyond one Claude Code run's comfortable size | Medium | Medium | Slice A is monitored at execution time; if the prompt exceeds healthy size or Claude Code shows degradation symptoms during slice A, the slice splits into A1 (methodology foundation) + A2 (helper retrofit) producing a seven-slice shape. The decision is made when the slice-A prompt is drafted, not pre-committed in the PRD. |
| `RELATIONSHIP_RULES` recomputation at module load misses the new pairs because of an import-order issue | Low | Medium | Slice A's tests explicitly assert the post-load contents of `RELATIONSHIP_RULES` for the new pairs; the test runs in v0.4's CI before any per-entity slice. |
| The cascading vocab dialog renders incorrectly for new pairs because of an ENTITY_TYPES vs RELATIONSHIP_RULES mismatch | Low | High | Slice C is the first slice that exercises the new vocab kind through the UI; the slice's smoke test opens the dialog with `(entity, domain)` source-target combination and asserts `entity_scopes_to_domain` appears in the kind combo. Slice D does the equivalent for `(process, process)`. |
| Concurrent identifier-assignment race on the new entity types produces duplicate identifiers | Low | High | Each of slices B–E carries a concurrent-insert test per its acceptance criterion #7 (or #8 for process). The test fails the slice if duplicates occur. The mechanism (row-level locking, optimistic retry) is implementation-level and follows v0.3's existing pattern; no new mechanism invented. |
| Singleton-`selected` enforcement on `crm_candidate` allows a race where two concurrent POSTs both attempt to insert `selected` and both succeed because the check runs before either inserts | Low | High | Slice E carries an explicit concurrent-POST test for two `selected` insertions. The mechanism is the same access-layer transaction pattern v3 uses for case-insensitive uniqueness; locking happens at the table level. |
| The create-then-attach flow generates more gestures than CBM-redo Phase 1 work can comfortably tolerate | Medium | Low | DEC-070 explicitly notes create-with-attach is a clean v0.5 upgrade if CBM redo surfaces friction. The deferral is intentional; the daily-driver test happens in real use. |
| Domain re-affiliation on `process` records (PATCH `process_domain_identifier`) breaks existing handoff renderings | Low | Medium | `process.md` section 3.5.4 permits re-affiliation; the detail pane re-renders on file-watch refresh. Slice D's tests cover the re-affiliation case explicitly. |
| The spec guide section 6 amendment lands but a downstream reader misses the methodology-only scope note and applies the conventions retroactively to governance entities | Low | Low | The scope-note paragraph is at the section head; the three updated rows carry "(methodology only)" labels. PI-006 tracks the eventual governance retrofit; if a reader confuses the two, the cross-references in the closing-paragraph addendum point to the deviation rationale. |

---

## 10. Open Questions

1. **Slice A size threshold for splitting into A1 + A2.** The slice combines methodology-foundation work and SES-010 helper retrofit. If the slice's Claude Code prompt exceeds ~800 lines or shows other size-related signals during drafting, the slice splits into A1 (methodology foundation, sidebar group, vocab + migration + amendment) and A2 (helper retrofit). The split decision is made at prompt-drafting time in the slice-A prompt commit; if the split happens, the implementation plan is updated to reflect seven slices.

2. **Delete-dialog clarifying note final wording on the `crm_candidate` panel.** Proposed in Section 4.6. Slice E refines if the proposed wording reads awkwardly in the actual dialog layout.

3. **`process_domain_identifier` combo default-selection behavior.** Per `process.md` section 3.6.4, the combo defaults to "the first live domain alphabetically, or to the user's last-selected domain if a per-session memory exists." The per-session memory mechanism is not specified; Slice D either implements a simple in-memory cache or falls back to the alphabetical-first default unconditionally. The choice is UI-detail.

4. **Status combo restriction enforcement strategy.** All four entity panels have status (or classification) transition validation. The detail-pane combo can either prevent invalid selections client-side or allow them and rely on the server's 422 surfacing inline. The slice's choice is per-panel; consistency across the four panels is preferred but not required. Working assumption: prevent client-side where feasible.

5. **Handoff direction widget on the Process detail pane.** Section 4.5 describes "two distinct sub-sections: 'Hands off to' and 'Receives from'" within the `ReferencesSection` widget. The widget's existing v0.3 implementation renders a single flat list; whether the two sub-sections require modifications to the widget itself or are handled by the panel's detail-pane layout is a slice-D implementation choice.

---

## 11. Decisions to Be Recorded

Per DEC-014 (every v2 conversation produces a session record) and DEC-025 (conversation_reference convention + seed-prompt-in-topics_covered), the v0.4-build-planning conversation that produced this PRD plus the 05-14-26 reconciliation/approval conversation that finalized it are captured in the v2 database at this PRD's closeout.

**Renumbering note.** The draft of this PRD anticipated SES-016 for the v0.4-build-planning conversation and DEC-065 through DEC-070 for its decisions. The catalog ingestion build (executed 05-14-26) consumed SES-016 and DEC-065/066/067 before this PRD reached approval. The records below use the renumbered identifiers. The renumbering is bookkeeping; no content change to the decisions themselves.

Records to write at PRD closeout:

- **SES-017** — UI v0.4 build planning. Status: Complete. `conversation_reference`: descriptive text per DEC-025 (`"Claude.ai planning conversation that produced ui-PRD-v0.4.md (draft), ui-v0.4-implementation-plan.md, the CLAUDE-CODE-PROMPT-v2-ui-v0.4 slice series, and the methodology-entity-schema-spec-guide section 6 amendment under PRDs/product/crmbuilder-v2/. Finalized 05-14-26 in a separate reconciliation conversation. No transcript preserved per DEC-025."`). `topics_covered` opens with the verbatim seed prompt rendered as `Seed prompt: "<kickoff content>"`, followed by a structured summary of the cross-spec consistency check outcome and the six architectural decisions resolved.
- **SES-018** — v0.4 PRD reconciliation and approval. Status: Complete. `conversation_reference`: descriptive text per DEC-025 (`"Claude.ai reconciliation conversation on 05-14-26 that detected the methodology-entity-schema-planning-prompt was stale relative to repo state, surveyed the in-flight v0.4 work, and approved ui-PRD-v0.4.md with renumbering deltas. Produced edits to ui-PRD-v0.4.md, ui-v0.4-implementation-plan.md, and methodology-entity-schema-spec-guide.md."`). `topics_covered` opens with the verbatim seed prompt; followed by reconciliation findings (workstream state, ID-collision analysis, three untracked-PI surfaces).
- **DEC-068** — Cross-spec consistency check accepted with three documented deviations as well-justified; spec guide section 6 amended per the workstream-established parent-prefix and source-first conventions.
- **DEC-069** — v0.4 slice breakdown: hybrid six-slice structure (foundation + four entity panels + closeout).
- **DEC-070** — Coordinated create-then-attach reference-attachment flow (Option A) for entity affiliations and process handoffs.
- **DEC-071** — Slice A scope including the SES-010 next-identifier helper retrofit folded into foundation.
- **DEC-072** — `crm_candidate` master-pane sort: simple identifier-ascending in v0.4; status-then-identifier reserved as v0.5+ candidate.
- **DEC-073** — PI-006 and PI-008 both deferred to v0.5+ outside v0.4 scope.
- **DEC-074** — v0.4 PRD approval. Records the SES-018 outcome: PRD status transition from "Draft — pending approval" to "Approved" after reconciliation; SES/DEC renumbering applied; three new PIs (PI-013, PI-014, PI-015) authored; v0.4 build prompts unblocked. Links to SES-018 via `decided_in`.
- **PI-013** — Cross-Domain Service representation. Description per Section 2 Out of Scope.
- **PI-014** — Catalog FK integration for methodology entities. Description per Section 2 Out of Scope.
- **PI-015** — Methodology entity renderers. Description per Section 2 Out of Scope.
- **References** — `decided_in` from SES-017 to each of DEC-068 through DEC-073; `decided_in` from SES-018 to DEC-074; `is_about` from SES-018 to each of PI-013, PI-014, PI-015 (the reconciliation conversation surfaced them).

A status update reflecting that UI v0.4 is now in build (phase `"v0.4 in build"`, version label incremented from `1.0` to whatever the closeout sequence produces) is also appropriate at the same time.

The PI sizing decisions in DEC-073 do not author new PIs because PI-006 and PI-008 already exist in the database from prior workstream conversations; DEC-073 records the deferral choice and links to the existing PIs. The three PIs authored at this closeout (PI-013, PI-014, PI-015) are net-new; they were surfaced as untracked during the 05-14-26 reconciliation conversation.

---

*End of document.*
