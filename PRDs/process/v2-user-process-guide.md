# CRMBuilder User Process Guide (v2)

> **Status: Transitional.** This document is being consolidated into the Master CRMBuilder PRD at `specifications/master-crmbuilder-PRD.md` (in development). Once the Master CRMBuilder PRD covers this content, this document will be archived. Continue to use this as reference until that supersession is explicit.

*An Engagement Playbook for Consultants Using the v2 Governance Stack*

| Field | Value |
|-------|-------|
| Version | 0.1 (draft) |
| Last Updated | 05-16-26 14:30 |
| Status | Initial draft — pre-review |
| Level | L3 (names v2 specifically and references MCP, SQLite, desktop UI) |
| Audience | Consultants operating CRMBuilder on a client engagement |
| Governs | How a consultant runs an engagement using v2's governance stack alongside the existing 13-phase Document Production Process |
| Does not govern | Conduct rules during stakeholder interviews (see `conduct/charter.md`), document authoring standards (see `interviews/authoring-standards.md`), application source code, the v1 deployment engine |

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-16-26 | Initial draft. Captures the two-layer governance/methodology model, engagement setup, the recurring session lifecycle, phase-by-phase walkthrough of the 13-phase Document Production Process annotated with v2 governance touchpoints, versioning and supersession rules, references and rendering, and a closing reference section. |

---

# Part I — Orientation

## 1. Purpose and Audience

This guide tells a consultant how to run a CRM Builder client engagement using the v2 governance stack. It assumes the v2 storage system is in place and that the engagement will be conducted through some combination of Claude.ai sessions (MCP-connected, or reading the REST API directly) and the v2 desktop application.

The reader of this guide is the consultant — the person organizing the engagement, conducting interviews, capturing decisions, producing artifacts, and ultimately delivering a configured CRM to the client. The client's stakeholders are not the audience for this document; they interact with the engagement through the conduct framework, not through this playbook.

**What this guide covers.** The lifecycle of an engagement: pre-engagement preparation, kickoff, the recurring session pattern, phase-by-phase methodology execution, versioning discipline, cross-references, rendering, and engagement closeout.

**What this guide does not cover.** Conduct rules for stakeholder-facing interviews (those live in `PRDs/process/conduct/`). Authoring standards for individual deliverable documents (those live in `PRDs/process/interviews/authoring-standards.md`). A reference manual for the v2 desktop application's UI. Development or extension of CRMBuilder itself. The v1 deployment engine.

**What this guide assumes you already know.** That you have read `CLAUDE.md` in the crmbuilder repo. That you understand the basic shape of the methodology — at least that there is a Master PRD, that domains organize the work, that entities are nouns the organization tracks, and that processes are how the work gets done. That you know the engagement will eventually produce a configured CRM instance and that v2's job is to make the path from requirements to that instance traceable and reproducible.

## 2. The Two-Layer Mental Model

The single most important idea in v2 is that an engagement has two layers, and the consultant works in both.

**The governance layer** is the project management layer. Its objects answer questions like "what is this engagement about?", "what have we decided?", "what did we cover last session?", "what's still open?", "what changed and when?". The governance layer is methodology-agnostic — it would look essentially the same for any consulting engagement that benefited from this kind of tracking, whether or not it involved building a CRM. Its objects in v2 are: Charter, Status, Decisions, Sessions, planning items, topics, risks, and references.

**The methodology layer** is the CRM Builder layer. Its objects answer questions like "what does the client do?", "what nouns do they track?", "what processes do they run?", "what fields belong to what entities?", "what does the deployed CRM need to look like?". The methodology layer is engine-agnostic at the requirements level and engine-specific only at the deployment-end of the process. Its objects in v2 are: domains, cross-domain services, entities, fields, processes, process steps, personas, requirements, manual-config items, and test specifications.

The two layers connect through the universal references table, but they don't merge. A Decision (governance) can reference an Entity (methodology). A Session (governance) can reference a Process (methodology). The Charter (governance) names the domains that are in scope without itself becoming a domain definition.

A functional test for which layer something belongs in:

> *If you swap clients but keep the methodology, what changes? That's governance.*
> *If you swap methodology but keep the client, what changes? That's methodology.*

A second test, especially useful when distinguishing the engagement Charter from the Master PRD:

> *The Charter describes the project building the thing.*
> *The Master PRD describes the thing being built.*

For one engagement you will have one Charter and one Master PRD. They both establish scope, but at different levels — the Charter's scope is the engagement (which domains will we cover, what's the timeline, what's out of scope for this engagement); the Master PRD's scope is the system (what must the CRM do, who does it serve, what does it cover).

## 3. The v2 Toolkit at a Glance

The v2 storage stack is layered, and you will interact with it through more than one surface during an engagement.

**The data layer** is a SQLite database file (`crmbuilder-v2/data/v2.db`). It is the source of truth. You do not edit it directly; you go through one of the layers above.

**The access layer** is a Python module that handles validation, transactions, and identifier generation. The desktop application uses it directly. You do not normally call it directly.

**The REST API** is a FastAPI server that exposes the database over HTTP. You start it with `crmbuilder-v2-api &`. It is what the desktop application talks to when the application is in REST mode, and what tooling outside the application talks to.

**The MCP server** wraps the REST API for Claude.ai tool calls. You start it with `crmbuilder-v2-mcp`. When the MCP server is connected to your Claude.ai session, the AI can read and write the governance and methodology objects directly through tool calls.

**The desktop application** is the PySide6 GUI. You use it for human-driven operations: reviewing the current Charter and Status, browsing decisions and sessions, building references, running CRM deployments, and the like.

**REST API mode** is for sessions where the MCP server is not available. The AI reads (and writes) the governance objects by calling the REST API directly — `curl http://127.0.0.1:8765/<entity>`, naming the engagement with the `X-Engagement` header and unwrapping the `{data, meta, errors}` envelope. The database is the single source of truth; you read it live, never from committed files. (PI-β removed the former git-tracked `db-export/` JSON snapshots.)

Three operating modes you will actually be in:

| Mode | When | What you read | What you write |
|------|------|--------------|----------------|
| MCP-connected Claude.ai session | Substantive AI-led work (interviews, drafting, decision capture) when MCP is running | Live database via MCP tool calls | Live database via MCP tool calls |
| REST-API Claude.ai session | Same kind of work when MCP is not running | Live database via the REST API (`X-Engagement` header) | Live database via the REST API |
| Desktop application | Human-driven review, governance maintenance, deployment operations | Live database via REST | Live database via REST |

A useful default: prefer MCP-connected sessions for any session where governance objects will change during the conversation. Use the REST API directly when MCP is not running. Use the desktop application for maintenance, browsing, and deployment.

---

# Part II — Engagement Setup

## 4. Pre-Engagement Preparation

Before kickoff, gather four kinds of information.

**Stakeholder map.** Who at the client organization owns which decisions, who provides which domain expertise, and who can speak for the mission. Names, roles, availability, and the natural pairing of stakeholders to upcoming methodology phases (the executive who will sit for the Master PRD interview is usually not the operations lead who will sit for a Domain Discovery interview).

**Prior artifacts.** Anything the client has already written down: org charts, mission statements, process documents, existing software systems, prior consulting engagements. These shape your hypotheses about domains and entities going into Phase 2, even though you will set those hypotheses aside during the actual discovery.

**Organizational context.** What the organization does, who it serves, how it is funded, what is changing, what is stable. You do not need a deep understanding before kickoff, but you should not be coming in cold either.

**Constraints.** Timeline, budget, integration requirements, regulatory or compliance considerations. These belong in the Charter as scope items or out-of-scope items.

While you are gathering this, refresh yourself on the conduct framework. The three documents at `PRDs/process/conduct/` — `charter.md`, `kickoff.md`, `question-library.md` — govern how you will run every stakeholder-facing session for the duration of the engagement. They are methodology-agnostic; they apply equally to a Master PRD interview and to a Domain Reconciliation conversation. If you have not read them recently, read them now. If you have, glance at the table of contents to refresh your memory of what's covered where.

You are not yet creating any governance objects. The engagement does not formally exist until kickoff.

## 5. Engagement Kickoff

Kickoff is the moment the engagement formally exists. It is where you create the first governance objects.

**Create the engagement Charter (version 0.1).** The Charter at kickoff should capture, at minimum:

- **Scope.** A short paragraph naming the client and the engagement's purpose.
- **In Scope.** The domains the engagement will cover. The deliverables. The methodology phases that will run.
- **Out of Scope.** Anything you have explicitly excluded — adjacent organizations, future phases of work, integrations that are deferred. Out-of-scope items prevent scope creep later by giving you a documented reference point.
- **Architectural Foundations.** Engagement-specific principles. Examples: "the deployed CRM will be self-hosted, not SaaS"; "all client data is sensitive and stays in the client's tenant"; "the methodology will follow the 13-phase Document Production Process without modification" (or, if you are deviating, state the deviation here).
- **Current State.** "Phase: kickoff complete, Phase 1 not yet started."
- **Open Planning Items.** Anything that was raised at kickoff but not resolved. Each open item should be a specific question, not a vague concern.

Version 0.1 of the Charter is not expected to be complete. It is expected to be honest about what is known and what is not. Subsequent versions will fill in gaps as decisions are made.

**Create the initial Status (version 0.1).** Status is more operational than Charter. It captures phase, sub-step, in-flight work, blockers, and reading-order guidance for the next session. At kickoff, the Status says: "Phase 1 (Master PRD) starting. No prior sessions. Next conversation: schedule the Master PRD interview."

**Log the kickoff Decisions.** Any consequential decision made at kickoff gets a DEC-NNN entry. Typical kickoff decisions:

- The list of in-scope domains (if the client has named them).
- Engagement timeline and cadence.
- Stakeholder ownership of major artifacts.
- Methodology variations (e.g., "Phase 6 Cross-Domain Services will be deferred until Phase 5 is complete because the client does not yet know which services will be shared").

Each decision gets a title, context, the decision itself, rationale, alternatives considered, and consequences. The structure matters — these entries will be read later by sessions trying to understand why something was done a particular way.

**Capture the kickoff Session record.** The Session record at SES-001 captures what was discussed at kickoff, what decisions came out of it, and what artifacts were produced (Charter v0.1, Status v0.1, the kickoff decisions). Session records are append-only — you do not edit them later. If the meeting's outcomes change, that is a new session, not an amendment.

**Register any open planning items.** Open items raised at kickoff but not resolved go into the planning_items table as PI-NNN entries, and are also listed in the Charter's Open Planning Items section. The Charter section is the high-level pointer; the planning_items row is where the work tracking happens.

After kickoff, the database contains: one Charter, one Status, some Decisions, one Session, and possibly some planning items. The engagement now exists as a tracked object. The next thing that happens is Phase 1.

---

# Part III — The Session Lifecycle (Recurring Pattern)

The same lifecycle pattern repeats for every substantive session in the engagement, regardless of which methodology phase the session is executing. Understanding this pattern once means you do not have to relearn it for each phase.

## 6. Pre-Session Orientation

Every session that engages v2 work begins with a tiered orientation, per the protocol in `CLAUDE.md`.

**Tier 1, universal, every session.** Read `CLAUDE.md` in the crmbuilder repo. If the session is stakeholder-facing, also read the three conduct files: `conduct/charter.md`, `conduct/kickoff.md`, `conduct/question-library.md`.

**Tier 2, v2 engagement, MCP-connected.** Through MCP tool calls:

- `get_current_charter` — to know what the engagement is and what's in scope.
- `get_current_status` — to know where the engagement currently stands.
- `list_recent_sessions(limit=3)` — to know what's recent context.
- `get_decision(<id>)` — for any decision referenced by name in the upcoming work.

**Tier 2, REST API.** When MCP is not connected, read the same context live from the REST API: `GET /charter`, `/status`, `/sessions`, `/decisions/<id>`, `/references?...` against `http://127.0.0.1:8765` with the `X-Engagement` header, unwrapping `.data` from the `{data, meta, errors}` envelope.

**Tier 3, on-demand.** Targeted queries during the session as specific topics arise. "What did we decide about X?" prompts a `get_decision` or `list_decisions_for_session` call mid-conversation, not a pre-loaded read.

The orientation protocol has a purpose: it gives the AI bounded, predictable context before substantive work begins, so sessions start informed without flooding context with irrelevant detail. Treat it as part of session setup, not as a ritual.

## 7. Conducting the Session

This guide does not tell you how to conduct a stakeholder-facing interview. That job belongs to `conduct/charter.md` and the phase-specific interview or guide document. What this guide tells you is which conduct documents apply to which phase, and which session-type variant from `conduct/kickoff.md` matches the conversation you're about to have.

Four session-type variants are defined in `conduct/kickoff.md`:

- **Administrator-as-proxy.** The administrator (often you, the consultant, in early phases) provides organizational information on behalf of the client. Common in Phase 1 before stakeholders are fully looped in.
- **First session with a real SME.** A stakeholder you have not interviewed before. Higher kickoff overhead — establish rapport, set expectations, calibrate to their communication style.
- **Follow-up with a known SME.** Same stakeholder you have interviewed before. Lower kickoff overhead — pick up where you left off, reference prior decisions by name.
- **Multi-stakeholder.** Several SMEs in the same conversation. Manage turn-taking, capture cross-stakeholder disagreements explicitly, avoid letting one voice dominate the transcript.

Pick the variant that matches the session you are about to run. The conduct files tell you how each variant differs in practice.

During the session, the principle from `conduct/charter.md` that does the most work is §11.6.b — *inferences require positive support*. You do not put words in the stakeholder's mouth; you do not extrapolate from one statement to a conclusion the stakeholder did not endorse. When you summarize, you summarize what was actually said.

The transcript is captured in the form specified by the relevant interview guide: topic-grouped Q&A with inline Decision callouts. Decision callouts in the transcript become the seed for the Decisions you log at end of session.

## 8. Post-Session Capture

After the session ends, before the next session begins, capture everything that needs to enter the governance and methodology layers. This is where engagements quietly succeed or quietly fail. The work is unglamorous, and skipping it accumulates debt that becomes invisible until a later session asks "why did we do X?" and there is no record.

**Log the Session record.** Create the SES-NNN entry. Required fields:

- Identifier (`SES-NNN`), title, date, status (typically `Complete` for a finished session).
- Conversation reference (link or note pointing back to the conversation that produced this record).
- Topics covered (the topic headers from the transcript).
- Summary (one or two paragraphs).
- Decisions made (references to the DEC-NNN entries you are about to create, or have just created).
- Artifacts produced (Word docs, YAML files, database records — anything that came out of the session).

Session records are append-only. Get them right the first time.

**Log Decisions.** For each consequential decision made during the session, create a DEC-NNN entry. The full structure:

- Identifier (`DEC-NNN`).
- Title — a short noun phrase, e.g., "Domain code for Mentor Recruiting will be MR not REC".
- Date.
- Status — typically `Active` for a new decision.
- Context — the situation that prompted the decision, written in enough detail that a future reader without session context can follow.
- Decision — the decision itself, stated affirmatively.
- Rationale — why this and not the alternatives.
- Alternatives considered — what else was on the table, briefly.
- Consequences — what this decision now commits the engagement to.
- Supersedes / Superseded by — only filled in when a later decision overturns an earlier one.

A useful discipline: if you cannot write the rationale section in two or three sentences, you may not have made a real decision yet. You may have stated a preference. Push back to the session if needed.

**Update planning items.** Open questions that were resolved during the session become closed (with a reference to the resolving decision). New open questions raised during the session get new PI-NNN entries.

**Update Status.** A new version of Status if anything material changed: phase advanced, sub-step changed, blocker introduced or cleared, reading-order guidance updated for the next session. Status updates are versioned, not edited in place.

**Update the Charter — only if needed.** Most sessions do not change the Charter. The Charter changes when scope, principles, or current state shifts meaningfully. A decision to add a new domain to scope is a Charter event. A decision about which field type to use for a phone number is not. Err on the side of leaving the Charter alone unless something genuinely engagement-level changed.

**Render artifacts as appropriate.** If the session produced methodology-layer content (Domain Discovery Report, Entity PRD, Process document), generate the Word document from the database at this time, or note in the Status that rendering is pending.

**Update references.** Any new cross-references that emerged during the session — a decision that touches a process, a session that covered an entity, a domain that consumes a service — go into the references table now. References are cheap to create and pay for themselves later in impact analysis.

After post-session capture is complete, the database is the source of truth for what just happened. The conversation can be forgotten; the records suffice.

---

# Part IV — Methodology Phase Walkthrough

The 13 phases of the Document Production Process are defined authoritatively in `PRDs/process/CRM-Builder-Document-Production-Process.docx`. This Part does not duplicate that content. It annotates each phase with the governance-layer activity that accompanies it.

For every phase, the same structural questions get answered:

- **Goal.** What this phase produces.
- **Conduct guidance.** Which session-type variant typically applies; any phase-specific kickoff notes.
- **Methodology artifacts.** What gets created or updated at the methodology layer.
- **Governance touchpoints.** What gets created or updated at the governance layer.
- **Decisions typically encountered.** Common DEC-NNN topics at this phase.
- **Exit criterion.** When you can move to the next phase.

## 9. Phase 1 — Master PRD

**Goal.** Produce the Master PRD: organization overview, personas, key business domains with sub-domain groupings where applicable, cross-domain services, and system scope.

**Conduct guidance.** Administrator-as-proxy is typical in the first half of Phase 1 (you describe the organization to the AI before the client SME is engaged). First-session-with-real-SME applies once the client representative joins.

**Methodology artifacts.** `PRDs/{Implementation}-Master-PRD.docx`.

**Governance touchpoints.** This is the phase where the Charter and the Master PRD relationship is most salient. The Charter already exists from kickoff and describes the engagement; the Master PRD now describes the system. Expect a Decision logged here that captures the domain list and ordering — that domain list is referenced from both the Master PRD body (where it appears as part of the deliverable) and the Charter (where it appears as engagement scope).

Common references created here: the engagement Charter references the Master PRD; the Master PRD references each domain by code; the Session for Phase 1 references the domain list.

**Decisions typically encountered.** Domain list and codes. Domain processing order. Whether sub-domains are needed for any complex domain. The list of cross-domain services. Personas in the system and their backing entities.

**Exit criterion.** Master PRD is complete, the domain list is stable, and the consultant is ready to begin Domain Discovery for the first domain in the ordering.

## 10. Phase 2 — Domain Discovery

**Goal.** A Domain Discovery Report capturing the proposed domain list, candidate entities, and candidate personas — all in the client's own language. This is a working artifact, not a durable inventory.

**Conduct guidance.** First-session-with-real-SME or multi-stakeholder depending on who the client puts in the room. Domain Discovery is the first deeply client-facing phase. The conduct framework's listening rules (§§ on probing, on inferences requiring positive support) earn their keep here.

**Methodology artifacts.** `PRDs/Domain-Discovery-Report.docx`. Three sections: Domain List, Candidate Entity Inventory, Candidate Persona Inventory.

**Governance touchpoints.** Sessions for Domain Discovery should reference the Master PRD (governance Decision) and capture per-domain coverage. If the client introduces a candidate domain or entity that wasn't anticipated, log it as a Decision with status Active and rationale noting the client source — it may be deferred or merged in Phase 3, but the surfacing decision is itself a record.

**Decisions typically encountered.** Whether a candidate term refers to one entity or several. Whether a function described by the client is a domain or a process within a domain. Whether a persona named by the client is backed by an entity or is External.

**Exit criterion.** The Discovery Report has been produced and the consultant believes it accurately reflects what was said. Reconciliation with the client happens in Phase 3.

## 11. Phase 3 — Inventory Reconciliation

**Goal.** The durable Entity Inventory and Persona Inventory, agreed with the client. The Master PRD's domain list is updated in place if discovery changed it.

**Conduct guidance.** Multi-stakeholder is common — the entities and personas often span multiple SMEs' areas of expertise, and reconciliation works best when the relevant parties are in the same conversation. Follow-up-with-known-SME also applies for SMEs who participated in Phase 2.

**Methodology artifacts.** `PRDs/Entity-Inventory.docx`, `PRDs/Persona-Inventory.docx`, updated `PRDs/{Implementation}-Master-PRD.docx`.

**Governance touchpoints.** A Decision is logged for each material reconciliation result — entity merges, persona splits, terms renamed to match client vocabulary. References from the Inventory entries to the originating Discovery Report entries help future sessions trace where a term came from.

**Decisions typically encountered.** "Term X and term Y from Discovery refer to the same entity." "Persona X is actually two roles." "Term X is dropped because the client uses term Y for the same concept." Identifier assignments for each entity and persona.

**Exit criterion.** Both inventories are agreed, IDs are assigned, the Master PRD reflects any domain changes. Phase 4 can now begin for any domain.

## 12. Phase 4 — Domain Overview + Process Definition

**Goal.** Per-domain: a Domain Overview document and one Process document per business process within that domain. Processes are written from the perspective of the personas executing them.

**Conduct guidance.** Typically the SME for the domain. Multi-stakeholder when a process spans personas. The Process Definition interview guide governs this phase content; it cites entries from the conduct question library for tricky moments.

**Methodology artifacts.** `PRDs/{DOMAIN-CODE}/{DOMAIN-CODE}-Domain-Overview.docx` and `PRDs/{DOMAIN-CODE}/{PROCESS-CODE}-{process-name}.docx` per process.

**Governance touchpoints.** Sessions reference the Domain Overview and the processes covered. Decisions log per-process design choices: which entities each process touches, which fields are required, what the lifecycle is, where the process hands off to another domain or to a cross-domain service.

References explode in this phase. Each process touches one or more entities (process → entity references); is executed by one or more personas (process → persona references); may consume cross-domain services (process → service references). Capturing these as you go pays off in Phase 7 and in change-impact analysis later.

**Decisions typically encountered.** Process boundaries (where does this process end and the next one begin?). Field-level decisions surfaced by process work but deferred to Phase 5 (logged as planning items). Cross-domain dependencies (logged as references and surfaced for Phase 6 if a new service is needed).

**Exit criterion.** All processes for the domain have a Process document. The Domain Overview lists them with one-line descriptions.

## 13. Phase 5 — Entity PRDs

**Goal.** Full PRD per entity, authored *after* the processes that use the entity are drafted. The methodology principle is: processes show you which fields the entity actually needs.

**Conduct guidance.** Domain SME, possibly with technical input from someone who knows what data the organization actually stores.

**Methodology artifacts.** `PRDs/{DOMAIN-CODE}/{ENTITY-CODE}-Entity-PRD.docx`.

**Governance touchpoints.** Sessions reference the entity being defined and the processes that consume it. Decisions capture field-level choices: type, required/optional, defaults, enumerated values, relationships to other entities.

**Decisions typically encountered.** Field type choices (especially link vs. relationship — recall the schema rule that link relationships go only in the top-level `relationships:` block, never as `type: link` in `fields:`). Default values. Required-versus-optional. Enum values and whether new values should be addable by users at runtime.

**Exit criterion.** Every entity referenced by any in-scope process has an Entity PRD. Field tables are complete with two rows per field per the field-table convention.

## 14. Phase 6 — Cross-Domain Service Definition

**Goal.** For each cross-domain service identified in the Master PRD: a service process document per service process, and an overall Service PRD. Services are structurally parallel to domains.

**Conduct guidance.** The SME for the service, who may be different from any single domain's SME. Multi-stakeholder is common because services consume multiple domains' input.

**Methodology artifacts.** `PRDs/services/{SERVICE-NAME}/` containing service process documents and a Service PRD.

**Governance touchpoints.** Sessions reference the service and the domains that consume it. Decisions log service capabilities, ownership, and any entities the service itself owns. The references from domain processes to service processes (created during Phase 4) should be reconciled here — if Phase 4 referenced a service capability that does not exist as defined, that's a Phase 6 finding.

**Decisions typically encountered.** Which entities the service owns versus which domains own. Service capabilities and how domains consume them. Whether a capability called for in Phase 4 is in scope for the service.

**Exit criterion.** All cross-domain services named in the Master PRD have a Service PRD. Domain processes that consume services have validated references to actual service capabilities.

## 15. Phase 7 — Domain Reconciliation

**Goal.** Per-domain: a Domain PRD that consolidates the Domain Overview, the Entity PRDs, the process documents, and the cross-domain service usage into a single document for stakeholder review.

**Conduct guidance.** Multi-stakeholder is the norm — reconciliation surfaces cross-stakeholder inconsistencies, and resolving them in the room is faster than resolving them async.

**Methodology artifacts.** `PRDs/{DOMAIN-CODE}/{DOMAIN-CODE}-Domain-PRD.docx`.

**Governance touchpoints.** A heavy session-record phase. Decisions log every reconciliation finding — a field that two processes referenced inconsistently, an entity whose lifecycle is unclear, a service dependency that wasn't surfaced in Phase 4. The references built up across Phases 4–6 are the input to this phase.

**Decisions typically encountered.** Inconsistency resolutions. Where ambiguity was discovered and how it was resolved. Whether any process or entity needs to be revised before stakeholder review.

**Exit criterion.** The Domain PRD has been produced and the consultant believes it is ready for stakeholder review.

## 16. Phase 8 — Stakeholder Review

**Goal.** Client stakeholder sign-off on each Domain PRD.

**Conduct guidance.** This phase happens outside the AI-facilitated session structure. The consultant presents the Domain PRD, captures feedback, and brings revisions back into the methodology and governance layers.

**Methodology artifacts.** Approved Domain PRDs (no new document — the existing Domain PRD is annotated with approval status).

**Governance touchpoints.** Each stakeholder review session is captured as a Session record. Approval is a Decision (`Active`); rejection or revision is a Decision with the rationale and the planning items it generates.

**Decisions typically encountered.** Approval. Revision requirements. Out-of-scope requests the client raises (which typically become Charter amendments — added to Out of Scope unless the engagement is being rescoped).

**Exit criterion.** All Domain PRDs are approved or the engagement scope has been formally renegotiated through a Charter version bump.

## 17. Phase 9 — YAML Generation

**Goal.** Deployment YAML programs, one per domain, generated from the database.

**Conduct guidance.** Largely AI-driven; minimal stakeholder involvement. The YAML Generation guide in `PRDs/process/interviews/guide-yaml-generation.md` is the operating manual for this phase.

**Methodology artifacts.** `programs/{domain}.yaml` in the client repo.

**Governance touchpoints.** Sessions reference the domain and the entities/processes the YAML covers. Decisions log any methodology-to-YAML translation choices — particularly around the schema rules (link fields go in `relationships:`, the three EspoCRM features with no API write path get flagged for manual config).

This is the v2 principle of "renders, not authored copies" in operation. YAML is generated from the database, not authored independently. If the YAML and the database disagree, the database is correct and the YAML is regenerated.

**Decisions typically encountered.** Manual-configuration callouts (the three known gaps: saved views, duplicate-check rules, workflows). Engine-specific translations that the schema cannot fully express.

**Exit criterion.** YAML files exist for all in-scope domains and pass `validate_program()`.

## 18. Phase 10 — CRM Selection

**Goal.** A CRM Evaluation Report documenting which CRM engine will be deployed and why. For engagements where the engine is predetermined, this phase is a brief confirmatory document; for engagements with multiple candidates, it is a full evaluation.

**Conduct guidance.** Administrator-driven, with stakeholder input on cost, hosting, and policy considerations.

**Methodology artifacts.** `PRDs/CRM-Evaluation-Report.docx`.

**Governance touchpoints.** A Decision logs the selected engine, the rationale, and the alternatives considered. The Charter may be amended if the engine choice changes engagement scope (e.g., a SaaS engine eliminates self-hosting work).

**Decisions typically encountered.** Engine selection. Hosting model. Cost commitments.

**Exit criterion.** The engine is chosen and the engagement is ready to deploy.

## 19. Phase 11 — CRM Deployment

**Goal.** A deployed CRM instance.

**Conduct guidance.** Administrator-driven, no stakeholder-facing AI session. The desktop application's Deployment tab is the operating surface.

**Methodology artifacts.** A running CRM instance with credentials persisted in the application's per-client SQLite store.

**Governance touchpoints.** A Session record captures the deploy run. Decisions log any deployment-time decisions (instance sizing, region, version, backup policy).

**Decisions typically encountered.** Instance configuration. Credentials and secret management. Recovery and backup posture.

**Exit criterion.** The instance is running and accessible.

## 20. Phase 12 — CRM Configuration

**Goal.** The deployed instance is configured to match the YAML programs.

**Conduct guidance.** Tool-driven. The application's Configure engine reads the YAML and applies it to the instance.

**Methodology artifacts.** Configured CRM instance. `.log` and `.json` reports per Configure run.

**Governance touchpoints.** Sessions capture each Configure run. Decisions log any manual-configuration items that the Configure engine flagged as `MANUAL CONFIG REQUIRED` — these become planning items until a human applies them through the admin UI.

**Decisions typically encountered.** Manual config completion (saved views, duplicate-check rules, workflows). Any post-deploy refinements.

**Exit criterion.** The instance configuration matches the YAML programs and the manual config items are tracked as planning items or as completed.

## 21. Phase 13 — Verification

**Goal.** A Verification Spec generated from the database, used to confirm the deployed instance matches the requirements.

**Conduct guidance.** Tool-generated; reviewed by the consultant.

**Methodology artifacts.** Verification Spec, verification reports.

**Governance touchpoints.** A Session captures the verification run. Decisions log any discrepancies between requirements and reality, and the resolution path for each.

**Decisions typically encountered.** Verification failures and their causes (YAML mismatch, manual config not completed, requirement misinterpretation). Whether a failure requires a YAML regeneration, a database correction, or a requirements revision (with appropriate methodology-layer rework).

**Exit criterion.** Verification passes for all in-scope requirements, or the unresolved items are tracked as planning items with clear ownership.

---

# Part V — Operations

## 22. Versioning and Supersession

Two governance objects are versioned: Charter and Status. The rest are not, but their history is recoverable through the change log.

**Charter and Status versioning.** Every material change produces a new version row. The active version is identified by `is_current: true`. Prior versions are preserved. The version label (`0.1`, `0.2`, `1.0`) is set when the version is committed. Versioning is intrinsic to these two objects — you do not "edit" a Charter, you create a new version of it.

The discipline question is: when does a change deserve a new version, versus when does it deserve no Charter or Status change at all?

For Charter: when scope, principles, or current state shifts meaningfully. Adding a new domain to scope is a Charter event. A new manual config item from Phase 12 is not — it's a planning item.

For Status: when phase advances, sub-step changes, a blocker is introduced or cleared, or the reading-order guidance for the next session updates. Most sessions update Status; not all sessions update Charter.

**Decision supersession.** Decisions are not deleted. When a later decision overturns an earlier one, both rows persist and the supersession relationship is recorded in the `supersedes` and `superseded by` fields. The earlier decision moves to status `Superseded`. A reader navigating from the superseded decision to the superseding one (or vice versa) can follow the relationship in either direction.

A practical rule: if you find yourself wanting to edit a Decision's body, you probably want a superseding Decision instead. The exception is administrative corrections (typos, fixing a broken reference) — those can be edited in place, with the change log entry capturing what changed.

**Session append-only.** Session records are never edited. If a session's outcome turned out to be wrong (the decision logged was reversed in a subsequent session), the reversal is a new Session and Decision, not a retroactive edit to the original.

**Change log discipline.** Every governance object should have a change-log mechanism appropriate to its versioning model: Charter and Status have explicit version tables; Decisions and Sessions use field-level audit (created_at, updated_at) plus supersession relationships; planning items, topics, risks, and references rely on the database's row-level history.

## 23. Cross-References and Impact Analysis

The universal references pattern (`source_type`, `source_id`, `target_type`, `target_id`, controlled-vocabulary `relationship`) is the foundation for understanding how anything in the database touches anything else.

The relationship vocabulary is defined in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`. The set of valid relationships is `REFERENCE_RELATIONSHIPS`, and the allowed `(source_type, target_type)` pairings are derived from `_kinds_for_pair`. The references-create dialog in the desktop UI drives its cascading filters from this same vocabulary, so end-to-end compliance is strict.

**Common reference patterns to capture as you go:**

- Decision → Topic (this decision was about this topic).
- Session → Decision (this session produced this decision).
- Session → Entity (this session covered this entity).
- Session → Process (this session covered this process).
- Decision → Entity (this decision changed something about this entity).
- Process → Entity (this process touches this entity).
- Domain → Process (this process belongs to this domain).
- Process → Service (this process consumes this service).
- Persona → Process (this persona executes this process).

**Impact analysis queries.** Once references are in place, "what does this touch?" becomes a uniform query regardless of the starting object type. Examples:

- "What decisions have been made about Entity X?" → references where `target_type = entity, target_id = X, source_type = decision`.
- "What processes consume Service Y?" → references where `target_type = service, target_id = Y, source_type = process`.
- "What sessions touched Domain Z?" → references where `target_type = domain, target_id = Z, source_type = session`.

The discipline is to create references at the point the relationship is established, not "when there's time later." A reference created during a Phase 4 process-definition session is worth more than the same reference reconstructed during a Phase 7 reconciliation session.

## 24. Rendering from the Database

Three classes of artifact are rendered from the database, not authored:

- **Word documents** for stakeholder review (Master PRD, Domain Discovery Report, Entity Inventories, Domain Overviews, Process documents, Entity PRDs, Service PRDs, Domain PRDs).
- **YAML programs** for deployment.
- **Test cases** for verification.

The rendering model has two principles.

**The database is authoritative.** If the rendered output and the database disagree, the database is correct. The Word document is the disposable rendering; the database row is the durable truth. If a stakeholder marks up a Word document with changes, those changes are applied to the database, and the document is re-rendered.

**Rendering happens at known points, not continuously.** Render when an artifact is needed for review or for the next phase. Do not render continuously and do not version rendered outputs separately from the source.

The practical consequence: if you find yourself editing a rendered Word document directly to fix something, you are creating drift. Edit the database, re-render.

---

# Part VI — Closing and Reference

## 25. Closing an Engagement

An engagement ends when its in-scope deliverables are complete, accepted, and the configured CRM is operating to the client's satisfaction. The closing checklist:

- **Final Charter version.** A closeout version of the Charter sets Current State to "Engagement complete" and lists final outcomes against original scope.
- **Final Status.** A closeout Status records the final phase, any unresolved items intentionally left open (typically as a deferred-work register for a future engagement), and reading-order guidance for anyone who picks the engagement up later.
- **Open planning items, resolved or deferred.** Every open planning item is either resolved (with a referencing Decision) or explicitly deferred to a future engagement (with rationale).
- **Final session.** A closeout Session captures the closeout meeting and any final decisions.
- **Database archive.** The engagement database is the system of record; it is archived per the engagement's data retention policy. (PI-β removed the former `db-export/` JSON snapshot tree — there is no JSON export to commit at closeout; the git-tracked governance trail is the close-out payloads and deposit-event logs.)
- **Deliverables inventory.** A list of every artifact produced during the engagement — Word documents, YAML files, the deployed CRM instance — with their final locations. This becomes the handover document.

The Charter and Status final versions, combined with the deliverables inventory, are sufficient to bring a future consultant up to speed on what was done, what was decided, and where to find everything.

## 26. Quick Reference

### Governance objects

| Object | Cardinality | Versioned? | Identifier |
|--------|-------------|------------|------------|
| Charter | Singleton | Yes | Version-numbered |
| Status | Singleton | Yes | Version-numbered |
| Decisions | Many | No (supersession instead) | `DEC-NNN` |
| Sessions | Many, append-only | No | `SES-NNN` |
| Planning items | Many | No | `PI-NNN` |
| Topics | Many | No | Prefixed string |
| Risks | Many | No | Prefixed string |
| References | Many | No | Prefixed string |

### Methodology objects (separate from governance)

Domains, cross-domain services, entities, fields, processes, process steps, personas, requirements, manual-config items, test specifications.

### Identifier conventions

- Governance entities with prefixed identifiers (`DEC-NNN`, `SES-NNN`, etc.) require the identifier to be computed client-side before a direct-API write. Helpers like `compute_next_session_identifier(client.list_sessions())` handle this in the desktop UI. Direct REST or MCP writes must compute the identifier and supply it in the POST body.
- Methodology entities use the human-readable-first format everywhere: *Client Intake (MN-INTAKE)*, never *MN-INTAKE: Client Intake*.

### Reading without MCP (REST API)

When MCP is unavailable, read the governance objects live from the REST API at `http://127.0.0.1:8765` (name the engagement with the `X-Engagement` header; unwrap `.data` from the `{data, meta, errors}` envelope). (PI-β removed the former `db-export/` JSON snapshots; there is no committed file copy to read.)

- `GET /charter`, `/charter/versions` — Charter and its versions.
- `GET /status`, `/status/versions` — Status and its versions.
- `GET /decisions`, `/decisions/<id>` — decisions.
- `GET /sessions`, `/sessions/<id>` — sessions.
- `GET /planning-items` — open and closed planning items.
- `GET /topics` — topics.
- `GET /risks` — risks.
- `GET /references?...`, `/references/touching/<type>/<id>` — references.

### Phase-to-conduct mapping

| Phase | Likely session-type variant | Primary conduct documents |
|-------|----------------------------|---------------------------|
| 1 Master PRD | Administrator-as-proxy → first-with-SME | `conduct/*`, `interview-master-prd.md` |
| 2 Domain Discovery | First-with-SME or multi-stakeholder | `conduct/*`, `interview-domain-discovery.md` |
| 3 Inventory Reconciliation | Multi-stakeholder or follow-up | `conduct/*`, `interview-inventory-reconciliation.md` |
| 4 Domain Overview + Process Definition | Domain SME, sometimes multi-stakeholder | `conduct/*`, `interview-process-definition.md`, `guide-domain-overview.md` |
| 5 Entity PRDs | Domain SME plus data owner | `conduct/*`, `interview-entity-prd.md` |
| 6 Cross-Domain Service Definition | Service SME, often multi-stakeholder | `conduct/*`, `interview-service-process-definition.md`, `guide-service-reconciliation.md` |
| 7 Domain Reconciliation | Multi-stakeholder | `conduct/*`, `guide-domain-reconciliation.md` |
| 8 Stakeholder Review | Outside AI-facilitated structure | (none — direct client engagement) |
| 9 YAML Generation | AI-driven | `guide-yaml-generation.md` |
| 10 CRM Selection | Administrator + stakeholders | `guide-crm-evaluation.md` |
| 11 CRM Deployment | Administrator | (application Deployment tab) |
| 12 CRM Configuration | Tool-driven | (Configure engine) |
| 13 Verification | Tool-generated, consultant-reviewed | (Verification Spec) |

### MCP tools (illustrative; see the v2 storage system for the full surface)

- `get_current_charter`
- `get_current_status`
- `list_recent_sessions(limit=N)`
- `get_decision(<id>)`
- `list_decisions_for_session(<id>)`
- Creation and update tools for each governance entity type.

---

## Notes for Future Versions of This Guide

- The 13-phase Document Production Process may evolve to the 5-phase evolved methodology under research at `PRDs/process/research/evolved-methodology/`. Part IV will need rework when that transition happens. Parts I, II, III, V, and VI are methodology-agnostic and should survive.
- The MCP tool surface listed in §26 is illustrative and will need to be aligned with the actual tool registry once a v2 MCP reference document exists.
- The relationship vocabulary in §23 should eventually be auto-rendered from `vocab.py` rather than narrated, to avoid drift.
- A companion **Application User Guide** (Option C from the scoping decision that produced this guide) would cover the v2 desktop application's UI tour. It is deliberately not included here.
- A companion **Governance Operations Manual** (Option A from the same scoping decision) — a methodology-agnostic version of Parts I, II, III, and V — could be extracted from this guide if the v2 governance stack is reused for non-CRM engagements.
