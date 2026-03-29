# CRM Builder — Documentation Generator

**Version:** 2.0
**Status:** Current
**Last Updated:** March 2026
**Depends On:** app-yaml-schema.md, app-document-architecture.md,
               feat-entities.md, feat-fields.md,
               feat-layouts.md, feat-relationships.md

---

## 1. Purpose

This document defines the requirements for the Documentation Generator
in CRM Builder — the feature that produces the Verification Spec
(Level 4 in the document hierarchy) from the YAML program files.

The Verification Spec is a QA artifact, not a requirements document.
Its sole purpose is to allow the administrator to confirm that the
YAML configuration faithfully represents what the PRDs require. It is
generated after YAML files are produced and reviewed before go-live.

The document hierarchy, document purposes, and the role of the
Verification Spec within the overall requirements process are defined
in `app-document-architecture.md`. This document defines the
generation process and output format specific to the Verification Spec.

The Verification Spec does not replace or supersede the Master PRD
or Domain PRDs. Those documents are the source of truth for all
requirements. The Verification Spec answers one question only:
does the YAML match what the PRDs require?

---

## 2. Design Principles

**Generated, never edited manually.** The Verification Spec is always
derived from the YAML program files. It must never be edited by hand.
To update it, update the YAML files and regenerate.

**YAML is the source for this document only.** All content in the
Verification Spec — entity descriptions, field descriptions, layout
structure, enum values — comes from the YAML files. The PRDs are the
source of truth for requirements. The Verification Spec reflects what
the YAML contains, which should match the PRDs.

**A QA tool, not a stakeholder document.** The Verification Spec is
for the implementation team to confirm configuration correctness. It
is not distributed to stakeholders. Stakeholders receive the Master
PRD and Domain PRDs.

**Dual format output.** The generator produces both a Word document
and a Markdown file for version control and developer reference.
Both formats are produced from the same data in a single run and
are always identical in content.

---

## 3. Trigger and Output Location

### 3.1 From the Application UI

The Generate Docs button in the main window triggers the generator.
The button is enabled when the selected instance has a project folder
configured with at least one YAML file in its `programs/` directory.

If no project folder is configured, the output panel shows a message
prompting the user to configure one.

### 3.2 Output Files

Output files are written to the instance's `Implementation Docs/`
directory within the project folder. Files are named after the
instance:

```
{Instance Name}-Verification-Spec.md
{Instance Name}-Verification-Spec.docx
```

For example, an instance named "CBM Demo CRM" produces:
```
CBM Demo CRM-Verification-Spec.md
CBM Demo CRM-Verification-Spec.docx
```

### 3.3 Command Line

The generator may also be invoked from the command line, specifying
the programs directory and output directory explicitly. Command line
usage is intended for automation and CI/CD integration.

---

## 4. Document Structure

The generated document has the following sections in order:

```
Title Page
Table of Contents
1. Introduction
2. Entities
3. Fields
4. Layouts
5. List Views
6. Filters (Search Presets)      ← placeholder — not yet implemented
7. Relationships                 ← placeholder — not yet implemented
8. Processes (Dynamic Logic)     ← placeholder — not yet implemented
Appendix A: Enum Value Reference
Appendix B: Deployment Status
```

Sections marked as placeholders include a fixed explanatory note
stating that the capability is planned but not yet implemented by
the deployment tool, and describing what will appear there when it is.

---

## 5. Section Specifications

### 5.1 Title Page

The title page includes:
- Organization name (derived from the instance name or YAML metadata)
- Document title: "CRM Verification Spec"
- A statement that the document is generated from YAML program files
  and must not be edited manually
- The document version (taken from the first YAML file loaded, or
  overridden via command line argument)
- The generation timestamp

### 5.2 Introduction

A fixed explanatory section covering:
- What this document is and who it is for — a QA artifact for the
  implementation team, not a stakeholder document
- How it relates to the Master PRD and Domain PRDs — those documents
  define requirements; this document confirms the YAML matches them
- How to use it to verify configuration correctness
- How to regenerate it when YAML files are updated
- An explanation of placeholder sections

### 5.3 Section 2 — Entities

One subsection per entity, ordered by deployment phase as defined
in the YAML files. Each entity subsection contains:

**An entity header table** showing:
- CRM entity name
- Display name (singular and plural)
- Entity type (native or custom, with base type if custom)
- Whether the stream panel is enabled
- Deployment method

**A description** — read directly from the entity's `description`
property in the YAML. If an entity has no description, a warning
is logged and "No description provided." is shown.

### 5.4 Section 3 — Fields

One subsection per entity in the same order as Section 2. Each entity
subsection contains a field table using a two-row format per field:

**Row 1 — Field data:**

| Field Name | Internal Name | Type | Required | Category | Notes |
|---|---|---|---|---|---|
| Contact Type | cContactType | Enum | No | Personal Info | Values: Mentor, Client |

**Row 2 — Description (spans full width):**

A second row immediately beneath each field row spans all columns
and displays the field's full description in readable prose. This
gives descriptions sufficient space to be read comfortably by both
administrators and stakeholders without truncation.

```
┌─────────────┬───────────────┬──────┬──────────┬───────────────┬────────────────┐
│ Field Name  │ Internal Name │ Type │ Required │ Category      │ Notes          │
├─────────────┼───────────────┼──────┼──────────┼───────────────┼────────────────┤
│ Contact Type│ cContactType  │ Enum │ No       │ Personal Info │ Values: Mentor,│
│             │               │      │          │               │ Client         │
├─────────────┴───────────────┴──────┴──────────┴───────────────┴────────────────┤
│   Classifies the contact as a Mentor or Client. Drives conditional             │
│   visibility of Mentor and Client detail panels. See PRD Section 4.1.         │
├─────────────┬───────────────┬──────┬──────────┬───────────────┬────────────────┤
│ Mentor      │ cMentorStatus │ Enum │ No       │ Mentor Role & │ See Appendix A │
│ Status      │               │      │          │ Capacity      │                │
├─────────────┴───────────────┴──────┴──────────┴───────────────┴────────────────┤
│   Tracks the lifecycle stage of a mentor from Provisional through Active,      │
│   Inactive, and Departed. Drives visibility of departure fields.               │
│   See PRD Section 4.2.                                                         │
└─────────────┴───────────────┴──────┴──────────┴───────────────┴────────────────┘
```

Field descriptions are shown in full — no truncation. If a field
has no description, the description row shows "No description
provided." in italics and an informational warning is logged.

**Notes column content:**
- Enum fields with ≤6 values: list values inline
- Enum fields with >6 values: "See Appendix A"
- Read-only fields: "Read only"
- Fields with a default value: "Default: {value}"

Fields within the table are grouped by category. A shaded category
header row separates each group. Fields with no category appear
first under "General".

### 5.5 Section 4 — Layouts

One subsection per entity. Describes the detail view panel and tab
structure in human-readable prose and structured lists. For each panel:
- Panel name and tab label
- Dynamic visibility condition, if any
- List of fields in the panel or sub-tab, in display order

### 5.6 Section 5 — List Views

One subsection per entity showing the list view columns as a simple
table with field name and column width.

### 5.7 Sections 6, 7, 8 — Placeholders

Each placeholder section includes:
- A status note: "Planned — Not Yet Implemented"
- An explanation of what the section will contain when implemented
- For Section 7 (Relationships), a list of the planned relationships
  as defined in the YAML `relationships` block, even though
  relationship deployment is not yet reflected here

### 5.8 Appendix A — Enum Value Reference

For every enum or multi-select field with more than six options,
lists all values in a table organized by entity and field. Fields
with six or fewer options have their values listed inline in the
Section 3 field table.

### 5.9 Appendix B — Deployment Status

A summary table of all entities showing what has been defined in
the YAML and what has been deployed. Status is derived automatically:

| Status | Condition |
|---|---|
| Ready to deploy | Fields and layout defined in YAML |
| Partially defined | Fields defined, layout missing or incomplete |
| Planned | Entity referenced but no YAML file found |

---

## 6. Content Requirements

### 6.1 Entity Descriptions

Entity descriptions are read directly from the `description` property
in the YAML entity block. The generator does not generate or infer
descriptions — it reports what is in the YAML.

If an entity is missing a description, the generator logs an
informational warning and uses "No description provided." in the
document.

### 6.2 Field Descriptions

Field descriptions are read from the `description` property on each
field definition. Descriptions are displayed in full in the sub-row
beneath each field — no truncation is applied. This ensures
stakeholders can read the complete business rationale for each field
without needing to consult the YAML files directly.

Fields missing a description show "No description provided." in the
description sub-row, and an informational warning is logged during
generation.

### 6.3 Type Display Names

YAML type identifiers are translated to human-readable display names
in the generated document:

| YAML Type | Display Name |
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

### 6.4 Entity Ordering

Entities appear in the document in a canonical order defined by their
sequence in the YAML program files. The canonical order should reflect
the logical data model — foundational entities (Account, Contact)
before dependent entities (Engagement, Session, etc.).

---

## 7. Output Format Requirements

### 7.1 Word Document (.docx)

The Word document uses professional formatting suitable for sharing
with stakeholders and clients:

- A title page with the organization name and generation timestamp
- Heading styles for sections, entity subsections, and sub-subsections
- Banded rows in all tables with a shaded header row
- A status callout style for placeholder sections
  (visually distinct from body text)
- An auto-generated table of contents
- Page numbers in the footer alongside the document title

### 7.2 Markdown (.md)

The Markdown document uses standard GitHub-flavored Markdown:

- `#` through `####` for heading levels
- Pipe tables for all tabular data
- Blockquote style for placeholder section status notes
- Code formatting for field names and internal identifiers

Both formats are generated from the same internal document model
in a single run. They are always identical in content.

---

## 8. Regeneration Workflow

The Verification Spec should be regenerated whenever YAML program
files are updated. The expected workflow:

1. Update the relevant YAML program file(s)
2. Click Generate Docs (or run the command line tool)
3. Review the Verification Spec against the relevant Domain PRD
   sections to confirm the YAML matches requirements
4. Commit both the updated YAML files and the regenerated
   Verification Spec to the client repository

The Verification Spec is committed to the client repository so the
implementation team can review it without running the generator.
It is not distributed to stakeholders — stakeholders receive
the Master PRD and Domain PRDs.

---

## 9. Future Considerations

As new YAML capabilities are added, the corresponding placeholder
sections become fully generated:

- **Section 6 — Filters** — generated from search preset definitions
  when that feature is implemented
- **Section 7 — Relationships** — generated from relationship
  definitions in the YAML `relationships` block
- **Section 8 — Processes** — generated from dynamic logic and formula
  definitions when those features are implemented
- **Appendix C — Role-Based Access** — generated from role definitions
  when the security feature is implemented
- **Multi-language support** — generating documents in languages other
  than English using the `translatedOptions` values already present
  in the YAML schema

---

*This document defines the Documentation Generator feature within the
CRM Builder document architecture. The governing document architecture,
identifier scheme, and document hierarchy are defined in
`app-document-architecture.md`.*
