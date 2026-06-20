# Finding entity + reconciliation gate — build notes (PI-134)

Status: **Built on branch `pi-133-134`** (Design WSK-033 + Develop WSK-034 +
Test WSK-035). Left **In Progress** for a separate PM session to verify the
working-demo bar (the gate blocks Develop on an open blocking finding, then
releases on resolution), **authorize + apply the live findings migration** (see
`pi-134-findings-migration-runbook.md`), merge to `main`, and resolve PI-134.

The spec is **DEC-400**; the requirements are **REQ-031..036 / REQ-027** under
topic **TOP-010** (Reconciliation). It builds on the Layer 2 pool (DEC-397).

## What PI-134 is

Two parts:

1. **The `finding` (`FND-`) entity** — a cross-area coherence problem recorded
   at the end of Design (REQ-031..036). The reconciliation check compares the
   area specifications for a Planning Item and records each problem as a finding.
2. **The reconciliation gate** — the runtime enforces that **Develop does not
   begin until that check is clean**: before dispatching a Planning Item's
   Develop Work Tasks, the runtime requires the PI's Design phase Complete *and*
   zero open blocking findings (REQ-027/033).

## The finding entity

- `finding_type` ∈ {`conflict`, `gap`, `dependency`, `overlap`} (REQ-032).
- `finding_severity` ∈ {`blocking`, `advisory`} (REQ-033).
- `finding_status` lifecycle `open → referred → resolved` (REQ-034/035): a
  finding is `open`, may be `referred` to a person when the agents cannot settle
  it, and is `resolved` once its resolution is recorded. **Only `resolved` is
  terminal and opens the gate; `open` and `referred` both hold it.**
- `finding_summary` (the short title the runtime records), `finding_description`,
  `finding_resolution` + optional `finding_resolution_method` ∈ {`revise`,
  `order`, `combine`, `refer`} (REQ-034). `finding_resolved_at` server-set on
  resolution.
- Edges: `finding_relates_to` (finding → planning_item | workstream | work_task —
  the specifications it involves) and `finding_resolved_by` (finding → decision |
  work_task | workstream). `learning_derived_from` now also targets `finding`
  (REQ-036 — the PI-122 D-δ6 target that was waiting on this entity).
- Engagement-scoped (`EngagementScopedPKMixin`), like workstream / work_task.

### Where it lives

- `access/models.py::Finding` — table `findings`, the CHECKs.
- `access/vocab.py` — `FINDING_TYPES` / `FINDING_SEVERITIES` / `FINDING_STATUSES`
  / `FINDING_STATUS_TRANSITIONS` / `FINDING_OPEN_STATUSES` /
  `FINDING_RESOLUTION_METHODS`; `finding` in `ENTITY_TYPES`; the two edge kinds in
  `REFERENCE_RELATIONSHIPS` + their `_kinds_for_pair` clauses (which rebuilds the
  `refs` + `change_log` CHECKs at create_all time — the model is the source of
  truth for tests).
- `access/repositories/findings.py` + `api/routers/findings.py` + `api/schemas.py`
  — the standard eight-endpoint CRUD surface (`/findings`).
- `access/entity_summary.py` + `migration/unify_engagement_dbs.py` — registered
  the new type for the entity-summary grid and the unified-DB / PG copy harness.
- Tests: `tests/.../access/test_finding.py` (14) +
  `tests/.../api/test_governance_api.py` (2 added).

## The reconciliation gate

- `runtime/reconciliation.py`:
  - **pure** `evaluate_develop_gate(phase_type, design_complete, findings)` — a
    non-Develop phase passes; a Develop phase is held while Design is incomplete
    or any related finding is open + blocking, and clears once Design is Complete
    with no open blocking findings (advisory / resolved findings never hold it).
    `is_open_blocking(finding)` is the per-finding predicate.
  - **I/O** `develop_gate(api_base, engagement, work_task)` — resolves the Work
    Task's owning Workstream → its Planning Item → the PI's Design Workstream
    status and the findings related to the PI (and its Design Workstream), then
    applies the pure decision.
- Wired into both runtimes via one shared helper
  `CoordinatingRuntime._reconciliation_gate_open(work_task)` (best-effort: a
  gate-read failure never wedges dispatch):
  - **Layer 1** `_next_assignment` filters the eligible list through it, so the
    serial loop skips a gated Develop task and moves to the next.
  - **Layer 2** `_eligible_candidates` filters through it, so the pool never
    dispatches a gated Develop Work Task.

### The working demo

`uv run python scripts/demo_pi134_reconciliation_gate.py` — end-to-end on a
throwaway **create_all** SQLite DB (NOT the live DB), via the in-process API.
Captured run:

```
Seeded: PI=PI-001  Design=WSK-001(Complete)  Develop=WSK-002  Develop-task=WTK-001(Ready)  finding=FND-001(blocking/open)

Phase 1 — open blocking finding
  gate decision : allow=False  reason='1 open blocking finding(s): FND-001'
  dispatchable  : []  → Develop is HELD ✔

  >>> resolved FND-001 (revised the Design spec)

Phase 2 — finding resolved
  gate decision : allow=True  reason='Design complete, no open blocking findings'
  dispatchable  : ['WTK-001']  → Develop is DISPATCHED ✔

  DEMO PASSED ✔
```

Unit tests: `tests/crmbuilder_v2/runtime/test_reconciliation.py` (14) — the pure
gate decision across all cases, the I/O resolution over a stubbed edge graph, and
the Layer 2 pool's candidate filter.

## Live-DB migration — prepared, NOT applied

The findings table + the three CHECK rebuilds are a destructive live-DB op,
**prepared and copy-tested but not applied** — see
`pi-134-findings-migration-runbook.md`. Migration files:
`migrations/versions/0045_pi_134_findings_entity.py` (SQLite) +
`migrations/pg/versions/0007_pi_134_findings_entity.py` (PG), guarded by
`tests/.../migration/test_0045_findings_entity.py`. A PM session authorizes and
runs the live apply after merge.
