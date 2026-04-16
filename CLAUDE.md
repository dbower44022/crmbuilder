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
├── core/              # Business logic — no GUI dependencies
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
│   ├── import_manager.py # Data import CHECK→ACT orchestration
│   └── deploy_manager.py # SSH execution, phase logic, deploy config read/write
├── ui/                # PySide6 GUI components
│   ├── main_window.py # Top-level window + state machine
│   ├── instance_panel.py # Instance list + CRUD
│   ├── instance_dialog.py # Add/Edit instance modal
│   ├── program_panel.py # Program file list
│   ├── output_panel.py # Color-coded output
│   ├── confirm_delete_dialog.py # Delete confirmation + entity name mapping
│   ├── import_dialog.py # Four-step data import wizard
│   ├── deploy_panel.py  # Deploy section in main window (context-driven)
│   ├── deploy_wizard.py # Six-step Setup Wizard modal dialog
│   └── deploy_dashboard.py # Deployment Dashboard (phases, log, cert status)
└── workers/
    ├── run_worker.py  # QThread background operations
    ├── import_worker.py # QThread import background worker
    └── deploy_worker.py # QThread background worker for SSH deployment phases

data/
└── instances/
    ├── {slug}.json          # Instance profile (gitignored)
    └── {slug}_deploy.json   # Deployment config per instance (gitignored)

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
│   ├── yaml-schema-prompts/  # Claude Code prompts for yaml-v1.1 series (A–H)
│   └── features/      # Feature-level specs (feat-*.md)
├── process/           # Document production methodology
│   ├── CRM-Builder-Document-Production-Process.docx
│   ├── interviews/    # Interview guides (master, entity, process, reconciliation)
│   └── templates/     # Document generation templates
└── implementation/    # Claude Code task prompts (CLAUDE-CODE-PROMPT-*.md)
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

## Deployment Feature Patterns

- Deploy panel content is driven by the selected instance — same pattern as
  the Program panel responding to instance selection
- `DeployConfig` is separate from `InstanceProfile` — an instance can exist
  without a deploy config, and a deploy config can exist while the instance
  is not yet reachable
- The only interaction between `DeployConfig` and `InstanceProfile` is in
  Phase 3: after successful deployment, `deploy_manager` writes
  `https://{full_domain}` back to the instance profile's `url` field
- Deploy config is stored as `{instance_slug}_deploy.json` in `data/instances/`
- All passwords are masked before being included in any log output — never
  log credential values, only placeholder strings like `[password]`
- DNS validation runs before Phase 1 and again before Phase 2 SSL issuance;
  it retries every 30 seconds up to a 10-minute timeout
- The official EspoCRM installer script is downloaded fresh each run via wget
  and run with `-y` (non-interactive) plus all config passed as flags
- Docker is installed in Phase 1; the EspoCRM installer script handles all
  container setup in Phase 2 — do not install Nginx, PHP, or MySQL manually
- SSL is always Let's Encrypt (`--ssl --letsencrypt`) — no HTTP-only or
  custom certificate paths in v1.0
- Certificate expiry is checked in a background thread each time the Deploy
  panel is shown; result stored in `DeployConfig.cert_expiry_date`
- `deploy_worker.py` follows the same QThread pattern as `run_worker.py` and
  `import_worker.py` — emit signals for log lines, phase status, and completion

## YAML Schema v1.1 — Implementation Complete

The YAML program file schema was extended from v1.0 to v1.1
to cover capabilities identified in the MR-pilot gap analysis
(`PRDs/product/yaml-schema-gap-analysis-MR-pilot.md`). The spec is
`PRDs/product/app-yaml-schema.md` v1.1.

**Implementation approach:** an eight-prompt Claude Code series
(Prompts A through H) stored in `PRDs/product/yaml-schema-prompts/`.
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
- Do not log credential values — mask all passwords in SSH command strings
  before emitting them to the log window
- Do not add new top-level directories — all deployment code lives within
  the existing `espo_impl/` structure
