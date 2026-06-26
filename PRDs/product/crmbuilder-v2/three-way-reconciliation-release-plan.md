# Three-Way Design/Instance Reconciliation — Release Plan

**Release:** REL-024 — *Three-Way Design/Instance Configuration Reconciliation*
**Project:** PRJ-062 — *Design ↔ Instance Reconciliation UI* (belongs to REL-024)
**Provenance:** TOP-109 ← SES-268 ← CNV-210 ← DEC-719…724
**Status:** Planning authored; requirements `candidate` awaiting human approval.
**Authored:** 2026-06-26 (engagement CRMBUILDER).

---

## 1. Goal

Give an operator a **side-by-side reconciliation surface** across the canonical
**design** and **two selected live CRM instances**. The tool shows every
configuration setting that differs across the three, grouped by entity, and lets
the operator reconcile each difference — pull an instance's value into the
design, or push the design's value out to either or both instances — or leave it
different. Every change is logged and reversible.

The design is the **hub and source of truth**. There is no direct
instance-to-instance edit; values move between instances by capturing into the
design and publishing back out.

## 2. What already exists (reused, not rebuilt)

- **Canonical inventory + per-instance membership** (PRJ-027, complete): audit a
  live instance, normalize to engine-neutral form, record per-`(object,
  instance)` presence/drift in `instance_membership` with a sparse per-attribute
  `override`. This is the substrate the three-way diff reads from.
- **Publish path** (PRJ-042, complete): generate → validate against the live
  target → pre-publish backup → deploy → re-audit verify. The "push design →
  instance" direction reuses this per selected object.
- **Engine-neutral adapters** (PRJ-025): concrete ↔ neutral mapping both ways.

The new work is the **three-way value-level comparison**, the **capture-back**
direction (instance → canonical design), the **transaction log + rollback**, the
**broadened coverage**, and the **UI**.

## 3. Settled design decisions

| # | Decision | Summary |
|---|----------|---------|
| DEC-719 | Two modes, one engine | A lightweight on-demand per-entity drill (fast single-instance design work) and a comprehensive full scan (design + both instances). One shared compare-and-apply engine and data model. |
| DEC-720 | Design is the hub | Capture instance→design; publish design→instance(s). Instance-to-instance routes through the design. |
| DEC-721 | Entity-first + checkbox tree | Start from an entity inventory; expand to a cascading checkbox tree; select whole entity or individual nodes. A relationship shows under **both** endpoint entities. |
| DEC-722 | Trust but log | No approval gate; every reconcile action (either direction, either mode) is logged with before/after, source, target, actor, time; everything is reversible. |
| DEC-723 | Rollback reach | Design undo is instant and clean. Live-instance revert is guarded: re-check current state, analyze impact, and **warn before proceeding if it could cause data loss** or cannot be cleanly applied. |
| DEC-724 | Full coverage in release 1 | Entity presence, fields + field settings, relationships, layouts, roles, teams, field-level security. Read-only-but-not-writable settings are shown as **non-actionable** rows, not hidden. |

## 4. Requirements (candidate — pending your approval)

All `human_defined`, provenance to CNV-210 / TOP-109.

| ID | Requirement | Priority |
|----|-------------|----------|
| REQ-352 | Three-way configuration difference view (one row per differing setting, grouped by entity, column per source) | must |
| REQ-353 | Per-entity drill and full-scan modes | must |
| REQ-354 | Entity-first navigation with granular checkbox selection | must |
| REQ-355 | Relationships listed under both linked entities | should |
| REQ-356 | Capture into design and publish to instances (design is hub) | must |
| REQ-357 | Full configuration coverage | must |
| REQ-358 | Read-only handling for non-writable settings | should |
| REQ-359 | Transaction log for all reconcile actions | must |
| REQ-360 | Rollback of design changes | must |
| REQ-361 | Guarded live-instance revert with data-loss analysis | must |
| REQ-362 | Safe publish with backup and verification | must |
| REQ-363 | Whole-entity copy including selected children | should |

## 5. Planning items (build phases, in PRJ-062)

| PI | Title | Implements |
|----|-------|-----------|
| PI-314 | Extend canonical inventory to full configuration coverage (data foundation) | REQ-357, REQ-358 |
| PI-315 | Targeted single-entity live audit path (drill freshness) | REQ-353 |
| PI-316 | Three-way comparison engine (value-level diff, relationship dual-listing) | REQ-352, REQ-355 |
| PI-317 | Reconcile/apply engine (capture, publish, whole-entity copy) | REQ-356, REQ-362, REQ-363 |
| PI-318 | Transaction log, design rollback, guarded live revert | REQ-359, REQ-360, REQ-361 |
| PI-319 | Desktop reconciliation UI | REQ-352, REQ-353, REQ-354 |
| PI-320 | Non-writable read-only handling, tests, documentation | REQ-358 |

**Suggested build order:** PI-314 → PI-316 → PI-315 → PI-317 → PI-318 → PI-319 →
PI-320. The data foundation (314) unblocks the comparison engine (316); the
apply/log/revert layers (317, 318) and the UI (319) build on it; polish + tests
(320) closes.

## 6. Key risks / hard parts

- **Capture-back is genuinely new.** The inventory has only ever flowed
  instance → membership; writing an audited value into the canonical design
  record is new (PI-317).
- **Layouts are positional.** A value-level diff/merge of panels/rows/columns is
  the hardest coverage item (PI-314/316); V1 only did whole-block layout match.
- **Some settings have no REST write path** (e.g. saved views, duplicate checks,
  workflows). These are shown read-only (REQ-358) so the tool never offers an
  action it cannot perform.
- **Live revert is best-effort.** Re-pushing a prior value is a new deployment;
  destructive originals cannot be fully undone — hence the data-loss analysis and
  warning (REQ-361), not a promise of perfect reversal.

## 7. Governance state & next steps

1. **You approve the requirements** in the desktop Requirements Review panel
   (the one human gate). Approval flips each `candidate → confirmed` via the
   approving-decision path and stamps `requirement_approved_at`. *(I deliberately
   did not auto-confirm — approval is yours.)*
2. **Freeze REL-024** (preliminary_planning → … → frozen) once requirements are
   confirmed and the design is reconciled, satisfying the release-scoped
   development gate before any PI goes In Progress.
3. **Execute** PI-314 onward on a branch; land governance bookkeeping on `main`
   after merge per the Model A branch protocol.

Until you approve, nothing is built — this is the planning deliverable for your
evaluation.

---

## 8. Implementation status (06-26-26)

Requirements REQ-352…363 **confirmed** (DEC-725); REL-024 **frozen**
(`reconciliation`, `release_frozen_at` 2026-06-26). Built on branches stacked off
`main` (`pi-314-inventory-coverage` → `pi-316-comparison-engine`); each PI's code
committed with tests passing. Live DB migration (0090) lands on merge per Model A.

- **PI-314 — inventory coverage:** Discovery — the coverage substrate (member
  types entity/field/association/layout/role/team/filtered_tab + their reconcile
  passes incl. field-level security) was **already built** by PRJ-027/PRJ-051.
  Remaining gap closed: broadened the field audit/override from type+required to
  `field_max_length`/`default_value`/`min`/`max`/`read_only` (forward-asymmetry
  to avoid platform-default noise). `09398a60`.
- **PI-316 — comparison engine:** `access/reconcile_compare.py` +
  `GET /reconcile/compare` — value-level three-way diff across design + two
  instances, grouped by entity, relationships dual-listed, drill + full-scan from
  one path, served from stored audit data (no live re-scan). `c9ada1fb`,
  `b9ea677f`.
- **PI-318 — transaction log + rollback + data-loss analysis:**
  `ReconcileTransaction` table/repo (migrations 0090 / PG 0047), blueprint
  rollback, and `reconcile_dataloss` revert impact analysis with
  `GET …/assess-revert`. `35fbb78e`, `db38481b` (+ rollback in `6ab3e68e`).
- **PI-317 — apply engine:** capture (instance→design) for field attributes with
  full transaction logging (`access/reconcile_apply.py`); `POST /reconcile/capture`,
  `/transactions/{id}/rollback`, `GET /transactions`. Publish (design→instance)
  **reuses the existing PRJ-042 publish path**. `6ab3e68e`.
- **PI-319 — desktop UI:** `ui/panels/reconcile.py` — two-instance picker,
  grouped three-column difference tree, capture A/B → design, transaction-log tab
  with data-loss-guarded rollback; `Reconcile` sidebar entry. `83c1db5e`.
- **PI-320 — read-only handling:** each comparison row carries an `actionable`
  flag; the UI only offers reconcile on actionable (field-attribute) rows and
  shows the rest for visibility (REQ-358).

**Deferred (non-blocking):** PI-315 targeted single-entity live audit (the diff
serves from stored data; only drill *freshness* needs it); whole-entity copy and
per-attribute publish-to-instance beyond the existing whole-object publish; capture
for non-field member types. **Next:** merge to `main`, apply migration 0090, run
the governance close-out (resolve PI-314…320), and advance REL-024 toward shipped.
