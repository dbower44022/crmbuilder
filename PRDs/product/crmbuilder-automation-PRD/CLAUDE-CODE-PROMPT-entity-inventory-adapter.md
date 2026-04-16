# CLAUDE-CODE-PROMPT: Entity Inventory Path B Adapter

**Repo:** `dbower44022/crmbuilder`
**Date:** 04-15-26
**Goal:** Migrate the Entity Inventory parser from Path A (`automation/cbm_import/`) to Path B (`automation/importer/`), fixing **Bug 7** — the Path A parser never extracts domain assignment, discriminator info, or entity labels. The new adapter will parse the full Entity Inventory document including detail cards (labels, owning domain) and the 7-column Entity Map table.

## Context

Read `CLAUDE.md` at the repo root before starting. This work follows the same pattern as the completed Entity PRD adapter (`automation/importer/parsers/entity_prd_docx.py`) and the Process Doc adapter (`automation/importer/parsers/process_doc_docx.py`). Study both as reference — particularly `entity_prd_docx.py`, which pioneered the `_NAME_CODE_RE` domain code extraction pattern and the Bug 6 primary domain fix that this adapter reuses.

Doug's local CBM clone is at `~/Dropbox/Projects/ClevelandBusinessMentors/` (short name). The GitHub repo is `dbower44022/ClevelandBusinessMentoring` (long name). Use the short name for local paths.

## Primary design reference: CBM-Entity-Inventory.docx v1.4

Located at `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/CBM-Entity-Inventory.docx`.

The document has 12 tables total and 7 sections (Heading 1):

- **Table 0** (header): 6-row, 2-col key/value
- **Table 1** (Entity Map): 29 rows × 7 cols — the core inventory
- **Tables 2–9** (Entity Detail Cards): 5-row, 2-col key/value per entity
- **Table 10** (Cross-Domain Matrix): 18 rows × 6 cols — skip (validation only)
- **Table 11** (Open Issues): 9 rows × 3 cols

## Deliverables

### 1. New error class

Add `EntityInventoryParseError(Exception)` to `automation/importer/parsers/__init__.py` alongside existing `MasterPrdParseError`, `ProcessDocParseError`, and `EntityPrdParseError`.

### 2. New adapter

Create `automation/importer/parsers/entity_inventory_docx.py` implementing:

```python
def parse(
    path: str | Path,
    work_item: dict,
    session_type: str = "initial",
) -> tuple[str, ParseReport]:
    """Parse an Entity Inventory .docx into a Path B envelope JSON string.

    :param work_item: Must have item_type == 'business_object_discovery'.
    :raises ValueError: If work_item['item_type'] != 'business_object_discovery'.
    :raises FileNotFoundError: If path does not exist.
    :raises EntityInventoryParseError: If the document is structurally unparseable.
    """
```

### 3. Tombstone

Tombstone `automation/cbm_import/parsers/entity_inventory.py` with `raise NotImplementedError(...)` following the existing tombstone pattern.

### 4. Test fixture

Copy `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/CBM-Entity-Inventory.docx` to `automation/tests/fixtures/cbm-entity-inventory-v1.4.docx`. Verify internal Version row reads `1.4` before committing.

### 5. Tests

`automation/tests/test_importer_parsers_entity_inventory_docx.py` — see Test Coverage section below.

## Envelope Shape

```json
{
  "output_version": "1.0",
  "work_item_type": "business_object_discovery",
  "work_item_id": "<work_item['id']>",
  "session_type": "initial",
  "payload": {
    "source_metadata": {
      "document_type": "Entity Inventory",
      "implementation": "Cleveland Business Mentors",
      "version": "1.4",
      "status": "Active",
      "last_updated": "...",
      "source_documents": "..."
    },
    "business_objects": [
      {
        "name": "Client Contact",
        "classification": "entity",
        "status": "classified",
        "entity_name": "Contact",
        "entity_type": "Person",
        "is_native": true,
        "source_domains": ["MN", "MR", "CR", "FU"],
        "singular_label": "Contact",
        "plural_label": "Contacts",
        "description": "Discriminator: contactType = Client"
      }
    ]
  },
  "decisions": [],
  "open_issues": [
    {"identifier": "OI-001", "description": "...", "resolution_path": "...", "status": "open"}
  ]
}
```

## Table Identification Strategy

Do NOT rely on table index positions. Classify each table by header content:

- **Header table:** First 2-col table where any cell (case-insensitive) contains `"document type"`.
- **Entity Map:** First table with ≥7 cols where header (case-insensitive) contains `"prd entity name"`.
- **Detail Cards:** All 2-col tables where row 0, col 0 text (case-insensitive) starts with `"entity type"`.
- **Cross-Domain Matrix:** Table with ≥6 cols where header (case-insensitive) contains `"domain count"`. **Skip entirely** — Table 1 is authoritative.
- **Open Issues:** Table with 3 cols where header (case-insensitive) contains `"id"` and `"issue"`.

**Hard-fail:** Entity Map table not found → `EntityInventoryParseError`.

## Section-by-Section Parsing Rules

### Header table (Table 0)

Two-column key/value. Expected rows: `Document Type`, `Implementation`, `Version`, `Status`, `Last Updated`, `Source Documents`.

Extract into `source_metadata` dict with lowercased/underscored keys. No hard failures on missing rows — warn for missing ones. This table is metadata only; the Entity Map is the critical table.

### Entity Map table (Table 1) — 7 columns

Header: `PRD Entity Name | CRM Entity | Native / Custom | Entity Type | Discriminator | Disc. Value | Domain(s)`

Each data row becomes one `business_objects` entry:

| Table 1 Column | Payload Field | Transform |
|---|---|---|
| PRD Entity Name (col 0) | `name` | Strip whitespace |
| CRM Entity (col 1) | `entity_name` | Strip whitespace; if empty, leave absent |
| Native / Custom (col 2) | `is_native` | `"Native"` → `True`, `"Custom"` → `False` (case-insensitive) |
| Entity Type (col 3) | `entity_type` | Passthrough: `"Base"`, `"Person"`, `"Company"`, `"Event"` |
| Discriminator (col 4) | *(see below)* | Store in description if present |
| Disc. Value (col 5) | *(see below)* | Store in description if present |
| Domain(s) (col 6) | `source_domains` | Split on `,`, strip each entry → list of domain codes |

**Classification logic:**
- If CRM Entity (col 1) is populated → `classification: "entity"`, `status: "classified"`
- If CRM Entity is empty/blank → `classification: "entity"`, `status: "unclassified"`, soft-warn

**Discriminator handling:**
- If both Discriminator (col 4) and Disc. Value (col 5) are populated (non-empty, not `"—"` or `"N/A"`), set: `description: "Discriminator: {col4} = {col5}"`
- Otherwise, `description` is empty string

**Entity code:**
- Do NOT include `entity_code` — let the mapper auto-generate it from `entity_name` (it already does this).

**Skip rows** where col 0 is empty or matches header keywords (case-insensitive): `"prd entity name"`, `"business concept"`, `"concept"`.

### Detail Cards (Tables 2–9) — enrichment

Each detail card is a 2-col, 5-row key/value table. Row 0 col 0 starts with `"Entity Type"`.

**Matching detail cards to business_objects:**

Multiple business_objects can share the same CRM Entity (e.g. "Client Contact" and "Mentor Contact" → Contact). The detail card describes the CRM Entity.

Extract the entity name from the **`Entity Type` row value** (row 0, col 1). The value may include qualifiers like `"Contact (Native — Person Type)"` — extract the entity name prefix before any parenthetical using regex: `^(.+?)(?:\s*\(.+\))?\s*$`.

Match to business_objects by comparing extracted entity name against `entity_name` (case-insensitive). All business_objects with the same `entity_name` receive the same enrichment.

**Fields to extract from detail card rows** (match row 0 col 0 case-insensitively):

| Detail Card Row | Payload Field | Notes |
|---|---|---|
| `Display Label (Singular)` | `singular_label` | Direct passthrough |
| `Display Label (Plural)` | `plural_label` | Direct passthrough |
| `Owning Domain` | `source_domains[0]` | Parse as `Name (CODE)` → extract CODE |
| `Activity Stream` | *(append to description)* | e.g., append `"; Activity Stream: Enabled"` |

**Owning Domain as primary domain (Bug 7 fix):**
- Parse with `_NAME_CODE_RE` pattern: `^(.+?)\s*\(([A-Z][A-Z0-9-]*)\)\s*$`
- Extracted code becomes the first entry in `source_domains` — insert at position 0, deduplicate
- If parsing fails, soft-warn with category `owning_domain_parse_failure` and leave `source_domains` as-is from Table 1
- If Owning Domain code is not already in the Table 1 `source_domains`, soft-warn with category `owning_domain_not_in_table1`

**Unmatched detail cards:** warn with category `unmatched_detail_card`.
**Business objects with no matching detail card:** warn with category `missing_detail_card` (only for entity-classified BOs).

### Open Issues table (Table 11) — 3 columns

Header: `ID | Issue | Resolution Path`

Each data row → entry in `envelope["open_issues"]`:

```python
{
    "identifier": row[0].strip(),
    "description": row[1].strip(),
    "resolution_path": row[2].strip(),
    "status": "open"
}
```

Skip rows where col 0 is empty or matches header keywords.

**Soft-warn:** Open Issues table not found (it's possible a clean inventory has none).

### Decisions

The Entity Inventory document has no Decisions table. Set `envelope["decisions"] = []`.

### Prose sections

Sections 1 (Overview), 3 (Shared Entity Summary), 4 (Custom Entity Summary), 5 (Cross-Domain Matrix), 7 (Next Steps) contain prose. The `business_object_discovery` mapper does **not** consume prose — only `business_objects`, `decisions`, and `open_issues`. **Skip prose extraction entirely.**

## Shared Utilities

Reuse the helper patterns from `entity_prd_docx.py`:

- `_NAME_CODE_RE` — for `Name (CODE)` parsing
- `_style_name()`, `_is_heading()` — for heading detection
- `_table_header()`, `_table_rows()` — for table parsing

Since these are private functions in `entity_prd_docx.py`, **re-implement them** in `entity_inventory_docx.py` (copy the pattern, don't import private functions). They are small utilities (5–10 lines each).

## Tombstone

`automation/cbm_import/parsers/entity_inventory.py`:

```python
"""TOMBSTONED — migrated to automation/importer/parsers/entity_inventory_docx.py on 04-15-26."""
from __future__ import annotations


def parse(*args, **kwargs):
    raise NotImplementedError(
        "Path A Entity Inventory parser has been migrated to "
        "automation/importer/parsers/entity_inventory_docx.py. Use Path B "
        "ImportProcessor with the new adapter."
    )
```

## Test Coverage

Target 20+ tests in `automation/tests/test_importer_parsers_entity_inventory_docx.py`.

**Fixture tests against CBM-Entity-Inventory.docx v1.4:**

1. Parse succeeds end-to-end, envelope round-trips through `json.loads`.
2. `source_metadata.version == "1.4"`, `source_metadata.document_type` present.
3. `work_item_type == "business_object_discovery"`, `output_version == "1.0"`.
4. `business_objects` count matches Entity Map table data row count (28 rows).
5. All entity-classified BOs have `entity_name`, `entity_type`, `is_native` populated.
6. At least one BO has `is_native == True` (e.g. Contact, Account).
7. At least one BO has `entity_type == "Person"` (e.g. Contact).
8. Detail card enrichment: BOs with `entity_name == "Contact"` have `singular_label == "Contact"` and `plural_label == "Contacts"`.
9. **Bug 7 fix:** BOs with detail cards have `source_domains[0]` set to the Owning Domain code (not just the Table 1 domain list).
10. Discriminator in description: BO with `name == "Client Contact"` has `"Discriminator:"` in description.
11. `source_domains` populated from Table 1 Domain(s) column — at least one BO has multiple domains.
12. `open_issues` list is non-empty, each entry has `identifier`, `description`, `resolution_path`, `status`.
13. `decisions` is empty list.
14. `parsed_counts` has keys for `business_objects`, `detail_cards`, `open_issues`.

**Hard-failure synthetic tests:**

15. `work_item['item_type']` != `'business_object_discovery'` → `ValueError`.
16. File not found → `FileNotFoundError`.
17. No Entity Map table → `EntityInventoryParseError`.

**Soft-warning synthetic tests:**

18. Business object with empty CRM Entity column → `status == "unclassified"`, warning emitted.
19. Detail card with unmatched entity name → `unmatched_detail_card` warning.
20. Missing Owning Domain parse → `owning_domain_parse_failure` warning.

**Structural tests:**

21. Envelope JSON valid, round-trips through `json.loads`.
22. All required top-level envelope keys present (`output_version`, `work_item_type`, `work_item_id`, `session_type`, `payload`, `decisions`, `open_issues`).
23. `payload` contains `source_metadata` and `business_objects` keys.

## Verification Steps

After implementation:

1. `uv run ruff check automation/` — clean.
2. `uv run pytest automation/tests/test_importer_parsers_entity_inventory_docx.py -v` — all tests pass.
3. `uv run pytest automation/tests/ -v` — no regressions from this work specifically (pre-existing failures acknowledged and out of scope).

## Reporting

Return a plain-text summary covering:
- Fixture internal version confirmed (`1.4`)
- Test counts (total / passed / skipped / failed) for the new test file
- Full suite counts (noting any pre-existing failures)
- Ruff status
- Number of business_objects extracted, number with detail card enrichment
- Number of open_issues extracted
- Any format surprises encountered that might affect other Entity Inventory documents
