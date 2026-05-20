# Governance Entity Schema Design — `close_out_payload` — Kickoff Prompt

**Last Updated:** 05-20-26 23:05
**Purpose:** Seed prompt for a new Claude.ai conversation that designs the `close_out_payload` entity type schema for the governance entity schema-design workstream.
**Position in workstream:** **Fifth of six** schema-design conversations. Predecessors: workstream-establishing conversation, `workstream`, `conversation`, `reference_book`, `work_ticket` schema designs. Successor: `deposit_event`.
**Workstream master:** `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md`
**Schema spec template:** `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md`

---

## The task

Design the `close_out_payload` entity type schema for V2's storage layer. Drive a structured architectural discussion that produces one deliverable:

**`PRDs/product/crmbuilder-v2/governance-schema-specs/close_out_payload.md`** — the complete schema specification per the template in `governance-entity-schema-spec-guide.md`.

Cadence matches the methodology workstream's schema-design conversations and the user-interface planning conversations: structured architectural discussion driven one decision at a time, building toward the specification section by section.

At conversation close: decisions written via direct API as decision records; any deferred items written as planning items; one session record written by Doug through the V2 desktop New Session dialog per the session-record-at-close pattern.

---

## Context — why close-out payload fifth

The close-out payload is one of two entities in the deposit bucket family established by DEC-117 and split by DEC-118. The other (deposit event) is designed in the sixth and final per-entity conversation. Splitting the design across two conversations matches the lifecycles' divergence: a close-out payload is produced once at a conversation's close; a deposit event is created at apply-time and can succeed or fail. They reference each other, but their schemas are meaningfully different.

Designing close-out payload fifth — after `conversation` — lets it cleanly express its "produced by one conversation" relationship against a settled parent schema. Designing it before `deposit_event` lets deposit event reference close-out payload as a settled parent.

The principal design question is **how the structured payload is represented in the database**. Today, close-out payloads live as JSON files under `PRDs/product/crmbuilder-v2/close-out-payloads/`. Bringing them under database governance requires a representation that can either store the structured content as a JSON column, store it as text with a parser, or reference the underlying file with metadata fields capturing what matters for queries.

---

## What `close_out_payload` needs to host

A close-out payload is the structured payload produced at a conversation's close, intended for application to the governance database. Real examples at the time of this kickoff:

- `close-out-payloads/ses_046.json` (today's predecessor scoping conversation's payload — produced earlier today).
- Historical examples: `ses_014.json`, `ses_015.json`, `ses_025.json` and others under the same directory.

Each payload is currently a JSON file with structured fields: a `metadata` block (session identifier, conversation reference, in-flight-at-end text), one or more sections of records to write (decisions, planning items, references, risks, topics), and any updates to existing records (e.g., supersession edits).

The payload's lifecycle:

1. **Produced** at the close of a conversation. The file is written; the conversation closes; the payload sits awaiting apply.
2. **Applied** via the standard apply script (`apply_close_out.py`) or the equivalent Claude Code prompt at `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`. Apply walks the payload and writes records via the V2 API.
3. **Outcomes recorded** as a deposit event (the next conversation's entity). The deposit event references back to the payload.

So the `close_out_payload` schema needs to host:

- Identifier and a human-readable title (often derived from the conversation it closed out)
- Foreign key to the conversation that produced it (one-to-one)
- The payload content itself — JSON column, text column with parser, or file-path-plus-metadata
- A status (drafted, ready, applied, superseded) — or append-only with last-update timestamps
- A schema-version field on the payload itself, in case payload structure evolves
- Lifecycle timestamps (`produced_at`, `applied_at`)
- Relationship-readiness for `deposit_event` to reference it back

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template.
4. `PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md`, `conversation.md`, `reference_book.md`, `work_ticket.md` — completed predecessor specifications.
5. The six foundation decisions, especially DEC-117 (three families) and DEC-118 (payload/event split). Available in `PRDs/product/crmbuilder-v2/db-export/decisions.json`.
6. The session records for the workstream-establishing and the four prior schema-design conversations, in `db-export/sessions.json`.
7. Several actual close-out payload files under `PRDs/product/crmbuilder-v2/close-out-payloads/` — at minimum `ses_046.json` (most recent), `ses_025.json` (the envelope-discipline canonical example), and one earlier file for comparison.
8. The canonical apply prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md` — shows what apply consumes from a payload and how the envelope is unwrapped.

---

## Architectural questions likely to arise

The conversation will surface these in some order. The list is illustrative, not exhaustive — let the conversation flow.

- **Identifier prefix.** Working assumption: `COP`. Alternatives: `CLOSE`, `CLOUT`, `PAY`, `PYLD`. `COP` is short but may be visually confused with `CRM`. Decision.
- **Field inventory.** Working minimum: `close_out_payload_identifier`, `close_out_payload_title`, `close_out_payload_status`, `conversation_id`, `payload_content` (or `payload_file_path`), `payload_schema_version`, timestamps. What else? Producer (Claude.ai session identifier matches if needed)? Summary of records written?
- **Payload content representation.** The principal question. Four options to consider:
  - **JSON column.** Store the structured payload directly as a JSON column. Queryable via JSON path operators. Largest column data; biggest convenience.
  - **Text column with on-demand parse.** Store as a text blob; parse when consumed. Slightly less query-friendly.
  - **File-path with metadata fields.** Store path; pull out queryable metadata (record counts by kind, total bytes, etc.) into columnar fields. The file remains the source of truth.
  - **Hybrid.** File path plus an extracted JSON-column snapshot for query convenience; the file is canonical, the column is derived.
  - Decision. The choice has consequences for how the build-planning conversation's apply path interacts with the payload entity (e.g., does apply read from the database column, or from the file?).
- **Status lifecycle.** Working set: `drafted`, `ready`, `applied`, `superseded`. Are all needed? Is the entity append-only after `applied` is reached (so updates to applied payloads are forbidden)?
- **Append-only vs. soft-delete posture.** Once a payload has been applied (and a deposit event records the apply), modifying the payload would erase the record of what was actually applied. Strong argument for append-only after apply. But before apply, the payload may legitimately need updates (correcting a typo). Working assumption: mutable in `drafted` and `ready` states; immutable in `applied` and `superseded`. Discuss.
- **Schema version field.** Payload structure may evolve. A `payload_schema_version` field on the record marks which payload-schema version the content conforms to. Working assumption: yes, include. Confirm.
- **Relationship to deposit event.** A close-out payload may have zero or one deposit event (zero if not yet applied; more than one only if re-apply is supported, which the next conversation may permit). The relationship lives on the deposit event side; close-out payload schema does not carry a `deposit_event_id` foreign key.
- **Engagement scoping.** Close-out payloads are per-engagement. Per V2's per-engagement isolation, automatic.
- **UI deviations.** Close-out payload detail panes may benefit from showing the JSON content prominently with structured rendering of records-to-be-written. The default detail pane is plain.
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
- `conversation_reference`: descriptive text identifying the conversation by its deliverable. Example template: `"Claude.ai schema-design conversation that produced governance-schema-specs/close_out_payload.md. No transcript preserved per DEC-025."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of architectural questions discussed.
- `artifacts_produced`: `governance-schema-specs/close_out_payload.md`, plus decision records authored, plus planning items authored.
- `in_flight_at_end`: `"Next workstream conversation: deposit event entity schema design. Kickoff at schema-design-kickoff-deposit-event.md."`

---

## What this conversation does NOT do

- Build any code. The build happens later — when the build-planning conversation produces slice prompts.
- Modify V2's storage architecture beyond what the new entity type additively requires.
- Modify the existing apply path (`apply_close_out.py` or the Claude Code apply prompts). The apply path's evolution to consume payloads from the database column versus the file is a build-planning conversation concern.
- Plan beyond `close_out_payload`. Deposit event has its own conversation next.
- Design `deposit_event` inline. The conversation may *name* the deposit event entity in its cross-references but does not design it.
- Retroactively populate close-out payload records for historical files. Backfill is deferred to a planning item authored by the build-planning conversation.

---

End of kickoff prompt.
