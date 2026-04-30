# Iterative Methodology Research

**Document type:** Research and planning (not active methodology)
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/iterative-methodology-research.md`
**Last Updated:** 04-30-26 14:55
**Version:** 0.2 (corrected to match current methodology)

---

## Status

This document describes a proposed direction for evolving the CRM Builder methodology. It is **research and planning only.** No existing methodology has been changed based on this document. The current 13-phase Document Production Process, the existing interview guides, and the existing PRD templates remain authoritative for any active engagement. Any methodology changes derived from this research will be planned and executed in a separate, explicitly-scoped effort.

The purpose of capturing this document now is to preserve the reasoning behind a substantial philosophical shift so that future conversations can build on it without having to reconstruct it from scratch.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 04-30-26 14:30 | Doug Bower / Claude | Initial draft capturing the iterative methodology discussion. |
| 0.2 | 04-30-26 14:55 | Doug Bower / Claude | Corrected phase references to match the actual 13-phase Document Production Process; added a subsection relating the proposed direction to the existing CBM MR pilot; updated the interview guides list to include YAML Generation. |

---

## Change Log

**Version 0.1 (04-30-26 14:30):** Initial creation. Captures the discussion exploring why the current interview-driven methodology produces extensive specifications without confirming the system meets basic needs, and proposes an iterative, multi-deploy, priority-driven alternative. No methodology changes implemented; this is a research artifact only.

**Version 0.2 (04-30-26 14:55):** Corrected references to the Document Production Process to reflect the actual 13-phase structure (the v0.1 draft had referred to it as 12-phase and had several phase numbers wrong, including identifying CRM Selection as Phase 9 when it is Phase 10 and YAML Generation as Phase 8 when it is Phase 9). Added a subsection in §4 relating the proposed direction to the existing CBM Mentor Recruitment pilot (Phases 9 → 11 → 12 → 13), which is a partial validation of the iterative idea. Updated the interview-guides list to include YAML Generation, which exists in the current methodology. No substantive change to the philosophical content.

---

## 1. Executive Summary

The current CRM Builder methodology is optimized for completeness of specification. Its 13-phase Document Production Process produces high-quality requirements artifacts, but it does so through extensive upfront interviewing that treats every requirement — critical and minor — with equal exhaustive depth. After weeks of effort, the client holds thousands of lines of specifications and **no evidence that the resulting system will actually deliver on the mission.**

The proposed direction reorients the methodology around a different success criterion: **rapid, iterative evidence that the tool delivers a working CRM that meets the client's mission-critical needs.** Specifications remain the eventual end state — they are the right artifacts and the current quality bar is correct — but they accumulate alongside an iterative deployment process rather than gating it.

Key elements of the proposed direction:

- A short focused intake produces a **prioritized backbone** of mission-critical processes, with everything else explicitly deferred.
- The backbone is deployed to **multiple candidate CRMs in parallel by default**, turning CRM selection into an empirical comparison of running systems rather than a paper procurement decision.
- The client **iterates against running software**, which they can react to far better than they can react to text.
- **Priority is established at the process level** (mission-critical, supporting, deferred) using the existing mission test, and **inherited downward** to entities, fields, and screens — avoiding the trap of asking about priority for every minor item.
- **CRM Builder proposes priority classifications confidently with grounded reasoning, and the client verifies and corrects.** Priority is not a question put to the client cold.
- **Best-practice defaults fill everything outside the current iteration's scope.** The running system surfaces wrong defaults faster than interviews could.
- **Comparison artifacts surface platform differences honestly without ranking** — CRM Builder makes differences visible and concrete; the client decides which differences matter for them.
- **Full requirements documents accumulate over iterations** rather than being completed up front. They grow up alongside running software, which validates assumptions before they harden.

The result is a methodology that delivers a workable, confidence-building system early and converges on full specification through repeated client engagement with the running product.

---

## 2. The Problem This Research Addresses

The triggering observation was that the existing interview process is not working. Initial framing focused on the interviews being too detailed — multiple confirmations and gory minutiae crowding out the big picture, with critical functionality treated the same as minor issues. "Perfect is the enemy of good."

That framing was correct but incomplete. A second articulation reached the actual problem:

> "I have put weeks of effort into interviews, and have never seen a single output that confirms that the system solves the basic needs. Instead I have thousands of lines of specifications that are very, very difficult to understand if they will provide a viable solution."

The real problem is not that the interviews are too detailed in the abstract. It is that **the artifacts produced — high-quality as they are — cannot answer the question that matters: does this solve the basic need?** Specifications are an especially poor medium for that verification:

- They are hard to read end-to-end, so reviewers skim and miss things.
- They look complete and authoritative even when they encode wrong assumptions.
- Reading a spec and imagining the system are different cognitive tasks. People approve specs they would reject if they saw them running.
- Errors compound silently. A wrong assumption in Phase 2 is baked into Phase 5's documents, and is not surfaced until something is built.

There is also a secondary cost: **the weight of the documentation makes course-correction expensive.** Once a 30-page Process Definition is approved, there is institutional pressure (the consultant's, even more than the client's) to treat it as decided. If the running system later reveals it is wrong, undoing it feels costly. Lighter-weight artifacts that are validated against running software make changes cheap.

A clarifying point Doug raised: **the existing artifacts are not the problem.** Their quality is correct and represents what should eventually be expected from the process. What is wrong is the **order and granularity of how they are produced.** The current process treats the full set of artifacts as the deliverable of a long upfront effort. The proposed direction treats them as the gradually-accumulating record of an iterative, demo-driven engagement.

---

## 3. The New Success Criterion

The methodology's job is not to produce comprehensive specifications. Its job is to **rapidly prove that the tool can deliver a working CRM that meets a specific client's mission-critical needs — and to do that before the client has invested so much time that failure is catastrophic.**

This is a fundamentally different success criterion than what the current 13-phase process optimizes for. The current process optimizes for completeness of documentation. The proposed direction optimizes for **early evidence that the tool works for this client's actual mission.**

A consequence: the highest-value thing to elicit first is not "all the domains" or "all the entities" — it is the answer to *"what would this client need to see running to believe the tool delivers?"* That is usually a small number of things. For CBM, it is something close to: a mentor and a mentee can be matched, an engagement record exists, a session can be logged against it, and the right people can see the right records. If that works, the tool is credible. If it doesn't, no amount of polish on the periphery saves it.

---

## 4. Iteration as the Validation Mechanism

The proposed direction replaces "interview to completion, then build" with "build a thin slice, demo it, iterate." The role of documents shifts accordingly.

In the current model, the Domain PRD for Mentoring is written, reviewed in text, approved, and then implemented. In the proposed model, the Domain PRD for Mentoring **grows up alongside a running Mentoring slice.** The earliest version is thin — based on best-practice defaults plus the few things the client said were critical. Each iteration with the client adds detail, corrects assumptions, and locks down decisions that the demo surfaced. By the time the document looks like the current Domain PRDs, it has been validated against something running, not just against the client's ability to read a spec.

For the CBM engagement specifically, this would have meant: a thin Mentoring slice deployed → CBM reacts → revise → deploy again → CBM reacts → ... and only after Mentoring felt real would Member Relationships have been started, repeating the same loop. The artifacts would have caught up to their current quality, but they would have done so while CBM was watching the system come to life, not while CBM was reading PDFs.

### Implications for the "locked decisions" principle

The current methodology treats approved PRDs as decided and not reopened. In an iterative model, this principle needs a small amendment:

- **Design decisions inside processes that have already been built remain locked.** Once an iteration ships, what it decided about the system is settled.
- **Priority classifications are explicitly not locked.** They are expected to be revisited at the start of each iteration as the system matures and circumstances evolve.
- The change log distinguishes between "what we've decided about the system" (locked) and "what we're working on next" (re-evaluated each iteration).

This is a controlled relaxation of the lock-in rule, not an abandonment of it. The lock simply happens later — when the demo confirms a decision works — rather than earlier when the client approved the text.

### Implications for the client's role

In the current model, the client's job is to **read and approve specifications.** In the proposed model, the client's job is to **react to running software** — try the workflow, notice what's wrong, name what's missing. This is a much easier job for most non-technical stakeholders, which is part of why engagement holds up better through long engagements.

### Relationship to the existing CBM MR pilot

The current Cleveland Business Mentors engagement is running a Mentor Recruitment pilot through Phases 9 → 11 → 12 → 13 (YAML Generation through Verification) specifically to validate that the methodology produces a deployable CRM. That pilot is itself a partial validation of the iterative idea — it does the *"deploy and verify"* step the proposed methodology centers on. The difference is timing: the MR pilot does it *after* Phases 1–7 have produced full specification artifacts for the Mentor Recruitment domain, while the iterative methodology would do it *much earlier and in smaller increments*, with specifications growing up alongside deployments rather than gating them. The MR pilot is therefore a useful data point on whether YAML-driven deployment can produce a working CRM from validated requirements; the iterative methodology asks the further question of whether the same loop, run earlier and more often, can also be the validation mechanism for the requirements themselves.

---

## 5. Multi-Deploy as the Default

A capability already inherent in CRM Builder's architecture takes on new strategic importance under the iterative model: the YAML-driven, automated deployment can target multiple CRMs from the same source, which means **the same iteration can be deployed to two or three candidate CRMs in parallel.**

This inverts the current approach to CRM selection. Today, Phase 10 picks a CRM based on feature matrices, vendor demos, and judgment, and then CRM Builder configures it. The selection is informed by the requirements but is essentially a procurement decision made on paper. Under multi-deploy, **selection becomes empirical rather than analytical.** The client doesn't pick a CRM by reading comparison charts or watching generic vendor demos with someone else's data. They pick a CRM by *using* their own mission-critical processes running on candidate platforms, side by side, with their own terminology, their own entities, their own workflow. The decision criterion becomes "which one feels right when our actual people do our actual work."

This is genuinely different from how anyone evaluates CRMs today. Vendor demos show the vendor's idea of a good workflow. Trial accounts show the platform's defaults. Pilots are expensive and usually only happen with one product. Multi-deploy from CRM Builder is a **multi-platform pilot, generated automatically, with the client's own process running on each.** It is a value proposition the methodology should make a feature of, not a side effect.

### Stance: multi-deploy is the default

Multi-deploy is the assumed mode of operation. Some clients will arrive having already chosen a CRM and want CRM Builder to configure that one only — that is supported as a conscious exception. Most clients, even those leaning toward a particular product, will look at a second system if the marginal cost is near zero, which is the entire premise of CRM Builder's deployment automation.

### Comparison without ranking

A core principle of the comparison artifact: **CRM Builder makes differences visible and concrete; it does not score, rank, or recommend.** The client weighs the differences themselves, because the weighing depends on factors only they fully understand — team tolerance for workarounds, budget, growth plans, integrations, internal politics.

Side-by-side feature-level commentary is the right form. *"CRM A handled the mentor-mentee match natively; CRM B required a custom relationship type and the UI shows it as a generic link."* The client reads that and knows what they're actually choosing between. Numerical scores hide the basis for the score and pretend to objectivity they don't have.

Staying descriptive also protects CRM Builder's credibility as a **neutral instrument.** The moment the methodology starts recommending winners, every engagement becomes an opportunity for the recommendation to be wrong, and trust erodes. Neutrality is a more durable position both commercially and technically.

### Implications for the schema and engines

If multi-deploy is the default, several previously-deferred concerns become priorities:

- **The YAML schema must be honestly platform-neutral.** Features that are "really an EspoCRM concept" cannot remain in the schema without acknowledgment of how they map (or don't) to other targets.
- **A second deployment engine has to exist soon, not eventually.** Portability cannot be validated against one target.
- **The methodology should be honest about a small supported set** of CRMs at any given time — say two or three — rather than claiming universal portability. That is a stronger and more defensible position.

### Handling features one CRM does well and another can't

When a feature is strong on one platform and weak on another, the methodology does not lowest-common-denominator it away. Instead:

1. The feature is deployed to each target as best as that target can express it.
2. The comparison artifact surfaces the gap honestly — what each CRM did, what it didn't, where it diverged from the requirements.
3. The client weighs whether the gap matters for their needs.

This is option 2 (best-effort with honest gaps) flowing into option 3 (client decides), as Doug summarized: "we highlight the differences — benefits and weaknesses of each platform, and the user can decide which meets their needs best." The gaps *are* the comparison; hiding them defeats the purpose.

### Handling shared misclassifications

A useful side effect: if all candidate CRMs feel rough in the same way, the dissatisfaction lands on **CRM Builder's interpretation of the requirements**, because the only common element across deployments is the YAML CRM Builder generated. That is actually a clearer signal of whether requirements are right than a single deployment can give. The iteration loop has to handle "all deployments are wrong in the same way" as a normal outcome, not a failure.

---

## 6. Slice Shape: Vertical Depth Plus Horizontal Connectivity

Within a domain, the first iteration is neither a pure vertical slice (one process, deep) nor a pure horizontal layer (all processes, shallow). It is a **hybrid sized for workability:** enough vertical depth to make the included processes actually usable, and enough horizontal breadth to show how the pieces connect.

Two factors determine where the boundary falls:

**Priority** decides which processes are in the slice at all. For CBM, Mentoring is in. Marketing campaigns are not, even though they live in the same overall system. Within Mentoring, intake and matching are in early because they're how a mentee becomes a mentee; reporting on mentor hours can wait. Priority is about what the client needs to *believe the system works.*

**Interoperability** decides how deep each included process has to go. A process can't stop at its boundary if the next process consumes its output — they have to be deep enough together that the handoff actually happens. If Intake produces a Match-ready record and Matching reads it, both processes need enough depth that the handoff is real, not faked.

This is where pure vertical-slice thinking breaks down: you can't really demo Intake without Matching consuming what it produced, because otherwise the client is reacting to a process whose value they can't see.

### The workability test

A slice is sized correctly if **a real client user, sitting at the deployed instance, can do their actual job for one realistic case from start to finish.** If yes, the slice is workable. If they have to imagine half the steps because they aren't built, the slice is too thin and the demo will feel like vapor.

Stated as a rule of thumb: **include the smallest set of connected processes that, deployed together, let a real user do real work end-to-end on the mission-critical thread.** Everything else is defaulted, stubbed, or omitted from the first iteration.

For CBM, the first iteration's workable slice is something close to Intake + Matching + Session logging. Together those three let a mentee come in, get matched to a mentor, and have that pairing produce trackable activity — a mentoring system in miniature. Onboarding and Departure are in the same domain but can be defaulted or deferred without breaking the demo. Member Relationships, Community Relationships, and Funding are not in iteration 1 at all.

### Why this shape supports multi-deploy comparison

Connected, workable processes also produce a meaningful CRM comparison. When the client experiences Intake → Match → Session running on CRM A and CRM B, they're not comparing screens in isolation, they're comparing **the experience of doing real work.** That is where platform differences actually surface: in the friction between steps, in how naturally the data flows from one process to the next, in whether the platform's defaults align with the work or fight it. A horizontal-only slice wouldn't expose that. A purely vertical single-process slice wouldn't either.

---

## 7. Priority Architecture

The current methodology has no priority concept. Everything in scope is treated as equally important, which is the root cause of the failure mode: critical and minor get the same exhaustive treatment.

A naive fix — add a priority field to every requirement, every entity, every field — would make things worse, not better. Every interview would now include "and what priority is this?" for hundreds of items, and the client would either thrash on the answer or rubber-stamp everything as "high" to move on. Work added without signal added.

The principle that avoids this trap: **priority is established at the level where it actually changes what gets built, and inferred everywhere else.**

### Where priority is set explicitly

**Process level (the primary level).** Each process is classified as one of:

- **Mission-critical** — without this process, the org isn't really doing its mission. Built in the current iteration.
- **Supporting** — real work the org does, but the org could function briefly without it. Built in later iterations.
- **Deferred** — acknowledged but parked indefinitely. Will be revisited as circumstances change.

This classification is the *one* place priority is debated explicitly, and it's debated using the existing mission test ("if this work stopped tomorrow, would the mission be in trouble?") applied at the process level.

**Domain level (only when needed to break ties).** Most engagements have one obvious primary domain (Mentoring for CBM), and the rest are clearly secondary. When that's not obvious — say, an org where two domains are roughly co-equal — the methodology asks once, at the domain level, which leads. It doesn't need to ask repeatedly.

### Where priority is inferred

**Everything below the process level inherits.** Entities, fields, validations, screens, permissions inside a mission-critical process are themselves mission-critical by inheritance. Inside a supporting process, they're supporting. There is no separate priority conversation for *"is the mentee's email field high priority?"* — it inherits the priority of Intake, which is mission-critical, so the field is too.

This is what stops the methodology from being annoying: **the per-field priority question is never asked, because it is already answered.**

### Defaults handle the long tail

For everything not in a mission-critical process, CRM Builder applies best-practice defaults rather than eliciting. The client sees the defaults in the deployed instance and reacts to them, which is the iteration loop doing what specifications can't. Defaults that turn out to be wrong get corrected; defaults that turn out to be fine never required a conversation. This is where the bulk of the time savings comes from.

### Priority changes over time

The classification is not permanent. As iterations progress, supporting processes graduate to "current iteration" status and get the full interview-and-build treatment. Deferred processes can be pulled forward if circumstances change.

The classification is a **sequencing tool, not a value judgment.** Calling something "supporting" doesn't mean it's unimportant — it means it's not in the critical path *right now*. That distinction matters for client conversations, because clients hear "low priority" as "you don't think this matters," which causes friction. "Not in this iteration" is the same information without the sting.

### CRM Builder proposes; the client verifies

Priority classifications are produced by CRM Builder, presented to the client with grounded reasoning, and verified or corrected by the client. Priority is **not** a question put to the client cold.

The reasoning for this stance: **someone has to bring expertise to the conversation, or the methodology is just a transcription service.** A client who has run a nonprofit for fifteen years knows their work intimately, but they don't necessarily know how to translate that work into a prioritized system implementation plan. That translation is a different skill, and it is exactly what CRM Builder should bring. If the methodology defers all priority calls to the client, it pretends the client has expertise they don't have, and the result is either paralysis (everything feels critical when you live it daily) or whatever-the-loudest-voice-said.

The verification step keeps the methodology honest. CRM Builder isn't claiming to know the client's work better than they do — it's offering a structured first pass and inviting correction. *"Here's what we think is mission-critical, here's why, push back where we got it wrong."* That is a much easier conversation for the client than *"please rank your 23 processes from 1 to 23,"* and it produces better results because it's a discussion grounded in reasoning rather than in arbitrary preference.

### Proposals must be confident, not hedged

A wishy-washy proposal — *"these might be the critical ones, but we're not sure, what do you think?"* — invites the client to do the work CRM Builder should be doing, and produces worse results than a clear proposal that turns out to be wrong. **Clients can correct a confident proposal much more easily than they can fix a vague one.**

The interview guides should coach toward something like:

> "We propose Intake, Match, and Session as the mission-critical backbone for Mentoring, because together they're the minimum thread that lets a mentee become a mentee and have that pairing produce trackable activity. If you remove any of the three, the mission breaks. We'd defer Onboarding and Departure to iteration 2 — they're real work but the system functions briefly without them. Does that match how you see it?"

That is a proposal a client can engage with substantively.

### Acknowledged risk: early proposals will sometimes be wrong

Especially before CRM Builder accumulates a deep pattern library across many engagements, proposed priority classifications will sometimes miss. The methodology should acknowledge this openly rather than pretend to authority it has not yet earned. Two things help:

1. **Proposals are grounded in observable evidence**, not just judgment. CRM Builder isn't saying *"we feel Mentoring Intake is critical"* — it's saying *"without Intake, no new mentees enter the system, which means the mission stops."* That is a defensible argument the client can engage with on its merits. When the reasoning is wrong, the client can see *where* it's wrong and correct it precisely.
2. **The iteration loop catches misclassifications quickly.** If CRM Builder proposes the wrong backbone, the first deployed slice won't feel right, and the client will react accordingly. That is a much cheaper way to discover a priority error than building everything and finding out at the end. The cost of being wrong about priority is bounded by the iteration cadence rather than spread across the entire engagement.

---

## 8. Implications for the Existing Methodology

This section names implications without proposing changes. Any changes will be planned and executed as a separate, scoped effort.

### Implications for the 13-phase Document Production Process

- The current Phase 1 (Master PRD), Phase 2 (Domain Discovery), and Phase 3 (Inventory Reconciliation) work persists but becomes lighter — the early elicitation's job is to produce a prioritized backbone, not a complete map.
- Phase 10 (CRM Selection) splits into two activities: an early "narrow the field" step (coarse fit — open source vs. commercial, budget, hosting, integrations) and a late "pick the winner" step driven by lived experience with the candidates.
- Phase 4 (Domain Overview + Process Definition), Phase 5 (Entity PRDs), Phase 7 (Domain Reconciliation), Phase 9 (YAML Generation), and Phase 11 (CRM Deployment) no longer happen sequentially across the whole org. They happen iteratively, scoped to the current iteration's mission-critical slice.
- Phase 12 (CRM Configuration) and Phase 13 (Verification) become per-iteration activities rather than terminal ones.
- Phase 6 (Cross-Domain Service Definition) and Phase 8 (Stakeholder Review) need their own treatment under the iterative model — see open questions.
- A new artifact — the **comparison output** — is produced when multi-deploy is in effect. It captures what each candidate CRM did well, what each did poorly, and where they diverged from the requirements.

### Implications for the interview guides

- The existing interview guides (Master PRD, Entity Definition, Process Definition, Domain Reconciliation, YAML Generation) shift from "elicit everything" to **"elicit the few things that drive priority, then default the rest."**
- Process Definition only fires for mission-critical processes in the current iteration. Supporting and deferred processes are not interviewed yet.
- Entity PRDs are written for entities that mission-critical processes need; defaulted for everything else.
- Guides need to actively support the skill of helping the client see their own operation through the mission lens — including pointed questions like *"if you didn't do X, would the mission stop?"* and willingness to push back when the answer is hand-wavy. This is not the natural mode of a typical interview.
- A new guide may be needed: **slice planning** — how to take the prioritized backbone and decide what makes a workable iteration 1.

### Implications for the schema and engines

- The YAML schema's portability becomes a headline concern rather than an eventual one.
- A second deployment engine needs to exist soon, not eventually.
- Schema features that are platform-specific need explicit acknowledgment of their portability story.

### Implications for the CRM Builder application

- The application needs first-class support for **iteration management** — tracking which processes are in which iteration, which decisions are locked vs. revisitable, and what's in the deferred backlog.
- The application needs first-class support for **multi-target deployment** in a single workflow, not as an afterthought.
- The application needs first-class support for the **comparison artifact** — generating it from the deployment results across targets.

### Implications for the change-log discipline

- Per-iteration change logs become more important, not less. They need to track both locked design decisions and unlocked priority re-evaluations, with the distinction visible.
- The methodology needs a clear convention for how iteration boundaries are recorded in the change log.

### Implications for client engagement

- The client's role changes from "read and approve specifications" to "react to running software."
- Engagement cadence becomes per-iteration rather than per-phase, with each iteration culminating in a working demo.
- The methodology produces better answers to "why aren't you building X yet?" — it can point to the prioritized backbone rather than relying on consultant judgment.
- Pricing and sales positioning likely need adjustment. "We help you specify your requirements and deploy them" is a consulting offer; "we let you run your real processes on multiple CRMs in parallel and pick based on lived experience" is a more distinctive offer that justifies different pricing and a different sales conversation.

---

## 9. Open Questions

This section captures questions raised during the discussion that were either deferred or not fully resolved. They are starting points for future research sessions.

- **How early should the first deployment happen?** Same week? After a one-or-two-session focused intake? After Phase 1–2 only? Discussion did not converge on a specific answer; depends partly on engagement type and partly on how lightweight the early elicitation can become.
- **Which two or three CRMs should CRM Builder support as deployment targets in the near term?** EspoCRM is the de facto first target. The second target's identity affects schema portability work directly.
- **What is the format of the comparison artifact?** The principle is settled (descriptive, side-by-side, no ranking) but the concrete document/UI form is not.
- **How are iteration boundaries marked in the change log?** Current change log conventions handle versioned documents, not iteration cycles.
- **How is CRM Builder's pattern library — accumulating evidence across engagements about what counts as mission-critical for which org types — captured and reused?** Without a pattern library, the priority proposals are based on consultant judgment alone, which limits the methodology's leverage.
- **How does the methodology handle clients who arrive with a CRM already chosen?** Single-deploy is supported as a conscious exception, but the engagement shape and value proposition are different and deserve their own treatment.
- **Does the iterative model change the role of the Cross-Domain Services (Notes, Email, Calendar, Surveys)?** They are structurally parallel to domains in the current methodology but their priority dynamics are not yet thought through under the new model.

---

## 10. Alternatives Considered and Set Aside

This section preserves the alternatives that came up during the discussion and were rejected, so future sessions don't have to re-derive why.

### "Tiered depth" — keep the same process but separate must-have from nice-to-have within each interview

Rejected. This would have helped, but it doesn't address the core problem that the artifacts themselves cannot answer "does this solve the basic need?" Tiered depth still produces specifications-first; the client still doesn't see anything running until the end.

### "Pareto cutoff" — time-box or question-box the interviews and force a stop

Rejected as the primary fix for the same reason. Time-boxing addresses the symptom (too much detail) without fixing the cause (no validation against running software). It also tends to produce arbitrary cutoffs that feel like rationing rather than principled prioritization.

### "Shallow first pass across the whole org, deepen later"

Partially right but incomplete. The "first pass shallow" instinct is correct, but framing it as a *pass over text artifacts* misses the point. The right answer is: first pass produces **deployed software**, not lighter documents. Doug articulated this directly: "I would not explain it as shallow, but focused on getting critical requirements, and make best assumptions for non-critical. Then create an implementation that can be used to refine requirements."

### "Pure vertical slice" — pick one process, build it deep, demo it

Rejected. A single-process slice doesn't show the handoffs to neighboring processes, and so the client is reacting to something whose value they can't see. The mentoring example: Intake alone, with no Matching to consume what it produced, is not a demo of mentoring — it's a demo of a form.

### "Pure horizontal layer" — build all processes shallow

Rejected. A skeleton of every process gives no process the depth to actually be done end-to-end, so the client can't really do real work in the demo. Looks complete, isn't workable.

### "Lowest-common-denominator multi-deploy" — only include features all targets can express faithfully

Rejected. Sacrifices capability and hides the very platform differences the comparison is meant to expose. The differences *are* the comparison.

### "CRM Builder ranks the candidates" — produce a recommended winner

Rejected. Hides the basis for the ranking, pretends to objectivity the methodology can't legitimately claim, and erodes CRM Builder's credibility as a neutral instrument. Side-by-side descriptive commentary is more useful and more honest.

### "Client-led priority classification" — ask the client to rank their own processes

Rejected. Either produces paralysis (everything feels critical when lived daily) or rubber-stamping. CRM Builder bringing prioritization expertise is the value-add; demanding it from the client is the methodology defaulting on its job.

### "Per-field priority" — add a priority field to every requirement

Rejected. Adds enormous interview overhead without adding signal. Priority set at the process level and inherited downward gets the same effect with none of the friction.

---

## 11. Glossary of Terms Introduced

- **Mission-critical process:** A process without which the organization is not really doing its mission. Built in the current iteration.
- **Supporting process:** Real work the organization does, but not on the critical path right now. Built in a later iteration.
- **Deferred process:** Acknowledged but parked indefinitely. May be revisited as circumstances evolve.
- **Prioritized backbone:** The set of mission-critical processes plus the connections between them, which collectively define the first iteration's scope.
- **Workable slice:** A deployment containing the smallest set of connected processes that lets a real user do real work end-to-end on the mission-critical thread.
- **Workability test:** "Can a real client user, sitting at the deployed instance, do their actual job for one realistic case from start to finish?"
- **Multi-deploy by default:** The methodology's assumption that the same iteration is deployed to multiple candidate CRMs in parallel, with single-deploy as a conscious exception.
- **Comparison artifact:** A descriptive, side-by-side output produced from a multi-deploy iteration, surfacing what each candidate CRM did with the requirements without ranking or recommending.
- **Iteration:** A bounded build-deploy-react cycle producing a working slice, accumulated documentation for that slice, and (under multi-deploy) a comparison artifact.

---

*End of document.*
