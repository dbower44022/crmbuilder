# PI-116 — Server-side relationship query-filter contract (extension surface)

**Status:** Design spec (Draft). Produced by WTK-060 (api area), Design phase of WSK-042 under PI-116, PRJ-016 "Improved link UI."
**Anchors:** PI-116 (link-panel in-panel search/filter), PRJ-016 (large link counts), WSK-042 (Design phase), WTK-059 (sibling UI design — client-side filter), WTK-060 (this task).
**Scope:** API-area design only. Specifies *whether and how* the relationship/link-listing endpoint should support server-side query filtering so panels with very large link counts can filter beyond the locally loaded rows. No code is written here.

---

## 1. Problem and decomposition context

PI-116 adds an in-panel search/filter to relationship (link) panels so a user can type to narrow a long list of linked records to the matches instead of scrolling. PRJ-016's core problem is objects that carry **large numbers of links**.

The PI was decomposed into two Design tasks:

- **WTK-059 (ui):** the in-panel filter *box* — placement, debounce, fields matched, empty state, clear control — filtering **client-side over the already-loaded link rows**. This is the explicit minimum per PI-116.
- **WTK-060 (api, this spec):** the **server-side** query-filter extension PI-116 left open at decomposition — needed only when the loaded-rows assumption breaks, i.e. when a record's link count is large enough that the panel does not (or should not) load every edge before filtering.

This document settles that open question: it specifies the request contract, the pagination interaction, the threshold/fallback rule that decides client-side vs server-side filtering, the verification criteria, and a recommendation on in-scope vs deferred.

## 2. The endpoint as it exists today

Link panels in the v2 desktop app are fed by the references repository through the FastAPI surface. The relevant facts (verified against source, not assumed):

- The link panel for one record loads via **`GET /references/touching/{entity_type}/{entity_id}`**
  (`api/routers/references.py` → `references.list_touching`). It returns
  `{"as_source": [...], "as_target": [...]}` inside the standard `{data, meta, errors}` envelope.
- Each row is the reference tuple (`source_type`, `source_id`, `relationship`, `target_type`, `target_id`, `id`, `reference_identifier`) **plus an `other_summary` block** for the far-side record, produced by `access/entity_summary.summarize`. `other_summary` carries the far record's **title, status, created, updated** (column map in `_SPECS`).
- `list_touching` today is **unbounded and unfiltered**: it selects every edge where the record is either source or target, enriches each with `summarize` (one lookup per edge — the documented N+1), and returns all of them. There is no `limit`, no `offset`, no text filter.
- Sibling list endpoints already establish the house pagination/search idioms this design reuses:
  - `commits`/`sessions` routers: `limit: int | None = None`, `offset: int = 0`, applied as `.offset(...).limit(...)` in the repository (`repositories/commits.py`).
  - `catalog` router: free-text search as `q: str = Query(..., min_length=1)`, `limit: int = Query(10, ge=1, le=50)`.
  - The envelope helper `ok(data, **meta)` lets any endpoint attach pagination metadata under `meta`.

The "match against the far record" semantics already exist: the client-side filter (WTK-059) matches the same `other_summary.title` (and identifier) that the user sees in the grid. The server-side contract must filter on the **same fields** so client→server is a transparent escalation, not a behavior change.

## 3. Request contract (server-side filter)

### 3.1 Where the parameters live

Extend the existing link-listing endpoint rather than add a new one — the panel already calls it, and the extension must be backward compatible (no params → today's behavior exactly).

```
GET /references/touching/{entity_type}/{entity_id}
        ?q=<text>            # optional free-text filter, min_length 1 when present
        &limit=<int>         # optional page size, 1..200, default unset (= all, legacy)
        &offset=<int>        # optional page start, >=0, default 0
        &direction=<enum>    # optional: both (default) | as_source | as_target
```

Parameter rules, matching house conventions:

| Param | Type / bound | Default | Meaning |
|---|---|---|---|
| `q` | `str`, `min_length=1` when supplied | unset | Case-insensitive substring match (see §3.2). Absent → no text filter. |
| `limit` | `int`, `1 <= limit <= 200` | unset → unbounded (legacy) | Max rows returned **after** filtering, per direction bucket (see §4). |
| `offset` | `int`, `offset >= 0` | `0` | Rows skipped after filtering, per direction bucket. |
| `direction` | enum `both \| as_source \| as_target` | `both` | Lets the panel page one side independently; `both` preserves today's two-bucket payload. |

`limit`/`offset`/`q`/`direction` all unset reproduces the current response byte-for-byte. This is the backward-compatibility contract and the first verification criterion (§6).

### 3.2 Match semantics for `q`

`q` matches **case-insensitively** as a substring against, for each candidate edge, the **far-side** record's:

1. `other_summary.title`
2. the far-side `identifier` (`source_id`/`target_id` depending on direction)

Match is the logical OR of (1) and (2). Rationale: these are exactly the two columns the link grid renders and the WTK-059 client-side filter matches, so the result set is identical whether filtering happened in the browser or the DB. Status and timestamps are **not** matched (they are not free-text the user types to find a record); a later iteration may add structured `status=` filtering, called out as a non-goal in §7.

Implementation note for the build phase (not prescriptive of code here): the far-side title lives on the far record's table, not on `refs`. A correct server-side `q` therefore requires either (a) per-far-type joins, or (b) an `EXISTS`/correlated lookup per entity type, because `refs` alone has only identifiers and types. The simplest correct shape mirrors `summarize`'s existing per-type column map (`_SPECS`): filter is "edge whose far `identifier` ILIKE %q% OR whose far record's title-column ILIKE %q%." This is the single most important downstream-implementation constraint and is the main reason server-side filtering is non-trivial (see §5 recommendation).

### 3.3 Ordering

Filtering must not change ordering relative to today, or paging is unstable. Preserve `list_touching`'s current implicit order within each bucket (insertion/`id` order) made explicit as an `ORDER BY` so `offset`/`limit` are deterministic. Stable, total order is a hard requirement whenever `limit` is supplied.

## 4. Pagination interaction

- The response keeps its **two-bucket shape** (`as_source`, `as_target`). `limit`/`offset` apply **independently within each requested bucket**, so a record that is heavily linked as a target but lightly as a source pages each side on its own. When `direction != both`, only the named bucket is returned (the other is `[]`).
- `q` is applied **before** `limit`/`offset`: you page the *filtered* set, not the raw set. This is what "filter beyond the locally loaded rows" means — the server narrows first, then hands back a page of matches.
- **`meta` carries the counts** the panel needs to render paging and the "showing N of M" affordance, attached via `ok(data, **meta)`:

  ```json
  {
    "data": { "as_source": [...], "as_target": [...] },
    "meta": {
      "as_source": { "total": 1240, "filtered": 37, "offset": 0, "limit": 50, "returned": 37 },
      "as_target": { "total": 3,    "filtered": 3,  "offset": 0, "limit": 50, "returned": 3 },
      "q": "acme"
    },
    "errors": null
  }
  ```

  - `total` = edges in the bucket before `q`.
  - `filtered` = edges in the bucket after `q` (== `total` when `q` absent).
  - `returned` = rows actually in this page (`<= limit`).

  `total` and `filtered` are what let the UI decide whether more matches exist beyond the page and whether to keep the server in the loop (§5).
- `other_summary` enrichment runs **only on the returned page**, not the whole filtered set. This is the performance win that justifies the extension: today `list_touching` runs the N+1 `summarize` across *every* touching edge; the paginated path runs it across at most `limit` rows per bucket.

## 5. Threshold / fallback rule — client-side vs server-side

The two filter implementations are not either/or per deployment; they are a **per-panel escalation** keyed on the record's link count. The rule:

1. **Load step.** When a link panel opens, request the first page with a bounded `limit` equal to the **client-cache ceiling `C`** (recommended `C = 200`, matching the endpoint's `limit` max) and no `q`. Read `meta.<bucket>.total`.

2. **Client-side regime (the common case).** If `total <= C` for the bucket, **every** edge for that bucket is already loaded. The WTK-059 client-side filter operates over the loaded rows and the server is never consulted again for filtering. Typing is instant, debounce is purely cosmetic, and `q` is *not* sent. This is the regime PI-116's minimum targets and covers essentially all current governance records.

3. **Server-side regime (the large-link case).** If `total > C` for the bucket, the panel has **not** loaded every edge, so a client-only filter would silently miss matches outside the loaded window. The panel switches that bucket to server-side: the debounced filter input now issues `GET .../touching/...?q=<text>&direction=<bucket>&limit=C&offset=0`, and the grid renders the returned page plus a "showing `returned` of `filtered` matches" indicator from `meta`. Paging controls walk `offset` in steps of `C`.

4. **Boundary stability.** The decision is made **per bucket per panel-open** from `total`, not re-evaluated on every keystroke, so a panel cannot flip regimes mid-typing. `C` is a single named constant so the UI and any tests share one threshold.

5. **Fallback / degradation.** If a server-side `q` request fails (network/API error), the panel falls back to filtering the already-loaded page client-side and surfaces a non-blocking "showing matches in loaded rows only" notice — never a hard error, consistent with the app's "buttons are never disabled, explain instead" posture. This keeps the feature usable when the API is mid-reconnect.

This rule is the crux of the WTK-060/WTK-059 split: WTK-059 owns regime 2 unconditionally; this spec's server contract only engages in regime 3. The threshold `C` is the contract between them.

## 6. Verification criteria

A build that implements this contract is correct iff:

1. **Backward compatibility.** `GET /references/touching/{type}/{id}` with no query params returns a payload byte-identical to the pre-change endpoint (same rows, same order, same `other_summary`), and `meta` is additive (absent-or-ignored by existing clients).
2. **Filter correctness.** With `q=<substr>`, every returned edge's far-side title or identifier contains `<substr>` (case-insensitive), and no edge that matches is omitted within the requested page window. A record linked beyond the client cache (`total > C`) returns a match that a client-only filter would have missed — the defining "filter beyond loaded rows" test.
3. **Pagination correctness.** For a bucket with `filtered = F`, walking `offset` 0, `C`, `2C`, … with fixed `limit = C` yields each matching edge exactly once, in stable order, with no gaps or repeats; `meta.<bucket>.filtered == F` on every page.
4. **Bucket independence.** `direction=as_source` returns only source-side edges with `as_target == []`; `direction=as_target` the mirror; `both` returns the legacy two-bucket shape. `limit`/`offset` applied to one bucket do not perturb the other.
5. **Enrichment scope.** `summarize` is invoked at most `returned` times per bucket (verify by query count / spy), not `total` times — i.e. enrichment is on the page, not the full set.
6. **Threshold behavior (cross-area, with WTK-059).** With `total <= C` no `q` request is sent on keystrokes (client-side regime); with `total > C` a debounced `q` request is sent and its results render with the "N of M" indicator (server-side regime). A forced server error degrades to loaded-rows filtering with a notice, not a failure.
7. **Validation bounds.** `limit` outside `1..200`, `offset < 0`, or empty `q` are rejected as 422 (FastAPI `Query` bounds), matching the catalog/commits validation idiom.

## 7. Non-goals (explicitly out of this contract)

- Structured/field-scoped filtering (`status=`, date ranges, relationship-kind facets) beyond the single free-text `q`. The endpoint already filters by `relationship_kind` on the flat `GET /references`; folding that into `touching` is a separate, additive iteration.
- Full-text ranking / relevance scoring — `q` is a deterministic substring match, not search ranking.
- Changing the two-bucket (`as_source`/`as_target`) response shape or the `other_summary` schema.
- Cursor/keyset pagination — `offset`/`limit` suffices at the link counts in play and matches every other paged endpoint in the API.

## 8. Recommendation — in-scope vs deferred

**Recommend: ship the client-side filter (WTK-059) now; DEFER the server-side implementation, and adopt this contract as the agreed interface for when it lands.**

Reasoning:

- **The minimum already solves the stated problem for current data.** Governance records' link counts are well under any reasonable `C` (200). In the client-side regime the server-side path is never exercised, so building it now delivers no user-visible value against today's DB.
- **The server-side path carries real implementation cost** concentrated in §3.2: `q` must match the far record's *title*, which lives on per-type tables, so a correct implementation needs the same per-type column map `summarize` uses, expressed as joins/`EXISTS` across ~20 entity types and rendered for both SQLite and Postgres (the dual-dialect constraint already live in the codebase). That is a non-trivial build, not a one-line `WHERE`.
- **Deferring is safe because the contract is forward-compatible.** WTK-059 is specified against the threshold `C` and the `meta.total` signal defined here, so the day a record legitimately exceeds `C`, the server path can be implemented behind the *same* request contract with **no UI change** — the panel already knows how to escalate. Nothing built now has to be unwound.
- **Trigger to pull it in-scope:** the first engagement (e.g. a populated CBM/CRMBUILDER record, or a methodology entity with hundreds of references) where a single bucket's `total` exceeds `C` in practice. At that point this spec is the build ticket: §3–§4 are the contract, §6 is the acceptance suite.

**Net:** WTK-060's deliverable is this settled contract. In-scope for PI-116: client-side filter (WTK-059) + this design as the documented extension surface. Deferred: the server-side `q` implementation, scoped and ready to lift directly from §3–§6 when a real large-link record appears.
