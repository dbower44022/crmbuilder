# CLAUDE-CODE-PROMPT: Entity PRD Path B Adapter

**Repo:** `dbower44022/crmbuilder`
**Date:** 04-12-26
**Goal:** Migrate the Entity PRD parser from Path A (`automation/cbm_import/`) to Path B (`automation/importer/`), fixing **Bug 6** — the current Path A parser never extracts any domain reference, so all 12 imported entities in `cbm-client.db` have `primary_domain_id = NULL` and don't appear under any domain in the Data Browser.

## Context

Read `CLAUDE.md` at the repo root before starting. This work follows the same pattern as the completed Master PRD adapter (`automation/importer/parsers/master_prd_docx.py`) and the Process Doc adapter (`automation/importer/parsers/process_doc_docx.py`). Study both as reference — particularly the process doc adapter, which pioneered the sub-domain/domain code resolution pattern that Bug 6 needs.

Doug's local CBM clone is at `~/Dropbox/Projects/ClevelandBusinessMentors/` (short name). The GitHub repo is `dbower44022/ClevelandBusinessMentoring` (long name). Use the short name for local paths.

## Primary design reference: Contact Entity PRD

Design was reviewed against `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/entities/Contact-Entity-PRD.docx` v1.3. This is the most complex existing Entity PRD (16 native + 38 custom fields, 7 contactType values, multi-domain, Dynamic Logic section, 8 open issues, 14 decisions). Other existing Entity PRDs (Account, Engagement, Session, Dues) may have minor format variations — out of scope for this prompt; address in a follow-up iteration.

## Deliverables

### 1. New error class

Add `EntityPrdParseError(Exception)` to `automation/importer/parsers/__init__.py` alongside existing `MasterPrdParseError` and `ProcessDocParseError`.

### 2. New adapter

Create `automation/importer/parsers/entity_prd_docx.py` implementing:

```python
def parse(
    path: str | Path,
    work_item: dict,
    session_type: str = "initial",
) -> tuple[str, ParseReport]:
    """Parse an Entity PRD .docx into a Path B envelope JSON string.

    :param work_item: Must have item_type == 'entity_prd' and 'entity_id' key.
    :raises ValueError: If work_item['item_type'] != 'entity_prd'.
    :raises FileNotFoundError: If path does not exist.
    :raises EntityPrdParseError: If the document is structurally unparseable.
    """
```

### 3. Mapper enhancement

In `automation/importer/mappers/entity_prd.py`, add resolution of `payload.entity_metadata.primary_domain_code` against `Domain.code`, and include the resolved `primary_domain_id` in the Entity update record. Use the same pattern as the process doc mapper's sub-domain resolution. This is the Bug 6 fix.

### 4. Tombstone

Tombstone `automation/cbm_import/parsers/entity_prd.py` with `raise NotImplementedError(...)` and guard call sites in `automation/cbm_import/importer.py` with try/except for `NotImplementedError`. Skip any legacy tests that exercise the Path A parser.

### 5. Test fixture

Copy `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/entities/Contact-Entity-PRD.docx` to `automation/tests/fixtures/cbm-contact-entity-prd-v1.3.docx`. Verify internal Version row reads `1.3` before committing.

### 6. Tests

`automation/tests/test_importer_parsers_entity_prd_docx.py` — 30+ tests. See Test Coverage section below.

## Envelope Shape

```json
{
  "output_version": "1.0",
  "work_item_type": "entity_prd",
  "work_item_id": <work_item['id']>,
  "session_type": "initial",
  "payload": {
    "source_metadata": {
      "entity_name": "Contact",
      "version": "1.3",
      "status": "Draft",
      "last_updated": "04-08-26 16:24",
      "source_documents": "Master PRD v2.0, Entity Inventory v1.0, ..."
    },
    "entity_metadata": {
      "name": "Contact",
      "entity_type": "Person",
      "is_native": true,
      "singular_label": "Contact",
      "plural_label": "Contacts",
      "activity_stream": true,
      "primary_domain_code": "MN",
      "contributing_domain_codes": ["MN", "MR", "CR", "FU"],
      "discriminator_field": "contactType (multiEnum)",
      "discriminator_values": "Client, Mentor, Partner, ...",
      "description": "<Section 1 prose joined with \\n\\n>"
    },
    "native_fields": [
      {"name": "firstName", "field_type": "varchar", "label": "First Name",
       "is_required": false, "default_value": null,
       "description": "<PRD mapping info>", "identifier": null,
       "referenced_by": "<content of Referenced By column>"}
    ],
    "custom_fields": [
      {"name": "prospectStatus", "field_type": "enum", "label": "Prospect Status",
       "is_required": false, "default_value": null,
       "values": "New, Nurture, Qualified, Applicant, Closed-Lost",
       "identifier": "CR-MARKETING-DAT-001",
       "description": "<prose>",
       "subsection": "Marketing and Source Attribution"}
    ],
    "relationships": [
      {"name": "Contact → Account", "related_entity": "Account",
       "link_type": "manyToMany", "prd_reference": "Native relationship",
       "domains": "MN, CR, FU"}
    ],
    "dynamic_logic": [
      {"section": "5.1", "title": "CBM Internal Types",
       "description": "<prose>"}
    ],
    "layout_guidance": "<Section 6 content, structure TBD after inspection>",
    "implementation_notes": "<Section 7 prose joined with \\n\\n>"
  },
  "decisions": [
    {"identifier": "CON-DEC-010", "description": "<prose>", "status": "accepted"}
  ],
  "open_issues": [
    {"identifier": "CON-ISS-001", "description": "<prose>", "status": "open"}
  ]
}
```

## Section-by-Section Parsing Rules

### Header table (Table 0)

Two-column key/value. Expected rows: `Document Type`, `Entity`, `Implementation`, `Version`, `Status`, `Last Updated`, `Source Documents`.

**Parse the `Entity` value** with regex `^(.+?)\s*\(\s*(Native|Custom)\s*[—\-–]\s*(.+?)\s*\)\s*$`:
- Group 1 → tentative `name`
- Group 2 → `is_native` (True if `"Native"`)
- Group 3 → `entity_type` (e.g. `"Person Type"` — strip trailing `" Type"` if present to produce `"Person"`)

If the regex doesn't match (bare entity name with no parens), soft-warn and set `name = value`, leave `is_native` and `entity_type` as `None` for later reconciliation with Entity Overview.

Ignore `Document Type` and `Implementation` rows (boilerplate).

**Hard-fail:** No header table. Missing `Entity` row.
**Soft-warn:** `Entity` value lacks parens. Missing `Version`, `Status`, `Last Updated`, or `Source Documents`.

### Entity Overview table (Table 1 area)

Locate by content: the first two-column key/value table in document order **after** the header table, whose first row's first cell matches (case-insensitive) `crm entity name` OR `entity name`.

Extract the following rows (case-insensitive key match):

- `CRM Entity Name` or `Entity Name` → cross-check against header's parsed name. Lenient cross-check — warn only on clearly different values (e.g. `"Contact"` vs `"Account"`), not minor whitespace/case differences.
- `Native / Custom` → cross-check against header's `is_native`. Lenient — warn only when one says `"Native"` and the other says `"Custom"`.
- `Entity Type` → cross-check against header's `entity_type`. Lenient.
- `Display Label (Singular)` → `singular_label`
- `Display Label (Plural)` → `plural_label`
- `Activity Stream` → boolean from `"Yes"`/`"No"` (case-insensitive). Missing row → warn, set to `False`.
- `Primary Domain` (optional) → parse as `Name (CODE)` format. Store code.
- `Contributing Domains` (required) → parse comma-separated list of `Name (CODE)` entries. Store list of codes.
- `Discriminator Field` (optional) → pass through raw.
- `Discriminator Values` (optional) → pass through raw.

**Bug 6 fix logic:**
- If `Primary Domain` present → use it directly as `primary_domain_code`.
- If absent → use first entry from `contributing_domain_codes`, emit soft warning with category `primary_domain_fallback`, location `Primary Domain`, message `"Primary Domain row missing — falling back to first contributing domain: {code}"`.
- If both absent (or `Contributing Domains` empty) → hard-fail.
- If `Primary Domain` code is not in `Contributing Domains` list → soft warning.

**Hard-fail:** No Entity Overview table. Missing `CRM Entity Name` row. Both `Primary Domain` and `Contributing Domains` absent. `Contributing Domains` present but empty or malformed.

**Soft-warn:** As described above, plus missing optional rows.

### Section 1 Entity Overview prose

After the Entity Overview table, find Heading 1 `^1\.\s+Entity Overview$`. Collect all non-heading paragraphs until next Heading 1 (typically Section 2). Join with `\n\n` and store as `entity_metadata.description`.

**Hard-fail:** No Section 1 Heading 1.
**Soft-warn:** Empty section.

### Section 2 Native Fields

Heading 1 `^2\.\s+Native Fields$`. Find the first table in range whose header row first cell matches (case-insensitive) `native field` or `field name`. Accept 4-column (`Native Field | Type | PRD Name(s) / Mapping | Referenced By`) or 5-column variants. Single-row-per-field (no description row).

For each data row, produce:

```python
{
  "name": row[0],
  "field_type": row[1].strip().lower(),   # raw pass-through
  "label": _to_label(row[0]),             # camelCase → "First Name"
  "is_required": False,
  "default_value": None,
  "description": row[2] if len(row) > 2 else "",
  "identifier": None,
  "referenced_by": row[3] if len(row) > 3 else "",
}
```

Helper `_to_label(name)`: insert space before uppercase letters, capitalize first char. Reuse from legacy parser if convenient.

**Hard-fail:** No Section 2 Heading 1. No matching table. Zero data rows.
**Soft-warn:** Field name is empty. `field_type` is empty.

### Section 3 Custom Fields

Heading 1 `^3\.\s+Custom Fields$`. Within range, find every Heading 2 subsection. For each subsection, find all six-column field tables within that subsection's range.

**Strip numeric prefix from subsection title** for the `subsection` value: e.g. `"3.3 Mentor-Specific Fields"` → `"Mentor-Specific Fields"`.

Parse each six-column field table using the **two-row-per-field pattern** already implemented in `process_doc_docx.py`:
- Row 0: header `["Field Name", "Type", "Required", "Values", "Default", "ID"]`
- Odd rows: field metadata
- Even rows: description (spanning all 6 cells)

For each field produce:

```python
{
  "name": meta_row[0],
  "field_type": meta_row[1].strip().lower(),   # raw pass-through
  "label": _to_label(meta_row[0]),
  "is_required": parse_required(meta_row[2]),  # "Yes"→True, "No"→False, anything else→True+warn
  "values": meta_row[3],                        # raw
  "default_value": _clean_default(meta_row[4]), # "—"/"-"/"N/A"/"" → None
  "identifier": meta_row[5],
  "description": desc_row[0],
  "subsection": <stripped subsection title>,
}
```

**Enum options:** When `field_type in ("enum", "multienum")` and `values` is non-empty (not `"—"` placeholder), split `values` on `","` (strip whitespace around each entry, drop empties). Include the parsed list in the field dict as `"value_options"`:

```python
field["value_options"] = [v.strip() for v in values.split(",") if v.strip()]
```

This gives the mapper both the raw string and the parsed list.

**Special case — Section 3.4 Incomplete Domain Fields:** Parse same as other subsections. For each field parsed from Section 3.4 (or any subsection whose title matches `^.*incomplete\s+domain.*$` case-insensitive), emit soft warning with category `incomplete_domain_field`, location `Field {name}`, message `"In Incomplete Domain subsection — may need revision when source domain processes are defined"`.

**Hard-fail:** No Section 3 Heading 1. Zero fields across all subsections.
**Soft-warn:** Subsection has no field tables. Field table with odd row count (missing description row). `values` contains `"TBD"` (informational).

### Section 4 Relationships

Heading 1 `^4\.\s+Relationships$`. Find the 5-column table with header matching (case-insensitive) `["Relationship", "Related Entity", "Link Type", "PRD Reference", "Domain(s)"]`. Produce:

```python
{
  "name": row[0],
  "related_entity": row[1],
  "link_type": row[2].strip(),       # raw
  "prd_reference": row[3],
  "domains": row[4],
}
```

Pass `name` through unchanged (do not split the `"Contact → Account"` arrow). Pass `prd_reference` through unchanged (preserves `"Native relationship"` marker).

**Hard-fail:** No Section 4 Heading 1. No matching 5-column table. Zero data rows.
**Soft-warn:** `link_type` not in `{"oneToMany", "manyToOne", "manyToMany", "oneToOne"}` (case-sensitive).

### Section 5 Dynamic Logic Rules

Heading 1 `^5\.\s+Dynamic Logic Rules$`. For each Heading 2 within range, produce one entry:

```python
{
  "section": <full number, e.g. "5.1">,
  "title": <heading title with number stripped, e.g. "CBM Internal Types">,
  "description": <all prose paragraphs to next Heading 2 or Heading 1, joined \\n\\n>,
}
```

**Hard-fail:** None. Section 5 may be absent entirely (not all entities have dynamic logic) — emit info-level note via ParseReport but do not warn.

**Soft-warn:** Section present but zero subsections. Subsection with no prose.

### Section 6 Layout Guidance

Heading 1 `^6\.\s+Layout Guidance$`.

**Inspect this section in the Contact fixture before implementing.** If it's prose/tables-per-layout-type with Heading 2 subsections, handle the same way as Section 5 (one dict per subsection). If it's a single flat prose block, store as a single string. If it has structured tables, extract as tables-of-dicts per subsection. Choose the handling that preserves the most information without inventing schema.

**Hard-fail:** None — may be absent.

### Section 7 Implementation Notes

Heading 1 `^7\.\s+Implementation Notes$`. Collect all non-heading paragraphs until next Heading 1. Join with `\n\n`. Store as `payload.implementation_notes` (flat string).

**Hard-fail:** None — may be absent.

### Section 8 Open Issues

Heading 1 `^8\.\s+Open Issues$`. Find first two-column table with header `["ID", "Issue"]` (case-insensitive, accept `["ID", "Description"]`). Each row → `{identifier, description, status: "open"}` in `envelope.open_issues` (not payload).

**Hard-fail:** No Section 8 Heading 1.
**Soft-warn:** `CLOSED`/`RESOLVED` markers in description (informational).

### Section 9 Decisions Made

Heading 1 `^9\.\s+Decisions Made$`. Find first two-column table with header `["ID", "Decision"]` (case-insensitive). Each row → `{identifier, description, status: "accepted"}` in `envelope.decisions` (not payload).

**Hard-fail:** No Section 9 Heading 1.
**Soft-warn:** Identifier doesn't match `^[A-Z]+-DEC-\d+$` pattern.

## Mapper Enhancement (entity_prd.py)

Add logic in `map_payload()`:

```python
metadata = payload.get("entity_metadata", {})
primary_domain_code = metadata.get("primary_domain_code")
if primary_domain_code and entity_id:
    from automation.importer.mappers.base import resolve_by_code
    domain_id = resolve_by_code(conn, "Domain", "code", primary_domain_code)
    if domain_id is not None:
        entity_update["primary_domain_id"] = domain_id
```

Ensure the Entity update record is emitted even when the ONLY change is `primary_domain_id` (don't skip the update when other metadata fields are absent).

## Tombstone

`automation/cbm_import/parsers/entity_prd.py`:

```python
"""TOMBSTONED — migrated to automation/importer/parsers/entity_prd_docx.py on 04-12-26."""
from __future__ import annotations


def parse(*args, **kwargs):
    raise NotImplementedError(
        "Path A Entity PRD parser has been migrated to "
        "automation/importer/parsers/entity_prd_docx.py. Use Path B "
        "ImportProcessor with the new adapter."
    )
```

Guard call sites in `automation/cbm_import/importer.py` — catch `NotImplementedError` in `import_all()` and equivalent entry points following the master PRD / process doc tombstone pattern.

## Test Coverage

Target 30+ tests in `automation/tests/test_importer_parsers_entity_prd_docx.py`.

**Fixture tests against Contact:**
1. Parse succeeds end-to-end, envelope round-trips through `json.loads`.
2. `source_metadata.entity_name == "Contact"`, version `"1.3"`.
3. `entity_metadata.is_native == True`, `entity_type == "Person"`, `singular_label == "Contact"`, `plural_label == "Contacts"`, `activity_stream == True`.
4. `primary_domain_code == "MN"` (from fallback — no Primary Domain row in Contact v1.3).
5. Soft warning `primary_domain_fallback` emitted.
6. `contributing_domain_codes == ["MN", "MR", "CR", "FU"]`.
7. `native_fields` count matches Section 2 table data row count.
8. `custom_fields` count matches total across all Section 3 subsections.
9. Every custom field has a non-empty `subsection` value.
10. Section 3.4 Incomplete Domain fields emit per-field soft warnings.
11. Relationships count ≥ 10 (Contact has many).
12. `dynamic_logic` has at least 7 entries (Contact has 5.1 through 5.7).
13. `layout_guidance` is present (exact shape depends on inspection).
14. `implementation_notes` is non-empty string.
15. `envelope.open_issues` count matches Section 8 table data row count (8 for Contact v1.3).
16. `envelope.decisions` count matches Section 9 table data row count (14 for Contact v1.3).

**Hard-failure synthetic tests (at least 10):**
17. `work_item['item_type']` != `'entity_prd'` → `ValueError`
18. File not found → `FileNotFoundError`
19. No header table → `EntityPrdParseError`
20. Missing `Entity` row in header → `EntityPrdParseError`
21. No Entity Overview table → `EntityPrdParseError`
22. Entity Overview missing `CRM Entity Name` row → `EntityPrdParseError`
23. Both `Primary Domain` and `Contributing Domains` absent → `EntityPrdParseError`
24. `Contributing Domains` present but empty/malformed → `EntityPrdParseError`
25. Missing Section 1 → `EntityPrdParseError`
26. Missing Section 2 → `EntityPrdParseError`
27. Section 2 has no matching native fields table → `EntityPrdParseError`
28. Missing Section 3 → `EntityPrdParseError`
29. Section 3 has zero fields → `EntityPrdParseError`
30. Missing Section 4 → `EntityPrdParseError`
31. Missing Section 8 → `EntityPrdParseError`
32. Missing Section 9 → `EntityPrdParseError`

**Soft-warning synthetic tests (at least 7):**
33. Header `Entity` value lacks parens → warning, name passes through, `is_native`/`entity_type` null
34. Lenient cross-check mismatch (Native in header, Custom in overview) → warning
35. Primary Domain row present but code not in Contributing Domains → warning
36. Missing Section 5 entirely → info-level note, no warning, `dynamic_logic` is empty list
37. Section 3 subsection with no field tables → warning
38. Unknown `link_type` value in relationships → warning
39. Decision identifier not matching pattern → warning

**Structural / round-trip tests (at least 4):**
40. Envelope JSON valid, round-trips through `json.loads`.
41. All required top-level envelope keys present.
42. `payload.entity_metadata` contains all required keys.
43. Adapter does not perform database lookups (pass a work_item with no `conn`).

## Verification Steps

After implementation:

1. `uv run ruff check automation/` — clean.
2. `uv run pytest automation/tests/test_importer_parsers_entity_prd_docx.py -v` — all tests pass.
3. `uv run pytest automation/tests/ -v` — no regressions from this work specifically (pre-existing schema/migration fixture failures acknowledged and out of scope).
4. **Bug 6 database verification:**
   - Use existing `automation/data/cbm-client.db` (do not rebuild).
   - Construct work_item for Contact: `{"id": <ai_session work item id>, "item_type": "entity_prd", "entity_id": <Contact Entity row id>}`.
   - Run adapter on `automation/tests/fixtures/cbm-contact-entity-prd-v1.3.docx` → envelope JSON.
   - Run envelope through `ImportProcessor.run_full_import()`.
   - Query: `SELECT id, name, primary_domain_id FROM Entity WHERE name = 'Contact';`
   - **Expected result:** `primary_domain_id` is non-NULL and equals the MN domain row id (matching the fallback logic since Contact v1.3 has no Primary Domain row).
   - Report the actual value in the summary.

## Reporting

Return a plain-text summary covering:
- Fixture internal version confirmed (`1.3`)
- Test counts (total / passed / skipped / failed) for the new test file
- Full suite counts (noting any pre-existing failures)
- Ruff status
- Bug 6 verification: Contact `Entity.primary_domain_id` before vs. after — should go from NULL to a valid Domain id
- Any format surprises encountered in Contact that might affect Account/Engagement/Session/Dues (deferred to follow-up iteration)
