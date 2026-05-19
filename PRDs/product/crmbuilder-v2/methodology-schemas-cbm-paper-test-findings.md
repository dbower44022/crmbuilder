# Methodology Schemas — CBM Content Paper-Test Findings

**Last Updated:** 05-19-26 03:00
**Status:** Draft complete — corrected for per-engagement identifier numbering (CBM is a fresh engagement; first records start at 001).
**Purpose:** Findings from the paper-test that validates the four MVS methodology entity schemas (`domain`, `entity`, `process`, `crm_candidate` — shipped in v0.4) against existing Cleveland Business Mentoring (CBM) domain content. Produces a single decision at conversation close: ship CBM redo Phase 1 on v0.4 as-is, or amend N specific schemas before Phase 1 starts.
**Predecessor:** Kickoff at `PRDs/product/crmbuilder-v2/methodology-schemas-cbm-paper-test-kickoff.md`.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 (draft) | 05-18-26 23:30 | Doug Bower / Claude | Initial drafting pass. Findings added incrementally as confirmed in the paper-test conversation. |
| 0.2 (corrected) | 05-19-26 03:00 | Doug Bower / Claude | Identifier-numbering correction. CBM is a fresh engagement under the multi-tenant architecture; its records start at 001 per engagement-local counter (not continuing the CRMBUILDER dogfood's sequence). Six PI-017 references corrected to PI-001 across §3.1, §3.3, and §4. No content changes outside identifier renumbering. |

---

## 1. Scope and method

This document categorizes every relevant piece of CBM domain content against the four v0.4 methodology entity schemas. It runs in two passes:

- **Pass 1 — Phase 1 fitness check.** For each CBM top-level domain, does the content map to v0.4 records faithfully enough that CBM redo Phase 1 can run on v0.4 as the system of record? Findings are categorized CLEAN / STRETCH / NO HOME / BLOCKING.
- **Pass 2 — v0.5+ gap inventory.** Where CBM content goes deeper than Phase 1 (Entity PRD field tables, multi-step process swimlanes, etc.), which deferred PIs does it surface? Severity rated 1–5.

The four buckets:

- **CLEAN** — maps to a v0.4 record without interpretive stretch.
- **STRETCH** — maps with a convention not enforced by the schema. Worth documenting; not blocking.
- **NO HOME** — concept doesn't exist in v0.4. Maps to a v0.5+ PI. Pass 2 work.
- **BLOCKING** — concept is required for CBM redo Phase 1 to produce usable output, and v0.4 doesn't admit it. The paper-test recommends amending the schema before Phase 1 starts.

The threshold for BLOCKING is high: the gap must materially impair Phase 1 outputs (Domain Inventory, surfaced entity names, Prioritized Backbone, Initial CRM Candidate Set), not Phase 2+ work.

CBM inputs read: Master PRD v2.6 (domains, personas, processes, cross-domain services); Entity Inventory v1.6 (28 business concepts → 17 CRM entities); Domain PRDs for MN, MR, CR, FU; Sub-Domain Overviews for the four CR sub-domains; process .docx files (MN ×5, MR ×5, CR ×7, FU ×4); twelve Entity PRDs under `PRDs/entities/`; the Notes Service process doc.

---

## 2. Pass 1 — Phase 1 fitness check

### Finding 1 — The four CBM top-level domains map CLEAN to v0.4 `domain` records

**Bucket:** CLEAN.

CBM's Master PRD names four top-level business domains: Mentoring (MN), Mentor Recruitment (MR), Client Recruiting (CR), Fundraising (FU). Each domain in the Master PRD already carries the content the v0.4 `domain` schema requires: a client-language name, a one-paragraph description of the kinds of work the domain covers, and an explicit Domain Purpose statement that answers the mission-relationship question (`domain_purpose`).

The v0.4 schema's three-value `domain_status` lifecycle (`candidate` → `confirmed` / `deferred`) maps cleanly to CBM redo Phase 1 cadence: each domain begins as `candidate` (consultant proposes), transitions to `confirmed` after Session 2 verification with the client. No CBM domain would end up `deferred` based on the current Master PRD — all four are in active scope, all four have process work in flight. (The redo may revisit this; nothing in v0.4 prevents that.)

Soft-delete handles the rejection path the methodology calls for — if the consultant proposed a domain the client rejected as not real. No CBM-side instances of this so far.

One detail to surface, not blocking: CBM's existing identifier scheme uses `MST-DOM-001` through `MST-DOM-004` (Master-PRD-scoped, three-letter `DOM` infix). v0.4 assigns `DOM-001`...`DOM-004` server-side. The migration is mechanical and the methodology identifier (`DOM-NNN`) supersedes the legacy `MST-DOM-NNN` form. Human-readable names ("Mentoring", "Mentor Recruitment", etc.) remain the user-facing labels.

**Confidence:** This is the easy mapping. The work that v0.4 was specifically scoped to do — Phase 1 Domain Inventory — fits CBM's domain inventory shape exactly. The only follow-on for Pass 2 (PI-007 short codes — `MN`, `MR`, `CR`, `FU`) is a master-pane scannability concern, not a Phase 1 output concern.

### Finding 2 — Client Recruiting sub-domain hierarchy is BLOCKING; v0.4 must be amended before CBM redo Phase 1 opens

**Bucket:** BLOCKING.

**The gap.** CBM's Master PRD §3.5 declares "MST-DOM-003 — Client Recruiting (CR)" as a single domain "organized into four sub-domains — Partner Relationship Management, Outreach and Marketing, Workshops and Event Management, and Client Reactivation and Recovery." Each sub-domain has its own coordinator, its own process inventory (CR-PARTNER has PROSPECT + MANAGE; CR-MARKETING has CONTACTS + CAMPAIGNS; CR-EVENTS has MANAGE + CONVERT; CR-REACTIVATE has OUTREACH), and its own Sub-Domain Overview document. The CR parent provides cross-sub-domain reporting, comparative channel effectiveness analysis, and shared audience strategy.

The v0.4 `domain` schema is flat. Section 3.3.4 of `domain.md` explicitly defers self-referential parent-child hierarchy with the rationale "Sub-domain structure is explicitly out of scope per the workstream plan section 3.1 and the evolved methodology Phase 1 outline. If real-engagement experience surfaces a need for sub-domains, the v0.5 schema migration adds a `domain_parent_identifier` self-FK following the existing `topic.parent_topic` pattern."

**Why this rises to BLOCKING.** The spec's deferral assumed real-engagement signal would arrive from running the redo. The paper-test discovers that the signal is already present in CBM's existing content — the redo doesn't need to run to generate it. The "minimum-viable, defer until signal" principle is designed to avoid speculation; it doesn't apply when the design conversation lacked the inputs to recognize the requirement and the paper-test makes those inputs explicit. Treating known requirements as if they were speculative defers under false premises.

The downstream cost of proceeding flat (Option A — CR as one flat record — or Option A′ — Option A with a high-priority planning item opened) is real: Sub-Domain Overview documents have no schema home; CBM stakeholders accustomed to the CR-with-sub-domains structure experience structural simplification; the Processes panel becomes lopsided (CR's seven processes commingle); and shared-audience-strategy and cross-sub-domain-reporting concepts the CR parent currently carries can be captured only in consultant context, not in data.

**The amendment.** Add `domain_parent_identifier` to the `domain` table as a nullable self-FK, validated at the access layer (matches `^DOM-\d{3}$`; refers to a live `domain` record; not the same as the row's own `domain_identifier`). List endpoint supports hierarchy-aware ordering or a `?parent=DOM-NNN` filter; detail pane renders parent and children. Mirrors the existing `topic.parent_topic` pattern noted in section 3.3.4. The amendment is small — one nullable column, FK validation, two UI render adjustments — and probably fits in a 2–3 slice mini-workstream (call it v0.4.1 or absorb into v0.5's first slice).

**Likely planning item.** No existing PI covers sub-domain hierarchy directly. The paper-test recommends opening a new PI in this conversation's close-out — working title "PI-NNN — `domain_parent_identifier` self-FK for sub-domain hierarchy" (next available number). It opens as the first v0.4.1 (or v0.5) planning conversation, before CBM redo Phase 1 starts.

**Sequencing implication.** CBM redo Phase 1 waits on this amendment. Per the kickoff's decision rubric, this finding alone is sufficient to flip the final recommendation from "ship as-is" to "amend N schemas before Phase 1 starts." If no other BLOCKING findings emerge, the recommendation is: amend `domain` with `domain_parent_identifier` as the first v0.4.1/v0.5 workstream, then open CBM redo Phase 1 against the amended schema.

### Finding 3 — Personas correctly absent from v0.4; PI-003 holds the v0.5+ work

**Bucket:** NO HOME (Pass 2 work; not a Pass 1 gap).

**The shape.** CBM's Master PRD §2 defines 13 personas (MST-PER-001 through MST-PER-013 — System Admin, Executive Member, Client Admin, Client Assignment Coordinator, Mentor Admin, Mentor Recruiter, Client Recruiter, Partner Coordinator, Content/Event Admin, Donor/Sponsor Coordinator, Mentor, Member, Client). Each persona carries detailed Responsibilities, What the CRM Provides, and Primary Domains attributes. Every Domain PRD references them by identifier; every Phase 3 process doc names which personas perform which step.

The v0.4 schema has no `persona` entity type. PI-003 tracks this as deferred to v0.5+.

**Why this is not Pass 1 blocking.** The evolved methodology's Phase 1 interview guide explicitly does not elicit personas in the interview; persona context comes from pre-engagement reading of operational role definitions, used as consultant background rather than captured as records (per the `entity.md` spec's external-references citation of `phase-1-interview-guide.md` line 62). CBM redo Phase 1 produces a Domain Inventory, surfaced entity names, Prioritized Backbone, and Initial CRM Candidate Set — none of those four outputs requires persona records to be valid. The methodology is intentionally designed to defer personas to later phases.

**On the kickoff's three options.** Option (a) (record personas as `entity` records with `ENT-PERSONA-NNN` convention) is methodologically wrong: entities are nouns the CRM tracks (Contact, Account, Session), personas are roles people play. Conflating them in one table pollutes the entity name space and forces downstream renderers to filter persona-disguised entities out of every "entities scoped to this domain" view. Option (b) (skip in v0.4) lines up with the methodology's deliberate design. Option (c) (BLOCKING) is the wrong frame because Phase 1's *own outputs* don't need personas, unlike sub-domains where Phase 1's outputs structurally need the hierarchy.

This finding differs from Finding 2 in a structural way worth naming: Finding 2 (sub-domains) is missing v0.4 capacity for content Phase 1 *produces*; Finding 3 (personas) is missing v0.4 capacity for content Phase 3+ *produces*, which is correct deferral. PI-003 is the right home.

**Pass 2 severity:** 4 out of 5. CBM's 13 personas are richly defined and load-bearing in every Phase 3 process doc; the redo's Phase 3 work will hit the gap immediately. PI-003 should be near the top of the v0.5+ queue alongside the sub-domain amendment from Finding 2.

### Finding 4 — Cross-Domain Services unrepresented in v0.4 is acceptable; CDS-owned entities handled by `entity_scopes_to_domain`; PI-013 holds the v0.5+ design question

**Bucket:** NO HOME (Pass 2 work; not a Pass 1 gap, under the methodology framing of services-as-infrastructure).

**The shape.** CBM's Master PRD §4 declares four Cross-Domain Services structurally parallel to domains: MST-SVC-001 Notes Service (all four domains, owns Note entity), MST-SVC-002 Email Service (all four domains, no entities), MST-SVC-003 Calendar Service (all four domains, no entities), MST-SVC-004 Survey Service (MN and CR, owns Survey and Survey Response). At least one service-internal process exists as a document: `PRDs/services/NOTES/NOTES-MANAGE.docx`. The Master PRD's framing: "Services are structurally parallel to domains: they can own entities, define processes, and produce their own reconciled Service PRD."

The v0.4 schema has no `service` entity type and no equivalent. PI-013 explicitly tracks the unresolved design question — separate entity type, subsumed into `process` once `process_kind` lands in v0.5+, or dropped.

**Why this is not Pass 1 blocking, under the evolved methodology's framing.** The evolved methodology's Phase 1 elicits "the big areas of work the client's mission forces the organization to address." Notes, Email, Calendar, and surveys are platform infrastructure that supports mission-driven work; they don't pass the priority test — if Notes Service stopped tomorrow, the mission would still continue (with paper notes, or no notes, or some other workaround). Services are infrastructure, not mission-driven domains in the methodology's frame. Surfacing them as `domain` records would distort the mission-criticality framing of the Domain Inventory.

**v0.4 handles the CDS-owned entities correctly via existing mechanisms.** Note becomes an `entity` record with `entity_scopes_to_domain` references to all four domains (MN, MR, CR, FU). Survey and Survey Response become `entity` records scoped to MN and CR. Email and Calendar own no entities, so nothing to record. The many-to-many affiliation mechanism is exactly the v0.4 capability that makes this work without interpretive stretch.

**The remaining friction** is service-internal processes like NOTES-MANAGE. Two acceptable resolutions for Phase 1: (a) the consultant treats them as platform infrastructure not subject to Phase 1's mission-driven Prioritized Backbone inventory, omitting them from `process` records entirely; or (b) the consultant assigns them to a nominal owner domain via `process_domain_identifier`, accepting that the cross-domain nature is lost in the schema. Either is acceptable for Phase 1; the redo's Phase 3 work surfaces whatever real friction v0.5+ design needs to address.

**Departure from Finding 3.** Personas have methodology backing for their Phase 1 absence ("Phase 1 explicitly does not elicit personas"). CDS has methodology *ambiguity* — PI-013 acknowledges the design question is unresolved. The recommendation here rests on the evolved methodology's mission-driven framing being authoritative for the redo's Phase 1; if CBM stakeholders or a future methodology revision treat services-as-parallel-to-domains as authoritative, this finding tips toward a BLOCKING amendment instead.

**Pass 2 severity:** 4 out of 5 for PI-013. The CDS-internal process question gets sharp in Phase 3 (when service processes need to attach somewhere) and the v0.5+ design work — separate type vs `process_kind` extension vs drop — needs to ship before the redo's Phase 3 process work hits the friction. PI-013 sits in the top v0.5+ tier alongside PI-003 and the sub-domain amendment from Finding 2.

### Finding 5 — Surfaced entity names map CLEAN to v0.4 `entity` records via `entity_scopes_to_domain` many-to-many

**Bucket:** CLEAN.

**The shape.** CBM has 28 business entity concepts mapping to 17 CRM entities per the Entity Inventory v1.6 (2 native + 12 custom + 3 TBD). Shared entities use discriminator fields: Contact hosts 7 variants (Client / Mentor / Partner / Administrator / Presenter / Donor / Member) via `contactType` multiEnum spanning all four domains; Account hosts 3 variants via `accountType`; Contribution hosts 3 variants via `contributionType` single-enum.

**Why this is CLEAN for Phase 1.** The variant decomposition (Contact-with-discriminator-multiEnum, Account-with-discriminator, Contribution-with-discriminator) is a Phase 3 reconciliation artifact — the work of mapping client-language nouns to CRM-implementation entities happens after Phase 1, when Entity PRDs are authored. Phase 1 surfaces the nouns the client uses ("Mentor", "Client", "Partner Contact", "Donor", "Engagement", "Session", "Dues", "Donation", etc.), not the post-reconciliation CRM-language consolidation ("Contact with `contactType=Mentor`"). Each client-language noun becomes one `entity` record with the appropriate multi-domain `entity_scopes_to_domain` references.

Concrete Phase-1-surfaced entities that map under v0.4 as-is:

- Mentor → `entity` record, scopes to MN and MR
- Client → `entity` record, scopes to MN and CR
- Partner Contact → `entity` record, scopes to CR
- Donor / Sponsor → `entity` record, scopes to FU
- Partner Organization → `entity` record, scopes to CR
- Client Organization → `entity` record, scopes to MN and CR
- Donor / Sponsor Organization → `entity` record, scopes to FU
- Engagement → `entity` record, scopes to MN
- Session → `entity` record, scopes to MN
- Dues → `entity` record, scopes to MR
- Donation / Sponsorship / Grant — three records, or a single "Contribution" record if the client's language consolidates, scoping to FU
- Workshop / Event → `entity` record, scopes to CR
- Note → `entity` record, scopes to all four (per Finding 4)
- Survey / Survey Response → `entity` records, scoping to MN and CR

The `entity_scopes_to_domain` many-to-many mechanism carries every multi-domain case faithfully. No interpretive stretch.

**On the spec's anticipated variant workaround.** The `entity.md` spec section 3.3.4 anticipated a name-suffixing workaround for the Mentor Contact / Client Contact variant pattern ("Contact — Mentor", "Contact — Client" as independent records). Under the evolved methodology's Phase 1 surfacing-of-client-nouns, the workaround isn't triggered: the consultant records "Mentor" and "Client" as independent records directly, without any compound name needed. The variant decomposition only becomes a concern at Phase 3 when entity-to-CRM mapping starts, and PI-010 (entity-schema v0.5+ extensions: variants, base-type/kind) is the right v0.5+ home for that work.

**Pass 2 implications.** PI-004 (field / requirement / manual_config / test_spec) and PI-010 (entity variants, base-type/kind) both surface here for severity rating — but those address Phase 3+ richness, not Phase 1 fitness.

### Finding 6 — Prioritized Backbone maps to v0.4 `process` records cleanly; identifier-scheme legibility is the only STRETCH

**Bucket:** CLEAN with one STRETCH (identifier scheme). Depends on Finding 2's `domain_parent_identifier` amendment for CR sub-domain process attachment.

**The shape.** CBM's Master PRD §3.2 enumerates 19 process / sub-domain entries: MN ×6 (INTAKE, MATCH, ENGAGE, INACTIVE, CLOSE, SURVEY), MR ×5 (RECRUIT, APPLY, ONBOARD, MANAGE, DEPART), CR ×4 sub-domains (each with 1–2 sub-processes — 7 actual sub-domain processes — PROSPECT, MANAGE, CONTACTS, CAMPAIGNS, EVENTS-MANAGE, CONVERT, OUTREACH), FU ×4 (PROSPECT, RECORD, STEWARD, REPORT). Each process has a one-paragraph description, a tier classification (Core / Important / Enhancement / Out of Scope), Business Value bullets, and Key Capabilities bullets. Processes within a domain are listed in dependency order.

**Structural mapping under v0.4.** Each CBM process becomes one `process` record with `process_name` (e.g., "Client Intake", "Mentor Application"), `process_purpose` (the one-paragraph description), and `process_domain_identifier` FK to the appropriate domain. Once Finding 2's amendment lands, CR's sub-domain processes attach directly to their sub-domain `domain` records (CR-PARTNER processes to the CR-Partner sub-domain, etc.); the parent CR `domain` record exists in its own right. Each process's classification gets re-derived under the evolved methodology's priority test ("if this stopped tomorrow, the mission would..."), producing a `process_classification` of `mission_critical`, `supporting`, or `deferred`. The redo doesn't carry forward CBM's legacy Core / Important / Enhancement / Out of Scope tier labels as identifiers — those are hints to the consultant, not methodology-authoritative tags.

**On the four-value-tier-to-three-value-classification gap.** CBM's tier system is about launch-readiness phasing (Core = required for launch; Important = within 60 days; Enhancement = deferable; Out of Scope = future). v0.4's classification is methodology-priority (mission_critical = passes the priority test; supporting = real work, not on critical path; deferred = parked). These are correlated but distinct concepts. The redo's Phase 1 priority test rewrites the classifications from scratch, so the gap doesn't matter — the consultant applies the priority test to each surfaced process and lets the answer fall where it falls. The Out-of-Scope tier loses a structural home; soft-delete handles "documented for future planning, not in current scope" if needed, otherwise those processes simply don't get authored in this redo's Phase 1.

**Handoffs.** CBM's Master PRD doesn't enumerate handoffs as discrete "Process A → Process B" statements, but the in-domain dependency ordering implies them (MN-INTAKE → MN-MATCH → MN-ENGAGE → MN-INACTIVE → MN-CLOSE; MR-RECRUIT → MR-APPLY → MR-ONBOARD → MR-MANAGE → MR-DEPART). Cross-domain handoffs are real and substantial: MR-APPLY (approved mentor) → MN-MATCH; CR-PARTNER referrals → MN-INTAKE; CR-EVENTS attendees → MN-INTAKE conversion; CR-MARKETING campaigns → MN-INTAKE; CR-REACTIVATE outreach → MN-INTAKE; MN-CLOSE → CR-REACTIVATE alumni. The redo's Phase 1 would surface these explicitly during Prioritized Backbone work. v0.4's `process_hands_off_to_process` is many-to-many directional via the universal references entity — not domain-bound, so cross-domain handoffs work without interpretive stretch.

**The one STRETCH — identifier scheme.** CBM uses mnemonic identifiers (`MN-INTAKE`, `MR-RECRUIT`, `CR-PARTNER`, `FU-PROSPECT`). v0.4 assigns numeric `PROC-NNN`. The mnemonic codes have substantial legibility value — CBM stakeholders read "MN-INTAKE" instantly; "PROC-007" requires a lookup. Phase 1 isn't blocked by this (the records are valid; names like "Client Intake" preserve human-readable meaning), but the legacy mnemonic codes lose their structural form in the v0.4 record's identifier field. They survive as text in `process_notes` or as part of the name if the consultant chooses ("Client Intake (MN-INTAKE)"). PI-007's `domain.short_code` field is the v0.5+ enabler for pulling the mnemonic into the identifier (e.g., `MN-001` rather than `PROC-001`); pulling PI-007 forward would resolve this STRETCH, but it's not a Phase 1 fitness blocker — just a legibility downgrade during the transition.

**On `process_description` vs `process_purpose`.** CBM's process docs carry the "one-paragraph what-it-does" content (maps to `process_purpose`), Business Value bullets (the priority-test answer — maps to `process_classification_rationale`), and Key Capabilities bullets (Phase 3+ content — not Phase 1 minimum-viable). The spec's deviation rationale holds: one purpose field suffices for Phase 1.

**Pass 2 implications.** PI-005 (process_step growth) surfaces here for severity rating — CBM has multi-step process content in the existing .docx files; the redo's Phase 3 would surface swimlanes. PI-007 (short codes) and PI-011 (scalar implementation priority) are minor follow-on items.

### Finding 7 — Initial CRM Candidate Set has no CBM content to validate against; v0.4 `crm_candidate` schema accommodates whatever the redo's Phase 1 produces

**Bucket:** CLEAN.

**The shape.** CBM's existing Master PRD and Entity Inventory both target EspoCRM directly ("Target Platform: EspoCRM" in the inventory header). There is no documented Initial CRM Candidate Set in CBM's current PRDs — the original methodology evidently committed to EspoCRM as the platform without going through the evolved methodology's candidate-set elicitation process. The engine pluggability workstream (Attio first, then HubSpot) tracked in the user-memory is a CRM Builder *engine* concern (which deployment backends the tool supports), not a CBM-engagement Phase 1 deliverable.

**What the redo's Phase 1 produces.** Two reasonable shapes:

- **Single-candidate confirmation.** The redo's Phase 1 records `CRM-001 — EspoCRM` as the only `crm_candidate` with status `active` (or `selected` from the start if Phase 5 is implicit-because-deployment-already-happened). The candidate-set was effectively pre-decided; the redo just captures the record.
- **Fresh candidate-set elicitation.** The redo runs the evolved methodology's Phase 1 elicitation properly: the consultant proposes 2–3 candidates fitting CBM's coarse criteria (open-source, self-hosted-capable, nonprofit-affordable, integrations with email and the public website), the client confirms; one is `selected` and the others `declined` (after Phase 3 / 4 lived-deployment if the redo runs full iterations) or all sit `active` if the redo is a documentation-only re-run.

Either shape works under v0.4's `crm_candidate` schema. The 4-status lifecycle (`active` / `selected` / `declined` / `removed`) accommodates either a single-candidate engagement (one record transitioning to `selected`) or a multi-candidate engagement with terminal states. The singleton-`selected` constraint protects against accidental dual selection. The lack of outgoing relationships in v0.4 is acceptable since `crm_candidate` doesn't relate to domain / entity / process content in v0.4.

**No friction surfaces for Phase 1.** The schema fits whatever the redo's consultant produces; the consultant decides single-vs-multi-candidate during Phase 1 elicitation.

**Pass 2 implication.** PI-012 (`crm_candidate` structured-metadata enums — vendor URL, hosting type, license type, price tier) surfaces here for severity rating. CBM has nothing currently structured for the hosting / license / price axes; the redo's Phase 1 `crm_candidate_fit_reason` prose carries it. Low severity since the candidate count is small (1–3) and the prose works.

---

## 3. Pass 2 — v0.5+ gap inventory

Pass 2 is advisory and does not affect the v0.4 ship/no-ship decision (Finding 2 already settled that — amendment required). What Pass 2 produces is the prioritization signal for which v0.5+ PI to open first after the sub-domain amendment lands. Per the kickoff: 1 = nice-to-have for v0.6+, 3 = real friction for CBM redo Phase 2, 5 = blocking work that's already on the runway.

### 3.1 Severity ratings — the seven deferred PIs named in the kickoff

**PI-003 — `persona` entity type. Severity: 4.** CBM's 13 personas (MST-PER-001 through MST-PER-013) are richly defined and every Phase 3 process doc references them by identifier. The redo's Phase 3 work cannot produce process docs without persona records or persona references. Pull-forward candidate for the first v0.5+ workstream after PI-001 (sub-domain amendment).

**PI-004 — `field`, `requirement`, `manual_config`, `test_spec` entity types. Severity: 5.** This is the biggest single v0.5+ workstream. CBM has 12 Entity PRDs under `PRDs/entities/` ranging from Contact v1.5 (47 fields) down to simpler entities. Every PRD has a detailed field table with names, types, required flags, defaults, validation rules. The redo's Phase 3 work to produce Entity PRDs cannot happen without `field` records. Likely multiple slices, not a single workstream. Includes the catalog-FK question (PI-014) as a dependency.

**PI-005 — `process_step` entity type and richer process content. Severity: 5.** Every CBM process .docx file has multi-step swimlane content. MN-INTAKE alone has substantial step content (application receipt → administrator review → decision → notification). The redo's Phase 3 process work requires `step_belongs_to_process` and step-level content. Joint with PI-004 as the two big Phase 3 enablers.

**PI-013 — Cross-Domain Service representation. Severity: 4.** Already rated in Finding 4. The unresolved design question (separate type vs `process_kind` extension vs drop entirely) needs resolution before Phase 3 surfaces CDS-internal processes like NOTES-MANAGE. Mid-severity — high enough to need pre-Phase-3 work, low enough that Phase 1 + early Phase 3 can proceed without it.

**PI-014 — Catalog FK integration for methodology entities. Severity: 3.** Not a Phase 1 question — Phase 1 surfaces client-language nouns ("Mentor"), not their post-reconciliation CRM archetypes (Contact). The catalog FK becomes relevant when Phase 3 entity-to-CRM mapping work happens. Effectively a dependency of PI-004 (when `field` lands, it needs to know whether to FK to a catalog `entity` row); the catalog-FK question gets resolved as part of the PI-004 design conversation rather than as its own workstream. Severity 3 reflects "real friction for Phase 3 work" without being on-the-runway blocking.

**PI-015 — Methodology entity renderers (.docx, YAML, JSON exports per DEC-008). Severity: 4.** DEC-008 prescribes renders, not authored copies. CBM currently maintains hand-authored .docx versions of everything — Master PRD, Domain PRDs, Domain Overviews, Sub-Domain Overviews, process docs, Entity PRDs, the Entity Inventory. The redo would benefit from .docx generation for Phase 1 Domain Inventory and Prioritized Backbone documents (and Phase 3 Entity PRDs once PI-004 lands). The operational cost of maintaining hand-authored Phase-1-output docs alongside v0.4 records is real — duplicate-source-of-truth risk. Severity 4 — pulls hard once Phase 1 has authored content and stakeholders ask "where's the Domain Inventory document?"

**PI-016 — Router-level per-pair vocab enforcement on `/references`. Severity: 1.** The kickoff frames this as "theoretical until external clients hit the endpoint." CBM workflows don't involve external scripts hitting `/references` directly — all reference creation goes through the desktop UI's reference-create dialog which already drives off `RELATIONSHIP_RULES`. No CBM signal raises this above v0.6+ nice-to-have. The only way severity rises is if external integrations are added later (e.g., a Phase 5 audit script that posts references directly).

### 3.2 Follow-on PIs surfaced in Findings 1–7

Lower priority than the above; named here so the prioritization signal is complete.

- **PI-007 — `domain.short_code` field. Severity: 2.** Master-pane scannability + identifier mnemonic-restoration for processes. Quality-of-life, not friction-driver. Pairs naturally with PI-009 (master-pane Domains column on Entities). Pull-forward only if Phase 1 stakeholders complain about `PROC-007` vs `MN-INTAKE` legibility loud enough.
- **PI-009 — master-pane Domains column on Entities panel. Severity: 2.** Joint with PI-007 since the column renders short codes. Quality-of-life.
- **PI-010 — entity variants, base-type/kind. Severity: 3.** Phase 3 entity-to-CRM mapping work (Mentor + Client + Partner Contact + Administrator + ... → Contact-with-discriminator). Joint with PI-004 — when fields land, variants need to land in the same workstream or shortly after.
- **PI-011 — scalar implementation priority on process. Severity: 2.** Phase 2 Slice Planning territory; not Phase 1 or Phase 3 friction.
- **PI-012 — `crm_candidate` structured metadata. Severity: 2.** Per Finding 7 — candidate count is small, prose works. Low value until candidate count grows beyond 3.

### 3.3 Suggested v0.5+ workstream ordering

Highest impact first, after the sub-domain amendment lands:

1. **PI-001** (sub-domain hierarchy amendment — BLOCKING for Phase 1; opens before Phase 1 starts).
2. **PI-004 + PI-014 + PI-010 joint workstream** (Phase 3 entity richness — fields, catalog FK, variants — likely the biggest single workstream of v0.5+).
3. **PI-005** (process_step growth — Phase 3 process richness; joint candidate with PI-004).
4. **PI-003** (persona entity type — Phase 3 process docs depend on it).
5. **PI-013** (Cross-Domain Service design question — resolve before Phase 3 hits CDS-internal processes).
6. **PI-015** (methodology entity renderers — pulls hard once Phase 1 content exists).
7. Lower-priority follow-ons: **PI-007, PI-009, PI-011, PI-012, PI-016** as quality-of-life or speculative.

---

## 4. The single decision

**Amend one schema before CBM redo Phase 1 starts: `domain` with `domain_parent_identifier` self-FK for sub-domain hierarchy.**

The amendment opens as the first v0.5+ planning conversation (or as v0.4.1 — naming TBD at the planning conversation). It is the only Pass-1-blocking gap identified by the paper-test. CBM redo Phase 1 waits on this amendment, then opens against the amended schema.

Six other findings (1, 3, 4, 5, 6, 7) resolve as CLEAN or NO HOME under v0.4 as-is. Finding 6 carries one acknowledged STRETCH (identifier-scheme legibility — mnemonic codes like `MN-INTAKE` lose their structural form to numeric `PROC-NNN`); not blocking, but a candidate for pull-forward of PI-007 if Phase 1 stakeholders surface enough friction.

Three NO HOME findings (3, 4, with consolidation in Pass 2) map cleanly to existing planning items: PI-003 (personas), PI-013 (Cross-Domain Services), with PI-004 / PI-005 / PI-015 carrying the bulk of post-Phase-1 work.

**Closing recommendation.** The workstream after this paper-test closes is the PI-001 planning conversation. The CBM redo Phase 1 conversation opens after that amendment ships and the schema spec for `domain.md` is updated to reflect the self-FK.

**Sequence:**

1. Paper-test conversation close-out — produces session record, three decisions (the BLOCKING categorization for sub-domains, the NO HOME categorizations for personas and CDS, the suggested PI-001 priority ordering), one new planning item (PI-001 — `domain_parent_identifier` self-FK for sub-domain hierarchy).
2. PI-001 planning conversation — produces the amendment spec, slice plan, and CLAUDE-CODE prompts for the self-FK migration.
3. PI-001 build conversations — execute the migration. Probably a 2–3 slice mini-workstream.
4. `domain.md` schema spec amended with section 3.3.4 updated to reflect that sub-domain hierarchy is now in scope.
5. CBM redo Phase 1 first conversation opens — first work the consultant does is author the CBM Domain Inventory under the amended `domain` schema.

---

*End of document.*
