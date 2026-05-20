# Governance Entity Schema Design — `reference_book` — Kickoff Prompt

**Last Updated:** 05-20-26 22:55
**Purpose:** Seed prompt for a new Claude.ai conversation that designs the `reference_book` entity type schema for the governance entity schema-design workstream.
**Position in workstream:** **Third of six** schema-design conversations. Predecessors: workstream-establishing conversation, `workstream` schema design, `conversation` schema design. Successors: `work_ticket`, `close_out_payload`, `deposit_event`.
**Workstream master:** `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md`
**Schema spec template:** `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md`

---

## The task

Design the `reference_book` entity type schema for V2's storage layer. Drive a structured architectural discussion that produces one deliverable:

**`PRDs/product/crmbuilder-v2/governance-schema-specs/reference_book.md`** — the complete schema specification per the template in `governance-entity-schema-spec-guide.md`.

Cadence matches the methodology workstream's schema-design conversations and the user-interface planning conversations: structured architectural discussion driven one decision at a time, building toward the specification section by section.

At conversation close: decisions written via direct API as decision records; any deferred items written as planning items; one session record written by Doug through the V2 desktop New Session dialog per the session-record-at-close pattern.

---

## Context — why reference book third

`reference_book` is the long-lived versioned workflow file family established by DEC-117. Designing it after `conversation` means the conversation entity's outgoing reference set is known — conversations point at reference books for their authoritative sources (kickoff prompts that cite a Product Requirements Document, a workstream master plan, a methodology guide, the multi-engagement architecture document).

The principal design question is **versioning**. Reference books accumulate changes over time. The workstream master plan for the methodology entity schema-design workstream has two versions (1.0 on 05-11-26 and 1.1 on 05-12-26); the methodology guide has 1.0 and 1.1; the multi-engagement architecture document has had several updates. How does the database represent this version history, and how does it answer "what version was in force at the time of session NNN"?

---

## What `reference_book` needs to host

A reference book is a long-lived versioned workflow file that is referenced repeatedly across many conversations over its lifetime. Real examples at the time of this kickoff:

- Product Requirements Documents (`ui-PRD-v0.1.md` through `ui-PRD-v0.6.md`, `storage-system-PRD-v0.1.md`, `catalog-ingestion-PRD-v0.1.md`).
- Implementation plans (`ui-v0.4-implementation-plan.md` etc.).
- Workstream master plans (`methodology-schema-workstream-plan.md`, `v0.5-engagement-management-workstream-plan.md`, this workstream's `governance-schema-workstream-plan.md`).
- Methodology guides (`methodology-entity-schema-spec-guide.md`, `governance-entity-schema-spec-guide.md`).
- Architecture documents (`multi-engagement-architecture.md`).
- Schema specifications (everything under `methodology-schema-specs/` and the forthcoming `governance-schema-specs/`).
- Conduct framework documents (`PRDs/process/conduct/charter.md`, `kickoff.md`, `question-library.md`).
- Investigation reports kept for reference (`multi-tenancy-routing-investigation-report.md`).

Excluded from reference book scope (these are work tickets — see next conversation): one-off kickoff prompts that drive one specific conversation and then are not referenced again as authoritative sources, ad-hoc apply prompts under `prompts/CLAUDE-CODE-PROMPT-*.md` produced for one slice's execution.

The distinction between reference book and work ticket is **continued reference**: a reference book is cited by subsequent conversations as a source of truth; a work ticket is consumed by one conversation and not revisited.

So the `reference_book` schema needs to host:

- Identifier and a human-readable title
- A description (what this reference book is, why it exists)
- A kind classification (Product Requirements Document, implementation plan, master plan, methodology guide, architecture document, schema specification, conduct framework, investigation report, other) — possibly
- A file path (where the canonical file lives in the repo)
- Version history (the principal design question)
- A status (active, archived, superseded) — possibly
- Relationship-readiness for `conversation` to reference it

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template.
4. `PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md` and `conversation.md` — completed predecessor specifications.
5. The six foundation decisions, especially DEC-117 (three families) and DEC-121 (single source of truth). Available in `PRDs/product/crmbuilder-v2/db-export/decisions.json`.
6. The session records for the workstream-establishing and the two prior schema-design conversations, in `db-export/sessions.json`.
7. The existing `charter` and `status` entities' versioning model — they use versioned-replace with Make Current semantics. This is the closest existing pattern in V2 and is the natural starting point for reference book versioning. Review `crmbuilder-v2/src/crmbuilder_v2/access/` charter and status modules.
8. A representative set of actual reference book files to ground the conversation: the methodology workstream master plan (`methodology-schema-workstream-plan.md`) is a good example with two versions.

---

## Architectural questions likely to arise

The conversation will surface these in some order. The list is illustrative, not exhaustive — let the conversation flow.

- **Identifier prefix.** Working assumption: `RB`. Alternatives: `REFB`, `REFBOOK`, `RBK`. `RB` is short but distinctive against the existing prefix list. Decision.
- **Field inventory.** Working minimum: `reference_book_identifier`, `reference_book_title`, `reference_book_description`, `reference_book_kind`, `reference_book_file_path`, `reference_book_status`, timestamps. What else? Author? Owner? Domain (for engagement-scoped reference books versus global ones)?
- **Kind classification.** Closed enum (Product Requirements Document, implementation plan, master plan, methodology guide, architecture document, schema specification, conduct framework, investigation report, other) or open string? The methodology workstream's status fields chose closed enums; this likely follows.
- **Versioning model.** The principal question. Three options to consider:
  - **Versioned-replace.** Modeled on charter and status. A `reference_book` record IS the current version; previous versions live in a parallel `reference_book_version` table. Make Current semantics. Query "in force at time T" goes against the versions table.
  - **Embedded version array.** A `reference_book` record holds its current state plus a JSON array of version history (timestamps, summaries, change log entries) on the same record.
  - **Content-addressed snapshots.** Each version is a separate record with a content hash; the current version is found by pointer or by latest-timestamp. More involved but supports forking.
  - **Link to git commits.** No in-database versioning; just record the file path and let git provide the history. Lightest weight but requires git access to answer queries.
  - Decision.
- **File path semantics.** Absolute, repo-relative, or symbolic (resolved against a per-engagement root)? Working assumption: repo-relative path string. Confirm.
- **Reference book "in force at time T" semantics.** Even with versioning in place, the query "what version was in force at session NNN" requires a notion of when a version was made current. Charter and status use a `made_current_at` timestamp on the version record. Working assumption: follow that pattern. Confirm.
- **Soft-delete versus append-only versus archive-status.** Reference books rarely disappear but sometimes become obsolete. The methodology workstream's superseded-but-retained pattern (e.g., `ui-v0.4-planning-prompt.md` retained with a supersession header) suggests an `archived` status rather than soft-delete. Discuss.
- **Engagement scoping.** Some reference books are global (methodology guides apply across engagements); others are engagement-specific (a Cleveland Business Mentors implementation plan). Per V2's per-engagement isolation, both kinds live in the per-engagement database. Does the schema need to mark global-versus-engagement-specific, or is that implicit in the file path?
- **UI deviations.** Reference books may warrant a heavier detail pane (preview of file content, version history visible inline) than the default. Consider.
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
- `conversation_reference`: descriptive text identifying the conversation by its deliverable. Example template: `"Claude.ai schema-design conversation that produced governance-schema-specs/reference_book.md. No transcript preserved per DEC-025."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of architectural questions discussed.
- `artifacts_produced`: `governance-schema-specs/reference_book.md`, plus decision records authored, plus planning items authored.
- `in_flight_at_end`: `"Next workstream conversation: work ticket entity schema design. Kickoff at schema-design-kickoff-work-ticket.md."`

---

## What this conversation does NOT do

- Build any code. The build happens later — when the build-planning conversation produces slice prompts.
- Modify V2's storage architecture beyond what the new entity type additively requires.
- Modify the existing `charter` or `status` entities' versioning behavior. The reference book versioning model may follow that pattern, but the existing entities are not touched.
- Plan beyond `reference_book`. The next three schemas have their own conversations.
- Design `work_ticket` inline. Work ticket is the next conversation; this conversation may *name* the work ticket entity in its cross-references but does not design it.
- Retroactively populate reference book records for past documents. Backfill is deferred to a planning item authored by the build-planning conversation.

---

End of kickoff prompt.
