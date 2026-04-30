# Evolved Methodology — Phase Outline

**Document type:** Active design work for an evolved methodology (research / not adopted)
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/evolved-methodology/evolved-methodology-phase-outline.md`
**Last Updated:** 04-30-26 15:25
**Version:** 0.1 (initial draft)

---

## Status

This document is **active design work for an evolved methodology that has not been adopted.** It is the first concrete artifact produced under the research direction described in `PRDs/process/research/iterative-methodology-research.md`. The current 13-phase Document Production Process and existing interview guides remain authoritative for any active engagement.

This outline is the *skeleton* of the evolved methodology. It is intended to be revised as the bottom-up design work (interview guides, artifact templates, ground rules) reveals composition problems. Treat any decision in this document as provisional until it has been validated by writing the corresponding concrete piece.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 04-30-26 15:25 | Doug Bower / Claude | Initial draft of the medium phase outline plus principles section. |

---

## Change Log

**Version 0.1 (04-30-26 15:25):** Initial creation. Establishes the medium-outline target: name, purpose paragraph, named outputs, named inputs, and phase-to-phase connection note for each phase, plus a principles section that the entire evolved methodology must satisfy. The outline currently proposes five phases. Phase mechanics (participants, cadence, lock/unlock decisions) are intentionally deferred to per-phase design.

---

## 1. Purpose of This Document

This outline serves three jobs:

1. **Aligns Doug and Claude on the overall shape of the evolved methodology** before any interview guides, templates, or rules are written.
2. **Provides the skeleton against which bottom-up design work hangs.** When we write the first interview guide, we know which phase we're writing it for and what it has to produce for the next phase.
3. **Surfaces composition problems early.** If two phases need outputs that can't reasonably both be produced in their predecessor, the outline reveals it before deeper design commits to incompatible structures.

It is deliberately *not* a complete methodology specification. It does not say who participates in each phase, how long each phase runs, what gets locked vs. revisitable inside a phase, or how interview guides are structured. Those questions are answered by the per-phase design work that this outline enables.

---

## 2. Principles

These principles apply to the entire evolved methodology. Every phase, interview guide, artifact, and rule must satisfy all of them. If a design decision later violates a principle, the principle wins by default — the design is wrong.

### Principle 1 — Specifications grow up alongside running software, not before it.

Documentation is the gradually-accumulating record of an iterative engagement, not the gating deliverable of an upfront effort. The artifacts that eventually exist (Domain PRDs, Process Documents, Entity PRDs, etc.) are validated against running deployments before they are considered locked. Specifications written ahead of any deployment are explicitly provisional.

### Principle 2 — Every phase produces something the client can react to in concrete form.

Phases that produce only specifications for client review are at high risk of producing extensive documentation without confirming the system meets basic needs. Wherever possible, phases produce running software, visible artifacts the client can tangibly engage with, or pointed proposals the client can confirm or correct — not lengthy text the client must read and approve.

### Principle 3 — Priority is established at the process level and inherited downward.

Mission-criticality is the consistent organizing principle. Each process is classified as mission-critical, supporting, or deferred using the mission test. Entities, fields, validations, screens, and permissions inside a process inherit the priority of the process. The methodology never asks the client to prioritize individual fields or low-level requirements.

### Principle 4 — CRM Builder proposes; the client verifies.

Where expertise about CRM implementation matters — priority classification, slice composition, default selection, methodology sequencing — CRM Builder proposes confidently with grounded reasoning, and the client verifies or corrects. The methodology does not ask the client cold for decisions that require translation from "how the org works" to "how the system should be built."

### Principle 5 — Multi-deploy is the default; differences are surfaced honestly without ranking.

The same iteration is deployed to multiple candidate CRMs by default. Single-deploy is supported as a conscious exception. Comparison artifacts make platform differences visible and concrete. CRM Builder does not score, rank, or recommend a winner — that judgment belongs to the client.

### Principle 6 — Best-practice defaults fill everything outside the current iteration's scope.

What is not in scope for the current iteration is defaulted, not interviewed. Defaults that turn out to be wrong are corrected through the iteration loop's reaction-to-running-software dynamic. Defaults that turn out to be fine never required a conversation.

### Principle 7 — Decisions inside shipped iterations are locked; priority is not.

Once an iteration ships, what it decided about the system is settled and not casually reopened. Priority classifications, however, are explicitly reviewed at the start of each iteration. The lock applies to design decisions, not to sequencing.

---

## 3. Phase Outline

The evolved methodology is structured as **five phases**, of which **three are recurring (run per iteration)** and **two are bracketing (run once at engagement start and once at engagement end)**.

```
Phase 1:  Mission and Backbone Identification     → engagement start
Phase 2:  Slice Planning                          → recurring per iteration
Phase 3:  Iteration Build and Deploy              → recurring per iteration
Phase 4:  Iteration Review and Comparison         → recurring per iteration
Phase 5:  Engagement Closure and Adoption         → engagement end
```

The recurring trio (Phases 2–4) constitutes the **iteration loop**, which runs as many times as needed to reach the engagement's goal. Each pass through the loop produces a working slice, an updated body of specifications, and a comparison artifact across deployment targets.

The substantial reduction from 13 phases to 5 reflects the methodology's shift in success criterion. The current 13-phase process is structured around **document types** (Master PRD, Domain PRDs, Process Docs, Entity PRDs, YAML, Verification Spec, etc.), each getting its own phase. The evolved methodology is structured around **client-facing milestones** (mission identified, slice planned, slice deployed, slice reviewed, engagement closed). Documents are produced inside phases as they are needed; they are not the organizing principle.

The phases are described below.

### Phase 1 — Mission and Backbone Identification

**Purpose.** Establish the client's mission in concrete operational terms, identify the domains that serve it, and produce a prioritized backbone of mission-critical processes spanning whichever domains are required for end-to-end workability. This phase replaces the current Master PRD, Domain Discovery, and Inventory Reconciliation phases (1–3), and absorbs the early portions of Domain Overview and Process Definition (Phase 4) only insofar as they're needed to identify which processes are mission-critical.

**Inputs.** Client-provided context about the organization (mission statement, organizational chart, existing process documentation if any, prior CRM artifacts if any), and any background research CRM Builder does on similar org types.

**Outputs.**

- **Mission Statement** — a one-page document expressing the client's mission in language CRM Builder can use as the priority test ("if X stopped tomorrow, would the mission be in trouble?"). Drafted by CRM Builder from intake conversation, verified by the client.
- **Domain Inventory** — short list of domains relevant to the mission, with one-paragraph descriptions. Proposed by CRM Builder, verified by client. Lighter than the current Domain Discovery Report.
- **Prioritized Backbone** — the named set of processes (drawn from across whichever domains are needed) that constitute the mission-critical thread for end-to-end work, plus the connections between them. Includes deferred-processes list. Proposed by CRM Builder, verified by client.
- **Initial CRM Candidate Set** — two or three CRM products selected for multi-deploy based on coarse fit (open source vs. commercial, hosting, budget, integrations, team-IT). Proposed by CRM Builder, verified by client. Final selection happens at Phase 5.

**Connection to next phase.** The Prioritized Backbone is the input to Phase 2 (Slice Planning), which decides which processes from the backbone are in iteration 1. The Initial CRM Candidate Set is the input to Phase 3 (Iteration Build and Deploy) and persists across all iterations.

**Why this phase exists.** Without a prioritized backbone, the iteration loop has no principled basis for deciding what to build first. Without a candidate set, multi-deploy can't happen. Both have to exist before iteration begins, and both depend on the mission being explicit.

### Phase 2 — Slice Planning

**Purpose.** Decide what's in the current iteration. For iteration 1, this means selecting from the Prioritized Backbone the smallest set of connected processes that lets a real user do real work end-to-end on the mission-critical thread. For later iterations, this means deciding which previously-deferred processes graduate to current scope based on what the prior iteration's deployment revealed.

**Inputs.**

- For iteration 1: Prioritized Backbone from Phase 1, Mission Statement.
- For iteration N (N>1): Prior iteration's Comparison Artifact (Phase 4 output), updated Prioritized Backbone, any new client-stated needs.

**Outputs.**

- **Iteration Plan** — a short document naming the processes in the current iteration, the connections that must work between them, the workability test that defines "done" for the iteration, and any explicit defaults for processes adjacent to the iteration scope (so the deployment doesn't have visible holes where defaults can stand in). Proposed by CRM Builder, verified by client.
- **Defaulted-vs-Elicited Map** — a short companion document declaring, for each process in the iteration, which aspects will be elicited in detail and which will use best-practice defaults that the running system will surface for client reaction. This is what stops the methodology from over-eliciting; the map is explicit about where deep questioning fires and where it doesn't.

**Connection to next phase.** The Iteration Plan and the Defaulted-vs-Elicited Map are the input to Phase 3 (Iteration Build and Deploy), which executes them. The Iteration Plan also tells Phase 4 (Iteration Review and Comparison) what the workability test is.

**Why this phase exists.** The methodology's whole claim to time-savings rests on being deliberate about what gets interviewed vs. defaulted. That decision is made here, once per iteration, on the record. Without an explicit Defaulted-vs-Elicited Map, the methodology drifts back toward eliciting everything.

### Phase 3 — Iteration Build and Deploy

**Purpose.** Produce the artifacts the iteration needs (process documents, entity PRDs, YAML for the iteration's scope) and deploy them to the candidate CRMs. This is the phase where the iteration's specifications are actually written, but only at the depth the Defaulted-vs-Elicited Map permits — and only for the processes in scope for this iteration. Specifications outside iteration scope remain stub or absent.

**Inputs.** Iteration Plan, Defaulted-vs-Elicited Map (from Phase 2), Initial CRM Candidate Set (from Phase 1).

**Outputs.**

- **Process Documents** for each in-scope process, written at depth proportional to what the iteration needs. Quality of the eventual full documents (per existing standards) is the target, but they may be incomplete in iteration 1 and grow in later iterations.
- **Entity PRDs** for entities the in-scope processes touch.
- **YAML files** for the iteration's scope, generated from the process docs and entity PRDs.
- **Deployed instances** — the YAML applied to each candidate CRM in the Initial CRM Candidate Set. Multiple instances by default; one if the client opted in to single-deploy.
- **Deployment Logs** — what was attempted on each target, what succeeded, what failed, what was substituted.

**Connection to next phase.** The deployed instances and the deployment logs are the input to Phase 4 (Iteration Review and Comparison), where the client reacts to them.

**Why this phase exists.** This is the phase where specifications meet running software. The principle that specs grow up alongside running software (Principle 1) is enacted here — specs and deployment are produced together, not specs first and then deployment.

**A note on the relationship to the current methodology.** This phase compresses what is currently Phases 4 (Domain Overview + Process Definition), 5 (Entity PRDs), 6 (Cross-Domain Service Definition), 7 (Domain Reconciliation), 9 (YAML Generation), 11 (CRM Deployment), and 12 (CRM Configuration) into a single phase scoped to the iteration. The compression is possible because the iteration's scope is narrow — we are not trying to do the whole org's worth of these activities at once.

### Phase 4 — Iteration Review and Comparison

**Purpose.** Get the client to react to the running system on each deployment target, capture the differences between targets honestly, and produce findings that feed into the next iteration's Slice Planning. This is the phase where the client's role is concretely "react to running software" rather than "read specifications."

**Inputs.** Deployed instances, Deployment Logs, Iteration Plan (with its workability test).

**Outputs.**

- **Workability Verdict** — does the deployed slice pass the iteration's workability test? Yes/no with specifics, not a numerical score. If no, what failed and on which targets.
- **Comparison Artifact** — descriptive, side-by-side account of how each candidate CRM handled the iteration's processes. Surfaces benefits and weaknesses of each platform without ranking. Includes notable divergences from the requirements (gaps where a target couldn't faithfully express the spec).
- **Updated Specifications** — process documents, Entity PRDs, and YAML revised based on what running software revealed. This is where decisions get locked (per Principle 7) — the iteration ships with its specifications validated against the deployed reality.
- **Backlog Updates** — what new things did the client surface during review? What previously-deferred items did they newly flag as important? What did they say they care less about than expected? These feed the next Phase 2 cycle.

**Connection to next phase.** If the engagement continues with another iteration, outputs feed back to Phase 2 (Slice Planning). If the engagement is closing, outputs feed Phase 5 (Engagement Closure and Adoption).

**Why this phase exists.** Without an explicit review-and-compare phase, the iteration loop has no defined point at which decisions get locked or at which the client's reaction is captured into the methodology's record. The phase is also what produces the multi-deploy comparison value — it has to be a deliberate output, not a side effect.

### Phase 5 — Engagement Closure and Adoption

**Purpose.** When the client decides the iterations have reached their goal — typically when the system covers the mission-critical work to a depth they can rely on — close the engagement by selecting a CRM from the candidate set, finalizing the chosen instance, and producing the durable artifact set. This phase replaces the late portion of the current Phase 10 (CRM Selection) and the current Phase 13 (Verification).

**Inputs.** Cumulative Comparison Artifacts from all iterations, full set of accumulated specifications, deployed instances on candidate CRMs.

**Outputs.**

- **CRM Selection Decision** — the client picks the winning CRM from the candidate set, based on lived experience across iterations and the cumulative Comparison Artifact. CRM Builder facilitates the decision process but does not make the recommendation.
- **Decommissioning of non-selected instances** — clean shutdown of the CRMs not chosen.
- **Durable Specification Set** — the accumulated specifications, finalized and aligned with the running selected instance. This is the artifact set that approximates what the current methodology produces — but it has been validated against running software at every step.
- **Verification Spec** — generated from the YAML against the selected CRM, confirming the deployment matches the specifications.
- **Handover Materials** — administrator documentation, training notes, integration guidance specific to the selected CRM. Produced once, against one platform, rather than across all candidates.

**Connection to nothing else.** Phase 5 is terminal. The engagement is complete after it.

**Why this phase exists.** The iteration loop alone never terminates without an explicit closure phase. Phase 5 also handles the platform-specific work (handover materials, final verification) that doesn't make sense to do across all candidates — it only makes sense to produce these artifacts once the client has chosen one CRM.

---

## 4. What This Outline Does Not Yet Specify

These are the design questions that the bottom-up work needs to answer. They are listed here so the outline doesn't pretend to have addressed them.

- **Phase mechanics.** Who participates in each phase (CRM Builder consultant only, consultant + client, client only)? What's the cadence (single session, multiple sessions, async)? What does an interview guide for each phase actually look like?
- **Lock/unlock conventions inside iterations.** Phase 4 mentions "decisions get locked." What format does the lock take? How is it visible in the change log? How is it distinguished from priority classifications, which remain unlocked?
- **The Defaulted-vs-Elicited Map's actual format.** The outline names this artifact but doesn't specify how it's structured. The format will affect whether the methodology stays disciplined about not over-eliciting.
- **The Comparison Artifact's actual format.** Same — named but not yet specified. Format affects whether the comparison is truly descriptive-without-ranking.
- **Cross-domain inheritance during multi-iteration engagements.** When iteration 2 introduces processes from a new domain, what does the methodology do about shared entities, cross-domain services, and personas that span domains?
- **Handling clients who arrive with a CRM already chosen.** Single-deploy is supported as a conscious exception. What changes about each phase when single-deploy is in effect?
- **Stakeholder Review's role in the evolved methodology.** Current Phase 8 is dedicated to stakeholder review outside Claude. The evolved methodology folds review into Phase 4 (Iteration Review). Is that sufficient, or is a separate stakeholder-review activity still needed for organizations with multiple stakeholders who need to weigh in?
- **The pattern library.** Principle 4 says CRM Builder proposes confidently. Confident proposals require something to draw on beyond consultant judgment. How does CRM Builder accumulate and reuse priority classifications, default sets, and slice templates across engagements?
- **Cross-Domain Services (Notes, Email, Calendar, Surveys).** How are they handled in the iterative model? Are they part of the prioritized backbone? Defaulted? Phased in by iteration?

---

## 5. Open Questions on the Outline Itself

Questions specifically about the structure proposed in this document, as opposed to the deeper design questions above.

- **Is five phases the right number?** Could Phase 1 and Phase 2 reasonably be merged for iteration 1 (since Phase 2 for iteration 1 has nothing to react to except Phase 1's output)? Could Phase 5 be subsumed into a final pass through Phases 2–4?
- **Is "Mission and Backbone Identification" one phase or two?** Mission identification and backbone identification are conceptually different activities — the first is about understanding the org, the second is about translating that understanding into a prioritized list. Combining them keeps Phase 1 short, but separating them might give the priority work more deliberate attention.
- **Does Phase 4 belong to CRM Builder or to the client?** The client is doing the reacting; CRM Builder is capturing it. The phase's center of gravity matters because it affects how interview guides and templates are designed.
- **Where does the existing CBM MR pilot fit in this structure?** The MR pilot is already running Phases 9 → 11 → 12 → 13 of the current methodology. In the evolved structure, that work corresponds roughly to Phase 3 (Iteration Build and Deploy) of an iteration whose Phase 1 and Phase 2 happened under the old methodology. This is worth being explicit about because the MR pilot may be a natural data source for testing whether the evolved methodology's Phase 3 makes sense.

---

## 6. Next Steps

This outline is the first artifact. It needs to be validated by writing the next concrete piece, which will reveal whether the outline holds up.

The natural next concrete piece is the **Phase 1 interview guide** — the script CRM Builder uses to walk a new client through Mission and Backbone Identification. Phase 1 is the right place to start because:

- It is the entry point of the methodology; if it's wrong, everything downstream is wrong.
- It exercises Principles 3 and 4 (priority architecture, CRM Builder proposes / client verifies) directly, which are the most distinctive parts of the methodology.
- Writing it will force decisions about pattern library use, confident-proposal language, and the format of the Mission Statement, Domain Inventory, and Prioritized Backbone outputs.
- It's also the natural starting point for the CBM redo — whatever Phase 1 looks like is what we run against the existing CBM material first.

After Phase 1 is drafted, we revise this outline based on what we learned, then proceed to Phase 2.

---

*End of document.*
