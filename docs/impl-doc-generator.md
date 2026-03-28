# CRM Builder — Documentation Generator Implementation Reference

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Requirements:** PRDs/features/feat-doc-generator.md
**Maintained By:** Claude Code

---

## 1. Purpose

This document describes the implementation of the documentation
generator in CRM Builder — the architecture, internal document model,
builders, renderers, YAML loading, and integration with the main
application UI.

---

## 2. File Locations

```
tools/generate_docs.py              # CLI entry point
tools/docgen/
├── __init__.py
├── models.py                       # Internal document model
├── yaml_loader.py                  # Load and index YAML program files
├── builders/
│   ├── __init__.py
│   ├── entity_builder.py           # Section 2 — Entities
│   ├── field_builder.py            # Section 3 — Fields
│   ├── layout_builder.py           # Section 4 — Layouts
│   ├── view_builder.py             # Section 5 — List Views
│   ├── placeholder_builder.py      # Sections 6, 7, 8 — Placeholders
│   └── appendix_builder.py         # Appendix A (enum values) + B (status)
└── renderers/
    ├── __init__.py
    ├── md_renderer.py              # Markdown output
    └── docx_renderer.py            # Word document output
```

---

## 3. Dependencies

| Package | Purpose |
|---|---|
| `pyyaml` | Read YAML program files |
| `python-docx` | Generate `.docx` output |

Node.js is no longer required. The generator uses `python-docx`
directly for Word document generation.

---

## 4. Internal Document Model (`tools/docgen/models.py`)

The builders produce a language-agnostic document model. The renderers
convert it to Markdown or DOCX. This ensures both output formats are
always identical in content.

```python
@dataclass
class DocParagraph:
    text: str
    style: str = "normal"    # "normal", "note", "code", "status"

@dataclass
class DocTable:
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None

@dataclass
class DocSection:
    title: str
    level: int               # heading level 1–4
    content: list            # list of DocParagraph | DocTable | DocSection

@dataclass
class DocDocument:
    title: str
    subtitle: str
    version: str
    timestamp: str
    sections: list[DocSection]
```

Content items within a `DocSection` may be `DocParagraph`,
`DocTable`, or nested `DocSection` objects (for subsections).

---

## 5. YAML Loader (`tools/docgen/yaml_loader.py`)

### 5.1 Loading

```python
def load_programs(programs_dir: Path) -> list[dict]:
    """
    Load all .yaml files from programs_dir.
    Returns list of raw YAML dicts in filename order.
    """
    files = sorted(programs_dir.glob("*.yaml"))
    return [yaml.safe_load(f.read_text()) for f in files]
```

### 5.2 Entity Index

```python
def build_entity_index(programs: list[dict]) -> dict[str, dict]:
    """
    Returns {entity_name: entity_dict} merged across all program files.
    Later files override earlier files for the same entity.
    """
```

### 5.3 Canonical Entity Order

Entities appear in the document in a defined canonical order. Entities
not in the canonical list appear at the end in the order they are
encountered:

```python
CANONICAL_ORDER = [
    "Account",
    "Contact",
    "Engagement",
    "Session",
    "NpsSurveyResponse",
    "Workshop",
    "WorkshopAttendance",
    "Dues",
]
```

### 5.4 Entity Display Names

Some entity names have human-readable display overrides:

```python
ENTITY_DISPLAY_NAMES = {
    "Account":             "Company",
    "NpsSurveyResponse":   "NPS Survey Response",
    "WorkshopAttendance":  "Workshop Attendance",
}

def display_name(entity_name: str) -> str:
    return ENTITY_DISPLAY_NAMES.get(entity_name, entity_name)
```

---

## 6. Type Display Name Mapping

Used by `field_builder.py` to translate YAML types to human-readable
display names:

```python
TYPE_DISPLAY_NAMES = {
    "varchar":   "Text",
    "text":      "Text (multi-line)",
    "wysiwyg":   "Rich Text",
    "bool":      "Boolean",
    "int":       "Integer",
    "float":     "Decimal",
    "date":      "Date",
    "datetime":  "Date/Time",
    "enum":      "Enum",
    "multiEnum": "Multi-select",
    "url":       "URL",
    "email":     "Email",
    "phone":     "Phone",
    "currency":  "Currency",
}
```

---

## 7. Internal Name Derivation

The c-prefix rule applied for internal field names in the document:

```python
def internal_name(field_name: str, entity_name: str) -> str:
    """
    Returns the c-prefixed internal name for custom fields.
    Native entity fields are returned as-is.
    """
    if entity_name in NATIVE_ENTITIES:
        # Native entities: only custom fields (those in YAML) get prefix
        return f"c{field_name[0].upper()}{field_name[1:]}"
    return f"c{field_name[0].upper()}{field_name[1:]}"
```

---

## 8. Builders

### 8.1 Entity Builder (`entity_builder.py`)

Produces Section 2. For each entity:

1. Build entity header table with properties from the YAML entity block
2. Add description paragraph (from `entity["description"]`)
3. Log INFO warning if description is missing

Entity type display:
- Native entity: `"Native ({entity_name})"`
- Custom entity: `"Custom ({type})"` where type is `Base`, `Person`, etc.

Deployment method display:
- Native: `"Field configuration only"`
- Custom with `delete_and_create`: `"delete_and_create"`
- Custom with `create`: `"create"`

### 8.2 Field Builder (`field_builder.py`)

Produces Section 3. For each entity, builds a field table grouped
by category using a two-row format per field.

**Category grouping:**
```python
from itertools import groupby

fields_sorted = sorted(entity_fields,
    key=lambda f: f.get("category") or "General")

for category, fields in groupby(fields_sorted,
        key=lambda f: f.get("category") or "General"):
    # Insert shaded category header row spanning all columns
    # Add field rows (two rows per field: data row + description row)
```

**Two-row format per field:**

Each field produces two rows in the output table:

Row 1 — field data:

| Column | Logic |
|---|---|
| Field Name | `field["label"]` |
| Internal Name | `internal_name(field["name"], entity_name)` |
| Type | `TYPE_DISPLAY_NAMES.get(field["type"], field["type"])` |
| Required | `"Yes"` / `"No"` from `field.get("required")` |
| Category | `field.get("category", "—")` |
| Notes | Inline enum values if ≤6, else "See Appendix A"; "Read only" if readOnly; "Default: {value}" if default set |

Row 2 — description (merged cell spanning all columns):

```python
desc = field.get("description", "")
if not desc:
    logger.info(f"  INFO: {field['name']} has no description")
    desc = "No description provided."

# In DOCX: merged cell across all columns, italic if no description
# In Markdown: indented continuation row below the field row
```

**DOCX implementation** — use `python-docx` merged cell spanning
all columns for the description row. Apply a subtle left indent
and slightly smaller font to visually distinguish it from the
field data row. If description is missing, use italic text.

**Markdown implementation** — render the description as an
indented block immediately following the field row:

```markdown
| Contact Type | cContactType | Enum | No | Personal Info | Values: Mentor, Client |
| | | | | | *Classifies the contact as Mentor or Client. Drives panel visibility. See PRD 4.1.* |
```

Alternatively, as a blockquote following the table row if the
Markdown renderer does not support merged cells cleanly.

### 8.3 Layout Builder (`layout_builder.py`)

Produces Section 4. For each entity, describes the detail view
panel structure in prose:

For each panel:
- Panel name and tab label (if tabbed)
- Dynamic visibility condition in parentheses if present
- Sub-tabs and their categories, or explicit field list

```
Panel 1: Overview (Tab)
  Fields: First Name, Last Name, Email Address, Phone

Panel 2: Mentor Details (Tab — visible when Contact Type = Mentor)
  Sub-tabs:
    Identity: Personal Email, Gmail Address, Professional Title
    Biographical: Professional Bio, Why Interested in Mentoring
```

### 8.4 View Builder (`view_builder.py`)

Produces Section 5. For each entity with a list layout defined,
builds a simple column table:

| # | Field | Width |
|---|---|---|
| 1 | Name | 25% |
| 2 | Contact Type | 15% |

### 8.5 Placeholder Builder (`placeholder_builder.py`)

Produces Sections 6, 7, and 8 with fixed placeholder text. Section 7
(Relationships) additionally renders a table of all relationships
defined in the YAML `relationships` block, even though full
relationship deployment is not yet reflected in the document.

### 8.6 Appendix Builder (`appendix_builder.py`)

**Appendix A — Enum Value Reference:**
Collects all `enum` and `multiEnum` fields with more than 6 options
across all entities. Groups by entity and field:

```python
for entity_name, entity in entity_index.items():
    for field in entity.get("fields", []):
        if field["type"] in ("enum", "multiEnum"):
            options = field.get("options", [])
            if len(options) > 6:
                # Add to appendix
```

**Appendix B — Deployment Status:**
For each entity, derives status automatically:

```python
def deployment_status(entity: dict) -> str:
    has_fields = bool(entity.get("fields"))
    has_layout = bool(entity.get("layout"))
    if has_fields and has_layout:
        return "Ready to deploy"
    if has_fields:
        return "Partially defined"
    return "Planned"
```

---

## 9. Renderers

### 9.1 Markdown Renderer (`md_renderer.py`)

Traverses the `DocDocument` model and produces GitHub-flavored
Markdown:

| Model Type | Markdown Output |
|---|---|
| `DocSection` level 1 | `# Title` |
| `DocSection` level 2 | `## Title` |
| `DocSection` level 3 | `### Title` |
| `DocSection` level 4 | `#### Title` |
| `DocParagraph` normal | Plain paragraph |
| `DocParagraph` status | `> **Status:** text` blockquote |
| `DocParagraph` code | `` `code` `` inline |
| `DocTable` | Pipe table |

### 9.2 DOCX Renderer (`docx_renderer.py`)

Uses `python-docx` to produce a formatted Word document. See the
DOCX skill at `/mnt/skills/public/docx/SKILL.md` for Word document
generation patterns.

**Style mapping:**

| Model Element | Word Style |
|---|---|
| Document title | `Title` |
| Section level 1 | `Heading 1` |
| Section level 2 | `Heading 2` |
| Section level 3 | `Heading 3` |
| Normal paragraph | `Normal` |
| Status callout | Custom shaded paragraph (light blue background) |
| Tables | Banded rows, header row shaded |

**Table of contents:**
Added as a TOC field at the start of the document. Requires the user
to press F9 in Word to update the TOC after opening the document.

---

## 10. CLI Entry Point (`tools/generate_docs.py`)

```
python tools/generate_docs.py \
  --programs data/programs/ \
  --output PRDs/generated/ \
  --format both \
  --title "CBM CRM Implementation Reference" \
  --version 1.0.0
```

| Argument | Default | Description |
|---|---|---|
| `--programs` | `data/programs/` | YAML program files directory |
| `--output` | `PRDs/generated/` | Output directory |
| `--format` | `both` | `docx`, `md`, or `both` |
| `--title` | (from instance name) | Document title override |
| `--version` | (from first YAML) | Version string override |

---

## 11. UI Integration

The **Generate Docs** button in `main_window.py` calls:

```python
def _on_generate_docs_clicked(self):
    if not self.state.instance:
        self._output("Select an instance first.", "yellow")
        return
    if not self.state.instance.project_folder:
        self._output(
            "Configure a project folder for this instance "
            "to use Generate Docs.", "yellow"
        )
        return

    programs_dir = self.state.instance.programs_dir
    docs_dir = self.state.instance.docs_dir
    instance_name = self.state.instance.name

    if not any(programs_dir.glob("*.yaml")):
        self._output("No YAML files found in programs/ directory.", "yellow")
        return

    # Run generator (currently synchronous — could be backgrounded)
    from tools.docgen import generate
    generate(
        programs_dir=programs_dir,
        output_dir=docs_dir,
        title=f"{instance_name} CRM Implementation Reference",
    )
    self._output(f"Documentation generated in: {docs_dir}", "green")
```

Output files are named after the instance:
```
{instance_name}-CRM-Reference.md
{instance_name}-CRM-Reference.docx
```

---

## 12. Testing

The doc generator is covered by `tests/test_docgen.py`:

| Test Area | Cases |
|---|---|
| YAML loading | Single file, multiple files, canonical ordering |
| Entity builder | Header table, description, missing description warning |
| Field builder | Category grouping, type mapping, description truncation |
| Appendix A | Fields with >6 options included, ≤6 excluded |
| Appendix B | Status derivation (ready/partial/planned) |
| MD renderer | Section headings, tables, status callouts |
| DOCX renderer | File produced, headings present, tables present |

Mocking pattern — tests use inline YAML dicts rather than files:

```python
def test_field_builder_groups_by_category():
    entity = {
        "fields": [
            {"name": "firstName", "type": "varchar",
             "label": "First Name", "category": "Personal"},
            {"name": "lastName", "type": "varchar",
             "label": "Last Name", "category": "Personal"},
            {"name": "mentorStatus", "type": "enum",
             "label": "Mentor Status", "category": "Mentor",
             "options": ["Active", "Inactive"]},
        ]
    }
    builder = FieldBuilder()
    section = builder.build("Contact", entity)

    table = next(c for c in section.content if isinstance(c, DocTable))
    categories = [row[4] for row in table.rows]
    assert categories.count("Personal") == 2
    assert categories.count("Mentor") == 1
```
