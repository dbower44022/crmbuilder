# Kickoff — Agent architecture walk, part 2 (continue from SES-216)

**Session type:** design / planning discussion with Doug (interactive, not a build).
**Project:** PRJ-039 "Release Pipeline Agent Hardening" (+ PRJ-040 "Process Pipeline
Improvements" for observability).
**Topic:** TOP-099 "Release Pipeline Agent Guardrails" (+ TOP-100 "Pipeline
Observability and Progress Reporting").
**Predecessor session:** SES-216 (conversation CNV-137 hardening / CNV-138 observability).
**Origin:** the REL-005 dev-lane run burned ~$40 / ~2 hours rebuilding already-shipped
work. The forensic root-cause is `REL-005-forensic-agent-trace.md`.

## How Doug wants this session run (STANDING RULES — read first)

1. **One issue at a time.** Bring a single decision, discuss it to resolution, *then*
   move to the next. Never batch several decisions into one prompt or one
   AskUserQuestion block. (Memory: `feedback_one_issue_at_a_time_discuss`.)
2. **Plain language.** Explain like he's smart but not in the code — translate jargon
   (delta-set, workstream, vN+1, etc.) into plain terms. He will stop you if you drift
   into "mumbo jumbo."
3. **Dedup before authoring — ALWAYS.** Before writing ANY new requirement, check it
   against the confirmed **TOP-005 Agent System** tree (it has ~96 agent-related
   requirements; most of the architectural vision is already confirmed there). If it
   overlaps, refine/link/amend the existing one — do not restate it. This is a hard
   rule he enforced repeatedly in SES-216.
4. **Requirement-first governance; design & decide, don't build.** Author requirements
   (candidate) and decisions in the live V2 DB **in real time via direct API POST**
   (Claude Code default — not a close-out payload). Nothing gets built until the
   requirement is **approved in the Requirements Review panel**. Doug reviews the topic
   himself.
5. **Governance mechanics that bit in SES-216** (so you don't relearn them):
   - `POST /requirements` rejects an `identifier` field; provenance attaches via
     separate `POST /references` (`requirement_belongs_to_topic` + `requirement_defined_in_conversation`).
   - `POST /conversations` needs its `conversation_belongs_to_session` edge inline; reserve
     the id via `/conversations/next-identifier`, then POST with `references:[...]`.
   - Decisions need `title`, `decision_date`, `status`, `executive_summary` (200–800 chars),
     `context`, `decision`.
   - **Rejecting** a requirement requires a `rejected_by_decision` edge first (then PATCH
     status `rejected`). **Changing a confirmed** requirement: POST a
     `requirement_changed_by_decision` edge → it AUTO-reopens the req to
     `candidate`/`needs_review`; then PATCH the narrowed text.
   - Refinement links: `requirement_refines_requirement` (source = the new/specific child,
     target = the confirmed parent).
   - All API calls send `X-Engagement: CRMBUILDER`; unwrap the `{data,meta,errors}` envelope.

## Where the walk is (the map so far)

Two stacked org models drive a release (full map in SES-216 transcript / the design canon):
- **Layer A — the conductor** (`runtime/release_runtime.py`): a status-driven step
  machine. Initiated by pointing it at ONE **frozen** release whose scope
  (projects → PIs → confirmed requirements) is already assembled by a human. Pipeline
  position = the single `release_status` column; 12 states; freeze gate
  (`development_planning → reconciliation`) splits human planning from conductor execution.
- **Layer B — two LLM planning agents** (fixed seams, not queue-dispatched):
  - **Reconciliation/Demands agent** = profile **AGP-003** (model/architect) — produces
    the demand-set (the change-list). One-shot structured-output call; the prompt
    over-describes its authority (claims to reconcile/resolve conflicts, which the
    conductor + a human actually do).
  - **Architect/Decomposition agent** = profile **AGP-004** (planning/architect) —
    produces the blueprint (vN+1 designs) + the build plan (workstreams/work tasks).
- **Layer C/D — the ADO dev-org**: PM → PI Lead → Phase Specialist (all deterministic
  substrate) → **Area Specialist** = the spawned `claude -p` workers. Only **5 profiles
  exist** (AGP-001..005); the ONLY worker profile is **AGP-002 (storage/developer)**, so
  every area's worker gets a storage card with `{AREA}` pasted in — no per-area dev/tester
  profiles, no enforced area constraints.

**Covered in SES-216:** conductor → reconciliation agent → architect → worker → verify/merge
→ phase gate (PI Lead `complete_phase`) → cross-area coherence gate.

**Key structural findings established:**
- Almost **no content verification anywhere** — only format/schema checks + a contradiction
  catcher; agents are told to TRUST inputs.
- The **worker** is where most guardrail gaps live (no step-0, no done-condition, wrong-area
  card, commit-after-work, unbounded self-verify, no halt path).
- The **phase gate** advances purely on "all tasks Complete"; the confirmed **coherence
  check (REQ-027/031) is unbuilt** — its substrate (the `finding` entity, PI-134) exists but
  is not wired into `lead.complete_phase`.
- **Observability is fragmented**: durable position in DB records, ephemeral stdout
  (conductor `ReleaseRunReport`, runtime `self.log` defaults to `print`), and rich agent
  reasoning in scattered `~/.claude` transcripts. No single durable progress log.

## NEXT — resume the walk here

1. **Release-level gates** (`release_runtime`): once all in-scope PIs are delivered,
   Develop → **QA gate** → Test → **test gate** → deployment → ship. How the whole release
   graduates; the gate-runner seam (`AGP-005` release/pi_lead, the LLM Release Lead); what
   "the release is done" actually checks. (Walk this first.)
2. **The deferred verification-ownership fork** (raised early in SES-216, not settled):
   should the *agent* self-verify at all, or should the *runtime* own the affected-tests
   gate and feed the agent the result? The runtime already owns
   `select_test_target`/`run_pytest`/`verify_result`. Now more answerable given REQ-283.
3. **Whole-picture annotated view** — the full agent structure with every gap/decision
   marked.
4. **Turn approved requirements into a build order** — per-(area,tier) `agent_profile`
   redesign (the worker-contract template below) + the runtime changes, once requirements
   are approved.

## Deliverable seed — the proper worker contract (from SES-216, refine don't restart)

A worker (area-specialist) contract template was sketched. Sections, with fill-source:
- **A. Identity** `[area-specific]` — `(area × technology × tier)`; the routing key.
- **B. Role & scope** `[fixed + area fill]` — does X; MUST NOT re-scope/re-architect/cross areas.
- **C. Step 0 — validate before building** `[fixed]` — input sanity + already-done check → no-op exit.
- **D. Hard guidelines** — D1 universal `[fixed]` + **D2 area/technology constraints**
  `[area-specific: framework, design-system/palette, conventions, testing idioms]`.
- **E. Deliverable & done-condition** `[per-task/per-batch — emitted by the architect]`.
- **F. Operating sequence** `[fixed]` — validate → implement → **commit-first** → bounded
  synchronous verify (time budget) → report → exit.
- **G. Halt / escalate** `[fixed]` — set workstream `needs_attention` + reason; never produce filler.
- **H. Reporting requirements** `[fixed shape]` — outcome class / files / done-condition result /
  commit SHA / halt reason — the durable record feeding observability.

The split (system owns the skeleton; each area card owns D2 + identity; the architect owns E)
is the design: it implies the architect must emit acceptance criteria, and the registry must
hold per-area D2 blocks. **Under REQ-283 the unit is an area-phase batch, so E is a SET of
acceptance criteria, not one.**

## Governance authored in SES-216 (current state — read before adding more)

New/changed requirements (all candidate unless noted; check live status before relying):
- **PRJ-040 / TOP-100:** **REQ-277** — pipeline progress & agent activity durably
  reported and queryable (refines REQ-014).
- **PRJ-039 / TOP-099 — the keystones:**
  - **REQ-278** — every agent has a strict, documented contract in the DB (role, hard
    guidelines, deliverables, reporting; must match actual behavior). Refines REQ-021.
  - **REQ-279** — *a receiving agent validates its inputs before starting* (narrowed to the
    receiver half; conductor-side verification is confirmed REQ-057). Refines REQ-057.
  - **REQ-280** — build-area agents encode hard technical/design constraints in their
    contract. Refines REQ-021.
  - **REQ-281** — the agent model supports multiple technology variants within one
    functional area (Desktop UI vs Web UI, coexisting in one project). Refines REQ-018.
  - **REQ-283** — an area expert builds its whole area for a phase as one batch across the
    release (option B; size-capped). Refines REQ-061; precedent REQ-208. (DEC-554.)
  - **REQ-273** (orig twelve) — area-match, linked refines REQ-252.
  - **REQ-274** (orig twelve) — narrowed to "decomposition re-validated as well-formed
    *before execution*"; refines confirmed REQ-258.
  - **REQ-282 — REJECTED** as a duplicate of confirmed REQ-004/044/045/046/047/006/252
    (system-default team + per-engagement customization + build-area profiles). (DEC-553.)
- **Amended confirmed requirements (now `needs_review` — Doug re-approves in panel):**
  - **REQ-024** — narrowed to area-detection + pass-layout; batch unit defers to REQ-283. (DEC-555.)
  - **REQ-027 / REQ-031** — coherence check amended per-PI → **release scope** (hard-gate
    semantics kept; gate is confirmed-but-UNBUILT — a PRJ-039 build gap). (DEC-556.)
- **Decisions:** DEC-552 (keep REL-005 fleet, don't revert — it's published on origin/main),
  DEC-553 (dedup disposition), DEC-554 (batch unit B), DEC-555 (amend REQ-024), DEC-556
  (amend REQ-027/031).

The genuinely-new SES-216 contribution after dedup: **REQ-277, 278, 280, 281, 283** + the
279/274 slivers. Everything else refines or amends confirmed TOP-005 requirements.

## Carried-in / out-of-scope reminders

- **PI-230/231 stale decompositions + REL-005 unstick** are owned by a *concurrent* session
  — do NOT touch that tree/DB area.
- **Do not re-run the dev-lane** until at least REQ-265 / REQ-267 / REQ-272 land.
- Requirement-first remains binding: this session designs & decides and authors
  requirements/decisions — it does not write pipeline code.

## Orientation reads (Tier 1–4)

1. `REL-005-forensic-agent-trace.md` (the failure modes G1–G8, full).
2. The TOP-099 requirements (Requirements Review panel) + the SES-216 governance above.
3. The runtime seams: `runtime/release_runtime.py` (conductor, gates, the two provider
   seams + `_DEMANDS_SYSTEM`/`_DECOMPOSE_SYSTEM`), `runtime/coordinating_runtime.py`
   (`operating_protocol`, `spawn_claude_agent`, `verify_result`, `select_test_target`/
   `run_pytest`), `runtime/dispatcher.py` (`select_profile_id` area fallback),
   `runtime/agent_runtime.py` (contract assembly), `access/repositories/registry_resolver.py`,
   `access/repositories/lead.py` (`start_phase`/`complete_phase` — the phase gate).
4. The live profiles AGP-001..005 (`GET /agent-profiles/AGP-00N/contract?engagement=CRMBUILDER`).
5. The ADO design canon: `agent-delivery-organization-design.md`,
   `agent-delivery-organization-evolution.md`, the Agent Profile Registry PRD
   (`agent-profile-registry/`) — being updated to reflect the SES-216 decisions.
