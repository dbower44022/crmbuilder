# Methodology Entity Schema Spec — `domain`

**Last Updated:** 05-11-26 23:00
**Status:** Draft v1.0 — produced by schema-design conversation
**Position in workstream:** First of four methodology-entity schema specs (`domain` → `entity` → `process` → `crm_candidate`)
**Predecessor conversation:** SES-011 (workstream-establishing planning conversation)
**Successor conversation:** `entity` schema design — kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-entity.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-11-26 23:00 | Doug Bower / Claude | Initial draft. Produced by the first schema-design conversation in the methodology-entity-schema-design workstream. Establishes the `domain` entity type for v2 storage and sets cross-spec conventions (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming) that the next three schema specs inherit. |

---

## Change Log

**Version 1.0 (05-11-26 23:00):** Initial creation. Defines `domain` as the v2 methodology entity type that hosts Phase 1 Domain Inventory members under minimum-viable v0.4 scope. Establishes seven fields (`domain_identifier`, `domain_name`, `domain_purpose`, `domain_description`, `domain_notes`, `domain_status`, plus inherited timestamps), three-status lifecycle (`candidate` / `confirmed` / `deferred`) with a one-way propose-verify gate and rejection-via-soft-delete, no outgoing relationships in v0.4, and standard endpoint set with server-side status-transition validation. Establishes parent-prefix field-naming convention (all non-identifier, non-timestamp fields prefixed with the parent entity name) and `{source}_{verb}_{target}` relationship-kind naming pattern for the methodology workstream — both conventions forward-only for methodology entities; governance retrofit tracked as PI-006. Six decisions (numbers assigned at conversation close) and two new planning items (PI-006, PI-007) produced. Acceptance criteria captured as 14 testable statements.

---

## 1. Purpose and Position

This document specifies the `domain` entity type for v2's storage layer. It is the first of four schema specs produced by the methodology-entity-schema-design workstream — the workstream that prepares v2 to host methodology *content* (not just governance about it) in time for the CBM redo, which will use the evolved methodology and v2 as its system of record.

The workstream is governed by `methodology-schema-workstream-plan.md`. Each schema spec conforms to the template in `methodology-entity-schema-spec-guide.md`. Four specs total are produced in this workstream — `domain`, then `entity`, `process`, `crm_candidate` — and feed a fifth v0.4-build-planning conversation that integrates them into a coherent release.

`domain` is the first spec because it is the most foundational. Both `entity` and `process` reference it (entities scope to or span domains; processes belong to a domain). Designing `domain` first lets the downstream specs treat it as a settled referent rather than a placeholder.

`domain`'s primary scope in v0.4 is minimal: it must host the Phase 1 Domain Inventory — a short list of 3–8 domains, each with a name, a one-sentence purpose, and a brief description. The schema is intentionally thin. Domain Overview documents (full per-domain documentation in the original methodology's Phase 4) are out of scope for v0.4 and addressed in v0.5+ as Phase 3 iteration work demands.

This conversation also establishes two cross-spec conventions that the next three schemas inherit:

- **Parent-prefix field naming.** All non-identifier, non-timestamp fields are prefixed with the parent entity name (e.g., `domain_status`, `domain_name`). Forward-only for methodology entities; governance-entity retrofit tracked as PI-006.
- **`{source}_{verb}_{target}` relationship-kind naming.** Relationship-kind vocabulary entries involving methodology entities are named source-first, with the source entity name, a verb phrase, and the target entity name (e.g., `entity_scopes_to_domain`). Forward-only for methodology vocab; governance vocab (`cites`, `supersedes`) stays as it is.

Both conventions require an amendment to the spec guide section 6, queued for the v0.4-build-planning conversation. The amendments do not block the next three schema-design conversations — those conversations adopt the conventions established here and reference this spec.

---

## 2. Summary

A `domain` record in v2 represents one member of a Phase 1 Domain Inventory: one of the big areas of work the client's mission forces their organization to address. Phase 1's Domain Inventory output identifies 3–8 such domains per engagement, each described in one paragraph. Each `domain` record captures the inventory's content for that domain — a client-language name, a one-sentence purpose answering why the mission requires the domain, a brief description of the kinds of work the domain covers, and an optional internal-notes scratchpad for consultant rationale — plus a lifecycle status tracking whether the domain is a CRM-Builder-proposed candidate, a client-confirmed scope member, or an acknowledged-but-deferred area.

The schema in v0.4 is the thinnest shape that can faithfully host Phase 1's output. It deliberately omits sub-domain hierarchy, Cross-Domain Service distinction, candidate-entity inventories, candidate-persona inventories, and full Domain Overview content — all of these belong to later methodology phases or to subsequent v2 releases. The minimum-viable shape grows additively in v0.5+ as the evolved methodology's later phases reveal what `domain` needs to carry.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `domain` |
| Display name (singular) | Domain |
| Display name (plural) | Domains |
| Identifier prefix | `DOM` |
| Identifier format | `DOM-NNN`, zero-padded to 3 digits (e.g., `DOM-001`, `DOM-042`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /domains/next-identifier` |

**Identifier-prefix note for the workstream.** `DOM` is three letters, consistent with the existing v2 governance-entity norm (DEC, SES, RSK, TOP, REF, CHR, STA — all three letters; PI is the lone outlier). The spec guide section 6 allows 3–5 letters; this spec affirms the 3-letter v2 norm without locking it as a strict requirement for downstream methodology entities. Downstream conversations (`process`, `crm_candidate`) may adopt 4-letter prefixes if the 3-letter form is ambiguous (e.g., `PROC` over `PRC` for clarity; `CRMC` over `CRM` to avoid product-name collision). Each downstream conversation justifies its choice in its own section 3.1.

### 3.2 Fields

Field naming follows the parent-prefix convention established by this spec: all non-identifier, non-timestamp fields are prefixed with the parent entity name (`domain_`). All fields including identifier and timestamps adopt the prefix in v0.4 for full convention consistency. The convention is forward-only for methodology entities; governance-entity field-name retrofit is tracked as PI-006.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `domain_identifier` | TEXT | yes | server-assigned | `^DOM-\d{3}$`, unique | The methodology-entity identifier in `DOM-NNN` format. Server-assigned when omitted from POST body. |
| `domain_name` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Domain name in the client's language (e.g., "Mentoring", "Mentor Recruitment", "Fundraising"). |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `domain_purpose` | TEXT | yes | — | non-empty trimmed | One-sentence statement of why the client's mission requires this domain to exist. Captures the priority-test artifact at domain granularity (mirrors the Phase 1 guide's per-domain purpose item from section 7.2). Plain text in v0.4; markdown support deferred to CBM-redo signal. |
| `domain_description` | TEXT | yes | — | non-empty trimmed | Brief paragraph describing the kinds of work the domain covers (mirrors the Phase 1 guide's per-domain description item). Plain text in v0.4; markdown support deferred to CBM-redo signal. |
| `domain_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of the Domain Inventory document render. Used to capture pattern-library rationale, push-back trails, between-session reasoning, etc. Plain text in v0.4; structured-journal pattern deferred to CBM-redo signal. |

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `domain_status` | TEXT | yes | `candidate` | enum: `candidate` \| `confirmed` \| `deferred`; valid transitions per section 3.4 | Lifecycle status. See section 3.4 for the transition map. |

#### 3.2.4 Relationship fields

None in v0.4. `domain` has no outgoing FK columns in this release. Inbound relationships from `entity` and `process` are declared in those specs. See section 3.3.

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `domain_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `domain_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `domain_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |

**No storage-level length caps.** Text fields are unconstrained at the storage layer in v0.4. The UI provides soft guidance via placeholder text ("One sentence", "Brief paragraph"). Pathological-input handling deferred to CBM-redo signal; length caps are easy to add via migration in v0.5 if needed.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

None in v0.4. `domain` has no FK fields to other entity types, no self-referential hierarchy, and no use of the references entity from the source side. The schema is target-side only for cross-entity relationships.

#### 3.3.2 Inbound relationships (anticipated; declared by source-side specs)

`domain` is the target of references from `entity` and `process`, declared in `entity.md` and `process.md` respectively. The relationship kinds, mechanisms, and cardinalities are:

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `entity_scopes_to_domain` | `entity` | `domain` | references-entity edge (working assumption) | many-to-many | An entity is scoped to one or more domains. Mirrors CBM's existing variant pattern (Mentor Contact / Client Contact scoped to MR and MN respectively). |
| `process_belongs_to_domain` | `process` | `domain` | direct FK column on `process` (working assumption) | many-to-one | A process belongs to exactly one domain. Mirrors the Phase 1 Prioritized Backbone's domain-grouped process listing. |

This table is informational from `domain.md`'s perspective. The `vocab.py` registration of these relationship kinds and the choice between direct-FK and references-entity mechanism belong to the `entity.md` and `process.md` schema-design conversations. The v0.4-build-planning conversation's cross-spec consistency check validates that the source-side mechanism choices align.

#### 3.3.3 Cross-spec relationship-kind naming convention established here

This spec establishes the `{source}_{verb}_{target}` naming pattern for relationship-kind vocabulary entries involving methodology entities. The pattern is source-first: source entity name, verb phrase, target entity name (e.g., `entity_scopes_to_domain`, not `domain_scoped_from_entity`). The convention applies forward to all methodology workstream specs; existing governance vocabulary (`cites`, `supersedes`, etc.) stays unchanged.

The convention is recorded as a decision in section 3.9 and requires an amendment to the spec guide section 6, queued for the v0.4-build-planning conversation. The methodology workstream operates under the new pattern in the meantime.

#### 3.3.4 Hierarchy

`domain` does not use the self-referential parent-child hierarchy pattern in v0.4. Sub-domain structure is explicitly out of scope per the workstream plan section 3.1 and the evolved methodology Phase 1 outline. If real-engagement experience surfaces a need for sub-domains, the v0.5 schema migration adds a `domain_parent_identifier` self-FK following the existing `topic.parent_topic` pattern.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `candidate` | CRM Builder has proposed; awaiting client verification. **Default starter status.** | (none — starter) | `confirmed`, `deferred` |
| `confirmed` | Client has verified this is a domain in scope for the engagement. | `candidate`, `deferred` | `deferred` |
| `deferred` | Client has acknowledged this is a real domain but it is out of current engagement scope. | `candidate`, `confirmed` | `confirmed` |

#### 3.4.2 Transition semantics

The status lifecycle implements a **one-way propose-verify gate**: once a domain has moved out of `candidate` (in either direction, to `confirmed` or to `deferred`), it does not regress to `candidate`. The rationale: the propose-verify moment is a meaningful client-engagement event; if the consultant later wants to fundamentally rethink a verified domain, the right action is to edit the record's content, not to regress its status. Status reflects engagement-scope position, not deliberation state.

Movement between `confirmed` and `deferred` in either direction is permitted to support mid-engagement scope changes (e.g., a domain initially confirmed but later deprioritized; a previously-deferred domain pulled back into scope at a later iteration).

#### 3.4.3 Rejection via soft-delete

When the client rejects a CRM-Builder-proposed domain candidate ("no, that's not actually a domain for us"), the rejection is handled by soft-delete rather than a `rejected` status value. `DELETE /domains/{domain_identifier}` sets `domain_deleted_at`; the record persists for audit and history, surfaces under the `?include_deleted=true` toggle, and is restorable via POST `/restore`. This piggybacks v2's existing soft-delete infrastructure rather than introducing a status value that duplicates the mechanism.

The principle established here for cross-spec consistency: **status values track engagement-scope lifecycle; soft-delete tracks existence-in-the-record.** Downstream methodology specs adopt the same posture unless they have a substantive reason to deviate.

#### 3.4.4 No `archived` status

`archived` is not introduced in v0.4. Soft-delete combined with the "show deleted" toggle already covers the "retained for record, not in active scope" use case. Adding `archived` would duplicate the mechanism.

#### 3.4.5 Soft-delete semantics

Soft-delete inherits v2's standard behavior:

- DELETE sets `domain_deleted_at` to the current ISO 8601 UTC timestamp.
- Soft-deleted records do not appear in `GET /domains` by default.
- `GET /domains?include_deleted=true` returns soft-deleted records alongside live ones.
- POST `/domains/{domain_identifier}/restore` clears `domain_deleted_at` and reappears the record in the default list.
- Restore on a record that is not soft-deleted returns HTTP 422.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/domains` | — | List endpoint. Returns active records by default. Supports `?include_deleted=true` to include soft-deleted records. |
| GET | `/domains/{domain_identifier}` | — | Single fetch by identifier. Returns 404 if not found. |
| POST | `/domains` | full record minus `domain_identifier` (server-assigned) | Create. Returns 201 with the assigned identifier in the response body. Server-side validation per section 3.2 applied. |
| PUT | `/domains/{domain_identifier}` | full record | Full replace. `domain_identifier` in body must match the path; mismatch returns 422. |
| PATCH | `/domains/{domain_identifier}` | partial record | Partial update. Status-transition validation applied (see 3.5.3). |
| DELETE | `/domains/{domain_identifier}` | — | Soft-delete; sets `domain_deleted_at`. Idempotent (DELETE on an already-soft-deleted record returns 200 with no state change). |
| POST | `/domains/{domain_identifier}/restore` | — | Clears `domain_deleted_at`. Returns 422 if the record is not soft-deleted. |
| GET | `/domains/next-identifier` | — | Returns `{"next": "DOM-NNN"}` for the next available identifier. Per SES-010 resolution (`GET /<entity>/next-identifier` helpers for all twelve prefixed-identifier entity types). |

**No deviations from the cross-spec default endpoint set.** No bulk operations, no webhooks, no event streams, no OPTIONS or HEAD support — all consistent with v2 norms.

#### 3.5.2 Identifier auto-assignment

`domain_identifier` is server-assigned on POST when omitted from the request body. The assignment logic queries the current maximum `domain_identifier` (including soft-deleted records, to avoid identifier reuse) and increments the numeric suffix. The `GET /domains/next-identifier` helper exposes the same logic for clients that want to know the assigned identifier before POSTing.

Concurrent identifier-assignment behavior (locking, optimistic retry, etc.) is implementation-level and decided by the v0.4 build. Acceptance criterion #7 in section 3.7 requires correctness under concurrent POSTs.

#### 3.5.3 Status-transition validation

Status transitions are validated server-side at the access layer. PATCH or PUT requests that specify a `domain_status` value that is not a valid successor of the current value (per section 3.4.1) return HTTP 422 with a body of the form:

```
{
  "error": "invalid_status_transition",
  "from": "<current status>",
  "to": "<requested status>"
}
```

The default-`candidate` rule applies on POST: if `domain_status` is omitted, the server assigns `candidate`. POST with `domain_status` explicitly set to a non-starter value is permitted (e.g., bulk-importing already-confirmed domains from prior engagement records).

#### 3.5.4 Other endpoint specifics

- All endpoints return JSON.
- 4xx error responses use the existing v2 error envelope shape.
- No additional list query parameters beyond `?include_deleted=true` in v0.4. Client-side filtering over the small expected domain count (3–8 records per engagement) is sufficient. Server-side filtering deferred to CBM-redo signal.

### 3.6 UI Considerations

This spec adopts the spec guide's default `ListDetailPanel` layout with no architectural deviations. Specifics for `domain` follow.

#### 3.6.1 Sidebar

A new "**Methodology**" sidebar group is introduced, sitting below the existing "Governance" group. The Methodology group's items follow workstream order:

1. Domains (this spec)
2. Entities (`entity.md`, forthcoming)
3. Processes (`process.md`, forthcoming)
4. CRM Candidates (`crm_candidate.md`, forthcoming)

All four entries ship together in v0.4. The Methodology group is hidden in v0.3 (does not exist) and appears as a single shipping unit when v0.4 lands.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with these columns:

| Stored field | Display header | Width | Notes |
|--------------|----------------|-------|-------|
| `domain_identifier` | Identifier | narrow | Default sort key, ascending |
| `domain_name` | Name | wide | Client-language name |
| `domain_status` | Status | narrow | Enum value rendered as-is |
| `domain_updated_at` | Updated | narrow | Localized date/time |

Right-click context menu offers New / Edit / Delete / Restore, consistent with v0.3 governance-entity panels per DEC-035 and DEC-036.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `domain_identifier` — read-only label
2. `domain_name` — single-line text editor
3. `domain_purpose` — single-line text editor with placeholder "One sentence"
4. `domain_description` — multi-line text editor with placeholder "Brief paragraph"
5. `domain_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default
6. `domain_status` — combo box with the three enum values
7. `ReferencesSection` widget — renders inbound references from `entity` and `process` once those entity types are integrated. No outgoing references from `domain` in v0.4; the widget shows the inbound side only. The widget is always present; its content is empty until cross-spec relationship kinds are registered in `vocab.py` (which happens in the same v0.4 ship as this spec).

The collapsed-by-default treatment of `domain_notes` is a deliberate UX cue reinforcing that the field is internal consultant scratchpad, not part of the client-facing Domain Inventory render.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `domain_identifier` not shown in create mode (server-assigned).
- `domain_status` defaults to `candidate`; user may select a different starter value if importing established domain records.
- Required-field validation client-side before submit.
- Server-side validation errors (uniqueness, format, transition) surface inline.

#### 3.6.5 Edit dialog

Same shape as create. `domain_identifier` displayed as read-only label. Status transitions enforced per section 3.4.1; invalid selections in the status combo are either prevented (recommended UX) or rejected by the server with the 422 surfacing inline (acceptable fallback).

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `domain_identifier` value (e.g., `DOM-002`) to enable the Delete button, matching v0.3 governance-entity patterns. Confirmation soft-deletes the record.

### 3.7 Acceptance Criteria

The following 14 statements define what "this entity type is correctly implemented in v0.4" looks like. Each is concrete and testable; v0.4 build planning translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `domains` table with all nine columns (`domain_identifier`, `domain_name`, `domain_status`, `domain_purpose`, `domain_description`, `domain_notes`, `domain_created_at`, `domain_updated_at`, `domain_deleted_at`), correct types and constraints, and runs both forward and backward without error.

2. **`domain_identifier` format constraint enforced.** Insertions with `domain_identifier` not matching `^DOM-\d{3}$` raise a validation error at the access layer.

3. **`domain_name` uniqueness enforced case-insensitively.** Inserting a second row whose `domain_name` matches an existing row by lowercase comparison raises a uniqueness violation.

4. **`domain_status` enum and transition validation.** Insertions with `domain_status` outside `{candidate, confirmed, deferred}` are rejected. PATCH/PUT requesting an invalid transition (e.g., `confirmed` → `candidate`) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

5. **Access-layer methods exist with expected signatures.** `client.list_domains()`, `client.get_domain(identifier)`, `client.create_domain(...)`, `client.update_domain(identifier, ...)`, `client.patch_domain(identifier, ...)`, `client.delete_domain(identifier)`, `client.restore_domain(identifier)`, `client.next_domain_identifier()` exist and pass unit tests covering happy path and at least one error case each.

6. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the v2 error envelope.

7. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /domains/next-identifier` returns `{"next": "DOM-NNN"}` for the next available number. POST with `domain_identifier` omitted assigns the same value. Two concurrent POSTs do not assign the same identifier (verified by a concurrent-insert test).

8. **Soft-delete and restore round-trip correctly.** DELETE sets `domain_deleted_at`; the record disappears from `GET /domains`. `GET /domains?include_deleted=true` shows it. POST `/restore` clears `domain_deleted_at`; the record reappears in the default list. Restore on a record that is not soft-deleted returns 422.

9. **`Domains` sidebar entry appears under a "Methodology" group.** The Methodology group sits below the existing Governance group. Domains is the first item within Methodology (with `entity`, `process`, `crm_candidate` following in workstream order in the same v0.4 ship).

10. **Master pane columns and default sort.** The Domains panel shows columns Identifier / Name / Status / Updated, sorted by Identifier ascending. Right-click context menu offers New / Edit / Delete / Restore.

11. **Detail pane renders all fields in section-3.2 order.** Identifier (read-only), Name, Purpose, Description, Notes (collapsed under "Internal notes" header), Status, ReferencesSection — all present and bound to the correct fields.

12. **CRUD dialogs work end to end.** Create assigns identifier server-side, persists all fields, surfaces server-side validation errors inline. Edit persists field changes including status transitions. Delete prompts for edge-text confirmation (user types the identifier) and soft-deletes on confirm. Restore reappears the record.

13. **File-watch refresh picks up external changes.** Authoring a `domain` row via direct REST call (curl or MCP) causes the desktop master pane to reflect the change within the file-watch interval without manual reload.

14. **Sample CBM-redo Phase 1 records authored through the UI.** A consultant can author 3–6 `domain` records (e.g., Mentoring, Mentor Recruitment, Client Recruiting, Fundraising) through the New dialog, transition them from `candidate` to `confirmed`, and the records persist correctly across application restart and across REST/MCP refetch.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For v0.4 build to settle

**[v0.4 build] Spec guide amendments.** Section 6 of `methodology-entity-schema-spec-guide.md` requires amendment to reflect (a) the parent-prefix field-naming convention adopted in this spec, and (b) the `{source}_{verb}_{target}` relationship-kind naming pattern for methodology vocab. Both changes are forward-only for methodology entities; governance-vocabulary and governance-entity field names retain their existing conventions until PI-006 retrofit lands. The v0.4-build-planning conversation coordinates the spec guide amendment as part of integrating the four schema specs.

**[v0.4 build] Source-side mechanism for inbound relationships.** Whether `entity_scopes_to_domain` lives as a references-entity edge (working assumption: yes, many-to-many) and whether `process_belongs_to_domain` lives as a direct FK column on `process` (working assumption: yes, one-to-many) is decided in `entity.md` and `process.md`. This spec's section 3.3.2 lists the anticipated mechanisms as working assumptions, but the authoritative choice belongs to the source-side specs. The v0.4-build-planning conversation's cross-spec consistency check validates that the choices fit together.

**[v0.4 build] Concurrent identifier-assignment behavior.** The mechanism for preventing two concurrent POSTs from assigning the same `DOM-NNN` (row-level locking, optimistic retry, advisory locks, etc.) is implementation-level and not specified by this spec. Acceptance criterion #7 requires correctness; the *how* is the v0.4 build's call. Likely solution is consistent with how v0.3 governance-entity identifier assignment handles concurrency.

#### 3.8.2 For CBM redo to surface

**[CBM redo] Markdown for `domain_description` and `domain_purpose`.** Both fields are plain text in v0.4. The CBM redo's actual Phase 1 work will reveal whether descriptions or purposes need emphasis, bullet lists, or inline links. If so, a v0.5 migration introduces markdown rendering on these fields. The decision deliberately waits on real-use signal rather than speculating in design.

**[CBM redo] Text-field length caps.** No storage-level length constraints in v0.4; UI placeholder text provides soft guidance. If the CBM redo produces pathological inputs (5000-character "brief paragraphs," 50-word "one-sentence purposes"), caps are added via migration in v0.5. The minimum-viable posture is preferred because hard caps are easy to add later and hard to relax once imposed.

**[CBM redo] `domain_notes` structure.** Flat plain text in v0.4. If consultant notes accrete substantially over an engagement — pattern-library reasoning, push-back-moment trails, between-session refinements — a structured-journal pattern (a `domain_notes_entries` table with timestamped entries keyed by `domain_identifier`) may pay off. This becomes a v0.5 candidate if the CBM redo signal supports it.

**[CBM redo] One-way propose-verify gate.** The status transition map (section 3.4.1) prohibits regression to `candidate` from either `confirmed` or `deferred`. The rationale is that propose-verify is a meaningful engagement event and consultants should edit content rather than regress status when fundamentally rethinking. The CBM redo will surface whether this constraint creates friction in practice; if so, a v0.5 transition-map amendment can open up regression paths.

**[CBM redo] `archived` status.** Not introduced in v0.4 because soft-delete already covers the "retained for record, not in active scope" case. If the CBM redo shows clients wanting to distinguish "rejected" (don't keep this in the record) from "archived" (keep, but not in scope), a fourth status value is a small v0.5 schema change.

**[CBM redo] Server-side list filters.** Only `?include_deleted=true` is supported in v0.4. Client-side filtering over the small expected domain count (3–8 records) is sufficient. If the CBM redo or subsequent engagements drive list sizes large enough that client-side filtering causes UI responsiveness issues, server-side filters (e.g., `?domain_status=confirmed`) become a v0.5 candidate. Unlikely to bite for `domain` specifically; more likely to surface for `process` or `entity` at scale.

#### 3.8.3 For v0.5+

**[v0.5+] PI-003 — `persona` entity type.** Already tracked. The evolved methodology's Phase 1 explicitly does not elicit personas in the interview; persona context comes from pre-engagement reading of operational role definitions, used as consultant background rather than captured as records. v0.5+ may introduce `persona` as a methodology entity type if subsequent phases require persona records.

**[v0.5+] PI-004 — additional methodology entity types.** Already tracked. `field`, `requirement`, `manual_config`, `test_spec`. These are late-phase methodology entity types deferred from the minimum-viable v0.4 scope.

**[v0.5+] PI-005 — process schema growth beyond Phase 1 thin shape.** Already tracked. The `process.md` schema ships thin in v0.4 (name, priority classification, domain reference, connections via references); fuller process content (steps, actors, fields touched, validations) attaches in v0.5+ as Phase 3 iteration work demands.

**[v0.5+] PI-006 — Retrofit governance entities to parent-prefix field-naming convention.** New planning item authored at this conversation's close. Substantial migration affecting eight existing governance tables (DEC, SES, RSK, PI, TOP, REF, CHR, STA), access-layer methods, REST API serialization, MCP tool input/output, UI dialogs, and DB-export JSON snapshots. The v0.4-build-planning conversation decides whether to pull this retrofit into v0.4 scope (significant additional work) or defer to v0.5+. The methodology workstream's specs ship with the new convention regardless.

**[v0.5+] PI-007 — `short_code` field on `domain` for mnemonic references.** New planning item authored at this conversation's close. Captures the 2-letter domain codes (MN for Mentoring, MR for Mentor Recruitment, CR for Client Recruiting, FU for Fundraising) historically used in the CBM project as prefixes for process and entity identifiers (e.g., `MN-INTAKE`, `MR-RECRUIT`). Deferred from the v0.4 minimum-viable shape pending CBM-redo signal on whether the evolved methodology continues to use mnemonic prefixes for downstream identifier construction. If yes, a v0.5 schema migration adds `domain_short_code` with uniqueness and validation; the `process` and `entity` schemas adopt it for human-readable identifier prefixes.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following decisions are authored at this conversation's close via direct API. Final DEC-NNN numbers are assigned at write time (after SES-011's pending decisions land). The decisions are listed here by topic; this section will be updated with concrete identifiers when the records are written.

- **DEC-NNN — `domain` identifier prefix and format.** Adopts `DOM` with the soft-3-letter posture for downstream methodology entity prefixes (see section 3.1).
- **DEC-NNN — `domain` field inventory and validation.** Two content fields (`domain_purpose`, `domain_description`), optional `domain_notes`, no storage-level length caps, case-insensitive `domain_name` uniqueness within the engagement (see sections 3.2 and 3.2 validation rules).
- **DEC-NNN — Parent-prefix field-naming convention for methodology entities.** Cross-spec rule applying to all four methodology entities in the workstream. Forward-only for methodology; governance-entity retrofit tracked as PI-006. Spec guide section 6 amendment queued for v0.4-build-planning (see section 1 and section 3.2).
- **DEC-NNN — `domain` status lifecycle and rejection-via-soft-delete posture.** Three values (`candidate`, `confirmed`, `deferred`), one-way propose-verify gate, rejection handled by soft-delete rather than a `rejected` status value, no `archived` status (see section 3.4).
- **DEC-NNN — `domain` relationship posture and cross-spec relationship-kind naming.** No outgoing relationships in v0.4. Inbound relationship kinds declared by source-side specs (`entity`, `process`). `{source}_{verb}_{target}` relationship-kind naming pattern established for methodology vocab (see section 3.3).
- **DEC-NNN — `domain` API surface and UI defaults.** Standard endpoint set with no deviations, server-side status-transition validation, default `ListDetailPanel` UI in a new Methodology sidebar group, `domain_notes` collapsed by default in the detail pane (see sections 3.5, 3.6, 3.7).

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry.
- `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan governing this and the next three schema-design conversations.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/schema-design-kickoff-domain.md` — this conversation's seed prompt.
- `PRDs/process/research/evolved-methodology/evolved-methodology-phase-outline.md` — sections 2 (Principles) and 3 (Phase outline, especially Phase 1's outputs).
- `PRDs/process/research/evolved-methodology/phase-1-interview-guide.md` — sections 2.3 (Prepare a draft Domain Inventory), 3.4 (Part B — Domain identification), 7.2 (Domain Inventory output specification).
- `PRDs/process/research/pattern-library-specification.md` — referenced by the Phase 1 interview guide as the source of pattern-library entries that inform domain identification.

#### 3.9.3 Related prior decisions informing this spec

- **DEC-029** — Charter/Status replace via raw JSON editor with Validate button + Make Current pattern. Informs the API write-pattern norms this spec adopts.
- **DEC-031** — Reference rendering generalized via shared `ReferencesSection` widget. Directly informs the detail pane reference rendering in section 3.6.3.
- **DEC-034** — Sessions create-only via UI. Informs CRUD-dialog conventions referenced in section 3.6.4.
- **DEC-035** — `ListDetailPanel` master-widget + context-menu factory refactor. Informs master pane patterns in section 3.6.2.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs context-menu behavior in section 3.6.2.

#### 3.9.4 Predecessor and successor conversations

- **Predecessor:** SES-011 — workstream-establishing planning conversation. Produced the workstream plan, spec guide, and four per-entity kickoff prompts.
- **Successor:** `entity` schema-design conversation. Kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-entity.md`. Will inherit the conventions established in this spec (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture, status-lifecycle semantics).

---

*End of document.*
