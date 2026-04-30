# CBM Redo — Step 2: Pre-Engagement Reading and Consultant Notes

**Document type:** Captured execution of the evolved methodology test
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/evolved-methodology/cbm-redo/cbm-redo-step-2-pre-engagement.md`
**Last Updated:** 04-30-26 17:55
**Version:** 1.0

---

## Status

This document captures Step 2 of the CBM redo execution plan, per `cbm-redo-ground-rules.md` §9. Step 2 is the simulated consultant's pre-engagement reading: what materials were read, what was noticed, what conclusions were drawn, and what questions are prepared for Session 1.

The document captures both the reading and the reasoning, so the audit trail back to specific materials is preserved. Per the Phase 1 interview guide §2 and the ground rules §2.4, the simulated consultant is constrained to read only the limited materials that approximate "what a real consultant would have at engagement start" — much less than the totality of in-bounds material.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 04-30-26 17:55 | Doug Bower / Claude | Initial captured execution of Step 2. |

---

## Change Log

**Version 1.0 (04-30-26 17:55):** Captured execution of Step 2 — pre-engagement reading. Records the four documents read, the operational and constraint findings extracted from each, the org-type recognition call, the pattern library check (none exists; no-library mode applies), the Session 1 question preparation, and the simulated consultant's working hypotheses entering Session 1. No methodology-decision content was inferred or used; reasoning is grounded in factual content from the in-bounds materials.

---

## 1. Materials Read

Per ground rules §2.4 and the Phase 1 guide §2, pre-engagement reading is limited to materials a real consultant would receive as a prospectus or initial intake document. Four documents were read in this round:

### 1.1 Current CBM Master PRD — sections 1.1, 1.2, 1.3 only

`PRDs/CBM-Master-PRD.docx`, sections "Mission and Context," "Operating Model," and "Why a CRM is Needed."

The Persona section (section 2 onward) was *not* read because personas are methodology-organized content. Personas are defined through interpretive consultant work and would contaminate the simulated consultant's view of how CBM should be structured.

### 1.2 Legacy Master PRD — sections 1, 2, 3 only

`PRDs/Archive/CBM-PRD-Master.docx`, sections "Purpose & Scope," "Organization Overview" (including 2.1 Mission, 2.2 Operating Model, 2.3 Initial Scale), and "Guiding Technology Principles."

Section 4 (Technology Domains Overview) and beyond were *not* read because they reflect prior methodology decisions about how CBM's technology stack should be organized into domains. The Domain Overview table in particular is a prior-consultant categorization that, if read, would contaminate the new methodology's domain identification work.

### 1.3 Mission draft — Tony's draft

`PRDs/Archive/Cleveland_Business_Mentors_Mission_tonysdraft (1).docx`, full document.

This document is dated February 26, 2026 and is labeled "draft for discussion." Its content is mission-level material — the kind of statement of purpose a real prospectus would include. Read in full because the entire document is operational mission content with no methodology decisions encoded.

### 1.4 Strategic Planning Session document

`PRDs/Archive/STRATEGIC PLANNING SESSION (1).docx`, full document.

This is a meeting agenda from the founding planning of CBM. The full document was read because it is a structured record of how CBM thought about its own founding — operational and strategic intent, not methodology decisions about CRM structure.

### 1.5 Materials deliberately not read

The following were inspected briefly during Step 1 (the survey) but not read for content during Step 2:

- **The current Master PRD's Persona section and beyond.** Per ground rules §2.1, personas are methodology-decision content.
- **Domain PRDs, process documents, Entity PRDs.** These are not pre-engagement materials. They become available only as the simulated client cites their content in response to consultant questions during the sessions.
- **`CBM-Decisions-Log.docx` from Archive.** Could plausibly count as pre-engagement material but its content is operational decisions made *during* CBM's history, not at engagement start. Holding it for citation during the sessions if it becomes relevant.
- **`BBM 2026 Proposed Budget.xlsx`.** Operational financial information that a real consultant might receive as part of intake. Decided against reading at this stage to keep pre-engagement bounded; will allow the simulated client to cite specific budget facts during Session 1 Part D if needed.
- **Prior CRM evaluation documents.** Reading them now would prematurely shape the consultant's CRM Candidate Set proposal. Per the ground rules, factual constraints from these documents are in-bounds for the candidate set work between sessions, not for pre-engagement.

---

## 2. What Was Noticed

This section captures what the simulated consultant noticed about CBM from the pre-engagement reading. Each finding is grounded in specific source material; speculation and inference are explicitly marked.

### 2.1 What CBM does, operationally

From the four documents combined:

- **CBM provides free, confidential, impartial mentoring and practical business education** to entrepreneurs, small businesses, and nonprofits. The "free, confidential, impartial" framing recurs in all four documents and appears to be a stable, deliberate self-description.
- **The geographic scope is exclusive to Northeast Ohio.** Both the current and legacy Master PRDs specify "exclusively in Northeast Ohio." Tony's draft uses the same phrasing. The Strategic Planning Session document narrows even further to "the established Cleveland footprint." The geographic exclusivity is not negotiable in CBM's self-description.
- **Mentoring is delivered by volunteer professionals** — experienced business and nonprofit professionals donating their time. This is operating-model-level information (current Master PRD §1.2 and legacy §2.2; Tony's draft "How We Work").
- **CBM also delivers workshops, clinics, office hours, and curated referrals to trusted Northeast Ohio ecosystem partners.** This appears across all four documents, though it is described as supplementary to one-to-one mentoring. The mentoring is the headline; workshops and referrals are auxiliary.
- **Year 1 operating targets are 25–30 mentors and 100–200 clients, with one technology-capable administrator.** This is from current Master PRD §1.2 and legacy §2.3. The legacy document is more explicit (it has a structured table); the current document refers to the same numbers in narrative.
- **CBM is a small organization at this scale.** Implication of the Year 1 numbers: a single tech-capable admin manages the platform, which means whatever CRM CBM uses needs to be operable by one non-engineer.

### 2.2 What CBM cares about, as expressed in their own materials

- **Always free for clients — no fees, no commissions, no equity, no referral arrangements.** This is one of the most emphatically stated commitments. Tony's draft labels it "Always free for clients — period." This is mission-critical to CBM's identity, not a preference.
- **Confidentiality is non-negotiable.** Recurs across all documents. Tony's draft: "mentoring conversations and client information are treated as confidential except where disclosure is required by law." Has implications for technology: the legacy Master PRD names "Data Privacy and Confidentiality" as a guiding technology principle. The current CRM master PRD §1.3 names "manage the mentor population through recruitment, onboarding, and ongoing participation" and "track client status throughout the full lifecycle" as core CRM duties — but the *confidentiality* requirement is not a feature, it's a constraint on how all features must work.
- **Impartiality and conflict-of-interest standards.** Tony's draft names this explicitly: "mentors do not market, sell, or pitch paid services to clients during mentoring engagements." This may have implications for CRM features around mentor profiles or matching (e.g., visibility rules).
- **Local control and partner-first approach.** Both Tony's draft and the strategic planning document express commitment to working through partners ("collaborate across the Northeast Ohio ecosystem," "Curated referrals to trusted Northeast Ohio ecosystem partners"). Partners are not just a backdrop — they are an explicit relationship CBM commits to maintaining.
- **The operating model is "lean."** Both Master PRDs describe lean operations. Implication: tooling that requires significant administrative overhead is a poor fit.

### 2.3 What CBM appears to identify as the central operational activity

From current Master PRD §1.3:

> "CBM's core mission — connecting the right mentor with the right client and managing that relationship through to a successful outcome..."

This sentence is the single clearest articulation of what CBM identifies as its operational center: **matching mentors to clients and managing the engagement.** Everything else (workshops, partner referrals, donor relationships) is real work but is described in supporting terms relative to this central thread.

The simulated consultant carries this into Session 1 as a working hypothesis: *the mission's operational center is mentor-client matching and engagement management.* Subject to confirmation in Session 1 Part A.

### 2.4 CBM as an organization in transition

The strategic planning document is dated as a founding-era artifact (no specific date but content places it at organizational founding). It says things like *"Why are we starting another organization?"* and *"Phase 1: Mobilizing the Leadership Team."* The current Master PRD is dated 04-10-26 and reflects an operational organization. Tony's mission draft is dated February 26, 2026 — between the two.

This trajectory matters. CBM has been actively building itself out, which means:

- The organization may still be refining what counts as core vs. supporting work
- Some processes the current Master PRD describes may be aspirational rather than fully operational
- The CRM is being designed for an operational state CBM is moving toward, not strictly the state it is in today

The simulated consultant should listen for this distinction in Session 1 — "do you do this today, or are you planning to?"

### 2.5 Pre-existing technology context

From the legacy Master PRD §3 (Guiding Technology Principles), several constraints surface even though this section is not yet methodology-decision content (it's stated principles, not tooling choices):

- **FOSS-First.** Free and open-source options preferred; only commercial when no FOSS alternative.
- **Cost Tiering.** Start with free/zero-cost tools.
- **Avoid Vendor Lock-In.** Prefer tools that allow free data export.
- **Simplicity Over Features.** "Can a non-technical senior volunteer use this confidently with minimal training?" is given as the test.
- **Local Control.** Self-hosting preferred where practical.
- **Volunteer-Friendly and Senior-Accessible UI.** Mentors are often older professionals; clean interfaces, large readable text, browser-based preferred over mobile apps, minimal number of platforms.

These are principles CBM has stated about itself, not consultant interpretations. They are valid pre-engagement context. They have direct implications for the Initial CRM Candidate Set:

- Open-source options should be in the candidate set
- Cost matters; free or near-free tier preferred
- Self-hostable options should be in the candidate set
- The user-experience bar is *senior-accessible* — this is unusual and worth honoring in candidate selection
- Browser-based, not app-driven

The Strategic Planning Session document mentions specific technology categories (CRM selection, Google Workspace/Office 365, website development, Mailchimp/Constant Contact) as items to discuss but doesn't take positions on them. This tells us CBM has been thinking about its tech stack actively and pragmatically.

---

## 3. Org Type Recognition

### 3.1 The org type call

CBM is recognizable as a **nonprofit volunteer-driven mentoring organization for small business and nonprofit clients.** Specifically:

- Service-delivery mission (provides direct service rather than advocacy or research)
- Volunteer-staffed core service (mentoring) with small administrative team
- Free-to-client model funded externally (donors, grants, sponsors)
- Geographic concentration (Northeast Ohio, specifically Cleveland)
- Multi-stakeholder relationships (mentees as service recipients; mentors as service providers; partners as ecosystem; donors as funders)

This org type bears strong family resemblance to organizations like SCORE, SBDCs, and similar nonprofit mentoring infrastructure. It is distinct from advocacy nonprofits, foundation-grant-makers, and research institutions.

### 3.2 What the simulated consultant should expect of this org type

Based on consultant judgment about this org type (no pattern library entry exists for CBM; per ground rules §2.4, judgment about org types is allowed where CBM-specific accumulated knowledge is not):

- **Mission-critical processes likely cluster around mentor-client matching and engagement lifecycle.** This is the org's reason for being and is supported by the current Master PRD's own articulation of its core mission.
- **Mentor pipeline likely matters operationally.** A mentoring org without enough mentors fails. Recruitment, vetting, training, and retention of volunteers is an ongoing concern with operational consequences.
- **Client intake and qualification likely matter.** A mentoring org that wastes mentor time on misaligned clients fails differently. There's likely a screening or qualification dimension to client intake.
- **Partners are likely a real domain, not background.** The repeated emphasis in CBM's own materials on partner relationships suggests partners are an active operational concern.
- **Donor and funder relationships are real for a free-service nonprofit.** No fees means external funding. There's a domain there even if it's not headline.
- **Reporting and impact measurement likely matter** to satisfy donor and board requirements.

These are expectations to test, not conclusions. The simulated consultant carries them into Session 1 as starting hypotheses but verifies through the conversation, not by assertion.

### 3.3 Pattern library check

Per ground rules §2.4 and Phase 1 guide §2.2: no pattern library exists yet. The simulated consultant operates in "no entry" mode for this engagement. This is acknowledged honestly in Session 2 per the Phase 1 guide §8.1: *"Because [client] is the first engagement of its type for us, this proposed backbone is based more on judgment than on accumulated patterns."*

For CBM specifically, this means the proposed backbone in Session 2 will be marked low-confidence even though consultant judgment is being applied. CBM's pushback is *expected* and welcomed.

---

## 4. Working Hypotheses Entering Session 1

The simulated consultant carries the following working hypotheses into Session 1. They are *not* conclusions; they are starting points the conversation will confirm or correct.

### Hypothesis A — operational mission

CBM's operational mission centers on **matching mentees (small businesses, entrepreneurs, nonprofits) with volunteer mentors and supporting that pairing through structured engagements.** Workshops, clinics, partner referrals, and donor relationships are real but secondary.

*Source for the hypothesis:* current Master PRD §1.3 ("connecting the right mentor with the right client and managing that relationship through to a successful outcome"); Tony's draft (mentoring listed first; workshops listed as supplementing).

*To confirm in Session 1 Part A:* "If you stopped matching mentors and clients tomorrow, would you no longer be doing your mission?"

### Hypothesis B — likely domains

The likely domains for CBM's mission are:

1. **Mentoring** — the mentor-mentee engagement lifecycle (the operational center)
2. **Mentor management** — recruiting, onboarding, training, and retaining the volunteer mentor population
3. **Client management** — finding, qualifying, intake, and supporting mentees
4. **Partner relationships** — managing the ecosystem of organizations CBM works with
5. **Funding / development** — donors, sponsors, grants

*Source for the hypothesis:* the current Master PRD §1.3 explicitly names client lifecycle, mentor population management, partner relationships, and impact reporting as CRM responsibilities. Tony's draft explicitly names the same categories ("Stakeholder Commitments" sections for Clients, Volunteers, Partners).

*To confirm in Session 1 Part B:* "What are the major areas of work the mission requires?"

These hypotheses correspond *roughly* to the existing CBM domain structure (MN, MR, CR, FU), but the simulated consultant deliberately doesn't assume that mapping. The client may name domains differently. In particular: the consultant's "Client management" hypothesis may map to CBM's "Client Recruiting," but the boundary between intake (which feels like Mentoring) and recruiting (which feels like outreach) is something the client should articulate.

### Hypothesis C — likely mission-critical thread

Within the likely domains, the most likely mission-critical thread is:

- Mentor exists and is enrollable → Client exists and is enrollable → Pair created → Activity tracked

This is the smallest set of capabilities that lets a real CBM staff member do the operational work end-to-end.

*Source for the hypothesis:* current Master PRD §1.3 ("connecting the right mentor with the right client and managing that relationship through to a successful outcome").

*To verify through workability check between Sessions:* the proposed backbone must include enough of mentor recruitment to produce mentor records, enough of client intake to produce client records, and a matching capability that joins them — plus session/engagement tracking to make the pairing produce visible work.

### Hypothesis D — CRM constraints

Based on the legacy Master PRD's stated technology principles:

- **Cost-sensitive.** Free or near-free tier preferred. Cost-tiered upgrade.
- **Open-source preferred.** FOSS evaluated before commercial.
- **Self-hostable options preferred.**
- **Senior-accessible UI is a hard requirement.** Mentors are often older professionals.
- **Browser-based preferred over apps.**

*Source for the hypothesis:* legacy Master PRD §3 (Guiding Technology Principles, eight principles).

*To confirm in Session 1 Part D:* "What constraints do you have on technology selection? What have you ruled in or out?"

### Hypothesis E — organizational maturity

CBM is an organization in active build-out, not strictly steady-state operation. Some processes the current Master PRD describes may be aspirational. Some processes that exist may be different in practice from how they're documented.

*Source for the hypothesis:* the document trajectory (Strategic Planning Session at founding → Tony's mission draft Feb 2026 → current Master PRD April 2026 v2.6 still in "Draft" status); the operating-targets language ("Year 1 targets") implying the org is in or near Year 1.

*To listen for in Session 1 generally:* "Do you do this today, or are you planning to?" The distinction matters because the methodology should design for what CBM does, not what it intends.

---

## 5. Session 1 Question Preparation

Per Phase 1 guide §2.4, the simulated consultant prepares 3–6 follow-up questions specific to the client based on the pre-engagement materials. These are questions in addition to the structured walkthrough, targeted at things the materials surfaced as worth probing.

### 5.1 Question 1 — operational/aspirational distinction

> "I noticed the Master PRD references Year 1 operating targets — 25–30 mentors and 100–200 clients. Are you currently operating at that scale, or building toward it? When you describe what your team does in our conversation today, I want to make sure we're talking about what's actually happening rather than what's planned."

*Why ask:* anchors the conversation in current operations and surfaces the aspirational/operational gap explicitly.

### 5.2 Question 2 — workshops/clinics relative to mentoring

> "Both your Master PRD and Tony's mission draft describe workshops, clinics, and office hours as real activities, but they're consistently described as supplementing one-to-one mentoring. Is that an accurate read — that the mentor-mentee pairing is the operational center, and workshops are real but secondary?"

*Why ask:* tests Hypothesis A (operational mission) directly, with a specific framing the client either confirms or corrects.

### 5.3 Question 3 — partners as operational

> "Your strategic planning document and Tony's draft both put significant weight on partner relationships — 'partner-first approach,' 'curated referrals to trusted partners.' Is partner relationship management a major area of work for your team, or is it more of a guiding principle that shapes how mentoring happens?"

*Why ask:* the materials are ambiguous. Partners could be a domain in their own right, or they could be a flavor of how mentoring operates. The distinction matters for backbone composition.

### 5.4 Question 4 — confidentiality as constraint

> "Confidentiality recurs across all your materials — 'free, confidential, and impartial.' I want to make sure I understand operationally: when you say confidential, who can see what, and what would be a violation?"

*Why ask:* confidentiality is a non-negotiable constraint that will shape system design (visibility rules, role-based access, audit). Worth surfacing early so it doesn't get treated as a feature later.

### 5.5 Question 5 — funding model and constraints

> "You operate as free-to-client, which means you're funded externally — donors, grants, possibly sponsors. Is donor and funder relationship management work your team does today, or is that primarily handled by the board or executive team?"

*Why ask:* the funding domain (FU in CBM's naming) is a real question. If the operational team handles it, it's a domain to consider. If it's board-driven, it's outside the operational team's CRM work and may be deferred.

### 5.6 Question 6 — technology-team capacity

> "The Master PRD mentions 'one tech-capable administrator' as the Year 1 staff. Is that one person who handles CRM administration alongside other duties, or someone whose specific role is technology? And for the mentors and clients who interact with the system — what's their technology comfort level?"

*Why ask:* affects all CRM Candidate Set decisions. The "senior-accessible UI" principle matters more or less depending on actual mentor demographics.

---

## 6. What the Consultant Will Not Carry Into Session 1

This section is as important as what the consultant *will* carry.

- **Specific domain names beyond CBM's own "the work the mission requires" framing.** The simulated consultant has hypothesized five domains but will let the client name them in Session 1 Part B. The consultant does not enter Session 1 with names like "MN," "MR," "CR," "FU" pre-loaded.
- **Specific process names.** The consultant does not enter Session 1 expecting "Intake," "Match," "Engage," "Close," "Inactive" as the Mentoring processes — that's the original methodology's structure, and using those names would shape the conversation toward confirming the original structure rather than letting CBM articulate its own work.
- **Specific entity names.** Same logic.
- **Priority classifications.** None proposed yet. The proposed backbone is between-sessions work.
- **Specific CRM products in mind.** None yet. The Initial CRM Candidate Set is between-sessions work shaped by Session 1 Part D.
- **Sub-domain structure (e.g., CR's PARTNER, MARKETING, EVENTS, REACTIVATE breakdown).** This is methodology-decision content from the original CBM engagement and is out-of-bounds.

If the consultant catches itself reaching for any of these during Session 1, that's a discipline failure to be logged in the gap log.

---

## 7. Notes for the Gap Log

No gaps yet — Step 2 read available materials successfully. The materials answered everything the pre-engagement reading was meant to surface.

One note for future gap log entries: the consultant resisted the temptation to read Decisions Log, the budget spreadsheet, and the prior CRM evaluation documents during pre-engagement. Each of those would have produced more useful starting context but would have over-extended the pre-engagement step beyond what a real consultant would have at engagement start. If Session 1 reveals that some of that material would have been genuinely useful at the pre-engagement stage, that itself is a finding about the methodology — Phase 1's pre-engagement scoping might be too narrow.

---

## 8. Step 2 Outputs

This section names what Step 2 produced and what it feeds into Step 3.

### 8.1 What Step 2 produced

- **Pre-engagement reading completed.** Four documents read end-to-end (subject to in-bounds constraints).
- **Operational understanding of CBM established.** Summarized in §2.
- **Org type recognition.** §3.
- **Five working hypotheses for Session 1.** §4.
- **Six prepared questions for Session 1.** §5.
- **Discipline boundaries explicit.** §6.

### 8.2 What Step 3 (Session 1 simulation) needs from Step 2

Step 3 needs the consultant entering Session 1 with:

- A working hypothesis about CBM's operational mission, ready to test in Part A
- A working hypothesis about CBM's likely domains, ready to test in Part B
- An understanding of the technology constraints, ready to confirm in Part D
- Six pointed questions to layer on top of the structured Phase 1 walkthrough
- Awareness of the aspirational/operational distinction CBM appears to have

All of this is captured here. Step 2 closes; Step 3 may begin.

---

*End of document.*
