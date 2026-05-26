# Methodology Entity Schema Spec — `test_spec`

**Last Updated:** 05-25-26 16:30
**Status:** Draft v1.0 — produced as part of PI-004 resolution
**Position in workstream:** Phase 3+ methodology entity (sibling of `field`, `persona`, `requirement`, `manual_config` per PI-004)
**Predecessor specs:** `domain.md`, `entity.md`, `process.md`, `crm_candidate.md`, `engagement.md` (v0.4 methodology schema specs), and the v0.5+ sibling specs (`field`, `persona`, `requirement`, `manual_config`) that share PI-004's resolution scope.
**Successor specs:** None within PI-004. Future expansion captured under v0.6+ planning items in section 3.8.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-25-26 16:30 | Doug Bower / Claude | Initial draft. Produced as part of PI-004 resolution scope (Additional methodology entity types for v0.5+: field, requirement, manual_config, test_spec). Defines `test_spec` as the v2 methodology entity type that hosts verification specifications — the bridge between requirements (what must be true) and verification runs (was it true on this deploy). Inherits all conventions established by the v0.4 methodology-entity-schema-design workstream (parent-prefix field naming per DEC-046, `{source}_{verb}_{target}` relationship-kind naming per DEC-048, soft-3-letter prefix posture per DEC-044). Establishes the dual-axis state pattern (methodology-lifecycle status separated from execution-outcome) as a v0.5+ convention candidate for any future verification-like entity. |

---

## Change Log

**Version 1.0 (05-25-26 16:30):** Initial creation. Defines `test_spec` as a verification specification — one test or check that confirms a requirement is satisfied. Adopts `TST-NNN` identifier format under the soft-3-letter posture. Inventories ten substantive fields (`test_spec_identifier`, `test_spec_name`, `test_spec_description`, `test_spec_setup`, `test_spec_steps`, `test_spec_expected`, `test_spec_notes`, `test_spec_status`, `test_spec_last_run_outcome`, `test_spec_last_run_at`, `test_spec_last_run_notes`) plus inherited timestamps. Implements **dual-axis state**: a three-status methodology lifecycle (`candidate` / `confirmed` / `deferred`, identical shape to `domain` / `entity`) plus a separate four-value execution-outcome field (`not_run` / `passing` / `failing` / `skipped`) that records the latest verification run's result. Justifies the separation on the methodology-vs-execution principle: lifecycle tracks whether the test spec belongs in the engagement; outcome tracks whether the most recent execution of that test passed. Many-to-many `test_spec_touches_entity`, `test_spec_touches_field`, `test_spec_exercises_process` relationships outbound via the references entity; the inverse-of-`requirement_verified_by_test_spec` edge is declared by the requirement-side spec, not here. Standard endpoint set with no surface deviation except an open-question `POST /test-specs/{id}/record-run` convenience endpoint deferred to the v0.5 build conversation. UI ships a five-column master pane (Identifier / Name / Status / Last Run / Updated) with a color-cued Last Run column — passing green, failing red, not_run gray, skipped amber — flagged as a UI-render deviation from the entity panel's pattern and justified by the operational value of scanning verification health at the master pane. Sixteen testable acceptance criteria covering schema migration with both status fields, enum + transition validation per axis, server-set `last_run_at` when outcome moves to a run state, access-layer signatures, REST surface, identifier auto-assignment, soft-delete / restore, sidebar placement, the colored master-pane cue, detail-pane sectioning of setup / steps / expected, last-run block, CRUD dialogs, references round-tripping for the three outbound kinds plus the inbound, and a sample acceptance of roughly 10 CBM test specs.

---

## 1. Purpose and Position

This document specifies the `test_spec` entity type for v2's storage layer. It is part of PI-004's resolution scope — the v0.5+ tranche of methodology entity types (`field`, `persona`, `requirement`, `manual_config`, `test_spec`) that extend the v0.4 minimum-viable set with the late-phase methodology objects the evolved methodology's Phase 3+ work produces.

The schema is governed by `methodology-entity-schema-spec-guide.md` and inherits all four cross-spec conventions established by the v0.4 workstream:

- **Soft-3-letter prefix posture** (DEC-044): three-letter identifier prefix when unambiguous.
- **Parent-prefix field naming** (DEC-046): all non-identifier, non-timestamp fields are prefixed with the parent entity name.
- **One-way propose-verify gate on methodology status** (DEC-047): once a record moves out of `candidate`, it does not regress.
- **`{source}_{verb}_{target}` relationship-kind naming** (DEC-048): vocabulary entries involving methodology entities are named source-first.

`test_spec` is positioned downstream of `requirement`. Each test spec typically verifies one requirement; the inverse-direction edge `requirement_verified_by_test_spec` is declared and registered by the requirement-side spec. From the test-spec side, that relationship is **inbound only** in this document (section 3.3.2) — registered once at the requirement side avoids the duplicate-registration hazard described by CLAUDE.md line 48 (the `REFERENCE_RELATIONSHIPS` + `_kinds_for_pair` + Alembic migration triad must be updated together, and each kind must appear exactly once across all source-side specs).

The test_spec's outbound edges traverse downward and sideways across the methodology graph: `test_spec_touches_entity` (entities the test reads, creates, or modifies), `test_spec_touches_field` (specific fields the test asserts on), `test_spec_exercises_process` (processes the test exercises end-to-end). These three are registered from this spec's side because `test_spec` is the source. `test_spec_touches_field` anticipates the `field` spec's v0.5+ identifier vocabulary (`FLD-NNN`) and assumes it is registered prior to or alongside this spec; the cross-spec consistency check at the v0.5-build-planning conversation validates the ordering.

The test_spec schema in v0.5+ is intentionally thin in the same minimum-viable shape established by the v0.4 workstream. It captures a verification specification's content (name, what it tests, preconditions, steps, expected results) plus a methodology lifecycle and an execution-outcome record of the most recent run. It deliberately omits full execution history (each historical run becomes a separate row in a `test_run` history entity in a future release per section 3.8.3), structured per-step expected-results decomposition (open question for CBM-redo signal), and automated execution / verification-engine integration (a much larger v0.6+ workstream).

---

## 2. Summary

A `test_spec` record in v2 represents one test or verification that confirms a requirement is satisfied — e.g., "Submit a mentor application form with all required fields populated; verify the confirmation email arrives within 2 minutes" or "Create a Mentor record with a Dues amount of 0.00 and verify the Mentor Status field updates to 'Active without Dues' after save." Test specs are the artifacts the evolved methodology's verification phase produces (analogous to Phase 13 in the current 13-phase methodology) — the bridge between requirements as authored objects and verification runs as executed events.

Each `test_spec` record holds: a methodology identifier (`TST-NNN`), a short name describing the test, a fuller free-text description of what the test is checking, three plain-text content fields (setup / preconditions, steps to execute, expected results), an optional consultant notes scratchpad, a methodology lifecycle status, and an execution-outcome snapshot tracking the most recent run (outcome value, timestamp, notes from the run). Verification artifacts the test spec is bound to — the requirement it verifies, the entities and fields it touches, the processes it exercises — are captured via the references entity using the standard v2 universal references store.

The schema implements **dual-axis state**: a `test_spec_status` field tracks the methodology lifecycle (`candidate` / `confirmed` / `deferred`, with the same propose-verify gate established by `domain` and `entity`), and a separate `test_spec_last_run_outcome` field tracks the execution result (`not_run` / `passing` / `failing` / `skipped`, with unrestricted transitions because results are observational rather than decisional). The separation matches the methodology-vs-execution principle that runs throughout v2's storage layer: lifecycle is the methodology team's judgment about whether the test belongs in the engagement; outcome is what happened when the test was last executed against a real deploy.

The schema in its initial release (v0.5+, PI-004 resolution) ships with last-run-snapshot only — no historical execution log, no integration with an automated verification engine. Both extensions are tracked as v0.6+ planning items in section 3.8.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `test_spec` |
| Display name (singular) | Test Spec |
| Display name (plural) | Test Specs |
| Identifier prefix | `TST` |
| Identifier format | `TST-NNN`, zero-padded to 3 digits (e.g., `TST-001`, `TST-042`) |
| Identifier auto-assignment | Server-side on POST omission per PI-002; helper at `GET /test-specs/next-identifier` per DEC-043 |

`TST` is three letters and adheres to the soft-3-letter prefix posture (DEC-044). It reads unambiguously as "test", has no collision with existing prefixes (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRM, WS, CONV, RB, WT, COP, DEP, CM, PER, FLD, REQ, MCF), and matches the v2 governance- and methodology-entity norm. The `TST` choice deliberately avoids `TS` (two letters; reads as a `topic_status` or a generic timestamp abbreviation) and `TEST` (four letters when three suffices).

No deviation from the cross-spec defaults: identifier auto-assignment on POST omission per PI-002, with the `GET /test-specs/next-identifier` helper endpoint per DEC-043 for clients that prefer read-then-write. Explicit identifiers in POST bodies are accepted when they match `^TST-\d{3}$` and do not collide with an existing row (collision → 409, malformed → 422), per the same rules that govern every prefixed-identifier entity type in v2.

### 3.2 Fields

Field naming follows the parent-prefix convention (DEC-046): all fields including identifier and timestamps adopt the `test_spec_` prefix for full convention consistency with the four v0.4 methodology entities and the rest of PI-004's resolution tranche.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `test_spec_identifier` | TEXT | yes | server-assigned | `^TST-\d{3}$`, unique | The methodology-entity identifier in `TST-NNN` format. Server-assigned when omitted from POST body per PI-002. |
| `test_spec_name` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Short name describing the test (e.g., "Mentor application form submission produces confirmation email", "Dues 0.00 sets Mentor Status to Active without Dues"). |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `test_spec_description` | TEXT | yes | — | non-empty trimmed | Free-text description of what the test verifies. Plain text in v0.5+; markdown deferred to CBM-redo signal. Sentence- to paragraph-length is typical. |
| `test_spec_setup` | TEXT | no | — | — | Preconditions and setup steps — what must be true before the test runs (e.g., "A mentor record exists with email mentor@example.com and status Active"; "The MR-Dues entity has been deployed and the operator is logged in as a CRM admin"). Plain text in v0.5+; structured-step shape an open question for CBM redo (section 3.8.2). |
| `test_spec_steps` | TEXT | yes | — | non-empty trimmed | Numbered or bulleted steps to execute the test, free-text. Plain text in v0.5+. Operators read the steps top-to-bottom; structured numbered-substep / expected-per-step shape is deferred to CBM-redo signal — see section 3.8.2. |
| `test_spec_expected` | TEXT | yes | — | non-empty trimmed | Expected results — what must be true after the steps execute for the test to be considered passing (e.g., "Confirmation email arrives at mentor@example.com within 2 minutes containing the application reference number"; "The Mentor Status field shows 'Active without Dues' and Dues field shows 0.00"). Plain text in v0.5+. |
| `test_spec_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of any client-facing render or verification-run record. Used to capture authoring rationale, alternative-approach trails, between-session reasoning about why the test exists in the form it does. Plain text in v0.5+. |

The split into `test_spec_setup`, `test_spec_steps`, and `test_spec_expected` (rather than collapsing into a single free-text `test_spec_body`) is per the verification-spec convention from current-methodology Phase 13: setup, action, expected are the three things any verification run needs separately, and free-text-blob authoring tends to elide one of the three. The cost is three fields rather than one; the value is a uniform shape that pays off in detail-pane rendering (section 3.6.3) and acceptance-criterion clarity. Markdown rendering on these fields is a CBM-redo signal item per section 3.8.2.

#### 3.2.3 Classification fields

The dual-axis state is captured here as two separate enum fields. The first tracks the methodology lifecycle (decisional — does this test spec belong in the engagement?); the second tracks the execution outcome (observational — did the most recent run pass?). The separation is justified in §3.4.3.

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `test_spec_status` | TEXT | yes | `candidate` | enum: `candidate` \| `confirmed` \| `deferred`; valid transitions per section 3.4.1 | Methodology lifecycle status. Same shape and transition map as `domain` and `entity`. Tracks whether the test spec is a CRM-Builder-proposed candidate, a client-confirmed in-scope verification, or an acknowledged-but-deferred area. |
| `test_spec_last_run_outcome` | TEXT | yes | `not_run` | enum: `not_run` \| `passing` \| `failing` \| `skipped`; transitions unrestricted per section 3.4.2 | Execution outcome of the most recent verification run. `not_run` means the test has not yet been executed. Transitions are unrestricted (results are observational, not decisional) — any value may move to any other value. Server enforces the cross-field rule that `last_run_at` must be set whenever this is not `not_run` (section 3.5.3). |

#### 3.2.4 Relationship fields

The execution-outcome triplet (outcome / when / notes) lives on the entity table; the relationships to the requirement being verified, the entities and fields the test touches, and the processes it exercises live in the references entity (section 3.3). The non-relationship fields in this category are the two execution-record companions to `test_spec_last_run_outcome`:

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `test_spec_last_run_at` | DATETIME | no | null | ISO 8601 UTC; must be set whenever `test_spec_last_run_outcome` is not `not_run` (server-enforced) | Timestamp of the most recent verification run. Server-set on the request that moves `test_spec_last_run_outcome` to `passing` / `failing` / `skipped` if the client omits it; client may also supply explicitly. Cleared back to null only if `test_spec_last_run_outcome` is reset to `not_run`. |
| `test_spec_last_run_notes` | TEXT | no | — | — | Free-text notes from the most recent run (e.g., "Failed at step 4 — confirmation email did not arrive within timeout"; "Skipped — feature not yet deployed to test instance"). Not part of historical execution log (deferred to v0.6+ test-run history entity per section 3.8.3). |

No FK columns on the entity table beyond the implicit references-table relationships. The choice mirrors `entity.md`'s posture — references discipline keeps the entity-table schema small, supports inverse queries via the existing references infrastructure, and matches v2's cross-entity-type pattern.

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `test_spec_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `test_spec_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `test_spec_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |

**No storage-level length caps on the text fields.** Same posture as `domain` and `entity` — UI placeholder text provides soft guidance ("Numbered steps to execute the test", "What must be true after the steps execute"). Pathological-input handling deferred to CBM-redo signal.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

`test_spec` declares three outgoing relationship kinds at first release.

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `test_spec_touches_entity` | `test_spec` | `entity` | references-entity edge | many-to-many | The test spec reads, creates, modifies, or asserts on records of this entity type. A test that "submits a mentor application form" touches the entity behind the form (e.g., `ENT-XXX` for the Mentor Application entity). A test may touch zero, one, or many entities; an entity may be touched by zero or many test specs. |
| `test_spec_touches_field` | `test_spec` | `field` | references-entity edge | many-to-many | The test spec asserts on the value of a specific field after the steps execute, or sets a specific field during the steps. Anticipates the `field` entity spec (PI-004 sibling); `FLD-NNN` identifier prefix per that spec. A test may touch zero, one, or many fields; a field may be touched by zero or many test specs. |
| `test_spec_exercises_process` | `test_spec` | `process` | references-entity edge | many-to-many | The test spec exercises one or more processes end-to-end (e.g., a "mentor application happy-path" test exercises the `PROC-XXX` mentor-application-intake process). Anticipates v0.5+ process-schema growth per PI-005; the relationship is registrable against the current `process` spec without modification. |

All three are many-to-many via the references entity. The mechanism choice is consistent with `entity.md` section 3.3.1's rationale (references discipline keeps the entity-table schema small, supports inverse queries, matches v2's cross-entity-type pattern), and consistent with the v0.4 workstream's established preference for references over multi-value FK columns whenever the cardinality is many-to-many.

**Mechanical additions per CLAUDE.md line 48:**

1. `test_spec_touches_entity`, `test_spec_touches_field`, `test_spec_exercises_process` added to `REFERENCE_RELATIONSHIPS` in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`.
2. `_kinds_for_pair` extended so:
   - `(test_spec, entity)` returns `{test_spec_touches_entity}`
   - `(test_spec, field)` returns `{test_spec_touches_field}`
   - `(test_spec, process)` returns `{test_spec_exercises_process}`
3. Alembic migration extending the `refs.relationship_kind` CHECK constraint to include the three new values.

**Cardinality and validation:**

- All three are many-to-many. No upper bound on either side.
- Zero-relationship is permitted across the board: a test spec authored before the entities, fields, or processes it touches are themselves authored is valid; the relationships attach later. The references discipline must not force pre-decided wiring.
- Source must be a live `test_spec` record; target must be a live record of the appropriate type. Existing access-layer rules for the references table.
- Duplicate `(source_id, target_id, relationship_kind)` tuples are rejected by the references-table uniqueness constraint.

**Lifecycle semantics:** soft-deleting a `test_spec` does not cascade-delete its outgoing references; the references persist and remain visible via the show-deleted UI toggle on either side. Same for soft-deleting any target. Restoring either endpoint restores its relationship rows in place. Mirrors `entity.md` section 3.3.1 lifecycle semantics.

#### 3.3.2 Inbound relationships (declared by source-side specs)

`test_spec` is the **target** of one anticipated relationship kind from the sibling `requirement` spec:

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `requirement_verified_by_test_spec` (declared by `requirement.md`) | `requirement` | `test_spec` | references-entity edge | many-to-many | A requirement is verified by one or more test specs; a test spec typically verifies one requirement but may verify several. The edge is registered from the requirement side per the source-first naming convention (DEC-048) and the once-per-kind registration rule (CLAUDE.md line 48). |

**This spec does NOT register the inverse edge.** Per the once-per-kind rule, each `relationship_kind` value appears exactly once across all source-side specs' `REFERENCE_RELATIONSHIPS` registrations. The `requirement_verified_by_test_spec` kind is registered by `requirement.md`; this spec lists it here as inbound informational, not as something the test_spec side declares.

The test_spec detail-pane `ReferencesSection` renders the inbound `requirement_verified_by_test_spec` references the same way it renders outbound edges — the widget treats inbound and outbound symmetrically and surfaces both whenever the relationships exist.

#### 3.3.3 Cross-spec relationship-kind naming — adopted, not established

This spec adopts the `{source}_{verb}_{target}` relationship-kind naming convention established by `domain.md` (DEC-048) and applied throughout the v0.4 workstream. All three outbound kinds (`test_spec_touches_entity`, `test_spec_touches_field`, `test_spec_exercises_process`) conform to the source-first pattern. The convention is not re-decided here.

#### 3.3.4 Hierarchy

`test_spec` does not use the self-referential parent-child hierarchy pattern. Test specs are flat; the closest hierarchical pattern (test suites composed of test specs) is a v0.6+ candidate, not a v0.5+ shape. If subsequent CBM-redo signal indicates that suites are a high-value organizing primitive, a `test_suite` entity type with a `test_spec_belongs_to_suite` references edge is the most likely shape, leaving `test_spec` itself unchanged.

### 3.4 Lifecycle

#### 3.4.1 Methodology status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `candidate` | CRM Builder has proposed; awaiting client / methodology-team verification. **Default starter status.** | (none — starter) | `confirmed`, `deferred` |
| `confirmed` | The test spec is verified as in-scope for the engagement's verification phase. | `candidate`, `deferred` | `deferred` |
| `deferred` | The test spec is acknowledged as a real verification need but is out of current engagement scope. | `candidate`, `confirmed` | `confirmed` |

The structure mirrors `domain.md` and `entity.md` exactly. The propose-verify gate (one-way, no regression to `candidate`) carries forward per DEC-047. Movement between `confirmed` and `deferred` in either direction is permitted to support mid-engagement scope changes.

#### 3.4.2 Execution-outcome values

| Outcome value | Description | Valid predecessors | Valid successors |
|---------------|-------------|--------------------|------------------|
| `not_run` | The test spec has not yet been executed. **Default starter outcome.** | any | any |
| `passing` | The most recent execution passed. | any | any |
| `failing` | The most recent execution failed. | any | any |
| `skipped` | The most recent execution was skipped (e.g., feature not yet deployed, dependency blocked). | any | any |

**Transitions are unrestricted across all four values.** Outcomes are observational — they record what happened on the last run, not a decision about what should be true. A test that was `passing` yesterday and `failing` today, or `failing` last week and `passing` after a fix, transitions freely. The same flexibility applies to `not_run`: an outcome may be reset to `not_run` (e.g., when a test spec is materially revised and prior runs no longer apply).

The asymmetry with the methodology status field — restricted transitions vs unrestricted transitions — is itself the point of the dual-axis separation. The methodology field is decisional and benefits from a propose-verify gate; the execution field is observational and benefits from frictionless update.

#### 3.4.3 Why dual-axis state — justification for separating methodology from execution

The naive shape would collapse outcome into the status enum: `candidate` / `confirmed` / `deferred` / `passing` / `failing` / `skipped` as one field. The justification for splitting them into two fields:

1. **Different lifecycles.** A test spec's methodology status describes whether the test belongs in the engagement (a methodology-team decision); its outcome describes what happened on the last run (an observation about a deploy). The two move on independent cadences — a `confirmed` test spec may go from `passing` to `failing` to `passing` across iterations without its methodology status changing, and a `deferred` test spec may still be executed periodically with the outcome recorded against future re-confirmation.

2. **Different transition semantics.** Methodology status uses a one-way propose-verify gate (DEC-047 pattern); execution outcome uses unrestricted transitions. Collapsing both into one enum would force one set of transition rules to govern both — either too restrictive for outcomes (a `failing` test couldn't naturally go to `passing` after a fix because that's not a valid transition under propose-verify semantics) or too permissive for methodology status (the propose-verify gate would be lost).

3. **Different rendering needs.** Methodology status is best rendered as a plain enum label in the master pane (consistent with `domain`, `entity`, etc.). Execution outcome benefits from a color cue (passing green, failing red, etc.) that makes verification health legible at a glance — see section 3.6.2.

4. **Different ownership.** Methodology status is set by the consultant / methodology team during scope discussions. Execution outcome is set by whoever ran the test most recently (potentially an operator, automation in a future release, etc.). Keeping them as separate fields makes the ownership story clean and supports future role-based edit affordances if needed.

5. **Pattern reuse.** The separation matches the methodology-vs-execution principle that runs throughout v2's storage layer (e.g., the apply-event / deposit-event distinction in governance, where the methodology object describes intent and the deposit records what happened). Establishing the same shape for `test_spec` makes the methodology/execution distinction a v0.5+ schema convention candidate for any future verification-like entity.

The cost of dual-axis state is one extra column (`test_spec_last_run_outcome`) plus its two companions (`test_spec_last_run_at`, `test_spec_last_run_notes`). The value is clean separation of concerns and a UI that can surface verification health without collapsing methodology and execution information.

#### 3.4.4 Cross-field invariant — `last_run_at` populated whenever outcome is a run state

Whenever `test_spec_last_run_outcome` is one of `passing`, `failing`, `skipped`, the `test_spec_last_run_at` field must be populated. The server enforces this at the access layer:

- POST / PUT / PATCH that move outcome to a run state without supplying `last_run_at` causes the server to set `last_run_at` to the current UTC timestamp.
- POST / PUT / PATCH that move outcome to `not_run` clears `last_run_at` to null (regardless of whether the client supplied a value).
- The invariant is checked on every write; manual PATCH attempts that violate it (e.g., setting outcome to `passing` while explicitly setting `last_run_at` to null) return HTTP 422.

`test_spec_last_run_notes` is unconstrained; it may be populated or null in any outcome state.

#### 3.4.5 Rejection via soft-delete

When the methodology team rejects a candidate test spec, the rejection is handled by soft-delete rather than a `rejected` status value, matching `domain.md` section 3.4.3's cross-spec principle: status values track engagement-scope lifecycle; soft-delete tracks existence-in-the-record.

#### 3.4.6 Soft-delete semantics

Soft-delete inherits v2's standard behavior: DELETE sets `test_spec_deleted_at`; soft-deleted records do not appear in `GET /test-specs` by default; `?include_deleted=true` toggles them on; `POST /test-specs/{id}/restore` clears the timestamp; restore on a record that is not soft-deleted returns HTTP 422.

Outgoing references on a soft-deleted test_spec are NOT cascade-deleted. They persist in the references table; show-deleted toggles on either side surface them. Matches `entity.md` section 3.4.6.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/test-specs` | — | List endpoint. Returns active records by default. Supports `?include_deleted=true`. |
| GET | `/test-specs/{test_spec_identifier}` | — | Single fetch by identifier. Returns 404 if not found. |
| POST | `/test-specs` | full record minus `test_spec_identifier` (server-assigned) | Create. Returns 201 with the assigned identifier in the response body. Server-side validation per section 3.2; cross-field invariant per section 3.4.4 applied. |
| PUT | `/test-specs/{test_spec_identifier}` | full record | Full replace. `test_spec_identifier` in body must match the path; mismatch returns 422. |
| PATCH | `/test-specs/{test_spec_identifier}` | partial record | Partial update. Status-transition validation applied (3.5.3); cross-field invariant on outcome / last_run_at applied (3.4.4). |
| DELETE | `/test-specs/{test_spec_identifier}` | — | Soft-delete; sets `test_spec_deleted_at`. Idempotent. |
| POST | `/test-specs/{test_spec_identifier}/restore` | — | Clears `test_spec_deleted_at`. Returns 422 if not soft-deleted. |
| GET | `/test-specs/next-identifier` | — | Returns `{"next": "TST-NNN"}` for the next available identifier per DEC-043. |

**No surface deviations from the cross-spec default endpoint set in the initial release.** No bulk operations, no webhooks, no event streams.

A `POST /test-specs/{id}/record-run` convenience endpoint — atomic update of `last_run_outcome`, `last_run_at`, and `last_run_notes` from a single small request body — is an open question for the v0.5 build conversation (see section 3.8.1). The PATCH endpoint already supports this in three-field form; the convenience endpoint would just be a thinner shape that's easier to call from automation. Either decision is consistent with the schema.

#### 3.5.2 Identifier auto-assignment

`test_spec_identifier` is server-assigned on POST when omitted per PI-002. The assignment uses the SAVEPOINT-retry helper that is safe under concurrent writes (per the PI-002 implementation across all prefixed-identifier entities). The `GET /test-specs/next-identifier` helper exposes the same logic for clients that prefer read-then-write.

#### 3.5.3 Status-transition validation (methodology lifecycle)

PATCH or PUT requests that specify a `test_spec_status` value that is not a valid successor of the current value (per section 3.4.1) return HTTP 422 with a body of the form:

```
{
  "error": "invalid_status_transition",
  "from": "<current status>",
  "to": "<requested status>"
}
```

The default-`candidate` rule applies on POST: if `test_spec_status` is omitted, the server assigns `candidate`. POST with `test_spec_status` explicitly set to a non-starter value is permitted (bulk-importing already-confirmed test specs from prior engagement records).

Execution-outcome transitions are unrestricted per section 3.4.2 — the server does not reject any outcome → outcome transition. The only outcome-side server-enforced rule is the cross-field `last_run_at` invariant in section 3.4.4.

#### 3.5.4 Decomposed reference handling

Relationships to requirement / entity / field / process records are NOT inlined into the test_spec create or update bodies. To attach a relationship, the client makes a separate `POST /references` per edge with the appropriate `source_type`, `source_id`, `target_type`, `target_id`, `relationship_kind`. The convention matches `entity.md` section 3.5.4 and the v2 references-first discipline (DEC-006). The New dialog and detail-pane "Add reference" affordance hide the multi-call sequence behind a single user gesture, but the API stays decomposed.

#### 3.5.5 Other endpoint specifics

- All endpoints return JSON wrapped in the v2 `{data, meta, errors}` envelope per the CLAUDE.md convention.
- 4xx error responses use the existing v2 error shape (some pass through FastAPI's standard error envelope per `crmbuilder-v2/src/crmbuilder_v2/api/errors.py`).
- No additional list query parameters beyond `?include_deleted=true` in the initial release. A `?last_run_outcome=failing` filter is a natural extension under CBM-redo signal (section 3.8.2).

### 3.6 UI Considerations

This spec adopts the spec guide's default `ListDetailPanel` layout with one rationale-justified deviation: the master-pane Last Run column renders with a color cue (passing green, failing red, not_run gray, skipped amber) rather than as a plain enum label. Justification is captured in section 3.6.2.

#### 3.6.1 Sidebar

`test_spec` joins the existing "Methodology" sidebar group below the v0.4 entries. Position within the group reflects PI-004 sibling ordering: after `requirement`, alongside `field` / `persona` / `manual_config`. The composite order (subject to the v0.5+ build planning conversation's final ordering choice):

1. Domains (`domain.md`, v0.4)
2. Entities (`entity.md`, v0.4)
3. Fields (`field.md`, PI-004 sibling)
4. Processes (`process.md`, v0.4)
5. Personas (`persona.md`, PI-004 sibling per PI-003)
6. Requirements (`requirement.md`, PI-004 sibling)
7. **Test Specs (this spec)**
8. Manual Config (`manual_config.md`, PI-004 sibling)
9. CRM Candidates (`crm_candidate.md`, v0.4)

The v0.5+ build conversation finalizes the ordering across all PI-004 entries.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with **five** columns (one more than the v0.4 entity panels' four-column default):

| Stored field | Display header | Width | Notes |
|--------------|----------------|-------|-------|
| `test_spec_identifier` | Identifier | narrow | Default sort key, ascending |
| `test_spec_name` | Name | wide | Short name of the test |
| `test_spec_status` | Status | narrow | Methodology lifecycle enum value rendered as-is |
| `test_spec_last_run_outcome` | Last Run | narrow | Execution-outcome enum value rendered with color cue (see deviation rationale below) |
| `test_spec_updated_at` | Updated | narrow | Localized date/time |

Right-click context menu offers New / Edit / Delete / Restore, consistent with v0.3 governance-entity panels per DEC-035 and DEC-036.

**Deviation rationale — color-cued Last Run column.** The v0.4 entity panels render status as a plain enum-label string. The test_spec panel's Last Run column instead renders the four execution outcomes with a color cue: `passing` shown in green, `failing` shown in red, `not_run` shown in gray, `skipped` shown in amber. The label text itself is also shown (color is additive, not replacement); both visual channels reinforce the value. The deviation is justified because the operational value of scanning verification health at the master pane is materially different from scanning methodology lifecycle: verification health changes on each run, drives immediate action (fix the failing tests), and is the primary information consultants want at a glance from the Test Specs panel. The Status column retains the plain-enum rendering to keep methodology-lifecycle reading consistent across all methodology panels; the Last Run column owns the color cue exclusively. Implementation note for the v0.5+ build conversation: the color cue is driven by a small render function on the master-pane view-model; no new column-rendering infrastructure is needed beyond a per-cell stylesheet hook.

#### 3.6.3 Detail pane

Vertical layout, organized into three sections to handle the larger field set cleanly:

**Identity and methodology block:**

1. `test_spec_identifier` — read-only label
2. `test_spec_name` — single-line text editor
3. `test_spec_description` — multi-line text editor with placeholder "What does this test verify?"
4. `test_spec_status` — combo box with the three methodology enum values

**Test body block** (subsection header "Test body"):

5. `test_spec_setup` — multi-line text editor with placeholder "Preconditions — what must be true before the test runs?"
6. `test_spec_steps` — multi-line text editor with placeholder "Numbered steps to execute the test"
7. `test_spec_expected` — multi-line text editor with placeholder "Expected results — what must be true after the steps execute?"

**Last run block** (subsection header "Last run"):

8. `test_spec_last_run_outcome` — combo box with the four outcome values
9. `test_spec_last_run_at` — datetime picker, populated automatically when outcome moves to a run state; clearable to null (which also forces outcome back to `not_run`)
10. `test_spec_last_run_notes` — multi-line text editor

**Internal notes block** (collapsible under "Internal notes" section header, collapsed by default):

11. `test_spec_notes` — multi-line text editor

**References section:**

12. `ReferencesSection` widget — renders both outgoing references (`test_spec_touches_entity`, `test_spec_touches_field`, `test_spec_exercises_process`) and the inbound `requirement_verified_by_test_spec` reference from the requirement spec. The widget exposes the existing "Add reference" affordance for attaching new relationships after the test spec exists.

The three-section grouping of body fields (setup / steps / expected) makes the verification-spec structure legible at a glance; collapsing internal notes by default matches the cross-spec consultant-scratchpad treatment from `domain.md` and `entity.md`.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `test_spec_identifier` not shown in create mode (server-assigned).
- `test_spec_status` defaults to `candidate`; user may select a different starter value if importing established records.
- `test_spec_last_run_outcome` defaults to `not_run`; user may select a different starter value if importing test specs with prior run history.
- `test_spec_last_run_at` is shown but disabled unless outcome is set to a run state; auto-populates with the current UTC timestamp the moment the user picks `passing` / `failing` / `skipped`, and is then editable.
- Required-field validation client-side before submit.
- Server-side validation errors (uniqueness, format, transition, cross-field invariant) surface inline.

#### 3.6.5 Edit dialog

Same shape as create. `test_spec_identifier` displayed as read-only label. Methodology status transitions enforced per section 3.4.1. Outcome transitions unrestricted; the `last_run_at` field shows the same auto-populate behavior on outcome change. Changing outcome back to `not_run` confirms with the user before clearing `last_run_at` and `last_run_notes`.

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `test_spec_identifier` value (e.g., `TST-002`) to enable the Delete button, matching v0.3 governance-entity patterns. Outgoing and inbound references on the soft-deleted test spec persist per section 3.4.6.

### 3.7 Acceptance Criteria

The following 16 statements define what "this entity type is correctly implemented at first release" looks like. Each is concrete and testable; the v0.5+ build-planning conversation translates these into specific test cases.

1. **Schema migration applies cleanly with both status fields.** Alembic migration creates the `test_specs` table with all twelve columns (`test_spec_identifier`, `test_spec_name`, `test_spec_description`, `test_spec_setup`, `test_spec_steps`, `test_spec_expected`, `test_spec_notes`, `test_spec_status`, `test_spec_last_run_outcome`, `test_spec_last_run_at`, `test_spec_last_run_notes`, plus the three inherited timestamp columns `test_spec_created_at`, `test_spec_updated_at`, `test_spec_deleted_at` — fifteen total when timestamps are counted), correct types and constraints, and runs both forward and backward without error.

2. **`test_spec_identifier` format constraint enforced.** Insertions with `test_spec_identifier` not matching `^TST-\d{3}$` raise a validation error at the access layer. Malformed POST → 422; colliding POST → 409.

3. **`test_spec_name` uniqueness enforced case-insensitively.** Inserting a second row whose `test_spec_name` matches an existing row by lowercase comparison raises a uniqueness violation.

4. **`test_spec_status` enum and transition validation (methodology lifecycle).** Insertions with `test_spec_status` outside `{candidate, confirmed, deferred}` are rejected. PATCH/PUT requesting an invalid transition (e.g., `confirmed` → `candidate`) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

5. **`test_spec_last_run_outcome` enum and unrestricted transitions.** Insertions with `test_spec_last_run_outcome` outside `{not_run, passing, failing, skipped}` are rejected. PATCH/PUT with any outcome → outcome transition (including `passing` → `failing`, `failing` → `not_run`, `not_run` → `skipped`, etc.) succeeds.

6. **Cross-field invariant — `last_run_at` set when outcome is a run state.** PATCH or POST that moves `test_spec_last_run_outcome` to `passing` / `failing` / `skipped` without supplying `test_spec_last_run_at` causes the server to set `last_run_at` to the current UTC timestamp. PATCH that explicitly sets `last_run_at` to null while outcome is in a run state returns 422. PATCH that moves outcome to `not_run` clears `last_run_at` regardless of any value the client supplies.

7. **Access-layer methods exist with expected signatures.** `client.list_test_specs()`, `client.get_test_spec(identifier)`, `client.create_test_spec(...)`, `client.update_test_spec(identifier, ...)`, `client.patch_test_spec(identifier, ...)`, `client.delete_test_spec(identifier)`, `client.restore_test_spec(identifier)`, `client.next_test_spec_identifier()` exist and pass unit tests covering happy path and at least one error case each.

8. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and `{data, meta, errors}` envelope-wrapped JSON bodies for happy-path and validation-failure cases.

9. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /test-specs/next-identifier` returns `{"next": "TST-NNN"}` for the next available number. POST with `test_spec_identifier` omitted assigns the same value via the PI-002 SAVEPOINT-retry helper. Two concurrent POSTs do not assign the same identifier.

10. **Soft-delete and restore round-trip correctly.** DELETE sets `test_spec_deleted_at`; the record disappears from `GET /test-specs`. `GET /test-specs?include_deleted=true` shows it. POST `/restore` clears the timestamp; the record reappears in the default list. Restore on a record that is not soft-deleted returns 422.

11. **`Test Specs` sidebar entry appears under the Methodology group, at the v0.5+ build-determined position within the PI-004 sibling ordering.** Section 3.6.1's proposed ordering serves as the working position pending build-planning finalization.

12. **Master pane columns and color-cued Last Run.** The Test Specs panel shows the five columns Identifier / Name / Status / Last Run / Updated, sorted by Identifier ascending. The Last Run column renders `passing` green, `failing` red, `not_run` gray, `skipped` amber. Right-click context menu offers New / Edit / Delete / Restore.

13. **Detail pane renders all fields in the section-3.6.3 grouped order.** Identity-and-methodology block (Identifier read-only, Name, Description, Status), Test body block (Setup, Steps, Expected), Last run block (Outcome, Run At, Run Notes), collapsible Internal notes block (Notes), ReferencesSection — all present, correctly grouped under their subsection headers, and bound to the correct fields.

14. **CRUD dialogs work end to end including the `last_run_at` auto-populate behavior.** Create assigns identifier server-side, persists all fields, surfaces server-side validation errors inline. Edit persists field changes including methodology status transitions and outcome transitions. Changing outcome to a run state in the dialog auto-populates `last_run_at` with the current UTC timestamp and unlocks the datetime picker for further editing. Changing outcome to `not_run` confirms with the user before clearing `last_run_at` and `last_run_notes`. Delete prompts for edge-text confirmation and soft-deletes on confirm. Restore reappears the record.

15. **References-section round-tripping for all four relationship kinds.** POST `/references` with `(test_spec, entity, test_spec_touches_entity)`, `(test_spec, field, test_spec_touches_field)`, and `(test_spec, process, test_spec_exercises_process)` succeed and are rendered in the test spec's `ReferencesSection`. Inbound `(requirement, test_spec, requirement_verified_by_test_spec)` references created from the requirement side render symmetrically in the test spec's `ReferencesSection` as inbound. Each kind appears in `REFERENCE_RELATIONSHIPS` and is constrained correctly in `_kinds_for_pair`; the Alembic CHECK-constraint extension covers all three new outbound kinds. (The inbound kind is registered by the requirement spec, not this spec.)

16. **Sample CBM-redo verification authoring through the UI.** A consultant / verification operator can author roughly 10 test_spec records covering the MR / MN / FU / CR domain test surface (e.g., "Mentor application form submission produces confirmation email", "Dues 0.00 sets Mentor Status to Active without Dues", "Fundraising contribution above threshold triggers thank-you workflow", etc.), attach `test_spec_touches_entity` / `test_spec_touches_field` / `test_spec_exercises_process` references to the appropriate authored records, attach inbound `requirement_verified_by_test_spec` references from authored `requirement` records, transition methodology status from `candidate` to `confirmed`, record execution outcomes after running each test against the deployed instance, and the records and references persist correctly across application restart and across REST/MCP refetch.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For v0.5 build to settle

**[v0.5 build] `POST /test-specs/{id}/record-run` convenience endpoint.** The PATCH endpoint already supports atomic update of `last_run_outcome`, `last_run_at`, and `last_run_notes`. A thinner convenience endpoint — `POST /test-specs/{id}/record-run` with body `{outcome, notes}` and server-set `last_run_at` — would be easier to call from automation and would surface a clearer intent than a generic PATCH. The trade-off is one more endpoint to maintain and document. The v0.5 build conversation decides whether to ship the convenience endpoint at first release, defer to a later release if automation pressure surfaces, or leave PATCH as the only path. The schema is consistent with any choice.

**[v0.5 build] Cross-spec consistency check on inbound vocabulary.** Once `requirement.md` lands as a sibling spec, the v0.5 build conversation's cross-spec consistency check verifies that the `requirement_verified_by_test_spec` kind name does not collide with any other vocab entry, and that the requirement-side registration aligns with this spec's section 3.3.2 anticipation. The expectation is no collision, but the check is the formal gate.

**[v0.5 build] Identifier prefix coordination across PI-004 siblings.** This spec adopts `TST`. The sibling specs adopt `FLD` (field), `PER` (persona), `REQ` (requirement), `MCF` (manual_config). The v0.5 build conversation's cross-spec consistency check validates that no collisions exist with the v0.4 prefix set (DOM, ENT, PROC, CRM) or with the governance-entity prefix set.

#### 3.8.2 For CBM redo to surface

**[CBM redo] Structured `test_spec_steps` shape.** Plain text in v0.5+. If the CBM-redo verification work surfaces that steps benefit from structured numbered substeps with per-step expected results (rather than free-text plus a single expected-results section), a v0.6+ schema migration introduces a `test_spec_steps` JSON column or a child `test_spec_step_items` table with `step_number`, `step_text`, `expected_result`. The decision deliberately waits on real-use signal — plain text is the cheap default and only worth complicating if operators actually want the structure.

**[CBM redo] Markdown for `test_spec_description` / `test_spec_setup` / `test_spec_steps` / `test_spec_expected`.** Plain text in v0.5+. Verification text may benefit from emphasis, bullet lists, inline links to entities or fields. Same posture as `domain` and `entity`: wait on real-use signal.

**[CBM redo] Server-side list filters.** Only `?include_deleted=true` is supported in the initial release. A `?last_run_outcome=failing` filter is the most operationally valuable extension (the "show me what's broken" view). `?test_spec_status=confirmed`, `?touches_entity=ENT-NNN`, and `?verified_by_requirement=REQ-NNN` are natural follow-ons. Most likely to bite for `test_spec` at moderate engagement scale, more than for any v0.4 methodology entity.

**[CBM redo] Text-field length caps.** No storage-level length constraints in v0.5+. If pathological inputs surface (5000-character "steps"), caps become a v0.6+ migration.

**[CBM redo] `test_spec_notes` structure.** Flat plain text in v0.5+. If consultant notes accrete substantially, a structured-journal pattern becomes a v0.6+ candidate.

**[CBM redo] Auto-`not_run`-on-edit behavior.** When a test spec's body content (setup, steps, expected) is materially edited, the prior `last_run_outcome` may no longer apply — the test now describes a different verification. Whether the system should auto-reset outcome to `not_run` on content edit, prompt the user, or leave it untouched is a real-use question. Default in the initial release is to leave it untouched; CBM-redo signal informs whether a more opinionated behavior is warranted.

#### 3.8.3 For v0.6+

**[v0.6+] PI — test-spec-to-test-run history.** New planning item authored at this conversation's close (working name "test_run history entity"). The initial release captures only the most recent run's outcome / timestamp / notes as snapshot fields on the test_spec row. A full execution history — every run with its outcome, timestamp, notes, who-ran-it, environment / instance pointer — is a separate `test_run` entity type with a `test_run_executes_test_spec` (or equivalently shaped) references edge or FK pointer. The history shape unlocks regression analysis (was this test passing last week and is now failing?), per-environment outcome tracking (passing on dev, failing on staging), and operator-attribution. Deferred from the initial release because the snapshot shape is sufficient for v0.5+ verification authoring and the history shape carries non-trivial additional design surface.

**[v0.6+] PI — automated test-spec execution / CRM Builder verification-engine integration.** New planning item authored at this conversation's close (working name "automated verification engine"). The initial release assumes test specs are executed manually by an operator who then records the outcome via the UI or PATCH. A verification engine that consumes test_spec records and executes them automatically against a deployed CRM instance — driving the configured CRM via API calls, capturing outcomes into the test_spec row (or into the v0.6+ test_run history entity), and reporting failures into a verification report — is a substantial v0.6+ workstream. The schema is consistent with such an engine: the engine becomes another writer of `test_spec_last_run_outcome` / `test_spec_last_run_at` / `test_spec_last_run_notes`, no schema change needed at the test_spec layer. The engine itself, however, is a much larger workstream.

**[v0.6+] PI — test suites as a grouping primitive.** A `test_suite` entity type with a `test_spec_belongs_to_suite` references edge or membership table. v0.5+'s flat list is sufficient for the CBM redo's verification count (roughly 20–80 test specs); larger engagements may benefit from suite-level grouping for "run all the dues tests" / "run all the mentor-application tests" / etc. Tracked separately because it leaves `test_spec` itself unchanged.

**[v0.6+] PI — outcome history sparkline in master pane.** Once the test-run history entity (preceding bullet) lands, the master-pane Last Run column could grow into a small sparkline showing the last N outcomes (e.g., last 10 runs as a row of green / red dots). Visual pattern-language for spotting flaky tests, regressions, etc. Tracked as a small UI follow-on to the test-run history PI.

**[v0.6+] PI — role-based outcome write affordance.** Once the methodology team grows roles (consultant authors test specs, operator records outcomes, automation runs tests), edit affordance on outcome vs methodology status can be split by role. Currently both fields are editable by anyone with edit rights to the test spec. Tracked as a small access-control follow-on under the same v0.6+ governance-roles workstream that absorbs related access-control questions.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against this conversation's close-out payload. Each is linked to its parent session via a `decided_in` reference recorded in the same payload. DEC numbers shift to the next-available values at payload-generation time per the parallel-sandbox identifier-collision contingency in CLAUDE.md.

- **DEC (TBD) — `test_spec` identifier prefix and format.** Adopts `TST` under the soft-3-letter posture per DEC-044. Reads unambiguously as "test"; no collision with any existing prefix.
- **DEC (TBD) — `test_spec` field inventory and dual-axis state.** Ten substantive fields plus inherited timestamps. Three plain-text body fields (`test_spec_setup`, `test_spec_steps`, `test_spec_expected`) rather than a collapsed `test_spec_body`. Dual-axis state separating methodology lifecycle (`test_spec_status`) from execution outcome (`test_spec_last_run_outcome`), justified in section 3.4.3. Cross-field invariant requiring `last_run_at` to be populated whenever outcome is a run state, server-enforced.
- **DEC (TBD) — `test_spec` methodology lifecycle.** Three-status methodology lifecycle mirroring `domain` and `entity` (`candidate` / `confirmed` / `deferred`, propose-verify gate per DEC-047). Execution outcome separately tracked with unrestricted transitions.
- **DEC (TBD) — `test_spec` outbound relationship mechanisms and vocabulary registration.** Three many-to-many outbound kinds via references entity: `test_spec_touches_entity`, `test_spec_touches_field`, `test_spec_exercises_process`. Inverse `requirement_verified_by_test_spec` declared by `requirement.md`, not registered here, per the once-per-kind rule (CLAUDE.md line 48). Alembic migration extends the `refs.relationship_kind` CHECK constraint to include the three new outbound values.
- **DEC (TBD) — `test_spec` API surface, UI defaults with one rationale-justified deviation, acceptance criteria.** Standard endpoint set with no surface deviation at first release. `POST /test-specs/{id}/record-run` convenience endpoint open question deferred to v0.5 build conversation. Default `ListDetailPanel` UI under the Methodology sidebar group at the PI-004-sibling-determined position. One UI deviation: master-pane Last Run column rendered with color cue (passing green, failing red, not_run gray, skipped amber). Three-section detail-pane grouping (identity-and-methodology / test body / last run) plus collapsible internal notes plus ReferencesSection. Sixteen testable acceptance criteria.

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry; documents the `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair` / Alembic-migration triad (line 48) and the once-per-kind registration rule that governs section 3.3.2's inbound treatment of `requirement_verified_by_test_spec`. Also documents the `{data, meta, errors}` envelope referenced in section 3.5.5.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — establishing predecessor; source of conventions inherited by this document (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture, status-lifecycle shape and propose-verify gate, rejection-via-soft-delete posture, no-archived posture).
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — worked example referenced throughout for the cross-entity references-discipline pattern, the three-or-four-column master pane defaults that this spec extends, and the inbound-relationship documentation pattern (section 3.3.2).
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` — target of the `test_spec_exercises_process` outbound relationship.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/field.md` (PI-004 sibling, in flight) — target of the `test_spec_touches_field` outbound relationship; provides the `FLD-NNN` identifier vocabulary.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/requirement.md` (PI-004 sibling, in flight) — source of the inbound `requirement_verified_by_test_spec` reference.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/persona.md`, `manual_config.md` (PI-004 siblings, in flight) — sibling specs sharing PI-004's resolution scope; relevant to sidebar ordering in section 3.6.1.

#### 3.9.3 Related prior decisions informing this spec

- **DEC-006** — Universal references table as the cross-entity-type edge store. Direct architectural foundation for the three outbound relationship mechanisms in section 3.3.1.
- **DEC-039** — Minimum entity inventory and multi-tenancy posture. Informs the thin-shape framing applied to `test_spec` (snapshot last-run rather than full history; manual execution rather than engine integration).
- **DEC-043** — SES-010 identifier-asymmetry resolution. Mandates the `GET /test-specs/next-identifier` helper endpoint cited in section 3.5.1.
- **DEC-046** — Parent-prefix field-naming convention for methodology entities. Establishes the field-naming pattern this spec inherits and applies (section 3.2).
- **DEC-047** — `domain` status lifecycle, propose-verify gate, and rejection-via-soft-delete posture. Establishes the methodology-lifecycle pattern this spec adopts unchanged for `test_spec_status` (section 3.4.1) — but explicitly diverges from for `test_spec_last_run_outcome`, with the dual-axis justification captured in section 3.4.3.
- **DEC-048** — `{source}_{verb}_{target}` relationship-kind naming convention. Applied in registering all three outbound kinds (section 3.3.1 and 3.3.3).

#### 3.9.4 Related planning items

- **PI-003** — `persona` entity type. PI-004 sibling per the v0.4 deferral; relevant to sidebar ordering and to the broader PI-004 resolution scope this spec is part of.
- **PI-004** — Additional methodology entity types for v0.5+ (field, requirement, manual_config, test_spec). This spec is part of PI-004's resolution scope. The four PI-004 siblings (this spec, `field`, `requirement`, `manual_config`) ship together as the PI-004 tranche.
- **PI-005** — Process schema growth beyond Phase 1 thin shape. Target of the `test_spec_exercises_process` outbound relationship; the relationship is registrable against the current `process` spec without modification and remains compatible with PI-005's planned schema growth.

#### 3.9.5 Predecessor and successor conversations

- **Predecessor specs:** The four v0.4 methodology specs (`domain.md`, `entity.md`, `process.md`, `crm_candidate.md`) plus `engagement.md` (v0.4.x extension). Conventions inherited as cited above.
- **Sibling specs (PI-004 tranche, in flight):** `field.md`, `persona.md`, `requirement.md`, `manual_config.md`. Cross-spec consistency check at the v0.5 build-planning conversation validates relationship-kind name uniqueness across the four siblings, prefix non-collision, and sidebar ordering.
- **Successor specs:** None within PI-004. The v0.6+ PIs surfaced in section 3.8.3 (test-run history entity, automated verification engine, test suites) are the natural extension points; each becomes its own design conversation when prioritized.

---

*End of document.*
