# Governance Entity Schema Design — `workstream` — Kickoff Prompt

**Last Updated:** 05-20-26 22:45
**Purpose:** Seed prompt for a new Claude.ai conversation that designs the `workstream` entity type schema for the governance entity schema-design workstream.
**Position in workstream:** **First of six** schema-design conversations. Predecessor: workstream-establishing conversation (session identifier assigned at close; nominally SES-047). Successors: `conversation`, `reference_book`, `work_ticket`, `close_out_payload`, `deposit_event`.
**Workstream master:** `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md`
**Schema spec template:** `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md`

---

## The task

Design the `workstream` entity type schema for V2's storage layer. Drive a structured architectural discussion that produces one deliverable:

**`PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md`** — the complete schema specification per the template in `governance-entity-schema-spec-guide.md`. The directory does not yet exist; this conversation creates it.

Cadence matches the methodology workstream's schema-design conversations and the user-interface planning conversations: structured architectural discussion driven one decision at a time, building toward the specification section by section.

At conversation close: decisions written via direct API as decision records; any deferred items written as planning items; one session record written by Doug through the V2 desktop New Session dialog per the session-record-at-close pattern.

---

## Context — why workstream first

`workstream` is the most independent of the six new governance entities. Nothing in the new set references back to it without going through `conversation` first. Designing it first lets every downstream schema treat workstream as a settled referent rather than placeholder.

As the workstream's first schema-design conversation, this conversation also **establishes the cross-spec consistency conventions** the subsequent five schemas will follow. The spec guide (section 6) names the conventions inherited from the methodology workstream (parent-prefix field naming, source-first relationship-kind naming, snake_case statuses, default soft-delete with append-only available) and locks the identifier-prefix collision list. The first specific decision each downstream conversation faces is "does the precedent `workstream` set still fit my entity?" — so `workstream`'s choices carry implicit downstream weight.

This conversation also **resolves the nested-workstream question** that DEC-120 explicitly deferred to "the workstream entity's own schema-design conversation." Whether a workstream can contain a sub-workstream — and if so, how the relationship is modeled — is settled here.

---

## What `workstream` needs to host

A workstream entity is a record of a coherent line of related conversations. Real examples from the project at the time of this kickoff (each currently exists only as documents and naming conventions, with no database record):

- The methodology entity schema-design workstream (SES-011 through SES-015, plus its build-planning conversation, plus the user-interface version 0.4 build itself).
- The user-interface version 0.5 engagement management workstream.
- The user-interface version 0.6 styling workstream.
- The multi-tenancy routing fix workstream.
- The Cleveland Business Mentors paper test workstream.
- The governance entity schema-design workstream (this one).

Typical workstream size: 5–15 conversations over a few days to a few weeks. Some are tightly scheduled (one conversation after another, daily); some run over weeks with gaps.

So the `workstream` schema needs to host:

- Identifier and a human-readable name
- A description (purpose, scope, what the workstream produces)
- A lifecycle that captures whether the workstream is planned, in flight, or complete (per DEC-120)
- Timestamps for those state transitions (planned_at, started_at, completed_at)
- Relationship-readiness for `conversation` to reference it as parent
- Whatever model emerges for nested workstreams (if the conversation chooses to allow them)
- Possibly: target user-interface version, link to the workstream's master plan reference book, link to the build-planning conversation that closes it

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template.
4. The six foundation decisions DEC-117 through DEC-122, with focus on DEC-120 (workstream as first-class) and DEC-122 (independence). Available in `PRDs/product/crmbuilder-v2/db-export/decisions.json`.
5. `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — engagement isolation; workstream records are per-engagement.
6. `PRDs/product/crmbuilder-v2/db-export/sessions.json` — read SES-046 (predecessor scoping conversation) and the workstream-establishing conversation's session record for context.
7. `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — current reference vocabulary; new relationship-kind values declared here are aggregated by the build-planning conversation.
8. The four methodology schema specifications in `PRDs/product/crmbuilder-v2/methodology-schema-specs/` — as exemplars of completed specifications at this level of detail.

---

## Architectural questions likely to arise

The conversation will surface these in some order. The list is illustrative, not exhaustive — let the conversation flow.

- **Identifier prefix.** Working assumption: `WS`. Alternatives: `WST`, `WSTRM`, `WORK`. Check against the existing prefix list in spec guide section 6 (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRM, ENG). Decision.
- **Field inventory.** Working minimum: `workstream_identifier`, `workstream_name`, `workstream_description`, `workstream_status`, timestamps. What else? Target user-interface version? Outcome summary at complete? Link to master plan reference book identifier?
- **Status lifecycle.** Working assumption per DEC-120: `planned` → `in_flight` → `complete`. Are these enough? Is there a `cancelled` or `superseded` state for workstreams that get redirected (the methodology workstream effectively superseded the original user-interface version 0.4 kickoff)? What transitions are valid? Default starter status?
- **Nested workstreams.** Can a workstream contain a sub-workstream? If yes, mechanism — self-referential foreign key (hierarchy), or references-table edge? If no, document the rationale (e.g., "treat nested work as a related-workstream cross-reference rather than parent-child"). Decision.
- **Workstream-to-conversation relationship.** Direct foreign key from `conversation.workstream_id` (one-to-many, settled cardinality), or references-table edge (more flexible). Working assumption: direct foreign key — `conversation` schema in the next conversation will follow up. Confirm.
- **Workstream completeness criteria.** What makes a workstream "complete"? All conversations complete? Or operator declares it complete regardless? The spec's lifecycle table answers this.
- **Master plan linkage.** Does workstream carry a foreign key to its master plan's reference book record (e.g., `workstream_master_plan_reference_book_id`), or is that relationship modeled as a references-table edge that can be added/removed/changed over time? Working assumption: references-table edge, since some workstreams may not have a written master plan (smaller ones).
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

- `identifier`: next available session identifier at conversation close (compute via `client.list_sessions()` or check `db-export/sessions.json`).
- `conversation_reference`: descriptive text identifying the conversation by its deliverable. Example template: `"Claude.ai schema-design conversation that produced governance-schema-specs/workstream.md. No transcript preserved per DEC-025."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of architectural questions discussed.
- `artifacts_produced`: `governance-schema-specs/workstream.md`, plus decision records authored, plus planning items authored.
- `in_flight_at_end`: `"Next workstream conversation: conversation entity schema design. Kickoff at schema-design-kickoff-conversation.md."`

---

## What this conversation does NOT do

- Build any code. The build happens later — first when all six schema specifications feed the build-planning conversation, then when that conversation's slice prompts run in Claude Code.
- Modify V2's storage architecture beyond what the new entity type additively requires. New table, new endpoints, new access-layer methods — yes. Modify existing entity types' tables, endpoints, behaviors — no.
- Plan beyond `workstream`. The next five schemas have their own conversations.
- Design `conversation` inline because it references `workstream`. The `conversation` entity has its own kickoff at `schema-design-kickoff-conversation.md`.
- Retroactively populate workstream records. Backfill is deferred to a planning item authored by the build-planning conversation.

---

End of kickoff prompt.
