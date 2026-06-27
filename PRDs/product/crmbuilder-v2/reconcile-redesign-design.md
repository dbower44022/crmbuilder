# Reconcile Surface Redesign — Design Doc

**Release:** REL-027 — *Reconcile Surface Redesign* (preliminary_planning)
**Project:** PRJ-067 — *Native Qt Reconcile Grid Rebuild* (belongs to REL-027)
**Supersedes (as the operator surface):** the PI-319 native panel `ui/panels/reconcile.py` shipped under REL-024.
**Status:** Design authored 2026-06-27 (engagement CRMBUILDER). Requirements REQ-368…378 created `candidate` and queued in the Requirements Review panel — **pending human approval before any build.** Planning items PI-331…335 created `Draft` in PRJ-067 with `implements` edges.
**Provenance:** topic TOP-111 ← session SES-272 ← conversation CNV-214 (this design conversation).

---

## 1. Why redesign (the problem with what shipped)

REL-024 shipped a working three-way reconciliation *engine* (compare design vs two
live instances, capture a field setting into the design, transaction log, rollback,
data-loss analysis). But the **operator surface** — the native Qt `ReconcilePanel`
— fails the user in concrete, observed ways:

1. **No existence overview.** The panel never tells you, at a glance, which entities
   exist in the design vs each instance. The operator's first real question —
   "is this whole entity missing from Production?" — is unanswerable from the UI.
2. **Only one direction, one narrow type.** It can pull a *field setting* into the
   design (1 of ~7 object types) and nothing else. The other half of the goal —
   push the design *out* to one or both instances — does not exist in the panel at
   all; it was punted to a separate whole-object "publish" on the Instances panel.
3. **Unreadable.** ~287 rows in a flat two-level tree, no grid lines, no alternating
   colors — the right-hand columns float free of the row they belong to.
4. **Jargon.** Column "Kind", values "presence / present / absent / unknown",
   buttons "Capture A → Design" — none of it reads like English to an operator.
5. **Dead rows with no explanation.** Most rows do nothing on click and only then
   pop "cannot be reconciled from here yet," so the panel feels broken.

This redesign rebuilds the operator surface against the same engine, fixing all five.

## 2. Goal

Give the operator a **fast, readable, any-direction reconciliation surface**, native
to the desktop app, where they can:

- see at a glance which entities exist in the design and each instance;
- drill into an entity and see every configuration difference, grouped and readable;
- pick the correct value and choose where it should apply — **design ← instance**,
  **design → instance(s)**, or **instance → instance** (routed through the design as
  hub) — in one action;
- select many items at once (a whole group or any mix of rows) and apply to all that
  support it;
- always *see* differences even for config the platform can't push, with a plain
  explanation when an item can't be moved.

The **design remains the hub and source of truth.** There is no direct
instance-to-instance write; instance→instance is mechanically design-capture then
design-publish.

## 3. Settled design decisions (this conversation, 2026-06-27)

| # | Decision |
|---|----------|
| D-1 | **Full redesign of the operator surface**, not an incremental tweak. The REL-024 engine and REST endpoints are reused/extended; the Qt panel is rebuilt. |
| D-2 | **Native Qt Model/View.** `QTreeView`/`QTableView` backed by a custom `QAbstractItemModel` + `QSortFilterProxyModel`, not the toy `QTreeWidget`, and not a web grid. (TanStack/ag-grid considered and rejected for desktop: would require embedding a browser engine via `QWebEngineView` — too heavy for one panel. Native Qt Model/View is the desktop-appropriate equivalent and covers every requirement below.) |
| D-3 | **Open on an entity-existence grid** — entities (rows) × locations (Master design, Instance A, Instance B), each cell showing exists / missing, enabling whole-entity promotion in one move. |
| D-4 | **Drill into an entity → a collapsible tree** grouped by **Fields, Layouts, Relations, Formulas, Settings, Other**; each section independently collapsible. |
| D-5 | **One unified apply model:** select source value, choose target(s), Apply. Directions: instance→design, design→instance(s), instance→instance (hub-routed). The words "capture", "publish", and "presence" never appear in the UI. |
| D-6 | **Multi-select + batch apply.** Select a whole group or any mix of individual rows; the action applies to every selected item that supports it; unsupported items are reported, not silently skipped. |
| D-7 | **Readability:** grid lines, alternating row colors, virtualized scrolling, clear visual association between a row and its columns. |
| D-8 | **View-only config is shown, never hidden, and the Apply button is never disabled.** Saved views, duplicate-check rules, and workflows have no platform REST write path. They appear in the comparison; the Apply button stays visible; clicking it on such an item pops a plain message explaining *why* it can't be pushed and that it must be configured by hand in the admin UI. (Consistent with the project-wide "never disable buttons, explain on click" rule.) |

## 4. The surface, screen by screen

### 4.1 Existence grid (landing view)

A `QTableView` over a custom model. One row per entity; columns: **Entity**,
**Master design**, **Instance A**, **Instance B** (instance columns labeled with the
chosen instances). Each location cell renders a clear state:

- **In** (exists here) / **Missing** (not here) / **n/a** (instance not audited /
  unknown) — color-coded (e.g. green/in, red/missing, gray/unknown), text label
  alongside the color so it's not color-only.

Row actions (multi-select aware):

- **Promote entire entity →** target picker (design / A / B / both instances) — copies
  the entity and all its supported child objects to wherever it's missing or differs.
- Double-click / Enter → **drill into the entity** (§4.2).

This view answers "what whole entities are out of sync, and where" before any
field-level detail.

### 4.2 Entity detail (drill-down)

A `QTreeView` over a tree model for the selected entity:

```
Account  (Company)
  ▾ Fields
      Applicant Since · Read only      design: No   A: Yes   B: No
      Company Partner Type · exists     design: In   A: Missing   B: n/a
      …
  ▾ Layouts
      Detail layout · panel order …
  ▾ Relations
      mentor (Account → Contact) · exists …
  ▾ Formulas
      …
  ▸ Settings        (collapsed)
  ▸ Other           (collapsed)   ← saved views / duplicate checks / workflows (view-only)
```

- Group headers (Fields/Layouts/…) are collapsible and show a count + a roll-up of
  how many rows differ.
- Each leaf row shows the difference: a plain-English label, then the value in
  **Master design / Instance A / Instance B**.
- Grid lines + alternating row colors on. Virtualized.
- A relationship appears under **both** endpoint entities (DEC-721 carry-over).

### 4.3 The Apply interaction

For one selected row (or a multi-selection), a compact action region:

- Shows the value in each location.
- The operator picks the **source of truth** for this change (design / A / B).
- The operator checks the **target(s)** to bring into line (design / A / B / both).
- **Apply.** The engine routes it: writing into the design is a capture; writing into
  an instance is a publish; instance→instance is capture-then-publish through the
  design.
- Every apply is transaction-logged with before/after, source, target, actor, time
  (reusing the REL-024 `ReconcileTransaction` log) and is reversible. Pushes to a
  live instance run through the existing safe-publish path (backup + verify) and the
  data-loss guard.
- View-only items (Other group, §3 D-8): Apply is visible; clicking explains why it
  can't be pushed.

## 5. Object-type coverage and write-path reality

| Group | Compare (read) | Move (write) | Notes |
|-------|----------------|--------------|-------|
| Fields | yes | yes | field presence + settings (type, required, read-only, max length, default, min/max). Capture-into-design exists today; design→instance via publish. |
| Relations | yes | yes | relationship presence + attributes. |
| Layouts | yes | partial | whole-block apply feasible; positional row/column merge is the hard case — deferred refinement, see §8. |
| Settings | yes | yes | entity collection settings (sort field/direction, full-text search, text filter fields). New capture/publish target. |
| Formulas | yes | yes* | field-level formula is a field attribute (writable); *workflow-style "formulas" that are really Advanced-Pack workflows fall under Other. |
| Other | yes | **no** | saved views, duplicate-check rules, workflows — no platform REST write path. View-only per D-8. |

"Move (write)" beyond field attributes and whole-object publish is **net-new apply
work** (the REL-024 apply engine only captures field attributes into the design).

## 6. Native Qt architecture

- **Models:** a custom `QAbstractItemModel` for the existence grid; a custom tree
  model for entity detail. Source data is the existing `GET /reconcile/compare`
  payload (extended — see §7), reshaped client-side into the grouped tree.
- **Proxy:** `QSortFilterProxyModel` for sort + a filter bar ("show only differences",
  "show only actionable", text filter).
- **Views:** `QTableView` (existence grid) and `QTreeView` (detail) with
  `setAlternatingRowColors(True)`, grid lines, and `ExtendedSelection`.
- **Delegates:** custom `QStyledItemDelegate` for the in/missing/value cells
  (color + label, never color-only).
- **Apply panel:** a widget driven by the current selection; calls the REST client
  synchronously (fast local calls) or via a worker for instance publishes (network).
- **Retire:** the existing flat `QTreeWidget` panel.

Everything stays inside the existing PySide6 desktop app. No web stack, no new
runtime dependency.

## 7. Backend / API implications

Mostly reuse; some extension:

- **Reuse:** `access/reconcile_compare.py` (`three_way_compare`),
  `access/reconcile_apply.py` (capture), `access/reconcile_dataloss.py`,
  `access/repositories/reconcile_transactions.py`, the PRJ-042 publish path, and the
  `api/routers/reconcile.py` endpoints.
- **Extend — existence rollup:** the compare payload already carries presence rows;
  add an entity-level existence summary so the landing grid doesn't have to infer it
  (one row per entity with per-location In/Missing/Unknown).
- **Extend — apply beyond field attributes:** capture/publish for **entity settings**
  (sort/full-text/text-filter), and a **per-object publish-to-instance** path driven
  from reconcile (today only field-attribute capture exists; publish is whole-object
  via Instances). Each new apply type: transaction-logged, data-loss-guarded.
- **Extend — whole-entity promote:** a batch apply that copies an entity + its
  supported children to a target where missing/different.
- **No change:** view-only types stay read-only (D-8); the API simply never offers a
  write for them.

## 8. Proposed requirements (candidate — pending your approval)

All `human_defined`, provenance to this conversation's topic. IDs assigned at
creation; numbering shown for readability.

| ID | Requirement | Priority |
|----|-------------|----------|
| REQ-368 | Entity-existence landing grid: entities × (design + each instance), showing exists / missing / unknown per location | must |
| REQ-369 | Whole-entity promotion to a chosen target where missing or different | must |
| REQ-370 | Entity detail drill grouped into Fields / Layouts / Relations / Formulas / Settings / Other, each independently collapsible | must |
| REQ-371 | Unified any-direction apply (design ← instance, design → instance(s), instance → instance hub-routed) selectable per item | must |
| REQ-372 | Multi-select across groups and rows with batch apply to all supported items; unsupported items reported | must |
| REQ-373 | Readable grid: grid lines, alternating row colors, virtualized scrolling, clear row/column association | must |
| REQ-374 | Operator-language UI — no "capture/publish/presence/kind" jargon on screen | should |
| REQ-375 | Apply coverage for entity settings (sort, full-text search, text filter fields) | must |
| REQ-376 | Per-object publish-to-instance driven from the reconcile surface, transaction-logged and data-loss-guarded | must |
| REQ-377 | View-only handling: view-only config is shown; Apply stays visible; clicking it explains why the item can't be pushed and must be configured manually | should |
| REQ-378 | Native Qt Model/View implementation (no web grid / browser-engine dependency) | must |

## 9. Proposed planning items (build phases, in PRJ-067)

| PI | Title | Implements |
|----|-------|-----------|
| PI-331 | Compare-payload extension: entity-existence rollup + grouped object types | REQ-368, REQ-370 |
| PI-332 | Apply engine extension: entity settings + per-object publish-to-instance + whole-entity promote | REQ-369, REQ-371, REQ-375, REQ-376 |
| PI-333 | Native Qt models/views: existence grid + entity-detail tree (grid lines, alt colors, virtualization, collapsible groups) | REQ-373, REQ-378, REQ-370 |
| PI-334 | Unified apply panel + multi-select batch apply + operator-language relabel | REQ-371, REQ-372, REQ-374 |
| PI-335 | View-only handling (visible Apply + explain-on-click), retire old panel, tests, docs | REQ-377 |

**Suggested build order:** PI-331 → PI-332 (backend foundation) → PI-333 → PI-334 →
PI-335 (UI + polish).

## 10. Deferred (non-blocking, call out, don't silently drop)

- **Positional layout merge** (row/column-level layout diff/apply) — hardest coverage
  item; whole-block apply first, positional merge later.
- **Manual-config checklist generation** for view-only items (the "(B)" option) — a
  later enhancement on top of D-8's explain-on-click.
- **Targeted single-entity live re-audit** (REL-024's deferred PI-315) — the compare
  still serves from the last stored audit; re-audit to refresh before reconciling.
- **Generalizing the engagement-empty state** — the panel should tell the operator
  when the active engagement has no instances (the CRMBUILDER-vs-CBM confusion), not
  sit blank. Fold into PI-333's empty-state handling.

## 11. Known constraints (carried from REL-024)

- The compare serves from the **last audit** (stored membership), not live — re-audit
  to refresh before reconciling.
- Matching is by **internal/neutral name** (c-prefix stripped), never by label.
- View-only config (saved views, duplicate checks, workflows) has no REST write path.

## 12. Governance next steps

1. Create the session + conversation + topic recording this design conversation.
2. Create REL-027 (preliminary_planning), PRJ-067 (belongs to REL-027), the candidate
   requirements (§8), and the planning items (§9) with their `implements` edges.
3. **You approve the requirements** in the Requirements Review panel (the one human
   gate) — flips each `candidate → confirmed` via the approving-decision path.
4. Freeze REL-027 once requirements are confirmed, satisfying the release-scoped
   development gate.
5. Execute PI-331 onward on `pi-NNN` branches; governance bookkeeping + release
   close-out on `main` after merge (Model A).

Until you approve, nothing is built — this doc is the deliverable for your evaluation.
