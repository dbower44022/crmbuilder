# Evolved Methodology — Phase 1 Interview Guide

## Mission and Backbone Identification

**Document type:** Active design work for an evolved methodology (research / not adopted)
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/evolved-methodology/phase-1-interview-guide.md`
**Last Updated:** 04-30-26 23:45
**Version:** 0.2 (revised after CBM redo and pattern library specification)

---

## Status

This document is **active design work for an evolved methodology that has not been adopted.** It is the first interview guide produced under the research direction in `PRDs/process/research/iterative-methodology-research.md` and the outline in `PRDs/process/research/evolved-methodology/evolved-methodology-phase-outline.md`. The current 13-phase Document Production Process and existing interview guides remain authoritative for any active engagement.

This guide is **provisional**. It has not been used in a real engagement; the first test will be the simulated CBM redo. Treat any procedure or wording in this document as subject to revision based on what the redo reveals.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 04-30-26 16:10 | Doug Bower / Claude | Initial draft of the Phase 1 interview guide for Mission and Backbone Identification. Two-session structure with optional third, pattern-library-aware, structured guide with worked examples for hard moments. |
| 0.2 | 04-30-26 23:45 | Doug Bower / Claude | Revised after CBM redo experiment and pattern library specification. Three substantive revisions: §2 pre-engagement reading scope expanded to include operational role definitions; §3 and §5 Tier 2 inference discipline tightened to require positive support in in-bounds material rather than pattern-matched plausibility; §8 pattern library handling rewritten to reflect the actual library mechanics from the spec. Several smaller clarifications elsewhere. |

---

## Change Log

**Version 0.1 (04-30-26 16:10):** Initial creation. Establishes the operational script for Phase 1 of the evolved methodology. Two sessions plus between-session draft work; structured walkthroughs with worked example dialog for confident-proposal moments, push-back moments, and deferred-vs-elicited transitions. Pattern library handling is structural, with explicit fallback to consultant judgment when no entry exists. Failure modes are documented for the most common ways Phase 1 can go wrong. Output specifications cover the four Phase 1 outputs (Mission Statement, Domain Inventory, Prioritized Backbone, Initial CRM Candidate Set).

**Version 0.2 (04-30-26 23:45):** Revised after the CBM redo experiment (`cbm-redo/`, completed 04-30-26) and the pattern library specification (`pattern-library-specification.md`, committed 04-30-26). Three substantive revisions:

- **§2 (Pre-engagement preparation) revised** to include operational role definitions in pre-engagement reading scope. The CBM redo Step 8 §3 finding established that the v0.1 scope was too narrow — holding back the persona section of the Master PRD as "methodology-organized content" cost the simulator access to operational facts about role ownership (e.g., the Funding Coordinator role at CBM) that a real consultant would benefit from at engagement start. The revised scope distinguishes "operational facts about who owns what work" (in scope) from "methodology-decision content about how to organize that information" (out of scope).

- **§3 and §5 (Session 1 and Session 2 discipline) revised** to tighten the Tier 2 inference rule. The v0.1 implicit standard allowed Tier 2 inferences when supporting content existed in the in-bounds material; the CBM redo Step 8 §2-3 findings established that "supporting content" was being interpreted as "pattern-matched plausibility from generic operations," which produced fabrications. The revised rule requires Tier 2 inferences to have **positive support in in-bounds material** rather than pattern-matched plausibility, and the rule is now made explicit in §3.5 and §5.4 rather than implicit.

- **§8 (Pattern library handling) rewritten** to reflect actual library mechanics from the now-existing `pattern-library-specification.md`. The v0.1 §8 referenced the library as a future artifact with concrete handling for "no library entry" mode and aspirational handling for "library entry exists" mode. With the spec and first entry (`pattern-library-entry-nonprofit-mentoring.md`) now committed, §8 has been replaced with concrete consultation steps from spec §4.1 and §4.2, the Section A/B/C content treatment, and the library-backed-vs-judgment-only framing distinction from spec §4.3.

Smaller clarifications elsewhere: §1.4 (reading order) updated to reference the pattern library specification as required reading; §2.2 (consult the pattern library) expanded with concrete steps; §11 (connection to Phase 2) lightly updated; §12 (gaps) updated to remove items now covered.

---

## 1. Purpose and How to Use This Guide

### 1.1 What Phase 1 produces

Phase 1 produces four artifacts that together define the engagement's starting point:

1. **Mission Statement** — a one-page document expressing the client's mission in operational terms, suitable for use as the priority test ("if X stopped tomorrow, would the mission be in trouble?").
2. **Domain Inventory** — a short list of domains relevant to the mission, with one-paragraph descriptions.
3. **Prioritized Backbone** — the named set of mission-critical processes spanning whichever domains are required for end-to-end workability, plus the connections between them. Includes a deferred-processes list.
4. **Initial CRM Candidate Set** — two or three CRM products selected for multi-deploy based on coarse fit.

These four outputs are the input to Phase 2 (Slice Planning) and persist throughout the engagement.

### 1.2 What this guide does not cover

- **Detailed process definition.** Phase 1 names mission-critical processes and identifies their connections; it does not define how they work in detail. That happens in Phase 3 (Iteration Build and Deploy) for processes in the current iteration.
- **Entity definition.** Phase 1 may surface entity names as nouns the client uses, but does not produce Entity PRDs.
- **Final CRM selection.** Phase 1 narrows the candidate field to a small set for multi-deploy. The winning CRM is selected at Phase 5.

### 1.3 Audience

The primary reader is the CRM Builder consultant who will run the sessions. Reasoning behind the guide's structure lives in the phase outline and research documents.

### 1.4 Reading order

Read the guide end-to-end before Session 1, even if Session 1 is far off. The Between-Sessions Work section in particular determines what notes to take during Session 1. Going in without knowing what the next session needs makes Session 1 less efficient.

Also read `pattern-library-specification.md` before running this guide for any engagement. The pattern library mechanics shape pre-engagement reading (§2.2 of this guide) and between-sessions consultant work (§4 of this guide). Without familiarity with the spec, the guide's library references will not be actionable.

---

## 2. Pre-Engagement Preparation

Before Session 1, the consultant does the following:

### 2.1 Review what the client has provided

Typical pre-engagement materials include the org's mission statement, organizational chart, any existing process documentation, prior CRM artifacts if relevant, and intake forms or correspondence. Read these before Session 1. Note specifically:

- **The mission statement as the org states it.** This is the starting point for the operational mission discussion. If it is vague or aspirational, plan to translate it during Session 1; if it is operational already, plan to confirm and use it.
- **Org type and size signals.** These feed pattern library lookup and CRM candidate selection.
- **Operational role definitions.** Read content that defines who owns what work — which person handles which function, who reports to whom, what the staffing structure is. This is *operational fact* and is in scope for pre-engagement reading even when it appears in methodology-organized form (e.g., a persona section of an existing PRD). The relevant line is "facts about who owns what work" (in scope) versus "methodology decisions about how to organize information about that work" (out of scope). Operational role facts surface assumptions that pattern-matching against generic operations would otherwise get wrong; see §9 (Failure Modes) and the pattern library entry for the org type.
- **Any pre-existing CRM commitments.** If the client has already chosen a CRM, the engagement may be single-deploy rather than multi-deploy. See §10.5 for handling.

### 2.2 Consult the pattern library

For the org type identified, look up the pattern library entry per `pattern-library-specification.md` §4.1. Pattern library entries (when they exist) contain typical mission-critical processes for orgs of this type, common cross-domain handoffs, defaults that have proven workable, and CRM candidates that have served similar engagements well. Per the spec, each entry has three content sections: **A — Tested generalizations** (use as defaults with light verification), **B — Single-instance observations** (use as starting hypotheses to test, not as defaults), and **C — Disconfirmed observations** (read as warnings about plausible patterns that have failed at observed instances).

**If a pattern library entry exists for this org type:**

1. Read the entry end-to-end. Treat Section A content as defaults the consultant can apply confidently subject to client verification; treat Section B content as hypotheses to surface during Session 1; treat Section C content as warnings about patterns that may seem plausible but have failed.
2. Use the entry's content categories (1 — mission and operational center through 10 — common pitfalls) to inform what to listen for in Session 1.
3. Note where the client's pre-engagement materials appear to differ from the entry. These are items to verify in Session 1, not defaults to apply.

**If no pattern library entry exists for this org type:**

Operate in "no library entry" mode. Rely on consultant judgment, drawing on prior engagement experience with similar organizations. Mark the proposed backbone as low-confidence in Session 2 (per §8.1); the client should know extra verification is warranted. The lack of a matching entry is itself information — it suggests the engagement may produce content that becomes the seed of a new entry.

**Guarding against pattern-matching against generic operations:**

The single most important discipline at this step is recognizing that *plausible-sounding patterns from generic operations are not a substitute for verified content.* Library Section A is verified. Library Section B is hypothesis. Generic plausibility (no library reference) is neither — it is a confirmation-bias trap. When the consultant catches themselves reasoning *"this is what nonprofit organizations typically do,"* without library content backing it, the right response is to flag the inference as a question for Session 1 rather than to carry it forward as an assumption. The CBM redo experiment surfaced two specific fabrications that propagated through the simulation because this discipline was not explicit; see `cbm-redo/cbm-redo-step-8-validation-pass.md` §6.3.

### 2.3 Prepare a draft Domain Inventory

Based on the pre-engagement materials and any pattern library entry, sketch the domains the org likely operates in. This sketch is for the consultant only; it is not shown to the client until Session 2 (and even then as a refined version, not the pre-engagement sketch).

### 2.4 Prepare the Session 1 agenda

Session 1 is structured (§3 below). Print or have available the section headings and required outputs. Also prepare a small set of follow-up questions specific to this client based on the pre-engagement materials — typically 3–6 questions about things in the materials that need clarification.

---

## 3. Session 1 — Mission and Domains

### 3.1 Session 1 goals

Session 1 produces, by the end of the session:

- **Drafted Mission Statement** — operational language, ready for client confirmation.
- **Preliminary Domain Inventory** — one-paragraph descriptions of domains, ready for refinement between sessions.
- **Notes for the Prioritized Backbone draft** — captured during the conversation, used between sessions.
- **Notes for the CRM Candidate Set draft** — captured during the conversation, used between sessions.

The session does not produce the finalized Prioritized Backbone or Initial CRM Candidate Set — those are drafted between sessions and presented in Session 2.

### 3.2 Session 1 structure

Session 1 has four parts:

**Part A — Operational mission (20–30 minutes).** What does the org actually do, in concrete terms?

**Part B — Domain identification (20–30 minutes).** What are the major areas of work the mission requires?

**Part C — Process surfacing (30–45 minutes).** Within each domain, what are the specific things people do?

**Part D — Pre-existing CRM context and constraints (10–15 minutes).** What has the client already considered? What are the hard constraints?

A typical session runs 90–120 minutes. Going significantly over is a signal that one of the parts is fighting back; see §9 (Failure Modes).

### 3.2.1 Cross-cutting discipline — inferences require positive support

Across all four parts of Session 1, the consultant maintains a discipline about how to handle inferences from what the client says.

When the consultant draws a conclusion that goes beyond what the client directly stated, the conclusion qualifies as a **legitimate Tier 2 inference** only if it has *positive support in something the client said or in pre-engagement materials* — not if it is plausibility-by-pattern-match against generic operations for similar organizations.

The distinction matters because plausibility-by-pattern-match is a confirmation-bias trap. *"Most nonprofits do X, so this nonprofit probably does X"* is generic pattern-matching, not verified content. It produces conclusions that often turn out to be wrong about the specific client and that propagate through subsequent methodology outputs unnoticed.

**The rule:** if the consultant catches themselves about to write down or proceed on something the client did not explicitly say, ask: *"What did the client actually say that supports this?"* If the answer is *"Nothing directly, but it follows from how similar orgs typically operate,"* the conclusion is **not** a legitimate Tier 2 inference. Capture it as a question to ask explicitly in Session 1 (or in Session 2 if the moment has passed), or as a Tier 3 gap in the gap log if the client cannot answer.

**Where this matters most:** Part C (process surfacing) is densest with inference opportunities because the consultant is mapping client-named activities onto methodology categories. Part B (domain identification) is also high-risk because category structures are tempting to apply against generic patterns. Parts A and D are lower-risk because they elicit directly from the client.

**Source:** the CBM redo experiment surfaced that the v0.1 of this guide was implicitly tolerant of pattern-match-as-Tier-2. See `cbm-redo/cbm-redo-step-8-validation-pass.md` §2 and §3 for two specific cases (fit/no-fit clients; operational-strategic donor split) where pattern-matched plausibility was treated as Tier 2 and turned out to be wrong about the specific client.

### 3.3 Part A — Operational mission

The goal of Part A is to produce a Mission Statement in **operational language** — language that survives the priority test ("if X stopped tomorrow, would the mission be in trouble?").

Many client-stated missions are aspirational rather than operational. *"We empower entrepreneurs in Northeast Ohio"* is aspirational. *"We match aspiring entrepreneurs with experienced mentors and support that pairing for 18 months"* is operational. The consultant's job is to translate, then confirm.

**Worked example — translating aspiration to operations:**

> Consultant: "The materials describe your mission as empowering small business owners in Northeast Ohio. To make sure I understand it operationally — when you think about what your organization concretely does on a Tuesday morning, what's happening?"
>
> Client: "We're connecting business owners with mentors who can help them work through whatever they're facing — financial planning, marketing, hiring, that kind of thing."
>
> Consultant: "So the central operational activity is matching business owners to mentors and supporting that matching over time. Is that right? Is there anything else that's equally central — that if you stopped doing it, you'd no longer be doing your mission?"
>
> Client: "Well, we also hold workshops and we do some advocacy work, but the matching and the mentoring is the core."
>
> Consultant: "Got it. So I'd write the operational mission as something like: *'We match business owners to experienced mentors and support that pairing through structured engagements over an extended period.'* Does that capture it?"

The consultant should aim to leave Part A with a one- or two-sentence operational mission that the client has confirmed. Capture it verbatim; this is the first draft of the Mission Statement output.

**Push-back moment — testing operational mission with the priority test:**

If the client offers an operational mission, test it once before moving on:

> "Just to make sure I have this right — if you stopped matching business owners to mentors tomorrow, you wouldn't be doing your mission anymore. Yes?"

A confident yes confirms the mission. A hedge ("well, we'd still be doing the workshops...") means the mission has more than one operational center and Part A isn't done. Continue until the central activities are explicit.

### 3.4 Part B — Domain identification

The goal of Part B is to identify the domains the mission requires. A domain is one of the big questions the mission forces the org to answer — not a department, not a screen, not a piece of software.

Common domains for nonprofit and similar service-delivery orgs include:

- The domain of delivering the core service (Mentoring, for an org whose mission is matching mentors and mentees)
- The domain of recruiting and managing the people who deliver the service (Mentor Recruitment, in the same example)
- The domain of bringing in and managing the people who receive the service (Mentee Intake, sometimes folded into the core service domain)
- The domain of relationships with external supporters (donors, partners, community organizations)
- The domain of internal operations (finance, HR, governance) — usually out of CRM scope but sometimes adjacent

These are typical, not prescribed. The consultant identifies domains that are real for this client, using the client's language where possible.

**Worked example — domain identification:**

> Consultant: "Now thinking about that operational mission — matching and supporting mentor-mentee pairs — what are the major areas of work that requires? Let me put it differently: what are the big jobs your organization does to make that matching happen?"
>
> Client: "Well, we have to find and screen mentors. That's a big effort — we have a recruiting committee, an application process, background checks, training. Then we have to find the business owners who want mentors. That's mostly outreach and word of mouth. Then there's the actual mentoring — the matching, the meetings, tracking how it's going. And we have to keep our funders happy, which is its own world."
>
> Consultant: "That sounds like four areas: recruiting and onboarding mentors, finding and signing up the business owners — let's call them mentees for now — actually doing the mentoring, and managing relationships with funders. Is that right? Anything I'm missing?"

Aim to identify 3–6 domains. Fewer than 3 usually means the client hasn't differentiated yet and Part B isn't done. More than 6 usually means the client is naming activities, not domains; combine related activities.

**Push-back moment — testing whether something is a domain or an activity:**

Some things the client names sound like domains but are actually activities within a larger domain. Test by asking:

> "Is [thing the client named] something you do as part of [larger area], or is it a separate area of work entirely?"

If the client says it's part of a larger area, it's an activity. If they say it's separate, treat it as a domain candidate. The consultant's judgment can override either answer if it's clearly wrong (e.g., the client calls "sending newsletters" a separate domain — that's almost certainly an activity within communications or fundraising, not a domain).

### 3.5 Part C — Process surfacing

The goal of Part C is to surface the specific processes inside each domain — enough to identify which ones are mission-critical, but not enough to define them in detail.

For each domain identified in Part B, ask:

> "Within [domain name], what are the specific things people in your organization do? Walk me through the major activities."

The consultant captures process names and very brief descriptions. Process *details* are out of scope for Phase 1 — they happen in Phase 3 for processes that make iteration scope.

**Worked example — process surfacing within a domain:**

> Consultant: "Let's go through the mentor recruiting and onboarding domain. What are the specific things people do in that area?"
>
> Client: "We have a recruiting committee that goes out and finds candidates — at networking events, through referrals, that kind of thing. Then anyone interested fills out an application. Then we screen the application, do an interview, run a background check. If they pass all of that, they go through training. Then they're an active mentor and they get assigned to mentees as we have matches available. We also have a process for when mentors leave — sometimes they retire, sometimes they move, sometimes they just stop being available."
>
> Consultant: "Got it. So within that domain you have: recruit candidates, application, screening including interview and background check, training, ongoing management of active mentors, and handling departures. Did I miss anything?"

Capture process names. Do not yet propose mission-critical classification — that's between-session work.

**Important discipline: do not deep-dive into any single process.** The temptation is strong, especially when the client wants to talk about a process in detail. Acknowledge interest, capture the highlight, and move on:

> "That sounds like an important process — I'd like to learn more about it in detail when we get to that iteration. For now I want to make sure I have all the major processes named so we can prioritize together."

This discipline is what keeps Phase 1 from becoming the current Process Definition phase under a different name.

### 3.6 Part D — Pre-existing CRM context and constraints

The goal of Part D is to surface what the client has already considered about CRM tooling, and what hard constraints exist. This feeds the Initial CRM Candidate Set draft.

Questions to cover:

- **Has the client already evaluated or chosen a CRM?** If yes, which one and how committed are they? (See §10.5 for single-deploy handling.)
- **What's the budget envelope?** Order-of-magnitude only — *"under $5K total," "$5K–$25K," "$25K+,"* or *"we don't know yet."*
- **Hosting preferences?** Cloud-only? Self-hosted? No preference?
- **Internal IT capacity?** Does the org have someone who can administer a system, or do they need fully-managed hosting?
- **Hard integrations?** Anything that absolutely must integrate (an existing email platform, a finance system, a website)?
- **Anti-requirements.** Anything they explicitly do *not* want? (Sometimes the most useful question — *"what have you tried that didn't work?"*)

Keep this part short. Detailed CRM evaluation happens through actual deployment in Phase 3, not through interviews.

### 3.7 End-of-session synthesis

In the last 5–10 minutes of Session 1, summarize back to the client:

- The drafted operational Mission Statement, verbatim
- The list of domains identified
- The list of processes within each domain
- A brief note on CRM context and constraints

Ask: *"Does anything in here look wrong, or did we miss something major?"*

Do not ask the client to confirm priorities. That happens in Session 2, after CRM Builder has done its draft work. Asking now would invite either thrash or rubber-stamping (per Principle 4).

End the session with: *"I'm going to take all of this and prepare a proposed prioritized backbone — what we'd build first, what we'd defer, and how we'd sequence things. We'll meet again in [timeframe] to walk through that proposal together."*

---

## 4. Between-Sessions Work

The consultant's job between Session 1 and Session 2 is to produce two drafts:

1. **Proposed Prioritized Backbone**
2. **Proposed Initial CRM Candidate Set**

Both are presented in Session 2 for client verification.

### 4.1 Drafting the Proposed Prioritized Backbone

For each process surfaced in Session 1 Part C, classify it:

- **Mission-critical** — without this process, the org isn't really doing its mission. *Apply the priority test:* if this process stopped tomorrow, would the mission stop?
- **Supporting** — real work the org does, but not on the critical path right now.
- **Deferred** — acknowledged but parked indefinitely.

Then identify which mission-critical processes have **handoff dependencies** between them. Process A hands off to Process B if A produces records or state that B requires to do its work. The mission-critical processes plus the handoffs between them constitute the backbone.

**Crucial step: workability check.** Look at the mission-critical set and ask: *"Could a real user, sitting at a deployed instance with only these processes, do their actual job for one realistic case from start to finish?"* If no — if the work can't be done end-to-end without something the consultant has classified as supporting or deferred — add the missing piece to the backbone, even if it lives in a domain the client didn't think of as critical.

This is where the methodology earns its keep. Cross-domain dependencies that the client wouldn't have flagged from their day-to-day perspective get surfaced because the consultant is asking the workability question. (For CBM specifically: Mentor enrollment lives in the Mentor Recruitment domain, but a Mentoring backbone without it has no mentor records, so Mentor enrollment is part of the Mentoring backbone whether the client thought about it that way or not.)

**Document the proposed backbone in this format:**

For each process in the backbone:
- Process name (in the client's language where possible)
- Domain it belongs to
- One-sentence purpose
- The reasoning for its mission-critical classification (the priority test answer)
- The handoffs it has to/from other backbone processes

For each process classified as supporting or deferred:
- Process name and domain
- Brief reason it isn't in the backbone
- Whether it's likely to graduate to a future iteration (supporting) or remain parked (deferred)

The proposed backbone document is what the consultant brings to Session 2.

### 4.2 Drafting the Proposed Initial CRM Candidate Set

Based on the constraints surfaced in Session 1 Part D and the pattern library entry (if one exists), propose two or three CRMs to deploy to in iteration 1.

The candidate set should usually represent **meaningfully different options**, not three variants of the same approach. For example, an open-source self-hostable option plus a commercial cloud-hosted option plus an org-type-specific tool gives the client a real comparison; three commercial cloud-hosted options of similar size and price point gives them a much narrower comparison.

For each candidate:
- Product name
- Hosting model and approximate cost
- Why it's in the candidate set (which constraints from Part D it satisfies)
- One-sentence note on what it's likely to be good or weak at relative to the proposed backbone

If the client is already CRM-committed (single-deploy, per §10.5), the candidate set has one entry and the document notes that single-deploy is in effect.

### 4.3 What the consultant does *not* do between sessions

- **Do not start writing detailed process specifications.** Phase 1's job is to identify processes, not define them. Detailed specs come in Phase 3.
- **Do not start drafting Entity PRDs.** Same reason.
- **Do not commit to YAML structures.** Same reason.
- **Do not pre-deploy.** Phase 1 ends with the proposed backbone and candidate set verified; deployment begins in Phase 3.

The discipline of "no work outside the phase's scope" is what keeps the methodology from drifting back toward upfront comprehensive specification.

---

## 5. Session 2 — Backbone Verification and CRM Candidate Confirmation

### 5.1 Session 2 goals

Session 2 produces, by the end of the session:

- **Confirmed Prioritized Backbone** (with whatever client-driven corrections were made)
- **Confirmed Initial CRM Candidate Set**
- **Finalized Mission Statement and Domain Inventory** (refined based on Session 1 and any new clarification)
- **Decision: continue to Phase 2 now, or schedule Session 3 to resolve open issues**

### 5.2 Session 2 structure

Session 2 has three parts:

**Part A — Recap and refinement (15–20 minutes).** Confirm the Mission Statement and Domain Inventory in their refined form.

**Part B — Backbone walkthrough (45–60 minutes).** Present the proposed Prioritized Backbone, get client verification or correction.

**Part C — CRM candidate review (20–30 minutes).** Present the proposed Initial CRM Candidate Set, get client confirmation.

A typical Session 2 runs 90–120 minutes. Going significantly over is usually a signal that the proposed backbone has structural problems that need a Session 3 to resolve, not more of Session 2.

### 5.3 Part A — Recap and refinement

Walk the client through the refined Mission Statement and Domain Inventory. These should be close to what was discussed in Session 1; any significant changes should be flagged and explained.

> Consultant: "I've cleaned up the Mission Statement we drafted last time. It now reads: *'[refined statement].'* The change from last week was [specific change and reason]. Does this still match what your organization actually does?"

Get explicit confirmation. Move on.

### 5.4 Part B — Backbone walkthrough

This is the heart of Session 2. The consultant presents the proposed Prioritized Backbone confidently, with grounded reasoning, and invites correction.

**Discipline reminder — what the consultant can and cannot claim.** When presenting the proposed backbone, the consultant separates content backed by Session 1 client statements (which can be presented confidently as "based on what you said") from content based on inference or pattern library Section A defaults (which can be presented confidently but with a different framing) from content that comes from Section B observations or generic plausibility (which must be presented as hypotheses the client should verify rather than as confident proposals). The same Tier 2 discipline from §3.2.1 applies: inferences require positive support, not pattern-match plausibility. If the consultant catches themselves presenting something as backbone-warranted that has no client-statement or library-Section-A support, the right response is to mark that part of the proposal as low-confidence in the framing rather than to present it as if it were backed.

**Worked example — the confident proposal opening:**

> Consultant: "I want to walk you through what we think is the mission-critical backbone for your organization. This is our proposal for what we'd build first — the smallest set of connected processes that lets a real person at your org do the work end-to-end. Everything outside this set we'd defer to later iterations.
>
> Here's what we've classified as mission-critical: [list of processes with their domains]. Connected to each other in this sequence: [briefly describe the handoffs].
>
> The reasoning is [for each process: the priority test answer that landed it in the backbone, plus any cross-domain dependencies]. If we removed any of these, the mission breaks in this specific way: [name the failure mode for each].
>
> Outside the backbone, we'd defer: [brief list of supporting and deferred processes, grouped]. These are real work, but they're not on the critical path right now.
>
> What we're looking for from you in this conversation is: did we get the backbone right? Are there processes we classified as deferred that you think have to be in iteration 1? Are there processes in the backbone that you think we could safely defer? Where did we get the handoffs wrong?"

Let the client respond. Most clients will push back somewhere — that's the point. Listen carefully and distinguish between two kinds of pushback:

**Push-back you should engage with:** The client identifies a process the consultant misclassified, or a handoff the consultant got wrong, or a cross-domain dependency the consultant missed. Engage substantively; the proposal was provisional and the client's feedback is valuable.

**Push-back you should redirect:** The client wants to add many things to the backbone because *"everything matters."* The methodology's value depends on disciplined prioritization. Redirect with the priority test:

> Consultant: "I hear you that [process X] feels important. Let me ask the priority question directly: if [process X] stopped tomorrow, would your mission stop?"

If the client says yes, the consultant probably misclassified it; engage with the substance. If the client hedges or says no, gently hold the classification:

> Consultant: "It sounds like it's important work but not on the immediate critical path. I'd suggest we keep it in supporting for now — that means it's not deferred forever, it's queued for the next iteration. We can pull it forward if iteration 1 reveals it's needed sooner. Does that work?"

**Worked example — the deferred-vs-elicited transition:**

When defending why something is being deferred, the consultant's tone matters. *"Low priority"* and *"deferred"* land differently with clients. Use deferred-not-dismissed language:

> Consultant: "I want to be clear about what 'deferred' means here. We're not saying [process X] doesn't matter or that we won't get to it. We're saying it isn't on the critical path for the first deployment. The reason that matters: if we try to build everything at once, we won't get a working system early enough for your team to react to it, and we end up spending a lot of time on things that turn out to be wrong. Deferring [process X] is how we make sure your iteration 1 deploys quickly enough to be useful."

End Part B with explicit confirmation:

> Consultant: "Okay — with the changes we just discussed, the backbone is now [updated list]. Are we agreed on that as the starting point for iteration 1?"

If yes, move to Part C. If the client wants more think-time, schedule Session 3 (see §6).

### 5.5 Part C — CRM candidate review

Present the proposed Initial CRM Candidate Set. The conversation here is shorter and more straightforward than the backbone discussion, because the candidate set is constrained more by external factors (budget, hosting, integrations) than by judgment.

> Consultant: "Based on the constraints you mentioned last time — [list constraints] — we're proposing we deploy iteration 1 to these candidates: [list]. Each one represents a meaningfully different approach: [explain the differentiation].
>
> The reason for multi-deploy is that your team will be able to use the iteration 1 functionality on each of these systems, with your real processes and your real terminology. That comparison will be much more useful for selecting a CRM than reading feature lists or watching vendor demos.
>
> We can drop any of these or add others if there are products you specifically want to evaluate. We can also do single-deploy if you've already chosen a CRM and don't want a comparison — that's fine. What are your reactions?"

Common client reactions:

- **"That set looks good."** Confirm and move on.
- **"I don't think we need [candidate X]."** Drop it. The candidate set is the client's to shape; the consultant is proposing.
- **"I'd like to add [candidate Y]."** Add it if reasonable. If the proposed addition is clearly a poor fit (e.g., a product the client mentions because they saw an ad, not because it actually serves their constraints), test the fit — *"What is it about [Y] that you'd like to evaluate? Does that match the constraints you mentioned?"* — and proceed accordingly.
- **"We've already chosen — please just deploy to [single CRM]."** Single-deploy mode (§10.5).

### 5.6 End-of-session synthesis

In the last 5–10 minutes of Session 2:

- Confirm all four Phase 1 outputs (Mission Statement, Domain Inventory, Prioritized Backbone, Initial CRM Candidate Set) are in their final form.
- Confirm whether Session 3 is needed. If not, move directly to Phase 2 (Slice Planning) scheduling.
- Tell the client what's coming next: *"In Phase 2 we'll plan iteration 1 — exactly what's in scope, exactly what we'll default. Then in Phase 3 we'll build it and deploy it. You should expect to see something running in [estimated timeframe]."*

---

## 6. Optional Session 3

Session 3 happens only when Session 2 surfaced unresolved ambiguity that the client needs think-time to resolve. Common reasons:

- The client wants to consult internally about a backbone classification before confirming.
- A cross-domain dependency was surfaced that the client hadn't thought about and wants to validate with their team.
- The CRM candidate set involves a product they want to research further before agreeing to deploy.

Session 3 is **not** a default; it's an exception. If most engagements need Session 3, that's a signal that Session 2 isn't doing enough work and the methodology needs revision.

When Session 3 happens, it is short (30–60 minutes) and targeted — it resolves the specific open items from Session 2 and confirms the four outputs. It does not reopen Session 1 or Session 2 material that was already settled.

---

## 7. Phase 1 Output Specifications

This section specifies what the four Phase 1 outputs look like when finalized.

### 7.1 Mission Statement

A one-page document containing:

- **Title:** "Mission Statement — [Client Name]"
- **Operational mission:** one or two sentences in operational language, drawn directly from Session 1 Part A.
- **Aspirational mission (if different):** one paragraph capturing the org's stated aspirational mission, for context.
- **Priority test reference:** an explicit statement of the form *"This mission is the basis for the priority test: a process is mission-critical if its absence would cause [specific operational consequence drawn from the operational mission]."*
- **Standard methodology footer:** revision control, change log, last-updated timestamp.

### 7.2 Domain Inventory

A short document containing:

- **Title:** "Domain Inventory — [Client Name]"
- **One paragraph per domain.** For each domain: name (in the client's language and a structural code), one-sentence purpose, brief description of the kinds of work it covers.
- **Standard methodology footer.**

The Domain Inventory is shorter than the current Domain Discovery Report. It does not include candidate entities or candidate personas; those are drafted in Phase 3 for in-scope domains.

### 7.3 Prioritized Backbone

A document containing:

- **Title:** "Prioritized Backbone — [Client Name]"
- **Overview paragraph** describing the backbone's scope and the workability case it satisfies.
- **Backbone processes section.** For each process in the backbone:
  - Process name and domain
  - One-sentence purpose
  - Mission-critical reasoning (the priority test answer)
  - Handoffs to/from other backbone processes
- **Supporting processes section.** For each: name, domain, one-line reason, expected iteration to graduate.
- **Deferred processes section.** For each: name, domain, one-line reason.
- **Workability statement.** One paragraph explaining why the backbone is sufficient for end-to-end work and what the workability test concretely looks like (e.g., for CBM: *"a mentor and a mentee can be enrolled, matched, and have their pairing produce a session record"*).
- **Standard methodology footer.**

### 7.4 Initial CRM Candidate Set

A short document containing:

- **Title:** "Initial CRM Candidate Set — [Client Name]"
- **Constraints summary.** The constraints from Session 1 Part D that drove the candidate selection.
- **Candidate list.** For each candidate: product name, hosting model, approximate cost, why it's in the set.
- **Multi-deploy or single-deploy declaration.** Explicit statement of which mode is in effect.
- **Standard methodology footer.**

---

## 8. Pattern Library Handling

The pattern library is specified in `pattern-library-specification.md`. This section is the operational view of how Phase 1 uses the library in practice. For library structure (what entries contain, how they're versioned, how content flows between Section A / B / C) refer to the spec; for the operational steps a consultant takes, this section is authoritative.

### 8.1 Three operating modes

The Phase 1 guide distinguishes three modes based on what library content exists for the engagement's org type:

**Mode A — Section A defaults available.** A library entry exists for the org type and contains tested generalizations (Section A content) covering one or more of the ten standard categories. The consultant uses Section A content as defaults during pre-engagement reading and between-sessions work. Verification happens during Session 1 lightly and Session 2 substantively, but the proposed backbone, candidate set, and supporting/deferred classifications can be grounded in Section A defaults with confident framing.

**Mode B — Only Section B observations available.** A library entry exists but Section A is empty or doesn't cover the relevant categories. Section B content is reference material — single-source observations that can shape what to ask about and listen for, but cannot be applied as defaults. The consultant operates with a stronger client-verification stance: Session 2 proposals are framed as informed-by-similar-but-untested-patterns rather than as backed-by-tested-defaults.

**Mode C — No library entry for the org type.** The consultant operates with judgment alone, drawing on prior consultant experience with similar organizations. Session 2 proposals are explicitly marked as low-confidence; the client is invited to scrutinize them more carefully than usual.

The mode is not all-or-nothing — a library entry may have Section A content for some categories (e.g., domain structure for the org type) and only Section B content for others (e.g., common backbone shapes). The consultant uses the appropriate mode per category, not for the engagement as a whole.

### 8.2 Mode A operational steps (Section A defaults available)

When Section A content covers a category relevant to the engagement, the consultant:

1. **In pre-engagement reading (§2.2):** uses Section A content as the basis for a draft backbone, draft candidate set, draft default classifications. These drafts are starting points for Session 1 verification, not pre-commitments.

2. **In Session 1:** lightly verifies that the org behaves the way Section A describes. Asks pointed questions where the client's pre-engagement materials suggest divergence from Section A defaults.

3. **In between-sessions work (§4):** carries Section A defaults forward into the proposed backbone where Session 1 confirmed the org matches the typical pattern; substitutes client-specific content where Session 1 surfaced divergence.

4. **In Session 2 (§5):** presents the proposed backbone confidently with the library reference visible:

> Consultant: "We've worked with similar organizations, and what we've seen consistently is [Section A content]. Based on what you described last time, [client] looks like it follows that pattern with one variation: [specific variation]. The proposed backbone reflects the typical pattern adjusted for that variation. Does it match how you see your organization?"

5. **After the engagement:** captures contributions to Section A — observations that confirm or contradict the typical pattern, used to update Section A's confidence levels.

### 8.3 Mode B operational steps (Section B observations available)

When the relevant content lives only in Section B:

1. **In pre-engagement reading (§2.2):** treats Section B content as hypotheses to surface in Session 1 rather than as defaults. Notes specifically which Section B observations to verify or contradict during the conversation.

2. **In Session 1:** asks explicitly about topics covered by Section B content — *"some similar organizations we've worked with have been structured this way; does that match your situation?"*

3. **In between-sessions work:** carries Section B content forward only where Session 1 explicitly confirmed it; otherwise treats the area as if no library content existed.

4. **In Session 2:** presents the proposed backbone with library content visible but explicitly marked as untested:

> Consultant: "Based on what you described last time, plus observations from similar but distinct organizations we've worked with, the proposed backbone is [proposal]. The reasoning that came from your description is [client-statement-backed parts]; the reasoning that came from observations of similar organizations and that we'd want you to scrutinize is [library-Section-B-backed parts]. Where do those break down for [client]?"

5. **After the engagement:** captures contributions that may promote Section B content to Section A (if confirmed) or move it to Section C (if disconfirmed).

### 8.4 Mode C operational steps (no library entry)

When no library entry exists for the org type:

1. **In pre-engagement reading:** rely on consultant judgment about similar org types. Be more cautious about applying any default that doesn't have direct support in the client's pre-engagement materials.

2. **In Session 1:** ask more open-ended questions; resist the temptation to lead with assumed structures. The consultant's job in Mode C is to elicit, not to confirm.

3. **In between-sessions work:** propose a backbone grounded in client-specific findings from Session 1 rather than in any pre-existing pattern.

4. **In Session 2:** explicitly acknowledge low confidence:

> Consultant: "Because [client] is the first engagement of this type for us, this proposed backbone is based more on judgment than on accumulated patterns. We'd ask you to scrutinize it more carefully than usual — places where your instinct conflicts with our proposal are likely places where we got it wrong."

5. **After the engagement:** the engagement becomes the seed of a new library entry. Substantial documentation is required because the entry's first content all lives in Section B and needs to be detailed enough to inform future engagements.

### 8.5 Section C usage (any mode)

Section C content (disconfirmed observations) is read as a warning regardless of operating mode. When the consultant catches themselves about to make an assumption that matches a Section C entry, they should pause and verify with the client rather than assume. Section C content is the methodology's accumulated record of *patterns that look right but typically aren't.*

The CBM redo experiment surfaced two specific Section C-style fabrications (fit/no-fit client screening; operational-strategic donor split). See `pattern-library/pattern-library-entry-nonprofit-mentoring.md` §C for the documented entries; see `cbm-redo/cbm-redo-step-8-validation-pass.md` §2 and §3 for how those fabrications surfaced and were corrected.

### 8.6 Contribution capture

After every engagement using this guide, regardless of operating mode, the consultant captures observations that should feed the library, per `pattern-library-specification.md` §5. These contributions go into the engagement's pre-validation findings document (the equivalent of `cbm-redo-step-7-pre-validation-findings.md` in the redo) and become input to the methodology owner's periodic library update.

---

## 9. Failure Modes

This section documents the most common ways Phase 1 can go wrong and how to handle each.

### 9.1 The client cannot articulate an operational mission

In Part A, the client speaks only in aspirational terms and resists translation. Common with founders or board members who view the organization in mission terms but don't think about it operationally.

**Handling:** ask process-of-elimination questions. *"If I came to your office on a Tuesday morning, what would I see your staff doing? What activities take up the most time? What activities does your organization spend money on?"* These usually unstick the conversation by anchoring in concrete observation.

If the client still cannot articulate operations, that's a signal the engagement may not be ready for CRM work. Note this honestly to the client; sometimes the right next step is consulting work to establish operational clarity, not CRM tooling.

### 9.2 Domains overlap or aren't separable

In Part B, the client describes work that doesn't cleanly divide into domains. Common in small organizations where a few people do many different kinds of work.

**Handling:** identify domains by the *kind of question they answer*, not by the people who do the work. Even if the same person handles mentor recruiting and donor relationships, those are different domains because the questions ("how do we get and keep good mentors?" vs. "how do we get and keep funding?") are different. Ask the client to validate the domain split by talking through who *would* do the work if the org grew.

### 9.3 The client wants every process classified as mission-critical

In Session 2 Part B, the client pushes back on every "supporting" or "deferred" classification and asserts everything is critical.

**Handling:** apply the priority test relentlessly but kindly. For each contested process, ask the question directly: *"If this process stopped tomorrow, would the mission stop?"* If the client keeps saying yes for everything, the next question is: *"Then if all of these are mission-critical, what's the smallest set we could build first to demonstrate the system works for your mission? What would you most need to see running?"* That reframes the question from "what's important" (everything) to "what's first" (which has to have an answer).

### 9.4 The client has already chosen a CRM and doesn't want a comparison

See §10.5. Single-deploy is supported. The methodology adapts.

### 9.5 The client wants to redo Session 1 in Session 2

In Session 2, the client raises substantive new things that should have been in Session 1 — new domains, very different mission framing, etc.

**Handling:** capture the new material seriously, but don't try to redo Session 1 inside Session 2. Acknowledge that significant new context has emerged, and re-plan: *"What you're describing is significant enough that the proposed backbone is probably wrong for it. I'd suggest we treat today as Session 1.5 — capture this new material — and meet again next week with a revised proposal. Better to delay one week than to commit to the wrong starting point."*

### 9.6 Cross-domain dependencies the client doesn't see

The consultant's workability check (§4.1) reveals that the backbone needs a process the client classified as supporting or deferred. The client pushes back: *"That's not really our work; we don't need it."*

**Handling:** explain the dependency concretely. *"The backbone requires Mentor enrollment because Matching needs Mentor records to exist. If we don't include a way to create Mentor records, Matching has nothing to match. We can include a minimal Mentor enrollment — just enough to create the record — without doing the full Mentor Recruitment work that would normally surround it. Does that work?"* The minimal-version framing usually unsticks the conversation; clients resist large additions but accept targeted ones.

### 9.7 Phase 1 is taking more than three sessions

If the engagement legitimately needs more than two-or-three sessions for Phase 1, something is wrong with either the methodology or the engagement. Possible causes:

- The client organization is much larger or more complex than typical engagements (real, not just methodology drift).
- The client has multiple stakeholders with conflicting views and Phase 1 has become a forum for resolving internal disagreements.
- The consultant is over-eliciting and Phase 1 has drifted into Phase 3 territory.

Diagnose the cause. If it's organizational complexity, the methodology may need adjustment. If it's stakeholder conflict, surface the conflict explicitly to the client and ask them to resolve it before Phase 1 can finish. If it's consultant over-elicitation, hold the line: Phase 1's job is to identify, not define.

---

## 10. Special Cases

### 10.1 Existing CRM artifacts from prior consultants

The client may have prior CRM artifacts (specifications, deployments, configurations) from a previous engagement. Treat these as background context, not as authoritative input. Read them as part of pre-engagement preparation, but do not let them shape the proposed backbone — the prior engagement may have been wrong in exactly the ways the new methodology is trying to fix.

### 10.2 Multi-stakeholder organizations

Some clients have multiple stakeholders who all need to weigh in on Phase 1 outputs (executive director, board chair, program director, etc.). Sessions can include multiple stakeholders, but the consultant should ensure one stakeholder is the **decision-maker of record** — the person whose verification finalizes the outputs. Otherwise Phase 1 can become hostage to inter-stakeholder negotiation.

### 10.3 Organizations in transition

If the organization is going through significant change (leadership transition, mission redefinition, merger), Phase 1 may need to surface that explicitly: *"Are we designing for the organization as it is today, or as it will be in [N] months?"* The answer affects everything downstream and deserves explicit treatment in the Mission Statement.

### 10.4 Very small organizations

Organizations with fewer than ~10 staff sometimes have so few processes that Phase 1's classification work is trivial — almost everything is mission-critical because everyone does everything. In these cases, Phase 1 may be very short, and the proposed backbone may be most or all of the org's processes. That's fine; the methodology doesn't require Phase 1 to be heavy.

### 10.5 Single-deploy mode

When the client has already committed to a CRM and doesn't want a comparison, Phase 1 changes minimally:

- Session 1 Part D confirms the commitment is firm rather than a preference.
- Between-sessions work produces an Initial CRM Candidate Set with one entry, and the document notes single-deploy is in effect.
- Session 2 Part C is a confirmation, not a discussion.

Everything else about Phase 1 works the same. The phases that change more substantially under single-deploy are Phase 4 (no comparison artifact) and Phase 5 (no CRM selection decision); see those phase guides when written.

---

## 11. Connection to Phase 2 (Slice Planning)

Phase 2 needs the following from Phase 1:

- The **Prioritized Backbone** — the set of processes Phase 2 chooses iteration 1 from.
- The **Mission Statement** — the basis for any priority re-test in Phase 2.
- The **Domain Inventory** — the structural reference for cross-domain considerations in iteration scope.
- The **Initial CRM Candidate Set** — the deployment targets Phase 2 plans against.

If any of these is incomplete or unconfirmed at the end of Phase 1, Phase 2 cannot start cleanly. Resolve before scheduling Phase 2, even if it means a Session 3.

The handoff from Phase 1 to Phase 2 is conceptual rather than ceremonial — there's no formal review document, but the consultant should ensure (with the client, briefly) that everyone is starting Phase 2 from the same understanding of the four Phase 1 outputs.

---

## 12. What This Guide Does Not Yet Cover

Acknowledged gaps to be addressed by future revisions or by separate artifacts:

- **Templates for the four Phase 1 outputs.** §7 specifies content; actual document templates (with the methodology's standard formatting) are a separate artifact.
- **Detailed scripts for the in-session synthesis at the end of Session 1 and Session 2.** §3.7 and §5.6 describe the synthesis activities; example wording is sparse compared to the worked examples elsewhere.
- **Metrics for evaluating Phase 1 quality.** No measurement scheme exists for whether Phase 1 went well — currently the test is whether Phase 2 can proceed cleanly, which is a coarse signal.
- **Coordination with Phase 0 / pre-engagement sales.** Some of the pre-engagement preparation work (§2.1, §2.4) overlaps with sales/intake activities that aren't part of the methodology proper. The seam between sales and Phase 1 deserves its own treatment eventually.
- **Empirical measurement of session length.** §3.2 and §5.2 cite 90–120 minute targets for each session, but these are estimates rather than measured durations. Real-engagement experience under the new methodology may show that sessions take longer or shorter than the estimates; the guide should be revised against measurements once they exist.
- **Multi-stakeholder Session-1 and Session-2 handling.** §10.2 addresses multi-stakeholder organizations briefly. As the methodology is applied to organizations with more complex stakeholder structures, this section will need expansion.

**Resolved in v0.2 (no longer gaps):**

- ~~The pattern library specification.~~ Specified in `pattern-library-specification.md` (committed 04-30-26). §8 of this guide updated to reference actual library mechanics.

---

*End of document.*
