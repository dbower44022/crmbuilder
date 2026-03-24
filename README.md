# CRM Builder

EspoCRM configuration deployment tool. Deploy field configurations from declarative YAML program files.

## Quick Start

```bash
uv sync
uv run crmbuilder
```

## Documentation Generator

Generate the CRM reference manual from YAML program files:

```bash
uv run python tools/generate_docs.py
```

This reads all YAML files from `data/programs/` and produces:
- `PRDs/generated/CBM-CRM-Reference.md` — Markdown reference
- `PRDs/generated/CBM-CRM-Reference.docx` — Word document reference

Options:
```
--programs   data/programs/          YAML program files directory
--output     PRDs/generated/         Output directory
--format     both                    docx, md, or both
--title      CBM CRM Implementation Reference
--version    (from first YAML file)
```

You can also use the **Generate Docs** button in the application UI.

## Documentation

- [User Guide](docs/user-guide.md)
- [Technical Guide](docs/technical-guide.md)
