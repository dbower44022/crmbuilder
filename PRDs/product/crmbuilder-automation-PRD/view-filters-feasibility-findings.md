# View Filters Feasibility Spike — Findings

## Revision Control

| Field | Value |
| --- | --- |
| Document | View Filters Feasibility Spike — Findings |
| Series | view-filters |
| Version | 0.2 |
| Last Updated | 05-04-26 19:55 |
| Author | Doug Bower (executed by Claude Code) |
| Status | Final, awaiting Doug's review |

## Change Log

| Version | Date | Notes |
| --- | --- | --- |
| 0.1 | 05-04-26 13:45 | Initial findings — verdict Not feasible (covered selectDefs/clientDefs metadata path only). |
| 0.2 | 05-04-26 19:55 | Doug surfaced the `PUT /Preferences/{userId}` write path observed in the admin-UI network log. Verdict revised to Partially feasible after hands-on verification. Adds Task 9 (Preferences write path), reframes the three filter mechanisms, and rewrites recommendations accordingly. |

---

## Verdict

**Partially feasible.** Two distinct filter mechanisms with different REST surfaces:

| Mechanism | Stored where | REST write path? | Visibility |
| --- | --- | --- | --- |
| Admin-defined primary / boolean filters | `selectDefs.{Entity}.filterDefs` and `clientDefs.{Entity}.filterList` (metadata) | **No** — verified against 14 payload-shape variants, all 404/405 | All users on the instance |
| Per-user preset filters (saved searches) | `Preferences.{userId}.presetFilters.{Entity}` (record) | **Yes** — `PUT /api/v1/Preferences/{userId}` returns 200 and the entries round-trip on subsequent GET | One user at a time |
| Report Filters (Advanced Pack) | `ReportFilter` records | Yes — already wired in `EspoAdminClient` | Configurable; requires Advanced Pack license |

The original spike prompt focused on the first row only and treated all three under one "view filter" umbrella. The hands-on evidence shows they are genuinely different features with different APIs and different scopes; pretending they are one feature would produce a YAML schema that promises something it cannot deliver. Doug's recommendation in the prompt — to revisit the existing `NOT_SUPPORTED` short-circuit — turns out to be partially correct: the short-circuit is right about admin-defined filters but blocks per-user preset filters that *are* writable.

---

## Test Setup

| Item | Value |
| --- | --- |
| Instance | `https://crm-test.clevelandbusinessmentors.org/` (CBM Hosted Test, default in `cbm-client.db`) |
| EspoCRM auth | basic, admin/cbm-crm-test |
| Entity | `Account` |
| Discriminator field | `cAccountType` (custom **multiEnum**, not enum) |
| Enum values | `Client`, `Partner`, `Donor/Sponsor` |
| Admin user id | `69f8a18e429456e87` (single user on this dev instance) |
| API client | `espo_impl.core.api_client.EspoAdminClient` (the existing client; the prompt's reference to `automation/api_client.py` is a stale path — the actual location per `CLAUDE.md` is `espo_impl/core/api_client.py`) |

> **Field-type discovery during baseline.** `cAccountType` is `multiEnum`, so any *server-side* where clause must use `arrayAnyOf` (verified empirically: `arrayAnyOf` matches a created test record, `equals` would not). The *client-side preset-filter* shape that the UI saves uses search-manager types (`anyOf`, `in`, etc.) — those are translated to where clauses by the browser when the user clicks a filter. The translation is shape- and type-sensitive; the YAML emitter must know the field's real type to emit the right pair.

---

## Path 1 — Admin-defined Filters (`selectDefs` / `clientDefs`)

### Evidence

Eight payload-shape variants for primary filters, six for boolean filters. Full request/response bodies preserved in `scripts/spikes/view-filters/task{2,3}-attempts.jsonl`.

#### Primary filters (Task 2)

| # | Method | URL | Payload top-level | Status |
| --- | --- | --- | --- | --- |
| 1 | PUT | `/api/v1/Metadata` | `{selectDefs, clientDefs}` (arrayAnyOf) | **405** Method Not Allowed |
| 2 | POST | `/api/v1/Metadata` | same | **404** Not Found |
| 3 | PATCH | `/api/v1/Metadata` | same | **405** |
| 4 | PUT | `/api/v1/Metadata?key=selectDefs.Account` | `{filterDefs}` | **405** |
| 5 | PUT | `/api/v1/Metadata/selectDefs/Account` | `{filterDefs}` | **405** |
| 6 | PUT | `/api/v1/Metadata` | `{selectDefs, clientDefs}` (equals) | **405** |
| 7 | PUT | `/api/v1/Admin/metadata` | `{selectDefs, clientDefs}` | **404** |
| 8 | POST | `/api/v1/Admin/metadata` | same | **405** |

#### Boolean filters (Task 3)

| # | Method | URL | Payload top-level | Status |
| --- | --- | --- | --- | --- |
| 1 | PUT | `/api/v1/Metadata` | `{selectDefs, clientDefs}` (boolFilters) | **405** |
| 2 | POST | `/api/v1/Metadata` | same | **404** |
| 3 | PATCH | `/api/v1/Metadata` | same | **405** |
| 4 | PUT | `/api/v1/Metadata?key=selectDefs.Account.boolFilters` | `{boolFilters}` | **405** |
| 5 | PUT | `/api/v1/Metadata/selectDefs/Account/boolFilters` | bare block | **404** |
| 6 | POST | `/api/v1/Admin/Action/clearCache` | (none) | **404** |

Every 404/405 response was an HTML error page (`<!doctype html>...405 Method Not Allowed</title>...`), not a JSON error envelope — confirming the request was rejected by the framework router before reaching any EspoCRM application code. There is no "right" payload shape that would unlock the route.

After every write attempt, `selectDefs.Account` and `clientDefs.Account` were re-fetched and verified byte-identical to the captured baseline (`task8_cleanup.py`).

### Verdict for Path 1: **Not feasible.**

---

## Path 2 — Per-user Preset Filters (`Preferences.presetFilters`)

### How the UI uses this path

When a user clicks "Save Filter" in a list view, the EspoCRM frontend captures the current search state, generates a short hex id (e.g. `f857472`), and PUTs the user's full Preferences record with the new entry appended to `presetFilters.{Entity}`. The browser then re-applies that filter on subsequent list-view loads by translating it into where-clause params on the GET request.

This means preset filters are:
- **Per-user state**, not system-wide.
- **Persisted server-side** in the `Preferences` record.
- **Applied client-side** by the browser, not resolved by a `presetName=` URL parameter on the search API.

### Evidence (Task 9)

Captured in `scripts/spikes/view-filters/task9-attempts.jsonl`. Sequence:

1. **Baseline GET** `/api/v1/Preferences/69f8a18e429456e87` — HTTP 200. Pre-existing `presetFilters.Account = [{id:"f857472",...}, {id:"f416649",...}]` (two filters Doug had created via the UI before the spike).
2. **Append three Account filters for `cAccountType`** with ids `886d748`, `336646f`, `9d41bb8` covering values `Client`, `Partner`, `Donor/Sponsor`. PUT same endpoint with `{"presetFilters": {...extended...}}` — **HTTP 200**.
3. **Verify GET** — all three spike ids present alongside the originals; structure intact.
4. **Functional probe** — see next section.
5. **Restore PUT** with the original `presetFilters` payload — **HTTP 200**. Final GET shows zero spike artifacts.

The PUT payload format that worked (the `data.{field}` shape mirrors what the EspoCRM search panel emits for a multiEnum selection):

```json
{
  "presetFilters": {
    "Account": [
      {"id": "886d748", "name": "886d748", "label": "Spike: Client",
       "data": {"cAccountType": {"type": "anyOf", "value": ["Client"],
                                  "data": {"type": "anyOf", "valueList": ["Client"]}}},
       "primary": null}
    ]
  }
}
```

The `data.cAccountType.type` is the *search-form view* type (`anyOf` for multiEnum); the inner `data.type`/`valueList` is the *where-builder hint*. The browser uses these together to render the search panel and emit the correct server query.

### Functional behaviour

| Probe | Result |
| --- | --- |
| `GET /Account?primaryFilter={presetId}` | **HTTP 400.** Preset ids are not primary-filter names. Confirms preset filters and primary filters are different mechanisms. |
| `GET /Account?presetName={presetId}` | **HTTP 200, total: 0.** The parameter is accepted but doesn't resolve preset-filter ids; it expects names registered in `selectDefs.{Entity}.filterDefs` (which we already established is read-only). |
| `GET /Account?where[0][type]=arrayAnyOf&where[0][attribute]=cAccountType&where[0][value][]=Client` (with one matching test record temporarily created) | **HTTP 200, total: 1.** Confirmed the underlying *server-side* shape that the browser would emit for this preset filter does correctly narrow records when used directly. |
| `GET /Account?where[0][type]=anyOf&...` (search-manager type used directly as where type) | **HTTP 400.** Confirms the inner-vs-outer type distinction: `anyOf` is search-form-only, `arrayAnyOf` is the where-clause type. The translation must be done by whatever code mirrors the UI behavior. |

### Distribution / visibility limitations

- **Preferences are per-user.** Writing preset filters to `admin`'s preferences only affects what `admin` sees. Other users do not inherit them.
- **There is no system-wide default for new users on this instance.** `app.preferences` and `app.user` metadata keys both return null; the `Settings` record has no `presetFilters`-related key (verified empirically in this spike).
- **Cross-user PUT is untested on this instance** because there is only one user (`admin`). Conceptually, an authenticated admin should be able to PUT `/Preferences/{otherUserId}` for any user, but this would require either looping over users and merging with each user's existing custom filters (preserving their personal saved searches) or overwriting them (destructive). Neither approach is appealing for a deploy pipeline.
- **Idempotence is not built in.** Each entry is identified by a generated id, and there is no `name`-based "upsert" semantic. A naïve re-run of a "create these N filters" deploy step would produce duplicates. A working implementation would need to compare-by-label (since label is the only operator-meaningful key) and do an in-place merge.

### Verdict for Path 2: **Feasible for the admin user only, with significant caveats for any wider rollout.**

---

## Path 3 — Report Filters (Advanced Pack)

Already wired in `EspoAdminClient.list_report_filters` / `create_report_filter` / `delete_report_filter` (`espo_impl/core/api_client.py:327–374`). On instances with Advanced Pack installed, these create/delete filter records that admin can expose in the UI.

`GET /api/v1/ReportFilter?...` returns HTTP 404 on the CBM dev instance — Advanced Pack is **not installed there**. So even this alternative is unavailable on this specific environment without a license change. Per-customer licensing decision.

### Verdict for Path 3: **Feasible on instances with Advanced Pack only. Not available on CBM dev today.**

---

## Edge Cases Revisited

| Case | Outcome |
| --- | --- |
| Slash in enum value (`Donor/Sponsor`) | Preset filter with literal slashed value PUT-ed and round-tripped without issue. The slash survives JSON serialization in both the `value` and the `valueList` arrays. |
| Cache behavior | Preset filters take effect on the next list-view load with no rebuild required. The metadata cache rebuild (`POST /Admin/rebuild`) is irrelevant to the Preferences path. |
| Custom-field discriminator (`c` prefix on `cAccountType`) | No special handling required — the field name is used as-is in `data.cAccountType`. |
| Order of operations (filterList before/after filterDefs) | N/A for Preferences path (single PUT). For the metadata path, untested because no write succeeded. |
| Idempotence | **Not built in.** Re-running a "create these filters" PUT will duplicate them unless the implementation diffs by label (or by some operator-meaningful key) and merges in place. |
| Field-type misalignment (`equals` on multiEnum) | Confirmed structurally: `arrayAnyOf` matches; `anyOf` as a where-clause type returns HTTP 400. The dual structure (search-form type ≠ where-clause type) is a real schema-design constraint. |
| Cross-user PUT | Untested — only one user on the dev instance. |

---

## Constraints Discovered

1. **`/api/v1/Metadata` is GET-only at the framework router.** All write attempts return HTML 404/405 pages, never reaching application code.
2. **`PUT /api/v1/Preferences/{userId}` is writable for the authenticated user.** Returns the full updated Preferences record on success.
3. **No system-wide default exists for new-user preset filters.** Neither Settings nor `app.preferences`/`app.user` metadata expose a way to seed new users with a starter preset-filter set.
4. **Preset filters are client-side state.** The `presetName=` URL parameter expects names registered in `selectDefs.{Entity}.filterDefs` (which is read-only via REST), not preset-filter ids from preferences. There is no server-side filter-by-id mechanism for preset filters.
5. **Preset-filter shape has dual structure.** Outer `data.{field}.type` is the search-form view type (`anyOf`, `in`, `startsWith`, …); inner `data.type/valueList` is the where-builder hint. The browser uses both to render the search panel and emit the correct server query.
6. **Field-type discipline matters.** `arrayAnyOf` ↔ multiEnum, `equals` ↔ enum (or text), etc. The YAML emitter must look up the field's type before choosing the where clause.

---

## Recommendations

### 1. Keep the existing `NOT_SUPPORTED` short-circuit for admin-defined filters

The configure pipeline's existing `saved_view_manager` short-circuit (and the parallel ones for duplicate checks and workflows) maps to the **selectDefs/clientDefs metadata path**, which is confirmed unwritable. **No change to that behavior is recommended.** The MANUAL CONFIGURATION REQUIRED block accurately reflects platform reality: an operator must touch the EspoCRM admin UI (or write JSON files on disk via SSH) to add admin-defined system filters that all users see.

### 2. Update `CLAUDE.md` to distinguish three filter mechanisms

The current language in `CLAUDE.md` under **Three features have no public REST API write path** lumps "saved views" together. After Doug accepts these findings, suggest amending:

> **Saved views — admin-defined system filters** (`selectDefs.filterDefs` / `clientDefs.filterList`) require disk-level edits to `custom/Espo/Custom/Resources/metadata/{select,client}Defs/{Entity}.json` plus cache rebuild. Verified read-only via REST against 14 payload-shape variants on 05-04-26 (`view-filters-feasibility-findings.md`).
>
> **Per-user preset filters** (`Preferences.{userId}.presetFilters`) *are* writable via REST (`PUT /api/v1/Preferences/{userId}`). They are per-user, applied client-side, and not currently emitted by the configure pipeline. A YAML capability is technically possible — see view-filters series — but adds operational complexity (per-user PUTs, no idempotence-by-name, destructive merge with users' personal saved searches). Out of scope for v1.

### 3. Decide between three options for a YAML capability

If Doug wants view filters in YAML, the realistic options are:

| Option | What it does | Trade-offs |
| --- | --- | --- |
| **A — Defer entirely** | Keep current MANUAL CONFIGURATION REQUIRED behavior; document the trade-off in operator-facing docs. | Zero engine work. Operators continue to do this in the EspoCRM admin UI. Best fit if filter authoring is a one-time post-deploy task per implementation. |
| **B — Admin-only preset filters** | Emit `PUT /Preferences/{adminUserId}` for filters declared in YAML. They show up only when admin uses the list views. | Small implementation. Useful for CRM Builder operators testing configuration during pilot. Doesn't help end users at all. |
| **C — Cross-user preset filters** | Loop through all users, GET each one's preferences, merge in the YAML-declared filters by label, PUT back. | Significantly more code and significantly more risk. Each run touches every user's personal saved-searches list. No clean idempotence story. Worst is silently overwriting a user's hand-edited filter. Not recommended for v1. |
| **D — SSH metadata file write** | Write `custom/Espo/Custom/Resources/metadata/{select,client}Defs/{Entity}.json` via SSH and rebuild cache. Filters become true admin-defined system filters that all users see. | Significant departure from the API-only model. Already gated on the per-instance SSH credential set used by the deployment layer. Cleanest filter semantics but biggest architecture change. |

**My recommendation:** Option A for now (no engine work, document the gap), revisit with Option D as part of a broader "metadata files via SSH" capability if/when other features (saved views proper, duplicate-check rules, workflow definitions) justify building that infrastructure.

If Doug wants Option B specifically (admin-only preset filters as a small win), that is the smallest viable engine change and could land as a single follow-on prompt — but it should not be confused with admin-defined system filters when documented.

### 4. Hold the YAML schema design

The original prompt deferred the schema-design prompt until a Feasible verdict. Verdict is mixed: the *admin-defined system filters* surface (which an operator most likely wants) is not feasible; the *per-user preset filters* surface is feasible but with caveats that change what the YAML category should look like. Schema design should follow the **Option A/B/C/D decision**, not lead it. Do not author `CLAUDE-CODE-PROMPT-view-filters-B-yaml-schema.md` until Doug picks an option.

---

## UI Verification Checklist (manual, for Doug)

The Preferences write path was confirmed at the API level. To close the loop on the *user-perceptible* behavior, Doug to manually verify:

- [ ] In a Brave/Chrome session logged in as `admin`, open the Account list view. Hard-refresh.
- [ ] Confirm Doug's two pre-existing test filters (`test filter`, `test 2`) still appear in the saved-searches dropdown and behave the same as before the spike — no residual spike artifacts.
- [ ] (Optional, if Doug wants to see the spike's filters in the UI) Re-run `task9_preferences_path.py`, then before it runs the restore step, open the Account list and confirm `Spike: Client`, `Spike: Partner`, `Spike: Donor/Sponsor` show in the saved-searches dropdown. Click each; confirm the filter panel re-renders with the right multi-enum selection.
- [ ] If the temporary `_spike_test_filters_account` test record was not cleaned up (it should have been; the script DELETEs it), search Account list for it and remove manually.

---

## Spike Artifacts

All artifacts live under `scripts/spikes/view-filters/`. Doug to decide whether to commit before closing the spike.

| File | Purpose |
| --- | --- |
| `_common.py` | Shared helpers — InstanceProfile loader (reads default `Instance` row from `cbm-client.db`), attempt logger, constants. |
| `task1_baseline.py` | Baseline `selectDefs.Account` and `clientDefs.Account` capture. |
| `task2_primary_filters.py` | Eight payload-shape variants for primary filters via metadata. |
| `task3_boolean_filters.py` | Six payload-shape variants for boolean filters via metadata. |
| `task8_cleanup.py` | Drift verification against the metadata baseline. |
| `task9_preferences_path.py` | Preferences write-path verification. PUTs three preset filters, GETs back, restores baseline. |
| `baseline-{select,client}Defs-Account.json` | Captured baseline metadata. |
| `task9-baseline-preferences.json` | Captured baseline of admin's full Preferences record. |
| `task{2,3,9}-attempts.jsonl` | One JSON record per attempted API call (full request and response). |
| `task{2,3}-post-*.json` | Post-attempt round-trip captures. |
| `task9-after-put-preferences.json` | Snapshot of preferences immediately after the spike PUT (before restore). |
