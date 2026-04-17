# CLAUDE-CODE-PROMPT: Domain PRD Path B Adapter

**Repo:** `dbower44022/crmbuilder`
**Date:** 04-15-26
**Goal:** Migrate the Domain PRD parser from Path A (`automation/cbm_import/`) to Path B (`automation/importer/`), fixing **Bug 8** — the Path A parser extracts only text blobs and decision identifiers. The new adapter will parse the full Domain PRD structure including personas, per-process requirement tables, 7-column consolidated field tables, 4-column decisions, and 4-column open issues.

## Context

Read `CLAUDE.md` at the repo root before starting. This work follows the same pattern as the completed Entity PRD adapter (`automation/importer/parsers/entity_prd_docx.py`) and the Process Doc adapter (`automation/importer/parsers/process_doc_docx.py`). Study both as reference — particularly:
- `entity_prd_docx.py` for `_NAME_CODE_RE`, heading helpers, table helpers
- `process_doc_docx.py` for per-process section parsing and two-row-per-field table parsing

Doug's local CBM clone is at `~/Dropbox/Projects/ClevelandBusinessMentors/` (short name). The GitHub repo is `dbower44022/ClevelandBusinessMentoring` (long name). Use the short name for local paths.

## Primary design reference: CBM-Domain-PRD-Mentoring.docx v1.0

Located at `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/MN/CBM-Domain-PRD-Mentoring.docx`.

The document has 6 sections (Heading 1) plus a header table:

- **Table 0** (header): 7-row, 2-col key/value
- **Section 1** Domain Overview: prose
- **Section 2** Personas: Heading 2 per persona with role description prose
- **Section 3** Business Processes: Heading 2 per process, each with Heading 3 sub-sections and per-process requirement tables (2-col)
- **Section 4** Data Reference: Heading 2 per entity, each with a 7-column field table (two-row-per-field pattern)
- **Section 5** Decisions Made: 4-column table
- **Section 6** Open Issues: 4-column table

## Deliverables

### 1. New error class

Add `DomainPrdParseError(Exception)` to `automation/importer/parsers/__init__.py` alongside existing `MasterPrdParseError`, `ProcessDocParseError`, `EntityPrdParseError`, and `EntityInventoryParseError`.

### 2. New adapter

Create `automation/importer/parsers/domain_prd_docx.py` implementing:

```python
def parse(
    path: str | Path,
    work_item: dict,
    session_type: str = "initial",
) -> tuple[str, ParseReport]:
    """Parse a Domain PRD .docx into a Path B envelope JSON string.

    :param work_item: Must have item_type == 'domain_reconciliation'.
    :raises ValueError: If work_item['item_type'] != 'domain_reconciliation'.
    :raises FileNotFoundError: If path does not exist.
    :raises DomainPrdParseError: If the document is structurally unparseable.
    """
```

### 3. Tombstone

Tombstone `automation/cbm_import/parsers/domain_prd.py` with `raise NotImplementedError(...)` following the existing tombstone pattern.

### 4. Test fixture

Copy `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/MN/CBM-Domain-PRD-Mentoring.docx` to `automation/tests/fixtures/cbm-domain-prd-mentoring-v1.0.docx`. Verify internal Version row reads `1.0` before committing.

### 5. Tests

`automation/tests/test_importer_parsers_domain_prd_docx.py` — see Test Coverage section below.

## Envelope Shape

```json
{
  "output_version": "1.0",
  "work_item_type": "domain_reconciliation",
  "work_item_id": "<work_item['id']>",
  "session_type": "initial",
  "payload": {
    "source_metadata": {
      "domain_name": "Mentoring",
      "domain_code": "MN",
      "version": "1.0",
      "status": "...",
      "last_updated": "...",
      "source": "...",
      "processes": "..."
    },
    "domain_overview_narrative": "<Section 1 prose joined with \\n\\n>",
    "personas": [
      {
        "identifier": null,
        "code": "Program Staff",
        "name": "Program Staff",
        "consolidated_role": "<prose under H2>",
        "description": "<same as consolidated_role>"
      }
    ],
    "process_summaries": [
      {
        "process_code": "MN-INTAKE",
        "process_name": "Intake Process",
        "description": "<all prose within subsection>",
        "requirements": [
          {"identifier": "MN-INTAKE-REQ-001", "description": "..."}
        ]
      }
    ],
    "consolidated_data_reference": [
      {
        "entity_name": "Contact",
        "deduplicated_fields": [
          {
            "name": "firstName",
            "field_type": "varchar",
            "is_required": "Yes",
            "values": "",
            "default_value": "",
            "identifier": "MN-INTAKE-DAT-001",
            "defined_in": "Intake Process",
            "description": "..."
          }
        ]
      }
    ]
  },
  "decisions": [
    {
      "identifier": "MN-DEC-001",
      "description": "...",
      "rationale": "...",
      "made_during": "...",
      "status": "locked"
    }
  ],
  "open_issues": [
    {
      "identifier": "MN-OI-001",
      "description": "...",
      "question": "...",
      "needs_input_from": "...",
      "status": "open"
    }
  ]
}
```

## Section-by-Section Parsing Rules

### Header table (Table 0)

Two-column key/value. Expected rows: `Domain`, `Domain Code`, `Version`, `Status`, `Last Updated`, `Source`, `Processes`.

**Table identification:** First 2-col table where any cell in col 0 (case-insensitive) contains `"domain"`.

**Domain code extraction:**
- Parse the `Domain` row value with `_NAME_CODE_RE` (`^(.+?)\s*\(([A-Z][A-Z0-9-]*)\)\s*$`). Example: `"Mentoring (MN)"` → name `"Mentoring"`, code `"MN"`.
- Cross-check against `Domain Code` row value. If both present and disagree, soft-warn.
- If `Domain` row parse fails, fall back to `Domain Code` row value directly.
- Store both `domain_name` and `domain_code` in `source_metadata`.

Extract remaining rows into `source_metadata`:
```python
{
    "domain_name": "Mentoring",
    "domain_code": "MN",
    "version": str,
    "status": str,
    "last_updated": str,
    "source": str,
    "processes": str    # Raw comma-separated process list
}
```

**Hard-fail:** No header table found. No domain code extractable from either `Domain` or `Domain Code` rows → `DomainPrdParseError`.
**Soft-warn:** Missing optional rows (`Version`, `Status`, etc.). `Domain` value doesn't match `Name (CODE)` pattern (when `Domain Code` row provides fallback).

### Section 1 — Domain Overview

Find Heading 1 matching `^1\.\s+Domain Overview$`. Collect all non-heading paragraphs until next Heading 1. Join with `\n\n`.

Store as `payload["domain_overview_narrative"]`.

**Hard-fail:** Section missing → `DomainPrdParseError`.
**Soft-warn:** Section present but empty.

### Section 2 — Personas

Find Heading 1 matching `^2\.\s+Personas$`. Each Heading 2 within range is one persona subsection.

**Strip numeric prefix from H2:** `"2.1 Program Staff"` → `"Program Staff"`.

For each persona, collect all non-heading paragraphs under the H2 until the next H2 or H1. Join with `\n\n`.

Produce:
```python
{
    "identifier": None,
    "code": "<persona name>",        # Name used as code for mapper lookup
    "name": "<persona name>",
    "consolidated_role": "<prose>",
    "description": "<prose>"         # Same as consolidated_role
}
```

The mapper resolves personas by `code` against existing Persona records. The Domain PRD doesn't include explicit identifiers — pass the name as `code` and let the mapper handle matching.

**Hard-fail:** None — Section 2 may be absent (produces empty list).
**Soft-warn:** Section present but no H2 subsections. Persona subsection with no prose.

### Section 3 — Business Processes

Find Heading 1 matching `^3\.\s+Business Processes$`. Each Heading 2 is a process subsection.

**Process code extraction from H2:**
- Strip numeric prefix from H2: `"3.1 Intake Process (MN-INTAKE)"` → `"Intake Process (MN-INTAKE)"`
- Try `_NAME_CODE_RE` on the result: `"Intake Process (MN-INTAKE)"` → name `"Intake Process"`, code `"MN-INTAKE"`
- If no parenthetical code, soft-warn and use the full heading text as `process_name`, leave `process_code` as the heading text

**Within each process subsection:**
- Heading 3 sub-sections mirror the process document structure. Do NOT re-parse the full process structure — collect all prose as a single description block.
- Collect all non-heading paragraphs under the H2 (including those under H3 sub-headings) until the next H2 or H1. Join with `\n\n`.
- Find any 2-column requirement tables within the subsection range. Header (case-insensitive): first col contains `"id"`, second col contains `"requirement"`. Extract each data row as `{identifier, description}`.
- To find tables within a subsection, use `_tables_in_range()` pattern from `entity_prd_docx.py` — map paragraph XML elements to indices and locate tables between the H2 boundaries.

Produce:
```python
{
    "process_code": "MN-INTAKE",
    "process_name": "Intake Process",
    "description": "<all prose within subsection, joined \\n\\n>",
    "requirements": [
        {"identifier": "MN-INTAKE-REQ-001", "description": "..."}
    ]
}
```

Store as `payload["process_summaries"]`. The `domain_reconciliation` mapper does not directly consume this field, but it preserves per-process requirement data in the envelope for traceability.

**Hard-fail:** None — Section 3 may vary across domains.
**Soft-warn:** Section missing. Process subsection with no content. Requirement identifier doesn't match expected `*-REQ-*` pattern.

### Section 4 — Data Reference

Find Heading 1 matching `^4\.\s+Data Reference$`. Each Heading 2 is an entity subsection.

**Entity name extraction from H2:**
- Strip numeric prefix: `"4.1 Contact"` → `"Contact"`

**Within each entity subsection:**
- Find the **7-column** field table. Header (case-insensitive): `Field Name | Type | Req | Values | Default | ID | Defined In`.
- Uses the **two-row-per-field pattern**: odd rows (1, 3, 5...) = field metadata, even rows (2, 4, 6...) = description row.
- To locate tables, use `_tables_in_range()` to find tables within the H2 subsection bounds.
- Identify the field table by column count (≥7) and header content (first cell case-insensitive contains `"field"` or `"name"`).

For each field (metadata row + description row pair):
```python
{
    "name": meta_row[0],           # Field Name
    "field_type": meta_row[1],     # Type (raw passthrough)
    "is_required": meta_row[2],    # Req (raw string "Yes"/"No")
    "values": meta_row[3],         # Values (raw)
    "default_value": meta_row[4],  # Default (raw)
    "identifier": meta_row[5],     # ID
    "defined_in": meta_row[6],     # Defined In — 7th column unique to Domain PRD
    "description": desc_row[0]     # Description from next row
}
```

**Handle odd row counts:** If the table has an odd number of data rows (after header), the last field may lack a description row. Soft-warn and set `description` to empty string.

For each entity subsection, produce:
```python
{
    "entity_name": "Contact",
    "deduplicated_fields": [ ... ]  # List of field dicts
}
```

Store as `payload["consolidated_data_reference"]` — this matches the mapper's expected field name exactly.

**Hard-fail:** None — Section 4 may be absent for simple domains.
**Soft-warn:** Section present but no entity subsections. Entity subsection with no field tables found. Field table with odd data row count (missing description row).

### Section 5 — Decisions Made

Find Heading 1 matching `^5\.\s+Decisions Made$`. Find 4-column table with header (case-insensitive): `ID | Decision | Rationale | Made During`.

**Table identification:** First table in the section range with ≥4 cols where header (case-insensitive) contains `"id"` and `"decision"`.

Each data row → entry in `envelope["decisions"]`:
```python
{
    "identifier": row[0].strip(),
    "description": row[1].strip(),
    "rationale": row[2].strip(),
    "made_during": row[3].strip(),
    "status": "locked"
}
```

Skip rows where col 0 is empty or matches header keywords.

**Hard-fail:** None.
**Soft-warn:** Section missing. Decision identifier doesn't match `^[A-Z]+-DEC-\d+$`.

### Section 6 — Open Issues

Find Heading 1 matching `^6\.\s+Open Issues$`. Find 4-column table with header (case-insensitive): `ID | Issue | Question | Needs Input From`.

**Table identification:** First table in the section range with ≥4 cols where header (case-insensitive) contains `"id"` and `"issue"`.

Each data row → entry in `envelope["open_issues"]`:
```python
{
    "identifier": row[0].strip(),
    "description": row[1].strip(),
    "question": row[2].strip(),
    "needs_input_from": row[3].strip(),
    "status": "open"
}
```

Skip rows where col 0 is empty or matches header keywords.

**Hard-fail:** None.
**Soft-warn:** Section missing.

## Shared Utilities

Reuse the helper patterns from `entity_prd_docx.py`:

- `_NAME_CODE_RE` — for `Name (CODE)` parsing
- `_style_name()`, `_is_heading()`, `_find_heading1()`, `_section_range()`, `_collect_prose()` — for heading/section navigation
- `_tables_in_range()` — for locating tables within section bounds
- `_table_header()`, `_table_rows()` — for table parsing

Since these are private functions in `entity_prd_docx.py`, **re-implement them** in `domain_prd_docx.py` (copy the pattern, don't import private functions). They are small utilities.

Additionally, add a `_LEADING_NUM_RE` pattern (already exists in `entity_prd_docx.py`) for stripping numeric prefixes from Heading 2 titles.

## Tombstone

`automation/cbm_import/parsers/domain_prd.py`:

```python
"""TOMBSTONED — migrated to automation/importer/parsers/domain_prd_docx.py on 04-15-26."""
from __future__ import annotations


def parse(*args, **kwargs):
    raise NotImplementedError(
        "Path A Domain PRD parser has been migrated to "
        "automation/importer/parsers/domain_prd_docx.py. Use Path B "
        "ImportProcessor with the new adapter."
    )
```

## Test Coverage

Target 18+ tests in `automation/tests/test_importer_parsers_domain_prd_docx.py`.

**Fixture tests against CBM-Domain-PRD-Mentoring.docx v1.0:**

1. Parse succeeds end-to-end, envelope round-trips through `json.loads`.
2. `source_metadata.domain_code == "MN"`, `source_metadata.domain_name == "Mentoring"`, `source_metadata.version == "1.0"`.
3. `work_item_type == "domain_reconciliation"`, `output_version == "1.0"`.
4. `domain_overview_narrative` is non-empty string.
5. `personas` list is non-empty, each entry has `name` and `consolidated_role`.
6. `process_summaries` list is non-empty, each entry has `process_code` and `process_name`.
7. At least one process summary has a non-empty `requirements` list.
8. `consolidated_data_reference` is non-empty, each entry has `entity_name` and `deduplicated_fields`.
9. Field dicts in data reference have 7-column `defined_in` key.
10. `decisions` list is non-empty, each has `identifier`, `description`, `rationale`, `made_during`, `status == "locked"`.
11. `open_issues` list is non-empty, each has `identifier`, `description`, `question`, `needs_input_from`, `status == "open"`.

**Hard-failure synthetic tests:**

12. `work_item['item_type']` != `'domain_reconciliation'` → `ValueError`.
13. File not found → `FileNotFoundError`.
14. No header table / no domain code → `DomainPrdParseError`.
15. Missing Section 1 (Domain Overview) → `DomainPrdParseError`.

**Soft-warning synthetic tests:**

16. `Domain` row doesn't match `Name (CODE)` pattern but `Domain Code` row provides fallback → warning, code still extracted.
17. Missing Section 2 → empty personas list, no error.

**Structural tests:**

18. All required top-level envelope keys present (`output_version`, `work_item_type`, `work_item_id`, `session_type`, `payload`, `decisions`, `open_issues`).
19. `payload` contains all expected keys (`source_metadata`, `domain_overview_narrative`, `personas`, `process_summaries`, `consolidated_data_reference`).

## Verification Steps

After implementation:

1. `uv run ruff check automation/` — clean.
2. `uv run pytest automation/tests/test_importer_parsers_domain_prd_docx.py -v` — all tests pass.
3. `uv run pytest automation/tests/ -v` — no regressions from this work specifically (pre-existing failures acknowledged and out of scope).

## Reporting

Return a plain-text summary covering:
- Fixture internal version confirmed (`1.0`)
- Test counts (total / passed / skipped / failed) for the new test file
- Full suite counts (noting any pre-existing failures)
- Ruff status
- Number of personas, process summaries, data reference entities, decisions, and open issues extracted
- Any format surprises encountered that might affect the MR Domain PRD or other domains
