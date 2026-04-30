# CBM Redo — Gap Log

**Document type:** Captured execution artifact (rolling, updated through redo execution)
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/evolved-methodology/cbm-redo/cbm-redo-gap-log.md`
**Last Updated:** 04-30-26 18:30
**Version:** 0.1 (Session 1 entries only)

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

---

## Change Log

**Version 0.1 (04-30-26 18:30):** Initial creation alongside `cbm-redo-step-3-session-1.md`. Six entries logged from Session 1: G-001 (intake-vs-reactivation boundary), G-002 (joint events overlap between Partners and Workshops domains), G-003 (donor work scope between operational team and board), G-004 (workshop follow-up cross-domain connection), G-005 (prior CRM evaluation document use), G-006 (funding domain scope boundary).

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

---

## 3. Gap Profile Observations

### 3.1 Gap density

Six gaps in one ~90-minute simulated session. Per ground rules §4.1, this seems like a moderate, expected number — not zero (which would be suspicious), not so many that the session couldn't proceed.

### 3.2 Gap clustering

All six gaps cluster around two themes:

**Cross-domain boundaries** (G-001, G-002, G-004, G-006) — places where the client's natural categorization of work has fuzzy edges between domains, and the in-bounds material doesn't resolve them. This is consistent with the new methodology's hypothesis (Principle 6 from the phase outline: best-practice defaults fill non-iteration scope) — the methodology *expects* boundary ambiguity to surface and be resolved either through workability checks or through iteration deployment, not through upfront elicitation.

**Operational-strategic split** (G-003, G-006) — places where work spans the boundary between the operational team's CRM-trackable work and the board's relationship work. This is a real organizational pattern not unique to CBM, and the methodology may need to develop a vocabulary for it.

### 3.3 No gaps in the methodology-flagged moments

The Phase 1 guide flags certain moments as discipline-sensitive: confident proposals, push-back, deferred-vs-elicited transitions. None of the Session 1 gaps occurred at those moments. This is partly because Session 1 doesn't include the confident proposal moment (that's Session 2), and partly because the push-back moments worked smoothly with operational mission as the test (the client confirmed the priority test cleanly).

### 3.4 Implications for Step 4 (between-sessions)

The proposed Prioritized Backbone produced in Step 4 should:

- Acknowledge the four cross-domain boundary gaps (G-001, G-002, G-004, G-006) and choose a defensible interpretation for each, marking each interpretation as low-confidence
- Treat the operational-strategic donor split (G-003, G-006) honestly — propose a backbone that includes only the operational portion of donor work and call this out explicitly in Session 2

### 3.5 Implications for the validation pass with CBM (Step 8)

Of the six gaps:

- **Definitely carry forward:** G-001, G-003, G-006 (intake/reactivation boundary, donor scope, where the operational/strategic line falls)
- **Carry forward only if relevant to iteration 1:** G-002, G-004 (joint events, workshop follow-up — only matter if those domains end up in iteration 1)
- **Do not carry forward:** G-005 (about consultant's between-sessions process, not about findings to validate)

This produces a tractable validation pass focused on operational scope questions rather than methodology meta-questions, consistent with ground rules §7.

---

*End of document. Will be updated as Steps 4, 5, and (if applicable) 6 add entries.*
