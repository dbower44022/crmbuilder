# Agent / Orchestrator Documentation Archive

This directory collects **all the documentation written while building the
CRMBuilder v2 agent / orchestrator (ADO) system and the multi-agent release
pipeline.** It was assembled on 2026-06-20 to be the single source pile for a
consolidation pass that produces a clean overview + technical reference (see
`../CLAUDE-CODE-PROMPT-consolidate-agent-docs.md`).

**Important:** these documents span an *evolving* design and were written at
different times. Many are superseded in part by later ones, and the taxonomy
changed mid-stream (e.g. the old "Phase Specialist / Area Specialist" tiers map
to the newer "Architect / Developer / Tester" tiers; "Workstream" was renamed to
"Project" and then re-used for a delivery phase; `SES-`/`CONV-` identifier
meanings shifted). **The live V2 database and the actual code under
`crmbuilder-v2/src/crmbuilder_v2/` are the ground truth for what is currently
built** — these docs are the design/build narrative behind it.

## What's here, grouped

### Top-level design & architecture (the spine)
- `agent-delivery-organization-design.md` — the ADO substrate: four agent tiers (PM / PI Lead / Phase Specialist / Area Specialist), how work decomposes into Workstreams → Work Tasks.
- `agent-delivery-organization-evolution.md` — the agent-layer redesign: matrix org, Architect/Developer/Tester tiers, phase-major + reconciliation gate, standing learning experts, release batching, spawn-on-demand runtime.
- `agent-pipeline-annotated-map.md` — annotated map of the whole agent pipeline.
- `orchestrator-planning.md`, `orchestrator/overview.md`, `orchestrator/child-agent-kickoff-template.md` — the parallel orchestrator design + the template used to brief a spawned child agent.

### Runtime (the schedulers that actually spawn & coordinate agents)
- `coordinating-runtime-layer1-build-notes.md` — serial spawn/verify/merge (Layer 1).
- `coordinating-runtime-layer2-build-notes.md` — concurrency-safe parallel pool (Layer 2).
- `ado-orchestration-driver-slice1/2/3-build-notes.md` — the PI-level scheduler driving the loop.
- `ado-agent-layer-completions-build-notes.md` — completion of the agent layer over the substrate.
- `pi-157-ado-runtime-resume-design.md` — resume/persistence across runs.
- `migration-lock-build-notes.md` — exclusive migration lock that pauses dispatch during a migration.
- `pi-145-atomic-phase-merge-design.md` — all-or-nothing phase merge.
- `pi-147-phase-verification-runs-affected-tests-design.md` — verification runs affected tests, blocks merge on breakage.
- `findings-entity-build-notes.md` — the `finding` entity + reconciliation gate.
- `kickoff-concurrency-promoted-records-and-substrate.md` — concurrency for promoted records (WS-012 orchestrator).

### Multi-agent release pipeline (PRJ-030)
- `multi-agent-release-pipeline-architecture.md` — overall release pipeline.
- `release-pipeline-agent-layer-architecture.md` — the agent layer driving releases.
- `pi-203-file-lock-architecture.md` — file-level locks for agent coordination.
- `pi-204-coordination-architecture.md` — single-occupancy / area ownership.
- `pi-205-release-entity-architecture.md` — the Release entity & staged pipeline.
- `pi-206-qa-test-levels-architecture.md` — QA / test levels.
- `pi-207-two-temperature-planning-architecture.md` — planning vs development windows.
- `pi-208-versioning-spine-architecture.md` — artifact versioning.
- `pi-209-planning-org-architecture.md` — planning org for reconciliation/versioning.
- `pi-211-plan-freeze-inviolability-architecture.md` — plan-freeze enforcement.
- `pi-212-area-reopen-architecture.md` — reopening a frozen area.
- `pi-213-cascade-revalidation-architecture.md` — cascade revalidation on change.
- `pi-214-reopen-approval-architecture.md` — reopen approval flow.
- `pi-215-reconciliation-engine-architecture.md` — the reconciliation merge engine.
- `pi-216-freeze-enforcement-architecture.md` — freeze enforcement.
- `REL-005-forensic-agent-trace.md` — a forensic trace of an actual pipeline run.

### Agent Profile Registry (the agents' skills/rules/learnings store)
- `pi-122-agent-profile-registry-architecture.md` — the registry architecture.
- `agent-profile-registry/agent-profile-registry-PRD-v0.1.md` — the registry PRD (living knowledge base, system|engagement scope, cross-engagement learning).
- `agent-profile-registry/profiles/*.md` — proven tier prompt profiles (development-phase-specialist, area-specialist).
- `agent-profile-registry/illustrative/*` — illustrative schema, runtime, migrations, seed, smoke test.

### Work-unit lifecycle schema specs (the records agents produce/consume)
- `governance-schema-specs/workstream.md` — the delivery-phase Workstream entity & its lifecycle states.
- `governance-schema-specs/work_ticket.md` — the kickoff Work Ticket.
- `governance-schema-specs/close_out_payload.md` — the close-out payload.
- `governance-schema-specs/deposit_event.md` — the apply/deposit event.

### Planning / build prompts
- `CLAUDE-CODE-PROMPT-agent-architecture-walk-part2.md`, `CLAUDE-CODE-PROMPT-agent-skills-and-guardrails-planning.md` — architecture-walk / skills-and-guardrails planning prompts.
- `prompts/*` — the orchestrator / release-pipeline / state-model build prompts (HANDOFF-WTK-001 ADO state-model substrate, release-pipeline-agent-layer, pi-025 orchestrator end-to-end, pi-081 orchestrator execute, pi-023 workstream-state reconciliation).

### Raw source
- `Agent Detailed Overview.md` — a raw terminal transcript of an agent-architecture planning session (noisy; mine for intent, not authority).

## Not moved here (referenced in place)
Shared substrate/infrastructure the agents *run on* but which is not the agent
system itself — left in `PRDs/product/crmbuilder-v2/`: the broader governance-entity
PRDs/plans, the unified-DB + Postgres foundation (`pi-123-*`, `pi-alpha-*`,
`pi-beta-*`, `pi-gamma-*`), `governance-redesign-target-model.md`, `pi-112-execution-plan.md`,
and the requirements-provenance docs. The consolidation prompt lists the specific
ones to read in place.
