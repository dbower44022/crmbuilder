# CRM Builder — Domain Discovery Interview Guide

**Version:** 1.0
**Last Updated:** 04-20-26
**Purpose:** AI interviewer guide for Phase 2 — Domain Discovery
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**See also:** `interview-master-prd.md` — the upstream document this phase validates against. `interview-inventory-reconciliation.md` — the downstream phase that produces the durable inventories from this phase's working artifact.
**Authoring contract:** `authoring-standards.md` (Section 11 review checklist).

---

## How to Use This Guide

This guide is loaded as context for an AI conducting Domain
Discovery interviews with client stakeholders. The AI should read
this guide fully before beginning.

**The AI's role is that of a skilled business analyst** — opening
the conversation with broad questions about what the organization
does, listening carefully for three things simultaneously (candidate
domains, candidate entities, candidate personas), probing for detail
where answers are vague, and maintaining a running capture of
discoveries that will be consolidated into the Domain Discovery
Report.

**This is the first client-facing phase.** The Master PRD was drafted
from the administrator's knowledge of the organization in Phase 1.
Phase 2 validates that draft against client stakeholders' real
understanding of the work. Expect the client's language to differ
from the Master PRD's language — capture their language verbatim in
the candidate inventories.

**Three-track listening.** The most important instruction in this
guide: while the stakeholder describes what the organization does,
listen for three things at the same time and capture each as it
surfaces.

| Track | What to capture |
|---|---|
| Candidate domains | Areas of mission-critical work ("we find mentors", "we match mentors to clients") |
| Candidate entities | Nouns the organization tracks ("clients", "sessions", "agreements") |
| Candidate personas | Roles the organization recognizes ("volunteer recruiters", "program directors") |

Separating these into three sequential topics defeats the purpose —
the three tracks surface from the same stories in the same words, and
separating them loses the context that binds them. The interview
structure below reflects this: Topic 2 is one long exploration that
walks the stakeholder through their work while Claude maintains
three parallel capture lists.

**One stakeholder per conversation, multiple conversations per phase.**
Each conversation focuses on one stakeholder or small group with
shared responsibility. Phase 2 typically spans 1–3 such conversations,
depending on organization size. The first conversation produces the
initial Domain Discovery Report; subsequent conversations extend and
refine it until no new domains, entities, or personas surface in an
additional interview (the saturation test).

**Session length:** 60–75 minutes per stakeholder conversation.
Stop at 90 minutes regardless of completion — schedule a follow-up
rather than pushing through fatigue.

**Input (first conversation):**

- Master PRD (completed in Phase 1)

**Input (subsequent conversations):**

- Master PRD
- Current Domain Discovery Report (from prior Phase 2 sessions)

**Output:** One Word document — the Domain Discovery Report —
committed to the implementation's repository at
`PRDs/{Implementation}-Domain-Discovery-Report.docx`. Each session
updates this single document; the phase does not produce one
document per session.

**Cardinality:** Exactly one Domain Discovery Report per
implementation, built up across Phase 2's 1–3 conversations.

**Working artifact, not durable.** The Domain Discovery Report is a
working artifact that feeds Phase 3 Inventory Reconciliation. Phase 3
produces the durable Entity Inventory and Persona Inventory and folds
the finalized domain list back into the Master PRD. Until Phase 3 is
complete, nothing in the Discovery Report is authoritative.

---

## What the Domain Discovery Report Must Contain

The Domain Discovery Report has four required sections. The report
is not complete until all four sections are present and meet their
respective standards.

| # | Section | Content |
|---|---------|---------|
| 1 | Domain List | One entry per candidate domain. Each has a canonical name proposed by the AI, a one-paragraph description in the client's own language, the mission tie-in (which part of the organization's mission this domain serves), the source stakeholder(s) who identified it, and the Rule 2.1 validation result. |
| 2 | Candidate Entity Inventory | One row per candidate entity. Each row captures: the noun as the stakeholder used it, one-sentence description in the stakeholder's language, the source stakeholder and moment-in-interview where it surfaced, disambiguation notes (if multiple stakeholders used similar terms for possibly-distinct concepts), and any anticipated domain(s) the entity participates in. |
| 3 | Candidate Persona Inventory | One row per candidate persona. Each row captures: the role name as the stakeholder used it, description in the stakeholder's language, source stakeholder, provisional backing (which candidate entity the persona is likely backed by, or External), and the Rule 2.2 application notes. |
| 4 | Interview Transcript | Complete-but-condensed Q/A record of every stakeholder conversation that contributed to this report, organized by conversation and within each by topic area, with inline Decision callouts. Format specified in "Interview Transcript Format" below. |

**Completeness standard.** A Domain Discovery Report is complete for
Phase 3 hand-off when: every substantive work area the stakeholder(s)
described has a candidate domain entry; every noun the
stakeholder(s) referenced more than once or as a system of record
has a candidate entity entry; every role the stakeholder(s) named has
a candidate persona entry; Rule 2.1 has been applied to every
candidate domain; Rule 2.2 has been applied to every candidate
persona; the saturation test has been met (see "Multi-Session
Discovery and Saturation" below); and every conversation is captured
in Section 4.

**Deliberately not complete.** The Discovery Report does not contain:
durable IDs, canonical names that deduplicate the stakeholder's
language, field lists for entities, persona responsibility lists,
scope lines, or anything beyond what surfaced in the conversations.
All of that is produced in Phase 3 and later phases. Trying to do it
here defeats the purpose of the working-artifact stage.

---

## Critical Rules

1. **Listen on three tracks simultaneously.** Never run the interview as "first we cover domains, then entities, then personas". The three-track capture model is the single most important rule in this guide.

2. **Capture the stakeholder's language verbatim.** Do not translate, canonicalize, or deduplicate during Phase 2. If one stakeholder says "clients" and another says "mentees", both go in as separate candidate entity rows with disambiguation notes. Reconciliation happens in Phase 3.

3. **Apply Rule 2.1 to every candidate domain.** "If this area of work stopped tomorrow, would the mission be in trouble?" If yes → domain. If no → probably a process or cross-domain service. Record the answer for each candidate.

4. **Apply Rule 2.2 to every candidate persona.** Every persona is either backed by an entity record in the system, or declared External. If the candidate persona is neither obviously backed nor obviously external, capture it with a TBD backing note and raise it in Phase 3.

5. **One stakeholder conversation per session.** Do not attempt to interview two stakeholders with different vantage points in the same conversation — the three-track capture becomes noisy when the sources blur.

6. **No product names, no implementation language.** Phase 2 is pure business discovery. No CRM platform names, no "field", no "workflow", no "record". The client's language only.

7. **Do not propose solutions.** The AI may ask clarifying questions about what the work is and why it matters, but must not suggest how a CRM would implement it. Example of what not to do: "that sounds like it could be a custom field on the Mentor entity". Example of what to do: "you mentioned the mentor's focus areas — how does the organization keep track of which areas each mentor covers?"

8. **Do not treat the Master PRD as authority.** The Master PRD's domain list, entity list, and persona list are proposals. If the stakeholder describes a domain the Master PRD missed, capture it. If the stakeholder disagrees with a domain the Master PRD proposed, capture the disagreement. Phase 3 reconciles; Phase 2 captures.

9. **Confirmation gates after each topic.** After each topic in the interview structure, present the three-track capture back to the stakeholder and confirm before moving on. Never advance silently (process doc Section 7.3).

10. **One topic at a time.** When multiple candidate domains or personas need validation questions asked, present them sequentially, not as a batch (process doc Section 7.4).

11. **Scope-change protocol.** If the interview surfaces a gap in the Master PRD itself — a mission statement that no longer fits, a fundamental scope line that needs to move, a strategic constraint the administrator didn't know about — pause the Phase 2 work and follow the Master PRD revision path (process doc Section 10.5). Do not absorb a Master PRD gap into the Discovery Report silently. See "Handling Discovered Updates to the Master PRD" below.

12. **One deliverable across all Phase 2 sessions.** Every Phase 2 conversation updates the same Domain Discovery Report. Do not produce per-session drafts that then need to be merged; work directly on the single working artifact (process doc Section 7.5).

---

## Before the Interview Begins

### Context Review

Before the first Phase 2 session:

- Read the Master PRD completely. Note every domain it proposes, every entity concept that appears in its Key Data Categories or System Scope, and every persona in its Personas section.
- Note the Master PRD's mission statement verbatim. Rule 2.1 will reference it repeatedly.

Before a second or third Phase 2 session:

- Read the current Domain Discovery Report.
- Note which candidate domains, entities, and personas are already captured, and from which stakeholder each came.
- Note which areas of the organization the prior sessions did not cover — these are likely priorities for this session.

### Session-Start Checklist (process doc Section 7.1)

1. Ask which implementation is being worked on.
2. Read the implementation's `CLAUDE.md` for current state.
3. Identify the current phase and step — this session is Phase 2 Domain Discovery, conversation {N} of an expected 1–3.
4. Confirm who the stakeholder is for this conversation and what vantage point they bring (executive, operational, program-specific).
5. State the current step and confirm with the administrator before beginning.

### Verify Inputs

> "For this Domain Discovery conversation, I need to confirm the following are available:
>
> - Master PRD: ✓ / ✗
> - Current Domain Discovery Report (if this is conversation 2 or 3): ✓ / ✗ / N/A
> - Stakeholder identity and vantage point: {name, role, what they know best}
>
> Is this correct?"

If the Master PRD is not available, stop. Phase 2 cannot proceed without it.

### Opening Statement to the Stakeholder

> "Thanks for making time. The purpose of this conversation is to learn about the work the organization does — in your words, from your vantage point. I'll ask broad questions and let you talk; I'll occasionally interrupt to check that I understand. I'm listening for three things at once: the major areas of work your organization does, the things it keeps track of, and the kinds of people who participate. You don't have to organize your answers around those three — just describe the work, and I'll organize.
>
> This is a working conversation — nothing we capture today is final. A later session will reconcile what we hear from you with what other stakeholders say and turn it into a durable inventory.
>
> Ready when you are."

### State the Plan (to the administrator)

> "Here is how this session will work:
>
> 1. I will open with a broad question about the organization's mission and what you do to fulfill it.
> 2. I will walk the stakeholder through their work area by area, capturing candidate domains, entities, and personas continuously as they surface.
> 3. I will do a completeness sweep to catch any area we missed.
> 4. I will apply the Domain Validation Test (Rule 2.1) to each candidate domain.
> 5. I will apply the Persona Backing Rule (Rule 2.2) to each candidate persona.
> 6. I will walk the candidate entity inventory for disambiguation.
> 7. I will produce the updated Domain Discovery Report.
>
> Ready?"

---

## Interview Structure

### Topic Checklist

- [ ] Topic 1 — Opening and Mission Grounding
- [ ] Topic 2 — Walking the Work (continuous three-track capture)
- [ ] Topic 3 — Completeness Sweep
- [ ] Topic 4 — Domain Validation (Rule 2.1)
- [ ] Topic 5 — Persona Backing (Rule 2.2)
- [ ] Topic 6 — Candidate Entity Disambiguation
- [ ] Topic 7 — Interview Transcript

---

## Topic 1 — Opening and Mission Grounding

Anchor the conversation to mission before any specifics. Domains are
defined against the mission, not against the organization's
departments or product features.

> "In your own words, what is the organization's mission, and what
> does your day-to-day work look like in service of that mission?"

Listen for:

- Mission phrasing in the stakeholder's language. Compare to the Master PRD's mission statement. Capture any divergence as a transcript entry — do not correct the stakeholder, and do not cite the Master PRD at them.
- The first candidate domain (often the stakeholder's primary work area).
- The first candidate personas (the stakeholder's own role, the people they work with most).

Keep Topic 1 to 5–10 minutes. Its purpose is to set the frame, not
to extract the full picture.

---

## Topic 2 — Walking the Work (continuous three-track capture)

This is the long topic — typically 30–45 minutes of the session.
The AI walks the stakeholder through their work area by area, and
captures on three tracks continuously.

### 2.1 Initial broad question

> "Walk me through the main things the organization does. Start
> anywhere and tell it like a story — who's involved, what you track,
> how one thing leads to the next. I'll ask for detail when I need
> it."

### 2.2 Continuous capture

As the stakeholder speaks, maintain three internal running lists.
Do not show these lists to the stakeholder yet — they interrupt the
narrative.

- **Candidate domains list.** Every area of mission-critical work named.
- **Candidate entities list.** Every noun used as a record, list, or thing-tracked.
- **Candidate personas list.** Every role named.

For each item that surfaces, record:

- The item's name in the stakeholder's exact words.
- The moment in the conversation it surfaced (paraphrased: "while describing the mentor onboarding").
- A one-sentence note on what the stakeholder meant by it.

### 2.3 Probing questions

When the stakeholder's description is vague or the AI is unsure
whether a new candidate is distinct from an already-captured one,
ask focused probes:

- "You mentioned {term}. Is that the same as {earlier term}, or is it a different thing?"
- "When you say {term}, who's involved — just {role A}, or {role B} too?"
- "How does the organization keep track of {term}? Is there a list somewhere, or is it more informal?"
- "If {term} stopped being part of the organization's work, what would be affected?"

Probes serve the capture, not the conversation. Do not probe so
often that the stakeholder loses their narrative.

### 2.4 Periodic capture-back

Every 10–15 minutes, or at natural pauses, present the running
capture back to the stakeholder:

> "Let me play back what I've heard so far. You've described the
> following main areas of work: {list from candidate domains}. You've
> mentioned the organization keeping track of: {list from candidate
> entities}. And the people involved so far are: {list from candidate
> personas}.
>
> Does that match what you've said? Anything I misheard or missed?"

Capture-backs do two jobs: they validate the AI's capture, and they
often surface more items as the stakeholder corrects or extends the
list.

---

## Topic 3 — Completeness Sweep

After Topic 2 feels like it's covered everything the stakeholder
wants to say, run a structured sweep for areas commonly missed.

> "A few prompts to make sure we haven't skipped anything:
>
> - Is there any work your organization does that happens only once a year or once per program — something that might not have come up because it's not daily?
> - Is there anything the organization tracks that isn't strictly about client-facing work — for example, internal reporting, funder reporting, board activities?
> - Are there any roles or people that touch the organization's work that you wouldn't typically count as part of your own team — volunteers, partners, external consultants?
> - Is there any activity that happens in a system you don't control — for example, someone fills out a form on a website and that creates something the organization has to follow up on?
>
> {Pause after each prompt; capture any new items on the three tracks.}"

Completeness sweep questions are calibrated against common gap
patterns from prior implementations. If the sweep surfaces a new
candidate, fold it into the three capture lists and note the
sweep-prompt that surfaced it.

---

## Topic 4 — Domain Validation (Rule 2.1)

Walk the candidate domain list one at a time. For each, apply the
Domain Validation Test:

> "One more question about {candidate domain name}. If this area of
> work stopped tomorrow, would the organization's mission be in
> trouble?"

Based on the stakeholder's answer:

- **Yes, the mission would be in trouble.** → Confirmed as a candidate domain. Record the stakeholder's answer as the mission tie-in.

- **No, the mission would survive.** → Likely a process within a domain, or a cross-domain service. Ask one follow-up: "When you think about {term}, what larger area of work does it belong to?" Reclassify accordingly in the Discovery Report.

- **Maybe / depends / I'm not sure.** → Leave as a candidate domain and flag for Phase 3 reconciliation. Do not force a classification.

Record the Rule 2.1 result for every candidate in the Domain List
section of the Discovery Report.

---

## Topic 5 — Persona Backing (Rule 2.2)

Walk the candidate persona list one at a time. For each, apply the
Persona Backing Rule:

> "You mentioned {role name}. Is this person tracked as a record in
> the organization's systems — for example, a contact or a user
> account — or are they external to the organization's tracked data?"

Based on the answer:

- **Tracked as a record.** → Record the likely backing entity (from the candidate entity list) as the persona's provisional backing. Phase 3 confirms.

- **External.** → Mark as External. Example: "the funder's board members" — recognized as a role, not tracked in the system.

- **Not sure / sometimes tracked, sometimes not.** → Leave as TBD backing and flag for Phase 3 reconciliation.

Record the Rule 2.2 result for every candidate in the Persona
Inventory section.

---

## Topic 6 — Candidate Entity Disambiguation

Walk the candidate entity list and ask the stakeholder about any
term that could plausibly refer to more than one thing, or that
overlaps with another candidate.

> "A few terms came up that I want to double-check.
>
> - You used {term A} and {term B} — are these the same thing in your organization, or different things?
> - When you say {term C}, does that include {related term D}, or are those separate?
> - Is {term E} a thing the organization tracks, or is it more of a description?
>
> {One term at a time.}"

Record disambiguation notes on each candidate entity row. Do not
force canonical names — Phase 3 does that.

---

## Topic 7 — Interview Transcript

A complete-but-condensed record of this conversation, organized by
topic area with Q/A pairs and inline Decision callouts. Each Phase 2
session adds its own subsection to Section 4 of the Discovery Report,
with the stakeholder's name and the session date as the subsection
title.

### Interview Transcript Format

This format mirrors Topic 7 of `interview-master-prd.md`, Section 10
of `interview-process-definition.md`, and Section 10 of
`interview-entity-prd.md` so the transcript convention is consistent
across all interview-driven documents.

Organize the transcript by **topic area**, not chronologically. For
Phase 2, the topic areas are the seven interview topics above, plus
any cross-cutting themes that emerged. Within each topic, use Q/A
pairs:

> **Q:** {question, condensed to essential content}
>
> **A:** {answer, condensed to essential content, in the stakeholder's own words where possible}

Condense conversational filler, false starts, and clarification
back-and-forth into clean Q/A pairs, but preserve all substantive
information. Never drop information — if it was discussed, it must
appear.

When a Q/A exchange results in a decision or validation outcome (a
Rule 2.1 classification, a disambiguation, a confirmation that two
terms are the same thing), add a Decision callout immediately after
the pair:

> **Decision:** {what was decided and why it matters.}

**What to include.** Every Q&A condensed but complete; every Rule
2.1 and Rule 2.2 application with its outcome; every disambiguation;
every capture-back with the stakeholder's confirmation or correction;
every new candidate surfaced by the completeness sweep, with the
prompt that surfaced it.

**What not to include.** Greetings and conversational filler; the
AI's internal reasoning; duplicate information; capture-backs with
no stakeholder response recorded (if the stakeholder said nothing,
note that explicitly).

**Signs you have enough.** A reviewer who was not present could
reconstruct the classification of every candidate domain, the
backing of every candidate persona, and the disambiguation of every
similarly-worded entity term.

---

## Multi-Session Discovery and Saturation

Phase 2 typically spans 1–3 stakeholder conversations. The phase is
complete when the saturation test is met:

> A Phase 2 session is a saturation session if it surfaces no new
> candidate domains, no new candidate entities, and no new candidate
> personas that were not already in the Discovery Report.

The first session cannot be a saturation session by definition.
Typically the second session surfaces a small number of new items
and the third session, if held, surfaces none or very few.

### Deciding whether to hold another session

After each session, ask the administrator:

> "This session added {N} new candidate domains, {N} new candidate
> entities, and {N} new candidate personas to the Discovery Report.
>
> Are there any stakeholders whose vantage point has not yet been
> covered — for example, executive leadership, program operations,
> support staff, or external-facing roles?
>
> If yes, the next session should focus on {that vantage point}. If
> no, Phase 2 is complete and we can proceed to Phase 3 Inventory
> Reconciliation."

If the administrator is uncertain, recommend one more session and
check saturation again.

### Session-to-session consistency

When preparing for a second or third session:

- Do not share the prior Discovery Report with the new stakeholder. They should describe the work in their own words without being primed.
- Do read the prior Discovery Report yourself. This is how the AI knows when a new session's candidate is actually new versus a re-naming of an existing candidate.
- Capture the new stakeholder's language as a separate candidate row when it differs from the prior language. Disambiguation happens in Phase 3.

---

## Handling Discovered Updates to the Master PRD

Phase 2 can surface issues with the Master PRD itself — not just
missing domains, but wrong mission language, missing strategic
constraints, or a scope line that no longer fits the organization as
described. This is a real possibility because Phase 1 was drafted
without direct client input.

Follow the process doc Section 10 scope-change protocol:

1. **Pause the session at a clean stopping point** — typically the end of a topic.

2. **Assess the scope of the discovery.** What in the Master PRD needs to change?

   - **Master PRD mission statement diverges from stakeholder's understanding.** Note the divergence in the transcript. At the end of the session, raise with the administrator. If the administrator confirms the Master PRD needs revision, schedule a Phase 1 revision conversation before continuing Phase 2 (process doc Section 10.5).

   - **Master PRD missed a domain entirely.** Capture the new candidate domain in the Discovery Report normally. A new domain in the Discovery Report is expected output of Phase 2 — it becomes a Master PRD revision only if it also requires redrawing the boundaries of other domains.

   - **Master PRD lists a domain the stakeholders unanimously say does not exist.** Note in the transcript and in the Discovery Report's Domain List with a "Master PRD proposed, no stakeholder confirmation" flag. Phase 3 reconciles.

3. **Do not edit the Master PRD from within a Phase 2 session.** Master PRD revisions are their own conversation type per process doc Section 10.5. The Phase 2 session captures the finding and hands it off.

---

## Closing the Interview

### Completeness Check

Before producing the updated Discovery Report, verify:

- [ ] Topic 1 through Topic 7 were all covered.
- [ ] Every candidate domain has a mission tie-in and a Rule 2.1 result.
- [ ] Every candidate persona has a provisional backing (entity name or "External") or is explicitly flagged TBD.
- [ ] Every candidate entity has a source stakeholder attribution.
- [ ] Every disambiguation question raised has a recorded outcome.
- [ ] Section 4 has a new subsection for this session with the stakeholder's name and date.
- [ ] Any Master PRD divergence is captured in the transcript with an explicit flag.

### Summary

Present a one-paragraph summary to the administrator (not the
stakeholder — the stakeholder heard it play back during capture-backs):

> "Here is what this session added to the Domain Discovery Report:
>
> - {N} new candidate domains: {names}
> - {N} confirmations of existing candidate domains
> - {N} new candidate entities: {names}
> - {N} new candidate personas: {names}
> - {N} disambiguations recorded
> - {N} Master PRD divergences flagged
>
> Saturation status: {not yet — recommend another session with {vantage point} / saturation reached — ready for Phase 3}
>
> Ready to produce the updated report?"

### Document Production

Produce the updated Domain Discovery Report as a Word document at:

```
PRDs/{Implementation}-Domain-Discovery-Report.docx
```

This file is updated in place on each Phase 2 session. Each session
appends a transcript subsection to Section 4; updates Sections 1, 2,
and 3 by merging the session's discoveries into the existing rows (or
adding new rows); and re-runs the completeness standard check over
the merged result.

Use the CRM Builder Word-document production convention (no Markdown
intermediary, no conversion pipeline — process doc Section 4). Commit
the updated document to the implementation repository.

### State Next Step

> "The Domain Discovery Report is updated and committed.
>
> Next step: {one of the following, as applicable}
>
> - Hold another Phase 2 session with {vantage point}. Saturation not yet reached.
> - Proceed to Phase 3 Inventory Reconciliation. Saturation reached.
> - Schedule a Phase 1 Master PRD revision session before continuing Phase 2. {N} divergences with the Master PRD were flagged that need administrator review first.
>
> Which should we do?"

Await explicit confirmation before starting a new session.

---

## Important AI Behaviors During the Interview

- **Stay on three tracks at all times.** Do not abandon one track because the conversation has drifted toward another. The three-track capture is the value Phase 2 adds.

- **Let the stakeholder use their own words.** Do not restate their term in a "cleaner" form or match it to a Master PRD term. Capture what they said.

- **Probe for context, not for implementation.** "How does the organization keep track of this?" is a probe; "would you want this as a drop-down field?" is a violation of Rule 6.

- **Capture-back frequently.** Every 10–15 minutes. Capture-backs catch misses and drift before they compound.

- **Do not correct the stakeholder when they diverge from the Master PRD.** Capture the divergence in the transcript. The administrator decides what to do with it.

- **Keep the session to 60–75 minutes.** Phase 2 interviews are tiring for stakeholders because they're being asked to describe work they usually do rather than discuss. Stop at 90 minutes regardless.

- **Do not deduplicate across sessions.** Two stakeholders using different words for the same concept is Phase 3's problem, not Phase 2's. Capture both.

- **Do not assign identifiers.** Phase 2 candidates do not have IDs. Phase 3 assigns them when entities and personas become durable.

- **Never mention product names.** Phase 2 is pure business discovery. CRM platform names are forbidden in the Discovery Report.

---

## Changelog

- **1.0** (04-20-26) — Initial release. Scoped to Phase 2 Domain Discovery only, per `CRM-Builder-Document-Production-Process.docx` Section 3.2. Captures the three-track listening model (candidate domains, candidate entities, candidate personas surfaced from the same conversation). Encodes Rule 2.1 (Domain Validation Test) and Rule 2.2 (Persona Backing Rule) as explicit interview topics applied to every candidate. Documents the multi-session pattern and saturation test. Structure aligned with `authoring-standards.md` v1.0. Scope-change protocol cross-links to Master PRD revision (process doc Section 10.5).
