# Kickoff prompt — build the multi-agent release pipeline's AGENT LAYER

> Paste this into a fresh Claude Code session. It is written to orient cold —
> follow the Orientation step before doing anything else.

---

## Mission

The multi-agent release pipeline **substrate** is fully built, merged, and proven
end-to-end (a release drove concept → shipped → live through every gate). What
remains is the **agent layer** — the intelligence + runtime that *drives* the
substrate so the pipeline runs autonomously instead of being hand-driven. Design
it, then build it incrementally, the same way the substrate was built.

## Orientation (do this first — V2 protocol)

1. Read `CLAUDE.md` (root) — esp. the v2 session-orientation protocol, the
   Model-A branch protocol, real-time governance, and requirements-provenance.
2. Read the memory note **`project_prj030_release_pipeline.md`** — it has the full
   build history, every PI, the commits, and this exact handoff.
3. The PRD / source of truth is **`PRDs/product/crmbuilder-v2/multi-agent-release-pipeline-architecture.md`**
   (reference book RB-014, topic TOP-094). Read §5.1, §7, §10 (the two agent
   orgs), and the per-PI architecture docs `pi-2NN-*.md` in the same folder.
4. Orient on the live DB (API on `127.0.0.1:8765`, header `X-Engagement: CRMBUILDER`):
   `get_current_status`, recent sessions, and the release-pipeline projects
   PRJ-029…034. Start the API with `crmbuilder-v2-api &` if needed.
5. Read the existing agent infrastructure you will build on (do NOT rebuild it):
   - **Agent Profile Registry (PI-122)** — `agent-profile-registry/` PRD;
     `access/repositories/registry_resolver.py` (resolve-contract) +
     `registry_lifecycle.py`. Holds agent profiles / skills / governance rules /
     learnings, system|engagement scoped.
   - **ADO runtime** — `runtime/ado_runtime.py`, `runtime/parallel_runtime.py`,
     the `crmbuilder-v2-ado` CLI; PI-γ principals + `mint_agent_principal`.
   - **ADO evolution design** — `agent-delivery-organization-evolution.md`
     (matrix org, Architect/Developer/Tester tiers, finding/learning entities).

## What is already built (the substrate — DO NOT rebuild)

Every release-pipeline PI (PI-203…216, all Resolved) across PRJ-029…034. The
access modules and their gates:
- `releases.py` — the Release entity + the staged-pipeline `transition()` with all
  gates (freeze, planned-completely, single-occupancy, qa/test, ship-cascade).
- `reconciliation.py` (+ pure `access/reconciliation.py`) — `reconcile_release`,
  conflict store, `resolve_conflict`. Resolved values fold into the delta-set.
- `planning.py` — `author_designs` (reconciled delta-set → vN+1) +
  `planning_readiness` + `plan_release`.
- `artifact_versions.py` — versioned designs; `live` = latest shipped.
- `coordination.py` — lane occupancy + single-owner-per-area.
- `freeze.py` — derived frozen-ness enforcement.
- `reopen.py` — area reopen, pause/resume, cascade re-validation, blast-radius
  approval tiers.
- `locks.py` — file/named-resource check-out/verify/reclaim (FL-1..6).
- `planning_area_claims` — single-threaded-by-area planning claims (PI-207).

The substrate is API-drivable and tested; the end-to-end walkthrough (a script that
drove a release through all 11 stages) confirmed every gate fires.

## The gap to close — the three agent seams

The walkthrough had to do three things by hand. Those ARE the agent layer:

1. **Demands authoring.** The structured requirement→design deltas that feed
   `reconcile_release` (`{requirement, artifact_type, artifact_identifier, field,
   facet, op, value}`) are currently *input*. Build the path that produces them —
   an interview/agent that reads a release's confirmed requirements and emits the
   deltas. **This is the biggest unknown; design it carefully.**
2. **Work-task decomposition.** `planning.author_designs` writes vN+1, but the
   judgment of *what work tasks, in what order* is not done. The Architect /
   area-planning-specialist agents produce the workstreams + sequenced work tasks
   that satisfy `planning_readiness`. (Note: the ADO structural decomposer refuses
   `execution_mode=interactive` PIs — DEC-425 — so reconcile this with how the
   release-pipeline PIs are decomposed.)
3. **The orchestration loop + agents.** Nothing drives the stages. Build the
   planning org (Architect Planning Agent → area specialists, consuming PI-207
   area claims) and the development org (lead → area specialists → sub-agents
   under the PI-203 file lock), as **Agent Profile Registry profiles** (PI-122)
   resolved + spawned by a **runtime** (extend the ADO scheduler).

## Scope decisions to make in a DESIGN pass FIRST (don't code blind)

- **Demands authoring**: agent-from-requirements vs an interview vs a derivation
  rule? Where do facet-level deltas come from given today's requirement records?
- **Reuse vs new runtime**: extend `parallel_runtime.py`/`ado_runtime.py`, or a
  release-pipeline-specific scheduler? How do release stages map to ADO phases?
- **Profiles**: which (area × tier) cells get profiles; what each contract is.
- **Boundary**: PI-209 Option A is the deterministic spine; the agent layer wraps
  it — keep that split.

## How to work (conventions)

- **Design-first, per unit**: an architecture doc → governed requirements (origin
  `ai_derived`, status `candidate`) → **Doug signs off in the Review panel** →
  build → tests green + `ruff` clean → commit → merge → Model-A build-closure
  (resolve the PI on `main`). This is exactly the cadence the substrate used.
- **Governance in real time** via direct API POST (Claude Code); decisions with
  options + rationale; requirements traced to a topic + conversation. New work
  likely lands under **PRJ-033 (Planning Agent Org)**, plus PRJ-029/030 for the
  dev-org/file-lock runtime; create new PIs as needed (`blocked_by` the substrate
  PIs, all Resolved).
- **Branch protocol (Model A)**: `pi-NNN` branch carries code only; build-closure
  + PI resolution happen on `main` after merge. Commit with explicit pathspec.
- **Validate**: run `uv run pytest tests/crmbuilder_v2/access -q` (+ api) after
  each PI; validate migrations via create_all + stamp + upgrade (the from-scratch
  chain is blocked at 0004 by the gitignored catalog — known).

## Suggested first move

Do an **agent-layer architecture pass**: confront the three seams (esp. demands
authoring), decide the scope decisions above with options, decompose into PIs, and
record it as governance — *before* writing code. Then build the smallest valuable
slice end-to-end (recommended: the **demands-authoring + decomposition for one
release**, so the existing substrate runs with real agent-produced input), prove it
against a real release, and iterate.

## Key references

- Memory: `project_prj030_release_pipeline.md`, `project_v2_specs_live_in_db.md`,
  `project_pi123_stage2_3_done.md`, `feedback_v2_governance_realtime.md`.
- PRD: `multi-agent-release-pipeline-architecture.md` (§5.1, §7, §10) + `pi-2NN-*.md`.
- Agent infra: `agent-profile-registry/`, `agent-delivery-organization-evolution.md`,
  `runtime/ado_runtime.py`, `runtime/parallel_runtime.py`.
- Proof it works: the end-to-end walkthrough (`/tmp/walkthrough.py` pattern, or
  re-derive from the access modules above).
