# PI-206 — Area-as-Freeze-Unit & the Two QA/Test Levels: Architecture

**Wave 1 of the multi-agent release pipeline build** (build plan §19; `blocked_by`
PI-205). Architecture-phase deliverable for **PI-206** — "Build area-as-freeze-unit
handoff and the two QA/test levels." Stacked on the `pi-205-release-entity` branch.

Governing design: `multi-agent-release-pipeline-architecture.md` §7.1, §8
(REQ-192, REQ-193). §15/§19.5 classify PI-206 as **extends-ADO**.

## 1. The reconciliation — area = the ADO Workstream (phase)

The release-pipeline "Area" (the freeze unit, §7.1) maps to an ADO **Workstream**
(a delivery phase of a Planning Item). The two area-level requirements are
**already delivered by the landed Lead substrate** (`access/repositories/lead.py`)
— PI-206 affirms them and does not rebuild them:

- **REQ-192 — never build on unfrozen ground.** `start_phase` opens a Workstream
  (`Ready → In Progress`) only when its serial `blocked_by` predecessors are
  terminal (`_predecessors_terminal`). A downstream area cannot start on an
  unfrozen upstream. *(Already built; affirmed by `test_lead.py`.)*
- **REQ-193 — an area freezes only after its QA + test.** `complete_phase`
  freezes a Workstream (`In Progress → Complete`) only when **every** Work Task
  in it is `Complete`. The area's QA-conformance and test-verification work *are*
  Work Tasks (the Develop and Test passes of the four-pass model); their
  completion is the area's QA+test pass. *(Already built.)*

So the **area level is the existing ADO phase model**. Adding a parallel
area-freeze mechanism would be redundant and is deliberately not done.

## 2. The net-new part — release-level QA/test gates (§8)

§8 defines **two** levels: area (in isolation) and **release** (the assembled
whole, end-to-end). PI-205 gave the Release the `… → qa → testing → deployment →
shipped` stages but left their *content* ungated. PI-206 gives §8 teeth at the
release level: **QA is a conformance gate and comes first; Testing is functional
verification** — so the release cannot leave `qa` until QA passed, nor leave
`testing` until tests passed.

### 2.1 Mechanism (DEC-504)

Two nullable timestamps on the Release record the release-level passes:
`release_qa_passed_at`, `release_test_passed_at`. Two repository actions record
them, and two gate predicates consume them in `releases.transition()`:

| Action | Precondition | Effect |
|---|---|---|
| `qa_pass(rel)` (`POST /releases/{id}/qa-pass`) | status is `qa` | stamp `release_qa_passed_at` |
| `test_pass(rel)` (`POST /releases/{id}/test-pass`) | status is `testing` | stamp `release_test_passed_at` |

| Gated transition | Gate |
|---|---|
| `qa → testing` | `release_qa_passed_at` is set |
| `testing → deployment` | `release_test_passed_at` is set |

- **Options:** (a) a separate `gate_pass` entity/table; (b) two timestamps on the
  Release. **Chosen:** (b) — a release passes each gate exactly once per pass, a
  timestamp is the minimal faithful record, and it lives with the stage it gates.
- **Rework invalidates passes.** A rework bounce-back (`qa|testing|deployment →
  development`, D-07) **clears both** timestamps in `transition()`, so re-QA and
  re-test are required on the way back up. This keeps "nothing ships that wasn't
  re-verified after a change."
- **The requirement is the through-line (§8).** Release testing verifies the
  release's requirements; `test_pass` is the recorded assertion that the
  composition's key requirements hold. (The automated coverage check that a
  release's requirements are all exercised is a thin follow-on; the gate + the
  recorded pass are the substrate.)

## 3. Schema / migration

- `Release` gains `release_qa_passed_at`, `release_test_passed_at` (nullable
  `DateTime(tz)`). SQLite `0065` + PG `0022` add the two columns (no CHECK
  rebuilds). `test_release`'s expected-columns set is updated.

## 4. Tests

- `qa_pass` requires `qa` status; `test_pass` requires `testing`; both stamp.
- `qa → testing` rejected until QA passed; `testing → deployment` rejected until
  tests passed; both succeed once passed.
- a rework bounce-back to `development` clears both passes; re-entering `qa` then
  requires a fresh QA pass.
- area-level REQ-192/193 affirmation references `test_lead.py` (no rebuild).
- SQLite + PG.

## 5. Requirement traceability

| REQ | Where |
|---|---|
| REQ-192 area opens only after upstream frozen | §1 — existing `start_phase` predecessor gate |
| REQ-193 area freezes only after area QA + test | §1 — existing `complete_phase` work-task gate |
| §8 release-level QA (conformance) before Testing (function) | §2 — `qa_pass`/`test_pass` + the two stage gates |
