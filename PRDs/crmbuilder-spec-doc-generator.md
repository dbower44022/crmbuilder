# CRM Builder — Documentation Generator Specification

**Version:** 1.0  
**Status:** Draft  
**Script:** `tools/generate_docs.py`  
**Repository:** `crmbuilder`

---

## 1. Overview

The documentation generator reads all YAML program files and produces a
structured reference manual describing the complete EspoCRM configuration
for the Cleveland Business Mentors CRM system.

The generated document is the authoritative implementation reference —
it defines what must be implemented in EspoCRM to support the requirements
stated in the client PRD documents. It replaces manually-maintained reference documents.

**The YAML files are the single source of truth.** The generated document
is always derived from them and is never edited manually.

### 1.1 Generated Outputs

| File | Format | Audience |
|---|---|---|
| `{Client}-CRM-Reference.docx` | Word document | Stakeholders, administrators |
| `{Client}-CRM-Reference.md` | Markdown | Developers, version control |

Both files are generated from the same data in a single run.

---

## 2. Invocation

```bash
python tools/generate_docs.py \
  --programs data/programs/ \
  --output PRDs/generated/
```

Options:

| Option | Default | Description |
|---|---|---|
| `--programs` | `data/programs/` | Directory containing YAML program files |
| `--output` | `PRDs/generated/` | Directory for output files |
| `--format` | `both` | Output format: `docx`, `md`, or `both` |
| `--title` | `{Client} CRM Implementation Reference` | Document title |
| `--version` | (from YAML files) | Override version string |

---

## 3. Document Structure

The generated document has the following sections in order:

```
Title Page
Table of Contents
1. Introduction
2. Entities
3. Fields
4. Layouts
5. Views (List Views)
6. Filters (Search Presets)      ← placeholder
7. Relationships                 ← placeholder
8. Processes (Dynamic Logic)     ← placeholder
Appendix A: Enum Value Reference
Appendix B: Deployment Status
```

---

## 4. Section Specifications

### 4.1 Title Page

```
Cleveland Business Mentors
CRM Implementation Reference

Generated from YAML program files
Version: {version}
Generated: {timestamp}

This document defines the EspoCRM configuration required to support
the requirements specified in the client PRD documents. It is generated
automatically from the YAML program files and must not be edited manually.
To update this document, update the YAML files and regenerate.
```

Version is taken from the `version` field of the first YAML file loaded,
or from the `--version` argument.

### 4.2 Introduction

Fixed text explaining:
- What this document is
- How it relates to the PRD documents
- How to use it as a reference
- How to regenerate it
- A note that sections marked "Planned — Not Yet Implemented" describe
  future capability not yet supported by the deployment tool

### 4.3 Section 2 — Entities

One subsection per entity, ordered by deployment phase:

```
2.1 Account (Company)
2.2 Contact
2.3 Engagement
2.4 Session
2.5 NPS Survey Response
2.6 Workshop
2.7 Workshop Attendance
2.8 Dues
```

Each entity subsection contains:

**Entity header table:**

| Property | Value |
|---|---|
| EspoCRM Entity Name | Account |
| Display Name (Singular) | Company |
| Display Name (Plural) | Companies |
| Entity Type | Native (Account) |
| Stream Enabled | No |
| Deployment Method | Field configuration only |

For custom entities, show:

| Property | Value |
|---|---|
| EspoCRM Entity Name | CEngagement |
| Display Name (Singular) | Engagement |
| Display Name (Plural) | Engagements |
| Entity Type | Custom (Base) |
| Stream Enabled | Yes |
| Deployment Method | delete_and_create |

**Brief description** — from the entity's `description` property in the YAML.
This is now a required property on all entity blocks. It explains the entity's
purpose, role in the data model, and PRD reference. Read directly from the
YAML `description` property — do not hardcode entity descriptions in the
generator. If an entity has no description, log an INFO warning and use
"No description provided."

### 4.4 Section 3 — Fields

One subsection per entity in the same order as Section 2. Each entity
subsection contains a field table.

**Field table columns:**

| Field Name | Internal Name | Type | Required | Category | Description | Notes |
|---|---|---|---|---|---|---|
| Contact Type | cContactType | Enum | Yes | Personal Information | Classifies contact as Mentor or Client... | Values: Mentor, Client |
| Mentor Status | cMentorStatus | Enum | Yes | Mentor Role & Capacity | Tracks mentor lifecycle progression... | See Appendix A |
| Is Mentor | cIsMentor | Boolean | No | Mentor Role & Capacity | Flags eligibility for primary mentor assignments... | Default: false |
| Professional Bio | cProfessionalBio | Rich Text | No | Mentor Biographical | Narrative professional background... | — |

Column definitions:
- **Field Name** — the display label from YAML
- **Internal Name** — the c-prefixed EspoCRM field name (e.g. `cContactType`)
- **Type** — human-readable type name (use the guide type vocabulary: Boolean,
  Integer, Enum, Multi-select, Rich Text, etc. — reverse map from YAML type)
- **Required** — Yes / No / Auto
- **Category** — the YAML `category` value, or "—" if not set
- **Description** — the YAML `description` property for the field, truncated
  to 200 characters if longer. If no description, show "—" and flag as INFO
  in the generator log.
- **Notes** — for enum fields with ≤ 6 values: list inline. For enum fields
  with > 6 values: "See Appendix A". For other notes: readOnly, default value.

**YAML type → display type reverse mapping:**

| YAML Type | Display Type |
|---|---|
| `varchar` | Text |
| `text` | Text (multi-line) |
| `wysiwyg` | Rich Text |
| `bool` | Boolean |
| `int` | Integer |
| `float` | Decimal |
| `date` | Date |
| `datetime` | Date/Time |
| `enum` | Enum |
| `multiEnum` | Multi-select |
| `url` | URL |
| `email` | Email |
| `phone` | Phone |
| `currency` | Currency |

**Internal name derivation:**
Apply the c-prefix rule: `c` + uppercase first letter + rest of name.
Example: `contactType` → `cContactType`.
Native entities use field names as-is for native fields; apply c-prefix
only for custom fields (those defined in the YAML fields list).

**Grouping within the table:**
Group rows by `category`. Insert a subtle category header row between
groups. Fields with no category appear at the top under "General".

### 4.5 Section 4 — Layouts

One subsection per entity. Describes the detail view panel and tab
structure in human-readable form.

For each entity:

**4.x.1 Detail View**

Describe each panel as a numbered subsection:

```
Panel 1: Overview (Tab)
  Fields: First Name, Last Name, Email Address, Phone, Address,
          LinkedIn Profile, Preferred Name, Middle Name, Contact Type

Panel 2: Client Details (Tab — visible when Contact Type = Client)
  Tab: Client Details
    Fields: Role at Business, Primary Contact, Zip Code

Panel 3: Mentor Details (Tab — visible when Contact Type = Mentor)
  Sub-tabs:
    Identity: Personal Email, Gmail Address, Professional Title,
              Current Employer, Currently Employed, Years of Experience
    Biographical: Professional Bio, Why Interested in Mentoring,
                  How Did You Hear About Us
    Skills: NAICS Sectors, Mentoring Focus Areas, Skills & Expertise Tags,
            Fluent Languages
    Capacity: Is Mentor, Is Co-Mentor, Is SME, Mentor Status,
              Accepting New Clients, Maximum Client Capacity,
              Current Active Clients, Available Capacity
    Administrative: Ethics Agreement Accepted, Ethics Agreement Date,
                    Terms & Conditions Accepted, T&C Date,
                    Background Check Completed, Background Check Date,
                    Felony Conviction, Moodle Training Completed,
                    Moodle Completion Date, Dues Status, Dues Payment Date,
                    Departure Reason, Departure Date
```

For panels with `dynamicLogicVisible`, show the condition in parentheses.
For sub-tabs, show fields in the order they would appear via auto-row generation.

**4.x.2 List View**

Simple column table:

| # | Field | Width |
|---|---|---|
| 1 | Name | 20% |
| 2 | Contact Type | 10% |
| 3 | Email Address | 20% |

### 4.6 Section 5 — Views (List Views)

**Status: Defined in YAML — Implemented**

This section documents the list view column definitions for each entity,
derived from the `layout.list` sections in the YAML files.

Present as a table per entity (same content as 4.x.2 but collected here
as a standalone reference).

### 4.7 Section 6 — Filters (Search Presets)

**Status: Planned — Not Yet Implemented**

```
This section will define the named search presets (saved views) configured
in EspoCRM for each entity. Search presets allow administrators and mentors
to quickly access commonly-used filtered views of CRM data.

Search preset definitions will be added to the YAML program files in a
future release of the implementation tool. When implemented, this section
will be generated automatically from those definitions.

Planned search presets are documented in the client PRD documents.
```

### 4.8 Section 7 — Relationships

**Status: Planned — Not Yet Implemented**

```
This section will define the relationships between entities — the links
that allow EspoCRM to connect related records across entity types.

Relationship definitions will be added to the YAML program files in a
future release of the implementation tool. When implemented, this section
will be generated automatically from those definitions.

Planned relationships include:
  - Account (Company) → Contact (one-to-many)
  - Account (Company) → Engagement (one-to-many)
  - Engagement → Contact / Assigned Mentor (many-to-one)
  - Engagement → Session (one-to-many)
  - Engagement → NPS Survey Response (one-to-many)
  - Workshop → Workshop Attendance (one-to-many)
  - Contact → Workshop Attendance (one-to-many)
  - Contact → Dues (one-to-many)
```

### 4.9 Section 8 — Processes (Dynamic Logic & Automation)

**Status: Partially Defined — Not Yet Implemented by Tool**

```
This section defines conditional field behavior (Dynamic Logic) and
automated field-setting rules (Entity Formula Scripts) configured in
EspoCRM.

Dynamic Logic and formula script definitions will be added to the YAML
program files in a future release. When implemented, this section will
be generated automatically.

Currently defined processes (configured manually):
```

List any dynamic logic or formula rules that are documented in the YAML
files via comments. For now, include a hardcoded table of known planned
processes:

| Entity | Trigger | Condition | Action |
|---|---|---|---|
| Contact | Display | Contact Type = Mentor | Show Mentor panels |
| Contact | Display | Contact Type = Client | Show Client Details panel |
| Contact | Display | Mentor Status = Departed | Show Departure Reason, Departure Date |
| Session | Display | Session Type = In-Person | Show Meeting Location Type |
| Session | Display | Meeting Location Type = Other | Show Location Details |
| Account | Display | Registered with State = Yes | Show registration fields |
| Engagement | On Save | Status changed to Assigned AND Mentor Assigned Date is empty | Set Mentor Assigned Date = today |

### 4.10 Appendix A — Enum Value Reference

For every enum or multiEnum field with more than 6 options, list all values
in a table organized by entity and field.

Format:

```
A.1 Contact

  A.1.1 NAICS Sectors
  11 - Agriculture, Forestry, Fishing
  21 - Mining, Quarrying, Oil & Gas
  ...

  A.1.2 Mentoring Focus Areas
  Business Planning & Strategy
  Marketing & Sales
  ...

A.2 Account

  A.2.1 NAICS Sector
  ...
```

### 4.11 Appendix B — Deployment Status

A summary table of all entities and what has been deployed via the tool:

| Entity | Fields | Layout | Relationships | Status |
|---|---|---|---|---|
| Account | ✓ Defined | ✓ Defined | Planned | Ready to deploy |
| Contact | ✓ Defined | ✓ Defined | Planned | Ready to deploy |
| Engagement | ✓ Defined | ✓ Defined | Planned | Ready to deploy |
| Session | ✓ Defined | ✓ Defined | Planned | Ready to deploy |
| NPS Survey Response | ✓ Defined | ✓ Defined | Planned | Ready to deploy |
| Workshop | ✓ Defined | ✓ Defined | Planned | Ready to deploy |
| Workshop Attendance | ✓ Defined | ✓ Defined | Planned | Ready to deploy |
| Dues | ✓ Defined | ✓ Defined | Planned | Ready to deploy |

Status is derived automatically:
- "Ready to deploy" — fields and layouts defined in YAML
- "Partially defined" — fields defined, layout missing or incomplete
- "Planned" — entity referenced but no YAML file found

---

## 5. Architecture

```
tools/
└── generate_docs.py           # Entry point

tools/docgen/
├── __init__.py
├── yaml_loader.py             # Load and index all YAML program files
├── builders/
│   ├── __init__.py
│   ├── entity_builder.py      # Section 2 — Entities
│   ├── field_builder.py       # Section 3 — Fields
│   ├── layout_builder.py      # Section 4 — Layouts
│   ├── view_builder.py        # Section 5 — Views
│   ├── placeholder_builder.py # Sections 6, 7, 8 — Placeholders
│   └── appendix_builder.py    # Appendices A and B
├── renderers/
│   ├── __init__.py
│   ├── md_renderer.py         # Renders to Markdown
│   └── docx_renderer.py       # Renders to Word document
└── models.py                  # Internal document model
```

### 5.1 Internal Document Model

The builders produce a language-agnostic document model which the renderers
then convert to the target format. This ensures Markdown and DOCX outputs
are always identical in content.

```python
@dataclass
class DocSection:
    title: str
    level: int              # heading level 1-4
    content: list           # list of DocBlock objects

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
class DocDocument:
    title: str
    subtitle: str
    version: str
    timestamp: str
    sections: list[DocSection]
```

### 5.2 Dependencies

```
pyyaml          # Read YAML program files
python-docx     # Generate .docx output
```

---

## 6. DOCX Formatting

The `.docx` output uses professional formatting consistent with the
existing client PRD documents.

- **Title page:** Client logo placeholder, document title, generated date
- **Headings:** Heading 1 for major sections, Heading 2 for entities,
  Heading 3 for subsections
- **Tables:** Banded rows, header row shaded, consistent column widths
- **Status callouts:** "Planned — Not Yet Implemented" sections use an
  Info-style box (light blue background)
- **Font:** Calibri 11pt body, Calibri Light headings
- **Page numbering:** Footer with page number and document title
- **Table of contents:** Auto-generated Word TOC field

Use the `docx` skill (`/mnt/skills/public/docx/SKILL.md`) for
implementation guidance.

---

## 7. Markdown Formatting

The `.md` output uses standard GitHub Markdown:

- `#` for major sections
- `##` for entity subsections
- `###` for sub-subsections
- Pipe tables for all tabular data
- `> **Note:**` blockquote for status callouts
- Code blocks for field names and internal identifiers

---

## 8. Regeneration Workflow

When the Implementation Guide needs updating:

1. Update the relevant YAML program file(s)
2. Run `python tools/generate_docs.py`
3. Review the generated reference document
4. Commit both the updated YAML files and the generated document to the repo

The generated document is committed to the repo so stakeholders can access
it without running the generator themselves.

---

## 9. Future Enhancements

As new YAML capabilities are added to the implementation tool, extend the
generator to populate the placeholder sections:

- **Section 6 (Filters):** Generate from search preset YAML definitions
- **Section 7 (Relationships):** Generate from relationship YAML definitions
- **Section 8 (Processes):** Generate from dynamic logic and formula YAML definitions
- **Appendix C (Role-Based Access):** Generate from role YAML definitions
