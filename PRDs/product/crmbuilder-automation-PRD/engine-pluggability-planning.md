# Engine Pluggability Architecture — Planning Document

**Document type:** Application development planning (planning only; not implementation)
**Repository:** `crmbuilder`
**Path:** `PRDs/product/crmbuilder-automation-PRD/engine-pluggability-planning.md`
**Last Updated:** 04-30-26 24:30
**Version:** 1.0 (initial draft)

---

## Status

This document is a **planning artifact** for engine pluggability architecture in the CRM Builder Automation app, with Attio CRM as the first concrete engine to validate the architecture. It is not implementation; it is the document that informs the Claude Code prompt series that will execute the implementation. Per Doug's working pattern, planning before prompting.

The work this document covers is anticipated to take a multi-prompt series (likely 8–14 prompts) extending across multiple work sessions. This document is the design authority for that series.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 04-30-26 24:30 | Doug Bower / Claude | Initial planning document. Surveys current architecture, defines the engine abstraction, plans the work series with Attio as first concrete engine. |

---

## Change Log

**Version 1.0 (04-30-26 24:30):** Initial creation. Documents the motivation for the work (multi-deploy unblocked); surveys the current EspoCRM-coupled architecture and the partial pluggability scaffolding already present; defines the engine abstraction layer (protocol/interface, dispatch mechanism, schema migration); plans Attio as first concrete engine and notes Attio-specific constraints (Pro+ plan requirement for custom objects, OAuth 2.0 vs. API key auth, no installer step for SaaS-only platforms); proposes a 12-prompt implementation series; flags open questions that should be resolved before the first prompt.

---

## 1. Motivation

This planning work responds to the strategic decision to expand CRM Builder's deployment target pool from EspoCRM-only to a broader set including Tier 1 SaaS CRMs (Attio, HubSpot) alongside open-source options (EspoCRM, and potentially CiviCRM and SuiteCRM later).

The decision was made in the context of the methodology evolution research recorded at `PRDs/process/research/evolved-methodology/`. Step 9 of that research (the CBM redo final findings, committed 04-30-26) identified multi-deploy as a structural blocker for the methodology evolution effort and as a feature whose delivery requires the deployment infrastructure to actually exist for multiple CRMs. The strategic decision was that the next CRM should be Attio (technical tractability via API-first design), with HubSpot to follow.

Beyond the methodology research, multi-deploy has standalone product value. CRM Builder's value proposition — *"declarative deployment of CRM configuration from YAML; deploy your real processes on candidates you're actually evaluating"* — is meaningfully stronger when the candidates include CRMs clients are actually shopping for. EspoCRM is a defensible niche choice but does not represent the broader market. Attio and HubSpot are. Adding them brings CRM Builder into the conversation for the broader market.

This document is the planning step that precedes implementation work. It exists to answer: what architecturally needs to change, what should be built first, and what work series accomplishes it.

---

## 2. Current Architecture Survey

This section captures what exists in the repository as of commit `f48b3cb` (the current `main` HEAD as of this document's creation). The survey informs the architecture design in §3.

### 2.1 Top-level structure

The repository organizes deployment-related code into two sibling directories:

- **`automation/`** — the application layer. Contains UI, database schemas, deployment orchestration, importers, document generation, and all client-facing concerns.
- **`espo_impl/`** — the EspoCRM engine implementation. Contains the EspoCRM-specific API client, configuration loaders, managers (field, entity, relationship, workflow, layout, etc.), workers, and EspoCRM-specific UI panels.

The naming convention `espo_impl` (with `_impl` suffix) signals that this directory is the EspoCRM-specific implementation — implicitly suggesting that other engine implementations would live in parallel directories (e.g., `attio_impl/`, `hubspot_impl/`).

### 2.2 What's already pluggability-aware

Several pieces of existing code anticipate multi-platform support:

- **YAML schema's design intent is platform-agnostic.** `PRDs/product/app-yaml-schema.md` §1 states: *"YAML program files are the single source of truth for CRM configuration. They are CRM-agnostic at the requirements level and are translated into platform-specific API calls at deployment time."* The schema speaks in entities, fields, layouts, workflows, duplicate checks — all platform-portable concepts.
- **Database `crm_platform` columns.** Both `Client.crm_platform` (in `automation/db/master_schema.py`) and `DeploymentRun.crm_platform` (in `automation/db/client_schema.py`) carry a CHECK constraint currently single-valued at `'EspoCRM'` but documented (DEC-075) as enumerating the supported platform list. Adding new platforms requires expanding the constraint, not adding a column.
- **`SUPPORTED_PLATFORMS` constant.** `automation/core/deployment/wizard_logic.py` declares `SUPPORTED_PLATFORMS: list[str] = ["EspoCRM"]` with an explicit comment: *"v1: EspoCRM only; structured for future expansion."* The list-typed constant is ready to expand.
- **`SUPPORTED_VERSIONS` dict.** `automation/core/deployment/connectivity.py` declares a dict keyed by platform name. Currently single-keyed (`{"EspoCRM": [...]}`), structurally ready for additional keys.
- **Manager pattern in `espo_impl/core/`.** Field, entity, relationship, workflow, layout, duplicate-check, saved-view, email-template, and tooltip managers exist as separate modules each owning a discrete schema concept. This decomposition maps cleanly to YAML schema sections and would be paralleled (with platform-specific implementations) in new engines.

### 2.3 What's NOT pluggability-aware

Several pieces of existing code are tightly coupled to EspoCRM:

- **`Instance` table has no engine type column.** Every row in the `Instance` table is implicitly EspoCRM. To support multi-engine, this table needs a new column (proposed: `crm_platform TEXT NOT NULL CHECK(...)`), and existing rows need to be backfilled with `'EspoCRM'`.
- **`automation/ui/deployment/` directly imports from `espo_impl/`.** Multiple files import EspoCRM-specific symbols: `EspoAdminClient`, `InstanceProfile`, `ConfigLoader`, `RunWorker`, `AuditWorker`, `AuditOptions`, `EntityAction`. Specifically:
  - `deployment_logic.py` lines 297–298: imports `EspoAdminClient` and `InstanceProfile` for connection testing
  - `instances_entry.py` lines 127–128: same imports for instance management
  - `audit_entry.py` lines 298, 310, 451: imports `AuditOptions`, `InstanceProfile`, `AuditWorker`
  - `configure_progress.py` lines 54, 189–190, 252: imports `EntityAction`, `ConfigLoader`, `InstanceProfile`, `RunWorker`
  - Several UI files import `enhance_table` from `espo_impl/ui/grid_helpers.py` (this last one is a shared UI utility, not engine-specific concern)
- **`InstanceProfile` model is EspoCRM-shaped.** `espo_impl/core/models.py` defines `InstanceProfile` with `auth_method` enum of `"api_key"` / `"hmac"` / `"basic"` — these are EspoCRM auth methods. Attio's Bearer token auth and HubSpot's OAuth do not map cleanly to this enum.
- **`automation/core/deployment/connectivity.py` checks for EspoCRM-specific API responses.** Lines 46–119 check connectivity by hitting EspoCRM's API and verifying the response shape. Cloud-hosted SaaS CRMs need different connectivity verification (an authenticated Bearer-token request rather than a basic-auth credential check).
- **`automation/core/deployment/ssh_deploy.py` is self-hosted-EspoCRM-specific.** This module SSHs into a server, runs the official EspoCRM installer, and verifies the EspoCRM login page. Cloud-hosted SaaS CRMs have no installer; the entire `ssh_deploy` flow is irrelevant for Attio and HubSpot.
- **EspoCRM-specific UI strings throughout the deployment wizard.** `automation/ui/deployment/deploy_wizard/wizard_dialog.py` contains hardcoded references to EspoCRM in user-facing strings (lines 247, 553, 559, 704, 723).
- **Deployment scenarios assume self-hosted as a category.** `SCENARIOS = ["self_hosted", "cloud_hosted", "bring_your_own"]` in `wizard_logic.py`. The "self-hosted" scenario is meaningless for SaaS-only platforms — Attio cannot be self-hosted at all. Either the scenario list needs to be platform-conditional, or platforms need to declare which scenarios they support.

### 2.4 Architectural verdict

CRM Builder's architecture is **partially structured for engine pluggability** — the directory naming convention, schema columns, version dicts, supported-platforms lists, and the YAML schema's explicit platform-agnostic intent all signal that pluggability was anticipated — but **not yet abstracted behind an engine interface**.

There is no `Engine` protocol, abstract base class, or dispatch mechanism. The `espo_impl` directory is the only engine; the deployment UI imports directly from it; there is no code path that says *"given platform X, dispatch to engine Y."*

This is actually a healthy starting point. The naming, schema, and constants provide the bones for pluggability; introducing the engine abstraction is a deliberate refactoring step rather than a fundamental restructuring. The Attio engine work cannot proceed without the abstraction, but the abstraction can be designed and introduced cleanly.

---

## 3. Engine Abstraction Design

This section defines the abstraction that engine pluggability requires. The proposal is conservative — introduce the minimum abstraction needed to support multiple engines, and let further refactoring follow as the second and third engines accumulate evidence about what the abstraction needs.

### 3.1 The engine protocol

A new module — proposed location `automation/core/engine/protocol.py` — defines a Python `Protocol` (or abstract base class) that engines implement. The protocol's surface area is the operations the deployment pipeline needs from an engine:

- **`test_connection(profile) -> tuple[bool, str]`** — verify the engine can reach and authenticate against the given instance profile. Returns success/failure plus a human-readable message. The current `EspoAdminClient.test_connection()` is the EspoCRM implementation of this; an Attio engine would have its own.
- **`load_program(yaml_path) -> ProgramFile`** — parse a YAML program file. Currently the EspoCRM-specific `espo_impl/core/config_loader.py` `ConfigLoader.load_program()` does this. The parsing itself is largely platform-agnostic (the YAML schema is portable), so much of the loading logic might end up in a shared layer rather than per-engine. This is worth examining during the refactor.
- **`apply_program(program, profile, options) -> RunResult`** — apply a program file to an instance, creating, updating, or removing entities, fields, layouts, workflows, etc. This is the heart of deployment. EspoCRM's implementation is in `espo_impl/core/` managers; Attio's would be in `attio_impl/core/`.
- **`audit_program(profile, options) -> AuditResult`** — read the current state of an instance and produce an audit document. EspoCRM's implementation uses `audit_manager.py`; Attio's would have its own.
- **`compare_programs(source_profile, target_profile, options) -> ComparisonResult`** — compare two instances. Currently this happens in EspoCRM-specific UI (`espo_impl/ui/crm_compare_window.py`). Whether this is per-engine or shared (with engines providing the data and a shared component doing the comparison) is a design question.
- **`supported_scenarios() -> list[str]`** — declare which deployment scenarios the engine supports. EspoCRM supports all three (`self_hosted`, `cloud_hosted`, `bring_your_own`). Attio supports only `bring_your_own` (the user already has an Attio workspace; we provision configuration into it). HubSpot would be similar to Attio.
- **`auth_methods() -> list[str]`** — declare which auth methods the engine supports. EspoCRM: `api_key`, `hmac`, `basic`. Attio: `bearer_token` (and `oauth_2` once OAuth flow is implemented). HubSpot: `oauth_2`, `private_app_token`.
- **`engine_metadata() -> EngineMetadata`** — declare engine name, display name, supported versions, default URL pattern, documentation links, etc. Used by the UI to render engine-specific text without hardcoding.

The protocol can grow — start with these and add as needed during the refactor.

### 3.2 Engine dispatch

A new module — proposed location `automation/core/engine/registry.py` — provides the dispatch mechanism. The registry maps platform names (`'EspoCRM'`, `'Attio'`, `'HubSpot'`) to engine instances. The application asks the registry for an engine by platform name, the registry returns the engine, the application calls protocol methods on the engine.

Existing call sites in `automation/ui/deployment/` that currently import directly from `espo_impl` are updated to:

1. Look up the engine via the registry using the active instance's `crm_platform` value
2. Call the protocol method on the returned engine

This is the main refactor. Each call site needs to be updated; the work scales with the number of call sites identified in §2.3 (six modules with direct `espo_impl` imports).

### 3.3 Schema changes

Several schema changes are required:

- **`Instance.crm_platform` column added.** New column with `CHECK (crm_platform IN ('EspoCRM', 'Attio'))` constraint (expanded as engines are added). Existing rows backfilled with `'EspoCRM'`.
- **`DeploymentRun.crm_platform` constraint expanded.** Currently `CHECK (crm_platform IN ('EspoCRM'))`; update to `CHECK (crm_platform IN ('EspoCRM', 'Attio'))`. Same applies as new engines are added.
- **`Client.crm_platform` constraint expanded.** Currently `CHECK (crm_platform IS NULL OR crm_platform IN ('EspoCRM'))`; update to expand the platform list.
- **Auth credentials may need engine-specific shape.** The current `Instance` table uses `username` and `password` columns. EspoCRM's auth model fits this. Attio's Bearer token is a single secret without a username equivalent; storing it in `password` works but is awkward. HubSpot's OAuth has tokens that refresh, which the current schema doesn't support. A future iteration may need an `auth_data` JSON column for engine-specific auth content; for now, the current columns can hold Attio's Bearer token (in `password`) with engine code knowing how to interpret it.

The schema work is one or two prompts in the series — focused, testable, with a clear migration path.

### 3.4 What the abstraction does NOT include

To keep the first iteration scoped:

- **No engine-specific UI components in the deployment tab.** The deployment UI is shared across engines. Where engine-specific UI is needed (e.g., the Attio OAuth flow, the EspoCRM SSH deployment wizard), the UI is conditional on the engine type rather than separately implemented.
- **No engine plugin system** (i.e., loading engines from external packages). Engines are first-class modules in the repository; new engines are added by writing the implementation directory and registering it.
- **No engine-version compatibility matrix.** Each engine declares its own supported versions; cross-engine version compatibility is not a concern at this iteration.
- **No automatic engine detection.** Connecting to an instance requires the user to declare what platform it is; the system does not probe an URL to determine whether it's an EspoCRM, Attio, or HubSpot instance.

---

## 4. Attio as First Concrete Engine

This section captures what's specific to building the Attio engine. Most of the engine abstraction work in §3 is engine-agnostic; the pieces here are Attio-specific.

### 4.1 Attio platform basics

(Verified via web search 04-30-26; subject to confirmation against current Attio docs at implementation time.)

- **REST API** at `https://api.attio.com/v2/`. OpenAPI/Swagger specs available.
- **Authentication.** Two options: (1) API key (Bearer token, scoped to a single workspace, configured with explicit scopes); (2) OAuth 2.0 (for integrations that need to authenticate on behalf of multiple users; requires Attio approval before publication). For CRM Builder's first Attio engine: API key is simpler and sufficient. OAuth can come later if needed.
- **Custom objects.** Available on Pro and Enterprise plans only. Free plan supports 3 objects total; Plus supports 5; Pro supports 12; Enterprise supports unlimited. The methodology's deployment value proposition depends on creating custom objects — meaning the Attio engine is really only useful on Pro+ plans or for engagements small enough to fit the standard objects.
- **Standard objects** are People, Companies, and (optional) Deals, Users, Workspaces. Custom objects are user-defined.
- **Attributes.** Each object has system-defined attributes plus user-defined attributes. Attribute types include text, number, select (single), multi-select, currency, date, person reference, record reference (links to other objects), etc.
- **Lists.** Lists aggregate records and can have their own attributes (per-list-entry attributes). Used for pipeline-style work.
- **Rate limits.** 100 read requests/sec and 25 write requests/sec; HTTP 429 on exceed with Retry-After header.
- **Python SDK** is officially supported (alongside TypeScript, .NET, Java, Go, PHP). Implementation can use the SDK rather than raw HTTP.

### 4.2 YAML schema → Attio mapping

The YAML schema's portability is what makes the Attio engine possible. Each YAML schema section has an Attio mapping:

- **Entities (YAML §5)** → Attio custom objects. Each entity in the YAML becomes a custom object in the workspace. Entity name → object name; entity description → object description.
- **Fields (YAML §6)** → Attio attributes. Field type maps to Attio attribute type. Most YAML field types have direct Attio equivalents (text, number, enum/select, multi-select, date, currency, link/relationship, boolean). Some may not have direct equivalents and need fallbacks.
- **Layouts (YAML §7)** → Attio record templates and view configuration. Attio's UI is more fluid than EspoCRM's panel-based layout; the mapping may be looser.
- **Relationships (entity links)** → Attio relationship attributes. Two-way relationships are first-class in Attio (the example in Attio docs is People.company ↔ Company.team).
- **Duplicate checks (YAML §5.5)** → Attio's Assert Records endpoint behavior, possibly combined with workflow rules.
- **Saved views (YAML §5.6)** → Attio lists with filters configured.
- **Email templates (YAML §5.7)** → not natively supported in Attio in the same way as EspoCRM. Likely requires Attio's automation features or external integration. May be deferred for the initial engine.
- **Workflows (YAML §5.8)** → Attio automations. Trigger events and actions need to be mapped; some may not have direct equivalents.
- **Calculated fields (YAML §6.1.3)** → Attio formula attributes. Likely supported for arithmetic and concat; aggregate may be more limited.
- **Conditional requirement / visibility (YAML §6.1.1, §6.1.2)** → Attio doesn't expose the same conditional-logic primitives as EspoCRM. May need to be approximated with multiple views or workflow rules. Worth investigating during implementation.

The mapping is mostly clean for entity-and-field schema. The places where YAML features don't have direct Attio equivalents (email templates, some workflow constructs, conditional logic) need explicit handling: either feature parity through workarounds, or graceful degradation with explicit warnings, or feature deferral.

### 4.3 Attio-specific architecture pieces

A new directory `attio_impl/` parallels `espo_impl/`:

- `attio_impl/core/api_client.py` — Attio REST API client (likely wrapping the official Python SDK)
- `attio_impl/core/config_loader.py` — load YAML and produce Attio-specific application plan (or share with espo_impl's loader if loading is platform-agnostic)
- `attio_impl/core/object_manager.py` — create/update/delete Attio custom objects
- `attio_impl/core/attribute_manager.py` — create/update/delete Attio attributes on objects
- `attio_impl/core/relationship_manager.py` — manage relationship attributes
- `attio_impl/core/list_manager.py` — manage lists (the closest thing to layouts)
- `attio_impl/core/workflow_manager.py` — manage Attio automations
- `attio_impl/core/engine.py` — the Attio engine class implementing the protocol from §3.1

The directory parallels `espo_impl/core/` deliberately — same manager pattern, same separation of concerns. The interfaces will differ where Attio's data model differs from EspoCRM's, but the structural shape is the same.

### 4.4 Attio-specific UI

Most of the deployment UI is shared (the engine abstraction in §3 ensures this). Attio-specific UI is minimal:

- **Engine selection** in the new instance dialog (when adding an Attio instance, the user selects "Attio" as the platform)
- **API key entry** (different label and help text than EspoCRM's username/password)
- **Workspace identification** (Attio API keys are workspace-scoped; the UI may need to show which workspace the instance is connected to)
- **No SSH/installer flow.** When the deployment scenario is `self_hosted` or `cloud_hosted` (which are EspoCRM-only), those paths are not exposed for Attio. Only `bring_your_own` is available — meaning the user has an existing Attio workspace and we provision configuration into it.

### 4.5 Constraints and limits

- **Attio Pro+ plan required for full schema fidelity.** Custom objects are gated behind Pro plans. For free or Plus plans, the Attio engine can deploy a limited subset (using only standard objects) but cannot deploy a full custom-entity schema. The engine should detect this and report it clearly rather than fail mysteriously.
- **API rate limits.** 100 read/sec and 25 write/sec. For typical CRM Builder deployments (modest entity counts, modest field counts), this is comfortably above the rate the application would generate. For very large schemas, batching and exponential backoff may be needed.
- **Custom object slug constraints.** Attio object slugs (URL-safe identifiers) cannot be changed once set. Once an object is created, its slug is permanent. This means renaming is not idempotent — care needed.
- **Some YAML features have no Attio equivalent.** Per §4.2 — email templates, some workflow primitives, some conditional logic. Initial Attio engine should have explicit "not supported on Attio" handling for these features rather than silent failure.

### 4.6 Attio API terms of service

Per `pattern-library-specification.md` §6.4 and the methodology research, commercial CRM APIs raise legal questions that open-source CRMs don't. Attio's developer terms of service govern what integrations can do. Before building the engine, verify:

- Provisioning custom objects and attributes via API is in scope for the developer terms
- Programmatic configuration changes are not subject to additional restrictions
- Distribution of CRM Builder (which calls Attio's API on behalf of users) is acceptable use

This is a small piece of work but it should not be skipped. A 30-minute review of Attio's developer terms before writing engine code is appropriate.

---

## 5. Proposed Implementation Series

This section proposes the Claude Code prompt series that delivers the engine abstraction and the Attio engine. The series is sequenced so that each prompt produces working, testable code with a clean fallback if a later prompt fails.

### 5.1 Phase 1 — Engine abstraction (prompts A–D)

**Prompt A — Engine protocol and registry.** Create `automation/core/engine/protocol.py` with the `Engine` protocol and `EngineMetadata` dataclass. Create `automation/core/engine/registry.py` with the registry mechanism. No engine implementations yet. Tests for the registry.

**Prompt B — Schema migration for `Instance.crm_platform` column.** Add `crm_platform` column to `Instance` table with `CHECK (crm_platform IN ('EspoCRM'))` constraint. Backfill existing rows with `'EspoCRM'`. Update `Instance` row models in `automation/ui/deployment/deployment_logic.py`. Update tests.

**Prompt C — EspoCRM engine adapter.** Create `automation/core/engine/espo_engine.py` that adapts the existing `espo_impl/` modules to the protocol from Prompt A. Register the EspoCRM engine in the registry. Tests for the adapter.

**Prompt D — Refactor `automation/ui/deployment/` to use the registry.** Update each call site that currently imports directly from `espo_impl/` to look up the engine via the registry instead. Six call sites identified in §2.3. After this prompt, no code in `automation/` directly imports from `espo_impl/`.

After Phase 1: the application functions identically to before, but the abstraction layer is in place. EspoCRM is the only registered engine; everything still works.

### 5.2 Phase 2 — Attio engine (prompts E–I)

**Prompt E — `attio_impl/` skeleton and Attio API client.** Create the `attio_impl/` directory structure paralleling `espo_impl/`. Implement `attio_impl/core/api_client.py` wrapping the Attio Python SDK or using `requests` directly. Implement `auth_methods()` and `test_connection()` for the Attio engine. Tests using mock responses. Register the Attio engine.

**Prompt F — Schema migration for Attio platform.** Update `Instance.crm_platform`, `DeploymentRun.crm_platform`, and `Client.crm_platform` CHECK constraints to include `'Attio'`. Update `SUPPORTED_PLATFORMS` constant. Update `SUPPORTED_VERSIONS` dict. Tests.

**Prompt G — Attio object and attribute managers.** Implement `attio_impl/core/object_manager.py` for custom object create/update/delete and `attio_impl/core/attribute_manager.py` for attribute create/update/delete. Tests.

**Prompt H — Attio program loading and apply (entity-level).** Implement the Attio engine's `apply_program()` for entity-and-field schema. Maps YAML entities to Attio custom objects and YAML fields to Attio attributes. Handles the Pro-plan-required-for-custom-objects constraint with clear error messaging. Tests with at least one YAML program file.

**Prompt I — Attio relationship manager and list manager.** Implement `attio_impl/core/relationship_manager.py` for relationship attributes and `attio_impl/core/list_manager.py` for list creation. Tests.

After Phase 2: the application can deploy entity-and-field schema to Attio. Workflow, layout, email template, and conditional logic features are not yet supported.

### 5.3 Phase 3 — Attio feature parity (prompts J–L)

**Prompt J — Attio workflow manager.** Implement `attio_impl/core/workflow_manager.py` mapping YAML workflows to Attio automations. Document features that don't translate cleanly.

**Prompt K — Attio layout / view configuration.** Implement layout-equivalent functionality — Attio record templates and views. Document the looser mapping.

**Prompt L — Attio audit support.** Implement `attio_impl/core/audit_manager.py` for reading the current state of an Attio workspace and producing an audit document equivalent to EspoCRM's audit output.

After Phase 3: the Attio engine has feature parity for the YAML schema features that have Attio equivalents, with explicit handling for features that don't.

### 5.4 Phase 4 — UI updates (prompts M–N)

**Prompt M — Engine selection in instance dialog.** Update `automation/ui/deployment/instance_dialog.py` (or equivalent — actual location to be confirmed during the prompt) to include engine selection when creating new instances. Update text and field labels conditionally based on selected engine.

**Prompt N — Deployment wizard updates for SaaS engines.** Update `automation/ui/deployment/deploy_wizard/wizard_dialog.py` to handle the no-installer case (Attio is `bring_your_own` only). Hide self-hosted scenario when the platform doesn't support it. Update EspoCRM-specific UI strings to come from `engine_metadata()` rather than be hardcoded.

After Phase 4: users can create Attio instances via the UI, deploy YAML programs to them, and audit them.

### 5.5 Series total

12 prompts (A through N). Each prompt produces working code with tests; the series is designed so that an interrupted series leaves the application in a working state (no half-broken intermediate state). EspoCRM continues working throughout.

The series is conservative on scope — the basic Attio engine in Phase 2 covers entity-and-field schema, which is the most-used part of YAML programs. Phase 3 fills in workflow and layout features. Phase 4 is UI integration. Email templates and conditional logic features that don't translate cleanly to Attio are documented with workarounds rather than implemented.

---

## 6. Open Questions Before First Prompt

Several questions should be resolved before the prompt series begins. Each is a small decision but each affects how the work proceeds.

### 6.1 Attio plan tier for testing

The Attio engine requires a Pro plan to exercise custom objects (which is the engine's main value). For testing, we need an Attio Pro workspace. Options: free trial workspace (Attio offers trials), purchased Pro plan, or constraint to standard-objects-only for the initial engine (which leaves the Pro-plan-needed handling untested until later).

Recommend: free trial Pro workspace for development and initial testing. Production deployment is the user's responsibility.

### 6.2 OAuth vs. API key for first engine

Per §4.1, API key is simpler. OAuth requires Attio approval and is needed only for multi-workspace integrations. The initial engine should use API key; OAuth can be added later if CRM Builder needs to operate across many users' Attio workspaces simultaneously.

Recommend: API key for the initial engine. OAuth deferred.

### 6.3 Whether `config_loader` is shared or per-engine

Per §3.1, YAML loading might be largely platform-agnostic. The current `espo_impl/core/config_loader.py` is 76K — substantial. Whether to keep it in `espo_impl/` or move it to a shared `automation/core/yaml/` location is a design question.

Recommend: defer this decision until Prompt G or H, when we have evidence of which loading concerns are platform-specific. For Phase 1 (Prompts A-D), keep config loading in `espo_impl/` and let the protocol's `load_program()` delegate to it.

### 6.4 How aggressive to be with EspoCRM-specific UI string extraction

The EspoCRM-specific UI strings in `wizard_dialog.py` (per §2.3) could either be (a) extracted to an engine-metadata-provided source as part of Prompt N, or (b) left as-is for now and addressed in a future iteration when more engines exist. Aggressive extraction is more work but cleaner; leaving them is faster but accumulates technical debt.

Recommend: minimum extraction in Prompt N — only the strings that *change meaning* depending on engine type. Strings that are EspoCRM-specific but only ever shown when EspoCRM is the engine can stay hardcoded for now.

### 6.5 Confirmation of memory's claim about `requirements_window.py` tech debt

Per memory, `requirements_window.py` has a tech debt note about bridging `ActiveClientContext` to legacy `ClientContext`. This refactor work is independent of engine pluggability but might intersect if the bridge touches deployment code. Confirm during Prompt D whether the bridge is in any of the call sites being updated.

### 6.6 Confirmation of memory's claim about doc location

Memory says the YAML schema doc lives at `PRDs/application/app-yaml-schema.md`, but the actual location is `PRDs/product/app-yaml-schema.md`. Memory is stale; this document references the actual location. Worth a memory update.

---

## 7. Out of Scope

Explicitly NOT covered by this work series:

- **HubSpot engine.** Phase 2 of the broader engine roadmap. Will be a separate planning document and prompt series after Attio is working.
- **CiviCRM and SuiteCRM engines.** Open-source candidates from the CBM redo's candidate set. Lower priority than HubSpot; would follow the same pattern.
- **Multi-deploy orchestration.** Deploying a single YAML to multiple instances in parallel as a single user-facing operation. Important for the methodology evolution effort but separate from per-engine work; needs its own design.
- **Comparison artifact generation.** Producing the descriptive comparison output across deployment targets. References in `pattern-library-specification.md` and methodology research; out of scope here.
- **Engine plugin loading.** External engine plugins; engines remain first-class repository modules.
- **Cross-engine version compatibility.** Each engine declares its own versions independently.

---

## 8. Connection to Other Artifacts

This planning document connects to:

- **`PRDs/product/app-yaml-schema.md`** — the YAML schema this work treats as platform-portable. §1 of that document explicitly states the platform-agnostic design intent.
- **`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`** — the L2 PRD currently at v1.17. Engine pluggability is a substantial enough feature that the L2 PRD will need updating; whether it's a v1.18 or a v2.0 is a question for when the work is closer to done.
- **`PRDs/process/research/evolved-methodology/`** — the methodology research that motivated this work. Particularly `cbm-redo/cbm-redo-step-9-final-findings.md` §6.4 step 4 ("Begin Phases 2–5 extension against CBM" — which has now been redirected to "build engine pluggability and a second engine").
- **`PRDs/process/research/evolved-methodology/pattern-library-specification.md`** §6.4 — the API terms of service consideration referenced in §4.6 of this document.

---

## 9. Next Steps If This Plan Is Accepted

If this planning document is accepted as the design for the work series:

1. **Resolve the open questions in §6** — particularly §6.1 (Attio Pro workspace for testing) and §6.6 (memory update for doc location).
2. **Verify Attio's developer terms** per §4.6 — 30-minute review before any engine code is written.
3. **Author Prompt A** — `CLAUDE-CODE-PROMPT-engine-A-protocol-and-registry.md` in `PRDs/product/crmbuilder-automation-PRD/`. Per the multi-prompt naming convention, every prompt in the series uses the `engine-{letter}` tag.
4. **Execute Prompt A via Claude Code** — Doug runs it in his local environment.
5. **Review Prompt A's results** before proceeding to Prompt B.
6. **Iterate** through the series, prompt by prompt, with review between each.

The series is paced by prompt completion — Doug controls the rate. There is no expectation that the series is delivered in any particular timeframe; it can pause and resume as Doug's bandwidth allows.

---

*End of document.*
