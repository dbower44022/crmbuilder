# CLAUDE-CODE-PROMPT — View Filters Feasibility Spike (Series A — Feasibility)

## Revision Control

| Field         | Value                |
|---------------|----------------------|
| Document      | View Filters Feasibility Spike |
| Series        | view-filters         |
| Version       | 0.1                  |
| Last Updated  | 05-04-26 10:30       |
| Author        | Doug Bower           |
| Status        | Draft, awaiting execution |

## Change Log

| Version | Date           | Notes                                |
|---------|----------------|--------------------------------------|
| 0.1     | 05-04-26 10:30 | Initial draft. First prompt of the view-filters series. |

---

## Session Start (Required)

Before any work begins, read `CLAUDE.md` in the repo root. Confirm understanding of session-start conventions, file locations, and commit discipline before proceeding.

---

## Purpose

Verify whether the metadata API supports creation of admin-defined **primary filters** and **boolean filters** for list views via PUT requests to `/api/v1/Metadata/selectDefs/{Entity}` and `/api/v1/Metadata/clientDefs/{Entity}`.

The existing automation marks `clientDefs`-based "saved views" as `NOT_SUPPORTED` and emits a MANUAL CONFIGURATION REQUIRED advisory. This spike verifies whether that short-circuit is too aggressive — specifically whether it incorrectly rejects admin-defined system filters that *are* expressible through metadata, conflating them with user-scoped saved searches that genuinely have no API path.

---

## Background

There are at least three distinct filter mechanisms in this CRM platform:

1. **User saved searches** — per-user filters saved through the UI, stored in user-scoped DB rows. No public REST API write path. **Confirmed unsupported. Out of scope for this spike.**

2. **Primary filters** (admin-defined dropdown options) — defined in `selectDefs.{Entity}` via either a PHP class (`primaryFilterClassNameMap`) or a pure `where` clause. UI listing controlled by `clientDefs.{Entity}.filterList`. **Hypothesis: writable via metadata API when expressed as a pure `where` clause.**

3. **Boolean filters** (admin-defined toggles) — defined in `selectDefs.{Entity}.boolFilters.{name}.where` with UI listing in `clientDefs.{Entity}.boolFilterList`. **Same hypothesis.**

If a filter is expressible as a pure `where` clause (no PHP, no nonstandard joins), then it should be creatable entirely through the metadata API. Scalar equality on a custom enum field is the textbook case.

---

## Test Target

| Item                  | Value                                          |
|-----------------------|------------------------------------------------|
| Instance              | CBM dev (NOT production). Use existing connection details from CRM Builder configuration. |
| Entity                | `Account`                                      |
| Discriminator field   | `cAccountType` (custom enum)                   |
| Enum values           | `Client`, `Partner`, `Donor/Sponsor`           |
| Expected behavior     | Each enum value maps to one primary filter that narrows the Account list to records with that `cAccountType` value. Boolean filter equivalents created in parallel for comparison. |

---

## Out of Scope

- Contact entity (mechanism is identical to Account; Account is sufficient proof).
- User saved searches (confirmed unsupported).
- Role-based / ACL-driven record visibility filters (deferred to v1.2 Category 6).
- YAML schema design for view filters (separate prompt in this series, only if the spike succeeds).
- Parser/manager implementation in `automation/` (separate prompts, only after schema is approved).
- Edits to any production code path.

---

## Investigation Tasks

### Task 1 — Baseline capture

Before any mutation:

- `GET /api/v1/Metadata/selectDefs/Account`
- `GET /api/v1/Metadata/clientDefs/Account`

Save the responses to:

- `scripts/spikes/view-filters/baseline-selectDefs-Account.json`
- `scripts/spikes/view-filters/baseline-clientDefs-Account.json`

These serve as both reference and rollback target.

### Task 2 — Primary filter creation

Construct a metadata PUT payload that:

- Adds three primary filter definitions under `selectDefs.Account` (proposed names: `accountTypeClient`, `accountTypePartner`, `accountTypeDonorSponsor`), each with a `where` clause of the form:
  ```json
  {"type": "equals", "attribute": "cAccountType", "value": "<EnumValue>"}
  ```
- Adds the three filter names to `clientDefs.Account.filterList`.

PUT each through the metadata API. Capture the exact request payload and response status/body.

If the API rejects the structure, iterate: try the older `primaryFilterClassNameMap` form, try array vs. object shapes, try `select.primaryFilters.*` path, etc. **Document every variant attempted, in order, with response codes.** Negative results are valuable.

### Task 3 — Boolean filter creation

Repeat for boolean filters:

- Definitions under `selectDefs.Account.boolFilters.{name}.where`
- UI listing under `clientDefs.Account.boolFilterList`

This gives a second data point on which metadata shapes are accepted.

### Task 4 — Persistence verification

After successful PUT:

- `GET` the same metadata paths and confirm the new filters round-trip correctly (structural compare against what was PUT).
- Determine whether a cache-clear (`POST /api/v1/Admin/clearCache` or equivalent) is required for changes to take effect.
- Wait/clear cache as needed and re-test.

### Task 5 — Functional verification

Execute searches that exercise the new filters:

```
GET /api/v1/Account?primaryFilter=accountTypeClient
GET /api/v1/Account?primaryFilter=accountTypePartner
GET /api/v1/Account?primaryFilter=accountTypeDonorSponsor
```

For each, confirm:

- Response includes only records matching the expected `cAccountType` value.
- Total count matches a direct equality query (`?where[0][type]=equals&where[0][attribute]=cAccountType&where[0][value]=Client`).

For boolean filters, the equivalent is `?boolFilterList[]={name}`.

### Task 6 — UI verification (manual, by Doug)

Document the manual UI checks for Doug to perform after backend tests succeed:

- Open the Account list view in browser, hard-refresh.
- Confirm the three new primary filters appear in the filter dropdown.
- Click each; confirm displayed records narrow correctly.
- Same exercise for boolean filter toggles.

The findings report should include a short, copy-pasteable checklist of these UI steps.

### Task 7 — Edge cases

Test and document:

- **Slash in enum value.** Does `Donor/Sponsor` cause encoding or parsing issues anywhere (filter name, `where`-clause value, URL params)? Use a sanitized name (`accountTypeDonorSponsor`) but the literal slashed value.
- **Cache behavior.** Is a cache clear strictly required, or does the UI pick up changes on next page load?
- **Custom-field discriminator.** Does the `c` prefix on `cAccountType` introduce any quirks vs. a stock field?
- **Order of operations.** Does `clientDefs.filterList` need the filter name to exist in `selectDefs` first, or vice versa? What error does the wrong order produce?
- **Idempotence.** PUT the same payload twice — should be a no-op the second time, not a duplicate or error.

### Task 8 — Cleanup

DELETE or PUT-revert the test metadata to restore the baseline captured in Task 1. Verify the baseline is restored by re-fetching and comparing.

**If cleanup fails, halt and surface the failure rather than leaving the instance in an inconsistent state.**

---

## Deliverables

### Required

1. **Findings report** at `PRDs/product/crmbuilder-automation-PRD/view-filters-feasibility-findings.md`, structured as:

   - Revision Control & Change Log (per output standards: `Last Updated MM-DD-YY HH:MM`).
   - **Verdict** — one of: **Feasible**, **Partially feasible**, or **Not feasible**.
   - **Evidence summary** — which API calls succeeded, which failed, with response codes.
   - **Working payload(s)** — exact JSON that successfully created a primary filter and a boolean filter, copy-paste reproducible.
   - **Edge case findings** — table form, one row per case from Task 7.
   - **Constraints discovered** — cache requirements, ordering rules, encoding quirks, etc.
   - **Recommendations** — should the existing `NOT_SUPPORTED` short-circuit be relaxed? If so, for which sub-cases? What stays unsupported?

2. **Spike scripts** at `scripts/spikes/view-filters/` — the actual Python scripts run during the spike, kept for reproducibility. Use the existing `automation/api_client.py` for all API calls. **Do not commit by default**; ask Doug whether to commit before doing so.

### Conditional (only if verdict is Feasible or Partially feasible)

3. **YAML schema sketch** — append a section to the findings report titled "Proposed YAML schema (sketch)" with a strawman of how view filters might be expressed in a CBM YAML program file. One paragraph of explanation plus one short example block. This is **not** a final spec — schema design happens in the next prompt of the series.

---

## Acceptance Criteria

- Findings report exists at the specified path and follows output standards (revision control, change log, `MM-DD-YY HH:MM` Last Updated).
- Verdict is unambiguous (one of the three options) and supported by captured evidence.
- If verdict is Feasible or Partially feasible, at least one working metadata payload is captured verbatim in the report.
- Baseline metadata is restored on the test instance (no residual test filters left behind).
- All spike scripts are in `scripts/spikes/view-filters/`.

---

## Constraints

- Use existing `automation/api_client.py` for all API calls. Do not reach for `requests` directly.
- No new package dependencies.
- All metadata mutations must be reversible.
- No edits to application source outside `scripts/spikes/`.
- Do not modify `program_engine`, parsers, managers, or any production code path.
- Diagnostic scripts must be Python (the `sqlite3` CLI is not installed on Doug's machine; if any local DB inspection is needed, use the `sqlite3` Python module).

---

## Next Step (after this spike)

- **If verdict is Feasible:** Doug authors `CLAUDE-CODE-PROMPT-view-filters-B-yaml-schema.md` to design the YAML category and schema for view filters.
- **If verdict is Partially feasible:** Doug and Claude review the report together to scope what subset to support; new prompt follows.
- **If verdict is Not feasible:** Update existing `NOT_SUPPORTED` documentation to reflect exactly what was tried and why it doesn't work; revisit when the platform's API surface changes.
