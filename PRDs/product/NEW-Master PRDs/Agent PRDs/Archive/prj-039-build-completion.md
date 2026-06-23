# PRJ-039 / PRJ-040 — Release-pipeline hardening: build completion record

**What this is.** The durable, git-tracked outcome of the SES-216 release-pipeline
hardening effort: the DEC-613 build order (six planning items) executed end to end.
The authoritative records are in the V2 database (the decisions, conversations, and
requirements named below); this note is the travels-with-the-clone summary.

**Origin.** The REL-005 dev-lane run burned ~$40 / ~2 hours rebuilding already-shipped
work. The forensic trace (`REL-005-forensic-agent-trace.md`, this folder) drove 21
requirements (PRJ-039 / TOP-099 guardrails + PRJ-040 / TOP-100 observability), decomposed
into six sequenced planning items (DEC-613).

## Build order outcome (DEC-613) — all six Resolved

| PI | Scope (requirements) | Outcome | Merge commit |
|----|----------------------|---------|--------------|
| **PI-268** | Redundant-work killers — exclude delivered, no-op exit, halt (REQ-265/267/272) | Built + merged | `c81fa8c2` |
| **PI-269** | Upstream planning filters — single-PI scope, graph re-validation, cancel-clear, fan-out cap (REQ-266/274/275/276) | Built + merged | `7cf37a21` |
| **PI-273** | Observability (foundational) — pipeline-event log + agent-activity + query (REQ-312/313/314) | Built + merged | `8d4941e7` |
| **PI-270** | Worker guardrails — input-validation, design-NA, commit-first, bounded verify, time budget (REQ-268/269/270/271/279) | Built + merged | `394b8ee8` |
| **PI-271** | Agent contract infrastructure — area-match refusal + technology variants (REQ-273/278/280/281) | Built + merged (Option A: mechanism + exemplars; full catalog deferred) | `0b65e463` |
| **PI-272** | Execution model (REQ-024/027/031/283) | **Verified already-built; re-traced, not rebuilt** | — (no code) |

Five PIs built end to end (~50 new tests, three migrations 0082/0083 + PG 0039/0040, all
green); the sixth verified already-delivered.

## The PI-272 finding (and a correction to the annotated map)

**PI-272's execution-model requirements were already delivered** by the per-area matrix
back half — **PI-245…249, all Resolved** — plus the reconciliation `develop_gate`, whose
code explicitly cites REQ-027/031. Building PI-272 from scratch would have rebuilt shipped
work: the exact REL-005 failure this project exists to prevent. So it was **verified and
re-traced, not rebuilt** (DEC for the verification; conversation CNV-176).

Verified coverage (now reflected in `planning_item_implements_requirement` edges):

- **REQ-024** (plan splits by area, lays out the passes) ← `run_area_design` (**PI-245**)
- **REQ-027** (Develop does not start until the cross-area coherence check is clean) ←
  `require_design_review_signoff` + `develop_gate` (**PI-246**)
- **REQ-031** (coherence check over the area design specs) ← PI-245 (specs) + PI-246 (review)
- **REQ-283** (an area expert builds its whole area for a phase across the release) ←
  `run_area_design` / `run_area_develop` / per-area Test (**PI-245 / PI-247 / PI-248**)

> **Correction to `agent-pipeline-annotated-map.md` (this folder).** That map states the
> cross-area coherence check (REQ-027/031) is **UNBUILT** — "`lead.complete_phase` advances
> on all-tasks-Complete and never runs it." That is true only of the **older**
> PM→Lead→Phase→Area path. The **newer per-area matrix back half (PI-245…249)** — the actual
> target execution model — **does** enforce it via the Design Review gate
> (`require_design_review_signoff`) and the finding-based `develop_gate`. The coherence gate
> exists where it matters; the older path is being superseded.

## What the hardening closed

The REL-005 failure mode is now closed from every angle: already-delivered work is never
planned (265), nothing over-scoped or malformed is decomposed or executed (266/274/276),
agents stop / halt / commit-first / verify-bounded within a time budget
(267/268/269/270/271/272/279), wrong-area contracts are refused with technology variants
supported (273/278/280/281), every agent action is durably recorded and queryable
(312/313/314), and the area-phase execution model with its coherence gate was confirmed
already in place (024/027/031/283).

**Authoritative records:** topics TOP-099 / TOP-100; requirements REQ-265…283 + REQ-312…316
(REQ-315/316 deferred) + the amended REQ-024/027/031; decisions DEC-552…556, DEC-613, and the
per-PI build-closure decisions; conversations CNV-137/138/167/170/171/172/174/175/176 under
session SES-216.
