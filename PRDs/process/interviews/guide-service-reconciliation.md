# CRM Builder — Service Reconciliation Guide

**Version:** 1.0
**Last Updated:** 04-20-26
**Purpose:** AI guide for Phase 6 — Service Reconciliation (producing the Service PRD)
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**See also:** `guide-domain-reconciliation.md` — the structurally-parallel guide for domain reconciliation. This guide defers to it for reconciliation structure, section standards, and conflict-detection rules, and documents only the service-specific differences. `interview-service-process-definition.md` — the upstream Phase 6 activity whose outputs this reconciliation synthesizes.
**Authoring contract:** `authoring-standards.md` (Section 11 review checklist).

---

## How to Use This Guide

This guide is loaded as context for an AI performing Service
Reconciliation for one Cross-Domain Service. The AI should read this
guide fully and `guide-domain-reconciliation.md` before beginning.

**Services are structurally parallel to domains** (process doc
Section 3.6). The Service PRD has the same structure and completeness
standards as a Domain PRD. Service Reconciliation is identical in
structure to Domain Reconciliation. This guide exists to document the
differences, not to duplicate the body.

**This is a synthesis task, not an interview.** The AI reads all
service process documents for the service, consolidates them into a
Service PRD, and surfaces conflicts for the administrator to resolve.
The administrator answers questions and reviews output, not
provides new information. Same model as Domain Reconciliation.

**One service per conversation.** Each conversation reconciles all
service process documents for a single service and produces a single
Service PRD.

**Session length:** 30–60 minutes, depending on the number of
service processes and conflicts discovered. Same as Domain
Reconciliation.

**Input:**

- Master PRD (with Cross-Domain Services section defining this service)
- Service Overview (if one was produced — optional, same role as Domain Overview)
- Every service process document for this service
- Entity PRDs for every entity the service uses (both service-owned and borrowed)

**Output:** One Word document — the Service PRD — committed to the
implementation's repository at:

```
PRDs/services/{SERVICE_NAME}/{Implementation}-Service-PRD-{ServiceName}.docx
```

**Cardinality:** One Service PRD per Cross-Domain Service.

---

## What the Service PRD Must Contain

The Service PRD has the same six required sections as a Domain PRD.
Refer to `guide-domain-reconciliation.md` "What the Domain PRD Must
Contain" for the full section list and standards.

The sections, with service-specific scoping, are:

| # | Section | Content (service-scoped) |
|---|---------|---|
| 1 | Service Overview | Expanded business context for the service. Describes which capabilities the service provides to consuming domains and any entities the service owns. |
| 2 | Personas | Service-scoped roles for any personas that participate. Often thinner than a Domain PRD's personas section because services tend to be consumed by domain personas rather than having dedicated personas of their own. |
| 3 | Service Processes | One subsection per service process, each containing the eight required sections from the service process document (Section 10 Interview Transcript is excluded from the Service PRD body — see `guide-domain-reconciliation.md` Step 2 for the exclusion rationale). |
| 4 | Data Reference | Consolidated view of all data the service uses, organized by entity, with full field-level detail. Entities the service owns are marked as such. |
| 5 | Decisions Made | Record of decisions made during service process definition conversations. |
| 6 | Open Issues | Unresolved questions requiring answers before implementation. |

**Completeness standard.** Same as Domain PRD — every service process
is included, every persona has scoped role description, every
entity's field definitions are reconciled across all service
processes, every decision is recorded, every open issue is listed.

---

## Differences from Domain Reconciliation

### 1. Service code instead of domain code

All identifier references in the Service PRD use the service's short
code in place of a domain code. The administrator confirms the short
code in the session-start checklist (the same short code used by the
service process documents being reconciled).

### 2. Section 1 is a Service Overview, not a Domain Overview

The Service Overview section in the Service PRD describes:

- Service purpose and the capabilities it provides to consuming domains.
- The consuming domains that use this service.
- Any entities the service owns, with an explicit note about service ownership.
- Any inter-service dependencies (rare, but possible — e.g., a Calendar service that delegates email notifications to an Email service).

### 3. Section 2 Personas is often minimal

Most services are consumed by domain personas rather than having
dedicated personas of their own. The Service PRD's Personas section
may be as short as "This service is consumed by {list of domain
personas from consuming domains}. No personas are owned by the
service." When the service does have dedicated personas (e.g., a
Survey service with a "Survey Respondent" persona), they are
described here with full scope.

### 4. Section 3 is Service Processes

Same structure as a Domain PRD's Section 3 Business Processes, but
the subsections cover service processes and any cross-process
dependencies within the service (rather than cross-process
dependencies within a domain). Services do not have sub-services —
there is no nested sub-domain structure to address.

### 5. Section 4 Data Reference distinguishes owned from borrowed entities

For each entity in the Data Reference, mark explicitly whether it
is:

- **Service-owned** — the service is the canonical home for this entity; the Entity Inventory lists the service (not a domain) as the source.
- **Borrowed** — the service consumes an entity owned by a domain or another service; the service adds fields or relationships that the owning Entity PRD must incorporate via carry-forward.

When a service borrows an entity and adds fields, the Service PRD
flags the borrowed-entity field additions in Section 6 Open Issues
unless they have already been carried forward to the owning Entity
PRD. A service should not silently add fields to a domain's entity
without the carry-forward back to the Entity PRD.

### 6. Cross-consumer conflict detection

Where Domain Reconciliation looks for conflicts across processes
within one domain, Service Reconciliation additionally looks for
conflicts across consuming domains — the same service process may
have slightly different expectations from different consumers.
Surface these as `{SERVICE}-ISS-NNN` open issues with the
divergent consumer behaviors listed.

### 7. Repository path

Service PRDs live at:

```
PRDs/services/{SERVICE_NAME}/{Implementation}-Service-PRD-{ServiceName}.docx
```

Not under a domain code. The `{SERVICE_NAME}` is the service's full
name (e.g., `Notes`), matching the folder that holds the service
process documents.

### 8. Downstream consumption

The Service PRD is consumed by:

- **Phase 7 Domain Reconciliation** for every consuming domain — the Domain PRD's Data Reference references service processes and service-owned entities.
- **Phase 9 YAML Generation** — services may have their own YAML files (e.g., a service with service-owned entities and fields) or contribute to domain YAML (e.g., a service that adds fields to borrowed entities).

Each of these downstream consumers expects the Service PRD to be
complete before they reference it.

---

## Everything Else — Follow guide-domain-reconciliation.md

For the following, follow `guide-domain-reconciliation.md` verbatim:

- Session-start checklist (process doc Section 7.1).
- Input verification routine.
- The step-by-step reconciliation structure (Conflict Detection → PRD Assembly → Review → Document Production).
- Conflict-detection categories (field definition conflicts, status value conflicts, persona role conflicts, cross-process gaps, required-field completeness check, conflict summary).
- Section-by-section assembly procedure.
- Closing: completeness check, summary, document production, state-next-step script.
- Important AI Behaviors.

If this guide and `guide-domain-reconciliation.md` disagree on
anything other than the eight differences enumerated above, that is
a bug in this guide — fix this guide.

---

## Additional AI Behaviors for Service Reconciliation

These behaviors add to — they do not replace — the Important AI
Behaviors in `guide-domain-reconciliation.md`.

- **Flag borrowed-entity field additions aggressively.** A service that adds a field to a domain-owned entity without a carry-forward back to the Entity PRD is a source of silent drift. Every such addition is either a carry-forward (drafted now, if not already) or an Open Issue.

- **Watch for cross-consumer divergence.** The same service process serving three consuming domains may have three slightly different sets of expectations. If one consumer expects a required field that another treats as optional, surface the divergence as an Open Issue rather than flattening it into a single required-status.

- **Distinguish service-owned from service-aware entities.** A service being aware of an entity (a Notes service that attaches to Contact records) is not the same as a service owning the entity. The Data Reference must mark each entity correctly. Misattributing ownership leads to YAML generation errors in Phase 9.

- **Recommend running Service Reconciliation before the consuming Domain Reconciliations when practical.** The process doc Section 3.6 allows domain process documents to reference services generically. But Phase 7 Domain Reconciliation prefers a reconciled Service PRD in hand, because field definitions for service-owned entities live in the Service PRD.

- **Propagate service decisions to consuming domains via carry-forward, not via direct editing.** A decision made during Service Reconciliation that affects a consuming domain's already-written process documents is a carry-forward. The Service PRD does not edit the domain's documents directly.

---

## Changelog

- **1.0** (04-20-26) — Initial release. Scoped to Phase 6 Service Reconciliation only, per `CRM-Builder-Document-Production-Process.docx` Section 3.6. Deferred-to-parent-guide pattern: body content inherits from `guide-domain-reconciliation.md`; this guide documents only service-specific differences (service code, Service Overview section, often-minimal Personas section, owned-vs-borrowed entity distinction in Data Reference, cross-consumer conflict detection, repository path, downstream consumption). Structure aligned with `authoring-standards.md` v1.0. **Not pilot-validated** — first use will be when CBM's Notes or Email service completes process definition and reconciles.
