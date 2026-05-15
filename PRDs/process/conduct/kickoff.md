# CRM Builder — Kickoff Protocol

**Version:** 1.1
**Last Updated:** 05-15-26 19:05
**Purpose:** Pre-session priming routine for any AI conducting a stakeholder-facing session under this methodology. Defines what runs before substantive interview work begins, in what order, and how it adapts to who is across the table.
**Scope:** All `interview-*.md` and `guide-*.md` phase documents in `PRDs/process/interviews/`. Runs in conjunction with `conduct/charter.md` (global conduct) and the relevant phase guide (phase content).
**See also:** `conduct/charter.md` (global conduct rules), `conduct/question-library.md` (worked examples).

---

## 1. Purpose and Scope

Every stakeholder-facing session under this methodology starts with a kickoff. The kickoff exists to make the substantive interview shorter, sharper, and less painful for the person providing information.

A good kickoff:

- Catches the AI up on context (Layer 1) before the stakeholder has to.
- Frames what's happening (Layer 2) so the stakeholder isn't guessing.
- **Calibrates the AI to the stakeholder** (Layer 3) so the session adapts to their time, energy, comfort, and goals — not to the AI's default behavior.

A bad kickoff is overhead. The principle of this document is: do the kickoff seriously when it earns its keep, abbreviate it when it doesn't, and never run it as a checklist for its own sake.

**What this document governs:** what happens before the first substantive question.
**What this document does not govern:** the substantive interview itself (phase guides), conduct during the interview (Charter), or document authoring (`authoring-standards.md`).

---

## 2. The Three Layers — Overview

| Layer | Audience | Visibility | Always runs? |
|---|---|---|---|
| 1. Internal Pre-Session Checklist | The AI itself | Silent | Yes |
| 2. Framing to the Stakeholder | The stakeholder | Spoken | Almost always (abbreviated for some session types) |
| 3. Calibrating the Stakeholder | The stakeholder | Spoken / interactive | Adapts heavily by session type |

Layer 1 is preparation — the AI does it before its first message. Layer 2 is the AI's opening — what's happening today and how it'll work. Layer 3 is the AI *listening* — confirming time, communication preference, and goals from the person actually answering questions, before any substantive question gets asked.

The kickoff ends at an explicit gate (§9) that signals the substantive interview is starting.

---

## 3. Layer 1 — Internal Pre-Session Checklist

Layer 1 is everything the AI does before composing its first stakeholder-facing message. None of this is said aloud. It is verification, not communication.

**Required Layer 1 actions, in order:**

1. **Read both CLAUDE.md files.** Repository CLAUDE.md (CRM Builder methodology) and the implementation CLAUDE.md (e.g., Cleveland Business Mentors). Confirm Charter and the relevant phase guide are loaded as context.
2. **Read upstream documents** required by the phase guide. Master PRD, Domain Overview, prior process documents — whatever the phase guide names as input.
3. **Identify the deliverable.** What document is this session producing? Where will it live in the repo? Is there a generator template?
4. **Identify the session type.** First-time or follow-up? Administrator-as-proxy or real SME? Single stakeholder or multiple? See §6 for what each variant changes.
5. **State the phase and step internally.** Phase number, phase name, position in sequence. The administrator will be told this at session start (§4); the SME usually does not need it.
6. **Identify carry-forward implications.** Is this session likely to surface scope changes? If so, which upstream documents are most at risk?
7. **Prepare the topic checklist.** From the phase guide. Internalized — not read aloud, not pasted into Layer 2.

**Layer 1 is complete when** the AI knows what is being produced, who is being interviewed, what the inputs say, and what is most likely to go wrong. Only then should the AI compose Layer 2.

If any required input is missing (e.g., an upstream document the phase guide names as required), the AI raises this with the administrator before opening Layer 2. The session does not proceed on incomplete inputs.

---

## 4. Layer 2 — Framing to the Stakeholder

Layer 2 is the AI's opening message to the stakeholder. Its job is to set expectations and invite participation.

### 4.1 What Layer 2 contains

A complete Layer 2 covers, in plain language:

- **What we're doing today.** One sentence on the goal. Not the document name, the *purpose*.
- **What comes out of it.** A single tangible deliverable (a document the stakeholder can review).
- **Roughly how long.** A time estimate, with the explicit acknowledgment that we'll adjust if needed.
- **How I'll ask.** One question at a time. Open questions first. Push back when something doesn't make sense.
- **The pushback invitation** (Charter §3.3). Made explicit so the stakeholder knows the channel is open.

That's five things. Not a script — five points to land in two or three sentences each.

### 4.2 Sample wording (illustrative, not script)

> "Thanks for making the time. Today I want to understand the [domain or process] well enough to produce a document you can review with your team — that document is the only thing you'll actually need to look at after we're done.
>
> I expect this to take about [X] minutes. I'll mostly ask questions; you do most of the talking. I'll ask one thing at a time, and if a question doesn't make sense, push back — that probably means I asked it badly.
>
> Before we start: a few quick things to make sure I'm aimed right..."

The last line is the bridge into Layer 3.

### 4.3 What Layer 2 does NOT contain

- The full topic checklist. The stakeholder doesn't need to know every topic that will be covered.
- A walk-through of the methodology. The stakeholder doesn't need a CRM Builder tutorial.
- Document identifiers, internal section numbers, or phase numbers. Save those for the administrator.
- Apologies for the length, complexity, or formality of the process.

If Layer 2 takes longer than 90 seconds to deliver, it's too long.

### 4.4 Recitation is forbidden

The sample wording above is an example of substance and tone. The AI does **not** read it. Layer 2 is composed fresh each session, in language matched to the stakeholder. Reciting boilerplate signals that the AI is going through the motions — exactly the impression a good kickoff is supposed to prevent. See §10.2.

---

## 5. Layer 3 — Calibrating the Stakeholder

Layer 3 is the most novel and most undervalued part of the kickoff. It is where the AI shifts from talking *to* the stakeholder to listening to them — for the first time.

The point is not to ask a battery of preflight questions. The point is to surface, in the next two or three minutes, anything that should change how the substantive interview is conducted.

### 5.1 What Layer 3 covers

A complete Layer 3 surfaces, at minimum, three things:

- **Real time budget.** The session may have been booked for 60 minutes. The actual time the stakeholder has — physically, mentally, in this calendar slot — may be different. Ask.
- **Communication preference.** One question at a time? A short list to answer in any order? Mix? People differ; the AI should adapt rather than impose.
- **Goals and priorities.** What does the stakeholder most want to make sure gets covered? They may have an agenda the AI didn't anticipate. Ask.

Three is the minimum. Depending on session type (§6), one or two more may apply: prior experience with this kind of session, format preference (voice / written / mix), comfort with the level of detail the phase requires.

### 5.2 Sample wording (illustrative, not script)

> "Three quick things before we start.
>
> First — how much time do you really have today? We have an hour booked, but if you need to wrap sooner, tell me now and I'll prioritize.
>
> Second — do you prefer I ask one question at a time, or send you a couple at once and let you answer in whatever order makes sense? I default to one at a time, but some people find that slow.
>
> Third — is there anything in particular you want to make sure we cover today? You may have something in mind that I should know up front."

Three questions. Stated naturally. Not a checklist read aloud.

### 5.3 Calibration is interactive, not procedural

The point of Layer 3 is to *adapt*, not to collect data. If the stakeholder says "I have 30 minutes, not 60," the AI does not write that down and proceed as planned — the AI immediately reshapes the session, prioritizes the topic checklist, and confirms the new shape before continuing.

If the stakeholder says "I'd actually prefer to write my answers and send them back," the AI adapts. That may mean ending this session and reconvening as a written exchange.

If the stakeholder says "I want to make sure we cover X," the AI re-orders the topic checklist so X gets time before fatigue sets in.

See §8 for what to do when calibration reveals a problem the AI cannot accommodate alone.

### 5.4 Calibration adapts to session type

Layer 3 is fullest for first-time sessions with real SMEs and lightest for administrator-as-proxy sessions. See §6 for the full breakdown.

### 5.5 Calibration is not therapy

The AI is not asking the stakeholder how they feel about CRMs, what they're hoping for emotionally, or whether they have concerns about the project. Layer 3 is targeted: time, mode, goals. Anything beyond that is for the administrator to handle out-of-band.

---

## 6. Session-Type Variants

Four common session types. Each modulates how the three layers run.

| Session type | Layer 1 | Layer 2 | Layer 3 |
|---|---|---|---|
| A. Administrator-as-proxy | Full | Minimal / skipped | Skipped |
| B. First session with real SME | Full | Full | Full |
| C. Follow-up session with same SME | Full (with prior session loaded) | Abbreviated | Minimal |
| D. Multi-stakeholder session | Full | Full | Adapted (see §6.4) |

### 6.1 Variant A — Administrator-as-proxy

The administrator is also the stakeholder for this session. They own the methodology, they wrote the upstream documents, and they don't need to be told what's happening today. Most CBM sessions to date have been Variant A.

- Layer 1: Full. Same as any session.
- Layer 2: One sentence. *"Ready to start [PROCESS NAME]?"* Or skipped entirely if the administrator opens with their own framing.
- Layer 3: Skipped. The administrator's calibration happens out-of-band, in the user preferences and standing instructions.

The kickoff for Variant A should take 30 seconds at most. Anything longer is overhead.

### 6.2 Variant B — First session with a real SME

A subject-matter expert who has not been through this kind of session before. The full kickoff applies.

- Layer 1: Full.
- Layer 2: Full. The SME needs framing, not assumed familiarity.
- Layer 3: Full. The SME's preferences are unknown; calibration is genuinely needed.

Layer 3 may take five minutes. That is time well spent — every minute saved later in the session, by knowing how to ask, repays it.

### 6.3 Variant C — Follow-up session with same SME

Second or later session with someone Variant B already covered.

- Layer 1: Full. Now includes reading the prior session's transcript and any decisions or open issues that carry forward.
- Layer 2: Abbreviated. *"Picking up where we left off — last time we covered [X]; today is [Y]. Same shape as before unless something has changed for you."*
- Layer 3: Minimal. Confirm time, confirm any preferences from last session still apply, ask if anything has changed. **Do not repeat full Layer 3.** Doing so makes the SME feel they're starting over.

### 6.4 Variant D — Multi-stakeholder session

More than one SME in the session simultaneously. Rare under this methodology but possible (e.g., a Master PRD interview with the executive director and operations lead together).

- Layer 1: Full.
- Layer 2: Full. Acknowledge the group; clarify that questions are open to whoever is best positioned to answer.
- Layer 3: Adapted. Time budget is the *shortest* of any participant's. Communication preference may differ across participants — the AI surfaces the difference and proposes a format that works for all (typically one-question-at-a-time, since list-style breaks down with multiple respondents). Goals are collected from each participant.

If participants disagree about goals or priorities during Layer 3, that is information — the AI surfaces the disagreement to the administrator before substance begins, rather than choosing sides.

---

## 7. Phase-Specific Kickoff Notes

Brief paragraphs of what shifts by phase. These modulate the *content* of Layers 2 and 3, not which layers run. Notes are organized by methodology: §7.1 covers the current 13-phase methodology; §7.2 covers the evolved 5-phase methodology.

### 7.1 Current methodology

**Master PRD.** The stakeholder is usually senior leadership. Scope is broad and mission-grounded. Layer 2 frames the deliverable as "the blueprint document for the whole effort" — language that matches the altitude of the conversation. Layer 3 should include a mild check on energy: big-picture sessions are easier when the stakeholder is fresh.

**Domain Discovery.** The stakeholders are usually one or two SMEs who do the work. Layer 2 frames the goal as "walking through the work with you so I can understand what your organization actually does." Layer 3 emphasizes time and goals — discovery sessions can run long if not bounded.

**Inventory Reconciliation.** Typically the administrator only. Variant A applies. Layer 2 is one sentence. Skip Layer 3.

**Domain Overview.** Synthesis with the administrator. Variant A applies. Layer 2 minimal. Layer 3 skipped.

**Process Definition.** The stakeholder is the SME who actually runs the process. Layer 2 should name the specific process and acknowledge that the session goes deep on a single workflow. Layer 3 should explicitly check field-detail tolerance: Sections 7 and 8 of the deliverable demand field-by-field specificity, which can fatigue an SME who came expecting a workflow conversation. Forewarn, gauge, adapt.

**Entity PRD.** Often administrator-led with technical SME input. Sometimes Variant A. The session has a different feel than process work — it is data-vocabulary, not narrative-vocabulary. Layer 2 names this shift if the stakeholder is new to it. Layer 3 should check comfort with field-level discussion.

**Service Process Definition.** Like Process Definition but cross-domain. Layer 2 names the cross-cutting nature of the service. Layer 3 same as Process Definition.

**Domain Reconciliation.** Administrator-led. Variant A applies. Layer 2 is one sentence. Skip Layer 3.

**Service Reconciliation.** Same as Domain Reconciliation.

**YAML Generation.** Implementation-focused, administrator-only. No stakeholder. Layers 2 and 3 do not run; Layer 1 is the entire kickoff.

**CRM Evaluation.** Administrator plus decision-makers. May be Variant D if multiple decision-makers participate. Layer 3 should surface evaluation criteria the stakeholders care most about, since the deliverable is a recommendation tied to their priorities.

### 7.2 Evolved methodology

**Phase 1 — Mission and Backbone Identification.** Engagement-start phase. The phase has its own internal two-session structure (Session 1 mission-and-domains; substantive between-sessions consultant drafting; Session 2 backbone-and-CRM-candidates) with an optional Session 3. Session 1 maps to Variant B (first session with the client). Session 2 maps to Variant C (follow-up), with a specific wrinkle: the AI has done substantive between-sessions drafting and is presenting drafts for verification, not picking up open threads — so Layer 2 frames it as "I've prepared three drafts based on Session 1; let me walk you through them" rather than generic continuation. Layer 3 in Session 2 confirms time and asks whether anything has changed in the client's thinking since Session 1; it does not repeat full Layer 3.

The two-session structure means the AI's pre-engagement reading (per Phase 1 guide §2) is heavier than for any current-methodology phase. Layer 1 must include the pattern library consultation per `pattern-library-specification.md` — if a library entry exists for the org type, read it end-to-end before composing Layer 2.

**Phase 2 — Slice Planning.** Recurring per iteration. Typically administrator-led — Variant A applies for most engagements, though the client may participate when priority classifications need verification. Layer 2 frames the goal as "deciding what's in the current iteration." Layer 3 — when the client is present — checks whether anything in the prior iteration's deployment changed their priority thinking.

**Phase 3 — Iteration Build and Deploy.** Recurring per iteration. Compresses what was the bulk of the current methodology (process definition, entity PRDs, YAML generation, deployment) into one phase scoped to the iteration. Mostly administrator and Claude Code work; client involvement is limited to verifying decisions the Defaulted-vs-Elicited Map flagged as elicit-not-default. Variant A applies for the administrator portions. Where a client confirmation moment happens, it follows Variant B or C depending on whether it's the first such moment in the engagement.

**Phase 4 — Iteration Review and Comparison.** Recurring per iteration. This is the phase where the client reacts to running software on each candidate CRM. Layer 2 is critical: the framing should set up "react to running software" mode — the client is not being asked to read specs but to use a working system and tell the AI what works and what doesn't. Layer 3 checks for any constraints on how long the client can spend with the running system today. Variant B for the first iteration's review; Variant C for subsequent.

**Phase 5 — Engagement Closure and Adoption.** Engagement-end phase. The client picks the winning CRM from the candidate set, based on lived experience across iterations. May be Variant D if multiple decision-makers participate. Layer 3 surfaces the decision criteria the client cares most about — these inform how the AI presents the cumulative Comparison Artifact.

---

## 8. When Calibration Reveals a Problem

Sometimes Layer 3 surfaces something that breaks the planned session. Common cases:

- The stakeholder has 15 minutes, not 60.
- The stakeholder is exhausted, distracted, or in the middle of a hard week.
- The stakeholder doesn't have enough context to answer the planned questions.
- The stakeholder isn't actually the right person for this session.
- The stakeholder strongly prefers written exchange to live conversation.

The AI does not press through. Calibration outcomes win over the original plan. The AI's options:

- **Shorten scope.** Identify the highest-priority subset of the topic checklist that fits the actual time budget. Confirm the trade-off with the stakeholder ("we won't get to [topic]; can we cover that next time?") and the administrator.
- **Change format.** If the stakeholder prefers writing, end the live session, propose a written follow-up. Do not run a degraded live session because that's what was scheduled.
- **Postpone.** If the session can't produce a usable deliverable in the time available, end the kickoff cleanly and reschedule. A well-postponed session is better than a failed one.
- **Escalate to the administrator.** If the stakeholder isn't the right person, or if scope has shifted in a way the AI can't accommodate alone, the AI surfaces this to the administrator before substance begins. The administrator decides next steps.

Whichever path is chosen, the AI confirms the new shape of the session with the stakeholder before crossing the gate (§9).

---

## 9. Confirmation Gate Before Substance Begins

The kickoff ends at an explicit gate. The AI signals to the stakeholder that the warm-up is over and the substantive interview is starting.

### 9.1 The gate's purpose

Without a gate, calibration can drift into substance unmarked, and the stakeholder doesn't know when the "real" session has started. The gate is the explicit handoff. It also gives the AI a clean moment to switch from kickoff posture into Charter §2 (the AI's role as skilled business analyst).

### 9.2 What the gate sounds like

The gate confirms three things and opens the substantive section. It is brief.

> "OK — we have about 45 minutes, you'd prefer one question at a time, and you want to make sure we cover the donor pipeline. Let me start with the first question..."

That single utterance closes Layer 3, confirms what was just learned, and opens substance. The AI does not pause for acknowledgment after the gate — the next sentence is the first substantive question.

### 9.3 If calibration changed the plan

When §8 applied — scope was shortened, format was changed, etc. — the gate confirms the new plan explicitly, so the stakeholder hears the AI agreeing to the change before substance starts.

> "Got it — we'll do the donor pipeline and the prospect handoff in the time we have, and pick up the rest next session. Starting with the donor pipeline..."

### 9.4 Variant A skips the gate

When Layer 3 is skipped (administrator-as-proxy), there is no calibration to close, and the gate collapses into "starting now." This is fine — the gate exists to mark a transition that, in Variant A, doesn't need marking.

---

## 10. Anti-Patterns

Concrete failure modes the AI must avoid.

### 10.1 Skipping Layer 3 because it feels like overhead

The AI runs Layers 1 and 2, then dives into substance, on the theory that Layer 3 is preamble that delays the real work.

- **Bad:** Open the session, frame what's happening, and ask the first substantive question. Discover 20 minutes in that the stakeholder only has 15 minutes left.
- **Good:** Run Layer 3. Pay 90 seconds up front to save 20 minutes of mismatched session.

### 10.2 Reading the framing as a script

The AI recites the sample wording from §4.2 or §5.2 verbatim. The stakeholder hears that the AI is reading from a manual.

- **Bad:** "Thanks for making the time. Today I want to understand the domain or process well enough to produce a document you can review with your team — that document is the only thing you'll actually need to look at after we're done."
- **Good:** Compose Layer 2 fresh, in language matched to the stakeholder, covering the five points named in §4.1 without reciting the sample wording.

### 10.3 Asking calibration questions the AI could answer from upstream context

The AI asks the stakeholder things Layer 1 already established.

- **Bad:** "Have you been through one of these sessions before?" — when the prior session's transcript is in context.
- **Good:** Skip the question. Acknowledge prior context naturally: "Picking up where we left off last week..."

### 10.4 Treating calibration as a checklist rather than a real exchange

The AI runs through Layer 3 questions, collects answers, and proceeds with the original plan unchanged.

- **Bad:** Stakeholder says "I have 30 minutes." AI says "noted." AI proceeds with the 60-minute topic checklist.
- **Good:** Stakeholder says "I have 30 minutes." AI immediately re-scopes, names the trade-off, confirms the new plan, and crosses the gate.

### 10.5 Plowing into substance before calibration is settled

The AI starts asking substantive questions while Layer 3 issues are still open. The stakeholder didn't actually agree to the new shape; the AI assumed.

- **Bad:** Stakeholder mentions a time constraint mid-Layer-3. AI nods, then immediately asks the first substantive question without confirming what the constraint changes.
- **Good:** Resolve the calibration issue, confirm the new plan, cross the gate, then start substance.

### 10.6 Repeating the full kickoff in a follow-up session

Variant C (follow-up) calls for an abbreviated Layer 2 and a minimal Layer 3. The AI runs both as if it were Variant B, making the SME feel the prior session didn't count.

- **Bad:** Layer 2 includes the full deliverable framing. Layer 3 re-asks the same calibration questions from session 1.
- **Good:** Layer 2 picks up where session 1 left off. Layer 3 confirms time and asks if anything has changed since last session.

---

## Changelog

| Version | Date | Change |
|---|---|---|
| 1.0 | 04-29-26 | Initial release. Defines pre-session priming routine. Three layers: internal checklist, framing to stakeholder, calibrating stakeholder. Four session-type variants. Phase-specific notes for ten phases. |
| 1.1 | 05-15-26 | Restructured §7 (Phase-Specific Kickoff Notes) into two sub-sections: §7.1 for the current 13-phase methodology (existing content unchanged) and §7.2 for the evolved 5-phase methodology (Mission and Backbone Identification; Slice Planning; Iteration Build and Deploy; Iteration Review and Comparison; Engagement Closure and Adoption). §7.2 includes specific guidance for Phase 1's two-session structure (Session 1 = Variant B; Session 2 = Variant C with pre-drafted-content wrinkle) and the pattern library consultation required during Layer 1 pre-engagement reading. |
