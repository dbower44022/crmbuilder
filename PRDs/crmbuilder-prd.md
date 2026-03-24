# CRM Builder — Product Requirements Document

**Version:** 3.0  
**Status:** Current  
**Last Updated:** March 2026

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 3.0 | March 2026 | Expanded vision — CRM-agnostic requirements, AI-assisted design, CRM selection engine |
| 2.0 | March 2026 | Generalized from CBM-specific to multi-client tool |
| 1.0 | Early 2026 | Initial release — EspoCRM field deployment |

---

## 1. Product Vision

CRM Builder is a tool for designing, selecting, and implementing CRM
configurations for any organization. It guides users through a structured
requirements process, recommends the best CRM platform for their needs,
and deploys the resulting configuration automatically.

The workflow is:

```
Phase 1 — Discovery
  AI-assisted interview to understand the organization,
  its processes, and its data requirements
       ↓
  Entity Map — which entities are needed and why
       ↓
Phase 2 — Entity Definition
  Detailed AI-assisted interview for each entity —
  fields, layouts, relationships, and business rules
       ↓
  PRD Document + YAML Program Files (always in sync)
       ↓
Phase 3 — CRM Selection
  Requirements scored against available CRM platforms
  Best-fit recommendation with justification
       ↓
Phase 4 — Implementation
  CRM-specific deployment artifacts generated from requirements
  YAML for EspoCRM, configuration scripts for other platforms
       ↓
Phase 5 — Deploy & Verify
  CRM Builder deploys the configuration and verifies the result
```

### 1.1 Core Principles

**Requirements first.** The organization's needs are defined before any
platform is chosen. Requirements are expressed in business terms, not
CRM-specific terms.

**PRD and YAML are always in sync.** Every change to requirements updates
both the human-readable PRD and the machine-readable YAML simultaneously.
Neither document is edited independently.

**CRM-agnostic design.** The discovery and entity definition phases produce
platform-independent requirements. The implementation phase translates those
requirements into platform-specific artifacts.

**Declarative and idempotent.** Configuration is described as desired end
state. Deploying the same configuration multiple times produces the same
result.

**Verifiable.** Every deployed configuration can be re-checked against the
specification at any time.

### 1.2 Target Users

- **Implementation consultants** — organizations helping clients select and
  implement CRM systems
- **Technical administrators** — IT staff responsible for CRM configuration
  and maintenance
- **Nonprofit technology teams** — small teams building CRM infrastructure
  without dedicated CRM specialists

Users should be comfortable with structured processes but do not need deep
CRM technical knowledge. The AI assistance is designed to guide non-experts
through the requirements process.

---

## 2. Phase 1 — Discovery Interview

### 2.1 Purpose

Understand the organization well enough to propose an entity map — the set
of entities that should be tracked in the CRM and why.

### 2.2 Interview Scope

The discovery interview covers:

- **Organization type** — nonprofit, business, association, etc.
- **Core mission** — what the organization does and for whom
- **People tracked** — volunteers, clients, donors, members, staff, contacts
- **Activities tracked** — sessions, events, cases, transactions, communications
- **Relationships** — who works with whom, what belongs to what
- **Reporting needs** — what questions must the CRM answer
- **Process automation** — what workflows need to be managed
- **Integration needs** — what other systems must connect

### 2.3 Output — Entity Map

A structured document proposing:
- Each recommended entity with business justification
- Whether each entity is a new custom entity or an extension of a native CRM entity
- Relationships between entities
- Entities explicitly excluded with reasoning

The user reviews and approves the entity map before Phase 2 begins.

### 2.4 Native Entity Awareness

The discovery interview is aware of native entities in supported CRM
platforms. For EspoCRM, this includes Account, Contact, Lead, Opportunity,
Case, Task, Meeting, Call, Email, and Document. The AI recommends extending
native entities where appropriate rather than creating custom entities
unnecessarily.

---

## 3. Phase 2 — Entity Definition

### 3.1 Purpose

Define each entity in enough detail to produce a complete PRD section and
YAML program file. One entity definition session per entity.

### 3.2 Interview Scope

For each entity, the interview covers:

**Identity:**
- Entity name, singular and plural labels
- Entity type (Base, Person, Company, Event)
- Business description and purpose

**Fields:**
- Each field with display label, data type, and business purpose
- Required vs. optional
- Allowed values for dropdowns (enum/multi-select)
- Default values

**Layout:**
- How fields are grouped into panels and tabs
- Conditional visibility rules (which fields or panels show based on values)
- List view columns

**Relationships:**
- Links to other entities, direction, and cardinality
- Labels on each side of the relationship

**Business Rules:**
- Lifecycle states and transitions
- Calculated or formula fields
- Access control requirements

### 3.3 Output — PRD Section + YAML File

Each entity definition session produces:
- A PRD section (Word document) describing the entity in human-readable form
- A YAML program file ready for deployment via CRM Builder

Both are produced simultaneously and remain in sync. Changes made via AI
update both documents together.

---

## 4. Phase 3 — CRM Selection

### 4.1 Purpose

Score the organization's requirements against available CRM platforms and
recommend the best fit.

### 4.2 Evaluation Criteria

Requirements are evaluated against each platform across:

- **Data model fit** — how well the platform's native entities match requirements
- **Customization capability** — ability to add custom entities and fields
- **Ease of configuration** — technical complexity of implementation
- **Hosting model** — cloud, self-hosted, or hybrid
- **Cost** — licensing, hosting, and implementation cost
- **Nonprofit suitability** — available discounts, nonprofit-specific features
- **Integration ecosystem** — available connectors and APIs
- **User experience** — ease of use for non-technical staff

### 4.3 Supported Platforms (Current)

| Platform | Status |
|---|---|
| EspoCRM | Fully supported |
| Others | Planned — Salesforce, HubSpot, CiviCRM |

### 4.4 Output — CRM Selection Report

A structured recommendation document covering:
- Requirements summary
- Platform scores by category
- Recommended platform with justification
- Known gaps or limitations
- Implementation effort estimate

---

## 5. Phase 4 — Implementation Artifacts

### 5.1 Purpose

Translate the platform-independent requirements into deployment artifacts
for the selected CRM.

### 5.2 EspoCRM Artifacts

For EspoCRM, the implementation artifacts are YAML program files as defined
in the current YAML specification. These are deployed via the CRM Builder
desktop application.

### 5.3 Future Platform Artifacts

For future platforms, implementation artifacts will be platform-specific.
The artifact format is an implementation detail — the requirements definition
(PRD) remains the same regardless of platform.

---

## 6. Phase 5 — Deploy & Verify (Current Capability)

The CRM Builder desktop application handles deployment and verification.
See Section 8 for current capabilities.

---

## 7. PRD and YAML Synchronization

### 7.1 The Synchronization Problem

PRDs and YAML files are two representations of the same information:
- PRD — human-readable, for stakeholders and reviewers
- YAML — machine-readable, for the deployment tool

Without active synchronization, they drift apart as requirements evolve.

### 7.2 The Synchronization Model

Changes to requirements are always made through AI-assisted conversation.
The AI updates both documents simultaneously. Direct editing of either
document outside the AI conversation is discouraged.

The recommended workflow for changes:

```
User describes change in natural language
       ↓
AI proposes updated PRD section
       ↓
User reviews and approves
       ↓
AI updates PRD document and YAML file simultaneously
       ↓
User commits both files to version control
```

### 7.3 Version Control

Both PRD and YAML files are stored in the client repository under version
control. The git commit history serves as the change log for requirements
evolution.

YAML files use `content_version` (semantic versioning) to track the
significance of each change:
- PATCH — descriptions, comments, minor corrections
- MINOR — new fields or values added
- MAJOR — fields removed, types changed, entity restructured

---

## 8. Current Implementation Capabilities (EspoCRM)

The CRM Builder desktop application currently supports:

### 8.1 Instance Management
- Add, edit, delete EspoCRM instance profiles
- Each instance bound to a project folder
- Three authentication methods: API Key, HMAC, Basic

### 8.2 Entity Management
- Create and delete custom entities (Base, Person, Company, Event)
- Delete-and-recreate for clean deployments

### 8.3 Field Management
- Create and update custom fields
- Supported types: varchar, text, wysiwyg, enum, multiEnum, bool,
  int, float, date, datetime, currency, url, email, phone
- Verify fields after deployment

### 8.4 Layout Management
- Detail view layouts (panels, tabs, rows)
- List view column definitions
- Category-based tab auto-population
- Dynamic Logic panel visibility conditions

### 8.5 Relationship Management
- One-to-many, many-to-one, many-to-many relationships
- Idempotent — checks before creating
- Handles EspoCRM c-prefix conventions automatically

### 8.6 Documentation Generation
- Reference manual (Markdown + Word) from YAML files
- Output to project folder's Implementation Docs/ directory

### 8.7 Reporting
- .log and .json reports after every Run and Verify
- Reports written to project folder's reports/ directory

---

## 9. Project Folder Structure

Each client instance is bound to a project folder:

```
ClientProjectFolder/
├── PRDs/                    ← PRD documents (Word)
├── programs/                ← YAML program files
├── Implementation Docs/     ← generated reference manual
└── reports/                 ← deployment run reports
```

---

## 10. Repository Architecture

```
crmbuilder/                  ← tool repo (this repo)
  ├── espo_impl/             ← desktop app source code
  ├── tools/                 ← utilities (doc generator, interview guides)
  ├── docs/                  ← tool documentation
  ├── PRDs/                  ← tool specs and Claude Code prompts
  └── tests/                 ← test suite

ClientRepo/                  ← client repo (separate per client)
  ├── PRDs/                  ← client PRD documents
  ├── programs/              ← YAML program files
  ├── Implementation Docs/   ← generated reference manual
  └── reports/               ← deployment reports
```

---

## 11. Planned Development Roadmap

### Near Term (EspoCRM completion)
- Dynamic Logic on individual fields
- Search presets / saved views
- Role-based access control
- Error handler improvements (full response body logging)
- content_version display in UI

### Medium Term (Requirements pipeline)
- Discovery interview guide
- Entity definition interview guide
- AI-assisted PRD generation
- AI-assisted YAML generation from PRD
- PRD/YAML synchronization workflow

### Longer Term (CRM-agnostic)
- CRM selection scoring engine
- CRM selection report generation
- Support for additional CRM platforms
- Platform-specific artifact generation

---

## 12. Technical Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Package manager | uv |
| GUI framework | PySide6 (Qt6) |
| HTTP client | requests |
| YAML parser | pyyaml |
| Document generation | python-docx, Node.js docx npm |
| Test framework | pytest |

---

## 13. Confirmed EspoCRM API Endpoints (v9.3.3)

| Operation | Method | Endpoint |
|---|---|---|
| Read field | GET | /api/v1/Metadata?key=entityDefs.{Entity}.fields.{field} |
| Create field | POST | /api/v1/Admin/fieldManager/{Entity} |
| Update field | PUT | /api/v1/Admin/fieldManager/{Entity}/{field} |
| Read entity | GET | /api/v1/Metadata?key=scopes.{Entity} |
| Create entity | POST | /api/v1/EntityManager/action/createEntity |
| Delete entity | POST | /api/v1/EntityManager/action/removeEntity |
| Rebuild cache | POST | /api/v1/Admin/rebuild |
| Read layout | GET | /api/v1/Layout/action/getOriginal?scope={Entity}&name={type} |
| Save layout | PUT | /api/v1/{Entity}/layout/{type} |
| Read link | GET | /api/v1/Metadata?key=entityDefs.{Entity}.links.{link} |
| Create relationship | POST | /api/v1/EntityManager/action/createLink |
| Delete relationship | POST | /api/v1/EntityManager/action/removeLink |
