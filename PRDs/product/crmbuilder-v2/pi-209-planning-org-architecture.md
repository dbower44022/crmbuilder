# PI-209 — Planning-Orchestration Substrate (Option A): Architecture

**Wave 3 of the multi-agent release pipeline build** (build plan §19; `blocked_by`
PI-205/207/208/215, all merged). Architecture-phase deliverable for **PI-209** —
"Build the Architect Planning Agent and area planning specialists." Project
**PRJ-033**. Stacked on `pi-wave3` (after PI-213/214). **The last PI of the
6-project release-pipeline build.**

Governing design: `multi-agent-release-pipeline-architecture.md` §5.1, §10
(REQ-195 with PI-207, REQ-208). Scope decision: **Option A — the deterministic
planning-orchestration substrate**, not the LLM agent profiles (PI-122 registry)
or the spawn runtime (ADO scheduler). It is the spine those later drive; the
genuine design/decomposition *judgment* is the deferred agent layer.

## 1. What architecture planning does (§5.1)

After reconciliation, the architecture-planning stage produces (a) the **versioned
design** — each touched artifact's vN+1, from the reconciled delta-set — and (b)
the **workstreams + work tasks**, sequenced, that satisfy the "planned completely"
gate. PI-209 Option A delivers the deterministic halves: **author the versioned
designs** from the reconciled delta-sets, and **report planned-completely
readiness**. The judgment-laden work-task decomposition is the agent's job
(deferred); the existing ADO decomposer handles ado-mode PIs, and interactive
release-pipeline PIs are decomposed by their human/agent owner.

## 2. Mechanism (no new schema)

`access/planning.py` (orchestrates merged substrate; no table, no migration):

- `author_designs(session, release, delta_sets)` — requires the release in
  `architecture_planning`; for each reconciled delta-set
  (`{artifact_type, artifact_identifier, merged}`, the hand-off from PI-215's
  `reconcile_release`, RC-5) snapshots `merged` as the release-tied **vN+1** via
  `artifact_versions.snapshot` (PI-208). **Idempotent** — skips an artifact already
  versioned for this release, so re-running the planning pass is safe.
- `planning_readiness(session, release)` — the deterministic "drive toward the
  gate" read: `{frozen, in_scope_planning_items, undecomposed_pis,
  designs_authored, sequencing_ok, ready, missing[]}`, computed from the same
  release → project → PI → workstream → work_task traversal the PI-205
  planned-completely gate uses (reusing its helpers; the work-task `blocked_by`
  graph acyclicity is `sequencing_ok`).
- `plan_release(session, release, delta_sets)` — the combined pass:
  `author_designs` then `planning_readiness`.

**Single-threaded by area (REQ-208):** the authoring is one deterministic
single-writer pass; the per-area planning claim (PI-207) is the agent-level
enforcement of serial-within-area when the LLM specialists run.

## 3. Stage boundary

- **Reconciliation (PI-215)** produces the conflict-free reconciled delta-set.
- **PI-209** consumes it to author vN+1 + report readiness — it does **not** re-run
  the merge or resolve conflicts (the `architecture_planning` stage is reached only
  after the RC-1 gate, so the delta-sets are conflict-free).
- **The planned-completely gate (PI-205)** is the downstream consumer of readiness:
  `architecture_planning → ready` still enforces it; `planning_readiness` is the
  non-raising report of the same conditions.

## 4. API

- `POST /releases/{id}/plan` `{delta_sets:[…]}` → `plan_release`.
- `GET /releases/{id}/planning-readiness` → the readiness report.

## 5. Deferred (the agent layer — not Option A)

- **LLM Architect / area-planning-specialist profiles** — Agent Profile Registry
  rows (PI-122): the design/decomposition *judgment*.
- **The spawn runtime** — resolve a contract + spawn a planning agent (ADO
  scheduler). Both drive this substrate; both are out of PI-209's Option-A scope.

## 6. Tests

- `author_designs` requires `architecture_planning`; snapshots vN+1 per delta-set;
  idempotent on re-run; ties versions to the release.
- `planning_readiness` reports frozen / designs-authored / undecomposed PIs /
  sequencing; `ready` true only when all hold.
- `plan_release` authors then reports. SQLite + PG.

## 7. Requirement traceability

| REQ | Where |
|---|---|
| REQ-195 conceptual → committed single-threaded (planning side) | §2 (single-writer authoring; PI-207 area claim is the agent-level enforcement) |
| REQ-208 Phase-2 planning serial-within-area, no backstop | §2 (one deterministic pass; no fan-out, so no lock backstop) |
