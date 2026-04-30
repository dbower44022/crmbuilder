# CBM Redo — Gap Log

**Document type:** Captured execution artifact (rolling, updated through redo execution)
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/evolved-methodology/cbm-redo/cbm-redo-gap-log.md`
**Last Updated:** 04-30-26 19:55
**Version:** 0.3 (Session 1 + Step 4 + Session 2 entries)

---

## Status

This document is the rolling gap log for the CBM redo, per `cbm-redo-ground-rules.md` §4. It records every gap encountered during the simulated execution: places where the in-bounds source material couldn't cleanly answer a consultant question (Tier 3), and places where an inference was made and hedged (Tier 2).

The gap log is one of the experiment's primary outputs. Per ground rules §4.1, gaps are valuable — they tell us where Phase 1's interview design might struggle in a real engagement. A gap log that's suspiciously short is itself a signal that something is being suppressed.

This document grows through Steps 3, 4, 5, and (if applicable) 6 of the execution plan. It is then the primary input to Step 7 (pre-validation findings draft) and Step 8 (validation pass with CBM).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 04-30-26 18:30 | Doug Bower / Claude | Initial creation. Six entries from Step 3 (Session 1 simulation): G-001 through G-006. |
| 0.2 | 04-30-26 19:15 | Doug Bower / Claude | Two entries added from Step 4 (between-sessions work): G-007 (Mentor Application & Initial Activation combination), G-008 (Client Application & Intake combination). Both are consultant judgment calls about process combination for iteration 1. |
| 0.3 | 04-30-26 19:55 | Doug Bower / Claude | One new entry added from Step 5 (Session 2 simulation): G-009 (CiviCRM senior-accessibility evaluation criterion). G-007 and G-008 marked as resolved by Session 2 — client pushed back on the combinations and the backbone was updated to carry them as separate processes. The classification of donor recording also changed from deferred to supporting based on client pushback in Session 2. |

---

## Change Log

**Version 0.1 (04-30-26 18:30):** Initial creation alongside `cbm-redo-step-3-session-1.md`. Six entries logged from Session 1: G-001 (intake-vs-reactivation boundary), G-002 (joint events overlap between Partners and Workshops domains), G-003 (donor work scope between operational team and board), G-004 (workshop follow-up cross-domain connection), G-005 (prior CRM evaluation document use), G-006 (funding domain scope boundary).

**Version 0.2 (04-30-26 19:15):** Two entries added from Step 4 (between-sessions work, recorded in `cbm-redo-step-4-between-sessions.md`):

- **G-007** — Mentor Application & Initial Activation: consultant judgment call to combine what the simulated client described as separate Application/Screening and Onboarding/Training activities into a single iteration-1 process. The consultant's reasoning was that the *minimum activation* portion of onboarding (enough to mark a screened mentor as available-for-matching) is mission-critical, while the full onboarding/training process is supporting. The combination simplifies the iteration 1 backbone but introduces a question for client review: does CBM consider Application + Initial Activation as one process or two?
- **G-008** — Client Application & Intake: parallel consultant judgment call combining Application and Intake/Qualification into a single iteration-1 process. The simulated client in Session 1 described these as distinct activities with the boundary acknowledged as fuzzy (G-001 is related). The combination simplifies the iteration 1 backbone; same question for client review.

Both G-007 and G-008 are explicitly carried forward to Session 2 (Step 5) for client verification. They may also be carried to the validation pass with CBM (Step 8) depending on how Session 2 resolves them.

**Version 0.3 (04-30-26 19:55):** One new entry from Step 5 (Session 2 simulation, recorded in `cbm-redo-step-5-session-2.md`):

- **G-009** — CiviCRM senior-accessibility evaluation criterion: in Session 2 Part C, the client questioned including CiviCRM in the candidate set on senior-accessibility-of-UI grounds. After discussion the client agreed to keep CiviCRM in but with the explicit understanding that senior-accessibility would be an evaluation criterion surfaced during iteration 1 use. This is a finding worth capturing because it shapes what iteration 1's evaluation has to make visible — not just feature-by-feature comparison but specifically how each CRM feels in use to senior users.

Resolutions of prior gaps in Session 2:

- **G-007 resolved.** Client pushback in Session 2 §3.4 established that Mentor Application and Mentor Initial Activation are loosely coupled in time (weeks may pass between application and review; weeks may pass between review and activation). The consultant accepted the client's correction and updated the proposed backbone to carry them as two separate processes rather than one combined process. The simplification was tested and found wanting, and the test surfaced cleanly. **No carry-forward to validation pass needed.**
- **G-008 resolved.** Same logic for Client Application and Client Intake — pushback from the client led to splitting them. **No carry-forward to validation pass needed.**

Reclassification driven by Session 2:

- **Donor Recording** moved from deferred to supporting per client pushback in Session 2 §3.5. The other three Donors/Funding processes (donor outreach, stewardship, reporting) remain deferred because they depend on donor recording being in place first. This is not a new gap; it's a classification update reflecting the deferred-not-dismissed framing.

Updated carry-forward to validation pass:

- **Definitely carry forward:** G-001 (intake/reactivation boundary), G-003 (donor scope between operational team and board), G-006 (where the operational/strategic line falls). All three remain — Session 2 didn't fully resolve them; they may need real-CBM verification.
- **Carry forward only if relevant to iteration 1:** G-002 (joint events), G-004 (workshop follow-up). Iteration 1 does not include Workshops or Partner joint events, so these do not need carry-forward in this round.
- **Carry forward conditional on iteration 1 outcome:** G-009 (senior-accessibility) becomes an iteration 1 evaluation criterion rather than a pre-deployment validation question.
- **Resolved, no carry-forward:** G-007, G-008 (resolved in Session 2).
- **Not relevant to validation pass:** G-005 (consultant process question).

**Best estimate of validation pass scope: 3 substantive questions** (G-001, G-003, G-006), plus a brief check that the new methodology's overall approach feels reasonable. Tractable for a 30–60 minute conversation per ground rules §7.

---

## 1. How to Read This Document

Each entry uses the format specified in `cbm-redo-ground-rules.md` §4.2:

- **Gap ID** — sequential identifier (G-001, G-002, ...)
- **Session and moment** — which step and which part of that step
- **Question or proposal that hit the gap** — exact consultant prompt
- **What the in-bounds material does say** — closest supporting content
- **Why it's a gap** — Tier 2 (inference made, hedged) or Tier 3 (declined)
- **What the simulator did** — how the simulated client responded; how the consultant proceeded
- **Carried forward to validation pass with CBM?** — yes/no, with reason

---

## 2. Entries

### G-001 — Intake vs. reactivation boundary

- **Session and moment:** Step 3, Session 1 Part C (process surfacing within "Bringing in Clients" domain)
- **Question or proposal that hit the gap:** Consultant was capturing processes within the "Bringing in Clients" domain. Client offered a process for clients who come in but aren't an immediate fit — keeping them in the system to re-engage when timing is right. Client described this as *"not really intake; more like reactivation when the time is right."*
- **What the in-bounds material does say:** The current Master PRD §1.3 and the Domain PRDs describe client-side activities including outreach, application, and intake. The original methodology has a separate sub-domain for reactivation under Client Recruiting. The legacy materials don't explicitly distinguish intake from reactivation as separate processes.
- **Why it's a gap:** Tier 2. The simulated client had operational language for the activity but expressed uncertainty about whether it's a separate process or part of intake. This is a genuine boundary ambiguity, not a methodology decision.
- **What the simulator did:** Simulated client expressed the ambiguity directly. Consultant captured both interpretations as a possible fourth process within "Bringing in Clients" and noted the boundary ambiguity for between-sessions work. No deep-dive.
- **Carried forward to validation pass with CBM?** Yes — worth confirming with CBM whether they treat reactivation as a distinct activity or part of intake. The answer affects backbone composition.

### G-002 — Joint events overlap between Partners and Workshops domains

- **Session and moment:** Step 3, Session 1 Part C (process surfacing within "Partner Relationships" domain)
- **Question or proposal that hit the gap:** Client described "joint events / co-programming" as a partner-domain activity, then noted *"the same event might be a workshop and a partner-co-hosted thing."*
- **What the in-bounds material does say:** The legacy Master PRD §4 mentions Partner Management as a domain. Tony's draft mentions *"co-programming"* as part of partner-first approach. Workshops are described separately across documents. None of the in-bounds material explicitly resolves the question of whether a co-hosted event belongs to the partner domain, the workshop domain, or both.
- **Why it's a gap:** Tier 2. The client offered the observation that the boundary is fuzzy without resolving it. The consultant didn't push for resolution because Phase 1 isn't the place for sub-domain boundary decisions.
- **What the simulator did:** Captured the cross-domain connection as a note for the workability check. The proposed backbone in Step 4 has to handle this — if workshops and partners are both in iteration 1, the connection has to be modeled; if only one is, the question of where co-hosted events go has to be answered.
- **Carried forward to validation pass with CBM?** Maybe — depends on whether the connection turns out to affect iteration 1 backbone composition. If yes, validate; if no, hold.

### G-003 — Donor work scope between operational team and board

- **Session and moment:** Step 3, Session 1 Part C (process surfacing within "Donors and Funding" domain)
- **Question or proposal that hit the gap:** Client described donor-domain activities, then noted *"some of this is the executive director's work, not really the program team's. The board does some of it too."*
- **What the in-bounds material does say:** The legacy Master PRD §3 (Guiding Technology Principles) and the Strategic Planning Session document acknowledge funding as an organizational concern but don't specify what's CRM-tracked vs. board-handled. The current Master PRD §1.3 names "report impact to funders and partners" as a CRM responsibility but doesn't differentiate operational from strategic donor work.
- **Why it's a gap:** Tier 2. The client knows operationally that donor work splits between teams but the in-bounds material doesn't crisply identify which slice belongs in CRM scope.
- **What the simulator did:** Captured the boundary in §5.4 of the session document. Consultant accepted the client's framing — operational team's donor work in CRM scope, strategic relationship work largely out — without forcing a sharper line.
- **Carried forward to validation pass with CBM?** Yes — worth confirming where the operational/strategic line falls for donor work, since it affects whether "Donors and Funding" is mission-critical, supporting, or partially-deferred for iteration 1.

### G-004 — Workshop follow-up cross-domain connection

- **Session and moment:** Step 3, Session 1 Part C (process surfacing within "Workshops and Events" domain)
- **Question or proposal that hit the gap:** Client noted that workshop follow-up converts attendees into prospective clients, mentors, or donors — *"a workshop where we get fifty attendees but no follow-up is mostly wasted."*
- **What the in-bounds material does say:** Tony's draft mentions workshops and clinics as service offerings. The legacy Master PRD treats Workshop & Event Management as its own domain. Neither explicitly characterizes follow-up as cross-domain bridging.
- **Why it's a gap:** Tier 2. The cross-domain connection is operationally real but the structural question — does follow-up live in Workshops, in the destination domain (clients/mentors/donors), or in both — isn't resolved by the in-bounds material.
- **What the simulator did:** Captured the connection as a note for the workability check. Workshops as a domain has thin connection to mentor-client matching directly; its value lands through the follow-up bridge to other domains. This may affect whether Workshops belongs in iteration 1 at all.
- **Carried forward to validation pass with CBM?** Yes — if the proposed backbone defers Workshops to a later iteration, validate that this matches CBM's prioritization. If the workability check argues Workshops needs to be in iteration 1 because of the follow-up bridge, validate that interpretation.

### G-005 — Prior CRM evaluation document use

- **Session and moment:** Step 3, Session 1 Part D (CRM context and constraints)
- **Question or proposal that hit the gap:** Client said CBM has done some informal CRM evaluation but hasn't committed. Client did not name specific products evaluated.
- **What the in-bounds material does say:** Per Step 1 survey, the Archive contains `espoCRM-vs-CiviCRM_comparison.docx` and `EspoCRM_Architecture_Guide.docx`. The ground rules §2.2 (as revised in v0.2) allow factual constraint content from these documents to inform the Initial CRM Candidate Set work, with their evaluative conclusions excluded.
- **Why it's a gap:** Tier 3 in the live conversation (the simulated client didn't have ready answers about which products were evaluated and what was found). The information exists in in-bounds material but not in the client's voice as represented in the conversation.
- **What the simulator did:** Consultant accepted the client's framing (informal evaluation, no commitment) and captured a between-sessions task to mine prior evaluation documents for factual constraint content (budget mentions, hosting preferences, team-capacity statements) without inheriting their conclusions about which product is best.
- **Carried forward to validation pass with CBM?** No — this gap is about the consultant's between-sessions process, not about uncertain findings to confirm with CBM.

### G-006 — Funding domain scope boundary

- **Session and moment:** Step 3, Session 1 Part D (CRM context and constraints)
- **Question or proposal that hit the gap:** Client confirmed that operational donor work is in CRM scope but strategic relationship work is largely board/executive-director work. Where does the line fall in practice?
- **What the in-bounds material does say:** Same as G-003 — the materials acknowledge the dual ownership but don't crisply specify the boundary.
- **Why it's a gap:** Tier 3. The client framed the answer in general terms ("mix of both") without offering a specific operational line.
- **What the simulator did:** Captured the general framing without forcing specifics. This is acceptable for Phase 1; the line has to get clearer for iteration 1's backbone composition (whether and which donor processes are in iteration 1) but not for the Phase 1 outputs themselves.
- **Carried forward to validation pass with CBM?** Yes — paired with G-003 as a single validation question: "where does the line fall between operational donor work that the CRM should track and strategic donor work that lives outside the operational team's CRM use?"

### G-007 — Mentor Application & Initial Activation combination — RESOLVED in Session 2

- **Session and moment:** Step 4, between-sessions process classification (§2.3 of `cbm-redo-step-4-between-sessions.md`)
- **Question or proposal that hit the gap:** The proposed Prioritized Backbone needs a mission-critical process that produces matchable mentor records. The simulated client in Session 1 described Application/Screening and Onboarding/Training as separate activities. The consultant's analysis: full onboarding/training is supporting, but a *minimum activation* portion (enough to mark a screened mentor as available-for-matching) is mission-critical. The combination question: should iteration 1 carry one combined process (Application + Initial Activation) or two separate processes (Application as mission-critical, Initial Activation as a sub-component)?
- **What the in-bounds material does say:** The current Master PRD describes Provisional → Active → Inactive → Departed mentor lifecycle states, suggesting that activation is a real distinct event after application/screening. The legacy materials don't specify the boundary. The simulated client in Session 1 described five activities including Application/Screening and Onboarding/Training as separate but did not explicitly address whether activation is a sub-step of onboarding or a separate event.
- **Why it's a gap:** Tier 2 — consultant judgment call about process granularity for iteration 1. The combination simplified the backbone but elided a real distinction CBM may consider important.
- **What the simulator did:** Proposed the combined form for iteration 1 with the explicit acknowledgment that this was a consultant judgment call. The proposed Prioritized Backbone §4.3.1 explicitly referenced this gap.
- **Resolution in Session 2:** The client pushed back in Session 2 §3.4, establishing that Mentor Application and Mentor Initial Activation are loosely coupled in time at CBM (weeks may pass between application and review; weeks between review and activation). The combination was incorrect for CBM's operational reality. The consultant accepted the correction and the proposed backbone was updated to carry them as two separate processes — Mentor Application and Mentor Initial Activation — both classified mission-critical for iteration 1. The simplification failed at first contact with the client; this is the right outcome.
- **Carried forward to validation pass with CBM?** No — resolved in Session 2.

### G-008 — Client Application & Intake combination — RESOLVED in Session 2

- **Session and moment:** Step 4, between-sessions process classification (§2.4 of `cbm-redo-step-4-between-sessions.md`)
- **Question or proposal that hit the gap:** Parallel to G-007 for the client side. The proposed backbone needs a mission-critical process that produces matchable client records. The simulated client described Application and Intake/Qualification as distinct activities (Session 1 §4.4) with the boundary acknowledged as fuzzy. The combination question: should iteration 1 carry one combined process or two?
- **What the in-bounds material does say:** The current Master PRD describes a client lifecycle (applicant → active → inactive → closed) and the existing methodology distinguishes Application from Intake. The simulated client in Session 1 indicated the boundary is fuzzy — *"Intake is its own thing... but I can see the case either way; the boundary is fuzzy."*
- **Why it's a gap:** Tier 2 — consultant judgment call. The simulated client themselves acknowledged the boundary was unclear; the consultant's combination call leveraged that ambiguity to simplify the backbone but didn't match what CBM wanted.
- **What the simulator did:** Proposed the combined form for iteration 1 with explicit acknowledgment that this was a consultant judgment call. The proposed Prioritized Backbone §4.3.2 explicitly referenced this gap.
- **Resolution in Session 2:** Client applied the same loose-coupling-in-time framing from G-007 and the consultant accepted the same correction. Backbone updated to carry Client Application and Client Intake as two separate mission-critical processes for iteration 1.
- **Carried forward to validation pass with CBM?** No — resolved in Session 2.

### G-009 — CiviCRM senior-accessibility evaluation criterion

- **Session and moment:** Step 5, Session 2 Part C (CRM candidate review, §4.3 of `cbm-redo-step-5-session-2.md`)
- **Question or proposal that hit the gap:** Client questioned CiviCRM's inclusion in the candidate set on senior-accessibility-of-UI grounds, citing prior experience that CiviCRM's interface is dated and may not meet CBM's senior-accessible-UI requirement.
- **What the in-bounds material does say:** The legacy Master PRD §3 establishes senior-accessible UI as a non-negotiable principle. The Archive's prior CRM evaluation document also rates CiviCRM's UI as "dated, complex" relative to EspoCRM's "clean, modern, mobile-ready" — but per ground rules §2.2, the evaluative conclusions of that document are out-of-bounds; the consultant should not have inherited that judgment. The client's senior-accessibility concern is independent and based on the client's own prior experience.
- **Why it's a gap:** Tier 2 — the client has a prior about CiviCRM that the consultant cannot verify against in-bounds material without using the prior CRM evaluation's conclusion (which is out-of-bounds). The consultant accepted the client's framing as legitimate operational concern.
- **What the simulator did:** Reframed the candidate-set debate as an evaluation-criterion clarification. CiviCRM stays in the candidate set; senior-accessibility becomes an explicit evaluation criterion that iteration 1's hands-on use will test.
- **Carried forward to validation pass with CBM?** No — this is an iteration 1 evaluation criterion rather than a pre-deployment validation question. The iteration 1 evaluation will surface whether CBM's mentors find each candidate's UI senior-accessible enough for the work.

---

## 3. Gap Profile Observations

### 3.1 Gap density and resolution

Nine entries logged across Steps 3, 4, and 5 of the redo. Two of those (G-007, G-008) were resolved in Session 2 — the consultant's between-sessions judgment calls were tested by client review and corrected. Seven entries remain open in some form.

The two resolutions are themselves a healthy sign. The methodology produced consultant judgment calls during between-sessions work, the calls were tested in Session 2, and the test surfaced cleanly. This is the iterative model working as intended — proposals are made, tested, and corrected through client engagement rather than locked in upfront.

### 3.2 Gap clustering

The nine entries cluster around four themes:

**Cross-domain boundaries** (G-001, G-002, G-004, G-006) — places where the client's natural categorization of work has fuzzy edges between domains. Consistent with the methodology's expectation that boundary ambiguity surfaces during elicitation and gets resolved through workability checks or iteration deployment.

**Operational-strategic split** (G-003, G-006) — places where work spans the boundary between operational team's CRM-trackable work and board's relationship work. Relevant primarily for Donors/Funding domain.

**Process-granularity judgment calls** (G-007, G-008) — both resolved in Session 2 as the simplifications failed at first contact with the client.

**Empirical-comparison criteria** (G-009) — surfaced in Session 2 when the client's prior experience with a candidate raised a concern that the iteration 1 evaluation must specifically test.

### 3.3 Methodology-flagged moments

The Phase 1 guide flags certain moments as discipline-sensitive: confident proposals, push-back, deferred-vs-elicited transitions. Session 2's Part B exercised all three:

- The confident proposal opening (§3.2 of Step 5) landed cleanly — the client engaged rather than rubber-stamped
- The push-back-and-engage moment (§3.4 — process combinations) led to a substantive change to the backbone
- The deferred-not-dismissed transition (§3.5 — Donors/Funding) led to the donor recording reclassification

None of those moments produced a new gap. The discipline held.

### 3.4 Implications for Steps 7 and 8

For Step 7 (pre-validation findings draft):

- The redo's Phase 1 outputs are complete (Mission Statement, Domain Inventory, Prioritized Backbone, Initial CRM Candidate Set)
- The gap log has nine entries with clear classification of which carry forward to validation
- The comparison criteria from ground rules §5.2 should be applied to what was produced

For Step 8 (validation pass with CBM):

- **Definitely carry forward:** G-001, G-003, G-006 (intake/reactivation boundary, donor scope, operational/strategic line)
- **Carry forward only if relevant to iteration 1:** G-002, G-004 (joint events, workshop follow-up — not relevant given iteration 1 scope)
- **Carry forward conditional on iteration 1 outcome:** G-009 (becomes iteration 1 evaluation criterion, not a pre-deployment validation question)
- **Resolved, no carry-forward:** G-007, G-008
- **Not relevant to validation pass:** G-005

**Best estimate of validation pass scope: 3 substantive questions** (G-001, G-003, G-006) plus a brief check on the new methodology's overall approach. Tractable for a 30–60 minute conversation per ground rules §7.

---

*End of document. May be updated by Step 6 if Session 3 occurs (it did not, per Step 5 §7.4).*
