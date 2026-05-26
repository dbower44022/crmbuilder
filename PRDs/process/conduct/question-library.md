# CRM Builder — Interview Question Library

> **Status: Transitional.** This document is being consolidated into the Master CRMBuilder PRD at `specifications/master-crmbuilder-PRD.md` (in development). Once the Master CRMBuilder PRD covers this content, this document will be archived. Continue to use this as reference until that supersession is explicit.

**Version:** 1.1
**Last Updated:** 05-15-26 19:10
**Purpose:** Annotated good/bad question examples organized by question intent. Provides the worked illustrations that `conduct/charter.md` references but does not contain.
**Scope:** All `interview-*.md` and `guide-*.md` phase documents in `PRDs/process/interviews/`. Phase guides cite specific entries by name rather than inventing local examples.
**See also:** `conduct/charter.md` (global conduct rules), `conduct/kickoff.md` (pre-session priming).

---

## How to Use This Library

This library contains worked examples of how to ask questions during a stakeholder-facing session. Each entry shows a bad version, a good version, and the reasoning that distinguishes them.

**Organization.** Entries are grouped by **question intent** — what the AI is trying to elicit when it composes the question. The same intent often applies across multiple phases; phase relevance is noted within each entry rather than driving the structure.

**When to consult.** When the AI is composing a question and isn't sure how to phrase it. When a phase guide cites an entry by name. When a session has gone wrong and the AI is diagnosing why.

**Entry format.**

- **Title** — what the entry covers
- **When to use** — the situation calling for this question
- **Bad example** — verbatim
- **Why it's bad** — one or two sentences
- **Good example** — verbatim
- **Why it works** — one or two sentences
- **Variants** — optional alternate phrasings
- **Phase relevance** — which phases this most applies to
- **See also** — related entries and Charter sections

**Phase abbreviations used in entries.** Two methodologies are referenced; entries note phase relevance for whichever apply.

- **Current methodology (13-phase):** Master PRD, Domain Discovery, Inventory Reconciliation, Domain Overview, Process Definition, Entity PRD, Service Process Definition, Domain Reconciliation, Service Reconciliation, CRM Evaluation, YAML Generation.
- **Evolved methodology (5-phase):** Phase 1 Mission and Backbone Identification; Phase 2 Slice Planning; Phase 3 Iteration Build and Deploy; Phase 4 Iteration Review and Comparison; Phase 5 Engagement Closure and Adoption.

---

## Category 1 — Eliciting People and Roles

### 1.1 Eliciting a persona from the work, not the org chart

**When to use.** The AI needs to identify the people who participate in a process or domain. The temptation is to ask about job titles or organizational structure; the better question elicits roles defined by the work itself.

**Bad example.** "Can you give me your org chart? Who reports to whom?"

**Why it's bad.** Org charts capture employment relationships, not work relationships. A volunteer who runs a critical workflow doesn't appear on an org chart; an executive who never touches the workflow does. The org-chart question gives a list of people the AI then has to translate into roles — and the translation is exactly what the stakeholder should be doing.

**Good example.** "When this process runs, who actually does the work? Walk me through the people involved — paid, volunteer, internal, external — anyone whose hands are on it."

**Why it works.** It elicits roles defined by participation in the work. Job titles emerge as a side effect when the stakeholder names the role; if a role has no title (a common case in nonprofits), the role still gets named.

**Variants.**
- For Master PRD: "Who are the people the organization serves, and who are the people who do the serving?"
- For Process Definition: "For this specific process — say, intake — who's involved at each step?"

**Phase relevance.** Current methodology: Master PRD, Domain Discovery, Process Definition. Evolved methodology: Phase 1 (Session 1 Part C — process surfacing).
**See also.** Entry 1.2 (multi-role situations); Charter §2 (the AI's role).

---

### 1.2 Disambiguating multi-role situations

**When to use.** The stakeholder mentions a person or job title that seems to do multiple things, or different people doing what sounds like the same thing. The AI needs to know whether this is one role or several.

**Bad example.** "So the Coordinator handles both intake and matching — should we model those as one persona or two?"

**Why it's bad.** It hands a modeling decision to the stakeholder. The stakeholder doesn't think in personas; they think in people and work. The question also assumes the answer matters to them, which it doesn't — what matters is whether the work is done by the same person or different people, with the same skill set or different ones.

**Good example.** "When the same Coordinator does intake and matching — is that the same skill set, the same training, the same person every time? Or could those split between two people on a busy week?"

**Why it works.** It elicits the business reality (one role or two) without asking the stakeholder to weigh in on modeling. The AI infers the persona structure from the answer.

**Variants.**
- If the stakeholder says "same person, same skills": treat as one persona.
- If the stakeholder says "could split": treat as two personas, even if the same individual currently does both. Two personas in one body is fine; one persona doing two unrelated jobs is wrong.

**Phase relevance.** Current methodology: Master PRD, Domain Discovery, Process Definition. Evolved methodology: Phase 1 (Session 1 Part B — domain identification).
**See also.** Entry 1.1; Charter §4.4 (don't ask decisions the stakeholder shouldn't make).

---

### 1.3 Eliciting an operational mission from an aspirational one

**When to use.** The stakeholder has stated their organization's mission, but the statement is aspirational ("we empower entrepreneurs in Northeast Ohio") rather than operational ("we match aspiring entrepreneurs with experienced mentors and support that pairing for eighteen months"). The AI needs an operational mission to use as the priority test downstream — "if X stopped tomorrow, would the mission be in trouble?" — and aspirational language doesn't pass that test.

**Bad example.** "Your mission statement is too vague. Can you make it more specific and operational?"

**Why it's bad.** It frames the stakeholder's mission as deficient and asks them to do the translation work. They are typically not equipped to translate aspirational language into operational language on demand — that's the AI's job — and the framing puts them on the defensive at the start of the engagement.

**Good example.** "The materials describe your mission as empowering small business owners in Northeast Ohio. To make sure I understand it operationally — when you think about what your organization concretely does on a Tuesday morning, what's happening?"

**Why it works.** It anchors the abstract mission to a concrete moment ("Tuesday morning"). The stakeholder describes the work they actually do; the AI extracts the operational mission from the description. The translation happens in the AI's drafting, not in the stakeholder's head.

**Follow-up — testing with the priority test:**

> "Just to make sure I have this right — if you stopped matching business owners to mentors tomorrow, you wouldn't be doing your mission anymore. Yes?"

A confident yes confirms the operational mission. A hedge ("well, we'd still be doing the workshops...") means the mission has more than one operational center and the conversation isn't done. Continue until the central activities are explicit.

**Variants.**
- "Walk me through what a typical week looks like for the people doing the front-line work."
- "If a brand-new staff member started Monday, what's the work you'd want them doing by end of the week?"

**Phase relevance.** Evolved methodology: Phase 1 (Session 1 Part A — Operational Mission). Current methodology: Master PRD (Organization Overview topic).
**See also.** Charter §2 (the AI's role — translate, don't lecture); Charter §11.6.b (inferences require positive support — operational mission language must come from what the stakeholder said, not from the AI's assumptions about typical operations).

---

## Category 2 — Eliciting Work

### 2.1 Opening a workflow elicitation

**When to use.** The AI needs to understand a process — the steps, the order, the triggers. This is the question that opens that conversation.

**Bad example.** "Can you list the steps in your intake process? I'd like to capture: what triggers it, who initiates it, what tools they use, what records get created, what notifications fire, what conditions cause branching, and what the completion criteria are."

**Why it's bad.** It stacks seven questions in one turn (Charter §4.1). It uses internal CRM vocabulary (notifications, branching, completion criteria) the stakeholder may not share. It asks the stakeholder to compose a structured answer rather than narrate.

**Good example.** "Walk me through what happens when a new client comes in. Start wherever feels natural — I'll ask follow-ups."

**Why it works.** It invites narration. The stakeholder picks the entry point; the AI lets the story unfold and probes for what's missing. Triggers, tools, branches all emerge through follow-ups (entry 2.2), one at a time.

**Variants.**
- For complex processes: "If you could only describe one example walk-through, pick the most typical one and walk me through that."
- For processes with multiple entry points: "Are there different ways this can start? Walk me through the most common one first."

**Phase relevance.** Current methodology: Process Definition, Service Process Definition, Domain Discovery. Evolved methodology: Phase 3 (Iteration Build — process documents); Phase 1 Session 1 Part C surfaces processes at a lighter depth.
**See also.** Entry 2.2; Charter §4.2 (open before closed).

---

### 2.2 Surfacing branches and exceptions without leading

**When to use.** The stakeholder has narrated a "happy path." The AI needs to know where the path branches or breaks. Asking the wrong way leads the stakeholder to invent branches that don't really exist.

**Bad example.** "Does it then go to approval? Or does the system automatically route it based on amount?"

**Why it's bad.** It proposes specific branches the stakeholder may not have. The stakeholder, wanting to be helpful, may agree with one of them. The branch enters the document as a real requirement when it was actually the AI's hypothesis.

**Good example.** "You've described what usually happens. What about the unusual cases — when does it not go that way?"

**Why it works.** It invites the stakeholder to surface real exceptions in their own words. If there are no exceptions, the stakeholder says so and the AI moves on. If there are, the stakeholder names them concretely.

**Variants.**
- "Is that always the case, or does it depend on something?"
- "What's the weirdest case you've seen — what threw the normal flow off?"
- "If we tried this with [different scenario], would it still work the same way?"

**Phase relevance.** Current methodology: Process Definition, Service Process Definition. Evolved methodology: Phase 3 (Iteration Build).
**See also.** Entry 2.1; Charter §5.1 (probing without leading); Charter §11.6 (substituting AI hypothesis).

---

### 2.3 Eliciting completion criteria

**When to use.** A process has been narrated, but it's unclear when the process is *done*. The AI needs explicit completion criteria for the deliverable.

**Bad example.** "What's the exit condition for this workflow?"

**Why it's bad.** "Exit condition" is system-design language. The stakeholder hears a request for technical specification rather than a question about their work.

**Good example.** "How do you know when this is finished? What tells you the work is done?"

**Why it works.** It asks the stakeholder for the human signal of completion — which is what the AI actually needs. Completion criteria might be "the client receives their welcome packet," "the record is closed," "the coordinator marks it complete," or all three. The stakeholder names them in their own terms.

**Variants.**
- "What does success look like for this process?"
- "Once this is done, what's different than before it started?"
- For processes with multiple end states: "Are there different ways this can end? What are the typical ones?"

**Phase relevance.** Current methodology: Process Definition, Service Process Definition. Evolved methodology: Phase 3 (Iteration Build); Phase 4 (Iteration Review — testing whether deployed flows match the workability criterion).
**See also.** Charter §3.1 (translate, don't lecture).

---

## Category 3 — Eliciting Information

### 3.1 Eliciting what data matters (without listing fields)

**When to use.** The AI needs to know what information about an entity matters — what gets recorded, what gets used. The temptation is to read a field list aloud and ask the stakeholder to confirm; the better question elicits the data from the work.

**Bad example.** "For the Client entity, do you need first name, last name, email, phone, address, date of birth, gender, race, employer, job title, household income, and number of dependents?"

**Why it's bad.** It is a multi-question stack (Charter §4.1) disguised as a confirmation. The stakeholder, confronted with a list, will say yes to most of it without considering whether each item is actually used. The AI ends up with twelve fields, half of which nobody ever fills in.

**Good example.** "When you sit down with a new client, what information do you actually need from them — to do the work, not just to fill out a form?"

**Why it works.** It distinguishes data that drives the work from data that just sits in fields. The stakeholder names the things they actually rely on. Optional or never-used fields can be added later if explicitly justified.

**Variants.**
- "If you could only ask three things at intake, what would they be?"
- "What's the information you go back and look up most often?"
- "What's information you wish you had but don't currently capture?"

**Phase relevance.** Current methodology: Entity PRD, Process Definition (sections 7 and 8). Evolved methodology: Phase 3 (Iteration Build — entity PRDs and process data).
**See also.** Entry 3.3; Charter §4.5 (need-to-know vs. nice-to-know).

---

### 3.2 Eliciting field constraints in business language

**When to use.** A field has been identified. The AI needs to know its constraints — required, format, valid values — but asking in technical terms loses the stakeholder.

**Bad example.** "For the email field — should it be a non-null varchar with a regex validation pattern?"

**Why it's bad.** Database vocabulary. The stakeholder either guesses or disengages. Either way the AI doesn't get useful information.

**Good example.** "When someone gives you their email — does it have to be there before you can move forward, or do you sometimes proceed without it? And does it need to be a real working email, or do you sometimes record a placeholder?"

**Why it works.** Two related but distinct constraints — required vs. optional, validated vs. permissive — asked in business language. The stakeholder answers from their actual experience.

**Variants.**
- For enums: "Are there standard categories you use for this, or does it vary?"
- For dates: "Does this need to be the actual date something happened, or is an approximate date OK?"
- For free text: "When you write a note here, what kinds of things go in it? Anything that should be kept out?"

**Phase relevance.** Current methodology: Entity PRD, Process Definition. Evolved methodology: Phase 3 (Iteration Build — entity PRDs and field definitions).
**See also.** Entry 3.3; Charter §3.1 (translate, don't lecture).

---

### 3.3 Distinguishing required from typical

**When to use.** The stakeholder describes what "usually happens" or what people "normally include." The AI needs to know whether something is *required* (the system enforces it) or *typical* (it usually happens but isn't enforced).

**Bad example.** "So is the phone number required?"

**Why it's bad.** "Required" is a binary the stakeholder may not own. They know what people typically do; they don't know what the system should enforce. The question asks them to make a system-enforcement decision they aren't equipped to make.

**Good example.** "You said most clients give a phone number. What about the cases where they don't — do you turn them away, or do you keep going? And what does that look like in your records?"

**Why it works.** It separates the business reality (do you turn them away?) from the system enforcement question (which the AI then derives). If the stakeholder says "we keep going," the field is not required. If "we turn them away," it is. Either way the answer is grounded in their work, not in a database concept.

**Variants.**
- "What happens when this is missing? Does it block the work, or does the work proceed anyway?"
- "Is this something you can always get, or does it sometimes come later?"

**Phase relevance.** Current methodology: Entity PRD, Process Definition. Evolved methodology: Phase 3 (Iteration Build).
**See also.** Entry 3.1, Entry 3.2; Charter §4.4.

---

## Category 4 — Eliciting Boundaries

### 4.1 Eliciting cross-domain handoffs

**When to use.** A process or domain hands off work to another domain or service. The AI needs to know what crosses the boundary, when, and what state changes happen on each side.

**Bad example.** "What's the integration between Mentoring and Follow-up? Is it event-driven, or do we need a polling mechanism?"

**Why it's bad.** Integration architecture vocabulary. The stakeholder doesn't know what an event-driven integration is, and shouldn't have to. The question is asking the wrong layer.

**Good example.** "When a mentoring engagement wraps up, what happens next? Does anyone need to be notified, does anyone pick up the work, does anything carry forward to a follow-up conversation?"

**Why it works.** It elicits the business handoff in narrative form. The AI infers the integration shape from the answer — what data crosses, what triggers the handoff, what state changes on each side. The stakeholder describes their work, not a system design.

**Variants.**
- "Once this is done, who else needs to know about it?"
- "Does information from this process feed anything later — six months, a year out?"
- For services: "When this process needs to send a notification, where does that come from? Is there a standard way you do that across the organization?"

**Phase relevance.** Current methodology: Process Definition, Service Process Definition, Domain Reconciliation. Evolved methodology: Phase 1 (Session 1 Part C — backbone connections); Phase 3 (Iteration Build — cross-process handoffs).
**See also.** Charter §3.1; Charter §8 (scope-change protocol — handoffs often surface upstream gaps).

---

## Category 5 — Handling Difficulty

### 5.1 Handling "I don't know" without pressing

**When to use.** The AI asks a question; the stakeholder says they don't know, or aren't sure, or it's not their area. The temptation is to press; the better behavior is to log and move on.

**Bad example.** AI: "What's the standard intake processing time?" Stakeholder: "I'm not sure, honestly." AI: "Even a rough estimate? A range? What's it usually like in your experience?"

**Why it's bad.** Pressing produces a guess that gets recorded as an answer. The deliverable then has fabricated requirements, which surface as bugs months later when implementation hits reality.

**Good example.** AI: "What's the standard intake processing time?" Stakeholder: "I'm not sure, honestly." AI: "Got it — I'll log that as an open question. Is there someone on your team who'd have that data?"

**Why it works.** It accepts the answer without judgment, captures it as a structured open issue, and identifies the right next person. The session keeps moving; the gap is documented for resolution out-of-band.

**Variants.**
- "No problem — let me put a placeholder and we can revisit. Who would I ask?"
- "Skip it for now; I'll come back to that one if there's time."

**Phase relevance.** All phases, both methodologies.
**See also.** Charter §5.3 (handling "I don't know"); Charter §11.6 (substituting AI hypothesis).

---

### 5.2 Recognizing and surfacing a guess

**When to use.** The stakeholder is answering, but the language hedges in ways that suggest they're reasoning rather than recalling. The AI needs to surface this gently so the answer is recorded with the right confidence level.

**Bad example.** AI captures "Standard intake takes 2–3 weeks" as a confirmed requirement, when the stakeholder said "I think probably 2–3 weeks usually, depending."

**Why it's bad.** Hedge words signal uncertainty. Recording the answer without preserving the hedge promotes a guess to a fact. Implementation will plan against the fact and discover the guess too late.

**Good example.** AI: "It sounds like that varies. Let me capture this as 'typically 2–3 weeks, varies by case' and flag it as something to confirm with someone who tracks intake metrics. Sound right?"

**Why it works.** It explicitly preserves the uncertainty in the recorded answer. The stakeholder hears the AI not over-claiming; the deliverable carries the hedge into downstream work.

**Variants.**
- "I'm hearing 'usually' — does the variation matter for the document, or is the typical case enough?"
- "Want me to log this as a confirmed answer or as something we should verify with [the person who'd know]?"

**Phase relevance.** All phases, both methodologies. Particularly important in the evolved methodology's Phase 1, where the tightened 'inferences require positive support' discipline (Charter §11.6.b) applies; see Entry 5.5.
**See also.** Charter §5.2 (recognizing guessing); Entry 5.1.

---

### 5.3 Handling contradiction with upstream

**When to use.** The stakeholder describes something that contradicts a document already produced (Master PRD, Domain Overview, prior process doc). Charter §8 says: stop, name, propose handling. This entry shows the *how*.

**Bad example.** AI silently adjusts the new document to match what the stakeholder is saying, ignoring the contradiction with the upstream. Or worse, AI argues with the stakeholder ("but the Master PRD says X").

**Why it's bad.** Silent adjustment produces inconsistent documents that fail reconciliation later. Arguing makes the stakeholder feel cross-examined, and the AI is wrong to argue anyway — the upstream document might be the one that's wrong.

**Good example.** "Hold on — what you just described is different from how this is captured in the Domain Overview. The overview says [X]; you're describing [Y]. Two possibilities: either the overview needs to be updated to match what you're telling me, or one of us is misreading. Want me to flag this so we can reconcile, or is there a quick way to clear it up now?"

**Why it works.** It names the contradiction without taking sides. It offers two paths (update upstream vs. reconcile). It respects the stakeholder as a source of truth while preserving the upstream document's role until the contradiction is resolved.

**Variants.**
- For minor contradictions: "Quick check — earlier you said [X]; now I'm hearing [Y]. Which is it, or is the difference important?"
- For contradictions that require research: "Let me log this as an issue and we'll reconcile after the session."

**Phase relevance.** Current methodology: all phases past Master PRD. Evolved methodology: Phase 4 (Iteration Review — where running-software contradictions with specifications surface); Phase 3 (Iteration Build — when prior iteration's specs disagree with what the new iteration needs).
**See also.** Charter §8 (scope-change protocol); `guide-carry-forward-updates.md`.

---

### 5.4 Handling stakeholder fatigue

**When to use.** The stakeholder's answers are shortening, losing detail, or becoming repetitive. They may not be saying they're tired — but they are.

**Bad example.** AI continues through the topic checklist on the theory that finishing matters more than the quality of the answers. The remaining 30 minutes produce thin, generic content that has to be redone in a follow-up session anyway.

**Why it's bad.** It wastes the stakeholder's time and the deliverable's quality. Pushing through fatigue is one of the fastest ways to make the methodology feel painful.

**Good example.** "I'm noticing we've been at this a while and I want to make sure we don't burn you out. We've covered [X] solidly. The remaining topics are [Y, Z]. Three options: keep going for another 15 minutes, wrap now and pick up next time, or do [Y] now and save [Z] for later — your call."

**Why it works.** It names the situation without attributing fatigue. It puts the choice in the stakeholder's hands. It explicitly preserves what's already been covered as solid, so wrapping now isn't a failure — it's a clean break.

**Variants.**
- "We have 15 minutes left and two topics. We can rush both or do one well — preference?"
- "You've earned a break. Want to pause for two minutes or wrap?"

**Phase relevance.** All phases, both methodologies. Most common in current methodology's Process Definition (long sessions with deep field detail) and in evolved methodology's Phase 1 (two- or three-session structure).
**See also.** Charter §11.5 (pushing past fatigue); Kickoff §5 (Layer 3 calibration on time budget).

---

### 5.5 Surfacing inferences for verification (the "positive support" check)

**When to use.** The AI catches itself drawing a conclusion that goes beyond what the stakeholder directly stated. The conclusion sounds plausible because it matches patterns the AI has seen in similar organizations — but the stakeholder has not said anything that directly supports it. Per Charter §11.6.b, inferences without positive support are confirmation-bias traps and must be converted to explicit questions before they enter the documentation.

**Bad example.** *(The AI proceeds silently with the inference and writes it into the deliverable as if confirmed.)* "Most nonprofits separate operational from strategic donor work, so we'll capture two donor categories — operational donors and strategic donors."

**Why it's bad.** The stakeholder never said they distinguish operational from strategic donors. The split is plausible from generic nonprofit patterns but may not apply to this specific organization. If the AI proceeds on the assumption, downstream specifications carry the fabrication unnoticed; by the time the system is built and the client sees that donor records are split this way, the original assumption is buried and the rework is expensive. The CBM redo experiment documented this exact failure mode.

**Good example.** "I'm noticing organizations like yours sometimes distinguish operational from strategic donor work — different teams, different rhythms, different records. Is that something you do, or is donor work undifferentiated for you?"

**Why it works.** The AI explicitly names the inference and surfaces it as a question. The stakeholder can confirm ("yes, that's how we work"), correct ("no, we don't separate that — all donor work goes through one team"), or partially confirm ("we don't currently, but it's something we've been thinking about"). Whichever response, the deliverable now reflects the stakeholder's actual reality.

The test to apply mentally before proceeding on an inference: *"What did the stakeholder actually say that supports this?"* If the answer is *"Nothing directly, but it follows from how similar orgs typically operate,"* the inference is not yet legitimate. Convert to a question, capture as a gap, or — if a pattern library entry exists for the org type — consult the library to distinguish library-tested patterns from generic plausibility.

**Variants.**
- "I want to check an assumption — [X] is common for organizations like yours, but I don't want to assume it applies to you. Does it?"
- "Hold on — I'm about to write down [Y]. Let me ask first whether you actually do that, since I'm inferring it from how things usually work in this space."
- "If a pattern library entry exists:" "The library entry for [org type] says [X] is a tested pattern. Does it match how you work?"

**Phase relevance.** Evolved methodology: all phases, but especially Phase 1 Session 1 Parts B and C (high inference density) and Phase 4 (reacting to running software, where the AI may infer reasons for client reactions). Current methodology: all phases, particularly Domain Discovery (Phase 2) and Process Definition (Phase 4).
**See also.** Charter §11.6.b (the rule itself); Charter §5.2 (recognizing guessing — related but distinct: 5.2 is about the stakeholder's guesses; this entry is about the AI's); pattern-library-specification.md §3.1 (the tested-vs-observed distinction the AI applies when a library entry exists).

---

## Category 6 — Handling Decisions and Confirmation

### 6.1 Presenting options when a decision is needed

**When to use.** A genuine decision needs to be made — one the stakeholder owns, not one the AI should make alone (per Charter §4.4). The stakeholder needs enough framing to choose without being overwhelmed.

**Bad example.** "There are several ways we could handle this. We could do option A which has properties X, Y, Z, with trade-offs P, Q, R; option B which has properties M, N, O, with trade-offs S, T, U; option C which combines elements of A and B; option D which..."

**Why it's bad.** It treats the stakeholder as a CRM consultant. They don't have the context to evaluate the options as presented; they certainly don't want to. The decision gets stalled or made on the wrong basis.

**Good example.** "Two ways to handle this. Option one: every client has exactly one mentor at a time. Simple, matches how you mostly work. Option two: a client can have multiple mentors at once for different topics. More flexible, but it adds complexity to scheduling and reporting. I'd lean toward one unless you tell me multi-mentor is common — what's your read?"

**Why it works.** Two options, not five. Each option named in business terms, not technical terms. AI gives a recommendation with the reason for it, leaving the stakeholder free to confirm or override. The stakeholder is being asked to validate a tentative answer, not to architect from scratch.

**Variants.**
- For binary decisions: "I think it should be [X] because [reason]. Agree, or do you want to do [Y]?"
- When the AI genuinely has no preference: "Either works. Which fits how your team thinks?"

**Phase relevance.** All phases where the stakeholder owns substantive decisions. In evolved methodology: Phase 4 (decision: does the deployed slice pass the workability test?); Phase 5 (CRM selection).
**See also.** Charter §4.4; Charter §2 (propose, don't dictate).

---

### 6.2 Confirming without re-asking

**When to use.** A decision was made earlier in the session (Charter §6.1 decision callout). The AI needs the decision to inform a subsequent question — but should not re-confirm the original decision while doing so.

**Bad example.** AI: "Earlier you said clients have exactly one mentor at a time — is that still right? OK, given that, when a client's mentor goes on leave..."

**Why it's bad.** The decision was confirmed when it was made. Re-confirming wastes time, signals the AI doesn't trust its own notes, and produces confirmation fatigue (Charter §6.4).

**Good example.** "OK, so given one mentor per client — what happens when that mentor goes on leave? Does the client wait, or get reassigned?"

**Why it works.** The decision is referenced as established context, not re-validated. The new question builds on the prior decision without litigating it. If the stakeholder wants to revisit the prior decision, they will — the AI doesn't need to invite the reopening.

**Variants.**
- "Building on what we said earlier about [X] — [next question]."
- "Same model as [prior decision] applies here, right? OK, then..." — only if the parallel is genuinely uncertain.

**Phase relevance.** All phases, both methodologies.
**See also.** Charter §6 (confirmation cadence); Charter §11.4 (re-confirming what's already settled).

---

### 6.3 Making a confident proposal with grounded reasoning

**When to use.** The AI has done its homework — read upstream documents, consulted the pattern library, understood the org type — and has a substantive recommendation to make. The stakeholder owns the final decision but is not equipped to make it cold. This is the "CRM Builder proposes, client verifies" pattern from the evolved methodology's Principle 4.

The distinction from Entry 6.1 (presenting options): 6.1 is when two or more genuinely viable paths exist and the stakeholder needs to choose between them. 6.3 is when the AI has one well-grounded proposal and the stakeholder's job is to verify or correct.

**Bad example.** "Based on the materials, I think your mission-critical processes are mentor recruitment, client intake, and engagement management. Does that sound right?"

**Why it's bad.** The "does that sound right?" framing invites a polite yes. The reasoning behind the proposal is hidden, so the stakeholder cannot push back on a specific premise — only on the whole thing. The AI also under-claims its work by saying "I think," which signals uncertainty even when the work is solid.

**Good example.** "Based on the operational mission we just established — matching mentors to clients and supporting that pairing — I would propose three mission-critical processes: mentor recruitment, client intake, and engagement management. Mentor recruitment because without mentors there's nothing to match; client intake because without clients there's no demand; engagement management because the value is in the supported pairing over time, not in the moment of match. The fundraising work is essential to your organization but isn't mission-critical in the operational sense — if you stopped fundraising tomorrow, you'd still be doing the matching for as long as funds lasted. Does this set match how you think about it, or am I missing something or over-claiming somewhere?"

**Why it works.** The AI states the proposal confidently, names the reasoning for each item, applies the priority test explicitly to one item that *wasn't* included, and ends with a verification question that invites disagreement at the specific-item level. The stakeholder can correct ("actually fundraising is mission-critical because...") without having to question the AI's whole approach.

The opening "Based on [X]" anchors the proposal to something the stakeholder said. The reasoning under each item ("because without mentors there's nothing to match") lets the stakeholder agree with the reasoning or disagree at a specific step. The closing "am I missing something or over-claiming somewhere?" invites both directions of correction.

**Variants.**
- "I would propose [X] because [reason]. Does that match, or do you see it differently?"
- "Working from [upstream document], my read is [X]. Want to push back on any piece of that?"
- For a confident-but-uncertain proposal: "I'd lean toward [X] based on [reason], but I'd want to check that against your judgment — is there something I'm not seeing?"

**Phase relevance.** Evolved methodology: throughout — this is the methodology's signature dynamic. Especially Phase 1 (mission, domain, backbone, and CRM candidate proposals); Phase 2 (slice composition); Phase 4 (workability verdicts). Current methodology: applies in Domain Reconciliation and Inventory Reconciliation where the AI proposes dispositions; less central than in the evolved methodology.
**See also.** Entry 6.1 (presenting options — use when multiple paths are viable); Charter §2 (the AI's role — propose, don't dictate); Charter §11.6.b (the proposal's reasoning must rest on positive support, not pattern-matched plausibility).

---

## Changelog

| Version | Date | Change |
|---|---|---|
| 1.0 | 04-29-26 | Initial release. Fifteen entries across six categories: people and roles (2), eliciting work (3), eliciting information (3), eliciting boundaries (1), handling difficulty (4), handling decisions and confirmation (2). |
| 1.1 | 05-15-26 | Updated all fifteen existing entries' phase relevance metadata to cover both the current 13-phase methodology and the evolved 5-phase methodology. Added three new entries surfaced by the evolved methodology: Entry 1.3 (Eliciting an operational mission from an aspirational one) — the aspirational-to-operational translation move; Entry 5.5 (Surfacing inferences for verification — the "positive support" check) — operationalizes Charter §11.6.b as a question pattern; Entry 6.3 (Making a confident proposal with grounded reasoning) — the "CRM Builder proposes, client verifies" pattern distinct from Entry 6.1's options presentation. Library now has eighteen entries. |
