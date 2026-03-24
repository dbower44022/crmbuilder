# Claude Code Prompt — Description Property + Documentation Generator

## Context

This prompt covers two related tasks:

1. **Add `description` property support** to the CRM Builder
2. **Build the Documentation Generator** that reads YAML files and produces
   a reference manual in `.docx` and `.md` formats

The YAML files are the single source of truth. The `description` property
transforms them from pure technical specs into self-documenting design artifacts.
The documentation generator produces a reference manual directly from the YAML,
replacing the manually-maintained Implementation Guide.

Key specifications:
- `PRDs/CBM-SPEC-espocrm-impl.md` (v1.5) — main tool spec
- `PRDs/CBM-SPEC-layout-management.md` — layout spec (panel description)
- `PRDs/CBM-SPEC-doc-generator.md` — documentation generator spec

Read all three before writing any code.
Also read `/mnt/skills/public/docx/SKILL.md` before implementing the DOCX renderer.

---

## Part 1 — Description Property Support

### Task 1 — Update `core/models.py`

Add `description` to `EntityDefinition`:
```python
description: str | None = None    # required on entities, optional on fields
```

Add `description` to `FieldDefinition`:
```python
description: str | None = None    # business rationale and PRD reference
```

Add `description` to `PanelSpec` (in layout models):
```python
description: str | None = None    # business rationale for this panel grouping
```

### Task 2 — Update `core/config_loader.py`

**Parse description on entities:**
```python
description=entity_data.get("description"),
```

**Parse description on fields** in `_parse_field()`:
```python
description=data.get("description"),
```

**Parse description on panels** in `_parse_panel()`:
```python
description=data.get("description"),
```

**Add validation:**
- Entity blocks without a `description` → WARNING (not ERROR — backward compatible)
- Fields without a `description` → INFO in generator output only, no validation error

### Task 3 — Tests

Add to `tests/test_config_loader.py`:
- Entity description parsed correctly
- Field description parsed correctly
- Panel description parsed correctly
- Entity without description passes validation with WARNING
- Field without description passes validation (no warning from validator)

Run `uv run pytest tests/ -v` and confirm passing before Part 2.

---

## Part 2 — Documentation Generator

Build a documentation generator that reads all YAML program files and produces
a structured reference manual. Full specification in `PRDs/CBM-SPEC-doc-generator.md`.

### Task 4 — Project Structure

Create:
```
tools/
└── generate_docs.py               # Entry point

tools/docgen/
├── __init__.py
├── models.py                      # Internal document model
├── yaml_loader.py                 # Load and index YAML program files
├── builders/
│   ├── __init__.py
│   ├── entity_builder.py          # Section 2 — Entities
│   ├── field_builder.py           # Section 3 — Fields
│   ├── layout_builder.py          # Section 4 — Layouts
│   ├── view_builder.py            # Section 5 — Views
│   ├── placeholder_builder.py     # Sections 6, 7, 8 — Placeholders
│   └── appendix_builder.py        # Appendices A and B
└── renderers/
    ├── __init__.py
    ├── md_renderer.py             # Renders to Markdown
    └── docx_renderer.py           # Renders to Word document
```

Add `python-docx` to `pyproject.toml` if not already present.

### Task 5 — Internal Document Model (`tools/docgen/models.py`)

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class DocTable:
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None

@dataclass
class DocParagraph:
    text: str
    style: str = "normal"   # "normal", "note", "code", "status"

@dataclass
class DocSection:
    title: str
    level: int              # 1=H1, 2=H2, 3=H3, 4=H4
    content: list[Any]      # DocTable, DocParagraph, or nested DocSection

@dataclass
class DocDocument:
    title: str
    subtitle: str
    version: str
    timestamp: str
    sections: list[DocSection]
```

### Task 6 — YAML Loader (`tools/docgen/yaml_loader.py`)

```python
ENTITY_ORDER = [
    "Account", "Contact", "Engagement", "Session",
    "NpsSurveyResponse", "Workshop", "WorkshopAttendance", "Dues",
]

ENTITY_DISPLAY_NAMES = {
    "Account": "Company",
    "NpsSurveyResponse": "NPS Survey Response",
    "WorkshopAttendance": "Workshop Attendance",
}

def load_programs(programs_dir: Path) -> dict[str, dict]:
    """Load all YAML files. Returns dict[entity_name → entity_dict]."""
```

- Load all `.yaml` and `.yml` files from `programs_dir`
- Build index keyed by natural entity name
- Preserve field order from YAML
- Warn if same entity appears in multiple files

### Task 7 — Builders

Implement each builder per the spec in `PRDs/CBM-SPEC-doc-generator.md`.

**Critical behavior for descriptions:**

**Entity builder** — read description from `entity_data.get("description")`.
If missing, use "No description provided." and log INFO.

**Field builder** — add Description as a column in the field table:
- Read from `field.get("description")`
- Truncate to 200 characters if longer (append "..." if truncated)
- Show "—" if no description, log INFO for generator summary

**Field builder column order:**
`Field Name | Internal Name | Type | Required | Category | Description | Notes`

**Panel/Layout builder** — for each panel that has a `description`, include
it as a paragraph below the panel header in the layout section.

**All other builder behavior** — follow spec Section 4 exactly.

### Task 8 — Markdown Renderer (`tools/docgen/renderers/md_renderer.py`)

```python
def render(doc: DocDocument) -> str:
    """Render DocDocument to Markdown string."""
```

- Level 1-4 sections → `#` through `####`
- DocTable → GitHub pipe table
- DocParagraph `"normal"` → plain paragraph
- DocParagraph `"note"` → `> **Note:** {text}`
- DocParagraph `"status"` → `> ⚠️ **{text}**`
- DocParagraph `"code"` → `` `{text}` ``
- Nested DocSections rendered recursively

### Task 9 — DOCX Renderer (`tools/docgen/renderers/docx_renderer.py`)

**Read `/mnt/skills/public/docx/SKILL.md` before implementing this task.**

```python
def render(doc: DocDocument, output_path: Path) -> None:
    """Render DocDocument to .docx file."""
```

Follow the DOCX skill pattern exactly:
- US Letter page size (12240 × 15840 DXA), 1-inch margins
- Override Heading1 through Heading4 styles
- Body font: Calibri 11pt
- Tables: banded rows, bold header row with shading
- `"status"` paragraphs: light blue shaded single-cell table (info box)
- Page footer: page number centered
- Table of contents after title page

### Task 10 — Entry Point (`tools/generate_docs.py`)

```python
def main():
    args = parse_args()
    entities = load_programs(args.programs)
    doc = build_document(entities, args)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.format in ("md", "both"):
        md_path = output_dir / "CBM-CRM-Reference.md"
        md_path.write_text(md_renderer.render(doc), encoding="utf-8")
        print(f"Generated: {md_path}")
    if args.format in ("docx", "both"):
        docx_path = output_dir / "CBM-CRM-Reference.docx"
        docx_renderer.render(doc, docx_path)
        print(f"Generated: {docx_path}")
```

CLI options:
```
--programs   data/programs/          YAML program files directory
--output     PRDs/generated/         Output directory
--format     both                    docx, md, or both
--title      CBM CRM Implementation Reference
--version    (from first YAML file)
```

`build_document()` calls all builders in order and assembles the DocDocument.

### Task 11 — Tests (`tests/test_docgen/`)

**`test_yaml_loader.py`:**
- Loads entity with description correctly
- Loads entity without description (None value)
- Preserves field order

**`test_field_builder.py`:**
- Description column present in table
- Description truncated to 200 chars when longer
- Missing description shows "—"
- Type reverse mapping covers all types
- Internal name c-prefix applied correctly
- Fields grouped by category with header rows

**`test_layout_builder.py`:**
- Panel description rendered as paragraph
- Panel with explicit rows listed correctly
- Panel with tabs shows sub-tab structure
- dynamicLogicVisible rendered as condition string

**`test_md_renderer.py`:**
- Heading levels correct
- Tables render as valid pipe tables
- Status paragraphs render as blockquotes

Run `uv run pytest tests/test_docgen/ -v` and confirm passing before DOCX renderer.

### Task 12 — Update Spec and Guides

**`PRDs/CBM-SPEC-espocrm-impl.md`** — already at v1.5 with description in schema.
No changes needed.

**`docs/technical-guide.md`:**
- Add `description` to FieldDefinition documentation block
- Add `description` to EntityDefinition documentation block
- Add new "Documentation Generator" section covering:
  - Purpose: YAML as single source of truth
  - How to run: `uv run python tools/generate_docs.py`
  - Output files: CBM-CRM-Reference.md and CBM-CRM-Reference.docx
  - When to regenerate: whenever YAML files are updated

**`docs/user-guide.md`:**
- Add `description` to Field Properties table with note "Optional. Business
  rationale for the field. Appears in the generated reference document."
- Add new "Generating Documentation" section:
  > After updating YAML program files, regenerate the reference manual:
  > ```bash
  > uv run python tools/generate_docs.py
  > ```
  > This produces CBM-CRM-Reference.docx and CBM-CRM-Reference.md in
  > PRDs/generated/. Commit both files alongside the updated YAML files.

**`README.md`:**
Add "Documentation Generator" section as specified in the doc generator spec.

---

## Task 13 — Integrate Generate Docs into the UI

Add a **Generate Docs** button to the main window, positioned in the bottom
bar alongside Clear Output and View Report.

**Behavior:**
- Enabled whenever at least one program file is loaded in the programs directory
- Does NOT require an instance to be selected (no EspoCRM connection needed)
- Runs synchronously in a background thread (use QThread like other operations)
- Output appears in the output panel:
  ```
  [DOCGEN]  Loading program files from data/programs/ ...
  [DOCGEN]  Loaded 8 entities, 127 fields
  [DOCGEN]  Generating CBM-CRM-Reference.md ...
  [DOCGEN]  Generating CBM-CRM-Reference.docx ...
  [DOCGEN]  Done. Reports written to PRDs/generated/
  ```
- After completion, View Report button opens the generated `.log` file as usual,
  but also enable a new **Open Reference Doc** button that opens the `.docx`

**UI placement:**
```
[Clear Output]    [Generate Docs]    [Open Reference Doc]    [View Report]
```

**Open Reference Doc** button:
- Disabled until Generate Docs has been run
- Opens `PRDs/generated/CBM-CRM-Reference.docx` in the system default viewer
- Uses `QDesktopServices.openUrl()` like the View Report button

---

## Implementation Order

1. Task 1 — models.py (description property)
2. Task 2 — config_loader.py (parse description)
3. Task 3 — tests for description (confirm passing)
4. Task 5 — docgen/models.py
5. Task 6 — yaml_loader.py
6. Task 7 — field_builder.py (most complex, do first)
7. Task 11 — field_builder tests (confirm passing)
8. Task 7 — remaining builders
9. Task 8 — md_renderer.py
10. Task 11 — remaining tests (confirm passing)
11. Task 9 — docx_renderer.py (read DOCX skill first)
12. Task 10 — entry point
13. Task 13 — UI integration
14. Task 12 — spec and guide updates

Confirm with me after step 3 (description tests passing), after step 10
(all non-DOCX tests passing), and after step 11 (DOCX renderer working)
before proceeding.

---

## Important Notes

### Description as YAML block scalar
The `description` property in YAML uses block scalar syntax (`>`):
```yaml
description: >
  Multi-line description text that wraps
  across lines in the YAML file but is
  treated as a single paragraph.
```
The `>` folded scalar collapses newlines into spaces. The parser should
read this as a single string — `pyyaml` handles this automatically.

### Entity display names
Always use the friendly display name in the generated document:
- `Account` → "Company"  
- `NpsSurveyResponse` → "NPS Survey Response"
- `WorkshopAttendance` → "Workshop Attendance"

### Entity descriptions for native entities
Account and Contact are native EspoCRM entities — they have no `action`
property in their YAML. Their `description` property works the same way
as custom entities. If missing, show "No description provided."

### Field description truncation
When rendering descriptions in the field table, truncate to 200 characters
and append "..." if the description is longer. Full descriptions appear in
the layout section where space is less constrained. In the DOCX renderer,
use a smaller font size (9pt) for description cells to keep tables readable.

### Programs directory for Generate Docs button
The Generate Docs button uses the same `data/programs/` directory as the
Program File panel. It reads all YAML files from that directory, not just
the currently selected one. This ensures the reference document always
covers the complete configuration.
