# Apply close-out — SES-139 (WTK-001 ADO state-model substrate)

**Engagement:** CRMBUILDER. **Branch:** `main` (Model A — applies run only on main).
**Payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_139.json`.

This is the **first scheduled-session close-out**, so the apply differs from a
normal new-session close-out in one important way (see step 3).

## 0. Prerequisites

- The v2 REST API is running on `127.0.0.1:8765` against the live engagement DB
  (`CRMBUILDER_V2_DB_PATH=crmbuilder-v2/data/engagements/CRMBUILDER.db`,
  `CRMBUILDER_V2_EXPORT_DIR=PRDs/product/crmbuilder-v2/db-export`).
- Migration `0036_ado_workstream_state_model_substrate` is already applied to the
  live DB (head `0035 -> 0036`). The code substrate is on `main` as commit
  `4915f5f`.
- If the running API was started before commit `4915f5f`, it holds the OLD code
  in memory. That is fine for THIS apply — the close-out creates only
  conversation / decision / reference / commit / deposit_event records, none of
  which touch the changed Workstream code paths. The final snapshots are
  regenerated with the new code via `force_export` (step 4), so the stale API
  cannot corrupt them. (Restart the API afterward so future Workstream writes can
  use the new statuses / `needs_attention`.)

## 1. Pre-flight identifier capture (collision protocol)

Heads at authoring (re-verify; re-key on any collision):
`SES-139` already exists (in_flight), next free `SES-140`; next `CNV-041`; next
`DEC-361`. PRJ-018, PI-114, WSK-001, WTK-001 all exist. SES-139 already carries
`session_belongs_to_project -> PRJ-018` and `session_works_work_task -> WTK-001`.

```bash
for ep in sessions/next-identifier conversations/next-identifier decisions/next-identifier; do
  curl -s "http://127.0.0.1:8765/$ep" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['next'])"
done
```

## 2. Drive WTK-001 -> Complete (done in-session)

```bash
curl -s -X PATCH http://127.0.0.1:8765/work-tasks/WTK-001 \
  -H 'Content-Type: application/json' -d '{"work_task_status":"Complete"}'
```
WSK-001 stays `In Progress` (the Development phase has more work ahead).

## 3. SES-139 is pre-existing — its session block 409s by design

SES-139 was pre-created in `planned` status and transitioned to `in_flight` at
session start. The apply script POSTs the payload's `session` block, which will
return **HTTP 409 (already present) — skipping**; that is expected and correct.
The session block in the payload is there for the record, the validator, and the
deposit_event linkage. The session is driven `in_flight -> complete` by a direct
PATCH AFTER the apply (so its mandatory `complete_session_requires_conversation`
check sees the just-created CNV-041):

```bash
# (run AFTER the apply in step 4, once CNV-041 + its conversation_belongs_to_session edge exist)
curl -s -X PATCH http://127.0.0.1:8765/sessions/SES-139 \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{"session_status":"complete",
 "session_executive_summary":"<the session_executive_summary from ses_139.json>",
 "session_description":"<the session_description from ses_139.json>"}
JSON
```

## 4. Apply + regenerate snapshots

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_139.json
```
Expected: conversation `CNV-041` created; session `SES-139` 409 (skipped);
decision `DEC-361` created; references created (`conversation_belongs_to_project`,
`decided_in`, `session_follows_from`); the `addresses_planning_items` entry
creates `CNV-041 addresses PI-114` (non-resolving — PI-114 stays Draft); the
commit `4915f5f` record created; and a `deposit_event` (DEP-NNN) recorded with
`records_summary` = 1 conversation + 1 decision + 1 commit and the matching
`wrote_record` edges (the 409'd session and the references are not counted).

Then regenerate the committed snapshots from current DB state with the NEW code
(so the two new Workstream columns appear and any stale-API snapshot writes from
the apply are corrected):

```bash
cd crmbuilder-v2
CRMBUILDER_V2_DB_PATH=data/engagements/CRMBUILDER.db \
CRMBUILDER_V2_EXPORT_DIR=../PRDs/product/crmbuilder-v2/db-export \
  uv run python -c "from crmbuilder_v2.access.db import force_export; force_export()"
```

## 5. Post-apply verification

```bash
curl -s http://127.0.0.1:8765/sessions/SES-139    | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('SES-139',d['session_status'])"
curl -s http://127.0.0.1:8765/conversations/CNV-041 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('CNV-041',d['conversation_status'])"
curl -s http://127.0.0.1:8765/decisions/DEC-361    | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('DEC-361',d['status'])"
curl -s http://127.0.0.1:8765/work-tasks/WTK-001   | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('WTK-001',d['work_task_status'])"
curl -s "http://127.0.0.1:8765/planning-items/PI-114" | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('PI-114',d['status'],'(should stay Draft — addressed, not resolved)')"
curl -s "http://127.0.0.1:8765/references?target_id=PI-114&relationship=addresses" | python3 -c "import sys,json;print('addresses PI-114:',[(e['source_id']) for e in json.load(sys.stdin)['data']])"
```

## 6. Commit (governance commit)

One commit on `main` with the regenerated `db-export/*.json` snapshots, the new
`deposit-event-logs/dep_NNN.log`, the close-out payload, and this apply prompt:

```bash
git add PRDs/product/crmbuilder-v2/db-export \
        PRDs/product/crmbuilder-v2/deposit-event-logs \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_139.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-139.md
git commit -m "v2: SES-139 close-out — WTK-001 ADO state-model substrate (DEC-361)"
```
The code/migration/tests/docs are already on `main` as commit `4915f5f`.
Doug pushes.
