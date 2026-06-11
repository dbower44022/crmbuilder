# Master CRMBuilder PRD

> **DISCUSSION DRAFT — NOT YET APPROVED.** This file is an authored proposal that has not been reviewed or approved. Every substantive structural and content choice is open for discussion. Treat this as a working artifact to react to, not a canonical specification.

| Field | Value |
|-------|-------|
| Version | 0.2 (draft) |
| Last Updated | 06-11-26 |
| Status | Phase 1 drafted (v0.1); Phase 1.5 (Existing System Baseline) and the Phase 3 baseline-triage section drafted (v0.2). Remaining phases placeholder. |
| Audience | Anyone running the CRMBuilder process for a client engagement (consultant, AI session, or future maintainer) |
| Governs | The entire process for using the V2 storage system to capture the complete definition of a product, from initial requirements through deployed functional application |
| Does not govern | Detailed V2 internals beyond what Phase 1 needs (schema, API, MCP, UI surfaces have their own component PRDs referenced here as they're consolidated in) |

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-26-26 | Initial draft. Orientation, two-layer mental model, phase sequence overview, Phase 1 (Business Context Capture) spec, the "what to do first" mini-guide for Phase 1. All other phases listed as placeholders to be drafted iteratively as the engagement reaches each one. |
| 0.2 | 06-11-26 | Added Phase 1.5 (Existing System Baseline) — the Audit function repurposed as a requirements input: existing systems are audited and data-profiled into *candidate* methodology records with provenance and utilization evidence. Added the Phase 3 baseline-triage section (keep / transform / drop dispositions, migration mapping capture, baseline-vs-interview conflict reconciliation); the remainder of Phase 3 stays placeholder. |

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
| 1 | Business Context Capture | **Drafted** (v0.1) |
| 1.5 | Existing System Baseline | **Drafted** (v0.2) — conditional; runs only when the client has one or more existing systems |
| 2 | Domain Discovery | Placeholder — drafted before Phase 2 runs |
| 3 | Inventory Reconciliation | **Partially drafted** (v0.2) — baseline-triage section only; the interview-derived inventory reconciliation remains placeholder |
| 4 | Domain Overview and Process Definition | Placeholder |
| 5 | Entity PRDs | Placeholder |
| 6 | Cross-Domain Service Definition | Placeholder |
| 7 | Domain Reconciliation | Placeholder |
| 8 | Stakeholder Review | Placeholder |
| 9 | YAML Generation | Placeholder |
| 10 | CRM Selection | Placeholder |
| 11 | CRM Deployment | Placeholder |
| 12 | CRM Configuration | Placeholder |
| 13 | Verification | Placeholder |

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
- **Identifiers assigned during the conversation.** Personas use `PER-NNN`. Domains use two-letter codes (`MN`, `MR`, etc.). Processes use `{DOMAIN}-{PROCESS}` (e.g., `MN-INTAKE`). Confirm each at assignment; identifiers are permanent once assigned.
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
| Personas | Persona records | Methodology | Each with identifier, responsibilities, primary domains |
| Domains | Domain records | Methodology | Each with two-letter code, purpose, tier |
| Processes (high-level) | Process records | Methodology | Each with name, parent domain, one-line description, tier |
| Cross-domain services | Cross-Domain Service records | Methodology | Each with purpose, capabilities |
| Scope determinations | Decision records (`DEC-NNN`) | Governance | Each with rationale |
| Deferred work | Planning Item records (`PI-NNN`) | Governance | Each with `item_type: pending_work` |
| Conceptual relationships | Reference records (`REF-NNNN`) | Governance | Universal references table |
| The interview itself | Session record (`SES-NNN`) | Governance | `topics_covered` opens with verbatim seed prompt |

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
- Every cross-domain service has a purpose and at least one capability listed
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
- **Evidence travels with the candidate.** Each candidate carries the utilization evidence that makes triage decidable: field population rate, last-populated date, actual enum value distribution vs. declared options, record counts and recency for entities, standard-vs-custom catalog classification.
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

## 8. Phase 3 — Inventory Reconciliation (partial: Baseline Triage)

> Only the baseline-triage section of Phase 3 is drafted here. The interview-derived inventory reconciliation (reconciling Phase 2's Domain Discovery Report into the durable Entity and Persona Inventories) remains placeholder and is drafted before Phase 3 runs. When the client had no existing system (Phase 1.5 skipped), this section does not apply.

### Purpose of the Triage Section

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

> Mechanics gap (v0.2): the migration-mapping record type does not yet exist in the V2 schema. Until it does, mappings are captured in a structured section of the triage session's deliverable and backfilled when the record type lands.

### Captured V2 Records (Triage)

| What is captured | V2 record type | Layer | Notes |
|---|---|---|---|
| Keep dispositions | Status transition `candidate → confirmed` on the baseline record | Methodology | Evidence and provenance ride along unchanged |
| Transform dispositions | New confirmed record + variant/supersession edge + closure of the baseline candidate | Methodology | The Decision explains the shape change |
| Drop dispositions | Terminal status on the candidate + Decision record (`DEC-NNN`) with rationale | Both | Drops are governed removals, never silent |
| Baseline-vs-interview conflicts | Reconciliation record + resolving Decision | Governance | See vocabulary note below |
| Migration mappings | Migration-mapping records (pending schema) | Methodology | One per keep/transform |
| The triage session(s) | Session records (`SES-NNN`) | Governance | One per domain batch, per the session lifecycle |

> Vocabulary note (v0.2): the delivery layer already has a `finding` record (type `conflict`, with resolution methods) for "two sources disagree." Whether methodology-layer baseline-vs-interview conflicts reuse `finding` or get their own record is an open schema decision; reuse is the working preference to keep one vocabulary for disagreement across the framework.

### Completion Criteria (Triage Section)

- Every baseline candidate from every Phase 1.5 source has exactly one terminal disposition
- Every keep and transform has a migration mapping recorded
- Every drop has a Decision record with rationale
- Every baseline-vs-interview conflict raised during triage is resolved by a Decision, or carried as an explicit Planning Item
- No baseline candidate remains at `candidate` status when Phase 3 closes

---

# Part III — Iterative Drafting

This PRD is authored iteratively. Each phase is drafted to a runnable state *before* it is executed against CRMBuilder dogfood. Execution surfaces gaps. Gaps refine the phase spec back into this PRD. Once the phase produces reproducible, satisfactory results against CRMBuilder, the next phase is drafted.

The CBM (Cleveland Business Mentors) engagement begins only after the process is sufficiently defined across the phases needed to deploy. CBM serves as validation against the prior document-driven CBM artifacts as benchmark.

### Sections to Be Drafted in Subsequent Versions

- Engagement setup mechanics (how to initialize V2 for a new client)
- The session lifecycle as a recurring pattern (open → conduct → close-out → apply)
- Phases 2 through 13 specifications, each drafted before its phase runs (Phase 3's interview-derived reconciliation half; Phase 1.5 and the Phase 3 triage section are drafted as of v0.2)
- The migration-mapping record type and the triage → migration-plan pipeline
- The baseline machinery's second pointing: drift detection against the *generated* system during post-deployment refinement (same audit engine, diffed against the confirmed graph instead of an empty one)
- V2 storage mechanics in depth (schema, API, MCP tool surface, desktop UI surfaces)
- The deployment engine specification (V1 EspoCRM today, future engines)
- YAML generation specifics
- Versioning, supersession, and cross-reference impact analysis
- Rendering of artifacts from V2 records
- Engagement closing
- Reference appendices (governance object types, methodology object types, identifier conventions, MCP tool catalog)

---

## Notes on This Draft

This is v0.2. It captures Phase 1 as a runnable specification (v0.1), plus Phase 1.5 and the Phase 3 baseline-triage section (v0.2), plus the orientation needed to read the document. Phase 1.5 is drafted ahead of its build: the audit → V2 deposit path, data profiler, and catalog normalizer it specifies do not exist yet (see §7 Known Limitations); the spec defines what they must do.

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

These gaps are expected and will be closed by running the phases against CRMBuilder and CBM, observing what's missing, and refining.
