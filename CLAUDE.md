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
