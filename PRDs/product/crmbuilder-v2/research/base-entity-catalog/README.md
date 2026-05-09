# Base Entity Catalog

**Last Updated:** 05-09-26 10:45
**Status:** Tiers 1-4 complete; Tier 5 pending
**Owner:** CRMBuilder v2

---

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.4 | 05-09-26 | Tier 4 (nonprofit-specialized) added: donation, recurring-gift, grant, membership, volunteer-hour, household, affiliation, soft-credit, constituent, engagement. Plus two specializations: account-household (Account specialization for the NPSP record-type pattern), donation-major-gift (Donation specialization for major-gift cultivation). 12 entries total. Tier 5 pending. |
| 0.3 | 05-08-26 | Tier 3 (vertical modules) added: case, solution, asset, campaign, campaign-member, email, form-submission, product, price-list, order, invoice, payment. 12 entities covering customer-service, marketing, and commerce concerns. |
| 0.2 | 05-08-26 | Tier 2 (sales pipeline) added: lead, opportunity, pipeline-stage, quote. |
| 0.1 | 05-08-26 | Initial Tier 1 sample: account, contact, activity, note, user, tag base entities plus account-nonprofit specialization. Schema established; sourcing methodology documented. |

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
└── specializations/
    ├── account-nonprofit.yaml             # T1 specialization of Account
    ├── account-household.yaml             # T4 specialization of Account
    └── donation-major-gift.yaml           # T4 specialization of Donation
```

Base entity files are universal types that every (or nearly every) CRM has. Specialization files reference a parent entity, name a discriminator (the parent attribute and value that selects this subclass), and list only delta attributes that the specialization adds beyond what the parent already defines.

A specialization may end up implemented as a record type, contact subtype, type discriminator, custom property, or even a separate entity depending on the target backend's subclassing capabilities. Each specialization YAML's `systems[]` block names the implementation pattern per system using a controlled `mechanism` vocabulary so V2 knows how to deploy the specialization to whichever target CRM is selected.

---

## Entity YAML schema

Every base-entity YAML file follows this shape. Specialization files use the same shape with two additions: `entry_kind: specialization`, `parent_entity` reference, and a `discriminator` block.

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `catalog_id` | string | yes | Stable identifier; matches filename minus `.yaml`. lowercase-hyphenated. |
| `catalog_version` | string | yes | Semantic version of this entry (e.g. `0.1`). |
| `last_updated` | string | yes | `MM-DD-YY HH:MM` per project standard. |
| `tier` | integer | yes | 1 (universal core), 2 (sales pipeline), 3 (vertical), 4 (nonprofit), 5 (comms detail). |
| `entry_kind` | enum | yes | `universal` or `specialization`. |
| `parent_entity` | string | conditional | Required when `entry_kind: specialization`. Catalog ID of the parent entity. |
| `discriminator` | object | conditional | Required when `entry_kind: specialization`. Names the parent attribute and value that selects this subclass. |
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
| `mechanism` | enum | conditional | Required for specializations only. One of `record_type`, `contact_subtype`, `type_discriminator`, `custom_property`, `separate_object`, `entity_inheritance`. Names the architectural pattern used to realize this specialization in this system. |
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
| `presence` | object | yes | Per-system presence map — keys are system names, values are one of `standard` (system ships it built-in), `custom` (system supports it but you'd add it as a custom field/property), `absent` (system structurally cannot or doesn't represent this concept). |
| `notes` | string | no | Cross-system divergence, naming differences, or other implementation considerations. |

### `relationships[]` schema (per-relationship)

| Field | Type | Required | Description |
|---|---|---|---|
| `target` | string | yes | Catalog ID of the related entity. |
| `cardinality` | enum | yes | One of `one-to-one`, `one-to-many`, `many-to-one`, `many-to-many`. |
| `role` | enum | yes | One of `parent`, `child`, `peer`, `polymorphic`. |
| `description` | string | yes | What the relationship represents. |
| `presence` | object | yes | Per-system presence map (same vocabulary as attribute presence). |

---

## Sourcing methodology

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

**Cross-system mapper.** When a deployment target is selected (Attio, EspoCRM, HubSpot, etc.), V2 uses the catalog's `systems[]` blocks to translate the user's domain entity into the target backend's native entity / attribute names. The same `mechanism` vocabulary on specializations lets V2 know how to deploy a specialization (record type, subtype, separate object, etc.) to the chosen backend.

The interview methodology consumes the same catalog through the `business_context` and `usage` prose, which are written specifically to give interviewers context-aware probing questions for each entity and attribute.
