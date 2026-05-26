# CRMBuilder Glossary

| Field | Value |
|-------|-------|
| Version | 0.2 |
| Last Updated | 05-26-26 14:00 |
| Status | In progress — terms added as they're discussed |
| Audience | Anyone reading or contributing to the Master CRMBuilder PRD and supporting documentation |
| Governs | Canonical definitions of terms used across CRMBuilder methodology, governance, and process documentation |
| Future state | This content will migrate to V2 records with desktop UI access per the Planning Items authored in this session. The MD file remains the human-readable view until that migration completes. |

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.2 | 05-26-26 | Adds Skill (TERM-002), Pattern (TERM-003), Inventory (TERM-004), Client (TERM-005). |
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

## Client

**Identifier:** TERM-005

**Definition:** An organization (or, less commonly, an individual) whose product is being defined through the CRMBuilder process. Each engagement serves one client; one client may have multiple engagements over time.

**Scope:** Used in the Master CRMBuilder PRD and supporting documentation when referring to the recipient of the engagement's work.

**Examples:**

- CRMBuilder is the client of its own dogfood engagement (the CRMBUILDER engagement).
- Cleveland Business Mentors is the client of the (future) CBM engagement.

**Distinguishing notes:**

- Not the same as **Engagement.** The engagement is the unit of work; the client is the organization receiving the work.
- Not the same as **Stakeholder.** A client is the organization; stakeholders are specific individuals within or associated with the client who participate in engagement activities.
- Not the same as **End User.** End users of the deployed product may differ from the client itself.

**Related terms:** Engagement, Stakeholder, Persona

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

## Inventory

**Identifier:** TERM-004

**Definition:** A reference list of typical items — entities, personas, processes — for a given domain or organizational type. Serves as a checklist or starting set when capturing a specific client's content.

**Scope:** Used as Process Support Knowledge/Tools (Category 3). Eventual V2 storage per Planning Items captured in this session.

**Examples:**

- An Inventory of typical personas for a nonprofit (Executive Director, Program Manager, Volunteer Coordinator, Donor Relations, etc.).
- An Inventory of typical entities for a membership organization (Member, Account, Dues Payment, Renewal, Event Registration).

**Distinguishing notes:**

- Distinction from **Skill** and **Pattern** is still being refined. Working hypothesis: an Inventory is the list level (just the items); a Pattern is the relationships among items; a Skill is the operational guidance.
- Not the same as a deliverable inventory. The reference inventory (Category 3) is reusable across engagements; an engagement-specific inventory of the actual items captured is a deliverable (Category 2).

**Related terms:** Skill, Pattern, Process Support Knowledge/Tools

## Pattern

**Identifier:** TERM-003

**Definition:** A reusable structural template describing the typical shape of a business domain or organizational type. Captures common entities, personas, processes, and their relationships, intended as a starting reference when working with clients of that type.

**Scope:** Used as Process Support Knowledge/Tools (Category 3). Eventual V2 storage per Planning Items captured in this session.

**Examples:**

- A Pattern for nonprofit mentoring organizations capturing the typical structure of mentor-mentee engagements, session types, recruiting flows.
- A Pattern for member-based associations capturing typical membership, dues, and communications structures.

**Distinguishing notes:**

- Distinction from **Skill** and **Inventory** is still being refined (see Skill entry).
- Not the same as an instance. A Pattern is reusable across clients; once instantiated for a specific engagement, the resulting entities are deliverables (Category 2).

**Related terms:** Skill, Inventory, Process Support Knowledge/Tools

## Skill

**Identifier:** TERM-002

**Definition:** A reusable knowledge file containing domain-specific guidance — typical entities, personas, processes, areas of questioning, key data — for an industry vertical or business function. Loaded contextually during the process when the client makes a defining statement that triggers it.

**Scope:** Used as Process Support Knowledge/Tools (Category 3). Currently stored as MD files in the crmbuilder repo as temporary scaffolding; eventual V2 storage per Planning Items captured in this session.

**Examples:**

- A Skill for "charitable foundation CRM" providing guidance on typical donor entities, campaign structures, regulatory considerations.
- A Skill for "social marketing CRM" covering campaign types, audience segmentation, engagement tracking patterns.
- A Skill for "nonprofit mentoring" covering mentor/mentee entities, engagement lifecycles, session types.

**Distinguishing notes:**

- Distinction from **Pattern** and **Inventory** is still being refined. Working hypothesis: a Skill is operational guidance (questions to ask, what to look for); a Pattern is structural (typical entities and their relationships); an Inventory is the list level (just the items).
- Not engagement-specific. A Skill applies across multiple engagements sharing the relevant domain characteristics.

**Related terms:** Pattern, Inventory, Defining Statement, Process Support Knowledge/Tools
