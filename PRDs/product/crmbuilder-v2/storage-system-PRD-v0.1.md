# CRMBuilder v2 — Storage System PRD

**Version:** 0.1 (draft)
**Last Updated:** 05-07-26 14:30
**Status:** Draft — pending approval

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-07-26 | Initial draft. Specifies the four-layer storage stack per DEC-005, the project-management entity schema, migration of bootstrap markdown content into the database, and acceptance criteria for a functioning system. |

---

## 1. Overview

### Purpose

This document specifies the requirements for the CRMBuilder v2 storage system: the foundational data layer that makes a structured database the source of truth for all v2 artifacts. It is the build specification handed to Claude Code, which produces its own implementation plan from these requirements and executes it. The PRD specifies what a functioning system must do; how to build it (single pass or staged) is Claude Code's call.

### Background

CRMBuilder v2 is the next major iteration of CRMBuilder. Per DEC-004 (Database as source of truth for all v2 artifacts), the v2 architecture inverts the current methodology's relationship between Word documents and the database: structured records become authoritative, and Word documents, deployment YAML, and test cases become renders generated from those records.

The storage system specified in this PRD is the foundation that makes that inversion real. Until it exists and is functioning, v2 work proceeds against markdown files (the current bootstrap state), which incurs the same drift cost the architecture is meant to eliminate. This PRD drives the work that closes that gap.

### Source decisions

This PRD does not re-derive architectural decisions; it specifies requirements grounded in the following decision records, which should be considered authoritative:

- **DEC-004 — Database as source of truth for all v2 artifacts.** Establishes the principle that drives this work.
- **DEC-005 — Storage stack: SQLite + access layer + REST API + MCP server.** Specifies the four-layer architecture this PRD details.
- **DEC-006 — Universal references pattern with controlled relationship vocabulary.** Specifies the cross-entity references mechanism.
- **DEC-007 — Topics table for free-floating concepts.** Specifies the topics entity.
- **DEC-008 — Renders, not authored copies.** Establishes that downstream artifacts (Word, YAML, tests) are derived, not authored. Renderers themselves are out of scope for v0.1.
- **DEC-011 — Session orientation protocol (tiered).** Drives the read-side query patterns the API and MCP server must support.

---

## 2. Scope

### In Scope

The following are required deliverables for v0.1:

1. **Schema.** Tables for the project-management artifacts currently bootstrapped as markdown (charter, status, decisions, sessions), plus the universal references table (DEC-006), the topics table (DEC-007), and supporting structures for change-log/versioning, risks, and open planning items.
2. **Python access layer.** A module that owns all reads and writes to the database. Validates inputs, enforces controlled vocabularies, manages transactions, and triggers JSON-export generation on every write.
3. **REST API (FastAPI).** HTTP service exposing CRUD operations for every entity in the schema, plus query endpoints supporting the tiered session orientation protocol (DEC-011) and cross-entity reference traversal (DEC-006).
4. **MCP server.** Thin adapter that translates MCP tool calls from Claude.ai into REST API calls. Stateless; no business logic beyond protocol translation.
5. **JSON export hook.** Transactional generation of human-readable, git-diffable JSON files from the database on every write.
6. **Migration of bootstrap content.** All four governance markdown files currently in `PRDs/product/crmbuilder-v2/` (charter.md, decisions.md, sessions.md, status.md) imported into the database with full fidelity. After migration, those markdown files are decommissioned (recoverable through git history but no longer the source of truth).

### Out of Scope

The following are explicitly deferred to later versions or separate work:

- **Methodology entity schema.** Personas, entities, fields, processes, process steps, requirements, manual-config items, test specifications. v0.1 covers project-management entities only; methodology entities are Step 0 follow-on work.
- **Renderers.** Word, YAML, and test-case rendering from the database (DEC-008 — renders, not authored copies). Future workstream.
- **Authentication and authorization.** v0.1 runs single-user, locally or on personal infrastructure. Auth is part of productization.
- **Hosting and deployment.** Where the system runs and how Claude.ai reaches it is a separate decision (see Open Questions). The v0.1 deliverable is the codebase, not a deployed service.
- **Application integration.** The existing CRMBuilder PySide6 desktop application is not modified by this work. Integration with v2 is a later workstream.
- **Migration of CBM (Cleveland Business Mentoring) content.** No CBM PRD content migrates as part of v0.1. CBM migration begins after v0.1 is operational, per DEC-010 (the priority order: MN, then MR, then CR, then FU).
- **PostgreSQL migration.** SQLite is the v0.1 backing store. Per DEC-005, migration to PostgreSQL is straightforward and deferred until multi-user remote becomes a requirement.

---

## 3. Architecture

The system is a four-layer stack plus a JSON-export side channel, per DEC-005 (the storage-stack decision):

```
┌─────────────────────────────────────────────────┐
│  Claude.ai (consumer)                           │
└──────────────┬──────────────────────────────────┘
               │ MCP tool calls
┌──────────────▼──────────────────────────────────┐
│  MCP Server (thin adapter, stateless)           │
└──────────────┬──────────────────────────────────┘
               │ HTTP / REST
┌──────────────▼──────────────────────────────────┐
│  FastAPI REST API (CRUD, query, traversal)     │
└──────────────┬──────────────────────────────────┘
               │ Python function calls
┌──────────────▼──────────────────────────────────┐
│  Python access layer                            │
│  (validation, transactions, JSON export hook)   │
└──────────────┬──────────────────────────────────┘
               │ SQL
┌──────────────▼──────────────────────────────────┐
│  SQLite database file                           │
└─────────────────────────────────────────────────┘
                                     │
                                     │ on every write
                ┌────────────────────▼─────────┐
                │  JSON export files (git)     │
                └──────────────────────────────┘
```

**Layer responsibilities:**

- **SQLite** stores all data in a single file. ACID transactions. No server process.
- **Python access layer** is the only code that reads or writes SQLite directly. Owns validation, controlled-vocabulary enforcement, transaction boundaries, and the JSON-export hook. All higher layers go through it.
- **FastAPI REST API** is the durable client interface. Stable endpoint contracts. Independently testable via curl. When productized, this layer becomes the hosted endpoint with authentication added.
- **MCP server** is the Claude.ai bridge. Translates MCP tool calls into REST API calls. Swappable: a different AI client interface could replace it without affecting the rest of the stack.
- **JSON export hook** generates human-readable, git-diffable JSON files transactionally on every database write, providing a git-trackable snapshot of database state.

---

## 4. Functional Requirements

### 4.1 Schema (data model)

The database must contain the entities described in section 5 (Data Model Requirements), with the constraints, relationships, and validation rules specified there.

### 4.2 Python access layer

The access layer must:

- Provide functions for CRUD operations on every entity type defined in section 5
- Validate inputs against the controlled vocabularies and field constraints defined in section 5
- Enforce referential integrity (foreign keys; controlled-vocabulary `relationship` values in the references table; valid `source_type` and `target_type` values)
- Wrap each operation in a transaction such that the database write and the JSON-export write are atomic — either both commit or both roll back
- Emit a change-log entry for every mutating operation (insert, update, delete)
- Return structured errors for validation failures, distinguishing client errors (bad input) from server errors (transaction failure, etc.)
- Be importable as a Python package independent of the REST API, so that scripts, tests, and the existing CRMBuilder application can use it directly without going through HTTP

### 4.3 REST API (FastAPI)

The REST API must:

- Expose CRUD endpoints for every entity type (create, read, list, update, delete)
- Expose query endpoints supporting the tiered session orientation protocol from DEC-011: retrieve current charter, retrieve current status, retrieve recent N sessions, retrieve a decision by identifier, retrieve all decisions referenced by a given session
- Expose reference-traversal endpoints: given an entity type and identifier, return all references where the entity is the source; given an entity type and identifier, return all references where the entity is the target; given an entity type and identifier, return both directions in a single response
- Return JSON in a consistent envelope (record body, metadata, errors) for every endpoint
- Provide an OpenAPI specification at a stable path (FastAPI's `/docs` and `/openapi.json`) for client tooling and for the MCP server's tool definitions
- Run as a standalone process; no integration with the existing CRMBuilder PySide6 application is required at this stage

### 4.4 MCP server

The MCP server must:

- Expose MCP tools that map onto the REST API endpoints, providing at minimum: create / read / update / delete for each entity type, the orientation queries listed in 4.3, and reference traversal in both directions
- Translate MCP tool calls into REST API HTTP requests; perform no business logic, validation, or direct database access
- Support local stdio transport for development and testing (Claude Desktop, Claude Code, or local MCP clients)
- Be capable of running under a hosted transport for Claude.ai access once a deployment target is decided (the deployment decision itself is out of scope for this PRD)
- Provide tool descriptions sufficient for Claude to select the correct tool from a natural-language session request without additional documentation

### 4.5 JSON export hook

The hook must:

- Generate, on every successful database write, a directory tree of JSON files representing the current database state
- Produce files that are human-readable (stable key ordering, consistent indentation) and git-diffable (small, predictable diffs for small database changes)
- Place files at a known repository location so they can be committed alongside other v2 artifacts. Proposed location: `PRDs/product/crmbuilder-v2/db-export/` (so exports appear next to existing v2 governance artifacts). Final location is Claude Code's call.
- Generate transactionally with the database write — if export generation fails, the database write rolls back

### 4.6 Migration of bootstrap content

Migration must:

- Successfully import the current contents of `PRDs/product/crmbuilder-v2/charter.md`, `decisions.md`, `sessions.md`, and `status.md` into the database with full structural fidelity
- Be deterministic and re-runnable without producing duplicate records (idempotent on the same source files)
- Produce a post-migration database state where the session orientation queries from 4.3 return content equivalent to what the markdown files currently contain
- Preserve all existing identifiers (DEC-001 through DEC-011, SES-001) — migration does not renumber records
- Explicitly create the cross-references implicit in the markdown content (for example: SES-001 → "decided_in" relationship to each of DEC-001 through DEC-011)
- Result, after migration is confirmed operational, in the four markdown source files being removed from the v2 home directory in the same commit that lands the migrated state; the deleted files remain recoverable through git history

---

## 5. Data Model Requirements

Column-by-column types, exact index choices beyond those specified, and ORM patterns are Claude Code's decisions. This section specifies what each entity must support, not how the table is declared.

### 5.1 Project-management entities

#### Charter

Singleton document representing the v2 project charter. One current row plus historical versions. Each version contains the structured sections of the charter (scope, in-scope, out-of-scope, architectural foundations, current state, open planning items). Section structure may be modeled as a JSON column or as separate columns; either is acceptable as long as section-level edits are supported through the API.

#### Status

Singleton document representing the current v2 project status. One current row plus historical versions. Captures: phase, sub-step, in-flight work, blockers, pending lists by category (immediate, planning, build), and reading-order guidance for new sessions.

#### Decisions

Append-mostly table of decision records. Each row corresponds to one DEC-NNN. Required fields:

- Identifier (DEC-NNN string, unique)
- Title
- Date
- Status (controlled vocabulary: Active, Superseded, Withdrawn)
- Context, Decision, Rationale, Alternatives Considered, Consequences (text fields; structure visible in DEC-001 through DEC-011)
- Supersedes (optional reference to a previous decision)
- Superseded by (optional reference to a later decision)

Decisions may be edited (e.g., to update Status to Superseded), but the historical content of a superseded decision is preserved through the change log.

#### Sessions

Append-only log of session records. Each row corresponds to one SES-NNN. Required fields:

- Identifier (SES-NNN string, unique)
- Title
- Date
- Status (e.g., Complete, In Progress)
- Conversation reference (free text)
- Topics covered (text)
- Summary (text)
- Decisions made (set of references to decision records)
- Artifacts produced (text)
- In-flight at session end (text)

#### Risks

Risk register, supporting the planning dimension #7 (risk register) work. Required fields:

- Identifier
- Title
- Description
- Probability (controlled vocabulary: Low, Medium, High)
- Impact (controlled vocabulary: Low, Medium, High)
- Response plan
- Status (controlled vocabulary: Open, Mitigated, Accepted, Closed)

This table is empty at v0.1 launch (no risks have yet been registered). It is required for completeness so that adding risks does not require a follow-on schema migration.

#### Planning items / open work

Generic structured table for open planning questions and work items not yet tied to a specific entity. Holds the four open planning dimensions currently named in the charter (#5 pacing, #6 division of labor, #7 risk register, #8 exit criteria) and any other open items registered in subsequent sessions. Required fields:

- Identifier
- Title
- Type (controlled vocabulary; initial values: `planning_dimension`, `open_question`, `pending_work`)
- Description
- Status (controlled vocabulary: Open, Resolved, Deferred)
- Resolution reference (optional reference to the decision or other artifact that resolved the item)

#### Topics (per DEC-007 — topics table for free-floating concepts)

Lightweight table for free-floating concepts that are not typed entities (architectural ideas, design discussions, planning topics). Required fields per DEC-007:

- Identifier
- Name
- Description
- Parent topic (optional reference, supports hierarchy)
- Created at

Methodology entities (personas, fields, requirements, etc., when they are added) do NOT live in the topics table — they remain first-class typed records.

### 5.2 References table (per DEC-006 — universal references pattern)

Single polymorphic table storing all cross-entity references. Required columns per DEC-006:

- `source_type` (controlled vocabulary of entity type names)
- `source_id` (matches the source entity's identifier)
- `target_type` (controlled vocabulary of entity type names)
- `target_id` (matches the target entity's identifier)
- `relationship` (controlled vocabulary; initial values: `is_about`, `supersedes`, `decided_in`, `affects`, `covers`, `blocks`, `references`)
- `created_at`

Required indexes for query performance: `(source_type, source_id)` and `(target_type, target_id)`.

The relationship vocabulary is its own design artifact and grows deliberately as new use cases are encountered. The access layer must reject `relationship` values that are not in the current vocabulary.

### 5.3 Change log

Every mutating operation (insert, update, delete) on any entity must produce a change-log entry. Required fields:

- Timestamp
- Entity type
- Entity identifier
- Operation (controlled vocabulary: `insert`, `update`, `delete`)
- Actor (controlled vocabulary; initial values: `claude_session`, `migration`, `manual` — full attribution depends on authentication, which is post-v0.1)
- Diff or before/after representation sufficient to reconstruct the change

The change log is append-only.

### 5.4 Versioning

Charter and Status are versioned: every update produces a new version row, with the latest row identified by a flag, version-number column, or equivalent mechanism. Other entities (Decisions, Sessions, Risks, Planning items, Topics, References) are not versioned per row; their history is recoverable through the change log.

### 5.5 Schema validation rules

The access layer must enforce:

- Identifier uniqueness within each entity type
- Controlled-vocabulary values for the fields enumerated above
- Foreign key integrity where foreign-key columns exist
- `relationship` values in the references table must match the controlled vocabulary
- `source_type` and `target_type` values in the references table must match defined entity types

---

## 6. Non-Functional Requirements

### 6.1 Tech stack (per DEC-005)

- Language: Python 3.11 or later
- Database: SQLite (file-based, single file per v2 instance)
- Web framework: FastAPI
- ORM or query layer: Claude Code's choice (SQLAlchemy, raw SQL with a thin wrapper, or other) as long as the access-layer abstraction in section 4.2 is preserved
- MCP framework: Claude Code's choice from current Python MCP server libraries
- JSON serialization: standard library or equivalent

### 6.2 Validation

All business validation lives in the access layer, not in the REST API or MCP server. Higher layers may perform format and parsing checks (is this a valid JSON request body), but business validation (controlled vocabularies, identifier uniqueness, referential integrity) is enforced at the access-layer boundary.

### 6.3 Transactions

Every API operation that mutates the database must be transactional. Transaction scope must encompass both the database write and the JSON-export write. Failure in either rolls back both.

### 6.4 Testing

The deliverable must include:

- Unit tests for the access layer covering CRUD and validation for every entity type
- Integration tests for the REST API covering every endpoint, including error cases
- A smoke test for the MCP server confirming tool calls translate to REST calls correctly
- A migration test confirming bootstrap markdown imports correctly into the database and round-trips cleanly through JSON export

Test framework choice (pytest, unittest, etc.) is Claude Code's call.

### 6.5 Repository organization

All v2 storage system code lives at a single path within the crmbuilder repository, separate from the existing v1 codebase, honoring DEC-003 (v1/v2 boundary tracking). Proposed path: `crmbuilder-v2/` at the repository root, with subdirectories for the access layer, REST API, MCP server, schema migrations, JSON exports, and tests. Final organization is Claude Code's call.

PRD documents (this PRD and any companion material) remain in `PRDs/product/crmbuilder-v2/`.

### 6.6 Configuration

The system must accept configuration for at minimum:

- Database file path
- JSON-export directory path
- REST API host and port
- MCP server transport (stdio, etc.)

Configuration may be via environment variables, a config file, command-line flags, or a combination. Defaults must be provided that allow the system to start in single-user local mode without further configuration.

---

## 7. Migration Requirements

The bootstrap markdown content currently in `PRDs/product/crmbuilder-v2/` must be migrated into the v2 database as part of the v0.1 deliverable. Specifically:

| Source file | Target table(s) | Notes |
|-------------|-----------------|-------|
| `charter.md` | charter (singleton) | Section structure preserved; the markdown change-log block becomes the charter's version history |
| `decisions.md` | decisions (eleven rows: DEC-001 through DEC-011) | Each decision parsed into a row using the structured fields specified in section 5.1 |
| `sessions.md` | sessions (one row: SES-001) | The single session record parsed into the session row |
| `status.md` | status (singleton) | Section structure preserved; the markdown change-log block becomes the status version history |

After successful migration:

- The four markdown files are deleted from the v2 home directory in the same commit that lands the migrated state
- The deleted files remain recoverable through git history
- All cross-references implicit in the markdown (such as SES-001 referencing DEC-001 through DEC-011 via a `decided_in` relationship) are explicitly created in the references table during migration

Migration must be idempotent: re-running it against an already-migrated database must not produce duplicate records or lose data.

---

## 8. Acceptance Criteria

The v0.1 storage system is "functioning" — and v2 work transitions from markdown-based to database-based — when all of the following hold:

1. **Schema deployed.** SQLite database file exists with all tables from section 5, indexes in place, controlled vocabularies seeded.
2. **Access layer operational.** Every CRUD operation for every entity type works through the Python access layer with validation enforced.
3. **REST API operational.** Every endpoint specified in section 4.3 returns correct responses for valid requests and structured errors for invalid requests. The OpenAPI specification is accessible at the documented path.
4. **MCP server operational.** Claude can read and write the database via MCP tool calls, at least via local stdio transport. The full set of tools specified in section 4.4 is exposed.
5. **JSON exports generated.** On every database write, the export directory updates atomically with the database. Diffs in the export directory match diffs in the database.
6. **Bootstrap content migrated.** Charter, decisions, sessions, and status from the markdown files are present in the database and queryable through the API. Markdown files are removed from the v2 home directory. Git history shows the migration commit.
7. **Test suite passing.** Unit, integration, and migration tests all pass.
8. **Session orientation works.** The Tier 2 reads specified by DEC-011 (current charter, current status, recent sessions, referenced decisions) succeed via MCP tool calls and return content equivalent to the pre-migration markdown.

---

## 9. Open Questions / Deferred Decisions

These items are not blockers for v0.1 implementation but require resolution before the system reaches its full intended use:

- **Hosting and deployment target.** Where the MCP server runs in production (i.e., where Claude.ai reaches it from). Options include hosted VPS, tunneled local server, or dedicated infrastructure. Not required for the codebase deliverable; required before Claude.ai sessions can use the system.
- **Authentication.** Single-user development is assumed for v0.1. Productization will require authentication on the REST API and corresponding identity propagation through the MCP server.
- **Methodology entity schema.** Personas, entities, fields, processes, requirements, and so on are deferred to Step 0 follow-on work. The references table and topics table are designed to accommodate them without schema changes.
- **Renderer design.** Word, YAML, and test-case generation from the database (per DEC-008 — renders, not authored copies) is a separate workstream. The REST API's read endpoints must be sufficient for renderers to consume, but renderer design is not constrained by this PRD.
- **Schema migration strategy beyond v0.1.** As entities are added (especially methodology entities), the schema will evolve. Choice of migration tool (Alembic or equivalent) is left to Claude Code, but the choice should be made deliberately during the v0.1 build and documented.
- **Backup and disaster recovery.** Out of scope for v0.1; the SQLite file plus git-committed JSON exports provide a functional backup. Productization will require formal recovery procedures.

---

## 10. References

This PRD is grounded in the following documents in `PRDs/product/crmbuilder-v2/`:

- `charter.md` — CRMBuilder v2 Charter v0.1
- `decisions.md` — Decisions log; specific decisions referenced throughout this PRD: DEC-003 (v1/v2 boundary tracking), DEC-004 (database as source of truth), DEC-005 (storage stack), DEC-006 (universal references pattern), DEC-007 (topics table), DEC-008 (renders, not authored copies), DEC-010 (CBM migration order), DEC-011 (session orientation protocol)
- `sessions.md` — Session records; SES-001 is the planning session that produced the decisions above
- `status.md` — Current project status and v1/v2/transition inventory

External standard referenced:

- Model Context Protocol (MCP) specification — defines the tool-call protocol the MCP server implements

---

## 11. Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-07-26 | Initial draft for review. Specifies schema, access layer, REST API, MCP server, JSON export hook, and migration of bootstrap content. Acceptance criteria define a functioning system. Methodology entities, hosting, authentication, and renderers explicitly deferred. |
