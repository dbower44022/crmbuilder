# CBM Redo — Ground Rules for the Simulated Phase 1 Test

**Document type:** Active design work for an evolved methodology test (research / not adopted)
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/evolved-methodology/cbm-redo/cbm-redo-ground-rules.md`
**Last Updated:** 04-30-26 16:55
**Version:** 0.1 (initial draft)

---

## Status

This document is **active design work for an evolved methodology test that has not been executed.** It establishes the ground rules under which the simulated Phase 1 redo of the CBM engagement will be run. It is the third artifact in the research stack:

1. `iterative-methodology-research.md` — the philosophical position
2. `evolved-methodology-phase-outline.md` — the methodology skeleton
3. `phase-1-interview-guide.md` — Phase 1 operational script
4. **This document** — the rules under which Phase 1 gets tested against CBM material

The current 13-phase Document Production Process and existing interview guides remain authoritative for any active CBM engagement. Nothing in this document changes the original CBM artifacts or the live methodology.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 04-30-26 16:55 | Doug Bower / Claude | Initial draft. Establishes source material rules, legitimate-answer criteria, gap handling, comparison criteria, and confirmation bias mitigation for the simulated Phase 1 redo against CBM material. CBM-specific with generalization markers for future methodology tests. |

---

## Change Log

**Version 0.1 (04-30-26 16:55):** Initial creation. Specifies what CBM artifacts count as the "client's voice" (moderate stance), what the simulated consultant is allowed to know about CBM, how gaps get logged when the source material can't answer a Phase 1 question, the comparison criteria for evaluating the redo against the original CBM engagement, and the confirmation-bias mitigations. Includes a planned validation pass with CBM scoped to specific findings. Generalization markers identify sections that would need parameterizing for a future test against a different client.

---

## 1. Purpose and Scope

### 1.1 What this experiment tests

The simulated Phase 1 redo tests whether the **evolved methodology's Phase 1 interview guide** can produce a workable Prioritized Backbone, Mission Statement, Domain Inventory, and Initial CRM Candidate Set for CBM, using significantly less elicitation effort than the original CBM engagement used to produce comparable artifacts.

It does *not* test:

- The full evolved methodology (only Phase 1 is tested in this round; Phases 2–5 remain unwritten or unvalidated)
- Whether running deployments would surface the same issues as text artifacts (no actual deployment occurs in this experiment)
- Whether real CBM staff would react to the new methodology the way the simulated client does (a small validation pass with CBM is planned but is not a full re-engagement)

### 1.2 What "the simulated Phase 1 redo" means concretely

The redo is an exercise in which Claude (the assistant) plays two roles in alternation:

- **The simulated consultant**, running the Phase 1 interview guide as written
- **The simulated CBM client**, answering the consultant's questions using only the source material this document defines

The roles are kept conceptually separate, even though one entity executes both. The discipline of the experiment depends on each role respecting its own constraints — the consultant doesn't peek at material the simulated client wouldn't volunteer; the simulated client doesn't volunteer material the consultant didn't ask for.

### 1.3 Scope of the redo

The redo runs **Phase 1 of the evolved methodology only**, applied to the CBM engagement in its entirety. The expected output is the four Phase 1 artifacts (Mission Statement, Domain Inventory, Prioritized Backbone, Initial CRM Candidate Set) for CBM as a whole — *not* for a single domain.

This is wider scope than the eventual iteration 1 will be, but it's correct for Phase 1's purpose: Phase 1 produces the prioritized backbone that *spans* whichever domains are needed for end-to-end workability, so it has to consider all CBM domains to make that determination.

---

## 2. Source Material Rules

### 2.1 The moderate stance

The simulated CBM client may "say" anything that meets this test:

> The statement is a factual claim about how CBM operates, makes its mission concrete, or describes its constraints — and the statement is supported by content in CBM-owned documents (see §2.2 for which documents count).

The simulated CBM client may **not** "say":

- Methodology decisions encoded in CBM artifacts. *Priority classifications, domain names, process names, sub-domain structures, candidate-entity lists, candidate-persona lists, cross-domain handoff identifications* — all of these reflect choices made by the original consultant and are exactly what the new methodology's Phase 1 is supposed to make on its own.
- Inferences the original consultant drew that aren't supported by underlying factual claims.
- Anything that comes from CLAUDE.md, prompt files, or session context (see §2.3).

The line between "factual claim" and "methodology decision" is sometimes fuzzy. When unclear, default to the stricter interpretation (methodology decision) and log the call in the gap log. This errs toward making the experiment harder for the new methodology, which is the right direction for honest testing.

### 2.2 In-bounds CBM artifacts

The simulated CBM client may draw on the following CBM-owned documents in the `ClevelandBusinessMentoring` repository:

**Allowed (factual claims only, per §2.1):**

- The CBM Master PRD (for stated mission, organizational overview, stakeholder roles in operational terms)
- Domain PRDs for MN (Mentoring), MR (Mentor Recruitment), and CR (Community Relationships) — only the **operational descriptions** of what CBM does in each area, not the structural choices about which domains exist, how they're named, or what's in each
- Process documents (any domain) — only the **descriptions of activities CBM staff perform**, not the process boundary decisions (which work counts as "this process" vs. "that process")
- Entity PRDs — only the **field descriptions and operational use of records**, not the entity boundaries themselves
- Any meeting transcripts or stakeholder review notes in the repository — these are typically the most direct expressions of the CBM client's voice and are highly weighted

**Out-of-bounds entirely:**

- The CBM CLAUDE.md
- All prompt files (SESSION-PROMPT, UPDATE-PROMPT, CLAUDE-CODE-PROMPT)
- Pilot findings documents
- The reconciliation documents (which are by definition methodology decisions about how to organize CBM's information)
- This research stack and any of its commits

**Generalization marker:** For a future test against a different client, the in-bounds list would parameterize as: *"Client-owned operational documentation, with all methodology-decision content (priority classifications, structural taxonomies, accumulated session context) excluded."*

### 2.3 Why CLAUDE.md and prompt files are excluded

The CLAUDE.md files and prompt files contain accumulated context across many sessions. That context encodes:

- Methodology decisions made over time (priority classifications, phase progressions, deferred items)
- Specific operational decisions about how to handle CBM (which person is the primary contact, which artifacts have been completed, what the current pilot is testing)
- Distilled summaries that pre-package CBM's situation in ways that benefit any agent reading them

Allowing the simulated consultant to read these would mean the consultant starts the test with knowledge a real consultant in a fresh engagement would not have. The test would no longer measure whether the new Phase 1 interview can elicit what it needs to — it would measure whether the new interview can confirm what's already in the consultant's context.

**Generalization marker:** For a future client, the equivalent exclusions would be: *any accumulated working memory that exists because of prior consultant engagement with the client (CLAUDE.md, accumulated prompt files, session notes, anything that represents work-in-progress methodology context).* If a client has *no* such accumulated context (a true cold start), this exclusion is moot.

### 2.4 What the consultant *is* allowed to know going in

Per the Phase 1 guide §2 (Pre-Engagement Preparation), the consultant reviews materials the client provides. The simulated equivalents are:

- **Pre-engagement materials.** The simulated consultant may read the CBM Master PRD's mission and organizational overview sections only — analogous to what a real consultant would receive as a prospectus or initial intake document. This is more limited than what's actually available in the repo, but it's a more honest stand-in for "what a real consultant would have at engagement start."
- **Pattern library.** No CBM-specific pattern library entry exists. The consultant operates in "no library entry" mode (per Phase 1 guide §8.1).
- **Org type recognition.** The consultant may recognize CBM as a "nonprofit mentoring organization" and apply general consultant judgment about that org type, but may not draw on CBM-specific accumulated knowledge.

The simulated consultant should *not* read the Domain PRDs, process documents, Entity PRDs, or transcripts in advance. Those materials become available only as the simulated client cites them in response to the consultant's questions during the session.

This is the most artificial part of the simulation. A real consultant would have whatever pre-engagement materials the client sent; in the redo, we're constraining what the consultant has read at the start to keep the test honest. It's a stronger constraint than reality would impose, but it's the right direction for testing whether Phase 1's interview design is sound.

### 2.5 The simulated client's behavior

The simulated client behaves as a **typical, reasonably articulate CBM stakeholder** — neither more forthcoming nor more reticent than a real client would be. Specifically:

- The client answers questions asked, drawing only on the in-bounds source material
- The client does not volunteer information not explicitly asked for, even when the asker would benefit from it (this models real client behavior — clients don't know what consultants need)
- The client speaks in the org's natural language as it appears in the source material — not in methodology terminology
- The client expresses uncertainty when the source material is ambiguous, rather than confidently picking an interpretation
- The client does not push back on consultant proposals using sophistication the source material doesn't support — the simulated client is not a methodology expert

If the consultant asks a question the in-bounds material can't answer, the simulated client says some version of "I'm not sure" or "I'd have to think about that" or "let me get back to you on that" — and the gap is logged (§4).

---

## 3. What Counts as a Legitimate Answer

### 3.1 Three tiers of legitimacy

When the simulated client gives an answer to a consultant question, the answer falls into one of three tiers:

**Tier 1 — Direct.** The answer is supported by an explicit statement in the in-bounds CBM material. The simulated client can give the answer with confidence. Most of the work in Session 1 Part A (operational mission) and Part B (domain identification) should produce Tier 1 answers, because the underlying factual claims about CBM's work are widely documented.

**Tier 2 — Reasonable inference.** The answer is not directly stated in the in-bounds material but can be inferred from multiple supporting statements. The simulated client may give the answer but with explicit hedge — "I think we... but I'd want to confirm." These answers are logged as inferences in the gap log so the validation pass with CBM can confirm or correct them.

**Tier 3 — Not supported.** The answer would require either methodology-decision content (excluded by §2.1) or pure invention. The simulated client must decline to answer — "I'd need to think about that" or "let me check on that and get back to you." These are logged as gaps. The consultant must proceed with the gap unfilled and note that fact in any subsequent proposal.

### 3.2 Examples of the three tiers (CBM-specific)

These examples illustrate the tier system. They are not exhaustive.

**Tier 1 example.** Consultant asks: *"What does CBM do operationally — what would I see your staff doing on a Tuesday morning?"* The simulated client can answer with content drawn from CBM Master PRD or process doc descriptions of mentor matching, mentee intake, session logging, etc. This is direct factual content about CBM's work.

**Tier 2 example.** Consultant asks: *"Are there any handoffs between Mentor Recruitment and Mentoring that are particularly important?"* The in-bounds material describes both domains' work but doesn't explicitly characterize specific handoffs as "particularly important." The simulated client can infer from the operational descriptions — *"Well, we need mentors to be enrolled before we can match them, so I guess that handoff matters"* — but should hedge and the inference goes in the gap log.

**Tier 3 example.** Consultant asks: *"How would you classify Marketing Campaigns relative to your mission — critical or supporting?"* The in-bounds material doesn't classify processes by priority (that's methodology-decision content). The simulated client must decline: *"I'd want to think about that — what counts as critical for us isn't something I have a clear answer to."* The consultant proceeds without the answer and proposes a classification in the between-sessions work; the proposal will be tested in Session 2 against the validation pass with CBM later.

### 3.3 The "would the client have said this on their own" test

When in doubt about whether an answer is legitimate, apply this test:

> If a real CBM stakeholder, in a fresh first engagement with no prior consultant work, were asked this exact question, would they likely give this exact answer?

If yes, the answer is legitimate. If the answer feels too polished, too well-organized, too aligned with what a methodology would want to hear, that's a signal it's drawing on inferences from the original consultant's work rather than from the client's own voice.

---

## 4. Gap Handling

### 4.1 Why gaps are valuable

The gaps the simulator hits during the redo are themselves a primary output of the experiment. They tell us where Phase 1's interview design might struggle in a real engagement — places where a question gets asked but the client doesn't have a ready answer, or places where the methodology assumes information that isn't naturally elicited.

A redo that produces zero gaps is suspicious. A redo with a moderate number of well-characterized gaps is exactly what's expected, and the gaps are part of the comparison. A redo with many gaps means the new Phase 1 interview is over-asking or asking the wrong things, which is also useful information.

### 4.2 The gap log format

Every gap encountered during the redo is logged in `cbm-redo-gap-log.md` (a sibling document to this one, created during the redo). Each entry contains:

- **Gap ID.** Sequential number (G-001, G-002, ...)
- **Session and moment.** Which session (Pre-engagement, 1, 2, between-sessions, 3) and which part of that session
- **Question or proposal that hit the gap.** The exact consultant prompt
- **What the in-bounds material does say.** Brief summary of the closest supporting content
- **Why it's a gap.** Tier 2 (inference made, hedged) or Tier 3 (declined)
- **What the simulator did.** How the simulated client responded; how the consultant proceeded
- **Carried forward to validation pass with CBM?** Yes / No, with reason

### 4.3 Gap-handling rules during the redo

When a Tier 2 inference is made:

- The simulated client gives the inferred answer with explicit hedge
- The consultant treats the answer as soft (not basis for confident proposal)
- The gap log records the inference
- The validation pass plan flags the inference for confirmation

When a Tier 3 gap is hit:

- The simulated client declines the question
- The consultant proceeds without the answer
- If the answer was needed for a subsequent proposal, the proposal is made with explicit acknowledgment that the supporting input was missing, and the proposal is marked as low-confidence
- The gap log records the gap
- The validation pass plan flags the gap as a candidate question for CBM

### 4.4 What gaps the experiment is expected to hit

Based on the Phase 1 interview guide structure and what's likely in the in-bounds material, here are the gaps we anticipate (these are predictions, not pre-determined outcomes):

- **Priority classifications.** The new methodology's Phase 1 has the consultant propose mission-critical / supporting / deferred classifications between sessions. The in-bounds material doesn't contain CBM's own priority statements, so the proposed classifications will be consultant judgment. Many will be hedged or contested in Session 2 in the simulation.
- **Cross-domain handoff identifications.** The consultant's workability check (Phase 1 guide §4.1) requires identifying which mission-critical processes have hand-offs between them. The in-bounds material describes processes within each domain but not necessarily the inter-domain dependencies in handoff terms. Some inferences will be required.
- **CRM candidate set.** The Initial CRM Candidate Set is shaped by client constraints (budget, hosting, IT capacity). The in-bounds material may have some of this information; it likely doesn't have all of it. The candidate set may be partially proposed on consultant assumption.
- **The decision-maker of record (Phase 1 guide §10.2).** Multi-stakeholder organization handling. The in-bounds material identifies stakeholders but may not be explicit about which one's signoff finalizes the four Phase 1 outputs.

If the actual gaps encountered are *very* different from these predictions, that itself is a finding worth examining.

---

## 5. Comparison Criteria

This is the most important section of the document. The comparison criteria define what the experiment can actually tell us. They are specified now, before the redo runs, and should not be changed after the redo begins. If the redo reveals that a criterion was wrongly specified, the right response is to acknowledge the limitation in the findings document, not to retroactively redefine the criterion.

### 5.1 What we are comparing

We are comparing **the redo's Phase 1 outputs and process** against **the equivalent work in the original CBM engagement.**

The equivalent work in the original CBM engagement is the content of:

- The CBM Master PRD (as the original Phase 1 output)
- The Domain Discovery work that produced the original Domain Inventory
- The Inventory Reconciliation work that produced the original Persona and Entity inventories (the Phase 1 redo doesn't produce these but the original methodology did, so this is a scope difference to acknowledge in comparison)
- The portions of Domain PRDs and process docs that establish *which processes exist* (process names, structural decisions) — these are the closest analog in the original methodology to the Prioritized Backbone, even though the original methodology didn't classify priority

The original CBM engagement did not produce a CRM Candidate Set in Phase 1 (it deferred that to Phase 10), so there is no original-engagement equivalent to compare the new Initial CRM Candidate Set against. This is a methodology-shape difference, not a gap.

### 5.2 The comparison criteria

The comparison evaluates the redo on these dimensions. Each is rated using the framing under it; ratings are descriptive ("the redo did X; the original did Y; here's the difference"), not numeric.

**Criterion 1 — Elicitation effort.** How much consultant-and-client time, measured in session-equivalents, did each engagement need to produce its Phase 1-equivalent outputs? The original CBM engagement spans many sessions across what would, in the new methodology, be Phase 1 territory; the redo targets two sessions plus optional third. The ratio is a primary measurement.

**Criterion 2 — Processes correctly identified as mission-critical.** Does the redo's Prioritized Backbone correctly identify the processes that, in retrospect, constitute the mission-critical thread for CBM? The reference for "correctly" is the candidate backbone Doug confirmed in this conversation: Mentor enrollment, Mentee intake, Matching, Session logging. Did the redo's simulated consultant arrive at this list (or close to it) using only the in-bounds material? If yes, that's strong evidence Phase 1 works. If no, that's strong evidence Phase 1 has a problem.

**Criterion 3 — Cross-domain dependencies surfaced.** Did the redo's workability check catch the cross-domain dependency that requires Mentor Recruitment processes to be in a Mentoring backbone? This is the specific issue the iterative methodology is supposed to handle better than the original methodology, so it's a high-stakes test of whether the new approach works.

**Criterion 4 — Quantity of artifacts produced.** How many pages of artifact content does the redo produce vs. the original? The new methodology claims to produce less specification material at Phase 1's stage. The comparison measures whether that's true. Not all reduction is good (skipping necessary content is bad); the comparison should distinguish between *less material because the methodology defers* and *less material because the methodology missed something*.

**Criterion 5 — Decisions made vs. deferred.** What decisions does the redo's Phase 1 *decide* (lock in) vs. *defer* to later phases? The new methodology should decide less at Phase 1 than the original methodology did at the equivalent stage, because the iterative model expects later iterations to validate more. The comparison measures whether the redo's deferral pattern is consistent with the methodology's claims.

**Criterion 6 — Gap profile.** How many Tier 2 inferences and Tier 3 gaps did the redo hit? Where did they cluster? Are the gaps in places that suggest Phase 1's interview design has weak spots, or in places where any methodology would struggle (genuine information unavailable)? The gap profile is primarily diagnostic — it tells us where to revise the interview guide.

**Criterion 7 — Defensibility of proposed classifications.** Are the redo's mission-critical / supporting / deferred classifications grounded in arguments the simulated consultant can articulate from the in-bounds material? Or are they reasonable but unjustifiable from what the simulated consultant could know? This tests whether the "CRM Builder proposes confidently with grounded reasoning" stance (Principle 4) is realistic at Phase 1.

### 5.3 What the criteria deliberately don't measure

- **Whether the resulting CRM works.** Phase 1 doesn't produce a CRM. That's later phases' job. This experiment can't say anything about whether the eventual CRM would be usable.
- **Whether CBM staff would prefer the new methodology.** The simulated client is a stand-in; it's not CBM. Real client preference is a different experiment (a full real engagement) that this redo isn't.
- **Whether the new methodology is faster overall.** Phase 1 is a small fraction of the total engagement. Faster Phase 1 doesn't necessarily mean faster engagement; the iterative model trades some upfront speed for the ongoing iteration loop. This experiment can only measure Phase 1.

### 5.4 What success would look like

A redo result that supports continuing the methodology evolution effort would have most or all of the following:

- Phase 1 completed in two-or-three sessions worth of simulated activity
- The four mission-critical processes (or close approximation) correctly identified
- The cross-domain Mentor Recruitment dependency surfaced
- Substantially less artifact content than the original engagement produced at the equivalent stage
- A clear deferral pattern that aligns with the methodology's claims
- A gap profile that suggests interview design is roughly right, with specific places to refine
- Proposed classifications that the simulated consultant can defend from in-bounds material

A redo result that suggests reconsidering the methodology evolution effort would have:

- Phase 1 stretching into many sessions to get to satisfactory outputs
- Mission-critical processes badly misidentified
- Cross-domain dependencies missed
- Specifications either as long as the original or considerably worse-quality
- Too many Tier 3 gaps to make confident proposals
- Classifications that can't be defended without going back to methodology-decision content

### 5.5 Honest acknowledgment of the comparison's limits

The original CBM engagement and the redo are not running under fair conditions. Specifically:

- **The simulator knows what the original engagement concluded.** Even with §2.1 source material discipline, the assistant can't fully unsee what it knows about how the original engagement ended up. This is the structural confirmation-bias risk addressed in §6.
- **The original methodology was applied by a real consultant with iterative reasoning over many sessions; the simulator runs Phase 1 in a single linear pass.** Some of the original engagement's quality came from extended thinking that the simulation can't replicate.
- **The simulated client is more articulate and patient than real clients.** Real clients miss meetings, change their minds, give vague answers, and surface concerns that don't fit the conversation flow. The simulated client doesn't.

These limits don't invalidate the experiment, but they should be cited in any findings document. The experiment is a useful early-stage signal, not definitive evidence.

---

## 6. Confirmation Bias Mitigation

### 6.1 The core problem

The same entity (Claude) is designing the new methodology, running the simulated test, evaluating the comparison, and reporting the findings. That's four roles that should be separated, and aren't. Without active mitigation, every step of the experiment risks subtly favoring the new methodology — not through deliberate bias but through the natural tendency of any agent to interpret ambiguous situations in ways consistent with hypotheses they're invested in.

This is not a hypothetical risk. It is the most likely failure mode of this experiment.

### 6.2 Mitigations baked into this document

These mitigations are structural — they're in place because of how the experiment is designed, not because of moment-to-moment vigilance:

- **Comparison criteria specified before the redo runs (§5.2).** The criteria can't be retroactively adjusted to favor whichever methodology performed better on a given dimension.
- **Source material rules specified before the redo runs (§2).** The simulator can't relax the rules mid-test to give the simulated client more material to draw on.
- **Tier system requires explicit hedging on inferences (§3).** The simulator can't quietly upgrade Tier 2 inferences to Tier 1 confidence to make the redo look smoother.
- **Gap log is a primary output (§4).** Failures to elicit are recorded, not glossed over. A gap log that's suspiciously short is itself a signal.
- **§5.5 limits are acknowledged.** The experiment doesn't claim more than it can deliver.

### 6.3 Mitigations during the redo

These require active discipline during execution:

- **Session-by-session pause for honest assessment.** After each simulated session, before continuing, write down: *what just happened that the methodology should be uncomfortable about?* Force the question explicitly. If the answer is consistently "nothing," that's a signal something is being suppressed.
- **Steelman the original methodology.** When the redo produces an output that looks better than the original engagement's equivalent output, ask: *what could the original methodology produce that I'm not crediting?* Look for reasons the original engagement made the choices it did before concluding those choices were wrong.
- **No retroactive rule adjustment.** If, during the redo, a rule in this document seems to be producing unfair results, don't change the rule. Run the redo to completion under the original rules, log the issue, and address it in a v0.2 of this document for any future test. Mid-test changes destroy the test's signal.
- **Document the calls.** When the simulator makes a judgment call about whether content is factual vs. methodology-decision (§2.1), or whether an inference is Tier 2 vs. Tier 3, log the call in the gap log with reasoning. This makes the calls auditable later.

### 6.4 Mitigations after the redo

- **Findings document drafted before discussion, not after.** The findings document should be drafted from the gap log and comparison results before any discussion of "what does this mean." Discussion shapes interpretation; raw findings should be captured first.
- **Validation pass with CBM (§7) is the primary external check.** It's the one place in the experiment where the simulator's interpretation gets tested against the original client's reality. Treat its findings as authoritative when they conflict with the redo's findings.
- **Any conclusion that the new methodology is better should clear a higher bar than any conclusion that the original methodology is comparable or better.** If the redo says "the new methodology produced equivalent quality in less time," fine. If the redo says "the new methodology produced higher quality," ask why a methodology designed under known constraints would beat a methodology that ran with no constraints, and require the answer to be specific and grounded.

---

## 7. Validation Pass with CBM

### 7.1 Purpose

The validation pass takes specific findings from the redo to CBM and asks them to confirm or correct. It is not a re-engagement; it is a small, targeted check that catches the worst simulated-interview errors.

### 7.2 Scope

The validation pass should be **one short conversation** — 30–60 minutes — with whichever CBM stakeholder is most appropriate. It is not a methodology demonstration, not a sales conversation, not a redo of any session. CBM should be told upfront what the conversation is for and roughly how long it will take.

### 7.3 What gets carried into the validation pass

From the redo's gap log, select:

- **All Tier 3 gaps that affected backbone composition.** If the redo proposed a backbone that included or excluded a process based on a Tier 3 gap, the gap goes to validation. *"Our analysis suggested X. Is that right?"*
- **All Tier 2 inferences that affected backbone composition.** Same logic, lower confidence — even more important to validate.
- **Specific cross-domain dependencies the redo identified or missed.** The redo's workability check is the new methodology's signature move; the validation pass is the place to confirm whether the workability calls were right.
- **The proposed CRM candidate set.** Validate whether the constraints inferred from the in-bounds material are correct, and whether the proposed candidates actually satisfy CBM's preferences.

### 7.4 What stays out of the validation pass

- Methodology meta-questions ("did this work better?"). The validation pass tests substantive findings, not methodological self-assessment.
- Open-ended exploration ("what else should we know?"). The conversation has a defined scope; expanding it defeats the discipline.
- Anything that would meaningfully consume CBM's time. The validation pass is a courtesy and a sanity check, not a workload.

### 7.5 What to do with validation pass results

The findings document records both the redo's conclusions and the validation pass's confirmations or corrections. Where validation pass and redo agree, the redo's conclusion stands. Where they conflict, the validation pass wins and the redo's conclusion is documented as an error.

A validation pass that produces many conflicts is a strong signal that the new Phase 1 has problems. A validation pass that produces zero conflicts is suspicious — either CBM rubber-stamped (because they're being polite or don't have time) or the redo somehow avoided all the places where it could be wrong, which is unlikely.

---

## 8. The Findings Document

### 8.1 What it is

After the redo completes (including the validation pass), a findings document is produced that synthesizes:

- The redo's outputs vs. the original engagement's equivalent outputs
- The gap log
- The comparison against the criteria in §5.2
- The validation pass results
- Honest assessment per §5.5 and §6.2–§6.4
- A recommendation: continue methodology evolution / pause and revise / abandon

### 8.2 What it isn't

The findings document is not a methodology specification. It is a research artifact that informs whether and how the methodology evolution effort continues. Any methodology changes that follow from the findings are scoped and executed separately.

### 8.3 Drafting discipline

Per §6.4: the findings document is drafted from raw findings (gap log, criteria comparisons, validation pass results) before any interpretive discussion. The first draft is descriptive. Interpretation is added after the descriptive draft is reviewed for completeness. This sequence prevents the findings from being shaped to fit a preferred narrative.

---

## 9. Execution Plan

The redo has the following phases of activity, each producing identifiable artifacts:

1. **Setup.** Confirm in-bounds material list against the actual `ClevelandBusinessMentoring` repo. May reveal that some artifacts are missing or different from memory. Adjust §2.2 if needed (this is the one acceptable rule adjustment, because it's pre-redo).
2. **Pre-engagement.** Simulated consultant reads the limited pre-engagement materials (§2.4). Notes captured.
3. **Session 1 simulation.** Run the Phase 1 guide §3 against simulated client. Capture session output (drafted Mission Statement, preliminary Domain Inventory, process surfacing notes, CRM context notes). Capture gap log entries.
4. **Between-sessions simulation.** Simulated consultant produces proposed Prioritized Backbone and Initial CRM Candidate Set per Phase 1 guide §4. Capture both proposals.
5. **Session 2 simulation.** Run the Phase 1 guide §5. Capture refined outputs and updated gap log.
6. **Optional Session 3 simulation.** Only if §5 surfaces unresolved issues per Phase 1 guide §6.
7. **Pre-validation findings draft.** Capture descriptive findings per §8.3 — what the redo produced, how it compared on each criterion in §5.2, what the gap log shows. No interpretation yet.
8. **Validation pass with CBM.** Real conversation with the appropriate CBM stakeholder, scoped per §7.
9. **Final findings document.** Synthesize per §8.1. Recommend per §8.1.

Each phase produces files in `PRDs/process/research/evolved-methodology/cbm-redo/`. Naming convention: `cbm-redo-{step}.md` (e.g., `cbm-redo-session-1.md`, `cbm-redo-gap-log.md`, `cbm-redo-findings.md`).

### 9.1 Anticipated effort

Steps 1–7 are all-Claude work. Realistic estimate: 3–5 working sessions to complete, depending on how many gaps the redo hits and how detailed the artifact captures need to be.

Step 8 requires CBM coordination and is the schedule constraint. It can happen any time after step 7 is done, but should happen before step 9.

Step 9 is short — a synthesis of completed material.

---

## 10. Generalization Markers Summary

Sections that would need parameterizing for a future test against a different client:

- **§2.2 (in-bounds artifacts).** The CBM-specific document list would be replaced with the equivalent list of operational documents for the other client.
- **§4.4 (anticipated gaps).** The CBM-specific predictions would be replaced with predictions tailored to the other client's available material.
- **§5.1 (what we are comparing).** The CBM-specific reference points (Master PRD, Domain Inventory equivalents) would be replaced with the other client's equivalents.
- **§5.2 Criterion 2 (mission-critical reference list).** The CBM-specific list (Mentor enrollment, Mentee intake, Matching, Session logging) would need to be derived from the other client's situation, ideally before the redo runs.
- **§7.3 (validation pass content).** The CBM-specific stakeholder choice and conversation scope would be replaced.

Sections that are fully generic and would not need parameterizing:

- §2.1 (the moderate stance), §2.3 (CLAUDE.md exclusion logic), §2.5 (simulated client behavior), §3 (legitimate answer tiers), §4.1–§4.3 (gap log mechanics), §5.5 (limits acknowledgment), §6 (confirmation bias mitigation), §8 (findings document discipline), §9 (execution plan structure).

A future generalization effort would be roughly: extract the generic sections into a `simulated-redo-rules.md` template, leave the parameterized sections as a per-client appendix.

---

## 11. What This Document Does Not Cover

- **The pattern library specification.** Referenced by Phase 1 guide §8, not specified anywhere yet. Future work.
- **Document templates for the four Phase 1 outputs.** Phase 1 guide §7 specifies content; physical templates are a separate artifact.
- **What happens after Phase 1 in the redo.** The redo is Phase 1 only. Whether to extend the redo into Phases 2–5 (which would require those phase guides to exist) is a decision for after the Phase 1 redo completes.
- **Coordination with Doug's working preferences.** This document specifies experiment rules, not session-by-session execution discipline. Doug's stated working preferences (one issue at a time, explicit approval before moving on, etc.) apply throughout but aren't restated here.

---

*End of document.*
