# CRM Builder — Product Requirements Document

**Version:** 4.1
**Status:** Current
**Last Updated:** April 2026

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 4.1 | April 2026 | Added Section 9.2 — User Process Guide Generator. Sibling `process_definition` work item now produces a CRM-aware how-to document per discovered process, combining DB process records with YAML program data. |
| 4.0 | March 2026 | Restructured for new doc architecture. Added CRM Deployment phase. Separated requirements from implementation detail. |
| 3.0 | March 2026 | Expanded vision — CRM-agnostic requirements, AI-assisted design, CRM selection engine |
| 2.0 | March 2026 | Generalized from CBM-specific to multi-client tool |
| 1.0 | Early 2026 | Initial release — EspoCRM field deployment |

---

## 1. Product Vision

CRM Builder is a tool for designing, selecting, provisioning, and configuring
CRM systems for any organization. It guides users through a structured
requirements process, recommends the best CRM platform for their needs,
provisions or onboards a CRM instance, and then deploys the resulting
configuration automatically.

The intended workflow is:

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
Phase 4 — CRM Deployment
  Instance provisioned on a hosting provider OR
  SaaS credentials collected and validated
       ↓
Phase 5 — Configuration
  CRM-specific configuration deployed from YAML program files
  Fields, layouts, relationships, security applied
       ↓
Phase 6 — Verify & Maintain
  Configuration re-checked against spec at any time
  Ongoing changes made through the same workflow
```

### 1.1 Core Principles

**Requirements first.** The organization's needs are defined before any
platform is chosen. Requirements are expressed in business terms, not
CRM-specific terms.

**PRD and YAML are always in sync.** Every change to requirements updates
both the human-readable PRD and the machine-readable YAML simultaneously.
Neither document is edited independently.

**CRM-agnostic design.** Discovery and entity definition produce
platform-independent requirements. Later phases translate those requirements
into platform-specific artifacts.

**Declarative and idempotent.** Configuration is described as desired end
state. Deploying the same configuration multiple times produces the same
result.

**Verifiable.** Every deployed configuration can be re-checked against the
specification at any time.

**Preview before commit.** Every destructive or significant operation shows
the user exactly what will happen before any changes are made.

### 1.2 Target Users

- **Implementation consultants** — organizations helping clients select and
  implement CRM systems
- **Technical administrators** — IT staff responsible for CRM configuration
  and maintenance
- **Nonprofit technology teams** — small teams building CRM infrastructure
  without dedicated CRM specialists

Users should be comfortable with structured processes but do not need deep
CRM technical knowledge. AI assistance guides non-experts through the
requirements process.

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
- Allowed values for dropdowns
- Default values

**Layout:**
- How fields are grouped into panels and tabs
- Conditional visibility rules
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
- A PRD section describing the entity in human-readable form
- A YAML program file ready for deployment via CRM Builder

Both are produced simultaneously and remain in sync.

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

### 4.3 Supported Platforms

| Platform | Status |
|---|---|
| EspoCRM | Fully supported |
| Salesforce | Planned |
| HubSpot | Planned |
| CiviCRM | Planned |

### 4.4 Output — CRM Selection Report

A structured recommendation document covering:
- Requirements summary
- Platform scores by category
- Recommended platform with justification
- Known gaps or limitations
- Implementation effort estimate

---

## 5. Phase 4 — CRM Deployment

### 5.1 Purpose

Establish a working CRM instance before configuration begins. This phase
has two paths depending on the selected platform and the organization's
hosting preference.

### 5.2 Path A — Provision a New Instance

CRM Builder provisions a fresh instance on a hosting provider on behalf
of the organization:

- The user selects a hosting provider and a plan
- CRM Builder handles provisioning via the provider's API
- The resulting instance credentials are stored in CRM Builder
- The user is guided through any required post-provisioning steps

Supported hosting providers will be defined per CRM platform.

### 5.3 Path B — Onboard an Existing Instance

The organization already has a CRM instance (SaaS or self-hosted):

- The user provides the instance URL and authentication credentials
- CRM Builder validates the connection and confirms admin access
- The instance is saved as a named profile in CRM Builder
- CRM Builder confirms the instance is ready for configuration

### 5.4 Instance Profiles

Regardless of which path is taken, the result is an **instance profile**
stored in CRM Builder. An instance profile contains:
- A display name
- The instance URL
- Authentication credentials
- A link to the client project folder containing YAML program files

Instance profiles persist across sessions and can be managed (added,
edited, deleted) at any time.

### 5.5 Authentication

CRM Builder supports multiple authentication methods to accommodate
different CRM platforms and hosting configurations. The specific methods
supported per platform are defined in the platform-specific configuration
feature docs.

---

## 6. Phase 5 — Configuration

### 6.1 Purpose

Apply the YAML program files to the provisioned or onboarded CRM instance,
deploying the full configuration defined in the entity definition phase.

### 6.2 Configuration Objects

CRM Builder manages configuration for the following object types, each
covered in its own feature specification:

- **Entities** — creating and managing custom entity types
- **Fields** — creating and updating custom fields on entities
- **Layouts** — defining how fields are arranged in the UI
- **Relationships** — linking entities together
- **Security** — roles and access control rules

### 6.3 The Check → Act Pattern

All configuration operations follow the same three-step pattern:

1. **Check** — read the current state of the object from the CRM
2. **Compare** — determine what differs from the desired spec
3. **Act** — create or update only what needs to change

This pattern ensures operations are idempotent and that the tool never
makes unnecessary changes.

### 6.4 Validate → Run → Verify Workflow

The user interacts with configuration through three actions:

**Validate** — parses the YAML program file and previews all planned
changes without contacting the CRM. Shows what will be created, updated,
or left unchanged.

**Run** — applies the configuration to the selected instance. Follows
the Check → Act pattern for each object. Produces a detailed log and
report.

**Verify** — re-reads the current instance state and confirms everything
matches the spec. Makes no changes. Can be run at any time to check
whether manual changes have caused drift.

### 6.5 Destructive Operations

Operations that delete or recreate CRM objects require explicit
confirmation before any changes are made. The user is shown exactly
which objects will be affected and must confirm before proceeding.

---

## 7. Phase 6 — Verify & Maintain

### 7.1 Ongoing Verification

After initial deployment, the Verify action can be run at any time to
confirm the CRM instance still matches the specification. This detects
manual changes that have drifted from the spec.

### 7.2 Updating Configuration

Changes to requirements follow the same workflow as initial configuration:

1. Update the relevant YAML program file
2. Validate and review the planned changes
3. Run to apply the changes
4. Verify the result

### 7.3 Version Control

YAML program files are stored in the client project folder under version
control. Each file carries a `content_version` that tracks the significance
of changes (patch, minor, major).

### 7.4 CRM Application Updates

CRM Builder tracks the version of the CRM platform running on each
instance. When a CRM platform update is available, CRM Builder notifies
the user and provides guidance on whether the update is compatible with
the current configuration. After a platform update, the Verify action
should be run to confirm configuration integrity.

For self-hosted instances, CRM Builder supports initiating platform
updates through the hosting provider's management interface where the
provider API supports it.

### 7.5 YAML Change Management

When YAML program files are updated to reflect changing requirements,
CRM Builder helps manage the change process:

- **Preview** — shows exactly what will change before any updates are applied
- **Versioning** — `content_version` increments indicate the scope of change
  (patch for minor corrections, minor for additive changes, major for
  breaking changes such as field removal or type change)
- **Audit trail** — every Run produces a timestamped report recording
  what changed, what was skipped, and any errors

### 7.6 System Backups

CRM Builder supports backup of CRM configuration state:

- **Configuration backup** — the YAML program files in the client project
  folder represent a complete, restorable description of the CRM
  configuration. Committing these files to version control constitutes
  a configuration backup.
- **Data backup** — for supported hosting providers, CRM Builder can
  initiate or schedule data backups through the provider's management
  interface.
- **Pre-change backups** — before any destructive operation (entity
  deletion, major configuration change), CRM Builder prompts the user
  to confirm a backup has been taken.

---

## 8. PRD and YAML Synchronization

### 8.1 The Problem

PRDs and YAML files are two representations of the same information:
- PRD — human-readable, for stakeholders and reviewers
- YAML — machine-readable, for the deployment tool

Without active synchronization, they drift apart as requirements evolve.

### 8.2 The Synchronization Model

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

---

## 9. Supporting Features

### 9.1 Documentation Generator

CRM Builder generates a structured reference manual from the YAML program
files. The generated document describes the complete CRM configuration in
human-readable form for stakeholders and administrators. It is always
derived from the YAML files and never edited manually.

See `features/feat-doc-generator.md` for the full specification.

### 9.2 User Process Guide Generator

CRM Builder generates one User Process Guide per business process
discovered during requirements work. Each guide is a CRM-aware
how-to document that combines the business-language process narrative
captured in Phase 4 (Process Definition) with the operational detail
captured in the YAML program files — entity labels, field labels,
panel/tab structure, allowed enum values, relationships. Each guide
serves both end-users (operational how-to) and process owners (high-
level walkthrough) in a single document.

User Process Guides are produced as a ninth document type in the
automation Document Generator pipeline, alongside the eight types
defined in the L2 automation PRD. The output lands at
`PRDs/{domain_code}/{PROCESS-CODE}-user-guide.docx` in the client
project folder.

See `features/feat-user-process-guide.md` for the full specification.

### 9.3 Data Import

CRM Builder supports importing records from external systems into the
configured CRM instance. The import wizard guides the user through mapping
source fields to CRM fields, previewing the planned changes, and executing
the import with a never-overwrite rule for existing data.

See `features/feat-data-import.md` for the full specification.

---

## 10. Project Folder Structure

Each client instance is associated with a project folder:

```
ClientProjectFolder/
├── PRDs/                    ← PRD documents
├── programs/                ← YAML program files
├── Implementation Docs/     ← generated reference manual
└── reports/                 ← deployment run reports
```

---

## 11. Repository Structure

```
crmbuilder/                  ← tool repository
  ├── PRDs/                  ← product requirements
  │   ├── CRMBuilder-PRD.md  ← this document
  │   ├── application/       ← cross-cutting requirements
  │   └── features/          ← feature-specific requirements
  ├── docs/                  ← implementation and user documentation
  │   ├── impl-*.md          ← implementation reference (Claude Code maintains)
  │   └── user/              ← end-user documentation
  ├── espo_impl/             ← application source code
  ├── tools/                 ← utilities
  └── tests/                 ← test suite
```

---

## 12. Development Roadmap

### Current Capability (EspoCRM — Implemented)
- Instance management with project folder support
- Entity management (create, delete, delete-and-create)
- Field management (all standard field types)
- Layout management (detail view, list view, tab expansion, dynamic logic)
- Relationship management
- Documentation generation (Markdown + Word)
- User Process Guide generation (one CRM-aware Word document per
  discovered process, combining DB records with YAML program data)
- Data import wizard (JSON → EspoCRM contacts, match-by-email, never-overwrite)
- Run/Verify reporting (.log and .json)

### Near Term
- Security / role-based access control
- Dynamic Logic on individual fields
- Search presets / saved views
- Error handler improvements

### Medium Term (Requirements Pipeline)
- Discovery interview guide (Phase 1)
- Entity definition interview guide (Phase 2)
- AI-assisted PRD generation
- AI-assisted YAML generation from PRD
- PRD/YAML synchronization workflow

### Longer Term (CRM-Agnostic)
- CRM Deployment — hosting provider provisioning (Phase 4, Path A)
- CRM selection scoring engine (Phase 3)
- CRM selection report generation
- Support for additional CRM platforms
- Platform-specific artifact generation

---

## 13. Technical Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Package manager | uv |
| GUI framework | PySide6 (Qt6) |
| HTTP client | requests |
| YAML parser | pyyaml |
| Document generation | python-docx |
| Test framework | pytest |
