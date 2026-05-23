# Audit Feature v1.2 — Planning Document

**Document type:** Application development planning (planning only; not implementation)
**Repository:** `crmbuilder`
**Path:** `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md`
**Last Updated:** 05-23-26 03:55
**Version:** 1.3 (identifier rebase — SES-060 / DEC-178..182)

---

## Status

This document is a **planning artifact** for the v1.2 expansion of the CRM Audit feature. It is not implementation; it is the design authority for the Claude Code prompt series that will execute the implementation. Per Doug's working pattern, planning before prompting.

The work this document covers is anticipated to span 11 Claude Code prompts across multiple work sessions. The series tag is `audit-v1.2`. Implementation prompts will follow the filename pattern `CLAUDE-CODE-PROMPT-audit-v1.2-{letter}-{descriptor}.md` and live in this same directory.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-23-26 01:10 | Doug Bower / Claude | Initial planning document. Captures Decisions 1, 2, 2.5, 3 from the planning kickoff conversation; surveys the existing v1.1 audit feature; designs the v1.2 expansion (entity-level selection, filtered tabs audit, full Section 12 round-trip including role-aware visibility); proposes an 11-prompt implementation series. |
| 1.1 | 05-23-26 02:30 | Doug Bower / Claude | Resolves all four §9 open questions: persona is documentation metadata with no validation; empty `scope_access:` roles produce an informational audit-log warning; `include_security` and `include_filtered_tabs` default to True; existing audit output is overwritten with a pre-run confirmation guard when the output directory contains prior emission. Corrects Prompt H to reference the project's actual versioned migration mechanism in `automation/db/migrations.py` (new `_client_v4` migration) rather than Alembic. Threads the overwrite-confirmation dialog into §4.1 operator flow and Prompt J. |
| 1.2 | 05-23-26 03:05 | Doug Bower / Claude | Resolves the `security.yaml` file-placement question carried as a workflow item in v1.1's §10: security files live in a `security/` subdirectory of the program directory, not at root alongside per-entity YAMLs. Future-proofs the v1.4 deferred work (Section 12.7 permission presets) by anchoring security-related files in a single folder. Updates §4.1 step 8, Prompt A loader scan, Prompt H emission target, and Prompt J overwrite-confirmation trigger pattern. §10 is updated to remove the placement bullet, leaving only the series-size workflow question. |
| 1.3 | 05-23-26 03:55 | Doug Bower / Claude | Identifier rebase. The PI-024 prior-workstreams backfill conversation ran concurrently with this resolution conversation and pushed its SES-059 / DEC-175..177 close-out to origin/main first (commit 44182d1 at 15:32 UTC; my v1.2 of this doc pushed at 15:28 UTC, but the close-out payload hadn't pushed yet). v1.3 rebases this conversation's identifiers from SES-059 / DEC-175..179 to SES-060 / DEC-178..182. §10 updated; close-out payload re-authored at ses_060.json; apply prompt re-authored at ses-060.md. No design content changes — pure identifier-collision repair. |

---

## Change Log

**Version 1.0 (05-23-26 01:10):** Initial creation. Records the design decisions made in the planning conversation: users out of audit scope (Decision 1, Option C); roles/teams full round-trip with both audit and deploy bundled in this workstream (Decision 2, Option B); all five parts of Section 12 in scope including role-aware visibility (Decision 2.5, Option A); pre-flight live discovery for the entity picker (Decision 3). Surveys the existing v1.1 audit feature in commit `1eabfbb` and the v1.3 schema gaps (Section 12 paper-only, no role-clause support in `condition_expression.py`). Proposes an 11-prompt series with letter assignments, dependencies, validation criteria, and per-prompt end states.

**Version 1.1 (05-23-26 02:30):** Resolves all four §9 open questions captured in v1.0 and corrects two design errors caught during the resolution conversation.

- §9.1 resolved as "no validation": the `persona:` field on `RoleDefinition` is documentation metadata only. The loader does not cross-check it; the audit emits whatever the source instance carries.
- §9.2 resolved as "yes, informational log warning": when a captured role has empty `scope_access:`, the audit log records an informational warning. The YAML output itself is unaffected.
- §9.3 resolved as "default True": `include_security` and `include_filtered_tabs` follow the existing `AuditOptions` pattern and default to checked. This is a revision from the provisional default-False answer in v1.0.
- §9.4 resolved as "overwrite with confirmation guard": v1.2 overwrites prior audit output in the same directory, but the Audit dialog displays a pre-run confirmation when the output directory contains files matching the audit emission pattern.

Two corrections folded in:

- Prompt H previously referenced "Alembic-style migration" for the new role and team tables. The project does not use Alembic; the actual mechanism is the versioned migration runner in `automation/db/migrations.py` with a `schema_version` table and `_client_v1` through `_client_v3` migrations. v1.1 corrects Prompt H to add a new `_client_v4` migration following the existing pattern. Prompt I receives the same correction for its filtered-tab tables (folded into `_client_v4` rather than a separate version).
- §4.1 operator flow gains a new step describing the overwrite-confirmation dialog. Prompt J's UI work picks up the dialog implementation.

§9 is renamed from "Open Questions" to "Resolved Design Questions" and rewritten to record the decisions rather than flag them. §10 is updated to reflect that the four §9 questions are resolved and Prompt A is now unblocked.

**Version 1.2 (05-23-26 03:05):** Resolves the `security.yaml` file-placement question that v1.1 carried as a workflow item in §10.

- **Resolution.** `security.yaml` lives in a `security/` subdirectory of the program directory, not at root alongside per-entity YAMLs.
- **Rationale.** The §7 deferred-work list already names v1.4 work (Section 12.7 field-level permissions and permission presets) that will produce additional security-related files. Anchoring those files in a single folder now is cheaper than migrating v1.2 outputs when v1.4 lands. The cost is a small loader convention (scan root plus `security/`) and a one-line addition to the §9.4 overwrite-confirmation trigger pattern.
- **Updates threaded through.** §4.1 step 8 specifies the emission path; Prompt A's loader work scans the `security/` subdirectory in addition to root; Prompt H emits to `security/security.yaml`; Prompt J's overwrite-confirmation trigger now matches `*.yaml` at root and `security/*.yaml` under the subdirectory.
- **§10 updated.** The `security.yaml` placement bullet is removed. The series-size mitigation question remains as the only workflow item, deliberately not resolved in the document.

**Version 1.3 (05-23-26 03:55):** Identifier-collision repair — pure rebase, no design content changes.

The PI-024 prior-workstreams backfill conversation ran concurrently with this audit-v1.2 resolution conversation. Both targeted SES-059 as the next available session identifier per the engagement's db-export snapshot (which still showed SES-057 as head locally because SES-058's apply had not yet run). PI-024 pushed its close-out commit first (44182d1 at 15:32 UTC), taking SES-059 with DEC-175 through DEC-177. v1.3 rebases this conversation's records to SES-060 with DEC-178 through DEC-182. §10's "recorded as formal governance records under SES-059 (DEC-175 through DEC-179)" updated to "SES-060 (DEC-178 through DEC-182)" with a note about the collision. The close-out payload was re-authored at `close-out-payloads/ses_060.json` and the apply prompt at `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-060.md`; the apply prompt's pre-flight expects SES-059 (Doug's PI-024 close-out) to be applied first.

---

## 1. Motivation

The CRM Audit feature shipped in April 2026 (commit `1eabfbb`) as a way to reverse-engineer a live EspoCRM instance into YAML program files. The v1.1 feature is functionally complete for its initial scope — custom entities, custom fields on native and custom entities, detail and list layouts, and relationships — but three gaps have become operationally relevant as CBM and other pilot use cases have evolved.

**Gap 1: Audit is category-wide, not entity-targeted.** The v1.1 UI offers category-level scope options (all custom entities, all custom fields on native entities, etc.) but no way to narrow an audit to a specific set of entities. In practice, an operator who has made a single change to one entity on the source instance has no efficient way to capture just that entity's current state; they have to audit everything and diff manually.

**Gap 2: Filtered tabs are not captured.** EspoCRM's "filtered tab" pattern — a top-level navigation entry that lands the user directly on a filtered list view — is fully supported on the deploy side. `filtered_tab_manager.py` deploys both halves of the pattern (Report Filter record over REST plus the three custom-scope metadata files in a deploy bundle). The audit, however, never inspects either half. A round-trip from source to YAML to target instance silently loses every filtered tab.

**Gap 3: Security structure is unaddressed.** Schema v1.3 specifies roles, teams, scope access, system permissions, and role-aware visibility in Section 12 (over 500 lines), but Section 12 is paper-only: `config_loader.py` doesn't reference `roles:` or `teams:`, `models.py` has no `RoleDefinition` or `TeamDefinition` dataclass, and no `role_manager.py` or `team_manager.py` exists in `espo_impl/core/`. The audit also captures none of it. As long as security is unimplemented on both ends, the operator manually recreates roles in each target instance — an error-prone step that scales poorly as the number of personas grows.

This planning workstream addresses all three gaps in one coordinated effort. The audit feature comes out of this workstream at v1.2: capable of entity-targeted captures, capable of capturing and emitting filtered tabs, and capable of full round-trip on security structure paired with new deploy-side managers.

---

## 2. Current State Survey

This section captures what exists in the repository as of commit `7e4592f` (current `main` HEAD as of this document's creation).

### 2.1 Audit feature v1.1 — what's there

| Module | Purpose | Size |
|---|---|---|
| `espo_impl/core/audit_manager.py` | Orchestrator: discovery, extraction, YAML emission | 936 lines |
| `espo_impl/core/audit_db.py` | Idempotent insertion into client SQLite database | 487 lines |
| `espo_impl/core/audit_utils.py` | Entity/field classification, reverse name mapping | 319 lines |
| `espo_impl/workers/audit_worker.py` | QThread background worker | 183 lines |
| `automation/ui/deployment/audit_entry.py` | Sidebar entry + progress dialog + scope checkboxes | 521 lines |
| `PRDs/product/features/feat-audit.md` | Feature PRD (Status: Implemented) | 610 lines |

The four metadata-discovery API methods added in `1eabfbb` are in `espo_impl/core/api_client.py`: `get_all_scopes()`, `get_entity_full_metadata()`, `get_all_links()`, `get_entity_field_list()`. The `InstanceRole` enum on `InstanceProfile` (`source` / `target` / `both`) gates which instances appear in which entry pickers.

### 2.2 What's missing for v1.2

| Gap | Where it lives |
|---|---|
| Per-entity scope filter on `AuditOptions` | `audit_manager.py` |
| Entity-picker UI populated by pre-flight discovery | `audit_entry.py` |
| `_discover_filtered_tabs()` step | `audit_manager.py` |
| `FilteredTabAuditResult` dataclass | `audit_manager.py` |
| Reverse of `filtered_tab_manager.py` (Report Filter records + custom-scope metadata files → YAML `filteredTabs:`) | `audit_manager.py` |
| `roles:` / `teams:` top-level recognition | `config_loader.py` |
| `RoleDefinition` / `TeamDefinition` / `ScopeAccess` dataclasses | `models.py` |
| `role_manager.py` + `team_manager.py` (CHECK→ACT) | `espo_impl/core/` |
| `role:` leaf clause variant in condition expressions | `condition_expression.py` |
| Role-aware `requiredWhen` / `visibleWhen` validation | `config_loader.py`, validators |
| Role-scoped layout/panel visibility (`forRoles:`) | `config_loader.py`, layout deploy |
| `_discover_roles()` / `_discover_teams()` / role-aware dynamic logic reversal | `audit_manager.py` |
| Section 12.6 deploy ordering for security pipeline step | `run_worker.py` orchestration |
| `security.yaml` emission convention | `audit_manager.py._write_yaml_files()` |
| User-guide documentation update | `docs/user/user-guide.md` |

### 2.3 Asymmetric API capabilities the workstream relies on

EspoCRM exposes these read paths used by the audit; this workstream extends usage of each:

- `GET /api/v1/Metadata?key=scopes` — entity discovery (already used)
- `GET /api/v1/Metadata?key=entityDefs.{entity}` — entity metadata (already used)
- `GET /api/v1/Metadata?key=clientDefs.{entity}` — for filtered-tab custom-scope metadata (new use)
- `GET /api/v1/ReportFilter?where[entityType]=...` — for filtered-tab criteria (already in `list_report_filters`, new use in audit)
- `GET /api/v1/Role?maxSize=200` — roles (new method needed)
- `GET /api/v1/Team?maxSize=200` — teams (new method needed)

EspoCRM exposes these write paths used by the new deploy-side managers:

- `POST /api/v1/Role` and `PATCH /api/v1/Role/{id}` — for `role_manager`
- `POST /api/v1/Team` and `PATCH /api/v1/Team/{id}` — for `team_manager`

Per-entity access control on EspoCRM Role records is stored as a JSON map on the Role itself (the `data` field), so role manager is a single-record write with translated scope_access payload rather than a multi-endpoint dance.

---

## 3. Design Decisions Captured from Planning Kickoff

This section is the durable record of the four design decisions made in the planning conversation. Implementation prompts cite these decisions by number.

### Decision 1 — User records out of audit scope

**Resolved:** Option C — users are out of audit scope.

**Rationale.** The audit's identity is a YAML-round-trip tool. The v1.3 schema (Section 12) explicitly excludes user-to-role assignment from the deployment artifact. Adding user records as a non-YAML side artifact would shift the audit's product identity from "configuration capture" to "configuration plus data snapshot" without a current operational driver. If user-roster visibility becomes important later, it can be a separate feature without disrupting the audit.

**Consequence for the workstream.** No new `GET /User` method on `api_client.py`. No `users.json` artifact. No user records inserted into the client database.

### Decision 2 — Roles and teams: audit + deploy in the same workstream

**Resolved:** Option B — roles and teams are audited AND deployed in this same workstream.

**Rationale.** Auditing without deploy-side support would produce half-round-trip YAML (security blocks describe roles but Configure can't apply them). Three alternatives were considered: silent no-op on unknown top-level keys (rejected — misleading), NOT_SUPPORTED treatment like saved views / duplicate checks / workflows (rejected as a fallback only), and deferring security entirely (rejected — Doug wants to resolve both sides). Bundling deploy-side managers into the audit workstream produces a coherent round-trip-clean feature at workstream end.

**Consequence for the workstream.** New `role_manager.py` and `team_manager.py` modules following the existing CHECK→ACT pattern. New `RoleDefinition` and `TeamDefinition` dataclasses in `models.py`. New `roles:` / `teams:` recognition in `config_loader.py`. New pipeline step in `run_worker.py` orchestration. The audit half captures and emits; the deploy half applies.

### Decision 2.5 — All five parts of Section 12 in scope, including role-aware visibility

**Resolved:** Option A — all five parts of Section 12 (12.1 Roles, 12.2 Teams, 12.3 Scope Access, 12.4 System Permissions, 12.5 Role-Aware Visibility) plus 12.6 Deploy Ordering are in scope for this workstream.

**Rationale.** Doug elected to resolve security comprehensively in one workstream rather than stage 12.5 to a follow-up. Section 12.5 is structurally different work — it extends `condition_expression.py` with a new leaf clause variant, threads role predicates through the existing dynamic-logic validators, and adds role-resolution to the audit's reverse-engineering of EspoCRM's logic clauses — but bundling it now avoids re-opening the security workstream later and produces complete v1.3 schema coverage for security in one shot.

**Consequence for the workstream.** The series grows by roughly four prompts to cover 12.5. `condition_expression.py` gets a new `role:` leaf clause. Validators thread it. Audit reverse-engineering picks up role-aware clauses from EspoCRM's clientDefs/entityDefs dynamic-logic JSON.

### Decision 3 — Entity picker uses pre-flight live discovery

**Resolved (routine draft):** Pre-flight live discovery. When the user opens the Audit dialog, the dialog runs `get_all_scopes()` against the source instance and shows the live result.

**Rationale.** A single API round trip adds 1–2 seconds to dialog open. The alternative (caching the prior audit's entity list in the client DB with manual refresh affordance) trades freshness for a marginal speedup and requires schema, invalidation logic, and a manual-refresh UX — none of which is justified.

**Consequence for the workstream.** No new client DB schema for cached entity lists. The picker UI in `audit_entry.py` calls `client.get_all_scopes()` synchronously (or via a brief worker) when the dialog opens.

---

## 4. Workstream Design — v1.2 Audit Feature End-to-End

This section describes what the v1.2 audit feature does, end-to-end, from the operator's perspective. Implementation details are in §5.

### 4.1 Operator flow

1. Operator selects a source instance from the Audit sidebar entry's instance picker (existing v1.1 behavior).
2. Operator clicks "Configure Audit" (renamed from current "Start Audit" button to make the options dialog more discoverable).
3. The options dialog opens. On open, it calls `get_all_scopes()` against the source instance and populates a scrollable entity-picker list with checkboxes. By default, all entities are selected. The operator can deselect entities they don't want audited, or use "Select All" / "Select None" buttons.
4. Below the entity picker, the existing category-level checkboxes remain: detail layouts, list layouts, relationships, native fields. New checkboxes are added: **Filtered tabs**, **Security (roles, teams, role-aware visibility)**. Both new checkboxes default to checked (§9.3).
5. Operator clicks "Run Audit". If the output directory contains files matching the audit emission pattern from a prior run — `*.yaml` at root or `security/*.yaml` under the subdirectory — the dialog displays an overwrite-confirmation prompt ("Output directory contains N existing audit YAML files; running this audit will overwrite them. Proceed?") and waits for the operator to confirm or cancel before opening the progress dialog (§9.4).
6. The progress dialog opens and the audit worker runs the pipeline.
7. The pipeline runs entity discovery (filtered to selected entities), field extraction, layout extraction, relationship discovery, filtered-tab discovery (if enabled), role and team discovery (if enabled).
8. YAML files are written to the audit output directory. Per-entity YAMLs sit at the program root and include their entity blocks plus the new `filteredTabs:` blocks if any. A separate `security.yaml` is written to `<output_dir>/security/security.yaml` (created if missing) when security was enabled and any roles or teams were found.
9. Database records are inserted (existing v1.1 behavior, extended to cover new dataclasses).
10. Progress dialog shows a summary: files written, records inserted, any warnings (including the §9.2 informational warning for any captured role with empty `scope_access:`).

### 4.2 v1.2 audit scope summary

| Object | Captured | YAML form |
|---|---|---|
| Custom entities (v1.1) | Yes, filtered by entity picker | Per-entity YAML |
| Custom fields on native entities (v1.1) | Yes, filtered by entity picker | Per-entity YAML |
| Detail layouts (v1.1) | Yes, filtered by entity picker | Per-entity YAML |
| List layouts (v1.1) | Yes, filtered by entity picker | Per-entity YAML |
| Relationships (v1.1) | Yes, filtered by entity picker | Per-entity YAML |
| **Filtered tabs (v1.2)** | Yes, filtered by entity picker | Per-entity YAML (`filteredTabs:` block) |
| **Roles (v1.2)** | Yes, all-or-nothing | `security.yaml` (`roles:` block) |
| **Teams (v1.2)** | Yes, all-or-nothing | `security.yaml` (`teams:` block) |
| **Role-aware visibility (v1.2)** | Yes, captured inline with field/panel `requiredWhen` / `visibleWhen` | Per-entity YAML |
| User records | **No** (Decision 1) | — |

### 4.3 Deploy-side capability summary

| Object | Deploy support | Module |
|---|---|---|
| Custom entities (existing) | Yes | `entity_manager.py` |
| Fields, layouts, relationships (existing) | Yes | `field_manager.py`, `layout_manager.py`, `relationship_manager.py` |
| Entity settings, duplicate checks, saved views, email templates, workflows (existing v1.1 schema, partial deploy) | Mixed (NOT_SUPPORTED for some) | various managers |
| Filtered tabs (existing) | Yes | `filtered_tab_manager.py` |
| **Roles (v1.2)** | Yes (new) | `role_manager.py` (new module) |
| **Teams (v1.2)** | Yes (new) | `team_manager.py` (new module) |
| **Scope access, system permissions (v1.2)** | Yes (new) | Part of `role_manager.py` payload translation |
| **Role-aware visibility (v1.2)** | Yes (new) | `condition_expression.py` extension; validator + existing managers thread through |

---

## 5. Prompt Series Plan

The implementation is broken into 11 Claude Code prompts. Each prompt is self-contained: it states its dependencies on prior prompts, what files it touches, what it produces, and how to verify it green. Prompts run sequentially; Doug reviews and confirms each before the next is written.

### Prompt A — `roles:` / `teams:` recognition + raw-passthrough dataclasses

**Depends on:** none (first in series)

**Adds:**
- `config_loader.py` recognizes `roles:` and `teams:` as valid top-level keys
- `config_loader.py`'s program-directory scan is extended to also scan `<program_dir>/security/*.yaml` in addition to root `*.yaml`. Files in the `security/` subdirectory are loaded with the same parser; the subdirectory is conventional for security-related YAMLs but the parser does not require any specific filename
- `models.py` adds `RoleDefinition` and `TeamDefinition` dataclasses with raw-passthrough fields for `scope_access_raw`, `system_permissions_raw` (mirroring how `saved_views_raw` and `workflows_raw` work today)
- `ProgramFile` gains `roles: list[RoleDefinition]` and `teams: list[TeamDefinition]` collections
- Hard-reject for malformed structures (missing `name:`, wrong types) per existing validator patterns

**Does NOT add:**
- Structured parsing of `scope_access:` or `system_permissions:` (Prompt B)
- Any deploy-side execution (Prompts C and D)

**Validation:**
- A test YAML with valid `roles:` and `teams:` blocks loads cleanly with all top-level fields populated
- A test YAML with a role missing its `name:` produces a clear validation error
- A `security.yaml` placed under `<program_dir>/security/` loads via the extended scan and produces the same parsed result as if it were at root (subdirectory placement is a convention, not a parsing dependency)
- All existing tests pass (no regression on existing schema)

**End state:** Loader and models recognize roles and teams; no deploy effect yet.

### Prompt B — Structured `scope_access:` and `system_permissions:` parsing

**Depends on:** Prompt A

**Adds:**
- New `ScopeAccess` dataclass per role.entity (Section 12.3): `entity_name`, `read`, `edit`, `delete`, `stream`, `assignmentPermission`, `recordAccessControl` fields
- New `SystemPermissions` dataclass per role (Section 12.4): the v1.3 enumeration of system-level permission keys
- `RoleDefinition.scope_access: dict[str, ScopeAccess]` and `RoleDefinition.system_permissions: SystemPermissions`
- Validators for: scope_access entity name resolves against batch + server state (deferred until Prompt E for full topological behavior); permission values from the v1.3 enumeration

**Does NOT add:**
- The 12.5 `role:` leaf clause (Prompt F)

**Validation:**
- Section 12 examples in `app-yaml-schema.md` parse and roundtrip through the loader cleanly
- Invalid scope_access values (unknown action, unknown entity, etc.) produce specific error messages

**End state:** Full v1.3 Section 12.1–12.4 structure is parsed and validated; still no deploy effect.

### Prompt C — `team_manager.py` deploy-side

**Depends on:** Prompt A

**Adds:**
- `espo_impl/core/team_manager.py` — CHECK→ACT pattern matching the existing managers
- `api_client.py` gets `get_teams()`, `create_team()`, `update_team()` methods
- Status enum: `TeamStatus` in `models.py` (OK, CREATED, UPDATED, ERROR)
- `TeamResult` in `models.py`

**Validation:**
- A YAML declaring a new team can be applied to a target instance; subsequent re-runs are idempotent
- A YAML modifying an existing team's description updates the existing record without creating a duplicate
- Team deletion is out of scope per the existing managers' conservative-deletion convention; document this

**End state:** Teams round-trip cleanly between YAML and target.

### Prompt D — `role_manager.py` deploy-side

**Depends on:** Prompts B and C

**Adds:**
- `espo_impl/core/role_manager.py` — CHECK→ACT pattern; this is the most substantive new module in the series
- `api_client.py` gets `get_roles()`, `create_role()`, `update_role()` methods
- `RoleStatus` and `RoleResult` in `models.py`
- The scope_access translation layer: maps YAML `scope_access:` blocks to EspoCRM Role record's `data` field shape (per-entity-per-action permission matrix with assignment scope)
- System permissions translation: maps YAML `system_permissions:` keys to EspoCRM Role record's top-level permission columns

**Validation:**
- A test role with scope_access on three entities applies cleanly; the deployed EspoCRM Role record has the correct per-entity permissions
- Re-running the same YAML is idempotent (CHECK passes, no spurious updates)
- Modifying a scope_access value in YAML and redeploying updates the existing role
- A role referencing a non-existent entity in scope_access produces a clear error before any API write

**End state:** Roles round-trip cleanly; full v1.3 Section 12.1–12.4 is deployable.

### Prompt E — Section 12.6 Deploy Ordering and security pipeline step

**Depends on:** Prompts C and D

**Adds:**
- A new pipeline step "Security" in `run_worker.py._run_full()`, ordered after Workflows per the existing orchestration sequence
- The step calls `team_manager` first (teams have no dependencies), then `role_manager` (roles reference entity names that must exist on the target)
- Dependency resolution: within a batch, security YAMLs are processed last regardless of filename alphabetical position
- Updated `STEP SUMMARY` block to include security step status

**Resolves a known interaction:** The existing engine-bug backlog notes that the deploy engine processes files in alphabetical order rather than topological order. Adding security requires ordering security YAMLs last because they reference entity names. This prompt does not solve the general topological-sort problem (still backlog), but it adds a special-case for security files — they always run last.

**Validation:**
- A batch containing entity YAMLs and a security.yaml deploys cleanly regardless of filename alphabetical position
- A security YAML referencing an entity not in the batch and not on the server produces a clear error (rather than a confusing HTTP error from the API)

**End state:** Security YAMLs deploy in the correct order alongside the rest of a domain batch.

### Prompt F — `role:` leaf clause variant in `condition_expression.py`

**Depends on:** Prompt A

**Adds:**
- `condition_expression.py` gets a new leaf clause variant for `role:` predicates (Section 12.5.1)
- AST: `RoleClause` joining the existing `LeafClause`, `AllNode`, `AnyNode` set
- `parse_condition()` recognizes `role:` keys at the leaf level
- `validate_condition()` accepts an optional `known_roles: set[str]` parameter; if provided, role names in clauses are validated against it
- `evaluate_condition()` is not extended for roles at this time (role-aware evaluation requires current-user context, which the deploy engine doesn't have; validators ensure clauses are well-formed but actual evaluation happens in the target CRM)
- `render_condition()` emits role clauses in structured form

**Validation:**
- Round-trip: a YAML `requiredWhen:` with a `role:` predicate parses and renders correctly
- Compound clauses mixing role and record-state predicates parse correctly
- Invalid role names (when `known_roles` is provided) produce specific errors

**End state:** The dynamic-logic parser knows about role clauses; validators thread them through; no evaluation behavior change.

### Prompt G — Section 12.5 wiring: role-aware field and panel visibility, role-scoped layouts

**Depends on:** Prompts D, F

**Adds:**
- `config_loader.py` validates that `requiredWhen` / `visibleWhen` clauses with `role:` predicates reference roles declared in the program batch
- `field_manager.py` and `layout_manager.py` translate role-aware clauses into EspoCRM's dynamic-logic JSON when writing to the target
- Layout-level `forRoles:` scoping (Section 12.5.2) is implemented as a layout-set selector at deploy time
- Validator cross-checks: every role referenced in any condition expression must exist in the batch's `roles:` block or on the target instance

**Validation:**
- A YAML with a field `requiredWhen` clause referencing the Mentor role deploys correctly; on the target, the field's dynamic logic includes the role-aware condition
- A layout with `forRoles: [Mentor Administrator]` deploys only to that role's effective layout
- A field with a role clause referencing an undeclared role produces a clear pre-deploy error

**End state:** Full v1.3 Section 12.5 (role-aware visibility) is deployable.

### Prompt H — Audit-side: `_discover_roles()`, `_discover_teams()`, role-aware logic reversal, `security.yaml` emission

**Depends on:** Prompts A–G (all schema and deploy work)

**Adds:**
- `audit_manager.py` gains `_discover_roles()` and `_discover_teams()` methods using new `get_roles()` / `get_teams()` API client methods
- New `RoleAuditResult` and `TeamAuditResult` dataclasses
- `_reverse_dynamic_logic()` is extended to recognize and emit `role:` leaf clauses when it sees EspoCRM's role-aware dynamic-logic JSON shape
- `_write_yaml_files()` writes a separate `security.yaml` to `<output_dir>/security/security.yaml` (creating the subdirectory if missing) containing the `roles:` and `teams:` blocks when security was captured and any results exist
- `_write_yaml_files()` also emits the §9.2 informational warning to the audit log for any captured role with empty `scope_access:`
- `AuditOptions.include_security: bool` (default True, per §9.3) controls whether the discovery runs
- New `_client_v4` migration in `automation/db/migrations.py` adds role and team tables to the client schema, following the existing `_client_v1` through `_client_v3` pattern (versioned migration runner with `schema_version` table). `audit_db.py` inserts role and team records into those tables.

**Validation:**
- An audit against a source with three roles and two teams produces `security.yaml` with the correct content; re-running deploy on the target reproduces the same role and team records
- A source field with a role-aware `requiredWhen` clause is captured with the role predicate intact
- A captured role with empty `scope_access:` produces an informational warning in the audit log; the YAML output still contains the role
- Audit run with the Security option unchecked produces no `security.yaml` and no role/team DB records

**End state:** Full v1.3 Section 12 round-trip is operational; audit can read what the deploy engine can write.

### Prompt I — Filtered-tab audit capture

**Depends on:** Prompt H (sequencing only — no logical dependency, but easier to slot after the security work is done)

**Adds:**
- `audit_manager.py` gains `_discover_filtered_tabs()`, called after relationship discovery
- New `FilteredTabAuditResult` dataclass
- Reverse-engineering walks both halves of the pattern: for each audited entity, query `list_report_filters(entity)` (existing method) for Report Filter records, and read `clientDefs.{entity}` metadata to identify any custom scope tabs binding to those filters
- YAML emission slots into each entity's existing `filteredTabs:` block in the per-entity YAML
- `AuditOptions.include_filtered_tabs: bool` (default True, per §9.3)
- The `_client_v4` migration from Prompt H is extended to add the filtered-tab table (one migration covers all v1.2 audit schema additions). `audit_db.py` inserts filtered-tab records into that table.

**Validation:**
- An audit against a source with two filtered tabs (one per entity) produces YAML entity blocks each containing one correct `filteredTabs:` entry
- Re-deploying the audited YAML against a fresh target reproduces both filtered tabs (assuming Advanced Pack is present)
- Audit run with the Filtered tabs option unchecked produces no filtered-tab DB records and no `filteredTabs:` blocks in YAML

**End state:** Filtered tabs round-trip cleanly through audit and deploy.

### Prompt J — Entity-picker UI and `AuditOptions.selected_entities`

**Depends on:** none (UI work, independent of schema work) — slotted late for sequencing convenience

**Adds:**
- `AuditOptions.selected_entities: set[str] | None` (default None = all, preserving current behavior)
- `_discover_entities()` is extended: after fetching all scopes, filter to those in `selected_entities` if not None
- `audit_entry.py` gains a pre-flight discovery step on dialog open: calls `client.get_all_scopes()` synchronously (with a brief loading state), populates a scrollable entity-picker `QListWidget` with checkboxes, default all checked
- "Select All" / "Select None" buttons above the picker
- The picker integrates with the existing category checkboxes (entity picker says "which entities", category checkboxes say "what aspects of those entities")
- New checkboxes added: "Filtered tabs", "Security (roles, teams, role-aware visibility)", both default-checked per §9.3
- An overwrite-confirmation dialog (§9.4) fires when the operator clicks Run Audit and the output directory contains files matching the audit emission pattern. The trigger condition matches `*.yaml` at root OR `security/*.yaml` under the subdirectory. Default focus on Cancel; operator must explicitly confirm to proceed.

**Validation:**
- Selecting two entities out of ten in the picker results in only those two entities being audited end-to-end
- Selecting "Select None" disables the Run button (no work to do)
- Pre-flight discovery failure (network error, auth error) shows a clear error in the dialog without crashing it
- Clicking Run Audit against an output directory containing prior audit output displays the overwrite-confirmation dialog; Cancel returns to the options dialog without writing anything; Proceed continues normally
- Clicking Run Audit against an empty output directory proceeds without the confirmation dialog

**End state:** Operator can audit a precisely-chosen subset of entities.

### Prompt K — Documentation: `feat-audit.md` v1.2 and user-guide updates

**Depends on:** Prompts A–J (all functional work)

**Adds:**
- `PRDs/product/features/feat-audit.md` bumped from v1.1 to v1.2 with new sections covering entity-level selection, filtered-tab audit, and full Section 12 security round-trip
- `docs/user/user-guide.md` updated section on Audit feature with new screenshots and option descriptions
- Updated entries in `CLAUDE.md` describing the new managers, dataclasses, and pipeline step

**Validation:**
- `feat-audit.md` v1.2 accurately describes the shipped feature (read against the actual code, not against this planning doc)
- User-guide steps reproduce successfully against a test instance

**End state:** Documentation reflects the v1.2 feature.

---

## 6. End State at Workstream Completion

After Prompt K, the CRM Audit feature is at v1.2 with the following properties:

- Operators can audit a precisely-chosen subset of entities on a source instance (Prompt J)
- Filtered tabs are captured by the audit and deployable from the resulting YAML (Prompts I and existing `filtered_tab_manager.py`)
- The full v1.3 schema Section 12 — roles, teams, scope access, system permissions, role-aware visibility, deploy ordering — is implemented end-to-end: paper-only no more (Prompts A–H)
- User records remain out of audit scope (Decision 1, Option C)
- The audit's existing v1.1 capabilities (entity discovery, field extraction, layout extraction, relationship discovery) are preserved with no regression

---

## 7. Out of Scope (Deferred to Future Workstreams)

- **Section 12.7 field-level permissions and permission presets** — explicitly deferred in the schema doc to v1.4 or later; not in this workstream
- **User records audit** — Decision 1, Option C; if needed later, it's a separate "CRM Instance Inspector" feature
- **General topological deploy ordering for non-security cross-file dependencies** — known backlog item; Prompt E adds a security-specific special case but does not solve the general problem
- **Validator-server-state for cross-batch field references** — known backlog item; not addressed here
- **Saved views, duplicate checks, workflows deploy resurrection** — these remain NOT_SUPPORTED until a separate workstream prioritizes their REST-capable reimplementations
- **Audit support for entity settings, email templates, formula fields beyond what v1.1 already captures** — extending audit to cover the full v1.1 schema additions is a separate workstream

---

## 8. Known Interactions and Risks

### 8.1 Topological deploy ordering for security

Section 12.6 specifies that security YAMLs must deploy after the entity YAMLs they reference. Prompt E adds a special-case ordering rule for security files. The general topological-sort problem remains unsolved in the backlog (known issue: "Deploys process files in alphabetical order, not topological order based on relationship dependencies"). If the general fix lands first, Prompt E's special case becomes a no-op; if Prompt E lands first, the general fix later replaces this special case with a uniform mechanism.

### 8.2 Role-clause evaluation context

`condition_expression.py`'s `evaluate_condition()` is not extended for role clauses (Prompt F). The validator checks clauses are well-formed; actual role-aware evaluation happens in the target CRM at runtime based on current-user context. This is the correct boundary — the deploy engine doesn't have a current user. The risk: if a future feature wants to simulate role-aware visibility during validation (e.g., "show me what the form looks like to a Mentor"), `evaluate_condition()` would need an extended signature. Out of scope for this workstream.

### 8.3 EspoCRM Role data shape

The scope_access translation in Prompt D maps YAML's relatively clean entity-scoped permission model to EspoCRM's `data` JSON field shape. EspoCRM's shape has been observed to vary across versions. Prompt D should target the current EspoCRM 9.x shape and document the version assumption; if the shape changes in a future EspoCRM major version, this manager needs adjustment.

### 8.4 Advanced Pack dependency for filtered tabs

Filtered tabs require EspoCRM's Advanced Pack (the same dependency as existing `filtered_tab_manager.py`). Audit-side discovery of Report Filter records returns HTTP 404 when Advanced Pack is not installed; Prompt I treats this as "no filtered tabs to capture" and continues gracefully.

### 8.5 Workstream size

11 prompts is on the higher end of the project's prompt-series scale (the v1.1 schema series was 8 prompts, A–H). Prompts D and G are the most substantive; the series may be reshaped if any individual prompt grows too large to execute as a single Claude Code session.

---

## 9. Resolved Design Questions

These items were open at v1.0 with provisional answers. v1.1 records the resolutions reached in the planning conversation continuation on 05-23-26. Implementation prompts cite these resolutions by number.

### 9.1 — `persona:` field is documentation metadata only

**Resolved:** No validation. The loader does not cross-check `persona:` values against any source; the audit captures whatever the source instance carries and emits it as-is.

**Rationale.** Schema Section 12.1 is explicit that `persona:` is documentation metadata. Cross-checking it would require a source-of-truth list of Master PRD personas, which doesn't live anywhere the loader has access to and would couple the loader to client-specific PRD content. The failure mode of a typo'd persona name is "documentation reader briefly confused" — not severe enough to justify the validation infrastructure or the coupling.

**Consequence for the workstream.** No persona-validation logic in `config_loader.py`. No new dependency from the loader on any client-specific document list. Prompts A, B, and D treat `persona:` as opaque metadata.

### 9.2 — Empty `scope_access:` on captured roles produces an informational warning

**Resolved:** Yes, informational warning in the audit log, not in the YAML output. When a captured role has no per-entity access, the audit log records a line of the form "Role X has no scope_access; this role grants no entity access on the source instance." The YAML output itself is unaffected — the role is emitted with whatever its source state was.

**Rationale.** Matches the existing audit log pattern for analogous edge cases (e.g., entity with no custom fields). Gives operators visibility into "this role grants nothing on the source and probably wants cleanup" without altering the audited content.

**Consequence for the workstream.** Prompt H's `_write_yaml_files()` emits the warning. No effect on the loader, the validator, or the deploy side — a role with empty `scope_access:` is a valid YAML construct that deploys as written.

### 9.3 — `include_security` and `include_filtered_tabs` default to True

**Resolved:** Default True. Both new checkboxes in the Audit dialog start checked. Operators opt out by unchecking.

**Rationale.** The existing `AuditOptions` defaults are all True; the audit's identity is "capture the full configuration of a source instance for round-trip deploy." A default-off new capability is a quiet inconsistency in that identity and has a bad failure mode (operators who never notice the new checkboxes get half-audits indefinitely). The "default-off avoids surprising operators" reasoning that produced the v1.0 provisional answer was overcautious for the actual operator situation: Doug is effectively the sole operator and will read the v1.2 release notes.

**Consequence for the workstream.** Prompts H, I, and J use `default=True` for the new `AuditOptions` booleans. Documentation in Prompt K notes the new default behavior. First v1.2 audit run after the workstream lands produces `security.yaml` and `filteredTabs:` blocks automatically; this is a one-time behavior change and is called out in the user guide update.

### 9.4 — Overwrite existing audit output with a pre-run confirmation guard

**Resolved:** Overwrite, with a one-line UX guard. When the operator clicks Run Audit and the output directory contains files matching the audit emission pattern (per-entity YAMLs or `security.yaml`), the dialog displays a confirmation prompt: "Output directory contains N existing audit YAML files; running this audit will overwrite them. Proceed?" The operator confirms or cancels. Empty output directories run without the prompt.

**Rationale.** Audited YAML is a snapshot, not source code. An audit run is the operator's explicit request to capture the current state of the source instance. Hand-editing audit output is an anti-pattern; the right place to fork audit output is into a separate working directory under the operator's control. But the audit itself doesn't enforce or document that, so the confirmation guard catches the lost-edits failure mode for a one-line UX cost. The merge option was rejected on maintenance grounds (diffing structural YAML is fragile across schema evolution); the alongside option was rejected because two YAML versions of the same entity coexisting in the same program root creates real deploy ambiguity.

**Consequence for the workstream.** Prompt J implements the confirmation dialog as part of the UI work. The dialog's trigger condition matches `*.yaml` at the output directory root OR `security/*.yaml` under the subdirectory — this uniformly covers entity YAMLs and the security YAML wherever it lives. Dialog default focus on Cancel; Proceed requires an explicit click.

---

## 10. Status — Prompt A Unblocked

As of v1.2, all four §9 design questions and the `security.yaml` placement question are resolved, and the two corrections (Alembic→`_client_v4` migration, overwrite-confirmation dialog) are folded into the relevant prompts. The doc is the design authority for Prompt A. The §9 resolutions and the placement decision are recorded as formal governance records under SES-060 (DEC-178 through DEC-182). The PI-024 prior-workstreams backfill conversation ran concurrently with this resolution conversation and claimed SES-059 first (DEC-175 through DEC-177); this session rebased to SES-060 / DEC-178 through DEC-182 to clear the collision.

The next step is writing **Prompt A** (`CLAUDE-CODE-PROMPT-audit-v1.2-A-roles-teams-recognition.md`) as the first implementation deliverable. Each subsequent prompt is written after the prior is confirmed green by Doug running it through Claude Code locally.

One workflow question is deliberately not captured in this document because it's about how to execute the design, not what the design is:

- **Series-size mitigation (§8.5).** Whether to pause at Prompt E for a deploy-side validation milestone before starting Prompts F–K is a workflow choice for Doug to make at execution time. The doc neither requires nor forbids the pause.
