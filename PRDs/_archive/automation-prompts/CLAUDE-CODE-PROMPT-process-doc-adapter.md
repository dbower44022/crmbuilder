# CLAUDE-CODE-PROMPT: Process Document Path B Adapter

**Repo:** `dbower44022/crmbuilder`
**Date:** 04-10-26
**Goal:** Migrate the process document parser from Path A (`automation/cbm_import/`) to Path B (`automation/importer/`), fixing Bug 4 (bad domain_code extraction) and Bug 5 (no sub-domain assignment) in the process.

## Context

Read `CLAUDE.md` at the repo root before starting. This work follows the same pattern used for the Master PRD adapter migration completed on 04-10-26 — see `automation/importer/parsers/master_prd_docx.py` as the canonical reference.

The Path A parser at `automation/cbm_import/parsers/process_document.py` has two confirmed bugs and is being tombstoned. The replacement adapter produces a Path B envelope JSON string that feeds the existing `ImportProcessor.run_full_import()` pipeline unchanged.

## Deliverables

1. **New error class** in `automation/importer/parsers/__init__.py`:
   `ProcessDocParseError(Exception)` — alongside the existing `MasterPrdParseError`.

2. **New adapter file** `automation/importer/parsers/process_doc_docx.py` implementing the parse logic described below.

3. **Small enhancement to** `automation/importer/mappers/process_definition.py` — use `payload.source_metadata.sub_domain_code` (when present) or `payload.source_metadata.domain_code` to look up the Domain record by code and emit a `Process.domain_id` update. Sub-domain takes precedence when present. This fixes Bug 5.

4. **Tombstone** `automation/cbm_import/parsers/process_document.py` — replace the body of `parse()` with `raise NotImplementedError("Path A process document parser has been migrated to automation/importer/parsers/process_doc_docx.py")`. Guard any call site in `automation/cbm_import/importer.py` that invokes it, following the same pattern as the master PRD tombstone.

5. **Test fixtures** — copy `PRDs/MN/MN-INTAKE.docx` and `PRDs/CR/PARTNER/CR-PARTNER-MANAGE.docx` from the `ClevelandBusinessMentoring` repo into `automation/tests/fixtures/` as `cbm-mn-intake-v2.3.docx` and `cbm-cr-partner-manage-v1.0.docx`. These are the two format exemplars (flat sequential workflow vs. activity-area workflow).

6. **Tests** `automation/tests/test_importer_parsers_process_doc_docx.py` — following the pattern of `test_importer_parsers_master_prd_docx.py`. Cover both fixture documents plus synthetic hard-failure and soft-warning cases. Target 20+ tests.

## Adapter API

```python
def parse(
    path: str | Path,
    work_item: dict,
    session_type: str = "initial",
) -> tuple[str, ParseReport]:
    """Parse a process document .docx into a Path B envelope JSON string.

    :param work_item: Must have item_type == 'process_definition' and
                      a 'process_id' key (the target Process row id).
    :raises ValueError: If work_item['item_type'] != 'process_definition'.
    :raises FileNotFoundError: If path does not exist.
    :raises ProcessDocParseError: If the document is structurally unparseable.
    """
```

## Envelope Shape

```json
{
  "output_version": "1.0",
  "work_item_type": "process_definition",
  "work_item_id": <work_item['id']>,
  "session_type": "initial",
  "payload": {
    "source_metadata": {
      "process_code": "CR-PARTNER-MANAGE",
      "process_name": "Partner Relationship Management",
      "domain_code": "CR",
      "sub_domain_code": "CR-PARTNER",
      "version": "1.0",
      "status": "Draft",
      "last_updated": "04-10-26 15:30"
    },
    "process_purpose": "<prose>",
    "triggers": "<prose>",
    "completion": "<prose>",
    "personas": [
      {"identifier": "MST-PER-008", "name": "Partner Coordinator",
       "role": "performer", "description": "<prose>"}
    ],
    "workflow": [
      {"name": "<str>", "description": "<str>",
       "step_type": "action", "sort_order": <int>}
    ],
    "process_data": [
      {"entity_name": "Engagement", "role": "referenced",
       "description": "<prose>",
       "field_references": [
         {"name": "referringPartner", "usage": "displayed",
          "description": "<prose>"}
       ]}
    ],
    "data_collected": [
      {"entity_name": "Account",
       "new_fields": [
         {"field_name": "partnerStatus", "label": "partnerStatus",
          "field_type": "enum", "is_required": true,
          "values": "Prospect, Active, Lapsed, Inactive",
          "default_value": "—",
          "identifier": "CR-PARTNER-MANAGE-DAT-025",
          "description": "<prose>"}
       ]}
    ],
    "system_requirements": [
      {"identifier": "CR-PARTNER-MANAGE-REQ-001",
       "description": "<prose>", "priority": "must"}
    ]
  },
  "decisions": [],
  "open_issues": [
    {"identifier": "CR-PARTNER-MANAGE-ISS-001",
     "description": "<prose>", "status": "open"}
  ]
}
```

## Section-by-Section Parsing Rules

### Header table (first table in document)

Two-column key-value structure. Extract:

- `Domain` row — parse value with regex `^(.+?)\s*\(([A-Z]+)\)\s*$`. Store code as `domain_code`.
- `Sub-Domain` row — optional. Same regex. If present, store code as `sub_domain_code`. Note the sub-domain code may be multi-segment like `CR-PARTNER` — adjust regex to `^(.+?)\s*\(([A-Z][A-Z0-9-]*)\)\s*$` to allow this.
- `Process Code` row — store as `process_code`.
- `Process Name` row — store as `process_name`.
- `Version`, `Status`, `Last Updated` rows — store as-is.

**Hard-fail** (raise `ProcessDocParseError`):
- No header table.
- Missing `Process Code` row.
- `Domain` row present but does not match `Name (CODE)` pattern.
- `Sub-Domain` row present but does not match pattern.
- **Process code prefix mismatch**: `process_code` must start with either `{domain_code}-` (when no sub-domain) or `{sub_domain_code}-` (when sub-domain is present). E.g. `CR-PARTNER-MANAGE` must start with `CR-PARTNER-`.

**Soft-warn:** Missing `Version`, `Status`, or `Last Updated` rows.

### Section 1 — Process Purpose → `payload.process_purpose`

Find Heading 1 matching `^1\.\s+Process Purpose$`. Collect all non-heading paragraphs until the next Heading 1. Join with `\n\n`. Hard-fail if section missing or empty.

### Section 2 — Process Triggers → `payload.triggers`

Same extraction pattern, Heading 1 `^2\.\s+Process Triggers?$`. Hard-fail if missing or empty.

### Section 3 — Personas → `payload.personas`

Find `^3\.\s+Personas Involved$` Heading 1. Within range to next Heading 1:

**First, check for a persona table** — any table in document order physically between this Heading 1 and the next Heading 1, whose header row contains cells matching (case-insensitive, substring) `id`, `persona`, and `role`.

- If found (Format B): each data row produces `{identifier: row[0], name: row[1], description: row[2]}`.

**Otherwise, paragraph scan** (Format A): look for lines matching `^(.+?)\s*\((MST-PER-\d+)\)\s*$`. The immediately following non-empty, non-heading paragraph is the `description`. `name` is group 1, `identifier` is group 2.

**Role derivation** for both formats: apply keyword heuristic to the description text (lowercased):
- contains `initiat` → `initiator`
- contains `approv` → `approver`
- contains `receiv` or `notif` → `recipient`
- otherwise → `performer`

**Hard-fail:** No Section 3 Heading 1, OR zero personas parsed.

### Section 4 — Process Workflow → `payload.workflow`

Find `^4\.\s+Process Workflow$` Heading 1. Determine format by scanning content between this Heading 1 and the next Heading 1:

**Format B — activity areas:** If any Heading 2 is found in the range, treat each Heading 2 as one step.
- `name` = Heading 2 text with leading number token stripped (regex `^\d+(?:\.\d+)?\s+`), max 200 chars
- `description` = all non-heading paragraphs between this Heading 2 and the next Heading 2 or Heading 1, joined with `\n\n`. Include `List Paragraph` bullets as part of the description.
- `step_type` = `"action"`
- `sort_order` = 1-based position
- Soft-warn if prose exists between the Section 4 Heading 1 and the first Heading 2 (framing paragraph); include it in `description` of step 1? No — drop it and warn. It's not a step.

**Format A — flat list:** If no Heading 2 is found, extract `List Paragraph` style items.
- Each non-empty paragraph with style name containing `"list"` (case-insensitive) is one step.
- `name` = first 200 chars of text
- `description` = full text
- `step_type` = `"action"`
- `sort_order` = 1-based position
- `Normal` paragraphs that immediately follow a List Paragraph item are appended to that item's `description` (space-separated). `Normal` paragraphs with no preceding step are dropped with soft-warn.
- Stop at next Heading 1.

**Hard-fail:** No Section 4 Heading 1, OR zero steps parsed.

**Performer persona:** Do not set. Leave unset so the mapper uses NULL. Deriving per-step performers from prose is unreliable.

### Section 5 — Process Completion → `payload.completion`

Heading 1 `^5\.\s+Process Completion$`. Same prose extraction as Section 1. Hard-fail if missing or empty.

### Section 6 — System Requirements → `payload.system_requirements`

Heading 1 `^6\.\s+System Requirements$`. Find the first table between this Heading 1 and the next Heading 1 whose header row is `["ID", "Requirement"]` (case-insensitive). Each data row → `{identifier: row[0], description: row[1], priority: "must"}`.

Skip empty rows and rows where `identifier` doesn't contain `-REQ-`.

**Hard-fail:** No Section 6 Heading 1, OR no matching table, OR zero requirements.

**Soft-warn:** requirement identifier doesn't match `^{PROCESS_CODE}-REQ-\d+$`.

### Section 7 — Process Data → `payload.process_data`

Heading 1 `^7\.\s+Process Data$`. Within range to next Heading 1, find each Heading 2 starting with `Entity:`. For each:

- `entity_name` = text after `Entity:`, stripped of any parenthetical qualifier. E.g. `Entity: Account (Partner Fields, Read)` → `entity_name = "Account"`. Keep the original heading in the description for context.
- `role` = `"referenced"`
- `description` = all non-heading paragraphs between this Heading 2 and the next Heading 2 or Heading 1, joined with `\n\n`. Prepend the original heading text (e.g. `"(Partner Fields, Read)"`) when a qualifier was present.
- `field_references` = list of `{name, usage: "displayed", description}` entries extracted from any six-column field table in this subsection. See **Field table parsing** below.

Empty Section 7 (only prose, no `Entity:` headings) → `process_data: []` with soft-warn `"Section 7 has no entity subsections"`. This is valid for entry-point processes.

**Hard-fail:** No Section 7 Heading 1.

### Section 8 — Data Collected → `payload.data_collected`

Heading 1 `^8\.\s+Data Collected$`. Same Heading-2-per-entity structure as Section 7, but for each entity produce `{entity_name, new_fields}` where `new_fields` comes from field tables within that subsection.

**Hard-fail:** No Section 8 Heading 1. Empty Section 8 (no entities) is allowed (soft-warn).

### Field table parsing (used by Sections 7 and 8)

CBM field tables have six columns and use the **two-row-per-field** pattern:

- Row 0: header `["Field Name", "Type", "Required", "Values", "Default", "ID"]`
- Odd rows (1, 3, 5, ...): field metadata — cells `[name, type, required, values, default, identifier]`
- Even rows (2, 4, 6, ...): description — all six cells contain the same description text (spanning).

For each field produce:

```python
{
  "field_name": row[0],           # keep camelCase
  "label": row[0],                # same as field_name
  "field_type": row[1],
  "is_required": parse_required(row[2]),
  "values": row[3],               # pass through raw
  "default_value": row[4],        # pass through raw
  "identifier": row[5],           # e.g. "CR-PARTNER-MANAGE-DAT-025"
  "description": description_row[0]
}
```

`parse_required(text)`:
- `text.strip().lower().startswith("yes")` → `True`
- `text.strip().lower().startswith("no")` → `False`
- anything else → `True` with soft-warn `"unclear required value: {text}"`

For `field_references` in Section 7, produce a simpler shape: `{name: field_name, usage: "displayed", description: description}`.

**Soft-warn:** field table has odd row count (missing description row for last field); description row cells don't all match (inconsistent spanning).

### Section 9 — Open Issues → `envelope.open_issues`

Heading 1 `^9\.\s+Open Issues$`. Find the **first** two-column table whose header is `["ID", "Issue"]` or `["ID", "Description"]` (case-insensitive). Each data row → `{identifier, description, status: "open"}`.

If a second two-column table exists in the section, soft-warn `"Section 9 has multiple tables; parsing only the first (process-owned issues). Subsequent tables likely contain inherited/upstream issues."` and ignore it.

Soft-warn on rows whose description starts with `CLOSED` or `RESOLVED` — include them anyway and let the mapper decide.

Empty Section 9 is allowed.

**Hard-fail:** No Section 9 Heading 1.

### Sections 10 and 11

Not parsed. No payload output.

## Mapper Enhancement (process_definition.py)

Add logic near the top of `map_payload()`, after extracting `process_id`:

```python
source_metadata = payload.get("source_metadata", {})
resolve_code = source_metadata.get("sub_domain_code") or source_metadata.get("domain_code")
if resolve_code and process_id:
    from automation.importer.mappers.base import resolve_by_code
    domain_id = resolve_by_code(conn, "Domain", "code", resolve_code)
    if domain_id is not None:
        # Fold into the Process update values built below
        proc_values["domain_id"] = domain_id
```

Be careful to emit a `Process` update record even when `proc_values` would otherwise be empty (e.g. if purpose/triggers/completion are all unchanged) — the `domain_id` update alone is worth writing.

## Tombstone

`automation/cbm_import/parsers/process_document.py`:

```python
"""TOMBSTONED — migrated to automation/importer/parsers/process_doc_docx.py on 04-10-26."""
from __future__ import annotations


def parse(*args, **kwargs):
    raise NotImplementedError(
        "Path A process document parser has been migrated to "
        "automation/importer/parsers/process_doc_docx.py. Use Path B "
        "ImportProcessor with the new adapter."
    )
```

Guard any call site in `automation/cbm_import/importer.py` that invokes `process_document.parse()` — catch `NotImplementedError` in `import_all()` following the master PRD tombstone pattern.

Delete or skip any legacy tests in `automation/tests/` that exercise the Path A process document parser.

## Tests

Follow the pattern in `automation/tests/test_importer_parsers_master_prd_docx.py`. Required test coverage:

**Fixture tests (real documents):**
1. MN-INTAKE fixture: parse succeeds, `source_metadata.domain_code == "MN"`, no `sub_domain_code`, process code prefix validates, 2 personas parsed, workflow has 8 steps (all Format A flat list), 13 requirements, 3 data_collected entities (Client Organization, Client Contact, Engagement), 1 open issue.
2. CR-PARTNER-MANAGE fixture: parse succeeds, `source_metadata.domain_code == "CR"`, `sub_domain_code == "CR-PARTNER"`, 1 persona (table format), workflow has 10 steps (all Format B activity areas, named `"Liaison Touchpoints"` through `"Partner Contact Management"`), 18 requirements, multiple `process_data` entities, multiple `data_collected` entities, 3 open issues (only first Section 9 table), soft-warn for second Section 9 table.

**Hard-failure synthetic tests:**
3. Missing header table → `ProcessDocParseError`
4. Missing Process Code row → `ProcessDocParseError`
5. Process code prefix mismatch (e.g. domain CR, process code `MN-FOO`) → `ProcessDocParseError`
6. Sub-domain code mismatch (e.g. sub-domain CR-PARTNER, process code `CR-MARKETING-FOO`) → `ProcessDocParseError`
7. Missing Section 1 Process Purpose → `ProcessDocParseError`
8. Missing Section 3 Personas → `ProcessDocParseError`
9. Section 3 exists but produces zero personas → `ProcessDocParseError`
10. Missing Section 4 Workflow → `ProcessDocParseError`
11. Section 4 exists but produces zero steps → `ProcessDocParseError`
12. Missing Section 6 System Requirements → `ProcessDocParseError`
13. Section 6 has no matching table → `ProcessDocParseError`
14. `work_item['item_type']` != `'process_definition'` → `ValueError`
15. File not found → `FileNotFoundError`

**Soft-warning synthetic tests:**
16. Missing Version/Status/Last Updated rows → warnings emitted, parse succeeds
17. Empty Section 7 (no Entity subsections) → warning + `process_data: []`
18. Empty Section 9 (no issues table) → parse succeeds, `open_issues: []`
19. Requirement identifier doesn't match process code prefix → warning
20. Field table with odd row count → warning
21. Section 9 has two tables → warning about second table, first is parsed
22. Unclear `is_required` value (e.g. `"Yes (system-generated)"`) → warning, treated as `True`

**Round-trip/structural tests:**
23. Envelope JSON is valid JSON and round-trips through `json.loads`
24. Envelope has required top-level keys (`output_version`, `work_item_type`, `work_item_id`, `session_type`, `payload`, `decisions`, `open_issues`)
25. Payload has all required keys present
26. Adapter does not perform database lookups (verify by passing a dummy work_item with no `conn`)

All tests must pass under `uv run pytest automation/tests/test_importer_parsers_process_doc_docx.py -v`.

## Verification Steps

After implementation:

1. `uv run ruff check automation/` — clean
2. `uv run pytest automation/tests/ -v` — all tests pass, no regressions
3. Manual verification against a real CBM rebuild: use the adapter to re-import MN-INTAKE and CR-PARTNER-MANAGE through the Path B pipeline, inspect the resulting `Process`, `ProcessStep`, `Requirement`, `ProcessPersona`, `ProcessEntity`, `ProcessField` rows in the CBM database, and confirm:
   - CR-PARTNER-MANAGE `Process.domain_id` points to the CR-PARTNER sub-domain Domain row, NOT CR (Bug 5 fix verified).
   - MN-INTAKE `Process.domain_id` points to the MN domain Domain row (no regression for top-level processes).
   - All workflow steps are present with correct `sort_order`.
   - All system requirements are present.

Report results back to Doug in plain text summary when complete.
