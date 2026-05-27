# CRMBuilder Phase 2 Domain Discovery — Candidate Inventory

| Field | Value |
|---|---|
| Engagement | CRMBUILDER (dogfood) |
| Phase | Phase 2 — Domain Discovery |
| Methodology | `PRDs/process/interviews/interview-domain-discovery.md` v1.1, conducted per Option C.1 (DEC-319) |
| Status | Working candidate inventory — not yet promoted to V2 records (see PI-092) |
| Session | SES-098 |
| Last Updated | 05-27-26 |

> **Working artifact.** This document is the durable Phase 2 output for the CRMBUILDER dogfood engagement under the Option C.1 session shape (DEC-319). It captures candidate domains, entities, and personas surfaced during SES-098, plus the Phase 2 interview transcript organized by topic. Candidates are not yet promoted to V2 Domain/Persona/Entity records — that work is captured in PI-092 pending the V2 close-out pipeline's methodology ingestion path. Until that promotion completes, this document is the source-of-truth for CRMBuilder's Phase 2 inventory.

---

## Change Log

| Version | Date | Description |
|---|---|---|
| 0.1 | 05-27-26 | Initial inventory authored during SES-098. 14 candidate domains, 9 candidate personas, ~40 candidate entities across domains. All 14 domains pass Rule 2.1. Rule 2.2 applied to all 9 personas (2 resolved, 7 TBD pending PI-091). |

---

## Working Mission (DEC-320)

The mission used to apply Rule 2.1 (Domain Validation Test) in this Phase 2:

> CRM Builder is an application framework for conducting the end-to-end process of designing, selecting or building, provisioning, configuring, and verifying a CRM system for any organization. The framework provides the methodology, AI-assisted interview surface, structured requirements capture, governance tracking, platform-selection and custom-build logic (recommend an existing CRM platform, extend an existing platform with custom functionality, or build a custom CRM from scratch), and declarative deployment-and-verification pipelines that hold the engagement together from initial discovery through deployed system.

This revises V1 PRD §1.1's tool-framing to an application-framework framing and adds the three-mode platform-or-build option (existing, extend, from-scratch). See DEC-320 for full rationale.

---

## 1. Candidate Domain List

Fourteen candidate domains identified for the CRMBUILDER engagement. All pass Rule 2.1 against the working mission above.

### Candidate Domain 1 — Methodology Authoring

**Description.** Defining and evolving CRMBuilder's process itself: interview guides, conduct rules, the Master CRMBuilder PRD, the authoring standards, the 13-phase process document. The "CRMBuilder uses its own process to define itself" dogfood activity.

**Mission tie-in.** "The framework provides the methodology…" — methodology authoring is the work of creating and evolving what the framework provides.

**Source.** Master CRMBuilder PRD §III (iterative drafting principle); dogfood premise throughout the corpus.

**Rule 2.1 result.** Pass (CRMBuilder-internal-only — see DEC-323). Without ongoing methodology authoring, the framework stagnates and stops evolving. For the CRMBUILDER engagement this is a per-engagement activity. For external client engagements, the client consumes methodology rather than authoring it; this domain is absent from external engagement domain sets.

### Candidate Domain 2 — Engagement Governance

**Description.** Project-management layer for any engagement: charter, sessions, decisions, planning items, references, work tickets, reference books, close-out payloads, deposit events, workstreams, topics, risks, conversations. Methodology-agnostic — would look essentially the same for any consulting engagement that benefits from this kind of tracking.

**Mission tie-in.** "…governance tracking… that hold the engagement together."

**Source.** Master CRMBuilder PRD §3 (governance layer of the two-layer model); V2 governance schema as implemented.

**Rule 2.1 result.** Pass. Without engagement governance, engagements can't be tracked, multi-session work loses continuity, decisions evaporate, and the engagement can't deliver the framework's promise of holding things together.

### Candidate Domain 3 — Requirements Capture

**Description.** Interview-driven discovery of the client's domains, sub-domains, processes, process steps, personas, entities, fields, requirements, manual config items, cross-domain services, test specifications. The methodology layer's authoring loop — turning stakeholder testimony into structured, deployable specs.

**Mission tie-in.** "…structured requirements capture…"

**Source.** Master CRMBuilder PRD §3 (methodology layer); 13-phase Document Production Process phases 1–7; V1 PRD §1 phase 1 Discovery + phase 2 Entity Definition.

**Rule 2.1 result.** Pass. Without requirements capture, no client's CRM gets designed; the framework has no input to its later phases.

### Candidate Domain 4 — CRM Platform Decision

**Description.** Evaluating captured requirements against the three modes — recommend an existing CRM platform, extend an existing platform with custom functionality, or build a custom CRM from scratch. Per-engagement matching of client requirements to the inventory maintained in #10.

**Mission tie-in.** "…platform-selection and custom-build logic (recommend an existing CRM platform, extend an existing platform with custom functionality, or build a custom CRM from scratch)…"

**Source.** Revised mission (DEC-320); 13-phase process Phase 9 (CRM Selection); V1 PRD §1 phase 3.

**Rule 2.1 result.** Pass. Without platform decision, the framework can't recommend a path forward for any client; the deployment phases have nothing to deploy against.

### Candidate Domain 5 — CRM Deployment

**Description.** Provisioning the chosen CRM for a client. SSH-based EspoCRM deployment is implemented in V1 (`espo_impl/`, `automation/core/deployment/`); SaaS account provisioning for cloud CRMs and bring-your-own credential capture are speculative. Consumes the pattern catalog from #11.

**Mission tie-in.** "…provisioning… declarative deployment… pipelines that hold the engagement together…"

**Source.** V1 PRD §1 phase 4; V1 codebase under `automation/core/deployment/`.

**Rule 2.1 result.** Pass. Without deployment, no CRM ever gets provisioned for any client; the framework can't deliver an actual working system.

### Candidate Domain 6 — CRM Configuration

**Description.** Translating captured requirements into platform-specific declarative configuration. For EspoCRM today: YAML programs interpreted into REST API calls (`espo_impl/core/`). For other platforms: equivalent translation pipelines. Configuration patterns are intrinsic to this domain rather than living in a paired knowledge-substrate domain (see DEC-322).

**Mission tie-in.** "…configuring… declarative… pipelines…"

**Source.** V1 PRD §1 phase 5; V1 codebase under `espo_impl/core/`.

**Rule 2.1 result.** Pass. Without configuration, a deployed CRM is empty and serves nothing; the framework's promise of producing a working system fails.

### Candidate Domain 7 — CRM Verification

**Description.** Re-checking deployed configuration against spec. Audit primitives (verify the live CRM matches the YAML); reconciliation primitives; discrepancy reporting.

**Mission tie-in.** "…verifying… declarative… verification pipelines…"

**Source.** V1 PRD §1 phase 6; V1 codebase audit and verify paths.

**Rule 2.1 result.** Pass. Without verification, drift between spec and reality is invisible; the framework can't guarantee its own deliverable is correct.

### Candidate Domain 8 — Custom CRM Build

**Description.** Building custom CRM functionality. Two sub-modes: extending an existing CRM platform with custom modules, or building a CRM from scratch. Not yet implemented; speculative.

**Mission tie-in.** "…build a custom CRM from scratch… extend an existing platform with custom functionality…" (added in DEC-320).

**Source.** Revised mission (DEC-320); no V1 implementation.

**Rule 2.1 result.** Pass. The revised mission commits the framework to the three-mode option. Without Custom CRM Build, the third mode ("build from scratch") and the second ("extend") have no operational home.

### Candidate Domain 9 — AI-Assisted Interview Surface

**Description.** The AI conducting interviews via chat-UI-on-API or MCP — capturing responses, writing records, navigating the methodology in real time. Includes the new chat-UI Python client work (PI-052) and the MCP tool surface for Claude Desktop.

**Mission tie-in.** "…AI-assisted interview surface…"

**Source.** Revised mission (DEC-320); existing MCP server; PI-052 chat-UI workstream.

**Rule 2.1 result.** Pass. Without the AI-assisted interview surface, interviews fall back to human-only conduct, which the framework's positioning explicitly rejects. The mission names this dimension.

### Candidate Domain 10 — CRM Inventory & Functional Analysis

**Description.** Ongoing research and cataloging of available CRM platforms — features, capabilities, costs, pricing tiers, limitations. Happens whether or not any client engagement is running. Feeds #4 CRM Platform Decision with the substrate of what platforms exist and what they can do.

**Mission tie-in.** Substrate for "…platform-selection…" — without an up-to-date inventory, platform recommendations can't be made.

**Source.** Doug-surfaced in Topic 2.

**Rule 2.1 result.** Pass. Without ongoing inventory work, recommendations become stale and the platform decision pipeline degrades.

### Candidate Domain 11 — CRM Deployment Pattern Inventory

**Description.** Ongoing research and codification of deployment patterns for each supported CRM platform — SSH-to-Droplet for EspoCRM, SaaS account provisioning, bring-your-own credential flows, containerized deployments. Feeds #5 CRM Deployment with the substrate of how each platform gets provisioned.

**Mission tie-in.** Substrate for "…provisioning… declarative deployment… pipelines…"

**Source.** Doug-surfaced in Topic 2.

**Rule 2.1 result.** Pass. Without pattern inventory work, new CRM deployment targets can't be added; the deployment domain stays locked to whatever platforms were studied in the past.

### Candidate Domain 12 — Configuration Artifact Generation

**Description.** Rendering V2 records into deployment-ready artifacts. For EspoCRM today: YAML programs. For other platforms in future: platform-specific equivalents. Platform-neutral name (the 13-phase process calls this "YAML Generation" in EspoCRM-specific terms).

**Mission tie-in.** Connects "…structured requirements capture…" to "…declarative deployment… pipelines…" — the rendering step in between.

**Source.** 13-phase process Phase 8 (YAML Generation); V1 implementation of YAML programs against the V2 schema (currently manual).

**Rule 2.1 result.** Pass. The "declarative deployment pipelines" require a deployment spec. If artifact generation stopped, the framework would lose its "from initial discovery through deployed system" pipeline.

### Candidate Domain 13 — Document Rendering

**Description.** Rendering V2 records into human-readable deliverables — PRDs, reports, methodology documents. V1 has `tools/docgen/` for this; the Master CRMBuilder PRD references "rendered document artifact" pipeline as future work. Symmetric renderer to #12, with humans (not deployment pipelines) as the consumer.

**Mission tie-in.** Supports "…that hold the engagement together from initial discovery through deployed system…" — Stakeholder Review (Phase 7 of the 13-phase process) requires reviewable artifacts. Without Document Rendering, stakeholders would review raw V2 records.

**Source.** V1 `tools/docgen/`; Master CRMBuilder PRD's rendering-pipeline references; 13-phase process Stakeholder Review.

**Rule 2.1 result.** Pass (on the strength of the Stakeholder Review dependency — see DEC-324 commentary).

### Candidate Domain 14 — Engagement Setup

**Description.** Initializing a new engagement: creating the V2 engagement record, bootstrapping Charter, seeding governance schema, configuring the engagement's identity. The Master CRMBuilder PRD §6.2 defers these "mechanics to be documented in a subsequent draft."

**Mission tie-in.** "…from initial discovery…" — discovery can't happen if the engagement hasn't been set up.

**Source.** Master CRMBuilder PRD §6.2 explicit deferral; V2's existing engagement-record machinery.

**Rule 2.1 result.** Pass. Without engagement setup, no engagement can start; the entire downstream pipeline has nothing to operate on.

---

## 2. Candidate Entity Inventory

Entities grouped by primary domain. Source codes: **V2** = currently in V2 schema; **V1** = currently in V1 codebase; **spec** = speculative, no implementation yet.

### Domain 1 — Methodology Authoring

Entities TBD. Most current methodology-authoring activity is recorded using Engagement Governance entities (Decision, Session, Planning Item). The domain may or may not need its own entity set; resolution deferred.

### Domain 2 — Engagement Governance

All entities listed are V2.

- **Engagement** (implicit container; V2 schema represents it via charter + database location).
- **Charter** (versioned).
- **Status** (versioned).
- **Decision**.
- **Session**.
- **Planning Item**.
- **Topic**.
- **Risk**.
- **Reference** (the universal references table).
- **Conversation**.
- **Work Ticket**.
- **Reference Book** (versioned).
- **Close-Out Payload**.
- **Deposit Event**.
- **Workstream**.

### Domain 3 — Requirements Capture

- **Domain** (V2).
- **Sub-Domain** (V2; reference via parent_domain field).
- **Process** (V2).
- **Process Step** (V2).
- **Entity** (V2; the client's methodology-layer entity records, which describe the entity types the client's deployed CRM will track).
- **Field** (V2).
- **Persona** (V2).
- **Requirement** (V2).
- **Manual Config Item** (V2).
- **Cross-Domain Service** (V2).
- **Test Specification** (V2).
- **Pattern Library Entry** (spec; surfaced in CBM-redo work; not yet in V2 schema). Disambiguated from Deployment Pattern (#11) by the "library" qualifier per DEC-324.

### Domain 4 — CRM Platform Decision

- **CRM Candidate** (partial V2 — `crm_candidates.json` snapshot exists; full schema TBD).
- **Evaluation Criterion** (spec).
- **Evaluation Score** (spec).
- **Recommendation Report** (spec).

### Domain 5 — CRM Deployment

All entities are V1.

- **Instance**.
- **Deployment Run**.
- **Deployment Config** (the `InstanceDeployConfig` table).
- **Hosting Provider Config**.
- **Server / Droplet**.
- **Credentials** (keyring-backed; opaque ref IDs stored in DB).

### Domain 6 — CRM Configuration

All entities are V1.

- **YAML Program**.
- **Field Definition** (in YAML).
- **Layout**.
- **Relationship**.
- **Entity Definition** (in YAML — the client-layer entity expressed for deployment).
- **Import Spec**.
- **Configuration Run**.
- **Configuration Report**.

**Configuration Pattern** is intrinsic to this domain rather than a first-class entity (DEC-322 and DEC-324).

### Domain 7 — CRM Verification

All entities are V1.

- **Verification Run**.
- **Verification Report**.
- **Audit Result**.
- **Discrepancy**.

### Domain 8 — Custom CRM Build

Entities TBD (domain is unimplemented). Speculative candidates: Custom Module, Build Specification, Integration Point, Module Component.

### Domain 9 — AI-Assisted Interview Surface

- **Conversation** (V2; the existing entity tracks AI sessions).
- **Tool Call** (implicit in code; not a first-class entity).
- **Tool Result** (implicit in code; not a first-class entity).
- **MCP Connection** (implicit in code; not a first-class entity).

### Domain 10 — CRM Inventory & Functional Analysis

Entities TBD (no implementation yet). Speculative candidates: CRM Platform Entry, Feature, Capability, Pricing Tier, Platform Limitation.

### Domain 11 — CRM Deployment Pattern Inventory

Entities TBD (no implementation yet). Speculative candidates: **Deployment Pattern**, Hosting Pattern, Auth Flow Pattern.

### Domain 12 — Configuration Artifact Generation

All entities are spec.

- **Render Run** (DEC-324 standardizes this name across domains 12 and 13; distinguished by `render_target_kind`).
- **Render Target** (the destination platform — EspoCRM, HubSpot, etc.).
- **Generated Artifact** (DEC-324 keeps this distinct from Generated Document since downstream consumer differs).

### Domain 13 — Document Rendering

- **Render Run** (per DEC-324, same entity as in #12, distinguished by `render_target_kind`).
- **Document Template** (partial V1 via `tools/docgen/` templates).
- **Generated Document** (partial V1 via `tools/docgen/` output).

### Domain 14 — Engagement Setup

All entities are spec.

- **Engagement** (the implicit container from Engagement Governance is owned by this domain as a first-class entity).
- **Setup Run** (records each engagement-initialization execution).
- **Initial Schema Seed** (the seed records bootstrapped at engagement start).

---

## 3. Candidate Persona Inventory

Nine candidate personas surfaced. Rule 2.2 backings: 2 resolved, 7 TBD pending PI-091 (user/role entity model).

### Candidate Persona 1 — Implementation Consultant

**Description.** Runs CRMBuilder engagements for client organizations. Conducts interviews via the AI surface; oversees CRM Platform Decision; supervises deployment, configuration, and verification.

**Source.** V1 PRD §1.2 ("Implementation consultants").

**Provisional backing.** TBD — V2 has no user/role entity today (see PI-091).

### Candidate Persona 2 — Client Administrator

**Description.** Designated representative at the client organization. Orchestrates the engagement on the client side; provides org context; approves scope decisions; bridges consultant and client SMEs. The "administrator" of administrator-as-proxy sessions (kickoff.md Variant A).

**Source.** kickoff.md Variant A; methodology-wide administrator concept.

**Provisional backing.** TBD — PI-091.

### Candidate Persona 3 — Client SME

**Description.** Subject-matter expert at the client organization. Provides domain-specific knowledge during Requirements Capture interviews. Multiple per engagement typically (one per domain or sub-domain).

**Source.** kickoff.md Variant B; interview-domain-discovery.md.

**Provisional backing.** TBD — PI-091.

### Candidate Persona 4 — Technical Administrator

**Description.** IT-side person who operates deployment, configuration, and verification tooling. May overlap with Implementation Consultant in small orgs.

**Source.** V1 PRD §1.2 ("Technical administrators").

**Provisional backing.** TBD — PI-091.

### Candidate Persona 5 — Methodology Author

**Description.** Evolves CRMBuilder's methodology itself. Today this is Doug. Specific to Candidate Domain 1.

**Source.** Master CRMBuilder PRD; dogfood premise.

**Provisional backing.** TBD — PI-091.

### Candidate Persona 6 — CRM Researcher

**Description.** Does ongoing CRM Inventory & Functional Analysis and Deployment Pattern Inventory research. Specific to domains 10 and 11. May overlap with Methodology Author or Implementation Consultant.

**Source.** Implied by Candidate Domains 10 and 11.

**Provisional backing.** TBD — PI-091.

### Candidate Persona 7 — AI Agent

**Description.** Claude (or another agent) conducting interviews via chat-UI-on-API or MCP. Charter §2 describes the role.

**Source.** Charter §2 (the AI's role as skilled business analyst).

**Provisional backing.** Tracked indirectly via Conversation (V2 entity). The Conversation entity carries the agent identity per session.

### Candidate Persona 8 — Custom Developer

**Description.** Builds custom CRM functionality for Candidate Domain 8 (Custom CRM Build). Speculative — domain is unimplemented.

**Source.** Implied by Candidate Domain 8.

**Provisional backing.** TBD — PI-091. (Originally provisionally marked External; revised in Topic 5 — Custom Developers in future engagements would be engagement participants tracked the same way as consultants.)

### Candidate Persona 9 — CRM End-User (questionable inclusion)

**Description.** Staff at the client org who use the deployed CRM day-to-day. They never interact with CRMBuilder directly; they consume what CRMBuilder produced.

**Source.** Implied by V1 PRD's nonprofit technology teams target audience.

**Provisional backing.** External. They interact with the deployed CRM, not with CRMBuilder.

**Note.** Inclusion flagged as questionable during Topic 5 — argue for: ultimate beneficiary of the engagement; argue against: not a CRMBuilder user. Kept on the list pending Phase 3 reconciliation.

---

## 4. Interview Transcript — SES-098

Phase 2 Domain Discovery session for the CRMBUILDER engagement, conducted in a Claude.ai sandbox conversation with Doug as both administrator and sole stakeholder (Variant A administrator-as-proxy adapted for dogfood). One conversation, CONV-068.

### Topic 1 — Opening and Mission Grounding

**Q:** Operative mission for Rule 2.1 — use V1 PRD §1.1 as-is, or revise?

**A:** Revise. Tweak language to capture that CRMBuilder is "more than just a CRM deployment tool, but a application framework for conducting that process."

**Decision:** Mission revised to application-framework framing (full text in §"Working Mission" above and in DEC-320).

**Q:** Modify the language about CRM platform selection logic to include the option to build custom CRM functionality to work with existing CRM or from scratch.

**A:** Confirmed.

**Decision:** Mission's platform-selection clause extended to three modes — recommend existing, extend existing with custom functionality, or build from scratch. DEC-320 captures both revisions.

### Topic 2 — Walking the Work (continuous three-track capture)

**Q:** Initial candidate domain list extracted from the corpus (V1 PRD 6-phase workflow; 13-phase process doc; Master CRMBuilder PRD's two-layer model; revised mission). 9 candidates presented: Methodology Authoring, Engagement Governance, Requirements Capture, CRM Platform Decision, CRM Deployment, CRM Configuration, CRM Verification, Custom CRM Build, AI-Assisted Interview Surface.

**A:** Add CRM Inventory and functional analysis, and CRM deployment pattern inventory.

**Decision:** Two more domains promoted (#10, #11). Their structural shape (knowledge-substrate domain feeding operational domain) flagged.

**Q:** Structural observation — the same shape (knowing-domain feeding doing-domain) could apply to CRM Configuration and Custom CRM Build. Add Configuration Pattern Inventory and Custom Build Pattern Inventory as parallels, or keep asymmetry?

**A:** Initially: "I do not understand your observation, could you explain it better." After clarification with concrete examples and the recommendation against adding the parallels: confirmed the parallels are not added.

**Decision:** Symmetric pattern-inventory parallels NOT added for #6 and #8. Patterns intrinsic to those operational domains (DEC-322).

### Topic 3 — Completeness Sweep

**Q:** Three additional corpus-supported candidates identified by the sweep: Requirements-to-deployment rendering, Documentation rendering, Engagement setup/initialization. Promote any to domain status, fold into existing, or skip?

**A:** Promote all three.

**Decision:** Three domains added — Configuration Artifact Generation (#12, platform-neutral name vs. "YAML Generation"), Document Rendering (#13), Engagement Setup (#14). Domain list locked at 14. The implicit Engagement entity is owned by #14, resolving an earlier tension.

### Topic 4 — Domain Validation (Rule 2.1)

**Q:** Apply Rule 2.1 — "if this stopped tomorrow, would the mission be in trouble?" — to each of 14 candidates. 12 are clear-pass; 2 (Methodology Authoring and Document Rendering) need explicit confirmation.

**A:** Confirm pass on both.

**Decision:** All 14 candidates pass Rule 2.1. Methodology Authoring designated CRMBuilder-internal-only (DEC-323). Document Rendering passes on the strength of the Stakeholder Review dependency (DEC-324 commentary).

### Topic 5 — Persona Backing (Rule 2.2)

**Q:** Apply Rule 2.2 to each of 9 candidate personas. 2 resolved (AI Agent backed by Conversation; CRM End-User External). 1 revision (Custom Developer revised from External to TBD). 7 TBD pending the user/role entity gap.

**A:** Confirm. The user/role gap is worth a planning item but should not block.

**Decision:** PI-091 captures the user/role entity model work. All 9 personas have Rule 2.2 results recorded.

### Topic 6 — Candidate Entity Disambiguation

**Q:** "Entity" overload was flagged earlier as a tension — methodology Entity vs. client's CRM entity type.

**A:** "I am not sure that the Entity term is a duplicate. The methodology process would create an entity like contacts."

**Decision:** Entity overload retracted. Methodology Entity is the lifecycle spec; the deployed CRM's "Contact" is its realization; same concept, different lifecycle stage.

**Q:** Three remaining tensions: Pattern overload (Deployment Pattern, Pattern Library Entry, implicit Configuration Pattern); Render Run vs. Render Job naming; Generated Artifact vs. Generated Document.

**A:** Confirm Pattern disambiguation, accept Render Run standardization, confirm Generated Artifact / Document stay distinct.

**Decision:** DEC-324 locks in the entity naming disambiguations.

### Topic 7 — Interview Transcript

Captured in this section. Per Option C.1, the SES record's `topics_covered` field carries a structured summary; this MD section carries the fuller transcript organized by topic.

### Session Methodology Shape — pivot during close-out preparation

**Q:** Investigation of `apply_close_out.py` revealed the v0.8 close-out payload schema is governance-only — no methodology-records section. Three revised paths: C.1 (defer methodology writes via PI + durable MD), C.2 (one-off methodology-write script), C.3 (raw curls in apply prompt). Recommendation: C.1.

**A:** "c.1 with additional requirement to convert MD document to database record when the closeout allows."

**Decision:** DEC-319 adopts C.1. PI-092 captures the MD-to-V2-records conversion work.

---

## 5. Decisions Made in SES-098

Six decisions captured. Full records (context, decision, rationale, alternatives_considered, consequences) in `close-out-payloads/ses_098.json`. Brief summaries:

- **DEC-319** — Adopt session methodology shape Option C.1 (durable MD inventory + standard governance close-out, methodology writes deferred to PI-092 pending close-out pipeline support).
- **DEC-320** — Mission revision to "application framework" framing with three-mode platform-or-build option.
- **DEC-321** — Domain set for CRMBUILDER engagement: 14 candidates.
- **DEC-322** — Symmetric pattern-inventory parallels rejected for #6 and #8 (patterns intrinsic to operational domains there).
- **DEC-323** — Methodology Authoring (#1) is CRMBuilder-internal-only; absent from external engagement domain sets.
- **DEC-324** — Entity naming disambiguation: Pattern qualifiers locked in; Render Run standardized across #12 and #13.

---

## 6. Planning Items Filed in SES-098

- **PI-091** — Design and implement a user/role entity model in V2 for tracking per-engagement participants. 7 personas have TBD backing pending this.
- **PI-092** — Promote Phase 2 candidate methodology records (14 Domains, 9 Personas, ~40 Entities) from this MD inventory into V2 records once the V2 close-out pipeline supports methodology ingestion. Includes a design step to determine the ingestion mechanism (v0.9 schema extension; separate apply path; MCP tool surface; inline curls; etc.).

---

## 7. Next Phase

Phase 2 Domain Discovery is complete for the CRMBUILDER engagement under the saturation test (sole stakeholder, no further sessions). Under the **old methodology** (13-phase process + Phase 2 Domain Discovery guide v1.1), the next phase is **Phase 3 Inventory Reconciliation** — but reconciliation has limited applicability for a sole-stakeholder dogfood engagement.

Under the **new Master CRMBuilder PRD** (in development), Phase 2 hasn't been drafted yet; this session effectively drafts it by execution (per Master CRMBuilder PRD §III iterative drafting principle, captured in DEC-319). The new methodology may absorb reconciliation into Phase 1 (Business Context Capture) or define a different next-phase.

**Recommended next session:** a separate working session to decide what the next phase looks like in dogfood. Open questions to resolve:
1. Does Phase 3 Inventory Reconciliation exist as a distinct phase in the new Master CRMBuilder PRD, or is it absorbed into Phase 1 or Phase 4?
2. What is the V2 methodology-records ingestion mechanism (PI-092 scope)?
3. Once methodology records are in V2, what does Phase 4 (Domain Overview + Process Definition) look like for the 14 CRMBuilder domains?

---

## 8. References

- Phase 2 Domain Discovery interview guide: `PRDs/process/interviews/interview-domain-discovery.md` v1.1
- Interviewer Charter: `PRDs/process/conduct/charter.md` v1.2
- Kickoff Protocol: `PRDs/process/conduct/kickoff.md` v1.1
- Master CRMBuilder PRD: `specifications/master-crmbuilder-PRD.md` v0.1 (draft)
- Governance Recording Rules: `specifications/governance-recording-rules.md` v0.1 (draft)
- V1 Product PRD: `PRDs/product/CRMBuilder-PRD.md` v4.1
- 13-Phase Document Production Process: `PRDs/process/CRM-Builder-Document-Production-Process.docx`
- This session's close-out payload: `PRDs/product/crmbuilder-v2/close-out-payloads/ses_098.json`
- This session's apply prompt: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-098.md`
