# Methodology Entity Schema Spec — `crm_candidate`

**Last Updated:** 05-12-26 08:45
**Status:** Draft v1.0 — produced by schema-design conversation
**Position in workstream:** Fourth and final of four methodology-entity schema specs (`domain` → `entity` → `process` → `crm_candidate`)
**Predecessor conversation:** `process` schema-design conversation (close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_014.json`)
**Successor conversation:** v0.4-build-planning conversation — kickoff at `PRDs/product/crmbuilder-v2/ui-PRD-v0.4-build-planning-kickoff.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-12-26 08:45 | Doug Bower / Claude | Initial draft. Produced by the fourth and final schema-design conversation in the methodology-entity-schema-design workstream. Defines `crm_candidate` as the v2 methodology entity type that hosts evolved-methodology Phase 1 Initial CRM Candidate Set members under minimum-viable v0.4 scope. Inherits conventions established by `domain.md` (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture) and applied by `entity.md` and `process.md`. Deviates on lifecycle: four-status enum (`active` / `selected` / `declined` / `removed`) with three terminal states, an access-layer singleton-`selected` constraint, `removed` as a first-class status value (not via soft-delete) — see section 3.4.4 for the rationale. Closes the per-entity schema-design portion of the workstream; the v0.4-build-planning conversation opens against the kickoff this conversation also authored. |

---

## Change Log

**Version 1.0 (05-12-26 08:45):** Initial creation. Defines five substantive fields (`crm_candidate_identifier`, `crm_candidate_name`, `crm_candidate_fit_reason`, `crm_candidate_notes`, `crm_candidate_status`) plus inherited timestamps; four-status lifecycle with three terminal states (`selected`, `declined`, `removed`); access-layer singleton-`selected` constraint enforcing at most one winner per engagement; no outgoing relationships in v0.4 (vocabulary work limited to adding `crm_candidate` to `ENTITY_TYPES`, which makes the universal `is_about` / `references` / `decided_in` / `supersedes` kinds automatically available wherever `crm_candidate` participates); standard endpoint set with no deviations; default `ListDetailPanel` UI at Methodology sidebar position #4. Defers structured classification metadata (vendor URL, hosting type, license type, price tier) to PI-012 pending CBM-redo signal. Five decisions produced (DEC-060 through DEC-064) and one new planning item (PI-012). Acceptance criteria captured as 12 testable statements. Final per-entity spec in the methodology entity schema-design workstream; v0.4-build-planning kickoff authored alongside.

---

## 1. Purpose and Position

This document specifies the `crm_candidate` entity type for v2's storage layer. It is the fourth and final spec produced by the methodology-entity-schema-design workstream — the workstream that prepares v2 to host methodology *content* (not just governance about it) in time for the CBM redo, which will use the evolved methodology and v2 as its system of record.

The workstream is governed by `methodology-schema-workstream-plan.md`. Each schema spec conforms to the template in `methodology-entity-schema-spec-guide.md`. The three predecessor specs (`domain.md`, `entity.md`, `process.md`) established and reaffirmed cross-spec conventions that this spec inherits:

- **Parent-prefix field naming** (DEC-046): all non-identifier, non-timestamp fields are prefixed with the parent entity name. All fields including identifier and timestamps adopt the prefix in v0.4 for full convention consistency.
- **`{source}_{verb}_{target}` relationship-kind naming** (DEC-048): vocabulary entries involving methodology entities are named source-first, with source entity name, verb phrase, target entity name. (This spec registers no new relationship-kind values, so the convention applies trivially.)
- **Soft-3-letter prefix posture** (DEC-044): three letters preferred, four letters acceptable where three would be ambiguous. This spec affirms three (see section 3.1).
- **Engagement-global case-insensitive name uniqueness** (DEC-045, DEC-051, DEC-056): adopted unchanged.
- **No `archived` status; soft-delete-for-existence-removal** (DEC-047, DEC-052): adopted for the authoring-error path. Engagement-scope lifecycle handling deviates — see section 3.4.4.
- **Decomposed reference handling** (DEC-053, DEC-058): no inline-reference convenience endpoints. (Trivially satisfied: `crm_candidate` has no outgoing references in v0.4.)
- **Standard 8-endpoint API surface with `/next-identifier` helper** (DEC-043, DEC-049, DEC-054, DEC-059): adopted unchanged.
- **Default `ListDetailPanel` UI under the Methodology sidebar group** (DEC-049, DEC-054, DEC-059): adopted unchanged; position #4.

This spec deviates from cross-spec precedent on one structural point: **`crm_candidate` uses `removed` as a status value rather than soft-delete for mid-engagement drops from the candidate set.** The deviation is documented and justified in section 3.4.4. Soft-delete continues to handle the authoring-error path (record created in error), keeping the cross-spec soft-delete semantics intact for that case.

`crm_candidate` is the simplest schema in the workstream and the most isolated. It does not relate to `domain`, `entity`, or `process` — a CRM candidate is metadata about *where* the iteration deploys, not about *what* the iteration models. Designing it last lets the conversation operate against a fully-settled body of cross-spec conventions and produce a spec that exercises the spec-methodology template on a small surface as a coda to the more interconnected predecessors.

`crm_candidate`'s primary scope in v0.4 is the Phase 1 Initial CRM Candidate Set output (section 3 of `evolved-methodology-phase-outline.md`, Phase 1 Outputs bullet 4): two or three CRM products selected for multi-deploy based on coarse fit (open source vs. commercial, hosting, budget, integrations, team-IT). Proposed by CRM Builder and verified by client; persists across all iterations as the input to Phase 3 (Iteration Build and Deploy); final selection happens at Phase 5 (Engagement Closure and Adoption). The v0.4 schema is the thinnest shape that can faithfully host these records — name, fit rationale, lifecycle status — and explicitly defers Phase 3 deployment logs, Phase 4 Comparison Artifact entries, and Phase 5 selection-decision capture (those are separate artifacts or live in governance decision records, not in `crm_candidate` itself).

---

## 2. Summary

A `crm_candidate` record in v2 represents one member of a Phase 1 Initial CRM Candidate Set: one of the two or three CRM products that CRM Builder proposes and the client verifies for multi-deploy across the engagement's iteration loop. The record carries a name (the CRM product, e.g., "EspoCRM", "SuiteCRM", "Salesforce"), a one-paragraph fit rationale capturing why this product was selected for inclusion in the candidate set (open-source-vs-commercial posture, hosting fit, budget alignment, integrations expected, team-IT capability fit), an optional internal-notes scratchpad for consultant rationale, and a lifecycle status that tracks the candidate through its engagement-long journey from `active` (in the multi-deploy set) to one of three terminal states: `selected` (the Phase 5 winner — at most one per engagement), `declined` (a Phase 5 loser), or `removed` (dropped from the set mid-engagement, before Phase 5).

The schema in v0.4 is the thinnest shape that can faithfully host Phase 1's candidate-set output and carry it through to Phase 5's selection decision. It deliberately omits structured classification metadata (vendor URL, hosting type enum, license type enum, price tier enum) — those classification axes live in the `crm_candidate_fit_reason` prose in v0.4, with structured-field extraction deferred to PI-012 pending CBM-redo signal. The schema also deliberately omits per-iteration deployment logs (Phase 3 territory; separate artifact), per-candidate Comparison Artifact entries (Phase 4 territory; separate artifact), and per-candidate selection-decision capture (Phase 5 territory; lives in governance decision records referencing the chosen `crm_candidate`). The minimum-viable shape grows additively in v0.5+ as the evolved methodology's Phase 3 / 4 / 5 work reveals what `crm_candidate` needs to carry directly versus what belongs in adjacent artifacts.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `crm_candidate` |
| Display name (singular) | CRM Candidate |
| Display name (plural) | CRM Candidates |
| Identifier prefix | `CRM` |
| Identifier format | `CRM-NNN`, zero-padded to 3 digits (e.g., `CRM-001`, `CRM-042`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /crm_candidates/next-identifier` |

**Prefix rationale.** `CRM` is three letters and adheres to the soft-3-letter prefix posture established in `domain.md` section 3.1. The methodology context disambiguates the prefix unambiguously: a `CRM-NNN` identifier names a *candidate* product (the kind of thing the engagement might deploy to), not the software the consultant is using or the v2 system itself. In the v2 UI and the methodology documents, identifier appearances always read as "CRM-001 (EspoCRM)" or similar, with the human-readable name immediately disambiguating any residual ambiguity. The four-letter alternative `CRMC` ("CRM Candidate") was considered and rejected: it adds a letter that the methodology context already supplies. No collision with existing prefixes (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC). The identifier-asymmetry helper endpoint per DEC-043 ships alongside the standard endpoint set.

### 3.2 Fields

Field naming follows the parent-prefix convention established by `domain.md` (DEC-046): all non-identifier, non-timestamp fields are prefixed with the parent entity name (`crm_candidate_`). All fields including identifier and timestamps adopt the prefix in v0.4 for full convention consistency.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `crm_candidate_identifier` | TEXT | yes | server-assigned | `^CRM-\d{3}$`, unique | The methodology-entity identifier in `CRM-NNN` format. Server-assigned when omitted from POST body. |
| `crm_candidate_name` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | CRM product name (e.g., "EspoCRM", "SuiteCRM", "Salesforce", "HubSpot"). The engagement-global uniqueness rule prevents two candidate records for the same product within an engagement; mirrors `domain` / `entity` / `process` precedent. |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `crm_candidate_fit_reason` | TEXT | yes | — | non-empty trimmed | One-paragraph rationale for including this CRM product in the candidate set. Captures the Phase 1 selection-criteria assessment (open-source-vs-commercial posture, hosting fit, budget alignment, integrations expected, team-IT capability fit) in client-context prose. Plain text in v0.4; markdown support deferred to CBM-redo signal. |
| `crm_candidate_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of any client-facing render. Used to capture pattern-library rationale, lessons learned across iterations on this candidate, between-iteration reasoning about whether to keep this candidate active. Plain text in v0.4. |

**No structured classification metadata in v0.4.** Vendor URL, hosting type enum (`cloud` / `self_hosted` / `both`), license type enum (`open_source` / `commercial` / `freemium`), and price tier enum (`free` / `paid`) were considered and deferred to v0.5+ under PI-012. The Phase 1 selection criteria all live in `crm_candidate_fit_reason` in v0.4. The minimum-viable posture is preferred because (a) Phase 1 produces 2–3 candidates per engagement, a count too small for scannability gains from structured fields to outweigh their schema-and-UI-and-migration cost; (b) the v0.4-deferred adjacent artifacts (deployment logs, Comparison Artifact) are the natural home for structured comparison data; (c) extracting structured fields from prose later is mechanical, but deciding the right enum values is easier with real CBM-redo signal in hand than with speculation now.

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `crm_candidate_status` | TEXT | yes | `active` | enum: `active` \| `selected` \| `declined` \| `removed`; valid transitions per section 3.4; singleton-`selected` constraint per section 3.4.3 | Lifecycle status. Tracks the candidate's journey from initial inclusion in the multi-deploy set through to a terminal Phase 5 selection outcome or mid-engagement removal. See section 3.4 for the transition map and the singleton constraint. |

#### 3.2.4 Relationship fields

None in v0.4. `crm_candidate` has no outgoing FK columns on its table, no self-referential hierarchy, and no use of the references entity from the source side. Methodology data about *where* deployments target (`crm_candidate`) does not relate to methodology data about *what* the engagement models (`domain`, `entity`, `process`); the two sides of v0.4's methodology schema are intentionally orthogonal. See section 3.3.

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `crm_candidate_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `crm_candidate_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `crm_candidate_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. Soft-delete reserved for authoring-error path only — see section 3.4.5. |

**No storage-level length caps.** Text fields are unconstrained at the storage layer in v0.4. The UI provides soft guidance via placeholder text ("One paragraph — why is this candidate in the set?"). Pathological-input handling deferred to CBM-redo signal; length caps are easy to add via migration in v0.5 if needed. Mirrors `domain` / `entity` / `process` posture.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

None in v0.4. `crm_candidate` declares no outgoing relationship kinds and registers no new vocabulary entries in `REFERENCE_RELATIONSHIPS`. The mechanical work this spec does demand is one additive change to `vocab.py`:

**Mechanical additions per CLAUDE.md line 48 (ENTITY_TYPES expansion, not relationship-kind addition):**

1. `crm_candidate` added to `ENTITY_TYPES` in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`. (Also: `domain`, `entity`, `process` are added in the v0.4 build per their specs; this spec's addition shares the same migration.)
2. No change to `_kinds_for_pair` is required for the universal kinds: by virtue of being in `ENTITY_TYPES`, `crm_candidate` automatically participates in `is_about` and `references` (universal — valid for any pair), `decided_in` (when `crm_candidate` is the source and a `session` is the target), and `supersedes` (when both source and target are `crm_candidate`).
3. Alembic migration extending the `refs.source_type` and `refs.target_type` CHECK constraints to admit `crm_candidate` as a valid value. (This migration also covers the parallel additions of `domain`, `entity`, and `process`.)

#### 3.3.2 Inbound relationships (anticipated; via existing governance vocabulary)

`crm_candidate` is the anticipated target of references from governance entities — specifically `decision` and `session` — using the existing universal `is_about` and `references` kinds. The methodology context driving these references is:

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `is_about` | `decision` | `crm_candidate` | A governance decision concerns one or more CRM candidates. Used for Phase 5 selection decisions ("DEC-NNN — Selected EspoCRM as the engagement-final CRM, based on iteration-3 Comparison Artifact"). Also used for mid-engagement decisions about removing a candidate from the set. Universal kind; no new vocabulary needed. |
| `references` | `decision` | `crm_candidate` | A governance decision cites a CRM candidate for context without being primarily about it. Universal kind; no new vocabulary needed. |
| `decided_in` | `crm_candidate` | `session` | A `crm_candidate` was created or its status was transitioned in a particular session. This direction (source=crm_candidate, target=session) is supported because the `decided_in` rule is keyed only on target=session. Useful for audit trails of when candidates were added, transitioned, or removed. |
| `is_about` | `session` | `crm_candidate` | A session covered a CRM candidate as a topic. Universal kind; useful for session records of Phase 5 selection or mid-engagement candidate-set adjustment conversations. |

These references are constructed via direct `POST /references` calls from the desktop UI's existing reference-create dialog (DEC-033 cascading vocab dialog). No spec changes to that dialog are required beyond the underlying `ENTITY_TYPES` and CHECK-constraint extensions; the dialog reads `RELATIONSHIP_RULES` at render time and adapts automatically.

**Anticipated v0.5+ vocabulary additions involving `crm_candidate` as target** (informational; not registered in v0.4):

| relationship_kind (anticipated v0.5+) | source | target | semantics |
|-------------------|--------|--------|-----------|
| `deployment_log_targets_candidate` (working name; v0.5+) | `deployment_log` | `crm_candidate` | A Phase 3 deployment log records what was attempted on a particular candidate CRM during a particular iteration. Deferred from v0.4 because `deployment_log` does not yet exist as an entity type. Tracked alongside PI-004 (additional methodology entity types). |
| `comparison_compares_candidates` (working name; v0.5+) | `comparison_artifact` | `crm_candidate` | A Phase 4 Comparison Artifact references each candidate it compared across. Deferred from v0.4 because `comparison_artifact` does not yet exist as an entity type. Tracked alongside PI-004. |

The v0.4-build-planning conversation's cross-spec consistency check verifies that the working names above (and any other anticipated vocab kinds named informationally across the four specs) do not collide.

#### 3.3.3 Cross-spec relationship-kind naming convention — adopted, not established

This spec adopts the `{source}_{verb}_{target}` relationship-kind naming convention established by `domain.md` section 3.3.3 (DEC-048). The adoption is trivial in this case because this spec registers no new relationship-kind values; the convention applies prospectively to the v0.5+ kinds named informationally in section 3.3.2.

#### 3.3.4 Hierarchy

`crm_candidate` does not use the self-referential parent-child hierarchy pattern in v0.4. There is no candidate-of-a-candidate concept in the methodology, and no reason to anticipate one in v0.5+. If a hypothetical future use case surfaces (e.g., grouping multiple candidate-set versions across engagement iterations), it would more naturally be modeled as a separate engagement-version entity type rather than as a self-FK on `crm_candidate`.

### 3.4 Lifecycle

**This spec deviates from `domain.md` and `entity.md` precedent on one structural point: `crm_candidate` uses `removed` as a first-class status value for mid-engagement drops, rather than handling drops via soft-delete.** The deviation is documented and justified in section 3.4.4. Soft-delete continues to handle the authoring-error path (record created in error), keeping the cross-spec soft-delete semantics intact for that case per section 3.4.5.

`crm_candidate` also adopts a four-status enum with three terminal states, where domain and entity have a three-status enum with no terminal states. The structure reflects the methodology reality that CRM candidates have an engagement-long lifecycle ending in a deliberate selection outcome at Phase 5, where domain and entity lifecycles are about ongoing in-scope-or-out-of-scope status without engagement-terminal events.

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `active` | **Default starter status.** Candidate is in the multi-deploy set and will be deployed to during Phase 3 iterations. Default for newly-created records. | (none — starter) | `selected`, `declined`, `removed` |
| `selected` | **Terminal.** Phase 5 outcome: this CRM is the engagement's winning candidate. At most one record per engagement may hold this status — see section 3.4.3 for the singleton constraint. | `active` | (terminal — no successors) |
| `declined` | **Terminal.** Phase 5 outcome: this CRM is not the engagement's winning candidate. Multiple records per engagement may hold this status (the losers of the Phase 5 selection). | `active` | (terminal — no successors) |
| `removed` | **Terminal.** Mid-engagement drop: this CRM was in the candidate set during some iterations but was pulled before Phase 5 (e.g., lived deployment experience revealed it doesn't fit; team-IT capability requirements outstrip the client's capacity; the vendor changed terms). | `active` | (terminal — no successors) |

#### 3.4.2 Transition semantics

The lifecycle implements **three terminal states**: once a candidate has moved out of `active`, it does not transition further. The rationale: each non-`active` value represents a real engagement event — a Phase 5 outcome (`selected` or `declined`) or a mid-engagement deliberate removal (`removed`). Reversing such an event after the fact is a bigger methodology gesture than a status edit can faithfully represent; if a Phase 5 outcome must be revised (e.g., the client changes their selected CRM after closure), that's a new engagement decision that should be captured in a fresh governance decision record and acted on by other means (e.g., a new engagement run, or an explicit administrative reversal handled outside the status field).

The four-status structure also means there is no propose-verify pre-state. Unlike `domain` and `entity` (which use `candidate` as a propose-but-not-yet-verified starter status), `crm_candidate` records exist in v2 only after the CRM Builder's proposal has been verified by the client in Phase 1. The methodology rationale: CRM-candidate proposal is a lightweight Phase 1 gesture (the consultant names two or three products and the client agrees in the same conversation), unlike domain and entity proposals which involve substantive back-and-forth about whether the noun or area-of-work is a real thing for the client. The verification event is the record-creation moment.

#### 3.4.3 Singleton-`selected` constraint

At most one `crm_candidate` record per engagement may hold `crm_candidate_status = selected`. The constraint reflects the methodology: Phase 5 picks one winner from the candidate set. Multiple `selected` records would be ambiguous about which CRM is the engagement's chosen platform.

The constraint is enforced **at the access layer**, not at the storage layer. The access-layer transition validator counts existing non-soft-deleted `crm_candidate` records with `status = selected` (the soft-deleted exclusion matters — see paragraph below) and rejects any POST, PUT, or PATCH that would create a second `selected` record. The rejection response is HTTP 422 with body:

```
{
  "error": "selected_candidate_already_exists",
  "existing": "CRM-NNN"
}
```

where `CRM-NNN` is the identifier of the already-selected record. The error envelope follows the v2 4xx convention.

**Soft-delete bypasses the singleton count.** Because the three non-`active` statuses are terminal (no transitions out), a record that has been mistakenly transitioned to `selected` cannot be edited back to `active` to free up the singleton slot. The only recovery path is to soft-delete the mistaken `selected` record, after which the singleton constraint considers no live `selected` record to exist, allowing a different record to be transitioned to `selected`. The mistakenly-`selected` record persists in `?include_deleted=true` views with both `status = selected` and `deleted_at != null`. This is acknowledged as a small UX rough edge — recovering from a fat-fingered selection requires the soft-delete + restore-elsewhere path rather than an edit — and is logged as a CBM-redo-surfaceable concern in section 3.8.2.

The check applies on POST (creating a record with explicit `status = selected` when another `selected` exists), on PATCH and PUT (transitioning a record into `selected` when another `selected` exists), and on POST `/restore` (restoring a soft-deleted `selected` record into a state where another `selected` already exists). All three are handled by the same access-layer validator.

#### 3.4.4 Deviation rationale — `removed` status vs rejection-via-soft-delete

The cross-spec principle established by `domain.md` (DEC-047) and reaffirmed by `entity.md` (DEC-052) is: **status values track engagement-scope lifecycle; soft-delete tracks existence-in-the-record.** For `domain` and `entity` and `process`, "we proposed it and the client decided it's not right" is existence-in-the-record removal handled by soft-delete — the consultant got the proposal wrong. This spec deviates from that pattern by introducing `removed` as a first-class status value rather than reusing soft-delete for mid-engagement drops.

**The dynamics differ enough from the predecessors to justify the deviation.** For domain / entity / process, rejection is *client-driven verification of a consultant proposal* — the client says "no, that's not actually a domain in our world." The soft-deleted record represents a consultant misjudgment caught at Session 2; keeping it visible behind `?include_deleted=true` is the right UX because it's an authoring-error trail. For `crm_candidate`, mid-engagement removal is *consultant-driven adjustment based on lived deployment experience across iterations*. A candidate dropped at iteration 2 because team-IT capabilities didn't match is not a misjudgment — the consultant could not have known at Phase 1; the iteration loop revealed the misfit; pulling the candidate from further iterations is the correct, methodology-prescribed adjustment. Keeping that record visible by default (as `status = removed`) honors that the engagement legitimately considered the candidate; demoting it to soft-deleted would mis-frame it as an error.

The deviation is small in scope: one extra enum value, one extra paragraph of rationale (this section), no new endpoints, no new access-layer infrastructure beyond the standard transition validator already used by domain, entity, and process. The cross-spec principle survives unchanged for the authoring-error path — see section 3.4.5.

#### 3.4.5 Rejection-via-soft-delete (for authoring errors only)

When a `crm_candidate` record was created in error — wrong product name, wrong rationale, accidentally-added duplicate, etc. — the consultant soft-deletes it via `DELETE /crm_candidates/{crm_candidate_identifier}`. The soft-delete sets `crm_candidate_deleted_at`; the record persists for audit and history, surfaces under the `?include_deleted=true` toggle, and is restorable via POST `/restore`. The cross-spec principle from DEC-047 / DEC-052 carries forward for this path: **soft-delete tracks existence-in-the-record**, separate from the engagement-scope lifecycle tracked by `crm_candidate_status`.

Distinguishing soft-delete from `removed`: soft-delete says "this record should not have existed" (typically because of a data-entry mistake); `status = removed` says "this candidate was legitimately in the set, was lived-deployed-to during some iterations, and was correctly pulled before Phase 5." Both are valid methodology states; they answer different questions.

#### 3.4.6 No `archived` status

Mirrors `domain`, `entity`, `process`. Soft-delete combined with the `?include_deleted=true` toggle already covers the "retained for record, not in active scope" case for the authoring-error path; `status = removed` covers the same for the legitimate-mid-engagement-drop path. No additional `archived` value needed.

#### 3.4.7 Soft-delete semantics

Soft-delete inherits v2's standard behavior:

- DELETE sets `crm_candidate_deleted_at` to the current ISO 8601 UTC timestamp.
- Soft-deleted records do not appear in `GET /crm_candidates` by default.
- `GET /crm_candidates?include_deleted=true` returns soft-deleted records alongside live ones.
- POST `/crm_candidates/{crm_candidate_identifier}/restore` clears `crm_candidate_deleted_at` and reappears the record in the default list.
- Restore on a record that is not soft-deleted returns HTTP 422.
- Restore of a `selected` record triggers the singleton-`selected` constraint check per section 3.4.3 and returns 422 if another live `selected` record already exists.

Inbound `is_about` / `references` / `decided_in` references on a soft-deleted `crm_candidate` are NOT cascade-deleted. They persist in the references table; show-deleted toggles on either side surface them. This matches v2's existing references-table soft-delete behavior.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/crm_candidates` | — | List endpoint. Returns active records by default. Supports `?include_deleted=true` to include soft-deleted records. |
| GET | `/crm_candidates/{crm_candidate_identifier}` | — | Single fetch by identifier. Returns 404 if not found. |
| POST | `/crm_candidates` | full record minus `crm_candidate_identifier` (server-assigned) | Create. Returns 201 with the assigned identifier in the response body. Server-side validation per section 3.2 applied. Singleton-`selected` check applied if request specifies `crm_candidate_status = selected`. |
| PUT | `/crm_candidates/{crm_candidate_identifier}` | full record | Full replace. `crm_candidate_identifier` in body must match the path; mismatch returns 422. |
| PATCH | `/crm_candidates/{crm_candidate_identifier}` | partial record | Partial update. Status-transition validation applied (see 3.5.3). Singleton-`selected` check applied if request transitions into `selected`. |
| DELETE | `/crm_candidates/{crm_candidate_identifier}` | — | Soft-delete; sets `crm_candidate_deleted_at`. Idempotent (DELETE on an already-soft-deleted record returns 200 with no state change). |
| POST | `/crm_candidates/{crm_candidate_identifier}/restore` | — | Clears `crm_candidate_deleted_at`. Returns 422 if the record is not soft-deleted. Singleton-`selected` check applied if the restored record has `status = selected`. |
| GET | `/crm_candidates/next-identifier` | — | Returns `{"next": "CRM-NNN"}` for the next available identifier. Per SES-010 resolution (DEC-043). |

**No deviations from the cross-spec default endpoint set.** No bulk operations, no webhooks, no event streams, no inline-reference convenience endpoints.

#### 3.5.2 Identifier auto-assignment

`crm_candidate_identifier` is server-assigned on POST when omitted from the request body. The assignment logic queries the current maximum `crm_candidate_identifier` (including soft-deleted records, to avoid identifier reuse) and increments the numeric suffix. The `GET /crm_candidates/next-identifier` helper exposes the same logic for clients that want to know the assigned identifier before POSTing.

Concurrent identifier-assignment behavior (locking, optimistic retry, advisory locks, etc.) is implementation-level and decided by the v0.4 build, consistent with how `domain`, `entity`, and `process` handle concurrency. Acceptance criterion #6 in section 3.7 requires correctness under concurrent POSTs.

#### 3.5.3 Status-transition validation

Status transitions are validated server-side at the access layer. PATCH or PUT requests that specify a `crm_candidate_status` value that is not a valid successor of the current value (per section 3.4.1) return HTTP 422 with a body of the form:

```
{
  "error": "invalid_status_transition",
  "from": "<current status>",
  "to": "<requested status>"
}
```

In particular, this body is returned for any attempt to transition out of a terminal state (`selected`, `declined`, or `removed`) — those states have no valid successors.

The default-`active` rule applies on POST: if `crm_candidate_status` is omitted, the server assigns `active`. POST with `crm_candidate_status` explicitly set to a terminal value is permitted (e.g., bulk-importing already-finalized candidate-set records from prior engagement records), subject to the singleton-`selected` check per section 3.5.4.

#### 3.5.4 Singleton-`selected` enforcement

The singleton-`selected` constraint per section 3.4.3 is enforced server-side at the access layer on three operations:

- **POST `/crm_candidates`** with `crm_candidate_status = selected` in the body. If a live (non-soft-deleted) `selected` record already exists, the POST is rejected with HTTP 422 and the `selected_candidate_already_exists` error body, naming the existing record's identifier.
- **PATCH `/crm_candidates/{id}`** or **PUT `/crm_candidates/{id}`** that transitions the target record into `selected`. Same check; same error body. The check excludes the target record itself from the count, so re-PUTting an already-`selected` record with the same status does not trigger the error.
- **POST `/crm_candidates/{id}/restore`** of a soft-deleted record whose current `crm_candidate_status` is `selected`. If a live `selected` record already exists, the restore is rejected with HTTP 422 and the `selected_candidate_already_exists` error body.

The check is purely access-layer; it is not enforced as a database-level constraint. The choice matches v2's existing soft-FK pattern (FKs validated at the access layer, not enforced by SQLite) and keeps the constraint relaxable in future schemas (e.g., a hypothetical "multi-winner" methodology variant would only need access-layer logic changes, not a schema migration).

#### 3.5.5 Other endpoint specifics

- All endpoints return JSON.
- 4xx error responses use the existing v2 error envelope shape.
- No additional list query parameters beyond `?include_deleted=true` in v0.4. Client-side filtering over the expected candidate count (2–3 per engagement) is trivially sufficient. Server-side filtering deferred to CBM-redo signal; unlikely to bite at this scale.

### 3.6 UI Considerations

This spec adopts the spec guide's default `ListDetailPanel` layout with no architectural deviations. Specifics for `crm_candidate` follow.

#### 3.6.1 Sidebar

The "Methodology" sidebar group introduced by `domain.md` section 3.6.1 hosts the new `crm_candidate` entry. Position #4 in the group, completing the workstream-ordered set:

1. Domains
2. Entities
3. Processes
4. **CRM Candidates** (this spec)

All four entries ship together in v0.4.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with these columns:

| Stored field | Display header | Width | Notes |
|--------------|----------------|-------|-------|
| `crm_candidate_identifier` | Identifier | narrow | Default sort key, ascending |
| `crm_candidate_name` | Name | wide | CRM product name |
| `crm_candidate_status` | Status | narrow | Enum value rendered as-is (`active`, `selected`, `declined`, `removed`) |
| `crm_candidate_updated_at` | Updated | narrow | Localized date/time |

Right-click context menu offers New / Edit / Delete / Restore, consistent with v0.3 governance-entity panels per DEC-035 and DEC-036.

Default ascending sort by identifier means newer candidates appear at the bottom; the small expected count per engagement (2–3 typically, occasionally more if mid-engagement additions occur) means alternative orderings are unnecessary in v0.4. No grouping or sub-section in the master pane in v0.4 — terminal-state records (`selected`, `declined`, `removed`) interleave with `active` records by identifier. Whether terminal records should sort separately (e.g., `active` first, terminal below) is a small UX question logged for v0.4-build (section 3.8.1) rather than decided here.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `crm_candidate_identifier` — read-only label
2. `crm_candidate_name` — single-line text editor
3. `crm_candidate_fit_reason` — multi-line text editor with placeholder "One paragraph — why is this candidate in the set?"
4. `crm_candidate_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default
5. `crm_candidate_status` — combo box with the four enum values; combo restricts available choices to valid successors of the current status per section 3.4.2 (so a record in `active` shows all four values; a record in any terminal state shows only the current value, making the combo effectively read-only post-transition)
6. `ReferencesSection` widget — renders any inbound governance-entity citations (`is_about` / `references` from decisions or sessions; `decided_in` to sessions; `supersedes` if two `crm_candidate` records have a supersession relationship). The widget is always present; in v0.4 the outgoing-references list is empty (no outgoing relationship kinds declared) and the inbound list populates as decision and session records are authored citing this candidate.

The collapsed-by-default treatment of `crm_candidate_notes` matches `domain_notes` / `entity_notes` / `process_notes` — internal consultant scratchpad, not part of any client-facing render.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `crm_candidate_identifier` not shown in create mode (server-assigned).
- `crm_candidate_status` defaults to `active`; the combo offers all four values so a consultant importing already-finalized candidate-set records can create directly into a terminal state (subject to the singleton-`selected` check for `selected`).
- Required-field validation client-side before submit (`crm_candidate_name`, `crm_candidate_fit_reason`).
- Server-side validation errors (uniqueness, format, transition, singleton-`selected`) surface inline.

#### 3.6.5 Edit dialog

Same shape as create. `crm_candidate_identifier` displayed as read-only label. Status transitions enforced per section 3.4.2; the combo restricts available choices to valid successors of the current status. Invalid selections in the status combo are either prevented (recommended UX) or rejected by the server with the 422 surfacing inline (acceptable fallback). Singleton-`selected` violations also surface inline via the 422 response.

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `crm_candidate_identifier` value (e.g., `CRM-002`) to enable the Delete button, matching v0.3 governance-entity patterns. Confirmation soft-deletes the record. The dialog's confirmation text should clarify that DELETE is for the authoring-error path (record created in error); for mid-engagement removal of a legitimate candidate, the consultant should transition `crm_candidate_status` to `removed` rather than delete — that distinction is the deviation rationale of section 3.4.4 surfacing at the UI level. Specific wording of the dialog's clarifying note is a v0.4-build detail.

### 3.7 Acceptance Criteria

The following 12 statements define what "this entity type is correctly implemented in v0.4" looks like. Each is concrete and testable; v0.4 build planning translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `crm_candidates` table with all eight columns (`crm_candidate_identifier`, `crm_candidate_name`, `crm_candidate_fit_reason`, `crm_candidate_notes`, `crm_candidate_status`, `crm_candidate_created_at`, `crm_candidate_updated_at`, `crm_candidate_deleted_at`), correct types and constraints, and runs both forward and backward without error. The same migration (or a coordinated companion migration) adds `crm_candidate` to the `refs.source_type` and `refs.target_type` CHECK constraints alongside the other three new methodology entity types.

2. **`crm_candidate_identifier` format constraint enforced.** Insertions with `crm_candidate_identifier` not matching `^CRM-\d{3}$` raise a validation error at the access layer.

3. **`crm_candidate_name` uniqueness enforced engagement-globally and case-insensitively.** Inserting a second row whose `crm_candidate_name` matches an existing row by lowercase comparison raises a uniqueness violation.

4. **`crm_candidate_status` enum and transition validation.** Insertions with `crm_candidate_status` outside `{active, selected, declined, removed}` are rejected. PATCH/PUT requesting an invalid transition — including any transition out of a terminal state (`selected`, `declined`, or `removed`) — returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

5. **Singleton-`selected` constraint enforced on POST, PATCH/PUT, and restore.** Creating a second record with `crm_candidate_status = selected` while another live `selected` record exists returns HTTP 422 with `{"error": "selected_candidate_already_exists", "existing": "CRM-NNN"}`. Same for transitioning a record into `selected` via PATCH or PUT when another live `selected` exists. Same for restoring a soft-deleted record whose `status` is `selected` when another live `selected` exists. The check excludes soft-deleted records from the count; soft-deleting a mistakenly-`selected` record frees the singleton slot for a different record.

6. **Access-layer methods exist with expected signatures.** `client.list_crm_candidates()`, `client.get_crm_candidate(identifier)`, `client.create_crm_candidate(...)`, `client.update_crm_candidate(identifier, ...)`, `client.patch_crm_candidate(identifier, ...)`, `client.delete_crm_candidate(identifier)`, `client.restore_crm_candidate(identifier)`, `client.next_crm_candidate_identifier()` exist and pass unit tests covering happy path and at least one error case each, including the singleton-`selected` rejection path.

7. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the v2 error envelope. Identifier auto-assignment under concurrent POSTs assigns distinct identifiers (concurrent-insert test required, consistent with the same property for `domain`, `entity`, `process`).

8. **Soft-delete and restore round-trip correctly for the authoring-error path.** DELETE sets `crm_candidate_deleted_at`; the record disappears from `GET /crm_candidates`. `GET /crm_candidates?include_deleted=true` shows it. POST `/restore` clears `crm_candidate_deleted_at`; the record reappears in the default list. Restore on a record that is not soft-deleted returns 422. Restore on a soft-deleted `selected` record when another live `selected` exists returns 422 per acceptance criterion #5.

9. **`crm_candidate` registered in `ENTITY_TYPES` and references-table CHECK constraint extended.** `ENTITY_TYPES` in `vocab.py` includes `crm_candidate`. POST `/references` with `source_type=crm_candidate` or `target_type=crm_candidate` and a compatible kind (`is_about`, `references`, `decided_in` to a session target, or `supersedes` between two `crm_candidate` records) succeeds. POST `/references` with an unsupported kind for the pair (e.g., `affects` from a `crm_candidate` source) returns 422 per the existing `RELATIONSHIP_RULES` lookup. Direct DB insert into `refs` with `source_type=crm_candidate` or `target_type=crm_candidate` succeeds.

10. **`CRM Candidates` sidebar entry appears under the Methodology group, position #4.** After Domains, Entities, and Processes (all four ship together in v0.4).

11. **Master pane columns and default sort.** The CRM Candidates panel shows columns Identifier / Name / Status / Updated, sorted by Identifier ascending. Right-click context menu offers New / Edit / Delete / Restore. Detail pane renders all fields in section-3.2 order: Identifier (read-only), Name, Fit Reason, Notes (collapsed under "Internal notes" header), Status, ReferencesSection.

12. **Sample CBM-redo Phase 1 records authored and a Phase 5 selection round-tripped through the UI.** A consultant can author 3 `crm_candidate` records (e.g., EspoCRM, SuiteCRM, Salesforce) through the New dialog at Phase 1, all starting in `active`. Mid-engagement, the consultant transitions one (e.g., SuiteCRM) to `removed` via the Edit dialog and the master pane reflects the change. At Phase 5, the consultant transitions one of the remaining records (e.g., EspoCRM) to `selected` and the other (e.g., Salesforce) to `declined`; attempting to transition both to `selected` is rejected with the singleton-`selected` 422. A governance decision record (DEC-NNN) authored separately and citing the `selected` `crm_candidate` via `is_about` renders in that candidate's ReferencesSection inbound list. The records, statuses, and references all persist correctly across application restart and across REST/MCP refetch.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For v0.4 build to settle

**[v0.4 build] Concurrent identifier-assignment behavior.** The mechanism for preventing two concurrent POSTs from assigning the same `CRM-NNN` (row-level locking, optimistic retry, advisory locks, etc.) is implementation-level and not specified by this spec. Acceptance criterion #7 requires correctness; the *how* is the v0.4 build's call, consistent with whatever pattern the `domain`, `entity`, and `process` builds adopt for the same property.

**[v0.4 build] Master-pane sort of terminal-state records.** Section 3.6.2 sorts by identifier ascending, which interleaves terminal-state records (`selected`, `declined`, `removed`) with `active` records. Two alternative behaviors are reasonable: (a) keep the simple identifier sort and accept the interleaving (the small per-engagement count makes this mostly cosmetic); (b) sort by status first (active first, then terminal states by some ordering) and identifier within status. The v0.4-build-planning conversation decides whether (a) or (b) is implemented; if (b), the status ordering needs to be settled (e.g., `active` → `selected` → `declined` → `removed`, putting the engagement winner immediately below the actives).

**[v0.4 build] Delete-dialog clarifying note wording.** Section 3.6.6 calls for the Delete dialog to clarify that DELETE is for the authoring-error path and that the `removed` status is the correct method for legitimate mid-engagement candidate-set adjustments. The specific wording of that note is a v0.4-build UI detail.

#### 3.8.2 For CBM redo to surface

**[CBM redo] Markdown for `crm_candidate_fit_reason`.** Plain text in v0.4. The CBM redo's actual Phase 1 work will reveal whether fit rationales need emphasis, bullet lists, or inline links to vendor pages. If so, a v0.5 migration introduces markdown rendering. The decision deliberately waits on real-use signal. Mirrors `domain` / `entity` / `process` posture.

**[CBM redo] Text-field length caps.** No storage-level length constraints in v0.4; UI placeholder text provides soft guidance. If the CBM redo produces pathological inputs, caps are added via migration in v0.5. Same posture as the predecessors.

**[CBM redo] `crm_candidate_notes` structure.** Flat plain text in v0.4. If consultant notes accrete substantially across an engagement — pattern-library reasoning about why this candidate was a fit, iteration-by-iteration observations about its behavior, lessons learned by Phase 5 — a structured-journal pattern becomes a v0.5 candidate. Same posture as `domain_notes` / `entity_notes` / `process_notes`.

**[CBM redo] Singleton-`selected` recovery friction.** Section 3.4.3 acknowledges that recovering from a fat-fingered transition into `selected` requires a soft-delete + restore-elsewhere path rather than a direct edit (because terminal states have no transitions out). The CBM redo will surface how often this happens and whether the friction is meaningful. A v0.5 mitigation, if needed, would either (a) introduce a "reverse a Phase 5 outcome" administrative path or (b) relax the terminal-state-no-transitions-out rule for the `selected → active` direction specifically. The minimum-viable posture defers both.

**[CBM redo] `removed` status real-world utility.** This spec introduces `removed` as a deviation from the rejection-via-soft-delete cross-spec principle, on the argument that mid-engagement candidate drops carry methodology value worth keeping visible by default. The CBM redo will validate this argument: if `removed` records sit in the master pane and nobody refers to them after the fact, the deviation didn't pay off and a v0.5 revision could collapse `removed` back into soft-delete. If `removed` records get referenced (in governance decisions documenting why the engagement narrowed the candidate set, in retrospectives across engagements, in the Phase 5 selection rationale citing what was considered and rejected), the deviation is justified by lived signal.

**[CBM redo] Server-side list filters.** Only `?include_deleted=true` is supported in v0.4. Client-side filtering over a 2–3-record engagement is trivially sufficient. Filters by status (e.g., `?status=active` to hide terminal-state records on the master pane) could become useful if engagements grow to many more candidates, but that's an unlikely scenario per the methodology.

**[CBM redo] Structured-metadata enums (hosting type, license type, price tier, vendor URL).** Deferred from v0.4 under PI-012 pending CBM-redo signal. The CBM redo will validate whether the consultant misses scannable classification at the panel level or whether the prose-in-`fit_reason` posture is sufficient.

#### 3.8.3 For v0.5+

**[v0.5+] PI-012 — `crm_candidate` structured-metadata enums.** New planning item authored at this conversation's close. Captures the deferred v0.4 fields: `crm_candidate_vendor_url` (free text URL), `crm_candidate_hosting_type` (enum: `cloud` / `self_hosted` / `both`), `crm_candidate_license_type` (enum: `open_source` / `commercial` / `freemium`), `crm_candidate_price_tier` (enum: `free` / `paid`). Triggered to v0.5 ahead of other v0.5 candidates if CBM-redo signal surfaces a need for scannable classification. Includes UI work for new combo boxes and master-pane column extensions; Alembic migration extending the table with optional new columns and CHECK constraints for the three enums.

**[v0.5+] PI-004 — additional methodology entity types.** Already tracked. `field`, `requirement`, `manual_config`, `test_spec`. Two of those v0.5+ entity types — a hypothetical `deployment_log` (Phase 3 output) and a hypothetical `comparison_artifact` (Phase 4 output) — would source inbound references targeting `crm_candidate` per section 3.3.2's anticipated table. Their addition to the schema also extends PI-004's scope.

**[v0.5+] PI-005 — process schema growth.** Already tracked. No direct interaction with `crm_candidate`, but the Phase 3 work that fleshes out process definitions will also produce the deployment-log artifacts that reference `crm_candidate` per section 3.3.2's anticipated `deployment_log_targets_candidate` kind.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following five decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against `PRDs/product/crmbuilder-v2/close-out-payloads/ses_015.json` at conversation close. Each is linked to SES-015 via a `decided_in` reference recorded in the same payload. The DEC numbers assume the SES-012 / SES-013 / SES-014 close-out payloads have already been applied (they have, per the apply commit at `2accd8c`); the next available DEC number is DEC-060.

- **DEC-060 — `crm_candidate` identifier prefix and format.** Adopts `CRM` (three letters) under `domain.md`'s soft-3-letter posture; methodology context disambiguates against "the CRM software" / "CRM Builder" without need for a four-letter form (see section 3.1).
- **DEC-061 — `crm_candidate` field inventory under minimum-viable v0.4 scope.** Five substantive fields (`crm_candidate_identifier`, `crm_candidate_name`, `crm_candidate_fit_reason`, `crm_candidate_notes`, `crm_candidate_status`) plus inherited timestamps. No structured-classification metadata in v0.4 (vendor URL, hosting type, license type, price tier deferred to PI-012). No storage-level length caps. Case-insensitive engagement-global name uniqueness inherited from DEC-045 / DEC-051 / DEC-056 (see section 3.2).
- **DEC-062 — `crm_candidate` lifecycle deviation from rejection-via-soft-delete cross-spec principle.** Four-status enum (`active` / `selected` / `declined` / `removed`) with three terminal states and a default starter of `active`. Introduces `removed` as a first-class status for mid-engagement drops rather than reusing soft-delete, on the rationale that consultant-initiated lived-deployment-driven adjustments are methodologically distinct from authoring-error rejections (see section 3.4.4 for the deviation rationale). Rejection-via-soft-delete preserved for the authoring-error path (see section 3.4.5). Access-layer singleton-`selected` constraint enforcing at most one winner per engagement (see section 3.4.3).
- **DEC-063 — `crm_candidate` relationship posture and `ENTITY_TYPES` expansion.** No outgoing relationships in v0.4. No new relationship-kind vocabulary entries registered. Single mechanical addition: `crm_candidate` added to `ENTITY_TYPES` in `vocab.py`, with the Alembic migration extending the `refs.source_type` and `refs.target_type` CHECK constraints to admit `crm_candidate`. Inbound references from governance entities (decisions, sessions) supported via the existing universal vocabulary (`is_about`, `references`, `decided_in`, `supersedes`) without further additions (see section 3.3).
- **DEC-064 — `crm_candidate` API surface, UI defaults, singleton-`selected` enforcement, and acceptance criteria for v0.4.** Standard 8-endpoint set with no deviations. Status-transition validation server-side per section 3.5.3. Singleton-`selected` enforcement on POST, PATCH/PUT, and restore per section 3.5.4. Default `ListDetailPanel` UI under the Methodology sidebar group at position #4. Detail pane renders inbound governance-entity citations via the standard `ReferencesSection` widget. Sort, dialog-wording, and similar UI details settled by the v0.4-build-planning conversation. 12 testable acceptance criteria (see sections 3.5, 3.6, 3.7).

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry; documents the `ENTITY_TYPES` / `_kinds_for_pair` / Alembic-migration triad that section 3.3.1's mechanical addition follows.
- `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan governing this conversation as the fourth and final per-entity schema-design conversation.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/schema-design-kickoff-crm_candidate.md` — this conversation's seed prompt.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — first predecessor spec; source of cross-spec conventions inherited and applied here (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture, rejection-via-soft-delete posture for the authoring-error path, no-archived posture, engagement-global case-insensitive name uniqueness).
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — second predecessor spec; source of further cross-spec conventions (decomposed reference handling, master-pane minimum-viable column posture).
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` — third predecessor spec; precedent for justified deviation from a cross-spec norm (process's no-status-field deviation in its section 3.4.1 is the pattern this spec follows for its `removed`-status deviation in section 3.4.4).
- `PRDs/process/research/evolved-methodology/evolved-methodology-phase-outline.md` — section 3 Phase 1 (Initial CRM Candidate Set output specification); section 3 Phase 3 (the candidate set is the input to Iteration Build and Deploy and persists across iterations); section 3 Phase 5 (CRM Selection Decision; decommissioning of non-selected instances).

#### 3.9.3 Related prior decisions informing this spec

- **DEC-006** — Universal references table as the cross-entity-type edge store. Foundation for the `is_about` / `references` / `decided_in` inbound-citation pattern in section 3.3.2.
- **DEC-035** — `ListDetailPanel` master-widget + context-menu factory refactor. Informs master pane patterns in section 3.6.2.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs context-menu behavior in section 3.6.2.
- **DEC-039** — Minimum entity inventory and multi-tenancy posture. Directly justifies `crm_candidate`'s inclusion in v0.4's minimum-viable set as a Phase 1-driven content entity.
- **DEC-043** — SES-010 identifier-asymmetry resolution. Mandates the `GET /crm_candidates/next-identifier` helper endpoint cited in section 3.5.1.
- **DEC-044** — `domain` identifier prefix and format; establishes the soft-3-letter prefix posture that section 3.1 invokes for `CRM`'s three-letter form.
- **DEC-046** — Parent-prefix field-naming convention for methodology entities. Establishes the field-naming pattern this spec inherits and applies (see section 3.2).
- **DEC-047** — `domain` status lifecycle, propose-verify gate, and rejection-via-soft-delete posture. Establishes the cross-spec principle from which this spec deviates on the engagement-scope-lifecycle handling (see section 3.4.4) while preserving for the authoring-error path (see section 3.4.5).
- **DEC-048** — `domain` relationship posture and `{source}_{verb}_{target}` relationship-kind naming convention. Establishes the relationship-kind naming pattern this spec adopts trivially (no new kinds registered).
- **DEC-049** — `domain` API surface, UI defaults, acceptance criteria for v0.4. Establishes the API-and-UI default patterns this spec adopts (see sections 3.5, 3.6, 3.7).
- **DEC-052** — `entity` status lifecycle adoption. Reaffirms the cross-spec rejection-via-soft-delete principle that this spec deviates from for the legitimate-mid-engagement-drop path.
- **DEC-054** — `entity` API surface, UI defaults, decomposed reference handling. Establishes the decomposed-reference posture (no inline-reference convenience endpoints) that this spec adopts trivially (no outgoing references in v0.4).
- **DEC-055** — `process` identifier prefix and format. Precedent for the soft-3-letter-with-explicit-deviation pattern; this spec affirms three letters where process took four.
- **DEC-056** — `process` field inventory under v0.4 scope, with no-status-field deviation. Precedent for a methodology entity deliberately deviating from a cross-spec norm on lifecycle structure when methodology semantics warrant; this spec's `removed`-status deviation follows the same pattern.
- **DEC-058** — `process` relationship architecture. Precedent for mixing FK and references-edge mechanisms within a single spec; this spec uses neither in v0.4 (no outgoing relationships), but the principle informs the section 3.3.2 anticipated v0.5+ vocabulary.
- **DEC-059** — `process` API surface, UI defaults, acceptance criteria. Cross-spec consistency reference for the standard endpoint set adopted here.

#### 3.9.4 Predecessor and successor conversations

- **Predecessor:** `process` schema-design conversation. SES-014 close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_014.json` (applied at commit `2accd8c`). Produced `process.md` v1.0, DEC-055 through DEC-059, and PI-011.
- **Successor:** v0.4-build-planning conversation — kickoff at `PRDs/product/crmbuilder-v2/ui-PRD-v0.4-build-planning-kickoff.md` (authored by this conversation alongside this spec). The build-planning conversation takes all four schema specs (`domain.md`, `entity.md`, `process.md`, `crm_candidate.md`) as input and produces the v0.4 PRD, implementation plan, and slice build prompts. The cross-spec consistency check defined in spec guide section 7.2 is the build-planning conversation's first task.

---

*End of document.*
