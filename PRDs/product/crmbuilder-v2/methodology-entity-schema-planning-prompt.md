# v2 Methodology Entity Schema — Planning Kickoff Prompt

> **SUPERSEDED 05-11-26** by `methodology-schema-workstream-plan.md`. **Do NOT use this as a kickoff prompt.** This document was drafted on 05-09-26 immediately after the catalog-ingestion planning conversation, before the methodology-entity-schema workstream had taken shape. It anticipated a single planning conversation producing one PRD, one implementation plan, and one Claude Code prompt covering a 15+-entity-type scope (project, master PRD, domain, sub-domain, persona, persona inventory, entity, entity inventory, field, process, process step, cross-domain service, requirement, manual config item, test specification). The actual workstream (SES-011, 05-11-26) redirected v0.4 from a UI-polish release into methodology entity schema design and scoped it to a **four-entity minimum-viable inventory** (domain, entity, process, crm_candidate) per **DEC-039**, with multi-tenancy settled as one-v2-instance-per-engagement, parent-prefix field naming per **DEC-046**, and source-first relationship-kind naming per **DEC-048**. The per-entity schemas live at `methodology-schema-specs/{domain,entity,process,crm_candidate}.md`; the integrating release PRD is `ui-PRD-v0.4.md`; the six build prompts are at `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-{A..F}-*.md`. The 15+ types this prompt named have been split: four are in scope for v0.4, the rest are deferred to v0.5+ as PI-003 / PI-004 / PI-005. **Read `methodology-schema-workstream-plan.md` first** for the canonical workstream frame. Retained here for history.

**Last Updated:** 05-09-26 17:00 (content frozen at supersession; the file body below preserves the original kickoff prompt as written)
**Purpose:** Seed prompt for a new Claude.ai conversation that plans the methodology entity schema for CRMBuilder v2.
**Predecessor:** Catalog ingestion (v2-C) — executed 05-09-26; 9 commits landed, 11/11 acceptance criteria passed, catalog populated in v2.db at Alembic head 0005.

---

## The task

Plan the methodology entity schema for CRMBuilder v2. Drive a structured architectural discussion that produces three deliverables:

1. **`PRDs/product/crmbuilder-v2/methodology-entity-schema-PRD-v0.1.md`** — intent, scope, schema specification, API surface, integration with the catalog and with the existing storage stack, acceptance criteria, open questions. Same length and shape as `catalog-ingestion-PRD-v0.1.md`.
2. **`PRDs/product/crmbuilder-v2/methodology-entity-schema-implementation-plan.md`** — commit sequence with deliverables and acceptance gates per commit. Same shape as `catalog-ingestion-implementation-plan.md`.
3. **`PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-D-methodology-entity-schema.md`** — Claude Code execution prompt. Same shape as `CLAUDE-CODE-PROMPT-v2-C-catalog-ingestion.md`.

Cadence matches prior planning sessions: structured architectural discussion, one decision at a time, building toward the PRD first, then the implementation plan, then the execution prompt. The conversation that produces these deliverables will be captured as a session record at its close.

---

## What "methodology entity schema" means

V2's storage system holds three layers of data, in order from most general to most project-specific:

1. **Project-management entities** — charter, decisions, sessions, status, topics, references, planning items. Already built in v2-B.
2. **Base entity catalog** — 42 universal CRM concepts (Account, Contact, Activity, Donation, etc.) as research-grade reference data. Ready to execute via v2-C; ~5,700 rows once ingested.
3. **Methodology entities** — the working artifacts produced when running the methodology against a specific client. **This is what's being planned in this conversation.**

Methodology entities are the CRMBuilder methodology's working products: personas, domains, entities, fields, processes, process steps, cross-domain services, requirements, manual-config items, test specifications, and the inventories that organize them. Currently these live as dozens of .docx files in client repositories (the Cleveland Business Mentoring repository at `dbower44022/ClevelandBusinessMentoring` is the canonical reference — domain folders MN, MR, CR, FU). Methodology entity schema work means giving these their own tables in V2's database so they become editable through V2's UI, consumable by V2's renderers, and traceable back to the catalog they reference.

---

## Context — what's shipped or ready to ship

**v2 storage system** (built in v2-B): SQLite + Alembic + access layer + REST API + MCP server. Eight project-management entity types. Universal references pattern with controlled relationship vocabulary (DEC-006). Topics table for free-floating concepts (DEC-007). Renders, not authored copies (DEC-008). Soft-delete pattern.

**v2 UI** (built across v0.1, v0.2, v0.3): PySide6 desktop application with sidebar navigation, master/detail layout, cross-entity reference rendering, soft-delete handling, CRUD for the project-management entities.

**v2 catalog ingestion** (built in v2-C, executed 05-09-26): the 42-entity catalog migrated into the database. Ten new tables (`catalog_entity`, `catalog_attribute`, `catalog_*_presence`, `catalog_*_synonym`, `catalog_*_system`, `catalog_source`, `catalog_relationship`, `catalog_relationship_presence`). REST API + four read-only MCP tools. Catalog rows are referenceable as targets in DEC-006 universal references (new `target_type` values: `catalog_entity`, `catalog_attribute`). YAML files decommissioned post-migration. Three new architectural decisions surfaced during execution:

- **DEC-065** — catalog tables use V2's INTEGER PK + `catalog_id` TEXT convention, not UUID PKs. The stable-identifier affordance is satisfied by `catalog_id`; universal references target catalog rows by that string. **This affects how the methodology entity schema references catalog rows — pick either INTEGER FK to `catalog_entity.id` or TEXT FK to `catalog_entity.catalog_id` when designing the methodology integration.**
- **DEC-066** — catalog code mirrors V2's actual flat layout (`access/models.py`, `api/routers/`, `api/schemas.py`, `mcp_server/tools.py`, repo-level `migrations/`). One structural evolution: `access/repositories/catalog/` is a package (read/write/exports), justified by size. Pydantic models are request-only (`*In`); responses stay `Envelope[dict]` like every other V2 router. **The methodology entity schema should match the same flat layout unless a comparable size justification applies.**
- **DEC-067** — catalog writes do not emit `change_log` entries at v0.1; the flat before/after contract doesn't fit nested catalog rows. The types were still added to `ENTITY_TYPES` + the CHECK constraint so a future audit format needs no migration. Audit trail is the git-tracked JSON exports. **Methodology entity schema may face the same fit issue depending on its row shape — worth flagging during design.**

**Catalog-to-methodology integration pattern** (locked during v2-C planning): hybrid pattern — methodology entities carry an optional `primary_catalog_entity_id` foreign key (the strongest "this entity is based on catalog X" claim, nullable for custom entities with no catalog parallel) plus DEC-006 universal references for weak ties (e.g., "this entity also borrows attributes from catalog `engagement`"). Same pattern applies to methodology fields referencing catalog attributes. With DEC-065 in place, the FK can be INTEGER (to `catalog_entity.id`) or TEXT (to `catalog_entity.catalog_id`); the planning conversation decides which is the better fit for V2's existing patterns. The catalog already exposes the affordances (stable INTEGER and TEXT identifiers, universal references vocabulary); methodology entities will plug into them.

---

## Read this first

Before producing any plan or schema, read the following in order:

1. **`crmbuilder/CLAUDE.md`** — universal session-startup entry. Important.
2. **`PRDs/product/crmbuilder-v2/catalog-ingestion-PRD-v0.1.md`** (v0.2, approved). Particular attention to section 3 (architecture and integration, including the methodology integration sketch in 3.3) and section 4 (schema specification — for the pattern to follow).
3. **`PRDs/product/crmbuilder-v2/catalog-ingestion-implementation-plan.md`** — for the implementation pattern (commit sequence, model layout, test strategy) that this workstream should mirror.
4. **`PRDs/product/crmbuilder-v2/storage-system-PRD-v0.1.md`** — for the established storage patterns, including soft-delete, universal references, topics, audit columns, JSON export hook.
5. **`PRDs/product/crmbuilder-v2/db-export/decisions.json`** — read all DEC entries; pay particular attention to DEC-004 (DB as source of truth), DEC-005 (storage stack), DEC-006 (universal references), DEC-007 (topics), DEC-008 (renders not authored copies), DEC-011 (session orientation).
6. **`PRDs/product/crmbuilder-v2/db-export/sessions.json`** — read the most recent session records to understand current project state and what was just shipped.
7. **`PRDs/process/`** — the CRMBuilder methodology itself. Particular attention to:
   - The 12-phase Document Production Process structure
   - Interview methodology guides (`interviews/`) — what the methodology asks interviewers to capture about personas, entities, processes
   - Templates for Domain Overview, Entity PRDs, Process Definitions, Cross-Domain Services
8. **CBM repository content** (clone `dbower44022/ClevelandBusinessMentoring` separately, sparse): the live working example of methodology entity content. Read:
   - `PRDs/MN/` — Mentoring domain (most complete; 5 process docs + Domain PRD)
   - `PRDs/MR/` — Mentor Recruiting (5 process docs + Domain PRD)
   - `PRDs/CR/` — Client Recruiting (Partner, Marketing, Events, Reactivation sub-domains)
   - `PRDs/services/` — Cross-Domain Services placeholder
   - At least one Entity PRD (e.g., `PRDs/entities/Contact-v1.5.docx` if present) and one Process Definition
   - The pattern library specification at `PRDs/methodology-extension/`

---

## Candidate scope

The planning conversation should resolve at minimum the following decisions. The list is comprehensive but not exhaustive — additional design choices may surface during discussion.

**Entity inventory (which tables hold what):**

- **Project** — top-level container. A V2 instance currently manages one project (CBM); whether V2 supports multiple projects concurrently is a key early decision
- **Master PRD** — Level 1 PRD scoping the project (mission, vision, scope, success criteria)
- **Domain** — top-level container per project (CBM has 4: MN, MR, CR, FU)
- **Sub-domain** — within a domain (CR has Partner, Marketing, Events, Reactivation)
- **Persona** — role definition (Mentor, Client, SME, Partner Contact, Client Administrator)
- **Persona Inventory** — the canonical list per project
- **Entity** — domain entity (CBM has Contact, Account, Engagement, Session, Dues, MN-INTAKE, plus deferred Marketing Campaign, Event, etc.)
- **Entity Inventory** — the canonical list per project
- **Field** — attribute on an entity
- **Process** — workflow definition
- **Process Step** — individual step within a process
- **Cross-Domain Service** — Notes, Email, Calendar, Surveys (consumed across domains)
- **Requirement** — system-level requirement derived from processes
- **Manual Configuration Item** — items flagged for manual configuration during deployment (e.g., the saved-views / dupe-check / workflows gaps in EspoCRM YAML schema)
- **Test Specification** — test cases derived from processes and requirements

**Catalog integration mechanics:**

- How methodology entities reference catalog entities (FK + universal references per Decision 7 of catalog ingestion)
- How methodology fields reference catalog attributes
- What it means for a methodology entity to "derive from" the catalog vs "customize"

**Document Production Process integration:**

- How V2 represents the 12 phases (Master PRD → Entity Definition → Domain Overview → Cross-Domain Service Definition → Process Definition → Domain Reconciliation → Stakeholder Review → YAML Generation → CRM Selection → CRM Deployment → CRM Configuration → Verification)
- Phase tracking on methodology entities (what phase is this entity in?)
- Decision logs on methodology entities (per-entity decision history, similar to DEC entries but scoped to one entity)
- Version control on methodology entities (revision history, supersedes pattern)

**Renderer integration (DEC-008):**

- .docx generation from DB rows replaces hand-authored Word documents
- YAML generation for CRMBuilder app input (per the existing `app-yaml-schema.md` v1.2.1)
- JSON exports for git-diff via the existing DEC-008 hook
- Word documents become renders, not authored copies
- This is potentially the largest implementation effort; consider scoping renderers separately if they don't fit in v0.1

**Multi-project considerations:**

- Does V2 v0.1 of methodology entities support one project at a time, or many?
- If many: project_id FK on every methodology entity row; project switcher in UI
- If one: each V2 install hosts one client's methodology data
- Either is defensible; the choice has UI and migration implications

**Scope boundaries to settle:**

- Does this build include any UI work, or is the methodology workbench UI a separate workstream?
- Does this build include renderers (.docx, YAML, JSON), or do those come later?
- Does this build migrate any CBM content from .docx files into the database, or is migration a separate workstream?

---

## Working style

Per the user's preferences:

- Discuss one architectural decision at a time. Wait for explicit approval before moving to the next.
- Plain text discussion. Bold section headings acceptable. Avoid bullet-point overload.
- Terse approvals ("yes", "confirm", "a", "1 good") are sufficient — do not re-summarize or re-confirm.
- Once a plan or PRD is complete, execute without per-step confirmation.
- Propose document structures and outlines; the user approves before drafting begins.
- For repo work, use sparse checkout: `git clone --filter=blob:none --sparse https://oauth2:{PAT}@github.com/dbower44022/crmbuilder.git`, then `git sparse-checkout set --skip-checks CLAUDE.md PRDs/ crmbuilder-v2/`. Same for the CBM repo if examining live methodology content.
- Set git identity before first commit: `git config user.email "doug@dougbower.com"` and `git config user.name "Doug"`.
- Always `git pull --rebase origin main` before pushing.

The two-part test for what counts as consequential (and therefore stops the flow for explicit discussion) applies: (1) real downstream impact AND (2) at least two viable options producing meaningfully different outcomes. Both true → pause and present using the eight-element consequential decision template. Only #1 → decide and announce briefly. Neither → just decide.

---

## Governance — at conversation close

When the planning conversation closes, create a session record summarizing the conversation. Per the established convention:

- `conversation_reference`: descriptive text identifying the conversation by its deliverables. Example: `"Claude.ai planning conversation that produced methodology-entity-schema-PRD-v0.1.md, methodology-entity-schema-implementation-plan.md, and CLAUDE-CODE-PROMPT-v2-D-methodology-entity-schema.md under PRDs/product/crmbuilder-v2/."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of the architectural questions discussed.
- `artifacts_produced`: list of deliverables (PRD, plan, execution prompt).
- `in_flight_at_end`: anything explicitly deferred to follow-on work (e.g., methodology workbench UI, content migration from CBM .docx files, renderer implementation).

A subsequent session record captures the v0.1 build itself, once Claude Code executes the prompt.

---

## Pre-flight checks for the planning conversation

Before the first architectural question is discussed:

1. Confirm the storage API and v2 test suite are healthy. Catalog ingestion landed on 05-09-26; the full v2 suite should show 741 tests passing.
2. Confirm v2.db is at Alembic head 0005 with the catalog loaded. Quick check: `sqlite3 v2.db "SELECT COUNT(*) FROM catalog_entity"` should return 42.
3. Read items 1 through 8 in the "Read this first" section above.
4. Pull latest: `git pull --rebase origin main` (both crmbuilder and CBM repos if both are needed).

Note: a fresh-install `alembic upgrade head` against an empty database currently fails at revision 0004 with a "catalog directory not found" error — this is documented deferred behavior per PRD §9 (packaged seed dump for fresh-install seeding is out of scope at v0.1). If working against an empty database, expect this failure; the methodology entity schema planning conversation can proceed without it, since the schema design doesn't require a populated catalog.

---

## What this conversation does NOT do

- **Build any code.** The build happens later, via Claude Code execution of the prompt produced here.
- **Modify the catalog ingestion design.** Catalog is settled in v2-C and ready to execute. Methodology entity schema plans on top of it.
- **Modify the storage system.** Storage is settled. Methodology entity schema plans on top of it.
- **Build the methodology workbench UI.** That's likely a separate workstream after the schema lands.
- **Migrate CBM .docx content into the database.** Likely a separate workstream after the schema lands.
- **Plan beyond v0.1.** Future-version candidates are noted as deferred but not designed.

---

End of kickoff prompt.
