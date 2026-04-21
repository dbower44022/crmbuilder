# CRM Builder — Service Process Definition Interview Guide

**Version:** 1.1
**Last Updated:** 04-21-26
**Purpose:** AI interviewer guide for Phase 6 — Service Process Definition
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**See also:** `interview-process-definition.md` — the structurally-parallel guide for domain process documents. This guide defers to it for interview structure, section standards, and field-level detail rules, and documents only the service-specific differences.
**Authoring contract:** `authoring-standards.md` (Section 11 review checklist).

---

## How to Use This Guide

This guide is loaded as context for an AI conducting a process
definition interview for one process belonging to a Cross-Domain
Service. The AI should read this guide fully and
`interview-process-definition.md` before beginning.

**Services are structurally parallel to domains** (process doc
Section 3.6). A Cross-Domain Service owns processes just like a
domain does. The Service Process Definition interview is identical
in structure and standards to a domain process definition interview.
This guide exists to document the differences, not to duplicate the
body.

**Structure reference.** For the full interview structure — the ten
required sections of a process document, the field-level detail
standard, the transcript format, the scope-change protocol, and the
closing sequence — follow `interview-process-definition.md`. That
guide governs this conversation except where this guide overrides.

**One service process per conversation.** Each conversation defines
a single service process and produces a single service process
document.

**Session length:** 45–60 minutes. Same as domain process definition.
Stop at 60 minutes regardless of completion — schedule a follow-up
rather than pushing through fatigue.

**Input (required):**

- Master PRD (with Cross-Domain Services section defining this service)
- Entity Inventory
- All previously completed service process documents for this service

**Input (optional, use when available):**

- Service Overview (if the service has more than a few processes and a Service Overview has been produced — same role as a Domain Overview; see `guide-domain-overview.md`)
- Entity PRDs for entities this service uses. Per process doc Rule 5.1, Entity PRDs come after process documents; service process work may run before the borrowed entities have completed Entity PRDs. When an Entity PRD exists, it informs field-level detail in Sections 7 and 8; when it does not, the process document cites the Entity Inventory row and proposes fields that will be reconciled into a later Phase 5 Entity PRD.

If a service owns entities not yet in the Entity Inventory, see
"Service-Owned Entity Discovery" below — this is a Phase 3
Entity-Inventory update, not an Entity-PRD prerequisite for the
current service process.

**Output:** One Word document — the service process document —
committed to the implementation's repository at:

```
PRDs/services/{SERVICE_NAME}/{SERVICE-PROCESS-CODE}.docx
```

**Cardinality:** One service process document per service process.

---

## What the Service Process Document Must Contain

The service process document has the same ten required sections as
a domain process document. Refer to
`interview-process-definition.md` "What the Process Document Must
Contain" for the full list and standards.

The sections are:

1. Process Purpose
2. Process Triggers
3. Personas Involved
4. Process Workflow
5. Process Completion
6. System Requirements
7. Process Data (Supporting)
8. Data Collected (New Data)
9. Open Issues
10. Interview Transcript

**Completeness standard.** Same as domain process documents —
Sections 7 and 8 must meet the field-level detail standard; all ten
sections must be present and meet their respective standards.

---

## Differences from Domain Process Definition

### 1. Service code instead of domain code

Identifiers in a service process document use the service name (or a
short form derived from the service name) in place of a domain code.
The process doc Section 3.6 says services are identified by their
full name to avoid confusion with domain codes.

**Identifier format for service processes:**

```
[SERVICE]-[PROCESS]-[TYPE]-[SEQ]
```

Where `[SERVICE]` is the service's short code (derived from the
service's full name and established at service creation — e.g.,
`NOTES`, `EMAIL`, `CAL`, `SURVEY`). The administrator confirms the
short code in the session-start checklist.

Examples:

- `NOTES-ATTACH-REQ-001` — Notes service, Attach Note process, Requirement 1
- `EMAIL-SEND-DAT-003` — Email service, Send Email process, Data item 3

### 2. Cross-domain consumer scoping

Service processes are consumed by multiple domains. Section 3
(Personas Involved) and Section 4 (Process Workflow) must scope
personas and workflow steps correctly: the service process's workflow
is domain-neutral, but personas that initiate or participate in the
process include personas from every consuming domain.

For Section 3, include:

- Personas from the service itself (if the service has dedicated personas — rare but possible).
- Personas from every domain that consumes this service process, with a note indicating their domain origin.

For Section 4, keep the workflow steps domain-neutral. Where a step
varies by consuming domain, capture the variation as a decision
branch in the workflow narrative (not as a separate workflow per
domain).

### 3. Service-owned entity discovery

A service may own entities not already in the Entity Inventory (e.g.,
a Notes service may own a `Note` entity; a Survey service may own
`Survey` and `SurveyResponse` entities). If the interview reveals a
new service-owned entity that is not in the Entity Inventory:

1. Pause the interview at a clean stopping point (process doc Section 10.2 applied to service entities).
2. Update the Entity Inventory to add the new entity with the service name as the source.
3. Conduct a Phase 5 Entity PRD session for the new entity using `interview-entity-prd.md`.
4. Resume the service process interview with the new Entity PRD available.

Services frequently surface new entities during process definition
because service scope often wasn't fully understood in Phase 3. This
is expected. Follow the scope-change protocol cleanly rather than
silently inventing entities in the service process document.

### 4. No domain overview context

Services do not always have a Service Overview analogous to a Domain
Overview. If the service has more than a few processes and a Service
Overview has been produced, use it as the primary context. Otherwise,
the Master PRD's Cross-Domain Services section plus the Entity PRDs
are the context set.

If this service has three or more processes and no Service Overview
exists, recommend to the administrator that a Service Overview be
produced before continuing service process definition. A Service
Overview follows `guide-domain-overview.md` scoped to the service.

### 5. Repository path

Service process documents live at:

```
PRDs/services/{SERVICE_NAME}/{SERVICE-PROCESS-CODE}.docx
```

Not under a domain code. The `{SERVICE_NAME}` is the service's full
name (e.g., `Notes`, `Email`, `Calendar`, `Surveys`). The
`{SERVICE-PROCESS-CODE}` uses the service's short code form (e.g.,
`NOTES-ATTACH` rather than the full service name).

### 6. No sub-service variant

Sub-domains are a valid construct for domains. Services do not have
a sub-service construct — if a service is large enough that
sub-service organization seems warranted, reconsider whether it is
actually one service or several services that should be split.

### 7. Carry-forward cross-references

When a service process definition surfaces a gap in a borrowed
entity's Entity PRD, or a consuming domain's process documents, the
carry-forward request crosses service-and-domain boundaries. Store
the carry-forward request at:

```
{implementation}/PRDs/services/{SERVICE_NAME}/carry-forward/SESSION-PROMPT-carry-forward-{slug}.md
```

If the carry-forward affects a specific consuming domain, mirror a
copy at:

```
{implementation}/PRDs/{domain_code}/carry-forward/SESSION-PROMPT-carry-forward-{slug}.md
```

The mirror is a pointer, not a duplicate content file — it points
at the service's canonical carry-forward file.

---

## Everything Else — Follow interview-process-definition.md

For the following, follow `interview-process-definition.md`
verbatim:

- Session-start checklist (Section 7.1 of the process doc).
- Input verification routine.
- Opening statement and state-the-plan scripts.
- The section-by-section interview structure (Topics 1 through 10).
- The field-level detail standard.
- Identifier assignment discipline (permanent, never reused — process doc Section 5).
- Section 10 transcript format.
- Closing: completeness check, summary, document production, state-next-step script.
- Important AI Behaviors (with the service-specific additions in the "Additional AI Behaviors for Service Processes" section below).

If this guide and `interview-process-definition.md` disagree on
anything other than the seven differences enumerated above, that is
a bug in this guide — fix this guide.

---

## Additional AI Behaviors for Service Processes

These behaviors add to — they do not replace — the Important AI
Behaviors in `interview-process-definition.md`.

- **Stay service-scoped.** A service process is not a domain process. When a consuming domain's specifics surface during the interview, capture them as workflow variations within the service process, not as reasons to redefine the service process for that domain.

- **Flag new service-owned entities immediately.** If a service process surfaces an entity not in the Entity Inventory, pause immediately. Do not let the conversation drift into defining fields on an entity that hasn't been reconciled.

- **Resist adding domain-specific fields to service-owned entities.** A Note entity belongs to the Notes service. If a consuming domain wants a domain-specific field on Note records, the field likely belongs on the consuming entity (the record the note is attached to), not on the Note entity. Surface the design question rather than silently adding the field.

- **Recommend a Service Overview when there are three or more processes.** Without one, each service process interview re-loads the full set of Entity PRDs and Master PRD references, which is inefficient and error-prone.

- **Use the service short code consistently.** Once the administrator confirms the short code (NOTES, EMAIL, etc.), every identifier in the session uses it. Do not mix full names and short codes.

---

## Changelog

- **1.1** (04-21-26) — Same over-tightening fix applied to `guide-domain-overview.md` v1.1 and `interview-entity-prd.md` v1.1. v1.0 required Entity PRDs for borrowed entities before the service process could be defined; per process doc Rule 5.1 Entity PRDs come after process documents. Entity PRDs moved to optional inputs — when they exist they inform field-level detail, when they do not the Entity Inventory row is the authority and proposed fields become Phase 5 Entity PRD inputs. Pilot-validation status: not yet exercised; first use will be when CBM's Notes or Email service runs.
- **1.0** (04-20-26) — Initial release. Scoped to Phase 6 Service Process Definition only, per `CRM-Builder-Document-Production-Process.docx` Section 3.6. Deferred-to-parent-guide pattern: body content inherits from `interview-process-definition.md`; this guide documents only service-specific differences. Structure aligned with `authoring-standards.md` v1.0. **Not pilot-validated; see v1.1.**
