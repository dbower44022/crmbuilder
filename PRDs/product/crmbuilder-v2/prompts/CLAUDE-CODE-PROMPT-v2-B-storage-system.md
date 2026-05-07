# CLAUDE-CODE-PROMPT-v2-B-storage-system

**Last Updated:** 05-07-26 14:45
**Series:** v2-B
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/storage-system-PRD-v0.1.md`

## Purpose

Build the CRMBuilder v2 storage system per the companion PRD. The PRD specifies what a functioning system must do; you (Claude Code) produce an implementation plan from those requirements and execute it. Single pass or staged delivery is your call, as long as the acceptance criteria in PRD section 8 are met.

This prompt is the second concrete execution step in the v2 series. The v2-A bootstrap prompt landed the planning artifacts as markdown files. This prompt builds the system that replaces those markdown files as the source of truth for v2.

## Project context

CRMBuilder v2 is the next major iteration of CRMBuilder. Per DEC-004 (Database as source of truth for all v2 artifacts), v2 makes a structured database the source of truth for all v2 artifacts — both project-management artifacts (charter, decisions, sessions, status, topics, references) and methodology artifacts (personas, entities, fields, processes, requirements, etc., added in follow-on work). The storage system you are building is the foundation that makes that inversion real.

The PRD's scope is explicit: project-management entities only for v0.1. Methodology entities, renderers, application integration, hosting, and authentication are deferred to follow-on work and are out of scope for this build.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set:
   - `git config user.name` should return `Doug`
   - `git config user.email` should return `doug@dougbower.com`
   - If not set, configure: `git config user.name "Doug"` and `git config user.email "doug@dougbower.com"`.
4. Pull latest from origin: `git pull --rebase origin main`.

## Reading order

Before producing any plan or code, read the following in order:

1. `crmbuilder/CLAUDE.md` — universal entry point.
2. `PRDs/product/crmbuilder-v2/charter.md` — project scope and architectural foundations.
3. `PRDs/product/crmbuilder-v2/status.md` — current state and v1/v2 inventory.
4. `PRDs/product/crmbuilder-v2/sessions.md` — SES-001, the planning record.
5. `PRDs/product/crmbuilder-v2/decisions.md` — all eleven decision records, with particular attention to:
   - DEC-003 (v1/v2 boundary tracking)
   - DEC-004 (database as source of truth)
   - DEC-005 (the four-layer storage stack — SQLite + access layer + REST API + MCP server)
   - DEC-006 (universal references pattern with controlled relationship vocabulary)
   - DEC-007 (topics table for free-floating concepts)
   - DEC-008 (renders, not authored copies)
   - DEC-011 (tiered session orientation protocol)
6. `PRDs/product/crmbuilder-v2/storage-system-PRD-v0.1.md` — the requirements you are implementing.

## Workflow

### Step 1 — Plan

Produce an implementation plan at `PRDs/product/crmbuilder-v2/storage-system-implementation-plan.md`. The plan must cover:

- **Build sequence** — the order in which schema, access layer, REST API, MCP server, JSON export, and migration are implemented and tested. Single pass or staged is your call; if staged, define each stage's exit criterion.
- **Repository layout** — final directory structure for v2 code (proposed in PRD section 6.5 is `crmbuilder-v2/` at the repo root; final structure is yours to set).
- **Implementation choices with rationale** — ORM or query layer, MCP framework, schema migration tool, test framework. State the choice and why.
- **Open questions encountered while reading the PRD** — anything ambiguous, contradictory, or under-specified. Surface these for Doug's attention before executing.
- **Milestones** — checkpoints at which acceptance-criteria progress can be reviewed.

Commit the plan before starting code. Use a `v2:` prefix on the commit message.

If the plan surfaces blockers or open questions you can't resolve from the PRD and the v2 governance docs, stop and report to Doug rather than choosing arbitrarily.

### Step 2 — Update status

Before starting code, update `PRDs/product/crmbuilder-v2/status.md` to reflect that the v0.1 build is in progress. Update the `Last Updated` timestamp (MM-DD-YY HH:MM format), update Phase / Active Work / Pending sections, and add a Change Log entry.

This update is captured in markdown because the migration step has not yet run. The migration in step 4 will pull this status update (and any others made along the way) into the database.

### Step 3 — Execute

Build the system per your plan. Honor the following while building:

- Commit incrementally with `v2:` prefix and descriptive messages (e.g., `v2: schema for project-management entities`, `v2: access-layer CRUD for decisions`, `v2: FastAPI endpoints for charter and status`).
- All v2 code lives at the path you defined in step 1, separate from the existing v1 codebase, per DEC-003.
- Do not modify v1 code (`espo_impl/`, `automation/`), v1 PRDs, or methodology guides under `PRDs/process/`.
- Do not modify CBM repository content.
- The PRD's acceptance criteria (section 8) define done. Cross-check progress against them.

### Step 4 — Migrate

Run the migration of bootstrap content per PRD section 7. Specifically:

- Import `charter.md`, `decisions.md` (DEC-001 through DEC-011), `sessions.md` (SES-001), and `status.md` into the database.
- Create the cross-references implicit in the markdown (e.g., SES-001 has a `decided_in` relationship to each of DEC-001 through DEC-011).
- Verify migration is idempotent (running it twice produces the same database state).
- After migration is verified, delete the four bootstrap markdown files from `PRDs/product/crmbuilder-v2/` in the same commit that lands the migrated state. Files remain recoverable through git history.

### Step 5 — Close out

After acceptance criteria pass:

- Append a session record (SES-002 — "v0.1 Storage System Build") to the database, summarizing the build, listing decisions made during execution that warrant new DEC-NNN entries, and noting any in-flight items or known follow-ons.
- Update database-resident status to reflect v0.1 complete and to update the Pending lists.
- Push all commits to origin/main.

### Step 6 — Report

Produce a completion report (in your final response to Doug, not as a committed file unless he asks) covering:

- **Acceptance criteria** — pass/fail for each of the eight criteria in PRD section 8.
- **Implementation choices** — what you chose for ORM, migration tool, test framework, repo layout, and why.
- **Deviations from plan** — anything that diverged from the implementation plan and the reason.
- **New decisions** — any architectural decisions made during execution that warrant DEC-NNN entries (with context, decision, rationale, alternatives considered, consequences). These should be added to the database as part of step 5.
- **Deferred items** — anything you elected to defer, with reason.
- **Operational notes for Doug** — how to start the system locally, how to point the MCP server at it from Claude Desktop or other clients, where the JSON exports live, where the database file lives.

## Constraints

- **No edits to v1 code or methodology.** v2 work is strictly additive to v1 per DEC-003. The existing CRMBuilder PySide6 application, automation pipeline, and methodology guides under `PRDs/process/` are not modified.
- **No CBM content migration.** Per PRD scope, no CBM (Cleveland Business Mentoring) content is migrated as part of v0.1. CBM migration is a separate workstream gated on v0.1 being operational.
- **No new external service dependencies.** Hosting and deployment are out of scope. Build the system to run locally; the deployment target is decided separately.
- **Stop and ask if uncertain.** If the PRD or governance docs leave a substantive question unresolved, stop and surface it rather than choosing silently.
