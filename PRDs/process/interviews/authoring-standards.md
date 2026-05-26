# CRM Builder — Interview and Guide Authoring Standards

> **Status: Transitional.** This document is being consolidated into the Master CRMBuilder PRD at `specifications/master-crmbuilder-PRD.md` (in development). Once the Master CRMBuilder PRD covers this content, this document will be archived. Continue to use this as reference until that supersession is explicit.

**Version:** 1.2
**Last Updated:** 05-24-26 12:31
**Purpose:** Authoring contract for every file under `PRDs/process/interviews/`
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`

---

## 1. Scope

This document governs how the interview guides and synthesis guides
under `PRDs/process/interviews/` are written. It is an authoring
contract for the files that CRM Builder loads as Claude context during
Phases 1–10 of the Document Production Process.

It does **not** govern the deliverables produced by those
conversations — the shape of the Master PRD, the Domain PRD, and so
on is specified in the `.docx` process doc itself. This file governs
the **instructional layer**: the guides that tell Claude how to run
the conversation that produces those deliverables.

The `.docx` process doc is the authority. If this file and the
`.docx` ever disagree, the `.docx` wins and this file is corrected.

### 1.1 When the `.docx` conflicts with itself

The `.docx` process doc has occasionally grown internal
inconsistencies as it has been revised. When authoring a guide,
if two passages of the `.docx` appear to contradict each other,
follow this resolution order:

1. **Prefer the passage with explicit rationale.** A passage that states *why* (e.g., Rule 5.1's "Writing Entity PRDs before process work means guessing; writing them after means recording") is more load-bearing than a passage that only states *what*.
2. **Prefer the passage that matches observed pilot practice.** If the CBM pilot (or another implementation that has reached the relevant phase) has executed one interpretation successfully, that interpretation has been validated and should win over an unvalidated alternative reading.
3. **Surface the contradiction in the guide's Changelog.** Do not paper over it. Note which `.docx` passages conflict, which interpretation the guide adopts, and why. This creates a paper trail for a future `.docx` revision.
4. **Flag the `.docx` for revision.** Internal inconsistencies should not persist — they produce rework every time a new guide is written or a new implementation is onboarded. The first guide that catches a contradiction should flag it to the administrator, who schedules a `.docx` revision pass.

### 1.2 Validate guides against pilot practice before authoritative release

A guide that has not been validated against at least one completed
execution of its phase is a **draft** regardless of version number.
The guide's Changelog entry should state whether the version is
pilot-validated, and against which pilot. For example:

```
- **1.0** (MM-DD-YY) — Initial release. Not yet pilot-validated.
- **1.1** (MM-DD-YY) — Revised based on CBM {domain} execution.
  Pilot-validated for flat-domain case; sub-domain case not yet
  exercised.
```

Guides released without pilot validation (as this entire authoring
standards round was) are at elevated risk of over-tightening or
spec-vs-practice divergence. The first pilot execution against an
unvalidated guide should be treated as a test session, with the
administrator prepared to pause and revise the guide if it blocks
on preconditions the pilot has already demonstrably operated
without.

---

## 2. Archetypes

Every file in `interviews/` belongs to exactly one of three
archetypes. The archetype determines the file-name prefix, the body
structure, and the session tone.

| Archetype | Prefix | Body shape | Claude's role | Example |
|---|---|---|---|---|
| **Interview** | `interview-*.md` | Topics 1..N or Sections 1..N of the output document, walked sequentially with the administrator | Skilled business analyst — asks open questions, listens, probes, captures | `interview-master-prd.md`, `interview-process-definition.md` |
| **Guide** | `guide-*.md` | Steps 1..N of a synthesis, generation, or propagation workflow | Executor — reads inputs, applies rules, surfaces conflicts, produces output with minimal administrator input | `guide-domain-reconciliation.md`, `guide-yaml-generation.md`, `guide-carry-forward-updates.md` |
| **Reference** | `reference-*.md` | Subject-matter chapters, not walked in order | Not used live — loaded as supplementary context by interview or guide sessions | (none yet — reserved) |

**Do not blur archetypes.** A file that reads like an interview for
some phases and a synthesis guide for others (as the legacy
`guide-entity-definition.md` does) must be split into two files with
the correct prefix for each.

---

## 3. File naming and location

- All files live flat under `PRDs/process/interviews/`. No archetype
  subdirectories.
- File names use lowercase kebab-case.
- The phase being governed is implied by the filename, not embedded.
  Do **not** write `interview-phase-1-master-prd.md` — phase
  assignment changes when the `.docx` process doc is revised; the
  filename should not have to change with it.
- The front-matter `Purpose:` line states the phase explicitly.

Supporting assets:

- `prompt-templates/template-<slug>.md` — minimal session-prompt
  templates the administrator pastes into a fresh Claude conversation.
  One per deliverable where a template meaningfully helps.
- `prompt-optimized/prompt-<slug>.md` — tuned session prompts for
  deliverables where the short template has proven insufficient.

---

## 4. Required front-matter

Every file begins with exactly this front-matter block, in this
order, followed by a horizontal rule:

```markdown
# CRM Builder — {Title}

**Version:** {major.minor}
**Last Updated:** {MM-DD-YY}
**Purpose:** {one sentence naming the archetype, the phase, and the deliverable}
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**See also:** {one line per cross-referenced guide, or omit the line if none}

---
```

Rules:

- **Version.** Start at 1.0. Bump minor for any material change to
  the instructions. Bump major when the archetype, the governed phase,
  or the output deliverable changes.
- **Last Updated.** `MM-DD-YY` matches the project-wide convention
  used by every existing guide.
- **Purpose.** One sentence. Name the archetype, the phase, and the
  deliverable. Examples:
  - `AI interviewer guide for Phase 1 — Master PRD`
  - `AI guide for Phase 7 — Domain Reconciliation`
  - `AI guide for propagating an upstream decision across dependent documents`
- **Governing Process.** Always this exact string. Do not paraphrase.
  If the `.docx` moves, fix every file.
- **See also.** Cite the carry-forward guide whenever the body of the
  new guide has any step that might discover a change to a prior
  document. Cite sibling guides when handoffs flow between them.

---

## 5. Required section skeleton

Both archetypes share a top-level shape. Section order is fixed.
Section names should match the canonical wording exactly — this is how
Claude finds and quotes them during a session.

### 5.1 Common skeleton (both archetypes)

```
1. How to Use This Guide
2. What the {Deliverable} Must Contain
3. How to Conduct This Phase
4. Before the {Interview|Reconciliation|Generation} Begins
5. {Body — see 5.2 for Interview, 5.3 for Guide}
6. Closing / Completion Criteria
7. Changelog
```

The `How to Conduct This Phase` section (item 3) replaces what
earlier versions of this standards doc named `Critical Rules` and
`Important AI Behaviors`. See Section 6.3 for content rules.

### 5.2 Interview body (archetype: interview-*)

- A `## Interview Structure` section that lists the topics/sections
  Claude walks through, with a checkable table of contents.
- One `## Topic N — {Name}` (or `## Section N — {Name}`) heading per
  topic, walked sequentially.
- Within each topic, `### N.1`, `### N.2` subsections for the
  structured follow-up the AI must do after the open question.
- A final `## Topic N — Interview Transcript` section (or equivalent)
  that captures the transcript section of the deliverable. Interview
  deliverables always include a transcript of the conversation that
  produced them.

See `interview-process-definition.md` and `interview-master-prd.md`
as the reference implementations. Do not invent a new interview body
shape without first updating this standards doc.

### 5.3 Guide body (archetype: guide-*)

- Numbered `## Step 1 — {Name}` through `## Step N — {Name}` headings
  walked sequentially.
- Steps are named in imperative form: "Conflict Detection", "Domain
  PRD Assembly", "Review", "Document Production and Next Steps".
- Each step has explicit inputs, explicit outputs, and an explicit
  "when to stop and ask" rule if administrator input is required.

See `guide-domain-reconciliation.md` and `guide-yaml-generation.md`
as the reference implementations.

### 5.4 Guides that use a gate model

Propagation and review guides (currently `guide-carry-forward-updates.md`)
use a gate model instead of a step walk. A gate model has:

- Exactly two gates named "Gate 1 — Decision Approval" and
  "Gate 2 — Execute and Report". Two is the ceiling, not a starting
  point. If a guide needs a third gate, that's a sign the work should
  be two separate sessions.
- The template for each gate's administrator-facing request spelled
  out verbatim in the guide.

---

## 6. Content rules for each required section

### 6.1 How to Use This Guide

This section sets the tone for the entire session. It must state:

- Who the AI is in this session ("skilled business analyst",
  "executor", "propagator") and who the administrator is.
- Whether the session is a **collaborative interview** (AI asks, admin
  answers) or a **synthesis/generation** (AI reads inputs and works,
  admin answers only when asked).
- **Charter and Question Library as prerequisite reading.** Generic
  interviewer conduct — communication style, question discipline,
  listening and probing, confirmation cadence, scope-change protocol,
  transcript capture, identifier discipline — is canonically governed
  by the Interviewer Charter at `PRDs/process/conduct/charter.md`.
  Question patterns by intent live in the Question Library at
  `PRDs/process/conduct/question-library.md`. Every guide must state
  in this section that both are required reading before conducting
  the phase. Guides do not restate Charter content.
- **One-per-conversation scope.** One process per conversation. One
  domain per reconciliation. One decision per carry-forward. State
  this explicitly for the governed phase.
- **Session length.** A realistic expected duration. Every current
  guide does this. Include a stop rule when one applies
  ("stop at 60 minutes regardless of completion — schedule a
  follow-up rather than pushing through fatigue").
- **Input.** The complete list of documents that must be uploaded
  before the session starts. Be exhaustive; do not say "and any
  relevant prior work".
- **Output.** Exactly one deliverable per conversation (the process
  doc rule in Section 7.5). Name it, state its repository path using
  the Section 6 repository structure from the `.docx`, and state its
  format (`.docx` for requirements documents; `.md` or `.yaml` for
  programmatic artifacts).

### 6.2 What the {Deliverable} Must Contain

- State the complete list of required sections of the deliverable.
  Use a table with columns `#`, `Section`, `Content`.
- State the completeness standard explicitly — what makes the
  deliverable "done". Every current guide does this; new guides must
  match.
- Where the `.docx` process doc specifies a "field-level detail
  standard" or equivalent, quote it in this section rather than
  paraphrasing. Mismatched paraphrases are a common source of drift.

### 6.3 How to Conduct This Phase

This section is where Claude looks when it needs to decide whether
to stop and ask during this phase specifically. Generic interviewer
conduct (one-question-at-a-time, listen-more-than-talk, avoid leading
questions, confirmation gates after each topic, scope-change protocol,
transcript capture format, identifier-first-time-then-numbered-after,
etc.) is governed by the Interviewer Charter and is **not** restated
here. See Section 6.1 — the Charter is required reading.

- 3–10 numbered or bulleted rules, no more. Phase-specific only.
- Rules must be phrased as imperatives ("Never proceed without...",
  "Always cite identifiers when referencing..."), not descriptions.
- If a rule you would write here is already in the Charter, do not
  write it. If your guide has nothing genuinely phase-specific to
  say, this section can be as short as a one-line pointer ("All
  conduct for this phase follows the Charter; this phase has no
  phase-specific additions.").
- Two cross-cutting concerns are NOT canonically in the Charter and
  do belong in this section when relevant: the one-deliverable
  contract (Section 7.5 below) and the business-language rule
  (Section 7.8 below — phase-appropriate phrasing, including the
  Phase 10 carve-out).

### 6.4 Before the {Interview|...} Begins

- Reprise the session-start checklist from Section 7.1 of the process
  doc: ask which implementation → read CLAUDE.md → identify phase/step
  → state it and confirm.
- Add phase-specific pre-flight: input verification, CRM-familiarity
  check, opening statement template, plan-the-session script.
- Every current guide has a subsection like "Verify Inputs" or
  "Context Review" that tells Claude what to read before speaking.

### 6.5 Closing / Completion Criteria

- A checklist of deliverable completeness (every required section
  present, identifiers assigned, transcript included if applicable).
- A summary-and-confirmation script: how Claude presents the
  completed deliverable to the administrator.
- Document-production instructions: exact filename, exact repository
  path, format (Word or otherwise), and commit guidance.
- A "state next step" script: what the next phase or next session is,
  what inputs it will need, and an explicit confirmation gate before
  advancing.

### 6.6 Changelog

- One bullet per version, newest first.
- Each bullet cites the version, the date, and a one-line summary of
  what changed. Enough to answer "why did this guide change?" without
  reading diffs.

---

## 7. Cross-cutting rules — pointers to canonical source

Each rule below has a canonical source. Where the canonical source
is the Interviewer Charter, guides reference it via the prerequisite
line in `How to Use This Guide` rather than restating it. Where the
canonical source is this standards doc or a phase-specific decision,
guides state the phase-appropriate form in `How to Conduct This
Phase`.

### 7.1 Session start (process doc 7.1)

Canonical source: kickoff protocol at `PRDs/process/conduct/kickoff.md`
(three-layer pre-session routine and session-type variants). Guides do
not restate this; they may reprise the implementation → CLAUDE.md →
phase confirmation script in `Before the X Begins` for ergonomics.

### 7.2 Context requirements (process doc 7.2)

Canonical source: `How to Use This Guide` Input list per guide.
Each conversation type has defined inputs; Claude does not proceed
if required inputs are missing.

### 7.3 Confirmation gates (process doc 7.3)

Canonical source: Charter Section 6 (Confirmation Cadence). Guides
do not restate; the Charter governs decision-callout, end-of-section,
end-of-session, and anti-fatigue rules.

### 7.4 One topic at a time (process doc 7.4)

Canonical source: Charter Section 4.1 (One question at a time).
Guides do not restate. The gate pattern (Section 5.4 above) remains
the only permitted way to group decisions for single approval and
is described in the guide that uses it.

### 7.5 One deliverable per conversation (process doc 7.5)

Phase-specific. Canonical source: `How to Use This Guide` Output
statement per guide. Every conversation produces exactly one committed
artifact. Guides that produce multiple artifacts (e.g., YAML Generation
produces YAML + MANUAL-CONFIG + EXCEPTIONS) treat them as one atomic
deliverable with three parts, produced together, and state this in
`How to Conduct This Phase`.

### 7.6 Scope-change protocol (process doc Section 10)

Canonical source: Charter Section 8 (Scope-Change Protocol). Guides
do not restate the protocol itself. A guide may add a phase-specific
trigger list in `How to Conduct This Phase` if there are phase-unique
triggers beyond those the Charter covers (e.g., "missing entity
discovered during this phase" for the Entity PRD guide). Cross-reference
to `guide-carry-forward-updates.md` belongs in the See-also block at
the top of the guide.

### 7.7 Identifier discipline (process doc Section 5)

Canonical source: Charter Section 10 (Identifier Discipline). Guides
do not restate the generic discipline. A guide MUST state the
phase-specific identifier format used in its deliverable
(three-level or four-level per sub-domain rules) in `How to Conduct
This Phase` or in the section where identifiers are assigned.

### 7.8 Business-language rule (process doc PRD Content Rules)

Phase-specific. Product names (EspoCRM, WordPress, Constant Contact,
etc.) are forbidden in every deliverable **except** the CRM Evaluation
Report produced in Phase 10. Every guide for Phases 1–9 must contain
an explicit "no product names" rule in `How to Conduct This Phase`;
the Phase 10 guide must contain the explicit carve-out.

### 7.9 Transcript requirement

Canonical source: Charter Section 9 (Transcript Capture) for format
and content. Interview deliverables include a transcript section;
synthesis/generation deliverables do not (they produce the artifact
directly from the inputs, and the "transcript" is effectively the
decisions made by applying the guide's rules, captured in a Decisions
Made section of the deliverable). Guides state which side of this
divide they are on in `How to Use This Guide`.

---

## 8. Output-document contract

Every guide must state, in the `## How to Use This Guide` section,
the exact values of the following variables:

| Variable | Example |
|---|---|
| Archetype | interview / guide |
| Governed phase | Phase 1 — Master PRD |
| Deliverable name | Master PRD |
| Deliverable format | `.docx` |
| Deliverable path | `PRDs/{Implementation}-Master-PRD.docx` |
| Cardinality | one per implementation / one per domain / one per process / one per entity / one per service |

When a guide produces more than one artifact in the same conversation
(YAML Generation), list every artifact in a table. Do not bury
secondary artifacts in prose.

---

## 9. Style

- **Tense and voice.** Imperative for instructions to Claude.
  Present tense for descriptive statements. No future tense ("Claude
  will...") — it reads as a prediction instead of an instruction.
- **Actor naming.** The two actors are "Claude" and "the
  administrator". Do not introduce synonyms ("the AI", "the assistant",
  "the user", "the client") except where the difference matters
  (client-facing sessions distinguish the administrator from the
  client).
- **Line width.** Wrap body prose at roughly 70 characters so the file
  is readable in a terminal. Tables and code blocks may exceed this.
- **Lists.** Prefer numbered lists only when order matters. Otherwise
  use bullets.
- **Code fences.** Use triple-backtick fences with a language tag
  (`yaml`, `markdown`, `text`) for anything the AI or administrator
  will copy verbatim.
- **Cross-references.** Refer to other guides by filename in
  backticks (`guide-carry-forward-updates.md`). Refer to the process
  doc by section number (`Section 10.2`) rather than by title — titles
  drift, section numbers are stable within a version.

---

## 10. Versioning

- Every guide has its own version line in the front-matter, which
  moves independently of the process doc version.
- A minor bump (1.3 → 1.4) reflects a substantive change to
  instructions: new step, new rule, rewritten section, new inputs.
- A major bump (1.x → 2.0) reflects archetype change, phase
  reassignment, or deliverable-schema change.
- Cosmetic edits (typos, formatting) may be committed without a
  version bump but must still update `Last Updated`.
- Every version bump gets a Changelog entry.

---

## 11. Review checklist

Use this before committing a new or revised guide. A guide that fails
any line on this list is not ready.

- [ ] Front-matter block is complete and matches the Section 4 template exactly.
- [ ] Archetype prefix in the filename (`interview-` or `guide-`) matches the body structure.
- [ ] Required section skeleton from Section 5 is present in the correct order.
- [ ] `How to Use This Guide` states archetype, phase, deliverable, format, path, cardinality, session length, inputs.
- [ ] `How to Use This Guide` names the Interviewer Charter and Question Library as required prerequisite reading.
- [ ] `What the Deliverable Must Contain` has a table and a completeness standard.
- [ ] `How to Conduct This Phase` has only phase-specific rules; generic interviewer conduct is governed by the Charter and is not restated.
- [ ] `Before the X Begins` echoes the session-start checklist from process doc Section 7.1.
- [ ] Identifier format is stated if the deliverable contains identifiers.
- [ ] Product-name rule is present in `How to Conduct This Phase` (either the ban, or the Phase 10 carve-out).
- [ ] One-deliverable contract is reflected in `How to Use This Guide` Output statement.
- [ ] Cross-reference to `guide-carry-forward-updates.md` is present in the See-also block when the phase can trigger updates to prior documents.
- [ ] Closing section contains completeness check, summary script, document-production instructions, and next-step script.
- [ ] Changelog has an entry for this version.
- [ ] `Last Updated` date reflects the commit date.
- [ ] No references to obsolete paths (check especially for `PRDs/application/` — the correct path is `PRDs/process/`).

---

## 12. Interview guide skeleton (copy to start a new interview guide)

```markdown
# CRM Builder — {Phase N — Deliverable} Interview Guide

**Version:** 1.0
**Last Updated:** MM-DD-YY
**Purpose:** AI interviewer guide for Phase N — {Deliverable}
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**See also:** `guide-carry-forward-updates.md` — used when this interview discovers that a previously-completed document needs to change.

---

## How to Use This Guide

{archetype role statement — "skilled business analyst"}

**Charter and Question Library as prerequisite reading.** Read
`PRDs/process/conduct/charter.md` and
`PRDs/process/conduct/question-library.md` before conducting this
phase. Generic interviewer conduct is governed there and is not
restated in this guide.

**One {unit} per conversation.**

**Session length:** N–M minutes. {Stop rule if any.}

**Input:** {exhaustive list of uploaded documents}.

**Output:** One Word document — the {Deliverable} — committed to
the implementation's repository at `{path}`.

---

## What the {Deliverable} Must Contain

{table of required sections}

{completeness standard}

---

## How to Conduct This Phase

{3–10 imperative rules, phase-specific only; no restatement of
Charter material. Include the no-product-names rule (or the Phase 10
carve-out) and the phase-specific identifier format if applicable.}

---

## Before the Interview Begins

### Context Review

{what Claude reads first}

### State the Context from Prior Work

{confirmation gate}

---

## Interview Structure

### Section Checklist

{table of topics Claude will walk}

---

## Topic 1 — {Name}

{open question, structured follow-up, identifier rules}

## Topic 2 — {Name}

...

## Topic N — Interview Transcript

{transcript requirements}

---

## Closing the Interview

### Completeness Check

### Summary

### Document Production

### State Next Step

---

## Changelog

- **1.0** (MM-DD-YY) — Initial version.
```

---

## 13. Synthesis/generation guide skeleton (copy to start a new guide-*.md)

```markdown
# CRM Builder — {Phase N — Activity} Guide

**Version:** 1.0
**Last Updated:** MM-DD-YY
**Purpose:** AI guide for Phase N — {Activity}
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**See also:** `guide-carry-forward-updates.md` — for post-{activity} updates driven by upstream scope changes.

---

## How to Use This Guide

{archetype role statement — "executor, not interviewer"}

**Charter and Question Library as prerequisite reading.** Read
`PRDs/process/conduct/charter.md` and
`PRDs/process/conduct/question-library.md` before conducting this
phase. Generic conduct is governed there and is not restated in this
guide.

**One {unit} per conversation.**

**Session length:** N–M minutes.

**Input:** {exhaustive list}.

**Output:** {artifact name(s), path(s), format(s)}.

---

## What the {Deliverable} Must Contain

{table of required sections}

{completeness standard}

---

## How to Conduct This Phase

{3–10 imperative rules, phase-specific only; no restatement of
Charter material. Include the no-product-names rule (or the Phase 10
carve-out) and the phase-specific identifier format if applicable.}

---

## Before {Activity} Begins

### Verify Inputs

### State the Plan

---

## Step 1 — {Name}

{inputs, procedure, outputs, stop-and-ask conditions}

## Step 2 — {Name}

...

## Step N — Document Production and Next Steps

### State Next Step

---

## Changelog

- **1.0** (MM-DD-YY) — Initial version.
```

---

## Changelog

- **1.2** (05-24-26 12:31) — Collapsed redundant `Critical Rules` and `Important AI Behaviors` sections in the section skeleton (Section 5.1) into a single `How to Conduct This Phase` section. Rewrote Section 6.3 to require phase-specific rules only; deleted Section 6.6 (Important AI Behaviors) entirely; renumbered 6.7 → 6.6 (Changelog). Reframed Section 7 from "every guide must echo these rules" to "every guide must reference the Charter as canonical source" — six of the nine cross-cutting rules are canonically governed by `PRDs/process/conduct/charter.md` and are no longer restated per guide; two (one-deliverable contract, business-language rule) remain phase-specific and stay in `How to Conduct This Phase`. Added a Charter-and-Question-Library prerequisite-reading bullet to Section 6.1. Updated the Section 11 review checklist accordingly. Updated the skeletons in Sections 12 and 13 to reflect the new shape.
- **1.1** (04-21-26) — Added Section 1.1 (resolution order when the `.docx` process doc conflicts with itself) and Section 1.2 (pilot-validation requirement before a guide is treated as authoritative). Triggered by the `guide-domain-overview.md` v1.0 → v1.1 episode: v1.0 over-tightened Section 3.4's Context Passing line into a hard precondition that contradicted Section 3.5 Rule 5.1 and blocked the CBM Funding Domain Overview session. Root cause was authoring from the `.docx` without spot-checking observed pilot practice. The new Section 1.1 gives authors a resolution protocol; Section 1.2 requires a pilot-validation note in the Changelog of every guide.
- **1.0** (04-20-26) — Initial authoring standards, derived from
  `interview-master-prd.md` v1.2, `interview-process-definition.md`
  v2.6, `guide-domain-reconciliation.md` v1.5,
  `guide-yaml-generation.md` v1.1, and
  `guide-carry-forward-updates.md` v1.1. Codifies the archetype split,
  the required section skeleton for each archetype, the cross-cutting
  rules inherited from `CRM-Builder-Document-Production-Process.docx`
  Sections 5, 7, and 10, and the review checklist for new or revised
  guides.
