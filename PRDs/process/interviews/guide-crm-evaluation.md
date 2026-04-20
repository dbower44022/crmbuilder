# CRM Builder — CRM Evaluation Guide

**Version:** 1.0
**Last Updated:** 04-20-26
**Purpose:** AI guide for Phase 10 — CRM Selection (producing the CRM Evaluation Report)
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**See also:** `guide-yaml-generation.md` — Phase 9 produces the YAML this evaluation reads. `guide-domain-reconciliation.md` — produces the approved Domain PRDs this evaluation reads. `guide-carry-forward-updates.md` — used if this evaluation surfaces a Domain PRD or YAML gap that must be fixed before a platform can be selected.
**Authoring contract:** `authoring-standards.md` (Section 11 review checklist).

---

## How to Use This Guide

This guide is loaded as context for an AI producing the CRM
Evaluation Report for an implementation. The AI should read this
guide fully before beginning.

**This is a synthesis and comparison task, not an interview.** The
AI reads the approved Domain PRDs, the YAML program files, and
optionally the Service PRDs; extracts the implementation's
distinctive capability requirements; compares those requirements
against known CRM platforms from the AI's training knowledge; and
produces a Word-document evaluation report recommending the top two
platforms. The administrator's role is to answer a small number of
scoping questions and review the output.

**One implementation per conversation.** Each conversation produces
exactly one CRM Evaluation Report for one implementation.

**Session length:** 45–90 minutes. Longer for implementations with
many domains or unusual capability requirements.

**Inputs:**

- All approved Domain PRDs for the implementation
- All Service PRDs for the implementation
- All YAML program files (from Phase 9)
- Any Manual Configuration List (from Phase 9) and Exception List (from Phase 9), because these describe capabilities that YAML could not express and that will shape platform fit
- Optional: administrator-supplied scoping constraints (budget ceiling, hosting requirements, integration constraints, team skills, preferred platforms to include or exclude)

**Output:** One Word document — the CRM Evaluation Report —
committed to the implementation's repository at:

```
PRDs/{Implementation}-CRM-Evaluation.docx
```

**Cardinality:** Exactly one CRM Evaluation Report per implementation.

**Audience.** The CRM Evaluation Report is written for executive and
operational stakeholders who will decide on the platform. It is
business-language and accessible to non-technical readers, while
carrying enough specificity that an implementer reading it
understands the tradeoffs.

---

## What the CRM Evaluation Report Must Contain

The CRM Evaluation Report has six required sections.

| # | Section | Content |
|---|---------|---------|
| 1 | Implementation Capability Profile | Summary of the distinctive capability requirements this implementation places on a CRM. Drawn from the Domain PRDs, Service PRDs, YAML, and Manual Configuration List. Business-language. Organized by capability category (entities and fields, relationships, workflows and automation, reporting and analytics, integration, access control, hosting and operational, cost envelope). |
| 2 | Scoring Framework | The criteria used to assess platforms and the weight assigned to each, grounded in Section 1. Weights reflect this implementation's priorities, not a universal CRM scorecard. Explicitly states the evaluation methodology so the reader can replicate the logic. |
| 3 | Platform Assessments | One subsection per candidate platform considered. Each subsection: platform name, vendor, summary of how the platform meets the implementation's requirements, specific strengths relative to the defined entities/processes/workflows, tradeoffs and limitations and areas requiring workarounds, estimated cost and licensing, migration and integration implications. |
| 4 | Top Two Recommendation | Named top two platforms with the rationale for each and a head-to-head comparison on the criteria that most distinguish them. |
| 5 | Decision Path | What the administrator and stakeholders should do next to finalize the selection: proof-of-concept recommendations, trial account setup, reference customer introductions if the vendor offers them, and the specific capability risks each recommended platform should be validated against before commitment. |
| 6 | Source References | Which Domain PRDs, Service PRDs, and YAML files drove the evaluation, with Last Updated dates so a reader can verify which version of the requirements shaped the report. |

**Completeness standard.** The CRM Evaluation Report is complete
when Section 1 names every distinctive capability requirement the
Domain and Service PRDs establish; Section 2 names the scoring
framework explicitly; Section 3 assesses every candidate platform
against the framework at enough specificity that a reader can judge
the fit for their own priorities; Section 4 names exactly two
platforms with justified rationale; Section 5 gives the
administrator a concrete next-step set; and Section 6 enumerates
the source documents and their versions.

---

## Critical Rules

1. **Product names are permitted in this document — and required.** This is the only document in the process doc's document hierarchy where specific CRM platform names appear. Use them. The ban applies to Master PRDs, Entity PRDs, Domain PRDs, and process documents. It does not apply here (process doc Section 3.10 and the PRD Content Rules in the governing process). Use vendor and product names precisely.

2. **Business language, not jargon.** Even though product names are permitted, the report is written for stakeholders. Technical CRM concepts (metadata, entity inheritance, formula fields, workflow rules, field-level security) are named but explained in business terms. Prefer short paragraphs over long bulleted lists.

3. **Assess against the implementation's requirements, not against a universal scorecard.** A "feature-complete" platform that is overkill for a three-domain nonprofit is a worse fit than a simpler platform that meets requirements at lower cost. Weights in Section 2 reflect the specific implementation.

4. **Top two, not top one.** Stakeholders deserve a comparison. Recommending a single platform removes the stakeholder from the decision — which is not the goal of this phase. Phase 10's job is to narrow the choice, not to eliminate it.

5. **Name tradeoffs explicitly.** Every platform has tradeoffs. A platform assessment that only names strengths is incomplete and unactionable. The "Tradeoffs and Limitations" subsection is mandatory for every platform assessed.

6. **Do not invent capabilities the source documents don't support.** If a Domain PRD does not mention a capability and the YAML does not implement it, do not assume the implementation needs it. Requirements drift during evaluation is a common failure mode.

7. **Flag gaps in the source documents before evaluating.** If the Domain PRDs or YAML have gaps that prevent a fair platform comparison (e.g., a Domain PRD references a service that was never reconciled, or YAML is missing for a domain that the Domain PRDs define), pause and surface the gap. Do not paper over missing inputs with assumptions.

8. **Cost estimates are named as estimates.** License costs, implementation costs, and operating costs change with vendor pricing changes, discounts, and customer size. Every cost figure is annotated with the date the estimate was derived and the assumptions behind it. "Estimated $X/user/month at list price for 25-user tier as of {date}" — not "$X/user/month".

9. **Consider open-source and commercial platforms on equal footing.** The implementation's requirements — not the licensing model — determine fit. Open-source platforms may have lower upfront cost but higher operational burden; commercial platforms may have higher upfront cost but lower operational burden. Surface the tradeoff; do not privilege one licensing model by default.

10. **Acknowledge what the AI does not know.** Platform capabilities evolve; vendor roadmaps change; pricing changes; new platforms launch. The report's source-of-truth is the AI's training knowledge as of the model's cutoff date, supplemented by the administrator's current knowledge when provided. State the knowledge cutoff explicitly in Section 6.

11. **Confirmation gate before final Top-Two selection.** The evaluation is a judgment call. Present the full platform assessment to the administrator for review before committing to the Top Two recommendation. The administrator may know things about specific platforms (recent migrations gone badly, vendor relationship issues, team preferences from prior work) that should influence the final two (process doc Section 7.3).

12. **One deliverable per conversation.** The report is produced as a single Word document in one session. If the evaluation reveals that the source documents are not yet approved or YAML is not yet complete, stop — Phase 10 is blocked (process doc Section 7.5).

---

## Before Generation Begins

### Session-Start Checklist (process doc Section 7.1)

1. Ask which implementation is being worked on.
2. Read the implementation's `CLAUDE.md` for current state.
3. Identify the current phase and step — this session is Phase 10 CRM Selection.
4. Confirm that all Domain PRDs are approved (Phase 8 Stakeholder Review has completed), all Service PRDs are produced, and all YAML has been generated (Phase 9 complete).
5. State the current step and confirm with the administrator before beginning.

### Verify Inputs

> "For the CRM Evaluation Report, I need to confirm the following are available and in their approved state:
>
> - All Domain PRDs (post-stakeholder-review): {list, with ✓ / ✗ per domain}
> - All Service PRDs: {list, with ✓ / ✗ per service}
> - YAML program files for every domain and service: ✓ / ✗
> - Manual Configuration List: ✓ / ✗
> - Exception List (if any): ✓ / ✗ / N/A
>
> Is this the complete set? Any documents that are still in draft?"

If any Domain PRD is not approved or any YAML is not complete, stop.
Phase 10 depends on a stable requirements-and-implementation
baseline; evaluating against a moving target guarantees rework.

### Scoping Questions to the Administrator

Before generating, ask the administrator for scoping constraints:

> "A few quick scoping questions before I begin the evaluation:
>
> 1. **Budget ceiling.** Is there a budget range for platform licensing? If yes, what is it (total annual cost or per-user-per-month at expected scale)?
> 2. **Hosting constraints.** Does the organization require cloud-hosted, self-hosted, or on-premises? Any data residency requirements (e.g., EU, US)?
> 3. **Integration constraints.** Any systems the CRM must integrate with (email, calendar, accounting, survey, document management, custom apps) whose integration capability should be weighted heavily?
> 4. **Team skills.** Does the organization have in-house developers, admin staff, or external implementation partners? This affects which platforms are realistic operationally.
> 5. **Platforms to include or exclude.** Are there specific platforms you want considered (or ruled out) — for example, platforms the organization has prior experience with, or platforms on a pre-approved vendor list?
>
> These answers will shape Section 2 of the report. Ready to proceed after these?"

Record the administrator's answers. Use them in Section 2's scoring
framework and Section 3's candidate platform list.

### State the Plan

> "Here is how this session will work:
>
> 1. I will consolidate the implementation's distinctive capability requirements from the Domain PRDs, Service PRDs, and YAML. (Section 1 draft.)
> 2. I will define the scoring framework based on your scoping answers and the capability profile. (Section 2 draft.)
> 3. I will identify candidate platforms — typically three to six — and assess each against the framework. (Section 3 draft.)
> 4. I will propose a Top Two and the decision path. I will present these to you for confirmation or adjustment before finalizing.
> 5. I will produce the CRM Evaluation Report document.
>
> Ready?"

---

## Step 1 — Consolidate the Implementation Capability Profile

Read the input documents and extract capability requirements into a
structured profile. The output of this step is a draft Section 1 of
the report.

Organize capabilities into eight categories. Not every category is
material for every implementation — the profile names only what this
implementation actually requires.

### 1.1 Entities and fields

- Entity count (total, and split into native-like and custom).
- Field count and distribution by type (especially unusual types: multi-enum, calculated, file attachment, currency, complex date, JSON).
- Shared entities with discriminators (e.g., Contact with contactType: Client, Mentor, Partner) and the number of discriminator values.
- Platform-native entity types required (Person, Company, Event, or platform-neutral equivalents).

### 1.2 Relationships

- Relationship count.
- Mix of relationship types (one-to-many, many-to-one, many-to-many, self-referential, parent-hierarchical).
- Any unusual patterns (e.g., many-to-many with attributes, hierarchical with cycle prevention).

### 1.3 Workflows and automation

- Workflow count (from YAML `workflows:` blocks plus Manual Configuration List workflow entries).
- Trigger types used (create, update, scheduled, external webhook).
- Action types used (field update, create related record, send email, notify user, call external API).
- Any complex automations (multi-step orchestration, conditional branching, cross-entity cascading updates).

### 1.4 Reporting and analytics

- Saved view count (from YAML `savedViews:` blocks).
- Condition-expression complexity (deep-nested, cross-entity predicates).
- Cross-domain reporting requirements (e.g., oversight analytics from a parent domain covering sub-domain activity).
- Any dashboard or widget requirements surfaced in Domain PRDs.

### 1.5 Integration

- Integrations named in Domain PRDs or Service PRDs.
- Direction (inbound / outbound / bidirectional).
- Integration patterns (batch, real-time, webhook, API polling).
- Specific systems named by the administrator in scoping.

### 1.6 Access control

- Role count and role types (from Master PRD personas and any field-level permissions deferred to later phases).
- Field-level permission requirements (YAML v1.1 defers field-level permissions; Manual Configuration List entries should reflect them).
- Record-level sharing rules (by owner, by group, by criteria).

### 1.7 Hosting and operational

- Data residency constraints.
- Backup and disaster recovery expectations.
- Uptime requirements (if Domain PRDs specify any).
- Compliance requirements (HIPAA, GDPR, SOC 2) if mentioned in Domain PRDs or Master PRD.

### 1.8 Cost envelope

- Expected user count at launch and at 2-year horizon.
- Volume expectations (record counts per major entity).
- Administrator's stated budget from scoping.

### Step 1 Output

Draft Section 1 as a structured profile covering the eight categories
(or a subset, for categories that are not material). Keep each
category section to one to three paragraphs in business language,
with specific counts and examples drawn from the source documents.

Present to the administrator:

> "Here is the draft Implementation Capability Profile (Section 1). This is what the implementation demands of a CRM platform:
>
> {Section 1 draft}
>
> Does this accurately capture the implementation's requirements? Is anything missing or overstated?"

Await confirmation before proceeding.

---

## Step 2 — Define the Scoring Framework

Translate the capability profile into a weighted scoring framework.
The weights reflect this implementation, not a generic CRM scorecard.

### 2.1 Weight Derivation

Typical weight distribution, adjusted per implementation:

- **Must-haves (veto criteria).** Capabilities without which no platform is viable. Often: number of entities/fields, specific integration requirements, hosting constraints. Platforms that fail a must-have are not scored — they are eliminated.
- **High-weight criteria.** Capabilities that dominate platform fit. Often: workflow complexity, access control sophistication, reporting flexibility.
- **Medium-weight criteria.** Capabilities that differentiate platforms but aren't decisive. Often: UI polish, API maturity, ecosystem depth.
- **Low-weight criteria.** Capabilities that round out the comparison. Often: specific field types, minor integration conveniences.

### 2.2 Scoring Framework Content

Draft Section 2 as:

- The full list of criteria used in the evaluation, organized by weight tier.
- For each criterion, a one-line definition of what "meets the criterion" means for this implementation.
- The source of each criterion (which part of Section 1 it reflects, or which administrator scoping answer).

Present to the administrator:

> "Here is the draft Scoring Framework (Section 2). These are the criteria I will use to assess platforms:
>
> {Section 2 draft, with criteria in weight tiers}
>
> Does the weighting match your priorities? Is any criterion missing or over-weighted?"

Await confirmation.

---

## Step 3 — Platform Assessment

Identify candidate platforms and assess each against the scoring
framework.

### 3.1 Candidate Platform Identification

Typical candidate list size: three to six platforms. Source:

- Well-known commercial CRM platforms that could plausibly fit the capability profile (Salesforce, HubSpot, Zoho CRM, Microsoft Dynamics 365, Pipedrive, etc.).
- Open-source and self-hosted platforms that could plausibly fit (SuiteCRM, EspoCRM, Vtiger, etc.).
- Nonprofit-specific platforms where relevant (Salesforce Nonprofit Cloud, Neon CRM, Bloomerang, Little Green Light, etc.).
- Any platform the administrator named in scoping.

Exclude platforms the administrator explicitly ruled out.

Eliminate platforms that fail any Section 2 veto criterion (do not
assess further). State the elimination in the report and the
criterion that eliminated the platform.

### 3.2 Assessment Per Platform

For each surviving candidate, draft a subsection with six parts:

1. **Platform summary.** One paragraph: vendor, hosting model, licensing model, target customer segment, market position.
2. **How the platform meets the implementation's requirements.** Two to three paragraphs walking through the implementation's capability profile and summarizing the platform's fit. Cite specific platform features.
3. **Strengths.** Bulleted list of the platform's strengths relative to this implementation's requirements (not universal strengths).
4. **Tradeoffs and limitations.** Bulleted list of the platform's gaps, workarounds required, or areas of friction. Every platform has these; an assessment that lists no tradeoffs is incomplete.
5. **Estimated cost.** Per-user and total annual cost at expected scale, with the list-price assumption and the date of the estimate.
6. **Migration and integration implications.** Paragraph on what implementing this platform would require: data migration complexity, integration build effort, any platform-specific prerequisites.

### 3.3 Platform Assessment Readback

Before moving to Section 4, present the platform assessment summary
to the administrator:

> "I have assessed {N} candidate platforms. Here is the summary:
>
> - {Platform A}: {one-line fit summary}
> - {Platform B}: {one-line fit summary}
> - {Platform C}: {one-line fit summary}
> - {Platform D}: eliminated — failed veto criterion {name}
> - ...
>
> Is there any platform you know something about that would change the assessment — a recent migration failure, a vendor relationship issue, a platform capability change since I last learned about it? Any platform you'd like me to reconsider or add?"

Update the assessment based on administrator input before drafting
Section 4.

---

## Step 4 — Top Two Recommendation

Select the top two platforms from the assessed list. Draft Section 4
as:

- **Platform 1 (Recommended).** Two to three paragraphs: why this platform ranks first, the top three strengths that made it rank first, the top two tradeoffs the organization should know about before committing.
- **Platform 2 (Runner-up).** Two to three paragraphs: why this platform ranks second, what would make it rank first for a different implementation, its top three strengths and top two tradeoffs.
- **Head-to-head comparison.** A short table comparing Platform 1 and Platform 2 on the three to five criteria that most distinguish them. Format: criterion, Platform 1 rating, Platform 2 rating, why it matters for this implementation.

Present Section 4 for administrator confirmation:

> "Here is the Top Two recommendation (Section 4):
>
> {Section 4 draft}
>
> Does this recommendation align with your intuition? Is there anything in the head-to-head that surprises you — either because I rated one platform wrongly or because the criterion I emphasized is not actually the deciding factor for stakeholders?"

Adjust based on administrator input. If the administrator has strong
reservations about the Top Two, explore the next-highest-scoring
platforms and reconsider.

---

## Step 5 — Decision Path and Document Production

### 5.1 Section 5: Decision Path

Draft Section 5 with practical next steps the administrator and
stakeholders can take to finalize the selection:

- **Proof-of-concept recommendations.** For each Top Two platform, what specific capability should be validated in a hands-on POC before commitment? Name the capability and why it carries risk.
- **Trial setup.** Whether each platform offers free trials, sandbox accounts, or demo instances — and what the administrator should try to do during the trial.
- **Reference customer introductions.** For each platform, whether the vendor offers reference customers the administrator could speak with (nonprofit-serving vendors often do).
- **Capability risks to validate.** A bulleted list of the specific implementation capabilities the Section 3 assessment flagged as "requires workaround" or "requires verification" — these are the items most likely to go wrong in a POC.

### 5.2 Section 6: Source References

Draft Section 6 as a bulleted list:

- Each Domain PRD with its file path and Last Updated date.
- Each Service PRD with its file path and Last Updated date.
- YAML program files by domain/service.
- Manual Configuration List and Exception List.
- The AI's knowledge cutoff date (explicit, because platform capabilities evolve).

### 5.3 Completeness Check

Before producing the document, verify:

- [ ] Section 1 covers every capability category material to this implementation.
- [ ] Section 2 names the scoring framework explicitly and the weights reflect the administrator's scoping.
- [ ] Section 3 assesses every candidate platform (or documents the elimination).
- [ ] Section 3 includes strengths, tradeoffs, cost estimate, and migration/integration for every assessed platform.
- [ ] Section 4 names exactly two platforms with justified rationale.
- [ ] Section 4 includes a head-to-head comparison.
- [ ] Section 5 gives concrete next steps, not generic advice.
- [ ] Section 6 lists source documents with Last Updated dates and the knowledge cutoff.
- [ ] Every cost figure is annotated with assumptions and date.

### 5.4 Summary

> "Here is the CRM Evaluation Report summary:
>
> - Capability categories profiled: {N} of 8
> - Candidate platforms assessed: {N}
> - Candidate platforms eliminated on veto criteria: {N}
> - Top Two recommendation: {Platform 1} and {Platform 2}
> - Decision path includes POC items for both platforms
>
> Ready to produce the document?"

### 5.5 Document Production

Produce the CRM Evaluation Report as a Word document at:

```
PRDs/{Implementation}-CRM-Evaluation.docx
```

Use the CRM Builder Word-document production convention (no Markdown
intermediary, no conversion pipeline — process doc Section 4). Commit
the document to the implementation repository.

### 5.6 State Next Step

> "The CRM Evaluation Report is complete and committed.
>
> Next step: Phase 11 CRM Deployment. The administrator reviews the report, discusses with stakeholders, selects one of the Top Two platforms (or counter-proposes a different platform with rationale), and then provisions the CRM instance. Deployment is performed using CRM Builder's deployment feature or the platform's own provisioning process, depending on the selected CRM.
>
> If stakeholders need more information before deciding, the common next actions are:
>
> - Run a POC on {Platform 1} against the flagged capability risk.
> - Run a POC on {Platform 2} against its flagged capability risk.
> - Request reference-customer introductions from both vendors.
> - Pilot the YAML-to-platform translation on one domain in both platforms to validate the YAML-to-schema mapping.
>
> Want me to draft a POC plan for one or both platforms?"

Await explicit confirmation before closing.

---

## Handling Gaps (Scope-Change Protocol)

If the evaluation surfaces that the source documents are inadequate
for a fair platform comparison, follow the process doc Section 10
scope-change protocol:

1. **Pause the evaluation at a clean stopping point** — typically the end of Section 1 where gaps usually surface.

2. **Assess the scope of the gap:**

   - **A Domain PRD gap that affects capability requirements.** Return to Phase 7 for a Domain PRD revision, or raise as a carry-forward if scoped.
   - **A YAML gap.** Return to Phase 9 for YAML completion on the affected domain.
   - **Missing scoping constraints.** Ask the administrator; do not assume.

3. **Do not produce the report against inadequate inputs.** An evaluation against incomplete requirements is worse than no evaluation — it gives stakeholders false confidence. Pause and get the inputs right.

---

## Important AI Behaviors During Generation

- **Use product names precisely.** This is the one document where product names appear. Use the vendor's canonical product name (Salesforce Nonprofit Cloud, not "Salesforce"; HubSpot Sales Hub, not "HubSpot"; EspoCRM, not "Espo"). Imprecise naming undermines the report's credibility.

- **Annotate every cost figure with assumptions and date.** List-price costs change; discounts are negotiable; user count affects per-user pricing tier. Costs without annotations mislead.

- **Name tradeoffs for every platform.** An assessment that lists only strengths is suspicious. Every platform has limitations relative to any specific implementation; the report's value depends on surfacing them.

- **Weight against this implementation, not against a universal scorecard.** A platform with powerful workflow automation scores lower for an implementation that needs no workflow than for one that needs complex workflow. The weights reflect need.

- **Acknowledge knowledge cutoff.** Platform capabilities evolve. Pricing changes. New platforms launch. State the knowledge cutoff in Section 6 so readers know what the evaluation covers and what it does not.

- **Take the administrator's platform knowledge seriously.** The AI has general platform knowledge; the administrator may have specific, current knowledge of recent migrations, vendor relationships, or capability changes. When the administrator contradicts the assessment, take it seriously — ask for the specifics and update the report.

- **Recommend exactly two, not one or three.** Recommending one platform removes the stakeholder from the decision. Recommending three or more dilutes the recommendation. Two is the deliberate number from the process doc.

- **Keep the report business-readable.** The audience is stakeholders, not implementers. Short paragraphs, concrete examples, minimal jargon.

- **Stop at 90 minutes per session.** Platform comparison is cognitively expensive. If the evaluation isn't converging by 90 minutes, schedule a follow-up — there is likely a source-document gap that needs to be addressed first.

---

## Changelog

- **1.0** (04-20-26) — Initial release. Scoped to Phase 10 CRM Selection only, per `CRM-Builder-Document-Production-Process.docx` Section 3.10. Codifies the product-name exception (this is the one document where product names are permitted and required), the Top Two recommendation discipline, the eight-category capability profile, the implementation-specific scoring framework, and the decision-path discipline (POC recommendations, capability risks to validate). Structure aligned with `authoring-standards.md` v1.0. Scope-change protocol cross-links to Domain PRD revision and YAML regeneration when source documents are inadequate.
