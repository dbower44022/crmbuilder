# CRM Platform API Capability Inventory

> **Generated:** 2026-03-30 by `crm_compare.py inventory`
> **Platforms:** 18
> **Source data:** `docs/crm-platforms/platforms/*.yaml`

---

## Platform Overview

| Platform | Type | API Protocol | Auth | Free/Dev Tier |
|----------|------|-------------|------|--------------|
| **ActiveCampaign** | Marketing Automation + CRM (SaaS) | REST | API key (Api-Token header) | Developer sandbox (100 contacts, 2-year expiry) |
| **Attio** | Cloud CRM (SaaS) | REST | Bearer token, OAuth 2.0, HTTP Basic | Free (3 seats, 50K records, 3 custom objects) |
| **CiviCRM** | Open-source nonprofit CRM (AGPL v3) | REST, PHP, CLI, AJAX | API Key (Bearer), JWT, Basic Auth (disabled by default) | Fully free and open-source (AGPL v3) |
| **Copper** | Cloud CRM (SaaS) | REST | API key + email headers | 14-day trial |
| **Creatio** | Low-code CRM platform | OData 3/4, DataService JSON-RPC | Forms auth, Basic auth, OAuth 2.0 | 14-day trial |
| **EspoCRM** | Open-source CRM (GPL v3) | REST | API Key, HMAC, Basic Auth | Free (self-hosted, unlimited) |
| **Freshsales (Freshworks CRM)** | Cloud CRM (SaaS) | REST | API key | Free (3 users, 1K contacts) |
| **HubSpot** | Cloud CRM (SaaS) | REST | OAuth 2.0, Private App tokens | Free CRM (1M contacts, 2 users) |
| **Insightly** | Cloud CRM (SaaS) | REST | Basic auth (API key) | None (removed Oct 2024) |
| **Microsoft Dynamics 365** | Cloud/On-premise CRM | OData v4 REST, FetchXML | OAuth 2.0 via Microsoft Entra ID (Azure AD) | Power Apps Developer Plan (Dataverse only); 30-day Dynamics trial |
| **Monday.com CRM** | Work OS with CRM product | GraphQL | API tokens | 14-day trial |
| **Odoo** | Open-source ERP/CRM (LGPL) | XML-RPC, JSON-RPC, REST API (Enterprise 17+) | Database + username + password/API key, OAuth 2.0 (Enterprise REST) | Community Edition (fully free, self-hosted, complete API) |
| **Pipedrive** | Cloud CRM (SaaS) | REST | OAuth 2.0, API tokens | 14-day trial |
| **Salesforce** | Cloud CRM (SaaS) | REST, SOAP, Metadata API, Tooling API, Bulk API | OAuth 2.0 | Developer Edition (2 users, 5MB data, 15K API calls/day) |
| **SugarCRM** | Commercial CRM (cloud + on-premise) | REST | OAuth 2.0 | None |
| **SuiteCRM** | Open-source CRM (AGPL v3) | REST, SOAP | OAuth 2.0 | Fully free and open-source |
| **Vtiger** | Cloud CRM + open-source Community | REST | Basic auth + access key, Session-based | Community Edition (OSS, self-hosted) |
| **Zoho CRM** | Cloud CRM (SaaS) | REST | OAuth 2.0 | Free (3 users, 5K API calls/day) |

## Tier Assessment

### Tier 1 — Full Feature Coverage — entity, field, layout, and relationship CRUD via API

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
- **Zoho CRM** — Free: Free (3 users, 5K API calls/day) | Min: $14/user/mo | Admin API: $40/user/mo

### Tier 3 — Fields Only — custom field creation via API, no entity/layout/relationship

- **Pipedrive** — Free: 14-day trial | Min: $14/user/mo

### Tier 4 — Data API Only — record CRUD only, no schema management

- **Creatio** — Free: 14-day trial | Min: $40/user/mo
- **Freshsales (Freshworks CRM)** — Free: Free (3 users, 1K contacts) | Min: $9/user/mo | Admin API: $na/user/mo
- **Insightly** — Free: None (removed Oct 2024) | Min: $29/user/mo | Admin API: $na/user/mo
- **SuiteCRM** — Free: Fully free and open-source | Min: $0/user/mo | Admin API: $na/user/mo
- **Vtiger** — Free: Community Edition (OSS, self-hosted) | Min: $15/user/mo | Admin API: $na/user/mo

## Core Capability Matrix

| Capability | **ActiveCampaign** | **Attio** | **CiviCRM** | **Copper** | **Creatio** | **EspoCRM** | **Freshsales (Freshworks CRM)** | **HubSpot** | **Insightly** | **Microsoft Dynamics 365** | **Monday.com CRM** | **Odoo** | **Pipedrive** | **Salesforce** | **SugarCRM** | **SuiteCRM** | **Vtiger** | **Zoho CRM** |
|------------|------------------|---------|-----------|----------|-----------|-----------|-------------------------------|-----------|-------------|--------------------------|------------------|--------|-------------|--------------|------------|------------|----------|------------|
| Create Entity | Partial | Full | Partial | None | Indirect | Full | None | Full | None | Full | Partial | Full | None | Full | Indirect | None | None | None |
| Delete Entity | Full | None | Partial | None | Indirect | Full | None | Full | None | Full | Partial | Full | N/A | Full | Indirect | None | None | None |
| Create Field | Full | Full | Full | Full | Indirect | Full | — | Full | None | Full | Full | Full | Full | Full | Full | None | None | Full |
| Update Field | Full | Full | Full | — | — | Full | — | Full | — | Full | — | Full | Full | Full | Full | — | — | Full |
| Read Layout | None | Partial | Partial | None | Indirect | Full | None | None | None | Full | None | Full | None | Full | Read-only | None | None | Read-only |
| Write Layout | None | None | Partial | None | Indirect | Full | None | None | None | Full | None | Full | None | Full | Indirect | None | None | None |
| Create Relationship | None | Full | Full | Partial | Indirect | Full | None | Full | None | Full | Partial | Full | None | Full | Full | None | None | Partial |
| Create Record | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full | Full |
| Search by Email | Full | Full | Full | — | — | Full | — | Full | — | Full | — | Full | — | Full | Full | — | — | Full |
| Batch/Bulk Import | Partial | None | Full | — | — | — | — | Full | — | Full | — | Full | — | Full | Full | — | — | Full |

## Layout Management Detail

| Capability | **ActiveCampaign** | **Attio** | **CiviCRM** | **Copper** | **Creatio** | **EspoCRM** | **Freshsales (Freshworks CRM)** | **HubSpot** | **Insightly** | **Microsoft Dynamics 365** | **Monday.com CRM** | **Odoo** | **Pipedrive** | **Salesforce** | **SugarCRM** | **SuiteCRM** | **Vtiger** | **Zoho CRM** |
|------------|------------------|---------|-----------|----------|-----------|-----------|-------------------------------|-----------|-------------|--------------------------|------------------|--------|-------------|--------------|------------|------------|----------|------------|
| Read Layouts | None | Partial | Partial | None | Indirect | Full | None | None | None | Full | None | Full | None | Full | Read-only | None | None | Read-only |
| Write Layouts | None | None | Partial | None | Indirect | Full | None | None | None | Full | None | Full | None | Full | Indirect | None | None | None |
| Detail View | No | No | Yes | — | — | Yes | — | No | — | Yes | — | Yes | — | Yes | Yes | — | — | No |
| Edit View | No | No | Yes | — | — | Yes | — | No | — | Yes | — | Yes | — | Yes | Yes | — | — | No |
| List View | No | No | Yes | — | — | Yes | — | No | — | Yes | — | Yes | — | Yes | Yes | — | — | No |
| Panels/Sections | No | No | Yes | — | — | Yes | — | No | — | Yes | — | Yes | — | Yes | Yes | — | — | No |
| Tabs | No | No | Yes | — | — | Yes | — | No | — | Yes | — | Yes | — | Yes | No | — | — | No |
| Conditional Visibility | No | No | Yes | — | — | Yes | — | No | — | Yes | — | Yes | — | Yes | Yes | — | — | No |

## Relationship Management Detail

| Capability | **ActiveCampaign** | **Attio** | **CiviCRM** | **Copper** | **Creatio** | **EspoCRM** | **Freshsales (Freshworks CRM)** | **HubSpot** | **Insightly** | **Microsoft Dynamics 365** | **Monday.com CRM** | **Odoo** | **Pipedrive** | **Salesforce** | **SugarCRM** | **SuiteCRM** | **Vtiger** | **Zoho CRM** |
|------------|------------------|---------|-----------|----------|-----------|-----------|-------------------------------|-----------|-------------|--------------------------|------------------|--------|-------------|--------------|------------|------------|----------|------------|
| Create Relationship | None | Full | Full | Partial | Indirect | Full | None | Full | None | Full | Partial | Full | None | Full | Full | None | None | Partial |
| One-to-Many | No | Yes | Yes | — | — | Yes | — | Yes | — | Yes | — | Yes | — | Yes | Yes | — | — | Yes |
| Many-to-Many | No | Yes | Yes | — | — | Yes | — | Yes | — | Yes | — | Yes | — | Yes | Yes | — | — | Yes |
| Link Labels | No | Yes | Yes | — | — | Yes | — | Yes | — | Yes | — | Yes | — | Yes | Yes | — | — | No |
| Audit Both Sides | No | No | No | — | — | Yes | — | No | — | Yes | — | Yes | — | Yes | Yes | — | — | No |
| Cascade Delete | No | No | No | — | — | — | — | No | — | Yes | — | Yes | — | Yes | No | — | — | No |
| Polymorphic | No | No | No | — | — | — | — | — | — | Yes | — | Yes | — | Yes | — | — | — | — |

## Future Capabilities

| Capability | **ActiveCampaign** | **Attio** | **CiviCRM** | **Copper** | **Creatio** | **EspoCRM** | **Freshsales (Freshworks CRM)** | **HubSpot** | **Insightly** | **Microsoft Dynamics 365** | **Monday.com CRM** | **Odoo** | **Pipedrive** | **Salesforce** | **SugarCRM** | **SuiteCRM** | **Vtiger** | **Zoho CRM** |
|------------|------------------|---------|-----------|----------|-----------|-----------|-------------------------------|-----------|-------------|--------------------------|------------------|--------|-------------|--------------|------------|------------|----------|------------|
| Workflow Rules | Read-only | None | Partial | None | Partial | — | — | None | None | Full | None | Full | None | Full | None | None | None | Read-only |
| Flows/Automation | None | None | Indirect | — | None | — | — | None | — | Full | — | — | None | Full | Partial | — | — | None |
| Approval Processes | None | None | None | — | — | — | — | None | — | Full | — | Indirect | — | Full | Partial | — | — | Partial |
| Create Roles | None | None | Partial | None | Partial | — | — | None | None | Full | None | Full | None | Full | Full | None | None | Read-only |
| Field-Level Security | None | None | Partial | — | — | — | — | None | — | Full | — | Full | — | Full | Full | — | — | None |
| Dashboards | None | None | Partial | None | Partial | — | — | None | None | Full | None | Full | None | Full | Partial | None | None | None |
| Reports | None | None | Full | — | — | — | — | None | — | Full | — | Full | — | Full | Partial | — | — | Partial |
| Email Templates | None | None | Full | None | Partial | — | — | None | None | Full | None | Full | None | Full | Full | None | — | Read-only |
| Webhooks | Full | Full | Indirect | None | Partial | — | — | None | None | Full | Partial | Full | Full | Indirect | Indirect | None | — | None |
| Event Subscriptions | Full | Full | Indirect | — | Partial | — | — | Partial | — | Full | — | Full | Full | Full | Indirect | — | — | Partial |

## Pricing Summary

| Platform | Free Tier | Min Paid | Full Admin API | Enterprise |
|----------|-----------|----------|---------------|-----------|
| **ActiveCampaign** | Developer sandbox (100 contacts, 2-year expiry) | $19/user/mo | $159/user/mo | $159/user/mo |
| **Attio** | Free (3 seats, 50K records, 3 custom objects) | $29/user/mo | $29/user/mo | $100/user/mo |
| **CiviCRM** | Fully free and open-source (AGPL v3) | — | $0/user/mo | — |
| **Copper** | 14-day trial | $9/user/mo | $119/user/mo | $119/user/mo |
| **Creatio** | 14-day trial | $40/user/mo | $40/user/mo | $70/user/mo |
| **EspoCRM** | Free (self-hosted, unlimited) | $15/user/mo | $0/user/mo | — |
| **Freshsales (Freshworks CRM)** | Free (3 users, 1K contacts) | $9/user/mo | $na/user/mo | $59/user/mo |
| **HubSpot** | Free CRM (1M contacts, 2 users) | $20/user/mo | $150/user/mo | $150/user/mo |
| **Insightly** | None (removed Oct 2024) | $29/user/mo | $na/user/mo | $99/user/mo |
| **Microsoft Dynamics 365** | Power Apps Developer Plan (Dataverse only); 30-day Dynamics trial | $65/user/mo | $65/user/mo | $150/user/mo |
| **Monday.com CRM** | 14-day trial | $12/user/mo | $na/user/mo | $Contact sales/user/mo |
| **Odoo** | Community Edition (fully free, self-hosted, complete API) | $25/user/mo | $0/user/mo | $47/user/mo |
| **Pipedrive** | 14-day trial | $14/user/mo | $14/user/mo | $99/user/mo |
| **Salesforce** | Developer Edition (2 users, 5MB data, 15K API calls/day) | $25/user/mo | $165/user/mo | $330/user/mo |
| **SugarCRM** | None | $49/user/mo | $49/user/mo | $85/user/mo |
| **SuiteCRM** | Fully free and open-source | — | $na/user/mo | — |
| **Vtiger** | Community Edition (OSS, self-hosted) | $15/user/mo | $na/user/mo | $58/user/mo |
| **Zoho CRM** | Free (3 users, 5K API calls/day) | $14/user/mo | $40/user/mo | $52/user/mo |

---

*Generated 2026-03-30 from 18 platform profiles by `tools/crm_compare.py`*
