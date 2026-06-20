# Kickoff — In-depth planning: skills & guardrails for each pipeline agent type

**Session type:** design / planning discussion with Doug (interactive, not a build).
**Project:** PRJ-039 "Release Pipeline Agent Hardening".
**Topic:** TOP-099 "Release Pipeline Agent Guardrails".
**Origin:** the REL-005 dev-lane run burned ~$40 / ~2 hours on two trivial
requirements — re-building already-shipped work, over-scoped decomposition, a
30-minute agent verification spin, and an inherited stale decomposition. The full
root-cause is traced agent-by-agent in the forensic report.

## Goal of this session

A **structured, in-depth design discussion** that defines, for **each agent type in
the multi-agent release pipeline**, its:

1. **Skills** — what this agent is *for*; the narrow job it does well.
2. **Instructions / contract** — the exact prompt it receives (system role, operating
   protocol, the per-task block).
3. **Acceptance criteria** — how *this* agent knows it is done (the gap the REL-005
   contracts entirely lacked).
4. **Guardrails** — its stop-conditions and escape hatches: no-op-when-already-done,
   halt-and-escalate-on-anomaly, bounded/synchronous verification, commit-before-verify,
   time budget, area-match.

The output is a **per-agent-type contract design doc** that becomes `agent_profile`
records (system-scoped) in the Agent Profile Registry, plus any additional requirements
beyond the twelve already authored.

## Read first (Tier 1–4 orientation)

1. **The forensic trace — read this in full:**
   `PRDs/product/crmbuilder-v2/REL-005-forensic-agent-trace.md`. It contains the
   identical agent contract template, both LLM planning layers, all 16 agents'
   instruction-vs-action records, the WTK-176 spin anatomy, and the G1–G8 redesign.
2. **The twelve hardening requirements** already authored as candidates under TOP-099
   (REQ-265…276) — the structural backbone this discussion refines into per-agent detail.
   Read them in the Requirements Review panel (topic TOP-099); approve or amend before
   building anything from them.
3. **The current agent contract + registry (the thing being redesigned):**
   - `crmbuilder-v2/src/crmbuilder_v2/runtime/coordinating_runtime.py` —
     `spawn_claude_agent` (the `claude -p` spawn + 1800s timeout), `_assignment_for`
     (contract assembly), the operating-protocol text, `select_test_target`/`run_pytest`.
   - `crmbuilder-v2/src/crmbuilder_v2/runtime/parallel_runtime.py` — the pool, the
     timeout/retry, `_integrate`/`verify_result`.
   - `crmbuilder-v2/src/crmbuilder_v2/runtime/agent_runtime.py` — how the registry
     contract + enforced gates + per-task block are composed into the final prompt.
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/registry_resolver.py` +
     `dispatcher.py` (`select_profile_id` — the area/tier fallback that mis-fit a ui
     task to a storage profile).
   - The live `agent_profile` rows (only 5 exist: AGP-001..005; **no per-area
     developer/tester profiles** — that gap is REQ-273's subject).
4. **The LLM planner seams:** `runtime/release_runtime.py` — `anthropic_providers()`,
   `_DEMANDS_SYSTEM`, `_DECOMPOSE_SYSTEM`, `_confirmed_requirements`, `_plan`, and the
   `_Decomposition`/`_Workstream` Pydantic schemas (the unconstrained `list[_Workstream]`
   that let the architect emit duplicate phase triples).
5. **The ADO design canon:** `agent-delivery-organization-design.md`,
   `agent-delivery-organization-evolution.md`, and the Agent Profile Registry PRD
   (`agent-profile-registry/`).

## The agent types to design (the agenda)

Work through each; for each, settle skills / instructions / acceptance criteria / guardrails:

1. **Reconciliation (Demands) agent** — model-area architect tier. Input discipline
   (must not see already-delivered requirements), output = the demand-set.
2. **Architect (Decomposition) agent** — planning. Single-item scope, one-phase-each,
   canonical order, proportionate task count, skip-already-built.
3. **Area Specialist — Architect tier** — design-area work.
4. **Area Specialist — Developer tier**, *per area* (storage / access / api / mcp / ui /
   methodology-*). Each area has different idioms (Qt vs SQLAlchemy vs FastAPI) — decide
   whether profiles are per-area, and what each one's orientation cues / acceptance test
   discipline should be.
5. **Area Specialist — Tester tier** — verification discipline (synchronous, bounded,
   scoped to touched files, Qt-flake handling), and what "tested" means per area.
6. **Release Lead / Gate runner** — the QA/test integration gates.
7. **PI Lead / PM (orchestration tiers)** — phase gating, needs-attention rollup, the
   halt/escalate routing that area agents feed.

## Cross-cutting design questions to resolve

- **The universal "step 0" check** — how does every agent cheaply determine "is my task
  already satisfied?" and what does the no-op exit record? (REQ-267)
- **The halt/escalate path** — what does an agent call to stop and raise needs-attention,
  and what does the orchestrator do with it? (REQ-272) The substrate has
  `workstream_needs_attention`; wire agents to it.
- **Verification ownership** — should the *agent* self-verify at all, or should the
  *runtime* own the affected-tests gate and feed the agent the result? (REQ-269/270/271;
  the WTK-176 spin was the agent polling its own background test run.)
- **Acceptance criteria source** — where does each work task's done-condition come from?
  (Today the task description is the only signal and it had none.) Should the architect
  emit explicit acceptance criteria per task?
- **Profile coverage** — seed real per-(area,tier) profiles, or make the dispatcher
  refuse a mismatch? (REQ-273)
- **Fan-out economics** — per-agent full-repo context reload is the scaling cost driver;
  decide scoping (file globs fed to the agent?) and proportionate task counts. (REQ-276)

## Deliverables of this session

1. A design doc — `agent-skills-and-guardrails-design.md` — one section per agent type
   (skills / instructions / acceptance / guardrails), plus the cross-cutting decisions.
2. Any **additional requirements** under TOP-099 the discussion surfaces (the twelve are
   the floor, not the ceiling).
3. The decisions recorded (governed), and a build order for turning the approved
   requirements into agent_profile records + runtime changes.

## Open actions carried in (not yet decided — raise with Doug early)

- **REL-005 keep-vs-revert:** the 32 fleet commits are **local only** (`origin/main` at
  `2fc432b0`). Local `main` carries real green code for REQ-249/REQ-242 plus redundant
  REQ-251 rework. Decide: revert to `2fc432b0`, or keep + finish.
- **Stale decompositions:** PI-230/231 still carry the malformed 17:50 decompositions
  (the deadlock source). Reset them before any re-run of PRJ-037.
- **Do not re-run the dev-lane** until at least REQ-265 (exclude delivered),
  REQ-267 (no-op exit), and REQ-272 (halt) land — those kill the redundant-work mode.

## Governance

Requirement-first remains binding: nothing gets built from this discussion until the
relevant requirement is **approved in the Review panel** and an implementing planning
item exists under PRJ-039. This session's job is to *design and decide*, then author the
requirements/decisions — not to write pipeline code.
