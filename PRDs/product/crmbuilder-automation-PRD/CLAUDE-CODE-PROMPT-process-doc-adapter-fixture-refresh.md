# CLAUDE-CODE-PROMPT: Process Doc Adapter — Fixture Refresh + Test Corrections

**Repo:** `dbower44022/crmbuilder`
**Date:** 04-12-26
**Goal:** Fix incorrect test fixtures and assertions left over from the 04-10-26 process doc adapter migration. Add the missing CR-PARTNER-MANAGE fixture so Format B (activity-area workflow, sub-domain header, persona table, two-table Section 9) is exercised by a real-document test, and verify the Bug 5 fix (sub-domain → Process.domain_id) actually works on a real document.

## Background

The 04-10-26 migration (commit history: new adapter at `automation/importer/parsers/process_doc_docx.py`, mapper enhancement, tombstoned Path A parser, fixture `automation/tests/fixtures/cbm-mn-intake-v2.3.docx`, and 44 tests in `automation/tests/test_importer_parsers_process_doc_docx.py`) shipped with two latent problems:

1. **The MN-INTAKE fixture is misnamed.** The file `automation/tests/fixtures/cbm-mn-intake-v2.3.docx` actually contains MN-INTAKE v2.2 content (its `Version` row says `2.2`). It was copied from a stale, sparse-checkout clone of the CBM repo that has since been deleted. The real v2.3 — which is materially different (4 additional REQ-010 through REQ-013) — lives in the canonical CBM clone at `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/MN/MN-INTAKE.docx`.

2. **The CR-PARTNER-MANAGE fixture was never added.** Three tests (`TestCRPartnerManage`) are skipped because the file doesn't exist. Without this fixture, none of the Format B code paths — sub-domain header row, table-based personas, activity-area workflow, two-table Section 9 — have a real-document test, and the Bug 5 fix (sub-domain → Process.domain_id) has no end-to-end verification.

3. **Adapter assumes a `Process Name` row** in the header table. The real MN-INTAKE v2.3 does not have one (its header rows are `Domain`, `Process Code`, `Version`, `Status`, `Last Updated`, `Source`). The adapter must treat `Process Name` as optional and fall back to `Process Code` when absent.

## Deliverables

### 1. Re-copy MN-INTAKE fixture (canonical source)

Replace the existing `automation/tests/fixtures/cbm-mn-intake-v2.3.docx` with the real v2.3 file from `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/MN/MN-INTAKE.docx`. Verify the version row inside the file reads `2.3`, not `2.2`, before committing.

### 2. Add CR-PARTNER-MANAGE fixture

Copy `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/CR/PARTNER/CR-PARTNER-MANAGE.docx` to `automation/tests/fixtures/cbm-cr-partner-manage-v1.0.docx`. Verify the version row reads `1.0` before committing.

### 3. Make `Process Name` header row optional

In `automation/importer/parsers/process_doc_docx.py`, change the header table parsing so that a missing `Process Name` row is **not** a hard failure. Instead:

- If `Process Name` row is absent, set `payload.source_metadata.process_name` to the value of `Process Code`, and emit a soft warning with category `missing_optional_header_row`, location `Process Name`, message `"Process Name row absent — defaulting to process code"`.
- All other hard-fail conditions for the header table remain unchanged.

### 4. Update test assertions to v2.3 counts

In `automation/tests/test_importer_parsers_process_doc_docx.py`, find the `TestMnIntake` (or equivalent) class and update assertions to match MN-INTAKE v2.3:

| Field | Expected value |
|---|---|
| `source_metadata.process_code` | `"MN-INTAKE"` |
| `source_metadata.domain_code` | `"MN"` |
| `source_metadata.sub_domain_code` | absent (None or missing key) |
| `source_metadata.version` | `"2.3"` |
| `source_metadata.process_name` | `"MN-INTAKE"` (fallback — no Process Name row) |
| `personas` count | 2 |
| `personas[0].identifier` | `"MST-PER-013"` (Client) |
| `personas[1].identifier` | `"MST-PER-003"` (Client Administrator) |
| `workflow` count | 9 (Format A — flat List Paragraph items) |
| `system_requirements` count | 13 |
| First requirement identifier | `"MN-INTAKE-REQ-001"` |
| Last requirement identifier | `"MN-INTAKE-REQ-013"` |
| `process_data` count | 0 (Section 7 is empty for entry-point process — soft warning expected) |
| `data_collected` count | 3 (Client Organization, Client Contact, Engagement) |
| `open_issues` count | 2 (one is marked CLOSED in description — adapter passes both through, mapper decides) |
| Soft warning expected | `"Process Name row absent"` (from deliverable 3) |
| Soft warning expected | `"Section 7 has no entity subsections"` |

### 5. Activate CR-PARTNER-MANAGE tests with v1.0 assertions

In the same test file, find `TestCRPartnerManage` (currently skipped) and:

- Remove the skip marker.
- Update assertions to match the real CR-PARTNER-MANAGE.docx v1.0:

| Field | Expected value |
|---|---|
| `source_metadata.process_code` | `"CR-PARTNER-MANAGE"` |
| `source_metadata.domain_code` | `"CR"` |
| `source_metadata.sub_domain_code` | `"CR-PARTNER"` |
| `source_metadata.version` | `"1.0"` |
| `source_metadata.process_name` | `"CR-PARTNER-MANAGE"` (fallback — no Process Name row) |
| `personas` count | 1 (table-format — MST-PER-008 Partner Coordinator) |
| `personas[0].identifier` | `"MST-PER-008"` |
| `personas[0].name` | `"Partner Coordinator"` |
| `workflow` count | 10 (Format B — Heading 2 activity areas) |
| `workflow[0].name` | `"Liaison Touchpoints"` (number prefix `4.1` stripped) |
| `workflow[9].name` | `"Partner Contact Management"` (number prefix `4.10` stripped) |
| `system_requirements` count | 18 |
| `process_data` count | ≥ 5 (Engagement, Session, Contact, Event, Marketing Records, Partnership Agreement, Account — exact count depends on adapter handling of qualifier suffixes) |
| `data_collected` count | ≥ 4 (Account, Contact, Partnership Agreement, Engagement, Note) |
| `open_issues` count | 3 (only first Section 9 table — the second table contains inherited issues) |
| Soft warning expected | `"Process Name row absent"` |
| Soft warning expected | `"Section 9 has multiple tables"` (second table flagged) |

### 6. Verify Bug 5 fix end-to-end (manual database test)

After tests pass, perform a real database verification:

1. Use the existing CBM client database at `automation/data/cbm-client.db` (from the 04-10-26 rebuild). Do NOT rebuild from scratch — we want to verify the mapper enhancement on top of the current database.
2. Construct a `work_item` for CR-PARTNER-MANAGE: `{"id": <ai_session work item id>, "item_type": "process_definition", "process_id": <Process row id for CR-PARTNER-MANAGE>}`. The Process row for CR-PARTNER-MANAGE was manually created in the 04-10-26 session with `domain_id` pointing to CR-PARTNER (Domain id=5).
3. Run the adapter on `automation/tests/fixtures/cbm-cr-partner-manage-v1.0.docx` to produce the envelope JSON.
4. Run the envelope through `ImportProcessor.run_full_import()`.
5. Inspect the resulting `Process` row for CR-PARTNER-MANAGE. Confirm `Process.domain_id` is still 5 (CR-PARTNER sub-domain), NOT 4 (CR top-level domain). This proves the Bug 5 fix works.
6. Repeat the same procedure for MN-INTAKE — confirm its `Process.domain_id` resolves to the MN domain row (whatever id MN has). This proves no regression for top-level processes.

Capture the database query results and report them in the summary.

## Verification Steps

After implementation:

1. `uv run ruff check automation/` — clean
2. `uv run pytest automation/tests/test_importer_parsers_process_doc_docx.py -v` — all tests pass (including the 3 previously-skipped CR-PARTNER-MANAGE tests, now active)
3. `uv run pytest automation/tests/ -v` — full suite, no regressions
4. Manual database verification per deliverable 6, with results pasted into the summary

Report results back to Doug in plain text. Specifically include:

- Confirmation that the MN-INTAKE fixture file's internal version row is now `2.3` (not `2.2`)
- Confirmation that the CR-PARTNER-MANAGE fixture file's internal version row is `1.0`
- Test counts: total tests, passed, skipped, failed
- Database verification: the actual `Process.domain_id` values found for both processes
