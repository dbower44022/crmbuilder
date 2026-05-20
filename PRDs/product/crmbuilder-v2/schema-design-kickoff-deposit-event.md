# Governance Entity Schema Design — `deposit_event` — Kickoff Prompt

**Last Updated:** 05-20-26 23:10
**Purpose:** Seed prompt for a new Claude.ai conversation that designs the `deposit_event` entity type schema for the governance entity schema-design workstream.
**Position in workstream:** **Sixth and last of six** schema-design conversations. Predecessors: workstream-establishing conversation, `workstream`, `conversation`, `reference_book`, `work_ticket`, `close_out_payload` schema designs. Successor: build-planning conversation (consumes all six schema specifications and produces the integrating Product Requirements Document, implementation plan, and per-slice execution prompts).
**Workstream master:** `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md`
**Schema spec template:** `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md`

---

## The task

Design the `deposit_event` entity type schema for V2's storage layer. Drive a structured architectural discussion that produces one deliverable:

**`PRDs/product/crmbuilder-v2/governance-schema-specs/deposit_event.md`** — the complete schema specification per the template in `governance-entity-schema-spec-guide.md`.

Cadence matches the methodology workstream's schema-design conversations and the user-interface planning conversations: structured architectural discussion driven one decision at a time, building toward the specification section by section.

At conversation close: decisions written via direct API as decision records; any deferred items written as planning items; one session record written by Doug through the V2 desktop New Session dialog per the session-record-at-close pattern. **This conversation also produces one additional artifact**: the kickoff prompt for the build-planning conversation that closes the workstream — see "Additional deliverable at close" below.

---

## Context — why deposit event last

The deposit event is the second of the two entities in the deposit bucket family (the close-out payload is the first; together they implement DEC-118's payload/event split). Designing deposit event last lets it reference close-out payload as a settled parent, and lets the design surface the cross-entity lifecycle question (a deposit event's existence implies a close-out payload reached the `applied` status; the close-out payload specification just produced may have anticipated this, or may need a small revision).

Deposit event is also the most relationally complex of the six new entity types. It references its parent close-out payload, AND it references the records the apply wrote — which can span multiple existing entity types (decisions, planning items, references, risks, topics, etc., per the kinds of records a payload typically contains). How those back-references are modeled is the most consequential design question of this conversation.

---

## What `deposit_event` needs to host

A deposit event is the record of a close-out payload being applied to the governance database. It captures what happened at apply time: when it ran, whether it succeeded, what records it wrote, and any errors encountered.

Real example for grounding the conversation (no actual deposit event records exist yet — this entity is being designed):

A deposit event for `ses_046.json` would record that the payload was applied on 05-20-26 at 21:51 (matching SES-046's `created_at`), succeeded with no errors, and wrote DEC-117 through DEC-122 (six decision records). The apply also created SES-046 itself (one session record). If the apply had instead failed midway, the deposit event would record the records written before the failure point plus the error.

Lifecycle:

1. **Created** at the moment apply begins (status `running`).
2. **Updated** as apply progresses, capturing records written.
3. **Finalized** with `success` or `failure` status.
4. **Append-only thereafter.** A deposit event is a fact about what happened; modifying it would erase history.

So the `deposit_event` schema needs to host:

- Identifier
- Foreign key to the close-out payload it applied (one-to-one with that payload, though re-apply may permit multiple events per payload — see architectural questions)
- A status (`running`, `success`, `failure`, possibly `aborted`)
- Outcome metadata: total records written, records-by-kind summary, error messages on failure
- Back-references to the records the apply wrote (the principal design question)
- Lifecycle timestamps (`started_at`, `completed_at`)
- Apply context: who ran apply (the API session that invoked it), from what environment

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template.
4. All five completed predecessor specifications: `governance-schema-specs/workstream.md`, `conversation.md`, `reference_book.md`, `work_ticket.md`, `close_out_payload.md`.
5. The six foundation decisions, especially DEC-117 (three families) and DEC-118 (payload/event split). Available in `PRDs/product/crmbuilder-v2/db-export/decisions.json`.
6. The session records for the workstream-establishing and the five prior schema-design conversations, in `db-export/sessions.json`.
7. The canonical apply prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md` — shows what apply does and what outcomes it can produce.
8. `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — the references-table vocabulary; if deposit event uses references-table edges for back-references, this is where the new relationship kinds get declared.

---

## Architectural questions likely to arise

The conversation will surface these in some order. The list is illustrative, not exhaustive — let the conversation flow.

- **Identifier prefix.** Working assumption: `DEP`. Alternatives: `DEPOS`, `DEPT` (visual collision with department-like reads), `EVT`, `APPLY`. Decision.
- **Field inventory.** Working minimum: `deposit_event_identifier`, `close_out_payload_id`, `deposit_event_status`, `total_records_written`, `records_summary` (JSON or text), `error_text`, `started_at`, `completed_at`. What else?
- **Back-references to records written.** The principal question. Four options to consider:
  - **References-table edges.** Each record the apply wrote becomes a `reference` row with `source_type='deposit_event'`, `source_id=DEP-NNN`, `target_type=...`, `target_id=...`, `relationship_kind='deposit_event_wrote_record'` or similar. Requires one new vocabulary entry, possibly per-target-type variants. Generalizes naturally; queries against references work.
  - **JSON list on the deposit event row.** A `records_written` JSON column holds an array of `{target_type, target_id}` pairs. One column, no extra rows; less queryable.
  - **Dedicated back-reference table.** A `deposit_event_record` table with `deposit_event_id`, `target_type`, `target_id` columns. More normalized than JSON, less universal than references-table. Introduces a new table just for this.
  - **Records on the target side.** Each record written by apply gets a `written_by_deposit_event_id` column added to its own table. Pulls the back-reference into the target tables; ergonomic for "which deposit wrote this decision?" queries but requires migrations on all target tables.
  - Decision. The references-table approach is the lightest extension and most aligned with V2's existing relationship-vocabulary discipline; it is the working assumption.
- **Status lifecycle.** Working set: `running`, `success`, `failure`, `aborted`. Are all four needed? Default starter status? What transitions are valid?
- **Re-apply semantics.** If a payload's apply fails, can it be re-applied? If yes, are there multiple deposit events per payload, or is the deposit event itself reset? Working assumption: append-only — each apply attempt creates a new deposit event; the close-out payload's `status` reflects the cumulative outcome (`applied` once the most recent deposit event is `success`). Discuss.
- **Append-only semantics.** Strong argument for full append-only on this entity. Deposit events should not be soft-deleted (they record facts). They should not be edited after `completed_at` (the apply happened the way it happened). Working assumption: full append-only — no PUT, no PATCH, no DELETE endpoints. Confirm.
- **Error capture.** What does `error_text` look like? Full Python traceback, structured error info, single-line summary? Apply currently logs richly to stdout; the database record should capture enough to diagnose. Working assumption: structured JSON `error_info` with `kind`, `message`, `step`, and optional `traceback` fields. Discuss.
- **Records summary structure.** `records_summary` should answer "how many of each kind did this apply write?" Working assumption: JSON object like `{"decisions": 6, "sessions": 1, "planning_items": 1}`. Discuss.
- **Apply context.** Who ran apply, from where, with what apply-script version? Useful for debugging. Working assumption: `apply_context` JSON with `apply_script_version`, `invocation`, `runner` fields. Discuss.
- **UI deviations.** Deposit events are read-only by nature; the panel may have no create/edit/delete dialogs and serve as a read-only audit log. Discuss.
- **Acceptance criteria.** Translate the schema into testable statements per spec guide section 3.7.

---

## Additional deliverable at close

Because this is the last schema-design conversation in the workstream, its close also produces **one additional artifact**: the kickoff prompt for the build-planning conversation that integrates all six schema specifications.

The build-planning kickoff prompt:

- Lives at `PRDs/product/crmbuilder-v2/governance-schema-build-planning-kickoff.md`.
- Names the six schema specifications as inputs and a Product Requirements Document, implementation plan, and per-slice build prompts as outputs.
- Lists the cross-spec consistency check (per the spec guide's section 7.2) as the build-planning conversation's first task.
- Names the target user-interface version as open — the build-planning conversation sets it in coordination with the active version sequence at that time.
- Names the retroactive backfill planning item (already authored by the workstream-establishing conversation) as a build-planning concern: the build-planning conversation refines and elaborates the backfill plan, including which prior workstreams and conversations to populate and in what order.

The build-planning kickoff is drafted at the end of this conversation, after the deposit event specification is complete, so it can reference the just-finalized specification as well as the prior five.

---

## Read this first

(Reproduced from earlier for completeness — actual reads are listed above.)

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
- `conversation_reference`: descriptive text identifying the conversation by its deliverable. Example template: `"Claude.ai schema-design conversation that produced governance-schema-specs/deposit_event.md, and the build-planning conversation's kickoff prompt. No transcript preserved per DEC-025."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of architectural questions discussed.
- `artifacts_produced`: `governance-schema-specs/deposit_event.md`, the build-planning conversation's kickoff prompt at `governance-schema-build-planning-kickoff.md`, plus decision records authored, plus planning items authored.
- `in_flight_at_end`: `"Next workstream conversation: build-planning. Kickoff at governance-schema-build-planning-kickoff.md. This conversation closes the schema-design portion of the governance entity schema-design workstream."`

---

## What this conversation does NOT do

- Build any code. The build happens later — when the build-planning conversation produces slice prompts.
- Modify V2's storage architecture beyond what the new entity type additively requires.
- Modify the existing apply path (`apply_close_out.py` or the Claude Code apply prompts). The apply path's evolution to write deposit event records as it runs is a build-planning conversation concern.
- Design the build-planning conversation's deliverables (Product Requirements Document, implementation plan, slice prompts). This conversation produces only the build-planning conversation's *kickoff prompt*.
- Re-litigate `close_out_payload`'s schema. Deposit event references close-out payload as a settled parent; if a small revision to close-out payload's specification is required to support deposit event cleanly, that revision is the close-out payload conversation's responsibility (reopen at the close-out payload spec, do not amend inline here).
- Retroactively populate deposit event records for historical applies. Backfill is deferred to a planning item authored by the build-planning conversation.

---

End of kickoff prompt.
