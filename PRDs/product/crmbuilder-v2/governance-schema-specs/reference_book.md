# Governance Entity Schema Spec — `reference_book`

**Last Updated:** 05-21-26 15:30
**Status:** Draft v1.1 — produced by schema-design conversation; v1.1 audit correction to kind-enum provenance narration
**Position in workstream:** Third of six governance-entity schema specs (`workstream` → `conversation` → `reference_book` → `work_ticket` → `close_out_payload` → `deposit_event`)
**Predecessor conversation:** SES-049 (`conversation` schema-design conversation)
**Successor conversation:** `work_ticket` schema design — kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-work-ticket.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-21-26 14:50 | Doug Bower / Claude | Initial draft. Produced by the third schema-design conversation in the governance-entity schema-design workstream. Adopts the four cross-spec precedents now in force: the three from SES-048 (references-edge over foreign-key for parent-child governance relationships, per-status lifecycle timestamps for workflow-shaped lifecycles, terminal-states-are-terminal discipline) plus the one from SES-049 (typed sequencing edges introduced when entity-family frequency justifies). Establishes a new cross-spec precedent of its own: documentary-shaped lifecycles inherit base timestamps only — the per-status lifecycle timestamps from DEC-126 apply only to workflow-shaped lifecycles, and the distinction is made explicit here for the remaining three downstream specs to apply on their own facts. Introduces the parent record + child versions table versioning pattern as the canonical documentary-entity versioning shape — lighter than the charter/status singleton-with-payload pattern because the file content itself lives in git and the database tracks version metadata only. Adds no new relationship-kind vocabulary — every inbound and outbound edge it requires was pre-declared by workstream.md or is admitted by the existing generic kinds. |
| 1.1 | 05-21-26 15:30 | Doug Bower / Claude | Post-audit correction. The three provenance-narration paragraphs in the Change Log, the DEC-138 description in §3.9.1, and the DEC-117 entry in §3.9.3 incorrectly named the three `reference_book_kind` values that are additions beyond DEC-117's seven artifacts as `workstream_master_plan`, `apply_script`, `session_startup_document`. Per the DEC-117 decision record, those three values are part of DEC-117's seven; the actual additions beyond DEC-117 are `architecture_document`, `conduct_framework`, `investigation_report`. Three text substitutions reconcile the narration with the enum. The eleven-value enum declaration in §3.2.3 was correct in v1.0 and is unchanged. No design or semantic substance is affected; this is a provenance-narration correction only, identified by the SES-050 audit pass before close-out apply. |

---

## Change Log

**Version 1.1 (05-21-26 15:30):** Post-audit correction. The three provenance-narration paragraphs in this Change Log section, the DEC-138 description in §3.9.1, and the DEC-117 entry in §3.9.3 incorrectly named the three `reference_book_kind` values that are additions beyond DEC-117's seven artifacts as `workstream_master_plan`, `apply_script`, `session_startup_document`. Per the DEC-117 decision record (`db-export/decisions.json`), those three values are explicitly listed in DEC-117's seven; the actual additions beyond DEC-117 are `architecture_document`, `conduct_framework`, `investigation_report`. Three text substitutions reconcile the narration with the enum. The eleven-value enum declaration in §3.2.3 line 93 was correct in v1.0 and is unchanged. No design or semantic substance is affected. The correction was identified by the SES-050 audit pass before close-out apply.

**Version 1.0 (05-21-26 14:50):** Initial creation. Defines `reference_book` as the V2 governance entity type that hosts the long-lived versioned workflow file concept — Product Requirements Documents, implementation plans, workstream master plans, methodology guides, architecture documents, schema specifications, conduct framework documents, investigation reports, apply scripts, session-startup entry documents, and other multi-consumer reference files per DEC-117's first family. Establishes seven content/classification fields (`reference_book_identifier`, `reference_book_title`, `reference_book_description`, `reference_book_notes`, `reference_book_kind`, `reference_book_status`, `reference_book_file_path`) plus two denormalized version-pointer columns (`reference_book_current_version_label`, `reference_book_current_version_date`) plus three inherited base timestamps — no per-status lifecycle timestamps because the lifecycle is documentary-shaped, not workflow-shaped. Establishes a sibling child table `reference_book_versions` carrying one row per known version of a reference book (`version_label`, `version_date`, `version_summary`, plus base timestamps), with `(reference_book_id, version_label)` unique. Three-status documentary lifecycle (`active` → `archived` / `superseded`) with terminal-states-terminal discipline inherited from workstream and a supersession-requires-edge rule mirroring workstream's pattern. Adopts a closed eleven-value kind enum covering all seven of DEC-117's reference-book artifacts plus three more observed in the project's operating history (`architecture_document`, `conduct_framework`, `investigation_report`) and a sentinel `other` value. No new relationship-kind vocabulary required — every needed edge was pre-declared by workstream.md (`workstream_planned_in_reference_book` inbound) or is admitted by the existing generic `references` / `is_about` / `supersedes` kinds. Standard API endpoint set plus three version-management sub-endpoints (`GET /reference-books/{id}/versions`, `POST /reference-books/{id}/versions`, `GET /reference-books/{id}/version-at?as_of=...`) realizing the in-force-at-time-T semantics named in the kickoff. Default soft-delete with restore, explicitly distinct from `archived` status (which is a lifecycle outcome) and `superseded` status (which is a successor-replaced outcome). Default UI layout with two natural additions: a Kind column in the master pane and an inline version-history section in the detail pane. Sixteen acceptance criteria captured. Six decisions and zero planning items authored at conversation close (PI-022 covers retroactive backfill for reference book records as it does for the other governance entity types).

---

## 1. Purpose and Position

This document specifies the `reference_book` entity type for V2's storage layer. It is the **third of six** schema specs produced by the governance-entity schema-design workstream — designed after `workstream.md` and `conversation.md` so that the workstream entity's master-plan linkage and the conversation entity's outgoing generic-references posture are settled referents.

The workstream is governed by `governance-schema-workstream-plan.md`. Each schema spec conforms to the template in `governance-entity-schema-spec-guide.md`. Six specs total are produced — `workstream`, `conversation`, then `reference_book`, `work_ticket`, `close_out_payload`, `deposit_event` — feeding a seventh build-planning conversation that integrates them into a coherent release.

`reference_book`'s primary scope in this release is to host the long-lived versioned workflow file concept per DEC-117's first family — the documents the project cites repeatedly across conversations over their lifetimes. The kickoff lists representative examples already in the project's operating history: the Product Requirements Documents (`ui-PRD-v0.1.md` through `ui-PRD-v0.6.md`, `storage-system-PRD-v0.1.md`, `catalog-ingestion-PRD-v0.1.md`); the implementation plans; the workstream master plans (`methodology-schema-workstream-plan.md`, `v0.5-engagement-management-workstream-plan.md`, `governance-schema-workstream-plan.md`); the methodology guides (`methodology-entity-schema-spec-guide.md`, `governance-entity-schema-spec-guide.md`); architecture documents (`multi-engagement-architecture.md`); the schema specifications themselves (`methodology-schema-specs/*.md` and the forthcoming `governance-schema-specs/*.md`); the conduct framework documents (`PRDs/process/conduct/charter.md`, `kickoff.md`, `question-library.md`); investigation reports retained for reference (`multi-tenancy-routing-investigation-report.md`); the apply scripts; and the session-startup entry documents themselves (`crmbuilder/CLAUDE.md`).

The schema is intentionally minimum-viable. Per-section content extraction, full-text search, file-watch refresh inside the dialog, and content blob storage in the database are deliberately out of scope; each is deferred to a future release pending real-use signal.

This conversation **inherits four cross-spec precedents now in force** and applies them throughout:

- **References-edge over foreign-key for parent-child governance relationships** (DEC-124, SES-048). Reference book's relationships to other governance entities live in `refs`, not as foreign-key columns. Every inbound and outbound edge follows.
- **Per-status lifecycle timestamps for workflow-shaped lifecycles** (DEC-126, SES-048). This spec **deviates** from this precedent — see the new precedent below for the justification.
- **Terminal-states-are-terminal discipline** (DEC-125, SES-048). Reference book's two terminal statuses (`archived`, `superseded`) admit no transitions out. Reactivation of an archived reference book is modelled as a new reference book that supersedes the prior, or as administrative restoration of the prior via the soft-delete restore path.
- **Typed sequencing edges introduced when entity-family frequency justifies** (DEC-133, SES-049). Reference book applies this precedent and **does not introduce** a typed sequencing kind. Reference book versions are sequenced within a single reference book via the child versions table; sequencing across distinct reference book records is rare (multi-document phase plans are the only observed case) and folds adequately into supersession or into free-text description; no `reference_book_succeeds_reference_book` kind is required.

This conversation also **establishes one new cross-spec precedent** the remaining three schemas inherit by default and may deviate from with rationale:

- **Documentary-shaped lifecycles inherit base timestamps only.** Reference book's lifecycle is documentary, not workflow — there is no meaningful timeline of "when did this reach status X" beyond `updated_at` because the lifecycle states (`active`, `archived`, `superseded`) carry no per-state duration semantics worth querying. The per-status lifecycle timestamps precedent from DEC-126 applies only to workflow-shaped lifecycles (workstream, conversation). The remaining three governance specs (`work_ticket`, `close_out_payload`, `deposit_event`) apply the workflow-vs-documentary distinction on their own facts: work_ticket has a workflow-shaped consumption lifecycle (drafted → ready → in-use → consumed) and inherits per-status timestamps; close_out_payload is likely workflow-shaped (drafted → applied) or append-only after apply; deposit_event is append-only with one timestamp. None of the three is documentary-shaped.

---

## 2. Summary

A `reference_book` record in V2 represents one long-lived versioned workflow file — a file that lives in the repo, accrues versions over its lifetime, and is cited repeatedly by other governance records as an authoritative source. Real examples already implicit in the project's history at this spec's authoring time include the `multi-engagement-architecture.md` document (cited by every workstream-establishing kickoff prompt and by the workstream and conversation schema specs); the `methodology-schema-workstream-plan.md` (cited by all four methodology-entity schema-design conversations as their workstream master plan); the `methodology-entity-schema-spec-guide.md` (the template all four methodology schemas followed); the `governance-schema-workstream-plan.md` (the workstream master plan governing this and the next three conversations); the `governance-entity-schema-spec-guide.md` (the template this document follows); the `governance-schema-specs/workstream.md` and `governance-schema-specs/conversation.md` documents (the predecessor schema specs cited by this conversation as inherited cross-spec precedent sources); the `PRDs/process/conduct/charter.md`, `kickoff.md`, and `question-library.md` documents (the conduct framework documents cited at every stakeholder-facing interview); and the project's `crmbuilder/CLAUDE.md` itself (the session-startup entry document read at the open of every Claude conversation). Each is structurally a multi-consumer versioned reference file — but before this entity type lands, each exists only as a path string on the filesystem and a citation in document text.

The schema in this release is the thinnest shape that captures the documentary-reference concept faithfully: a human-readable title, a paragraph description, an optional consultant notes field, a closed kind classification, a three-status documentary lifecycle, a repo-relative file path string, a denormalized pointer to the current version label and date, references-edge linkages inbound from workstream (the master-plan linkage already declared in `workstream.md` as `workstream_planned_in_reference_book`) and outbound for supersession (the existing generic `supersedes` kind), and a sibling child table tracking one row per known version of the reference book. The schema deliberately omits content blob storage, full-text search index columns, file-watch refresh, author/owner tracking, and engagement-scoping flags — each grows additively in a later release if real-use signal supports it.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `reference_book` |
| Display name (singular) | Reference Book |
| Display name (plural) | Reference Books |
| Identifier prefix | `RB` |
| Identifier format | `RB-NNN`, zero-padded to 3 digits (e.g., `RB-001`, `RB-042`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /reference-books/next-identifier` |

**Identifier-prefix posture.** `RB` is two letters, matching `WS` and `PI` in the existing short-prefix set. DEC-123 affirmed two-letter form acceptable; the spec guide's section 6 range admits 2 to 5 letters. The collision list at this spec's writing has no conflict with `RB` — the existing `REF` prefix is the references entity, structurally and semantically distinct, and the two-letter `RB` versus three-letter `REF` does not introduce visual ambiguity. The kickoff's open methodology question 2 asked whether `RB` is short enough to risk collision with future prefixes; the answer is no — the remaining three governance entities have working prefixes (`WT`, `COP`, `DEP`) that do not begin with `R`, and the longer-form alternatives (`REFB`, `REFBOOK`, `RBK`) add no value beyond length. The kickoff's open question is resolved in favour of `RB` with an explicit collision check.

### 3.2 Fields

Field naming follows the parent-prefix convention per DEC-046: all fields including identifier and timestamps are prefixed `reference_book_`. The `reference_book_versions` child table's fields are prefixed `reference_book_version_` for the same reason.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `reference_book_identifier` | TEXT | yes | server-assigned | `^RB-\d{3}$`, unique | The reference book identifier in `RB-NNN` format. Server-assigned when omitted from POST body; helper endpoint `GET /reference-books/next-identifier` returns the next available value. |
| `reference_book_title` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Reference book title in the project's working language (e.g., "Governance Entity Schema-Design Workstream Plan", "User Interface Product Requirements Document Version 0.6", "Multi-Engagement Architecture"). Distinct from the file's own internal title, though typically aligned. |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `reference_book_description` | TEXT | yes | — | non-empty trimmed | Paragraph describing the reference book's purpose — what it is, who reads it, what role it plays in the workflow. Used in master-pane previews, search snippets in later releases, and human scanning of the reference book catalog. Plain text in this release. |
| `reference_book_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of the reference book's user-facing summary. Used to capture authoring context, supersession reasoning at archive time, or pointers to discussion threads that produced a major version bump. Plain text in this release; structured-journal pattern deferred to signal. |

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `reference_book_kind` | TEXT | yes | — | enum: `product_requirements_document` \| `implementation_plan` \| `workstream_master_plan` \| `methodology_guide` \| `architecture_document` \| `schema_specification` \| `conduct_framework` \| `investigation_report` \| `apply_script` \| `session_startup_document` \| `other` | Classification of what kind of reference document this is. Closed enum; `other` is the sentinel for documents that do not fit the named categories. See section 3.4.2 for the rationale on each value. |
| `reference_book_status` | TEXT | yes | `active` | enum: `active` \| `archived` \| `superseded`; valid transitions per section 3.4.1; additional rule for `superseded` per section 3.4.3 | Lifecycle status. See section 3.4 for the full state machine. |

#### 3.2.4 Relationship fields

None. Every relationship — inbound master-plan from workstream, supersession edges between reference books, generic citations from conversations and other governance entities — lives in the universal references table per the inherited precedent from `workstream.md` (DEC-124). No foreign-key columns on the reference_book table.

#### 3.2.5 File pointer and version metadata fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `reference_book_file_path` | TEXT | yes | — | non-empty trimmed; must be a repo-relative path (no leading slash, no `..` segments, no scheme prefix); unique within the engagement | Repo-relative path to the canonical file (e.g., `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md`). Resolution at use time is performed against the consuming repository's root — typically the crmbuilder repo for dogfood records and the client repo for engagement-specific records. The path is not validated for existence at write time (the file may be authored separately and the record updated to point at it); a future build prompt may add a "check path resolves" verification step. |
| `reference_book_current_version_label` | TEXT | no | null | non-empty trimmed when set; typically a SemVer-like string (e.g., `1.0`, `1.1`, `0.6`) but free-form to admit whatever the document's own Revision Control table uses | Denormalized pointer to the most recent version of this reference book — the value should match the corresponding row in `reference_book_versions` for this `reference_book_id` and the latest `version_date`. Nullable for reference books that have not yet had a first version recorded (the parent record may be created before the first version row lands). |
| `reference_book_current_version_date` | DATETIME | no | null | ISO 8601 UTC when set; matches the `version_date` of the most recent version row | Denormalized pointer to the date the most recent version was made current. Nullable per the same first-version-not-yet-recorded case. The access layer maintains this in sync with the child versions table — any write to `reference_book_versions` recomputes both `reference_book_current_version_label` and `reference_book_current_version_date` on the parent row. |

**No `reference_book_author` or `reference_book_owner` column.** The project's working pattern has Doug as sole author and owner of every reference book; no per-record author tracking is needed. If multi-author engagements emerge, the column is one migration away.

**No `reference_book_engagement_scope` column.** Per V2's per-engagement isolation (DEC-115 / DEC-116), all reference book records in a given engagement database are scoped to that engagement; the CRMBuilder dogfood engagement holds dogfood reference books, the Cleveland Business Mentors engagement holds CBM reference books. There is no concept of a "global" reference book record cutting across engagements at the database level — the same logical document (e.g., the methodology guide) may exist as a reference book record in each engagement that cites it. The implicit scoping makes the column unnecessary.

**No storage-level length caps** on text fields, matching the workstream / conversation precedents.

#### 3.2.6 Timestamp fields (base only)

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `reference_book_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `reference_book_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `reference_book_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |

**Per-status lifecycle timestamps deliberately omitted.** This is the new cross-spec precedent established by this conversation (see section 1). Reference book's lifecycle is documentary-shaped, not workflow-shaped: there is no operational meaning to "time spent in active" or "time spent in archived" beyond what `updated_at` already captures, and the status transitions are infrequent (a typical reference book moves from `active` to `archived` or `superseded` at most a few times in its lifetime). The change_log table already records status transitions with full before/after detail; per-status lifecycle timestamps would add storage with no query-time benefit. The remaining three downstream specs (`work_ticket`, `close_out_payload`, `deposit_event`) apply the documentary-vs-workflow distinction on their own facts; each is workflow-shaped or append-only and is expected to carry per-status timestamps where applicable.

#### 3.2.7 The `reference_book_versions` child table

A sibling table records one row per known version of a reference book. Schema:

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `id` | INTEGER | yes | auto-increment primary key | — | Internal numeric identifier. Version rows are not externally addressed by a prefixed identifier — they are addressed by `(reference_book_id, version_label)`. |
| `reference_book_id` | INTEGER | yes | — | foreign key to `reference_books.id`; `ON DELETE CASCADE` | The parent reference book this version belongs to. |
| `reference_book_version_label` | TEXT | yes | — | non-empty trimmed; unique within `(reference_book_id, version_label)` | The version label as captured in the reference book file's own Revision Control table (e.g., `1.0`, `1.1`, `0.6`, `2.4`). Free-form text — the file's own internal versioning convention is authoritative. |
| `reference_book_version_date` | DATETIME | yes | — | ISO 8601 UTC | The date this version was made current — typically the timestamp from the file's `Last Updated` header at the moment that version was committed. Drives the in-force-at-time-T query: the version "in force at time T" is the most recent version_date ≤ T. |
| `reference_book_version_summary` | TEXT | no | — | — | Short summary of what changed in this version, typically copied from the corresponding row of the file's Revision Control table. Nullable for the bootstrap case where the parent record is recorded retroactively without per-version summaries. |
| `reference_book_version_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. The moment the version row was recorded in the database, which may differ from `version_date` (the moment the version was made current in the file). |

**The parent's denormalized pointer fields stay in sync with the child rows.** The access layer rebuilds `reference_book_current_version_label` and `reference_book_current_version_date` on the parent after any insert/update/delete on `reference_book_versions` for that parent: the most recent `version_date` wins. This denormalization keeps the master-pane Current Version column free of joins.

**No `is_current` flag on version rows.** Unlike the charter/status singleton-with-payload pattern, the reference_book versioning model does not designate a single "current" version row by a Boolean flag. The current version is computed from the most recent `version_date`. This admits the natural case where a backfilled record is later updated to add an earlier-dated version — the current pointer recomputes automatically without a separate "make this version current" step.

**Version label uniqueness is per-reference-book.** Two different reference books may both have a version `1.0`; the constraint is `(reference_book_id, version_label)` unique, not `version_label` globally unique. This matches the project's actual versioning conventions: every reference book starts at `1.0` or its own counter.

**Soft-delete on the parent cascades to versions via `ON DELETE CASCADE`.** Soft-deleting a reference book (via `DELETE /reference-books/{id}`) sets the parent's `reference_book_deleted_at`; the parent record is excluded from list endpoints by default but the child versions are not directly affected (their rows persist in the database). Restoring the parent restores its visibility; the child rows do not have their own `deleted_at` semantics. A hard-delete on the parent (not exposed via REST in this release) would cascade-remove the child rows.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

One outgoing reference kind in this release, modelled as a references-table edge per the inherited cross-spec precedent.

**Supersession linkage.** When a reference book's status is set to `superseded`, it must have an outgoing reference edge identifying the successor reference book that carries forward as the authoritative source. The relationship uses the existing generic `supersedes` reference kind (already permitted for `(reference_book, reference_book)` once `reference_book` is in `ENTITY_TYPES` because `_kinds_for_pair`'s `source_type == target_type` rule admits `supersedes` for any same-type pair). No new kind is introduced for this relationship; the established vocabulary is reused, identical to workstream's and conversation's patterns.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `supersedes` (existing kind, reused) | `reference_book` | `reference_book` | This reference book was replaced; the target reference book carries forward as the authoritative source. Required when source.status = `superseded`; access-layer enforces. The same edge expresses two semantically related but distinct cases: (a) versioning-via-new-record supersession (a major-version bump produced a new RB-NNN record rather than a new version row on the original — the original is marked superseded with the supersedes edge pointing at the new record); (b) reframing supersession (a methodology guide was rewritten enough that a new reference book was warranted, with the original retained for history).

**Generic citations.** A reference book may reference any other governance record using the existing generic `is_about` and `references` kinds — no new vocabulary required. These are used rarely outbound from a reference book (the typical pattern is inbound — other records cite the reference book — not outbound). One example outbound use: a reference book that documents an investigation may carry an `is_about` edge to the planning item that motivated the investigation.

#### 3.3.2 Inbound relationships (declared by source-side specs)

`reference_book` is the target of inbound references from `workstream` and from `conversation`, plus from the not-yet-designed `work_ticket`, `close_out_payload`, and `deposit_event` entities. Each declares its outbound edge to reference_book in that spec; reference_book.md lists the relationships here for cross-spec consistency-check purposes.

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `workstream_planned_in_reference_book` | `workstream` | `reference_book` | references-table edge | many-to-one from reference_book's perspective (a reference book may serve as master plan for one or more workstreams, though one is typical) | The reference book contains a workstream's master plan document. Declared outbound in `workstream.md` section 3.3.1; kind name committed there tentatively, may be refined here for verb-tense consistency. **This conversation does not refine the kind name.** See section 3.8.1 for the rationale. |
| `is_about` / `references` (existing generic kinds) | `conversation` | `reference_book` | references-table edge | many-to-many (a conversation may cite multiple reference books; a reference book is cited by many conversations) | Conversation cites the reference book as an authoritative source. The conversation entity's spec (section 3.3.2) confirms the generic-kinds posture for conversation→reference_book references. |
| Tentative kinds from not-yet-designed entities | `work_ticket`, `close_out_payload`, `deposit_event` | `reference_book` | references-table edge | varies | Anticipated inbound from the three remaining governance entities. A work_ticket (kickoff prompt) typically carries `read_first` or similar inbound edges to reference books named in its read-list; a close_out_payload may name the reference books its application updates; a deposit_event may carry an edge to the apply script reference book that ran it. Each is designed in its source-side spec. |

These rows are informational from `reference_book.md`'s perspective. The vocab.py registration of `workstream_planned_in_reference_book` and the access-layer enforcement of its cardinality belong to `workstream.md` (where it is already declared in section 3.3.4's additions table). The remaining tentative inbound kinds are designed in their own schema-design conversations.

#### 3.3.3 Hierarchy

Reference book does not use the self-referential parent-child hierarchy pattern in this release. A reference book does not contain sub-reference-books; multi-document phase plans (a "Phase 1 implementation plan" followed by a "Phase 2 implementation plan") are modelled as separate reference book records, optionally linked by supersession when a later document replaces the earlier or by the generic `is_about` / `references` kinds when they coexist. The versioning child table (`reference_book_versions`) captures the related but distinct concept of internal version history within a single reference book; that is not hierarchy.

#### 3.3.4 New reference vocabulary additions this spec requires

**None.** This is the first of the six schema specs to require no new vocabulary additions. The needed additions are all pre-declared:

- `workstream_planned_in_reference_book` is in `workstream.md` section 3.3.4's additions table.
- `reference_book` is in `ENTITY_TYPES` per `workstream.md` section 3.3.4's additions table.
- The `(reference_book, reference_book)` supersedes pair is admitted by the existing `_kinds_for_pair` rule `if source_type == target_type: kinds.add('supersedes')` once `reference_book` is in `ENTITY_TYPES`.
- Generic `is_about` and `references` kinds are admitted by the existing `_kinds_for_pair` defaults for any pair.

The build-planning conversation aggregates this nil contribution into its consolidated vocab.py update without action; no Alembic migration on `refs.relationship_kind`'s CHECK constraint is required from this spec.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `active` | The reference book is currently the authoritative source — readers should consult this version. **Default starter status.** | (none — starter) | `archived`, `superseded` |
| `archived` | The reference book is retained for history but is no longer authoritative — typically because the document's role in the workflow has ended (e.g., the workstream it documented is complete and the master plan no longer drives ongoing work) or because the document was an investigation report whose findings have been absorbed elsewhere. Terminal. Distinct from `superseded`: an archived reference book has no successor — the work moved on, not the document. | `active` | (none — terminal) |
| `superseded` | The reference book was replaced by another reference book that carries forward as the authoritative source. Requires an outgoing `supersedes` edge to the successor reference book per section 3.4.3. Terminal. | `active` | (none — terminal) |

The default starter status is `active`. There is no intermediate status between creation and active use — reference books begin as the authoritative source immediately on creation. A reference book that is being drafted but not yet authoritative is captured by the file's own internal Revision Control table (the document may be at v0.1 internally while the database records its single version row); the database does not model draft state separately.

#### 3.4.2 Kind enum values

The eleven `reference_book_kind` values, with semantics:

- `product_requirements_document` — A Product Requirements Document. Examples: `ui-PRD-v0.6.md`, `storage-system-PRD-v0.1.md`, `catalog-ingestion-PRD-v0.1.md`. Typically lives at `PRDs/product/crmbuilder-v2/*-PRD-vX.Y.md`.
- `implementation_plan` — An implementation plan, typically the per-version build plan. Examples: `ui-v0.4-implementation-plan.md`, `storage-system-implementation-plan.md`, `catalog-ingestion-implementation-plan.md`. Typically lives at `PRDs/product/crmbuilder-v2/*-implementation-plan.md`.
- `workstream_master_plan` — A workstream's master plan document, the artifact the workstream entity may declare a master-plan linkage to via `workstream_planned_in_reference_book`. Examples: `methodology-schema-workstream-plan.md`, `governance-schema-workstream-plan.md`, `multi-tenancy-routing-fix-slice-plan.md`. Typically lives at `PRDs/product/crmbuilder-v2/*-workstream-plan.md` or `*-slice-plan.md`.
- `methodology_guide` — A methodology document — the templates and how-to references for workstream conduct. Examples: `methodology-entity-schema-spec-guide.md`, `governance-entity-schema-spec-guide.md`. Typically lives at `PRDs/product/crmbuilder-v2/*-spec-guide.md` or in `PRDs/process/`.
- `architecture_document` — An architecture or design document outlining a cross-cutting structural choice. Examples: `multi-engagement-architecture.md`. Typically lives at `PRDs/product/crmbuilder-v2/*-architecture.md`.
- `schema_specification` — A schema specification produced by a schema-design conversation. Examples: `methodology-schema-specs/domain.md`, `governance-schema-specs/workstream.md`, this document itself once it lands. Typically lives at `PRDs/product/crmbuilder-v2/*-schema-specs/*.md`.
- `conduct_framework` — One of the three conduct framework documents governing AI-led requirements interview conduct. Examples: `PRDs/process/conduct/charter.md`, `kickoff.md`, `question-library.md`.
- `investigation_report` — A report documenting an investigation or analysis. Examples: `multi-tenancy-routing-investigation-report.md`, `methodology-schemas-cbm-paper-test-findings.md`. Typically lives at `PRDs/product/crmbuilder-v2/*-investigation-report.md` or `*-findings.md`.
- `apply_script` — An apply script for landing close-out payloads (the Markdown prompts under `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-*.md` that drive the apply runs). DEC-117 names this as one of the seven reference book artifacts. Note the distinction from one-off kickoff prompts (which are work_tickets, not reference books): apply scripts are referenced repeatedly across the workstream's life (every close-out reuses the format); kickoff prompts are single-use.
- `session_startup_document` — The session-startup entry document (`crmbuilder/CLAUDE.md`, `ClevelandBusinessMentoring/CLAUDE.md`) read at the open of every Claude conversation per the Session orientation protocol. DEC-117 names this as one of the seven reference book artifacts.
- `other` — Sentinel for documents that do not fit the named categories. The intent is that real use will surface additional kinds; new kinds are added by extending the enum in a future migration. The sentinel is the documented escape hatch.

#### 3.4.3 Supersession-requires-edge rule

Setting `reference_book_status` to `superseded` requires the record to have an outgoing reference edge of kind `supersedes` to another reference book record. The access layer enforces this as a single combined validation, identical to workstream's and conversation's supersession-requires-edge patterns:

- POST creating a record with `status = 'superseded'` and no `supersedes` edge: HTTP 422 `{"error": "supersession_requires_successor_edge"}`.
- PUT or PATCH transitioning an existing record to `status = 'superseded'` without an outgoing `supersedes` edge present: same 422.
- The edge may be supplied in the same request body.
- DELETE on the `supersedes` edge while the source record still has `status = 'superseded'`: HTTP 422 `{"error": "superseded_reference_book_requires_supersedes_edge"}`. The status must be changed first (e.g., via re-activation if appropriate, or the source must be soft-deleted).

No corresponding required-edge rule exists for the `archived` status — archived reference books have no successor by definition; the `archived` outcome means the work that the document supported has ended, not that another document carries the work forward.

#### 3.4.4 Transition semantics

The status lifecycle is **forward-only with two truly terminal terminal states**, identical posture to workstream and conversation per the inherited precedent. Each terminal state admits no outgoing transitions; re-activating an archived or superseded reference book is not supported. A reference book whose role resumes after being archived is modelled as a new reference book record, optionally with an inbound `references` or `is_about` edge from the new record to the prior. A reference book whose successor turns out to be unsuitable is handled by the successor being marked superseded itself (transitively) or by administrative restoration via the soft-delete restore path (if the supersession itself was an error).

Two corollaries, parallel to workstream's and conversation's:

- **No regression from terminal.** `archived` and `superseded` cannot regress to `active`. A reference book whose role resumes is a new reference book record, not an edit of the prior record's status.
- **No movement between terminal states.** An `archived` reference book cannot be reclassified as `superseded` even if a successor emerges later. The supersession relationship is modelled by the inbound reference from the successor (a new reference book may declare it `supersedes` the prior archived one, in which case both records co-exist with their original terminal statuses intact and a `supersedes` edge connecting them — the source's status remains `archived`). The status field captures the original lifecycle outcome at the moment the terminal transition happened; the references table captures the relationship to successors.

Server-side validation rejects invalid transitions with HTTP 422 and body `{"error": "invalid_status_transition", "from": <current>, "to": <requested>}`. The access-layer enforcement table mirrors the predecessor-successor map above.

#### 3.4.5 Soft-delete semantics

Default V2 base behavior. `reference_book_deleted_at` set on DELETE; soft-deleted records do not appear in `GET /reference-books` by default; `?include_deleted=true` reveals them; POST `/restore` clears `reference_book_deleted_at` and restores them to the active list. Soft-delete is administrative (the record is removed from the active view, typically used to undo an erroneous creation) and is distinct from both `archived` status (a lifecycle outcome — the role ended) and `superseded` status (a successor-replaced outcome). A record that is both `superseded` and soft-deleted is a superseded reference book whose record was also administratively removed; restore puts it back with status still `superseded`.

### 3.5 API Surface

#### 3.5.1 Endpoints — parent

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/reference-books` | — | List active reference books; `?include_deleted=true` shows soft-deleted; `?kind=<value>` filters by kind; `?status=<value>` filters by status. |
| GET | `/reference-books/{identifier}` | — | Single fetch by identifier. Response includes the denormalized current-version pointer fields; does NOT inline the full versions array (see version-management endpoints below). |
| POST | `/reference-books` | full reference book JSON; identifier optional | Create. Identifier server-assigned when omitted. Default `reference_book_status` is `active` if omitted. The body may include a `versions` array; if present, the access layer creates the parent record plus one row per supplied version in a single transaction and recomputes the denormalized pointer fields. |
| PUT | `/reference-books/{identifier}` | full reference book JSON | Full replace. Status-transition validation per section 3.4. The `versions` array, if supplied, replaces the child rows in a single transaction; otherwise the child rows are unaffected. |
| PATCH | `/reference-books/{identifier}` | partial reference book JSON | Partial update. Same validation as PUT for any field touched. Version management is via the dedicated child-endpoints below, not via PATCH on the parent. |
| DELETE | `/reference-books/{identifier}` | — | Soft-delete; sets `reference_book_deleted_at`. Child version rows are preserved (not soft-deleted in their own right). |
| POST | `/reference-books/{identifier}/restore` | — | Clears `reference_book_deleted_at`. 422 if not currently soft-deleted. |
| GET | `/reference-books/next-identifier` | — | Returns `{"next": "RB-NNN"}` for the next available value. Used by clients computing the identifier client-side, e.g., the desktop New Reference Book dialog. |

#### 3.5.2 Endpoints — versions (child)

Three sub-endpoints scoped to a specific reference book's versions:

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/reference-books/{identifier}/versions` | — | List all known versions of the reference book in `version_date` descending order. Returns an array of version records; empty array if no versions are recorded yet. |
| POST | `/reference-books/{identifier}/versions` | version JSON (`version_label`, `version_date`, `version_summary` optional) | Record a new version. Insert into `reference_book_versions`; recompute parent's `reference_book_current_version_label` and `reference_book_current_version_date` (the row whose `version_date` is the new maximum wins). Returns the created version row. 422 on `(reference_book_id, version_label)` collision. |
| GET | `/reference-books/{identifier}/version-at` | — (query string: `?as_of=YYYY-MM-DD` or full ISO 8601) | Returns the version that was in force at the specified instant — the row with the highest `version_date` that is ≤ `as_of`. Returns `{"data": null}` if no version was in force at that instant (the reference book did not yet exist, or had no version recorded yet). |

The version-at endpoint realizes the in-force-at-time-T semantics named in the kickoff. The query is fully resolved against the child versions table; no scanning of git history is required.

**No DELETE on individual version rows in this release.** Removing a version row is rare and not routinely needed — versions are append-only in practice. The build-planning conversation may add a DELETE if a real need surfaces; the schema admits it additively. Soft-deleting the parent reference book preserves the version rows (per section 3.2.7's note on `ON DELETE CASCADE` applying only on hard-delete).

#### 3.5.3 Identifier auto-assignment

Default V2 server-side auto-assignment on POST omission for the parent record. Version rows do not have prefixed identifiers; they are addressed by `(reference_book_id, version_label)` as documented in section 3.2.7.

All endpoints return the `{data, meta, errors}` envelope per existing V2 convention.

### 3.6 User Interface Considerations

Default layout per spec guide section 3.6, with two natural additions: a Kind column in the master pane (because kind is the most operationally meaningful classification for a reference book — consultants ask "what's the PRD for v0.6" or "what's the methodology guide for governance entity schema-design") and an inline version-history section in the detail pane (because the version list is the reference book's distinctive shape). Both follow naturally from this spec's field inventory and do not constitute architectural deviation.

#### 3.6.1 Sidebar

The Reference Books panel goes in the Governance sidebar group, immediately after Conversations in workstream order. Position within the new-six set is the build-planning conversation's call; the working assumption remains that the six new entities sit at the end of the existing Governance group in workstream order (workstream first, then conversation, reference book, work ticket, close-out payload, deposit event).

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with five columns — one more than workstream's four, with Kind added because kind is the most operationally meaningful classification for browsing the reference book catalog.

| Column | Header | Width | Notes |
|--------|--------|-------|-------|
| `reference_book_identifier` | Identifier | narrow | Sortable; default sort. |
| `reference_book_title` | Title | wide | Project-language title. |
| `reference_book_kind` | Kind | medium | Enum value rendered as a friendly label (e.g., "Product Requirements Document" instead of `product_requirements_document`). |
| `reference_book_current_version_label` | Version | narrow | Denormalized pointer; rendered as-is. Empty for reference books with no versions recorded yet. |
| `reference_book_updated_at` | Updated | narrow | Localized date/time. |

Default sort: identifier ascending. Filter controls in the panel toolbar: a kind selector (filters by `?kind=`) and a status selector (filters by `?status=`). Both default to "all". Right-click context menu offers New / Edit / Delete / Restore, consistent with the user-interface version 0.3 governance-entity panels per DEC-035 and DEC-036.

**`reference_book_status` not in the default master pane.** Most reference book queries are scoped to active records (the default list filter excludes none); status is the kind of attribute users filter by, not browse by. The status selector in the toolbar covers the explicit-filter case; consultants who want to scan archived or superseded records use the filter.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order with the version-history section interleaved:

1. `reference_book_identifier` — read-only label.
2. `reference_book_title` — single-line text editor.
3. `reference_book_description` — multi-line text editor with placeholder "Paragraph describing the reference book — what it is, who reads it, what role it plays."
4. `reference_book_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default. The collapsed default reinforces that the field is internal consultant scratchpad.
5. `reference_book_kind` — combo box with the eleven enum values rendered as friendly labels.
6. `reference_book_file_path` — single-line text editor with placeholder "Repo-relative path, e.g., `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md`". No file-system existence validation in this release; the value is stored verbatim after trim.
7. `reference_book_status` — combo box with the three enum values; the combo's selectable subset at any moment is the union of `{current_status}` and the valid successors of the current status per section 3.4.1, so the user cannot select an invalid transition. Server-side validation is the final gate.
8. **Version history section** — a subordinate panel rendering the child versions table for this reference book in `version_date` descending order. Each row shows `version_label`, `version_date` (localized), and `version_summary` (rendered with line wrapping). An "Add version" button opens a small dialog capturing `version_label`, `version_date`, and `version_summary`. The current version (the most recent `version_date`) is visually distinguished (bold label, or a "Current" badge). For reference books with no versions, the section shows a placeholder ("No versions recorded yet — click Add version to record the first.") with the same button.
9. `ReferencesSection` widget — renders the outbound `supersedes` edge (when present), inbound `workstream_planned_in_reference_book` edges (when present), inbound generic citations from conversations and other governance entities, and any other inbound or outbound edges the references vocabulary admits. The "Add reference" affordance from the user-interface version 0.3 references-create dialog filters available kinds and target entity types by the strict vocab per `_kinds_for_pair`.

The denormalized `reference_book_current_version_label` and `reference_book_current_version_date` are not separately editable — they are computed from the version history section's contents and rendered as part of the version display (the "Current" badge), not as standalone editable fields.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `reference_book_identifier` not shown in create mode (server-assigned).
- `reference_book_status` defaults to `active`; the user may select a different starter value for backfill of historical records (e.g., creating a reference book record for a document that was archived before the entity type existed).
- Required-field validation client-side before submit.
- Server-side validation errors (uniqueness on title, format on identifier, file path format, supersession-requires-edge) surface inline.
- The "Add version" affordance in the version-history section is hidden in create mode; the dialog admits one or more versions as part of the initial create (a `versions` array in the request body) via a "First version (optional)" subsection that captures `version_label`, `version_date`, and `version_summary` for an initial version row.

#### 3.6.5 Edit dialog

Same shape as create. `reference_book_identifier` displayed as read-only label. Status transitions enforced per section 3.4.1; the combo box restricts selectable values to valid transitions plus the current value (no-op). Setting status to `superseded` requires an outgoing `supersedes` edge to be present (added via the ReferencesSection's "Add reference" affordance before the status change is committed, or via the same patch payload); attempting to commit `superseded` without the edge surfaces the 422 inline.

The version-history section is fully interactive in edit mode — adding a new version is the routine operational case (every Revision Control table bump in a real reference book file corresponds to an Add Version operation in the dialog).

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `reference_book_identifier` value (e.g., `RB-005`) to enable the Delete button, matching the user-interface version 0.3 governance-entity patterns. Confirmation soft-deletes the parent record; the child version rows persist for restore-recovery.

### 3.7 Acceptance Criteria

The following sixteen statements define what "this entity type is correctly implemented in the eventual build" looks like. Each is concrete and testable; the build-planning conversation translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `reference_books` table with all eleven columns (`reference_book_identifier`, `reference_book_title`, `reference_book_description`, `reference_book_notes`, `reference_book_kind`, `reference_book_status`, `reference_book_file_path`, `reference_book_current_version_label`, `reference_book_current_version_date`, base timestamps), the `reference_book_versions` child table with six columns (`id`, `reference_book_id` with `ON DELETE CASCADE` foreign key to `reference_books.id`, `reference_book_version_label`, `reference_book_version_date`, `reference_book_version_summary`, `reference_book_version_created_at`), the `(reference_book_id, version_label)` unique constraint, correct types and constraints, and runs both forward and backward without error.

2. **`reference_book_identifier` format constraint enforced.** Insertions with `reference_book_identifier` not matching `^RB-\d{3}$` raise a validation error at the access layer.

3. **`reference_book_title` uniqueness enforced case-insensitively.** Inserting a second row whose `reference_book_title` matches an existing row by lowercase comparison raises a uniqueness violation.

4. **`reference_book_kind` enum enforced.** Insertions with `reference_book_kind` outside the eleven-value enum are rejected; the rejection error names the value supplied.

5. **`reference_book_status` enum and transition validation.** Insertions with `reference_book_status` outside the three-value enum are rejected. PATCH or PUT requesting an invalid transition (e.g., `archived` → `active`) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

6. **Terminal states are truly terminal.** Both terminal statuses (`archived`, `superseded`) reject every outgoing transition, including transitions between terminal states (e.g., `archived` → `superseded`). Same 422 shape.

7. **Supersession-requires-edge rule.** POST or PATCH setting `reference_book_status = 'superseded'` without an outgoing `supersedes` edge to another reference_book record returns HTTP 422 with `{"error": "supersession_requires_successor_edge"}`. The edge may be supplied in the same request body. Deletion of an existing `supersedes` edge on a `superseded`-status record returns the parallel 422.

8. **`reference_book_file_path` validation.** Insertions with `reference_book_file_path` containing leading slash, `..` segments, or scheme prefix (e.g., `https://`, `file://`) are rejected at the access layer. Empty or whitespace-only file paths are rejected.

9. **Versions table CRUD round-trip.** A version row inserted via `POST /reference-books/{id}/versions` is retrievable via `GET /reference-books/{id}/versions`; the parent's denormalized `reference_book_current_version_label` and `reference_book_current_version_date` are recomputed to match the row whose `version_date` is the newest. Insertion of a second version with the same `version_label` (collision on the unique constraint) returns HTTP 422.

10. **In-force-at-time-T query.** `GET /reference-books/{id}/version-at?as_of=YYYY-MM-DD` returns the version row whose `version_date` is the maximum among rows with `version_date ≤ as_of`. A reference book with versions at 05-11-26 (v1.0) and 05-12-26 (v1.1) queried `as_of=05-11-26` returns v1.0; queried `as_of=05-12-26` returns v1.1; queried `as_of=05-10-26` returns `{"data": null}`.

11. **Access-layer methods exist with expected signatures.** `client.list_reference_books()`, `client.get_reference_book(identifier)`, `client.create_reference_book(...)`, `client.update_reference_book(identifier, ...)`, `client.patch_reference_book(identifier, ...)`, `client.delete_reference_book(identifier)`, `client.restore_reference_book(identifier)`, `client.next_reference_book_identifier()`, `client.list_reference_book_versions(identifier)`, `client.create_reference_book_version(identifier, ...)`, `client.get_reference_book_version_at(identifier, as_of)` exist and pass unit tests covering happy path and at least one error case each.

12. **REST endpoints return expected responses for representative cases.** All eleven endpoints (eight parent + three child) from section 3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the V2 `{data, meta, errors}` envelope per `crmbuilder-v2/src/crmbuilder_v2/api/envelope.py`.

13. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /reference-books/next-identifier` returns `{"next": "RB-NNN"}` for the next available number. POST with `reference_book_identifier` omitted assigns the same value. Two concurrent POSTs do not assign the same identifier (verified by a concurrent-insert test).

14. **Soft-delete and restore round-trip correctly.** DELETE sets `reference_book_deleted_at`; the record disappears from `GET /reference-books`. `GET /reference-books?include_deleted=true` shows it. POST `/restore` clears `reference_book_deleted_at`; the record reappears. Version child rows persist throughout the soft-delete / restore cycle. Restore on a record that is not soft-deleted returns 422.

15. **`Reference Books` sidebar entry appears in the Governance group.** Position within the new-six set is whatever the build-planning conversation chooses; the entry exists, the panel opens, the panel is bound to the access-layer methods including the version sub-endpoints.

16. **End-to-end backfill of the governance-schema-workstream-plan reference book.** A consultant can author a `reference_book` record for `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` through the New Reference Book dialog with kind `workstream_master_plan` and one version row (`version_label="1.0"`, `version_date="2026-05-20T00:00:00Z"`, summary copied from the Revision Control table), observe the master-plan inbound edge from the WS-002 record (the governance entity schema-design workstream, once backfilled per PI-022) landing as a `workstream_planned_in_reference_book` inbound reference, and later record a version 1.1 row when the file is updated. The reference book record and its version rows persist across application restart and across REST/MCP refetch.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For the build-planning conversation to settle

**[build] Sidebar grouping for the six new governance entities.** Inherited from `workstream.md` section 3.8.1 and `conversation.md` section 3.8.1. Still pending; this spec does not change the situation.

**[build] Tentative kind name `workstream_planned_in_reference_book`.** This spec inherits the kind name as declared in `workstream.md` section 3.3.4. The verb-tense and source-target framing was not refined in this conversation. Two observations support leaving the name as-is: (a) the past-participle `planned_in` mirrors the documentary-shape semantics of the relationship — the workstream is the active organising unit, and `_planned_in_` reads as "the workstream had its planning placed in this reference book"; (b) any refinement would also need to harmonize with the not-yet-designed work_ticket entity's inbound kinds to reference book (e.g., `work_ticket_read_first_lists_reference_book` or similar) and the close_out_payload and deposit_event inbound kinds. The build-planning conversation has all five source-side specs visible and is the right place to harmonize, if harmonization is needed. The kind name lock-in is the build-planning conversation's call; this spec accepts the inherited tentative name.

**[build] Version-management endpoint pathing.** This spec proposes `/reference-books/{id}/versions` and `/reference-books/{id}/version-at` as the child-endpoint paths. The build-planning conversation may revisit if a different pattern (e.g., `/reference-book-versions?reference_book=RB-001` as a top-level resource) reads better against the rest of the V2 API. The schema works with either; the access-layer signatures are unaffected.

**[build] Friendly-label rendering for kind enum values.** The detail pane combo and the master pane Kind column render the enum values as friendly labels (e.g., "Product Requirements Document" for `product_requirements_document`). The mapping table is a small UI fixture; the build-planning conversation specifies whether it lives in the panel module, in a shared user-interface helper, or as a derived property from the access layer.

**[build] Cycle prevention in the supersedes edge.** Reference book supersession may form a chain (`RB-005 supersedes RB-002 supersedes RB-001`) but should never form a cycle (`RB-005 supersedes RB-002 supersedes RB-005`). Workstream and conversation inherit a similar concern but workstream.md and conversation.md do not document cycle prevention as a specific access-layer rule (they rely on the per-edge-pair semantics). The build-planning conversation specifies whether a cross-cutting access-layer cycle-prevention helper covers all `supersedes` pairs uniformly, or whether each entity registers its own.

#### 3.8.2 For retroactive backfill (PI-022) to surface

**[backfill] Which historical documents become RB records.** PI-022 covers retroactive population of reference book records. The seed list at this spec's writing includes the workstream master plans, the methodology guides, the multi-engagement architecture document, the conduct framework documents, the session-startup entry document, and the apply scripts — eleven to twenty documents depending on inclusion judgments. The PRD documents and implementation plans add another fifteen-plus. The full inclusion policy (e.g., "every document at `PRDs/product/crmbuilder-v2/*.md` becomes an RB record" vs. "only documents that have been cited by a session record's topics_covered text" vs. "only documents that exist at HEAD and are not deprecated") is PI-022's call. This spec admits any policy — the schema does not constrain inclusion.

**[backfill] Version row populating policy.** Reference book files carry their own Revision Control tables internally. The backfill pass reads each file's table and populates version rows accordingly. Edge cases — version_label not yet declared, version_summary too long for a single row, multiple "Last Updated" headers in one file — are PI-022's call. The schema admits any per-version metadata the backfill produces.

**[backfill] `reference_book_kind` assignment for ambiguous documents.** Some documents legitimately fit multiple kinds (e.g., a "schema specification" that is also an "investigation report"). PI-022's policy: pick the dominant kind, use the `other` sentinel only as a last resort. The schema does not constrain disambiguation; the access layer accepts whichever value the backfill supplies.

#### 3.8.3 For a future release

**[future] File content blob in the database.** Not introduced in this release. The file lives in git/files; the database tracks the pointer. If a real query need surfaces ("show me the full text of the v1.1 methodology guide as it was committed"), a future release could either (a) add a `version_payload` JSON or BLOB column on `reference_book_versions` populated at commit time, or (b) lean on git-blob lookup via a path+commit-sha pair. The current pointer-only schema admits either retrofit additively.

**[future] Full-text search.** Not introduced in this release. If a real query need surfaces ("find every reference book mentioning 'multi-tenancy'"), a future release adds a FTS5 virtual table fronting the description plus per-version summary text plus (if option (a) of the previous bullet lands) the version_payload column. The schema admits the retrofit additively.

**[future] File-system existence validation.** Not introduced in this release. The schema accepts any well-formed repo-relative path string without checking that the file actually exists at the current commit. If a real friction case surfaces (records pointing at files that have been renamed or deleted), a future release adds a verification check, either at write time (rejected) or as a separate "find broken pointers" maintenance query. The schema admits the retrofit additively.

**[future] Author and owner tracking.** Not introduced in this release. The project's working pattern has Doug as sole author. If multi-author engagements emerge, columns are one migration away.

**[future] Inline file content preview in the detail pane.** Not introduced in this release. The detail pane shows the file path as a string; clicking does not open the file (the dialog is a database record editor, not a file viewer). If a real friction case surfaces, a future user-interface release adds a "Preview content" tab on the detail pane that loads the file from the repo and renders it with a Markdown viewer. The schema does not change.

**[future] DELETE on individual version rows.** Not introduced in this release. The versions child table is append-only in practice. If a real need surfaces (a version row was created in error), the schema admits a DELETE endpoint additively; the current absence is a routing-table omission, not a schema constraint.

**[future] Typed sequencing between distinct reference book records.** Not introduced in this release. Workstream's deferred-sequencing-to-signal posture (DEC-127, section 3.8.3 of workstream.md) is inherited by reference_book per the cross-spec frequency test. Reference book sequencing across distinct records is rare: a "Phase 1 implementation plan" followed by a "Phase 2 implementation plan" is the most common case, and supersession or generic `references` kinds cover it adequately. If a real high-frequency need surfaces, a future release adds `reference_book_succeeds_reference_book` as one vocab.py line plus build-planning aggregation.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following six decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against `PRDs/product/crmbuilder-v2/close-out-payloads/ses_050.json` at conversation close. Each is linked to SES-050 via a `decided_in` reference recorded in the same payload. Decision identifiers (anticipated DEC-135 through DEC-140) are assigned by the apply script at write time and may shift if other conversations close before this one applies.

- **DEC-135 — `reference_book` identifier prefix and format.** Adopts `RB` as the prefix; affirms two-letter form is acceptable and resolves the kickoff's open-question concern about visual ambiguity by checking the remaining-three-conversations' working prefixes (`WT`, `COP`, `DEP`) for confirmed non-collision.
- **DEC-136 — `reference_book` versioning model: parent record plus child versions table.** Adopts the parent-plus-child versioning shape — distinct from charter/status's singleton-with-payload pattern because the file content lives in git/files and the database tracks version metadata only. Denormalized current-version pointer fields on the parent stay in sync with the child rows via access-layer recompute on any child-table write. Establishes the documentary-entity versioning pattern.
- **DEC-137 — `reference_book` documentary-shaped lifecycle with three statuses and base timestamps only.** Adopts `active` / `archived` / `superseded` with the transition map of section 3.4.1, the truly-terminal posture of section 3.4.4, and the supersession-requires-edge access-layer rule of section 3.4.3. **Establishes new cross-spec precedent: documentary-shaped lifecycles inherit base timestamps only**, deviating from DEC-126's per-status-timestamps-for-workflow-shapes precedent. The remaining three governance specs apply the documentary-vs-workflow distinction on their own facts.
- **DEC-138 — `reference_book_kind` closed enum with eleven values.** Captures the eleven-value closed enum covering DEC-117's seven artifact types plus three additional types observed in the project's operating history (`architecture_document`, `conduct_framework`, `investigation_report`) plus an `other` sentinel.
- **DEC-139 — `reference_book` field inventory, repo-relative file path semantics, no engagement-scoping flag, soft-delete posture.** Captures the seven content/classification fields plus the three file-pointer fields plus the base timestamps (no per-status timestamps per DEC-137). Repo-relative file path with no leading slash and no `..` segments; resolved at use time against the consuming repository. No engagement-scoping flag (per V2's per-engagement isolation, scoping is implicit). Default soft-delete with restore, distinct from `archived` and `superseded` status outcomes.
- **DEC-140 — `reference_book` API surface, version-management sub-endpoints, master-pane Kind column, default UI with inline version-history section, sixteen acceptance criteria.** Standard 8-endpoint set for the parent plus three version-management sub-endpoints (`GET /reference-books/{id}/versions`, `POST /reference-books/{id}/versions`, `GET /reference-books/{id}/version-at?as_of=...`) realizing the in-force-at-time-T semantics; list-endpoint filters `kind` and `status` (alongside `include_deleted`); master-pane Kind column as the third column; inline version-history section in the detail pane with Add Version affordance; sixteen acceptance criteria.

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry. (Itself a reference book of kind `session_startup_document` per DEC-138's enum.)
- `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan governing this and the next three schema-design conversations. (Itself a reference book of kind `workstream_master_plan` per DEC-138's enum.)
- `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template this document follows. (Itself a reference book of kind `methodology_guide` per DEC-138's enum.)
- `PRDs/product/crmbuilder-v2/schema-design-kickoff-reference-book.md` — this conversation's seed prompt. (Itself a work_ticket per DEC-117's family classification, not a reference book.)
- `PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md` — settled referent for the workstream→reference_book master-plan linkage and the source of three of the four inherited cross-spec precedents.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/conversation.md` — settled referent for the conversation→reference_book generic-citations posture and the source of the fourth inherited cross-spec precedent (typed-sequencing-frequency-justified).
- `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — per-engagement isolation; `reference_book` records live in the per-engagement database; the same logical document may exist as a reference book record in each engagement that cites it. (Itself a reference book of kind `architecture_document` per DEC-138's enum.)
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — controlled vocabulary; no new entries required from this spec.
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/charter.py` and `status.py` — the existing versioned-replace pattern this spec's versioning model adapts (parent-plus-child instead of singleton-with-payload).

#### 3.9.3 Foundation decisions this spec extends

- **DEC-117** — Track workflow files as three purpose-built entity-type families. **Most directly extended.** `reference_book` is family 1 (long-lived multi-consumer versioned reference documents), the seven-artifact family. This spec's kind enum (eleven values) realizes the family with three additions beyond DEC-117's named seven artifacts (`architecture_document`, `conduct_framework`, `investigation_report`) plus an `other` sentinel.
- **DEC-118** — Two entities within the deposit bucket family. Not directly extended; the deposit-bucket family is families 3 (close_out_payload) and 4 (deposit_event), designed in the fifth and sixth schema-design conversations.
- **DEC-119** — Add a conversation entity. The conversation→reference_book relationship via generic `is_about` / `references` kinds is declared in `conversation.md` section 3.3.2; this spec inherits the posture.
- **DEC-120** — Add a workstream entity. The workstream→reference_book master-plan linkage via `workstream_planned_in_reference_book` is declared in `workstream.md` section 3.3.1; this spec inherits the posture and confirms the kind name as-is (section 3.8.1).
- **DEC-121** — Single-source-of-truth coverage extension. `reference_book` makes the multi-consumer versioned reference document concept machine-resolvable; the in-force-at-time-T query is fully resolved against the child versions table without scanning git history, which is exactly the weak-coupling pattern DEC-121 says to eliminate.
- **DEC-122** — The governance workstream opens immediately, in parallel to other in-flight work. This spec operates against the CRMBuilder dogfood engagement only.

#### 3.9.4 Related prior decisions informing this spec

- **DEC-013** — Decisions and sessions are append-only and immutable. Reference book versions are append-only in practice (the version rows are not edited after insertion in the routine case), but the parent reference book record is soft-delete-with-restore rather than append-only because the parent is organizing metadata, not transactional fact.
- **DEC-025** — Per-conversation transcript capture infeasible. Informs section 3.9.1's reliance on the close-out payload's apply script and the session record as the durable artifacts of this conversation.
- **DEC-029** — Charter and Status replace via JSON editor with Validate + Make Current. The closest existing V2 pattern to this spec's versioning model. This spec adapts the singleton-with-payload pattern to a parent-plus-child shape because reference books are a collection (not a singleton) and the payload lives in git/files (not the database).
- **DEC-031** — Reference rendering generalized via shared `ReferencesSection` widget. Directly informs the detail pane reference rendering in section 3.6.3, including the multiple inbound-edge kinds (workstream master plan, generic citations from conversations, anticipated inbound from the three remaining governance entities).
- **DEC-033** — Cascading reference create dialog driven by strict vocab. The reference book entity's outbound `supersedes` plus the generic `is_about`/`references` defaults all flow through the existing dialog without modification.
- **DEC-035** — `ListDetailPanel` master-widget plus context-menu factory refactor. Informs master pane patterns in section 3.6.2 including the addition of the Kind column and the toolbar filter combos.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs context-menu behavior in section 3.6.2.
- **DEC-046** — Parent-prefix field-naming convention. Inherited and applied throughout (all parent-table fields prefixed `reference_book_`, all child-table fields prefixed `reference_book_version_`).
- **DEC-048** — Source-first `{source}_{verb}_{target}` relationship-kind naming. Inherited; the inbound `workstream_planned_in_reference_book` kind already follows the pattern.
- **DEC-115 / DEC-116** — Per-engagement isolation architecture. `reference_book` records live in the per-engagement SQLite file; the same logical document (e.g., the methodology guide) may exist as a reference book record in each engagement that cites it, distinguished by the engagement's database identity rather than by an engagement-scope column.
- **DEC-123 through DEC-128** — All six decisions from SES-048 (the workstream schema-design conversation). DEC-123 affirms the two-letter `RB` prefix is acceptable. DEC-124's references-edge cross-spec precedent applies to all of this spec's relationships. DEC-125's truly-terminal and supersession-requires-edge patterns are inherited verbatim. DEC-126's per-status lifecycle timestamps precedent is **deviated from with explicit justification** in this spec — see section 1 and DEC-137; the new cross-spec precedent locked here. DEC-127's flat-catalog posture is structurally analogous to this spec's no-hierarchy posture (sections 3.3.3 and 3.8.3). DEC-128's standard-defaults posture is what this spec uses for API surface, UI layout, soft-delete, and acceptance-criteria framing.
- **DEC-129 through DEC-134** — All six decisions from SES-049 (the conversation schema-design conversation). DEC-129 affirms each downstream conversation makes its own prefix-length call (two-letter `RB` is fine). DEC-130's references-edge precedent for parent-child relationships applies (though reference_book has no parent — the precedent applies to outbound supersession and to the inbound workstream master-plan linkage already declared by workstream.md). DEC-131's lifecycle patterns inform this spec's documentary-shaped three-state lifecycle. DEC-132's tentative-kind-name posture is what this spec accepts for the inherited `workstream_planned_in_reference_book` kind name. DEC-133's typed-sequencing-frequency-justified precedent is applied here — reference_book sequencing across distinct records is rare, so no typed sequencing kind is introduced (the precedent licences both adoption and deferral; this spec defers). DEC-134's standard-defaults-with-natural-additions posture is what this spec uses for API surface and UI layout.

#### 3.9.5 Predecessor and successor conversations

- **Predecessor:** SES-049 — conversation schema-design conversation. Second per-entity schema-design conversation in the governance entity schema-design workstream. Established the typed-sequencing-frequency-justified cross-spec precedent that this conversation applies to defer reference_book sequencing kinds.
- **Successor:** `work_ticket` schema-design conversation. Kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-work-ticket.md`. Inherits the five cross-spec precedents now in force: the three from workstream (references-edge over foreign-key, per-status lifecycle timestamps for workflow-shaped lifecycles, terminal-states-are-terminal), the one from conversation (typed sequencing introduced when entity-family frequency justifies), and the one from this conversation (documentary-shaped lifecycles inherit base timestamps only — workflow-shape per-status timestamps remain the default for workflow-shaped lifecycles, which work_ticket likely is). The work_ticket entity is structurally most directly related to this spec through its anticipated inbound `read_first`-style edges to reference books named in a kickoff prompt's read-list, and through its outbound consumption-by-conversation edge already declared as `work_ticket_consumed_by_conversation` (tentative) in `conversation.md` section 3.3.2.

---

*End of document.*
