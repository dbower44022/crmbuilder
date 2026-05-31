# Apply close-out — SES-140 (WTK-002 ADO structural decomposer)

**Engagement:** CRMBUILDER. **Branch:** `main` (Model A). **Payload:**
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_140.json`.

A **normal** new-session close-out (unlike SES-139, the session does NOT pre-exist
— the `session` block POSTs and creates SES-140).

## 0. Context

- WTK-002 (the decomposer Work Task) was created via `POST /work-tasks` (an
  operational entity — Workstreams/Work Tasks are written directly, never bundled
  into close-out payloads), belongs to WSK-001 (the PI-114 Development phase), and
  was driven `Planned → Ready → Claimed(CNV-042) → In Progress → Complete`.
- The decomposer code is on `main` (see the `commits` section). The new endpoint
  `POST /planning-items/{id}/decompose` only goes live once the running API is
  restarted onto the new code; this close-out does not require invoking it.

## 1. Pre-flight heads (collision protocol)

Heads at authoring: next SES-140, CNV-042, DEC-362; WTK-002 exists (Complete),
WSK-001 / PRJ-018 / PI-114 exist. Re-verify and re-key on any collision:

```bash
for ep in sessions conversations decisions; do
  curl -s "http://127.0.0.1:8765/$ep/next-identifier" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['next'])"
done
```

## 2. Apply + regenerate snapshots

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_140.json
```
Expected: CNV-042 created; SES-140 created; commit record created; DEC-362
created; references created (`session_belongs_to_project`,
`session_works_work_task`, `conversation_belongs_to_project`, `decided_in`,
`session_follows_from`); `addresses_planning_items` creates `CNV-042 addresses
PI-114` (non-resolving — PI-114 stays Draft); deposit_event DEP-NNN recorded
(1 session + 1 conversation + 1 commit + 1 decision).

If the running API still holds the pre-`4915f5f`/decomposer code, regenerate the
committed snapshots from current DB state with the NEW code afterward:

```bash
cd crmbuilder-v2
CRMBUILDER_V2_DB_PATH=data/engagements/CRMBUILDER.db \
CRMBUILDER_V2_EXPORT_DIR=../PRDs/product/crmbuilder-v2/db-export \
  uv run python -c "from crmbuilder_v2.access.db import force_export; force_export()"
```

## 3. Post-apply verification

```bash
curl -s http://127.0.0.1:8765/sessions/SES-140      | python3 -c "import sys,json;print('SES-140',json.load(sys.stdin)['data']['session_status'])"
curl -s http://127.0.0.1:8765/conversations/CNV-042 | python3 -c "import sys,json;print('CNV-042',json.load(sys.stdin)['data']['conversation_status'])"
curl -s http://127.0.0.1:8765/decisions/DEC-362     | python3 -c "import sys,json;print('DEC-362',json.load(sys.stdin)['data']['status'])"
curl -s http://127.0.0.1:8765/work-tasks/WTK-002    | python3 -c "import sys,json;print('WTK-002',json.load(sys.stdin)['data']['work_task_status'])"
curl -s "http://127.0.0.1:8765/planning-items/PI-114" | python3 -c "import sys,json;print('PI-114',json.load(sys.stdin)['data']['status'],'(should stay Draft)')"
```

## 4. Commit (governance commit)

```bash
git add PRDs/product/crmbuilder-v2/db-export \
        PRDs/product/crmbuilder-v2/deposit-event-logs \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_140.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-140.md
git commit -m "v2: SES-140 close-out — WTK-002 ADO structural decomposer (DEC-362)"
```
The decomposer code/tests are already on `main`. Doug pushes.
