# UPDATE PROMPT: Document Production Process — Domain Overview Phase and CRM Split

## Session Goal

Update the Document Production Process (v1.4) to incorporate two structural changes from the CRM Builder Automation L2 PRD v1.1 (Section 9, Workflow Engine):

1. Add a new **Domain Overview** phase between Entity Definition and Process Definition.
2. Split **CRM Selection and Deployment** into two separate phases.

This resolves ISS-006 from the L2 PRD.

## Context

### What Changed

The Workflow Engine design (L2 PRD Section 9) introduced two new work item types that do not have corresponding phases in the current Document Production Process:

**domain_overview** — Each domain gets a focused definition conversation before its process interviews begin. The Domain Overview document assembles personas, business process inventory, and data reference from upstream work (Master PRD + Entity PRDs), providing a single context document for all process definition conversations in that domain. It also serves as the dependency node for cross-domain ordering (e.g., Mentoring domain must complete before Mentor Recruitment begins).

**crm_deployment** — CRM Selection (AI conversation producing an evaluation report) and CRM Deployment (provisioning the instance) are now separate work items because they are distinct activities with different outputs and may be separated by time.

### Key Documents

Upload these files from the crmbuilder repo into this conversation:
- `PRDs/process/CRM-Builder-Document-Production-Process.docx` (current v1.4 — the document being updated)
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` (L2 PRD v1.1 — source of the design decisions)

### Relevant L2 PRD Decisions

- **DEC-015:** Domain overview as gateway to process work. Each domain has a domain_overview work item that produces a domain-scoped reference document assembling personas, business process inventory, and data reference from upstream work items.
- **DEC-016:** CRM Selection and CRM Deployment are separate work items. CRM Selection is an AI-session conversation producing a CRM Evaluation Report. CRM Deployment is the provisioning of the actual CRM instance.

### Domain Overview Document Structure (from L2 PRD Section 9.10)

The Domain Overview document contains:
- **Domain Purpose** — expanded business context, drawn from and elaborating on the Master PRD's domain description.
- **Personas** — personas participating in this domain, scoped from the Master PRD's persona definitions to their domain-specific roles.
- **Business Processes** — the complete process inventory for the domain with lifecycle narrative, process relationships, and dependency ordering. Describes how the processes connect end to end.
- **Data Reference** — the entities and fields relevant to this domain, assembled by reference to the completed Entity PRDs. Shows which entities the domain uses without redefining them.

### Domain Overview Context Requirements

Each Domain Overview conversation receives:
- Master PRD
- Entity Inventory
- All Entity PRDs for entities that participate in this domain

## Changes Required

### 1. Add Phase 3: Domain Overview

Insert a new phase section between Entity Definition (current Phase 2) and Process Definition (current Phase 3). The section should follow the same structure as other phase sections:

- Conversations: 1 per domain
- Input: Master PRD + Entity Inventory + Entity PRDs for entities participating in this domain
- Output: Domain Overview document (Word)
- Repository location: PRDs/{domain_code}/{Implementation}-Domain-Overview-{DomainName}.docx
- Description of what the conversation covers and what the document contains
- Context passing explanation
- Domain Overview document structure (4 sections listed above)
- Completeness standard

The section should also explain the cross-domain dependency option: if one domain must complete before another begins, the administrator sets the later domain's overview to depend on the earlier domain's reconciliation.

### 2. Split Phase 7 into Two Phases

Current Phase 7 (CRM Selection and Deployment) becomes:
- **Phase 8: CRM Selection** — AI conversation evaluating platforms, producing CRM Evaluation Report
- **Phase 9: CRM Deployment** — Provisioning the CRM instance using CRM Builder or the platform's own process

Most of the existing Phase 7 content covers CRM Selection. CRM Deployment needs a short new section describing what happens during provisioning.

### 3. Renumber All Phases

The new phase numbering:
| Phase | Name |
|-------|------|
| 1 | Master PRD |
| 2 | Entity Definition |
| 3 | Domain Overview |
| 4 | Process Definition |
| 5 | Domain Reconciliation |
| 6 | Stakeholder Review |
| 7 | YAML Generation |
| 8 | CRM Selection |
| 9 | CRM Deployment |
| 10 | CRM Configuration |
| 11 | Verification |

### 4. Update Phase Summary Table (Section 2)

Add Domain Overview row and split CRM Selection/Deployment into separate rows. Update all phase numbers.

### 5. Update Document Hierarchy (Section 9)

Insert Domain Overview at the appropriate level. The hierarchy should reflect that Domain Overview sits between Entity PRDs and Process Documents.

### 6. Update Context Requirements Table (Section 7.2)

Add a row for Domain Overview conversations with their required inputs. Also update Process Definition inputs to include the Domain Overview document instead of uploading Master PRD + Entity Inventory + Entity PRDs directly.

### 7. Update Document Language Table

Add Domain Overview with audience "Domain stakeholders, administrators" and language "Business — no product names or implementation details."

### 8. Update Version

- Version: 1.4 → 1.5
- Status: Current
- Last Updated: Use current timestamp in MM-DD-YY HH:MM format
- Replaces: v1.4

## Output Format

Produce the updated Document Production Process as a Word document committed to the crmbuilder repo at the same path.

## Working Style

- Discuss and resolve one change at a time before moving to the next
- Ask for confirmation before finalizing each change
- Present the complete change list for approval before modifying the document
