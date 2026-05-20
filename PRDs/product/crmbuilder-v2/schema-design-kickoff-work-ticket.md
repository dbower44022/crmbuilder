# Governance Entity Schema Design — `work_ticket` — Kickoff Prompt

**Last Updated:** 05-20-26 23:00
**Purpose:** Seed prompt for a new Claude.ai conversation that designs the `work_ticket` entity type schema for the governance entity schema-design workstream.
**Position in workstream:** **Fourth of six** schema-design conversations. Predecessors: workstream-establishing conversation, `workstream`, `conversation`, `reference_book` schema designs. Successors: `close_out_payload`, `deposit_event`.
**Workstream master:** `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md`
**Schema spec template:** `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md`

---

## The task

Design the `work_ticket` entity type schema for V2's storage layer. Drive a structured architectural discussion that produces one deliverable:

**`PRDs/product/crmbuilder-v2/governance-schema-specs/work_ticket.md`** — the complete schema specification per the template in `governance-entity-schema-spec-guide.md`.

Cadence matches the methodology workstream's schema-design conversations and the user-interface planning conversations: structured architectural discussion driven one decision at a time, building toward the specification section by section.

At conversation close: decisions written via direct API as decision records; any deferred items written as planning items; one session record written by Doug through the V2 desktop New Session dialog per the session-record-at-close pattern.

---

## Context — why work ticket fourth

`work_ticket` is the single-use seed document family established by DEC-117. Designing it after `reference_book` lets `work_ticket` define itself partly in contrast — what makes a workflow file a work ticket rather than a reference book is the single-use semantics that `reference_book`'s schema has established by negation.

The principal design question is **what distinguishes work ticket from reference book at the schema level**, given that both are workflow files with similar surface fields (title, description, file path, status). The distinction is in lifecycle and reference pattern: a work ticket is produced for one specific conversation, consumed by that conversation, and not subsequently referenced as a source of truth.

---

## What `work_ticket` needs to host

A work ticket is a single-use seed document produced for one specific conversation. Real examples at the time of this kickoff:

- Kickoff prompts for one-shot conversations: `governance-entity-schema-workstream-establishing-kickoff.md` (the kickoff that opened the conversation producing this very file's parent set), the per-entity kickoff prompts in this workstream (`schema-design-kickoff-workstream.md`, etc.), `methodology-schemas-cbm-paper-test-kickoff.md`.
- The forthcoming kickoff for the build-planning conversation that closes this workstream.
- The kickoff prompts for the methodology workstream's schema-design conversations: `schema-design-kickoff-domain.md`, `schema-design-kickoff-entity.md`, `schema-design-kickoff-process.md`, `schema-design-kickoff-crm_candidate.md`.
- The user-interface version planning prompts (`ui-v0.4-planning-prompt.md` etc.) — although note these are sometimes referenced after the fact when a successor planning conversation runs, which raises the boundary question with reference book.
- Claude Code apply prompts (`prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md`, etc.) — these are single-use for one slice's execution.

The boundary case to think through during the conversation: the methodology workstream's master plan was itself produced by a planning conversation (SES-011) whose kickoff was `ui-v0.4-planning-prompt.md`. That kickoff was *redirected* by the conversation (workstream plan supersedes the kickoff), so the kickoff was then referenced *forward* — historically — by subsequent documents discussing what happened. Is that retroactive forward-referencing enough to make it a reference book? Or does it remain a work ticket because it was only "consumed" once, with the retroactive citations being archival rather than authoritative? The conversation will need to resolve this principle.

So the `work_ticket` schema needs to host:

- Identifier and a human-readable title
- A description (what conversation this work ticket is for, what it intends to elicit)
- A kind classification (kickoff prompt, apply prompt, ad-hoc prompt, other)
- A file path (where the canonical file lives in the repo)
- A foreign key to the conversation it produced for (one-to-one with that conversation)
- A status (drafted, ready, consumed, superseded, cancelled) — for lifecycle through pre-conversation states
- Relationship-readiness for `conversation` to reference back to it as its kickoff

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template.
4. `PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md`, `conversation.md`, `reference_book.md` — completed predecessor specifications.
5. The six foundation decisions, especially DEC-117 (three families). Available in `PRDs/product/crmbuilder-v2/db-export/decisions.json`.
6. The session records for the workstream-establishing and the three prior schema-design conversations, in `db-export/sessions.json`.
7. A representative set of actual work ticket files: this kickoff itself; `schema-design-kickoff-domain.md` as a methodology-workstream exemplar; `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md` as an apply-prompt exemplar.
8. The conduct framework documents at `PRDs/process/conduct/` — these are *reference books* (long-lived, cited by many conversations) and serve as the contrast class for understanding work ticket boundaries.

---

## Architectural questions likely to arise

The conversation will surface these in some order. The list is illustrative, not exhaustive — let the conversation flow.

- **Identifier prefix.** Working assumption: `WT`. Alternatives: `WKT`, `TIX`, `TKT`. `WT` is short but distinctive. Decision.
- **Field inventory.** Working minimum: `work_ticket_identifier`, `work_ticket_title`, `work_ticket_description`, `work_ticket_kind`, `work_ticket_file_path`, `work_ticket_status`, `conversation_id`, timestamps. What else? Author? Target deliverable description?
- **Kind classification.** Closed enum (kickoff prompt, apply prompt, ad-hoc prompt, other) or open string? Likely closed enum following the methodology workstream's pattern.
- **The boundary with reference book.** When is a work ticket revisited often enough that it should have been a reference book? Three approaches:
  - **Bright line by intent.** Work ticket if produced-for-one-conversation; reference book if intended-for-recurring-reference. Authorial intent at creation time settles the classification.
  - **Bright line by lifecycle.** Work ticket if no version after consumption; reference book if it has versions. Versioning is the operational distinction.
  - **Re-categorization.** Allow a work ticket to be re-categorized to a reference book after the fact if it turns out to be referenced repeatedly. Schema would need an evolution path.
  - Decision.
- **Status lifecycle.** Working set: `drafted`, `ready`, `consumed`, `superseded`, `cancelled`. Are all five needed? What transitions are valid?
- **Conversation foreign key direction.** Work ticket points at conversation (`work_ticket.conversation_id`), or conversation points at work ticket (`conversation.work_ticket_id`)? Both directions are foreign-key-able. Working assumption: bidirectional — work ticket carries `conversation_id` (one work ticket per conversation; settled cardinality); conversation may also carry `work_ticket_id` if the conversation specification chose to. Confirm both directions or just one.
- **File path semantics.** Same as reference book — repo-relative string path. Inherit the convention `reference_book` settles, unless deviating.
- **Soft-delete versus append-only versus archive-status.** Work tickets become stale (the conversation they were for has completed). Likely follow `consumed` status rather than archive; the record remains as the historical trace of what kicked off the conversation.
- **Engagement scoping.** Work tickets are per-engagement (the kickoff for a Cleveland Business Mentors conversation is engagement-scoped). Per V2's per-engagement isolation, this is automatic.
- **UI deviations.** Work tickets often need to be browsed by status (`ready` to see what is queued up for opening). A status-first column ordering may suit better than the default identifier-first.
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
- `conversation_reference`: descriptive text identifying the conversation by its deliverable. Example template: `"Claude.ai schema-design conversation that produced governance-schema-specs/work_ticket.md. No transcript preserved per DEC-025."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of architectural questions discussed.
- `artifacts_produced`: `governance-schema-specs/work_ticket.md`, plus decision records authored, plus planning items authored.
- `in_flight_at_end`: `"Next workstream conversation: close-out payload entity schema design. Kickoff at schema-design-kickoff-close-out-payload.md."`

---

## What this conversation does NOT do

- Build any code. The build happens later — when the build-planning conversation produces slice prompts.
- Modify V2's storage architecture beyond what the new entity type additively requires.
- Re-litigate `reference_book`'s versioning model. Work tickets may inherit some conventions, but the versioning model is reference book's responsibility.
- Plan beyond `work_ticket`. The next two schemas have their own conversations.
- Design `close_out_payload` or `deposit_event` inline. Those entities have their own kickoffs.
- Retroactively populate work ticket records for past kickoff prompts. Backfill is deferred to a planning item authored by the build-planning conversation.

---

End of kickoff prompt.
