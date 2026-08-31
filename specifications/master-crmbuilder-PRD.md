# Master CRMBuilder PRD

> **DISCUSSION DRAFT — NOT YET APPROVED.** This file is an authored proposal that has not been reviewed or approved. Every substantive structural and content choice is open for discussion. Treat this as a working artifact to react to, not a canonical specification.

| Field | Value |
|-------|-------|
| Version | 0.6 (draft) |
| Last Updated | 08-31-26 |
| Status | Phase 1 drafted, executed against the CRMBuilder dogfood, refined (v0.3). Phase 1.5 drafted (v0.2), built, and validated against the CBM test instance. Phase 2 drafted (v0.3). Phase 3 fully drafted (v0.4: interview reconciliation + the v0.2 baseline triage as two streams of one phase). Cross-phase mechanics added (v0.5: requirement capture and approval; engagement setup and the session lifecycle). Phases 4–8 placeholder with candidate requirements drafted. Phase 11 (CRM Deployment) drafted and executed live (v0.6, four deploy runs, DEC-956); Phases 12–13 drafted against the built publish/verification capability; Phase 9 subsumed into Phase 12; Phase 10 placeholder. |
| Audience | Anyone running the CRMBuilder process for a client engagement (consultant, AI session, or future maintainer) |
| Governs | The entire process for using the V2 storage system to capture the complete definition of a product, from initial requirements through deployed functional application |
| Does not govern | Detailed V2 internals beyond what Phase 1 needs (schema, API, MCP, UI surfaces have their own component PRDs referenced here as they're consolidated in) |

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-26-26 | Initial draft. Orientation, two-layer mental model, phase sequence overview, Phase 1 (Business Context Capture) spec, the "what to do first" mini-guide for Phase 1. All other phases listed as placeholders to be drafted iteratively as the engagement reaches each one. |
| 0.2 | 06-11-26 | Added Phase 1.5 (Existing System Baseline) — the Audit function repurposed as a requirements input: existing systems are audited and data-profiled into *candidate* methodology records with provenance and utilization evidence. Added the Phase 3 baseline-triage section (keep / transform / drop dispositions, migration mapping capture, baseline-vs-interview conflict reconciliation); the remainder of Phase 3 stays placeholder. |
| 0.3 | 06-12-26 | Phase 1 refined from its first dogfood execution (SES-166 against CRMBuilder, PI-160): tier respecced to process level, store-assigned identifiers replace legacy code schemes, cross-domain services carried transitionally in charter scope (service entity type is PI-161), new Capture Mechanics subsection (lifecycle status at capture, charter occupancy, product-venture interview variant). Phase 2 (Domain Discovery) drafted to runnable: per-domain SME discovery into candidate records, with the Phase 1.5 Baseline Report integrated as the post-unprompted-account probe queue and a no-confirmation rule (reconciliation is Phase 3's job). Phase 1.5 validated against the CBM test instance on 06-12-26 (first live run). |
| 0.4 | 06-12-26 | Phase 3 completed as a two-stream phase: new Stream A (interview reconciliation — cross-domain dedup, cross-stream matching against baseline candidates before any disposition, persona reconciliation, conflict resolution, evidence-led confirmation session) joins the v0.2 baseline triage as Stream B, under whole-phase completion criteria (every candidate terminal, no duplicate confirmed records, no silent conflict absorption). Stream B's two stale v0.2 notes updated: the `rejected` lifecycle state and the migration-mapping record type now exist (built by the Existing System Baseline project), and methodology-layer conflicts reuse the live `finding` record. |
| 0.6 | 08-31-26 | Delivery phases drafted after being executed for real (SES-363/PRJ-111): new Part V — The Delivery Phases. Phase 11 (CRM Deployment) specified from the shipped admin-driven deployment capability (REQ-522) and its four-run live proof (DEC-956): deploy runs as resumable service-owned background jobs, keep-and-report failure (DEC-945), the production-host boundary (DEC-946). Phase 12 (CRM Configuration) drafted against the built publish/reconcile pipeline; Phase 13 (Verification and Handover) drafted against the three built verification surfaces. Phase 9 (YAML Generation) recorded as subsumed — generation is an internal publish step, not an operator phase. Former Part V (Iterative Drafting) renumbered Part VI. |
| 0.5 | 08-29-26 | Requirements-phase consolidation pass (SES-362, PI-069). New Part III — Cross-Phase Mechanics: §10 *Requirement Capture and Approval* (the provenance-and-review model from `requirements-provenance-and-review-anchor.md`, live in the store as the REQ-108 family, previously absent from this PRD) and §11 *Engagement Setup and the Session Lifecycle* (from the V2 user process guide §4–8, rewritten against the current store). Phase 2 gains the multi-session saturation rule from the domain-discovery guide. New Part IV placeholder for the design phases (4–8) pointing at the candidate requirement set in `PRDs/product/crmbuilder-v2/design-phase-candidate-requirements.md`; that document also carries the document-by-document consolidation ledger for the requirements phase. Former Part III (Iterative Drafting) renumbered Part V. |

---

# Part I — Orientation

## 1. What This PRD Is

The Master CRMBuilder PRD is a process-definition document. It specifies how the V2 storage system is used to capture user input, requirements, processes, entities, personas, and decisions — the entire definition of a product — from first interview through deployed application.

This PRD is the canonical source of truth for CRMBuilder's process. Where the existing methodology documents (the 13-phase Document Production Process, the interview and guide documents in `PRDs/process/interviews/`, the conduct documents in `PRDs/process/conduct/`, the V2 user process guide) conflict with this PRD, this PRD wins. Existing documents remain available as reference until their content is fully subsumed; each carries a transitional status header pointing here as the future authority.

This PRD is L3 — it names V2 specifically and references concrete surfaces (SQLite, REST API, MCP, PySide6 desktop UI). Client-facing artifacts generated from V2 records remain product-name-neutral per the L1/L2 rule; this PRD is internal.

## 2. The Client Concept

Every engagement that uses this process is a *client* of the process. The product being defined varies by client. The process itself is constant across clients.

- **First client: CRMBuilder (dogfood).** CRMBuilder uses its own process to define itself. The product being defined is CRMBuilder as a software product; its V2 database holds CRMBuilder's own governance content (decisions, planning items, sessions, work tickets) and, as the process runs, its methodology content (domains, entities, processes, personas, requirements).
- **Second client: Cleveland Business Mentors (validation).** CBM is a nonprofit organization whose CRM-shaped system will be defined and deployed using this process. The CBM engagement is the validation case: does running this process produce a deployable system that matches and exceeds the prior document-driven approach. CBM begins after the process is sufficiently defined on CRMBuilder.

## 3. The Two-Layer Mental Model

An engagement has two layers, and the consultant works in both.

**Governance layer** — the project-management layer. Methodology-agnostic; would look essentially the same for any consulting engagement that benefits from this kind of tracking. Governance objects in V2: Charter, Status, Decisions, Sessions, planning items, topics, risks, references, conversations, work tickets, reference books, close-out payloads, deposit events.

**Methodology layer** — the CRMBuilder layer. Engine-agnostic at the requirements level; engine-specific only at the deployment end. Methodology objects in V2: domains, cross-domain services, entities, fields, processes, process steps, personas, requirements, manual-config items, test specifications.

The two layers connect through the universal references table. They do not merge. A Decision (governance) can reference an Entity (methodology). A Session (governance) can reference a Process (methodology). The Charter (governance) names the domains that are in scope without itself becoming a domain definition.

Layer test:

> *If you swap clients but keep the methodology, what changes? That's governance.*
> *If you swap methodology but keep the client, what changes? That's methodology.*

A second test, especially useful for distinguishing the engagement Charter from the captured business content:

> *The Charter describes the project building the thing.*
> *The captured business content describes the thing being built.*

For one engagement you will have one Charter and one accumulated set of methodology content (personas, domains, processes, entities, fields, etc.).

---

# Part II — The V2 Process Guide

The process is sequenced across phases. Each phase has a defined purpose, input, captured records, output, and completion criterion. Phases are run iteratively per engagement, in order, with refinement loops back to earlier phases as later phases surface gaps.

## 4. Phase Sequence Overview

| Phase | Name | Status in this PRD |
|-------|------|---------------------|
| 1 | Business Context Capture | **Drafted, executed, refined** (v0.1 → dogfood SES-166 → v0.3) |
| 1.5 | Existing System Baseline | **Drafted** (v0.2), **validated live** against the CBM test instance 06-12-26 — conditional; runs only when the client has one or more existing systems |
| 2 | Domain Discovery | **Drafted** (v0.3) |
| 3 | Inventory Reconciliation | **Drafted** (v0.4) — Stream A interview reconciliation + Stream B baseline triage (v0.2) as one phase |
| 4 | Domain Overview and Process Definition | Placeholder — **design phase**; candidate requirements drafted (Part IV) |
| 5 | Entity PRDs | Placeholder — design phase (Part IV) |
| 6 | Cross-Domain Service Definition | Placeholder — design phase (Part IV) |
| 7 | Domain Reconciliation | Placeholder — design phase (Part IV) |
| 8 | Stakeholder Review | Placeholder — design phase (Part IV) |
| 9 | YAML Generation | **Subsumed into Phase 12** (v0.6) — program generation happens inside publish, not as an operator phase |
| 10 | CRM Selection | Placeholder |
| 11 | CRM Deployment | **Drafted and executed live** (v0.6) — capability shipped and proven by a four-run live proof (DEC-956) |
| 12 | CRM Configuration | **Drafted** (v0.6) against the built publish/reconcile capability |
| 13 | Verification | **Drafted** (v0.6) against the built verification surfaces |

Phase numbering, ordering, and naming may evolve based on gaps discovered during execution. The phase set above mirrors the existing 13-phase Document Production Process as a starting point.

## 5. Phase 1 — Business Context Capture

### Purpose

Capture the foundational business context of the client: what the organization does, who it serves, the personas involved, the key business domains, the processes those domains contain, the cross-domain services needed, and the scope boundary of the engagement.

### Inputs

- An initialized V2 engagement record for the client (for CRMBuilder dogfood, the CRMBUILDER engagement already exists)
- The client's available stakeholders (typically administrator-as-proxy first, then domain SMEs in later phases)
- Any prior artifacts (org charts, mission statements, existing systems, prior consulting engagements)

### Conduct Rules

- Global interview conduct rules: `PRDs/process/conduct/charter.md` (transitional reference until subsumed by this PRD)
- Pre-session kickoff protocol: `PRDs/process/conduct/kickoff.md` (transitional reference)
- Question patterns by intent: `PRDs/process/conduct/question-library.md` (transitional reference)

### Phase-Specific Rules

- **Business language only.** No product names, no implementation technologies. Integration needs are described by function ("bulk email communication") not by product.
- **Identifiers assigned during the conversation.** All methodology records use their store-assigned identifiers (`PER-NNN`, `DOM-NNN`, `PROC-NNN`). The legacy two-letter domain codes (`MN`, `MR`, etc.) and `{DOMAIN}-{PROCESS}` process codes are optional informal short names, recordable in the record's name or notes — they are not schema fields (v0.3, dogfood finding). Confirm each human-readable name at assignment; identifiers are permanent once assigned and never discussed with the stakeholder.
- **No entity field-level detail.** The Phase 1 capture does not define entities, fields, or data structures. Entity-level detail comes in Phase 5.
- **Don't over-engineer.** Resist proposing data structures or field definitions during the interview.
- **Watch for scope discoveries.** If the administrator describes something that doesn't fit any domain being discussed, flag it immediately rather than force-fitting. New domains can be added; better to discover now than during Phase 2.

### Activity

The consultant conducts an interview with the client following the conduct charter and kickoff protocol. Topics covered:

1. **Organization overview** — mission, operating context, why a CRM is needed.
2. **Personas** — for each: responsibilities, what the CRM provides them, primary domains.
3. **Key business domains** — for each: purpose, personas involved, processes (one-line description + tier), key data categories.
4. **Cross-domain services** — for each: name, purpose, capabilities, any entities it may own.
5. **System scope** — in scope, out of scope, key integrations described by function.
6. **Implementation tier definitions** — Core, Important, Enhancement, Out of Scope; process tier table.
7. **Processing order** — which domain first, sequencing of processes within domains.

### Captured V2 Records

As the interview proceeds, records are written to V2 in real time (via MCP-connected session, desktop UI, or post-session close-out, depending on operating mode):

| What is captured | V2 record type | Layer | Notes |
|---|---|---|---|
| Strategic vision (mission, why a CRM) | Charter (versioned) | Governance | Charter's `mission`, `objectives`, `scope` fields populated |
| Personas | Persona records | Methodology | Each with identifier, responsibilities, primary domains (`persona_scopes_to_domain` edges) |
| Domains | Domain records | Methodology | Each with purpose and description. **Tier lives at process level, not on domains** (v0.3): the schema carries no domain tier, and the dogfood showed tiering misfits domains that are sequential lifecycle stages. A domain-level tier ruling, when one is made (e.g. "everything is launch-core"), is recorded as a Decision |
| Processes (high-level) | Process records | Methodology | Each with name, purpose, and mandatory parent domain; tier via `process_classification` (mission_critical / supporting / deferred) |
| Cross-domain services | *Transitional:* charter scope text | Methodology | The service entity type does not exist yet (PI-161). Until it lands, capture each service's name and one-line purpose in the charter's scope section; backfill service records when the type ships |
| Scope determinations | Decision records (`DEC-NNN`) | Governance | Each with rationale |
| Deferred work | Planning Item records (`PI-NNN`) | Governance | Each with `item_type: pending_work` |
| Conceptual relationships | Reference records (`REF-NNNN`) | Governance | Universal references table |
| The interview itself | Session record (`SES-NNN`) | Governance | `topics_covered` opens with verbatim seed prompt |

### Capture Mechanics (v0.3, codified from the first dogfood run)

- **Lifecycle status at capture.** Interview-captured methodology records are created at `candidate` status as they emerge in conversation, and transitioned to `confirmed` after the stakeholder approves the end-of-session read-back (conduct charter §6.3). A record the read-back skipped or the stakeholder questioned stays `candidate`.
- **The engagement charter is THE charter.** `PUT /charter` versions are a single line: whatever charter content existed before Phase 1 (e.g., a build-project charter from earlier work) is superseded by the Phase 1 version and remains recoverable in version history. There is no second charter slot; the two-layer test's "project building the thing" content lives in the *new* version's framing, not in a parallel record.
- **Product-venture variant.** When the client is a product or venture rather than an operating organization (the dogfood case): Topic 1's "describe your organization" becomes "describe the venture — what it does, who it's for, and where it is in its life"; and when the domains that emerge are *sequential lifecycle stages* of one journey, do not ask the stakeholder to tier them against each other — ask the launch-scope question instead ("does the whole pipeline need to be working software, or are there stages you'd do by hand at first?") and record the answer as a Decision.
- **Validated as-is:** process records require their parent domain at creation; the store enforces it and the interview flow supports it naturally.

### Output

Phase 1 is complete when the V2 database holds, for the engagement:

- A Charter at version ≥ 1 naming mission, objectives, and engagement scope
- A complete set of Persona records for the scope
- A complete set of Domain records with two-letter codes
- High-level Process records under each Domain (one per identified process)
- Cross-Domain Service records for shared platform capabilities
- Decision records for every scope determination
- A Session record for the interview, status `Complete`, with a close-out payload applied

A rendered Master PRD document artifact may be generated from these records via the rendering pipeline. Until the rendering pipeline exists, the records themselves are the canonical output and the document is generated ad-hoc or deferred.

### Completion Criteria

- Charter exists at version ≥ 1
- Every persona is attached to at least one domain
- Every domain has at least one process (placeholder process records are acceptable; they are refined in Phase 4)
- Every cross-domain service has a name and purpose captured (in charter scope text until the service entity type lands — PI-161)
- The Session record's status is `Complete` and the close-out payload has been applied
- The consultant (or Doug, for CRMBuilder dogfood) has signed off on Phase 1

## 6. The "What to Do First" Mini-Guide for Phase 1

For someone running Phase 1 for the first time:

1. **Read this PRD.** Orientation (Part I), Phase 1 spec (§5), this mini-guide (§6), then the transitional conduct charter and kickoff protocol at `PRDs/process/conduct/`.
2. **Confirm the engagement exists in V2.** For CRMBuilder dogfood, the CRMBUILDER engagement already exists. For a new client, an engagement record must be created first (mechanics to be documented in a subsequent draft).
3. **Pre-session preparation.** Gather prior artifacts, stakeholder map, organizational context. See `PRDs/process/conduct/kickoff.md` §1 (Internal checklist).
4. **Open a Session record in V2** with identifier `SES-NNN`, `conversation_reference` noting this is Phase 1 against the client, and `topics_covered` opening with the verbatim seed prompt for this session.
5. **Apply the kickoff protocol.** Frame what the session does, set stakeholder expectations, calibrate communication style.
6. **Conduct the interview** topic by topic (Activity, §5), applying conduct charter rules throughout.
7. **Capture records as you go.** Decisions as `DEC-NNN`, deferred work as `PI-NNN`, conceptual relationships as `REF-NNNN`, Charter writes via the versioned-replace API, and Persona/Domain/Process/Service creates via their respective endpoints.
8. **Close the session.** Author the close-out payload, draft the apply prompt, commit and push from the session sandbox per the working conventions.
9. **Verify completion criteria** (§5, Completion Criteria) before declaring Phase 1 done and proceeding to Phase 2.

## 7. Phase 1.5 — Existing System Baseline

### Purpose

Capture the client's existing system(s) — a live CRM, spreadsheets, or other operational data stores — as **candidate** methodology records in V2, each carrying provenance and utilization evidence. The existing system is treated as a *witness to requirements*, not a template: its configuration is evidence of what the organization once needed and its data is evidence of what the organization actually uses. The phase produces the candidate baseline graph and a rendered Baseline Report consumed by Phase 2 (Domain Discovery) and Phase 3 (triage).

Phase 1.5 is **conditional**: it runs only when the client has at least one existing system to audit. If no baseline source exists, the phase is skipped and a Decision record states that explicitly, so downstream phases know the absence is deliberate rather than an omission.

Phase 1.5 is **mechanical**: it is automated capture, not an interview. No stakeholder session is required to run it, and no keep/drop judgments are made in this phase. All judgment is deferred to Phase 3 triage.

### Inputs

- Phase 1 complete (the domain vocabulary and Charter scope exist; triage and discovery cannot organize baseline output without them)
- Read-only access to each existing system. For an EspoCRM source this is an instance profile with `role: source` per the Audit feature (`PRDs/product/features/feat-audit.md`, transitional reference until subsumed). For other sources (spreadsheets, other CRM products), a source adapter — see Known Limitations below
- The Audit function (schema discovery) and the data profiler

### Phase-Specific Rules

- **Candidates never auto-confirm.** Every record produced by this phase enters at `candidate` status. Only Phase 3 triage, with the stakeholder, promotes a candidate to `confirmed`. The moment audited configuration auto-confirms, the process is rebuilding the old system with new tooling — the opposite of its purpose.
- **Provenance is mandatory.** Each audit run deposits its records through a `deposit_event` whose `wrote_record` edges point at every candidate created, and whose `apply_context` carries the source system, instance identity, and snapshot timestamp. Every candidate must be answerable to "where did this come from, and as of when."
- **Evidence travels with the candidate.** Each candidate carries the utilization evidence that makes triage decidable: field population rate, last-populated date, actual enum value distribution vs. declared options, record counts and recency for entities, standard-vs-custom catalog classification. *Travels with* is a transport property, not a storage design — evidence arrives together with the candidate wherever the candidate is read; storage is the `utilization_evidence` child table per the candidate-lifecycle schema spec (this wording was flagged as ambiguous by reconciliation finding FND-001; do not read it as requiring inline-on-candidate storage).
- **Anchoring discipline.** Baseline output is withheld from the stakeholder during Phase 2 discovery until their unprompted account of each domain has been captured. Baseline candidates are then introduced as probes ("you didn't mention X, but your current system tracks it — tell me about that"), never as the opening frame. Showing stakeholders their old system first biases discovery toward reproducing it.
- **One deposit event per source system.** A client with multiple existing systems gets one audit run and one deposit event per source, so provenance stays unambiguous.
- **Business-language rule applies to renders, not records.** The candidate records and the Baseline Report may name the source product (they are internal working artifacts); client-facing documents generated later remain product-name-neutral per the L1/L2 rule.

### Activity

1. **Connect and audit schema.** Run the Audit function against each source: custom entities, custom fields, fields added to native entities, relationships, layouts, roles, teams, filtered tabs, and the items with no API write path (saved views, duplicate-check rules, workflows).
2. **Profile the data.** For each discovered entity and field: record counts, creation recency, per-field population rate, actual enum value usage, dormant entities. Schema shows what was built; data shows what is used.
3. **Normalize through the catalog.** Map each discovered field to the engine-agnostic field type vocabulary and partition every item as *standard* (part of the source product's stock schema) or *custom* (added for this client). Custom items are concentrated requirements signal — someone paid to add them; standard items are signal only where the data profile shows real use.
4. **Deposit candidates into V2.** Write candidate methodology records (table below) with evidence inline, linked by a `deposit_event` with `wrote_record` provenance edges.
5. **Render the Baseline Report.** A generated document grouping candidates by best-guess domain, showing the standard/custom partition, the utilization findings, and a headline **gaps-and-ghosts list**: items the system has that nobody may want anymore (low population, dormant), and structural oddities (workflows referencing deleted fields, empty roles). This report is working input to Phases 2 and 3 — analogous to the Domain Discovery Report, but machine-produced.

### Captured V2 Records

| What is captured | V2 record type | Layer | Status at capture | Notes |
|---|---|---|---|---|
| Discovered entities | Entity records (`ENT-NNN`) | Methodology | `candidate` | With kind, description from source labels, utilization evidence |
| Discovered fields | Field records (`FLD-NNN`) | Methodology | `candidate` | Mapped to engine-agnostic types; `field_belongs_to_entity` edges; population evidence |
| Roles / teams | Persona records (`PER-NNN`) | Methodology | `candidate` | Source roles and teams are persona *evidence*, not personas — confirmed or merged against Phase 1 personas in triage |
| Workflows / filtered tabs | Process records (`PROC-NNN`) | Methodology | `candidate` (classification `unclassified`) | Automation is process evidence; named for what it does, in business language where derivable |
| Saved views, duplicate rules, workflows, role permissions | Manual-config records (`MCF-NNN`) | Methodology | `candidate` | Items in categories with no API write path on the eventual target |
| The audit run itself | Deposit event | Governance | — (born-terminal) | `wrote_record` edges to every candidate; `apply_context` = source identity + snapshot timestamp |
| Anomalies needing follow-up | Planning Item records (`PI-NNN`) | Governance | per PI lifecycle | e.g., unauditable items, NOT_AUDITABLE advisories |
| The run record | Session record (`SES-NNN`) | Governance | `complete` | Medium per how the run was driven; no stakeholder attendance required |

### Output

- The candidate baseline graph in V2 (entities, fields, personas, processes, manual-config items), every record carrying provenance and evidence
- The rendered Baseline Report per source system, including the gaps-and-ghosts list
- A Decision record if the phase was skipped (no baseline source exists)

### Completion Criteria

- Every discovered custom entity and custom field has a candidate record with utilization evidence attached
- Every candidate is reachable from its source's deposit event via `wrote_record`
- The Baseline Report renders without unexplained gaps (anything unauditable is logged as a Planning Item, not silently dropped)
- **No candidate has been confirmed** — confirmation is exclusively a Phase 3 triage outcome; a Phase 1.5 run that confirmed anything is a process violation
- The consultant has reviewed the gaps-and-ghosts list and flagged the items to be raised as probes in Phase 2

### Known Limitations (v0.2)

- The audit → V2 deposit path is not yet built. The Audit function currently emits YAML program files and V1 client-database rows; the transform from `AuditReport` to candidate methodology records plus deposit-event provenance is new work.
- The data profiler (population rates, recency, value distributions) is not yet built.
- EspoCRM is the only source adapter. The spreadsheet adapter (CSV/Sheet profiler proposing entity/field candidates) is the planned second source, since for small organizations the "existing system" is most often a spreadsheet.
- Provenance reference kinds (e.g., a dedicated `observed_in` relationship) may be added to the vocabulary; until then `wrote_record` from the deposit event is the provenance trail.

## 8. Phase 3 — Inventory Reconciliation

### Purpose

Reconcile everything proposed so far into the engagement's confirmed inventories. Phase 3 is the confirmation gate at the end of the discovery front half: Phase 2's per-domain interview candidates and Phase 1.5's baseline candidates converge here, and every candidate leaves at a terminal disposition — `confirmed` into the inventory, `rejected` with recorded rationale, or `deferred`. Nothing downstream (process definition, entity PRDs, generation) builds on an unreconciled candidate.

Phase 3 runs as **two streams in one phase**: Stream A reconciles the interview-derived candidates; Stream B is the baseline triage (drafted at v0.2, below). When the client had no existing system, Stream B does not apply.

### Inputs

- Phase 2 complete for every in-scope domain: candidate entities, personas, and processes with domain edges, plus the logged conflict queue
- When Phase 1.5 ran: the baseline candidates with utilization evidence, the Baseline Report, and Phase 2's recorded probe reactions
- Phase 1's confirmed frame (charter, domains, personas)

### Stream A — Interview Reconciliation

1. **Cross-domain deduplication.** The same real-world thing discovered under different names in different domains ("member" in one session, "mentor" in another) merges into one record. Each merge is a Decision; where two shapes genuinely coexist, the `entity_variant_of_entity` edge records the relationship instead.
2. **Cross-stream matching (when Phase 1.5 ran).** Before any disposition, match interview candidates against baseline candidates by name and meaning. A match merges into a single record carrying both kinds of support — the SME's language *and* the utilization evidence. Dispositions then happen once per real-world thing, in Stream B's disposition vocabulary, with both streams' evidence in hand.
3. **Persona reconciliation.** New Phase 2 persona candidates reconcile against the Phase 1 set (usually merges into it). Where a persona is itself tracked as data, the `persona_realized_as_entity` edge records it.
4. **Conflict resolution.** Work the queue Phase 2 logged through the scope-change protocol. Every conflict resolves by a Decision, or becomes a Planning Item when it needs research the session can't do.
5. **Confirmation session.** Evidence-led walk of the reconciled inventory with the stakeholder (administrator-as-proxy acceptable): confirm, reject, or defer each candidate. The conduct charter's triage rules below (lead with evidence, no default dispositions) apply to this walk identically.

### Captured V2 Records (Stream A)

| What is captured | V2 record type | Notes |
|---|---|---|
| Confirmations | `candidate → confirmed` transitions | The inventory is the set of confirmed records, queryable per domain |
| Rejections / deferrals | `candidate → rejected` / `deferred` transitions + Decision per rejection | The `rejected` terminal state exists in the lifecycle (built by PRJ-022) |
| Merges and variants | Surviving record + `entity_variant_of_entity` edges + Decisions | Merged-away candidates are rejected with the merge Decision as rationale |
| Persona realizations | `persona_realized_as_entity` edges | |
| Conflict resolutions | Decision records (or Planning Items) | One per queued conflict — none absorbed silently |
| The reconciliation session(s) | Session + conversation records | Per the session lifecycle |

### Completion Criteria (whole phase, both streams)

- Every candidate from every stream is at a terminal disposition — no record remains at `candidate` when Phase 3 closes
- No two confirmed records name the same real-world thing (every merge recorded as a Decision)
- Every queued conflict is resolved by a Decision or carried as an explicit Planning Item
- Every keep/transform disposition in Stream B has its migration mapping recorded
- The confirmed inventories are queryable per domain: entities and personas with domain edges, processes with classifications

### Stream B — Baseline Triage (drafted v0.2)

Give every Phase 1.5 baseline candidate a deliberate, stakeholder-confirmed disposition, so the confirmed inventory reflects decisions rather than inheritance. Triage is where the old system's gravity is broken: nothing carries forward by default, and nothing is dropped silently.

### Dispositions

Every baseline candidate receives exactly one terminal disposition:

| Disposition | Meaning | V2 effect | Migration consequence |
|---|---|---|---|
| **Keep** | Carried forward as-is | `candidate → confirmed`, unchanged | Migration mapping recorded: source → target, direct |
| **Transform** | The need is real but the shape changes | New confirmed record in the target shape; variant/supersession edge to the baseline candidate (e.g., `entity_variant_of_entity`); baseline candidate closed | Migration mapping recorded: source → target with transform rules |
| **Drop** | Deliberately not carried forward | Candidate moved to its rejected/deferred terminal state, with the rationale captured as a Decision record | None; the Decision is the durable answer to "where did this go?" |

The disposition vocabulary is the consultant's frame; the stakeholder hears plain questions ("keep this as it is, change it, or let it go?").

### Conduct Rules for Triage

Triage is a different interview type from elicitation: the material already exists, and the job is *judgment*, not discovery. In addition to the global conduct charter:

- **Lead with evidence, not with the item.** "This field is on 87% of your contacts" and "this field hasn't been filled in since 2024" are different conversations. The data profile decides which question to ask; never present a list of field names and ask "which do you want?"
- **Work the gaps-and-ghosts list explicitly.** Items the system has that the stakeholder never mentioned in Phase 2 are either forgotten requirements or cruft — the stakeholder says which. Items the stakeholder asked for that the system lacks are unmet needs (often the reason for replacement) and become new candidate requirements, not triage items.
- **Conflicts are reconciliation items, not awkward moments.** When the baseline and the interview disagree — "you said you don't track referral sources, but the system shows the field populated weekly" — record the conflict, resolve it with the stakeholder, and capture the resolution as a Decision. Neither source of truth wins by default.
- **No default dispositions.** The consultant never proposes "keep" as the path of least resistance. An unconsidered keep is how old-system cruft becomes new-system requirements. Where the evidence strongly suggests a disposition, say so and say why — but the stakeholder decides.
- **Batch by domain.** Triage sessions are organized per domain (using Phase 1 domain assignments and the Baseline Report grouping), not as one undifferentiated pass over the whole system. Cross-domain items (shared fields, global roles) are triaged in a dedicated closing pass.
- **Identifier discipline.** Dispositions reference candidates by their V2 identifiers (`ENT-NNN`, `FLD-NNN`); human-readable names lead in conversation per the global identifier rules.

### Migration Mapping

Every *keep* and *transform* creates a data-migration obligation, recorded at triage time while the knowledge is fresh and the stakeholder is present: source entity/field → target entity/field, plus transform rules for transforms (type changes, value mappings for enums, merges, splits). These mappings are the input to migration planning and eventually compile into executable migration via the data-import machinery. A keep/transform without a recorded mapping is incomplete triage.

> Mechanics (updated v0.4): the migration-mapping record type **exists** — built by the Existing System Baseline project and served at `/migration-mappings` — so mappings are recorded directly at triage time. (The v0.2 draft flagged this as a pending schema decision; it has since shipped.)

### Captured V2 Records (Triage)

| What is captured | V2 record type | Layer | Notes |
|---|---|---|---|
| Keep dispositions | Status transition `candidate → confirmed` on the baseline record | Methodology | Evidence and provenance ride along unchanged |
| Transform dispositions | New confirmed record + variant/supersession edge + closure of the baseline candidate | Methodology | The Decision explains the shape change |
| Drop dispositions | Terminal status on the candidate + Decision record (`DEC-NNN`) with rationale | Both | Drops are governed removals, never silent |
| Baseline-vs-interview conflicts | Reconciliation record + resolving Decision | Governance | See vocabulary note below |
| Migration mappings | Migration-mapping records (pending schema) | Methodology | One per keep/transform |
| The triage session(s) | Session records (`SES-NNN`) | Governance | One per domain batch, per the session lifecycle |

> Vocabulary note (updated v0.4): the delivery layer's `finding` record (type `conflict`, with resolution methods and the `finding_resolved_by` → Decision edge) is live and proven in use. Methodology-layer baseline-vs-interview conflicts reuse it — one vocabulary for "two sources disagree" across the framework. A finding raised in Phase 2/3 resolves by Decision exactly as a reconciliation finding does in delivery.

### Completion Criteria (Triage Section)

- Every baseline candidate from every Phase 1.5 source has exactly one terminal disposition
- Every keep and transform has a migration mapping recorded
- Every drop has a Decision record with rationale
- Every baseline-vs-interview conflict raised during triage is resolved by a Decision, or carried as an explicit Planning Item
- No baseline candidate remains at `candidate` status when Phase 3 closes

## 9. Phase 2 — Domain Discovery

### Purpose

Deepen each in-scope domain from Phase 1's sketch into a discovered candidate model: the entities the domain's work touches, the personas who do that work, and the processes it runs — captured from the SMEs' own language as candidate methodology records. Phase 2 is discovery, not definition: candidates are proposed here and reconciled in Phase 3; fields and entity detail wait for Phase 5.

When Phase 1.5 ran, Phase 2 is also where the **baseline meets the stakeholder for the first time** — as probes, after their unprompted account, never as the opening frame.

### Inputs

- Phase 1 complete: confirmed Charter, Domain, Persona, and anchor Process records
- The Baseline Report(s) from Phase 1.5, when it ran — specifically the gaps-and-ghosts list and the per-domain candidate groupings
- One or more SMEs per in-scope domain (administrator-as-proxy acceptable per the kickoff protocol's Variant A; the conduct charter governs either way)
- Conduct documents (charter, kickoff, question library)

### Phase-Specific Rules

- **One domain per session.** A discovery session covers one domain. Multiple sessions per domain are fine; one session spanning domains is not — coverage tracking and the transcript both degrade.
- **Unprompted account first (anchoring discipline).** Each session opens with the SME's own walkthrough of the domain's work. Baseline material stays unmentioned until the AI judges the unprompted account captured. Then baseline probes run (see Activity). This is the same rule stated in Phase 1.5; Phase 2 is where it executes.
- **Candidates, not commitments.** Everything captured lands at `candidate` status. Phase 2 sessions do not confirm records — confirmation is Phase 3's job, where cross-domain reconciliation and baseline triage happen together. (This differs from Phase 1, whose read-back confirms: Phase 1's records are the engagement's frame; Phase 2's records are raw discovery that needs reconciliation.)
- **Entities are nouns the SME actually said.** A candidate entity requires the SME having named the thing (or confirmed a probe about it). Per conduct charter §11.6.b, "organizations like this usually track X" is not a basis for a candidate.
- **No field-level detail.** When an SME volunteers fields ("we track their email and renewal date"), capture the volunteered items in the entity's notes verbatim and move on — do not elicit more. Field definition is Phase 5.
- **Process handoffs are discovery gold.** When a process leaves the domain ("then accounting takes over"), record the handoff (`process_hands_off_to_process` once both ends exist; notes until then) — these become the cross-domain seams Phase 3 reconciles.
- **Saturation ends the domain, not a session count** (v0.5, from the domain-discovery guide). A domain typically takes one to three sessions. A session is a *saturation session* when it surfaces no new candidate entity, persona, or process for the domain; the first session cannot be one. After each session, ask the administrator whether any vantage point (leadership, operations, support, external-facing roles) is still uncovered — if yes, the next session targets it; if no, the domain is complete. A later stakeholder is never shown the earlier candidates before their own account (the anchoring rule applies between stakeholders as it does to the baseline); the AI reads them, so it can tell a genuinely new candidate from a renaming, and records differing language as a separate candidate for Phase 3 to disambiguate.

### Activity

Per in-scope domain, one session:

1. **Kickoff** per the protocol (full Variant B for a first-time SME; one line for Variant A).
2. **Unprompted walkthrough.** "Walk me through the work of [domain] — what happens, who does it, what do you keep track of?" Probe per the conduct charter; capture candidate entities, personas, and processes as they are named.
3. **Baseline probes** (when Phase 1.5 ran). Work the domain's slice of the gaps-and-ghosts list and any baseline candidates the SME did not mention. Use the report's probe seeds as advisory wording — adapted, never verbatim, never leading. Record the SME's reaction in the candidate's notes: it is evidence for Phase 3 triage, not a disposition (no keep/transform/drop decisions in Phase 2).
4. **Conflict capture.** When the SME's account contradicts the baseline ("we don't track that" vs. a field at 87% population) or contradicts Phase 1 (a process that fits no domain), apply the scope-change protocol (conduct charter §8): name it, log it, continue under the stated assumption. These conflicts are Phase 3's queue.
5. **Close** with the end-of-section summary (not a confirming read-back — candidates stay candidates) and the session lifecycle (conversation summary, session complete).

### Captured V2 Records

| What is captured | V2 record type | Status at capture | Notes |
|---|---|---|---|
| Things the domain tracks | Entity records (`ENT-NNN`) | `candidate` | With kind where evident; `entity_scopes_to_domain` edge; volunteered field mentions in notes |
| People who do the work | Persona records (`PER-NNN`) | `candidate` | New ones only — Phase 1 personas are settled; `persona_scopes_to_domain` edges either way |
| Workflows the domain runs | Process records (`PROC-NNN`) | mission_critical / supporting / deferred via classification | New processes under the domain; Phase 1 anchor processes enriched (steps/triggers/outcomes fields), not duplicated |
| Baseline probe reactions | Notes on the probed candidate | — | Evidence for Phase 3 triage; no disposition recorded |
| Baseline/upstream conflicts | Decision or Planning Item per the scope-change protocol | — | Phase 3's reconciliation queue |
| The session | Session + conversation records | `complete` | One per domain; `session_belongs_to_project` |

### Output

- Per in-scope domain: candidate entities, personas, and processes with domain edges, capturing the SME's account in the SME's language
- The worked baseline-probe record: every gaps-and-ghosts item for the domain either probed (reaction noted) or explicitly deferred with a reason
- The Phase 3 queue: logged conflicts and scope changes
- A rendered Domain Discovery Report per domain remains optional until the rendering pipeline exists; the records are canonical

### Completion Criteria

- Every in-scope domain has at least one completed discovery session
- Every candidate entity and new persona carries a domain edge and attributable SME language (name/description/notes traceable to what was said)
- When Phase 1.5 ran: every gaps-and-ghosts item assigned to the domain is probed or explicitly deferred — none silently dropped
- All discovered conflicts are logged as Decisions or Planning Items — none absorbed silently
- No Phase 2 record was transitioned to `confirmed` (a Phase 2 session that confirmed anything is a process violation; confirmation is Phase 3)

---

# Part III — Cross-Phase Mechanics

The two mechanics below run in every phase. They were carried by separate documents until v0.5; this Part is now their process home. The store enforces both — they are not conventions to remember.

## 10. Requirement Capture and Approval

*Source consolidated:* `PRDs/product/crmbuilder-v2/requirements-provenance-and-review-anchor.md` (founding design record, 06-13-26) — live in the store as REQ-108 and its family under topic TOP-087.

### Principle

The human project manager defines what is to be built. Everything that exists traces to something a human defined or an AI interpretation a human approved. The conversation and the decision are the truth; requirements, plans, and code are projections of it that can be re-checked against it at any time.

### The model

- **A requirement is one declarative, testable statement with an acceptance criterion.** It says what the system must do, not how, and never carries build history.
- **Requirements form a tree.** The top is one broad statement a human can read; each level adds detail. A leaf is validated by *where it hangs*, not by reading it.
- **Every requirement has provenance.** A top-level requirement carries its own — the conversation, session, and decision that defined it. A child inherits through its parent. The only forbidden state is a requirement with no parent and no provenance.
- **Every requirement records its origin:** human-defined, or AI-derived-and-human-approved. Approval is a recorded event — a person, a time, the exact text.
- **A requirement lives in two structures.** Its parent requirement carries derivation; its topic carries navigation. Topics are the table of contents of the system's capabilities; one conversation addresses exactly one topic.
- **The spine** is traceable both ways: `defined → decided → specified → planned → developed → verified` — conversation, decision, requirement, planning item, commit, test.

### Lifecycle in the store

| State | Meaning | How it is reached |
|---|---|---|
| `candidate` | A human stated it, or an AI derived it; on the record, not yet a commitment | Created with its conversation and topic edges |
| `confirmed` | A commitment to deliver | **Only** by an approving decision (`requirement_approved_by_decision`) — never by editing the status field (REQ-243) |
| `deferred` / `rejected` | Deliberately not now / not ever, with the deciding decision recorded | By decision; never deleted |
| `needs_review` (flag) | Living drift — a parent, governing decision, or downstream artifact changed | Raised automatically; cleared only by a recorded review (REQ-249, REQ-345) |

A decision resolves a requirement one of three ways: **deliver** (it goes active), **decline** (recorded, not dropped — nothing a human said silently dies), or **change** (the current text is superseded and the revision re-enters approval). An AI-derived requirement is approved with its source conversation shown beside it, so approval is against intent, not against the paraphrase.

### Readability gate

Approval is only as strong as the clarity of what is approved; an unreadable statement gets rubber-stamped. The store therefore rejects, at confirm time, a description over 75 words or 4 sentences, one that embeds identifiers, or one lacking an acceptance criterion (LSN-036). Identifiers and history go in the requirement's notes.

### Review

Review is by topic, never by flat list: pick the topic, read its requirement tree top-down, trace anything doubtful to its conversation, read across the spine, and sign off — a recorded attestation that the topic's set matches intent. Three cross-topic queues support it: the approval queue (candidates awaiting a decision), the drift queue (everything flagged), and the coverage-gaps report (stated intents that became nothing, confirmed requirements built by nothing, capabilities no requirement asked for). A requirement must resolve to a topic before it can be activated, because an item unreachable under a topic could never have been reviewed.

### How the phases use it

Phase 1 and Phase 2 conversations produce methodology records first (personas, domains, processes, entities); requirements appear when a stakeholder states what the system must do, and are captured at that moment under the domain's topic with the conversation as root. Phase 3 confirms or declines them alongside the inventory. The design phases (Part IV) consume confirmed requirements and link each to what realizes it. Nothing is built — no planning item, no commit — without a confirmed requirement above it (GVR-230).

### Open

Cross-cutting requirements (a concern that touches every topic without being duplicated) and the governance of decomposition depth remain undecided; the working rule is that a human approves the *shape* — a node's immediate children — at each level, and decomposition stops when a leaf is testable.

## 11. Engagement Setup and the Session Lifecycle

*Source consolidated:* `PRDs/process/v2-user-process-guide.md` §4–8, rewritten against the current store. The engagement-setup records themselves are unbuilt (REQ-407 / PI-072; client inputs REQ-406 / PI-071) — this section describes the process those records will hold.

### Before the engagement exists

Gather four things: a **stakeholder map** (who owns which decisions, who holds which domain knowledge, who can speak for the mission, and which of them sits for which phase); **prior artifacts** (org charts, mission statements, process documents, existing systems — these become Phase 1.5 sources and Phase 2 hypotheses to be set aside during discovery); **organizational context**; and **constraints** (timeline, budget, integrations, compliance) that will land in the charter as scope or out-of-scope items. Re-read the conduct documents. No records are created yet.

### Kickoff — the engagement comes to exist

1. Create the **engagement** record (the workspace; every record below belongs to it).
2. Write the **charter** at version 0.1: scope, in scope (domains, deliverables, phases that will run), out of scope, architectural foundations (engagement-specific principles and any methodology deviation), current state, open items. It is expected to be honest, not complete.
3. Record the **participants** — the real people and roles from the stakeholder map — so later personas can be backed by them.
4. Log each consequential kickoff **decision** with context, decision, rationale, alternatives, consequences.
5. Record the kickoff **session** (append-only) and any open questions as **planning items**.

For CRMBuilder dogfood the engagement already exists; for a client the mechanics above are Phase 0 and precede Phase 1.

### Every session, the same lifecycle

**Open.** Orient from the store, not from files: the charter, the active governance rules and preferences, the last few sessions, and any decision the upcoming work names (the session-bootstrap protocol in `CLAUDE.md`). A stakeholder-facing session also re-reads the conduct documents and picks its kickoff variant: administrator-as-proxy, first session with an SME, follow-up with a known SME, or multi-stakeholder. Open the session record at the start — anchored on the planning item it advances and belonging to its project — not after the fact.

**Conduct.** The conduct charter governs how; the phase section governs what. The rule that does the most work is §11.6.b — *inferences require positive support*: summarize what was said, never what was implied. Capture records as they emerge (candidate status for methodology records; decisions and planning items as they are made), because the store, not the transcript, is the deliverable.

**Close.** Before the next session begins:

- One **conversation** record per topic touched, each with its summary and its `addresses` (or, for the final delivering conversation, `resolves`) edge to the planning item.
- Every consequential **decision** logged with rationale — if the rationale cannot be written in three sentences, a preference was stated, not a decision made.
- **Planning items** resolved or raised; **references** created at the moment the relationship was established (a decision that touches an entity, a process that consumes a service) — never reconstructed later.
- The **charter** versioned only if scope, principles, or current state genuinely shifted; most sessions leave it alone.
- Renders generated where the phase calls for one, or noted as pending.
- The session record transitioned to `complete` with its executive summary.

After close, the store is the source of truth for what happened; the conversation can be forgotten. In Claude Code these writes happen in real time against the live API (GVR-231); the close-out-payload path is the sandbox fallback (LSN-042).

# Part IV — The Design Phases (Phases 4–8) — Placeholder

The design phases take a domain from its **confirmed inventory** (the exit of Phase 3) to an **approved, engine-checked design version** ready for publish (the entry of Phase 9 and the publish/reconcile capabilities already governed under TOP-101 / TOP-109 / TOP-091). In the legacy process these are Phases 4–8: process definition and domain overview, entity PRDs, cross-domain service definition, domain reconciliation, and stakeholder review. Under V2 the documents those phases produced become renders of design records, and the reconciliation and review steps become checks and sign-offs on those records.

The phases are not yet drafted. The first candidate requirement set for the capability they need — twenty candidates covering derivation from the inventory, coherence and completeness gates, renders and recorded approval, change propagation, and the conduct of design sessions — is at `PRDs/product/crmbuilder-v2/design-phase-candidate-requirements.md` (Part B), together with the decisions that gate writing them to the store (Part C). Once those decisions are made and the candidates are confirmed, each phase here is drafted to runnable and executed against the dogfood per Part V.

The store's design model itself (entities, fields, relationships, layouts, roles, teams, filtered tabs, dynamic-logic rules, views, automations, engine overrides, versions) is already built and governed under TOP-089; Part IV specifies how it is populated and approved, not what it is.

# Part V — The Delivery Phases (Phases 9–13)

The delivery phases take an engagement from an **approved design** (the exit of the design phases) to a **running, configured, verified CRM in its users' hands**. Unlike the placeholder design phases, most of this part is specified from capability that exists and has been executed for real: the deployment capability shipped under REQ-522, was proven by a four-run live proof on 2026-08-30 (DEC-956), and was rolled out to the production service the same day.

Two of the five legacy phase numbers change meaning here:

- **Phase 9 (YAML Generation) is subsumed.** Under V2 the engine program files are generated *inside* the publish operation, in memory, from the canonical design (REQ-287) — there is no operator step that produces YAML as an artifact. The number is retained in the phase table for historical alignment with the 13-phase document process; nothing runs at it.
- **Phase 10 (CRM Selection) remains a placeholder.** The store's `crm_candidate` records and the evaluation-report render carry the current practice; the phase is drafted when an engagement next reaches a genuine engine choice.

## 12. Phase 11 — CRM Deployment

### Purpose

Stand up the client's CRM instance from nothing: create the server at an infrastructure provider, point a DNS name at it, install the target engine with transport security, verify the installation, and register the result as an engagement instance that later phases can configure and audit. The phase is complete when an administrator who started with no infrastructure has a reachable, empty, healthy CRM registered in V2 with a working credential.

Deployment is executed by the **service**, not the operator's desktop: the operator submits a *deploy run* and may close their machine; the run continues, survives service restarts, and its status, phases, and log are shared history for every administrator (Deploy History).

### Inputs

- An engagement with an administrator principal (deploying spends money and changes public DNS; the surfaces are admin-only — DEC-945)
- The engagement's **provider credentials**: an infrastructure-provider token and a DNS-provider token, stored encrypted behind opaque references (REQ-157). CRMBuilder's own accounts are the usual default; a client may supply its own so the server bills to them
- A DNS zone under the engagement's DNS-provider account (the client's domain, or a CRMBuilder-held domain for the client)
- The deployment parameters: server region/size/image, the instance hostname (subdomain + zone), the certificate contact address, and the CRM administrator account (username, email, generated password)

### Phase-Specific Rules

- **A deploy run is a resumable background job.** It is created queued, claimed by a deploy worker with a heartbeat, and driven through an ordered, idempotent phase sequence with a persisted checkpoint. A run abandoned by a restarted service is reclaimed and resumed at the phase that did not complete — proven live by killing the service mid-install (DEC-956).
- **Failure keeps everything and reports it (DEC-945).** A failed run never destroys what it built; the server, DNS record, and failed phase are recorded and shown, and Retry resumes from the checkpoint without creating a second server. Cleanup of an abandoned run's infrastructure is a deliberate operator act in the provider console.
- **The production boundary (DEC-946).** Provisioning a *client's* server from the engagement's credential is product behaviour; CRMBuilder's own production host is refused as a target at request time and again in the runner. Deploying CRMBuilder itself remains human-only.
- **DNS records are created unproxied** (DNS-only), or certificate issuance and shell access to the server break. Readiness is checked against **public resolvers**, never the service host's own resolver, whose negative cache otherwise stalls a fresh name for its negative-TTL (a live-proof finding).
- **Secrets cross once.** Passwords and tokens enter through request bodies, are stored encrypted behind opaque references, resolve only inside the worker, and are masked in every log line. Each run generates its own shell keypair for the server; nothing personal is baked in.
- **Verification is part of the run.** The run ends by probing the deployed instance (redirect, transport security, certificate, login surface, scheduler, database) with polling rather than single probes; gaps demote the outcome to succeeded-with-issues rather than passing silently.
- **Registration closes the loop.** A successful run writes the instance record (role `both`, with the CRM administrator login as its stored credential) and its deploy/provisioning facts (REQ-172) in the same transaction as the terminal status — so a succeeded run and a registered instance cannot disagree.

### Activity

1. Store or confirm the engagement's provider credentials (once per engagement).
2. Submit the deploy run from the desktop wizard: server choice from the provider's live catalog, hostname from the zone list, certificate contact, CRM admin account.
3. The service executes the run: validate credentials and refuse protected hosts → create the server (recovering any server already tagged with this run) → await its address → upsert the DNS record → await public resolution → prepare the server → run the engine's installer with transport security → post-install checks → verify → register the instance.
4. The operator follows progress live or walks away; Deploy History carries every run's status, phases, log, and — for failed runs — what still exists.
5. On failure: fix the cause (usually a credential), Retry; the run resumes.

### Captured V2 Records

| What is captured | V2 record type | Layer | Status at capture | Notes |
|---|---|---|---|---|
| The provisioning job | Deploy run (`DEP-NNN`) | Delivery (operational log) | queued → running → terminal | Spec, checkpoint, capped log, worker claim; not a governance entity |
| Provider tokens | Provider credential | Delivery (operational) | — | One per provider per engagement; opaque secret references only |
| The deployed CRM | Instance record (`INST-NNN`) | Delivery | active | Role `both`; CRM admin login as stored credential |
| Provisioning facts | Instance deploy config | Delivery | — | Server identity/address, DNS record, certificate, key references, the registering run (REQ-172) |
| The deployment decision trail | Decision / session records | Governance | per lifecycle | When the deployment is itself a governed milestone (as the first one was — DEC-945/946/956) |

### Output

- A running CRM at its HTTPS name, empty of configuration, healthy under the run's verification checks
- The registered instance with working credentials, immediately auditable and publishable
- The run's durable record in Deploy History

### Completion Criteria

- The deploy run is `succeeded` (or `succeeded_with_issues` with every gap explicitly accepted)
- The instance answers over HTTPS at its name with a valid certificate, and the CRM administrator can log in
- The instance record exists with role `both` and its stored credential works — proven by a clean audit round-trip
- No orphaned infrastructure: every failed or abandoned run's kept server has been retried to success or deliberately destroyed

### Known Limitations and Engine Notes (v0.6)

- Current engine stack: EspoCRM via its official installer, on DigitalOcean (server) + Cloudflare (DNS) as the single supported provider pair. The phase definition above is provider-agnostic; adding a provider is adapter work.
- Open minor findings from the live proof (tracked in DEC-956): the run log's line cap can drop early evidence under installer output; certificate expiry is not yet recorded on the instance; a stale provider-credential status reads *Configured* until used.
- Re-deployment (replacing a live instance's server in place) and in-place upgrade remain the V1 server-management layer's territory; this phase covers first deployment.

## 13. Phase 12 — CRM Configuration

### Purpose

Make the empty instance *the client's* CRM: apply the engagement's approved design — entities, fields, relationships, layouts, and the rest of the design model — to the deployed instance, and complete the items no engine API can write. The design in the store remains canonical; the instance is a target the design is pushed to, never hand-edited into divergence.

### Inputs

- Phase 11 complete (a registered instance with working credentials)
- The engagement's approved design version (the exit of the design phases / Phase 8)
- The engagement's manual-config records (`MCF-NNN`) — the accumulated list of items with no API write path

### Phase-Specific Rules

- **Publish, don't configure by hand.** The publish operation generates the engine's program form from the canonical design in memory, validates it against the engine schema *and the live instance*, captures a pre-publish backup of the target's configuration, applies, and verifies — recording the whole run (`PUB-NNN`). Hand configuration of anything the pipeline can write is drift by construction.
- **Validate against the live target, not just the schema.** Cross-references may resolve against configuration already on the instance; validation reads the live target so a correct design is not rejected for what the file alone cannot see (REQ-288).
- **Manual configuration is tracked, not remembered.** Every design item the engine cannot accept through its API surfaces as a manual-config instruction; the phase is not complete while any remains open. The operator performs them in the engine's admin surface and marks them done.
- **Reconcile is the referee.** After publish and manual work, the three-way reconcile (design ↔ instance) must show agreement on everything publishable; differences are dispositioned deliberately (capture, publish, or accept) — never left silent.

### Activity

1. Publish the design to the instance (validate-only first if desired; scoped publishes for iteration).
2. Work the manual-config list against the instance's admin surface.
3. Run reconcile; disposition every difference; repeat publish/manual work until agreement.
4. Load seed and reference data where the engagement calls for it (record export/import surfaces).

### Captured V2 Records

| What is captured | V2 record type | Layer | Status at capture | Notes |
|---|---|---|---|---|
| Each publish | Publish run (`PUB-NNN`) | Delivery (operational log) | born terminal | Scope, pre-publish backup (REQ-292), outcome + verification (REQ-293) |
| Manual work | Manual-config records (`MCF-NNN`) | Methodology | per lifecycle | Completed as the operator performs them |
| Instance agreement | Membership / reconcile records | Delivery | — | The stored design-vs-instance verdicts |

### Output

- The instance carrying the approved design, with a publish history and pre-publish backups
- A completed manual-config list
- A reconcile view showing agreement

### Completion Criteria

- The latest publish run succeeded and its post-publish verification found every published object present
- No open manual-config item for this instance
- Reconcile shows no unexplained difference between the approved design and the instance

### Known Limitations (v0.6)

- The publish direction for roles, teams, and filtered tabs waits on emitter work (the capture direction is live); ordinary layouts publish, engine-bound layout variants do not. These arrive as design-model publish coverage grows.
- Saved views, duplicate-check rules, and workflows have no engine API write path and remain manual-config by design.

## 14. Phase 13 — Verification and Handover

### Purpose

Prove the deployed, configured CRM is the CRM the engagement defined — then put it in its users' hands. Verification under V2 is not a separate test authoring effort bolted on at the end; it is the accumulation of three built checks plus the engagement's own acceptance pass.

### Inputs

- Phases 11 and 12 complete
- The engagement's test-specification records (`TST-NNN`) where authored, and its stakeholders for acceptance
- The client's user roster for onboarding

### Phase-Specific Rules

- **Three mechanical layers come first.** (1) The deploy run's infrastructure verification (transport, certificate, scheduler, database) — already recorded in Phase 11. (2) The publish run's object verification — every published object read back from the instance. (3) The full audit/reconcile — the instance's entire configuration read back and compared to the design. A failure at any layer is fixed at its own phase, not papered over here.
- **Acceptance is human and recorded.** Stakeholders exercise the processes the design claims to support — against test specifications where they exist, as a guided walkthrough where they do not — and the outcome lands as governance records (session, findings, decisions), not as a verbal all-clear.
- **Handover is an act, not an ebbing away.** The CRM administrator credential is transferred to the client's owner; users are created with their roles; the client is shown where the manual-config items live for future reference; and a decision records that the engagement's deployment is accepted.

### Activity

1. Confirm the three mechanical layers are green (re-run reconcile as the final check).
2. Run the acceptance pass with stakeholders; capture findings; loop fixes through Phase 12 (design/publish) — never through hand edits.
3. Create users and roles for the client's roster; transfer the administrator credential; record the acceptance decision.

### Captured V2 Records

| What is captured | V2 record type | Layer | Status at capture | Notes |
|---|---|---|---|---|
| Acceptance sessions | Session / conversation records | Governance | complete | With stakeholder participants |
| Acceptance problems | Finding records | Delivery | per lifecycle | Looped back through Phase 12 |
| The acceptance itself | Decision record | Governance | Active | The engagement's deployment is accepted |

### Output

- A verified CRM whose configuration provably matches the approved design
- Users onboarded; administrator credential in the client's hands
- The recorded acceptance

### Completion Criteria

- Reconcile shows agreement; the latest publish verification found no gaps; the instance's infrastructure checks pass
- Every acceptance finding is resolved or explicitly deferred by decision
- The acceptance decision is recorded and the client holds the administrator credential

### Known Limitations (v0.6)

- Test-specification records exist in the store but have no execution pipeline; acceptance runs as guided sessions until one lands.
- Post-handover drift detection (the audit engine pointed at the *generated* system on a schedule) remains future work, as noted since v0.1.

# Part VI — Iterative Drafting

This PRD is authored iteratively. Each phase is drafted to a runnable state *before* it is executed against CRMBuilder dogfood. Execution surfaces gaps. Gaps refine the phase spec back into this PRD. Once the phase produces reproducible, satisfactory results against CRMBuilder, the next phase is drafted.

The CBM (Cleveland Business Mentors) engagement begins only after the process is sufficiently defined across the phases needed to deploy. CBM serves as validation against the prior document-driven CBM artifacts as benchmark.

### Sections to Be Drafted in Subsequent Versions

- ~~Engagement setup mechanics~~ — process drafted at §11 (v0.5); the records are PI-071/PI-072
- ~~The session lifecycle as a recurring pattern~~ — §11 (v0.5)
- Phases 4 through 8 specifications, each drafted before its phase runs (candidate requirements and a Part IV placeholder as of v0.5); ~~Phases 9–13~~ — delivery phases drafted at Part V (v0.6): Phase 11 executed live, Phases 12–13 drafted against built capability, Phase 9 subsumed, Phase 10 still placeholder
- The migration-mapping record type and the triage → migration-plan pipeline
- The baseline machinery's second pointing: drift detection against the *generated* system during post-deployment refinement (same audit engine, diffed against the confirmed graph instead of an empty one)
- V2 storage mechanics in depth (schema, API, MCP tool surface, desktop UI surfaces)
- The deployment engine specification (V1 EspoCRM today, future engines) — Phase 11's engine notes (v0.6) carry the current stack; the engine-adapter contract remains to be specified
- YAML generation specifics
- Versioning, supersession, and cross-reference impact analysis
- Rendering of artifacts from V2 records
- Engagement closing
- Reference appendices (governance object types, methodology object types, identifier conventions, MCP tool catalog)

---

## Notes on This Draft

This is v0.5 (the notes below accumulate from v0.3). Phase 1 has now been through one full Part V loop: drafted (v0.1), executed against the CRMBuilder dogfood (SES-166, 06-12-26), and refined from the run's six findings (PI-160). Phase 1.5's specified components were built (PRJ-022) and the phase ran live against the CBM test instance the same day — its Baseline Report is the concrete input Phase 2's draft is designed against. Phase 2 is drafted and awaits its own dogfood execution.

Source materials drawn upon, all retained as reference material with transitional status headers until subsumed:

- `PRDs/process/interviews/interview-master-prd.md` v1.4 — the existing strategic-vision/business-context interview guide; primary source for Phase 1 activity, topics, and phase-specific rules
- `PRDs/process/v2-user-process-guide.md` v0.1 — the existing V2-aligned process guide; primary source for orientation, the two-layer mental model, the phase sequence, and the operating-modes framing
- `PRDs/process/conduct/charter.md`, `kickoff.md`, `question-library.md` — referenced as conduct rules; not inlined here pending the decision on whether to subsume conduct into this PRD or keep it as a separate methodology-agnostic document
- `PRDs/product/CRMBuilder-PRD.md` v4.1 — context for the V1 product vision
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l1-PRD.docx` — context for the V2 strategic vision
- `PRDs/product/features/feat-audit.md` v1.3 — the Audit feature spec; primary source for Phase 1.5's discovery scope, source-instance roles, and the not-auditable list

Gaps and questions known at v0.1:

- The naming of Phase 1 — the existing methodology calls this "Master PRD" which collides with this document's name. "Business Context Capture" is the working title and may change.
- The exact API surface and MCP tool calls for writing each record type in real time are referenced generically here; the V2 storage system PRD and component PRDs at `PRDs/product/crmbuilder-v2/` carry the detail until that detail is consolidated in.
- Whether conduct documents (charter, kickoff, question library) live inside this PRD or alongside it as referenced supporting documents is unresolved.
- The mechanics of engagement initialization for a new (non-CRMBuilder) client are not specified; this matters when CBM begins.

Gaps and questions added at v0.2 (Phase 1.5 and triage):

- **No rejected/terminal disposition exists in the methodology lifecycle.** The current one-way gate is `candidate → confirmed → deferred`. Triage's *drop* disposition wants a true rejected terminal state with recorded rationale, distinct from deferred. Schema decision pending.
- **The audit → V2 deposit path, data profiler, and catalog normalizer are unbuilt.** The Audit function today emits YAML and V1 client-database rows only. Phase 1.5 cannot run until these land; they are well-shaped Planning Item candidates.
- **The migration-mapping record type does not exist.** Until it does, triage captures mappings in the session deliverable for later backfill.
- **Finding reuse vs. a methodology-layer conflict record** for baseline-vs-interview disagreements is undecided; reuse of the delivery layer's `finding` is the working preference.
- **Source adapters beyond EspoCRM** (spreadsheet first) are future work; Phase 1.5 currently assumes an EspoCRM source.
- **Where evidence lives on candidate records** — a structured evidence column/child table vs. free-text notes — is a schema decision; the spec requires evidence to be structured enough for triage queries ("all fields under 5% population").

Gaps and questions added at v0.3:

- **The cross-domain service entity type remains unbuilt** (PI-161); Phase 1 carries services in charter scope text transitionally.
- **Phase 2's dogfood target is awkward**: CRMBuilder's Phase 1 domains are sequential pipeline stages whose "SMEs" are all the same administrator — Phase 2's per-domain SME discovery will exercise the mechanics but not the multi-SME dynamics. CBM (post-process-definition) is where Phase 2's conduct rules get a real test.
- **The Domain Discovery Report renderer does not exist**; the records are canonical and the report is optional until the rendering pipeline lands.
- ~~Phase 3 needs its other half drafted~~ — done at v0.4 (Stream A interview reconciliation).

Gaps and questions added at v0.4:

- **Stream A's cross-stream matching is manual judgment.** Matching interview candidates to baseline candidates by "name and meaning" has no tooling support yet — a candidate-matching assist (even name-similarity ordering in the confirmation walk) is a quality-of-life build item once Phase 3 runs for real.
- **The inventory render** (confirmed entities/personas per domain as a reviewable document) waits on the rendering pipeline, like the other renders.
- **Phases 1.5 + 2 + 3 are now a complete discovery front-half on paper.** The next dogfood milestone is running 2 → 3 end to end; the next CBM milestone is the same sequence with the already-deposited baseline. Phase 4+ (process definition onward) remains the placeholder frontier.

Gaps and questions added at v0.5:

- **The conduct documents decision (v0.1) still blocks retiring `interview-master-prd.md`**, whose topic-by-topic question set is only otherwise held in the question library. See the consolidation ledger, Part A of `design-phase-candidate-requirements.md`.
- **§11's records are unbuilt.** Engagement setup (PI-072) and client-input storage (PI-071) are Draft; §11 describes the process ahead of the records.
- **The V2 user process guide's §22–24** (versioning, cross-references, rendering) and the legacy process document's Phases 9–13 remain unconsolidated pending the storage-mechanics and deployment sections.
- **The design phase's boundary and the term "V3"** are open decisions (D-1, D-2 in the candidate-requirements document); Part IV assumes Phases 4–8 and coins no new term.

These gaps are expected and will be closed by running the phases against CRMBuilder and CBM, observing what's missing, and refining.
