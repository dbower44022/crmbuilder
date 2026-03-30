# CRM Platform API Capability Inventory

> **Generated:** 2026-03-30 by `crm_compare.py inventory`
> **Platforms:** 25
> **Source data:** `docs/crm-platforms/platforms/*.yaml`

---

## Platform Overview

| Platform | Type | Open Source | License | API Protocol | Auth | Free/Dev Tier |
|----------|------|------------|---------|-------------|------|--------------|
| **ActiveCampaign** | Marketing Automation + CRM (SaaS) | No | Proprietary | REST | API key (Api-Token header) | Developer sandbox (100 contacts, 2-year expiry) |
| **Agile CRM** | Cloud CRM (SaaS) | No | Proprietary | REST | Basic Auth (email + API key) | Free (10 users, 50K contacts, 1 workflow) |
| **Attio** | Cloud CRM (SaaS) | No | Proprietary | REST | Bearer token, OAuth 2.0, HTTP Basic | Free (3 seats, 50K records, 3 custom objects) |
| **Bigin (by Zoho)** | Lightweight CRM (SaaS) | No | Proprietary | REST | OAuth 2.0 (Zoho-oauthtoken) | Free (1 user, 5K API credits/day) |
| **Bitrix24** | All-in-one Business Platform (CRM + PM + Comms) | No | Proprietary (cloud and self-hosted) | REST | OAuth 2.0 (marketplace apps), Webhook URLs (secret token) | Free (unlimited users, 5GB, but NO REST API access since Jan 2021) |
| **CiviCRM** | Open-source nonprofit CRM (AGPL v3) | Yes | AGPL v3 | REST, PHP, CLI, AJAX | API Key (Bearer), JWT, Basic Auth (disabled by default) | Fully free and open-source (AGPL v3) |
| **Copper** | Cloud CRM (SaaS) | No | Proprietary | REST | API key + email headers | 14-day trial |
| **Creatio** | Low-code CRM platform | No | Proprietary | OData 3/4, DataService JSON-RPC | Forms auth, Basic auth, OAuth 2.0 | 14-day trial |
| **EspoCRM** | Open-source CRM (GPL v3) | Yes | GPL v3 | REST | API Key, HMAC, Basic Auth | Free (self-hosted, unlimited) |
| **Freshsales (Freshworks CRM)** | Cloud CRM (SaaS) | No | Proprietary | REST | API key | Free (3 users, 1K contacts) |
| **HubSpot** | Cloud CRM (SaaS) | No | Proprietary | REST | OAuth 2.0, Private App tokens | Free CRM (1M contacts, 2 users) |
| **Insightly** | Cloud CRM (SaaS) | No | Proprietary | REST | Basic auth (API key) | None (removed Oct 2024) |
| **Microsoft Dynamics 365** | Cloud/On-premise CRM | No | Proprietary | OData v4 REST, FetchXML | OAuth 2.0 via Microsoft Entra ID (Azure AD) | Power Apps Developer Plan (Dataverse only); 30-day Dynamics trial |
| **Monday.com CRM** | Work OS with CRM product | No | Proprietary | GraphQL | API tokens | 14-day trial |
| **Monica** | Open-source Personal CRM (AGPL v3) | Yes | AGPL v3 | REST | OAuth 2.0 Bearer token | Hosted: 10 contacts; Self-hosted: unlimited, free |
| **Nimble** | Cloud CRM (SaaS) | No | Proprietary | REST | OAuth 2.0, API key | 14-day trial (5 licenses) |
| **Odoo** | Open-source ERP/CRM (LGPL) | Yes | LGPL v3 (Community); Proprietary (Enterprise) | XML-RPC, JSON-RPC, REST API (Enterprise 17+) | Database + username + password/API key, OAuth 2.0 (Enterprise REST) | Community Edition (fully free, self-hosted, complete API) |
| **Pipedrive** | Cloud CRM (SaaS) | No | Proprietary | REST | OAuth 2.0, API tokens | 14-day trial |
| **Salesforce** | Cloud CRM (SaaS) | No | Proprietary | REST, SOAP, Metadata API, Tooling API, Bulk API | OAuth 2.0 | Developer Edition (2 users, 5MB data, 15K API calls/day) |
| **Salesmate** | Cloud CRM (SaaS) | No | Proprietary | REST | Bearer token + x-linkname header | 15-day trial |
| **SugarCRM** | Commercial CRM (cloud + on-premise) | No | Proprietary (current versions; SugarCRM CE was open-source, now SuiteCRM) | REST | OAuth 2.0 | None |
| **SuiteCRM** | Open-source CRM (AGPL v3) | Yes | AGPL v3 | REST, SOAP | OAuth 2.0 | Fully free and open-source |
| **Twenty** | Open-source CRM (AGPL v3) | Yes | AGPL v3 | REST, GraphQL | API key (Bearer token) | Self-hosted: free; Cloud Pro: $9/user/mo |
| **Vtiger** | Cloud CRM + open-source Community | Yes | MPL-derived (Community); Proprietary (Cloud) | REST | Basic auth + access key, Session-based | Community Edition (OSS, self-hosted) |
| **Zoho CRM** | Cloud CRM (SaaS) | No | Proprietary | REST | OAuth 2.0 | Free (3 users, 5K API calls/day) |

## Tier Assessment

### Tier 1 — Full Feature Coverage — entity, field, layout, and relationship CRUD via API

- **Bitrix24** — Free: Free (unlimited users, 5GB, but NO REST API access since Jan 2021) | Min: $49/user/mo
- **EspoCRM** — Free: Free (self-hosted, unlimited) | Min: $15/user/mo | Admin API: $0/user/mo
- **Microsoft Dynamics 365** — Free: Power Apps Developer Plan (Dataverse only); 30-day Dynamics trial | Min: $65/user/mo
- **Odoo** — Free: Community Edition (fully free, self-hosted, complete API) | Min: $25/user/mo | Admin API: $0/user/mo
- **Salesforce** — Free: Developer Edition (2 users, 5MB data, 15K API calls/day) | Min: $25/user/mo | Admin API: $165/user/mo

### Tier 2 — Strong but Gaps — most capabilities via API, missing layout or entity creation

- **ActiveCampaign** — Free: Developer sandbox (100 contacts, 2-year expiry) | Min: $19/user/mo | Admin API: $159/user/mo
- **Attio** — Free: Free (3 seats, 50K records, 3 custom objects) | Min: $29/user/mo
- **CiviCRM** — Free: Fully free and open-source (AGPL v3) | Min: $0/user/mo
- **Copper** — Free: 14-day trial | Min: $9/user/mo | Admin API: $119/user/mo
- **HubSpot** — Free: Free CRM (1M contacts, 2 users) | Min: $20/user/mo | Admin API: $150/user/mo
- **Monday.com CRM** — Free: 14-day trial | Min: $12/user/mo | Admin API: $na/user/mo
- **SugarCRM** — Min: $49/user/mo
- **Twenty** — Free: Self-hosted: free; Cloud Pro: $9/user/mo | Min: $9/user/mo | Admin API: $0/user/mo
- **Zoho CRM** — Free: Free (3 users, 5K API calls/day) | Min: $14/user/mo | Admin API: $40/user/mo

### Tier 3 — Fields Only — custom field creation via API, no entity/layout/relationship

- **Monica** — Free: Hosted: 10 contacts; Self-hosted: unlimited, free | Min: $9/user/mo | Admin API: $0/user/mo
- **Nimble** — Free: 14-day trial (5 licenses) | Min: $25/user/mo
- **Pipedrive** — Free: 14-day trial | Min: $14/user/mo

### Tier 4 — Data API Only — record CRUD only, no schema management

- **Agile CRM** — Free: Free (10 users, 50K contacts, 1 workflow) | Min: $9/user/mo
- **Bigin (by Zoho)** — Free: Free (1 user, 5K API credits/day) | Min: $7/user/mo | Admin API: $na/user/mo
- **Creatio** — Free: 14-day trial | Min: $40/user/mo
- **Freshsales (Freshworks CRM)** — Free: Free (3 users, 1K contacts) | Min: $9/user/mo | Admin API: $na/user/mo
- **Insightly** — Free: None (removed Oct 2024) | Min: $29/user/mo | Admin API: $na/user/mo
- **Salesmate** — Free: 15-day trial | Min: $23/user/mo
- **SuiteCRM** — Free: Fully free and open-source | Min: $0/user/mo | Admin API: $na/user/mo
- **Vtiger** — Free: Community Edition (OSS, self-hosted) | Min: $15/user/mo | Admin API: $na/user/mo

## Core Capability Matrix

| Capability | **ActiveCampaign** | **Agile CRM** | **Attio** | **Bigin (by Zoho)** | **Bitrix24** | **CiviCRM** | **Copper** | **Creatio** | **EspoCRM** | **Freshsales (Freshworks CRM)** | **HubSpot** | **Insightly** | **Microsoft Dynamics 365** | **Monday.com CRM** | **Monica** | **Nimble** | **Odoo** | **Pipedrive** | **Salesforce** | **Salesmate** | **SugarCRM** | **SuiteCRM** | **Twenty** | **Vtiger** | **Zoho CRM** |
|------------|------------------|-------------|---------|-------------------|------------|-----------|----------|-----------|-----------|-------------------------------|-----------|-------------|--------------------------|------------------|----------|----------|--------|-------------|--------------|-------------|------------|------------|----------|----------|------------|
| Create Entity | Partial | None | Full | None | Full | Partial | None | Indirect | Full | None | Full | None | Full | Partial | None | None | Full | None | Full | None | Indirect | None | Full | None | None |
| Delete Entity | Full | N/A | None | N/A | Full | Partial | None | Indirect | Full | None | Full | None | Full | Partial | N/A | N/A | Full | N/A | Full | N/A | Indirect | None | Full | None | None |
| Create Field | Full | None | Full | None | Full | Full | Full | Indirect | Full | — | Full | None | Full | Full | Partial | Full | Full | Full | Full | None | Full | None | Full | None | Full |
| Update Field | Full | — | Full | — | Full | Full | — | — | Full | — | Full | — | Full | — | — | — | Full | Full | Full | — | Full | — | Full | — | Full |
| Read Layout | None | None | Partial | Read-only | Full | Partial | None | Indirect | Full | None | None | None | Full | None | None | None | Full | None | Full | None | Read-only | None | Partial | None | Read-only |
| Write Layout | None | None | None | None | Full | Partial | None | Indirect | Full | None | None | None | Full | None | None | None | Full | None | Full | None | Indirect | None | None | None | None |
| Create Relationship | None | None | Full | Partial | Full | Full | Partial | Indirect | Full | None | Full | None | Full | Partial | Read-only | None | Full | None | Full | Partial | Full | None | Full | None | Partial |
| Create Record | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full |
| Search by Email | Full | Full | Full | — | — | Full | — | — | Full | — | Full | — | Full | — | — | Full | Full | — | Full | — | Full | — | — | — | Full |
| Batch/Bulk Import | Partial | None | None | Full | Full | Full | — | — | — | — | Full | — | Full | — | None | None | Full | — | Full | — | Full | — | Full | — | Full |

## Layout Management Detail

| Capability | **ActiveCampaign** | **Agile CRM** | **Attio** | **Bigin (by Zoho)** | **Bitrix24** | **CiviCRM** | **Copper** | **Creatio** | **EspoCRM** | **Freshsales (Freshworks CRM)** | **HubSpot** | **Insightly** | **Microsoft Dynamics 365** | **Monday.com CRM** | **Monica** | **Nimble** | **Odoo** | **Pipedrive** | **Salesforce** | **Salesmate** | **SugarCRM** | **SuiteCRM** | **Twenty** | **Vtiger** | **Zoho CRM** |
|------------|------------------|-------------|---------|-------------------|------------|-----------|----------|-----------|-----------|-------------------------------|-----------|-------------|--------------------------|------------------|----------|----------|--------|-------------|--------------|-------------|------------|------------|----------|----------|------------|
| Read Layouts | None | None | Partial | Read-only | Full | Partial | None | Indirect | Full | None | None | None | Full | None | None | None | Full | None | Full | None | Read-only | None | Partial | None | Read-only |
| Write Layouts | None | None | None | None | Full | Partial | None | Indirect | Full | None | None | None | Full | None | None | None | Full | None | Full | None | Indirect | None | None | None | None |
| Detail View | No | — | No | — | — | Yes | — | — | Yes | — | No | — | Yes | — | — | — | Yes | — | Yes | — | Yes | — | No | — | No |
| Edit View | No | — | No | — | — | Yes | — | — | Yes | — | No | — | Yes | — | — | — | Yes | — | Yes | — | Yes | — | No | — | No |
| List View | No | — | No | — | — | Yes | — | — | Yes | — | No | — | Yes | — | — | — | Yes | — | Yes | — | Yes | — | No | — | No |
| Panels/Sections | No | — | No | — | — | Yes | — | — | Yes | — | No | — | Yes | — | — | — | Yes | — | Yes | — | Yes | — | No | — | No |
| Tabs | No | — | No | — | — | Yes | — | — | Yes | — | No | — | Yes | — | — | — | Yes | — | Yes | — | No | — | No | — | No |
| Conditional Visibility | No | — | No | — | — | Yes | No | — | Yes | — | No | — | Yes | No | — | — | Yes | — | Yes | — | Yes | — | No | — | No |

## Relationship Management Detail

| Capability | **ActiveCampaign** | **Agile CRM** | **Attio** | **Bigin (by Zoho)** | **Bitrix24** | **CiviCRM** | **Copper** | **Creatio** | **EspoCRM** | **Freshsales (Freshworks CRM)** | **HubSpot** | **Insightly** | **Microsoft Dynamics 365** | **Monday.com CRM** | **Monica** | **Nimble** | **Odoo** | **Pipedrive** | **Salesforce** | **Salesmate** | **SugarCRM** | **SuiteCRM** | **Twenty** | **Vtiger** | **Zoho CRM** |
|------------|------------------|-------------|---------|-------------------|------------|-----------|----------|-----------|-----------|-------------------------------|-----------|-------------|--------------------------|------------------|----------|----------|--------|-------------|--------------|-------------|------------|------------|----------|----------|------------|
| Create Relationship | None | None | Full | Partial | Full | Full | Partial | Indirect | Full | None | Full | None | Full | Partial | Read-only | None | Full | None | Full | Partial | Full | None | Full | None | Partial |
| One-to-Many | No | — | Yes | — | Yes | Yes | — | — | Yes | — | Yes | — | Yes | — | — | — | Yes | — | Yes | — | Yes | — | Yes | — | Yes |
| Many-to-Many | No | — | Yes | — | Yes | Yes | — | — | Yes | — | Yes | — | Yes | — | — | — | Yes | — | Yes | — | Yes | — | No | — | Yes |
| Link Labels | No | — | Yes | — | — | Yes | — | — | Yes | — | Yes | — | Yes | — | — | — | Yes | — | Yes | — | Yes | — | Yes | — | No |
| Audit Both Sides | No | — | No | — | — | No | — | — | Yes | — | No | — | Yes | — | — | — | Yes | — | Yes | — | Yes | — | — | — | No |
| Cascade Delete | No | — | No | — | — | No | — | — | — | — | No | — | Yes | — | — | — | Yes | — | Yes | — | No | — | — | — | No |
| Polymorphic | No | — | No | — | — | No | — | — | — | — | — | — | Yes | — | — | — | Yes | — | Yes | — | — | — | Yes | — | — |

## Future Capabilities

| Capability | **ActiveCampaign** | **Agile CRM** | **Attio** | **Bigin (by Zoho)** | **Bitrix24** | **CiviCRM** | **Copper** | **Creatio** | **EspoCRM** | **Freshsales (Freshworks CRM)** | **HubSpot** | **Insightly** | **Microsoft Dynamics 365** | **Monday.com CRM** | **Monica** | **Nimble** | **Odoo** | **Pipedrive** | **Salesforce** | **Salesmate** | **SugarCRM** | **SuiteCRM** | **Twenty** | **Vtiger** | **Zoho CRM** |
|------------|------------------|-------------|---------|-------------------|------------|-----------|----------|-----------|-----------|-------------------------------|-----------|-------------|--------------------------|------------------|----------|----------|--------|-------------|--------------|-------------|------------|------------|----------|----------|------------|
| Workflow Rules | Read-only | None | None | None | Full | Partial | None | Partial | — | — | None | None | Full | None | None | None | Full | None | Full | None | None | None | None | None | Read-only |
| Flows/Automation | None | — | None | None | Full | Indirect | — | None | — | — | None | — | Full | — | None | None | — | None | Full | None | Partial | — | None | — | None |
| Approval Processes | None | — | None | — | — | None | — | — | — | — | None | — | Full | — | — | — | Indirect | — | Full | — | Partial | — | — | — | Partial |
| Create Roles | None | None | None | Read-only | Partial | Partial | None | Partial | — | — | None | None | Full | None | None | None | Full | None | Full | None | Full | None | Partial | None | Read-only |
| Field-Level Security | None | — | None | — | — | Partial | — | — | — | — | None | — | Full | — | — | — | Full | — | Full | — | Full | — | — | — | None |
| Dashboards | None | None | None | None | Partial | Partial | None | Partial | — | — | None | None | Full | None | None | None | Full | None | Full | None | Partial | None | None | None | None |
| Reports | None | — | None | — | — | Full | — | — | — | — | None | — | Full | — | — | — | Full | — | Full | — | Partial | — | — | — | Partial |
| Email Templates | None | None | None | None | Partial | Full | None | Partial | — | — | None | None | Full | None | None | None | Full | None | Full | None | Full | None | None | — | Read-only |
| Webhooks | Full | Partial | Full | Partial | Full | Indirect | None | Partial | — | — | None | None | Full | Partial | None | None | Full | Full | Indirect | Partial | Indirect | None | Full | — | None |
| Event Subscriptions | Full | — | Full | — | — | Indirect | — | Partial | — | — | Partial | — | Full | — | — | — | Full | Full | Full | — | Indirect | — | Full | — | Partial |

## Pricing Summary

| Platform | Free Tier | Min Paid | Full Admin API | Enterprise |
|----------|-----------|----------|---------------|-----------|
| **ActiveCampaign** | Developer sandbox (100 contacts, 2-year expiry) | $19/user/mo | $159/user/mo | $159/user/mo |
| **Agile CRM** | Free (10 users, 50K contacts, 1 workflow) | $9/user/mo | $9/user/mo | $48/user/mo |
| **Attio** | Free (3 seats, 50K records, 3 custom objects) | $29/user/mo | $29/user/mo | $100/user/mo |
| **Bigin (by Zoho)** | Free (1 user, 5K API credits/day) | $7/user/mo | $na/user/mo | $18/user/mo |
| **Bitrix24** | Free (unlimited users, 5GB, but NO REST API access since Jan 2021) | $49/user/mo | $49/user/mo | $350/user/mo |
| **CiviCRM** | Fully free and open-source (AGPL v3) | — | $0/user/mo | — |
| **Copper** | 14-day trial | $9/user/mo | $119/user/mo | $119/user/mo |
| **Creatio** | 14-day trial | $40/user/mo | $40/user/mo | $70/user/mo |
| **EspoCRM** | Free (self-hosted, unlimited) | $15/user/mo | $0/user/mo | — |
| **Freshsales (Freshworks CRM)** | Free (3 users, 1K contacts) | $9/user/mo | $na/user/mo | $59/user/mo |
| **HubSpot** | Free CRM (1M contacts, 2 users) | $20/user/mo | $150/user/mo | $150/user/mo |
| **Insightly** | None (removed Oct 2024) | $29/user/mo | $na/user/mo | $99/user/mo |
| **Microsoft Dynamics 365** | Power Apps Developer Plan (Dataverse only); 30-day Dynamics trial | $65/user/mo | $65/user/mo | $150/user/mo |
| **Monday.com CRM** | 14-day trial | $12/user/mo | $na/user/mo | $Contact sales/user/mo |
| **Monica** | Hosted: 10 contacts; Self-hosted: unlimited, free | $9/user/mo | $0/user/mo | $9/user/mo |
| **Nimble** | 14-day trial (5 licenses) | $25/user/mo | $25/user/mo | $25/user/mo |
| **Odoo** | Community Edition (fully free, self-hosted, complete API) | $25/user/mo | $0/user/mo | $47/user/mo |
| **Pipedrive** | 14-day trial | $14/user/mo | $14/user/mo | $99/user/mo |
| **Salesforce** | Developer Edition (2 users, 5MB data, 15K API calls/day) | $25/user/mo | $165/user/mo | $330/user/mo |
| **Salesmate** | 15-day trial | $23/user/mo | $23/user/mo | $63/user/mo |
| **SugarCRM** | None | $49/user/mo | $49/user/mo | $85/user/mo |
| **SuiteCRM** | Fully free and open-source | — | $na/user/mo | — |
| **Twenty** | Self-hosted: free; Cloud Pro: $9/user/mo | $9/user/mo | $0/user/mo | $19/user/mo |
| **Vtiger** | Community Edition (OSS, self-hosted) | $15/user/mo | $na/user/mo | $58/user/mo |
| **Zoho CRM** | Free (3 users, 5K API calls/day) | $14/user/mo | $40/user/mo | $52/user/mo |

---

*Generated 2026-03-30 from 25 platform profiles by `tools/crm_compare.py`*
