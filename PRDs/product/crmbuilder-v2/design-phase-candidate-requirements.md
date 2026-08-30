# Requirements-Phase Consolidation Ledger and Design-Phase Candidate Requirements

> **DISCUSSION DRAFT — NOT YET APPROVED.** Produced in SES-362 (2026-08-29) under PRJ-023 / PI-069 (REQ-404). Nothing in Part B has been written to the store; each candidate becomes a requirement record only after Doug rules on the two decisions in Part C. The word "V3" appears here only as Doug's working label and is not a term until approved (GVR-232).

| Field | Value |
|-------|-------|
| Version | 0.1 (draft) |
| Date | 2026-08-29 |
| Session | SES-362 |
| Governs | Nothing yet — a reviewable proposal |
| Companion | `specifications/master-crmbuilder-PRD.md` v0.5 (same session) |

## Purpose

Two jobs, in the order they must happen:

1. **Part A** — settle what the Master CRMBuilder PRD already subsumes of the *requirements gathering and definition* phases (Master PRD Phases 1, 1.5, 2, 3) and what each transitional document still carries, so the remaining content can be folded in and the documents retired (REQ-405 / PI-070).
2. **Part B** — the first candidate set of requirements for the *design phase*: the work between a confirmed inventory (the exit of Phase 3) and a canonical design that is approved and ready to publish. In the legacy 13-phase process this is Phases 4–8 (process definition, entity PRDs, service definition, domain reconciliation, stakeholder review). Phase 9 (generation) already has its own topic (TOP-101 YAML Publish & Validate) and is treated as the boundary, not part of the design phase.

The dividing line used throughout: **the requirements phase ends when every candidate has a terminal disposition and the confirmed inventories are queryable per domain** (Master PRD §8, Completion Criteria). **The design phase ends when a domain's design is approved as a version and passes the engine translation check.**

---

# Part A — Consolidation Ledger for the Requirements Phase

## A.1 What the store already holds

The database is the source of truth (GVR-238); documents are renders or, for the Master PRD, an authored process spec. The requirements-phase capability is already governed by these confirmed records:

| Home topic | Requirements | What they cover |
|---|---|---|
| TOP-066 Methodology Process & Master PRD | REQ-116, REQ-117 | Existing systems baselined into candidates with evidence (Phase 1.5); the methodology refines itself from dogfood |
| TOP-067 Consolidation & Format | REQ-404, REQ-405 | Author the remaining Master PRD phases (PI-069, Draft); mark documents consolidated (PI-070, Draft) |
| TOP-068 Methodology Process | REQ-410, REQ-411 | Session/conversation governance process; the standard process-definition process (PI-087, PI-088, Draft) |
| TOP-069 CRMBUILDER Dogfood Domain Inventory | REQ-408, REQ-409, REQ-413 | Domain overview + personas for the governance-recording domain; promote the Phase 2 candidate inventory (PI-085/086/095, Draft) |
| TOP-074 Engagement Setup & Client Inputs | REQ-406, REQ-407 | Storing client-provided inputs; engagement-level setup process (PI-071/072, Draft) |
| TOP-087 Requirements Capture, Documentation & Organization | REQ-108, REQ-148, REQ-243, REQ-249, REQ-251, REQ-345 | The provenance model: every requirement traces to a conversation, is organized under a topic, is confirmed only by an approving decision, and carries a drift flag |
| TOP-105 Source Instance Mapping Model | REQ-300–306, REQ-319, REQ-341 | Phase 3 Stream B tooling: human-gated mapping of audited objects into the canonical design |
| TOP-031 Methodology Entity Schema | REQ-120 (deferred) | Cross-domain services as first-class records — Phase 1 still carries services in charter text |

Six of the implementing planning items (PI-069, 070, 071, 072, 085–088, 095) are still **Draft**. The requirements phase is fully specified on paper and in the store; its remaining work is execution (dogfood Phases 2→3) and the unbuilt setup/promotion items.

## A.2 Document-by-document disposition

Status vocabulary: **Subsumed** — the Master PRD carries the content; the document can be marked consolidated once PI-070's mechanism exists. **Partly** — named residue remains. **Reference** — deliberately kept as a standalone reference (not consolidated). **Superseded** — content overtaken by V2; nothing to carry. **Pending** — content belongs to a Master PRD section not yet drafted.

| Source document | Scope covered | Master PRD home | Status | Residue / action |
|---|---|---|---|---|
| `PRDs/process/interviews/interview-master-prd.md` v1.4 | Phase 1 interview | §5 Phase 1, §6 mini-guide | **Partly** | Topic-by-topic question wording (Topics 1–7) and the transcript format are not inlined. Keep as question reference until the conduct decision (A.3, D-A) is made; then either inline the question set into §5 or retire in favour of the question library. |
| `PRDs/process/interviews/interview-domain-discovery.md` v1.1 | Phase 2 interview | §9 Phase 2 | **Subsumed** | "Multi-session discovery and saturation" is the one rule not in §9 — added to §9 in v0.5. "Handling discovered updates to the Master PRD" is the scope-change protocol (conduct charter §8). Retire. |
| `PRDs/process/interviews/interview-inventory-reconciliation.md` v1.2 | Phase 3 Stream A | §8 Phase 3 | **Subsumed** | "Implementations in flight — retrofit path" describes the legacy document-era CBM case and is obsolete under V2 (CBM restarts from Phase 1.5). "Master PRD update" is charter versioning. Retire. |
| `PRDs/product/features/feat-audit.md` v1.3 | Phase 1.5 discovery scope | §7 Phase 1.5 | **Reference** | Remains the engine feature spec for the Audit function (a V1 surface); only its discovery scope and not-auditable list were consolidated. Keep. |
| `PRDs/process/v2-user-process-guide.md` v0.1 | Whole process | §1–3 (orientation), §9–11 (Phases 1–3) | **Partly** | §4–8 (pre-engagement, kickoff, orientation, conduct, post-session capture) were **not** in the Master PRD — folded into new §11 in v0.5. §12–21 (Phases 4–13) are **Pending** Part IV/V. §22–24 (versioning, cross-references, rendering) are **Pending** the "V2 storage mechanics" section. Its MCP tool names and the `Status` object are stale against the current store and were not carried verbatim. |
| `PRDs/process/CRM-Builder-Document-Production-Process.docx` | Whole 13-phase process | §4 phase table, §5–9 | **Partly** | §3.1–3.3 subsumed. §3.4–3.13 **Pending** Part IV/V. §4 document language → GVR-200/201 (in the store). §5 identifier scheme → superseded by store-assigned identifiers (v0.3). §7 session protocol → §11. §10 scope-change protocol → conduct charter §8. Retire once Part IV lands. |
| `PRDs/process/conduct/charter.md`, `kickoff.md`, `question-library.md` | Conduct of every interview | Referenced from every phase | **Reference** | Open since v0.1: subsume or keep standalone (decision D-A below). They are methodology-agnostic and are referenced, not copied. |
| `PRDs/product/crmbuilder-v2/requirements-provenance-and-review-anchor.md` (2026-06-13) | How a requirement is captured, rooted, approved, reviewed, and kept true | **Was absent** | **Subsumed in v0.5** | The one requirements-*definition* source the Master PRD never carried. Its model is live in the store (REQ-108 family, TOP-087). Folded into new §10. Keep the anchor as the founding design record; §10 is the process view. |
| `PRDs/product/features/feat-prd-creation.md` v2.0 | V1 vision: in-app PRD interviews | — | **Superseded** | The V1 "Requirements tab" design. Its premise ("requirements first, configuration second") is the Master PRD's premise; the mechanics are replaced by V2 records + REQ-108. Mark superseded. |
| `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l1-PRD.docx` / `-l2-PRD.docx` | V2 strategic vision (structured DB, workflow engine, prompt generator, import processor, doc generator, impact analysis) | Part I orientation | **Superseded** (vision realised) | Every §6 capability now exists as store records and surfaces. Keep as historical; no process content to carry. Format rule already forbids editing the .docx. |
| `PRDs/process/research/evolved-methodology/*`, `iterative-methodology-research.md` | An alternative iterative (slice-based) methodology | — | **Reference** (not adopted) | Two of its principles are carried into Part B as candidates: *CRM Builder proposes, the client verifies* (DR-18) and *best-practice defaults fill everything outside scope* (DR-06). The slice/iteration shape itself is not adopted by this ledger — that is a methodology decision for Doug, outside this session. |
| `PRDs/process/interviews/authoring-standards.md`, `guide-carry-forward-updates.md` | Authoring/version-carry rules for the legacy documents | — | **To assess** | Not read this session; likely superseded by "documents are renders" (GVR-206). Assess in the PI-070 pass. |
| `PRDs/process/interviews/interview-process-definition.md` v2.7, `interview-entity-prd.md` v1.2, `guide-domain-overview.md` v1.1, `guide-domain-reconciliation.md`, `guide-service-reconciliation.md`, `interview-service-process-definition.md`, `guide-yaml-generation.md`, `guide-crm-evaluation.md` | Legacy Phases 4–13 | — | **Pending** Part IV/V | These are the *design-phase* sources. Their required-section standards (nine process sections, field-level detail standard, Entity PRD sections 1–10, Domain PRD structure) are the raw material for Part B and for drafting Part IV. |
| `PRDs/product/crmbuilder-v2/CRMBuilder-Phase-2-Candidate-Inventory.md` | Dogfood Phase 2 output | — | **Data** | Awaits promotion into records (PI-095). Not a spec. |

## A.3 What is now consolidated, and what remains for the requirements phase

Consolidated as of Master PRD v0.5: Phases 1, 1.5, 2, 3 (already), plus the two cross-phase mechanics that were missing — **§10 requirement capture and approval** and **§11 engagement setup and the session lifecycle**.

Remaining, in priority order:

1. **D-A (decision):** subsume the conduct documents into the Master PRD or keep them standalone. Until decided, `interview-master-prd.md` cannot be retired because its question set is only otherwise held in the question library.
2. **PI-070:** define the "consolidated" marker mechanism and apply it to the three Subsumed documents above.
3. **PI-072 / PI-071:** engagement setup records and client-input storage — §11 describes the process; the records it names are unbuilt.
4. **Dogfood execution of Phases 2→3** (the "next dogfood milestone" the v0.4 notes name) — the requirements phase is drafted but has run end-to-end only through Phase 1.

---

# Part B — Design-Phase Candidate Requirements

## B.1 What already exists (do not re-ask for it)

The store's *design model* is largely built. The design phase's job is to **populate and approve** it, not to define it:

- **Design record types in the store:** entity, field (+ field options), association (relationship), engine override, rule (dynamic logic), view, automation, dedup rule, message template, layout, role, team, filtered tab, field permission/visibility rule, manual config, test spec, process, service, persona, domain, artifact versions, design staleness.
- **Founding requirements (TOP-089):** the database is the engine-neutral design source of truth (REQ-139); adapters generate engine artifacts (REQ-140/141); every construct validates against two engines (REQ-142/143); records capture full design intent (REQ-144/145); design records are operable by AI agents through MCP (REQ-146); the model renders human-readable documents such as an Entity PRD (REQ-147); the field vocabulary describes any CRM without loss (REQ-501–516).
- **Versioning (DEC-482):** versions are per artifact, release-tied; live = latest shipped.
- **Downstream of the design:** publish/validate (TOP-101), three-way reconciliation (TOP-109/111), instance audit and conformance (TOP-091), source mapping (TOP-105).
- **Requirement tracing edges already in the vocabulary:** `requirement_scopes_to_domain`, `requirement_touches_entity`, `requirement_touches_field`, `requirement_realized_by_process`, `requirement_verified_by_test_spec`, `manual_config_realizes_requirement`.

So the gap is the **process and tooling that turns a confirmed inventory into an approved design**: step-level process definition, field elicitation grounded in process need, coherence and completeness gates, design renders for review, a recorded design sign-off, and change propagation.

## B.2 Candidate requirements

Each candidate is written to the store's readability gate (LSN-036: ≤75 words, ≤4 sentences, no identifiers in the description, acceptance criterion present). Identifiers here (**DR-nn**) are working labels for this document only; the store assigns `REQ-` identifiers on creation. "Existing coverage" names what the candidate builds on so the store does not get duplicates.

### Group 1 — From confirmed inventory to design (derivation)

**DR-01 — Design work starts only from a reconciled inventory.**
Description: A design element — a process step, a field, a relationship, a layout — is created only against a confirmed entity, persona, process, or requirement. Creating one against a candidate is refused, and a design element whose antecedent is later rejected is flagged for review.
Acceptance: Given a candidate entity, creating a field on it is refused with a message naming the missing confirmation. Given a confirmed entity later rejected, its fields appear in the drift queue.
Existing coverage: candidate/confirmed lifecycle; needs-review flag on requirements (REQ-249, REQ-345). Proposed topic: TOP-066 (new child topic proposed in Part C).

**DR-02 — Processes are defined at step level before their entities are detailed.**
Description: Each confirmed process is defined as an ordered set of steps with triggers, the persona acting at each step, decisions, alternative end states, and hand-offs to other processes or services. This happens before the entities the process uses receive their field detail, because the steps reveal which fields matter.
Acceptance: A process can be recorded with its steps, triggers, personas, end states, and hand-offs, and the store reports which processes in a domain still lack steps.
Existing coverage: process record (process-v2 spec: steps/triggers/outcomes fields exist at Phase 1 granularity); `process_hands_off_to_process`.

**DR-03 — Every process step names the data it reads and the data it writes.**
Description: For each step, the design records which entities the step creates, reads, or updates and, at field level, what it reads and what it writes. This is the field-level detail standard: type, required status (with condition where conditional), allowed values, and purpose in the step.
Acceptance: Given a step, the store lists its read set and write set by entity and field; a step with an empty write set on a "creates" entity is reported.
Existing coverage: none at step level; `requirement_touches_field` exists at requirement level.

**DR-04 — Every field traces to a need.**
Description: A field on a design entity exists because at least one process step reads or writes it, or a confirmed requirement calls for it. A field with no consumer is not an error but is listed for review so cruft does not enter the design unnoticed.
Acceptance: A report lists every field in a domain with no step and no requirement referencing it.
Existing coverage: `requirement_touches_field`; baseline utilization evidence (Phase 1.5) as a second signal.

**DR-05 — System requirements stated during process definition become requirement records.**
Description: When a stakeholder says what the system must do during a process conversation, that statement is captured as a requirement under the process's domain topic, rooted in that conversation, and linked as realized by the process. Nothing said is lost to a document section.
Acceptance: A "the system must" statement made in a process session exists as a requirement traceable to that conversation and linked to that process.
Existing coverage: REQ-108 model; `requirement_realized_by_process` edge.

**DR-06 — Best-practice defaults fill what the stakeholder did not specify, and say so.**
Description: Where the stakeholder gave no guidance — a layout, a default value, a label, a permission — the design is completed from a best-practice default rather than left blank or asked about. Each defaulted value is marked as defaulted so a reviewer can distinguish it from a stated choice.
Acceptance: A design element can carry a "defaulted" origin; the review render lists defaulted elements separately from stated ones.
Existing coverage: none; principle taken from the evolved-methodology research (Principle 6). Requires a value-origin attribute on design records.

**DR-07 — Cross-domain services are designed alongside domains.**
Description: A shared capability used by several domains — messaging, calendar, notes, surveys — is designed as a service with the entities it owns and the capabilities it offers. A domain process that consumes a service names the capability it uses, and a consumed capability that does not exist is reported.
Acceptance: A process can reference a service capability; the store lists consumed capabilities no service provides.
Existing coverage: `service` entity type exists in the vocabulary; REQ-120 (services as first-class records) is **deferred** — DR-07 depends on it being reactivated.

**DR-08 — Kept and transformed baseline objects seed the design.**
Description: An entity or field the client kept or transformed at triage enters the design already shaped by its mapping and migration record, so design work on it starts from what the client has, not from a blank record. The design element carries the mapping so the migration plan and the design never diverge.
Acceptance: Given a kept baseline field, the design field shows its source mapping; changing the design field's type raises the mapping's staleness signal.
Existing coverage: migration mappings (Phase 3 Stream B); source mapping model (REQ-300–306, staleness REQ-304).

### Group 2 — Coherence and completeness (the reconciliation gate)

**DR-09 — Inconsistent definitions of one thing become findings.**
Description: When two processes, or a process and a baseline, define the same field or relationship differently — different types, different allowed values, different required rules — the contradiction is recorded as a finding and resolved by a decision. A domain's design does not reach review while a blocking finding is open.
Acceptance: Given two steps that write different allowed-value lists for one field, a finding exists naming both; the review gate reports it as blocking until resolved.
Existing coverage: `finding` entity and `finding_resolved_by` → decision (delivery layer, DEC-400); Master PRD §8 already reuses it for methodology conflicts.

**DR-10 — A completeness check reports what a domain's design still lacks.**
Description: On demand, the system reports for a domain: processes without steps, entities used by a step but lacking fields, personas that act in no process, confirmed requirements realized by nothing and not declined, and services consumed but undefined. The report is machine-readable and repeatable so it can gate review.
Acceptance: Running the check twice on an unchanged domain gives identical output; each gap names the record it concerns.
Existing coverage: coverage-gaps report for requirements (provenance anchor); conformance-run shape (REQ-492/493) as the pattern.

**DR-11 — The design is checked against the target engine before review.**
Description: Before a domain's design goes to stakeholders, the adapter translation runs and names every construct the target CRM cannot hold and what will be done about it — carried as manual configuration, degraded, or dropped. Stakeholders review a design that is known to be deployable, with its limits stated.
Acceptance: The translation report for a domain lists zero unrecognized constructs, and every unholdable construct has a named disposition.
Existing coverage: REQ-142/143 (two-engine validation), REQ-502 (translation names what the target cannot hold), REQ-489 (deliberately-not-applied vs missing).

### Group 3 — Renders, stakeholder review, and approval

**DR-12 — Design documents render from records.**
Description: A domain overview, a process document, an entity definition, and a consolidated domain document are generated from the design records in business language, without product names. A render is disposable; a change requested on a render is applied to the records and the document is regenerated.
Acceptance: Each of the four documents renders for a domain, and a field changed in the store appears changed in the next render without hand editing.
Existing coverage: REQ-147 (Entity PRD render); GVR-200 (no product names); GVR-206 (renders, not authored copies). Extends REQ-147 to three more documents.

**DR-13 — Stakeholder feedback lands in the records, not in the document.**
Description: A stakeholder's review comments on a rendered design document are captured as proposed changes against the records they concern, each resolved by acceptance, decline, or change with a recorded reason. The document is then re-rendered. No edit is made to a rendered file.
Acceptance: A review comment exists as a record linked to the field or step it concerns and to the decision that resolved it.
Existing coverage: decision records; finding entity as a possible carrier. Requires a review-comment or change-request record.

**DR-14 — A domain's design is approved as a recorded sign-off on a version.**
Description: Stakeholder approval of a domain's design is a recorded attestation — who, when, and against which version of which records — not an annotation on a document. Only an approved design version can be published, and later changes create a new version that needs its own approval.
Acceptance: Given an unapproved design version, publish is refused; given an approved one, the instance's design-version stamp names it after publish.
Existing coverage: DEC-482 versioning; review sign-offs for requirements (TOP-087, `review_signoffs`); REQ-495 design-version stamp on instances.

### Group 4 — Change and impact after design

**DR-15 — A change upstream flags the design elements that depend on it.**
Description: When a confirmed requirement, process, or entity changes after design has begun, every design element derived from it is flagged for re-review, and an approved design version containing a flagged element is reported as stale. The flag clears only by a recorded review.
Acceptance: Changing a process step's write set flags the fields it writes; the domain's approved version is listed as stale until each flag is cleared.
Existing coverage: living drift on requirements (REQ-249, REQ-345); `design_staleness` mechanism exists for mappings. Extends both to design elements.

**DR-16 — Impact is answerable from any record in either direction.**
Description: From any design element a reader can see what depends on it downstream — steps, layouts, roles, published instances — and what it depends on upstream — requirements, processes, conversations. The answer is a query over stored references, not a reconstruction.
Acceptance: Given a field, the system lists the steps that use it, the requirements that call for it, the layouts it sits on, and the instances where it is published.
Existing coverage: universal references table; the spine `defined → decided → specified → planned → developed → verified`. Requires the design edges from DR-03/04 to exist.

**DR-17 — Discoveries during design follow the scope-change protocol.**
Description: A new entity, field, process, or domain discovered during design is captured as a candidate with its provenance and the decision that admitted or declined it. Nothing enters the design silently, and the requirements phase's rules for candidates apply unchanged.
Acceptance: A field first mentioned in a design session exists as a candidate rooted in that conversation and is not usable by a step until confirmed.
Existing coverage: conduct charter §8 (scope-change protocol); candidate lifecycle; DR-01.

### Group 5 — Conduct of design sessions

**DR-18 — The system proposes the design; the stakeholder verifies it.**
Description: From the confirmed inventory, the processes, and the baseline, the AI proposes each domain's design — steps, fields, relationships, layouts — and the stakeholder confirms, corrects, or declines each proposal. A proposed element is distinguishable from a confirmed one until the stakeholder has spoken to it.
Acceptance: Design elements carry a proposed/confirmed state; a review render separates the two; a proposed element cannot be included in an approved version.
Existing coverage: candidate/confirmed lifecycle on methodology records; conduct charter §11.6.b (inferences require positive support) bounds what may be proposed. Principle from the evolved-methodology research (Principle 4).

**DR-19 — A design session's context is assembled from records, not uploaded documents.**
Description: A process-definition or entity-definition conversation opens with its context drawn from the store — the domain, its personas, the confirmed inventory, prior processes in the domain, and the relevant baseline evidence — assembled by the system. The consultant no longer gathers and uploads documents to seed a session.
Acceptance: Opening a design session for a process produces a context bundle naming the domain, personas, entities, prior steps, and baseline items it drew, with no file upload step.
Existing coverage: session/conversation model; MCP design-record operations (REQ-146); reference libraries (TOP-073) as an additional source.

**DR-20 — One process per conversation, in dependency order within a domain.**
Description: Each design conversation covers one process, and a domain's processes are worked in dependency order — lifecycle processes that create and transition records before the asynchronous processes that react to them. The system proposes the order from recorded hand-offs and lets the consultant override it with a reason.
Acceptance: A domain shows a proposed process order derived from hand-off edges; a conversation bound to two processes is refused.
Existing coverage: one-topic-per-conversation rule (provenance anchor); `process_hands_off_to_process`; legacy DPP §3.4 "Process Order".

## B.3 Coverage map: legacy Phases 4–8 → candidates

| Legacy phase | Legacy artifact | Candidates that replace it |
|---|---|---|
| 4 Domain Overview + Process Definition | Domain Overview doc; nine-section process doc; field-level detail standard | DR-02, DR-03, DR-05, DR-19, DR-20 (process); DR-12 (overview render) |
| 5 Entity PRDs | Entity PRD sections 1–10 | DR-01, DR-04, DR-06, DR-08, DR-12 (entity render) |
| 6 Cross-Domain Service Definition | Service process docs; Service PRD | DR-07 |
| 7 Domain Reconciliation | Domain PRD synthesis; contradictions as exceptions | DR-09, DR-10, DR-11, DR-12 (domain render) |
| 8 Stakeholder Review | Approved Domain PRDs; cross-domain conflict detection | DR-13, DR-14, DR-15, DR-16, DR-17, DR-18 |
| 9 YAML Generation (boundary) | YAML programs | Not in scope here — TOP-101 |

---

# Part C — Decisions for Doug

Presented one at a time in the session; listed here so the document is self-contained.

**D-1 — The term "V3", and the name of this phase.** The store has no "V3" anywhere; "design" is already a defined concept (the engine-neutral design, TOP-089). Options: (a) approve "V3" as the label for the next product major version, with the design phase as its headline capability — record a decision defining it; (b) do not coin "V3"; name this work "Design phase (Master PRD Part IV)" and let releases carry version numbers as they do today; (c) approve "V3" as the *phase* name. Recommendation: **(b)** — it introduces no new term, and "V3" as a phase name would collide with the per-artifact version numbering in DEC-482 ("Contact v3").

**D-2 — Scope boundary of the design phase.** Options: (a) legacy Phases 4–8, ending at an approved design version with the engine translation check as the exit gate (this document's assumption); (b) Phases 4–9, including generation/publish. Recommendation: **(a)** — publish already has its own topic and requirement set (TOP-101, TOP-091, TOP-109), and DR-11/DR-14 give the phase a clean hand-off.

**D-3 — Write the candidates to the store now, or after review.** Options: (a) create the twenty as candidate requirements now under a new child topic of TOP-066, each rooted in SES-362's conversation, so review happens in the Requirements Review panel; (b) review this document first, then create only the survivors. Recommendation: **(a)** once D-1 and D-2 are settled — the store's review surface is the governed path, and candidates that are declined are recorded, not deleted. Until then this document is the record.

**D-A (carried from Master PRD v0.1) — Conduct documents: subsume or keep standalone.** Blocks retiring `interview-master-prd.md`. Recommendation: keep standalone and referenced; they are methodology-agnostic and would bloat the Master PRD.

## Proposed topic placement (if D-3(a))

- New child topic under TOP-066: **"Design Phase — from confirmed inventory to approved design"** (name subject to approval), holding DR-01 – DR-20.
- DR-07 also `is_about` TOP-031 (services); DR-11 also `is_about` TOP-089; DR-14 also `is_about` TOP-101.
