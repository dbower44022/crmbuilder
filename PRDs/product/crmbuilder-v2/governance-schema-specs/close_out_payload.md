# Governance Entity Schema Spec — `close_out_payload`

**Last Updated:** 05-21-26 19:30
**Status:** Draft v1.0 — produced by schema-design conversation
**Position in workstream:** Fifth of six governance-entity schema specs (`workstream` → `conversation` → `reference_book` → `work_ticket` → `close_out_payload` → `deposit_event`)
**Predecessor conversation:** SES-051 (`work_ticket` schema-design conversation)
**Successor conversation:** `deposit_event` schema design — kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-deposit-event.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-21-26 19:30 | Doug Bower / Claude | Initial draft. Produced by the fifth schema-design conversation in the governance-entity schema-design workstream. Adopts the six cross-spec precedents now in force: the three from SES-048 (references-edge over foreign-key for parent-child governance relationships, per-status lifecycle timestamps for workflow-shaped lifecycles, terminal-states-are-terminal discipline), the one from SES-049 (typed sequencing edges introduced when entity-family frequency justifies), the one from SES-050 (documentary-shaped lifecycles inherit base timestamps only; workflow-shaped lifecycles get per-status timestamps), and the one from SES-051 (terminal-state consumption requires the inbound consumption edge — the inverse of supersession-requires-edge). Realizes the `applied`-requires-inbound-edge rule that SES-051's section 3.4.3 named close_out_payload as the parallel for. Declines a `payload_content` JSON column in favour of a single repo-relative `close_out_payload_file_path` pointer per the file-tracking-entity precedent locked by DEC-139 (reference_book) and DEC-145 (work_ticket); the file remains the authoritative artifact, the database carries the governance view. Declines a `close_out_payload_kind` enum because every record is the same artifact kind (no taxonomic axis exists). Declines a `close_out_payload_schema_version` field because the payload structure has been stable across all 50+ historical files; a future migration adds the column if structure evolves. Introduces one new relationship-kind vocabulary entry — `close_out_payload_produced_by_conversation` — outbound to the conversation that produced the payload, required at all statuses. The inbound `deposit_event_applies_close_out_payload` kind is named here informationally; its registration belongs to `deposit_event.md`. Adds no new cross-spec precedent — every architectural call follows an inherited precedent on its own facts. Sixteen acceptance criteria captured. Six decisions and zero planning items authored at conversation close; PI-022 continues to cover retroactive backfill for close_out_payload records alongside the other governance entity types. |

---

## Change Log

**Version 1.0 (05-21-26 19:30):** Initial creation. Defines `close_out_payload` as the V2 governance entity type that hosts the single-use state-write package concept per DEC-117's third family — the structured payload produced at a conversation's close, intended for application to the governance database via the standard apply script. Establishes six content/classification fields (`close_out_payload_identifier`, `close_out_payload_title`, `close_out_payload_description`, `close_out_payload_notes`, `close_out_payload_status`, plus the file-pointer field `close_out_payload_file_path`) plus seven timestamp columns (three inherited base, four per-status lifecycle: `close_out_payload_ready_at`, `close_out_payload_applied_at`, `close_out_payload_cancelled_at`, `close_out_payload_superseded_at`). Establishes a five-status workflow-shaped lifecycle (`drafted` → `ready` → `applied`, plus terminals `cancelled` and `superseded`) with truly-terminal terminal states inherited from workstream and conversation precedents, an applied-requires-edge access-layer rule realizing the inverse-pattern precedent locked by SES-051, and a supersession-requires-edge rule mirroring the pattern from prior specs. Adopts the repo-relative file_path semantics from `reference_book.md` and `work_ticket.md` verbatim; the path canonically points at a file under `PRDs/product/crmbuilder-v2/close-out-payloads/` (the historical home for payload files) but is not constrained to that directory at the validation layer. Declines a content-storage column on the table — the payload's content lives in the file under git, exactly as `reference_book` records' content does. Declines a kind enum because every record is the same kind. Declines a schema-version field as premature; the structure has been stable. Introduces one new relationship-kind vocabulary entry, `close_out_payload_produced_by_conversation`, outbound from this entity to the conversation entity, with cardinality "exactly one outbound edge per payload" at all statuses. The inbound `deposit_event_applies_close_out_payload` kind from the next schema-design conversation is listed in section 3.3.2 informationally; its `vocab.py` registration belongs to `deposit_event.md`. Standard API endpoint set with no deviations. Default soft-delete with restore, explicitly distinct from `cancelled` status (a lifecycle outcome — the payload was abandoned without being applied) and `applied` status (a successful-use outcome — the deposit_event records the apply). Default UI layout with one natural addition paralleling `work_ticket.md`'s pattern: a Status filter combo in the master-pane toolbar (because browse-by-status is the operational pattern for payloads — `ready` to see what is queued up for apply, `applied` to see what has been deposited). Sixteen acceptance criteria captured. Six decisions and zero planning items authored at conversation close (PI-022 covers retroactive backfill for close_out_payload records as it does for the other governance entity types).

---

## 1. Purpose and Position

This document specifies the `close_out_payload` entity type for V2's storage layer. It is the **fifth of six** schema specs produced by the governance-entity schema-design workstream — designed after `workstream.md`, `conversation.md`, `reference_book.md`, and `work_ticket.md` so that every entity the close_out_payload relates to or inherits patterns from is a settled referent, and designed before `deposit_event.md` so that the deposit_event schema-design conversation can treat close_out_payload as the settled parent of the family-3 (deposit bucket) pairing established by DEC-118.

The workstream is governed by `governance-schema-workstream-plan.md`. Each schema spec conforms to the template in `governance-entity-schema-spec-guide.md`. Six specs total are produced — `workstream`, `conversation`, `reference_book`, `work_ticket`, `close_out_payload`, then `deposit_event` — feeding a seventh build-planning conversation that integrates them into a coherent release.

`close_out_payload`'s primary scope in this release is to host the single-use state-write package concept per DEC-117's third artifact family — the structured payload produced at a conversation's close, declaring what records should be written to the governance database when the payload is applied. The schema is intentionally minimum-viable. A content-storage column, a kind enum, a schema-version field, and a record-counts-by-kind summary are all deliberately out of scope; each is deferred to a future release pending real-use signal or is satisfied by deriving the value from the file at use time.

This conversation **inherits six cross-spec precedents** now in force and applies them throughout:

- **References-edge over foreign-key for parent-child governance relationships** (DEC-124, SES-048). The close_out_payload-to-conversation relationship lives in `refs` with the new kind `close_out_payload_produced_by_conversation`, never as a foreign-key column. No modification to the conversations table. No `conversation_id` column on the close_out_payloads table.
- **Per-status lifecycle timestamps for workflow-shaped lifecycles** (DEC-126, SES-048). Close_out_payload is workflow-shaped (it moves through distinct workflow states with operational meaning at each); the schema carries one timestamp column per non-starter status, server-set on transition.
- **Terminal-states-are-terminal discipline** (DEC-125, SES-048). Once a payload reaches `applied`, `cancelled`, or `superseded`, no transitions out are admitted — including transitions between terminal states. A payload that needs to be re-applied is modelled as a new payload that supersedes the prior, not as a reactivation of the terminal record.
- **Typed sequencing edges introduced when entity-family frequency justifies** (DEC-133, SES-049). Close_out_payload sequencing (one payload superseded by another) is rare but real; this spec uses the existing generic `supersedes` kind for the same-type pair rather than introducing a typed `close_out_payload_succeeds_close_out_payload` kind. The frequency-justified test points at "generic" for this entity, consistent with workstream's posture and unlike conversation's.
- **Documentary-vs-workflow distinction** (DEC-137, SES-050). Close_out_payload is workflow-shaped, not documentary; per-status lifecycle timestamps apply, parallel to work_ticket and unlike reference_book.
- **Terminal-state consumption requires the inbound consumption edge** (DEC-143, SES-051). This spec realizes the rule SES-051 explicitly named as the precedent's first downstream application: the transition to `applied` requires the inbound `deposit_event_applies_close_out_payload` edge. The edge is named here as the inbound name only; the kind's `vocab.py` registration belongs to `deposit_event.md`.

This conversation introduces **no new cross-spec precedent of its own**. Every architectural call follows an inherited precedent on its own facts. The sixth and final schema-design conversation (`deposit_event.md`) is expected to introduce the append-only-with-one-timestamp precedent that the family-3 deposit-event side of the pairing requires.

---

## 2. Summary

A `close_out_payload` record in V2 represents one structured payload produced at a conversation's close — the slip declaring what records should be written to the governance database when the payload is applied. Real examples already implicit in the project's history include the SES-046 payload (governance scoping conversation's close-out, applied 05-20-26), the SES-049 payload (conversation schema-design close-out, applied 05-21-26), the SES-050 payload (reference_book schema-design close-out, applied 05-21-26), and the SES-051 payload (work_ticket schema-design close-out, applied 05-21-26); a dozen earlier payloads from SES-001 through SES-044 follow the same structural shape. Each is structurally a single-use state-write package with a defined production-moment (conversation close), a single application moment (when the apply script runs), and an outcome captured in a paired deposit_event record — but before this entity type lands, each exists only as a JSON file under `PRDs/product/crmbuilder-v2/close-out-payloads/` and as a free-text mention in the session record the payload itself authored. The `close_out_payload` entity makes them queryable as governance objects.

The schema in this release is the thinnest shape that captures the single-use state-write package concept faithfully: a human-readable title, a one-sentence description, an optional consultant notes field, a five-status workflow-shaped lifecycle with timestamps for each non-starter transition, a repo-relative file_path pointing at the canonical JSON file, mandatory production by exactly one conversation via a references-edge to that conversation, and standard same-type supersession via the existing generic `supersedes` kind when a payload is replaced by another for the same conversation. The schema deliberately omits a content-storage column (the file under git is the authoritative artifact), a kind enum (every record is the same kind), a schema-version field (the payload structure has been stable across all 50+ historical files), and a denormalized record-counts-by-kind summary (derivable from the file at use time if a query need surfaces). The inbound linkage from the deposit_event entity that records the apply event is designed inbound from that entity's own spec in the next schema-design conversation; this spec lists it informationally only.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `close_out_payload` |
| Display name (singular) | Close-Out Payload |
| Display name (plural) | Close-Out Payloads |
| Identifier prefix | `COP` |
| Identifier format | `COP-NNN`, zero-padded to 3 digits (e.g., `COP-001`, `COP-046`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /close-out-payloads/next-identifier` |

**Identifier-prefix posture.** `COP` is three letters, matching the most common existing prefix length (`DEC`, `SES`, `RSK`, `TOP`, `REF`, `CHR`, `STA`, `DOM`, `ENT`). The two-letter forms `CO` and `CP` were rejected for ambiguity (`CO` reads as "Company" or "Carbon monoxide"; `CP` reads as too many generic abbreviations). The four-letter alternatives `CLOUT`, `PYLD`, and `CLOSE` add length without disambiguation. The five-letter `CLOSEOUT` is too long. `COP` is the kickoff prompt's working assumption and survives the collision check against the full existing prefix list (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRMC, ENG, WS, CONV, RB, WT). Per DEC-123's affirmation that each downstream conversation makes its own prefix-length call within the 2-to-5 letter range, three letters is appropriate here.

### 3.2 Fields

Field naming follows the parent-prefix convention per DEC-046: all fields including identifier, file pointer, and timestamps are prefixed `close_out_payload_`.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `close_out_payload_identifier` | TEXT | yes | server-assigned | `^COP-\d{3}$`, unique | The close-out payload identifier in `COP-NNN` format. Server-assigned when omitted from POST body; helper endpoint `GET /close-out-payloads/next-identifier` returns the next available value. |
| `close_out_payload_title` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Close-out payload title in the project's working language (e.g., "SES-046 governance scoping close-out", "SES-048 workstream schema close-out", "SES-051 work_ticket schema close-out"). Typically derived from the conversation whose close the payload effected; the title is the human-readable handle for the payload distinct from its file_path. |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `close_out_payload_description` | TEXT | yes | — | non-empty trimmed | One- or two-sentence description of what the payload contains and what conversation produced it. The historical `label` field at the top of each payload file (e.g., "SES-046 governance entity schema scoping: 1 session, 6 decisions (DEC-117..122), 1 planning item (PI-022), 7 references") is the natural value for this field, restated in prose. Plain text in this release. |
| `close_out_payload_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of the payload's user-facing summary. Used to capture decisions made during payload authoring that don't fit the payload's structured content (e.g., "this payload supersedes COP-008 because the original missed the PI-001 update; see DEC-... for context"). Plain text in this release; structured-journal pattern deferred to signal. |

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `close_out_payload_status` | TEXT | yes | `drafted` | enum: `drafted` \| `ready` \| `applied` \| `cancelled` \| `superseded`; valid transitions per section 3.4.1; additional rules for `applied` and `superseded` per sections 3.4.3 and 3.4.4 | Lifecycle status. See section 3.4 for the full state machine. |

#### 3.2.4 Relationship fields

None. The parent-child relationship from this payload to the conversation that produced it lives in the universal references table per the inherited precedent from workstream.md and Decision 1 of this conversation. The inbound apply-linkage from the deposit_event record (when present) also lives in `refs`. The supersession linkage to a successor payload (when present) uses the existing generic `supersedes` kind for the same-type pair. No foreign-key columns on the close_out_payloads table.

#### 3.2.5 File pointer field

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `close_out_payload_file_path` | TEXT | yes | — | non-empty trimmed; must be a repo-relative path (no leading slash, no `..` segments, no scheme prefix); unique within the engagement | Repo-relative path to the canonical JSON file (e.g., `PRDs/product/crmbuilder-v2/close-out-payloads/ses_046.json`). Resolution at use time is performed against the consuming repository's root — typically the crmbuilder repo for dogfood records and the client repo for engagement-specific records. The path is not validated for existence at write time (the file may be authored separately and the record updated to point at it, or the record may be authored first and the file committed after); a future build prompt may add a "check path resolves" verification step. The historical convention is `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` where `NNN` is the session number the payload's close-out produced; the schema does not enforce this convention at the validation layer. The same `file_path` value may legally coexist as a `work_ticket_file_path` or `reference_book_file_path` value on a parallel record per the section-2 boundary discipline established by `work_ticket.md`; uniqueness is within the close_out_payloads table only, not across the union of file paths. |

**Path-semantics parity with `work_ticket.md` and `reference_book.md`.** The `close_out_payload_file_path` column follows the same repo-relative semantics as `reference_book_file_path` per `reference_book.md` section 3.2.5 and `work_ticket_file_path` per `work_ticket.md` section 3.2.5. The three columns are independent; in principle the same string could be the canonical file_path of all three record types in the same engagement, with each record providing the governance view appropriate to its lifecycle. In practice the path patterns differ — reference_book paths point at long-lived PRDs and methodology documents, work_ticket paths point at kickoff and Claude Code prompts, close_out_payload paths point at JSON files under `close-out-payloads/`. The cross-table coexistence rule is structural admission, not an expected pattern.

**No `payload_content` column.** The payload's content (the structured JSON declaring session, decisions, planning_items, references to be written) lives in the file under git, not in the database. This is the cross-spec precedent locked by `reference_book.md` and inherited by `work_ticket.md`: file-tracking entities store the path, not the content. The apply script reads the file at apply time; the database carries the governance view (identifier, title, description, status, lifecycle timestamps, references to producing conversation and applying deposit_event). Section 3.8.3 documents the future-add path if a real query need surfaces (e.g., "preview the records this payload would write" as a UI affordance) — the addition is a derived-view endpoint that parses the file on demand, not a content column on the table.

#### 3.2.6 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `close_out_payload_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `close_out_payload_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `close_out_payload_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |
| `close_out_payload_ready_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on the `drafted` → `ready` transition. Once set, not user-editable. Remains null on payloads that move directly from `drafted` to `cancelled` or `superseded` without ever entering `ready`. |
| `close_out_payload_applied_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on the `ready` → `applied` transition. Once set, not user-editable. Mutually exclusive with `close_out_payload_cancelled_at` and `close_out_payload_superseded_at` — exactly one of the three terminal-state timestamps is populated. |
| `close_out_payload_cancelled_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on any transition to `cancelled` (from `drafted` or `ready`). Once set, not user-editable. |
| `close_out_payload_superseded_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on any transition to `superseded` (from `drafted` or `ready`). Once set, not user-editable. |

**No `close_out_payload_drafted_at` column.** A payload's drafted-at moment is always equal to its `close_out_payload_created_at` (the default starter status is `drafted`, set at insert time). A separate column would be redundant. The backfill case for historical payloads created with non-starter status uses `close_out_payload_created_at` with a backfill timestamp; the distinction is not tracked separately in this release.

**No storage-level length caps** on text fields, matching the precedents from workstream, conversation, reference_book, and work_ticket. UI placeholder text provides soft guidance.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

One outgoing reference kind introduced by this spec, plus the existing generic `supersedes` reused for the same-type supersession pair. Both modelled as references-table edges per the inherited precedent.

**Production linkage.** Every close_out_payload record must have exactly one outbound reference edge identifying the conversation whose close produced the payload. The relationship is required at every status — a payload that has no producing conversation is malformed by family-3 definition (per DEC-117, a payload is "produced at conversation close"; the producing conversation is part of the payload's identity).

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `close_out_payload_produced_by_conversation` | `close_out_payload` | `conversation` | The payload was produced at this conversation's close. Cardinality: a close_out_payload has exactly one outbound edge of this kind (enforced at the access layer); a conversation may be the target of zero or more such edges (zero if the conversation has not yet closed; one in the typical case of a single payload per conversation; more than one if drafts were superseded and replaced before the conversation's final payload was applied). The edge is required at every payload status, including `drafted`. |

**Supersession linkage.** When a payload's status is set to `superseded`, it must have an outgoing reference edge identifying the successor payload that carries the apply forward. The relationship uses the existing generic `supersedes` reference kind (already registered in `vocab.py`'s `REFERENCE_RELATIONSHIPS`, and already admitted for `(close_out_payload, close_out_payload)` once `close_out_payload` is added to `ENTITY_TYPES` because `_kinds_for_pair`'s `source_type == target_type` rule admits `supersedes` for any same-type pair). No new kind is introduced for this relationship; the established vocabulary is reused, identical to the workstream, conversation, reference_book, and work_ticket patterns.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `supersedes` (existing kind, reused) | `close_out_payload` | `close_out_payload` | This payload was replaced; the target payload carries forward the apply. Required when `source.status = 'superseded'`; access-layer enforces. |

No other outgoing reference kinds in this release. Typed predecessor-successor chains between non-superseding payloads are not modelled — payloads are not naturally sequenced (each is produced by exactly one conversation, which itself is sequenced by `conversation_succeeds_conversation`); the conversation-side chain provides the timeline. Per DEC-133's frequency-justified test, no typed sequencing kind on the payload side is justified.

#### 3.3.2 Inbound relationships (declared by source-side specs)

`close_out_payload` is the target of one inbound reference kind from the next schema-design conversation's entity, `deposit_event`. The kind, mechanism, and cardinality:

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `deposit_event_applies_close_out_payload` | `deposit_event` | `close_out_payload` | references-table edge | one-to-one in the typical case (each successful apply produces one deposit_event linking to one close_out_payload; each close_out_payload has at most one inbound edge of this kind, enforced at the access layer) | The deposit_event records the application of this close_out_payload to the database. **Required-when** rule from close_out_payload's side: when close_out_payload.status = `applied`, exactly one inbound edge of this kind must be present (see section 3.4.3 for the applied-requires-edge rule). **At-most-one** rule under the working assumption that a payload is applied at most once: multiple inbound edges return HTTP 422 at the access layer. Whether re-apply is supported (which would permit multiple inbound edges with different deposit_event records) is a deposit_event-side question deferred to that schema-design conversation; this spec admits at-most-one under the safe default. |

This table is informational from `close_out_payload.md`'s perspective. The `vocab.py` registration of `deposit_event_applies_close_out_payload`, the `_kinds_for_pair` clause binding it to the `(deposit_event, close_out_payload)` pair, and the at-most-one-edge-per-target access-layer rule belong to the `deposit_event.md` schema-design conversation. This spec lists the kind here because the applied-requires-edge rule in section 3.4.3 names it, and because the cross-spec consistency check before build-planning relies on both specs naming the relationship.

Also informational: any conversation may carry a generic `references` edge from this close_out_payload to other governance records the payload's authoring referenced (e.g., a payload may `references` a reference_book record that documented the conversation's methodology). The existing default rules in `_kinds_for_pair` admit `references` for any (source, target) pair where both types are in `ENTITY_TYPES`; no per-pair registration is required.

#### 3.3.3 Hierarchy

Close_out_payload does not use the self-referential parent-child hierarchy pattern. Payloads are flat; the only intra-type relationship is the `supersedes` same-type chain when a draft is replaced. This is consistent with the workstream, conversation, reference_book, and work_ticket precedents — none of those entities adopted hierarchy either, and close_out_payload has no real-use signal suggesting it should.

#### 3.3.4 New reference vocabulary additions this spec requires

The following additions are named here and aggregated by the build-planning conversation into one consolidated `vocab.py` update plus one Alembic migration on the `refs.relationship_kind` CHECK constraint, alongside the additions named by the other governance schema specs.

| Add to | Value | Rationale |
|--------|-------|-----------|
| `REFERENCE_RELATIONSHIPS` | `close_out_payload_produced_by_conversation` | Outbound production linkage from a payload to its producing conversation. Realizes Decision 1 of this conversation; required at all statuses. |
| `ENTITY_TYPES` | `close_out_payload` | This entity type. |
| `_kinds_for_pair` | `if source_type == 'close_out_payload' and target_type == 'conversation': kinds.add('close_out_payload_produced_by_conversation')` | Source-target constraint binding the production-linkage kind to the matching pair only. |

The existing generic `supersedes` kind is reused for the `(close_out_payload, close_out_payload)` supersession edge; no addition required for that relationship. The `_kinds_for_pair` rule already admits `supersedes` for any same-type pair, so once `close_out_payload` is in `ENTITY_TYPES`, the rule applies automatically. The existing defaults for the generic `references` and `is_about` kinds admit all generic citations to and from close_out_payload without additional clauses. The inbound `deposit_event_applies_close_out_payload` kind is the responsibility of `deposit_event.md` to register; it is not added here.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `drafted` | The payload record has been created and its file_path declared, but the payload is not yet finalized as ready for apply. **Default starter status.** The producing conversation may still be in flight. | (none — starter) | `ready`, `cancelled`, `superseded` |
| `ready` | The payload is finalized and queued for apply. The producing conversation has closed (or is in its closing turn); the file at `close_out_payload_file_path` is complete and apply-ready. | `drafted` | `applied`, `cancelled`, `superseded` |
| `applied` | The apply has run; a deposit_event record exists naming this payload's apply outcome. Terminal. Requires an inbound `deposit_event_applies_close_out_payload` edge per section 3.4.3. | `ready` | (none — terminal) |
| `cancelled` | The payload was abandoned without being applied, and no successor payload carries the work forward. Reachable from `drafted` or `ready`. Typical case: the producing conversation was itself cancelled before close, or the payload was authored speculatively and then discarded. Terminal. | `drafted`, `ready` | (none — terminal) |
| `superseded` | The payload was abandoned without being applied, but a successor payload carries the apply forward (typically a rewritten payload addressing an issue discovered before apply). Terminal. Requires an outgoing `supersedes` edge to the successor payload per section 3.4.4. Reachable from `drafted` or `ready`. | `drafted`, `ready` | (none — terminal) |

#### 3.4.2 Transition semantics

The status lifecycle is a **forward-only workflow timeline with three truly terminal terminal states**, identical in shape to work_ticket's lifecycle and inheriting the truly-terminal posture from workstream and conversation. Each terminal state admits no outgoing transitions; reactivation of a terminal payload is not supported. The rationale: a payload's apply is a once-only governance act, and "reopening" a finished payload (whether applied, cancelled, or superseded) blurs the audit semantics. A payload that needs to be re-applied is modelled as a new payload that supersedes the prior — typically with a fresh file_path pointing at a corrected JSON file. Reactivation as a status transition is not a workflow this release supports.

Transitions between terminal states are forbidden (e.g., a `cancelled` payload cannot become `applied`; an `applied` payload cannot become `superseded`). The access layer enforces this at PATCH and PUT time with HTTP 422 `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

#### 3.4.3 Applied-requires-edge rule

Setting `close_out_payload_status` to `applied` requires the record to have an inbound reference edge of kind `deposit_event_applies_close_out_payload` from a deposit_event record. The access layer enforces this as a single combined validation, mirroring the consumed-requires-edge pattern locked by DEC-143:

- POST creating a record with `status = 'applied'` and no inbound `deposit_event_applies_close_out_payload` edge: HTTP 422 `{"error": "applied_payload_requires_deposit_event_edge"}`.
- PUT or PATCH transitioning an existing record to `status = 'applied'` without an inbound `deposit_event_applies_close_out_payload` edge present: same 422.
- POST or PATCH supplying the inbound edge in the same transaction as the status set: accepted; the access layer validates the edge and the status set together at commit time. (Coordinated transactional behavior across the close_out_payload and deposit_event tables and the references table is a build-planning concern — see section 3.8.1.)
- DELETE on the inbound edge while the target record still has `status = 'applied'`: HTTP 422 `{"error": "applied_payload_requires_deposit_event_edge"}`. The status must be changed first (e.g., via supersession with a new payload addressing the same apply target) or the target close_out_payload must be soft-deleted.

**Cross-spec precedent realized.** This rule is the first downstream application of the terminal-state-consumption-requires-edge precedent locked by DEC-143 (work_ticket's consumed-requires-edge). The structural parallel is exact: work_ticket transitions to `consumed` require the inbound `conversation_opens_against_work_ticket` edge from the consuming conversation; close_out_payload transitions to `applied` require the inbound `deposit_event_applies_close_out_payload` edge from the applying deposit_event. Both terminal states are defined by an external act (consumption / application); the edge naming the actor must be present before the status transition is admitted. The naming differs ("consumed" vs "applied") because the verb-orientation of the acting relationship differs, but the rule pattern is identical.

#### 3.4.4 Supersession-requires-edge rule

Setting `close_out_payload_status` to `superseded` requires the record to have an outgoing reference edge of kind `supersedes` to another close_out_payload record. The rule is identical to the workstream / conversation / reference_book / work_ticket pattern (DEC-125 and successors), and is enforced at the access layer with the same 422 shape and the same in-transaction admission of the edge in the status-setting payload:

- POST creating a record with `status = 'superseded'` and no outgoing `supersedes` edge: HTTP 422 `{"error": "superseded_payload_requires_successor_edge"}`.
- PUT or PATCH transitioning to `status = 'superseded'` without the edge: same 422.
- DELETE on the outgoing `supersedes` edge while the source record has `status = 'superseded'`: HTTP 422 with the parallel error.

#### 3.4.5 Production-edge required at all statuses

Independent of the applied-requires-edge and supersession-requires-edge rules, the close_out_payload schema enforces production-linkage semantics at all statuses. Every payload record must have exactly one outbound edge of kind `close_out_payload_produced_by_conversation` regardless of current status — including `drafted`. The rule realizes DEC-117's family-3 definition: a close-out payload is "produced at a conversation's close"; the producing conversation is part of the payload's identity.

- POST creating a record without the outbound `close_out_payload_produced_by_conversation` edge: HTTP 422 `{"error": "payload_requires_producing_conversation_edge"}`.
- PATCH or PUT that would remove the edge: same 422.
- DELETE of the edge directly on the references table while the close_out_payload record exists: same 422.
- Multiple outbound edges of this kind on the same close_out_payload record: HTTP 422 `{"error": "payload_single_producer_violation"}`, enforced at the access layer regardless of status. A payload is produced by exactly one conversation; the at-most-one rule applies symmetrically to the exactly-one rule.

#### 3.4.6 Soft-delete semantics

Default V2 base behavior: DELETE sets `close_out_payload_deleted_at`; soft-deleted records do not appear in list endpoints; "show deleted" toggle supported per the Decisions panel pattern; POST `/restore` clears the timestamp. Append-only is not adopted for this entity — the deposit_event record (the next conversation's entity) is the natural append-only record for the deposit bucket family; close_out_payload remains soft-delete because legitimate cleanup operations exist (e.g., removing a stale draft that was never finalized).

Soft-delete is **explicitly distinct from `cancelled` status** and from `applied` terminal status:

- `cancelled` is a lifecycle outcome — the payload was abandoned without being applied; the record is still meaningful as a historical artifact and remains visible in list endpoints.
- `applied` is a successful-use outcome — the deposit_event records the apply; the payload record continues to exist as the canonical reference for what was deposited.
- `soft-deleted` is a record-management operation — the consultant removed the record from default views, typically because it was a noise entry (e.g., a misfired draft). The record can be restored.

A close_out_payload record can be in any of the five lifecycle statuses and additionally soft-deleted; the two states are orthogonal. Soft-deleted `applied` records are unusual but admitted (e.g., a consultant cleaning up records in a test engagement).

### 3.5 API Surface

#### 3.5.1 Endpoints

The standard V2 endpoint set with no deviations:

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/close-out-payloads` | — | List. Supports `?include_deleted=true` to include soft-deleted records and `?status=<value>` to filter by lifecycle status (single value or comma-separated list for status-set filtering). |
| GET | `/close-out-payloads/{identifier}` | — | Single fetch. Returns 404 if not found (including soft-deleted unless `?include_deleted=true`). |
| POST | `/close-out-payloads` | full close_out_payload JSON; identifier optional | Create. Identifier server-assigned when omitted. Default `close_out_payload_status` is `drafted` if omitted. The body may include a `references` array; the access layer validates the production-edge requirement (section 3.4.5) and, if status is `applied` or `superseded`, the corresponding edge requirement (sections 3.4.3 and 3.4.4) at commit time. |
| PUT | `/close-out-payloads/{identifier}` | full close_out_payload JSON | Full replace. Status-transition validation per section 3.4.1. |
| PATCH | `/close-out-payloads/{identifier}` | partial close_out_payload JSON | Partial update. Status-transition validation per section 3.4.1. |
| DELETE | `/close-out-payloads/{identifier}` | — | Soft delete. Sets `close_out_payload_deleted_at`. |
| POST | `/close-out-payloads/{identifier}/restore` | — | Restore from soft delete. Clears `close_out_payload_deleted_at`. Returns 422 if record is not currently soft-deleted. |
| GET | `/close-out-payloads/next-identifier` | — | Returns `{"next": "COP-NNN"}` for the next available identifier. |

All endpoints return the `{data, meta, errors}` envelope per existing V2 convention.

#### 3.5.2 Identifier auto-assignment

Default V2 server-side auto-assignment on POST omission. The helper endpoint `GET /close-out-payloads/next-identifier` exposes the same computation for clients that need the identifier before submitting (e.g., the desktop dialog populating a read-only Identifier label).

### 3.6 User Interface Considerations

Default layout per spec guide section 3.6, with one natural addition paralleling `work_ticket.md`'s pattern: a Status filter combo in the master-pane toolbar. The addition follows naturally from the operational pattern of browsing payloads by lifecycle status (`ready` to see what is queued up for apply; `applied` to see what has been deposited) and does not constitute architectural deviation.

#### 3.6.1 Sidebar

The Close-Out Payloads panel goes in the Governance sidebar group, after the Work Tickets panel (the predecessor entity in the schema-design workstream order). Position within the group is the build-planning conversation's call; the working assumption is that the six new governance entities sit at the end of the existing Governance group in workstream order. The build-planning conversation may introduce a sub-grouping if the resulting Governance group becomes hard to scan; that question is out of scope for this spec.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with columns:

| Column | Header | Width | Notes |
|--------|--------|-------|-------|
| `close_out_payload_identifier` | Identifier | narrow | Sortable; default sort. |
| `close_out_payload_title` | Title | wide | Human-readable handle. |
| `close_out_payload_status` | Status | narrow | Enum value rendered as-is. |
| `close_out_payload_updated_at` | Updated | narrow | Localized date/time. |

Default sort: identifier ascending. Right-click context menu offers New / Edit / Delete / Restore, consistent with the user-interface version 0.3 governance-entity panels per DEC-035 and DEC-036.

**Status filter combo in the master-pane toolbar.** A single-select combo offering "All", "Drafted", "Ready", "Applied", "Cancelled", "Superseded" (and an "All including deleted" toggle separately) lets the consultant scope the visible list. The combo's default is "All (excluding deleted)"; selecting a single value narrows to that status; the consultant can scan `ready` payloads to see what is queued for apply or `applied` payloads to see the deposit history. The toolbar combo is implemented as part of the standard `ListDetailPanel` filter machinery; no new widget is introduced.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `close_out_payload_identifier` — read-only label.
2. `close_out_payload_title` — single-line text editor.
3. `close_out_payload_description` — multi-line text editor with placeholder "One- or two-sentence description of what the payload contains".
4. `close_out_payload_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default. The collapsed default reinforces that the field is internal consultant scratchpad, not part of the payload's user-facing summary.
5. `close_out_payload_status` — combo box with the five enum values; the combo's selectable subset at any moment is the union of `{current_status}` and the valid successors of the current status per section 3.4.1, so the user cannot select an invalid transition. Server-side validation is the final gate; the combo's filtering is a UX convenience.
6. `close_out_payload_file_path` — single-line text editor with placeholder "Repo-relative path, e.g., `PRDs/product/crmbuilder-v2/close-out-payloads/ses_046.json`". No file-system existence validation in this release; the value is stored verbatim after trim.
7. **Lifecycle timestamps section** — read-only labels rendered only for the timestamps that are non-null. A `drafted` payload sees no lifecycle timestamps; a `ready` one sees Ready-at; an `applied` one sees Ready-at and Applied-at; a `cancelled` one sees Cancelled-at and (optionally) Ready-at; a `superseded` one sees Superseded-at and (optionally) Ready-at. The conditional rendering mirrors the underlying nullable columns and keeps the detail pane clean, parallel to workstream's pattern.
8. `ReferencesSection` widget — renders the outbound production-edge (`close_out_payload_produced_by_conversation`) prominently at top because it is the family-defining relationship, then the inbound apply-edge from a deposit_event record (`deposit_event_applies_close_out_payload`) when present, then the outbound supersession edge (`supersedes`) when present, then any inbound supersession edges (other payloads that this one superseded), then generic `references` edges and `is_about` edges in either direction. The "Add reference" affordance from the user-interface version 0.3 references-create dialog filters available kinds and target entity types by the strict vocab per `_kinds_for_pair`.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `close_out_payload_identifier` not shown in create mode (server-assigned).
- `close_out_payload_status` defaults to `drafted`; the user may select a different starter value for backfill of historical records — for example, when creating a payload record for a payload that was applied before this entity type existed, the user can set status directly to `applied` and the create endpoint accepts the matching lifecycle timestamps (`close_out_payload_ready_at`, `close_out_payload_applied_at`) as user-supplied for the backfill case. Backfill behavior is access-layer-detected by the absence of intermediate transitions and is documented as part of section 3.8 (Open questions — retroactive backfill).
- `close_out_payload_file_path` required.
- The production-edge (`close_out_payload_produced_by_conversation`) required at all statuses — supplied via the ReferencesSection's "Add reference" affordance before save, or via the create payload's `references` array. The create dialog detects the missing edge and surfaces a hint inline ("This payload has no producing conversation — add the production edge via the References section before saving.").
- Required-field validation client-side before submit.
- Server-side validation errors (uniqueness, format, transition, production-edge, applied-requires-edge, supersession-requires-edge, single-producer) surface inline.

#### 3.6.5 Edit dialog

Same shape as create. `close_out_payload_identifier` displayed as read-only label. Status transitions enforced per section 3.4.1; the combo box restricts selectable values to valid transitions plus the current value (no-op). Setting status to `applied` requires the inbound `deposit_event_applies_close_out_payload` edge to be present; the edit dialog detects this and surfaces a hint inline if the edge is missing ("This payload has no deposit_event yet — add the apply edge via the References section before transitioning to Applied. In practice the deposit_event-side dialog supplies the edge as part of recording the apply."). Setting status to `superseded` requires an outgoing `supersedes` edge to be present (added via the ReferencesSection's "Add reference" affordance before the status change is committed, or via the same patch payload); attempting to commit `superseded` without the edge surfaces the 422 inline.

The production-edge cannot be removed via the edit dialog while the record exists; the ReferencesSection's "Remove" affordance is suppressed for the `close_out_payload_produced_by_conversation` edge per the single-producer rule of section 3.4.5. Replacing the producing conversation (rare) requires a deliberate workflow not exposed in this release; the build-planning conversation may add an "Edit production-edge" affordance if a real use case surfaces.

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `close_out_payload_identifier` value (e.g., `COP-046`) to enable the Delete button, matching the user-interface version 0.3 governance-entity patterns. Confirmation soft-deletes the record. Soft-deleting an `applied` payload is admitted but unusual — the deposit_event record continues to reference the soft-deleted payload, and the inbound edge remains valid (soft-deletion does not break references at the access layer; only hard deletion would, and hard deletion is not exposed).

### 3.7 Acceptance Criteria

The following sixteen statements define what "this entity type is correctly implemented in the eventual build" looks like. Each is concrete and testable; the build-planning conversation translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `close_out_payloads` table with all eleven columns (`close_out_payload_identifier`, `close_out_payload_title`, `close_out_payload_description`, `close_out_payload_notes`, `close_out_payload_status`, `close_out_payload_file_path`, `close_out_payload_created_at`, `close_out_payload_updated_at`, `close_out_payload_deleted_at`, `close_out_payload_ready_at`, `close_out_payload_applied_at`, `close_out_payload_cancelled_at`, `close_out_payload_superseded_at`), correct types and constraints, and runs both forward and backward without error.

2. **`close_out_payload_identifier` format constraint enforced.** Insertions with `close_out_payload_identifier` not matching `^COP-\d{3}$` raise a validation error at the access layer.

3. **`close_out_payload_title` uniqueness enforced case-insensitively.** Inserting a second row whose `close_out_payload_title` matches an existing row by lowercase comparison raises a uniqueness violation.

4. **`close_out_payload_status` enum and transition validation.** Insertions with `close_out_payload_status` outside the five-value enum are rejected. PATCH or PUT requesting an invalid transition (e.g., `applied` → `ready`, or `cancelled` → `applied`) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

5. **Terminal states are truly terminal.** All three terminal statuses (`applied`, `cancelled`, `superseded`) reject every outgoing transition, including transitions between terminal states (e.g., `cancelled` → `superseded`, `applied` → `superseded`). Same 422 shape.

6. **Applied-requires-deposit-event-edge rule.** POST or PATCH setting `close_out_payload_status = 'applied'` without an inbound `deposit_event_applies_close_out_payload` edge from a deposit_event record returns HTTP 422 `{"error": "applied_payload_requires_deposit_event_edge"}`. The edge may be supplied in the same request body (typically by the deposit_event-side coordinated create). Deletion of the edge on an `applied` payload returns the parallel 422.

7. **Supersession-requires-edge rule.** POST or PATCH setting `close_out_payload_status = 'superseded'` without an outgoing `supersedes` edge to another close_out_payload record returns HTTP 422 `{"error": "superseded_payload_requires_successor_edge"}`. The edge may be supplied in the same request body. Deletion of an existing `supersedes` edge on a `superseded`-status record returns the parallel 422.

8. **Production-edge required at all statuses.** POST creating a record without an outbound `close_out_payload_produced_by_conversation` edge returns HTTP 422 `{"error": "payload_requires_producing_conversation_edge"}`. PATCH or PUT that would remove the edge returns the same 422. Multiple outbound edges of this kind on the same record return HTTP 422 `{"error": "payload_single_producer_violation"}`.

9. **Lifecycle timestamps server-set on transition.** `close_out_payload_ready_at` is set when status transitions to `ready`; `close_out_payload_applied_at` when to `applied`; `close_out_payload_cancelled_at` when to `cancelled`; `close_out_payload_superseded_at` when to `superseded`. Each is idempotent. Each is mutually exclusive at the three-terminal level (exactly one of `_applied_at`, `_cancelled_at`, `_superseded_at` is non-null on a terminal record). Client-supplied values for these columns are ignored on PUT and PATCH except in the documented backfill case (create with terminal status accepts user-supplied terminal timestamps).

10. **`close_out_payload_file_path` repo-relative validation enforced.** Insertions with a leading slash, `..` segments, or scheme prefix (e.g., `http://`, `file://`) are rejected at the access layer. Uniqueness within the engagement is enforced case-sensitively (file paths are case-sensitive in the underlying filesystem). The same `file_path` value may coexist in a `work_ticket` or `reference_book` record in the same engagement; the close_out_payload-side uniqueness check is against the close_out_payloads table only.

11. **Access-layer methods exist with expected signatures.** `client.list_close_out_payloads()`, `client.get_close_out_payload(identifier)`, `client.create_close_out_payload(...)`, `client.update_close_out_payload(identifier, ...)`, `client.patch_close_out_payload(identifier, ...)`, `client.delete_close_out_payload(identifier)`, `client.restore_close_out_payload(identifier)`, `client.next_close_out_payload_identifier()` exist and pass unit tests covering happy path and at least one error case each.

12. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the V2 `{data, meta, errors}` envelope per `crmbuilder-v2/src/crmbuilder_v2/api/envelope.py`. List endpoint correctly filters by `?status=` query parameter (single value and comma-separated list).

13. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /close-out-payloads/next-identifier` returns `{"next": "COP-NNN"}` for the next available number. POST with `close_out_payload_identifier` omitted assigns the same value. Two concurrent POSTs do not assign the same identifier (verified by a concurrent-insert test).

14. **Soft-delete and restore round-trip correctly.** DELETE sets `close_out_payload_deleted_at`; the record disappears from `GET /close-out-payloads`. `GET /close-out-payloads?include_deleted=true` shows it. POST `/restore` clears `close_out_payload_deleted_at`; the record reappears. Restore on a record that is not soft-deleted returns 422.

15. **Vocabulary additions registered.** `REFERENCE_RELATIONSHIPS` includes `close_out_payload_produced_by_conversation`; `ENTITY_TYPES` includes `close_out_payload` (alongside the other governance entities and pre-existing types); `_kinds_for_pair` returns the correct kind set for the `(close_out_payload, conversation)` pair. The matching Alembic migration on `refs.relationship_kind`'s CHECK constraint passes. The inbound `deposit_event_applies_close_out_payload` kind belongs to `deposit_event.md`'s registration pass; this spec does not register it. The cardinality rule "exactly one outbound `close_out_payload_produced_by_conversation` edge per close_out_payload" is enforced at the access layer; "at most one inbound `deposit_event_applies_close_out_payload` edge per close_out_payload" is also enforced (as the at-most-one half of the close_out_payload-side contribution; the deposit_event-side enforces the other half from its direction).

16. **End-to-end backfill of a representative historical payload.** A consultant can author a `close_out_payload` record for one of the historical payload files (e.g., `PRDs/product/crmbuilder-v2/close-out-payloads/ses_046.json`) through the New Close-Out Payload dialog with status `applied`, lifecycle timestamps `close_out_payload_ready_at` and `close_out_payload_applied_at` backfilled to historical values, the mandatory `close_out_payload_produced_by_conversation` edge pointing at the conversation record for the producing conversation (`CONV-NNN` for SES-046's conversation), and (after the deposit_event entity ships in the next conversation's build slice) the inbound `deposit_event_applies_close_out_payload` edge from the deposit_event record naming the SES-046 apply event. The payload record persists across application restart and across REST/MCP refetch. The same workflow applies to payloads for SES-001 through SES-051 once their producing conversation records and applying deposit_event records are also backfilled.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For the build-planning conversation to settle

**[build] Coordinated multi-record transaction for the apply moment.** The applied-requires-edge rule requires the inbound `deposit_event_applies_close_out_payload` edge to be present when close_out_payload transitions to `applied`. The deposit_event entity (next conversation) will likely have its own creation-time invariants. The natural workflow at apply time is: (a) deposit_event record is created with its own fields populated, (b) the references-table edge from deposit_event to close_out_payload is inserted, (c) the close_out_payload's status transitions to `applied` with its `close_out_payload_applied_at` server-set. Build-planning specifies whether this is one transaction (all-or-nothing across both entity tables and the references table) or a sequence of coordinated single-entity transactions, and how the access layer surfaces partial-failure cases. The pattern parallels the conversation-complete / work_ticket-consumed coordination noted in `work_ticket.md` section 3.8.1; build-planning may resolve all three coordinations with one mechanism.

**[build] Sidebar grouping for the six new governance entities.** Inherited from `workstream.md` section 3.8.1. The existing Governance group plus six new entries makes the group thirteen entries deep. The build-planning conversation decides whether to introduce a sub-grouping (e.g., "Governance — workflow" for the six new ones) or to reorder the existing group, or to accept the longer list as-is. This spec declares default position (Governance group, somewhere among the six new entries in workstream order); the build-planning conversation may overrule.

**[build] Migration ordering across the six schemas.** Inherited from `workstream.md`, `conversation.md`, `reference_book.md`, and `work_ticket.md` section 3.8.1. Each of the six governance schemas requires its own Alembic migration creating the entity table; the references-vocab additions across all six are consolidated into one migration per the spec guide section 9 aggregation rule. Sequencing those migrations safely is build-planning's call. The close_out_payload table depends on the conversation table (the production-edge points at conversation records); migration ordering must respect this.

**[build] Apply-script evolution to consume from the close_out_payloads table.** The current `apply_close_out.py` script (and the equivalent Claude Code apply prompts) reads payload content from the file at the path supplied as a command-line argument. The script does not currently know about close_out_payloads records. Two evolution paths for build-planning: (a) the script continues reading from the file, and records a close_out_payload entry alongside the deposit_event entry as part of the apply (the entity table becomes a register of past applies); (b) the script accepts a close_out_payload identifier as input, looks up the record, reads file_path from the record, then proceeds as today (the entity table becomes the canonical entry-point for apply). Both are consistent with this schema; the choice affects scripting ergonomics and is build-planning's call.

**[build] Whether a derived-view endpoint exposes payload content.** The kickoff prompt named the question of whether a UI affordance "preview the records this payload would write before apply" or "show me what this payload deposited" should live on the payload entity. This spec does not store payload content as a column; if such an affordance is wanted, the natural shape is a derived-view endpoint `GET /close-out-payloads/{identifier}/content` that reads file_path on demand, parses the JSON, and returns a structured shape (record-counts-by-kind, full list of identifiers, etc.). The endpoint addition is non-breaking — no schema change, no migration. Build-planning decides whether to ship the endpoint with the entity or defer it as a planning item.

#### 3.8.2 For retroactive backfill (PI-022) to surface

**[backfill] Historical close_out_payload records.** PI-022 covers retroactive population of close_out_payload records for the 50+ historical payload files under `PRDs/product/crmbuilder-v2/close-out-payloads/`. The retroactive records require `applied` status, plausible historical timestamps for `close_out_payload_ready_at` and `close_out_payload_applied_at`, the production-edge pointing at the conversation record for each payload's producing conversation, and (after deposit_event ships) the inbound apply-edge from the corresponding deposit_event record. The backfill pass determines which dates to use (commit dates on the payload file vs. the matching session record's session_date vs. wall-clock at backfill time) and resolves any ambiguity case-by-case. This is a question for PI-022's resolution, not for this spec.

**[backfill] Identifier ordering for backfilled records.** When 50+ historical payloads are backfilled, identifier ordering matters for consultant intuition. The natural ordering is by producing-conversation session number (the payload for SES-001 gets COP-001, the payload for SES-046 gets COP-046, etc.), aligning payload identifier with session identifier where possible. The schema does not enforce this alignment — identifiers are server-assigned in insertion order. PI-022's backfill pass either (a) inserts in producing-conversation order to preserve the alignment, or (b) accepts identifier-vs-session drift and documents the divergence. This is a backfill-policy question, not a schema question.

#### 3.8.3 For a future release

**[future] Derived-view endpoint for payload content.** Not introduced in this release. If a real UI affordance ("preview before apply", "show what was deposited") emerges, the natural addition is a `GET /close-out-payloads/{identifier}/content` endpoint that reads file_path on demand, parses the JSON, and returns a structured shape — record-counts by kind, full identifier lists, optionally the full payload content. The endpoint addition is non-breaking; no schema change.

**[future] `payload_schema_version` column.** Not introduced in this release. The payload structure has been stable across all 50+ historical files (label, session, decisions, planning_items, references). If the structure evolves — for example, if a payload schema needs to add a new top-level section, or change the shape of a record kind — a `close_out_payload_schema_version` column is a one-line migration plus default values for historical rows. The schema admits this additive change; the column is not pre-added on the speculation that structure will evolve.

**[future] `payload_kind` enum.** Not introduced in this release. Every record in the close_out_payloads table is the same kind ("close-out payload at conversation close"). If future workstreams introduce other state-write package variants (e.g., a "bulk import payload" or a "migration payload"), the natural addition is a `close_out_payload_kind` enum column with `close_out_payload` as the default and the new kinds added explicitly. The schema admits this additive change.

**[future] Re-apply semantics and multi-deposit-event support.** This spec assumes a payload is applied at most once (the at-most-one inbound `deposit_event_applies_close_out_payload` edge rule). If a real use case for re-apply emerges (e.g., a payload was applied to a test engagement, then re-applied to a production engagement), the schema admits relaxing the at-most-one rule to many-to-one (a payload may have multiple inbound deposit_event apply edges). The relaxation is an access-layer rule change, not a schema change; the deposit_event-side spec may pre-emptively support it from inception. The decision belongs to `deposit_event.md`'s conversation.

**[future] Inline payload-content rendering in the detail pane.** Not introduced in this release. If the derived-view endpoint above is added, the detail pane could render the parsed payload content inline below the existing fields — a tree view of records-to-be-written with counts by kind and clickable identifiers. The addition is a UI version; no schema change. Build-planning may scope this as a follow-on UI slice if the affordance is operationally valuable.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following six decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against `PRDs/product/crmbuilder-v2/close-out-payloads/ses_052.json` at conversation close. Each is linked to SES-052 via a `decided_in` reference recorded in the same payload. Decision identifiers (anticipated DEC-147 through DEC-152) are assigned by the apply script at write time and may shift if other conversations close before this one applies.

- **DEC-147 — `close_out_payload` identifier prefix and format.** Adopts `COP` as the prefix. Three-letter form chosen on the strength of the existing three-letter precedent (DEC, SES, REF, etc.); two-letter alternatives `CO` and `CP` were rejected for ambiguity; four- and five-letter alternatives were rejected for length-without-disambiguation gain. Per DEC-123's affirmation that each downstream conversation makes its own prefix-length call within the 2-to-5 letter range.
- **DEC-148 — `close_out_payload` content representation: file_path pointer only, no content column.** Adopts the file-tracking-entity precedent locked by DEC-139 (reference_book) and DEC-145 (work_ticket): a single repo-relative `close_out_payload_file_path` column, no `payload_content` JSON column. The payload's authoritative content lives in the file under git; the database carries the governance view. Future content-query needs are satisfied by a derived-view endpoint that parses file_path on demand, not by a content column.
- **DEC-149 — `close_out_payload` workflow-shaped lifecycle with five statuses, truly terminal terminals, applied-requires-edge rule, supersession-requires-edge rule, production-edge required at all statuses.** Adopts `drafted` / `ready` / `applied` / `cancelled` / `superseded` with the transition map of section 3.4.1, the truly-terminal posture inherited from workstream and conversation, the applied-requires-edge rule realizing the inverse-pattern precedent locked by DEC-143 (work_ticket's consumed-requires-edge), the supersession-requires-edge rule inherited verbatim, and the production-edge-required-at-all-statuses rule from this spec's section 3.4.5. Establishes no new cross-spec precedent — each rule follows an inherited precedent on this spec's facts.
- **DEC-150 — `close_out_payload` production-linkage via references-edge with new kind `close_out_payload_produced_by_conversation`, declines typed sequencing kind.** Confirms the cross-spec references-edge-over-FK precedent on the close_out_payload-to-conversation relationship. Names the new outbound kind required at all statuses with cardinality "exactly one outbound edge per payload". Declines a typed `close_out_payload_succeeds_close_out_payload` sequencing kind on the strength of DEC-133's frequency-justified test — payload sequencing is rare (drafts are typically not chained), and the existing generic `supersedes` kind suffices for the same-type supersession edge.
- **DEC-151 — `close_out_payload` field inventory including four per-status lifecycle timestamps; declines `payload_kind` enum and `payload_schema_version` column.** Captures the eleven-column shape (identity, content, classification, no FK fields, file pointer, base plus four per-status lifecycle timestamps) per section 3.2. Declines the `close_out_payload_kind` enum because every record is the same kind (no taxonomic axis exists); admits the column as a future additive change if other state-write package variants emerge. Declines the `close_out_payload_schema_version` column because the payload structure has been stable across all 50+ historical files; admits the column as a future additive change if structure evolves.
- **DEC-152 — `close_out_payload` API surface, default UI with Status filter combo, soft-delete posture, sixteen acceptance criteria.** Standard API endpoint set with no deviations. Default UI layout with one natural addition: a Status filter combo in the master-pane toolbar (operational browse-by-status pattern parallel to work_ticket). Default soft-delete with restore, explicitly distinct from `cancelled` lifecycle status and from `applied` terminal status. Sixteen acceptance criteria captured, mirroring the work_ticket spec's sixteen.

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry.
- `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan governing this and the prior four schema-design conversations.
- `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/schema-design-kickoff-close-out-payload.md` — this conversation's seed prompt.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md` — first schema spec in the workstream; locked the three foundational cross-spec precedents this spec inherits.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/conversation.md` — second schema spec; the conversation entity is the producing-side counterpart of this spec's production-linkage relationship.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/reference_book.md` — third schema spec; established the file_path semantics this spec inherits, established the documentary-vs-workflow distinction this spec applies on its own facts.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/work_ticket.md` — fourth schema spec; established the consumed-requires-edge precedent this spec realizes as applied-requires-edge.
- `PRDs/product/crmbuilder-v2/schema-design-kickoff-deposit-event.md` — sixth conversation's kickoff; the deposit_event entity references this spec's records as the apply-target.
- `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — per-engagement isolation; `close_out_payload` records live in the per-engagement database.
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — controlled vocabulary the new entity type and relationship kind register against.
- `PRDs/product/crmbuilder-v2/close-out-payloads/` — historical home for payload files; the canonical file_path pattern for backfilled and forward-going records.
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md` — canonical envelope-discipline apply prompt; the apply path that consumes payload files today.

#### 3.9.3 Foundation decisions this spec extends

- **DEC-117** — Track workflow files as three purpose-built entity-type families. **Most directly extended.** `close_out_payload` is family 3 (single-use state-write packages). This spec is the realization of the family-3 entity within the deposit bucket pair established by DEC-118; the second entity in the pair (`deposit_event`) is designed in the sixth and final per-entity conversation.
- **DEC-118** — Two entities within the deposit bucket family. **Most directly extended.** This spec realizes the payload half of the pair. The deposit_event half is designed in the next conversation. The pair's structural split — payload produced at conversation close, event recorded at apply — is reflected in this spec's lifecycle (the `applied` terminal is the apply-event marker on this side, with the deposit_event record providing the apply-event detail on its side).
- **DEC-119** — Add a conversation entity. The `conversation` entity is the target of this spec's required outbound production-linkage edge (`close_out_payload_produced_by_conversation`). Every payload record has exactly one outbound edge of this kind, at every status.
- **DEC-120** — Add a workstream entity. Indirectly extended — the workstream entity is the conversation's parent, and this spec's production-linkage navigates through the conversation to reach the workstream context. No direct relationship from close_out_payload to workstream.
- **DEC-121** — Single-source-of-truth coverage extension. `close_out_payload` is one of the six new entity types closing the coverage gap.
- **DEC-122** — The governance workstream opens immediately, in parallel to other in-flight work. This spec operates against the CRMBuilder dogfood engagement only.

#### 3.9.4 Related prior decisions informing this spec

- **DEC-013** — Decisions and sessions are append-only and immutable. Informs section 3.4.6's soft-delete-not-append-only posture for `close_out_payload`: the entity is the planning-side record (produced at conversation close, but mutable in `drafted` and `ready` states before apply); the deposit_event entity is the natural append-only counterpart for the family-3 pair.
- **DEC-025** — Per-conversation transcript capture infeasible. Informs section 3.9.1's reliance on the close-out payload's apply script and the session record as the durable artifacts of this conversation.
- **DEC-029** — Charter and Status replace via JSON editor with Validate + Make Current. Not directly applicable to `close_out_payload` (the entity does not use the versioned-replace pattern), but informs the API write-pattern norms this spec adopts.
- **DEC-031** — Reference rendering generalized via shared `ReferencesSection` widget. Directly informs the detail pane reference rendering in section 3.6.3, including the prominent display of the outbound `close_out_payload_produced_by_conversation` edge as the family-defining relationship.
- **DEC-035** — `ListDetailPanel` master-widget plus context-menu factory refactor. Informs master pane patterns in section 3.6.2 including the Status filter combo addition.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs context-menu behavior in section 3.6.2.
- **DEC-046** — Parent-prefix field-naming convention. Inherited and applied throughout (all fields are prefixed `close_out_payload_`).
- **DEC-048** — Source-first `{source}_{verb}_{target}` relationship-kind naming. Inherited; `close_out_payload_produced_by_conversation` follows the pattern (passive-voice verb with the producer as target).
- **DEC-115 / DEC-116** — Per-engagement isolation architecture. `close_out_payload` records live in the per-engagement SQLite file; the CRMBuilder dogfood engagement is where this entity type's first records land.
- **DEC-123 through DEC-128** — All six decisions from SES-048 (the workstream schema-design conversation). DEC-123 affirms three-letter `COP` is acceptable. DEC-124's references-edge cross-spec precedent applies to this spec's production-linkage relationship. DEC-125's truly-terminal and supersession-requires-edge patterns are inherited verbatim. DEC-126's per-status lifecycle timestamps precedent applies (close_out_payload is workflow-shaped). DEC-127's flat-catalog posture is structurally analogous to this spec's no-hierarchy posture. DEC-128's standard-defaults posture is what this spec uses for API surface, UI layout (with the Status filter combo addition), soft-delete, and acceptance-criteria framing.
- **DEC-129 through DEC-134** — All six decisions from SES-049 (the conversation schema-design conversation). DEC-130's references-edge precedent for parent-child relationships applies (the production-linkage from close_out_payload to conversation is references-edge per the precedent). DEC-131's lifecycle patterns inform this spec's workflow-shaped five-state lifecycle. DEC-133's typed-sequencing-frequency-justified precedent is applied here to decline a typed `close_out_payload_succeeds_close_out_payload` kind in favour of generic `supersedes` for the rare supersession case. DEC-134's standard-defaults-with-natural-additions posture is what this spec uses for API surface and UI layout.
- **DEC-135 through DEC-140** — All six decisions from SES-050 (the reference_book schema-design conversation). DEC-135 affirms each downstream conversation makes its own prefix-length call (three-letter `COP` is fine). DEC-137's documentary-vs-workflow distinction is the precedent this spec applies on its own facts — close_out_payload is workflow-shaped (not documentary), so per-status lifecycle timestamps apply per DEC-126. DEC-139's repo-relative file path semantics are inherited verbatim, with the cross-table coexistence rule (the same `file_path` may exist in `work_ticket`, `reference_book`, and `close_out_payload` records) extended one further table.
- **DEC-141 through DEC-146** — All six decisions from SES-051 (the work_ticket schema-design conversation). DEC-141's prefix posture parallels this spec's COP choice. DEC-142's intent-at-creation classification with no in-place re-categorization is not directly applicable (close_out_payloads are unambiguously family 3; no boundary case with reference_book exists in practice). DEC-143's consumed-requires-edge precedent is **most directly realized** as this spec's applied-requires-edge rule in section 3.4.3; SES-051's section 3.4.3 explicitly named close_out_payload as the precedent's first downstream application. DEC-144's single-use enforcement parallels this spec's single-producer rule in section 3.4.5 (the family-3 definition that each payload has exactly one producing conversation, just as each work_ticket has at most one consuming conversation). DEC-145's field-inventory pattern (identity / content / classification / file-pointer / per-status timestamps) is followed verbatim. DEC-146's standard-API-with-Status-filter-combo UI posture is what this spec uses.

#### 3.9.5 Predecessor and successor conversations

- **Predecessor:** SES-051 — `work_ticket` schema-design conversation. Locked the consumed-requires-edge precedent this spec realizes as applied-requires-edge. Established the file_path semantics, single-use enforcement rule, and Status filter combo UI addition that this spec inherits.
- **Successor:** `deposit_event` schema-design conversation. Kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-deposit-event.md`. Inherits the seven cross-spec precedents now in force: the six from SES-048 / SES-049 / SES-050 / SES-051 plus the applied-requires-edge realization locked by this spec. The deposit_event entity is structurally this spec's family-3 counterpart — the apply-event record that records each `close_out_payload` apply. The next conversation's primary architectural question is whether deposit_event adopts pure append-only (no PUT, no PATCH, no DELETE) or admits soft-delete for record-management cleanup. This spec deliberately does NOT decide that question; it belongs to deposit_event's own conversation. This spec's section 3.3.2 lists the inbound `deposit_event_applies_close_out_payload` kind informationally only; the kind's vocab.py registration and access-layer enforcement of the deposit_event-side cardinality rule belong to the next conversation.

---

*End of document.*
