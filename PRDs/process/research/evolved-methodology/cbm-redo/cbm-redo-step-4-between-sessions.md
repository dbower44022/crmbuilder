# CBM Redo — Step 4: Between-Sessions Work

**Document type:** Captured execution of the evolved methodology test
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/evolved-methodology/cbm-redo/cbm-redo-step-4-between-sessions.md`
**Last Updated:** 04-30-26 19:15
**Version:** 1.0

---

## Status

This document captures Step 4 of the CBM redo execution plan, per `cbm-redo-ground-rules.md` §9. Step 4 is the simulated consultant's between-sessions work: classifying processes by mission-criticality, running the workability check, drafting the proposed Prioritized Backbone, and drafting the Initial CRM Candidate Set. No client involvement at this step.

The proposed Prioritized Backbone and Initial CRM Candidate Set are **embedded** in this document (per Doug's confirmed preference) rather than separated into standalone artifacts. In a real engagement these would be standalone deliverables. For the research test, the audit value of having reasoning next to artifact outweighs the standalone-artifact convention.

Two gap log entries (G-007, G-008) were added during Step 4 execution and are recorded in `cbm-redo-gap-log.md` v0.2.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 04-30-26 19:15 | Doug Bower / Claude | Initial captured execution of Step 4. Proposed Prioritized Backbone with four mission-critical processes and Initial CRM Candidate Set with three open-source options. |

---

## Change Log

**Version 1.0 (04-30-26 19:15):** Captured execution of Step 4 — between-sessions consultant work. Records the process-by-process priority classification (4 mission-critical, 13 supporting, 4 deferred), the workability check that confirmed cross-domain dependency between The Mentor Pool and The Mentoring, the proposed Prioritized Backbone with Mentor Application & Initial Activation, Client Application & Intake, Matching, and Session Logging as the iteration 1 mission-critical set, and the proposed Initial CRM Candidate Set with EspoCRM, CiviCRM, and SuiteCRM as three meaningfully different open-source candidates. Two new gap log entries added.

---

## 1. Step 4 Inputs

Step 4 takes the following inputs from prior steps:

- **Drafted Mission Statement** (Step 3 §2.4) — operational mission language with priority test framing
- **Six-domain Domain Inventory** (Step 3 §3.6) — in client's natural language
- **Twenty-one processes** (Step 3 §4) — captured at name and one-sentence-description level across the six domains
- **CRM context notes** (Step 3 §5.5) — seven stated principles, capacity constraints, user-base requirements, confidentiality requirements, scope boundary
- **Six gap log entries** (cbm-redo-gap-log.md v0.1) — boundary ambiguities and operational-strategic splits

Step 4 also has narrow access to factual constraints from prior CRM evaluation documents (per ground rules §2.2 v0.2 narrow allowance) for the candidate set work, with their evaluative conclusions excluded.

---

## 2. Process Classification

### 2.1 Methodology

Each of the twenty-one processes from Session 1 is classified as **mission-critical**, **supporting**, or **deferred**, applying the priority test framing from the Mission Statement:

> *"A process is mission-critical if its absence would prevent CBM from matching volunteer mentors with clients in Northeast Ohio and supporting those engagements as confidential, free, structured pairings."*

Classifications are the consultant's proposal. They will be tested against the workability check (§3) and presented to the client for verification in Session 2.

### 2.2 Domain — The Mentoring (5 processes)

| Process | Classification | Reasoning |
|---|---|---|
| Matching | Mission-critical | The mission's central operational activity. Without matching, no mentor-client pairing exists, and the mission cannot be performed. |
| Session activity tracking | Mission-critical | Without tracked sessions, there is no evidence the pairing is producing the structured engagement the mission promises. The pairing exists only in name. |
| Engagement monitoring (detecting quiet engagements) | Supporting | Real work but not on the critical path for iteration 1. A system can deploy without proactive quietness detection and add it later as the engagement volume justifies the alerting. |
| Engagement closing | Supporting | Same logic. Engagements that are closed can be marked closed manually in iteration 1 without a formal closure process. The closure-formalization can come in iteration 2. |
| Intake (boundary with Bringing in Clients) | See §2.4 | This boundary is fuzzy per G-001. Treated under Bringing in Clients per the client's classification. |

### 2.3 Domain — The Mentor Pool (5 processes)

| Process | Classification | Reasoning |
|---|---|---|
| Outreach to potential mentors | Supporting | Real work that maintains the pool over time, but iteration 1 can deploy with whatever mentor population CBM has at engagement start. New mentor recruiting can be added in iteration 2. |
| Application and screening | Mission-critical | Without a way to enroll new mentors and produce mentor records that the matching coordinator can see, the system cannot grow with CBM's operational reality. See workability check §3. |
| Onboarding and training | Mission-critical (minimal form) | Without at least *minimal* activation — enough to mark a screened mentor as "available for matching" — matching cannot proceed. The full onboarding-and-training process can be supporting; the activation portion has to be in iteration 1. **Combined with Application and screening into a single process for iteration 1; see G-007.** |
| Active mentor management (capacity, dues) | Supporting | Real work but not on the critical path. Iteration 1 can deploy with manual capacity tracking. |
| Departure | Supporting | Real work but not on the critical path. Iteration 1 can deploy with manual departure marking. |

### 2.4 Domain — Bringing in Clients (3+1 processes)

| Process | Classification | Reasoning |
|---|---|---|
| Outreach to potential clients | Supporting | Iteration 1 can deploy with whatever inbound client volume CBM has. Active outreach can be added in iteration 2. |
| Application | Mission-critical | Without a way to take in client applications and produce client records, the system cannot grow with CBM's operational reality. |
| Intake / qualification | Mission-critical | Without qualifying clients before they reach matching, the matching coordinator's work degrades — they're matching mentors with poorly-fit clients. **Combined with Application into a single process for iteration 1; see G-008.** |
| Reactivation (per G-001) | Deferred | Per G-001 the boundary between intake and reactivation is fuzzy. Iteration 1 doesn't need to handle reactivation; clients who don't fit at first contact can be left in the system without a formal reactivation process. |

### 2.5 Domain — Partner Relationships (4 processes)

| Process | Classification | Reasoning |
|---|---|---|
| Identifying and approaching potential partners | Supporting | Real work that extends CBM's reach but is not on the critical path for mentor-client matching. |
| Negotiating partnership agreements | Supporting | Same logic. Partnership agreements that exist can be referenced manually in iteration 1. |
| Ongoing partner management | Supporting | Same logic. |
| Joint events / co-programming | Deferred | Per G-002 the boundary between this and Workshops is unclear. Iteration 1 doesn't need joint events. |

### 2.6 Domain — Donors and Funding (4 processes)

All four classified **deferred** for iteration 1. Per G-003 and G-006, the operational-strategic split is itself unresolved, and even the operational portion is not on the critical path for mentor-client matching. Donor work can be added in iteration 2 or 3 once the boundary with board/exec-director work is clear.

This is a meaningful difference from how some clients might classify it — donor work feels important to many nonprofits — but the priority test is unambiguous: if donor recording stopped tomorrow, the mission of matching mentors and clients still happens. The mission stops if matching stops, not if donor recording stops.

The consultant should be prepared in Session 2 for client push-back here. The deferred-not-dismissed framing from Phase 1 guide §5.4 will matter.

### 2.7 Domain — Workshops and Events (3 processes)

All three classified **deferred** for iteration 1. Workshops are real work that supplements the mentoring per CBM's own framing in Session 1 — they are not the mentoring. The workshop follow-up cross-domain connection (G-004) is genuine but doesn't mean workshops belong in iteration 1; it means that *when* workshops eventually come into scope, the follow-up bridges have to be modeled then.

### 2.8 Classification summary

- **Mission-critical (4 processes for iteration 1):**
  - Mentor Application & Initial Activation (combined per G-007)
  - Client Application & Intake (combined per G-008)
  - Matching
  - Session activity tracking

- **Supporting (10 processes for iteration 2 or later):**
  - Mentor outreach
  - Full mentor onboarding and training (the portion beyond initial activation)
  - Active mentor management
  - Mentor departure
  - Client outreach
  - Engagement monitoring (quietness detection)
  - Engagement closing (formal closure with outcome capture)
  - Partner identification
  - Partnership agreements
  - Ongoing partner management

- **Deferred (7 processes):**
  - Reactivation (per G-001)
  - Joint events (per G-002)
  - Donor outreach
  - Donor recording
  - Donor stewardship
  - Donor reporting
  - All workshop processes (planning, registration, follow-up)

This is the classification proposal that goes into the workability check.

---

## 3. Workability Check

### 3.1 The check

Per Phase 1 guide §4.1: *"Could a real CBM staff member, sitting at a deployed instance with only the mission-critical processes, do their actual job for one realistic case from start to finish?"*

The mission-critical set is: Mentor Application & Initial Activation, Client Application & Intake, Matching, Session activity tracking.

### 3.2 Walk-through — one realistic case

A mentor candidate hears about CBM through professional networks. They go to CBM's website and submit an application.

- **Mentor Application & Initial Activation (mission-critical):** the system captures the application, the Mentor Administrator reviews it, conducts whatever screening is appropriate, and either approves the candidate (which produces a mentor record marked available-for-matching) or declines. The minimal-activation portion is enough to make the mentor matchable. Full onboarding and training is not in iteration 1 — the mentor can be matchable on a provisional basis pending later training (acknowledged honestly with the client in Session 2).

A potential client hears about CBM through a partner referral. They submit an application.

- **Client Application & Intake (mission-critical):** the system captures the application, the Client Administrator reviews it, conducts the intake conversation, and either qualifies the client (which produces a client record marked ready-for-matching) or declines. Same minimal-activation logic.

The Client Assignment Coordinator now sees: an available mentor and a ready client.

- **Matching (mission-critical):** the coordinator reviews the available mentors and ready clients, identifies a fit based on industry/expertise/availability, and creates the engagement record that pairs them. The system records the matching rationale.

The mentor and client meet for their first session and subsequent sessions.

- **Session activity tracking (mission-critical):** sessions are logged against the engagement record. The Mentor Administrator and Client Administrator can see that activity is occurring.

This is a workable end-to-end case. A real CBM staff member can execute this case using only the four mission-critical processes.

### 3.3 What the workability check confirmed

- **Cross-domain dependency surfaced.** Matching (in The Mentoring) requires mentor records (from The Mentor Pool) and client records (from Bringing in Clients). The simulated client identified these as separate domains in Session 1. The workability check confirms that all three domains contribute mission-critical processes to iteration 1. **This is the cross-domain dependency the iterative methodology is designed to surface, and it surfaced cleanly.**
- **Minimum activation suffices.** Full mentor onboarding and full client intake are real work but not required for the workable case. The minimum is "produce a record marked available/ready for matching." Anything beyond that is supporting.
- **Engagement monitoring and closing are not in the minimum.** A system can deploy without proactive engagement monitoring or formal closure processes. These can be added in iteration 2 once the iteration 1 deployment reveals which monitoring or closure tooling is actually needed.

### 3.4 What the workability check did not require adding

The simulated consultant considered whether other processes had to be added to make the case workable. Specifically:

- **Engagement closing.** The case ends with sessions occurring; it doesn't require the engagement to formally close in iteration 1. Closing can be added in iteration 2.
- **Partner referrals.** The case mentions a partner referral as the source of the client, but the system doesn't need to *track* the referral source for the case to work. Tracking referral sources is supporting work.
- **Mentor capacity tracking.** The matching coordinator can use judgment about mentor capacity in iteration 1 without formal capacity tracking. This is supporting work.

These judgment calls are visible in the proposed backbone (§4) and will be tested in Session 2.

### 3.5 Workability statement

The proposed Prioritized Backbone is workable. It supports a real CBM staff member doing real work for one realistic case end-to-end: a mentor applies, is screened and activated; a client applies, is qualified and made ready; the coordinator matches them; their sessions are tracked. Anything not in this minimum is real work but not on the critical path for the iteration 1 deployment.

---

## 4. Proposed Prioritized Backbone

### 4.1 Document framing

Per Phase 1 guide §7.3, the Prioritized Backbone is one of the four Phase 1 outputs. In a real engagement this would be a standalone document. Embedded here for the research test.

### 4.2 Overview

The proposed iteration 1 backbone for CBM is the smallest set of connected processes that lets a real CBM staff member do real work end-to-end on the mission-critical thread. It spans three of the six domains identified in Session 1 (The Mentor Pool, Bringing in Clients, The Mentoring), with the connection between them being: mentor records produced by The Mentor Pool flow into Matching; client records produced by Bringing in Clients flow into Matching; Matching produces engagement records that Session activity tracking attaches to.

This is the cross-domain backbone. The simulated client experienced these as three separate areas of work in Session 1; the workability check confirmed they need to be jointly in iteration 1 because the work cannot be done end-to-end without all three contributing.

**This proposed backbone is marked low-confidence per Phase 1 guide §8.1**, because no pattern library entry exists for nonprofit volunteer-driven mentoring organizations and the consultant's proposal is grounded in operational analysis rather than accumulated patterns. The client should scrutinize it carefully in Session 2.

### 4.3 Backbone processes

#### 4.3.1 Mentor Application & Initial Activation

- **Domain:** The Mentor Pool
- **Purpose:** Take in volunteer mentor applications, conduct screening, and produce mentor records marked available for matching.
- **Mission-critical reasoning:** Without a way to enroll mentors and produce matchable mentor records, Matching has no mentors to match. The mission stops.
- **Handoffs to other backbone processes:** *Produces:* mentor record (for Matching to consume). *Consumes:* nothing in the backbone — application intake is the entry point.
- **Scope note:** This is a *combined* form of what the simulated client described as separate Application/Screening and Onboarding/Training activities. The combination is for iteration 1 only; the full Onboarding/Training process is supporting and graduates to iteration 2 if iteration 1 reveals it's needed sooner. **G-007 in the gap log captures this consultant judgment call.**

#### 4.3.2 Client Application & Intake

- **Domain:** Bringing in Clients
- **Purpose:** Take in client applications, conduct intake/qualification conversations, and produce client records marked ready for matching.
- **Mission-critical reasoning:** Without a way to enroll clients and produce matchable client records, Matching has no clients to match. The mission stops.
- **Handoffs to other backbone processes:** *Produces:* client record (for Matching to consume). *Consumes:* nothing in the backbone — application intake is the entry point.
- **Scope note:** This is a *combined* form of what the simulated client described as Application and Intake/Qualification activities. The combination is for iteration 1 only. **G-008 in the gap log captures this consultant judgment call.**

#### 4.3.3 Matching

- **Domain:** The Mentoring
- **Purpose:** Pair available mentors with ready clients and create engagement records that capture the rationale and the assignment.
- **Mission-critical reasoning:** This is the central operational activity of the mission. Without matching, no mentor-client pairing exists and the mission cannot be performed.
- **Handoffs to other backbone processes:** *Produces:* engagement record (for Session activity tracking to consume). *Consumes:* mentor record (from Mentor Application & Initial Activation), client record (from Client Application & Intake).

#### 4.3.4 Session activity tracking

- **Domain:** The Mentoring
- **Purpose:** Record the sessions occurring within active engagements so that the pairing produces visible, structured activity.
- **Mission-critical reasoning:** Without tracked sessions, there is no evidence the pairing is producing the structured engagement the mission promises. A pairing that exists only in name is not the mission.
- **Handoffs to other backbone processes:** *Consumes:* engagement record (from Matching).

### 4.4 Supporting processes (next iteration candidates)

Captured here for reference. Detailed in §2 above.

- Mentor outreach, full onboarding/training, active management, departure
- Client outreach, engagement monitoring, engagement closing
- Partner identification, partnership agreements, ongoing partner management

### 4.5 Deferred processes

Captured here for reference. Detailed in §2 above.

- Reactivation
- Joint events
- All Donors and Funding processes
- All Workshops and Events processes

### 4.6 Workability statement

A real CBM staff member can use the proposed backbone to: enroll a mentor, enroll a client, pair them, and track their sessions. This is the smallest set of connected processes that produces a working mentoring system in miniature. Anything outside this set is supporting or deferred work that does not block iteration 1 from being a usable system.

### 4.7 Honest framing for Session 2

The backbone proposal will be presented to the client confidently per Phase 1 guide §5.4, with the explicit acknowledgment that:

- The combinations made in §4.3.1 and §4.3.2 are consultant judgment calls (G-007, G-008) — the client may push back and want them separated
- The "minimum activation" framing for both mentor and client paths may not match how CBM actually does the work — the client may want fuller activation in iteration 1
- All Donors/Funding deferral may surprise or concern the client — the deferred-not-dismissed framing from Phase 1 guide §5.4 will be deployed
- All Workshops/Events deferral may also surprise — same framing
- The cross-domain dependency between The Mentor Pool, Bringing in Clients, and The Mentoring is the methodology's signature surfacing and should be presented as such

---

## 5. Proposed Initial CRM Candidate Set

### 5.1 Document framing

Per Phase 1 guide §7.4, the Initial CRM Candidate Set is one of the four Phase 1 outputs. In a real engagement this would be a standalone document. Embedded here.

### 5.2 Constraints driving the selection

Drawn from Session 1 Part D (CRM context notes §5.5) plus narrow factual constraint extraction from prior CRM evaluation documents (per ground rules §2.2 v0.2):

**Operational constraints:**
- Open-source preferred (FOSS-First principle)
- Cost-tiered: free or near-free at iteration 1 scale
- Self-hostable preferred where capacity exists
- Senior-accessible UI (mentors range up to 70s+, technology comfort variable)
- Browser-based, not app-driven
- Workflow automation configurable without custom code
- One tech-capable administrator with no developer-level expertise

**Integration constraints (factual content extracted from prior evaluation docs, conclusions excluded):**
- Google Workspace integration required (CBM uses Google Workspace; per-user Gmail OAuth would be valuable)
- WordPress integration required via REST API (CBM's website is on WordPress)
- Calendar integration desirable (mentor scheduling)

**Operational scope constraints:**
- Mentoring relationship management is the primary use case
- Engagements, sessions, and outcome tracking are core
- Visibility rules required for confidentiality
- Fundraising and event management are explicitly NOT iteration 1 (per the proposed backbone) — secondary consideration only

### 5.3 Candidate set

The proposed candidate set has three options, representing meaningfully different approaches to the constraints:

#### 5.3.1 EspoCRM

- **Hosting model:** standalone, self-hostable on any LAMP/LEMP stack or Docker
- **Approximate cost:** open-source, $0 license; hosting $20–$60/month
- **Why in the candidate set:** modern lightweight standalone open-source CRM with strong custom-entity support. Built-in workflow automation without code (the BPM engine). Standard REST API for WordPress integration. Per-user Google OAuth integration available. Modern browser-based UI considered senior-accessible.
- **Likely strength relative to backbone:** custom entities and dynamic logic make it natural to model Engagements, Sessions, Mentor lifecycle states declaratively. CRM Builder's existing tooling supports it.
- **Likely weakness relative to backbone:** smaller community than CiviCRM. If iteration 2+ adds donor work, the donor features are less mature.

#### 5.3.2 CiviCRM

- **Hosting model:** plugin for WordPress, Drupal, or Joomla — cannot run standalone. CBM's WordPress is a fit.
- **Approximate cost:** open-source, $0 license; hosting included with WordPress hosting
- **Why in the candidate set:** purpose-built for nonprofit work. Native fundraising, donor management, events, memberships, grants — these match CBM's eventual iteration 2+ scope cleanly. Large nonprofit-focused community.
- **Likely strength relative to backbone:** if iteration 2+ adds donor and event work, CiviCRM's native capability is significant. Nonprofit terminology and workflows align with CBM's eventual full scope.
- **Likely weakness relative to backbone:** UI is reportedly more dated than EspoCRM (worth verifying against the senior-accessible UI requirement during iteration). Mentoring relationships are not native and would need custom modeling. Per-user Gmail OAuth is not native. Standalone hosting is not an option.

#### 5.3.3 SuiteCRM

- **Hosting model:** standalone, self-hostable
- **Approximate cost:** open-source, $0 license; hosting $20–$60/month
- **Why in the candidate set:** mature general-purpose open-source CRM (fork of SugarCRM). Established ecosystem. Self-hostable. REST API. Workflow automation without code. Represents the "traditional general-purpose CRM" approach as a counterpoint to EspoCRM (lightweight modern) and CiviCRM (nonprofit-specialized).
- **Likely strength relative to backbone:** mature ecosystem, broader plugin/integration availability than newer CRMs.
- **Likely weakness relative to backbone:** UI is more traditional and may be less senior-accessible than EspoCRM. Custom entity modeling is somewhat more cumbersome than EspoCRM. Mentoring use case is general-CRM-shaped rather than purpose-fit.

### 5.4 Why these three

These three represent meaningfully different shapes of solution:

- **EspoCRM** — lightweight, modern, customizable, standalone
- **CiviCRM** — nonprofit-specialized, native fundraising/events, requires CMS host
- **SuiteCRM** — traditional general-purpose, mature, standalone

A meaningful comparison requires meaningful differences. Three commercial cloud-hosted CRMs of similar shape would give CBM a much narrower comparison.

The candidate set deliberately does **not** include:

- **Closed-source commercial CRMs** (Salesforce, HubSpot, Microsoft Dynamics, Zoho) — violates FOSS-First principle. CBM has stated this principle explicitly, and the candidate set should honor it. If CBM wants to evaluate a commercial option in Session 2, that's a conversation, not a default inclusion.
- **Microsoft / Google built-in CRM tools** — not full CRMs; insufficient for the operational scope.
- **Niche nonprofit/mentoring-specific tools** (e.g., MentorcliQ, Together) — not investigated for FOSS status; many are commercial. Mentoring-specific tools may be worth a conversation in Session 2 if CBM brings them up, but are not in the default candidate set.

### 5.5 Multi-deploy declaration

Multi-deploy is the default mode of operation. CBM has not committed to a CRM, so the iteration 1 deployment will produce three running instances — one on each candidate — for parallel comparison.

### 5.6 Honest framing for Session 2

The candidate set will be presented to the client confidently per Phase 1 guide §5.5, with the explicit acknowledgment that:

- The candidate set is open to client adjustment — drop any of these, add others if there are products CBM specifically wants to evaluate
- The senior-accessible UI requirement is a hard constraint that may favor EspoCRM in evaluation, but the *evaluation* happens through actual deployment in iteration 1, not from the consultant's pre-judgment
- The consultant deliberately avoided inheriting the prior CRM evaluation document's recommendation. CBM may have already discussed EspoCRM internally; the methodology's value is in letting the comparison happen empirically rather than reading prior consultants' verdicts

---

## 6. Step 4 Outputs

### 6.1 What Step 4 produced

- **Process classification proposal** (§2) — 21 processes classified as 4 mission-critical, 10 supporting, 7 deferred
- **Workability check** (§3) — confirmed the proposed backbone is workable for one realistic case end-to-end; surfaced the cross-domain dependency between The Mentor Pool, Bringing in Clients, and The Mentoring
- **Proposed Prioritized Backbone** (§4) — embedded artifact ready for Session 2 verification
- **Proposed Initial CRM Candidate Set** (§5) — embedded artifact ready for Session 2 verification (multi-deploy, three meaningfully different open-source candidates)
- **Two new gap log entries** (G-007, G-008) — process-combination judgment calls

### 6.2 What Step 5 (Session 2 simulation) needs from Step 4

Step 5 needs:

- The proposed Prioritized Backbone, presented confidently with grounded reasoning per Phase 1 guide §5.4
- The proposed Initial CRM Candidate Set, presented per Phase 1 guide §5.5
- The honest framing notes (§4.7 and §5.6) so the consultant enters Session 2 prepared for likely client push-back points
- The gap log entries that affect backbone composition (G-007, G-008 specifically — the combinations may not survive Session 2 client review)

### 6.3 What was harder in this between-sessions step

- **Honest acknowledgment of confirmation bias risk.** The consultant came into Step 4 knowing what the candidate backbone Doug confirmed earlier looked like (Mentor enrollment + Mentee intake + Matching + Session logging). The proposed backbone matches that exactly. Per ground rules §6, this is named openly: the priority test logically leads to this conclusion (the workability check is grounded), but the consultant cannot fully unsee what they know. The mitigation was to log the combination judgment calls (G-007, G-008) honestly — the backbone is *not* identical to four canonical original-methodology processes; the combinations are consultant simplifications that the client may or may not accept.
- **The CRM candidate set involved factual extraction from documents the consultant was instructed to keep at arm's length.** The prior CRM evaluation documents have a clear EspoCRM-favored conclusion. The consultant pulled factual constraints (Google Workspace usage, WordPress as website, integration requirements) without inheriting the conclusion. This required active discipline; the temptation to let the prior evaluation's conclusion settle the candidate set was real. The candidate set as proposed deliberately includes EspoCRM, CiviCRM, and SuiteCRM as three meaningfully different shapes; the prior evaluation's preference for EspoCRM is not inherited as a recommendation.

### 6.4 What worked well in this between-sessions step

- The priority test produced clean classifications for most processes. Donors/Funding and Workshops/Events were clearly deferred against the test, even though they may be operationally important to CBM in absolute terms.
- The workability check produced an unambiguous result — the cross-domain dependency surfaced cleanly, and no additional processes had to be added beyond the four mission-critical ones.
- The candidate set selection produced three meaningfully different shapes without inheriting the prior evaluation's verdict.

---

*End of document.*
