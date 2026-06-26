# Continuation Kickoff — Test & Enhance the Comparison/Reconciliation Capabilities

A kickoff prompt for the next session to continue **testing** and **enhancing** the
three-way design/instance reconciliation feature. The core is shipped; this picks
up the deferred work, hardens it, and extends coverage.

---

## 0. Orientation — read these first

- **`CLAUDE.md`** (repo root) — current V2 state + the binding conventions
  (requirement-first precondition, release-scoped model, Branch-work Model A,
  push convention). Non-negotiable.
- **Feature docs:** `three-way-reconciliation-release-plan.md` (design + as-built
  §8), `three-way-reconciliation-user-guide.md` (how it behaves), and the docs
  index `README.md` in this directory.
- **Live state is the DB, not files** — read governance via the REST API
  (`http://127.0.0.1:8765`, `X-Engagement` header) or MCP. Start the API with
  `cd crmbuilder-v2 && uv run crmbuilder-v2-api`.

## 1. What is already shipped (do not rebuild)

Two releases, both `shipped`, merged to `main`, live DB at Alembic head **`0093`**:

- **REL-024 — Three-way reconciliation** (REQ-352…361, PI-314…320). Compare the
  canonical **design** against **two live instances**, grouped by entity;
  capture a field-attribute value into the design; transaction log; blueprint
  rollback; guarded live-revert with data-loss analysis.
- **REL-025 — Label capture** (REQ-364…366, PI-322…324). Audit captures entity
  (`entity_label`/`entity_label_plural`) + field (`field_label`) display labels
  from the source i18n and the panels show them.

**Code map:**
- `access/reconcile_compare.py` — `three_way_compare()` + pure `compute_member_rows()`; groups carry `entity_label`; rows carry an `actionable` flag.
- `access/reconcile_apply.py` — `capture_field_attribute()` (instance→design) + `rollback()` (blueprint undo).
- `access/reconcile_dataloss.py` — `assess_field_change()` / `assess_revert()`.
- `access/repositories/reconcile_transactions.py` — `ReconcileTransaction` log.
- `access/repositories/inventory.py` — `_MEMBER_SOURCES`, `membership_summary`, `publish_plan`.
- `introspect/reconcile.py` — the audit reconcile passes (entities/fields/associations/layouts/roles/field-permissions/teams/filtered-tabs) + label capture via `get_i18n`.
- `api/routers/reconcile.py` — `GET /reconcile/compare`, `POST /reconcile/capture`, `GET /reconcile/transactions`, `GET /reconcile/transactions/{id}/assess-revert`, `POST /reconcile/transactions/{id}/rollback`.
- `ui/panels/reconcile.py` — the desktop **Governance → Reconcile** panel.

## 2. Governance — required before ANY build

This is V2 go-forward work, so **before writing code**: a confirmed requirement
(approved via decision, not a status edit) + an implementing PI, inside a
**new release** (REL-024/025 are shipped/terminal — create a new one; a project
belongs to exactly one release). Mark hand-built PIs `execution_mode=interactive`.
Land code on a `pi-NNN` branch; governance bookkeeping + release close-out on
`main` after merge (Model A). Claude Code commits; Doug pushes.

**Operational gotcha (recurring):** when any PR merges to `main` and adds a
migration, the live DB falls behind head and the **PI-308 drift gate refuses to
start the API**. Fix: back up `crmbuilder-v2/data/v2-unified.db`; for a
**batch-recreate** migration (rebuilds change_log/refs CHECKs) **verify on a copy
first** (`CRMBUILDER_V2_DB_PATH=<copy> uv run alembic upgrade head`, then
`PRAGMA integrity_check` + compare row counts); then `uv run alembic upgrade head`
on the live DB; restart the API.

## 3. Testing backlog (do this first)

1. **Live end-to-end** against the two CBM instances (INST-001 CBMTEST,
   INST-002 CBM Production, `X-Engagement: CBM`). Re-audit both, open
   **Reconcile**, and exercise: compare (full scan + a per-entity view), capture
   a real field-attribute drift instance→design, confirm the transaction logs,
   roll it back, and trigger the data-loss warning on a narrowing/destructive
   revert. Record findings.
2. **Stabilize the Qt test suite** — `pytest tests/crmbuilder_v2/` intermittently
   SIGSEGVs in the offscreen UI teardown under load (a known flake; see
   `pi-159-qt-paint-segfault-design.md` / the conftest gc hook). Get a reliable
   green full run, or isolate the flaky module.
3. **Widen unit coverage** — `reconcile_dataloss` edge cases (type widen vs
   narrow, enum option removal, money/precision), `compute_member_rows` for the
   global-group member types, and a capture→rollback→re-capture cycle.
4. **Capture-back correctness on real drift** — confirm that after capture, the
   source instance's membership drops the captured attribute from its override
   and the three-way row clears.

## 4. Enhancement backlog (scope each as a requirement + PI in a new release)

Roughly highest-value first:

1. **PI-315 (deferred) — targeted single-entity live audit.** The compare serves
   from stored audit data; add an on-demand "re-audit this entity" so the
   per-entity drill reflects current live state without a full scan.
2. **Capture beyond field attributes.** Today only field-attribute rows are
   `actionable`; entity options, relationships, layouts, roles, teams show but
   can't be captured. Extend `reconcile_apply` + the panel per type.
3. **Whole-entity copy** (design↔instance) honoring a checkbox-tree selection —
   the DEC-721 model. Currently single-row capture only; add the cascading
   checkbox tree + batch apply.
4. **Selective publish-to-instance.** "Push design→instance" currently reuses the
   whole-object PRJ-042 publish via the Instances panel; add per-object / per-row
   publish driven from the Reconcile panel, transaction-logged like capture, with
   the data-loss guard wired to the live revert.
5. **Literal instance↔instance side-by-side** (originally deferred). The engine
   data supports A-vs-B; add a dedicated view if useful beyond the design-hub model.
6. **Coverage breadth.** Broaden audited/compared attributes (entity collection
   options drift, more field intrinsics, positional layout diff — the hard case).
7. **Labels everywhere.** Use captured labels in reconcile row member names and
   other panels; consider capturing relationship/option labels too.

## 5. Known constraints

- The audit matches by **internal/neutral name** (c-prefix stripped), never by
  label — labels are descriptive only (this is why the old label-as-name audit
  produced the CBM duplicate entities that were cleaned up 06-26).
- Some config types are read-but-not-writable via the platform (saved views,
  duplicate checks, workflows) — surface them read-only, never offer an action
  that can't execute (REQ-358 / the `actionable` flag).
- Three-way diff is served from the **last audit** (stored membership), not live
  — re-audit to refresh before reconciling.

---

*Provenance: REL-024 + REL-025 (shipped). Plan: `three-way-reconciliation-release-plan.md`.
Author the next requirement set against a new release before building.*
