# CRMBuilder V2 — Object Executive Summary

Generated 2026-08-30 from `crmbuilder-v2/src/crmbuilder_v2/access/models.py` and the repository
`_IDENTIFIER_PREFIX` constants. One row per stored object, grouped by the role it plays.

## 1. Engagement governance (the "how we work" spine)

| Object | Prefix | Executive summary |
|---|---|---|
| Charter | — | Singleton, versioned document stating the engagement's purpose and scope. `is_current=True` marks the live row; prior versions are retained. |
| Status | — | Versioned narrative snapshot of the engagement's overall state — current phase, direction, what recently shipped, notable open work. Since DEC-954 (PI-433) each version is generated from stored records (in-flight projects and releases, resolved and open planning items, recent sessions, code version) with an optional human narrative; read for orientation, not by code. Same versioning shape as Charter. |
| Decision | DEC | A dated, statused record of one choice made — context + the decision itself + an executive summary. The audit trail for *why* the design/process looks the way it does. |
| Planning Item | PI | The unit of governed work. Typed (feature, fix, process, …), statused (Open → Resolved/Deferred/Cancelled), carries area labels for parallel-agent partitioning and a `resolution_reference`. Every code commit traces to one. |
| Requirement | REQ | One testable statement of what the CRM (or CRMBuilder) must do. Statused, prioritized, with origin (`human_defined` / `ai_derived`) and a review state. Requirement-first: no PI/code without one. |
| Risk | RSK | A probability × impact concern with a status (Open/Mitigated/Accepted/Closed). |
| Topic | TOP | Hierarchical knowledge-organizing node (parent/child). Groups the canonical corpora, e.g. TOP-013 governance recording rules. |
| Project | PRJ | A coherent line of related conversations/work — the container above PIs. |
| Engagement Area | — | User-defined work area within an engagement (UI, API, DB, …); drives PI area labels, locks, and planning claims. |
| Finding | FND | A cross-area coherence problem discovered during review/reconciliation. |
| Session | SES | One discrete unit of communication in any medium (Claude Code, chat, meeting, …). |
| Conversation | CNV | A focused topical thread inside a Session. |
| Reference | — | Universal polymorphic link between any two records (`relates_to`, `implements`, `supersedes`, …) — the graph edges. Vocabulary in `vocab.py`. |
| Commit | — | A git commit captured as a governance record, tied to its `Governed-By` PI. |
| Change Log | — | Append-only log emitted by every mutating access-layer call — the system's own audit trail. |
| Term | TERM | Glossary entry. No new terminology without approval; every term lives here. |

## 2. Methodology / design records (the "what the CRM is" content)

| Object | Prefix | Executive summary |
|---|---|---|
| Domain | — | A Phase 1 Domain Inventory member — a functional area of the client's business (e.g. Mentoring, Fundraising). |
| Entity | — | One CRM-modeled noun (Contact, Engagement, Session…) with kind, status, and base type. |
| Field / Field Option | — | One attribute on an entity — type, format, display, required/visible semantics, supplied-by, derived/formula spec. Field Option is one allowed value on a choice field. |
| Association | — | Engine-neutral entity-to-entity link (the relationship model). |
| Persona / Participant | — | Persona is a role/actor in the client org; Participant is the real person backing it in the engagement. |
| Process | — | A Phase 1 Prioritized Backbone member — a business process the CRM supports. |
| Service | — | A cross-domain service in the target system. |
| CRM Candidate | — | A Phase 1 Initial CRM Candidate Set member — a thing that *might* become an entity. |
| Rule | — | Condition-carrying gate: required-when / visible-when / valid-when. |
| View | — | A list view (saved filter) of an entity. |
| Automation | — | Trigger / condition / action rule (workflow). |
| Dedup Rule / Message Template | — | Duplicate-detection rule; notification/email template. |
| Layout | LAY | Engine-neutral screen layout for an entity. |
| Role / Team | ROL / TM | Security roles and teams. |
| Field Permission Rule / Field Visibility Rule | — | (role × field) → permission level; (role × field) → visible?. |
| Filtered Tab | FTB | Navigation tab scoped by a filter. |
| System Setting / System Setting Value | SET | A CRM system setting the design governs, and the value each instance is declared to hold. |
| Engine Override | — | Sparse per-engine (EspoCRM vs. other) override of a neutral design record. |
| Manual Config | — | A discrete config item the deploy cannot apply via API — the operator's punch list. |
| Test Spec | — | A verification specification with run outcomes. |
| Migration Mapping | — | Keep/transform disposition and its migration obligation at entity or field level. |

## 3. Source-system mapping (legacy → new CRM)

| Object | Prefix | Executive summary |
|---|---|---|
| Source Mapping (+ Target, Join) | SMG | Entity-level decision mapping a source-system object to design entities, with the declared join key. |
| Field Mapping (+ Translation) | FMP | Field-level mapping decision, optionally with a translation rule. |
| Association Mapping | AMP | Relationship-level mapping. |
| Value Mapping | — | Enum value → value mapping. |
| Mapping Candidate | — | Auto-discovered, pre-decision candidate awaiting a human disposition. |

## 4. Instances & deployment (the live-system side)

| Object | Executive summary |
|---|---|
| Instance | An engagement-scoped connection to a live CRM (URL, credentials via Fernet-encrypted Secret Value). |
| Instance Membership | Which canonical design objects are deployed to which instance. |
| Instance Deploy Config | Provisioning/SSH config for an instance. |
| Provider Credential | Infrastructure-provider token (e.g. DigitalOcean). |
| Deploy Run | One recorded provisioning job execution. |
| Publish Run | One recorded push of design to a target instance. |
| Reconcile Transaction | Append-only log of one reconcile (design ⇄ live) action. |
| Secret Value | Ciphertext for an opaque secret reference. |

## 5. Release & orchestration pipeline (multi-agent delivery)

| Object | Executive summary |
|---|---|
| Workstream | A single delivery phase of one Planning Item. |
| Work Task | A single-area execution unit within a Workstream; Task Transition logs every status change. |
| Release | The pipeline keystone tying requirements → reconciled change set → area specs → runs. |
| Release Demand | A structured requirement→design delta feeding reconciliation. |
| Reconciliation Conflict | A same-facet contradiction between requirements' demands. |
| Release Change Set | The persisted, reviewable reconciled change set. |
| Release Signoff / Review Signoff | Recorded human sign-off at a pipeline stage / on requirements review. |
| Area Spec | Per-(release, area) implementation + testable spec. |
| Artifact Version | Versioned, release-tied change spine. |
| Release Run | One run outcome of a release. |
| Resource Lock / Planning Area Claim / Area Reopen | Concurrency controls: file/resource check-out, single-threaded-by-area planning claim, in-lane reopen of a frozen area. |
| Work Ticket / Close-Out Payload / Deposit Event | Single-use kickoff seed document; single-use state-write package; the durable record of applying one. |
| Cost Event / Budget Approval / Pipeline Event | AI spend per model call; pre-launch budget decision; durable pipeline-progress/agent-activity event. |
| Utilization Evidence | Append-only snapshot backing a baseline candidate decision. |
| Identifier Reservation | Server-side hold on a block of prefixed IDs for parallel writers. |

## 6. Cross-engagement registry & knowledge (shared, not tenant-scoped)

| Object | Prefix | Executive summary |
|---|---|---|
| Governance Rule | GVR | Binding operating rule (e.g. requirement-first, Governed-By trailer). The SSoT for how sessions must behave. |
| Preference | PRF | Advisory interaction/UI/workflow preference. |
| Lesson | LSN | Operational gotcha or how-to, with provenance edges. |
| Learning | LRN | Evidence-tagged accumulated learning from agent runs. |
| Reference Pointer | RFP | Pointer to an external resource (server, dashboard, doc, credential location). |
| Reference Entry / Reference Book (+ Version) | RFE | Reference-library record; long-lived versioned reference document. |
| Agent Profile / Agent Profile Binding | AGP | ADO agent definition keyed to (area × tier); its registry binding. |
| Skill | SKL | Shared reusable capability definition for agents. |
| Catalog (Entity, Attribute, Relationship, Source, Synonym, Presence…) | — | Industry-neutral catalog of known CRM entities/attributes/relationships and which systems have them — the seed for candidate discovery. |
| Engagement / Principal / API Token / Role Assignment | ENG | Tenant row; authenticated human or AI actor; hashed bearer token; principal's role on an engagement (RBAC). |
