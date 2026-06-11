# PI-120 — Workstream Panel: render child Work Tasks as a grid (reuse the References grid) — UI Design

**Version:** 0.1
**Status:** Draft (design deliverable)
**Planning Item:** PI-120 — *Workstream panel: render child Work Tasks as a grid (like References), not just a count*
**Project:** PRJ-016 — *usability for objects that carry large numbers of links*
**Work Task:** WTK-075 (area: ui) / Workstream WSK-057 (Design)
**Builds on:** PI-116 (`pi-116-link-panel-search-filter-ui-design.md`) — debounced filter; PI-117 (`pi-117-link-panel-multicolumn-sort-grouping-ui-design.md`) — `MultiSortProxyModel` + `GroupingTreeModel` + `MultiSortHeaderView`; PI-118 (`pi-118-link-panel-inline-preview-ui-design.md`) — inline preview; PI-119 (`pi-119-link-panel-column-resize-ui-design.md`) — interactive column resize. All shipped, all carried by `references_section.py`.

## 1. Overview

### Purpose

On the v2 desktop **Workstreams** view panel, replace the dedicated *Work Tasks*
section — today a flat list of identifier-only navigable links — with an
**inline grid** that shows each child Work Task's *identifier, title, area,
status, and claim state*, reusing the grid the References panel already carries
(filter + multi-column sort/grouping + inline preview + drag-resize columns).
This is the PI-120 readability item in the PRJ-016 candidate set: a Workstream
that fans out to many Work Tasks should be scannable in place, the same way the
link panel made a record's references scannable.

### The scoping fact that makes this a real PI

The PI title says *"not just a count."* In the code at HEAD the Work Tasks
section is **not literally a count** — `WorkstreamsPanel._work_tasks_section`
(`panels/workstreams.py:214–233`) renders one rich-text `<a href>` `QLabel` per
inbound `work_task_belongs_to_workstream` edge, showing **only the identifier**.
So a reader sees `WTK-001`, `WTK-002`, … with no title, area, status, or claim
state — informationally that is "a count of links," which is exactly what the PI
calls out. The work is to lift that section to the same grid the References
panel uses, surfacing the five fields per row.

### The data fact that shapes the whole design

The grid the References panel uses is fed from the `other_summary` block the
access layer attaches to each edge (`references.list_touching` →
`entity_summary.summarize`). For a `work_task`, that summary carries **only**
`identifier`, `title`, `status`, `created_at`, `updated_at`
(`access/entity_summary.py:76` — `_Spec(models.WorkTask, work_task_identifier,
work_task_title, work_task_status, work_task_created_at, work_task_updated_at)`).
It does **not** carry `work_task_area` or claim state. Two of the five fields
PI-120 requires are therefore **not** in the references payload the panel
already fetches. This is the decisive constraint (§3.3): the panel must enrich
the rows by reading the actual Work Task records, in the worker thread, via the
client read methods that already exist — **not** by widening the edge summary
(that is the access area, not ui, and would change the payload for all 25
References-grid consumers).

### What this design changes (the delta)

1. **A contract seam in the grid widget** so the same grid implementation can
   render an arbitrary row/column set, with the References configuration as its
   built-in default — *no divergent fork* (§3.1, §3.2).
2. **A Work Task column model** (five columns) and **row builder** that join the
   authoritative child set (the membership edges) with the fetched Work Task
   records (for area + claim state) (§3.3, §3.4).
3. **The integration point** in `panels/workstreams.py`: `fetch_detail_extras`
   additionally loads the child Work Task records; `_work_tasks_section` returns
   the grid instead of the label list (§3.5).
4. **Strictly additive** — the References default path is byte-unchanged, so the
   25 existing usages and `test_context_menus` do not regress (§3.6, §5, §6).

Deliverable is **the spec/design only, not code.**

## 2. Constraints (hard)

- **C1 — no divergent fork.** Exactly one grid implementation may exist. The
  Work Task grid and the References grid must be two *configurations* of the
  same code, not a copied-and-edited sibling. Any change adopted to satisfy
  PI-120 is made in the shared grid, never in a clone.
- **C2 — strictly additive; References usages do not regress.** All 25 current
  `ReferencesSection(...)` call sites (`grep -rn "ReferencesSection(" src` —
  charter, status, decisions, planning_items, risks, domains, entities, field,
  persona, processes, requirements, test_spec, topics, sessions, conversations,
  projects, commits, reference_books, work_tickets, work_tasks, close_out_payloads,
  deposit_events, crm_candidates, manual_config, **and the workstream-level refs
  block in `workstreams.py:190` itself**) must render identically. The References
  default contract must be byte-for-byte the current behavior.
- **C3 — `test_context_menus` green, unchanged.** `WorkstreamsPanel._build_context_menu`
  (`panels/workstreams.py:260–271`) and the grid's per-row right-click menu are
  not touched in a way that changes their label sets.
- **C4 — all five fields per row.** Each child Work Task row renders
  *identifier, title, area, status, claim state* — including the two
  (area, claim state) absent from the edge summary.
- **C5 — preserve the grid feature stack.** The new grid keeps PI-116 debounced
  filter, PI-117 multi-column sort + grouping, PI-118 inline preview, and PI-119
  drag-resize, because it *is* the same grid — not a stripped re-implementation.
- **C6 — read-only.** Work Tasks are authored by the decomposer / agents
  (the panel exposes no New/Edit/Delete; `panels/workstreams.py:69`). The Work
  Task grid is navigable (double-click / "Go to") but has **no** Add/Delete
  affordance — `set_add_enabled(False)`, and the contract supplies no row
  mutation actions.
- **C7 — worker-thread fetch.** Any extra network read to enrich rows happens in
  `fetch_detail_extras` (already a worker-thread hook), never on the GUI thread
  in `render_detail`.

## 3. Design decisions

### 3.1 Reuse-vs-extract: **parameterize the existing grid behind a contract seam** (recommended), do not extract-and-rewrite now

The grid in `references_section.py` is one `QWidget` (`ReferencesSection`) wired
to references through a small, identifiable set of references-specific seams:

| Seam (HEAD) | What is references-specific |
|---|---|
| `_COLUMNS` (`references_section.py:101–110`) | 8 columns: Direction, Relationship, Identifier, Type, Title, Status, Created, Updated |
| `_flatten` (`references_section.py:269–301`) | turns an `{as_target, as_source}` edge payload into row dicts |
| date columns set `("created","updated")` (`:143`, `:222`) | which columns format via `_fmt_dt` |
| nav/bookkeeping keys `other_type` / `other_id` / `ref` (`:296–298`) | double-click + "Go to" + Delete target |
| `_GROUP_OPTIONS` (`references_section.py:125–132`) | group-by choices (Relationship/Type/Status/Direction/Created-by-day) |
| preview extractor lambda (`references_section.py:446–451`) | `(other_type, other_id, title, kind_label)` |
| row-menu factory `_build_row_menu` (`references_section.py:712–735`) | Delete reference + "Go to" |
| the Add-reference button + dialogs (`references_section.py:650–663`, `741–774`) | references-only write path |

Everything else — `_RefsModel` (generic over `_COLUMNS` + row dicts already),
`MultiSortProxyModel`, `MultiSortHeaderView`, the `QStackedWidget` table/tree,
`GroupingTreeModel`, `LinkFilterInput`, `PreviewController`, `_fit_height`, the
column-resize and grouping machinery — is **generic** and carries the entire
PI-116…119 feature stack. The references-ness is concentrated in the eight seams
above; the 90% that is the actual grid is already type-agnostic.

**Decision (recommended): introduce a single internal "grid contract" object
that names those eight seams, build the references contract as the widget's
*default* (preserving current behavior exactly), and add a thin Work Task
configuration that supplies a different contract.** Two configurations, one
implementation — which is precisely "no divergent fork" (C1) — and the
References default path is unchanged, which is "strictly additive" (C2).

**Why this over the two alternatives:**

- **vs. "extract a brand-new generic grid widget and rewrite `ReferencesSection`
  to compose it" (the full-extract option).** This is the cleaner *end-state*
  architecture (a neutral `RecordGridSection` core that both panels compose),
  and the contract seam below is deliberately shaped so it can become that core
  by a *pure rename* later. But doing the extraction *in this Work Task* means
  rewriting the internals of a 794-line widget that is on the detail pane of 25
  panels and is covered by five dedicated widget test files
  (`test_references_section*.py`, `test_linked_record_preview.py`). That is a
  large-blast-radius refactor to land a single read-only section on one panel —
  disproportionate, and at odds with "strictly additive." Recorded as the
  natural follow-on (§3.7), not built here.
- **vs. "fork the grid into a `WorkTaskGridSection` copy."** Explicitly forbidden
  by C1, and it would immediately diverge: the four PI-116…119 features and their
  future fixes would have to be maintained twice. Rejected outright.

**Shape of the contract (design intent, names illustrative).** A small value
object passed into the grid widget, with the references values as the default:

```text
GridContract:
  columns:        list[(header, row_key)]          # was module _COLUMNS
  datetime_keys:  set[str]                          # was the {"created","updated"} literal
  group_options:  list[(label, row_key)]            # was module _GROUP_OPTIONS
  navigate(row)   -> (entity_type, identifier) | None   # was (row["other_type"], row["other_id"])
  preview_fields(row) -> (type, id, title, subtitle) | None  # was the :446–451 lambda
  row_actions(row) -> list[(label, callback)]        # was _build_row_menu's Delete/Go-to
  add_action      -> optional ("Add …" handler) | None   # references-only; None for work tasks
```

The widget keeps its public surface intact: constructor signature, the
`navigate_requested(str, str)` and `references_changed()` signals, and
`set_add_enabled(bool)` are unchanged. References call sites construct the
widget exactly as today (no `GridContract` argument → built-in references
default). The Work Task section constructs it with a work-task contract — either
by passing the contract through a new **defaulted** keyword argument, or via a
thin subclass/factory (`WorkTaskGridSection`) that supplies the contract in its
constructor. Either expression satisfies C1/C2; the subclass form reads better
at the `workstreams.py` call site and is the suggested default.

> **Naming note.** If the contract seam lands, the class name `ReferencesSection`
> becomes slightly broader than its label. The spec deliberately does **not**
> rename it in this Work Task (a rename touches 25 imports and the test files for
> no functional gain). The follow-on extraction (§3.7) is where a neutral name
> (`RecordGridSection`) would be introduced.

### 3.2 The generic core needs exactly two parameterizations it does not have today

`_RefsModel` already reads `_COLUMNS` for headers, column count, and cell keys —
it is generic the moment `_COLUMNS` is supplied per-instance instead of read as a
module global. Two hardcodes must move into the contract:

1. **The column model** `_COLUMNS` → `contract.columns`. `_RefsModel.data`,
   `_RefsModel.headerData`, `_cell_display`, and `_rebuild_tree`'s `headers`
   all consume it; each must read the instance's columns. (`_cell_display` is a
   module function shared by the grouped tree — it gains the columns/date-keys as
   parameters or becomes a bound method.)
2. **The date-formatted column set** `("created","updated")` → `contract.datetime_keys`,
   read in `_RefsModel.data` (`:222`) and `_cell_display` (`:143`). For the Work
   Task contract this set is **empty** (none of the five fields is a timestamp;
   claim state is rendered as text — see §3.4).

The `_flatten` step becomes contract-supplied row construction: for references,
the existing edge-flattening; for work tasks, the row builder in §3.4. The
remainder of `_build` (filter row, model/proxy/header wiring, stacked
table/tree, preview install, height fit, add-button row) is **unchanged** and
runs identically for both contracts — which is how the PI-116…119 feature stack
comes along for free (C5).

### 3.3 Data sourcing — join the membership edges with fetched Work Task records (settled)

**Decision: the panel sources child Work Task rows by (a) reading the
authoritative child set from the inbound `work_task_belongs_to_workstream`
edges already in the references payload, and (b) fetching the corresponding
Work Task records for the fields the edge summary omits — in
`fetch_detail_extras`, on the worker thread.**

Rationale: the edge `other_summary` carries identifier/title/status but **not**
`work_task_area` or claim state (§1, *the data fact*). To render all five fields
(C4) the panel must read the records. The edges are still the source of truth
for *which* tasks belong (membership is an edge, not a field on the task), so the
build is a join: child set from edges, fields from records.

Two equivalent fetch strategies; the spec leaves the choice to the build session
as a cost detail, with a default:

- **Default — `list_work_tasks()` once, index by identifier, filter to the child
  set.** One network round-trip regardless of fan-out; the client method exists
  (`client.py:2704`). Best when a Workstream has several Work Tasks (the PI's
  motivating case).
- **Alternative — `get_work_task(id)` per child edge** (`client.py:2710`).
  Precise (fetches only the children) but N round-trips; acceptable only for
  small fan-out.

**Graceful degradation:** if a record fetch fails or a child id is missing from
the list, fall back to the edge summary's identifier/title/status for that row
and render area/claim state as the dash sentinel `—`. A missing field never
drops the row; the membership edge set defines the rows.

**Explicitly rejected:** widening `entity_summary.summarize` to add area + claim
state to the `work_task` summary. That is the **access** area, it changes the
edge payload for every consumer of `list_references_touching` (25 panels), and it
is out of scope for a ui Work Task. Keep the enrichment ui-local.

### 3.4 The Work Task column model (the five fields → grid contract)

The contract's `columns` for the Work Task grid, in display order:

| # | Header | row-dict key | Source field | Notes |
|---|---|---|---|---|
| 0 | Identifier | `identifier` | `work_task_identifier` | also the nav target id |
| 1 | Title | `title` | `work_task_title` | the Stretch column (slack absorber, mirrors References col "Title") |
| 2 | Area | `area` | `work_task_area` | **from the fetched record** (not the edge summary) |
| 3 | Status | `status` | `work_task_status` | lifecycle value (Ready/Claimed/In Progress/Complete/Blocked/Failed) |
| 4 | Claim state | `claim_state` | derived from `work_task_claimed_by` | **from the fetched record**; rendered text (§below) |

`datetime_keys = {}` (none of the five is a timestamp).

**Claim state rendering.** Derive a single display string from `work_task_claimed_by`
(+ optionally `work_task_claimed_at`): `claimed_by` set → `"Claimed · {who}"`;
unset → `"Unclaimed"`. This keeps the column to the five-field budget the WTK
specifies while making the agent-claim state legible at a glance, consistent with
the standalone Work Tasks panel which surfaces `claimed_by` as a first-class
field (`panels/work_tasks.py:70, 78, 119–121`). (A separate *Claimed at*
timestamp column is a possible sixth field; out of scope — the WTK names five.)

**Bookkeeping keys on each Work Task row** (so the generic nav/preview paths work
unchanged): `other_type = "work_task"`, `other_id = work_task_identifier`. No
`ref` key (no edge-delete path — read-only). The `contract.navigate(row)` returns
`("work_task", row["identifier"])`; `contract.preview_fields(row)` returns
`("work_task", identifier, title, area)` so the PI-118 preview card resolves the
far side via `get_work_task` exactly as it resolves any other linked record.

**Group-by options for the Work Task contract** (the PI-117 grouping combo):
`(none)`, **Area**, **Status**, **Claim state**. (References' Direction /
Relationship / Created-by-day options do not apply; Area is the natural primary
bucket for a phase's tasks.)

**Row right-click menu for the Work Task contract:** "Go to {identifier}" only
(navigates), plus optionally "Copy identifier" to match the standalone panels'
idiom. **No** "Delete reference" — these are not edges and are read-only (C6).
Because the menu is contract-supplied, this does not touch the References menu
path, so `test_context_menus` is unaffected (C3).

### 3.5 Integration point in `panels/workstreams.py` (read against HEAD)

Two localized edits; the workstream-level references block at the bottom of the
pane (`workstreams.py:189–197`) is **left untouched** — PI-120 only re-renders
the dedicated *Work Tasks* section.

**(a) `fetch_detail_extras` (`workstreams.py:102–110`)** — additionally load the
child Work Task records. Today it returns only `{"references": ...}`. Add the
child records under a new key, computed on the worker thread:

```text
# design intent (not final code)
def fetch_detail_extras(self, record):
    identifier = record.get("workstream_identifier")
    if not identifier:
        return {"references": {"as_source": [], "as_target": []}, "child_work_tasks": []}
    references = self._client.list_references_touching("workstream", identifier)
    child_ids = [e["source_id"] for e in references.get("as_target", [])
                 if e.get("relationship") == "work_task_belongs_to_workstream"]
    tasks_by_id = {t["work_task_identifier"]: t
                   for t in self._client.list_work_tasks()}          # §3.3 default strategy
    children = [tasks_by_id.get(cid, {"work_task_identifier": cid}) for cid in child_ids]
    return {"references": references, "child_work_tasks": children}
```

**(b) `_work_tasks_section` (`workstreams.py:214–233`)** — change its **body** to
build the five-field rows from `extras["child_work_tasks"]` and return the
contract-driven grid instead of the `QVBoxLayout` of `_link_or_dim` labels.
Signature changes from `_work_tasks_section(references)` to receive the child
records (or the whole `extras`); the **empty case is preserved** — when there are
no child tasks, render the existing `"No Work Tasks recorded."` dim label rather
than an empty grid. Wire the grid like the bottom refs block already does
(`workstreams.py:190–197`): `set_add_enabled(False)` and
`grid.navigate_requested.connect(self.navigate_requested)`. The call site at
`workstreams.py:163–164` passes the new argument.

`_link_or_dim` (`workstreams.py:235–247`) stays — it is still used for the parent
Planning Item link (`workstreams.py:158`). Only the Work-Tasks branch stops using
it.

### 3.6 Why this is strictly additive (C2) and `test_context_menus` is green (C3)

- The grid widget's **References default contract reproduces today's behavior
  byte-for-byte** — same `_COLUMNS`, same `_flatten`, same date keys, same nav
  keys, same group options, same preview extractor, same row menu, same Add
  button. The 25 References call sites pass no contract and are unchanged.
- `WorkstreamsPanel._build_context_menu` and the grid's **References** row-menu
  path are untouched. The Work Task row menu is a *separate* contract-supplied
  set, so the existing context-menu sweep (`test_context_menus.py`) — which never
  exercised the Work Task grid — keeps its exact assertions.
- The change to `panels/workstreams.py` is confined to the Work-Tasks section and
  the extras fetch; the workstream-level refs block, the master columns, the
  attention banner, and the identifier overrides are unchanged.

**One existing test legitimately changes (and that is not a regression of
References usages).** `test_workstreams_panel.test_detail_pane_renders_parent_pi_and_work_tasks`
(`tests/.../test_workstreams_panel.py:133–144`) asserts the child tasks render as
`<a href="work_task:WTK-001">` **labels**. Once the section is a grid, the child
tasks render as **grid rows**, not href labels, so this assertion must be updated
to read the grid's rows/model. That is an expected, scoped test update for the
section being redesigned — distinct from C2 (the *References* grid usages and
`test_context_menus`), which must not change. The build session updates this one
workstreams-panel test and adds a positive test that the grid renders all five
fields for each child (§5).

### 3.7 Follow-on (documented, not built): extract a neutral `RecordGridSection` core

The contract seam (§3.1) is deliberately the same boundary a future extraction
would use. The natural follow-on, when a second non-references grid consumer
appears (or as housekeeping), is a **pure refactor**: move the generic machinery
into a neutrally-named `RecordGridSection` widget that takes a `GridContract`,
and reduce `ReferencesSection` to `RecordGridSection` + the references contract.
That is a rename/move with no behavior change — explicitly **out of scope** for
PI-120, recorded here as the architectural end-state the seam points at.

## 4. Files touched

| File | Change | Why |
|---|---|---|
| `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py` | Introduce the `GridContract` seam (columns, datetime_keys, group_options, navigate, preview_fields, row_actions, add_action); make `_RefsModel`, `_cell_display`, `_rebuild_tree`, the preview extractor, and the row-menu read it; build the **references contract as the unchanged default**. Optionally add a thin `WorkTaskGridSection` configuration. (§3.1–3.2) | Single grid implementation, two configurations — no fork (C1), References default unchanged (C2). |
| `crmbuilder-v2/src/crmbuilder_v2/ui/panels/workstreams.py` | `fetch_detail_extras` also loads `child_work_tasks`; `_work_tasks_section` builds the five-field rows and returns the grid (empty case preserved). (§3.5) | Replace the identifier-only label list with the inline grid. |
| `tests/crmbuilder_v2/ui/test_workstreams_panel.py` | Update `test_detail_pane_renders_parent_pi_and_work_tasks` to assert grid rows (not href labels); add a test that each child row carries identifier+title+area+status+claim-state. (§3.6, §5) | The section's rendering changed; prove the five-field contract (C4). |
| `tests/crmbuilder_v2/ui/widgets/test_references_section.py` *(or a new sibling)* | Add a test that a non-references `GridContract` renders its own columns/rows/nav, and that the default (references) contract is byte-identical to today. | Guard the seam and C2. |

No change to `multi_sort_header.py`, `multi_sort_proxy.py`, `grouping_tree_model.py`,
`linked_record_preview.py`, `link_filter_input.py`, `panels/work_tasks.py`,
`panels/references.py`, or `access/entity_summary.py` (the access widening is
explicitly rejected, §3.3).

## 5. Verification approach

Offscreen Qt (`QT_QPA_PLATFORM=offscreen`), the established pattern for these
widget/panel tests. The build session asserts:

1. **Five fields per child row (C4).** Build `WorkstreamsPanel` over the existing
   `_handler`/`_TOUCHING_WSK001` fixture extended with `list_work_tasks`
   responses carrying `work_task_area` and `work_task_claimed_by`; render the
   detail pane; locate the Work Tasks grid; assert its model exposes columns
   *Identifier, Title, Area, Status, Claim state* and that for each child the row
   cells carry the identifier, title, area, status, and a derived claim-state
   string. (Tasks with `claimed_by` → `"Claimed · …"`; without → `"Unclaimed"`.)
2. **Navigation preserved.** Double-click / "Go to" on a Work Task row emits
   `navigate_requested("work_task", "WTK-00x")` (the grid's `navigate_requested`
   is connected to the panel's, `workstreams.py` wiring).
3. **Empty case preserved.** A Workstream with no `work_task_belongs_to_workstream`
   edges still shows `"No Work Tasks recorded."` and builds no grid.
4. **Grid feature stack present (C5).** On the Work Task grid, filter
   (`_on_filter_changed`) narrows rows, the group-by combo offers Area/Status/
   Claim state and switches to the tree, and the header is `Interactive` with the
   Title column `Stretch` (the PI-119 assertions) — confirming it is the same
   grid, not a re-implementation.
5. **References default unchanged (C2).** The existing `test_references_section*.py`
   suite passes unchanged; a focused assertion confirms the default-contract
   column headers are exactly Direction/Relationship/Identifier/Type/Title/
   Status/Created/Updated.
6. **Context menus not regressed (C3).** `tests/crmbuilder_v2/ui/test_context_menus.py`
   passes unchanged.

**Commands the build session runs:**

```bash
cd crmbuilder-v2
QT_QPA_PLATFORM=offscreen uv run pytest \
  ../tests/crmbuilder_v2/ui/test_workstreams_panel.py \
  ../tests/crmbuilder_v2/ui/widgets/test_references_section.py \
  ../tests/crmbuilder_v2/ui/widgets/test_references_section_sort_group.py \
  ../tests/crmbuilder_v2/ui/widgets/test_references_section_resize_wtk073.py \
  ../tests/crmbuilder_v2/ui/widgets/test_linked_record_preview.py \
  ../tests/crmbuilder_v2/ui/test_context_menus.py -q
uv run ruff check \
  src/crmbuilder_v2/ui/widgets/references_section.py \
  src/crmbuilder_v2/ui/panels/workstreams.py
```

## 6. Acceptance criteria

- **AC1** — The Workstream detail pane's *Work Tasks* section is an inline grid;
  each child Work Task is a row showing identifier, title, area, status, and
  claim state (C4).
- **AC2** — Area and claim state — absent from the edge summary — are sourced
  from the fetched Work Task records in `fetch_detail_extras` (worker thread),
  not by widening the access-layer summary (§3.3, C7).
- **AC3** — The grid is the *same* grid the References panel uses: filter, multi-
  column sort + grouping, inline preview, and drag-resize all work, with no forked
  copy of the grid (C1, C5).
- **AC4** — All 25 existing `ReferencesSection` usages render identically; the
  References default contract is byte-for-byte today's behavior (C2).
- **AC5** — `test_context_menus`, `test_references_section*`, and
  `test_linked_record_preview` pass unchanged (C2, C3).
- **AC6** — The Work Task grid is read-only: navigable (double-click / "Go to"),
  no Add/Delete affordance (C6).
- **AC7** — The empty case renders `"No Work Tasks recorded."` (preserved).
- **AC8** — The full-extract-and-rename refactor (§3.7) and a sixth *Claimed at*
  column (§3.4) are recorded as deliberate out-of-scope decisions with a
  documented path, not silent omissions.

## 7. Decisions log (for governance capture at build close)

- **D1** — Reuse via a **contract seam in the existing grid** (References contract
  as default) — one implementation, two configurations; **no fork** (§3.1, C1).
- **D2** — **Do not** extract/rewrite the grid into a new core widget in this Work
  Task; record the neutral `RecordGridSection` extraction as a pure-rename
  follow-on (§3.1, §3.7).
- **D3** — Work Task column model = Identifier, Title, Area, Status, Claim state;
  `datetime_keys` empty; Title is the Stretch column (§3.4, C4).
- **D4** — Source area + claim state from **fetched Work Task records** in
  `fetch_detail_extras`; **reject** widening `entity_summary` (access area)
  (§3.3, C7).
- **D5** — Child set = the inbound `work_task_belongs_to_workstream` edges (the
  membership source of truth), joined to records by identifier; graceful
  degradation to summary fields + `—` on a missing record (§3.3).
- **D6** — Work Task grid is read-only: navigable, no Add/Delete; row menu is "Go
  to" (+ optional "Copy identifier"), a contract-supplied set that does not touch
  the References menu path (§3.4, C3, C6).
- **D7** — Integration point: re-render only the dedicated *Work Tasks* section
  (`workstreams.py:214–233`); leave the workstream-level references block
  (`:189–197`) untouched (§3.5).
- **D8** — Claim state is a single derived string (`"Claimed · {who}"` /
  `"Unclaimed"`); a separate *Claimed at* column is out of scope (§3.4).
