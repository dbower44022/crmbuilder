# Delivery Efficiency Plan — 2026-07-02

**Status:** DRAFT v1.1 — pending Doug's approval pass. Nothing below is a
requirement, PI, or release yet; §6 defines how this document is processed into
governance records after approval.
**v1.1 (07-02-26, same-day revision):** Phase 2 rescoped after discussion with
Doug — from an all-domains CBM re-run to a **single-domain (mentoring) delivery
culminating in the CBM mentor application**, validating that EspoCRM can support
a custom app's backend. Two feasibility spikes ran and are folded in (§2a):
mentor-auth (answered) and ADO-foreign-repo (answered). Candidates C14–C18 added.
**Pass type:** review + plan only. Nothing built, resolved, or recorded in the
governance store by this document's authoring session.
**Engagement:** ENG-001. **Store consulted:** cloud API (`https://api.crmbuilder.ai`),
read-only, 07-02-26.
**Goal:** make CRMBuilder's process efficient at its actual purpose — **delivering
custom applications** — by shifting capacity from building the delivery machine to
running client deliveries through it, and letting measured friction (not intuition)
drive further machinery work.

---

## 1. Where the process stands (07-02-26)

The v2 rearchitecture is essentially **complete as infrastructure**:

- Governance core (requirements with provenance + human approval, decisions, PIs,
  releases, full traceability) enforced by the commit gate (warn mode).
- The ADO delivers autonomously: multi-task PIs go dispatch → decompose → scope →
  build → test-gate → merge → Resolved without a human in the loop. The Agent
  Profile Registry carries 38 real per-area contracts + the learning lifecycle.
- The store is unified multi-tenant Postgres, **cut over to cloud
  (`api.crmbuilder.ai`, auth on) on 07-01**, ending the local-SQLite corruption era.
- The deploy engine (v1) is validated against real YAML batch deploys; the
  three-way reconcile surface shipped (REL-027/037).
- The release backlog is burned down: **67 releases — 15 shipped, 37
  delivered-off-pipeline, 13 cancelled/superseded, 2 open.**

The two open releases are the strategic ones:

| Release | Title | State |
|---|---|---|
| **REL-013** | Master CRMBuilder PRD consolidation + dogfood | Human-led track; Phase 1 refined, Phase 2 drafted; largely idle while machinery work dominated |
| **REL-039** | Database as Single Source of Truth | PI-355/356 done; PI-357 largely landed (WTK-283..287 merged); PI-358 partially landed (CLAUDE.md bootstrap section); PI-359/360 remain |

## 2. The inefficiency diagnosis

1. **Machinery has consumed the roadmap.** ~7 weeks of work went into the delivery
   apparatus itself. No custom application has yet been delivered end-to-end *by*
   the system: the CBM MR pilot validated the deploy engine only, the full
   Requirements→deployed-app re-run is still pending, and the one real production
   app (cbm-client-intake) was hand-built outside CRMBuilder.
2. **Per-unit process cost is high.** Requirement + approval + PI + release +
   workstreams + work tasks + session/conversation records per change. Real-time
   recording and the gate reduced it, but the 06-28 triage still found
   retroactive-container releases invented purely to satisfy the pipeline.
3. **Operational fragility burned wall-clock hours** (all since remediated or
   guarded — REL-043/055 delivered the scheduler guards, REL-044 the store cutover —
   but the pattern matters): stranded lane occupant silently blocking the batch;
   2.5 h hang on a failed `git worktree add`; parallel drivers clobbering each
   other's worktrees; schema-behind-code refusals on local stores.
4. **Planning redundancy.** Role security spread across 3 releases; Postgres
   targeted by 3 releases; REL-016 overlapping the built registry; REL-040
   overlapping RBAC. Triage passes to untangle this are pure overhead.
5. **Deploy-engine gaps force manual work in every client delivery:** alphabetical
   (not topological) YAML batch ordering; validator blind to server-side fields;
   the foreign-field two-run caveat; savedViews/duplicateChecks/workflows landing
   as MANUAL CONFIG with no generated operator artifact.
6. **Stale orientation surfaces.** The status record sat unrefreshed from 06-13
   through three weeks of heavy delivery; CLAUDE.md grew to ~880 lines that every
   session pays to read. (Exactly what REL-039 fixes.)

## 2a. Discussion outcomes and spike results (07-02-26)

Decisions taken in discussion with Doug, and the two feasibility spikes run the
same day, that reshape Phase 2:

1. **Scope: one domain, not all — and the deliverable is an application.** The
   validation run covers the **mentoring domain** and culminates in the **CBM
   mentor application** (`cbm-custom-mentor-app` — four L1/L2 PRDs drafted
   05-12/13, dormant since). Goal: make the domain more efficient for CBM *and*
   validate that EspoCRM can support a custom app's backend. This exercises the
   part of the product promise ("through deployed, functional application") that
   the 13-phase process has never defined — the stretch that was hand-built for
   `cbm-client-intake` outside the methodology.
2. **Mentor-auth spike — ANSWERED (Option 1 wins).** Live spike on crm-test
   proved Espo's `own` ACL honors `assignedUsers` membership; the pre-existing
   Mentor Role confines a mentor to their own engagements; session logging works
   self-assigned. Portals are structurally mismatched (they scope by
   Contact/Account; CBM keys mentor access by User) and are skipped. Report:
   `cbm-custom-mentor-app/prds/CBM_Mentor_App_Spike_Report_Mentor_Authentication.md`.
3. **ADO-foreign-repo spike — ANSWERED (feasible, two small gaps).** The
   scheduler takes `--engagement`/`--repo-root`; worktrees/agents/test-runner are
   repo-agnostic; the **`CBMMENTOR`** engagement already exists in the cloud
   store. Gaps: the affected-test gate hardcodes CRMBuilder's tree (needs a
   per-repo config PI), and engagement-scoped *profiles* are not
   dispatcher-selectable (rules/learnings overlays DO flow; profile selection is
   an optional second PI). Report: `ado-foreign-repo-spike-2026-07-02.md`.
4. **Who builds: hybrid, structured as a bounded ADO audition.** Human-paired
   (architecture, scaffold, auth/Espo integration); ADO auditions on
   well-specified mechanical work tasks after the spike's prep list clears; an
   explicit escape hatch (fixed friction budget → fall back to hand-build,
   record every failure as a finding/lesson). Full V2 governance under
   `CBMMENTOR` regardless of who builds.

## 3. The plan

Organizing principle: **stop improving the machine speculatively; run a real client
delivery through it and let measured friction drive the backlog.**

### Phase 1 — Finish the two open releases

- **REL-039 first** (PI-358..360): knowledge into the DB; sessions orient from
  `preference` / `lesson` / `reference_pointer` queries instead of a ~880-line
  CLAUDE.md. Direct cut to per-session startup cost for every human and agent
  session. Mostly mechanical → ADO-dispatchable.
- **REL-013 time-boxed:** schedule the human-led Master PRD sessions as calendar
  commitments — three weeks of evidence says they don't happen "in the gaps." The
  PRD only needs to be complete enough to run Phase 2 of this plan, not perfect.

### Phase 2 — The mentor-domain delivery as forcing function (rescoped v1.1)

One domain (mentoring), end-to-end, culminating in the **CBM mentor
application** — requirements through deployed, functional app. The shape:

1. **Ingest** — the four mentor-app PRDs plus existing MR/MN artifacts into V2
   under the CBM engagements (`CBM` for the CRM domain, `CBMMENTOR` for the app).
   Real test of the ingest path on pre-governance documents.
2. **Capture** — audit the mentor-domain entities on live prod (CMentorProfile,
   CEngagement, CSession, Contact, Account) and reconcile into design records.
   This slice drifted heavily past every PRD (the mentoradmin build); after
   capture, the design finally reflects reality. Realistic client simulation:
   clients always have a drifted live system.
3. **Gap interviews** — genuinely new requirements: the mentor's experience of
   the app. Nobody has specified what a mentor sees at login.
4. **Backend feasibility** — the new methodology phase: derive the app's API
   contract, validate Espo supports it before app code. The auth model is
   already answered (§2a-2); the remaining feasibility items follow the same
   spike pattern.
5. **CRM config delivery** — new fields/entities the app needs: generated from
   the DB, deployed, verified (the CRMBuilder pipeline proper).
6. **App build** — hybrid per §2a-4: human-paired scaffold/auth, bounded ADO
   audition on mechanical work tasks after the prep list
   (`ado-foreign-repo-spike-2026-07-02.md` §4) clears.

**Finish line (functional, not clerical):** a mentor logs in with their
provisioned Espo credentials, sees exactly their engagements, logs a session —
and the data lands correctly in Espo with ACL enforced server-side.

Rules of engagement (unchanged from v1.0):

- **Instrument every phase:** start/end timestamps, manual-intervention count,
  workaround log. Pipeline events already exist; this is mostly discipline plus a
  small metrics read.
- **Every manual workaround becomes a requirement candidate with cycle-time data
  attached** — the efficiency backlog gets prioritized by measured cost.
- **Humans handle stakeholder-facing phases; mechanical phases go to the ADO**
  within the audition bounds.

### Phase 3 — Close the deploy-engine gaps that hit every client

All four are known, scoped, and small (documented in CLAUDE.md's engine-bug
backlog and YAML Schema Rules):

1. Topological sort of YAML batches from the relationships graph (kills the
   two-step manual deploy).
2. Validator unions server-side fields when an instance is connected (kills the
   include-dependency-YAMLs workaround).
3. Single-run foreign fields (order relationship creation before field creation,
   or two-pass within one run).
4. duplicateChecks via the EntityManager endpoint; workflows via Workflow CRUD
   gated on Advanced Pack detection; saved views stay manual (platform
   constraint) but the MANUAL CONFIG block becomes a **generated per-client
   checklist artifact** handed to the operator.

### Phase 4 — Cut process overhead per unit of work

- **Tiered governance, formalized:** full requirement→approval→PI rigor for
  capabilities; a documented lightweight lane (the existing `Governed-By: trivial`
  + exemption log) with explicit thresholds, so neither humans nor agents
  over-ceremonialize small fixes — and no more retroactive-container releases.
- **Batch approvals:** a standing approval-queue review cadence (one sitting
  clears the queue) instead of per-requirement round trips. Human approval is the
  pipeline's slowest gate; batching it is the cheapest speedup available.
- **Verify the REL-043/055 scheduler guards hold** across the next real build
  batch (pool-worker halt, concurrent-build guard, run-locks); add per-orchestrator
  worktree isolation if contention recurs.
- **Derive, don't author, the status record** — generate it from the release/PI
  tables at release close. A stale status is how sessions re-derive already-settled
  state.
- **Flip the governance gate warn→enforce** once warnings are clean — prevention
  is cheaper than after-the-fact triage passes.

### Phase 5 — Measure and iterate

Three metrics, computed from data the store already captures, surfaced on a panel:

1. **Lead time** — PI `Ready → Resolved`.
2. **Autonomy rate** — agent-delivered vs. human-intervened work tasks.
3. **Manual-config burden** — MANUAL CONFIG items per client deploy.

**Success criterion for the whole plan:** the next domain/app delivery (after the
mentor-domain run) is measurably faster than the first, with a lower
manual-intervention count.

## 4. Sequencing

```
Phase 1 (REL-039 finish, REL-013 time-box)  ──►  Phase 2 (mentor-domain delivery
        │                                            │     → mentor app)
        └── lowers every session's cost              ├── Phase 3 items pulled in
                                                     │   as their gap is hit live
Phase 4 (process-overhead cuts)  — continuous, independent
Phase 5 (metrics)                — stand up before Phase 2 starts
```

Phase 2 is the spine. Phase 1's REL-039 goes first because it lowers the cost of
everything after it. Phase 3 items are *not* built speculatively — each is pulled
into a release when (and in the order that) the mentor-domain run actually hits
it, except the topological-sort fix, which is certain to be hit and can be built
ahead. The ADO-audition prep (C15–C17) precedes Phase 2 step 6 but not steps 1–5.

## 5. Candidate requirements (for the approval pass)

Drafted in plain declarative language per TOP-013; identifiers assigned on
creation in the store. Each maps to a plan phase.

| # | Candidate requirement | Phase |
|---|---|---|
| C1 | Master PRD dogfood sessions are scheduled as time-boxed calendar commitments with a defined "complete enough to run a client delivery" exit criterion | 1 |
| C2 | A client delivery run records per-phase start/end timestamps, manual-intervention count, and a workaround log in the governance store | 2 |
| C3 | Every manual workaround observed during a client delivery is captured as a requirement candidate carrying its measured time cost | 2 |
| C4 | YAML batch deploys process files in dependency (topological) order derived from the relationships graph, with cycle detection | 3 |
| C5 | Program validation unions server-side entity fields (live metadata) with batch-declared fields when an instance is connected | 3 |
| C6 | A YAML declaring a relationship and a foreign field over it deploys correctly in a single Configure run | 3 |
| C7 | duplicateChecks deploy via the EntityManager API; workflows deploy via the Workflow entity CRUD API when Advanced Pack is detected | 3 |
| C8 | Each deploy run emits a generated per-client manual-configuration checklist artifact covering all NOT_SUPPORTED items | 3 |
| C9 | The governance-exemption ("trivial") lane has documented, binding thresholds distinguishing it from requirement-gated work | 4 |
| C10 | Requirement approvals are processed on a standing batch cadence via the approval queue | 4 |
| C11 | The status record is derived from release/PI state at each release close rather than manually authored | 4 |
| C12 | The governance enforcement gate runs in enforce mode once existing warnings are clean | 4 |
| C13 | Delivery metrics (PI lead time, autonomy rate, manual-config burden per deploy) are computable from the store and surfaced on a panel | 5 |
| C14 | The mentor application authenticates mentors as regular EspoCRM users via their provisioned logins, acts as the authenticated mentor on all CRM operations, and relies on EspoCRM ACL (Mentor Role) for row-level authorization | 2 |
| C15 | The ADO scheduler's affected-test gate takes its test root / source prefix / mirror map from per-repo configuration, with a plain `tests/` fallback | 2 |
| C16 | Agent dispatch prefers an engagement-scoped agent profile over the system profile for the same (area, tier, technology) cell when one exists | 2 (optional) |
| C17 | The CBMMENTOR engagement carries registry-seeded governance rules and learnings (Espo integration gotchas, house conventions, spike lessons) that reach every spawned agent's contract | 2 |
| C18 | The ADO's first foreign-repo build runs as a bounded audition: a fixed friction budget, hand-build fallback, and every failure recorded as a finding or lesson | 2 |

## 6. How this document is processed

Per the governance preconditions (CLAUDE.md "Governance is a precondition") and
TOP-013: this document authorizes nothing by itself.

1. Doug reviews; approves / amends / strikes candidates in §5.
2. Approved candidates are created as `requirement` records with provenance
   (conversation + topic), then confirmed via the approving-decision path.
3. Confirmed requirements get implementing PIs inside projects, scoped into
   releases (reuse REL-013/REL-039 where the work belongs to them; new releases
   for Phases 2–5 work).
4. Only then does any build begin — ADO-dispatched where mechanical, human-led
   where stakeholder-facing.
