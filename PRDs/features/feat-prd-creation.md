# CRM Builder — PRD Creation & Requirements Management

**Version:** 1.0
**Status:** Draft — Planned Feature
**Last Updated:** March 2026
**Depends On:** app-yaml-schema.md

---

## 1. Purpose

This document defines the requirements for the PRD Creation feature
in CRM Builder — the AI-assisted process of capturing an organization's
CRM requirements, generating the human-readable PRD documents that
describe those requirements, and producing the YAML program files that
deploy them.

PRD Creation addresses the hardest part of any CRM implementation:
translating what an organization does into a well-structured data model.
This feature guides non-technical users through that process using
structured AI-assisted interviews, producing both the documentation
stakeholders can review and the configuration files the tool can deploy.

---

## 2. Status

PRD Creation is a planned feature. The requirements in this document
define the intended behavior. Implementation has not yet begun.

The current tool assumes YAML program files already exist and focuses
on deploying them. PRD Creation adds the upstream capability that
produces those files in the first place.

---

## 3. Core Concept — Two Documents, Always in Sync

Every CRM requirement is represented in two forms simultaneously:

**The PRD** — a human-readable Word document describing the CRM
configuration in business terms. Written for stakeholders, reviewers,
and administrators who need to understand what the CRM does and why.

**The YAML program file** — a machine-readable configuration file
that CRM Builder uses to deploy the described configuration. Written
for the deployment tool.

These two documents are always kept in sync. Changes to requirements
are made through AI-assisted conversation, which updates both documents
simultaneously. Neither document is edited independently. This
synchronization is the central principle of this feature.

---

## 4. The Requirements Workflow

PRD Creation supports the first two phases of the CRM Builder workflow:

```
Phase 1 — Discovery
  AI-assisted interview about the organization
       ↓
  Entity Map — proposed entities with justification
       ↓
  User review and approval
       ↓
Phase 2 — Entity Definition
  AI-assisted interview for each entity
       ↓
  PRD section + YAML program file per entity
       ↓
  User review and approval
```

Phase 1 produces an understanding of the organization. Phase 2 turns
that understanding into deployable configuration.

---

## 5. Phase 1 — Discovery Interview

### 5.1 Purpose

The discovery interview gathers enough information about the
organization to propose an entity map — the set of entities the
CRM should track and why.

### 5.2 Interview Topics

The interview covers the following areas in a conversational,
guided format:

- **Organization type** — nonprofit, business, association, etc.
- **Core mission** — what the organization does and for whom
- **People tracked** — who the organization works with (clients,
  members, volunteers, donors, contacts, staff)
- **Activities tracked** — what happens between people and the
  organization (sessions, cases, events, transactions)
- **Relationships** — how tracked things connect to each other
- **Reporting needs** — what questions the CRM must be able to answer
- **Process automation** — workflows that need to be managed
- **Integration needs** — other systems that must connect

The interview is conversational, not a form. The AI asks follow-up
questions based on the organization's answers and guides the user
toward a complete picture without requiring CRM expertise.

### 5.3 Native Entity Awareness

The discovery interview is aware of the native entities provided by
the selected (or candidate) CRM platforms. Where an organization's
needs can be met by extending a native entity rather than creating
a custom one, the interview recommends that approach.

For EspoCRM, native entities include Account, Contact, Lead,
Opportunity, Case, Task, Meeting, Call, Email, and Document.

### 5.4 Output — Entity Map

The discovery interview produces an **entity map**: a structured
proposal of the entities that should exist in the CRM. The entity
map includes:

- Each proposed entity with its business justification
- Whether it is a native entity (to be extended) or a custom entity
  (to be created)
- High-level relationships between entities
- Entities explicitly excluded and why

The entity map is presented to the user for review and approval
before Phase 2 begins. The user may accept the proposal, request
changes, or reject individual entities.

---

## 6. Phase 2 — Entity Definition Interview

### 6.1 Purpose

The entity definition interview produces the detailed specification
for a single entity — its fields, layout, relationships, and business
rules. One interview session per entity.

### 6.2 Interview Topics

For each entity, the interview covers:

**Identity**
- Entity name, singular and plural labels
- Entity type (Base, Person, Company, Event)
- Business description and purpose

**Fields**
- Each data element the entity needs to store
- Display label and data type for each field
- Whether each field is required
- Allowed values for dropdown fields
- Default values

**Layout**
- How fields should be grouped into panels and tabs
- Which fields should be shown together
- Conditional visibility (e.g., show mentor fields only for mentors)
- List view columns

**Relationships**
- Links to other entities
- Direction and cardinality of each link
- Display labels on each side

**Business Rules**
- Lifecycle states and transitions
- Access control requirements

### 6.3 Output — PRD Section and YAML File

Each entity definition interview produces two outputs simultaneously:

**A PRD section** — a section of the Word document describing the
entity in human-readable form. Written in business language, suitable
for review by stakeholders without CRM knowledge.

**A YAML program file** — a complete, valid YAML file for the entity,
ready for deployment via CRM Builder.

Both are produced together. Neither is produced alone. The two outputs
are always synchronized.

---

## 7. Change Management — The Sync Workflow

### 7.1 The Synchronization Problem

After initial creation, requirements evolve. Stakeholders request
changes, new needs emerge, and mistakes are discovered. Managing
these changes without letting the PRD and YAML drift apart is the
central challenge this feature addresses.

### 7.2 The Change Workflow

All changes to requirements follow a consistent workflow:

```
1. User describes the change in natural language
         ↓
2. AI proposes the updated PRD section
         ↓
3. User reviews and approves the proposal
         ↓
4. AI updates the PRD document and YAML file simultaneously
         ↓
5. User commits both files to version control
```

Neither the PRD nor the YAML file is ever edited directly outside
this workflow. Direct editing breaks the synchronization and is
explicitly discouraged.

### 7.3 Version Control as Change Log

Both the PRD document and the YAML program files are stored in the
client project repository under version control. The git commit
history serves as the audit trail for requirements evolution.

The YAML `content_version` property communicates the significance
of each change (patch, minor, or major) so reviewers can quickly
assess the impact of an update.

---

## 8. PRD Document Structure

### 8.1 Client PRD vs Tool PRD

This feature produces **client PRDs** — documents describing a
specific organization's CRM requirements. These are distinct from
the CRM Builder tool's own PRD documents (which describe the tool
itself).

Client PRDs live in the client project repository, not in the
CRM Builder tool repository.

### 8.2 Client PRD Contents

A complete client PRD contains:

**Cover section**
- Organization name
- Document version and date
- Brief overview of the CRM implementation scope

**Entity sections** — one per entity, produced by Phase 2 interviews
- Entity description and purpose
- Field definitions with business rationale
- Layout description
- Relationships

**Appendix — Enum Value Reference**
- Complete lists of dropdown values for all enum fields

The client PRD is a living document. It grows as entities are defined
and is updated when requirements change.

### 8.3 PRD and Reference Manual

The client PRD (produced by this feature) and the CRM Reference Manual
(produced by the Documentation Generator) are complementary but
distinct:

| | Client PRD | CRM Reference Manual |
|---|---|---|
| Produced by | AI-assisted interview | Documentation Generator |
| Source | Human conversation | YAML program files |
| Audience | Stakeholders, reviewers | Administrators, developers |
| Content | Requirements and rationale | Technical configuration |
| Format | Word document | Word + Markdown |

---

## 9. Interview Interface

### 9.1 Conversational UI

The PRD Creation interviews are conducted through a conversational
interface — a structured chat where the AI asks questions, the user
responds, and the AI guides the conversation toward a complete
requirements definition.

The interface must:
- Present one topic at a time to avoid overwhelming the user
- Allow the user to go back and revise earlier answers
- Show what has been captured so far so the user can verify
- Provide examples and explanations when the user is uncertain

### 9.2 Preview Before Commit

Before generating output (entity map, PRD section, or YAML file),
the AI presents a summary of what will be produced and asks for
confirmation. The user can request changes before the output is
finalized.

### 9.3 Incremental Output

Output is produced incrementally as interviews complete:
- The entity map is produced after Phase 1 and can be reviewed
  before any entity definition interviews begin
- Each entity's PRD section and YAML file is produced when that
  entity's definition interview is complete
- The full PRD document is assembled as entity sections are completed

---

## 10. Integration with Deployment

The YAML program files produced by this feature are the same files
consumed by the configuration deployment feature. There is no
translation step — the interview directly produces deployable YAML.

Once an entity's interview is complete and its YAML file is approved:
- The file is placed in the project folder's `programs/` directory
- It appears immediately in the Program File panel
- It can be deployed to a CRM instance using the standard
  Validate → Run → Verify workflow

---

## 11. Future Considerations

- **CRM platform awareness** — the interview can tailor its
  recommendations based on the CRM platform already selected,
  suggesting native entities and field types that are well-supported
  on that platform
- **Template library** — common organization types (nonprofits,
  professional associations, service businesses) may benefit from
  starting templates that pre-populate common entities and fields
- **Import from existing PRD** — organizations that have existing
  Word document requirements may want to import them as a starting
  point rather than conducting the full interview from scratch
- **Multi-user review** — a workflow for routing draft PRD sections
  to stakeholders for comment and approval before finalizing
- **Requirement traceability** — linking individual fields and
  entities back to specific business requirements for audit and
  impact analysis purposes
