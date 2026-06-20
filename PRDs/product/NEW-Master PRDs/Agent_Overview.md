# Agent Architecture Planning Session

---

**please read this prompt and then start an in depth architectural planning session where we review the entire agent structure and functionality with the goal of making it more efficient, and reliable. the prompt: CLAUDE-CODE-PROMPT-agent-skills-and-guardrails-planning.md**

---

This is a design/planning session for the agent guardrails hardening project — specifically hardening the release pipeline's multi-agent structure after the costly REL-005 run. Let me orient properly and read the core documents and live database state.

The forensic trace is clear and well-structured. I now have a thorough picture of the whole pipeline after reading the forensic trace in full, the twelve requirements, the contract-assembly path, the LLM planner seams in the release runtime, and the spawn/verify/operating-protocol seams in the coordinating runtime.

Before we design, three things from the carried-in state have changed and one matters a lot:

**Carried-in state — one correction, two confirmations**

⚠️ The keep-vs-revert premise is stale. The kickoff says the 32 fleet commits are local only with origin/main at 2fc432b0. That's no longer true: local main and origin/main are both at 5cdae83e, 33 commits past 2fc432b0. The fleet is already published. So "revert to 2fc432b0" now means rewriting published history, not discarding local commits — a materially bigger, riskier action than the kickoff assumed.

Confirmed — PI-230/231 still hold the malformed decompositions. PI-230 carries WSK-150–153, PI-231 carries WSK-154–159 (the duplicate Design→Develop→Test tracks that deadlocked). REL-005 is still in development status — stuck mid-lane. These must be cleared before any re-run, regardless of what we design.

**What the forensic trace and code tell me about the design**

The twelve requirements map cleanly onto the eight failure modes, and the code confirms each seam exists and is reachable:

| Failure | Req | The actual code seam |
|---|---|---|
| Dispatched already-shipped work | 265 | `_confirmed_requirements` has no Resolved filter |
| Decomposed "the whole release" per PI | 266 | `_plan` passes all delta_sets to every PI; `_DECOMPOSE_SYSTEM` says "one planning item" but is fed everything |
| No "already done → stop" | 267 | operating_protocol step 2 = "Do the work"; no step 0 |
| Design re-documented shipped code | 268 | no NA path; phase always runs |
| 30-min verify spin | 269/270/271 | operating_protocol step 3 commits after work; no time budget; agent self-runs pytest (the runtime already owns select_test_target/run_pytest but doesn't use them for the agent) |
| Couldn't halt a mis-scope | 272 | needs_attention exists on the workstream but agents have no path to set it — only the runtime does, post-hoc |
| ui task → storage profile | 273 | select_profile_id falls back to any tier profile; only AGP-001–005 exist, no per-area dev/tester rows |
| Malformed graph executed | 274/275 | `_plan` skips PIs that already have workstreams — inherits stale graphs |
| 16 agents for 2 trivial reqs | 276 | unconstrained list schema |

The strongest signal in the trace: the runtime already has the verification machinery the agents were spinning on. `verify_result`, `select_test_target`, `run_pytest`, `is_doc_only_change` all live in the coordinating runtime — but the agent is told to self-verify with its own pytest run anyway. That points hard toward one architectural answer.

Before I draft the per-agent design doc, four decisions genuinely shape it and are yours to make: (1) what to do with the REL-005 fleet commits now that they're published, (2) who should own verification — the runtime or the agent, (3) how to close the area-match profile gap, and (4) where each task's acceptance criteria should come from.

---

**One of the rules for our engagement is that you bring one issue to me at a time. So we can discuss.**

---

Got it — one issue at a time, discussed before moving on. I've recorded that as a standing preference.

**Issue 1 of the carried-in actions: what to do with the REL-005 fleet commits**

The situation has changed since the kickoff was written. The kickoff says the 32 fleet commits are local only, with origin/main parked at 2fc432b0 — making "revert" a cheap, private rollback. That's no longer the case. Local main and origin/main are both at 5cdae83e — the fleet is already pushed and published.

That changes the cost of each option:

- Revert now means a force-push that rewrites published history on origin/main. Much riskier, and it throws away the genuinely-good code along with the redundant work.
- Keep costs nothing in history terms — we just clear the stale decompositions and let REL-005 move forward.

What's actually in those 33 commits, per the forensic trace:

- Real, green, wanted code: WTK-174 (review_state→current on approval), WTK-177 (reviewer authorization wiring), WTK-178 (status-counts read process). These are net-new capabilities the release was supposed to deliver.
- Redundant but harmless: the rework that re-documented or added tests to code that PI-229 already shipped. The tests pass; they don't regress anything. The waste was the ~$40/2hr to produce them, which is already spent — reverting doesn't refund it, it just deletes passing tests.

My recommendation: keep + finish. There's no correctness argument for revert — nothing in the fleet is broken or wrong, it's just that some of it was unnecessary. Reverting trades a published-history rewrite for the deletion of working code, to "clean up" effort that's already sunk.

Do you want to keep + finish, or do you see a reason to revert that I'm missing?

---

**I believe they were already pushed by the previous session.**

---

Right — that matches what I found: origin/main is at 5cdae83e, the same as local, so the previous session pushed them. That confirms the keep-vs-revert decision is now a published-history question, not a local-only one.

So the practical picture stands: reverting would mean a force-push rewriting origin/main, deleting working code to undo already-sunk redundant effort — with no correctness benefit. Keeping costs nothing and loses nothing.

My recommendation is unchanged: keep + finish. Do you agree, or do you want to revert despite the publish?

---

**Keep and finish, but I believe the prior session is handling 230/231**

---

Keep + finish it is. And good — if the prior session owns PI-230/231 and the REL-005 unstick, I'll stay out of that tree and database area entirely so we don't collide. I'll treat the "don't re-run the dev-lane until the initial guardrail requirements land" note as a standing constraint, not an action.

I'll record the keep+finish decision in the governance database now, then bring the next issue.

Decision recorded. That closes the carried-in operational actions — keep + finish, and PI-230/231 stays with the other session.

---

**Issue 2: Who owns verification — the agent, or the runtime?**

This is the pivotal fork. Everything about the area-agent contract flows from the answer.

What happened in REL-005 (the 30-minute spin work task): the agent did its real work in ~90 seconds, then spent ~13 minutes launching pytest four times into a background channel whose output file never populated, looping on sleep until a kill discarded everything. The agent was the wrong place to run a slow, flaky Qt suite asynchronously.

The key fact: the runtime already owns the entire verification toolkit and doesn't use it for the agent. In the coordinating runtime:

- `select_test_target(touched_paths)` — maps changed files to the minimal scoped test target
- `run_pytest(worktree_path, target, timeout=...)` — runs it synchronously with a timeout, returns a structured result
- `is_doc_only_change(...)` — skips the gate entirely for doc-only work
- `verify_result(...)` — already decides merge-safety post-hoc

My recommendation: the runtime owns the affected-tests gate; the agent stops self-verifying. The area agent's job becomes: orient → no-op check → implement → commit → exit. No pytest. This removes the poll-loop failure surface entirely.

Where do you land — runtime-owns the gate, or hybrid with a bounded agent smoke?

---

**Whoa... Slow down. I want to discuss the overall architecture of agents before we get into the weeds.**

---

Understood — let's stay at altitude. Let me lay out the whole agent architecture as it actually exists today, so we're looking at the same map before we touch any one piece.

**The agent architecture, end to end**

There are two organizational models stacked on top of each other, and a release flows down through both.

**Layer A — the Release Pipeline** (deterministic step machine)

Not an agent itself — a Python state machine that drives one release: author demands → reconcile → plan/decompose → finalize → enter dev-lane → develop (per PI) → QA gate → test gate → ship. It calls out to agents at four seams. This is the spine.

**Layer B — the LLM planning agents** (the two "thinking" seams the pipeline calls)

1. Reconciliation / Demands agent (model-area, architect tier) — reads the release's confirmed requirements → a structured demand-set.
2. Architect / Decomposition agent (planning, architect tier) — takes a planning item's design deltas → workstreams + work tasks (the Design/Develop/Test phases).

These two are LLM calls, structured-output, one-shot.

**Layer C — the development organization** (executes each planning item inside the dev-lane)

A 4-tier hierarchy, but most of it is deterministic substrate, not LLM agents:
- PM (tier 1) — picks the next eligible planning item, dispatches it. Substrate today.
- PI Lead (tier 2) — phase gating: start phase, complete phase, needs-attention rollup. Substrate today.
- Phase Specialist (tier 3) — decompose + scope a phase into Work Tasks. Substrate today.
- Area Specialist (tier 4) — the actual spawned agents. One Work Task, one area, one tier.

**Layer D — the Area Specialists** (the 16 spawned agents in REL-005)

A matrix: area × tier.
- Areas: storage, access, api, mcp, ui, methodology-product, methodology-process (+ engagement areas).
- Tiers: Architect / Developer / Tester (build areas get all three; design/methodology areas get Architect-only).
- Each boots from a registry contract (agent profile → resolved system prompt + skills + rules + learnings) plus the runtime's operating protocol (claim → work → commit → complete → exit).

A few structural observations worth your eye before any guardrail tuning: (1) LLM judgment lives in only 4 places: demands, decomposition, the area agents, and the QA/test gates. (2) The registry is the contract source of truth — but it's nearly empty, only 5 profiles exist. (3) The two org models overlap confusingly — "Architect tier" means one thing in Layer B and another in Layer D.

What aspect of this overall structure do you want to examine first?

---

**Whoa big fella! Bite size chunks, so we can be sure we understand. So layer A is basically the conductor - It starts the process, and monitors the various agents to make sure they follow the pipeline?**

---

Yes — that's the right mental model, with one important boundary to get precise.

Layer A is the conductor of the release, not of the individual agents. Two things it does:

1. Sequences the pipeline. It walks the release through a fixed order of steps — demands → reconcile → decompose → dev-lane → QA gate → test gate → ship — one step at a time, in order. It won't start a step until the prior one is done.
2. Gates between steps. After each step it checks a result and either continues or halts (pauses for a human). E.g.: did this planning item reach a "delivered" status? If not → stop and raise it. Did the QA gate pass? If not → stop. That's its "monitoring."

The boundary that matters: Layer A does not watch the individual coding agents. When it hits the develop step, it hands an entire planning item down to the lower runtime and waits. That lower runtime is what spawns the area agents, watches them, verifies, and merges. Layer A only sees the coarse result that comes back up: "PI-230 reached In Review ✓" or "PI-231 never reached a delivered state ✗ → halt."

So the conductor analogy holds, but think of it conducting sections (phases of the release), while a section leader one layer down conducts the individual players (the area agents) within each section.

Does that boundary — conductor of phases vs. conductor of players — land for you? And do you want to look at how Layer A decides to halt next, or move down to that section-leader layer?

---

**So what initiates the Layer A conduction - What are the inputs and required status/info?**

---

Good question — here's the precise answer, straight from the conductor's decision logic.

**What initiates Layer A**

The single input: one release identifier. You point the conductor at one release and it runs.

The required status: the release must be FROZEN. This is the key gate. Before freeze — while the release is in preliminary planning or development planning — the conductor does nothing but wait. It just returns "freeze is a deliberate human/PM act."

Freeze is the hand-off line: a human/PM, in the planning workbench, decides "planning is done, execution can start" and freezes the release. That's what flips the conductor from idle to active. Nothing automatic crosses that line.

The required info: the release's scope must be populated. For the conductor to have anything to do, the frozen release needs in-scope projects attached to it, those projects' planning items, and those planning items' confirmed requirements. That scope is exactly what the human assembles in the workbench before freezing.

**How it runs once initiated**

Each tick, the conductor reads two things and nothing else: (1) the release's status (its position in the pipeline), and (2) a handful of derived flags computed fresh from the live records: demands_present, has_open_conflicts, readiness_ready, all_pis_delivered, qa_passed, test_passed.

From just those, it returns the one next step owed. So the conductor is stateless between ticks — it re-derives everything from the release record and the database each time.

In one sentence: the conductor is initiated by pointing it at a single frozen release whose scope is already assembled, and from then on it's driven entirely by the release's status plus flags it re-reads from the live records each tick.

Does that match what you expected — particularly the "frozen + scope must already exist" precondition being a human act, not something the conductor sets up itself?

---

**yes. not yet. Where is the "Pipeline" position stored, and what are the various states?**

---

**Where the pipeline position is stored**

A single field — `release_status` — on the release record. That one column is the pipeline position. Nothing else holds it; the conductor reads it, and one guarded mutator is the only thing allowed to change it. That mutator won't let the status jump arbitrarily — every move is validated against an allowed-transitions map.

**The states (12 total)**

In pipeline order:

| # | State | What it means |
|---|---|---|
| 1 | preliminary_planning | born here; scope being formed |
| 2 | development_planning | scope being settled |
| 3 | reconciliation | ← FREEZE gate crossed here (human/PM act) |
| 4 | architecture_planning | demands done; decomposing |
| 5 | ready | ← PLANNED-COMPLETELY gate; planning slice fully done |
| 6 | development | ⎱ |
| 7 | qa | ⎬ the exclusive "lane" — single-occupancy |
| 8 | testing | ⎬ (only one release in here at a time) |
| 9 | deployment | ⎰ |
| 10 | shipped | terminal — success |

Plus two terminal off-ramps reachable from almost anywhere: cancelled (killed) and superseded (replaced by a corrected release).

**Three things worth noting about the flow**

1. The freeze gate is the development_planning → reconciliation edge — exactly the human hand-off we discussed. Before it: states 1–2 (conductor idle). After it: the conductor drives 3 onward.
2. States 6–9 are "the lane" — held exclusively. Only one release can occupy development..deployment at a time. And there's a rework bounce-back: qa can drop back to development if the gate fails.
3. Everything can be cancelled/superseded. No state is a trap except the two terminals + shipped.

So the whole pipeline is one column walking a guarded state graph, with the freeze gate splitting "human planning" (1–2) from "conductor-driven execution" (3–10).

Does the state list and the freeze split look right to you? And do you want to look at what happens at each of states 3–5 (the planning half) or jump to state 6, the dev lane?

---

**As each phase in the pipeline executes, where does it log status or progress?**

---

Good — I just read the conductor's run loop, and the answer is more layered (and more fragmented) than you might expect.

**Where progress is logged**

Progress is scattered across four different surfaces, none of them unified:

1. The release record's `release_status` field — the coarse pipeline position (what we just mapped). This is the one authoritative source, but it's only a single status word per release, not a log.
2. Workstream and Work Task status fields — each planning item's phases and tasks carry their own statuses (pending, in_progress, complete, needs_attention). These are the fine-grained progress signals, but only for the dev-lane work; nothing equivalent exists for the planning phases.
3. Python logger output — the conductor, the coordinating runtime, and the ADO substrate all emit standard Python logging. That goes to stdout/stderr, and unless something captures it (a file, a monitoring tool), it vanishes when the process ends.
4. Agent exit reports — when an area agent finishes, it writes a natural-language summary to the Work Task's notes field. That's durable, but it's prose in a notes blob, not structured and not queryable.

**What's missing**

There is no unified, durable, queryable progress log. If you want to know "what did the storage agent do, exactly, at 2pm yesterday," you're reading task notes prose, not pulling a structured record. And if the process crashed mid-run, the logger output is gone — the only evidence is whatever status the last completed step left behind.

This is a real gap, and it feeds directly into your earlier concern that agents' work isn't visible enough. A structured agent-activity log — who ran, when, what they produced, what the verification result was — doesn't exist yet as a first-class entity.

---

**yes. What are live records?**

---

"Live records" = the actual rows in the V2 governance database, read in real time — not a cached copy, not a file, not anything the conductor holds in memory.

In this project the database is the source of truth (everything — releases, projects, requirements, decisions — lives there as queryable records, not in documents). So "live records" are the current rows as they exist right now in that database:

- the release row — carries the status the conductor reads
- the project rows scoped to it
- the planning item rows under those projects
- the requirement rows those planning items implement
- and, once execution starts, the workstream and work task rows, plus the reference edges that link them all together

When I said the conductor "re-reads the live records each tick," I mean: every time it decides the next step, it queries the database fresh — what's the release's status right now? are there demands yet? are all planning items delivered yet? — and answers from whatever the rows currently say. If an agent down in the lowest layer just flipped a work task to Complete a second ago, the conductor sees that on its next read.

The practical upshot: there's one shared, current truth that every layer reads from and writes to. The conductor doesn't get a stale snapshot handed to it — it looks at the same live database the agents are actively changing. (It's also why two sessions touching the same records at once is hazardous — they're writing to the same live rows.)

Ready to drop down to the section-leader layer (how a whole planning item gets handed off and conducted), or stay on Layer A?

---

**yes. not yet. Where is the "Pipeline" position stored, and what are the various states?**

*(This question was already answered above — conversation continued)*

---

**Nope.... I do not understand the mumbo jumbo. But it is clear that this design does not match my requirements. Every agent in the process must have precisely defined requirements and prompts that are documented in the V2 database. It should be a very, very specific prompt with strict guidelines, deliverables, and reporting requirements. Please in language like I am 5 describe what instructions the reconciliation agent is given, and where that is stored.**

---

Fair. Let me drop all the jargon and answer your two questions plainly.

**What the reconciliation agent is, in plain words**

It's the first helper the conductor asks for help. Its job is simple to state: "Here's the list of things the customer wants. Turn that into a precise, tidy list of exact changes to make to the data." That's it. It doesn't build anything — it just writes the change-list.

**What instructions is it given?**

Two things, every time:

1. A standing "job card" — the same instructions it always gets, describing who it is and how to do its job.
2. The actual to-do for this run — the real list of customer wants for this particular release, pasted in.

**Where is the job card stored?**

In the V2 database — as a record named AGP-003. So the good news first: the instructions for this agent do live in the database, which is exactly what you're asking for. That part of the design matches your requirement.

**What the job card actually says (plain English)**

If I translate AGP-003 out of the jargon, it says roughly:

> "You're the person who turns wishes into a precise change-list for the data. Read the wishes. Write the smallest honest list of changes. If two wishes contradict each other, don't quietly pick one — flag it. Do the changes in a sensible order."

And three "rules," which are really gentle suggestions ("you should…", "try to…").

**The honest problem — you've spotted it correctly**

The job card is in the database, but it is loose, not strict. Specifically:
- The rules are advisory — suggestions, not hard "you must / you may not" lines the agent is forced to obey.
- There is no precise definition of "done" — nothing that says exactly what a finished, acceptable change-list looks like.
- There are no reporting requirements — nothing that says "report back exactly these facts in exactly this shape."
- And the card even describes work the agent doesn't actually do (it claims to handle contradictions and re-run things that the conductor and a human actually handle).

So you're right: this is not the "very specific prompt with strict guidelines, deliverables, and reporting requirements" you require. It's a vague job description sitting in the right place.

---

What you just said — "every agent must have a precisely defined requirement and a strict, specific prompt with deliverables and reporting requirements, documented in the V2 database" — is itself a requirement for this whole hardening effort. It's the standard we'd hold every agent's job card to.

Want me to capture that as a requirement in the database, so it becomes the bar we redesign every agent against?

---

**yes, capture that requirement along with a plain english description.**

---

Captured as REQ-278, under the agent guardrails project and topic, with provenance traced to this session.

**REQ-278 — "Every pipeline agent has a strict, documented contract in the V2 database" (priority: must)**

The plain-English description spells out that each agent must have, stored in the database, two things:

1. A requirement saying what the agent is for, and
2. A strict, specific prompt (its job card) containing, at minimum:
   - Role & scope — what it does and what it must not do
   - Guidelines — hard must / must-not rules, not soft "you should" suggestions
   - Deliverables — exactly what it must produce + a checkable definition of "done"
   - Reporting requirements — exactly what facts it reports back, in a defined shape, so its work is observable

It also states the prompt must match what the agent actually does — citing the AGP-003 example where the job card claims work the agent doesn't perform.

This is the standard the rest of the hardening project is measured against. It's a candidate awaiting your approval in the Requirements Review panel.

Where to next — keep walking the agents (the decomposition agent is next, where REL-005's over-production actually happened), or stop the architecture tour here and start turning this into the per-agent contract redesign?

---

**I would like to discuss what happens when the first agent completes. Does the conductor check and verify what was accomplished, or simply move ahead? Do the follow on agents have instructions to verify the information provided to them before starting?**

---

Good question — this gets at whether the pipeline trusts its agents blindly.

**Q1: When the first agent finishes, does the conductor check its work?**

Mostly it just moves ahead. There are only two checks, and neither asks "is this good?"

1. A format check (automatic). When the agent hands back its change-list, the system checks the shape — are all the boxes filled in, in the right format? That's like making sure a form isn't missing fields. It does not check whether the answers are correct.
2. A contradiction check (the merge). The conductor then runs a dumb, mechanical merge that catches one thing: two changes that directly contradict each other. If it finds one, the conductor stops and waits for a human to decide. That's a real safety net — but it only catches internal contradictions.

What nobody checks: whether the change-list actually matches what the customer asked for, whether it's complete, or whether it includes work that's already built. The conductor trusts the agent's list and saves it as-is.

And the rule for moving on is purely mechanical: "Is there a change-list at all, and no contradictions? → go." Not "Is the change-list any good? → go." That's exactly why REL-005 sailed past 6 demands' worth of already-shipped work — nothing was looking for that.

**Q2: Do the follow-on agents verify their inputs before starting?**

No — the opposite. The second agent (the one that turns the change-list into a build plan) is literally instructed to trust its input. Its job card says: "Consume the reconciled delta-set; do not re-run the merge or re-open settled conflicts." That's a "take this and run with it" instruction, not a "check this first" one.

There is no instruction anywhere that says: "Before you start — is this input sane? Is it scoped to just my piece? Is this work already done?"

This is precisely where REL-005 broke: the second agent was handed the whole release's changes instead of just its one item's, and because nothing told it to question that, it dutifully planned "build the entire release" for every item — the duplicate, bloated plan that deadlocked.

**The gap, in one line**

There is almost no checking of content anywhere in the handoff — only format-checks and a contradiction-catcher. Everything else is blind trust, agent to agent. Agents don't verify what they're given, and the conductor doesn't verify what it gets back.

---

That's two missing standards your design clearly wants: the conductor must verify an agent's deliverable is correct/complete/non-redundant before advancing, and each agent must verify its inputs before starting. Want me to capture those as requirements? I'd suggest one requirement that states the principle from both sides, rather than splitting it.

---

**Capture it as one requirement**

---

Captured as REQ-279 — "Every pipeline handoff is verified, not trusted" (priority: must), under the hardening project, traced to this session.

It states the principle from both sides of every handoff:

1. Input validation (receiving agent, before it starts) — is this input sane and complete? scoped to my piece? already done (so I stop, not redo)? If wrong or already satisfied → stop and report.
2. Deliverable verification (conductor, before it advances) — is the deliverable correct, complete, and non-redundant against its done-condition? Format-checks and contradiction-catching aren't enough.

I also wired it explicitly to REQ-278: that one defines the bar (every agent has a strict contract with a checkable done-condition); this one says both the agent and the conductor must actually check work against that bar at every handoff. Together they're becoming the spine of the effort.

So you've now added three keystone requirements that reframe the whole project:
- REQ-277 (under the observability topic) — durable, queryable progress/agent-activity logging
- REQ-278 — every agent has a strict, documented contract in the database
- REQ-279 — every handoff is verified, not trusted

These three are higher-altitude than the original twelve, which now read as specific instances of them. Where next — keep walking the agents (the area specialists, where the worker-level trust gap lives), or pause the tour and look at how these three reframe the original twelve into a clean structure?

---

**So, the reconciliation agent has created a reconciled list of requirements. And in the future will be doing much more to prep them for the next steps Architecture. What does the next Agent do?**

---

Plain English — the second agent is the architect. The reconciliation agent gave it a settled change-list (nothing contradicts). Now this agent turns that change-list into something a build crew can actually follow. It makes two things:

1. **The blueprint** — what each thing looks like after the changes

   It takes the change-list ("add these 3 fields to the Customer record, remove that one") and writes out the new, finished design of each thing being touched — the "after" picture. So instead of a list of edits, you now have the actual new shape of the Customer record, drawn out in full. That's the blueprint the builders will work toward.

2. **The build plan** — the list of jobs, grouped and put in order

   Then it chops the work into specific jobs, and for each job it says which area it belongs to (the data layer, the screens, the connections, etc.), what phase it's in (Design, then Develop, then Test), and what order they go in (this job can't start until that one is done). That ordered list of jobs is the build plan the worker agents will pick up later.

**Then it "finalizes" — and that's a big moment**

When it's done, it declares "planning is complete" and hands the finished plan to the build crew, which opens the build stage.

Here's the part that matters most for your hardening goal: after this agent finishes, all the thinking is supposed to be over. The build stage is designed to be mechanical — the worker agents just walk the list and do each job. Nobody is meant to re-plan or re-decide during the build.

That makes this agent the last real judgment step before actual building starts. If it gets the plan wrong, everything downstream builds the wrong thing — and the builders aren't expected to catch it, because they've been told to just follow the plan.

And that's exactly where REL-005 went off the rails: this agent was handed the whole release's changes instead of one chunk at a time, so it wrote a build plan that said "build the entire release" for every chunk — duplicate jobs, in a tangled order that jammed.

---

**go one level down into how it breaks work into jobs. But I do not understand the term jobs.**

---

Good — let me kill the word "job" and give you the real term, because the system actually has a name for it.

**The thing I was calling a "job" is a Work Task**

A Work Task is the smallest unit of work in the whole system: one specific piece of work, in one area, sized for a single worker agent to do in one sitting.

Examples of a single Work Task:
- "Add the phone-number field to the data storage."
- "Add the phone-number box to the Customer screen."
- "Write a test that saving a phone number works."

Each of those is one Work Task. One worker agent picks up one Work Task, does just that, and stops. That's the unit.

**How the work nests (from biggest to smallest)**

Think of it as a set of nested boxes:
1. The release — everything shipping this round. (biggest box)
2. Planning items — the release is made of a few chunks of work; each chunk is a "planning item." Think of one chunk as roughly one feature or one requirement's worth of work.
3. Phases — the architect takes one chunk and splits it into three phases: Design → Develop → Test. (In the system these phase-boxes are called "Workstreams" — same thing: a phase of one chunk.)
4. Work Tasks — inside each phase, the actual pieces of work — one per area that needs touching. (smallest box)

So: release → chunks → each chunk gets 3 phases → each phase holds the Work Tasks.

**A tiny concrete example**

Say the release has one chunk: "Add a phone number to the Customer."

The architect breaks that one chunk down like this:
- Design phase → Work Task: "design where the phone field goes."
- Develop phase → two Work Tasks (because two areas are touched): "add phone field to the data storage" and "add phone box to the Customer screen"
- Test phase → Work Task: "test that saving a phone works."

That's 4 Work Tasks, in 3 phases, for 1 chunk. Four workers (or one worker four times) each do one piece.

**Where this broke in REL-005**

Two of the three steps went wrong: the architect was handed the whole release's blueprint for every chunk — so for each chunk it made Work Tasks covering all the changes, not just that chunk's. Result: the same tasks created over and over (16 Work Tasks for two tiny requirements, half of them duplicates of already-built work). And it set a Design task to wait on a Test task — which can never happen, so the whole thing jammed.

---

**before we do that, are work tasks organized by areas?**

---

Short answer: every Work Task is labeled with exactly one area — but the tasks aren't grouped by area. They're grouped by phase. Let me untangle that, because it's an important distinction.

**Each Work Task carries one area label**

A Work Task always has exactly one area stamped on it. The possible areas:

| Area | In plain words |
|---|---|
| storage | the database tables — where data is physically kept (bottom layer) |
| access | the rules for reading/writing that data |
| api | the web service other programs talk to |
| mcp | the interface the AI tools use |
| ui | the screens and buttons people see (top layer) |
| methodology-process / -templates / -product / -interviews | the documentation and process side — not code |
| infrastructure, automation, espo, programs | servers, scripts, the CRM engine, config files |

The first five are stacked in layers (storage at the bottom → screens at the top). That layering is why order matters — you build the storage field before the screen that shows it.

**But the organizing structure is by phase, not area**

The Work Tasks live inside phase boxes, not area boxes. Within a single phase, you'll have several Work Tasks each carrying a different area label.

So using the phone-number example, the Develop phase holds two tasks: "add phone field to storage" (area = storage) and "add phone box to screen" (area = ui). Same phase box, two different area labels.

**What the area label is actually for**

The area isn't how tasks are filed — it's how they get routed to a worker. Each area is meant to have its own specialist agent, and the area label is what tells the system which specialist to hand this task to.

And that's exactly where REL-005's worker-level failure lived: a Work Task labeled ui had no ui specialist to route to, so it fell back to a storage specialist — who got ui work with storage-shaped instructions.

So, precisely: organized by phase, labeled with an area, routed by that area.

---

**Yes. And it is exactly as I designed it. However, where are the instructions for each phase/area agent? The design/UI agent should have very different instructions and skills than the database agent? It should include color pallet restrictions, technology restrictions (Angular or React?) to assure that the output is never unexpected.**

---

This is the heart of it, and your instinct is exactly right.

**Where the per-area instructions are supposed to live**

In the V2 database, as one "agent profile" per (area, phase-tier) combination. The design is right: a profile can carry not just a base prompt but attached skills and attached hard rules — so a ui profile could carry color-palette rules, an "only React, never Angular" rule, framework restrictions, all enforced. The database shelf is built to hold exactly what you're describing.

**What's actually on that shelf**

Only five profiles exist in the entire system:

| Profile | Area / tier | What it is |
|---|---|---|
| AGP-001 | storage / architect | data design |
| AGP-002 | storage / developer | the only actual "builder" profile |
| AGP-003 | model / architect | the reconciliation agent |
| AGP-004 | planning / architect | the decomposition agent |
| AGP-005 | release / pi_lead | a coordinator |

Look at what's missing: there is one builder profile in the whole system — storage / developer — and zero builder profiles for ui, access, api, or mcp, and zero tester profiles of any kind.

**So the UI agent you're describing does not exist**

When a ui Work Task comes through, the system can't find a UI builder — so it falls back to the storage-developer's card and just pastes the word "ui" into it. The UI agent therefore boots with database-flavored instructions, no color-palette rules, no framework restriction, no Qt/widget rules, and everything it does say is a soft suggestion, not a hard limit.

That is precisely the "output is unexpected" failure you're trying to prevent. There is nothing today stopping a UI agent from doing whatever it improvises.

**Your design is correct — the shelf is just empty**

Each area agent having its own strict, specific skills and hard technical/design constraints is exactly what the registry was built for. The mechanism exists (profiles carry enforced rules and skills); the content was never authored.

One grounding note: CRMBuilder's UI is a PySide6 / Qt desktop app, not a web app — so the UI agent's hard rules here would be Qt-specific. The principle is identical to your Angular-vs-React, color-palette example — name the exact technology and the exact limits so the output can never surprise you.

---

What you just said is itself a requirement: each area/phase agent's contract must encode its area's hard technical and design constraints — allowed technology/framework, design-system and color rules, testing idioms — stored in the database, so its output is bounded and never unexpected. Want me to capture that as a requirement?

---

**Yes, capture that requirement. About that grounding note. Well, what if the requirement was "Create a web app that allows remote users to view the V2 database"? So there may be two types of agents: Desktop UI and Web UI with different sets of rules.**

---

Capturing that one now — it's a sharp, specific standard. Captured as REQ-280 under the agent guardrails topic.

Now your desktop-vs-web point — that's a genuinely deeper insight, and it exposes that the area label is too coarse.

**You've found the hole: one area, two technologies**

"ui" is a functional label — "the part people look at." But it says nothing about how it's built. A Qt desktop screen and a React web page are both ui, and they need completely different rule sets — different framework, different testing, different everything. So a single ui agent card can never be right for both.

And your specific example is the hard version of the problem. "Create a web app that lets remote users view the V2 database" — that's a web UI added to a project that already has a desktop (Qt) UI. So now one project has two UI technologies running at the same time. The system has to be able to tell, per work task, which UI a given task is for, and hand it the matching rules.

**So yes — "Desktop UI agent" and "Web UI agent" are two different agents**

Each with its own contract: the Desktop UI agent bounded to Qt/PySide6 and its idioms; the Web UI agent bounded to the chosen web framework and palette. Same functional area, two technology variants, two rule sets.

The system actually has a mechanism that could carry this — it already supports project-specific areas defined on top of the fixed system ones — so "web-ui" could be its own routable area distinct from the desktop "ui." The requirement is the principle: the agent model must support multiple technology variants of the same functional area, each with its own rules, even when both exist in one project at once — and route each task to the right one.

Want me to capture that as its own requirement? I'd keep it separate from REQ-280 (which is "contracts carry hard constraints") because this one is structural — it's about the taxonomy being able to represent variants at all.

---

**Yes, capture that requirement. What we want to design in crmBuilder is a huge list of possible agents with defined skills in a wide variety of areas so that when a requirement says "We need a phone app too" that the whole system does not break down. And the goal is to have system default agents, and then allow engagement specific customizations. One project may want web to be angular, and another client wants react. So make sure that the requirements are there to accommodate these issues.**

---

Capturing both facets — the variant requirement you approved, and the broader catalog/defaults vision you just laid out. They're distinct enough to stand alone.

Both captured:
- REQ-281 — technology variant requirement: the agent model supports multiple technology variants of one area (Desktop UI vs Web UI), coexisting in one project, routed per task.
- REQ-282 — catalog requirement: a broad library of system-default agents, gracefully extensible, customizable per engagement (Angular here, React there).

Here's the structure you've built this session — six new requirements that reframe the whole effort from the top down:

**Under the agent contracts & guardrails topic:**

| ID | The standard |
|---|---|
| REQ-278 | Every agent has a strict, documented contract in the database (role, hard guidelines, deliverables, reporting) |
| REQ-279 | Every handoff is verified, not trusted (agents validate inputs; conductor validates deliverables) |
| REQ-280 | Build-area agents encode hard technical & design constraints (framework, palette, conventions, tests) |
| REQ-281 | The model supports multiple technology variants of one area (Desktop UI vs Web UI), coexisting in one project, routed per task |
| REQ-282 | A broad library of system-default agents, gracefully extensible, customizable per engagement (Angular here, React there) |

**Under the observability topic:**

| ID | The standard |
|---|---|
| REQ-277 | Pipeline progress & agent activity are durably reported and queryable |

One genuine piece of good news on REQ-282: the system-defaults + engagement-overrides mechanism already partly exists — the registry has system rows plus engagement overlay/override rows. So "Angular for this client, React for that one" has a real foundation to build on.

---

**before we go much further, have you read all requirements in the top-005 - Agent Systems? Let's make sure we are not duplicating**

---

Good diligence — I have not read the Agent Systems topic yet. Let me pull the whole agent-system requirement tree and check for overlap.

This was the right call — there's substantial overlap with the confirmed Agent Systems set, and one of our six is essentially a duplicate. Here's the honest map.

**Dedup analysis: our six new requirements vs. confirmed Agent Systems**

| New (candidate) | Verdict | Overlaps with (confirmed) |
|---|---|---|
| REQ-282 broad library of system-default agents, customizable per engagement | 🔴 Duplicate — withdraw | Already fully covered by confirmed requirements for standard agent teams, engagement visibility, engagement customization, changes reviewed, and fleet profiles |
| REQ-279 every handoff verified, not trusted | 🟠 Mostly covered — narrow or withdraw | Conductor-side verification is nearly verbatim in a confirmed requirement. Only the "agent validates its inputs are sane/correctly-scoped before starting" sliver is genuinely new |
| REQ-278 strict documented contract in DB | 🟡 Refinement — keep + link | Existing requirements say contracts exist; REQ-278 adds the strictness + deliverables + reporting + must-match-behavior bar, which is genuinely additive |
| REQ-280 hard tech/design constraints in contract | 🟡 Refinement — keep + link | Additive — existing says "each expert has rules" + "testable spec"; REQ-280 adds enforced technology/framework/palette limits |
| REQ-281 multiple technology variants within one area | 🟢 Genuinely new — keep | Nothing covers Desktop-UI-vs-Web-UI within one area |
| REQ-277 durable progress/activity logging | 🟡 Refinement — keep + link | Parent intent exists; REQ-277 is the concrete "that intent isn't actually met" requirement |

And two of the original twelve also overlap confirmed requirements — REQ-274 adds only "re-validate before execution" (narrow it to that sliver), and REQ-273's "refuse a mismatch rather than misroute" is the enforcement (keep but link).

**What I'd recommend**

1. Withdraw REQ-282 (cancel it) — fully subsumed.
2. Narrow REQ-279 — the conductor half is already covered; narrow to just "the receiving agent validates its inputs before starting" and link it as refining the existing requirement.
3. Keep REQ-277, REQ-278, REQ-280, REQ-281 — but add refines links to their confirmed parents so the provenance is honest.
4. Narrow REQ-274 to the "re-validate before execution" sliver, linked to the existing well-formedness requirement.

The bigger takeaway: the Agent Systems topic already confirms most of your architectural vision. What's genuinely missing and worth net-new requirements is narrower than it first looked — mainly the strictness/enforcement bar, technology variants, input-validation, and real observability.

How do you want to proceed — shall I execute that disposition, or do you want to adjust any verdict first?

---

**execute that disposition. I will review the entire topic when we are done.**

---

Executing. All executed cleanly, recorded under a new decision (DEC-553 — the rejecting authority for REQ-282 and the record of the narrowings). Final state:

**Disposition complete**

- REQ-282 → rejected (tombstoned with a note pointing to the confirmed requirements that cover it). It'll show in your review as explicitly withdrawn, not vanished.
- REQ-279 → narrowed to "A receiving agent validates its inputs before starting" (the genuinely-new receiver-side half); refines the existing conductor-side verification requirement.
- REQ-274 → narrowed to "A decomposition is re-validated as well-formed before execution" (the stale-graph re-check); refines the existing well-formedness requirement.
- Refinement links added so nothing reads as a fresh invention:
  - REQ-277 → refines the "all agent work documented & visible" requirement
  - REQ-278 → refines the "each expert has its own skills & rules" requirement
  - REQ-280 → refines the same
  - REQ-281 → refines the "areas as units of expertise" requirement
  - REQ-273 → refines the "fleet has build-area profiles" requirement

**Net result**

Your genuinely-new contribution this session, after dedup, is five tight requirements, each clearly positioned against the confirmed baseline:
- REQ-277 — real observability (the fragmented-logging gap)
- REQ-278 — the strictness/deliverables/reporting bar on contracts
- REQ-280 — hard, enforced tech/design constraints in build-area contracts
- REQ-281 — technology variants within one area (Desktop vs Web UI)
- REQ-279 / REQ-274 — the input-validation and re-validate-before-execution slivers

That's a much cleaner footprint than the six we started with, and it sits on top of the confirmed vision rather than re-stating it.

Want to keep walking the architecture (next would be the worker/area-specialist level — how a Work Task becomes a worker's actual instructions), or pause here so you can do the review first?

---

**keep walking the architecture**

---

Now we're at the level you care most about — the worker (area specialist). This is where most of the guardrail gaps actually live.

The only hard rule the worker has is: "Before you mark the task done, run the linter clean and the tests green on what you touched." And it's the only enforced rule. No done-condition, no area-specific instructions.

**Here's the worker level in plain terms — using a concrete task: "add the phone box to the Customer screen" (area = ui, tier = developer)**

**How a Work Task becomes the worker's instruction sheet**

The worker's full instructions are three pieces stacked together:

*Piece 1 — the job card (from the registry)*

The system looks for a "ui developer" job card. As we found, there isn't one. So it grabs the only worker card that exists — the storage developer card — and pastes the word "ui" into it. Generic, storage-flavored. No Qt rules, no color rules, no framework rules.

*Piece 2 — the hard gate + the task*

Exactly one hard "you must" rule: run the linter and tests clean before marking done. The task itself: its title, area, and description — and no definition of "done" beyond that one test rule.

*Piece 3 — the operating protocol (how to actually run)*

Five steps: (1) claim the task → (2) do the work → (3) commit → (4) mark Complete → (5) exit. Notice commit is step 3, after the work.

That stacked sheet is handed to a fresh worker agent, spawned in its own private copy of the code, running by itself with no human.

**How the result is checked**

The runtime doesn't watch the worker — it checks the result: is the task marked Complete AND did it leave commits on its branch? If yes → it merges the branch into main. If the task isn't Complete or the branch is empty → it's held or retried.

**Where the gaps bite — almost all of them, right here**

| Gap | What goes wrong | Req |
|---|---|---|
| No "step 0: already done?" | The card says "produce the deliverable" — so even if the work exists, the worker builds something anyway | 267 |
| No definition of "done" | The worker can't tell success except "tests are green" — which looks true even when nothing was needed | 278 |
| Wrong-area card | UI work done with storage-flavored instructions; no Qt/color/framework limits | 273/280/281 |
| Commit is step 3, after the work | Killed mid-work → everything is lost. This is the REL-005 disaster | 270 |
| "Self-verify with tests," no time limit, no "run in foreground" | It can spin forever polling a slow test suite. The one hard rule is itself the trap | 269/271 |
| No "stop and raise a flag" exit | Notices the task is duplicate/mis-scoped → can only finish anyway by producing filler | 272 |

**The punchline**

The worker is the lowest and most numerous agent, it has the weakest, most generic instructions, and nearly every failure mode we've catalogued lives right here. This is exactly the level REQ-278 and REQ-280 are so high-leverage.

---

**sketch what a proper worker contract would contain**

---

Here's a sketch of a proper worker (area-specialist) contract that satisfies the standards you've set — REQ-278, REQ-280, REQ-281, plus the individual guardrail requirements. I've marked which parts are fixed (same for every worker), area-specific (filled per card), or per-task (filled by the architect).

---

**Worker Contract Template**

**A. Identity — the routing key** [area-specific]

(area × technology × tier) — e.g. (ui, qt-desktop, developer). This is what makes the card unique and what the task routes to. One card per combination, so a Qt-desktop UI worker and a React-web UI worker are different cards. No card for the exact combo → the task is refused, not run under a near-match.

**B. Role & scope** [fixed shape, area-specific fill]

- One-line role: "You build one Work Task in the {area} area using {technology}, and nothing else."
- DOES: implement exactly the assigned task, in this area, in this technology.
- DOES NOT (hard boundaries): re-scope, re-architect, change the plan, touch another area, introduce another technology, or "improve" things outside the task.

**C. Step 0 — Validate before you build** [fixed] (mandatory first action)

Before any work, the worker MUST:
1. Check the inputs: is the task well-formed, complete, and scoped to my area+technology only? If it was handed someone else's work or is ambiguous → halt and escalate, do not proceed.
2. Check if it's already done: is the deliverable already present on main with its tests green? If yes → record "no-op — already satisfied" with the evidence and exit without producing anything. Never manufacture filler to look busy.

**D. Hard guidelines — MUST / MUST NOT** [D1 fixed + D2 area-specific]

D1 — Universal (every worker):
- MUST commit before verifying (so an interruption never loses work)
- MUST stay inside the assigned area + technology
- MUST NOT push or merge (the runtime merges)
- MUST NOT add a dependency/framework not listed in D2

D2 — Area + technology constraints [the REQ-280 content — filled per card]:
- Allowed / forbidden technology & framework
- Required patterns & conventions
- Design system / component / color rules (for UI areas)
- Testing idioms (how work in this area is proven)

**E. Deliverable & done-condition** [per-task — supplied by the architect]

- Exactly what to produce (the task's output).
- The acceptance criterion for THIS task — a concrete, checkable statement of "done," written by the architect at decomposition time. The worker checks its own output against it and reports the result. (No task ships without one — that's the gap that sank REL-005.)

**F. Operating sequence** [fixed]

1. Validate (Step 0) → 2. Implement → 3. Commit → 4. Verify synchronously, in the foreground, within a time budget — never background-poll → 5. Report → 6. Exit.
- Time budget: {N} minutes. On overrun → commit + report what's done, do not spin into a kill.

**G. Halt / escalate** [fixed]

Halt conditions: mis-scoped task, duplicate work, blocked/missing dependency, or an ambiguous/absent done-condition.
Action: set the workstream's needs-attention flag with a written reason, stop, and report. Never finish by producing filler to satisfy "produce a deliverable."

**H. Reporting requirements** [fixed shape]

On exit the worker MUST emit a defined report:
- Outcome class: built / no-op-already-done / halted-needs-attention / failed
- Files + signatures touched; reuse-vs-new and why
- The done-condition checked + pass/fail
- Verification result; commit SHA
- Any convention uncertainty; any halt reason

---

**The same template, filled for two areas (showing D2 + E differ)**

*(storage, sqlalchemy, developer)*
- D2: SQLAlchemy models + Alembic migrations only; mirror the sibling table's column idioms; guard migrations for mid-chain entry. Tests: pytest, sub-second, no Qt.
- E: "The new column exists, the migration upgrades+downgrades cleanly, and a round-trip test passes."

*(ui, qt-desktop, developer)*
- D2: PySide6/Qt only — no web framework; use CopyableMessageBox, never raw QMessageBox; test Qt offscreen; follow the segfault-avoidance patterns; palette = the app's existing widget styling. Tests: pytest-qt, offscreen, the single touched widget's test file, bounded.
- E: "The phone field renders on the Customer detail panel, saves through the existing worker, and the widget's offscreen test passes."

---

Two things worth your eye on this sketch: (1) It cleanly splits the three "fill" sources — the system owns the fixed skeleton, each area card owns D2 + the technology identity, and the architect owns E. (2) D2 and E are the only parts that vary — everything else is one shared, strict skeleton. That keeps the "huge catalog of agents" manageable: you're not writing 50 contracts from scratch, you're writing one skeleton + 50 small D2 blocks.

---

**Let's discuss scope. Why wouldn't we have the agent handle all work tasks in their area in a single process. It would allow for more efficient processing, may prevent sequencing issues, and allow the expert in the area to figure out the best way to implement the entire work for their area?**

---

This is a genuinely good architectural question, and your instinct is sound — it also happens to align with the confirmed design intent better than the current implementation does.

**Your instinct matches the confirmed model**

The confirmed Agent Systems requirements already think in per-area units, and one deferred-but-confirmed requirement is literally your idea — one standing expert owning its area across the whole release. So the current "one Work Task = one spawned agent" isn't the designed target; it's an over-decomposition that drifted finer than the confirmed intent. You're not fighting the design — you're pulling a deferred piece of it forward.

**Your three benefits are all real**

1. Efficiency (the big one). Per-agent full-repo context reload is named in the forensic trace as the scaling cost driver. A ui expert that handles all the UI work in one session loads the UI context once, not once per task.
2. Sequencing within the area. If the storage expert owns all storage work, it orders its own steps internally — intra-area dependency edges disappear from the graph. Fewer edges = fewer ways to deadlock.
3. Holistic implementation. One expert seeing all its area's work writes shared helpers, consistent naming, no duplicate scaffolding.

Plus two you didn't name: fewer worktrees/merges (one branch per area instead of per task), and smaller fan-out.

**The real decision: what's the batch unit?**

"Handle all work tasks in their area" has several sizes:

| Option | Batch unit | Effect |
|---|---|---|
| (a) today | (area, phase, one PI) | finest; most context reload; most fan-out |
| (b) | (area, phase, whole release) | one expert does all the release's develop-work for its area at once |
| (c) | (area, all phases, one PI) | collapses Design→Develop→Test for an area into one session |
| (d) | (area, everything) | one expert does literally all its area's work, all phases, all PIs |

My recommendation is (b): batch by area within a phase, across the whole release. It captures all three of your benefits, collapses the PI-level fragmentation that caused REL-005's duplicate decompositions — but it keeps the phase boundaries. The one tension to respect: the cross-area coherence gate (confirmed requirements say design ends with a coherence check across areas, which only works if all areas finish their design before anyone builds). Batching within a phase preserves that gate.

One guardrail to add either way: bigger batches mean a single agent's reliability degrades as the batch grows, so an area's pass needs a size cap if it grows too large for one agent.

Does (b) match what you were picturing, or were you thinking bigger (collapse the phases too, option c/d)?

---

**yes. B was the original intent.**

---

B it is — and since it's the original intent, I positioned it correctly against the confirmed set before capturing so I didn't repeat the duplication problem.

Captured:
- A new decision (DEC-554) — the batch unit = (area, phase, whole release), size-capped, with the rationale and rejected alternatives recorded.
- REQ-283 — "An area expert builds its whole area for a phase as one batch across the release" (should), refines the deferred standing-area-expert requirement, defined in this session.

Two things this ripples into, on the record:
1. REQ-024 needs amending. It's confirmed and currently says "one design task per area per planning item" — that's the per-PI fragmentation REQ-283 replaces. It's a confirmed requirement, so changing it is a real edit you'll want to make deliberately.
2. The worker contract sketch shifts. The "one Work Task" framing becomes "one area-phase batch." Section E (deliverable & done-condition) changes from one acceptance criterion to a set — one per piece of the area's phase-pass.

---

**Lets deal with Req-024 so it is not forgotten.**

---

Good call — let's not leave a confirmed requirement contradicting REQ-283.

The proper path is the governed reopen mechanism — it reopens the requirement to candidate + needs_review, gated by a decision. REQ-024 is also already implemented, so its per-PI granularity is baked into the live decompose code — meaning amending REQ-024 and building REQ-283 are the same code change.

Here's the plan, executed now:

1. Record a decision that REQ-024's per-PI granularity is superseded by REQ-283.
2. Wire REQ-024 to the decision → this auto-reopens REQ-024 to candidate + needs_review (clearing its confirmed approval, as it should — its meaning is changing).
3. Narrow REQ-024's text to its still-valid core (identify areas + lay out the passes), handing the batch-unit granularity to REQ-283.

Done — both amended consistently:

- DEC-555 records the amendment rationale.
- REQ-024 is now candidate / needs_review (its confirmed approval cleared because its meaning changed) and narrowed to its still-valid core: "Plan identifies which areas the work touches and lays out the Design/Develop/Test passes." The batch-unit granularity now explicitly defers to REQ-283.
- It's wired with a changed_by reference to DEC-555, so the change is traceable.

One honest note for later: this amendment has a code consequence. When REQ-283 is implemented, the decompose code changes to emit release-level area-phase batches. So REQ-024's re-approval and REQ-283's build are the same implementation work — noted in DEC-555.

That's REQ-024 closed out. Where to next — keep walking (the post-worker merge + cross-area coherence gate), revisit the deferred verification-ownership fork, or step back for the whole-picture view?

---

**keep walking**

---

We've walked down to the worker. Now let me walk forward — what happens after a worker finishes.

**After a worker finishes — three steps**

1. **Verify + merge (per area)** — The runtime checks the result (task marked Complete + the branch actually has commits), runs the affected tests, and merges that area's branch into main. Each area's work lands on main one branch at a time.

2. **The phase gate (the PI Lead)** — A phase (say, Develop) is declared Complete only when every Work Task in it is Complete. Then the next phase opens — but only if its predecessors are finished (Design must be done before Develop opens). This keeps the passes serial: all areas Design → all areas Develop → all areas Test. But look at what that gate actually checks: the only criterion is "are all the tasks marked Complete?" Nothing else.

3. **The missing piece — the cross-area coherence check** — Here's the gap. The confirmed model says the Design phase should end with a coherence check across areas — before anyone builds, do the separate area designs actually fit together? For example: the api area designed a field called phoneNumber, but the ui area designed its screen around "phone." Each area was designed in isolation, so they can quietly disagree. The substrate for this check exists — there's a "finding" entity and a reconciliation gate built to record and resolve exactly these cross-area conflicts. But it is not wired into the phase gate. The PI Lead advances Design → Develop purely on "all design tasks Complete," and never runs the coherence check.

**Why this matters**

Today, two areas can design incompatible things, every task gets marked Complete, the phase advances cleanly — and the mismatch isn't caught until it breaks in Develop or Test, or worse, ships.

This looks like an implementation gap against confirmed requirements (the confirmed pair describes the check, not that the phase is blocked on it) — unless you want a sharper requirement that the coherence check must be enforced as a hard gate between phases.

Want me to capture that "coherence check is a hard phase gate" requirement, or note it as an implementation gap and keep walking to the release-level gates?

---

**capture that coherence gate requirement**

---

Before I capture — I need to flag something, because it's exactly the duplication trap you had me guard against earlier.

The existing confirmed requirement (REQ-027) already is the hard-gate requirement. Its acceptance criterion reads: "Develop does not start for a Planning Item until the cross-area coherence check reports no unresolved conflicts." That's a blocking gate, already confirmed. So a fresh "make coherence a hard gate" requirement would restate REQ-027 — the same kind of duplicate we just rejected and cleaned up.

There are really two separate problems here, and neither is "we lack the requirement":

1. It's unbuilt (implementation gap). REQ-027 mandates the gate; the PI Lead's phase completion doesn't run it. That's a build gap against a confirmed requirement.
2. Its scope is now misaligned — the same issue we just fixed on REQ-024. REQ-027 and REQ-031 are written per Planning Item ("the area specifications for a Planning Item"). But REQ-283 just changed the batch unit to release-level. So the coherence check must now compare area designs release-wide, across all in-scope planning items — not per-PI. REQ-027/031's per-PI framing is stale exactly like REQ-024's was.

The consistent action (mirroring what we just did for REQ-024) isn't a new requirement — it's to amend REQ-027 and REQ-031 to release-level scope via a change decision, and separately note the unbuilt-gate as an implementation gap.

My recommendation: amend REQ-027/031 to release scope rather than capture a duplicate. Do you want me to amend REQ-027/031, or do you still want a separate new requirement — and if so, what would it say that REQ-027 doesn't?

---

**amend REQ-027/031 to release scope**

---

On it — same treatment as REQ-024: one change decision, auto-reopen both, then narrow to release scope.

Done — both amended consistently with REQ-024:

- DEC-556 records the rationale.
- REQ-027 → reopened needs_review, now: "Develop does not start until the cross-area coherence check across the release's in-scope area design specifications reports no unresolved conflicts." Hard-gate semantics kept; scope lifted per-PI → release.
- REQ-031 → reopened needs_review, now compares "the area specifications for the release's in-scope work."
- Both wired to DEC-556; both will appear in your needs-review queue alongside REQ-024.

And I recorded the separate fact inside DEC-556 so it's not lost: REQ-027's gate is confirmed but unbuilt — complete_phase advances on "all tasks Complete" and never runs the coherence check. That's a build gap for the hardening project implementation, not a requirement gap, so I tracked it in the decision rather than inventing a requirement for it.

That's a clean stopping point on this thread. We've now walked: conductor → reconciliation → architect → worker → verify/merge → phase gate → coherence gate. The natural next step forward is the release-level gates (Develop done → QA → Test → ship) — how the whole release graduates once all the planning items are delivered. Want to keep walking there, or pause?

---

**Create a new script to continue walking so we can use a new session. Then let's update the existing agent documentation**

---

Two tasks. Let me do the continuation script first, then turn to the docs.

I'll capture exactly where the walk is, the governance authored this session, and the standing rules, so a fresh session resumes cleanly.

*(Session ended — continuation script and documentation updates written)*

---

---

# Glossary of Agent-Specific Terms

---

**Acceptance Criterion (AC)**
The exact, checkable definition of "done" for a specific piece of work. Think of it like a teacher's grading rubric — before the student (agent) turns in the homework, they check it against the rubric. If the rubric says "the phone field must appear on the Customer screen and save correctly," the agent can look at what it built and answer yes or no. Without an acceptance criterion, the agent has to guess whether its work is good enough, which leads to guessing wrong.

---

**Agent**
A copy of an AI (like Claude) that is given a specific job, a set of instructions, and access to the codebase, then sent off to do that one job by itself with no human watching. When it's done, it reports back. Think of it like hiring a contractor: you hand them the blueprints and the key to the building, they go do the work, and they call you when they're finished.

---

**Agent Profile (AGP)**
The stored record in the database that defines who an agent is and what it knows. It contains the agent's job card (its prompt/instructions), any hard rules it must follow, the skills it has, and which area and tier it belongs to. Think of it like a personnel file: it describes what this type of worker is trained to do and what they're not allowed to do. Each profile has an identifier like AGP-001 or AGP-004.

---

**Area**
The specific layer of the software an agent is responsible for. Every piece of work is labeled with exactly one area, and that label determines which specialist agent handles it. The areas form a stack from bottom to top: storage (the database) → access (rules for reading/writing data) → api (the web service) → mcp (the AI interface) → ui (the screens people see). There are also non-code areas like methodology and infrastructure. Each area requires different knowledge and different rules — a storage expert and a UI expert need completely different instructions.

---

**Area Specialist**
The worker agent at the bottom of the agent hierarchy. It receives one Work Task (or one area-phase batch), does the actual coding or documentation work in its assigned area, commits the result, and exits. These are the agents that do the real building. In REL-005, 16 area specialists were spawned — far more than needed, and many were given the wrong job cards.

---

**Batch Unit**
The amount of work a single area specialist handles in one session. Today the batch unit is too small — one agent per Work Task per Planning Item, which means the storage expert gets re-hired and re-briefed separately for each tiny chunk of storage work across the release. The better model (option B, which was the original design intent) is one agent per area per phase across the whole release — so the storage expert sees all the storage work for the entire release's Develop phase at once, does it in one session, and moves on.

---

**Branch**
A private copy of the codebase that an area specialist works in. When an agent is spawned, it gets its own branch — like a separate workbench — so it can make changes without interfering with anyone else's work. When the agent is done and its work is verified, the runtime merges the branch back into the main codebase. If the agent is killed mid-work and never committed, everything on that branch is lost.

---

**Coherence Check (Cross-Area Coherence Check)**
A review that happens after all areas finish their Design phase and before anyone starts building. Its job is to make sure the different areas' designs actually fit together. For example: the api area designed a field called "phoneNumber" but the ui area designed its screen to display "phone" — these don't match. The coherence check catches disagreements like this before any code is written. Today this check exists as a concept and has infrastructure built for it, but it is not actually wired into the phase gate — meaning the system advances to Develop without ever running it.

---

**Conductor**
The informal name for Layer A — the release pipeline state machine. It's called the conductor because, like an orchestra conductor, it controls the tempo and sequence of the whole release without playing any instrument itself. It decides when each phase starts, watches for the phase to finish, checks whether the result was acceptable, and either advances to the next phase or halts and waits for a human. It does not watch individual agents — it only sees the high-level result after a whole phase completes.

---

**Contract (Agent Contract)**
The complete set of instructions, rules, and expectations that define what an agent is, what it must do, what it must not do, what it must produce, and how it must report back. A proper contract has eight sections: identity (area/technology/tier), role and scope, a mandatory Step 0 input validation, hard guidelines (MUST/MUST NOT rules), a deliverable and done-condition, an operating sequence, a halt/escalate procedure, and a reporting requirement. Today most agents have loose, vague contracts — more like a casual note than a real contract.

---

**Coordinating Runtime**
The software layer that manages the area specialist agents during the development phase. It spawns each agent in its own worktree, watches for the agent to finish, verifies the result (did the task get marked Complete? did the branch get commits?), runs the affected tests, and merges the branch into main. It already owns all the test-running machinery — but today it hands that responsibility back to the agents, which is exactly where the 30-minute test-spin disaster happened.

---

**Decision (DEC)**
A formal governance record in the V2 database that captures a significant choice: what was decided, why, what alternatives were considered, and what the consequences are. Every important architectural or requirement change is anchored to a decision record so the reasoning is permanently traceable. Decisions are identified with codes like DEC-554 or DEC-556.

---

**Decomposition**
The act of breaking a Planning Item (a chunk of feature work) into a structured set of Workstreams (phases) and Work Tasks. The Decomposition Agent (AGP-004) does this work. A well-formed decomposition has three phases (Design → Develop → Test), with Work Tasks inside each phase, and a valid ordering (no task depending on something that runs after it). A malformed decomposition — like REL-005's, where a Design task was told to wait on a Test task — will deadlock and never complete.

---

**Decomposition Agent (AGP-004)**
The second LLM agent in the pipeline, also called the Architect Agent. After the Reconciliation Agent produces the change-list, this agent turns it into the actual build plan: a set of phases and Work Tasks for each Planning Item, with each task labeled by area and ordered by dependency. It is the last real judgment step before building starts — if it gets the plan wrong, the workers downstream just follow it and build the wrong thing.

---

**Delta Set**
The set of specific data changes that need to happen for a Planning Item — things like "add this field," "rename that entity," "remove this relationship." It's the output of the Reconciliation Agent: a precise, tidy list of changes rather than a vague wish list. The Decomposition Agent consumes the delta set and turns it into a build plan. In REL-005, the delta set for the whole release was incorrectly handed to every Planning Item's decomposition, causing each one to plan "build everything" instead of just its own piece.

---

**Dev Lane**
The exclusive stretch of the release pipeline (states 6–9: development, qa, testing, deployment) where only one release is allowed at a time. Think of it like a single-lane bridge — one vehicle crosses at a time. When a release enters development, no other release can be in development, qa, testing, or deployment at the same time. A release enters the dev lane by crossing the ready → development transition, which is itself gated: it won't open if another release is already in the lane.

---

**Engagement**
A specific instance of the CRMBuilder system being used for one client or project. Each engagement has its own isolated database of governance records (sessions, decisions, requirements, etc.). The CRMBuilder dogfood work (building CRMBuilder itself) is one engagement; Cleveland Business Mentoring is another. Agent profiles can be customized per engagement — so one engagement might use Angular for its web UI agent and another might use React.

---

**Fan-Out**
The number of agents spawned to do a batch of work. High fan-out means many agents running in parallel, each doing a tiny piece. Low fan-out means fewer agents, each doing a larger piece. REL-005 had excessive fan-out — 16 agents for 2 simple requirements — because the batch unit was too fine (one agent per Work Task per Planning Item). The fix (batch by area across the whole release) dramatically reduces fan-out.

---

**Fleet**
The collection of all the agent-spawned commits produced during a release's development phase. When area specialists do their work and commit to branches, those commits accumulate as "fleet commits." In REL-005, the fleet consisted of 33 commits that had already been pushed to origin/main before the planning session where we discussed keeping vs. reverting them.

---

**Forensic Trace**
A detailed after-the-fact record of what went wrong during a failed or problematic run. In this session, the forensic trace documented exactly what each agent did during REL-005 — how long it ran, what it produced, where it spun, what it committed, and why things went wrong. Reading the forensic trace was the first step in understanding which code seams needed fixing.

---

**Freeze / Frozen**
The human act of declaring that planning is complete and execution can begin. Before freeze, the release is in preliminary or development planning and the conductor does nothing. When a human/PM freezes the release (transitioning it from development_planning to reconciliation), the conductor wakes up and starts driving the pipeline. Nothing automatic crosses the freeze line — it is always a deliberate human decision.

---

**Governance Database**
The V2 SQLite database that stores all structured records for an engagement: sessions, decisions, requirements, planning items, work tickets, agent profiles, references, and more. It is the single source of truth. All reads and writes must go through the API — direct edits to the database file are prohibited. When the conversation refers to "live records," it means the actual rows in this database as they exist right now.

---

**Guardrail**
A rule, check, or structural constraint that prevents an agent from going off the rails. Guardrails can be in the agent's contract ("you MUST commit before verifying"), in the runtime code ("if verification fails, halt"), or in the database schema ("rejection requires a governing decision"). A guardrail is only as good as its enforcement — a soft suggestion is not a guardrail.

---

**Hardening**
The project of making the agent pipeline more reliable and predictable by fixing the gaps that caused failures. "Hardening" means adding strict contracts, enforcing guardrails, closing the missing-profile gaps, wiring checks that exist but aren't connected, and generally moving the system from "loosely defined and hoping for the best" to "precisely specified and mechanically enforced."

---

**Implementation Gap**
A situation where a requirement is confirmed (agreed upon and approved) but the code doesn't actually implement it yet. The coherence gate is an example: REQ-027 says "Develop does not start until the cross-area coherence check passes," and that requirement is confirmed — but the PI Lead's code never runs the coherence check. The requirement exists; the build does not. An implementation gap is different from a missing requirement.

---

**Job Card**
The informal name for the agent's stored prompt — the instructions it receives at the start of every run. A proper job card tells the agent its role, its hard rules, what it must produce, and how it must report back. Today most job cards are loose and vague. AGP-003's job card, for example, describes steps the agent doesn't actually perform (the conductor does them instead), creating a false picture of what the agent does.

---

**Layer A / B / C / D**
The four conceptual layers of the agent architecture. Layer A is the conductor (the release pipeline state machine). Layer B is the two LLM planning agents (Reconciliation and Decomposition). Layer C is the development organization substrate (PM, PI Lead, Phase Specialist tiers — mostly deterministic code, not LLM agents). Layer D is the area specialists — the actual coding agents that do the work. Releases flow from Layer A down through B, C, and D and back up.

---

**Live Records**
The actual rows in the governance database as they exist right now, not a cached snapshot. When the conductor "reads live records each tick," it means it queries the database fresh every time it needs to decide what to do next. If an agent just updated a Work Task to Complete two seconds ago, the conductor sees that on its very next read.

---

**Merge**
The act of taking the work an area specialist did on its private branch and combining it back into the main shared codebase. The runtime (not the agent) performs the merge after verifying the agent's work passed the tests. Agents are explicitly prohibited from merging or pushing — that authority belongs to the runtime.

---

**Needs Attention (needs_attention)**
A flag an agent can set on a Workstream to signal "I hit a problem I can't resolve — a human needs to look at this." Today agents have no path to set this flag themselves — only the runtime sets it, after the fact, when it detects something went wrong. A properly designed agent would set needs_attention proactively when it discovers a mis-scoped task, a duplicate, a missing dependency, or an absent done-condition, and then stop rather than produce filler work.

---

**Operating Protocol**
The step-by-step procedure an agent follows during its run: (1) claim the task, (2) do the work, (3) commit, (4) verify, (5) mark Complete, (6) exit. The current operating protocol has no "Step 0: check if this work is already done" and no time budget on verification, which is why REL-005's agent could spin for 30 minutes on a test suite before being killed. A corrected protocol adds Step 0 validation, moves commit before verify, and adds a time budget with an "on overrun → commit and report what's done" instruction.

---

**Phase**
One of the three sequential stages that every Planning Item's work passes through: Design (figure out exactly what to build), Develop (build it), and Test (verify it works). All areas must complete their Design tasks before any area starts its Develop tasks, and all areas must complete Develop before any area starts Test. In the database these phase containers are called Workstreams.

---

**Phase Gate**
The check that must pass before the pipeline advances from one phase to the next. For example, the gate between Design and Develop currently only checks "are all Design tasks marked Complete?" A stronger gate would also run the cross-area coherence check to make sure the different areas' designs actually agree before anyone starts building.

---

**PI Lead**
The tier-2 agent (actually a deterministic substrate, not an LLM) responsible for phase gating within a single Planning Item. It starts phases when their predecessor is complete, declares phases complete when all their tasks are done, and rolls up needs_attention flags. It is the component that should be running the coherence check between Design and Develop — but currently doesn't.

---

**Pipeline**
The fixed sequence of stages a release moves through from initial planning to shipped: preliminary_planning → development_planning → reconciliation → architecture_planning → ready → development → qa → testing → deployment → shipped. The pipeline position is stored in a single `release_status` field on the release record. The conductor drives the release through this pipeline one step at a time.

---

**Planning Item (PI)**
A chunk of work within a release — roughly one feature or one requirement's worth of work. A release is made up of one or more Planning Items. Each Planning Item goes through its own Design → Develop → Test cycle. Planning Items are identified with codes like PI-230 or PI-231.

---

**Profile Gap**
The situation where a Work Task arrives labeled with an area (like "ui") but no agent profile exists for that area. Today only five profiles exist (AGP-001 through AGP-005), covering only storage and a few planning-level roles. There are zero profiles for ui, access, api, mcp, or any tester role. When a ui task arrives and there's no ui profile, the system falls back to the storage developer's card — and the UI agent boots with database-flavored instructions and no UI-specific rules at all.

---

**Reconciliation Agent (AGP-003)**
The first LLM agent in the pipeline. The conductor hands it the full list of confirmed requirements for the release, and it produces a reconciled demand-set: a precise, tidy list of exact data changes needed. If two requirements contradict each other, it's supposed to flag the conflict rather than quietly pick one. The conductor then does the actual persisting and conflict-resolution — the agent only produces the change-list. Today its job card describes several steps it doesn't actually perform, creating a misleading picture of its authority.

---

**Registry**
The database table that stores all agent profiles (AGP records). It is the authoritative source of agent contracts. When a Work Task needs to be assigned to an agent, the system looks up the registry to find the right profile for that area and tier combination. If no matching profile exists, today the system falls back to the nearest available profile — which is the source of the profile gap problem. The fix is to refuse the task rather than misroute it.

---

**Release**
The top-level container for a batch of work being shipped together. A release has a scope (which projects and Planning Items it includes), a pipeline status (where it is in the development process), and a governance record in the database. Only one release can be in the dev lane at a time. Releases are identified with codes like REL-005.

---

**Requirement (REQ)**
A formal, database-stored statement of something the system must do, with an acceptance criterion that makes it testable. Requirements have lifecycle states (candidate → confirmed → deferred / rejected) and can be linked to the decisions that created or changed them. In this session, several new requirements were captured (REQ-277 through REQ-283) and several existing confirmed requirements were amended when their scope became stale.

---

**Runtime**
The Python code infrastructure that manages agents — spawning them, handing them their instructions, watching for them to finish, verifying their results, and merging their work. The coordinating runtime and parallel runtime are the two variants (serial vs. pooled). The runtime already owns the test-running machinery (`select_test_target`, `run_pytest`, `verify_result`) that agents were redundantly re-running during REL-005.

---

**Seam**
A point in the code where one component hands off to another — specifically, a place where the deterministic substrate calls out to an LLM agent. There are four seams in the pipeline: the demands/reconciliation call, the decomposition call, the area specialist spawns, and the QA/test gates. "The code seam" is the precise location in the source code where a gap or fix lives.

---

**Spawn**
The act of starting a new agent instance. When the coordinating runtime is ready to assign a Work Task, it "spawns" an agent: creates a fresh worktree off main, resolves the right agent profile from the registry, builds the combined instruction sheet (job card + hard rule + operating protocol + task), and launches the agent process. Each spawned agent is independent and isolated.

---

**State Machine**
A system that can only be in one state at a time and can only move between states in pre-approved ways. The release pipeline is a state machine: a release is always in exactly one pipeline state (like "development" or "qa"), and it can only move to states that are on the allowed-transitions list. You can't jump from "development" directly to "shipped" — you have to go through qa, testing, and deployment first. This rigidity is intentional; it makes the pipeline predictable and prevents states from being skipped.

---

**Tier**
The level of expertise an agent has within its area. The three tiers are Architect (designs the solution), Developer (builds it), and Tester (verifies it works). For build areas (storage, access, api, mcp, ui), all three tiers exist. For design-only areas (methodology), only the Architect tier is needed. A Work Task's area label and tier together determine which exact agent profile should handle it — today most tier combinations have no profile at all.

---

**Topic (TOP)**
A hierarchical grouping of requirements in the V2 database. Topics are organizational lenses — they group related requirements together for review but don't get built themselves. The agent guardrails work lives under TOP-099; observability lives under TOP-100; the broader Agent System lives under TOP-005. Requirements can belong to one topic and refine or extend requirements in other topics.

---

**Verification / Verify**
The act of checking that an agent's work is correct before accepting it. There are two kinds of verification discussed in this session: (1) the runtime's post-agent check (did the task get marked Complete? did the branch get commits? do the affected tests pass?), and (2) the agent's own self-check before marking itself done (today: run the linter and tests). The core architectural question was whether agents should self-verify or whether the runtime should own the test gate. The answer leaned toward runtime-owns, because self-verification is exactly where the 30-minute spin disaster occurred.

---

**Worktree**
A separate, isolated copy of the codebase created specifically for one agent's use. When an area specialist is spawned, it gets its own worktree — like a private sandbox — so it can make changes without touching anyone else's work. When the agent is done and its work is verified, the runtime merges the worktree's branch into main and discards the worktree. If an agent is killed before committing, everything in its worktree is lost.

---

**Work Task (WTK)**
The smallest unit of work in the system: one specific piece of work, in one area, sized for a single agent session. A Work Task always belongs to exactly one phase (Design, Develop, or Test) of exactly one Planning Item, and is labeled with exactly one area. It has a title, a description, and — in the properly designed version — an acceptance criterion written by the Decomposition Agent at planning time. Work Tasks are identified with codes like WTK-174 or WTK-176.

---

**Workstream (WSK)**
The database name for a phase container. A Workstream represents one phase (Design, Develop, or Test) within one Planning Item. When the Decomposition Agent breaks a Planning Item into phases, it creates three Workstream records. Work Tasks live inside Workstreams. The PI Lead manages the Workstream lifecycle — opening and closing each phase as it progresses. Workstreams are identified with codes like WSK-150 or WSK-154.
