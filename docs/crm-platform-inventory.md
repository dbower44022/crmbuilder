# CRM Platform API Capability Inventory

> **Purpose:** Comprehensive, maintainable inventory of commercial CRM platforms
> evaluated against the CRM Builder feature set. Used to assess which platforms
> could be targeted by CRM Builder adapters.
>
> **Last Updated:** 2026-03-30
>
> **Platforms Covered:** EspoCRM (reference), Salesforce, Zoho CRM, Microsoft
> Dynamics 365, HubSpot, Odoo, SugarCRM, Pipedrive, Creatio, Freshsales,
> Vtiger, Insightly, Copper, Monday.com CRM, SuiteCRM

---

## Table of Contents

1. [How to Read This Document](#how-to-read-this-document)
2. [CRM Builder Feature Reference](#crm-builder-feature-reference)
3. [Platform Profiles](#platform-profiles)
4. [Capability Comparisons](#capability-comparisons)
   - A. [API Protocol & Authentication](#a-api-protocol--authentication)
   - B. [Standard Entities](#b-standard-entities)
   - C. [Custom Entity Management](#c-custom-entity-management)
   - D. [Field Types](#d-field-types)
   - E. [Field Properties](#e-field-properties)
   - F. [Layout Management](#f-layout-management)
   - G. [Relationship Management](#g-relationship-management)
   - H. [Data Import & Record Operations](#h-data-import--record-operations)
   - I. [Workflow & Automation](#i-workflow--automation-future)
   - J. [Roles & Permissions](#j-roles--permissions-future)
   - K. [Dashboards & Reports](#k-dashboards--reports-future)
   - L. [Email Templates](#l-email-templates-future)
   - M. [Webhooks & Events](#m-webhooks--events-future)
5. [API Rate Limits & Pricing](#api-rate-limits--pricing)
6. [Tier Assessment](#tier-assessment)
7. [Revision History](#revision-history)

---

## How to Read This Document

**Rating Scale** used throughout capability tables:

| Rating | Meaning |
|--------|---------|
| **Full** | Complete API support — create, read, update, delete metadata via REST/API |
| **Partial** | Some operations available; significant gaps or workarounds required |
| **Read-only** | Can read/query metadata via API but cannot create or modify |
| **Indirect** | Achievable through package upload, file manipulation, or non-REST mechanism |
| **None** | Not available via any API; UI-only configuration |
| **N/A** | Feature does not exist on this platform |
| **—** | Not yet researched |

**Edition markers** indicate minimum tier required for API access:

- **(Free)** — Available on free/developer tier
- **(Pro)** — Requires Professional-tier license
- **(Ent)** — Requires Enterprise-tier license
- **(All)** — Available on all paid tiers

---

## CRM Builder Feature Reference

These are the capabilities CRM Builder currently implements against EspoCRM,
plus anticipated future features. Each capability section in the comparison
tables maps back to this reference.

### Current Features (v1.0)

| Category | Capability | EspoCRM Implementation |
|----------|-----------|----------------------|
| **Entities** | Create custom entity types (Base, Person, Company, Event) | `POST /EntityManager/action/createEntity` |
| **Entities** | Delete custom entities | `POST /EntityManager/action/removeEntity` |
| **Entities** | Check entity existence | `GET /Metadata?key=scopes.{entity}` |
| **Entities** | Cache rebuild after schema changes | `POST /Admin/rebuild` |
| **Fields** | Create custom fields (14 types) | `POST /Admin/fieldManager/{entity}` |
| **Fields** | Update field properties | `PUT /Admin/fieldManager/{entity}/{field}` |
| **Fields** | Read field metadata | `GET /Metadata?key=entityDefs.{entity}.fields` |
| **Fields** | Compare field spec vs live state | Property-by-property diff in `comparator.py` |
| **Fields** | Tooltip management | `PUT /Admin/fieldManager/{entity}/{field}` |
| **Layouts** | Read detail/edit/list layouts | `GET /Layout/action/getOriginal` |
| **Layouts** | Write detail/edit/list layouts | `PUT /{entity}/layout/{type}` |
| **Layouts** | Panel/section structure | Panels with rows, labels, styles |
| **Layouts** | Tab grouping | `tabBreak` + `tabLabel` on panels |
| **Layouts** | Conditional visibility | `dynamicLogicVisible` on panels |
| **Relationships** | Create oneToMany/manyToOne/manyToMany | `POST /EntityManager/action/createLink` |
| **Relationships** | Check link existence | `GET /Metadata?key=entityDefs.{entity}.links` |
| **Relationships** | Audit flags on both sides | `audited` / `auditedForeign` |
| **Import** | Create records via API | `POST /{entity}` |
| **Import** | Update records (PATCH, no overwrite) | `PATCH /{entity}/{id}` |
| **Import** | Search by email for deduplication | `GET /{entity}?where[0][type]=equals&...` |
| **Deploy** | Provision instance via SSH | `deploy_manager.py` (not API-dependent) |

### Anticipated Future Features

| Category | Capability | Notes |
|----------|-----------|-------|
| **Workflow** | Create automation rules via API | Trigger-based field updates, email sends |
| **Roles** | Manage roles and permissions via API | Module-level and field-level ACLs |
| **Dashboards** | Configure dashboards via API | Chart types, data sources, layout |
| **Reports** | Create saved reports/views via API | Filters, columns, grouping |
| **Email Templates** | Manage email templates via API | Merge fields, HTML body |
| **Webhooks** | Configure outbound notifications | Event subscriptions, endpoint URLs |
| **Formula Fields** | Calculated/derived field values | Dependent on platform support |
| **Validation Rules** | Field-level validation logic | Regex, range, cross-field rules |
| **Record Types** | Entity subtypes with different layouts | Per-type field sets and page layouts |
| **Portal Access** | External user/customer access config | Portal roles, visible entities |

---

## Platform Profiles

### EspoCRM (Reference Platform)

- **Type:** Open-source CRM (GPL v3)
- **Deployment:** Self-hosted (Docker)
- **API:** REST (JSON), versioned at `/api/v1/`
- **Auth:** API Key, HMAC, Basic Auth
- **Admin API:** Full metadata CRUD for entities, fields, layouts, relationships
- **Pricing:** Free (self-hosted); hosted plans from $15/user/mo
- **Developer Tier:** Unlimited (self-hosted)

### Salesforce

- **Type:** Cloud CRM (SaaS)
- **Deployment:** Salesforce-hosted only
- **API:** REST + SOAP + Metadata API + Tooling API + Bulk API
- **Auth:** OAuth 2.0 (JWT Bearer, Web Server, Device flows)
- **Admin API:** Full metadata CRUD via Metadata API (SOAP/REST)
- **Pricing:** $25–330/user/mo depending on edition
- **Developer Tier:** Free Developer Edition (2 users, 5MB data, 15K API calls/day)

### Zoho CRM

- **Type:** Cloud CRM (SaaS)
- **Deployment:** Zoho-hosted; no self-hosted option
- **API:** REST (JSON), current version V7
- **Auth:** OAuth 2.0 with granular scopes
- **Admin API:** Field creation (Enterprise+); layout and module creation UI-only
- **Pricing:** Free–$52/user/mo
- **Developer Tier:** Free (3 users, 5K API calls/day); Developer account at developer.zoho.com

### Microsoft Dynamics 365

- **Type:** Cloud/On-premise CRM
- **Deployment:** Azure-hosted (Dataverse) or on-premise
- **API:** OData v4 REST (JSON), FetchXML
- **Auth:** OAuth 2.0 via Microsoft Entra ID (Azure AD)
- **Admin API:** Full metadata CRUD via EntityDefinitions/RelationshipDefinitions endpoints
- **Pricing:** $65–150/user/mo
- **Developer Tier:** Free Power Apps Developer Plan (Dataverse only); 30-day Dynamics trial

### HubSpot

- **Type:** Cloud CRM (SaaS)
- **Deployment:** HubSpot-hosted only
- **API:** REST (JSON), versioned at `/crm/v3/` and `/crm/v4/`
- **Auth:** OAuth 2.0, Private App tokens
- **Admin API:** Properties (all tiers); Custom objects (Enterprise only); No layout API
- **Pricing:** Free–$150/user/mo
- **Developer Tier:** Free CRM (1M contacts, 2 users); no custom objects on free tier

### Odoo

- **Type:** Open-source ERP/CRM (LGPL)
- **Deployment:** Self-hosted, Odoo.sh (PaaS), or Odoo Online (SaaS)
- **API:** XML-RPC, JSON-RPC; REST API (Enterprise, Odoo 17+)
- **Auth:** Database + username + password/API key; OAuth 2.0 (Enterprise REST)
- **Admin API:** Full model/field/view/automation CRUD via `ir.model`, `ir.ui.view`, etc.
- **Pricing:** Free (Community); $25–47/user/mo (Enterprise)
- **Developer Tier:** Community Edition is fully free with complete API access

### SugarCRM

- **Type:** Commercial CRM (cloud + on-premise)
- **Deployment:** Sugar Cloud (hosted) or on-premise (Enterprise only)
- **API:** REST v11.5 (JSON), OAuth 2.0
- **Auth:** OAuth 2.0 (password grant, platform type)
- **Admin API:** Field CRUD via `/Metadata/fields`; relationships via `/Metadata/relationships`; layouts read-only via REST (file-based write)
- **Pricing:** ~$49–85/user/mo
- **Developer Tier:** No free tier; trial available

### Pipedrive

- **Type:** Cloud CRM (SaaS), sales-focused
- **Deployment:** Pipedrive-hosted only
- **API:** REST (JSON), v1 and v2 endpoints
- **Auth:** OAuth 2.0, API tokens
- **Admin API:** Custom field CRUD only; no entity, layout, or relationship APIs
- **Pricing:** $14–99/user/mo
- **Developer Tier:** 14-day trial; developer sandbox for marketplace apps

### Creatio

- **Type:** Low-code CRM platform
- **Deployment:** Cloud or on-premise
- **API:** OData 3/4 (JSON), DataService (JSON-RPC)
- **Auth:** Forms auth (cookie), Basic, OAuth 2.0
- **Admin API:** Record CRUD via OData; schema changes require package deployment
- **Pricing:** $25/user/mo (platform) + $15/user/mo per product module
- **Developer Tier:** 14-day trial; minimum ~$10K/year

### Freshsales (Freshworks CRM)

- **Type:** Cloud CRM (SaaS)
- **Deployment:** Freshworks-hosted only
- **API:** REST (JSON)
- **Auth:** API key (header)
- **Admin API:** Record CRUD; schema management poorly documented/unavailable
- **Pricing:** Free–$59/user/mo
- **Developer Tier:** Free (3 users, 1K contacts)

### Vtiger

- **Type:** Cloud CRM + open-source Community Edition
- **Deployment:** Cloud (hosted) or self-hosted (Community)
- **API:** REST via `/webservice.php`; VTAP (Cloud)
- **Auth:** Basic auth + access key (Cloud); session-based (Community)
- **Admin API:** Record CRUD + metadata read; no schema creation via API
- **Pricing:** Free (Community, self-hosted); $15–66/user/mo (Cloud)
- **Developer Tier:** Open-source Community Edition

### Insightly

- **Type:** Cloud CRM (SaaS)
- **Deployment:** Insightly-hosted only
- **API:** REST v3.1 (JSON)
- **Auth:** Basic auth (API key)
- **Admin API:** Record CRUD only; all schema operations UI-only
- **Pricing:** $29–99/user/mo (annual only)
- **Developer Tier:** None (free tier removed Oct 2024)

### Copper

- **Type:** Cloud CRM (SaaS), Google Workspace-focused
- **Deployment:** Copper-hosted only
- **API:** REST (JSON)
- **Auth:** API key + email in headers
- **Admin API:** Custom field definition CRUD; no entity or layout APIs
- **Pricing:** $9–119/user/mo
- **Developer Tier:** 14-day trial; full API requires Business plan ($119/user/mo)

### Monday.com CRM

- **Type:** Work OS with CRM product
- **Deployment:** Monday.com-hosted only
- **API:** GraphQL (not REST)
- **Auth:** API tokens (personal or app-level)
- **Admin API:** Board/column CRUD (analogous to entity/field); no layout API
- **Pricing:** $12–28+/seat/mo (min 3 seats)
- **Developer Tier:** Free plan (individual); 14-day CRM trial

### SuiteCRM

- **Type:** Open-source CRM (AGPL v3), fork of SugarCRM CE
- **Deployment:** Self-hosted only
- **API:** REST v8 (JSON:API format), legacy SOAP/REST v4.1
- **Auth:** OAuth 2.0 (password grant)
- **Admin API:** Record CRUD via JSON:API; schema operations require Studio UI or code
- **Pricing:** Free (self-hosted); managed hosting from ~£100/mo
- **Developer Tier:** Fully free and open-source

---

## Capability Comparisons

### A. API Protocol & Authentication

| Platform | Protocol | Format | Auth Methods | Admin Auth Required |
|----------|----------|--------|-------------|-------------------|
| **EspoCRM** | REST | JSON | API Key, HMAC, Basic | Admin role |
| **Salesforce** | REST + SOAP + Metadata API | JSON/XML | OAuth 2.0 (multiple flows) | System Admin profile |
| **Zoho CRM** | REST | JSON | OAuth 2.0 | Admin user + scopes |
| **Dynamics 365** | OData v4 REST | JSON | OAuth 2.0 (Azure AD) | System Admin role |
| **HubSpot** | REST | JSON | OAuth 2.0, Private App tokens | Super Admin account |
| **Odoo** | XML-RPC, JSON-RPC, REST (Ent 17+) | JSON/XML | Password, API key, OAuth 2.0 | Admin group membership |
| **SugarCRM** | REST | JSON | OAuth 2.0 (password grant) | Admin role |
| **Pipedrive** | REST | JSON | OAuth 2.0, API token | Account admin |
| **Creatio** | OData 3/4, DataService | JSON | Forms, Basic, OAuth 2.0 | SysAdmins role |
| **Freshsales** | REST | JSON | API key | Admin account |
| **Vtiger** | REST | JSON | Basic + access key, session | Admin login |
| **Insightly** | REST | JSON | Basic (API key) | Admin account |
| **Copper** | REST | JSON | API key + email | Admin account |
| **Monday.com** | GraphQL | JSON | API token | Account admin |
| **SuiteCRM** | REST (JSON:API) | JSON | OAuth 2.0 | Admin role |

---

### B. Standard Entities

CRM Builder works with both native (standard) and custom entities. This table
documents which standard CRM entities ship with each platform.

| Entity Concept | EspoCRM | Salesforce | Zoho | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|---------------|---------|-----------|------|-------------|---------|------|----------|
| **Contact / Person** | Contact | Contact | Contacts | Contact | Contacts | res.partner (type=contact) | Contacts |
| **Account / Company** | Account | Account | Accounts | Account | Companies | res.partner (type=company) | Accounts |
| **Lead** | Lead | Lead | Leads | Lead | Leads (Ent) | crm.lead (type=lead) | Leads |
| **Opportunity / Deal** | Opportunity | Opportunity | Deals | Opportunity | Deals | crm.lead (type=opportunity) | Opportunities |
| **Case / Ticket** | Case | Case | Cases | Incident (Case) | Tickets | helpdesk.ticket (module) | Cases |
| **Task** | Task | Task | Tasks | Task | Tasks | mail.activity | Tasks |
| **Meeting** | Meeting | Event | Meetings | Appointment | Meetings | calendar.event | Meetings |
| **Call** | Call | Task (type=Call) | Calls | PhoneCall | Calls | voip.phonecall | Calls |
| **Email** | Email | EmailMessage | Emails | Email | Emails | mail.mail | Emails |
| **Campaign** | Campaign | Campaign | Campaigns | Campaign | N/A | utm.campaign | Campaigns |
| **Target List** | TargetList | CampaignMember | N/A | List (MarketingList) | N/A | mailing.list | Target Lists |
| **Document** | Document | ContentDocument | Documents | Annotation (Note) | N/A | documents.document | Documents |
| **Product** | N/A | Product2 | Products | Product | Products | product.product | Products (Catalog) |
| **Quote** | N/A | Quote | Quotes | Quote | Quotes | sale.order | Quotes |
| **Invoice** | N/A | N/A (AppExchange) | Invoices | Invoice | Invoices | account.move | Invoices |
| **User** | User | User (SystemUser) | Users | SystemUser | Users | res.users | Users |
| **Team** | Team | Group | Teams | Team | Teams | crm.team | Teams |

**Entity Type Categories (Subclassing):**

| Platform | Entity Type System | Types Available |
|----------|-------------------|----------------|
| **EspoCRM** | Entity types at creation | Base, Person, Company, Event |
| **Salesforce** | Record Types on any object | Unlimited record types per object; Activity entities inherit from ActivityPointer; Person Accounts hybrid |
| **Zoho CRM** | Multiple Layouts per module | Layouts serve as record type equivalent; no formal entity subclassing |
| **Dynamics 365** | Table type categories | Standard, Activity, Virtual, Elastic, Child; plus OwnershipType (User, Org, Business, None) |
| **HubSpot** | None | Fixed object types; no record type or subclassing system |
| **Odoo** | Model inheritance | Delegation inheritance (`_inherits`), extension inheritance (`_inherit`); custom models via `ir.model` |
| **SugarCRM** | Module templates | Basic, Company, File, Issue, Person, Sale templates at creation |

**Label Renaming via API:**

| Platform | Can Rename Standard Entity Labels? | Mechanism |
|----------|-----------------------------------|-----------|
| **EspoCRM** | Yes | Language/label customization |
| **Salesforce** | Yes (display labels only) | `CustomObjectTranslation` metadata; API name stays fixed |
| **Zoho CRM** | UI only | Settings > Rename Modules; not via API |
| **Dynamics 365** | Yes | Update `DisplayName`/`DisplayCollectionName` on `EntityDefinitions` |
| **HubSpot** | No | Standard object labels are fixed |
| **Odoo** | Yes | Update `name` field on `ir.model` |
| **SugarCRM** | Yes | Language file customization via Vardefs |

---

### C. Custom Entity Management

| Capability | EspoCRM | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM | Pipedrive | Creatio |
|-----------|---------|-----------|----------|-------------|---------|------|----------|-----------|---------|
| **Create custom entity via API** | Full | Full | None (UI only) | Full | Full (Ent) | Full (Free) | Indirect (Module Loader) | None | Indirect (packages) |
| **Delete custom entity via API** | Full | Full | None | Full | Full (Ent) | Full | Indirect | N/A | Indirect |
| **Check entity existence via API** | Full | Full | Full | Full | Full | Full | Full | N/A | Full |
| **Entity type/template at creation** | Base, Person, Company, Event | N/A (use Record Types) | N/A | Standard, Activity, Virtual, Elastic | N/A | Custom model name prefix `x_` | Basic, Company, File, Issue, Person, Sale | N/A | N/A |
| **Cache/rebuild after schema change** | Full (`POST /Admin/rebuild`) | Required (`PublishXml` action) | N/A | Required (`PublishXml`/`PublishAllXml`) | N/A (automatic) | N/A (automatic) | Required (Quick Repair) | N/A | Required (compile) |
| **Activity stream on entity** | Yes (`stream` flag) | Yes (Chatter, Feed Tracking) | Yes (timeline) | Yes (Activity feeds) | Yes (timeline) | Yes (mail.thread mixin) | Yes (Activity Stream) | No | Yes (Feed) |
| **Max custom entities** | Unlimited | 10–2,000 (by edition) | 0–100 (by edition) | No hard limit | 10 (Ent, expandable) | Unlimited | Unlimited | 0 | Unlimited |
| **Custom entity naming convention** | C-prefix (auto) | `__c` suffix | System-assigned | Publisher prefix | System-assigned | `x_` prefix required | System module name | N/A | Publisher prefix |
| **Min edition for entity creation** | Free | Developer/Enterprise | Enterprise ($40) | All paid | Enterprise ($150) | Free (Community) | All paid (~$49) | N/A | All ($40+) |

**Detailed Notes:**

- **Salesforce**: Entities created via `createMetadata('CustomObject', ...)` on the Metadata API. Up to 10 components per call. Requires `deploymentStatus`, `sharingModel`, and a `nameField` definition.
- **Zoho CRM**: Custom module creation is exclusively a UI operation. The API can perform CRUD on records within custom modules but cannot create the module definition itself.
- **Dynamics 365**: Entities created via `POST /EntityDefinitions` with full property control. Must call `PublishXml` after creation. Uses solution publisher prefix for naming.
- **HubSpot**: Custom objects created via `POST /crm/v3/schemas`. Limited to 10 definitions (expandable). Requires Enterprise subscription ($150/user/mo).
- **Odoo**: Custom models created via `ir.model` with `execute_kw`. Technical name must start with `x_`. Available on free Community Edition. No practical limit on number of models.
- **SugarCRM**: No direct REST endpoint to create modules. Modules are built as packages and installed via Module Loader API (`POST /Administration/packages`).
- **Pipedrive**: Fixed entity model (Deals, Persons, Organizations, Products, Activities, Leads, Projects). Cannot create custom entities.
- **Creatio**: Entity schemas created via IDE or package deployment, not via OData REST. Packages can be deployed via `UploadPackage` endpoint.

---

### D. Field Types

CRM Builder currently supports 14 field types. This table maps each to the
equivalent type on each platform and indicates API creatability.

| CRM Builder Type | EspoCRM | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|-----------------|---------|-----------|----------|-------------|---------|------|----------|
| **varchar** | `varchar` | `Text` | `text` | `StringType` (Text format) | `string` / `text` | `char` | `varchar` |
| **text** | `text` | `LongTextArea` | `textarea` | `MemoType` | `string` / `textarea` | `text` | `text` |
| **wysiwyg** | `wysiwyg` | `Html` (Rich Text Area) | `richtextarea` | `MemoType` (RichText) | `string` / `html` | `html` | `html` |
| **enum** | `enum` | `Picklist` | `picklist` | `PicklistType` | `enumeration` / `select` | `selection` | `enum` |
| **multiEnum** | `multiEnum` | `MultiselectPicklist` | `multiselectpicklist` | `MultiSelectPicklistType` | `enumeration` / `checkbox` | `selection` (w/ widget) | `multienum` |
| **bool** | `bool` | `Checkbox` | `boolean` | `BooleanType` | `enumeration` / `booleancheckbox` | `boolean` | `bool` |
| **int** | `int` | `Number` (scale=0) | `integer` | `IntegerType` | `number` | `integer` | `int` |
| **float** | `float` | `Number` (with scale) | `decimal` | `DecimalType` or `DoubleType` | `number` | `float` | `float` / `decimal` |
| **date** | `date` | `Date` | `date` | `DateTimeType` (DateOnly) | `date` | `date` | `date` |
| **datetime** | `datetime` | `DateTime` | `datetime` | `DateTimeType` (DateAndTime) | `datetime` | `datetime` | `datetime` |
| **currency** | `currency` | `Currency` | `currency` | `MoneyType` | `number` (manual) | `monetary` | `currency` |
| **url** | `url` | `Url` | `website` | `StringType` (URL format) | `string` / `text` | `char` (widget=url) | `url` |
| **email** | `email` | `Email` | `email` | `StringType` (Email format) | `string` / `text` | `char` (widget=email) | `email` |
| **phone** | `phone` | `Phone` | `phone` | `StringType` (Phone format) | `string` / `phonenumber` | `char` (widget=phone) | `phone` |

**Additional Field Types Available Per Platform (not yet in CRM Builder):**

| Type Category | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|--------------|-----------|----------|-------------|---------|------|----------|
| **Auto-number** | `AutoNumber` | `autonumber` | `AutoNumberFormat` property | N/A | N/A | `autoincrement` |
| **Formula / Calculated** | `Formula` | `formula` (limited API) | `SourceTypeMask=1` | `calculation_equation` (UI only) | `compute` (code only) | `formula` (SugarLogic) |
| **Rollup Summary** | `Summary` | `rollup_summary` (UI only) | `SourceTypeMask=2` | `calculation_rollup` (UI only) | N/A | N/A |
| **Lookup / Relate** | `Lookup` | `lookup` | `LookupType` | N/A (via associations) | `many2one` | `relate` |
| **Master-Detail** | `MasterDetail` | N/A | N/A (cascade config) | N/A | N/A | N/A |
| **Image** | N/A (use File) | `imageupload` | `ImageType` | N/A | `image` / `binary` | `image` |
| **File** | `File` | `fileupload` | `FileType` | `file` (read-only) | `binary` | `file` |
| **Address** | N/A (compound) | N/A (compound) | N/A (compound) | N/A | N/A (compound) | N/A (compound) |
| **Percent** | `Percent` | `percent` | N/A (use Decimal) | N/A | N/A (use Float) | N/A |
| **Encrypted** | N/A | N/A (Ent) | N/A | N/A | N/A | `encrypt` |
| **JSON** | N/A | N/A | N/A | N/A | `json` (17+) | `json` |
| **Reference (polymorphic)** | N/A | N/A | `CustomerType` | N/A | `reference` | `parent` (flex relate) |
| **Time** | N/A | N/A | N/A (use DateTime) | N/A | N/A | N/A |
| **Geolocation** | N/A | N/A | `Location` | N/A | N/A | N/A |

**Field Creation via API — Summary:**

| Platform | All Current CRM Builder Types Creatable? | Total Types Available | API for Field Creation |
|----------|----------------------------------------|----------------------|----------------------|
| **EspoCRM** | Yes (14/14) | ~14 | `POST /Admin/fieldManager/{entity}` |
| **Salesforce** | Yes (14/14) | ~30 | Metadata API `createMetadata('CustomField', ...)` |
| **Zoho CRM** | Yes (14/14) — Enterprise+ only | ~20 | `POST /settings/fields?module={mod}` **(Ent)** |
| **Dynamics 365** | Yes (14/14) | ~20 creatable | `POST /EntityDefinitions({id})/Attributes` |
| **HubSpot** | Partial (12/14 — no dedicated currency/url type) | ~12 | `POST /crm/v3/properties/{objectType}` |
| **Odoo** | Yes (14/14) | ~18 | `ir.model.fields` via `execute_kw` |
| **SugarCRM** | Yes (14/14) | ~30+ | `POST /Metadata/fields/{module}` |
| **Pipedrive** | Partial (12/14 — limited wysiwyg/url) | ~17 | `POST /v1/{entity}Fields` |
| **Creatio** | None via API | ~20 | Package deployment only |

---

### E. Field Properties

| Property | EspoCRM | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|----------|---------|-----------|----------|-------------|---------|------|----------|
| **label** | `label` | `label` | `field_label` | `DisplayName` | `label` | `field_description` | `label` / `vname` |
| **required** | `required` | `required` | `required` (Ent) | `RequiredLevel` | N/A (pipeline-based) | `required` | `required` |
| **default** | `default` | `defaultValue` | `default_value` (Ent) | `DefaultValue` | N/A (workflow-based) | `default` | `default_value` |
| **readOnly** | `readOnly` | via Layout `behavior` | `read_only` (Ent) | via Form XML | N/A | `readonly` | `readonly` |
| **audited** | `audited` | `trackHistory` (max 20/obj) | UI only | `IsAuditEnabled` | N/A | `tracking` | `audited` |
| **description / help text** | `description` | `inlineHelpText` | `tooltip` (Ent) | `Description` | `description` | `help` | `help` |
| **tooltip** | `tooltip` | `inlineHelpText` | `tooltip` (Ent) | `Description` | N/A | `help` | `help` |
| **min / max** | `min` / `max` | `precision` / `scale` | N/A | `MinValue` / `MaxValue` | N/A | `digits` (precision) | `min` / `max` |
| **maxLength** | `maxLength` | `length` | `length` (Ent) | `MaxLength` | N/A | `size` | `len` |
| **unique** | N/A | `unique` | `unique` (Ent) | N/A (via alternate keys) | `hasUniqueValue` | `index` (partial) | N/A |
| **options (enum)** | `options` | `valueSet` / `picklist` | `pick_list_values` (Ent) | `OptionSet` | `options` | `selection_ids` | `options` (dropdown list) |
| **translatedOptions** | `translatedOptions` | via `CustomObjectTranslation` | N/A | `LocalizedLabels` | N/A | `translate=True` | Language files |
| **optionDescriptions** | `optionDescriptions` | N/A | N/A | N/A | N/A | N/A | N/A |
| **style (enum colors)** | `style` | N/A | N/A | N/A | N/A | N/A | N/A |
| **isSorted** | `isSorted` | N/A (manual order) | N/A | N/A | `displayOrder` on options | `sequence` on options | N/A |
| **displayAsLabel** | `displayAsLabel` | N/A | N/A | N/A | N/A | N/A | N/A |
| **copyToClipboard** | `copyToClipboard` | N/A | N/A | N/A | N/A | `copied` | N/A |
| **category (for layout grouping)** | `category` | N/A | N/A | N/A | `groupName` | N/A | N/A |
| **formula / calculated** | N/A | `formula` expression | `formula` (limited) | `FormulaDefinition` | N/A (UI only) | `compute` (code) | `formula` (SugarLogic) |
| **externalId / indexed** | N/A | `externalId` | N/A | Alternate Keys | N/A | `index` | N/A |

**Notes:**
- Properties marked **(Ent)** for Zoho require Enterprise edition for API write access.
- HubSpot notably lacks `required` and `default` as direct property attributes — these are enforced through pipeline/workflow configuration.
- EspoCRM's `optionDescriptions`, `style`, `displayAsLabel`, and `copyToClipboard` are unique features with no direct equivalent on most other platforms.

---

### F. Layout Management

This is the most significant differentiator between platforms.

| Capability | EspoCRM | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|-----------|---------|-----------|----------|-------------|---------|------|----------|
| **Read layouts via API** | Full | Full | Full (read-only) | Full | None | Full | Full (read-only) |
| **Write/update layouts via API** | Full | Full | None | Full | None | Full | Indirect (file-based) |
| **Detail/record view** | Full | Full (Layout + FlexiPage) | None | Full (SystemForm FormXml) | None | Full (`ir.ui.view` form) | Indirect |
| **Edit view** | Full (separate) | Same as detail (behavior property) | None | Same as detail | None | Same as detail | Indirect |
| **List view** | Full | Full (ListView metadata) | None | Full (SavedQuery) | None | Full (`ir.ui.view` tree) | Indirect |
| **Panel / section support** | Full (panels with labels, styles) | Full (LayoutSection) | N/A | Full (tabs → sections → rows → cells) | N/A | Full (group, notebook, page) | Indirect |
| **Tab grouping** | Full (`tabBreak` + `tabLabel`) | Full (via FlexiPage tabs) | N/A | Full (tab elements in FormXml) | N/A | Full (`notebook` → `page` elements) | Indirect |
| **Conditional visibility** | Full (`dynamicLogicVisible`) | Full (Dynamic Forms on FlexiPage) | None | Full (Business Rules on forms) | None | Full (`invisible` attribute with domain) | Indirect (SugarLogic `dependency`) |
| **Field width control** | Fixed 2-column grid | 1 or 2 column sections | N/A | 1–4 column sections, cell span | N/A | 12-column grid via `col`/`colspan` | Indirect (span property) |
| **Empty cell handling** | `false` / `null` for empty cells | N/A (empty LayoutItem) | N/A | Empty cells in grid | N/A | N/A (automatic) | N/A |
| **Kanban view** | N/A | N/A (Kanban paths) | N/A | N/A | N/A (board = pipeline) | Full (kanban view type) | N/A |
| **Calendar view** | N/A | N/A | N/A | N/A | N/A | Full (calendar view type) | N/A |
| **Min edition for layout API** | Free | Enterprise (for FlexiPage) | N/A | All paid | N/A | Free (Community) | All paid |

**Key Takeaways:**
- Only **EspoCRM**, **Salesforce**, **Dynamics 365**, and **Odoo** offer full programmatic layout management.
- **Zoho CRM** and **HubSpot** are notably weak — layouts are UI-only despite otherwise capable APIs.
- **SugarCRM** can modify layouts via file manipulation + API rebuild trigger, but lacks direct REST endpoints for layout CRUD.
- **Odoo** is the most flexible — views are XML stored in `ir.ui.view` records, fully readable and writable via API, with inheritance/override support.

---

### G. Relationship Management

| Capability | EspoCRM | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|-----------|---------|-----------|----------|-------------|---------|------|----------|
| **Create relationship via API** | Full | Full | Partial (lookup fields only) | Full | Full (Ent for labels) | Full | Full |
| **One-to-Many** | Full (`oneToMany`) | Full (`Lookup` field) | Partial (create lookup) | Full (`OneToManyRelationshipMetadata`) | Full (associations) | Full (`many2one` + `one2many`) | Full |
| **Many-to-One** | Full (`manyToOne`) | Full (`Lookup` field, reverse) | Partial (create lookup) | Full (reverse of 1:N) | Full (associations) | Full (`many2one`) | Full |
| **Many-to-Many** | Full (`manyToMany` + `relationName`) | Indirect (junction object + 2 MD fields) | Partial (`multiselectlookup`, Ent) | Full (`ManyToManyRelationshipMetadata`) | Full (associations, no junction) | Full (`many2many` + junction table) | Full (join table) |
| **Link labels (panel labels)** | Full (`label` / `labelForeign`) | Full (`relationshipLabel`) | N/A | Full (`AssociatedMenuConfiguration`) | Full (association labels, Ent) | Full (via view string attrs) | Full (`lhs_label` / `rhs_label`) |
| **Audit on both sides** | Full (`audited` / `auditedForeign`) | Per-field (`trackHistory`) | N/A | Per-relationship (`IsAuditEnabled`) | N/A | Per-field (`tracking`) | Per-field (`audited`) |
| **Check relationship existence** | Full (metadata query) | Full (describe/metadata) | Full (field metadata read) | Full (relationship metadata query) | Full (association type query) | Full (`fields_get`) | Full (metadata read) |
| **Cascade delete config** | N/A (system default) | Full (`deleteConstraint`: SetNull, Restrict, Cascade) | N/A | Full (`CascadeConfiguration`: 6 behaviors) | N/A | Full (`on_delete`: set null, restrict, cascade) | Partial |
| **Polymorphic / flex relate** | N/A | `Customer` type (Account OR Contact) | N/A | `CustomerType` (polymorphic lookup) | N/A | `reference` field (any model) | `parent` (flex relate) |
| **Self-referential** | Yes | Yes (Hierarchy on User) | Yes | Yes | N/A | Yes | Yes |
| **Min edition** | Free | Developer / Enterprise | Enterprise ($40) | All paid | Enterprise ($150) for labels | Free (Community) | All paid (~$49) |

---

### H. Data Import & Record Operations

| Capability | EspoCRM | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|-----------|---------|-----------|----------|-------------|---------|------|----------|
| **Create record** | Full | Full | Full | Full | Full | Full | Full |
| **Read record by ID** | Full | Full | Full | Full | Full | Full | Full |
| **Update record (PATCH)** | Full | Full | Full | Full | Full | Full (`write`) | Full |
| **Delete record** | Full | Full | Full | Full | Full (archive) | Full (`unlink`) | Full |
| **Search by field value** | Full (where filter) | Full (SOQL) | Full (COQL + search) | Full (OData $filter) | Full (search API, 10K max) | Full (domain expressions) | Full (filter API) |
| **Search by email** | Full | Full | Full | Full | Full | Full | Full |
| **Upsert (match + insert/update)** | Manual (search then create/patch) | Full (native upsert) | Full (`/upsert` endpoint) | Full (PATCH with alternate key) | N/A (manual) | Manual | Full (`/Imports` endpoint) |
| **Batch create** | N/A | 200 records/call (Collections) | 100 records/call | 1,000 ops/batch | 100 records/batch | Native (list of dicts) | 20-25 calls/bulk request |
| **Bulk async import** | N/A | Bulk API 2.0 (150MB/job) | Bulk Read/Write API | `CreateMultiple` action | Import API (CSV) | `load` method | Import API |
| **Query language** | Where filters | SOQL + SOSL | COQL (SQL-like) | OData + FetchXML | Search filters | Domain expressions | Filter API |
| **Max results per query** | Configurable | 2,000 (50K via queryMore) | 200/page | 5,000/page | 10,000 max | Configurable | Configurable |
| **Non-overwrite update** | CRM Builder logic (not API) | CRM Builder logic needed | CRM Builder logic needed | CRM Builder logic needed | CRM Builder logic needed | CRM Builder logic needed | CRM Builder logic needed |

---

### I. Workflow & Automation (Future)

| Capability | EspoCRM | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|-----------|---------|-----------|----------|-------------|---------|------|----------|
| **Create workflow rules via API** | — | Full (Workflow metadata) | Read-only | Full (Workflow entity) | None (UI only) | Full (`base.automation`) | Partial (SugarBPM export/import) |
| **Create automation/flows via API** | — | Full (Flow metadata) | None | Full (Cloud Flows as Workflow records) | None | Full (`ir.actions.server`) | None (visual designer) |
| **Approval processes** | — | Full (ApprovalProcess metadata) | Read + execute only | Full (BPF via API) | None | Full (custom) | SugarBPM (visual only) |
| **Validation rules** | — | Full (on CustomObject metadata) | None | Full (Business Rules) | None | Full (`ir.rule` + constraints) | SugarLogic dependencies |
| **Scheduled actions** | — | Full (Scheduled Flows) | None | Full (Cloud Flows) | None | Full (`ir.cron`) | None (UI cron) |
| **Email send from template** | — | Full (`SendEmailFromTemplate`) | Yes (use template ID) | Full (`SendEmailFromTemplate`) | Yes | Full (`mail.template`) | Yes |
| **Trigger types** | — | Record change, schedule, platform event | N/A | Record change, schedule, signal | N/A | on_create, on_write, on_unlink, on_time, on_stage_set | N/A |

---

### J. Roles & Permissions (Future)

| Capability | EspoCRM | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|-----------|---------|-----------|----------|-------------|---------|------|----------|
| **Create roles via API** | — | Full (Role metadata) | Read-only | Full (Role entity) | None (UI only) | Full (`res.groups`) | Full (`ACLRoles` endpoint) |
| **Module-level permissions** | — | Full (Profile/PermissionSet) | Read-only | Full (Role privileges) | None | Full (`ir.model.access`) | Full (ACL) |
| **Field-level security** | — | Full (FieldPermission) | None | Full (FieldSecurityProfile) | None | Full (field `groups` attr) | Full (field ACL) |
| **Record-level rules** | — | Full (SharingRules) | None | Full (via plugin/custom) | None | Full (`ir.rule` with domain) | Full (team-based) |
| **User management via API** | — | Full (User sObject) | Full (create/assign role) | Full (SystemUser) | Full (invite/assign) | Full (`res.users`) | Full |

---

### K. Dashboards & Reports (Future)

| Capability | EspoCRM | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|-----------|---------|-----------|----------|-------------|---------|------|----------|
| **Create dashboards via API** | — | Full (Dashboard metadata + Analytics API) | None | Full (SystemForm type=Dashboard) | None | Full (`ir.ui.view` type=dashboard) | Partial |
| **Create/run reports via API** | — | Full (Report metadata + Analytics API) | Read + execute only | Full (SavedQuery + Charts) | None | Full (custom) | Partial |
| **Create saved views/filters** | — | Full (ListView metadata) | None | Full (SavedQuery entity) | None | Full (`ir.filters`) | Yes |

---

### L. Email Templates (Future)

| Capability | EspoCRM | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|-----------|---------|-----------|----------|-------------|---------|------|----------|
| **CRUD email templates via API** | — | Full (EmailTemplate metadata) | Read-only | Full (Template entity) | N/A | Full (`mail.template`) | Yes |
| **Merge fields / dynamic content** | — | Merge fields in body | Template variables | `{!Entity:field}` syntax | N/A | Jinja2/QWeb | Sugar template vars |
| **HTML body support** | — | Yes (HTML, Visualforce) | Yes | Yes | N/A | Yes (QWeb) | Yes |

---

### M. Webhooks & Events (Future)

| Capability | EspoCRM | Salesforce | Zoho CRM | Dynamics 365 | HubSpot | Odoo | SugarCRM |
|-----------|---------|-----------|----------|-------------|---------|------|----------|
| **Outbound webhooks via API** | — | Indirect (Outbound Messages, Platform Events) | UI only (workflow config) | Full (ServiceEndpoint webhooks) | UI only (workflow) | Full (`ir.actions.server` type=webhook, 17+) | Indirect (Logic Hooks) |
| **Event subscriptions** | — | Full (Platform Events, CDC) | Partial (`/actions/watch`) | Full (webhooks + Azure Service Bus + Event Grid) | Webhooks (workflow-based) | Full (automated actions) | Indirect |
| **Sync vs Async** | — | Both | Async only | Both | Async only | Both | Async only |
| **Retry on failure** | — | Yes (Outbound Messages) | N/A | Yes (1 retry on 502/503/504) | N/A | N/A | N/A |

---

## API Rate Limits & Pricing

### Rate Limits

| Platform | Rate Limit | Daily Limit | Burst/Concurrent |
|----------|-----------|------------|------------------|
| **EspoCRM** | Self-hosted (unlimited) | N/A | N/A |
| **Salesforce** | N/A (no per-second limit) | 15K–5M+ (by edition/user count) | 25 concurrent (prod) |
| **Zoho CRM** | 10–30 req/min/user (by edition) | 5K–2.5M credits/day (by edition) | 5–25 concurrent |
| **Dynamics 365** | 6,000 req/5min/user/server | 40K req/day (per license) | 52+ concurrent |
| **HubSpot** | 100–200 req/10sec (by edition) | 500K req/day | N/A |
| **Odoo** | Self-hosted (unlimited) | N/A | N/A |
| **SugarCRM** | N/A (unlimited calls included) | Unlimited | N/A |
| **Pipedrive** | 80 req/2sec (120 Enterprise) | Effectively unlimited | N/A |
| **Creatio** | Not documented | Not documented | N/A |

### Pricing Summary

| Platform | Free/Dev Tier | Minimum Paid | Full Admin API | Enterprise |
|----------|-------------|-------------|---------------|-----------|
| **EspoCRM** | Free (self-hosted, unlimited) | $15/user/mo (hosted) | Free | Free |
| **Salesforce** | Free Developer Edition | $25/user/mo (Starter) | $165/user/mo (Enterprise) | $330/user/mo |
| **Zoho CRM** | Free (3 users) | $14/user/mo | $40/user/mo (Enterprise) | $52/user/mo |
| **Dynamics 365** | Free Dev Plan (Dataverse) | $65/user/mo (Professional) | $65/user/mo | $150/user/mo |
| **HubSpot** | Free CRM | $20/user/mo (Starter) | $150/user/mo (Enterprise) | $150/user/mo |
| **Odoo** | Free (Community Edition) | $25/user/mo (Standard) | Free (Community) | $47/user/mo |
| **SugarCRM** | None | ~$49/user/mo (Sell) | ~$49/user/mo | ~$85/user/mo |
| **Pipedrive** | 14-day trial | $14/user/mo | $14/user/mo (fields only) | $99/user/mo |
| **Creatio** | 14-day trial | $40/user/mo (platform + Sales) | $40/user/mo (packages) | $70/user/mo |
| **Freshsales** | Free (3 users) | $9/user/mo | N/A (limited admin API) | $59/user/mo |
| **Vtiger** | Free (Community OSS) | $15/user/mo | N/A (limited admin API) | $58/user/mo |
| **Insightly** | None | $29/user/mo | N/A | $99/user/mo |
| **Copper** | 14-day trial | $9/user/mo | $119/user/mo (Business) | $119/user/mo |
| **Monday.com** | 14-day trial | $12/seat/mo | N/A | Contact sales |
| **SuiteCRM** | Free (self-hosted, OSS) | £100/mo (managed, 10 users) | N/A (code-level) | N/A |

---

## Tier Assessment

Based on the complete inventory, platforms are grouped by their viability as
CRM Builder targets.

### Tier 1 — Full Feature Coverage via API

These platforms support entity, field, layout, and relationship management
entirely through their APIs, making them directly viable for CRM Builder
adapters.

| Platform | Strengths | Gaps | Adapter Complexity |
|----------|----------|------|-------------------|
| **Salesforce** | Gold standard metadata API; all 14 field types; full layout + relationship CRUD; largest market share; free dev tier | SOAP-based Metadata API adds complexity; XML layout format; high pricing for production use | Medium-High (Metadata API is SOAP/deploy-based, not simple REST) |
| **Dynamics 365** | Full OData metadata CRUD; entities, fields, relationships, forms all via REST; strong enterprise market | FormXml is XML not JSON; `PublishXml` required after changes; complex auth (Azure AD); no accessible free tier | Medium-High (OData + XML form definitions) |
| **Odoo** | Most flexible — models, fields, views, automation, security ALL via API; free Community Edition; unlimited customization | Not REST (XML-RPC/JSON-RPC); `x_` naming prefix; views are XML arch; RPC deprecation planned for Odoo 22 (2028) | Medium (RPC protocol + XML view arch) |

### Tier 2 — Strong but Missing Layout API

These platforms support entity and field management via API but lack
programmatic layout control.

| Platform | Strengths | Gaps | Adapter Complexity |
|----------|----------|------|-------------------|
| **Zoho CRM** | Dedicated field creation API; good record CRUD; affordable | **No layout API**; **no custom module API**; Enterprise required for field API ($40/user/mo) | Low (if layout management dropped) |
| **SugarCRM** | Strong field REST API (`/Metadata/fields`); relationship API; full ACL API; on-premise option | Modules require package deployment; layouts are file-based not REST; no free tier | Medium (package-based module + file-based layout) |
| **HubSpot** | Clean REST API; good property CRUD; large ecosystem | **No layout API**; custom objects require Enterprise ($150/mo); no `required`/`default` on properties; limited field types | Low (if scoped to fields + relationships only) |

### Tier 3 — Fields Only

These platforms allow custom field creation via API but cannot create entities,
layouts, or relationships programmatically.

| Platform | Viable For |
|----------|-----------|
| **Pipedrive** | Field provisioning on fixed entity model only |
| **Copper** | Field provisioning (Business plan required at $119/mo) |
| **Monday.com** | Column creation on boards (GraphQL, different paradigm) |

### Tier 4 — Data API Only

These platforms have functional record CRUD APIs but no schema/metadata
management capabilities. Not viable for CRM Builder configuration automation.

| Platform | Notes |
|----------|-------|
| **Freshsales** | Custom module/field creation not documented via API |
| **Vtiger** | API is data-oriented; Module Builder is UI-only |
| **Insightly** | All schema operations UI-only; free tier removed |
| **SuiteCRM** | Open source but API is data-only; schema via code/Studio |
| **Creatio** | Schema changes require package/IDE; OData is data-only |

### Recommended Priority for CRM Builder Adapters

1. **Salesforce** — Largest addressable market; most complete API; free dev tier for testing
2. **Odoo** — Free, open-source, fully API-configurable; strong in SMB/mid-market
3. **Dynamics 365** — Strong enterprise market; full metadata API; complex but capable
4. **SugarCRM** — Good field/relationship API; on-premise option; mid-market focus
5. **Zoho CRM** — Affordable; good field API; layout gap requires UI setup
6. **HubSpot** — Large market but Enterprise gate on key features is a barrier

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2026-03-30 | Initial inventory — 15 platforms across 13 capability dimensions | Claude / Doug |
