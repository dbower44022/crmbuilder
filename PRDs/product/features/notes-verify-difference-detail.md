# Note — Configure verify/preview difference detail (runtime verification)

**Date:** 06-10-26
**Commits:** `a3e0732` (verify/preview detail), `704f68c` (Configure tab path + Open in Editor)
**Feature:** The Configure tab's Verify and preview now spell out *why* a YAML
field and the deployed field differ — field-type differences and enum-option
missing/extra values — instead of listing only the property names.

## What changed

- `espo_impl/core/comparator.py` — `ComparisonResult` carries a structured
  `detailed: list[FieldDifference]` (property, expected, actual, message) plus a
  `detail_text` helper. Existing `differences` / `matches` / `type_conflict`
  are unchanged.
- `espo_impl/core/field_manager.py` — `verify()` and `preview()` emit a
  per-property bullet under each DIFFERS / TYPE CONFLICT / UPDATE line and carry
  the detail in `FieldResult.error`, so it streams to the Configure output panel
  and flows into the `.log` / `.json` reports.

Message forms:
- type: `type differs — YAML expects 'enum' but deployed is 'multiEnum'`
- options: `options differ — missing from deployed: [X]; extra in deployed: [Y]`
  (`missing from deployed` = in YAML, not deployed; `extra in deployed` =
  deployed, not in YAML)
- scalar: `label differs — YAML expects 'New' but deployed has 'Old'`

## Runtime verification — PASS

Drove the exact orchestration the Configure worker builds
(`InstanceProfile` → `EspoAdminClient` → `FieldComparator` →
`FieldManager(...).verify()/.preview()`, mirroring `configure_progress.py:199`
and `run_worker.py:161-171`) against the **live CBM test CRM**
(`crm-test.clevelandbusinessmentors.org`, instance #1 in
`automation/data/cbm-client.db`). Target: the real deployed
`Contact.cContactType` (`multiEnum`, options `['', 'Client', 'Mentor',
'Partner', 'Administrator', 'Presenter', 'Donor', 'Member']`).

Captured output-panel lines (the `output_fn` slot appends these verbatim):

```
[VERIFY]  Contact.contactType ... DIFFERS (options)
            • options differ — missing from deployed: [Volunteer]; extra in deployed: [Donor]

[VERIFY]  Contact.contactType ... TYPE CONFLICT
            • type differs — YAML expects 'enum' but deployed is 'multiEnum'

  Contact.contactType — UPDATE (options)              # preview path
      • options differ — missing from deployed: [Volunteer]; extra in deployed: [Donor]
```

Probes:
- Exact-match YAML (options identical to deployed) → `VERIFIED`, **no** bullet
  emitted (no false positives).
- `preview()` path produces the same detail and carries it in
  `FieldResult.error`.

Notes / caveats:
- Drove the real verify/preview code path against the live CRM with the
  identical client/comparator/manager construction the GUI worker uses; did
  **not** click through the Qt window under a display server. The output-panel
  slot appends these `(msg, color)` lines verbatim, so what a user sees is
  identical — only the literal pixel rendering was not exercised.
- `cContactType`'s deployed `label` returns `None` from the Metadata API (it
  lives in the translation system); the comparator correctly skips it, so label
  never showed a spurious diff.
