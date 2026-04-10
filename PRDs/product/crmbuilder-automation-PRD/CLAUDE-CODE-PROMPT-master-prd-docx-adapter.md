# Claude Code Prompt — Master PRD `.docx` → Path B Adapter

**Target repo:** `dbower44022/crmbuilder`
**Branch:** `main`
**Author:** Doug Bower (via Claude design session 04-10-26)

---

## Context

The CRM Builder Automation app currently has two parallel Master PRD importers:

1. **Path A** — `automation/cbm_import/` — legacy `.docx` parser that writes
   directly to the database. Has multiple bugs: doesn't parse sub-domains at
   all, mangles domain names by including section numbers and master IDs,
   collapses all Cross-Domain Services into a single synthetic "SVC" Domain row.

2. **Path B** — `automation/importer/` — the L2 PRD §11 seven-stage pipeline
   (`Receive → Parse → Map → Detect → Review → Commit → Trigger`) that
   consumes a JSON envelope. Already supports sub-domains and services
   correctly via `automation/importer/mappers/master_prd.py` (after the
   `is_service` payload-honoring fix in commit `6400ec1`).

This work migrates Master PRD imports from Path A to Path B by introducing a
new adapter that turns `CBM-Master-PRD.docx` into a Path B envelope JSON
string. The adapter feeds the existing seven-stage pipeline unchanged. Path A's
master PRD code is guarded with `NotImplementedError` (the other four Path A
parsers — process_document, entity_prd, entity_inventory, domain_prd — are
left untouched and will be migrated in future work).

**Source document version:** This adapter is built against
`CBM-Master-PRD.docx` v2.6 in `dbower44022/ClevelandBusinessMentoring`. v2.6
introduced the `MST-SVC-NNN` master ID series for services so that all
top-level entities (personas, domains, services) follow the same heading
format conventions.

---

## Acceptance Criteria

After this prompt runs successfully:

1. New module `automation/importer/parsers/master_prd_docx.py` exists with a
   `parse()` function matching the contract in **Section 2** below.
2. New supporting module `automation/importer/parsers/__init__.py` defines
   `ParseWarning`, `ParseReport`, and `MasterPrdParseError`.
3. The adapter passes a comprehensive test suite (see **Section 7**) using
   both synthetic in-memory documents and the real `CBM-Master-PRD.docx`
   fixture.
4. Path A's master PRD parser raises `NotImplementedError` when invoked
   (`automation/cbm_import/parsers/master_prd.py`,
   `automation/cbm_import/importer.py` master-PRD entry points,
   `automation/cbm_import/cli.py` master-PRD CLI flag).
5. Full test suite passes: `python -m pytest automation/tests/ -q` reports
   zero failures.
6. `ruff check automation/` reports zero issues.
7. End-to-end smoke test (described in **Section 9**) successfully imports
   the real `CBM-Master-PRD.docx` v2.6 into a fresh client database via
   `ImportProcessor.run_full_import()` and produces the expected
   Domain/Persona/Process counts.

---

## Section 1 — File Layout

Create:

```
automation/importer/parsers/
├── __init__.py              # ParseWarning, ParseReport, MasterPrdParseError
└── master_prd_docx.py       # parse() entry point + helpers
```

Modify:

```
automation/cbm_import/parsers/master_prd.py   # replace body with NotImplementedError
automation/cbm_import/importer.py             # guard master-PRD entry points
automation/cbm_import/cli.py                  # guard master-PRD CLI flag
```

Add tests:

```
automation/tests/test_importer_parsers_master_prd_docx.py
automation/tests/fixtures/cbm-master-prd-v2.6.docx   # copy from CBM repo
```

---

## Section 2 — Adapter Entry Point Contract

```python
# automation/importer/parsers/master_prd_docx.py

def parse(
    path: str | Path,
    work_item: dict,
    session_type: str = "initial",
) -> tuple[str, ParseReport]:
    """Parse CBM-Master-PRD.docx into a Path B envelope JSON string.

    :param path: Path to the .docx file.
    :param work_item: Work item dict with keys 'id' and 'item_type'.
                      item_type must be 'master_prd' or ValueError is raised.
    :param session_type: Session type for the envelope. Default 'initial'.
    :returns: Tuple of (envelope_json_string, ParseReport).
    :raises FileNotFoundError: If path does not exist.
    :raises MasterPrdParseError: If the document is structurally unparseable
                                 (see Section 5 for the six conditions).
    :raises ValueError: If work_item['item_type'] != 'master_prd'.
    """
```

The returned JSON string is a complete Path B envelope:

```json
{
  "output_version": "1.0",
  "work_item_type": "master_prd",
  "work_item_id": <int from work_item['id']>,
  "session_type": "<session_type arg>",
  "payload": { ... see Section 3 ... },
  "decisions": [],
  "open_issues": []
}
```

`output_version` must match what the existing
`automation/importer/parser.py` validator expects. Inspect that file to find
the canonical value.

---

## Section 3 — Payload Shape

The `payload` dict must conform to what
`automation/importer/mappers/master_prd.py` consumes (see
`automation/tests/test_importer_mappers_master_prd.py::_payload` for the
authoritative test fixture).

```python
{
    "organization_overview": "## Mission and Context\n\n...\n\n## Operating Model\n\n...",
    "personas": [
        {
            "identifier": "MST-PER-001",
            "name": "System Administrator",
            "description": "Paragraph one.\n\nParagraph two.",
        },
        # ... 13 personas
    ],
    "domains": [
        {
            "name": "Mentoring",
            "code": "MN",
            "description": "Domain Purpose paragraph(s) joined by \\n\\n",
            "sort_order": 1,
            "is_service": False,
            "sub_domains": [],   # MN has none
        },
        # MR (sort_order=2, no sub_domains),
        {
            "name": "Client Recruiting",
            "code": "CR",
            "description": "...",
            "sort_order": 3,
            "is_service": False,
            "sub_domains": [
                {
                    "name": "Partner Relationship Management",
                    "code": "CR-PARTNER",
                    "description": "...",  # from prose if found
                    "sort_order": 1,
                    "is_service": False,
                },
                # CR-MARKETING (sort_order=2),
                # CR-EVENTS (sort_order=3),
                # CR-REACTIVATE (sort_order=4),
            ],
        },
        # FU (sort_order=4, no sub_domains),
        # Services as additional top-level domain entries:
        {
            "name": "Notes Service",
            "code": "NOTES",
            "description": "Purpose paragraph(s) joined by \\n\\n",
            "sort_order": 101,
            "is_service": True,
            "sub_domains": [],
        },
        # Email Service (sort_order=102),
        # Calendar Service (sort_order=103),
        # Survey Service (sort_order=104),
    ],
    "processes": [
        {
            "name": "Client Intake",
            "code": "MN-INTAKE",
            "description": "One-line plain paragraph following the code/name paragraph.",
            "sort_order": 1,
            "tier": "core",
            "domain_code": "MN",
        },
        # ... 15 processes total in global Table 2 order, skipping sub-domain rows
    ],
}
```

---

## Section 4 — Parsing Strategy (One Section Per Source-Document Section)

### 4.1 Organization Overview (Section 1 of source)

- Locate `Heading 1` matching `^1\.\s+Organization Overview$`.
- Walk forward; for each `Heading 2` whose text matches
  `^1\.\d+\s+(.+)$`, capture the title (stripping the `1.N` prefix), then
  collect non-empty plain paragraphs (any non-Heading style) until the next
  `Heading 2` or `Heading 1`.
- Emit as markdown:
  ```
  ## {Subsection Title}

  {paragraph 1}

  {paragraph 2}
  ```
- Subsections joined with double newlines. Final result is the
  `organization_overview` string.
- **Warning if zero subsections found** → emit warning, set
  `organization_overview = ""`.

### 4.2 Personas (Section 2 of source)

- Locate `Heading 1` matching `^2\.\s+Personas$`.
- Walk forward until the next `Heading 1`. For each `Heading 3` whose text
  matches `^(MST-PER-\d+)\s*[—–-]\s*(.+)$`:
  - Capture `identifier` (group 1) and `name` (group 2, trimmed).
  - Collect subsequent non-empty plain paragraphs until the next `Heading 3`
    or `Heading 1`. Join with `\n\n` as `description`.
- **Hard failure** (`MasterPrdParseError`) if zero personas parsed.
- **Warning** if any persona has empty description.
- Emit personas in document order.

### 4.3 Top-Level Domains (Section 3 of source)

- Locate `Heading 1` matching `^3\.\s+Key Business Domains$`.
- Walk forward until the next `Heading 1`. For each `Heading 2` matching
  `^\d+(?:\.\d+)?\s+MST-DOM-\d+\s*[—–-]\s*(.+?)\s*\(([A-Z]+)\)\s*$`:
  - Capture `name` (group 1) and `code` (group 2).
  - Discard the `MST-DOM-NNN` master ID.
  - Find the `Heading 3 — Domain Purpose` child within this domain section.
    Description = the plain paragraphs immediately under it, joined with
    `\n\n`. Stop at the next `Heading 3` or `Heading 2`.
  - Assign `sort_order` by document position within Section 3 (1-indexed).
  - `is_service = False`.
  - `sub_domains = []` initially (populated in 4.4).
- **Hard failure** if zero top-level domains parsed.
- **Warning** for any domain missing its `Domain Purpose` subsection.

### 4.4 Sub-Domains (driven by Table 2)

**Table 2 is identified as the table whose first row has cells matching
`["Code", "Process / Sub-Domain", "Domain", "Tier"]` (case-insensitive,
trimmed).** Locate it once and reuse for both 4.4 and 4.6.

- **Hard failure** if no such table is found.
- **Hard failure** if the column header doesn't match the expected four-column
  structure.

For each data row of Table 2:

1. Strip and read four columns.
2. If column 2 (`Process / Sub-Domain`) ends with `(Sub-Domain)` (case-
   insensitive, ignoring trailing whitespace):
   - This row is a **sub-domain**.
   - `code` = column 1.
   - `name` = column 2 with `(Sub-Domain)` suffix stripped and trimmed.
   - Parent domain code = the parenthesized code in column 3
     (regex: `\(([A-Z]+)\)`).
   - `sort_order` within parent = position among sub-domain rows that share
     the same parent, in Table 2 row order (1-indexed).
   - `is_service = False`.
   - `description = ""` initially (enriched below).
3. Otherwise the row is a process — defer to 4.6.

**Prose enrichment:** Within each top-level domain section in Section 3, look
for a `Heading 3` whose text equals `Sub-Domains`. If found, walk plain
paragraphs underneath until the next `Heading 3` or `Heading 2`. For each
plain paragraph matching `^([A-Z]+-[A-Z]+)\s*[—–-]\s*(.+)$`:
- Capture the code (group 1).
- The very next non-empty plain paragraph is the description.
- Build a `{code: description}` lookup.

After Table 2 is fully walked, merge: for each sub-domain in the Table 2
list, look up its description in the prose lookup. If found, set it. If
missing, warn (`category="missing_description"`,
`location="Sub-domain {code}"`) and leave as `""`.

For each prose entry whose code is **not** in the Table 2 sub-domain list,
warn (`category="orphan_prose"`,
`location="Sub-Domains prose for {code}"`).

Attach sub-domains to their parent domain entries via the parent code lookup.

### 4.5 Cross-Domain Services (Section 4 of source)

- Locate `Heading 1` matching `^4\.\s+Cross-Domain Services$`.
- Walk forward until the next `Heading 1`. For each `Heading 2` matching
  `^\d+(?:\.\d+)?\s+MST-SVC-\d+\s*[—–-]\s*(.+?)\s*\(([A-Z]+)\)\s*$`:
  - Capture `name` (group 1, **keeping the trailing "Service" word**) and
    `code` (group 2).
  - Discard the `MST-SVC-NNN` master ID.
- For description: within this service's section, find a non-styled paragraph
  whose stripped text equals `Purpose` (no colon). Collect subsequent
  non-empty plain paragraphs until a paragraph whose stripped text is
  `Capabilities` or starts with `Consuming Domains:` or `Entities Owned:`,
  or until the next `Heading 2`. Join with `\n\n`.
- Discard `Capabilities`, `Consuming Domains`, `Entities Owned` content
  entirely (no warning — they're intentionally not in the payload contract).
- Assign `sort_order` starting at **101**, incrementing by document position
  within Section 4. (Notes=101, Email=102, Calendar=103, Survey=104.)
- `is_service = True`, `sub_domains = []`.
- Append services to the same `payload["domains"]` list as top-level domains
  — they are top-level Domain records per DEC-020.
- **Warning** if Section 4 is missing entirely → no service entries, no
  hard failure.
- **Warning** if any service has empty Purpose.

### 4.6 Processes (driven by Table 2)

Walk Table 2 again (or in the same pass as 4.4). For each row whose column 2
does **not** end with `(Sub-Domain)`:

- `code` = column 1.
- `name` = column 2, trimmed (no suffix to strip).
- `domain_code` = the parenthesized code in column 3.
- `tier` = column 4, **lowercased**. Expected values: `core`, `important`,
  `enhancement`. If the lowercased value is none of those, warn
  (`category="bad_tier"`, `location="Process {code}"`,
  `message="Unexpected tier '{value}'"`) and set `tier=None`.
- `sort_order` = global 1-indexed position among non-sub-domain rows in
  Table 2 order.
- `description = ""` initially (enriched below).

**Prose enrichment:** Within each top-level domain section in Section 3, look
for a `Heading 3` whose text equals `Business Processes`. Walk plain
paragraphs underneath until the next `Heading 3` or `Heading 2`. For each
plain paragraph matching `^([A-Z]+(?:-[A-Z]+)+)\s*[—–-]\s*(.+)$`:
- Capture the code (group 1).
- The very next non-empty plain paragraph is the one-line description.
- Build a `{code: description}` lookup.

Merge: for each Table 2 process, look up the description and set it. If
missing, warn (`category="missing_description"`,
`location="Process {code}"`). If a prose entry has no matching Table 2 row,
warn (`category="orphan_prose"`,
`location="Business Processes prose for {code}"`).

- **Hard failure** if zero processes parsed.

---

## Section 5 — Hard Failure Conditions

The adapter raises `MasterPrdParseError` exactly in these six cases:

1. Document has no `Heading 1` matching `^2\.\s+Personas$`.
2. Document has no `Heading 1` matching `^3\.\s+Key Business Domains$`.
3. Process Tier Summary table not found (no table whose header row matches
   `["Code", "Process / Sub-Domain", "Domain", "Tier"]`).
4. Process Tier Summary table has wrong column structure (header found but
   doesn't have exactly 4 columns or wrong column names).
5. Zero personas parsed despite Section 2 existing.
6. Zero top-level domains parsed despite Section 3 existing, **or** zero
   processes parsed despite Table 2 existing with data rows.

`FileNotFoundError` propagates naturally for missing files (no wrapping).
`ValueError` for `work_item['item_type'] != 'master_prd'`.

All other issues are warnings in `ParseReport`.

---

## Section 6 — `ParseReport` Module

`automation/importer/parsers/__init__.py`:

```python
"""Source-format parsers — turn external files into Path B envelope JSON."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ParseWarning:
    """A soft issue encountered during parsing — does not abort parsing."""
    severity: Literal["info", "warning"]
    category: str    # e.g. "missing_description", "orphan_prose", "bad_tier"
    location: str    # e.g. "Persona MST-PER-007", "Process MN-INTAKE"
    message: str


@dataclass
class ParseReport:
    """Soft-issue report returned alongside the parsed envelope."""
    warnings: list[ParseWarning] = field(default_factory=list)
    parsed_counts: dict[str, int] = field(default_factory=dict)

    def warn(self, category: str, location: str, message: str) -> None:
        """Append a warning-severity entry."""
        self.warnings.append(
            ParseWarning(
                severity="warning",
                category=category,
                location=location,
                message=message,
            )
        )


class MasterPrdParseError(Exception):
    """Raised when CBM-Master-PRD.docx is structurally unparseable."""
```

`parsed_counts` keys after a successful parse should be:
`persona`, `domain`, `sub_domain`, `service`, `process`.

---

## Section 7 — Tests

Create `automation/tests/test_importer_parsers_master_prd_docx.py` with:

### 7.1 Real-document tests (use the v2.6 fixture)

Copy `CBM-Master-PRD.docx` v2.6 from
`dbower44022/ClevelandBusinessMentoring` to
`automation/tests/fixtures/cbm-master-prd-v2.6.docx`. (You can download it
via the GitHub raw URL or expect Doug to commit it. Document this in the
prompt response.)

- `test_parse_real_document_returns_envelope_and_report` — basic shape:
  envelope is a JSON string that parses to a dict with required fields,
  report is a ParseReport instance.
- `test_parse_real_document_envelope_metadata` — `output_version`,
  `work_item_type="master_prd"`, `work_item_id`, `session_type` correctly
  populated from inputs.
- `test_parse_real_document_persona_count` — exactly 13 personas with codes
  `MST-PER-001` through `MST-PER-013`.
- `test_parse_real_document_domain_count` — exactly 4 top-level non-service
  domains: MN, MR, CR, FU with `is_service=False`. Names are exactly
  `Mentoring`, `Mentor Recruitment`, `Client Recruiting`, `Fundraising`
  (no section numbers, no master IDs).
- `test_parse_real_document_subdomain_structure` — CR has exactly 4
  sub-domains in this order: CR-PARTNER, CR-MARKETING, CR-EVENTS,
  CR-REACTIVATE. MN, MR, FU have empty `sub_domains` lists.
- `test_parse_real_document_service_count` — exactly 4 service domains:
  NOTES, EMAIL, CALENDAR, SURVEY with `is_service=True`,
  `sort_order` 101–104, names ending in " Service".
- `test_parse_real_document_process_count` — exactly 15 processes with
  global sort_order 1..15.
- `test_parse_real_document_process_tiers` — every process has a tier in
  `{"core", "important", "enhancement"}` (no `None`, no warnings about bad
  tiers).
- `test_parse_real_document_organization_overview_format` — overview
  contains `## Mission and Context`, `## Operating Model`, and
  `## Why a CRM is Needed` markdown headers.
- `test_parse_real_document_no_warnings_on_v26` — `report.warnings` is empty
  when parsing the canonical v2.6 fixture. **This is a regression guard:
  it locks in that the canonical document parses cleanly with zero soft
  issues.**

### 7.2 Hard-failure tests (synthetic minimal documents)

Use `python-docx` to construct minimal in-memory documents and assert each
of the six raise conditions:

- `test_raises_on_missing_personas_section`
- `test_raises_on_missing_domains_section`
- `test_raises_on_missing_table2`
- `test_raises_on_table2_wrong_columns`
- `test_raises_on_zero_personas_parsed`
- `test_raises_on_zero_domains_parsed`
- `test_raises_on_zero_processes_parsed`
- `test_raises_filenotfound`
- `test_raises_valueerror_on_wrong_work_item_type`

### 7.3 Soft-warning tests

- `test_warns_on_missing_domain_purpose` — synthetic doc where MN has no
  `Domain Purpose` Heading 3; assert warning category
  `missing_description`, location contains `MN`.
- `test_warns_on_orphan_prose_subdomain` — Table 2 has CR-PARTNER but prose
  has CR-PARTNER + CR-GHOST; assert orphan warning for CR-GHOST.
- `test_warns_on_bad_tier_value` — Table 2 row has tier `Critical`; assert
  warning category `bad_tier` and that the resulting process has
  `tier=None`.

### 7.4 Round-trip test (most important)

- `test_envelope_passes_path_b_validation` — parse the v2.6 fixture, then
  pass the resulting JSON string through
  `automation.importer.parser.parse_and_validate` and assert no exception.
  This proves the adapter produces a structurally valid Path B envelope.

- `test_envelope_round_trip_through_mapper` — parse the v2.6 fixture,
  decode the JSON, run `automation.importer.mappers.master_prd.map_payload`
  on the payload, and assert that the resulting `ProposedBatch` contains:
  - 13 Persona create records
  - 8 Domain create records (MN, MR, CR, FU, NOTES, EMAIL, CALENDAR, SURVEY)
  - 4 sub-domain Domain create records with `parent_domain_id` intra-batch
    refs to `batch:domain:CR`
  - 15 Process create records, each with either a resolved `domain_id` or
    an intra-batch ref

---

## Section 8 — Path A Guards

### 8.1 `automation/cbm_import/parsers/master_prd.py`

Replace the **entire file body** (after the module docstring and imports
needed for the exception) with:

```python
"""Master PRD .docx parser — MIGRATED to Path B.

The Master PRD parser has moved to:
    automation.importer.parsers.master_prd_docx

This module is retained as a tombstone. Calling parse() raises immediately.
"""

from __future__ import annotations
from pathlib import Path


def parse(path: str | Path):
    raise NotImplementedError(
        "Master PRD parsing has migrated to "
        "automation.importer.parsers.master_prd_docx.parse(). "
        "Use ImportProcessor.run_full_import() with the envelope JSON "
        "produced by the new adapter. "
        "See PRDs/product/crmbuilder-automation-PRD/"
        "CLAUDE-CODE-PROMPT-master-prd-docx-adapter.md for context."
    )
```

### 8.2 `automation/cbm_import/importer.py`

Find every entry point in `importer.py` that handles master PRD imports
(the methods that call into `parsers/master_prd.py` or that handle the
master_prd document type). Add an early raise:

```python
raise NotImplementedError(
    "Master PRD imports must go through Path B: "
    "automation.importer.parsers.master_prd_docx + ImportProcessor."
)
```

**Do not** modify the `_get_or_create_services_domain` helper or any
process-import code paths — those are still used by the other four
legacy parsers. Be surgical.

### 8.3 `automation/cbm_import/cli.py`

If the CLI has a `--type=master_prd` flag, document type detection logic, or
any branch that dispatches to master PRD handling, add an early-fail message:

```python
if document_type == "master_prd":
    raise SystemExit(
        "Master PRD imports have migrated to Path B. "
        "Use the new ImportProcessor entry point. "
        "See PRDs/product/crmbuilder-automation-PRD/"
        "CLAUDE-CODE-PROMPT-master-prd-docx-adapter.md."
    )
```

The exact location depends on the CLI's structure — inspect the file and
place the guard at the earliest point where master_prd is identifiable.

### 8.4 Update legacy tests

Any existing test in `automation/tests/` that imports from
`automation.cbm_import.parsers.master_prd` or that exercises the master PRD
path through `cbm_import.importer` must be updated to either:
- Be marked `@pytest.mark.skip(reason="Path A master PRD migrated to Path B")`, or
- Be deleted if they have no analog in the new test file.

Prefer skipping over deleting so the historical test intent is preserved.
Do not delete tests for the other four legacy parsers.

---

## Section 9 — End-to-End Smoke Test (manual, by Doug after the prompt runs)

After all automated tests pass, the prompt should print instructions for
Doug to manually verify the end-to-end import works against the real
database. The instructions should be a Python snippet roughly like:

```python
# Run from repo root after `git pull` and after a fresh DB reset.
import json
from pathlib import Path
from automation.db.connection import get_client_connection, get_master_connection
from automation.importer.parsers.master_prd_docx import parse
from automation.importer.pipeline import ImportProcessor

work_item = {"id": <find_a_master_prd_work_item_id>, "item_type": "master_prd"}
envelope_json, report = parse(
    "../ClevelandBusinessMentoring/PRDs/CBM-Master-PRD.docx",
    work_item,
)
print(f"Warnings: {len(report.warnings)}")
print(f"Counts: {report.parsed_counts}")

processor = ImportProcessor(client_conn, master_conn)
result = processor.run_full_import(work_item["id"], envelope_json)
print(f"Imported successfully. Session: {result.ai_session_id}")
```

The expected outcome when run against CBM:

- `report.parsed_counts == {"persona": 13, "domain": 4, "sub_domain": 4, "service": 4, "process": 15}`
- `report.warnings == []`
- After commit, `SELECT id, code, name, parent_domain_id, is_service FROM Domain ORDER BY ...` returns:
  - 4 top-level non-service domains (MN, MR, CR, FU) with clean names
  - 4 sub-domains (CR-PARTNER, CR-MARKETING, CR-EVENTS, CR-REACTIVATE) with `parent_domain_id` pointing at CR's id
  - 4 service domains (NOTES, EMAIL, CALENDAR, SURVEY) with `is_service=1`, `parent_domain_id IS NULL`
- `SELECT COUNT(*) FROM Process` returns 15
- `SELECT COUNT(*) FROM Persona` returns 13

---

## Section 10 — Implementation Notes & Constraints

- Use `python-docx` (already a project dependency — `pip install python-docx`
  if not). Read paragraphs via `doc.paragraphs`, tables via `doc.tables`.
- When checking paragraph style, use `p.style.name if p.style else 'None'`
  to avoid `AttributeError` on paragraphs with no style.
- Em-dash is U+2014 (`—`); en-dash is U+2013 (`–`); hyphen-minus is `-`.
  Use the regex character class `[—–-]` for tolerant separator matching.
  **Note: in the regex, the hyphen must be last to avoid being interpreted
  as a range.**
- Do not use the `automation.cbm_import.docx_parser` helpers — the new
  parser is fully self-contained in
  `automation.importer.parsers.master_prd_docx`. The Path A and Path B
  trees should not import from each other.
- The adapter is **pure**: no logging, no print statements, no file system
  writes other than reading the input. All output goes through the return
  value.
- All code must be type-hinted and pass `ruff check`.
- Follow the existing project style: snake_case, dataclasses for structured
  data, `from __future__ import annotations` at the top of new modules.
- The JSON envelope serialization should use `json.dumps(envelope,
  ensure_ascii=False, indent=2)` for human-readable storage in
  `AISession.raw_response` (mirrors how AI session imports look).

---

## Section 11 — Out of Scope

The following are explicitly **not** part of this prompt and should not be
attempted:

- Migration of the other four Path A parsers (process_document, entity_prd,
  entity_inventory, domain_prd). They remain on Path A.
- Deletion of the `automation/cbm_import/` package. Tombstone-guard only.
- Changes to the L2 PRD document.
- Changes to `automation/importer/mappers/master_prd.py` (already fixed in
  commit `6400ec1`).
- UI work to surface `ParseReport` warnings in the Data Browser or Import
  screens. The CLI smoke test in Section 9 is the only consumer for now.
- Sub-domain-level processes (e.g., CR-PARTNER-PROSPECT). These are not in
  the Master PRD and will be handled by a future process_document parser.

---

## Reporting Back

When the prompt completes, report:

1. List of files created and modified.
2. Test results (`python -m pytest automation/tests/ -q` summary).
3. Ruff results (`ruff check automation/`).
4. Any deviations from this spec, with justification.
5. The exact `parsed_counts` output from a test parse of the v2.6 fixture
   (if the fixture was committed in this run; otherwise note that Doug
   needs to commit the fixture before tests can run).
