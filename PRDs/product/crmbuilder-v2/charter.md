# CRMBuilder v2 Charter

**Version:** 0.1 (draft)
**Last Updated:** 05-06-26 19:28
**Status:** In planning — pre-build

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-06-26 | Initial draft from planning conversation. Captures scope, name, architectural foundations, session orientation protocol, and remaining planning dimensions. |

## Scope

CRMBuilder v2 is the next major iteration of CRMBuilder. It rebuilds the methodology's foundation by making a structured database the source of truth for all CRM implementation artifacts — personas, entities, fields, processes, process steps, requirements, decisions, manual-config items, test specifications, and cross-references — with Word documents, deployment YAML, and test cases all generated as renders of that source rather than authored separately. It evolves the authoring loop, the storage layer, and the parts of the application that read or write methodology data, on the basis of lessons learned during the CBM pilot.

CBM is the test case that validates progress at each step, not a parallel client commitment that constrains the work. The new system's correctness is demonstrated by its ability to absorb CBM's existing PRD content and produce equivalent or improved deployment, authoring, and verification outcomes.

## In Scope

The following are in scope for CRMBuilder v2:

- **Schema design.** Designing the structured data model for both project management artifacts (decisions, sessions, statuses, topics, references) and methodology artifacts (personas, entities, fields, processes, requirements, etc.).
- **Storage and rendering implementation.** Building the SQLite + Python access layer + REST API + MCP server stack, plus the renderers that produce Word documents, deployment YAML, and test cases from the database.
- **Authoring evolution.** Moving from Word-document authoring sessions to structured database authoring through Claude.ai and MCP tool calls. Includes evolving the methodology's interview guides and prompt templates accordingly.
- **Application changes to support the new model.** Modifying the existing crmbuilder PySide6 desktop application to read and write the v2 database directly, rather than importing Word documents into a per-client store.
- **Migration of CBM into the new model.** Porting CBM's existing PRD content into the v2 database one domain at a time, in priority order: MN first as the proving ground, then MR, then CR, then FU.
- **Test infrastructure.** Building the layered functional testing system (CRUD → integration → process/persona → UI) that exercises deployed CRMs against database-stored requirements, with structured feedback to Claude Code for iterative remediation.

## Out of Scope

The following are explicitly out of scope, and continue or proceed as separate workstreams:

- **Incremental fixes to the existing v1 deployment engine.** Continue under the existing crmbuilder roadmap. v2 does not replace the engine itself; it replaces the storage and authoring foundation that feeds it.
- **Engine pluggability work for additional CRM backends.** The Attio and HubSpot deployment series proceed independently. v2 makes engine pluggability cleaner over time (renders for different engines come from the same source), but the pluggability work itself is a separate stream.
- **New client onboardings before the migration is sufficiently complete.** No new clients onboarded through CRMBuilder until v2 can support them. CBM completes its migration before any second client is considered.

## Architectural Foundations

These are the design principles that underpin the v2 system. Each is captured in detail with rationale, alternatives considered, and consequences in the companion decisions document (see `decisions.md`).

**Database as source of truth.** All v2 artifacts — both project management artifacts (decisions, sessions, statuses) and methodology artifacts (personas, entities, fields, processes, requirements) — live in a single structured database. Word documents, deployment YAML, and test cases are renders of that database, not independently authored. This eliminates the drift cost paid today, where the same field is referenced from multiple Word documents and any change requires manual reconciliation.

**Storage stack.** The data layer is SQLite (file-based, no server required, ACID transactions). Above it sits a Python access layer that handles validation, transactions, and JSON exports for git diffability. Above that sits a REST API (FastAPI) that exposes the database over HTTP, providing a stable interface for any client. An MCP server adapts the REST API for Claude.ai tool calls, allowing AI sessions to read and write the database in real time. The same architecture migrates to PostgreSQL when productization needs multi-user remote access; the protocol stays the same.

**Universal references pattern.** Cross-references between any two records — a decision about a topic, a session covering a requirement, a process step touching a field — are stored in a single `references` table with `source_type`, `source_id`, `target_type`, `target_id`, and a controlled-vocabulary `relationship` field. This scales linearly with the number of entity types instead of quadratically, makes "give me everything related to X" a uniform query regardless of what X is, and provides the foundation for change-impact analysis.

**Topics as a generic concern type.** A `topics` table stores free-floating subjects that aren't typed entities (architectural concepts, design discussions, planning topics). Methodology entities are first-class typed records and don't live in topics; both can be referenced through the same `references` table.

**Renders, not authored copies.** Word documents for stakeholder review, YAML programs for deployment, test cases for verification — all are generated from the database on demand. Authoring flows update the database; rendered artifacts are derivative and disposable.

**CBM as test case.** Cleveland Business Mentoring is the first client whose existing PRD content migrates into v2. Migration validates that the schema can absorb real implementation content. Migration order is priority-driven: MN first, then MR, then CR, then FU.

**v1/v2 boundary tracking.** Directory separation (v2 artifacts under `PRDs/product/crmbuilder-v2/`), file naming conventions, commit message scope tag (`v2:`), and a living status document maintain a clear distinction between v2 work and the existing v1 codebase and methodology.

**Session orientation protocol.** Every Claude.ai session that engages v2 follows a tiered orientation: Tier 1 reads `CLAUDE.md`, Tier 2 queries CHARTER, STATUS, recent sessions, and relevant decisions via MCP, Tier 3 issues on-demand queries during conversation. Bounded context cost, predictable session start.

## Current State

**Phase:** Planning (pre-build).

Planning dimensions completed:

- #1 (project identity) — resolved
- #2.1 (session orientation protocol) — resolved
- #2.2 (CLAUDE.md update) — design resolved; mechanical implementation pending
- #2.3 (handoff conventions) — substantially resolved by sessions table + references; full design happens in schema work
- #2.4 (capture of working ideas) — substantially resolved by topics + references
- #3 (decision management) — substantially resolved by decisions table + references
- #4 (CBM coexistence) — collapsed (CBM is the test case, not a parallel commitment)

Planning dimensions remaining:

- #5 (pacing, cadence, milestones)
- #6 (division of labor)
- #7 (risk register)
- #8 (exit criteria)

**Active work:** Drafting this charter and the companion decisions document as the first durable artifacts of the project. Architectural decisions are being numbered retroactively as DEC-001 through DEC-N.

**Not yet started:** Step 0 (schema design), implementation of any v2 code, creation of the v2 home directory in the repo, CLAUDE.md update, MCP server build.

## Open Planning Items

The following planning dimensions remain to be resolved before Step 0 (schema design) begins:

**#5 — Pacing, cadence, and milestones.** What does a working session on this project look like? Cadence weekly, ad-hoc, or time-blocked against ongoing CBM work? What does "done" mean for each phase and sub-step? What are the gates that determine whether to proceed forward, iterate within the current step, or stop and reassess?

**#6 — Division of labor.** Where are the boundaries between Claude.ai work (design, drafting, schema iteration), Claude Code work (implementation, file edits, repo changes), and Doug-only work (methodology decisions, stakeholder coordination, final approval, validation review)? What's the handoff protocol between modes?

**#7 — Risk register.** What can fail and what's the response? Schema design taking longer than budgeted, the schema being wrong only after a domain is migrated, application UI work being substantially larger than scoped, the existing methodology continuing to accrue Word-doc artifacts faster than the new system can absorb them.

**#8 — Exit criteria.** Success criterion that lets us commit from Step 0 (schema design) to Step 1 (storage layer build). Abort criterion that says "this isn't viable, fall back to the existing model." Per-phase gates at each subsequent boundary.

Once these are resolved, the next major workstream is **Step 0 — Schema Design**, itself a multi-session design effort covering the project management schema, the methodology schema (entities, fields, personas, processes, requirements, decisions, manual-config items, test specifications), the references vocabulary, and validation rules.
