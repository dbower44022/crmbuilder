# CLAUDE-CODE-PROMPT-v2-C-catalog-ingestion

**Last Updated:** 05-09-26 15:15
**Series:** v2-C
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/catalog-ingestion-PRD-v0.1.md` (v0.2, approved)
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/catalog-ingestion-implementation-plan.md` (v0.1)

## Purpose

Build the CRMBuilder v2 catalog ingestion subsystem per the companion PRD and implementation plan. Unlike the v2-B storage system build, the implementation plan is already drafted and approved — your job is to execute it, not to redraft it.

This is the third concrete execution step in the v2 series. The v2-A bootstrap prompt landed the planning artifacts as markdown files. The v2-B storage system prompt built the storage stack and migrated those markdown files into the database. This prompt brings the base entity catalog (42 entries, 415 attributes, ~5,700 rows total) into the database and decommissions the YAML files that currently hold it.

After this build lands, the catalog is editable through V2's REST API and consumable by V2's MCP server. Methodology entity schema work (Step 0 follow-on proper) can then proceed against a populated catalog.

## Project context

CRMBuilder v2 is the next major iteration of CRMBuilder. The base entity catalog is V2's foundational reference data — 42 catalog entries across 5 tiers, with 415 attributes carrying per-system mappings, common synonyms, and full cross-system api_name resolution. The catalog was authored in YAML during a research process; it now needs to live in V2's database as authoritative data (per DEC-004) so V2's UI, API, and MCP server can serve the three runtime use cases (reference library, cross-system mapper, gap checker) without external file dependencies.

The catalog YAML files live at `PRDs/product/crmbuilder-v2/research/base-entity-catalog/`. The companion documents `base-entity-catalog-research.md` and `entity-system-map.yaml` are cross-cutting deliverables generated from the catalog. All three are decommissioned after migration — recoverable through git history but no longer the source of truth.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set:
   - `git config user.name` should return `Doug`
   - `git config user.email` should return `doug@dougbower.com`
   - If not set, configure: `git config user.name "Doug"` and `git config user.email "doug@dougbower.com"`.
4. Pull latest from origin: `git pull --rebase origin main`.
5. Confirm V2 storage system is in place: the directory you set in v2-B (e.g., `crmbuilder-v2/` or similar) should exist with the storage stack operational. If it doesn't, stop — this build depends on v2-B being complete.

## Reading order

Before producing any code, read the following in order:

1. `crmbuilder/CLAUDE.md` — universal entry point.
2. `PRDs/product/crmbuilder-v2/catalog-ingestion-PRD-v0.1.md` — the requirements you are implementing (v0.2, approved). Particular attention to section 4 (schema specification), section 5 (ingestion mechanics), section 6 (API surface), and section 8 (acceptance criteria).
3. `PRDs/product/crmbuilder-v2/catalog-ingestion-implementation-plan.md` — the build plan you are executing. This is your primary execution guide. Particular attention to section 5 (commit sequence), section 6 (test fixture strategy), section 7 (acceptance criteria → test file mapping), and section 9 (build validation gate).
4. `PRDs/product/crmbuilder-v2/research/base-entity-catalog/README.md` — schema and conventions documentation for the catalog YAML files. Includes the naming conventions section that the loader must understand.
5. `PRDs/product/crmbuilder-v2/research/base-entity-catalog/account.yaml` — read one example YAML to understand the structure the loader will parse. (You don't need to read all 42; one is enough to see the schema in concrete form.)
6. The current state of database-resident governance: the decisions table (looking for DEC-004, DEC-005, DEC-006, DEC-008 in particular) and the most recent session record.

## Workflow

### Step 1 — Confirm understanding

Before writing code, post a brief summary to Doug covering:

- Your understanding of the build scope (the 8 commits A-H from implementation plan section 5)
- Any ambiguities you encountered in the PRD or implementation plan that need clarification
- Any deviations from the plan you want to propose, with rationale

If everything is clear and you have no proposed deviations, state that explicitly and ask Doug for the go-ahead. Wait for confirmation before proceeding.

### Step 2 — Update status

Update database-resident status to reflect that the catalog ingestion build is in progress. The exact mechanism depends on V2's access layer (likely a direct DB update via the access layer or an `alembic-shell`-style CLI). Set:

- Phase / Active Work entry: "Catalog ingestion v0.1 build in progress"
- Update `Last Updated` per V2's status conventions

This step uses V2's database directly since the storage system is operational. No markdown file edits.

### Step 3 — Execute the build

Execute the 8 commits A-H from implementation plan section 5, in order. Each commit lands a coherent slice; do not skip ahead or merge multiple commits unless explicitly justified.

**Commit conventions:**

- All commit messages use the `v2:` prefix (e.g., `v2: catalog schema migration`, `v2: catalog loader helper module`, `v2: catalog data migration + YAML decommissioning`)
- Each commit includes the test coverage for that commit's code (no commits without tests, except trivial ones)
- Push to `origin/main` after each commit or as a batch at the end of step 3, your choice

**Per the implementation plan:**

- Use the agreed file paths in section 3 of the implementation plan. If V2's actual layout differs, mirror the actual convention and document the deviation.
- Use the agreed library choices in section 2 (Python 3.12+, SQLAlchemy 2.0, Alembic, FastAPI, Pydantic v2, official mcp SDK, PyYAML). No new dependencies should be introduced.
- Use the agreed Pydantic model naming in section 4 (`CatalogEntityRead` / `Create` / `Update` / `Patch` family). If V2 uses different suffixes, mirror them.
- Use the agreed access layer split in section 3 (`crmbuilder_v2/storage/access/catalog/` as a package with `read.py` / `write.py` / `exports.py`).

**Commit C is the critical one** — it lands the data migration and removes the catalog YAML directory plus the two cross-cutting deliverables from the working tree (via `git rm`). After commit C, the migration has run, the database is populated, and the YAML files are gone. Treat this commit with extra care:

- Run the migration against a fresh database first (the validation gate in section 9 of the implementation plan)
- Confirm row counts match expected (42 entities, 415 attributes, 2,905 presence cells)
- Confirm subclass FKs resolve, including the donation-major-gift → donation.donationType discriminator (fixed in catalog v0.10)
- Only then run the `git rm` of YAML files

If commit C fails or produces unexpected results, stop and report to Doug rather than proceeding with the YAML removal.

**Honor while building:**

- Do not modify v1 code (`espo_impl/`, `automation/`), v1 PRDs, or methodology guides under `PRDs/process/`.
- Do not modify CBM repository content.
- The PRD's acceptance criteria (section 8) define done. Cross-check progress against them.
- The implementation plan's build validation gate (section 9) is the final verification. Run it after commit H lands.

### Step 4 — Close out

After all 8 commits land and the build validation gate passes:

- Append a new session record (next available SES-NNN) to the database, summarizing the build. Cover: build scope, commits landed, any deviations from plan, any new decisions made during execution that warrant DEC-NNN entries, any in-flight items or known follow-ons (e.g., the methodology entity schema build that comes next).
- Update database-resident status to reflect catalog ingestion v0.1 complete. Move the entry from Active Work to Completed; update Pending if any new items surfaced.
- Add new DEC-NNN entries to the decisions table for any architectural decisions made during execution that aren't already covered by DEC-004 / 005 / 006 / 008 or the eight resolved decisions documented in the PRD's section 10.
- Push all remaining commits to origin/main.

### Step 5 — Report

Produce a completion report (in your final response to Doug, not as a committed file unless he asks) covering:

- **Acceptance criteria** — pass/fail for each of the eleven criteria in PRD section 8, with brief evidence (e.g., test name, row count, file count).
- **Build validation gate** — pass/fail for each of the seven steps in implementation plan section 9, with output snippets.
- **Implementation choices** — anything you chose differently from what the plan specified, and why.
- **Deviations from plan** — anything that diverged from the implementation plan, with rationale.
- **New decisions** — any architectural decisions made during execution that warrant DEC-NNN entries (with context, decision, rationale, alternatives considered, consequences). These should have been added to the database in step 4.
- **Deferred items** — anything you elected to defer (e.g., the catalog editing UI is explicitly deferred to a separate workstream).
- **Operational notes for Doug** — how to query the catalog via REST locally, how to invoke the MCP tools, where the JSON exports live, how to verify the YAML files are decommissioned (`git ls-files PRDs/product/crmbuilder-v2/research/base-entity-catalog/` returns empty).

## Constraints

- **No edits to v1 code or methodology.** v2 work is strictly additive to v1 per DEC-003. The existing CRMBuilder PySide6 application, automation pipeline, and methodology guides under `PRDs/process/` are not modified.
- **No CBM content migration.** Catalog ingestion does not touch CBM repository content.
- **No new external service dependencies.** All capabilities are covered by V2's existing dependency set per implementation plan section 2.
- **No catalog editing UI in this build.** REST endpoints exist; the V2 web UI that consumes them is a separate workstream (parallel to existing decisions / planning-items UIs). Stay within the PRD scope.
- **No methodology entity schema work in this build.** Catalog ingestion exposes integration affordances (UUID primary keys, universal references vocabulary, stable catalog_id identifiers); the methodology entity schema itself is a separate workstream that follows this build.
- **Stop and ask if uncertain.** If the PRD or implementation plan leaves a substantive question unresolved, stop and surface it rather than choosing silently.
- **Commit C requires extra care.** Validate row counts and FK resolution before removing the YAML files. If anything looks off, stop and report rather than committing the removal.
