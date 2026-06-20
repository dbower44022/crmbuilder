# Claude Code Prompt — Consolidate the Agent / Orchestrator Documentation

## Why you're here

The documentation describing how CRMBuilder v2's **agent / orchestrator (ADO)
system** and **multi-agent release pipeline** were built has sprawled across ~57
files written at different times across an evolving design. It's become
overwhelming. Your job is to read all of it, reconcile it against what is
*actually built*, and produce **two clean, authoritative documents** that
replace the need to wade through the archive.

You are **not** changing any code or any design. This is a documentation
synthesis task: read → reconcile → write two new docs.

## The two deliverables

Write both into this directory:
`/home/doug/Dropbox/Projects/crmbuilder/PRDs/product/NEW-Master PRDs/Agent PRDs/`

### Deliverable 1 — `Agent-System-Overview.md` (the "explain it simply" doc)
A **very high-level overview** of what the agents do and the process they
follow. Audience: a smart person who knows nothing about this system. Goals:
- A plain-language narrative of the whole thing: what problem the agent system
  solves, who the "agents" are, how a piece of work travels from an idea to
  shipped code through the agent pipeline, end to end. Use an analogy (e.g. a
  software company with managers, leads, and specialists) and keep it concrete.
- A simple diagram (Mermaid flowchart or a clean ASCII diagram) of the flow:
  idea/requirement → planning → decompose → phases → agents do the work →
  reconcile → merge → release/ship. Show where the runtime, the registry, the
  locks, and the reconciliation gate sit.
- **A complete glossary.** Every term, entity, role, tier, status, and acronym
  the system uses gets an entry, and **each definition is written as if
  explaining it to a five-year-old** — one or two short sentences, no jargon,
  with a tiny everyday analogy where it helps. Terms to cover include at least:
  ADO, agent, agent tier, Project Manager / PI Lead / Phase Specialist / Area
  Specialist, Architect / Developer / Tester, orchestrator, runtime / scheduler,
  coordinating runtime, parallel runtime, Project (PRJ), Planning Item (PI),
  Workstream (the delivery phase, WSK) vs the old "workstream", Work Task (WTK),
  Work Ticket (WT), area (System area vs Engagement area), phase (Plan / Design /
  Develop / Test, or Architecture/Development/Testing/...), Release (REL),
  reconciliation, finding (FND), plan freeze, area reopen, cascade revalidation,
  file lock / resource lock, Agent Profile Registry, agent profile (AGP), skill
  (SKL), governance rule (GVR), learning (LRN), close-out payload, deposit event,
  decomposition, scoping, dispatch, claim, the gate model statuses, blocked_by,
  needs_attention, engagement, contract / version stamp, spawn-on-demand. Add any
  others you encounter. Order the glossary so a beginner can read it top to
  bottom (foundational terms first), not strictly alphabetical — or provide both.

Keep Deliverable 1 readable in one sitting. No code. Favor clarity over completeness of edge cases.

### Deliverable 2 — `Agent-System-Technical-Reference.md` (the component-by-component doc)
A **detailed technical overview of each component** of the design. For **every**
component, document a consistent template:
- **Name & one-line purpose.**
- **What functionality it provides** — what it's responsible for.
- **Triggers** — what causes it to run / fires it (an API call, a runtime tick, a
  prior phase completing, an operator action, etc.).
- **Inputs** — what it reads/consumes (records, edges, prior-phase outputs, env).
- **Outputs** — what it writes/produces (records, edges, commits, merges, logs,
  contracts, findings).
- **States** — the lifecycle states the component or the records it manages can
  exist in, and the legal transitions between them. Be exact about status
  enums and gates.
- **Where it lives** — the real module(s)/endpoint(s) in code (path + symbol).
- **Interactions** — which other components it calls or hands off to.

Components to cover (at minimum — discover the full set as you read):
- The **agent tiers** (PM / PI Lead / Phase Specialist / Area Specialist; and the
  Architect / Developer / Tester evolution) and their substrates.
- The **orchestrator** and the **runtimes**: coordinating (serial Layer 1),
  parallel (Layer 2), the ADO PI-level driver, the release runtime.
- **Decomposition** and **scoping**.
- **Dispatch / claim / release** of Planning Items and Work Tasks.
- The **gate model**: Planning Item six-state lifecycle, Workstream lifecycle,
  Work Task lifecycle, the `blocked_by` serial chains, `needs_attention`.
- **Reconciliation** and the **finding (FND)** entity + the reconciliation gate.
- **Concurrency**: file locks / resource locks, the migration lock, single-occupancy.
- The **multi-agent release pipeline**: Release entity, staged pipeline, QA/test
  levels, two-temperature planning, versioning spine, plan freeze + freeze
  enforcement, area reopen + reopen approval, cascade revalidation, the
  reconciliation engine.
- The **Agent Profile Registry**: agent_profile / skill / governance_rule /
  learning entities, the resolver (effective contract + version stamp), the
  write-back lifecycle (capture → accumulate → promote → curate), system|engagement
  scope merge, cross-engagement promotion.
- **Work-unit records** the agents produce/consume: Work Ticket, close-out
  payload, deposit event.

Use tables for the state machines. Cross-reference Deliverable 1's glossary
rather than re-explaining basics.

## How to do it — read order & ground truth

1. **Start with the archive manifest:** read
   `Archive/README.md` in this directory — it groups all 57 archived files and
   flags that the design evolved (superseded parts, taxonomy renames).
2. **Read the design spine, newest-wins:** `agent-delivery-organization-evolution.md`
   supersedes parts of `agent-delivery-organization-design.md`; the
   `pi-203…216` release-pipeline architectures and `multi-agent-release-pipeline-architecture.md`
   are the latest layer. When two docs conflict, prefer the later/more-specific one
   and **verify against code**.
3. **Ground truth is the code and the live DB, not the docs.** The docs are the
   build narrative; some describe aspirational or since-changed designs. Confirm
   the *current* shape against:
   - **Runtime code:** `crmbuilder-v2/src/crmbuilder_v2/runtime/` —
     `ado_runtime.py`, `coordinating_runtime.py`, `parallel_runtime.py`,
     `release_runtime.py`, `dispatcher.py`, `migration_lock.py`, `reconciliation.py`,
     `release_gate.py`, `sub_agent_locks.py`, `agent_runtime.py`.
   - **Substrate repositories:** `crmbuilder-v2/src/crmbuilder_v2/access/repositories/` —
     `pm.py`, `lead.py`, `decomposition.py`, `scoping.py`, `workstreams.py`,
     `work_tasks.py`, `work_tickets.py`, `findings.py`, `reconciliation.py`,
     `releases.py`, `release_demands.py`, `registry_resolver.py`,
     `registry_lifecycle.py`, `registry_seed.py`.
   - **CLI entrypoints** (the real "how it's launched"): `crmbuilder-v2-ado`,
     `crmbuilder-v2-ado-pm`, `crmbuilder-v2-release` (see root `pyproject.toml`).
   - **Status enums / vocab:** grep the models and `access/vocab.py` for the
     actual `*_STATUSES` sets, phase-type vocab, and reference relationship kinds.
   - **The live V2 DB** for the real entities: the REST API at
     `http://127.0.0.1:8765` (start it with `crmbuilder-v2-api &`; send an
     `X-Engagement: CRMBUILDER` header; unwrap the `{data, meta, errors}`
     envelope). Useful reads: `/projects`, `/planning-items`, `/workstreams`,
     `/work-tasks`, `/releases`, `/agent-profiles`, the topic trees. The
     agent-system spec also lives in the DB as a topic/requirement tree
     (`TOP-005`) — see project memory `project_v2_specs_live_in_db.md`.
4. **Reconcile and note evolution.** Where a doc describes something that was
   later renamed or replaced, document the *current* truth in the body and, where
   useful, add a short "(formerly X)" note so a reader meeting an old doc isn't lost.
5. **Don't invent.** If something is designed-but-not-built, or built-but-the-doc-
   is-stale, say so plainly and mark confidence. Prefer "verified in code at
   `path:symbol`" over "the design doc says."

## Cross-references to read *in place* (not in the archive)
These shared-substrate docs stayed in `PRDs/product/crmbuilder-v2/` because they
serve the whole system, but they give essential context for the agent layer:
- `governance-redesign-target-model.md` and `pi-112-execution-plan.md` — the
  Project / Workstream / Work Task / area model the agents operate on.
- `pi-123-unified-db-architecture.md`, `pi-alpha-postgres-foundation-architecture.md`,
  `pi-beta-defile-architecture.md`, `pi-gamma-rbac-architecture.md` — the
  unified multi-tenant DB + agent-principal (`service_agent`) substrate the
  registry's cross-engagement learning depends on.
- The root `CLAUDE.md` sections "Agent Delivery Organization (ADO) substrate",
  "ADO agent-layer evolution", "Agent Profile Registry substrate", and the
  Branch-work / governance-precondition rules — the authoritative current summary.
- Project memory under `/home/doug/.claude/projects/-home-doug-Dropbox-Projects-crmbuilder/memory/`:
  `project_prj030_release_pipeline.md` (the release pipeline's current built
  state), `project_ado_orchestration_driver.md`, `project_coordinating_runtime_layer1.md`,
  `project_coordinating_runtime_layer2.md`, `project_pi133_pi134_built.md`,
  `project_pi123_stage2_3_done.md`, `project_v2_specs_live_in_db.md`.

## Style & constraints
- Markdown only (per the repo's MD-going-forward rule).
- Use full absolute or repo-relative paths when naming files (this repo has
  thousands of files; bare filenames are ambiguous).
- Deliverable 1 = plain language, glossary ELI5. Deliverable 2 = precise,
  tabular, code-anchored. Keep them as two separate files.
- Mermaid is fine for diagrams.
- This is documentation only — make no code changes and no governance records.
  (Writing two reference docs is below the requirement threshold; state that
  explicitly if anyone asks, rather than assuming it.)

## Definition of done
- `Agent-System-Overview.md` exists with: narrative, one flow diagram, and a
  glossary where every term is defined ELI5.
- `Agent-System-Technical-Reference.md` exists with: every component documented
  under the {purpose, functionality, triggers, inputs, outputs, states, location,
  interactions} template, with state-machine tables.
- Every nontrivial claim is anchored to a code path/symbol or a live-DB read, not
  just to a design doc — and conflicts between docs are resolved in favor of code.
- A short "Sources" section at the end of each doc lists which archived files and
  code modules it drew from.
