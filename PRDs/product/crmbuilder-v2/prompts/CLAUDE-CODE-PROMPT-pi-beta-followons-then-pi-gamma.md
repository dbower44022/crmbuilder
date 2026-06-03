# New session — finish PI-β follow-ons, then start PI-γ (RBAC)

You are Claude Code in `~/Dropbox/Projects/crmbuilder`. Two pieces of work, in
order: **Part A** clears the three loose ends PI-β intentionally deferred;
**Part B** starts PI-γ (identity/auth/RBAC). Do Part A first (small, fast), then
Part B (the real program).

## Orient first (Tier 1–2)

1. Read `CLAUDE.md`, especially the **PI-β "De-file + kill-snapshots"** note and
   the **PI-α Postgres** note under the Production Multi-Tenant API section.
2. Read the memory note `project_pi123_stage2_3_done.md` for the running state of
   PRJ-019 (PI-α/β done; PI-γ scoped).
3. Read `PRDs/product/crmbuilder-v2/pi-gamma-rbac-architecture.md` (PI-γ's design;
   governance PI-127) and skim `production-multitenant-api-architecture.md` D2/D3/D4.
4. **Current state (verify, don't trust):** `main` is at the PI-β build-closure
   (`14bedeb`, SES-155/DEC-378, PI-126 Resolved). One unified DB; the API resolves
   the engagement **per request from the `X-Engagement` header** (no marker, no
   meta DB, no db-export snapshots). `engagement_scoping_enabled` defaults True.
   Governance heads after the build-closure: next **SES-156 / DEC-379 / CNV-058**;
   PI-γ = **PI-127** (Draft) under **PRJ-019**.

> **GOTCHA — stale running services.** Doug's long-running `crmbuilder-v2-api`
> (8765), `crmbuilder-v2-ui`, and `crmbuilder-v2-mcp` may still be **pre-PI-β
> code** (check `GET /admin/version`: post-PI-β returns a single `schema` block,
> pre-PI-β returns `engagement_schema`/`meta_schema`). Before any governance apply
> or live testing, run the API on **current `main`** (restart it, or start a fresh
> one on an alternate port via `CRMBUILDER_V2_API_PORT=8766 crmbuilder-v2-api` and
> use `--base`). A pre-PI-β API still runs the old export hook and would
> regenerate the deleted `db-export/` tree.

> **GOTCHA — test clients must send `X-Engagement`.** The FastAPI `TestClient`
> runs the app in a portal thread that does not inherit the test thread's scope
> ContextVar, so every real-backend test client must send the header (`v2_env`
> seeds `ENG-001`). `apply_close_out.py` already does (`--engagement`, default
> CRMBUILDER).

---

## Part A — PI-β deferred follow-ons

These are small. Do them on a short-lived `pi-beta-followons` branch (code only;
governance/build-closure on `main` after merge, per the branch-work protocol), or
fold them into the front of the PI-γ branch — your call. Run `uv run pytest
tests/crmbuilder_v2/ -q` green before moving on.

**A1 — MCP per-engagement selection.** The MCP server's httpx client
(`mcp_server/server.py::build_server`) sends no `X-Engagement` header, so MCP tool
calls are unscoped (fine for the single-engagement dogfood since prod enforcement
is off, but wrong for multi-engagement). Give the MCP server a way to name the
engagement: a config/env default (e.g. `CRMBUILDER_V2_MCP_ENGAGEMENT`) the client
sends as `X-Engagement`, and/or a tool/argument to select it per session. Mirror
the desktop's model. (architecture §5 open question.)

**A2 — Drop the vestigial `engagement_export_dir` column + its UI.** PI-β left the
column (no schema change that slice). It is now dead: nothing reads it. Remove the
column (Alembic migration on the SQLite chain **and** the PG chain
`migrations/pg/` — see the PI-α dual-head note), the model field, the
`_validate_export_dir` validation, and its UI (the engagements panel
ExportDirWarningBand + `_update_export_dir_warning` + `focus_export_dir_field`, the
engagement-CRUD export-dir form field, the crud_dialog `_show_export_dir_error_dialog`
/ `_open_active_engagement_edit`, the connection-info "Export directory" row). This
is the schema-change pass PI-β deferred.

**A3 — Repoint `scripts/enumerate_commits.py`.** It defaults to reading the
last-ingested SHA from the **deleted** `db-export/commits.json` snapshot. Repoint
it at the live API (`GET /commits` / a by-repository query) instead of the file,
or drop the file default. (Its test passes today only because it takes the dir as
an arg and uses a temp dir.)

When A is done, author a small build-closure on `main` (a session + a DEC if any
real decisions were made; otherwise just a session recording the cleanup) per
`specifications/governance-recording-rules.md` — or fold these commits into PI-γ's
build-closure if you go straight into Part B on one branch.

---

## Part B — PI-γ (RBAC), PI-127

Build per `pi-gamma-rbac-architecture.md`. Branch `pi-gamma-rbac` already exists
but was cut **before PI-β** — **rebase it onto current `main` (`14bedeb`) first**,
because PI-β rewrote `scope_middleware`, `api/deps`, `cli.run_api`, and the
engagement-resolution model the principal layer composes with. Expect to
reconcile those files.

Design decisions already made (from the architecture doc / memory):
- **Principals + hashed `api_tokens`** (system/shared tables; add to **both**
  Alembic chains — SQLite `migrations/` and PG `migrations/pg/`).
- A **`resolve_principal` chokepoint** + bearer-token middleware, with a new
  `_active_principal` ContextVar mirroring `engagement_scope`. It sits
  **outermost** — engagement selection (the `X-Engagement` header) is validated
  against the principal's `allowed_engagements`.
- **Roles + per-engagement `role_assignments`** + a thin `require(permission)`
  guard composed with the existing row-level engagement filter.
- **ADO agents = scoped service principals** (the orchestrator mints a token at
  spawn; `claimed_by` / `change_log.actor` become real principal refs).
- **Gated by `principal_auth_enabled` (default OFF → a default owner principal)**
  so the single-operator localhost flow stays unbroken; **OIDC/SSO deferred** (the
  parked MCP OAuth AS / Cloudflare setup plugs into `resolve_principal` later).
- 6-slice build order in the architecture doc. **PI-122** (Agent Profile Registry)
  consumes PI-γ's principal model + `system|engagement` scope (DEC-373), so keep
  that surface clean.

**Branch-work protocol (Model A):** the `pi-gamma-rbac` branch carries only code,
schema, and migration commits — no governance applies, no `deposit-event-logs/`
commits off `main`. Land each slice green. At the end, author the PI-γ
build-closure as a close-out payload + apply prompt and apply it on `main` (it
resolves **PI-127**), re-keyed to main's then-current heads. `apply_close_out.py`
now requires `--engagement CRMBUILDER` and a **post-PI-β API** (see the gotchas).

Suite gate throughout: `uv run pytest tests/crmbuilder_v2/ -q` (SQLite). The
`scripts/test_apply_close_out.py` main-branch-guard failures off `main` and the
`test_0037` alembic-from-scratch `NoSuchTableError: charter` are **known
pre-existing** — not your regressions.
