# CBM Redo — Step 1 Survey Findings

**Document type:** Research artifact for evolved methodology test
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/evolved-methodology/cbm-redo/cbm-redo-step-1-survey.md`
**Last Updated:** 04-30-26 17:25
**Version:** 1.0

---

## Status

This document records the findings of Step 1 of the CBM redo execution plan, as specified in `cbm-redo-ground-rules.md` §9. Step 1 verifies the in-bounds artifacts list (§2.2 of the ground rules) against the actual contents of the `dbower44022/ClevelandBusinessMentoring` repository.

The survey was conducted on 04-30-26 at the state of the CBM repository as of commit history through that date. The findings drove the v0.2 revision of `cbm-redo-ground-rules.md`.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 04-30-26 17:25 | Doug Bower / Claude | Initial finalized survey. |

---

## Change Log

**Version 1.0 (04-30-26 17:25):** Survey conducted by sparse-clone of `dbower44022/ClevelandBusinessMentoring` and inspection of its `PRDs/` tree. Findings drove five revisions to ground rules §2.2 plus minor additions; ground rules document bumped to v0.2 in same work session. Survey results captured here as a permanent reference for the redo's later steps.

---

## 1. Survey Method

The survey was conducted by:

1. Sparse-cloning the `dbower44022/ClevelandBusinessMentoring` repository with `CLAUDE.md` and the entire `PRDs/` tree
2. Pulling the latest from `main`
3. Listing the directory structure to depth sufficient to identify all artifacts
4. Inspecting representative files where classification was ambiguous (specifically `CBM-Consolidated-Design.md` to confirm it is methodology-synthesis content and `Archive/CBM-PRD-Master.docx` to confirm it contains operational-mission content)
5. Applying the §2.1 logic from `cbm-redo-ground-rules.md` to each identified artifact category
6. Comparing the resulting classification against the v0.1 §2.2 list

The survey did not read the full content of every CBM document — that level of inspection happens during the redo proper, not during artifact classification. The survey is sufficient to establish what *categories* of artifact exist and how each category should be classified.

---

## 2. Repository Structure Found

The `PRDs/` tree at survey time contains the following structural elements:

**Top-level documents:**

- `CBM-Master-PRD.docx` — current methodology Master PRD
- `CBM-Domain-PRD-Mentoring.md` and `.docx` — Domain PRDs (also live in domain subdirs)
- `CBM-Domain-PRD-MentorRecruitment.md` and `.docx`
- `CBM-Domain-PRD-ClientRecruiting.md` and `.docx`
- `CBM-Domain-PRD-Fundraising.md` (no `.docx` at top-level; FU has only `.docx` for sub-documents)
- `CBM-Consolidated-Design.md` — synthesis document for YAML generation (methodology-decision content)
- `CBM-Entity-Inventory.docx` — reconciliation output
- `CBM-EspoCRM-HowTo.docx` — product-specific implementation
- `CBM-PRD-CRM-Client-Process-4.1-4.3-4.1 - Client Intake.drawio.png` — workflow diagram
- `SESSION-PROMPT-Entity-Discovery.md` — prompt file
- `UPDATE-PROMPT-Master-PRD-Cross-Domain-Services.md` — prompt file

**Domain subdirectories:**

- `MN/` (Mentoring) — Domain PRD, five process documents (MN-INTAKE, MN-MATCH, MN-ENGAGE, MN-CLOSE, MN-INACTIVE), corresponding PDFs, several SESSION-PROMPT and UPDATE-PROMPT files, one PHASE6-TEST-Gap-Analysis.md (methodology testing artifact)
- `MR/` (Mentor Recruitment) — Domain PRD, five process documents (MR-RECRUIT, MR-APPLY, MR-ONBOARD, MR-MANAGE, MR-DEPART), several SESSION-PROMPT files, three `generate-*.js` scripts
- `CR/` (Client Recruiting) — Domain Overview, Domain PRD, four sub-domain subdirectories, multiple SESSION-PROMPT files including stakeholder review and carry-forward prompts
  - `CR/PARTNER/` — Sub-Domain Overview, two process documents (PROSPECT, MANAGE), three SESSION-PROMPT files
  - `CR/MARKETING/` — Sub-Domain Overview, two process documents (CAMPAIGNS, CONTACTS), four SESSION-PROMPT files
  - `CR/EVENTS/` — Sub-Domain Overview, two process documents (MANAGE, CONVERT), three SESSION-PROMPT files
  - `CR/REACTIVATE/` — Sub-Domain Overview, one process document (OUTREACH), two SESSION-PROMPT files
- `FU/` (Fundraising) — Domain Overview, four process documents (FU-PROSPECT, FU-RECORD, FU-REPORT, FU-STEWARD), several SESSION-PROMPT files, five `generate-*.js` scripts, `carry-forward/` subdirectory containing two carry-forward SESSION-PROMPT files

**Other top-level subdirectories:**

- `entities/` — eleven Entity PRDs (Account, Contact, Engagement, Session, Dues, Event, EventRegistration, MarketingCampaign, CampaignGroup, CampaignEngagement, Segment, PartnershipAgreement), several SESSION-PROMPT files, multiple `generate-*.js` scripts
- `services/` — only `NOTES/` populated (with `NOTES-MANAGE.docx` and one SESSION-PROMPT); `EMAIL/`, `CALENDAR/`, `SURVEY/` directories named in CBM CLAUDE.md as "future" but not present
- `pilot/` — `PILOT-FINDINGS.md`
- `Graphics/`, `WorkflowDiagrams/` — visual content (PNG, drawio)
- `Archive/` — substantial pre-methodology and legacy material; ~30 files, see §3 below for inventory

---

## 3. Archive Inventory

The Archive directory was inspected in detail because its classification was ambiguous in v0.1 of the ground rules. Contents:

**Pre-methodology / strategic material (most useful for redo):**

- `Cleveland_Business_Mentors_Mission_tonysdraft (1).docx` — early mission drafting
- `STRATEGIC PLANNING SESSION (1).docx` — strategic planning notes
- `CBM-Decisions-Log.docx` — operational decisions log
- `BBM 2026 Proposed Budget.xlsx` — budget data (operational/financial)

**Legacy Master and Domain-equivalent PRDs (factual content valuable; structure not):**

- `CBM-PRD-Master.docx` — legacy Master PRD with operational mission language and Year 1 targets
- `CBM-PRD-CRM-Client.docx` — legacy client-domain PRD
- `CBM-PRD-CRM-Mentor.docx` — legacy mentor-domain PRD
- `CBM-PRD-CRM-Partners.docx` — legacy partners-domain PRD
- `CBM-PRD-CRM-Implementation.docx` — legacy implementation overview
- `CBM-PRD-CRM-Deploy.docx` and `.md` — legacy deployment specification
- `CBM-PRD-CRM-Deploy-Context.md` — legacy deployment context
- `CBM-PRD-CRM.docx` and `.pdf` — legacy comprehensive CRM PRD
- `CBM-PRD-Communication-Workshops-Learning.docx` — legacy workshop/communication PRD
- `CBM-PRD-Forms.docx` and `.md` — legacy forms specification
- `CBM-PRD-LearningPlatform.docx` — legacy learning platform PRD
- `CBM-PRD-Security.docx` — legacy security specification
- `CBM-PRD-Volunteer-Donor-Documents-Reporting-Security.docx` — composite legacy PRD
- `CBM-PRD-Website.docx` and `.md` — legacy website specification

**Workflow diagrams (visual, mostly redundant):**

- `CBM-PRD-CRM-Client-Process-4.1-4.3.drawio`
- `CBM-PRD-CRM-Mentor-Process-4.1-4.7.drawio`
- `CBM-PRD-CRM-Client.pdf`
- `CBM-PRD-CRM-Mentor.pdf`
- `CBM-PRD-CRM-Partners.pdf`
- `CRM High Level Workflows and Notes.docx`, `(1).docx`, `_Edited.docx`

**CRM technology evaluation and architecture (factual constraints in-bounds; conclusions out-of-bounds):**

- `espoCRM-vs-CiviCRM_comparison.docx`
- `EspoCRM_Architecture_Guide.docx`
- `cbm_Espo_ArchitectureDiscussion.docx`
- `espo-open_API-Spec.md`
- `CBM-EspoCRM-Navigation-Design.docx`
- `CBM-EspoCRM-HowTo.docx` (also exists at top-level)

**Other directories within Archive:**

- `Claude AI Discussions/` — accumulated Claude session content (not inspected; assumed methodology-shaped, treat as out-of-bounds)
- `Forms-Implementation-Package/` — implementation artifact (out-of-bounds)
- `Implementation Docs/` — implementation artifacts (out-of-bounds)
- `Old PRD Documents/` — archived earlier-than-archive PRDs (likely in-bounds for factual content; not inspected in detail)

**Other Archive material:**

- `Google workspace-checklist.docx` — operational checklist
- `README.md` — Archive directory documentation

---

## 4. Classification Findings

For each artifact category, the §2.1 logic was applied. Findings:

### 4.1 Categories the v0.1 ground rules already addressed correctly

- Master PRD → in-bounds (operational content only)
- Domain PRDs → in-bounds (operational content only)
- Process documents → in-bounds (activity descriptions only)
- Entity PRDs → in-bounds (field descriptions, operational use only)
- CLAUDE.md → out-of-bounds
- All prompt files → out-of-bounds
- Pilot findings → out-of-bounds
- Reconciliation documents (Entity Inventory) → out-of-bounds

### 4.2 Categories the v0.1 ground rules missed or under-specified

- **Cross-Domain Service process documents** (`services/NOTES/NOTES-MANAGE.docx`): not addressed in v0.1. Should be in-bounds (activity descriptions only), parallel to domain process documents. Added to v0.2.
- **Consolidated Design and synthesis documents** (`CBM-Consolidated-Design.md`): described in v0.1 only as "reconciliation documents" generically, but the actual document isn't named "reconciliation" and could escape that classification on a literal read. Document explicitly identifies itself as "the single authoritative source for YAML generation" and resolves cross-domain conflicts — clearly methodology-decision content. v0.2 adds explicit out-of-bounds entry.
- **Sub-Domain structure within CR**: v0.1 didn't address the existence of sub-domains. Sub-domain *structure* (the choice to split CR into PARTNER, MARKETING, EVENTS, REACTIVATE) is methodology-decision content. Sub-Domain Overview documents codify that decision and are out-of-bounds. Process documents *within* sub-domains describe activities and are in-bounds. v0.2 clarifies both directions.
- **Domain Overview documents**: distinct from Domain PRDs. Domain Overviews exist for CR and FU; their job in the original methodology is to assemble upstream context including domain-structural decisions, so they're methodology-decision content. v0.2 adds them to out-of-bounds while preserving Domain PRDs as in-bounds.
- **Product-specific implementation documentation** (`CBM-EspoCRM-HowTo.docx`, navigation design): would contaminate the CRM Candidate Set work. v0.2 adds to out-of-bounds.
- **Methodology tooling** (`generate-*.js` scripts, gap-analysis documents): clearly methodology-side content. v0.2 makes the out-of-bounds classification explicit.
- **Workflow diagrams**: visual representations of content already in text documents. Not a primary source, but not strictly out-of-bounds either (a real consultant would look at diagrams provided to them). v0.2 classifies as not-primary-source.

### 4.3 The Archive question

This was the most consequential classification call. The Archive contains pre-methodology and legacy material that predates the current methodology's interpretive decisions. Two competing considerations:

**For inclusion:** The Archive is closer to the client's voice than the current methodology artifacts because it predates the current consultant's interpretive work. A simulated Phase 1 first-engagement should have access to material like a real first-engagement would — and a real client would naturally have pre-engagement materials of exactly this kind.

**Against inclusion:** The Archive contains methodology-style decisions from prior consultants (the legacy CBM-PRD-CRM-* docs). Including them whole-hog would import contamination from a different methodology era.

**Resolution:** Apply the operational-vs-methodology line within Archive content, just as we apply it everywhere else. Operational descriptions of CBM (mission, mentoring activity, financial scale, organizational structure) are in-bounds regardless of which document they appear in. Methodology decisions encoded in any Archive document (the legacy Master PRD's organization into "sections," prior consultants' priority calls, prior structural categorizations) are out-of-bounds.

This is the same rule as elsewhere; the Archive isn't getting special treatment, it's getting the same treatment under the same rule.

### 4.4 Prior CRM evaluation documents

The Archive contains documents that evaluated CRM platforms (EspoCRM vs. CiviCRM comparison, EspoCRM architecture guide, etc.). These were produced as part of choosing the current CRM. Under §2.1's logic:

- Their **factual content about CBM's constraints** (budget, hosting preferences, team capacity, integration needs) is in-bounds for Phase 1's Initial CRM Candidate Set work — these are factual claims a real client would express
- Their **evaluative conclusions** ("EspoCRM is better than CiviCRM for CBM because...") are methodology-decision content and out-of-bounds

v0.2 captures this narrow allowance explicitly.

---

## 5. What This Survey Did Not Determine

- **Whether the in-bounds material is sufficient to answer Phase 1's questions.** This survey establishes which material the simulated client may draw from. Whether the answers are *available* in that material is a question the redo itself answers.
- **The detailed content of each in-bounds document.** Step 1 establishes classification; the redo proper engages with content.
- **Whether the Archive's pre-methodology material is fully consistent with the current methodology's claims about CBM.** Some discrepancies likely exist (the legacy Master PRD says something the current Master PRD doesn't, or vice versa). Per §2.1, when discrepancies arise during the redo, the simulated client treats both sources as available and may express uncertainty. The discrepancies themselves are interesting findings and would be logged in the gap log.

---

## 6. Implications for Subsequent Steps

**Step 2 (Pre-engagement):** the simulated consultant's pre-engagement reading is limited to the Master PRD's mission and organizational overview sections per ground rules §2.4. The Archive's mission-related material may be referenced as additional pre-engagement context insofar as a real client would have provided it. Specifically, the legacy Master PRD's mission and operating model sections, the strategic planning session document, and the mission draft document are reasonable pre-engagement-equivalent materials.

**Step 3 (Session 1 simulation):** the simulated client has access to all in-bounds material per the revised §2.2. The Archive's pre-methodology content is particularly valuable here because it's closer to the client's voice.

**Step 4 (Between-sessions):** the simulated consultant's proposed Prioritized Backbone draws on what surfaced in Session 1; cross-references against Archive operational content are permitted to validate consistency.

**Step 5 (Session 2 simulation):** the simulated client may push back on the proposed backbone using only material in-bounds. The discipline of not letting the client cite methodology decisions encoded in current artifacts is preserved.

**Steps 7–9:** survey findings don't directly affect synthesis, validation pass, or final findings.

---

## 7. Recommendation Captured

The recommendation arising from Step 1, which has been executed in v0.2 of `cbm-redo-ground-rules.md`:

> Update §2.2 with the five revisions plus minor additions documented in the v0.2 change log. No other ground-rules sections require change. Step 1 closes; Step 2 (pre-engagement reading) may now begin.

Step 1 is complete.

---

*End of document.*
