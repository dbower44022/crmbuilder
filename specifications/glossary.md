# CRMBuilder Glossary

| Field | Value |
|-------|-------|
| Version | 0.1 |
| Last Updated | 05-26-26 12:45 |
| Status | Initial — first term defined |
| Audience | Anyone reading or contributing to the Master CRMBuilder PRD and supporting documentation |
| Governs | Canonical definitions of terms used across CRMBuilder methodology, governance, and process documentation |
| Future state | This content will migrate to V2 records with desktop UI access per the Planning Item authored in this session. The MD file remains the human-readable view until that migration completes. |

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-26-26 | Initial. Defines "Engagement" (TERM-001). |

---

## How to Read and Contribute

Terms are listed alphabetically by name. The identifier (`TERM-NNN`) is the stable reference and is assigned in creation order — the alphabetical ordering of entries below is rendering-only.

When adding a new term, follow the standard entry format:

- **Term name** (as a level-2 heading)
- **Identifier** — `TERM-NNN`, next available in creation order
- **Definition** — one or two sentences in plain English
- **Scope** — where this term applies (which documents, which contexts)
- **Examples** — one or two concrete uses to ground the abstraction
- **Distinguishing notes** — what the term is NOT to be confused with
- **Related terms** — cross-references to other glossary entries

---

## Engagement

**Identifier:** TERM-001

**Definition:** A defined unit of work in which the CRMBuilder process is applied to capture the complete definition of one product — a deployed, functional application — for one client organization. Each engagement is its own partition in V2's storage system, holding a single Charter, Status, and the full set of governance and methodology records produced during the engagement's lifecycle.

**Scope:** Used throughout the Master CRMBuilder PRD and supporting documentation when referring to a client's structured relationship with the CRMBuilder process. Also used as the partitioning concept in V2's storage system — each engagement has its own data isolation.

**Examples:**

- The CRMBUILDER engagement: the dogfood engagement in which CRMBuilder uses its own process to define itself. The product being defined is CRMBuilder as a software product.
- The (future) CBM engagement: Cleveland Business Mentors using the process to define their CRM-shaped system. The product being defined is a configured CRM serving CBM's mentoring mission.

**Distinguishing notes:**

- Not synonymous with **Client.** A client is the organization being served; an engagement is the specific application of the CRMBuilder process to that client. One client could in principle have multiple engagements over time.
- Not the same as a **Session.** A session is a single interview or working interaction within an engagement; an engagement contains many sessions across its lifecycle.
- Not the same as a **Project** in the colloquial sense. "Engagement" specifically means the structured application of the CRMBuilder process with its phases, governance records, and deliverables.

**Related terms:** Client, Session, Phase, Charter, Status
