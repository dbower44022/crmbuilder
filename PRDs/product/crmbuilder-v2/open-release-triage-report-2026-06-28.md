# Open-Release Triage Report — 2026-06-28

**Pass type:** triage only (read + draft-candidate-requirements + report). Nothing
built, shipped, frozen, decomposed, resolved, or cancelled.
**Engagement:** ENG-001 (`X-Engagement: CRMBUILDER`). **Governance:** SES-294 (complete),
DEC-811. **Scope:** all 19 open releases (`release_status NOT IN shipped/cancelled/superseded`),
re-derived live. Backlog has churned since the handoff doc — REL-014 and REL-031 are now shipped.

Only Doug's two action types remain below: **approve** (§2 + the §3 cleanups) and **decide** (§4).

---

## 1. Ready to build

All open PIs carry a **confirmed** requirement. No input needed — these go to the post-approval build batch.

### Already frozen (reconciliation lane)
| Release | Title | Open PIs (confirmed req) |
|---|---|---|
| **REL-007** | Deploy path — custom-tree writability hardening | PI-292 (REQ-328/329), PI-293 (REQ-330) |
| **REL-010** | Agent Delivery Organization | PI-321 (REQ-253) — Agent Secret Storage; rest of PRJ-018 Resolved |
| **REL-011** | Production Database Architecture | PI-100 (REQ-255) — Postgres scale check; rest Resolved |
| **REL-021** | Relationship deploy — native-target link-name correctness | PI-298 (REQ-338) |
| **REL-022** | Audit-candidate provenance guarantee | PI-299 (REQ-339) |
| **REL-034** | Governance Enforcement Gate | PI-286, PI-287 (both REQ-320) |

### Forming (not yet frozen, all PIs confirmed) — already in motion today
| Release | Title | Open PIs (confirmed req) |
|---|---|---|
| **REL-036** | EspoCRM activity-parent & email-account engine fixes | PI-348 (REQ-388), PI-349 (REQ-389) — next step is freeze→build |
| **REL-037** | Reconcile UI quick improvements | PI-350 (REQ-390/391), PI-351 (REQ-392) — created today |
| **REL-038** | Audit role semantics + non-destructive inventory reconcile | PI-352 (REQ-393), PI-353 (REQ-394), PI-354 (REQ-395) — created *during* this pass |

> These three are confirmed-ready; they just need their freeze when you start their build. They were
> hot during this pass (REL-038 was created mid-pass), so I only read them.

---

## 2. Requirements to approve

18 candidate requirements drafted this pass (`REQ-396…413`, origin `ai_derived`, readability-safe,
full topic + conversation + implements provenance). **All 18 verified approvable** in the Review panel
(`has_provenance` ✓ + `has_topic` ✓). Approving each unblocks its PI for the build batch.

### REL-012 — Multi-User & Concurrency Safety
| REQ | PI | Why |
|---|---|---|
| REQ-396 | PI-103 | Lost-update protection for promoted governance records (optimistic-check vs lease — design at build) |

*(REL-012's other open PIs, PI-135/PI-136, already have confirmed reqs.)*

### REL-016 — Cross-Engagement Reference Libraries
| REQ | PI | Why |
|---|---|---|
| REQ-397 | PI-062 | Cross-engagement reference store architecture (foundational) |
| REQ-398 | PI-063 | Skills reference library |
| REQ-399 | PI-064 | Pattern reference library |
| REQ-400 | PI-065 | Inventory reference library |
| REQ-401 | PI-066 | Contextual skill loading mechanism |
| REQ-402 | PI-067 | Authoring tools for the reference content (depends on PI-062) |

### REL-017 — YAML Publish & Engine
| REQ | PI | Why |
|---|---|---|
| REQ-403 | PI-020 | Cross-file layout aggregation in the deploy engine (last-file-wins layout-clobber bug) |

### REL-013 — Master CRMBuilder PRD consolidation + dogfood
*(the methodology backlog — see Decision #1; drafted so it's approvable either way)*
| REQ | PI | Why |
|---|---|---|
| REQ-404 | PI-069 | Author the remaining Master CRMBuilder PRD phases |
| REQ-405 | PI-070 | Mark methodology documents fully consolidated into the Master PRD |
| REQ-406 | PI-071 | Architecture for storing engagement-scoped client inputs |
| REQ-407 | PI-072 | Engagement-level setup process and records |
| REQ-408 | PI-085 | Domain Overview for the governance-recording domain |
| REQ-409 | PI-086 | Persona records for the governance-recording domain |
| REQ-410 | PI-087 | Session and conversation governance process definition |
| REQ-411 | PI-088 | Standard process-definition (meta) process |
| REQ-412 | PI-094 | User and role entity model for engagement participants |
| REQ-413 | PI-095 | Promote captured candidate methodology inventory into records |

---

## 3. Recommended cleanups

*(Recommendations only — I executed none of these.)*

### Done — all PIs Resolved, but the release record still sits at `preliminary_planning`
Recommend walking each to `shipped` (the work shipped) or cancelling as a no-op container. No build impact.
| Release | Title | Evidence |
|---|---|---|
| **REL-008** | Manual-release execution mode | PRJ-051 — PI-294, PI-295 both Resolved (built/merged/shipped) |
| **REL-029** | Agent Registry runtime wiring | PRJ-069 — 6 PIs (PI-339/340/341/343/346/347) all Resolved |
| **REL-033** | Agent System Redesign (target model) | PRJ-041 — 23 PIs all Resolved |

### Deferred / no actionable open work
| Release | Title | State | Recommendation |
|---|---|---|---|
| **REL-015** | V2 Methodology Schema Enrichment | PRJ-045 — 12 PIs all Deferred | Cancel the release, or leave parked (Decision #4) |
| **REL-035** | Role-aware field-level security deploy | PRJ-072 — PI-310 Deferred | Fold into the role-aware-security consolidation (Decision #2) |

### Leave parked (deliberate)
| Release | Title | Reason |
|---|---|---|
| **REL-018** | claude.ai-web MCP connector | PRJ-028 upstream-blocked (Anthropic connector bug). Leave parked. |

### Blocked-artifact (bad edge dragging a release)
| Release | Problem | Exact fix |
|---|---|---|
| **REL-013** | `freeze-readiness` is `ready=False` because **Cancelled** PI-161 (with deferred, unconfirmed REQ-120) still carries a `planning_item_belongs_to_project` edge into PRJ-023. | Remove PI-161's `planning_item_belongs_to_project` edge. After that + approving the 10 §2 candidates, REL-013 is freezable. (PI-160 is Resolved and fine.) |
| **REL-032** | Its only `project_belongs_to_release` edge is **malformed**: `source_id = "__self__"` (REF-7051, created today 06-28 05:34). No real project/PIs attached; release is effectively empty. | Repair or remove REF-7051 and attach the real project. **Created today — looks like in-progress role-aware-security setup; confirm before touching.** Ties into Decision #2. |

---

## 4. Decisions needed

1. **REL-013 methodology backlog scope.** Ten open-ended dogfood/methodology-authoring PIs (Master PRD
   phases, Domain Overviews, Personas, Process PRDs, engagement setup, user/role model, candidate-record
   promotion). Pursue as a buildable release now, or keep as a long-running dogfood track *outside* the
   release-build batch? I drafted candidate requirements for all 10 (§2) so it's approvable either way —
   but several are design-heavy, not straight code, and depend on each other.

2. **Role-aware field-level security — three releases for one capability.** REL-032 (v1.4, empty/malformed
   edge), REL-035 (deploy, PI-310 Deferred), plus the salvaged PI-051 work (local-only branches, REQ-128/129
   per the security-salvage note). Consolidate into one live release and retire the others? This also
   resolves the REL-032 malformed-edge cleanup above.

3. **Done-but-open release records (REL-008 / REL-029 / REL-033).** All PIs Resolved. Walk each to `shipped`,
   or cancel as a no-op container? Pure bookkeeping — pick the convention you want.

4. **REL-015 (methodology schema enrichment).** 12 PIs all Deferred. Cancel the release, or leave it parked
   for a later phase?

---

---

## Execution log (post-decision walkthrough)

Doug walked the four decisions and chose: **(1) split REL-013 · (2) consolidate role-aware
security into REL-035 and park · (3) ship REL-008/029/033 · (4) cancel REL-015.** Governance:
SES-297, DEC-839. During execution, all 18 §2 candidates were **confirmed** in the Review panel.

| Decision | Action taken | State |
|---|---|---|
| **4 — cancel REL-015** | `transition → cancelled` (pre-lane, clean). 12 deferred PIs retained as backlog. | ✅ Done |
| **2 — role-aware security** | Cancelled empty **REL-032**; deleted its malformed `__self__` edge (REF-7051); re-homed resolved **PI-051** from PRJ-017 (terminal REL-019) into **PRJ-072**; **parked REL-035** (left `preliminary_planning` + notes: no platform write path). | ✅ Done |
| **1 — split REL-013** | Carved **PI-094** (user/role model) into new **REL-040** + new project **PRJ-077**; removed it from PRJ-023. REL-013 stays open as the human-led dogfood track (9 PIs). REQ-412 now confirmed → REL-040 is forming-ready. | ✅ Done |
| **3 — ship REL-008/029/033** | **HALTED — not executed.** | ⚠️ Needs Doug |

### Why Decision 3 was halted
The release ship path requires, **even in manual execution mode**, a *fresh human review sign-off*
at two stages — **reconciliation** (`_check_reconciliation_review`) and **architecture planning**
(`_check_architecture_planning_review`) — each bound to that stage's actual pipeline output. These
three releases are retroactive containers around work that shipped via normal PRs and **never ran the
pipeline**, so there is no reconciled change-set or architecture design for a sign-off to attest to.
Recording those sign-offs would **fabricate human-review evidence** — the exact thing the
requirements-provenance system exists to prevent. So I stopped and left it for you.

**Honest options for the three delivered-but-open releases:**
- **A (recommended) — annotate and leave** at `preliminary_planning` with a note ("delivered via PRs
  outside the release pipeline; retained for traceability; not pipeline-shipped"). Truthful; they read
  as done in triage even though the status isn't a pipeline terminal.
- **B — cancel** them. Rejected earlier for good reason: it labels delivered work as abandoned.
- **C — force them through the lane** with hand-authored reconciliation + architecture sign-offs.
  This is the fabrication path; I won't do it without you explicitly accepting that trade-off.

**Resolution (Doug's call): neither A, B, nor C — fix the missing status.** `cancelled` lies (work was
delivered), `shipped` needs fabricated sign-offs, and `preliminary_planning` also misrepresents built
work. The schema is missing an honest *terminal* state for "delivered outside the pipeline." Drafted
candidate **REQ-420** ("Honest terminal status for work delivered outside the release pipeline", topic
Releases) with implementing **PI-361** in a new forming release **REL-041** / project **PRJ-078**.
On approval + build it adds a `delivered_outside_pipeline` terminal status (reachable from pre-lane
states, no sign-off/QA/test gates), and REL-008/029/033 get closed truthfully. **The three are left
untouched at `preliminary_planning` until that ships.**

---

### Coverage check
20 open releases (REL-038 was created mid-pass), all classified: **6 ready (frozen) + 3 ready (forming)
= 9 Ready** · **4 with requirement-less PIs → 18 candidates drafted** · **3 done + 2 deferred + 1 parked
= 6 Empty** · **2 blocked-artifact** (REL-013 also appears in §2 for its real backlog; REL-032 empty
behind its bad edge).
