# Apply close-out SES-156 — PI-γ build-closure (RBAC) + PI-β follow-ons

Applies `close-out-payloads/ses_156.json` on `main`: records the PI-γ
(identity / authentication / RBAC, PRJ-019 / **PI-127**) build plus the three
PI-β follow-ons, ingests the eleven commits since the PI-β closure, records
**DEC-379**, and **resolves PI-127**.

## Pre-flight

1. **On `main`** (the branch-work protocol — `apply_close_out.py` refuses off
   `main` without `--allow-branch-local`). `pi-gamma-rbac` is already merged FF.
2. **Run against a post-PI-γ API.** Doug's long-running API on `:8765` may be
   stale (pre-PI-β). Start a fresh one on an alternate port from current `main`:

   ```bash
   CRMBUILDER_V2_API_PORT=8766 crmbuilder-v2-api &
   curl -s http://127.0.0.1:8766/admin/version   # expect a single `schema` block, head 0042
   ```

3. **The live unified DB is `create_all`-managed (no `alembic_version`).** PI-γ
   added migrations `0040`/`0041`/`0042`, but the live DB cannot run the chain
   (the gitignored base-entity-catalog YAMLs). Apply the schema delta directly
   *before* starting the API, after backing the DB up:

   ```bash
   cp crmbuilder-v2/data/v2-unified.db crmbuilder-v2/data/v2-unified.db.pre-pi-gamma-backup-<date>
   # create_all (idempotent) creates the 3 RBAC tables; ALTER adds the column.
   python - <<'PY'
   from sqlalchemy import create_engine
   from crmbuilder_v2.access.models import Base
   import sqlite3
   create_engine("sqlite:///crmbuilder-v2/data/v2-unified.db").pipe  # noqa
   PY
   # (see the build session for the exact one-liner: create_all + ALTER TABLE
   #  change_log ADD COLUMN principal_id VARCHAR(32))
   ```

   The apply writes `change_log` rows with `actor=claude_session` /
   `principal_id=NULL` (auth off), so the pre-existing actor CHECK still admits
   them; the actor-CHECK widening and the `engagement_export_dir` drop are
   deferred on the live DB (harmless with auth off).

4. **Re-key if heads moved.** Heads expected at authoring: next `SES-156` /
   `CNV-058` / `DEC-379`, `PI-127` Draft under `PRJ-019`. Verify with
   `GET /sessions?...&order=desc`, `/decisions/next-identifier`,
   `/conversations/next-identifier`, `/planning-items/PI-127`; if anything was
   claimed in parallel, re-key the payload identifiers.

## Apply

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py \
    ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_156.json \
    --base http://127.0.0.1:8766 \
    --engagement CRMBUILDER
```

`apply_close_out.py` HOISTS the `session_belongs_to_project` membership edge
onto the session POST, so it will not appear in the references-loop output —
that is correct. The apply lazy-creates the `close_out_payload` +
`deposit_event` entities and tees the log to `deposit-event-logs/dep_NNN.log`.

## Post-apply verification

```bash
curl -s -H X-Engagement:CRMBUILDER http://127.0.0.1:8766/planning-items/PI-127 \
  | python -c "import sys,json; d=json.load(sys.stdin)['data']; print(d['identifier'], d['status'])"
# expect: PI-127 Resolved
curl -s -H X-Engagement:CRMBUILDER http://127.0.0.1:8766/decisions/DEC-379 \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['identifier'])"
```

Then commit the new `deposit-event-logs/dep_NNN.log` + this payload + this apply
prompt + the PI-γ deliverables in one commit. (PI-β removed the db-export
snapshot tree — there is no snapshot to regenerate.)
