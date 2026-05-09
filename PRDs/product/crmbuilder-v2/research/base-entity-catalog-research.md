# Base Entity Catalog: Cross-System Research Narrative

**Last Updated:** 05-09-26 12:00
**Version:** 0.1
**Companion to:** `base-entity-catalog/` (42 entries; Tiers 1-5 complete)
**Owner:** CRMBuilder v2

---

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-09-26 | Initial narrative covering all five tiers of the base entity catalog. Documents archetype patterns observed across seven surveyed CRMs, modeling divergences worth flagging for V2's interview methodology, and design recommendations for V2's catalog ingestion and cross-system mapping. |

---

## Purpose

This document is the narrative companion to the structured base entity catalog at `base-entity-catalog/`. The catalog itself answers "what attributes does each entity have, and where does it live in each surveyed system." This document answers the bigger questions: where do CRM data models genuinely differ, what patterns recur across the survey, and what should V2 do about it.

The audience is V2 implementers and the methodology team. The catalog is for runtime consumption (seed data, lookups, advisory prompts); this document is for human reading at design time and onboarding.

---

## Survey methodology

Seven CRMs were surveyed across five tiers of entity scope:

| System | Variant | Why it's in the survey |
|---|---|---|
| Salesforce Sales Cloud | Tier-1 commercial sales CRM | Dominant B2B archetype; widest standard-object surface; richest ecosystem |
| HubSpot CRM | Tier-1 commercial sales CRM | Opinionated mid-market sales motion; unified-Contact pattern; growing into Service / Marketing / Commerce |
| Attio | Modern flexible-schema CRM | Newer architecture optimized for relationship intelligence; auto-enrichment; calendar / email integration as primary signals |
| EspoCRM | Open-source CRM | Currently CRMBuilder's primary deployment target; full schema accessible via GitHub; representative of the "open-source mid-market" segment |
| CiviCRM | Open-source nonprofit CRM | Most nonprofit-aware open-source system; unified Contact entity; rich extension ecosystem |
| Salesforce NPSP | Salesforce-based nonprofit pack | Dominant nonprofit deployment in the Salesforce ecosystem; data-model gallery is publicly documented |
| Bloomerang | SaaS nonprofit donor-management | Purpose-built for individual-donor management; unified Constituent entity; representative of the dedicated-donor-CRM segment |

Sourcing followed three priorities, in order: (1) official documentation, (2) official API / developer guides, (3) direct schema inspection of open-source repositories where they add fidelity beyond docs alone (EspoCRM `entityDefs/*.json`, CiviCRM API source, NPSP data model gallery). Community blog posts, consultant write-ups, and implementation-partner content were excluded as primary sources.

The catalog records 228 source citations across 42 entries. Per-entity citation counts vary based on the entity's coverage: entities present as standard in many systems carry 6-12 sources; entities present in only 1-3 systems carry 3-6 sources. The catalog deliberately doesn't pad citations on absent-in-most-systems entries.

---

## Archetype patterns and divergences

Eight cross-cutting patterns recurred enough across the survey to warrant explicit treatment. Each shapes V2's modeling choices and has implications for cross-system deployment.

### 1. The Person+Organization unification debate

The single most consequential modeling choice in any CRM is whether Person and Organization are one entity or two. Two patterns dominate the survey:

**Split pattern (Salesforce, HubSpot, Attio, EspoCRM, NPSP):** Contact and Account (or Person and Company) are separate entities. A person belongs to one or more organizations via foreign-key linkage. Pros: cleaner B2B sales modeling where a sales rep is selling to a buyer at a specific company; supports many-to-many people-to-organizations elegantly. Cons: extra modeling overhead for nonprofits where most "donors" are individuals not affiliated with an organization in any sales-relevant way.

**Unified pattern (Bloomerang, CiviCRM partial):** A single primary entity (Constituent in Bloomerang; Contact in CiviCRM with three contact_type values) handles individuals, organizations, and households uniformly. Pros: simpler for nonprofit fundraising where individual and organizational donors flow through identical workflows. Cons: type-conditional fields complicate validation; B2B sales motions with deep org hierarchies don't fit cleanly.

Bloomerang is the strongest example of the unified pattern (its primary entity is Constituent with a Type discriminator). CiviCRM partially follows but retains some per-subtype schema differences. The catalog captures both patterns: `contact.yaml` and `account.yaml` document the split pattern; `constituent.yaml` documents the unified pattern as its own catalog entry. V2's methodology must be capable of handling either, which means the interviewer should not assume "Contact" and "Account" both exist when probing the client's data model — they may be facing a Bloomerang or CiviCRM deployment where the unified entity is the right answer.

### 2. Donation modeling — three patterns, no consensus

The most divergent entity in the survey. The three patterns:

**Opportunity-with-Record-Type (NPSP):** The Salesforce Opportunity object is repurposed for donations via custom Record Types (Donation, Major Gift, Grant, In-Kind, Matching Gift, Membership, Recurring Donation). Pledged stage = committed; Closed Won = received. Inherits all Opportunity infrastructure (stages, owners, forecasts) but loads it with non-sales semantics.

**First-class donation entity (CiviCRM Contribution, Bloomerang Transaction):** A purpose-built donation entity with native fields for donation-specific concerns: payment_instrument, financial_type, contribution_status, fund/campaign/appeal designation. No reuse of sales-pipeline modeling.

**Absent — requires custom build (vanilla Salesforce, HubSpot, Attio, EspoCRM):** No donation entity. Implementations either follow the NPSP pattern (custom Opportunity Record Types and fields) or build custom objects entirely.

The catalog's response is to keep `donation.yaml` as its own Tier 4 entity rather than modeling it as an Opportunity subclass. The reasoning: Opportunity is genuinely absent from CiviCRM and Bloomerang (they have no sales-pipeline concept), so positioning Donation as an Opportunity subclass would force a parent-entity dependency on systems where the parent doesn't exist. Better to make Donation universal-at-Tier-4 and let `systems[]` blocks describe the implementation pattern per backend (including the NPSP pattern of "Opportunity with Record Type=Donation").

### 3. Activity fragmentation

Activity is theoretically universal but operationally fragmented across systems:

| System | Modeling pattern |
|---|---|
| Salesforce | Task (work item) + Event (calendared meeting), separate objects, shared "Activity" reporting layer |
| HubSpot | Single Engagement entity with subtypes (CALL, EMAIL, MEETING, TASK, NOTE, COMMUNICATION) |
| Attio | Tasks separate from Meetings, Calls, Emails — multiple first-class entities |
| EspoCRM | Task / Meeting / Call as three distinct first-class entities |
| CiviCRM | Single unified Activity entity with activity_type_id discriminator |
| NPSP | Same as Salesforce (Task + Event) with NPSP-specific subtype customization |
| Bloomerang | Single Interaction entity covering all touchpoint types via subtype enum |

The catalog handles this via the `activity.yaml` Tier 1 entity plus five Tier 5 Activity subclasses (email, phone-call, meeting, video-meeting, sms). V2's cross-system mapper must understand that "Activity" in a CiviCRM deployment is one entity with type discriminators, while "Activity" in a Salesforce deployment is two entities (Task + Event) with shared reporting. The catalog's `mechanism` field on each subclass tells V2 which deploy-time pattern to apply per backend.

### 4. The Lead-vs-Contact split

Three patterns observed:

**Explicit Lead with conversion (Salesforce, EspoCRM, NPSP):** Lead is a separate entity that converts to Account + Contact + Opportunity at qualification time. Lead records persist post-conversion as audit history but functionally retire.

**No Lead — lifecyclestage on Contact (HubSpot):** No separate Lead entity. Pre-qualification status is a property on Contact (`lifecyclestage = lead | mql | sql | opportunity | customer`).

**No Lead concept at all (Attio, CiviCRM, Bloomerang):** Every prospect is a Contact / Person / Constituent from initial entry. Pre-qualification status, if tracked, is a custom field or list/group membership.

The presence-map on `lead.yaml` is sharp: `standard` in three systems, `absent` in four. This is one of the catalog entries where V2 must clearly tell the interviewer "your target backend doesn't have a Lead concept; if you need one, that's a meaningful customization decision."

### 5. Subclassing mechanisms — six different patterns

The most architecturally diverse area in the survey. Six distinct mechanisms for representing what would be a "subclass" in OOP terms:

| Mechanism | Pattern | Surveyed systems using it |
|---|---|---|
| `record_type` | Same physical object, metadata-layer subtype with separate page layout | Salesforce, NPSP |
| `contact_subtype` | Native subtype hierarchy with subtype-specific custom field groups | CiviCRM (purpose-built for this) |
| `type_discriminator` | Single enum field on parent gates which attributes apply | EspoCRM, Bloomerang, HubSpot via lifecyclestage |
| `custom_property` | Custom property with no schema-level distinction | HubSpot |
| `separate_object` | Fully separate entity (loses inheritance entirely) | Attio, custom-object patterns |
| `entity_inheritance` | Formal entity inheritance at metadata level | EspoCRM (rare) |

The catalog's subclass mechanism field uses this controlled vocabulary on each entry's `systems[]` block. V2 ingests it to know how to deploy a subclass on whichever target backend the user has chosen. This is the catalog's key cross-system value-add: the same business concept ("Nonprofit Organization Account") can deploy as a Record Type on Salesforce, a Contact subtype on CiviCRM, a custom property on HubSpot, or a separate object on Attio — and the catalog tells V2 which.

### 6. Tag and classification modeling

Tags are the most architecturally varied of the universal entities. Four patterns:

**First-class Tag entity (CiviCRM, EspoCRM, Bloomerang):** Tags are a separate table, polymorphic across multiple parent types, with hierarchy support and management UI.

**Topic + Multi-select picklist hybrid (Salesforce):** Topics exist as a tag-like framework, but most admins reach for Multi-select picklists which are field-typed, not entity-typed. Customers asking for "tags" usually get picklists.

**Multi-select attribute on each object (Attio):** Tag-style attributes are configured per object; values don't cross objects.

**No first-class tag (HubSpot):** What users call tags are Multi-select properties (one per object that needs them) or static Lists. Cross-object tagging requires duplicate properties on each object.

V2's interview methodology should treat tags as a deliberate modeling decision rather than a casual requirement. "We need to tag donors with Major / Mid / New" might mean a property on Contact, a multi-select on Donation, or a polymorphic Tag entity — and the right answer depends on the target backend's tag capability.

### 7. Pipeline-stage modeling

Three patterns:

**Separate configuration entity (Salesforce OpportunityStage, HubSpot Pipelines API):** Stages are first-class records the admin manages, with API access for programmatic pipeline configuration.

**Enum on parent (EspoCRM):** Stages are picklist values on Opportunity.stage with no separate Stage table.

**Status discriminator (Attio, CiviCRM contribution_status, Bloomerang):** A status attribute that gates lifecycle behavior, often without explicit "stage" semantics — closer to status than to pipeline stage.

The catalog handles this with `pipeline-stage.yaml` as a Tier 2 universal entity, with the `systems[]` block documenting all three patterns. Multi-pipeline support (separate New Business and Renewal pipelines) is unevenly available — HubSpot has the strongest support; Salesforce supports it via Sales Processes; most others don't.

### 8. Soft Credit complexity

Soft Credit is the most nonprofit-distinctive concept in the catalog. The richness gradient:

**Rich (NPSP):** Three layers — Opportunity Contact Role → Partial Soft Credit → Account Soft Credit, with nightly batch rollups to Contact and Household giving totals. Most expressive soft-credit model in the survey.

**First-class but flatter (CiviCRM, Bloomerang):** Single Soft Credit / Acknowledgement entity attached to Contribution / Transaction with type discriminator (Solicitor, Spouse, In Honor Of, In Memory Of, Workplace Match, DAF Advisor).

**Absent (Salesforce vanilla, HubSpot, Attio, EspoCRM):** No soft-credit concept; Opportunity Contact Role partially overlaps in Salesforce.

This is a high-value area for V2 to handle thoughtfully because soft-credit reporting is operationally important in fundraising organizations and the cross-system divergence is wide. A nonprofit moving from Bloomerang to NPSP, for example, will need its soft-credit data restructured into the NPSP three-layer model.

---

## Modeling decisions worth flagging

Several catalog modeling decisions emerged from the survey that deserve explicit documentation, since reasonable people could choose differently:

### Why Donation is a universal Tier 4 entity, not an Opportunity subclass

The temptation: NPSP is the most-deployed nonprofit pattern in the Salesforce ecosystem, and NPSP repurposes Opportunity for donations. So Donation could be modeled as `subclasses/opportunity-donation.yaml`.

The decision: **no.** Donation is universal at Tier 4. NPSP's pattern is captured in Donation's `systems[]` block as `mechanism: record_type`, not as a parent-child relationship in the catalog.

The reasoning: Opportunity is genuinely absent from CiviCRM and Bloomerang. A subclass-of-Opportunity formulation would force a parent-entity dependency on systems where the parent doesn't exist. Subclass relationships in the catalog should respect parent-entity availability.

### Why Household appears in two places

Household is captured both as a Tier 4 universal entity (`household.yaml`) and as a Tier 1 Account subclass (`subclasses/account-household.yaml`).

The reasoning: NPSP models Household as an Account Record Type — an Account specialization. CiviCRM models Household as a contact_type alongside Individual and Organization (still a Contact, but a distinct subtype). Bloomerang doesn't have Household at all — it uses Relationships between individual Constituents.

Picking one canonical form would force a misrepresentation of two of the three patterns. Maintaining both lets V2's cross-system mapper use the appropriate one per backend at deploy time. The two entries cross-reference each other in their notes.

### Why Constituent has its own entry rather than being collapsed into Contact

Constituent is the unified Person+Organization entity used by Bloomerang as primary entity. It overlaps with Contact (Tier 1) significantly — they're variations on "the person/organization the CRM tracks."

The decision: keep Constituent as its own catalog entry. The reasoning: documenting the unified pattern as a distinct entry lets V2 reason about it explicitly. If a client uses Bloomerang, V2 reads Constituent as the primary entity and treats Contact and Account as components that fold into it. Without this entry, V2 would need split-entity gymnastics every time it touched a Bloomerang deployment.

### Why all five Tier 5 communication entities are subclasses, not standalone universals

Email, Phone Call, Meeting, Video Meeting, and SMS share Activity's parent attributes (subject, date, owner, related-to) and add only channel-specific delta attributes. Modeling them as standalone universals would mean repeating Activity's attributes five times across them; modeling them as subclasses says-once and adds-delta.

The deploy-time mapping respects each system's actual structure: Salesforce maps activity-meeting to Event (separate object); CiviCRM maps it to Activity with activity_type=Meeting (type_discriminator); HubSpot maps it to Engagement with subtype=MEETING (type_discriminator). The subclass model in the catalog is the truthful data shape; the deployment mechanism varies per backend.

### Why Video Meeting is split from in-person Meeting

Most surveyed systems do not natively split video from in-person meetings — they have one Meeting / Event entity with optional location or URL fields. The catalog separates them anyway because the data shape genuinely differs (URL vs physical location, platform identifier, recording / transcript URLs) and because the deploy-time pattern is increasingly being modeled distinctly in modern CRMs (HubSpot's auto-detection of video URLs in calendar events; Attio's calendar sync that recognizes platform metadata).

If a client deploys to a system that uses a single Meeting entity, V2 will map both subclasses to it via the `mechanism: type_discriminator` pattern and add the platform / URL fields as customizations. This is a case where the catalog's modeling is ahead of most current implementations — deliberately, because Video Meeting is a real and growing channel.

---

## Recommendations for V2 implementation

### Catalog ingestion at Step 0 follow-on

When V2's methodology entity schema is built (the next major build milestone after UI v0.1), the catalog's 42 YAML files ingest as seed data. Recommended ingestion approach:

1. Each catalog entry becomes a row in a `catalog_entity` table with: catalog_id, name, tier, entry_kind, parent_entity (nullable), discriminator (nullable), purpose, business_context, data_model_role.

2. Each attribute becomes a row in a `catalog_attribute` table with foreign key to catalog_entity.

3. Each system entry on each catalog entity becomes a row in a `catalog_entity_system` table with: catalog_entity_id, system, system_name, api_name, is_standard, mechanism (nullable), notes.

4. Each per-attribute presence value becomes a row in a `catalog_attribute_presence` table with: catalog_attribute_id, system, presence (standard / custom / absent).

5. Sources collapse into a `catalog_source` table referenced by catalog_entity.

The denormalized YAML form is convenient for human authoring; the normalized DB form is what V2 queries at runtime.

### Three runtime use cases V2 should optimize for

**Reference library** (during entity drafting): given a draft entity name and attributes, find the closest-matching catalog entity and surface its `systems[]` block alongside the user's draft. This helps interviewers prompt clients with "Most CRMs that have a Contact entity also include do-not-contact, communication preferences, and email opt-out flags — do you want those?" The query is "for catalog_entity X, what attributes are standard in 5+ surveyed systems?"

**Cross-system mapper** (during deployment configuration): given a target backend and a domain entity, produce the deploy-time mapping. Query: "for catalog_entity X on target system Y, what's the entity name, is_standard flag, mechanism (for subclasses), and per-attribute presence?" This is the entity-system-map.yaml's primary use case.

**Gap checker** (during entity-PRD review): given a draft entity, compare its attribute set against the catalog's universal-attributes list and flag missing common attributes. Query: "for catalog_entity X, what attributes are present (standard or custom) in 5+ surveyed systems?" Variation: "and which of those are missing from this draft?"

### Don't import names, import patterns

When V2 surfaces catalog content in the interview methodology, it should reference business concepts in the user's language, not the surveyed-system terminology. "Account" is the catalog's name; the client may call them "companies," "organizations," "agencies," or "members." V2 should match by `common_synonyms` and `purpose` semantics, not by exact name match.

The catalog's `business_context` prose was deliberately written to be system-agnostic and methodology-friendly — it's the right text for V2 to surface verbatim during interviews. The `usage` prose on each attribute is the same: written for the interviewer to use as probing question material, not for the system architect to use as schema documentation.

### Subclass mechanism deserves runtime branching

When V2 deploys a subclass to a target backend, the `mechanism` field tells it which deploy-time pattern to apply. The branching:

- `record_type` → create a Salesforce Record Type with custom fields visible only on that type's page layout
- `contact_subtype` → create a CiviCRM contact subtype with a custom field group attached
- `type_discriminator` → add an enum value to the parent's type field, plus visibleWhen rules on subclass-specific custom fields
- `custom_property` → add custom properties to the parent object (HubSpot pattern)
- `separate_object` → create a fully separate custom object (Attio pattern when the subclass diverges significantly)
- `entity_inheritance` → create a child entity with metadata-level inheritance from parent (rare; EspoCRM)

V2 should never attempt to apply a `record_type` mechanism to HubSpot (which has no Record Type concept) or a `contact_subtype` mechanism to Bloomerang (which has no Contact entity). The catalog data tells V2 which mechanism is valid per backend.

### The "no native equivalent" gap

For entries where multiple systems show `is_standard: false`, V2 has a methodology decision to make at deployment time. Options:

1. **Map to closest analog.** E.g., for Donation deployment to vanilla Salesforce, suggest using Opportunity with Record Type = Donation (the NPSP pattern). The catalog's `systems[]` notes typically mention the closest analog.

2. **Create custom object.** E.g., for Donation deployment to Attio, recommend a custom Donation object linked to Person and Company.

3. **Block deployment with explicit advisory.** For entities that are too critical to map approximately (Soft Credit on a non-NPSP/CiviCRM/Bloomerang backend; Volunteer Hour without an extension package), V2 should surface a "this requires significant customization or extension" advisory rather than silently mapping to a poor fit.

The catalog supplies the data for V2 to make these calls; the methodology guide should document the policy.

---

## Out-of-scope observations

A few patterns surfaced during research but were not included in the catalog because their fit didn't justify a separate entry:

**Currency and multi-currency.** Most surveyed systems support multi-currency at the system-configuration level rather than as an entity. Currency conversion and multi-currency reporting are operational concerns for V2 to handle in deployment configuration rather than entity modeling.

**External-ID fields.** Salesforce and HubSpot both support External ID flags on custom fields for integration deduplication. This is a field-level configuration concern rather than an entity concern.

**Workflow / Process Builder / Flow.** Automation tooling varies hugely across systems (Salesforce Flow, HubSpot Workflows, EspoCRM Workflows / BPM, CiviCRM CiviRules, Attio Automations). The catalog stays at the data-model layer; automation modeling is a separate concern that the methodology should address but not via entity catalog.

**Reporting / Dashboard objects.** Salesforce has Report and Dashboard as configurable objects accessible via API; HubSpot, Attio, etc. do too. These are out-of-scope for an entity catalog focused on operational data.

**Custom objects.** Every surveyed system supports user-defined custom objects. The catalog documents standard / native entities; user-defined customs are by definition out of scope for a cross-system reference.

---

## Cited sources by system

Authoritative source roots used in the catalog. Per-entity sources lists in the YAML files cite specific URLs within these roots.

| System | Source root |
|---|---|
| Salesforce | https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/ |
| HubSpot | https://developers.hubspot.com/docs/ |
| Attio | https://attio.com/help/reference/ and https://docs.attio.com/ |
| EspoCRM | https://docs.espocrm.com/ and https://github.com/espocrm/espocrm |
| CiviCRM | https://docs.civicrm.org/ |
| Salesforce NPSP | https://developer.salesforce.com/docs/platform/data-models/guide/nonprofit-success-pack.html (Data Model Gallery) |
| Bloomerang | https://bloomerang.com/api/rest-api-v1/ and https://support.bloomerang.co/ |

Plus standards / regulatory references:
- IRS Publication 1771 (Charitable Contributions Substantiation)
- IRS Tax-Exempt Organization Search (TEOS / Pub 78)
- NTEE Classification System (National Center for Charitable Statistics)
- TCPA (Telephone Consumer Protection Act) — referenced for SMS compliance
- GDPR / CAN-SPAM — referenced for communication-preference modeling

---

## Summary statistics

| Tier | Universal | Subclass | Total | Cumulative |
|---|---|---|---|---|
| Tier 1 (universal core) | 6 | 1 | 7 | 7 |
| Tier 2 (sales pipeline) | 4 | 0 | 4 | 11 |
| Tier 3 (vertical modules) | 12 | 0 | 12 | 23 |
| Tier 4 (nonprofit-specialized) | 10 | 2 | 12 | 35 |
| Tier 5 (communications detail) | 2 | 5 | 7 | 42 |
| **Total** | **34** | **8** | **42** | — |

414 attributes. 228 source citations. Zero validation errors. Coverage spans seven CRM systems on each entry.
