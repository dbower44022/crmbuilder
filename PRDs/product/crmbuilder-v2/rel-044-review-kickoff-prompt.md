# Kickoff — Review REL-044 (Postgres flip — dogfood store cutover)

**Paste this into a fresh Claude Code session rooted at `~/Dropbox/Projects/crmbuilder`.**

Your task is to **review REL-044** and report — is it buildable, already delivered, or genuinely open? — and recommend a disposition. This is a *review*, not a build; do not change governance or code unless Doug asks after seeing your findings.

## What REL-044 is (from the live cloud DB, 2026-07-02)

- **REL-044 — "Postgres flip — dogfood store cutover"** — `preliminary_planning`, mode `manual`, **not frozen**. Scopes **PRJ-081** (`planned`).
- **One PI — PI-365** (`Draft`, mode **`interactive`**, implements **REQ-425** confirmed): *"Cut the live dogfood store over to local Docker Postgres."*
  - PI-365 detail: stand up docker-compose Postgres (PG16, `:55432`), install psycopg, bootstrap the PG schema, run `sqlite_to_postgres.migrate()`, set `CRMBUILDER_V2_DATABASE_URL` durably in `crmbuilder.env`, restart API/UI/MCP on Postgres, verify record counts + concurrent-write safety.
  - **REQ-425 — "Concurrency-safe live store for multi-agent writes":** the live store was a single SQLite file written by the API and many parallel agent runtimes at once, and that concurrency **corrupts** it. Acceptance: *many runtimes writing at once do not corrupt it; existing data migrated without loss; and the API, agents, and desktop all use the concurrency-safe store.*

## The central question to answer

**Has REQ-425 already been satisfied by the 2026-07-01 cloud Postgres cutover — making REL-044 a close-as-delivered, not a build?** There is a direct precedent: **REL-012 ("Multi-User & Concurrency Safety") was closed as delivered** on 07-01 because Postgres + auth went live in the cloud (see memory `project_cloud_deployment_v2`; that closure is SES-336/CNV-292/DEC-888). REL-044 targets the *same underlying problem* (SQLite concurrency corruption) with a *different, pre-cloud mechanism* (a **local** docker PG). The live store is now **DO Managed Postgres** in the cloud, data was migrated intact (pg_dump→pg_restore, exact row-count match), and the API runs on it.

So the likely finding is "substantively delivered by the cloud cutover," **but verify each acceptance clause before concluding** — don't assume:

1. **No-corruption / concurrency-safe engine** — the cloud store is Managed Postgres. ✅ almost certainly met. Confirm the API + governance writes go to cloud PG.
2. **Data migrated without loss** — the cloud migration validated exact row counts. Confirm.
3. **"The API, agents, and desktop all use the concurrency-safe store"** — this is the clause most worth scrutiny:
   - **API** — cloud, on Managed PG. ✅
   - **Desktop** — PI-386 remote mode points it at `https://api.crmbuilder.ai`. Confirm.
   - **Agents** — *does the parallel ADO/fleet actually write to the concurrency-safe (cloud PG) store, or is there still a local SQLite in play?* The repo shows recent **`crmbuilder-v2/data/v2-unified.db.corrupt-*`** files (local SQLite corruption). If the agent runtimes still touch a local SQLite in their worktrees, the corruption risk REQ-425 targets may **persist locally** even though the cloud is safe. This is the crux — investigate it, don't hand-wave it.
4. **The `local docker PG :55432` mechanism in PI-365** is now largely moot — the memory notes Doug's local docker PG (`:55432`) is a **stale snapshot** as of the cloud migration; the real cutover went to cloud Managed PG. Note this method/intent divergence.

## How to orient and gather facts

- **Source of truth = the cloud** (`https://api.crmbuilder.ai`, auth ON). You won't have a bearer token; read the live store by SSH to the droplet and using the access layer directly (RBAC is enforced at the API layer, not the repositories):
  ```
  ssh -i ~/.ssh/id_ed25519 root@138.197.72.15
  cd /opt/crmbuilder && QT_QPA_PLATFORM=offscreen .venv/bin/python3 -   # pipe a script over stdin
  ```
  Wrap in `with session_scope() as s:`; tables are prefixed for some entities (`release_*`, `project_*`, `requirement_*`) and unprefixed for others (`planning_items`, `decisions`, `refs` use `identifier`/`status`). Read `releases`/`projects`/`planning_items`/`requirements` and the `project_belongs_to_release` / `planning_item_belongs_to_project` / `planning_item_implements_requirement` edges in `refs`.
- Read the memories `project_cloud_deployment_v2`, `project_outstanding_work_release_plan`, and the REL-012 closure precedent. Also check the git-tracked `crmbuilder-v2/data/*.corrupt-*` artifacts for the local-SQLite-corruption evidence.

## Deliverable

A review in the same shape used for REL-012/013/016/039:
- Release status line + the PI/requirement table.
- A verdict: **close-as-delivered** (REQ-425 met by the cloud cutover), **partially open** (e.g. cloud is safe but local agent runtimes still risk SQLite corruption → a residual concurrency-safety gap worth its own requirement), or **genuinely open**.
- If close-as-delivered: outline the close-out path (a build-closure conversation with a `resolves` edge to PI-365 → flips it Resolved; then PRJ-081 → `complete` and REL-044 → `delivered_off_pipeline` — both irreversible), **but leave the decision to Doug.**
- Note that **PI-365 is `interactive`** — even if not delivered, it's human-executed ops (ADO-invisible), never an agent build.

## Do not

- Do not run migrations, cut over any store, or write governance during the review.
- Do not close REL-044 or resolve PI-365 without Doug's explicit go-ahead — the terminal transitions are irreversible.
