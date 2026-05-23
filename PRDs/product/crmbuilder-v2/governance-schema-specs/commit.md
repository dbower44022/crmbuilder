# Governance Entity Schema Spec — `commit`

**Last Updated:** 05-23-26 22:30
**Status:** Draft v1.0 — produced by PI-028 schema-design conversation
**Position in workstream:** First and (so far) only schema spec produced under the Code Change Lifecycle methodology workstream established in SES-057. Seventh governance entity type overall, after the six produced by the SES-048..053 governance-entity schema-design workstream (`workstream`, `conversation`, `reference_book`, `work_ticket`, `close_out_payload`, `deposit_event`).
**Predecessor conversation:** SES-061 (methodology drafting; produced `methodology-code-change-lifecycle.md` v1.0, which settles eight foundation decisions DEC-183 through DEC-190 that this spec inherits)
**Successor conversation:** PI-029 — schema migration and access layer (Claude Code execution); kickoff at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-A-commits-table-and-vocab.md`
**Methodology authority for this spec:** `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` v1.0

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-23-26 22:30 | Doug Bower / Claude (SES-063) | Initial draft. Produced by the first schema-design conversation under the Code Change Lifecycle methodology workstream. Renders the v0.8 commit entity type defined in `methodology-code-change-lifecycle.md` §3.1 into the nine-subsection format prescribed by `governance-entity-schema-spec-guide.md`. Inherits eight cross-spec precedents in force after SES-053: references-edge over foreign-key for parent-child governance relationships (DEC-124), per-status lifecycle timestamps for workflow-shaped lifecycles (DEC-126), truly-terminal terminals (DEC-125), typed sequencing edges introduced when entity-family frequency justifies (DEC-133), documentary-vs-workflow distinction (DEC-137), terminal-state consumption requires the inbound consumption edge (DEC-143), born-terminal append-only with creation as the event-recording moment (DEC-156), and multi-event-per-target-record under born-terminal append-only (DEC-158). Applies them on the commit entity's facts: commit is documentary-shaped per DEC-137 and goes one step further — it is **status-free**, the first governance entity type with no status field at all. Establishes four new cross-spec precedents of its own (see §1). Adopts the v0.8 fifteen-column field inventory from methodology §3.1 verbatim with full validation specification. Confirms the FK-on-`commit_conversation_id` deviation from DEC-124's references-edge precedent already chosen by the methodology, with frequency-justified-denormalization rationale documented in §3.3. Adds one new entity type to `ENTITY_TYPES` (`commit`) and zero new relationship-kind values — the three new kinds named by the methodology (`resolves`, `addresses`, the renamed `blocked_by`) are governance-edge vocabulary owned by PI-029's migration, not by this entity-type-defining spec. Thirteen acceptance criteria captured (§3.7 hits the spec-guide minimum of ten with room). Open questions: derived endpoint URL shapes (`GET /conversations/{id}/commits` and others) for build-planning; SHA-256 migration anticipation for a future v0.9; `commit_author_kind` field for attribution discipline if it becomes a problem. Three decisions and zero planning items authored at conversation close. PI-028 stays Open at this conversation's close per methodology §9 — the `resolves_planning_items` payload section the methodology specifies does not yet ship; PI-033 resolves PI-028 retroactively. |

---

## Change Log

**Version 1.0 (05-23-26 22:30):** Initial creation. Defines `commit` as the V2 governance entity type that hosts the git-commit-as-governance-record concept per the Code Change Lifecycle methodology — a durable, queryable record of each git commit produced by a conversation, attributed to that conversation via the `commit_conversation_id` foreign key, with full commit-message, author, repository, branch, parent, and file-change-count metadata captured at the time of close-out ingestion. Adopts the methodology's fifteen-column field inventory verbatim. Adopts a **status-free documentary lifecycle** (no `commit_status`, no transitions, no workflow); the entity either exists or doesn't, with soft-delete-with-restore as the only state-change mechanism. Articulates the **FK-over-references-edge deviation** from DEC-124's cross-spec precedent on frequency-justified-denormalization grounds: commits are dense (estimated several hundred per engagement over the project's life, vs ~tens for the workstream-designed governance entities), every audit query in methodology §6 walks commit→owning-conversation, and the FK saves both a refs row per commit and a JOIN per query. Adopts the `commit_sha` natural key as a UNIQUE INDEX, with a new natural-key lookup endpoint pattern `GET /commits/by-sha/{sha}` accepting both full and prefix SHA values (ambiguous prefix → HTTP 409 with candidate list per the methodology). Introduces the **JSON-array column pattern for variable-cardinality scalar lists** (`commit_parent_shas` is the first such column on a governance entity table; the pattern generalizes to any future 0-to-N scalar list that doesn't warrant a separate normalized table). Restates DEC-187's **conversation-scoped accounting unit principle** as a cross-spec precedent for future governance entities representing artifacts that physically live outside the engagement database — commits live in git, but their governance records live in the producing conversation's engagement database, with `commit_repository` distinguishing physical home from governance home. Standard API endpoint set per the spec guide §6, plus the new `GET /commits/by-sha/{sha}` natural-key lookup endpoint. Default soft-delete with restore (no append-only deviation — commits are not born-terminal events the way deposit_events are; soft-delete supports the rare cases of mis-ingestion correction). Default UI layout per the spec guide §3.6, with two natural additions paralleling work_ticket and close_out_payload precedents: a Repository column in the master pane and a Repository filter combo in the master-pane toolbar (browse-by-repository is the operational pattern, since the per-engagement database may carry commits from multiple repos). Thirteen acceptance criteria captured. Three decisions (DEC-198, DEC-199, DEC-200) and zero planning items authored at conversation close. PI-022 covers retroactive backfill for commit records as it does for the other governance entity types; the specific backfill scope (every historical commit across both repos from start through PI-033 apply date) is named in methodology §7.1.

---

## 1. Purpose and Position

This document specifies the `commit` entity type for V2's storage layer. It is the **seventh governance entity type** in V2 overall and the **first under the v0.8 release** — produced under the **Code Change Lifecycle** methodology workstream (established in SES-057), distinct from the SES-048..053 governance-entity schema-design workstream that produced the six v0.7 governance entities (`workstream`, `conversation`, `reference_book`, `work_ticket`, `close_out_payload`, `deposit_event`).

The workstream is governed by `methodology-code-change-lifecycle.md` v1.0 (produced by SES-061), which settles eight foundation decisions DEC-183 through DEC-190 and names PI-028 (this conversation), PI-029 (schema migration), PI-030 (close-out payload extension and apply), PI-031 (UI), PI-032 (methodology rollout), and PI-033 (back-fill) as the downstream planning items that consume the methodology. This spec produces PI-028's deliverable. The schema-spec format follows `governance-entity-schema-spec-guide.md` v1.0 — the same template the six v0.7 governance entities used.

`commit`'s primary scope is to host the **git-commit-as-governance-record** concept per the methodology — every commit produced by a Claude.ai or Claude Code conversation, attributed to that conversation, with enough metadata captured to support the methodology's audit query patterns (methodology §6) without re-querying git at audit time. Real examples already implicit in the project's history at this spec's authoring time include every commit under `dbower44022/crmbuilder` and `dbower44022/ClevelandBusinessMentoring` — each is structurally a commit record waiting to be authored. Before this entity type lands, those commits exist only as git objects with no machine-resolvable backreference to the conversation that produced them.

The schema is intentionally minimum-viable. The deferred fields named in methodology §3.1 — `commit_files_changed_paths`, `commit_signed_by`, `commit_committer_name`, `commit_committer_email`, `commit_message_trailers` — are explicitly out of scope for v0.8 and deferred to v0.9 or later pending real-use signal. The audit-trail use case the methodology motivates does not need them; if they become needed, each is one additive migration away.

This conversation **inherits eight cross-spec precedents** in force after SES-053 (the deposit_event schema-design conversation that closed the v0.7 governance-entity schema-design workstream) and applies them throughout:

- **References-edge over foreign-key for parent-child governance relationships** (DEC-124, SES-048). This spec **deviates** from the precedent for the `commit_conversation_id` field on frequency-justified-denormalization grounds. The deviation is articulated and justified in §3.3; the FK choice itself was already settled by the methodology (§3.1, audit queries in §6.1 and §6.2 join through the FK directly).
- **Per-status lifecycle timestamps for workflow-shaped lifecycles** (DEC-126, SES-048). Not applicable — commit's lifecycle is documentary, not workflow-shaped. Base timestamps only per the DEC-137 precedent and the status-free refinement this spec establishes.
- **Terminal-states-are-terminal discipline** (DEC-125, SES-048). Not applicable in the conventional sense — commit has no status field, hence no terminal status to enforce. Discipline preserved structurally: the absence of a status field is itself the strongest form of "no transitions, ever" — there is nothing to transition.
- **Typed sequencing edges introduced when entity-family frequency justifies** (DEC-133, SES-049). Applied on this spec's facts: the methodology already names three new kinds (`resolves`, `addresses`, `blocked_by`) but those are **governance-edge vocabulary, not commit-specific vocabulary**. This spec adds the `commit` entity type to `ENTITY_TYPES` and adds **zero** new relationship-kind values — the FK on `commit_conversation_id` carries the dominant relationship, and the parent-SHA references between commits are captured in the `commit_parent_shas` JSON array rather than as typed sequencing edges. A future `commit_parents_commit` typed kind is rejected on DEC-133 grounds: the queryable pattern (walk parents to find merge ancestry) is operational metadata that the JSON array column serves directly with no JOIN cost.
- **Documentary-vs-workflow distinction** (DEC-137, SES-050). Applied on this spec's facts: commit is documentary-shaped. This spec **establishes a new cross-spec precedent refinement** — see below.
- **Terminal-state consumption requires the inbound consumption edge** (DEC-143, SES-051). Not applicable — commit has no terminal state. Discipline preserved structurally per the absence-of-status argument above.
- **Born-terminal append-only with creation as the event-recording moment** (DEC-156, SES-053). Not adopted — commit is not born-terminal append-only despite its event-shape similarity to deposit_event. The difference: deposit_event records an apply *attempt* (a one-time event with success/failure outcome that admits no edit machinery and no soft-delete); commit records a git object that may need administrative correction (mis-ingestion, wrong repository attribution, corrupted message). Soft-delete-with-restore preserves the correction path. Commit also carries `commit_updated_at` (allowing rare metadata corrections like a fixed message-first-line truncation), which born-terminal append-only would forbid.
- **Multi-event-per-target-record under born-terminal append-only** (DEC-158, SES-053). Not applicable — commit is not born-terminal append-only.

This conversation **establishes four new cross-spec precedents** that successor governance schemas may inherit by default and may deviate from with rationale:

- **Status-free documentary lifecycles** (refinement of DEC-137). DEC-137 established that documentary-shaped lifecycles inherit base timestamps only (no per-status timestamps). Reference_book — the precedent's original instance — still carries a three-value status field (`active` → `archived` / `superseded`). Commit goes one step further: **documentary lifecycles MAY drop the status field entirely** when no operationally meaningful states exist. Commit has no `commit_status`, no transitions, no terminals. The entity either exists or doesn't, with soft-delete as the only state-change mechanism. The refinement generalizes — any future governance entity that captures an immutable observed fact (a git object, a network response, a measurement) and has no workflow states a consultant would query by status is free to drop the status field. The refinement is intentionally permissive (MAY, not MUST); future documentary entities with even a two-status distinction (e.g., active/archived) follow reference_book's precedent.

- **Natural-key lookup endpoints via `GET /{plural}/by-{key}/{value}`** (new). The standard endpoint set includes identifier-based lookup at `GET /{plural}/{identifier}`. Commit introduces the natural-key variant `GET /commits/by-sha/{sha}` — the SHA is the entity's intrinsic identity in git, not the V2-assigned `CM-NNNN` identifier. The endpoint accepts both full (40-char) and prefix SHA values, with ambiguous prefix returning HTTP 409 plus the candidate list. The precedent generalizes — any future governance entity with a strong natural key distinct from its V2 identifier (a future `file_artifact` entity with content-hash as natural key, a `network_response` entity with response-id as natural key) inherits the `/{plural}/by-{key}/{value}` URL pattern and the ambiguous-prefix-returns-409 semantic. Singular entity types (where the natural key is the V2 identifier itself, like reference_book or work_ticket) do not need the variant.

- **JSON-array columns for variable-cardinality scalar lists** (new). Commit's `commit_parent_shas` is the first JSON array column on a governance entity table — a 0/1/2-element list of parent SHAs that doesn't warrant a separate normalized `commit_parents` table because (a) the cardinality is bounded at 2 by git's data model, (b) the values are read as a unit (never queried by individual element), and (c) the relationship is intrinsic to the commit object rather than independently queryable governance metadata. The precedent generalizes — any future governance entity with a bounded-cardinality scalar list intrinsic to the entity's identity follows the JSON-column pattern. Unbounded or queried-by-element lists still warrant separate tables (the reference_book → reference_book_versions pattern remains the precedent for those).

- **Conversation-scoped accounting unit principle** (restating DEC-187 in cross-spec precedent form). DEC-187 (methodology §3.1's authoritative settling, settled in SES-061) established that every record produced by a conversation belongs to that conversation's engagement database, regardless of which physical artifact (repo, file, external system) the record describes. Commit is the first governance entity whose physical artifact (the git commit object) lives outside the engagement database — commits are git objects in repositories that the engagement does not own. The cross-spec precedent restates DEC-187 in spec-inheritable form: **the physical home of an artifact and the governance home of its record are independent**; the governance home is always the producing conversation's engagement database; the physical home is captured by an attribute (here, `commit_repository`). The precedent generalizes to any future governance entity representing an external artifact (a network response, a deployed config, a database backup) — the record lives in the producing conversation's engagement database; the artifact's physical location is one column.

---

## 2. Summary

A `commit` record in V2 represents one git commit produced by a Claude.ai or Claude Code conversation. The methodology's seven-stage Code Change Lifecycle places commits at Stage 4 (execution conversation produces commits) and ingests them at Stage 5 (close-out payload records). Each record carries the commit's intrinsic git identity (`commit_sha`, the 40-character SHA-1 hash that uniquely identifies the commit object), its substantive content (`commit_message_first_line`, `commit_message_full`), its authorship and timing metadata from `git log` (`commit_author_name`, `commit_author_email`, `commit_committed_at`), its repository context (`commit_repository`, `commit_branch`), its parent-SHA list for ancestry navigation (`commit_parent_shas`), a denormalized file-change-count for compact display (`commit_files_changed_count`), and a foreign-key linkage to the producing conversation (`commit_conversation_id`).

The schema is the thinnest shape that captures the Code Change Lifecycle's audit-trail use case faithfully: enough commit metadata to support every query pattern in methodology §6 without re-querying git, no more. Deferred fields per methodology §3.1 (`commit_files_changed_paths` — separate-table candidate; `commit_signed_by` — Doug's commits aren't signed; `commit_committer_*` — practically identical to author; `commit_message_trailers` — not currently used) grow additively in a future release if real-use signal supports them.

**Boundary with the v0.7 governance entities.** Commit is structurally distinct from all six v0.7 entities. The closest analogue is deposit_event — both capture an external-event fact with no workflow lifecycle — but commit deviates from deposit_event in two ways: it is not born-terminal append-only (soft-delete is admitted for administrative correction); and it has no `_outcome` field because there is no success-vs-failure axis to a git commit (a commit either exists or doesn't, and the "doesn't" case is captured by the absence of a record rather than a `failed` outcome value). The next-closest analogue is reference_book — both are documentary-shaped — but reference_book carries a three-value status field (the document has a lifecycle from authoritative through archived or superseded), and commit has none.

**Boundary with what commits are NOT.** A commit record is not the commit's diff. The full content of what changed lives in git, retrievable on demand via `git show <sha>`; the database carries only the metadata needed for audit queries. A commit record is not the commit's blame information — line-level authorship lives in git, queryable via `git blame`. A commit record is not a deployment event — deploying a commit somewhere produces a separate governance record (deposit_event for an apply, or a future `deployment` entity for production deploys). The line is the same as for the existing governance entities: the database carries the governance view appropriate to its query patterns; the physical artifact remains the authoritative source for its substance.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `commit` |
| Display name (singular) | Commit |
| Display name (plural) | Commits |
| Identifier prefix | `CM` |
| Identifier format | `CM-NNNN`, zero-padded to **four** digits (e.g., `CM-0001`, `CM-0427`) |
| Identifier auto-assignment | **Client-side** per the prefixed-identifier convention in repo `CLAUDE.md` line 62; helper at `GET /commits/next-identifier` returns the next available value for any client that wants the server to compute it |

**Identifier-prefix posture.** `CM` is two letters, matching `WS`, `RB`, `WT`, and `PI` in the existing short-prefix set. The collision list at this spec's writing has no conflict with `CM` — no existing governance, methodology, or v0.7 entity-type prefix begins with `C` other than `CHR` (charter, three letters, no ambiguity with `CM`) and `CRM` (crm_candidate, three letters, no ambiguity). The methodology's working assumption of `CM` (DEC-184, SES-061) is confirmed; alternatives `COM`, `CMT`, `GIT` add length without clarity and `GIT` carries the connotation of "anything from git" rather than "one commit specifically".

**Identifier-width posture (four digits).** Every v0.7 governance entity uses three-digit zero-padded identifiers (`WS-001`, `RB-001`, `WT-001`, `COP-001`, `DEP-001`) because the expected per-engagement cardinality is at most a few hundred per type. Commit deviates to four digits because the expected per-engagement cardinality is materially larger: at this spec's authoring time the crmbuilder repository has ~530 commits and the CBM repository has another ~200, and the back-fill named in methodology §7.1 will author roughly that many in PI-033's initial pass; sustained development adds dozens per quarter going forward. Three digits would cap at 999 and require a second migration within the foreseeable horizon; four digits cap at 9,999 which comfortably accommodates a decade of development across both engagements. The width is locked at four for this entity type only; future entity types make their own width call based on expected cardinality (refer §3.5.3 for the `next-identifier` helper's zero-pad-width responsibility).

**Identifier-assignment-side posture (client-side, not server-side).** The spec guide §6 names server-side auto-assignment-on-POST-omission as the default. Commit deviates to client-side per the prefixed-identifier convention in repo CLAUDE.md line 62: the apply script computes the identifier client-side via `GET /commits` highest-suffix + 1 and supplies it in the POST body. The deviation matches the operative pattern for every prefixed-identifier entity type in V2 (sessions, decisions, planning_items, risks, topics, etc.) — the server does not currently auto-assign for any of them. The helper endpoint `GET /commits/next-identifier` is exposed for symmetry with the other governance entities but is **not** the apply script's mechanism (the script's batch ingestion would race against the helper if the helper were called per-commit; client-side computation against a single `GET /commits` list is the safe pattern).

### 3.2 Fields

Field naming follows the parent-prefix convention per DEC-046: all fields including identifier and timestamps are prefixed `commit_`.

The methodology's §3.1 field inventory is adopted verbatim. The total is fifteen columns (twelve substantive + three governance-standard timestamps); the methodology's "fourteen columns including the three governance-standard timestamps" count appears to treat `commit_deleted_at` as not-yet-set in the default record state — both counts describe the same field set.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `commit_identifier` | TEXT | yes | client-assigned per CLAUDE.md line 62 | `^CM-\d{4}$`, unique within engagement | The commit's V2 governance identifier in `CM-NNNN` format. Client-side assignment via list-and-increment; server helper at `GET /commits/next-identifier` is exposed for symmetry but not used by the apply script's batch path. |
| `commit_sha` | TEXT | yes | — | `^[0-9a-f]{40}$`, lowercase enforced, unique within engagement | The commit's intrinsic git identity — the 40-character SHA-1 hash that uniquely identifies the commit object in any git repository. The natural key for the entity, exposed by the `GET /commits/by-sha/{sha}` lookup endpoint (§3.5). Lowercase enforcement is for canonical comparison; SHA values are case-insensitive in git but the schema normalizes to lowercase to make UNIQUE INDEX behavior deterministic. SHA-256-migration anticipation is captured as an open question in §3.8.2; v0.8 enforces SHA-1's 40-character shape. |

**`commit_sha` is both identity and natural key.** Most governance entities have a single identity field — the V2 identifier. Commit has two: the V2 identifier (`commit_identifier`) and the natural key (`commit_sha`). The two are unique in different ways: the V2 identifier is unique within the engagement; the SHA is unique within the engagement *and* unique within git itself (with cryptographic confidence). Either can be used to fetch the record; both have their own GET endpoint.

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `commit_message_first_line` | TEXT | yes | — | non-empty trimmed; no embedded newlines | The first line of the commit message, used for compact display in lists, prose, and audit-query results. From `git log --format=%s` (subject line). Captured separately from `commit_message_full` to avoid splitting at display time — every query that lists commits uses this column directly. |
| `commit_message_full` | TEXT | yes | — | non-empty trimmed; may contain embedded newlines and `v2:` prefix and `Co-authored-by:` trailers and any other commit-message content | The complete commit message body including the first-line subject. From `git log --format=%B` (raw body). Captured for audit completeness so that any future query needing the full text (e.g., "find commits whose body mentions `breaking change`") works without re-querying git. |

#### 3.2.3 Classification fields

**None.** Commit has no classification fields — no `commit_kind` enum, no `commit_status`, no `commit_priority`. The absence is intentional and is the schema-level realization of the status-free documentary lifecycle precedent this spec establishes (§1, §3.4):

- No `commit_kind`: there is no taxonomic axis on a git commit. Every commit is structurally the same artifact. (Conventional-commit-style prefixes like `v2:` live in the message text, not in a separate column.)
- No `commit_status`: there is no workflow on a commit itself. A commit either exists in the database or doesn't.
- No `commit_priority`: priority is a property of work (planning items, work_tickets), not of completed git objects.

If a future use case warrants a classification axis (e.g., a `commit_attribution_kind` enum to distinguish `claude_ai` / `claude_code` / `manual` per methodology §5.6's deferral), it is added as one additive migration.

#### 3.2.4 Relationship fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `commit_conversation_id` | TEXT | yes | — | non-empty trimmed; must match `^CONV-\d{3}$`; must reference an existing `conversation` record's `conversation_identifier` (access-layer validation, not a database-level foreign-key constraint per V2's soft-FK convention) | Foreign-key reference to the conversation that produced this commit. The V2 pattern for FK columns whose target is a prefixed-string identifier: column type `TEXT`, value is the target's identifier string (e.g., `CONV-014`), validated at the access layer rather than at the database boundary (V2 does not use SQLite-level `FOREIGN KEY` constraints — the access layer is the canonical enforcement point). See §3.3 for the rationale for the FK-over-references-edge choice. |
| `commit_parent_shas` | JSON | yes | `[]` for the initial commit of a repository; otherwise the parent SHA list | JSON array of 0, 1, or 2 lowercase 40-char hex SHA values; array length validation `0 <= len <= 2`; per-element validation `^[0-9a-f]{40}$` | Parent-SHA list. Zero entries for the initial commit of a repository; one entry for a normal commit; two entries for a merge commit. From `git log --format=%P` (split on space). Captured as JSON because the cardinality varies (0/1/2) and the values are read as a unit; see §1's new cross-spec precedent on JSON-array columns for variable-cardinality scalar lists. |

**`commit_conversation_id` is a foreign-key column, deviating from DEC-124.** DEC-124 (SES-048) established the cross-spec precedent that parent-child governance relationships use references-edge mechanism over foreign-key columns. Commit's relationship to its producing conversation is structurally a parent-child relationship — the conversation is the parent, the commit is the child — and would, under DEC-124, live in `refs` rather than as a column. The methodology document (§3.1 field table, §6.1 and §6.2 audit-query JOINs) chose the FK column anyway. This spec articulates that choice as a frequency-justified deviation:

- **Frequency-of-traversal argument.** Every audit query in methodology §6 walks from commit to owning conversation. The references-edge model would require a `refs` row per commit (refs grows linearly with commit count) and a JOIN per query (every commit query becomes a two-table operation). Commits are dense — methodology §7.1 estimates ~221 historical work_tickets but several hundred historical commits per engagement, and ongoing development adds far more commits than any other governance entity type. The FK column saves both the refs row and the JOIN, at the cost of one TEXT column on the commits table.

- **Cardinality argument.** A commit has exactly one producing conversation, always. The references-edge model is many-to-many by default; the FK column expresses one-to-many cleanly and lets the schema enforce the one-conversation constraint via the NOT NULL declaration (every commit MUST have a `commit_conversation_id`). Under references-edge, the constraint would require an access-layer rule (every commit MUST have an inbound edge of kind X from a conversation), which is more machinery for the same outcome.

- **DEC-187 reinforcement.** The conversation-scoped accounting unit principle (DEC-187, SES-061) makes every commit's conversation membership mandatory by the model. FK enforces mandatory ownership at the schema level via NOT NULL; references-edge does not (a record without an edge is still a valid record absent a separate access-layer rule).

- **Parallel to DEC-133's frequency-justified-deferral logic.** DEC-133 (SES-049) established that typed sequencing edges are introduced only when entity-family frequency justifies. The same frequency-justification logic, run in the opposite direction, justifies FK denormalization for dense governance entities. The two precedents are siblings, not contradictions: DEC-133 says "don't introduce typed structure absent frequency justification"; this spec's deviation says "do introduce FK denormalization when frequency justifies it."

The deviation is locked here for this entity type. Future high-volume governance entities (a future `database_row_change` entity, a future `api_request` entity) may apply the same frequency-justified-FK reasoning. Low-volume entities continue to default to references-edge per DEC-124.

**Hierarchy.** Commit's parent-SHA list (`commit_parent_shas`) captures the intra-commit ancestry relationship (the git DAG). The list is NOT a typed parent-child hierarchy in the V2 governance sense — it does not link commit records to other commit records via the references table, and it does not generate `refs` rows. A commit's parent SHAs may reference commits that are not yet ingested into V2 (e.g., commits from before the back-fill date, or commits in repositories not yet tracked); the JSON column carries the SHA strings as opaque values, not as governance-record references. If future use cases warrant queryable ancestry (e.g., "show me every governance-record commit in this branch's first-parent line back to commit X"), a future migration adds a derived `commit_ancestry` view or a typed `commit_parents_commit` relationship-kind. Per the DEC-133 frequency-justified-introduction test, this spec defers — the JSON column serves the v0.8 use cases adequately.

#### 3.2.5 Git metadata fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `commit_author_name` | TEXT | yes | — | non-empty trimmed | The commit author's display name. From `git log --format=%an`. Typically "Doug Bower" for Doug's commits and "Claude" for sandbox commits. Captured as-recorded by git; no normalization. |
| `commit_author_email` | TEXT | yes | — | non-empty trimmed; must contain `@`; basic email shape (no full RFC 5322 validation) | The commit author's email address. From `git log --format=%ae`. Typically `doug@dougbower.com` for Doug's commits. Captured as-recorded by git; no normalization. |
| `commit_committed_at` | TIMESTAMP | yes | — | strict ISO 8601 with explicit timezone offset (e.g., `2026-05-23T20:45:12-04:00`); not normalized to UTC | The commit's committer date — the moment the commit object was created in git, in the committer's local timezone with the offset preserved. From `git log --format=%cI`. **Deviation from V2 base timestamps** (which use ISO 8601 UTC) — committer-local time with offset is preserved because (a) git records it that way and re-deriving from UTC loses the offset signal, (b) the committer's timezone is informational signal (Doug works in `-04:00` / `-05:00`), and (c) chronological ordering still works correctly across timezones via lexicographic comparison of ISO 8601 strings. |
| `commit_repository` | TEXT | yes | — | non-empty trimmed; no whitespace; no path separators (`/`, `\`); no scheme prefix (`http://`, `git@`, etc.); no enum constraint — new repos added as encountered | The repository name only, not a full path. Current values in operation: `crmbuilder` (for `dbower44022/crmbuilder`) and `ClevelandBusinessMentoring` (for `dbower44022/ClevelandBusinessMentoring`, using the long form that matches the GitHub repository name per repo CLAUDE.md line 19-27). The methodology's DEC-187 conversation-scoped accounting unit principle places every record in the producing conversation's engagement database regardless of which physical repo it describes; this column distinguishes physical home from governance home. |
| `commit_branch` | TEXT | yes | `main` | non-empty trimmed; no whitespace; typical values `main` and rarely a feature branch name | The branch the commit was observed on at ingestion time. Almost always `main` in this project's operating pattern. Not a foreign-key into a branches table (no such table exists in v0.8); plain string column. If branch-pinning queries become operationally important, a future v0.9 may normalize. |
| `commit_files_changed_count` | INTEGER | yes | — | non-negative integer; `>= 0` | Count of files changed by this commit. From `git diff-tree --no-commit-id --name-only -r <sha> \| wc -l`. Captured as a denormalized scalar to avoid recomputing at audit time; the full path list is deferred to v0.9 (the methodology's deferred-fields list names `commit_files_changed_paths` for that purpose). Counts the file change events at the commit, not the line changes — a one-line edit in three files yields a count of 3. Zero is admissible for empty commits (e.g., `git commit --allow-empty`). |

**No `commit_committer_name` or `commit_committer_email`.** Per methodology §3.1's deferred-fields list: in this project's working pattern, the committer is practically always identical to the author (no patch-pipeline workflows where author and committer differ). Capturing both fields would double the storage with no informational gain. If a workflow emerges where author and committer materially differ, a future migration adds the columns.

**No `commit_signed_by`.** Per methodology §3.1's deferred-fields list: Doug's commits aren't currently signed (`git log --format=%G?` returns `N` for all observed commits). If commit signing is adopted in operation, a future migration adds the column.

**No `commit_message_trailers`.** Per methodology §3.1's deferred-fields list: parsed `Co-authored-by:`, `Signed-off-by:`, etc., are not currently used as governance metadata. The full message text is preserved in `commit_message_full`, so trailers can be parsed on demand from that column if a query ever needs them.

#### 3.2.6 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `commit_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. The moment the commit record was ingested into V2 (NOT the moment the commit was authored — that's `commit_committed_at`). The two are deliberately separate; `commit_committed_at` may be days or weeks earlier than `commit_created_at` for back-fill commits ingested in bulk. |
| `commit_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. Rarely updated for commits — the commit object in git is immutable, so the metadata captured here is effectively read-only. Updates are reserved for administrative correction (e.g., fixing a malformed `commit_message_first_line` truncation captured during back-fill). |
| `commit_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. Used for administrative correction of mis-ingestion (wrong repository attribution, wrong conversation linkage) — not for representing commits that were `git reset`-removed from a branch (those still exist in git's object database and remain valid governance records). |

**Deliberate separation of `commit_committed_at` and `commit_created_at`.** The two timestamps mean different things. `commit_committed_at` is the moment the commit object was created in git (committer-local time with offset). `commit_created_at` is the moment the V2 record was ingested (server-side UTC at apply time). The two are equal only when a commit is ingested at the same close-out as the one that produced it; for back-fill commits, `commit_committed_at` may be months or years before `commit_created_at`. Both are kept; neither is derivable from the other.

### 3.3 Relationships

#### 3.3.1 Outbound relationships from `commit`

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| (FK column, no relationship_kind value) | `commit` | `conversation` | foreign-key column (`commit_conversation_id`) | many-to-one (each commit has exactly one producing conversation; each conversation may produce zero or more commits) | The conversation that produced this commit per the Code Change Lifecycle methodology §3.1. Deviation from DEC-124's references-edge cross-spec precedent; rationale documented in §3.2.4. |
| `is_about` (existing kind) | `commit` | any governance entity type | references-table edge | many-to-many | Generic topical reference. Rare for commits outbound — the typical pattern is the producing conversation's references, not the commit's. May be used in administrative correction scenarios (e.g., "this commit is about PI-NNN even though its message doesn't say so explicitly"). |
| `references` (existing kind) | `commit` | any governance entity type | references-table edge | many-to-many | Generic citation. As rare outbound as `is_about` for the same reasons. |
| `supersedes` (existing kind) | `commit` | `commit` | references-table edge | one-to-one chronologically | Reserved for the administrative case where a re-ingested commit replaces a prior (mis-ingested) commit record for the same SHA. The prior record is soft-deleted; the new record carries the `supersedes` edge to the old. In normal operation, supersession does not occur — `commit_sha` UNIQUE rejects the second ingestion. |

#### 3.3.2 Inbound relationships to `commit` (declared by source-side specs)

`commit` is the target of inbound references from any governance entity type via the generic kinds. The Code Change Lifecycle methodology does not introduce any commit-specific inbound kinds (the methodology's three new kinds — `resolves`, `addresses`, `blocked_by` — target `planning_item`, not `commit`). Future workstreams may introduce targeted inbound kinds; this spec lists the inbound posture for cross-spec consistency-check purposes.

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `is_about` (existing kind) | any governance entity type | `commit` | references-table edge | many-to-many | Generic topical reference pointing at the commit. Used when a planning item, decision, session, or other governance record's narrative is specifically about a commit (e.g., a decision record that documents the rationale for a specific commit). |
| `references` (existing kind) | any governance entity type | `commit` | references-table edge | many-to-many | Generic citation pointing at the commit. Common case: a decision record's `rationale` text names a commit SHA. |
| `decided_in` (existing kind) | — | — | — | — | Not applicable — `decided_in` targets sessions, not commits. |

#### 3.3.3 Hierarchy

Commit does not use the V2 self-referential parent-child hierarchy pattern. A commit's parent-SHA list lives in the `commit_parent_shas` JSON column (§3.2.4); it is opaque scalar data, not a governance-record-to-governance-record edge. See §3.2.4's hierarchy paragraph for the deferred-introduction rationale.

#### 3.3.4 New reference vocabulary additions this spec requires

The following additions are needed for this spec. **This spec contributes one new entity type and zero new relationship-kind values.** The methodology's three new kinds (`resolves`, `addresses`, `blocked_by`) are owned by PI-029's migration, not by this entity-type-defining spec — they target `planning_item`, not `commit`, and their vocab.py registration belongs to PI-029 alongside the consolidated migration that PI-029 produces.

| Add to | Value | Rationale |
|--------|-------|-----------|
| `ENTITY_TYPES` | `commit` | This entity type. Required for the `_kinds_for_pair` function to admit `(commit, ...)` and `(..., commit)` pairs, and for the CHECK constraint on the `refs.source_type` and `refs.target_type` columns to permit values referencing commits. |
| `_kinds_for_pair` | (no new clauses required) | The existing same-type rule `if source_type == target_type: kinds.add('supersedes')` admits the rare `(commit, commit)` supersession edge once `commit` is in `ENTITY_TYPES`. The existing defaults for the generic `is_about` and `references` kinds admit all generic citations to and from commit without additional clauses. The methodology's three new kinds (`resolves`, `addresses`, `blocked_by`) require new `_kinds_for_pair` clauses for `(conversation, planning_item)`, `(work_ticket, planning_item)`, and `(planning_item, planning_item)` respectively, but those clauses are owned by PI-029, not by this spec. |

The build-planning conversation (here: PI-029) aggregates this contribution alongside the methodology's three new kinds into one consolidated `vocab.py` update plus one Alembic migration on `refs.relationship_kind`'s CHECK constraint. See the PI-029 Prompt A `CLAUDE-CODE-PROMPT-pi-029-A-commits-table-and-vocab.md` for the migration's full scope.

### 3.4 Lifecycle

#### 3.4.1 Status values

**None.** Commit has no status field. The entity either exists in the database or doesn't, with soft-delete-with-restore as the only state-change mechanism.

This is the **status-free documentary lifecycle** refinement of DEC-137 that this spec establishes as a new cross-spec precedent (see §1). DEC-137 (SES-050) established that documentary-shaped lifecycles inherit base timestamps only (no per-status lifecycle timestamps); reference_book — the precedent's original instance — still carries a three-value status field. Commit goes further: no status field, no transitions, no terminals. The justification: a git commit is an immutable observed fact. There is no `active` → `archived` analogue because a commit doesn't become inauthentic when its message is supplanted by a later commit (the two coexist in the DAG); there is no `superseded` analogue because git's reset/revert operations don't supersede commits, they add new commits. The absence of a meaningful workflow on the underlying artifact is the absence of a meaningful workflow on its governance record.

#### 3.4.2 Transition semantics

Not applicable in the conventional sense — there are no status transitions. The discipline established by DEC-125 (terminal-states-are-terminal) is preserved structurally: the absence of a status field is the strongest possible form of "no transitions, ever" — there is nothing to transition. Every cross-spec precedent that constrains transitions (DEC-125, DEC-143) is honored vacuously.

#### 3.4.3 Mis-ingestion correction posture

The rare path that needs handling: a commit was ingested with wrong metadata (most likely wrong `commit_conversation_id` attribution per methodology §5.6 — a manual commit Doug made between conversations was rolled into the wrong conversation; or wrong `commit_repository` if the helper's repo-detection logic is imperfect). Two correction mechanisms:

1. **Update** the existing record via PATCH. Most cases — fix the incorrect field, leave the record's `commit_identifier` and the SHA-based identity stable. The `commit_updated_at` timestamp captures the correction time. This is the path for any correction that doesn't change the commit's identity.

2. **Soft-delete and re-create** the record. Reserved for the case where the correction changes the entity identity (e.g., the wrong SHA was captured — an extremely rare case requiring a `supersedes` edge from the new record to the old, the old record's `commit_sha` becomes available for re-use, and the new record carries the correct SHA). The `supersedes` edge per §3.3.1 documents the relationship.

In both cases, the original `commit_sha`'s UNIQUE constraint prevents accidental duplicate ingestion. The administrative scenarios are rare enough that no dedicated dialog or workflow is built; the existing CRUD dialogs and reference-edit dialog handle them.

#### 3.4.4 Soft-delete semantics

Standard V2 base behavior:
- DELETE on `/commits/{identifier}` sets `commit_deleted_at` to the server's current UTC timestamp.
- Soft-deleted records do not appear in `GET /commits` list responses unless `?include_deleted=true` is supplied.
- Soft-deleted records still appear by direct fetch (`GET /commits/{identifier}` returns the record with `commit_deleted_at` populated).
- POST `/commits/{identifier}/restore` clears `commit_deleted_at` and returns the record to active status.
- The `commit_sha` UNIQUE constraint applies across all rows including soft-deleted rows. A second ingestion of the same SHA while the first is soft-deleted is rejected with HTTP 409; the appropriate path is to restore the original and patch its metadata.

#### 3.4.5 No append-only deviation

Commit deliberately does NOT adopt the deposit_event-style born-terminal append-only posture (DEC-156, SES-053). The two entity types appear similar — both record external-event facts with no workflow lifecycle — but they differ in administrative-correction need:

- A `deposit_event` records a one-time apply attempt with a permanent success/failure outcome; the apply happened or it didn't, and the record's content is determined by the apply's actual behavior. There is no correction path because there is nothing to correct — the apply behaved as it behaved.
- A `commit` records a git object's metadata as observed at ingestion. The metadata capture may be wrong (helper bugs, manual back-fill errors, attribution mistakes) even when the underlying git object is fine. Soft-delete-with-restore preserves the correction path; born-terminal append-only would forbid it.

The asymmetry justifies the asymmetric lifecycle posture. Future entities follow whichever precedent matches their correction-need profile.

### 3.5 API surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/commits` | — | List with `?include_deleted=true` flag, `?commit_repository=<name>` filter, `?commit_conversation_id=<id>` filter, standard pagination, default sort `commit_committed_at` descending. |
| GET | `/commits/{identifier}` | — | Single fetch by `CM-NNNN` V2 identifier. Returns soft-deleted records with `commit_deleted_at` populated. |
| GET | `/commits/by-sha/{sha}` | — | **New natural-key lookup endpoint.** Accepts full 40-character SHA or a prefix of any length 4+. Full SHA: returns the single matching record or 404. Unambiguous prefix: returns the single matching record. Ambiguous prefix: returns HTTP 409 with a JSON body listing the candidate matches as `{"data": null, "meta": ..., "errors": [{"code": "ambiguous_sha_prefix", "candidates": ["<sha-1>", "<sha-2>", ...]}]}`. Miss: returns HTTP 404. Soft-deleted records are NOT included in the by-sha lookup unless `?include_deleted=true` is supplied. The endpoint pattern is the new cross-spec precedent this spec establishes (§1). |
| GET | `/commits/next-identifier` | — | Returns the next available `CM-NNNN` identifier as `{"data": {"identifier": "CM-NNNN"}}`. Exposed for symmetry with other governance entities; the apply script's batch path computes identifiers client-side via list-and-increment instead per the client-side-assignment posture in §3.1. |
| POST | `/commits` | full record body including `commit_identifier` | Create. Identifier required in body per the client-side-assignment convention. The `commit_conversation_id` field's referent (the named conversation) must exist; the access layer validates and returns HTTP 422 `{"error": "commit_conversation_id_not_found", "value": "<value>"}` if the conversation does not exist. The `commit_sha` field must be unique across all commits in the engagement (including soft-deleted); HTTP 409 `{"error": "commit_sha_duplicate", "existing": "<existing-CM-identifier>"}` on collision. |
| PATCH | `/commits/{identifier}` | partial record body | Partial update. The `commit_identifier` and `commit_sha` fields are not updatable via PATCH (they define the record's identity); attempts return HTTP 422 `{"error": "field_not_updatable", "field": "commit_identifier"}` or `"commit_sha"`. Other fields including `commit_conversation_id` are updatable for the administrative correction path (§3.4.3). The `commit_updated_at` timestamp is set server-side on every successful PATCH. |
| PUT | `/commits/{identifier}` | full record body | Full replace. Same identity-field rules as PATCH; same access-layer validations as POST. |
| DELETE | `/commits/{identifier}` | — | Soft-delete per §3.4.4. Sets `commit_deleted_at`; the record is preserved. |
| POST | `/commits/{identifier}/restore` | — | Clears `commit_deleted_at` and returns the record to active status. Returns the restored record. |

All responses use the standard `{data, meta, errors}` envelope per V2 convention (`crmbuilder-v2/src/crmbuilder_v2/api/envelope.py`).

#### 3.5.2 Identifier auto-assignment behavior

Per §3.1: client-side assignment via list-and-increment on `GET /commits`, in the body of POST. The helper endpoint `GET /commits/next-identifier` is exposed for symmetry but is **not** the apply script's mechanism. The apply script's batch ingestion path:

1. `GET /commits` (or with `?commit_repository=<name>` filter for a single repo's batch) to retrieve the existing identifiers.
2. Compute the next-after-highest identifier in `CM-NNNN` format.
3. For each commit in the close-out payload's `commits` section, increment the identifier and POST.

The race window: another writer (UI, a parallel apply, etc.) could increment between step 2 and step 3. The apply script's reaction: catch HTTP 422 `{"error": "identifier_collision"}` on POST, re-fetch the head, recompute, retry. The path is described in the apply prompt's pre-flight and is consistent with the pattern other prefixed-identifier apply paths use.

#### 3.5.3 Identifier-format note for the next-identifier helper

The `next-identifier` helper must produce four-digit zero-padded identifiers (`CM-NNNN`), not three-digit (`CM-NNN`). The width is locked at four for this entity type by §3.1. The helper implementation reads the highest existing identifier, increments, and zero-pads to four. The first commit ingested at backfill is `CM-0001`.

### 3.6 User interface considerations

#### 3.6.1 Sidebar position

Commits panel under the existing "Governance" sidebar group in the V2 desktop UI, ordered after the six v0.7 governance entities (`workstream` → `conversation` → `reference_book` → `work_ticket` → `close_out_payload` → `deposit_event` → **`commit`**). Final layout details — including whether the Governance group's growing entry count (now seven) warrants a sub-grouping or vertical reorganization — are deferred to PI-031 build planning. The default-position declaration here is the convention; the build-planning conversation may overrule per the spec guide §3.6 default-with-deviation pattern.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list following the existing v0.7 governance panel conventions:

- **Columns** (default left-to-right): `commit_identifier`, `commit_repository`, `commit_message_first_line`, `commit_author_name`, `commit_committed_at`.
- **Default sort**: `commit_committed_at` descending (most recent commits first — the operational pattern for "what just happened" queries, parallel to deposit_event's deviation from the V2 default ascending sort per the audit-log nature of the entity).
- **Toolbar additions** (natural addition paralleling `reference_book.md` and `work_ticket.md`):
  - **Repository filter combo** ("All / crmbuilder / ClevelandBusinessMentoring / [any other repos that appear in data]") populated from the distinct values in `commit_repository`. The "All" option is the default selection.
  - **Conversation filter combo** ("All / [list of conversations that have produced at least one commit]") populated from the distinct values in `commit_conversation_id`. Optional for v0.8; the build-planning conversation decides whether the affordance is worth the dropdown space.
- **Right-click context menu**: New / Edit / Delete / Restore matching v0.3 patterns. The New affordance is hidden by default for typical operators since commits are ingested at close-out apply rather than authored in the UI; the menu item is reserved for the rare administrative-correction case where a missing commit needs to be backfilled manually.

#### 3.6.3 Detail pane

Vertical layout matching the v0.7 governance detail-pane convention:

- Identity section: `commit_identifier` (read-only), `commit_sha` (read-only after creation), `commit_repository`, `commit_branch`.
- Content section: `commit_message_first_line`, `commit_message_full` (multi-line text area, read-only by default — administrative correction is the rare path).
- Authorship section: `commit_author_name`, `commit_author_email`, `commit_committed_at` (all read-only after creation).
- Statistics section: `commit_files_changed_count`, `commit_parent_shas` (rendered as a comma-joined list of short-SHA prefixes for readability, with click-to-copy on each).
- Relationships section: `commit_conversation_id` rendered as a clickable link to the conversation detail panel. Standard `ReferencesSection` widget below the FK link for any `is_about`/`references`/`supersedes` edges authored against this commit.
- Timestamps section: `commit_created_at`, `commit_updated_at`, `commit_deleted_at` (if soft-deleted).

#### 3.6.4 Create dialog

`EntityCrudDialog` subclass for the rare administrative-correction case. Fields match the field-order convention with `commit_identifier` auto-assigned (read-only in create mode); all other fields editable. The typical operator does not invoke this dialog — commits are created by apply scripts at close-out time. The dialog is built so the affordance exists; usage is expected to be rare enough that no special "bulk create" or "import from git" affordance is added in v0.8 (the helper that does that is the apply path, not the dialog).

#### 3.6.5 Edit dialog

Same shape as create; identity fields (`commit_identifier`, `commit_sha`) read-only. The administrative-correction path runs through this dialog when a PATCH is the appropriate mechanism (vs. soft-delete-and-recreate per §3.4.3).

#### 3.6.6 Delete dialog

Standard `EntityCrudDeleteDialog` with edge-text confirmation matching v0.3 patterns. The dialog clarifies that soft-delete is reversible via the Restore affordance and that the underlying git object is unaffected (soft-deleting a commit record does not delete the commit from git).

### 3.7 Acceptance criteria

This entity type is correctly implemented in the eventual build (PI-029, PI-030, PI-031) when:

1. **Schema migration applies cleanly.** The Alembic migration produced by PI-029 adds the `commits` table to an existing CRMBuilder engagement database without conflict; running it on a database that already has v0.7 governance tables succeeds with no manual reconciliation.

2. **`commit` entity-type registration round-trips.** `commit` is in `ENTITY_TYPES` per `vocab.py`; the CHECK constraint on `refs.source_type` and `refs.target_type` admits `'commit'` values; the `_kinds_for_pair` function returns the expected kind set for every `(commit, X)` and `(X, commit)` pair (generic `is_about`, `references`, plus `supersedes` for same-type).

3. **Identifier auto-assignment helper returns next identifier in `CM-NNNN` format.** `GET /commits/next-identifier` returns `{"data": {"identifier": "CM-0001"}}` against an empty commits table and returns `CM-0002` after one commit has been ingested. The width is exactly four digits (verifies the §3.1 width-locking).

4. **Identifier collision is rejected on POST.** POSTing a commit with `commit_identifier` equal to an already-existing identifier (active or soft-deleted) returns HTTP 422 with the standard `identifier_collision` error envelope.

5. **`commit_conversation_id` FK existence is enforced.** POSTing a commit with `commit_conversation_id` referencing a non-existent conversation returns HTTP 422 `{"error": "commit_conversation_id_not_found"}`. POSTing with no `commit_conversation_id` returns the standard request-validation error (the field is required).

6. **`commit_sha` validation is enforced.** POSTing with a SHA of incorrect length (39, 41, etc.) returns HTTP 422. POSTing with uppercase hex characters (`ABC123...`) returns HTTP 422 (lowercase enforced). POSTing with non-hex characters (`g`, `z`, etc.) returns HTTP 422.

7. **`commit_sha` uniqueness is enforced across the engagement (including soft-deleted).** A second POST with the same SHA returns HTTP 409 `{"error": "commit_sha_duplicate", "existing": "<existing-CM-identifier>"}`, and the response identifies which existing record holds the SHA. Soft-deleted records' SHAs are included in the uniqueness check.

8. **`commit_parent_shas` array-shape validation is enforced.** POSTing with `commit_parent_shas` of length 3 or more returns HTTP 422. POSTing with an element that fails the per-element SHA regex returns HTTP 422. Empty arrays (initial commit) and single-element arrays (normal commit) and two-element arrays (merge commit) all POST successfully.

9. **`commit_repository` validation is enforced.** POSTing with empty, whitespace-only, or path-separator-containing values returns HTTP 422. New repository names (not in any existing record) are admitted without enum validation — the column has no enum constraint per §3.2.5.

10. **`GET /commits/by-sha/{sha}` natural-key lookup behaves correctly across all four cases.** Full SHA hit returns the single record. Unambiguous prefix hit (e.g., 8-character prefix matching exactly one record) returns the single record. Ambiguous prefix returns HTTP 409 with the candidate-SHA list in the error body. SHA miss returns HTTP 404. The endpoint excludes soft-deleted records by default; `?include_deleted=true` includes them.

11. **Soft-delete and restore cycle round-trips.** DELETE on a commit returns success and sets `commit_deleted_at`. Subsequent `GET /commits` (without `?include_deleted=true`) does not include the record. `GET /commits/{identifier}` directly returns the record with `commit_deleted_at` populated. POST `/commits/{identifier}/restore` clears `commit_deleted_at`; the record reappears in subsequent list endpoints.

12. **Commits panel appears in the Governance sidebar group in the correct position.** The panel renders after the six v0.7 governance entries in the order specified in §3.6.1. The master pane shows the columns specified in §3.6.2 with the default sort applied (descending by `commit_committed_at`). The Repository filter combo populates from distinct values in the data and filters the list when changed.

13. **Sample governance records can be authored.** A small test set of governance records — say, five commits attached to two conversations across both repositories — can be created either via the apply path (POSTing through the apply script's batch mechanism) or via the Create dialog (administrative correction path), and after creation each commit appears in the master pane with the expected metadata; each commit's detail pane renders all fields including the FK link to the producing conversation and any references in the `ReferencesSection` widget.

### 3.8 Open questions and deferred decisions

#### 3.8.1 Derived endpoint URL shapes [for build-planning]

Beyond the standard endpoint set, candidate derived endpoints include `GET /conversations/{conversation_identifier}/commits` (list all commits produced by a specific conversation) and possibly `GET /workstreams/{workstream_identifier}/commits` (list every commit produced by any conversation belonging to the workstream). The first can be done via `GET /commits?commit_conversation_id=<id>` against the standard list endpoint; the derived endpoint just provides a more discoverable URL. The second requires either a two-hop query (workstream → conversations → commits) at the endpoint or denormalization of the workstream linkage onto the commits table; the choice is a build-time decision that benefits from cross-entity visibility. Deferred to PI-029 build planning.

#### 3.8.2 SHA-256 migration anticipation [for retroactive backfill or future user-interface version]

Git is in the early stages of a SHA-256 migration; some repositories and tooling have begun emitting 64-character SHA values. The schema's `commit_sha` validation locks 40-character SHA-1 for v0.8. When SHA-256 becomes operationally relevant — either because a tracked repository adopts it or because a tooling change in git's default makes mixed-mode unavoidable — the validation must widen to `^[0-9a-f]{40}$|^[0-9a-f]{64}$` and the UNIQUE INDEX may need partitioning (a commit's SHA-1 and its SHA-256 are different values referring to the same object). The migration is a forward-compatible additive widening of the regex with no breakage of existing 40-character data. Deferred to v0.9 or later pending real-use signal; flagged here so future readers know the anticipation has been made.

#### 3.8.3 `commit_author_kind` attribution discipline [for future user-interface version]

Methodology §5.6 names this as a candidate v0.9 addition: a `commit_author_kind` enum with values `claude_ai`, `claude_code`, `manual` to distinguish commits Claude made in sandbox conversations from commits Claude Code made at Doug's terminal from commits Doug hand-typed between conversations. The simplification adopted in v0.8 is that every commit in a conversation's range is attributed to the close-out's conversation regardless of physical authorship; if attribution discipline becomes a problem (e.g., Doug's between-conversation manual commits are skewing audit reports), the enum is one additive migration away. The methodology document defers; this spec defers by reference.

#### 3.8.4 Branch-pinning queries [for retroactive backfill]

`commit_branch` is captured as a plain string (almost always `main`). If queries like "show me every commit on the `feature-X` branch" become operationally important — which would require deeper branch metadata than this spec captures — a future schema update normalizes branches into a separate table with proper FK linkage. The v0.8 simplification (string column, no enum constraint, no FK) covers the dominant `main`-everywhere pattern adequately.

#### 3.8.5 Sub-grouping in the Governance sidebar [for build-planning]

The Governance sidebar group now has seven entries (six v0.7 entities plus commit). The spec guide §3.6 notes that the build-planning conversation may introduce a sub-grouping if the group becomes hard to scan. PI-031 makes the call; this spec's default-position declaration assumes a single flat group continues. If sub-grouping is adopted, a natural division is "Governance — workstreams" (workstream, conversation) / "Governance — artifacts" (reference_book, work_ticket, commit) / "Governance — apply" (close_out_payload, deposit_event). The decision is deferred.

### 3.9 Cross-references

#### 3.9.1 Decisions authored by this conversation

- **DEC-198 — Commit lifecycle is documentary and status-free; refines DEC-137.** Adopts a status-free documentary lifecycle (no `commit_status` field, no transitions, no terminals; soft-delete-with-restore as the only state-change mechanism). Refines DEC-137 (documentary-shaped lifecycles inherit base timestamps only) by permitting the absence of a status field entirely when no operationally meaningful states exist. Rejects the alternative of carrying a placeholder `commit_status` enum with values like `active`/`reverted` on the grounds that revertedness is not v0.8-scoped and a placeholder column with no semantics adds noise. Locks the precedent as MAY-not-MUST: future documentary entities with even a two-status distinction (e.g., active/archived) follow reference_book's precedent rather than this one.

- **DEC-199 — `commit_conversation_id` modeled as a foreign-key column, not a references-edge; deviation from DEC-124 on frequency-justified-denormalization grounds.** Adopts the FK column per the methodology's §3.1 field table and §6 audit-query JOINs. Articulates the deviation from DEC-124's cross-spec precedent (references-edge over FK for parent-child governance relationships) with three justifications: frequency of traversal (every audit query walks commit→conversation; the JOIN cost compounds linearly with commit count), cardinality (every commit has exactly one producing conversation, which FK + NOT NULL expresses cleanly), and DEC-187 reinforcement (the conversation-scoped accounting unit principle makes ownership mandatory by the model, and FK enforces mandatory ownership at the schema level). Rejects the references-edge alternative on the grounds that the access-layer rule needed to make the relationship mandatory under references-edge is more machinery for the same outcome.

- **DEC-200 — Commit spec establishes four new cross-spec precedents.** (a) Status-free documentary lifecycles as a refinement of DEC-137 — see DEC-198. (b) Natural-key lookup endpoints via `GET /{plural}/by-{key}/{value}` — introduced by `GET /commits/by-sha/{sha}` for SHA-based commit lookup; precedent generalizes to any future entity with a strong natural key distinct from its V2 identifier. (c) JSON-array columns for variable-cardinality scalar lists — introduced by `commit_parent_shas`; precedent generalizes to any 0-to-N scalar list that doesn't warrant a separate normalized table. (d) Conversation-scoped accounting unit principle as a cross-spec precedent — restating DEC-187 (settled by methodology authoring at SES-061) in spec-inheritable form; physical home and governance home are independent, with the governance home always being the producing conversation's engagement database. Rejects the conservative alternative of elevating zero new precedents on the grounds that successor governance specs benefit from named precedents to inherit, and the four named above are each likely to recur (the by-sha pattern especially when future entity types appear).

#### 3.9.2 Related schemas and other PRD documents

- `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` v1.0 — the authoritative methodology this spec implements. §3.1 (commit v0.8 field inventory), §6 (audit query patterns), §3.4 (the four new close-out payload sections), and DEC-183 through DEC-190 (foundation decisions) are the direct sources for this spec's substance.
- `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` v1.0 — the schema-spec template this spec follows. §3 (required sections), §6 (cross-spec consistency requirements), §7.1 (per-spec completeness gate) are the structural constraints.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/work_ticket.md` v1.0 — closest existing precedent (closed-enum classification, similar audit-grain role, documentary-vs-workflow boundary discussion in §1). The cross-spec-precedent-inheritance pattern in §1 of this spec follows work_ticket's §1 structure.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/reference_book.md` v1.1 — DEC-137 source (documentary-shaped lifecycle precedent), refined by DEC-198 here.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/deposit_event.md` v1.0 — closest non-precedent comparison (born-terminal append-only with no status, similar event-shape to commit). The boundary discussion in §2 of this spec cites the differences.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/conversation.md` v1.0 — target of the FK on `commit_conversation_id`. The `conversation` entity's `conversation_identifier` is the value the FK column holds.
- `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — engagement isolation; commit records live per-engagement, per DEC-187's conversation-scoped accounting unit principle.
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — `ENTITY_TYPES` and `_kinds_for_pair` registration; this spec contributes `commit` to `ENTITY_TYPES` and no new relationship-kind entries. PI-029's migration registers the methodology's three new kinds (`resolves`, `addresses`, `blocked_by`) separately.

#### 3.9.3 Foundation decisions this spec extends

- **DEC-183** — Commit identifier shape `CM-NNNN`. **Directly extended.** This spec locks the four-digit width and the client-side assignment posture in §3.1.
- **DEC-184** — `commit` as the entity type name and `CM` as the identifier prefix. **Directly extended.** §3.1 confirms the prefix collision check.
- **DEC-185** — `commit_sha` as the natural-key UNIQUE INDEX. **Directly extended.** §3.2.1 validates the SHA format; §3.5.1 introduces the `GET /commits/by-sha/{sha}` lookup endpoint.
- **DEC-186** — v0.8 field inventory (fourteen substantive columns plus three governance-standard timestamps). **Directly extended.** §3.2 renders the inventory verbatim into the standard field-table format.
- **DEC-187** — Conversation-scoped accounting unit principle (every record produced by a conversation belongs to that conversation's engagement database). **Directly extended.** The FK on `commit_conversation_id` enforces the principle at the schema level (DEC-199); the conversation-scoped accounting unit principle is restated as a new cross-spec precedent in DEC-200.
- **DEC-188** — Three new relationship-kinds added by the methodology (`resolves`, `addresses`, `blocked_by`). **Not directly extended.** Those kinds target `planning_item`, not `commit`; their registration belongs to PI-029's migration, not to this spec.
- **DEC-189** — Broad work_ticket authoring rule (every single-use seed document committed to either repo is born as a work_ticket record in the same close-out payload). **Not directly extended.** The rule applies to this spec's kickoff document (`schema-design-kickoff-commit.md`) which was authored as a work_ticket in SES-061's close-out; this spec does not modify the rule.
- **DEC-190** — Default close-out payload section ordering and apply-script dependency graph. **Not directly extended.** The ordering is owned by PI-030's apply-script extension, not by this entity-defining spec.

#### 3.9.4 Related prior decisions informing this spec

- **DEC-013** — Decisions and sessions are append-only and immutable. Informs this spec's choice NOT to adopt append-only for commit. Decisions and sessions are governance content authored deliberately and immutable by design; commits are observed facts about external objects whose ingestion may need correction. The asymmetry justifies the different posture.
- **DEC-031** — Reference rendering generalized via shared `ReferencesSection` widget. Directly informs the detail pane reference rendering in §3.6.3.
- **DEC-033** — Cascading reference create dialog driven by strict vocab. The `(commit, X)` and `(X, commit)` pairs flow through the existing dialog once `commit` is in `ENTITY_TYPES`.
- **DEC-035** — `ListDetailPanel` master-widget plus context-menu factory refactor. Informs the master pane patterns in §3.6.2 including the Repository column and the Repository filter combo.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs the §3.6.2 context-menu behavior.
- **DEC-046** — Parent-prefix field-naming convention. Inherited and applied throughout (all fields prefixed `commit_`).
- **DEC-048** — Source-first `{source}_{verb}_{target}` relationship-kind naming. Inherited; would apply to any new typed kind this spec might have introduced, but the spec introduces zero new typed kinds.
- **DEC-115 / DEC-116** — Per-engagement isolation architecture. `commit` records live in the per-engagement SQLite file; the CRMBuilder dogfood engagement is where this entity type's first records land.
- **DEC-117** — Track workflow files as three purpose-built entity-type families. Not directly extended — commit is a fourth family (the git-commit-as-governance-record family) that DEC-117 did not anticipate. DEC-117's families remain workflow files (kickoffs and prompts); commit covers a different class of artifact entirely (git objects). The fourth-family-introduction is implicit in this spec's authoring; no DEC-117 amendment is needed because the families are independent.
- **DEC-123 through DEC-128** (SES-048, workstream schema). DEC-124's references-edge precedent is deviated from with rationale (see DEC-199). DEC-125's truly-terminal discipline is preserved structurally (no status field, hence no terminals). DEC-126's per-status timestamps are not applicable (no statuses). DEC-127's flat-catalog posture is structurally analogous (no sub-categorization of commits). DEC-128's standard-defaults posture is what this spec uses for soft-delete behavior and acceptance-criteria framing.
- **DEC-129 through DEC-134** (SES-049, conversation schema). DEC-133's typed-sequencing-frequency-justified precedent is applied on this spec's facts to defer typed `commit_parents_commit` and accept the JSON-array column instead.
- **DEC-135 through DEC-140** (SES-050, reference_book schema). DEC-137's documentary-vs-workflow distinction is the precedent this spec refines (see DEC-198 and the new cross-spec precedent in §1). DEC-139's repo-relative file path semantics are not directly applicable (commit has no file-path field; the artifact lives in git, not in the repo's filesystem at a path).
- **DEC-141 through DEC-146** (SES-051, work_ticket schema). DEC-143's terminal-state consumption requires inbound consumption edge precedent is not applicable (no terminal state). DEC-145's closed-enum kind taxonomy is not applicable (no kind field).
- **DEC-147 through DEC-152** (SES-052, close_out_payload schema). DEC-149's workflow-shaped lifecycle is not applicable. No directly applicable inheritance beyond what SES-048..050 already established.
- **DEC-153 through DEC-158** (SES-053, deposit_event schema). DEC-156's born-terminal append-only precedent is not adopted (this spec uses soft-delete-with-restore instead, see §3.4.5). DEC-158's multi-event-per-target-record under born-terminal append-only is not applicable.

#### 3.9.5 Predecessor and successor conversations

- **Predecessor:** SES-061 — methodology drafting conversation (PI-027). Produced `methodology-code-change-lifecycle.md` v1.0, which settles DEC-183 through DEC-190 and names PI-028 (this conversation) as the planning item that produces this spec. Authored the kickoff for this conversation (`schema-design-kickoff-commit.md`) as a work_ticket record per the broad work_ticket authoring rule (DEC-189).
- **Successor:** PI-029 — schema migration and access layer for commit (Claude Code execution). First prompt in the multi-prompt series at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-A-commits-table-and-vocab.md`. Inherits this spec's specification verbatim and produces: the Alembic migration adding the `commits` table; the vocab.py update adding `commit` to `ENTITY_TYPES`; the access-layer methods for commit CRUD; the REST endpoints; the `apply_close_out.py` integration for the future `commits` close-out-payload section that PI-030 enables. Subsequent prompts (B, C, ...) in the PI-029 series emerge from the build-planning approach taken in PI-028's close-out.

---

*End of document.*
