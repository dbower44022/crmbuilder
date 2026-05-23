# Kickoff — Code Change Lifecycle methodology drafting conversation

**Last Updated:** 05-23-26 19:00
**Work ticket kind:** kickoff_prompt
**Status:** ready
**Workstream:** Code Change Lifecycle (established in SES-057)
**Planning item this conversation resolves:** PI-027
**Predecessor conversation:** SES-057 (diagnostic and design conversation that adopted Option III and authored this kickoff)
**Successor conversation:** PI-028 commit entity schema spec conversation (kickoff produced as this conversation's deliverable)

> **Note on this document's status as a work_ticket.** This kickoff is structurally a work_ticket record (kind: `kickoff_prompt`, status: `ready`). It is NOT yet authored as a WT-NNN row in the database — close-out payloads do not currently support a `work_tickets` section, and extending the payload format is part of the workstream this kickoff opens (PI-030). PI-033 back-fill will retroactively author this kickoff as the WT-NNN record consumed by the conversation it opens.

---

## Goal

Draft `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` — the V2 methodology document defining the seven-stage code change lifecycle and the access-layer rules that make it auditable. Settle eight deferred design decisions in passing. Produce the kickoff prompt for the commit entity schema spec conversation (PI-028) as the closing deliverable.

The motivating problem is documented in SES-057. The short version: only one of 26 planning_items in the CRMBUILDER engagement database shows status `Resolved`, and that one was achieved via a manual status flip with no companion governance edge. The audit chain from a planning item through its planning conversation, work tickets, execution conversation, commits, and resolution is not currently machine-readable. Option III (adopted in DEC-168) is the comprehensive fix: first-class commit entities, resolves edges, work_ticket authoring methodology, and a full PI-to-SHA join queryable in SQL. This conversation drafts the methodology that drives the rest of the workstream.

---

## Eight deferred design decisions to settle

### 1. Commit identifier strategy

How does a commit record get its identifier?

- **(a) Sequence-style `CM-NNN`** with server-side auto-assignment, matching the pattern of every other governance entity. SHA stored as a separate `commit_sha` field. Pro: identifier discipline is uniform across the system; back-fill order matches commit chronology. Con: the SHA is the natural identifier in git, and aliasing it adds a translation step.
- **(b) SHA-as-identifier** with the full 40-character SHA (or a stable prefix like 12 characters) as the primary key. Pro: zero translation; can be cross-referenced against git tooling directly. Con: breaks the NNN-prefix convention and the auto-assignment helper pattern.
- **(c) Both** — `CM-NNN` as identifier per the convention, with the SHA as a unique secondary key and the standard /commits/by-sha/{sha} lookup endpoint. Pro: convention preserved, SHA-as-natural-key preserved. Con: two ways to refer to the same record; downstream code must pick one.

### 2. Granularity of `resolves` edges

A commit resolves a planning item, or a conversation resolves a planning item, or both?

- **(a) Per-commit only**: `commit_resolves_planning_item` is the canonical edge. The conversation does not get its own resolution edge — its commits do. Pro: finest grain; defect investigation lands on a specific SHA. Con: a planning item that takes ten commits across two conversations to resolve has ten edges, which may overstate the resolution signal.
- **(b) Per-conversation only**: `conversation_resolves_planning_item` is the canonical edge. Commits are linked to the conversation but not directly to the planning item. Pro: one edge per resolution event; matches the close-out-payload-grain at which resolution is declared. Con: defect investigation has to walk through the conversation to find the actual delivering commits.
- **(c) Both**: per-conversation as the canonical resolution event, per-commit as a finer-grain "this specific commit delivered" edge. Pro: covers both query patterns. Con: doubled edge volume; methodology must specify which is declared in the payload and which is derived.

### 3. Commit ingestion trigger

When and how do commits flow from git log into the commits table?

- **(a) Manual via close-out payload**: the conversation enumerates its commits in the payload's `commits` array; the apply script POSTs them. No git-log scanning. Pro: explicit, auditable. Con: a forgotten commit in the payload is silently absent from the audit chain.
- **(b) Git post-commit hook**: a git hook running on every commit invokes a small script that POSTs the commit record to the API. Pro: nothing gets missed. Con: requires the API to be running on the developer workstation at every commit time; failure handling needed.
- **(c) Background polling**: a periodic job scans `git log` on both repos and POSTs new commits. Pro: nothing missed, no commit-time coupling. Con: latency between commit and ingestion; complexity of polling state.
- **(d) Apply-time ingestion**: when `apply_close_out.py` runs, it scans `git log` since the last applied close-out and POSTs every new commit. Pro: ingestion is coupled to the natural cadence of close-outs; nothing missed; payload doesn't have to enumerate. Con: ingestion happens at apply time rather than commit time, so the live database lags real commits until the next close-out.

### 4. Commit record fields

What lives in a commit record? Minimum set is clear; optional set is open.

- **Minimum (all options include)**: `sha`, `message`, `author`, `author_email`, `committed_at`, `repository`, `branch`, `parent_sha`.
- **Optional candidates**: `files_changed_count`, `files_changed_paths` (potentially large; JSON array column or separate table), `signed_by` (commit signature verification), `committer` (when distinct from author), `merge_parent_sha` (for merge commits, second parent).

Settle which optional fields are in v0.8 versus deferred to v0.9.

### 5. Multi-repo and multi-engagement scoping

The V2 engagement databases are per-client. The CRMBUILDER engagement DB holds dogfood records; the CBM engagement DB holds Cleveland Business Mentors records. But Claude Code conversations sometimes touch both repos in a single conversation — e.g., a dogfood conversation that fixes a bug in `crmbuilder` and also updates a CBM YAML deployment file.

- **(a) Conversation scoped to one engagement; commits split by repo**: the conversation record lives in one engagement DB (typically the one whose PI motivated the work); commits in each repo are tracked in their respective engagement DB; cross-engagement references link them. Pro: each engagement DB stays internally consistent. Con: cross-engagement query mechanics needed for the full chain.
- **(b) Conversation forks into per-engagement child records**: a parent conversation in one DB plus child conversation records in each engagement DB whose repo received commits. Pro: each engagement DB has self-contained conversation records. Con: doubles or triples conversation records for cross-repo work.
- **(c) Commits live in a shared meta DB, references stay in engagement DBs**: a separate commits-only DB tracks every commit across every repo; engagement DBs link to it. Pro: one source of truth for commits. Con: introduces a new shared-DB pattern that doesn't exist elsewhere.

### 6. Typed `addresses` relationship_kind for work_ticket-to-planning_item

A work_ticket is born to address a planning item. Today this is `is_about` (generic). Should it be a typed kind?

- **(a) Add `addresses`** as a typed kind: `work_ticket → planning_item [addresses]`. Pro: queryable as "all work_tickets created to address PI-NNN" without disambiguating generic `is_about` mentions. Con: more vocabulary.
- **(b) Stay with `is_about`**: defer the typed kind until query patterns prove necessary. Pro: smaller vocabulary, follows DEC-133's frequency-justified deferral test. Con: queries against the relationship are ambiguous.

### 7. Work_ticket authoring rule scope

Which committed documents are born as work_ticket records?

- **(a) Only `CLAUDE-CODE-PROMPT-*.md`** under `PRDs/product/crmbuilder-v2/prompts/` and `PRDs/product/crmbuilder-automation-PRD/`. The narrowest, machine-detectable rule.
- **(b) All `kickoff_prompt`-kind documents**: includes planning-kickoff files like `ui-v0.8-planning-prompt.md` and workstream-establishing kickoffs like the one this conversation is opening against. The work_ticket spec at `governance-schema-specs/work_ticket.md` already names many of these as canonical examples.
- **(c) Broader still**: every single-use seed document committed to the repo, including session prompts, schema-design kickoffs, and methodology-kickoff documents.

The work_ticket spec admits option (b) explicitly; the diagnostic in SES-057 noted that no Claude Code prompts have been authored as work_tickets to date, and the back-fill effort scales with the chosen rule.

### 8. Direction of the `blocks` relationship_kind

The diagnostic in SES-057 surfaced a direction ambiguity. The v0.7 backfill created `PI-025 → blocks → PI-024` and `PI-026 → blocks → PI-025` for the Phase 2 / Phase 3 / Phase 4 chain. Natural English reading "PI-025 blocks PI-024" would mean PI-024 waits for PI-025 — but the phase ordering suggests Phase 2 (PI-024) precedes Phase 3 (PI-025) precedes Phase 4 (PI-026). The two interpretations are incompatible.

Settle the convention by reading the existing rows in the dogfood database against the phase descriptions in DEC-166 and documenting the convention in the methodology. Either:

- **(a) Source blocks target** — meaning "the source must be resolved before the target can proceed" (target waits for source). Reading: PI-024 (Phase 2) waits for PI-025 (Phase 3), which is opposite to natural phase ordering — implying the v0.7 backfill rows are reversed.
- **(b) Source is blocked by target** — meaning "the source cannot proceed until the target is resolved." Reading: PI-025 (Phase 3) waits for PI-024 (Phase 2), matching natural phase ordering — implying the v0.7 backfill rows are correct.

If (a) is adopted, the v0.7 backfill rows need a one-time correction. If (b) is adopted, the convention is documented in the methodology and the rows stand. The methodology document is the place where future workstreams find the answer to "which direction do `blocks` edges go."

---

## Deliverable shape

Two artifacts produced by this conversation:

### Artifact 1: Methodology document

Path: `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md`

Expected sections:

1. **Purpose and Scope** — what the methodology covers; what is out of scope (e.g., legacy v1 records).
2. **The Seven-Stage Lifecycle** — narrative walkthrough of each stage with the entities and edges that record it. Stages: (i) planning item motivates the work; (ii) planning conversation produces decisions and work_ticket(s); (iii) execution conversation opens against a work_ticket; (iv) execution conversation produces commits; (v) close-out payload records resolves edges, work_ticket consumptions, and commits; (vi) apply transaction lands the records; (vii) downstream queries walk the chain.
3. **Vocabulary additions** — for each new relationship_kind named in the deferred decisions, the source-target types it admits and the access-layer rules that govern it.
4. **Close-out payload format extension** — what `resolves_planning_items`, `work_tickets`, and `commits` look like in the payload JSON; how `apply_close_out.py` processes each section; idempotency rules.
5. **Authoring rules** — when a work_ticket is born versus consumed versus superseded; when a planning item is resolved; when a commit gets ingested; the work_ticket authoring rule scope chosen in deferred decision #7.
6. **Audit query patterns** — example SQL or API calls that walk the full chain. At minimum: "given PI-NNN, list every commit that contributed to its resolution"; "given a commit SHA, list every planning item it resolves and the planning conversation that motivated each".
7. **Migration and back-fill posture** — what PI-033 will retroactively author; what stays as historical noise.
8. **Revision control** — standard project format.

The methodology document is the source of truth for every schema decision that follows. PI-028 (commit entity schema spec) derives from this document.

### Artifact 2: Kickoff for the PI-028 commit schema spec conversation

Path: `PRDs/product/crmbuilder-v2/schema-design-kickoff-commit.md`

Same tight kickoff structure as this document: goal, design decisions the schema spec must answer (these are derived from the methodology — likely a much shorter list than this kickoff's eight items), deliverable shape (the seven-section schema spec), read list (this methodology document, the six v0.7 governance schema specs as precedent, the schema spec guide). The PI-028 schema conversation opens against this kickoff in a fresh Claude.ai conversation.

---

## Read list

Required reading before drafting:

1. **`PRDs/product/crmbuilder-v2/close-out-payloads/ses_057.json`** — this kickoff's predecessor session record. The full diagnostic findings and option framing live here; this kickoff intentionally does not repeat them.
2. **`PRDs/product/crmbuilder-v2/governance-schema-specs/work_ticket.md`** — the work_ticket entity that already exists and is central to the methodology.
3. **`PRDs/product/crmbuilder-v2/governance-schema-specs/conversation.md`** and **`close_out_payload.md`** and **`deposit_event.md`** — the three governance entities whose existing edges form most of the chain.
4. **`PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md`** — the template Artifact 2 must follow.
5. **`crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`** — the existing REFERENCE_RELATIONSHIPS, ENTITY_TYPES, and `_kinds_for_pair` that the new methodology extends.
6. **`tools/diagnostics/diagnose_planning_items.py`** and the conversation that produced it — the diagnostic that surfaced the gaps.

Optional but useful:

7. The v0.7 governance build-planning kickoff at `governance-schema-build-planning-kickoff.md` — example of a workstream-integration kickoff produced from per-entity schema specs.
8. **`PRDs/product/crmbuilder-v2/close-out-payloads/ses_055.json`** and **`ses_056.json`** — recent close-out payloads showing the established structure that the new payload sections extend.

---

## Close-out expectations for the PI-027 conversation

When this conversation closes, its close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_058.json` should contain:

- **1 session record** (SES-058) — the methodology drafting conversation.
- **8 decisions** — one per deferred decision settled. Decision identifiers DEC-171 through DEC-178 (subject to availability check at apply time). Each carries the standard eight fields including alternatives_considered.
- **1 planning item resolution** — PI-027 marked Resolved with `resolution_reference` pointing to SES-058. This is the first real exercise of the `resolves_planning_items` payload section, BUT the payload format does not yet support it. Two options for the methodology conversation to handle this:
  - **(a) Defer**: leave PI-027 Open in this close-out; rely on PI-033 back-fill to resolve it once PI-030 ships. Honest and consistent with the rest of the workstream.
  - **(b) Hand-flip**: manually flip PI-027's status to Resolved via a direct API PATCH or the V2 desktop UI after the close-out applies, noting the manual transition in the session record. Less honest but completes the lifecycle visually.
  - The methodology conversation should pick one in passing and document the choice.
- **References** — three or more `decided_in` per the 8 decisions, plus `is_about` from SES-058 to PI-028 (the next planning item to surface), plus cross-decision `references` where one settlement informs another.
- **Artifacts produced** — `methodology-code-change-lifecycle.md` (Artifact 1) and `schema-design-kickoff-commit.md` (Artifact 2).
- **In flight at end** — PI-028 commit schema spec conversation queued, opening against Artifact 2.

The close-out itself should aim to demonstrate the methodology it documents wherever the current payload format permits. Where the payload format does not permit (the `resolves_planning_items` and `work_tickets` and `commits` sections), the methodology document should explicitly call this out as a known gap that PI-030 closes.

---

## What is explicitly NOT in scope for this conversation

- The commit entity schema specification itself (PI-028's job).
- Any code changes to `vocab.py`, `apply_close_out.py`, migrations, repositories, API routers, or UI (PI-029, PI-030, PI-031's jobs).
- Back-fill of historical records (PI-033's job).

The methodology document names what these downstream planning items must produce, but does not produce them. If a schema-level question arises that the methodology cannot answer abstractly, name it as a follow-on decision for PI-028 rather than over-reaching here.
