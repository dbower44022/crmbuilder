# CBM Redo — Step 7: Pre-Validation Findings

**Document type:** Descriptive findings draft (interpretation deferred)
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/evolved-methodology/cbm-redo/cbm-redo-step-7-pre-validation-findings.md`
**Last Updated:** 04-30-26 20:35
**Version:** 1.0

---

## Status

This document captures Step 7 of the CBM redo execution plan, per `cbm-redo-ground-rules.md` §9. Step 7 is the **descriptive findings draft** — what the redo produced, what the gap log shows, how the redo's outputs map against the comparison criteria from ground rules §5.2.

Per ground rules §8.3, **this draft is descriptive only.** Interpretation, recommendations, and "what does this mean" are deliberately deferred to the final findings document (Step 9), which is produced after the validation pass with CBM (Step 8). The discipline of separating descriptive findings from interpretive conclusions exists to prevent confirmation bias from shaping the findings to fit a preferred narrative.

The reader should not expect this document to recommend continuing or pausing the methodology evolution effort. That recommendation belongs to Step 9.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 04-30-26 20:35 | Doug Bower / Claude | Initial descriptive findings draft. Comparison against the seven criteria from ground rules §5.2 with explicit acknowledgment of §5.5 limits. No interpretive conclusions. |

---

## Change Log

**Version 1.0 (04-30-26 20:35):** Initial creation of the descriptive findings draft. Records the redo's Phase 1 outputs, surveys the gap log, applies the seven comparison criteria from ground rules §5.2 against descriptive characterization of the original CBM engagement's equivalent work, and acknowledges the §5.5 limits. No interpretation included by design.

---

## 1. The Redo's Phase 1 Outputs

The four Phase 1 outputs as finalized at end of Session 2 (Step 5):

### 1.1 Mission Statement

> *"CBM matches volunteer mentors with entrepreneurs, small businesses, and nonprofits in Northeast Ohio, and supports those mentoring engagements through their full lifecycle, at no cost to clients and confidentially."*

Aspirational context (workshops, partner ecosystem, community impact) acknowledged as real but secondary. Priority test framing: *"a process is mission-critical if its absence would prevent CBM from matching volunteer mentors with clients in Northeast Ohio and supporting those engagements as confidential, free, lifecycle-managed pairings."*

### 1.2 Domain Inventory

Six domains in the client's natural language, ordered with The Mentoring first per Session 2 client preference:

1. The Mentoring
2. The Mentor Pool
3. Bringing in Clients
4. Partner Relationships
5. Donors and Funding
6. Workshops and Events

### 1.3 Prioritized Backbone

**Mission-critical (six processes for iteration 1):**

| Process | Domain |
|---|---|
| Mentor Application | The Mentor Pool |
| Mentor Initial Activation | The Mentor Pool |
| Client Application | Bringing in Clients |
| Client Intake | Bringing in Clients |
| Matching | The Mentoring |
| Session activity tracking | The Mentoring |

**Supporting (eleven processes for iteration 2 or later):**

Mentor outreach; full mentor onboarding/training; active mentor management; mentor departure; client outreach; engagement monitoring; engagement closing; partner identification; partnership agreements; ongoing partner management; donor recording.

**Deferred (six processes):**

Reactivation; joint events; donor outreach; donor stewardship; donor reporting; all workshop processes (planning, registration, follow-up).

The backbone spans three of the six domains. The cross-domain dependency between The Mentor Pool, Bringing in Clients, and The Mentoring is the methodology's signature surfacing for CBM.

### 1.4 Initial CRM Candidate Set

Three open-source candidates representing meaningfully different approaches:

- **EspoCRM** — modern lightweight standalone, custom-entity-strong
- **CiviCRM** — nonprofit-specialized, native fundraising/events, requires CMS host
- **SuiteCRM** — traditional general-purpose, mature ecosystem

Multi-deploy mode confirmed. Senior-accessibility-of-UI noted as evaluation criterion (per G-009) to surface during iteration 1 use.

---

## 2. Gap Log Summary

Nine entries logged across Steps 3–5. Two resolved in Session 2.

| Gap ID | Step | Theme | Status |
|---|---|---|---|
| G-001 | Step 3 | Cross-domain boundary | Open — carry to validation pass |
| G-002 | Step 3 | Cross-domain boundary | Open — not relevant to iteration 1 |
| G-003 | Step 3 | Operational-strategic split | Open — carry to validation pass |
| G-004 | Step 3 | Cross-domain boundary | Open — not relevant to iteration 1 |
| G-005 | Step 3 | Consultant process | Open — not validation-pass-relevant |
| G-006 | Step 3 | Operational-strategic split | Open — carry to validation pass |
| G-007 | Step 4 | Process granularity | Resolved in Session 2 |
| G-008 | Step 4 | Process granularity | Resolved in Session 2 |
| G-009 | Step 5 | Empirical evaluation criterion | Open — becomes iteration 1 evaluation criterion |

Validation pass scope per ground rules §7: three substantive questions (G-001, G-003, G-006) plus brief approach check.

---

## 3. Characterization of the Original CBM Engagement at the Equivalent Stage

To apply the comparison criteria, the original CBM engagement's equivalent work has to be characterized. Per ground rules §5.1, the equivalent work is the content of:

- The CBM Master PRD (as the original Phase 1 output)
- The Domain Discovery work that produced the original Domain Inventory
- The Inventory Reconciliation work that produced the original Persona and Entity inventories
- The portions of Domain PRDs and process documents that establish *which processes exist* (process names, structural decisions) — these are the closest analog in the original methodology to the Prioritized Backbone, even though the original methodology did not classify priority

### 3.1 What the original methodology produced at the equivalent stage

**CBM Master PRD (current version 2.6):** approximately 6,400 words, organized into eight numbered sections covering Organization Overview (1.1–1.3), Personas (twelve personas defined with responsibilities and CRM capabilities for each), Key Business Domains (with per-domain sub-sections covering tier definitions, process tier summary, and four named domains MN/MR/CR/FU), Cross-Domain Services (NOTES, EMAIL, CALENDAR, SURVEY), System Scope (in scope, out of scope, key integrations, universal contact-creation rules).

**Domain Inventory equivalent:** four domains identified — Mentoring (MN), Mentor Recruitment (MR), Client Recruiting (CR), Fundraising (FU) — with sub-domain structure under CR (PARTNER, MARKETING, EVENTS, REACTIVATE).

**Process structure for equivalent of Prioritized Backbone:** at the original methodology's Phase 1-equivalent stage, processes within each domain are named but not classified by mission-criticality. As the original methodology continued past Phase 1, processes were defined in detail through Process Definition sessions: five processes in MN (INTAKE, MATCH, ENGAGE, INACTIVE, SURVEY, CLOSE) plus one survey process; five processes in MR (RECRUIT, APPLY, ONBOARD, MANAGE, DEPART); a series of processes across CR sub-domains; four processes in FU (PROSPECT, RECORD, REPORT, STEWARD).

**Entity Inventory:** the Inventory Reconciliation phase produced a curated list of entities with cross-domain bindings.

**Persona Inventory:** thirteen personas defined (MST-PER-001 through MST-PER-013).

**Initial CRM Candidate Set equivalent:** the original methodology defers CRM selection to Phase 10. At the Phase 1 equivalent stage, no candidate set is produced.

### 3.2 Total artifact volume at the equivalent stage

- Master PRD: approximately 30 pages
- Domain Discovery / Reconciliation outputs: Entity Inventory, Persona Inventory — multiple pages each
- Sub-domain Overview documents (under CR): four documents at multiple pages each
- Process documents identified (not yet defined in detail at Phase 1 equivalent): roughly 18–20 process names across the four domains and sub-domains

Total at the Phase 1 equivalent stage: approximately 50–80 pages of text artifacts, depending on which sub-phase boundary is used as the cutoff.

This characterization is for comparison purposes. It is descriptive of what exists in the CBM repository as of the survey timestamp (Step 1, 04-30-26).

---

## 4. Application of the Seven Comparison Criteria

### 4.1 Criterion 1 — Elicitation effort

**Reference framing from ground rules §5.2:** "How much consultant-and-client time, measured in session-equivalents, did each engagement need to produce its Phase 1-equivalent outputs?"

**The redo:** Two client-facing sessions plus one between-sessions consultant work session. Session 1 was approximately 90–120 minutes simulated; Session 2 was approximately 95 minutes simulated. The between-sessions consultant work would represent perhaps 4–8 hours of consultant time in a real engagement. Total client-facing effort: approximately 3–4 hours. Total consultant effort: approximately 8–14 hours.

**The original CBM engagement:** the work equivalent to Phase 1 in the new methodology spans Phases 1–3 of the current 13-phase Document Production Process (Master PRD, Domain Discovery, Inventory Reconciliation), plus the early portions of Phase 4 (Domain Overview) where domain structure and process names are first established. Per the existing methodology spec, each is a separate conversation; the actual CBM engagement has produced multiple iterations and versions of these documents over months. Exact session count is not directly recoverable from the artifacts surveyed, but the change-log entries on the Master PRD (v2.6 as of 04-10-26) and the multi-month timeline of the engagement indicate the equivalent work spans many client-facing sessions over a multi-month period.

**Descriptive comparison:** the redo produced its four Phase 1 outputs in a small bounded number of sessions (two plus consultant work) over a notional one-to-two-week elapsed period. The original CBM engagement's equivalent work spans many sessions over months. A direct ratio calculation requires making assumptions about session count for the original, which the artifacts surveyed do not directly provide.

### 4.2 Criterion 2 — Processes correctly identified as mission-critical

**Reference framing from ground rules §5.2:** "Does the redo's Prioritized Backbone correctly identify the processes that, in retrospect, constitute the mission-critical thread for CBM? The reference for 'correctly' is the candidate backbone Doug confirmed in this conversation: Mentor enrollment, Mentee intake, Matching, Session logging."

**The redo's mission-critical set (six processes):**

1. Mentor Application
2. Mentor Initial Activation
3. Client Application
4. Client Intake
5. Matching
6. Session activity tracking

**Mapping to the reference:** the reference of *"Mentor enrollment, Mentee intake, Matching, Session logging"* maps to the redo's six as follows:

- "Mentor enrollment" → split across Mentor Application + Mentor Initial Activation (split made in Session 2 in response to client pushback per G-007)
- "Mentee intake" → split across Client Application + Client Intake (split made in Session 2 in response to client pushback per G-008)
- "Matching" → Matching
- "Session logging" → Session activity tracking

**Descriptive characterization:** the redo's six processes cover the same operational territory as the four-process reference. The redo's split into six rather than four reflects the Session 2 client correction that Application and Activation/Intake are loosely coupled in time at CBM and should not be combined into single processes.

**The original CBM engagement at this criterion:** the original methodology does not classify processes by mission-criticality. The closest analog is the structure of the Domain PRDs, which describe processes within each domain at the same depth without prioritization. There is no "iteration 1 backbone" in the original methodology's outputs.

### 4.3 Criterion 3 — Cross-domain dependencies surfaced

**Reference framing from ground rules §5.2:** "Did the redo's workability check catch the cross-domain dependency that requires Mentor Recruitment processes to be in a Mentoring backbone? This is the specific issue the iterative methodology is supposed to handle better than the original methodology."

**The redo:** the workability check in Step 4 (`cbm-redo-step-4-between-sessions.md` §3) surfaced the cross-domain dependency explicitly: Matching (in The Mentoring) requires mentor records (from The Mentor Pool) and client records (from Bringing in Clients). The check was: *"Could a real CBM staff member, sitting at a deployed instance with only the mission-critical processes, do their actual job for one realistic case from start to finish?"* Walking through one realistic case (mentor applies → activated → client applies → intake → matching → sessions) confirmed the three domains are jointly required for iteration 1.

The cross-domain dependency was carried into Session 2 §3.7 and the simulated client accepted it without confusion. Step 5 §3.7 records this directly: *"the client did not push back on the cross-domain dependency framing... the client appeared to find it natural that mentor enrollment, client intake, and matching are jointly in iteration 1 because the work cannot be done end-to-end without all three."*

**The original CBM engagement at this criterion:** the original methodology surfaces cross-domain dependencies but does so later in the process, through the Reconciliation phases (Phase 7 — Domain Reconciliation, Phase 8 — Stakeholder Review) and the Consolidated Design document. The cross-domain dependencies are documented (the Mentor entity is shared between MN and MR, the Engagement entity links the two, etc.) but are not surfaced as a Phase 1-equivalent output. They emerge after substantial domain-specific work is complete.

**Descriptive comparison:** the redo surfaced the cross-domain dependency in between-sessions consultant work after one client conversation, before any deep domain or process specification. The original engagement surfaces equivalent dependencies during Reconciliation, after each domain has been specified in depth.

### 4.4 Criterion 4 — Quantity of artifacts produced

**Reference framing from ground rules §5.2:** "How many pages of artifact content does the redo produce vs. the original?"

**The redo's deliverable Phase 1 outputs:**

- Mission Statement: approximately 1 page
- Domain Inventory: less than 1 page
- Prioritized Backbone: approximately 3 pages of substance plus reasoning
- Initial CRM Candidate Set: approximately 2 pages

Total deliverable artifact content: **approximately 7–8 pages**.

(The captured execution documents — Steps 3, 4, 5 — total approximately 30 pages but include narrative reasoning, dialogue, and audit material that would not be in real engagement deliverables. Those execution documents are research artifacts, not Phase 1 deliverables.)

**The original CBM engagement at the equivalent stage:**

- Master PRD: approximately 30 pages
- Domain Inventory equivalent material: spread across Domain Discovery outputs, Master PRD §3, etc. — approximately 5–10 pages
- Entity Inventory: approximately 10 pages
- Persona Inventory: incorporated into Master PRD §2; approximately 6 pages worth
- Sub-domain Overview documents (CR sub-domains): four documents at approximately 3–5 pages each
- Process names and brief descriptions across four Domain PRDs at the depth available at the Phase 1 equivalent stage: approximately 10–15 pages worth

Total at the equivalent stage: **approximately 70–85 pages**.

**Descriptive comparison:** the redo produced approximately 7–8 pages of Phase 1 deliverables. The original engagement produced approximately 70–85 pages at the equivalent stage. The ratio is approximately 10:1.

### 4.5 Criterion 5 — Decisions made vs. deferred

**Reference framing from ground rules §5.2:** "What decisions does the redo's Phase 1 *decide* (lock in) vs. *defer* to later phases?"

**The redo locks at Phase 1:**

- Operational mission language
- Six-domain inventory in client's natural language
- Six mission-critical processes with cross-domain dependency
- Eleven supporting processes (queued for iteration 2 or later)
- Six deferred processes (parked indefinitely)
- Three-CRM candidate set with multi-deploy mode

**The redo explicitly does NOT lock at Phase 1:**

- Detailed process specifications (deferred to Phase 3 / iteration build for in-scope processes)
- Entity definitions (deferred)
- Persona definitions (deferred)
- Sub-domain breakdowns (deferred — the redo does not introduce sub-domain structure)
- Cross-domain service identification (deferred)
- Specific CRM selection (deferred to Phase 5 / engagement closure)
- Field-level requirements, validations, layouts (deferred)

**The original CBM engagement at the equivalent stage locks:**

- Master PRD content (mission, organization overview, why a CRM is needed, system scope)
- Persona definitions (thirteen personas defined with responsibilities)
- Domain structure including sub-domains (CR breaks into PARTNER, MARKETING, EVENTS, REACTIVATE)
- Cross-domain services (NOTES, EMAIL, CALENDAR, SURVEY)
- Entity Inventory with cross-domain bindings
- Process names per domain and sub-domain
- Implementation tier definitions and process tier summary

**The original engagement explicitly does NOT lock at the equivalent stage:**

- Detailed process specifications (deferred to Phase 4 / Process Definition)
- Field-level entity definitions (deferred to Phase 5 / Entity PRDs)
- Cross-domain service definitions in detail (deferred to Phase 6)
- Specific CRM selection (deferred to Phase 10)
- YAML / configuration (deferred to Phase 9 / 12)

**Descriptive comparison:** at the Phase 1 equivalent stage, the original engagement locks more decisions than the redo. The redo defers entity definition, persona definition, sub-domain structure, and cross-domain service identification — all of which the original engagement has decided at the equivalent stage.

### 4.6 Criterion 6 — Gap profile

**Reference framing from ground rules §5.2:** "How many Tier 2 inferences and Tier 3 gaps did the redo hit? Where did they cluster? Are the gaps in places that suggest Phase 1's interview design has weak spots, or in places where any methodology would struggle?"

**The redo's gap profile:**

- 9 entries total across Steps 3–5
- 2 resolved in Session 2 (G-007, G-008 — process-granularity judgment calls corrected by client pushback)
- 7 open at end of Phase 1 simulation
- Cluster around four themes: cross-domain boundaries (4 entries), operational-strategic splits (2 entries), process granularity (2 entries — both resolved), empirical evaluation criteria (1 entry)

**Where the gaps occurred:**

- 6 in Session 1 (process surfacing portion was the densest source)
- 2 in between-sessions consultant work (process granularity judgment)
- 1 in Session 2 (CRM candidate concern)

**Where the methodology-flagged moments were exercised without producing gaps:**

- Confident proposal opening in Session 2 §3.2 — exercised, no gap
- Push-back-and-engage moments (process combinations, Donors/Funding deferral) — exercised, the push-back produced backbone changes without producing new gaps about the methodology itself
- Deferred-not-dismissed framing (Donors/Funding) — exercised, produced reclassification without producing a new gap

**The original CBM engagement at this criterion:** the original methodology does not have a gap log concept. Equivalent issues surface as "open issues" tracked in domain reconciliation documents (the Decisions Made section, the Open Issues section in Domain PRDs, carry-forward documents) and are resolved through subsequent work. The original methodology's accumulated open-issues content for CBM at the equivalent stage is non-trivial — the most recent CR domain work alone references multiple ACT-ISS-* identifiers and the FU domain has multiple ISS-* identifiers in process documents — but the structure differs enough from a Phase-1-equivalent gap profile that a direct numerical comparison is not meaningful.

### 4.7 Criterion 7 — Defensibility of proposed classifications

**Reference framing from ground rules §5.2:** "Are the redo's mission-critical / supporting / deferred classifications grounded in arguments the simulated consultant can articulate from the in-bounds material?"

**Mission-critical classifications:** each of the six mission-critical processes has an articulated argument from operational mission. From `cbm-redo-step-4-between-sessions.md` §2.2–§2.4 and §4.3, summarized:

- Mentor Application + Initial Activation: without enrolled mentors, matching has nothing to match
- Client Application + Intake: without enrolled clients, same problem
- Matching: the mission's central operational activity per current Master PRD §1.3
- Session activity tracking: without tracked sessions, the pairing exists only in name

These arguments are defensible from in-bounds material — they reference the operational mission and the priority test framing, both of which are grounded in the CBM Master PRD's own language.

**Supporting classifications:** each is articulated as "real work but not on the critical path for iteration 1." The argument is structural rather than per-process: iteration 1 can deploy with manual or absent handling of these processes; iteration 2 picks them up.

**Deferred classifications:** each is articulated against the priority test. The Donors/Funding deferral specifically was tested in Session 2 §3.5 — the client pushed back, and the consultant's response held that the priority test does not place donor recording on the critical path for matching mentors and clients. Donor recording was reclassified as supporting (iteration 2) rather than deferred (parked), but the iteration-1 exclusion held.

**The original CBM engagement at this criterion:** the original methodology does not have priority classifications to defend. Process scope decisions are made on the basis of completeness rather than prioritization.

---

## 5. Limits Acknowledgment

Per ground rules §5.5, the experiment runs under three known unfair conditions that should be cited in the findings:

### 5.1 The simulator could not fully unsee what it knew

The same entity (Claude) designed the new methodology, ran the simulated test, and is now characterizing the comparison. Even with §2.1 source material discipline, the simulator cannot fully unsee what was known about how the original engagement ended up. The mitigation strategy (per ground rules §6) was to log judgment calls explicitly (G-005, G-007, G-008) and to acknowledge in the redo documents (Step 4 §6.3, Step 5 §6) where the consultant's reasoning matched what the simulator already knew the answer to be.

### 5.2 The original methodology was applied with iterative reasoning over many sessions; the redo ran in a single linear pass

The original CBM engagement's quality came partly from extended thinking across many sessions, with multiple revisions to the Master PRD (currently v2.6), multiple Domain PRD versions, and a substantial accumulated decisions log. The redo's two-session simulation cannot replicate this extended thinking. To the extent the original engagement's outputs benefit from iterative refinement that the redo did not perform, the comparison underestimates what the original methodology produces.

### 5.3 The simulated client was more articulate and patient than real clients

Real clients miss meetings, change their minds, give vague answers, surface concerns that don't fit the conversation flow, and sometimes don't recognize what they're being asked. The simulated client in the redo did none of these. Step 5 §7.5 specifically notes that the simulated client may have been more articulate about the temporal coupling distinction (in the G-007/G-008 resolution) than a real CBM stakeholder would be in a real first engagement. The redo's smoothness on the methodology-flagged moments may reflect simulator-client articulateness rather than methodology quality.

---

## 6. What This Document Does Not Contain

By design, this document does not contain:

- Interpretation of what the criteria measurements *mean*
- Recommendations about whether to continue the methodology evolution effort
- Conclusions about whether the new methodology is better, worse, or comparable
- Arguments about the magnitude of the differences observed
- Predictions about how the validation pass with CBM will go

These are deferred to the final findings document (Step 9), which incorporates the validation pass results and applies interpretation to the descriptive findings here.

---

## 7. Step 7 Outputs

### 7.1 What Step 7 produced

A descriptive findings draft that:

- Records the redo's four Phase 1 outputs (§1)
- Summarizes the gap log (§2)
- Characterizes the original CBM engagement at the equivalent stage (§3)
- Applies the seven comparison criteria (§4)
- Acknowledges the three §5.5 limits (§5)
- Holds back interpretation per §6 by design

### 7.2 What Step 8 (validation pass with CBM) needs from Step 7

Step 8 needs:

- The three substantive validation questions identified in the gap log (G-001, G-003, G-006)
- Clear framing for the brief approach check
- An understanding of which findings would change if validation pass surfaces a different reality

### 7.3 What Step 9 (final findings document) will add

Step 9 will:

- Incorporate validation pass results
- Apply interpretation to the descriptive findings
- Provide the recommendation: continue methodology evolution effort / pause and revise / abandon
- Note any open questions for further research

---

*End of document.*
