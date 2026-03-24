# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project

This is the **EspoCRM Implementation Tool** — a PySide6 desktop application
that deploys EspoCRM configuration declaratively from YAML program files.

This is NOT the CBM client repository. Client-specific YAML files and
generated documentation live in the client's own repository (e.g.,
`ClevelandBusinessMentoring`), not here.

## Commands

```bash
# Install dependencies
uv sync

# Run the application
uv run espo-impl

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
│   └── reporter.py    # .log and .json report generation
├── ui/                # PySide6 GUI components
│   ├── main_window.py # Top-level window + state machine
│   ├── instance_panel.py # Instance list + CRUD
│   ├── instance_dialog.py # Add/Edit instance modal
│   ├── program_panel.py # Program file list
│   ├── output_panel.py # Color-coded output
│   └── confirm_delete_dialog.py # Delete confirmation + entity name mapping
└── workers/
    └── run_worker.py  # QThread background operations

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
- Reports go to `{project_folder}/reports/`
- Generated docs go to `{project_folder}/Implementation Docs/`

## What NOT to Do

- Do not add client-specific YAML files to `data/programs/`
- Do not add generated documentation to `PRDs/`
- Do not modify `data/instances/` files (contain credentials, gitignored)
- Do not refactor `get_espo_entity_name()` out of `confirm_delete_dialog.py`
  without updating all imports
