# Base Entity Catalog

**Last Updated:** 05-09-26 14:50
**Status:** All 5 tiers complete; schema v0.10 with donationType discriminator fix; catalog at 42 entries
**Owner:** CRMBuilder v2

---

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.10 | 05-09-26 | Latent bug fix — added `donationType` attribute to `donation.yaml` and updated `subclasses/donation-major-gift.yaml` discriminator to reference `donationType` (was referencing nonexistent `parent.type`). The new attribute captures the donation categorization pattern shared across systems: enum values Donation / Major Gift / In-Kind Gift / Stock Gift / Tribute Gift / Matching Gift. Cross-system mapping: CiviCRM `financial_type_id` (standard), NPSP `RecordTypeId` (standard), others custom or absent. Catalog now has 415 attributes (was 414). This fix unblocks catalog ingestion into V2 (see `catalog-ingestion-PRD-v0.1.md` section 10's pre-existing-issue note). Map regenerated to v0.4. |
| 0.9 | 05-09-26 | Naming convention rationalization. Selectively renamed generic-noun attribute internal names (Pattern C from the design discussion): bare `name`, `status`, `type`, `amount` get entity-context prefixes — e.g., `account.name` → `account.accountName`, `donation.amount` → `donation.giftAmount`, `case.status` → `case.caseStatus`. ~50 attributes renamed across 31 entities. Display names also standardized: any bare `Status` / `Type` / `Subject` / `Body` / `Role` display gets entity prefix (`Activity Status`, `Engagement Type`, `Note Body`, etc.). `Description` and `Title` stayed bare (judged contextually clear). Subclass discriminators referencing renamed parent attributes were updated (`account-household` and `account-nonprofit` discriminator now references `accountType` not `type`). Naming convention documented in new "Naming conventions" section below. Note: `donation-major-gift` subclass discriminator still references `parent.type` but `donation.yaml` has no `type` attribute — pre-existing latent bug not addressed by this rename pass; flagged for follow-up commit that adds `donationType` to donation.yaml. The api_name overrides in `presence` are unchanged — system api_names stayed the same (Salesforce.Account.Name is still `Name`, etc.); only the catalog-internal name was prefixed. Map regenerated to v0.3. |
| 0.8 | 05-09-26 | Schema enhancement (no new entries; existing 42 entries enriched). Two additions to attribute schema: (1) `common_synonyms` — optional list of alternate vocabulary terms users say when describing the attribute (e.g., `industry` synonyms = sector, vertical, line of business). 81 attributes backfilled with synonyms across high-divergence-vocabulary fields. (2) `presence` per-system value transformed from a flat status string into a structured object: `{ status: standard\|custom\|absent, api_name: "system-specific-field-name" }`. The api_name is populated on standard cells via a combination of: (a) explicit overrides from authoritative system documentation (~250 known divergences — Salesforce StageName, HubSpot lifecyclestage, NPSP npe-prefixed custom objects, CiviCRM snake_case fields, etc.), and (b) convention-based defaults for the rest (Salesforce PascalCase, HubSpot lowercase, EspoCRM camelCase, CiviCRM snake_case, Bloomerang PascalCase, Attio snake_case). All 1,545 standard cells across 2,898 total cells are populated; absent on `custom` cells (where the customer chooses the name at deploy time) and `absent` cells. **V2 deployment configuration should verify api_names against current target-system docs before applying** — convention-derived defaults are best-effort and may need correction for specific fields. Both changes are backward-compatible additions; ingestion-time consumers handle the new structure. |
| 0.7 | 05-09-26 | Cross-cutting deliverables published as siblings to this directory: `../base-entity-catalog-research.md` (narrative companion documenting archetype patterns, modeling decisions, and V2 implementation recommendations) and `../entity-system-map.yaml` (programmatically-generated flat lookup table mapping each catalog entity to its representation in all 7 surveyed systems). Catalog content unchanged in this version. |
| 0.6 | 05-09-26 | Tier 5 (communications detail) added: 5 Activity subclasses (activity-email, activity-phone-call, activity-meeting, activity-video-meeting, activity-sms) plus 2 standalone universal entities (document, contract). All 5 communication subclasses share Activity's parent attributes and add channel-specific delta attributes only. Catalog now stands at 42 entries: 34 universal + 8 subclasses across all 5 tiers. |
| 0.5 | 05-09-26 | Refactor: renamed `specialization` → `subclass` throughout the catalog. Same conceptual model (parent entity + discriminator + delta attributes); friendlier terminology that maps cleanly to OOP subclassing for technical readers and is intuitive to non-technical readers. Changes: `entry_kind: specialization` → `entry_kind: subclass`; directory `specializations/` → `subclasses/`; all README prose updated. No semantic change to the catalog. |

| Version | Date | Description |
|---------|------|-------------|
| 0.4 | 05-09-26 | Tier 4 (nonprofit-specialized) added: donation, recurring-gift, grant, membership, volunteer-hour, household, affiliation, soft-credit, constituent, engagement. Plus two subclasss: account-household (Account subclass for the NPSP record-type pattern), donation-major-gift (Donation subclass for major-gift cultivation). 12 entries total. Tier 5 pending. |
| 0.3 | 05-08-26 | Tier 3 (vertical modules) added: case, solution, asset, campaign, campaign-member, email, form-submission, product, price-list, order, invoice, payment. 12 entities covering customer-service, marketing, and commerce concerns. |
| 0.2 | 05-08-26 | Tier 2 (sales pipeline) added: lead, opportunity, pipeline-stage, quote. |
| 0.1 | 05-08-26 | Initial Tier 1 sample: account, contact, activity, note, user, tag base entities plus account-nonprofit subclass. Schema established; sourcing methodology documented. |

---

## Purpose

This catalog is a structured reference of CRM base entity types and their attributes, surveyed across seven CRM systems. It is the foundational reference material that CRMBuilder v2 uses to guide users through entity selection, attribute selection, cross-system mapping, and gap-checking during the methodology's Inventory Reconciliation and Entity PRD phases.

The catalog answers four questions for any CRM concept (e.g., "Account," "Donation," "Activity"):

1. What is it conceptually, and why do CRMs track it?
2. What attributes typically describe it, and what do those attributes usually mean in a business context?
3. How does each surveyed CRM represent it, and what are the attributes called?
4. How does it relate to other entities?

The catalog is authored in YAML so it ingests cleanly into V2's future entity schema (Step 0 follow-on work) without requiring re-extraction from prose.

---

## Systems surveyed

| System | Variant | Primary docs |
|--------|---------|---------------|
| Salesforce Sales Cloud | Tier-1 commercial sales CRM | https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_list.htm |
| HubSpot CRM | Tier-1 commercial sales CRM (opinionated) | https://developers.hubspot.com/docs/reference/api/crm/properties |
| Attio | Modern flexible-schema CRM | https://attio.com/help/reference/managing-your-data/objects/manage-standard-objects |
| EspoCRM | Open-source CRM (currently CRMBuilder's deployment target) | https://docs.espocrm.com/administration/entity-manager/ |
| CiviCRM | Open-source nonprofit-oriented CRM | https://docs.civicrm.org/user/en/latest/organising-your-data/contacts/ |
| Salesforce NPSP | Salesforce-based nonprofit pack | https://trailhead.salesforce.com/content/learn/modules/nonprofit-success-pack-administration-basics/understand-the-npsp-data-model |
| Bloomerang | Nonprofit donor-management CRM | https://bloomerang.com/api/rest-api-v1/ |

## Companion deliverables

The catalog has two cross-cutting companions stored alongside this directory:

- `../base-entity-catalog-research.md` — narrative document covering archetype patterns observed across the survey (Person+Org unification debate, donation modeling divergence, activity fragmentation, subclassing mechanisms, etc.), modeling decisions worth flagging, and V2 implementation recommendations. Read this for the "why behind the catalog."

- `../entity-system-map.yaml` — flat lookup table programmatically generated from the catalog, listing for each of the 42 entities its representation in all 7 surveyed systems (name, api_name, is_standard, mechanism for subclasses, docs_url). Optimized for V2's deploy-time cross-system mapping use case.

Both are authoritative; the entity-system-map regenerates from the catalog YAMLs and should be regenerated when catalog entries change.

---

## Directory structure

```
base-entity-catalog/
├── README.md                              # this file
├── account.yaml                           # T1 base entity
├── contact.yaml                           # T1 base entity
├── activity.yaml                          # T1 base entity
├── note.yaml                              # T1 base entity
├── user.yaml                              # T1 base entity
├── tag.yaml                               # T1 base entity
├── lead.yaml                              # T2 base entity
├── opportunity.yaml                       # T2 base entity
├── pipeline-stage.yaml                    # T2 base entity
├── quote.yaml                             # T2 base entity
├── case.yaml                              # T3 base entity
├── solution.yaml                          # T3 base entity (Knowledge Article)
├── asset.yaml                             # T3 base entity
├── campaign.yaml                          # T3 base entity
├── campaign-member.yaml                   # T3 base entity (junction)
├── email.yaml                             # T3 base entity
├── form-submission.yaml                   # T3 base entity
├── product.yaml                           # T3 base entity
├── price-list.yaml                        # T3 base entity
├── order.yaml                             # T3 base entity
├── invoice.yaml                           # T3 base entity
├── payment.yaml                           # T3 base entity
├── donation.yaml                          # T4 base entity
├── recurring-gift.yaml                    # T4 base entity
├── grant.yaml                             # T4 base entity
├── membership.yaml                        # T4 base entity
├── volunteer-hour.yaml                    # T4 base entity
├── household.yaml                         # T4 base entity
├── affiliation.yaml                       # T4 base entity
├── soft-credit.yaml                       # T4 base entity
├── constituent.yaml                       # T4 base entity
├── engagement.yaml                        # T4 base entity
├── document.yaml                          # T5 base entity
├── contract.yaml                          # T5 base entity
└── subclasses/
    ├── account-nonprofit.yaml             # T1 subclass of Account
    ├── account-household.yaml             # T4 subclass of Account
    ├── donation-major-gift.yaml           # T4 subclass of Donation
    ├── activity-email.yaml                # T5 subclass of Activity
    ├── activity-phone-call.yaml           # T5 subclass of Activity
    ├── activity-meeting.yaml              # T5 subclass of Activity
    ├── activity-video-meeting.yaml        # T5 subclass of Activity
    └── activity-sms.yaml                  # T5 subclass of Activity
```

Base entity files are universal types that every (or nearly every) CRM has. Subclass files reference a parent entity, name a discriminator (the parent attribute and value that selects this subclass), and list only delta attributes that the subclass adds beyond what the parent already defines.

A subclass may end up implemented as a record type, contact subtype, type discriminator, custom property, or even a separate entity depending on the target backend's subclassing capabilities. Each subclass YAML's `systems[]` block names the implementation pattern per system using a controlled `mechanism` vocabulary so V2 knows how to deploy the subclass to whichever target CRM is selected.

---

## Entity YAML schema

Every base-entity YAML file follows this shape. Subclass files use the same shape with two additions: `entry_kind: subclass`, `parent_entity` reference, and a `discriminator` block.

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `catalog_id` | string | yes | Stable identifier; matches filename minus `.yaml`. lowercase-hyphenated. |
| `catalog_version` | string | yes | Semantic version of this entry (e.g. `0.1`). |
| `last_updated` | string | yes | `MM-DD-YY HH:MM` per project standard. |
| `tier` | integer | yes | 1 (universal core), 2 (sales pipeline), 3 (vertical), 4 (nonprofit), 5 (comms detail). |
| `entry_kind` | enum | yes | `universal` or `subclass`. |
| `parent_entity` | string | conditional | Required when `entry_kind: subclass`. Catalog ID of the parent entity. |
| `discriminator` | object | conditional | Required when `entry_kind: subclass`. Names the parent attribute and value that selects this subclass. |
| `name` | string | yes | Canonical display name (e.g. `Account`). |
| `display_name` | string | yes | Human-readable name shown in V2 UI. |
| `purpose` | string | yes | Terse what-it-is, two to three sentences. |
| `business_context` | string | yes | Why CRMs track it. What business processes typically touch it. What its presence on a deployment signals. Surfaced during interview methodology to guide entity-level discussion. |
| `data_model_role` | enum | yes | `anchor`, `event`, `classifier`, `junction`, `log`, `document`. Lets V2 reason about entities at the type level. |
| `typically_required` | boolean | yes | Is this entity required for any meaningful CRM deployment, or optional? |
| `common_synonyms` | array | no | Other names the same concept goes by (e.g. `[Company, Organization, Constituent Organization]`). |
| `systems` | array | yes | Per-system equivalence info (one entry per surveyed system). |
| `attributes` | array | yes | The attribute list — see `Attribute schema` below. |
| `relationships` | array | no | Inter-entity relationships — see `Relationship schema` below. |
| `sources` | array | yes | Citations: title and URL for each authoritative source consulted. |

### `systems[]` schema (per-system equivalence)

| Field | Type | Required | Description |
|---|---|---|---|
| `system` | enum | yes | One of `salesforce`, `hubspot`, `attio`, `espocrm`, `civicrm`, `salesforce_npsp`, `bloomerang`. |
| `name` | string | yes | What this system calls the entity. |
| `api_name` | string | yes | The technical / API identifier in this system. |
| `is_standard` | boolean | yes | Whether the entity is built-in (true) or has to be created custom (false). |
| `mechanism` | enum | conditional | Required for subclasss only. One of `record_type`, `contact_subtype`, `type_discriminator`, `custom_property`, `separate_object`, `entity_inheritance`. Names the architectural pattern used to realize this subclass in this system. |
| `notes` | string | no | Any quirks, divergences, or implementation considerations specific to this system. |
| `docs_url` | string | no | Direct URL to the system's reference for this entity. |

### `attributes[]` schema (per-attribute)

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Internal name in lowerCamelCase. |
| `display_name` | string | yes | Human-readable label. |
| `type` | enum | yes | One of: `string`, `text`, `richtext`, `integer`, `decimal`, `currency`, `boolean`, `date`, `datetime`, `time`, `enum`, `multienum`, `reference`, `multireference`, `email`, `phone`, `url`, `address`, `attachment`, `autonumber`, `formula`. |
| `required` | boolean | yes | Whether this attribute is typically required across the systems where it's standard. |
| `max_length` | integer | no | For string types. |
| `enum_values` | array | conditional | Required for `enum` and `multienum` types. |
| `reference_target` | string | conditional | Required for `reference` and `multireference` types. Names the target entity. |
| `description` | string | yes | Terse what-it-is. |
| `usage` | string | yes | Why it exists, what business processes it serves, what its presence on a record signals. Surfaced during interview methodology to guide field-level discussion. |
| `presence` | object | yes | Per-system presence map — keys are system names, values are structured objects with `status` (one of `standard` / `custom` / `absent`) and optional `api_name` (the system-specific field identifier when status is `standard`). See "Per-system presence schema" below. |
| `common_synonyms` | array | no | Alternate vocabulary terms users say when describing the attribute. Example: `industry` carries `[sector, vertical, line of business, business type]`. Populated selectively on attributes where vocabulary divergence is high; absent on system fields and on attributes whose name is unambiguous. |
| `notes` | string | no | Cross-system divergence, naming differences, or other implementation considerations. |

#### Per-system presence schema (under `attributes[].presence`)

Each system entry within `presence` is a structured object:

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | enum | yes | One of `standard` (system ships it built-in), `custom` (system supports it but you'd add it as a custom field/property — name varies by deployment), `absent` (system structurally cannot or doesn't represent this concept). |
| `api_name` | string | conditional | Populated when status is `standard` and the api_name is authoritatively known (e.g., `Industry` on Salesforce, `industry` on HubSpot, `categories` on Attio). Absent on `custom` cells (where the customer chooses the name at deploy time) and on `absent` cells. May also be absent on rare `standard` cells where authoritative naming wasn't yet captured — V2's cross-system mapper handles missing api_name as a TBD signal. |


### `relationships[]` schema (per-relationship)

| Field | Type | Required | Description |
|---|---|---|---|
| `target` | string | yes | Catalog ID of the related entity. |
| `cardinality` | enum | yes | One of `one-to-one`, `one-to-many`, `many-to-one`, `many-to-many`. |
| `role` | enum | yes | One of `parent`, `child`, `peer`, `polymorphic`. |
| `description` | string | yes | What the relationship represents. |
| `presence` | object | yes | Per-system presence map (same vocabulary as attribute presence). |

---

## Naming conventions

Catalog field names follow these conventions. They emerged from the v0.9 rationalization and apply to all future entries.

### Internal attribute name (`attributes[].name`)

The internal name is what V2's logic uses for identity, lookup, and cross-reference. Two rules:

1. **Descriptive names stay bare.** When the attribute name is unambiguous in any context — `industry`, `firstName`, `birthDate`, `paymentMethod`, `phoneNumber`, `mailingAddress`, `numberOfEmployees`, `annualRevenue` — the internal name uses the descriptive form without entity prefix.

2. **Generic-noun names get an entity-context prefix.** When the bare name is too generic to stand alone in queries / cross-references / API code (`name`, `status`, `type`, `amount`), the internal name adopts an entity-context prefix:
   - `account.accountName` (not `account.name`)
   - `donation.giftAmount` (not `donation.amount`)
   - `case.caseStatus` (not `case.status`)
   - `engagement.engagementType` (not `engagement.type`)
   - `pipeline-stage.stageName` (not `pipeline-stage.name`)
   - Audit fields (`createdAt`, `lastModifiedAt`, `id`) and reference fields whose name already implies the target (`assignedUser`, `parentAccount`, `account`, `contact`) stay bare — they're universally understood.

### Display name (`attributes[].display_name`)

The display name is what V2 surfaces to users in interview methodology, gap reports, and cross-system mapping output. Always entity-prefixed when bare would be ambiguous:

- `Account Name`, `Donation Status`, `Gift Amount`, `Case Subject`, `Note Body`, `User Role`
- Already-descriptive names display bare: `First Name`, `Industry`, `Email`, `Phone`, `Mobile Phone`
- Internal name and display_name conventions are aligned but not identical — `internal: industry` displays as `Industry` (no prefix needed); `internal: accountName` displays as `Account Name`.

### Subclass attributes

Subclasses inherit the parent's attribute conventions. Discriminator references in `discriminator.attribute` must match the (post-rename) parent attribute name. When a parent attribute is renamed, all subclass discriminators referencing it must also be updated.

### Why these conventions

The rule set balances three pressures: (1) most CRM systems use bare attribute names natively (Salesforce.Account.Name, HubSpot.companies.name, Attio.companies.name), so prefixing in the catalog adds catalog-only naming that diverges from system conventions — handled in the api_name override table at deployment time; (2) catalog readers and V2 logic frequently encounter attribute references out of entity context (in cross-references, gap reports, multi-entity queries), where bare generic nouns are genuinely ambiguous; (3) display names are user-facing and benefit from disambiguation regardless of internal naming.

The chosen pattern — bare internal names for descriptive attributes, prefixed internal names for generic-noun attributes, always-prefixed display names for ambiguous bare nouns — minimizes friction with system conventions while resolving the genuine ambiguity in catalog-internal contexts.

---



For every entry in this catalog, claims are grounded in the following sources, in order of authority:

1. **Official documentation** — each system's authoritative reference (object reference, field reference, admin guide).
2. **Official API / developer guides** — each system's REST or developer documentation, which typically gives more rigorous schema information than admin docs (types, requiredness, enum values, max lengths).
3. **Direct schema inspection** — for the three open-source systems with public source code (EspoCRM, CiviCRM, Salesforce NPSP), the actual schema files in the system's repository are consulted as ground truth where they add fidelity beyond what docs alone provide.

Community/admin guides (third-party blog posts, consultant write-ups, implementation partner content) are explicitly excluded as a primary source — too much variability and staleness risk. The `usage` and `business_context` prose draws on general industry knowledge of how these entities are used in practice and is not directly cited.

Each entity's `sources[]` block lists every authoritative URL consulted for that entry. A claim that cannot be supported by one of these sources is not in the catalog.

---

## How V2 uses the catalog

Once V2's methodology entity schema is built (Step 0 follow-on), the catalog ingests into the database as seed data. From there V2 surfaces it to users in the following ways:

**Reference library.** While a user is drafting an entity definition during Inventory Reconciliation or Entity PRD work, V2 displays the catalog entry for the closest-matching base entity alongside the draft, so the user sees how Salesforce / HubSpot / Attio / EspoCRM / CiviCRM / NPSP / Bloomerang typically represent the same concept.

**Starter templates.** When a user picks a base entity from the catalog, V2 pre-populates a draft entity with the most commonly-used standard attributes. The user edits down or adds to. Reduces blank-page friction.

**Advisor / gap-checker.** When a user defines their own entity, V2 compares the draft against the catalog and flags missing attributes that are standard in 5+ surveyed systems with a prompt like "Most CRMs that have a Contact entity also include `last_modified`, `owner`, and `do_not_contact` — do you want those?"

**Cross-system mapper.** When a deployment target is selected (Attio, EspoCRM, HubSpot, etc.), V2 uses the catalog's `systems[]` blocks to translate the user's domain entity into the target backend's native entity / attribute names. The same `mechanism` vocabulary on subclasss lets V2 know how to deploy a subclass (record type, subtype, separate object, etc.) to the chosen backend.

The interview methodology consumes the same catalog through the `business_context` and `usage` prose, which are written specifically to give interviewers context-aware probing questions for each entity and attribute.
