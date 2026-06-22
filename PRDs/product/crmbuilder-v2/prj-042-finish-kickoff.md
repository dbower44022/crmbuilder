# Kickoff — Finish PRJ-042 "YAML Publish & Validate"

**For:** a fresh Claude Code session.
**Goal:** build the five remaining, already-approved requirements of PRJ-042 so the
publish feature is complete end-to-end.

This prompt is self-contained — read it, orient against the live DB, then execute
the slices in order. Do **not** assume the state below is current; verify it first
(§1), because parallel ADO orchestrators advance `main` and the governance DB
continuously.

---

## 0. The one rule that governs everything

**Governance is a precondition, not a postscript** (CLAUDE.md). Before any code for
a slice: a **confirmed requirement** + an **implementing planning item** must exist.
The five requirements are *already confirmed* (REQ-290..294 — verify in §1). So per
slice you only need to **create the implementing PI first**, then write code. Use the
**Model A branch protocol**: code/tests on a `pi-NNN` branch; governance close-out
(session/conversation/`resolves` edge) recorded on `main` after merge via direct API
POST (real-time recording, DEC-383).

---

## 1. Orient (do this first, every time)

Tier-1: you've read this file and CLAUDE.md. Tier-2 (the live DB is the source of
truth — never committed files):

```bash
# API must be up (desktop UI owns one, or: cd crmbuilder-v2 && uv run crmbuilder-v2-api &)
H='-H X-Engagement:CRMBUILDER'
curl -s $H http://127.0.0.1:8765/projects/PRJ-042 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['project_name'],d['project_status'])"
# The 8 requirements under the project's topic TOP-102 + which already have an implementing PI:
for r in 287 288 289 290 291 292 293 294; do
  built=$(curl -s $H "http://127.0.0.1:8765/references?target_id=REQ-$r&relationship=planning_item_implements_requirement" | python3 -c "import sys,json;d=json.load(sys.stdin).get('data') or [];print(' '.join(e['source_id'] for e in d) or 'NONE')")
  curl -s $H http://127.0.0.1:8765/requirements/REQ-$r | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('REQ-$r',d['requirement_status'],d['requirement_name'][:55],'| PIs:','$built')"
done
```

**Expected at handoff (06-22):** REQ-287 (publish, PI-243/250/251), REQ-288
(validate, PI-243/250), REQ-289 (preview, PI-252) are **built + merged + resolved**.
**REQ-290..294 are confirmed with NO implementing PI** — those are your work.
Also read the governance recording rules: `GET /topics/TOP-013` (real-time direct
POST in Claude Code; close-out payload only as a sandbox fallback).

---

## 2. What already exists (reuse it — do not rebuild)

The publish path is built and live-validated. The pieces to extend:

| Layer | File | What it gives you |
|---|---|---|
| Deploy engine | `espo_impl/core/deploy_pipeline.py` | `deploy_pipeline(program, client, field_mgr, output_fn, *, skip_deletes, dry_run, managers)` → `DeployOutcome(report, ...)`. Qt-free. `dry_run=True` = non-destructive preview (no writes); fields use `field_mgr.preview()`. |
| Per-manager dry_run | `espo_impl/core/{entity,relationship,layout,entity_settings,filtered_tab}_manager.py` + team/role | each takes `dry_run: bool=False` (report planned action, no write). |
| Service | `crmbuilder-v2/src/crmbuilder_v2/publish/service.py` | `publish(instance_record, design_client, *, api_key, secret_key, rendered_at, engagement, validate_only, preview, output_fn) -> PublishResult`; helpers `build_target_profile`, `generate_design_yaml`, `parse_programs`, `validate_programs`. |
| REST | `crmbuilder-v2/src/crmbuilder_v2/api/routers/instances.py` | `POST /instances/{id}/publish`, `/publish-validate`, `/publish-preview`; `_resolve_publish_target`, `_run_publish`, `_serialize_publish_result`. |
| Client | `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` | `publish_instance`, `publish_validate_instance`, `publish_preview_instance`. |
| UI | `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/publish_dialog.py` | `PublishDialog` (Re-validate / Preview / Publish), pure renderers `render_validate_html` / `render_preview_html` / `render_publish_html`. Opened from `ui/panels/instances.py` "Publish…" button. |
| Audit/drift (for verify/backup) | `crmbuilder-v2/src/crmbuilder_v2/introspect/reconcile.py`, `access/repositories/inventory.py` (`publish_plan`, `membership_summary`) | live introspection + the canonical-vs-target delta. |

Adapter (design → in-memory YAML): `crmbuilder-v2/src/crmbuilder_v2/adapters/espocrm/`.
Design source over HTTP: `RestDesignClient`.

---

## 3. The five slices (recommended order)

Build smallest/highest-value first. **One PI per requirement**, each with
`planning_item_belongs_to_project → PRJ-042` and
`planning_item_implements_requirement → REQ-NNN`, `execution_mode: interactive`
(so background ADO doesn't grab it).

### Slice A — REQ-294: surface the manual-config checklist (easiest; mostly UI)
The serialized publish result **already carries `manual_config`** (the adapter's
MANUAL-CONFIG.md) and `deferrals`. `render_publish_html`/`render_preview_html`
already note it exists — make it a real, readable **post-publish checklist** in the
dialog (the workflows / saved-views / dup-checks / role-visibility items EspoCRM
can't apply via REST). Likely no engine/API change — render what's already returned;
add a test asserting the checklist renders the deferral/manual items. Confirm the
adapter populates `manual_config` for a design that has such items.

### Slice B — REQ-291: post-publish verify
After a real publish, re-audit the target and confirm the published objects are now
present/matching. Reuse `introspect/reconcile.py` (the same path
`POST /instances/{id}/audit` uses) scoped to the just-published entities. Surface a
per-object present/matching/missing result. Wire into `service.publish` as a
post-deploy step (only when not preview/validate_only) and into the dialog
("Verifying…" → results). Add `POST /instances/{id}/publish` returning a `verify`
section, or a separate `/verify` call the dialog makes after publish.

### Slice C — REQ-290: scoped publish
Let the caller publish a **subset**: an explicit set of design objects, or **only the
delta** the publish-plan computes (`inventory.publish_plan`). Thread a `scope`
argument through `service.publish` (filter the parsed programs / the design fetched
from `RestDesignClient`) and the endpoint; in the dialog, a selection list (default:
the drifted/absent set). Keep "publish everything" as the default.

### Slice D — REQ-292: backup before publish
Before applying, capture a snapshot of the target's current config (reuse the
audit/introspection read) and store it so a publish is reviewable/reversible. Decide
the store with Doug if unclear (a backup artifact file under the engagement, or a
governance record). Gate: no backup → no publish (or a clear override).

### Slice E — REQ-293: publish history
Record each publish — scope, target, timestamp, outcome — durably and listable.
Likely a small new entity (e.g. `publish_run`) or reuse the deposit-event/governance
trail. Surface a history view. **This is the one that may need a schema migration**
(see §5). Scope the entity with Doug before building if it's new.

> R3 (instance-vs-instance compare) is **out of scope** here — deferred to its own
> design session.

---

## 4. Per-slice loop

1. **Create the implementing PI** (interactive) + the two edges. Example:
   ```bash
   H='-H X-Engagement:CRMBUILDER -H Content-Type:application/json'
   # POST /planning-items {title, item_type:"pending_work", status:"Draft",
   #   execution_mode:"interactive", description, executive_summary(>=... )}
   # then POST /references for belongs_to_project(PRJ-042) + implements_requirement(REQ-NNN)
   ```
2. **Branch** off `main`: `git checkout -b pi-NNN <slice> main`.
3. **Build + tests.** Keep V1 (`espo_impl`) green; mirror existing test patterns
   (`tests/crmbuilder_v2/publish/`, `tests/crmbuilder_v2/api/test_instance_publish_api.py`,
   `tests/crmbuilder_v2/ui/test_publish_dialog.py`, `tests/test_deploy_pipeline_dry_run.py`).
   `uv run ruff check` the changed files.
4. **Commit** with explicit pathspec (`git commit -m "…" -- <files>`) — parallel
   orchestrators stage files; a bare commit sweeps them in. End the message with the
   Co-Authored-By trailer.
5. **Merge to `main`** (see §5). **Close out** on `main` via direct API POST: a
   `session` (medium `chat`, `session_belongs_to_project → PRJ-042`), a
   `conversation` (`conversation_belongs_to_session` + `resolves → PI-NNN`, which
   flips the PI to Resolved). Session must be created as `in_flight` or — if
   `complete` — only after its inbound conversation edge exists.

---

## 5. Merge & environment gotchas (learned 06-21/22 — heed these)

- **`main` diverges constantly.** A clean fast-forward usually fails. Land each commit
  via an **isolated worktree cherry-pick** so you never disturb the shared (often
  orchestrator-contaminated) working tree:
  ```bash
  git worktree add --detach /tmp/wt origin/main
  git -C /tmp/wt cherry-pick <sha>
  git -C /tmp/wt push origin HEAD:main
  git worktree remove /tmp/wt --force
  git fetch origin && git branch -f main origin/main
  ```
  Doug pushes in normal flow; he authorized direct push/merge during the push when asked.
- **Shared-index contamination:** if `git checkout`/rebase fails on foreign staged or
  unmerged files (parallel orchestrators), `git reset` (unstage all — working tree
  untouched) then proceed. Never commit files you didn't author; always pathspec.
- **Build in the main checkout, not a separate worktree** — the package is an editable
  install pointing at `…/crmbuilder/`, so tests only see code in that tree.
- **The live DB is SQLite in a Dropbox-synced folder** → intermittent
  `database is locked` / `disk I/O error` on writes. Governance POSTs occasionally
  return empty/500 — **just retry** (idempotent reads; for creates, check then retry).
  `sessions/next-identifier` has been flaky; fetch the max SES and use the next free id
  explicitly if needed. The live DB is already WAL. The real fix is Postgres (PRJ-019),
  out of scope here.
- **Requirement gates** (if you ever add/adjust a requirement): the readability gate
  caps a statement at 75 words (one idea), the name has a length limit, and approval is
  Doug's via the Review panel (never a status edit). The five here are already approved.

---

## 6. Definition of done

- REQ-290..294 each have a Resolved implementing PI; `GET /coverage/capabilities`
  shows no new orphans for PRJ-042.
- The publish dialog supports: validate, preview, scoped publish, publish-with-verify,
  backup-before-publish, and a manual-config checklist.
- All publish/preview/UI test suites green; V1 deploy-engine suite green; lint clean.
- Each slice merged to `main` and closed out (session + `resolves` edge).
- A short note to Doug summarizing what shipped and any decisions made (backup store,
  history entity shape).

Start with **§1 (orient)**, then **Slice A**.
