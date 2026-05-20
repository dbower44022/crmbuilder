# Governance Entity Schema Design — `conversation` — Kickoff Prompt

**Last Updated:** 05-20-26 22:50
**Purpose:** Seed prompt for a new Claude.ai conversation that designs the `conversation` entity type schema for the governance entity schema-design workstream.
**Position in workstream:** **Second of six** schema-design conversations. Predecessors: workstream-establishing conversation, then `workstream` schema design. Successors: `reference_book`, `work_ticket`, `close_out_payload`, `deposit_event`.
**Workstream master:** `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md`
**Schema spec template:** `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md`

---

## The task

Design the `conversation` entity type schema for V2's storage layer. Drive a structured architectural discussion that produces one deliverable:

**`PRDs/product/crmbuilder-v2/governance-schema-specs/conversation.md`** — the complete schema specification per the template in `governance-entity-schema-spec-guide.md`.

Cadence matches the methodology workstream's schema-design conversations and the user-interface planning conversations: structured architectural discussion driven one decision at a time, building toward the specification section by section.

At conversation close: decisions written via direct API as decision records; any deferred items written as planning items; one session record written by Doug through the V2 desktop New Session dialog per the session-record-at-close pattern.

---

## Context — why conversation second

`conversation` references `workstream` (every conversation belongs to a workstream). Designing it second means `workstream` is already settled and the relationship can be designed against a known parent schema rather than a placeholder.

The conversation entity is also the most lifecycle-rich of the six new governance entities. Per DEC-119, the working state set is `planned`, `kickoff-drafted`, `ready`, `in-flight`, `complete`, `cancelled`, `superseded`. This conversation refines that working set into a final lifecycle table and sets the precedent for how rich a lifecycle the spec guide's "prefer-simple" posture tolerates when the entity legitimately needs the states.

---

## What `conversation` needs to host

A conversation entity represents one unit of conversational work through its full lifecycle, distinct from the after-the-fact session record. Real examples from the project at the time of this kickoff (each currently exists implicitly in kickoff prompts and session records, with no first-class entity record):

- Today's workstream-establishing conversation (in-flight at this kickoff's authoring time; will be complete by the time this kickoff is used).
- Tomorrow's `workstream` schema-design conversation.
- The conversation that opens this kickoff (planned at this kickoff's authoring time).
- A historical example: SES-011 (methodology entity schema-design workstream-establishing conversation, completed 05-11-26).
- A future example: the user-interface version 0.7 styling conversation (planned but no kickoff yet authored, in some kind of pre-planned state).

Conversations have distinct phases:

- **Planned.** Identified as something to do but no kickoff drafted yet.
- **Kickoff drafted.** Kickoff prompt written but not yet ready to open (perhaps awaiting dependencies).
- **Ready.** Kickoff complete; can be opened.
- **In-flight.** Currently open in Claude.ai; in dialogue with Doug.
- **Complete.** Closed with a session record and any artifacts committed.
- **Cancelled.** Decided not to run after all.
- **Superseded.** Replaced by a different conversation (e.g., kickoff scope changed enough to warrant a new kickoff).

So the `conversation` schema needs to host:

- Identifier and a human-readable title
- A description (purpose, intended deliverable)
- A workstream foreign key
- A lifecycle that captures all the phases above
- Timestamps for state transitions
- Links to its kickoff prompt (a work ticket, designed in the next-next conversation), its session record (after completion), and its close-out payload (after completion)
- Possibly: a `next_conversation` link or `predecessor_conversation` reference for chained sequences

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template.
4. `PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md` — completed workstream specification (settled referent for this conversation's relationships).
5. The six foundation decisions DEC-117 through DEC-122, with focus on DEC-119 (conversation as first-class). Available in `PRDs/product/crmbuilder-v2/db-export/decisions.json`.
6. The session record for the workstream-establishing conversation and the `workstream` schema-design conversation, in `db-export/sessions.json`, for context on conventions already established.
7. `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — current reference vocabulary.
8. `PRDs/product/crmbuilder-v2/methodology-schema-specs/` — methodology specifications as exemplars.

---

## Architectural questions likely to arise

The conversation will surface these in some order. The list is illustrative, not exhaustive — let the conversation flow.

- **Identifier prefix.** Working assumption: `CONV`. Alternatives: `CONVO`, `CHAT`, `CV`. Check against the existing prefix list (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRM, ENG, plus `workstream`'s chosen prefix). Decision.
- **Field inventory.** Working minimum: `conversation_identifier`, `conversation_title`, `conversation_description`, `conversation_status`, `workstream_id`, timestamps. What else? Intended deliverable description? Estimated duration? Priority?
- **Status lifecycle.** Working set per DEC-119: `planned`, `kickoff_drafted`, `ready`, `in_flight`, `complete`, `cancelled`, `superseded`. Are all seven needed in user-interface version 0 — could `kickoff_drafted` and `ready` collapse to one state? What transitions are valid? Default starter status? Is the lifecycle linear, or can it branch (e.g., `in_flight` → `cancelled`)?
- **Session record relationship.** A conversation produces zero or one session records. Direct foreign key on session from `session.conversation_id`, or references-table edge, or computed-via-conversation-reference text matching? Per existing append-only sessions table semantics, modifying session shape is delicate. Working assumption: add a `conversation_id` foreign key to session in the build (back-fillable for historical records), keep direct relationship simple. Discuss.
- **Kickoff prompt relationship.** A conversation has one kickoff prompt (a work ticket, designed in the work-ticket conversation). Reference via foreign key (one-to-one), via references-table edge, or via implicit name-matching against the work-ticket file? Decision.
- **Chained conversation sequences.** Some conversations have explicit predecessors and successors in the same workstream. The kickoff prompt for the `conversation` entity itself names a predecessor and successor. Model as references-table edges (`conversation_succeeds_conversation`), as a `predecessor_conversation_id` foreign key, or as implicit (look at the workstream's conversations sorted by `planned_at`)? Decision.
- **Cross-workstream conversation links.** Sometimes a conversation in one workstream references work done in another. Model how?
- **UI deviations.** A conversation panel needs to show lifecycle prominently (the panel is operational — a consultant asks "what's queued up next" by filtering on status). May warrant a deviation from the default master-pane column layout to show status first.
- **Acceptance criteria.** Translate the schema into testable statements per spec guide section 3.7.

---

## Working style

Per Doug's preferences:

- Discuss one architectural decision at a time. Wait for explicit approval before moving to the next.
- Plain text discussion. Bold section headings acceptable. Avoid bullet-point overload.
- Terse approvals ("yes", "confirm", "a", "1 good") are sufficient — do not re-summarize.
- Propose document structures and outlines; the user approves before drafting begins.
- Once architectural questions are settled and outline is approved, execute the specification drafting end-to-end without per-step confirmation. Full review at the end.

For repo work: sparse checkout (`git clone --filter=blob:none --sparse` then `git sparse-checkout set --skip-checks CLAUDE.md PRDs/ crmbuilder-v2/`). Set git identity before first commit (`git config user.email "doug@dougbower.com"`, `git config user.name "Doug"`). Always `git pull --rebase origin main` before pushing.

---

## Pre-flight checks

Before the first architectural question:

1. `curl -sf http://127.0.0.1:8765/health` — API up.
2. `uv run pytest tests/crmbuilder_v2/ -v` — test suite green.
3. `git pull --rebase origin main` — clone current.
4. Read items 1–8 in "Read this first."

---

## Governance — at conversation close

Per DEC-013, one Claude.ai conversation produces one session record. This conversation's session record is written **at the actual close of the conversation, not during drafting**.

Doug writes the session record through the V2 desktop New Session dialog. The record captures:

- `identifier`: next available session identifier at conversation close.
- `conversation_reference`: descriptive text identifying the conversation by its deliverable. Example template: `"Claude.ai schema-design conversation that produced governance-schema-specs/conversation.md. No transcript preserved per DEC-025."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of architectural questions discussed.
- `artifacts_produced`: `governance-schema-specs/conversation.md`, plus decision records authored, plus planning items authored.
- `in_flight_at_end`: `"Next workstream conversation: reference book entity schema design. Kickoff at schema-design-kickoff-reference-book.md."`

---

## What this conversation does NOT do

- Build any code. The build happens later — when the build-planning conversation produces slice prompts.
- Modify V2's storage architecture beyond what the new entity type additively requires.
- Modify the existing `session` table's shape. The proposed `session.conversation_id` foreign key is a design *target* for the build-planning conversation; this conversation specifies the relationship but does not implement the migration.
- Plan beyond `conversation`. The next four schemas have their own conversations.
- Design `reference_book`, `work_ticket`, `close_out_payload`, or `deposit_event` inline because they reference `conversation`. They have their own kickoffs.
- Retroactively populate conversation records. Backfill is deferred to a planning item authored by the build-planning conversation.

---

End of kickoff prompt.
