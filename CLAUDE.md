# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project

This is the **CRM Builder** — a PySide6 desktop application that covers
the full EspoCRM lifecycle:

1. **Deploy** — provision a fresh EspoCRM instance on a DigitalOcean Droplet
   via SSH using the official EspoCRM installer script (Docker-based)
2. **Configure** — deploy fields, layouts, relationships, and data declaratively
   from YAML program files via the EspoCRM REST API

This is NOT the CBM client repository. Client-specific YAML files and
generated documentation live in the client's own repository (e.g.,
`ClevelandBusinessMentoring`), not here.

**Note on the CBM repo's local directory name.** The GitHub repo is
named `dbower44022/ClevelandBusinessMentoring`, but Doug's local clone
is at `~/Dropbox/Projects/ClevelandBusinessMentors/` — the short form
(ending in `Mentors`, not `Mentoring`). When Claude Code or a session
prompt refers to a local path on Doug's machine, use the short name.
When referring to the GitHub repo itself (clone URL, remote name, PR
links), use the long name. A previous two-directory split (both long
and short names as separate clones) was reconciled on 04-10-26; only
the short-named clone now exists locally.

## CRMBuilder v2 — Methodology Rearchitecture

CRMBuilder v2 is the next major iteration of CRMBuilder. It rebuilds the methodology's foundation by making a structured database the source of truth for all CRM implementation artifacts (personas, entities, fields, processes, requirements, decisions, manual-config items, test specifications, cross-references). Word documents, deployment YAML, and test cases become renders generated from the database, not authored separately. CBM is the test case validating progress at each step.

**v2 home:** `PRDs/product/crmbuilder-v2/` (PRDs and prompts) and `crmbuilder-v2/` (the storage system code).

**Tracking:** Commits touching v2 work prefix the subject with `v2:`. v1 work (the existing application code, methodology guides, app-level product specs, engine pluggability planning, and the CBM client repo) continues unchanged under existing locations.

**Storage system v0.1 has landed.** Charter, status, decisions, and sessions now live in the v2 SQLite database (`crmbuilder-v2/data/v2.db`, gitignored) with git-tracked JSON snapshots at `PRDs/product/crmbuilder-v2/db-export/`. The four governance markdown files that previously held this content have been retired (recoverable through git history). The PRD and the implementation plan remain in markdown at `PRDs/product/crmbuilder-v2/` because they are external specs, not bootstrapped governance content.

**Session orientation protocol** (per DEC-011):

When a session engages v2 work — by the conversation referencing v2, or the user explicitly engaging it — Claude follows this tiered orientation:

- **Tier 1 (universal, every session):** Read this CLAUDE.md (already done by reading this section).
- **Tier 2 (v2 engagement, MCP-connected sessions):** Call `get_current_status`, `get_current_charter`, `list_recent_sessions(limit=3)`, then `get_decision(<id>)` or `list_decisions_for_session(<id>)` as referenced. Tools are exposed by the local `crmbuilder-v2` MCP server (run `crmbuilder-v2-api &` and `crmbuilder-v2-mcp` from the repo).
- **Tier 2 (file-fallback when MCP is not connected):** Read the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` directly — `status.json`, `charter.json`, `sessions.json`, `decisions.json`, `references.json`. Same content as the MCP returns; just static.
- **Tier 3 (on-demand):** Targeted queries during conversation as topics arise.

**Reference relationship vocabulary lives in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`.** The set of valid kinds is `REFERENCE_RELATIONSHIPS`; the `(source_type, target_type) → frozenset[kinds]` constraint mapping (`RELATIONSHIP_RULES`) is precomputed at module load by `_kinds_for_pair` from seven semantic rules. The UI's references-create dialog drives its cascading filters from `RELATIONSHIP_RULES` directly, so vocab compliance is strict end-to-end. **Adding a new relationship kind requires updating both** — `REFERENCE_RELATIONSHIPS` for the kind's existence, and `_kinds_for_pair` for its source/target constraints. (The `refs.relationship_kind` CHECK constraint also needs an Alembic migration.)

v1 work continues normally — the deployment engine, methodology guides, and existing app code are not part of v2 and are maintained under their existing locations.

## Commands

```bash
# Install dependencies
uv sync

# Run the application
uv run crmbuilder

# Run tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ --cov=espo_impl

# Lint
uv run ruff check espo_impl/ tools/ tests/

# Generate docs (requires a project folder with YAML files)
uv run python tools/generate_docs.py --programs /path/to/programs/
```

## Architecture

```
espo_impl/
├── core/              # Configuration-side business logic (Requirements + YAML)
│   ├── models.py      # Data models (dataclasses + enums)
│   ├── api_client.py  # EspoCRM REST API wrapper
│   ├── config_loader.py # YAML parsing + validation
│   ├── field_manager.py # Field CHECK→ACT orchestration
│   ├── layout_manager.py # Layout CHECK→ACT orchestration
│   ├── relationship_manager.py # Relationship CHECK→ACT orchestration
│   ├── entity_manager.py # Entity create/delete
│   ├── condition_expression.py # Shared condition-expression parser/validator/evaluator (v1.1)
│   ├── relative_date.py # Relative-date vocabulary resolver (v1.1)
│   ├── comparator.py  # Field spec vs API state comparison
│   ├── reporter.py    # .log and .json report generation
│   └── import_manager.py # Data import CHECK→ACT orchestration
├── ui/                # PySide6 dialogs that aren't part of the Deployment tab
│   ├── main_window.py # Top-level window — three-tab architecture
│   ├── instance_panel.py # (legacy panel; kept for shared widgets)
│   ├── instance_dialog.py # Add/Edit instance modal
│   ├── program_panel.py # Program file list
│   ├── output_panel.py # Color-coded output
│   ├── confirm_delete_dialog.py # Delete confirmation + entity name mapping
│   └── import_dialog.py # Four-step data import wizard
└── workers/           # QThreads for the Configure / Verify / Audit / Import paths
    ├── run_worker.py
    ├── import_worker.py
    ├── audit_worker.py
    └── tooltip_worker.py

automation/
├── core/deployment/   # Deploy / Upgrade / Recovery business logic (no Qt)
│   ├── ssh_deploy.py            # SSH helpers + four-phase deploy
│   ├── wizard_logic.py          # Wizard DB writes (Instance, DeploymentRun)
│   ├── deploy_config_repo.py    # InstanceDeployConfig CRUD (with keyring)
│   ├── upgrade_ssh.py           # Four-phase EspoCRM in-place upgrade
│   └── recovery_ssh.py          # Admin reset + full DB reset primitives
├── core/secrets.py    # Keyring-backed secret storage
├── ui/deployment/     # Deployment-tab UI (sidebar entries + modals)
│   ├── deployment_window.py     # Tab container (sidebar + picker + content)
│   ├── instance_picker.py       # Active-instance dropdown + version/cert badges
│   ├── deploy_entry.py          # Deploy sidebar entry + Upgrade/Recovery buttons
│   ├── deploy_wizard/           # Six-step Setup Wizard modal
│   ├── connection_config_dialog.py # Backfill dialog for InstanceDeployConfig
│   ├── upgrade_dialog.py        # Modal: Upgrade EspoCRM
│   ├── upgrade_worker.py        # UpgradeWorker + VersionCheckWorker QThreads
│   ├── recovery_dialog.py       # Modal: admin reset + full DB reset
│   └── recovery_worker.py       # CredentialResetWorker + FullResetWorker
└── db/                # Per-client SQLite schema + migrations

data/
└── instances/         # Legacy JSON profile store (configuration side only)
    └── {slug}.json    # Instance profile (gitignored)

tools/
└── docgen/            # Documentation generator
    ├── yaml_loader.py
    ├── builders/      # Section builders
    └── renderers/     # Markdown and DOCX renderers

PRDs/
├── product/           # CRM Builder product specs
│   ├── CRMBuilder-PRD.md
│   ├── app-*.md       # App-level specs (YAML schema, UI patterns, logging)
│   ├── yaml-schema-gap-analysis-MR-pilot.md  # v1.1 design rationale
│   └── features/      # Feature-level specs (feat-*.md)
├── process/           # Document production methodology
│   ├── CRM-Builder-Document-Production-Process.docx
│   └── interviews/    # Interview guides (master, entity, process, reconciliation)
└── _archive/          # Completed prompt files (see _archive/INDEX.md)
```

## Key Patterns

- `get_espo_entity_name()` in `confirm_delete_dialog.py` maps YAML entity
  names to EspoCRM internal names (C-prefix for custom entities)
- Custom fields use c-prefix internally: `contactType` → `cContactType`
- Native entities (Account, Contact) do not get C-prefix
- For native entity primary sides in relationships, EspoCRM auto-applies
  c-prefix to link names — the tool handles this in check/verify steps
- Each instance profile has a `project_folder` pointing to the client repo
- YAML files live in `{project_folder}/programs/`
- Reports go to `{project_folder}/reports/` (including import reports)
- Generated docs go to `{project_folder}/Implementation Docs/`
- Import Data button opens a self-contained wizard dialog (no UIState interaction)
- Import matches records by email; never overwrites existing non-empty fields
- Phone numbers are auto-cleaned to E.164 (+1 for US 10-digit numbers)
- firstName/lastName are derived from record name or email when not mapped
- Buttons are never disabled — click handlers show explanatory messages instead

## Server Management Layer (feat-server-management.md)

The Deployment tab handles four operations against an EspoCRM Droplet:
deploy (the Setup Wizard), upgrade (Upgrade EspoCRM button), recovery
(admin reset + full DB reset), and verification. All four share the
same SSH connection and credentials, persisted in the
`InstanceDeployConfig` table (per-client SQLite, migration `_client_v9`).

- **Persistence model.** `Instance` carries the EspoCRM API credentials
  (admin user/password). `InstanceDeployConfig` (1:1, FK + UNIQUE on
  `instance_id`, `ON DELETE CASCADE`) carries SSH host/port/auth, db
  root password, domain, and version-tracking fields. Secrets live in
  the OS keyring via `automation/core/secrets.py` — the DB stores
  opaque `crmbuilder:{uuid4}` reference IDs only. SSH key paths are
  stored inline (paths aren't sensitive); SSH passwords and the db
  root password round-trip through keyring.
- **Wizard persistence.** On a successful self-hosted deploy,
  `wizard_logic.persist_deploy_config_from_wizard` writes the
  `InstanceDeployConfig` row immediately after `update_instance_from_wizard`.
  Failure is non-fatal — the deploy succeeded; the user is prompted on
  first Upgrade/Recovery click via `ConnectionConfigDialog` instead.
- **Self-hosted gate (strict).** Upgrade and Recovery buttons are
  visible only when the active instance's most recent successful
  `DeploymentRun.scenario == 'self_hosted'` (or when an existing
  `InstanceDeployConfig` already declares it). Cloud-hosted and
  bring-your-own scenarios cannot be SSHed into; the buttons are
  hidden, not disabled.
- **Upgrade flow.** Four phases: pre-flight checks, backup
  (mariadb-dump + tar of data volume to `/var/backups/espocrm/{ts}/`,
  retention 3), `php command.php upgrade -y` inside the container,
  verify. Major-version jumps (7.x → 8.x) trigger a confirmation
  modal before the worker starts. Never re-run `install.sh --clean` to
  upgrade — that wipes data.
- **Recovery flow.** Admin reset issues a SQL UPDATE inside
  `espocrm-db`; full reset tears down containers/volumes, removes
  `/var/www/espocrm`, and re-runs install + post-install + verify.
  Full reset is gated behind a typed `DELETE ALL DATA` phrase plus a
  warning modal. Both operations write the new admin credentials back
  to `Instance.username` / `Instance.password`.
- **Common rules.** All passwords are masked in log output via
  `mask_secrets()` from `upgrade_ssh.py`. SSL is always Let's Encrypt.
  DNS validation runs before Phase 1 and Phase 2 of deploy with a
  30-second retry interval and 10-minute timeout. Workers persist
  state to `InstanceDeployConfig` after each phase so a mid-flow
  failure leaves the recorded state consistent. The version badge in
  the instance picker is fed by `VersionCheckWorker` on every
  `instance_changed` signal.

## YAML Schema v1.1 — Implementation Complete

The YAML program file schema was extended from v1.0 to v1.1
to cover capabilities identified in the MR-pilot gap analysis
(`PRDs/product/yaml-schema-gap-analysis-MR-pilot.md`). The spec is
`PRDs/product/app-yaml-schema.md` v1.1.

**Implementation approach:** an eight-prompt Claude Code series
(Prompts A through H), now archived in `PRDs/_archive/yaml-schema-prompts/`.
Prompts were executed sequentially; each built on the prior.

**Current state (04-15-26):**

- **All prompts (A–H) executed.** The full v1.1 schema is
  implemented in the loader, validators, and deploy managers.

**Series map:**

| Prompt | Categories | What it adds |
|---|---|---|
| A | Section 11 | Condition expressions, relative dates, loader plumbing (**done**) |
| B | 1, 2 | `settings:` block (with v1.0 deprecation merge), `duplicateChecks:` (**done**) |
| C | 3 | `savedViews:` with condition-expression filters (**done**) |
| D | 4, 5 | `requiredWhen:`, `visibleWhen:` (field + panel level) (**done**) |
| E | 7 | `emailTemplates:` with body-file resolution, merge-field validation (**done**) |
| F | 8 | `formula:` — aggregate, arithmetic (recursive-descent parser), concat (**done**) |
| G | 9 | `workflows:` — triggers, actions, cross-block template/arithmetic reuse (**done**) |
| H | 10 | `externallyPopulated:` flag, Verification Spec generator skeleton (**done**) |

Category 6 (Roles, field-level permissions) is deferred to v1.2.

**Key modules from Prompt A (already shipped):**

- `condition_expression.py` — public API: `parse_condition(raw)`,
  `validate_condition(parsed, entity_field_names, related_entity_field_names=None)`,
  `evaluate_condition(parsed, record, today=None)`,
  `render_condition(parsed)`. AST: `LeafClause`, `AllNode`, `AnyNode`
  (union type `ConditionNode`). Note: `render_condition` always emits
  structured form (`{all: [...]}`) even for shorthand input.
- `relative_date.py` — public API: `RELATIVE_DATE_TOKENS`,
  `is_relative_date(value)`, `resolve_relative_date(value, today=None)`.
- `models.py` — `EntityDefinition` carries `settings_raw`,
  `duplicate_checks_raw`, `saved_views_raw`, `email_templates_raw`,
  `workflows_raw`. `FieldDefinition` carries `required_when_raw`,
  `visible_when_raw`, `formula_raw`, `externally_populated`.
  `PanelSpec` carries `visible_when_raw`. `ProgramFile` carries
  `deprecation_warnings`.

**Orchestration order:**

EntitySettings → EmailTemplates → DuplicateChecks → SavedViews →
Fields/Layouts/Relationships → Workflows

## YAML Schema Rules — Authoritative Constraints

These are constraints that operators must follow when authoring YAML
program files. Some are documented in the schema spec
(`PRDs/product/app-yaml-schema.md` v1.2.1+); all are enforced at
deployment time by `validate_program()`, which runs as a hard-reject
pre-flight in the Configure flow as of error-handling Prompt E
(05-02-26). A YAML file with any validation error is excluded from the
deployment batch entirely with errors shown in the run log; other files
in the batch run normally.

### Link relationships go in `relationships:` only

Link relationships between entities are declared exclusively in the
top-level `relationships:` block. **`type: link` is not a valid field
type** and is rejected at validation time with a hard-reject error that
points to this rule. Reason: EspoCRM creates link fields automatically
from the `relationships:` block via `EntityManager/action/createLink`;
declaring them additionally as `type: link` fields causes the
field-creation API to create stub link fields without proper
foreign-entity wiring, which then causes `createLink` to return HTTP
409 Conflict. (FU-Contribution.yaml v1.0.0 was the historical
discovery case — fixed in v1.0.1.)

Field-level metadata an operator might want to attach to a link
(`description`, `category` for layout grouping) does not propagate onto
link records via the deploy pipeline. If such metadata is needed,
configure it post-deployment via the EspoCRM admin UI. Working pattern
reference: `MR-Dues.yaml` in the CBM repo declares its `mentor` link
only in the `relationships:` block, with no field-side counterpart.

### Three features have no public REST API write path

`savedViews:`, `duplicateChecks:`, and `workflows:` directives are
recognized at parse and validation time but are not applied via REST.
The deploy pipeline returns `NOT_SUPPORTED` status for each item, emits
a `[NOT SUPPORTED] {entity}.{block}[{id}] — manual config required`
line per item, and consolidates everything in a `MANUAL CONFIGURATION
REQUIRED` block at the end of the run. `NOT_SUPPORTED` items do NOT
count as step failures (they are platform constraints, not deployment
errors). The operator configures these manually via the EspoCRM admin
UI before the deployment is considered complete.

This was originally a bug — `EspoAdminClient.put_metadata()` calls a
non-existent endpoint method (`/api/v1/Metadata` accepts GET only;
there is no PUT/POST/PATCH). It was rerouted to the short-circuit path
in error-handling Prompt D (05-02-26) until proper REST-capable
reimplementations are prioritized:

- **Saved views** require disk-level edits to
  `custom/Espo/Custom/Resources/metadata/clientDefs/{Entity}.json` plus
  cache rebuild. SSH-based file writes from the Configure flow are
  outside the API-only model and would need a new capability.
- **Duplicate-check rules** need to be reimplemented against the
  EntityManager endpoint instead of metadata writes.
- **Workflows** need to be reimplemented against the Workflow entity
  CRUD API, gated on Advanced Pack detection.

The dead API-path code in `saved_view_manager.py`,
`duplicate_check_manager.py`, and `workflow_manager.py` is retained
with `TODO(error-handling-D)` markers for resurrection when these
reimplementations land.

### Error handling architecture (post Prompts A–E, 05-02-26)

The Configure pipeline is now resilient to unexpected response formats
and unexpected manager exceptions, with truthful per-step status
reporting:

- `EspoAdminClient._request()` catches `JSONDecodeError`, `ValueError`,
  and `RequestException`, returning sentinel body dicts (`_parse_failed`,
  `_request_failed`) so callers always have diagnostic detail. Use
  `_format_error_detail(body)` to render any body — sentinel or normal —
  as a one-line error string.
- `RunWorker._run_full()` wraps each of the 10 pipeline steps in
  `_run_step()`, isolating failures: a manager error or unexpected
  exception in any step is contained, marked `StepStatus.FAILED`, and
  the run continues to the next step. Authentication failures (401)
  remain a hard abort.
- Each step has a `failure_check` callable that downgrades
  `StepStatus.OK` → `FAILED` when the body returns normally but the
  result list contains `ERROR` records. `DRIFT` is informational, not
  failure. `NOT_SUPPORTED` is platform constraint, not failure.
- The `STEP SUMMARY` block at the end of every run truthfully reports
  each step as OK / FAILED / SKIPPED / NO_WORK. `NO_WORK` (rendered
  `NO WORK SPECIFIED` in the log) means the YAML asked for nothing
  for that step (a valid by-design outcome); `SKIPPED` is reserved
  for explicit user opt-out (e.g. field-update-mode bypassing
  entity deletions). The footer reads "Run completed successfully"
  or "Run completed with N step failure(s)" — `NO_WORK` is not a
  failure.

### Deployment validation pass (05-04-26)

A nine-fix engine stabilization session driven by deploying the
five-file MN+CR-Account batch
(`programs/{CR/CR-Account, MN/MN-Account, MN/MN-Contact,
MN/MN-Engagement, MN/MN-Session}.yaml`) against a freshly-reset
EspoCRM instance for the first time. Every fix surfaced from real
deployment behavior; each one was authored as a single Claude Code
prompt under
`PRDs/product/crmbuilder-automation-PRD/CLAUDE-CODE-PROMPT-*.md`,
applied, verified, and committed in sequence. End state: all five
files deploy clean, including a brand-new custom entity exercising
entity creation, cache rebuild, metadata polling, deferred-options
field, layout writing, and relationship creation + verification.

| Commit | Fix |
|---|---|
| `3b3e9dc` | Layout writer skips `c-` prefix on custom-entity fields. EspoCRM only c-prefixes custom fields when the parent entity is native (Contact, Account); custom entities (CEngagement) store fields under natural names. |
| `1115527` | Layout comparator compares `name` and `width` per item in list-column payloads. Was structurally blind to flat-dict items, so any list payloads of equal length matched. |
| `3daab49` | Auto-place required `name` field on detail/edit layouts via `settings.autoPlaceName` (default `true`). Without it, EspoCRM rejects record saves with `Field: name, Validation: required`. Schema bumped to v1.2.3. |
| `52abb94` | `STEP SUMMARY` distinguishes `NO_WORK` (YAML declared nothing) from `SKIPPED` (user opted out). Adds `StepStatus.NO_WORK` and renders it as `NO WORK SPECIFIED` (gray). |
| `d98db71` | Validator resolves field references across sibling YAMLs in a deployment batch. New `ProgramContext` value object carries the union of field names per entity across the batch; new `validate_program_with_context` consumes it. Single-file `validate_program` preserved via self-context fallback. Configure UI builds one shared context per batch. |
| `8345cd8` | Validator resolves EspoCRM native fields. New `espo_impl/core/native_entity_types.py` maps native entity names (Contact → Person, Account → Company, Meeting → Event) to base types; `_native_field_names()` consumes the existing `audit_utils` catalog (`SYSTEM_FIELDS`, `NATIVE_PERSON_FIELDS`, `NATIVE_COMPANY_FIELDS`, `NATIVE_EVENT_FIELDS`, `NATIVE_BASE_FIELDS`). |
| `fb50b95` | Validator supports `optionsDeferred: true` on `enum`/`multiEnum` fields. When true with empty `options:`, validator passes; deploy engine accepts. Schema doc Section 6.3 + 6.4.1 document the deferred-options pattern with the `MANUAL-CONFIG.md` companion-artifact rule. |
| `e5f18fe` | `EntityManager.wait_for_metadata_ready()` polls `GET /Metadata?key=entityDefs.{entity}` after `rebuild_cache()` until each named entity's metadata is materialized or a 30s timeout elapses. Closes the async-rebuild race window between entity creation and downstream operations. Backoff: 0.5/0.5/1/1/2s+. Yellow-warns on timeout, doesn't fail. |
| `e4ca6a6` | Removed `ENTITY_NAME_MAP` override entirely. Three of its five entries (`Session → CSessions`, `Workshop → CWorkshops`, `WorkshopAttendance → CWorkshopAttendee`) were wrong — current EspoCRM applies a simple `f"C{name}"` rule for all custom entities with no pluralization or renaming. Same fix applied symmetrically to `INVERSE_ENTITY_NAME_MAP` in `audit_utils.py`. The remaining map entries were redundant with the fallback. |
| `1464559` | Configure log shows absolute path of YAML being processed. Adds a `Source: {absolute_path}` line in gray immediately after the existing per-file run header. `file_info.path` was already populated; the new line just surfaces it. Closes the diagnostic gap that cost ~10 minutes of investigation when a stale-clone hypothesis surfaced earlier in the session. |
| `1d9bd0e` | `phase_verify` polls network-dependent verification checks instead of probing once. Extends the inner `run_check` helper with `poll: bool = False` and a 60s per-check deadline using a 1/1/2/2/3/3/5s+ backoff. The four network-dependent probes (HTTP redirect, HTTPS, SSL cert, login page) now poll; the three stable probes (containers, cron, database) keep single-probe behavior. Same fix benefits both `phase_verify` call sites: `recovery_worker.py:220` (Recovery & Reset) and `deploy_wizard/deploy_worker.py:160` (fresh deploy). First-probe passes preserve the legacy log shape exactly. |
| `aeba0e6` | `phase_post_install` reads cert expiry from disk (`/etc/letsencrypt/live/{domain}/fullchain.pem`) instead of going through nginx port 443. Replaces the brittle `openssl s_client | openssl x509` pipe with a direct `openssl x509 -in {path}`. Doesn't depend on nginx being up. Warning message on failure now includes the cert path and exit code. |

Three CBM-side YAML fixes accompanied the engine work:

| Commit (CBM repo) | Fix |
|---|---|
| `11d5a5d` | `FU-Account.yaml` v1.0.2 — strip duplicate `type:link` field declaration; the link is already correctly declared in `relationships:`. Schema rule per `app-yaml-schema.md` Section 6.2. |
| `7b3414a` | `programs/MR/templates/` — three test-minimal HTML body files for the email templates declared in `MR-Contact.yaml` (`mentor-application-confirmation`, `mentor-application-decline`, `mentor-duplicate-email-alert`). Bodies are placeholder `TEST TEMPLATE` content with merge-field placeholders intact; CBM-voice authoring deferred to post-deployment-validation. |
| `ffee4ca` | `MN-Account.industrySubsector` and `MN-Session.topicsCovered` — added `optionsDeferred: true` to both deferred-options enum fields per the new schema flag. Inline comments expanded to make the deferral and operator post-deploy responsibility visible at the YAML level. |
| `a538b01` | `FU-Account.geographicServiceArea` and `FU-FundraisingCampaign.geographicServiceArea` — added `optionsDeferred: true` to both deferred-options multiEnum fields. Same pattern as `ffee4ca`; both reference the same Northeast Ohio zip code master list deferred per `FU-Y9-EXC-001` with operator post-deploy responsibility documented in `MANUAL-CONFIG.md FU-MC-OL-001`. |

**Engine-bug backlog** (cosmetic and post-validation findings,
non-blocking, not yet fixed):

- Recovery worker Phase 4 had no warm-up delay between
  `docker compose up` and HTTPS probes. ✅ **Fixed in commit
  `1d9bd0e`** — `phase_verify` now polls network-dependent
  checks on a backoff schedule with a 60s per-check timeout.
- Cert-expiry read piped nothing into `openssl x509` (`Could not
  read certificate from <stdin>`). ✅ **Fixed in commit
  `aeba0e6`** — reads the cert file directly from disk.
- Configure log didn't show the absolute path of the YAML file
  being processed. ✅ **Fixed in commit `1464559`** — added
  `Source: {absolute_path}` line after each per-file run header.
- **Validator doesn't consult server state for cross-batch field
  references.** Surfaced during the FU deployment: FU-Account
  references `accountType` (declared by CR-Account, already
  deployed). Validator rejected because CR-Account.yaml wasn't
  in the current batch — `ProgramContext` from `d98db71` only
  unions fields across YAMLs in the batch, not against fields
  already on the server. Workaround used: include dependency
  YAMLs (CR-Account, MR-Contact) in the batch and let them run
  idempotent. Real fix: when an instance is connected, validator
  queries `GET /Metadata?key=entityDefs.{entity}.fields` and
  unions the server-side fields into `field_names`. Falls back
  to current batch-only behavior if no instance is connected.
  **Not yet fixed.**
- **Deploys process files in alphabetical order, not topological
  order based on relationship dependencies.** A YAML declaring a
  relationship to a sibling YAML's not-yet-deployed custom
  entity hits HTTP 500 because the target entity doesn't exist.
  Surfaced when FU-Contribution's `campaign` link to
  FundraisingCampaign failed in alphabetical-order processing.
  Workaround used: two-step manual deploy (FundraisingCampaign
  alone first, then the rest). Real fix: build a dependency
  graph from each YAML's relationships block, topological-sort
  the file list before invoking per-file deploys. Cycle
  detection produces a clear error rather than a deploy attempt.
  **Not yet fixed.**
- **YAML `description` type-conflict polish.** FU-FundraisingCampaign
  re-declares `description` (a native field on Base entities) with
  a different type. Engine correctly skips with `TYPE CONFLICT
  (skipped)` rather than clobbering the native field. The
  defensive engine behavior is right; the YAML should drop the
  redeclaration or align with the native type. Trivial. **Not
  yet fixed.**

**Validated against fresh deploy (11 of 19 YAML files):**

- **MN domain (4/4 ✅ complete)** — MN-Account (5 fields with
  type-conditional visibility), MN-Contact (placeholder, NO_WORK),
  MN-Engagement (19 fields, 6 relationships, 6 saved views),
  MN-Session (7 fields, 3 relationships, Event base type)
- **MR domain (2/2 ✅ complete)** — MR-Contact (43 fields, 3
  emailTemplates created, 5 saved views and 4 workflows surfaced
  as MANUAL_CONFIG, 1 duplicateCheck surfaced, 5 formula-fields),
  MR-Dues (8 fields, 1 relationship, Base custom entity)
- **FU domain (4/4 ✅ complete)** — FU-Account (6 fields, 1
  relationship, geographicServiceArea with `optionsDeferred:true`),
  FU-Contact (4 fields), FU-Contribution (15 fields, 3
  relationships including the cross-custom-entity link to
  FundraisingCampaign), FU-FundraisingCampaign (9 fields)
- **CR domain (1/9)** — CR-Account validated; 8 remain
  (CR-Contact plus 7 CR custom entities: PartnershipAgreement,
  Event, EventRegistration, MarketingCampaign, CampaignGroup,
  CampaignEngagement, Segment)

**Live entities on the test instance after the validation pass:**

- 5 custom entities created: CEngagement, CSession, CDues,
  CContribution, CFundraisingCampaign
- 2 native entities extended: Contact (47 custom fields total
  across MR, FU, CR contributions), Account (22 custom fields
  total across CR, MN, FU contributions)
- ~125 custom fields total, ~12 relationships, 3 emailTemplates
- ~15 saved views, ~4 workflows, ~2 duplicate-checks correctly
  surfaced as MANUAL_CONFIG entries

## Document Production Process

This section governs requirements work done in Claude.ai sessions —
producing Master PRDs, process documents, Domain PRDs, YAML, and
Verification Specs for any CRM implementation using CRM Builder.

The full process specification is in:
`PRDs/process/CRM-Builder-Document-Production-Process.docx`

### Process Summary

> **Note:** The authoritative phase specification is
> `PRDs/process/CRM-Builder-Document-Production-Process.docx`. This
> summary tracks that document — if the two ever disagree, the .docx wins
> and this summary should be corrected.

The process has thirteen phases executed in strict sequence:

```
Phase 1:  Master PRD                → 1 conversation, produces Word doc
Phase 2:  Domain Discovery          → 1 conversation, produces a working
                                       Domain Discovery Report containing
                                       proposed domains, candidate entities,
                                       and candidate personas
Phase 3:  Inventory Reconciliation  → 1 conversation with the client that
                                       reconciles the discovery report and
                                       produces the durable Entity Inventory
                                       and Persona Inventory
Phase 4:  Domain Overview +         → 1 Domain Overview conversation per
          Process Definition          domain, followed by 1 conversation per
                                       business process in dependency order;
                                       produces one Word doc per process
Phase 5:  Entity PRDs               → 1 conversation per entity, drafted
                                       after the processes that use the
                                       entity are complete
Phase 6:  Cross-Domain Service      → 1 conversation per service (Notes,
          Definition                   Email, Calendar, Surveys, etc.)
Phase 7:  Domain Reconciliation     → 1 conversation per domain, synthesizes
                                       process docs and Entity PRDs into the
                                       Domain PRD
Phase 8:  Stakeholder Review        → outside Claude, via Google Docs
Phase 9:  YAML Generation           → 1 conversation per domain
Phase 10: CRM Selection             → 1 conversation, produces CRM
                                       Evaluation Report
Phase 11: CRM Deployment            → administrator provisions CRM instance
Phase 12: CRM Configuration         → tool-driven, YAML applied to CRM
Phase 13: Verification              → generated by CRM Builder tool
```

### Current Pilot

The **Cleveland Business Mentors (CBM) MR pilot** is running Phases
9 → 11 → 12 → 13 (YAML Generation through Verification) on the
Mentor Recruitment domain to validate that the methodology produces a
deployable CRM. Phase 9 conversations are guided by
`PRDs/process/interviews/guide-yaml-generation.md`. Findings are logged
in `ClevelandBusinessMentoring/PRDs/pilot/PILOT-FINDINGS.md` and may
drive changes to this methodology before the next domain is piloted.

### Key Principles

- Discovery captures candidate entities AND candidate personas together
  in Phase 2, from the client's own language; both are reconciled in
  Phase 3 before any process work begins
- Entities are sketched early for shared vocabulary but fully defined
  as Entity PRDs only in Phase 5, after the processes that use them are
  drafted
- Every persona is either backed by an entity record or is an external
  role not tracked as data
- Domain Overview (part of Phase 4) assembles upstream context into a
  single domain-scoped reference, replacing the need to upload Master
  PRD + Entity Inventory + Persona Inventory into each process session
- One process per conversation — never define an entire domain in one
  session
- Word documents throughout — no Markdown source files, no converter
- No Consolidated Design as a separate document — conflict detection
  happens during stakeholder review and YAML generation
- Each conversation has defined inputs (uploaded prior documents) and
  one clear output (a Word document or YAML files)
- Stakeholders own documents after Claude's first draft
- When scope changes are discovered mid-conversation, stop and fix the
  upstream document before continuing (see process doc Section 10)

### PRD Content Rules

- Never mention specific product names (EspoCRM, WordPress, Moodle,
  Constant Contact, etc.) in Master PRDs, Entity PRDs, process documents,
  or Domain PRDs. These are implementation details only. Product names
  are permitted in the CRM Evaluation Report (Phase 10).
- Every requirement, entity, and data item must have a unique identifier
  following the scheme in the process document Section 5.
- Process documents are not complete until all nine required sections
  are present and meet their respective standards (see process doc
  Section 3.4).

### At the Start of Every Requirements Session

1. Ask the user which implementation is being worked on
2. Read the implementation's CLAUDE.md for current state
3. Identify which phase and step the implementation is on
4. State the current step and confirm before proceeding

## Known Limitations

### Path B has no batch back-fill for legacy or empty client databases

The Path B / Import Processor pipeline at
`automation/importer/pipeline.py` ingests one document at a time, driven
from the Documents view in the Requirements tab. Each import requires a
target work item to already exist in the client database. The legacy
bootstrap CLI at `automation/cbm_import/cli.py` previously walked an
entire client repository in batch to populate a fresh client database,
but every concrete import method in that CLI has been migrated to Path B
and now emits a warning and skips. Running the legacy CLI today produces
only an empty work item skeleton (a master_prd row plus a
business_object_discovery row, both force-completed) with no Domain,
Entity, Process, or document content.

The consequence is that there is currently no in-app path from a
legacy-bootstrapped or empty client database to a fully populated one
under Path B. A client whose documents were drafted before the Path B
migration cannot have its Requirements tab populated after the fact
without either rebuilding from scratch through Path B one document at a
time in dependency order, or building a new batch back-fill path that
calls the Path B parsers and ImportProcessor for each work item.

The CBM implementation in `dbower44022/ClevelandBusinessMentoring` is
the canonical example. Its Requirements tab is intentionally empty and
the planned remediation is a full re-run end-to-end after the
application has been updated based on lessons learned from the first
implementation. See that repository's CLAUDE.md for the decision record.

This is deferred work, not a defect requiring immediate fix. New clients
started from a Master PRD session under Path B do not encounter this
limitation.

## What NOT to Do

- Do not add client-specific YAML files to `data/programs/`
- Do not add generated documentation to `PRDs/`
- Do not modify `data/instances/` files (contain credentials, gitignored)
- Do not refactor `get_espo_entity_name()` out of `confirm_delete_dialog.py`
  without updating all imports
- Do not install Nginx, PHP, or MySQL directly on the server — the EspoCRM
  installer script handles all of this via Docker
- Do not create a `cbmadmin` non-root user — the installer runs as the
  configured SSH user (typically root on a fresh Droplet)
- Do not support HTTP-only or custom certificate SSL modes in v1.0
- Do not log credential values — pass all passwords through
  `mask_secrets()` (or `mask_credentials()` for `SelfHostedConfig`)
  before emitting to the log window
- Do not re-run `install.sh --clean` to "upgrade" an existing deployment —
  it is destructive. Use `upgrade_ssh.phase3_run_upgrade` which calls
  the EspoCRM CLI upgrader inside the container
- Do not store secrets in plaintext columns — route through
  `automation/core/secrets.py` (keyring-backed) and store opaque refs
- Do not show the Upgrade or Recovery buttons for cloud-hosted or
  bring-your-own scenarios — they cannot be SSHed into
- Do not add new top-level directories — all deployment code lives within
  the existing `espo_impl/` structure
- Do not declare link relationships as `type: link` fields in an entity's
  `fields:` block — they go exclusively in the top-level `relationships:`
  block. `validate_program()` will hard-reject the file. See "YAML Schema
  Rules" above
- Do not call `EspoAdminClient.put_metadata()` from new code — the
  endpoint it targets does not exist (`/api/v1/Metadata` accepts GET
  only). The method is dead code retained pending removal. The three
  managers that historically used it (saved views, duplicate checks,
  workflows) now short-circuit to NOT_SUPPORTED. See "YAML Schema Rules"
  above
- Do not skip `validate_program()` from a new code path that loads YAML
  for deployment — every Configure-time YAML load must run validation
  before handing the program to a worker. Validation is hard-reject by
  design
