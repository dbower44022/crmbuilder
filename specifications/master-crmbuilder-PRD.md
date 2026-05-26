# Master CRMBuilder PRD

| Field | Value |
|-------|-------|
| Version | 0.1 (draft) |
| Last Updated | 05-26-26 12:00 |
| Status | Initial draft — minimum-viable content to run Phase 1 against CRMBuilder dogfood |
| Audience | Anyone running the CRMBuilder process for a client engagement (consultant, AI session, or future maintainer) |
| Governs | The entire process for using the V2 storage system to capture the complete definition of a product, from initial requirements through deployed functional application |
| Does not govern | Detailed V2 internals beyond what Phase 1 needs (schema, API, MCP, UI surfaces have their own component PRDs referenced here as they're consolidated in) |

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-26-26 | Initial draft. Orientation, two-layer mental model, phase sequence overview, Phase 1 (Business Context Capture) spec, the "what to do first" mini-guide for Phase 1. All other phases listed as placeholders to be drafted iteratively as the engagement reaches each one. |

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
| 1 | Business Context Capture | **Drafted** (this version) |
| 2 | Domain Discovery | Placeholder — drafted before Phase 2 runs |
| 3 | Inventory Reconciliation | Placeholder |
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

---

# Part III — Iterative Drafting

This PRD is authored iteratively. Each phase is drafted to a runnable state *before* it is executed against CRMBuilder dogfood. Execution surfaces gaps. Gaps refine the phase spec back into this PRD. Once the phase produces reproducible, satisfactory results against CRMBuilder, the next phase is drafted.

The CBM (Cleveland Business Mentors) engagement begins only after the process is sufficiently defined across the phases needed to deploy. CBM serves as validation against the prior document-driven CBM artifacts as benchmark.

### Sections to Be Drafted in Subsequent Versions

- Engagement setup mechanics (how to initialize V2 for a new client)
- The session lifecycle as a recurring pattern (open → conduct → close-out → apply)
- Phases 2 through 13 specifications, each drafted before its phase runs
- V2 storage mechanics in depth (schema, API, MCP tool surface, desktop UI surfaces)
- The deployment engine specification (V1 EspoCRM today, future engines)
- YAML generation specifics
- Versioning, supersession, and cross-reference impact analysis
- Rendering of artifacts from V2 records
- Engagement closing
- Reference appendices (governance object types, methodology object types, identifier conventions, MCP tool catalog)

---

## Notes on This Draft

This is v0.1. It captures only Phase 1 as a runnable specification, plus the orientation needed to read the document.

Source materials drawn upon, all retained as reference material with transitional status headers until subsumed:

- `PRDs/process/interviews/interview-master-prd.md` v1.4 — the existing strategic-vision/business-context interview guide; primary source for Phase 1 activity, topics, and phase-specific rules
- `PRDs/process/v2-user-process-guide.md` v0.1 — the existing V2-aligned process guide; primary source for orientation, the two-layer mental model, the phase sequence, and the operating-modes framing
- `PRDs/process/conduct/charter.md`, `kickoff.md`, `question-library.md` — referenced as conduct rules; not inlined here pending the decision on whether to subsume conduct into this PRD or keep it as a separate methodology-agnostic document
- `PRDs/product/CRMBuilder-PRD.md` v4.1 — context for the V1 product vision
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l1-PRD.docx` — context for the V2 strategic vision

Gaps and questions known at v0.1:

- The naming of Phase 1 — the existing methodology calls this "Master PRD" which collides with this document's name. "Business Context Capture" is the working title and may change.
- The exact API surface and MCP tool calls for writing each record type in real time are referenced generically here; the V2 storage system PRD and component PRDs at `PRDs/product/crmbuilder-v2/` carry the detail until that detail is consolidated in.
- Whether conduct documents (charter, kickoff, question library) live inside this PRD or alongside it as referenced supporting documents is unresolved.
- The mechanics of engagement initialization for a new (non-CRMBuilder) client are not specified; this matters when CBM begins.

These gaps are expected and will be closed by running Phase 1 against CRMBuilder, observing what's missing, and refining.
