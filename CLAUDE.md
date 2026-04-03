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

## Document Production Process

This section governs requirements work done in Claude.ai sessions —
producing Master PRDs, process documents, Domain PRDs, YAML, and
Verification Specs for any CRM implementation using CRM Builder.

The full process specification is in:
`PRDs/process/CRM-Builder-Document-Production-Process.docx`

### Process Summary

The process has eleven phases executed in strict sequence:

```
Phase 1:  Master PRD             → 1 conversation, produces Word doc
Phase 2:  Entity Definition      → 1 conversation for Entity Discovery
                                    (produces Entity Inventory)
                                    + 1 conversation per entity
                                    (produces Entity PRDs)
Phase 3:  Domain Overview        → 1 conversation per domain
                                    assembles upstream context into
                                    domain-scoped reference document
Phase 4:  Process Definition     → 1 conversation per business process
                                    done in dependency order within each domain
                                    produces one Word doc per process
Phase 5:  Domain Reconciliation  → 1 conversation per domain
                                    synthesizes process docs into Domain PRD
Phase 6:  Stakeholder Review     → outside Claude, via Google Docs
Phase 7:  YAML Generation        → 1 conversation per domain
Phase 8:  CRM Selection          → 1 conversation, produces CRM Evaluation
                                    Report
Phase 9:  CRM Deployment         → administrator provisions CRM instance
Phase 10: CRM Configuration      → tool-driven, YAML applied to CRM instance
Phase 11: Verification           → generated by CRM Builder tool
```

### Key Principles

- Entities are defined before processes — Entity Definition (Phase 2)
  establishes all entities so process conversations reference pre-defined
  entities rather than introducing them implicitly
- Domain Overview (Phase 3) assembles upstream context into a single
  domain-scoped reference, replacing the need to upload Master PRD +
  Entity Inventory + Entity PRDs into each process session
- One process per conversation — never define an entire domain in one session
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
  are permitted in the CRM Evaluation Report (Phase 8).
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
