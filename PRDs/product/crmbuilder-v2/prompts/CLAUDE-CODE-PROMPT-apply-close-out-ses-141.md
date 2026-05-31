# Apply close-out — SES-141 (WTK-003 ADO phase-specialist substrate)

**Engagement:** CRMBUILDER. **Branch:** `main` (Model A). **Payload:**
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_141.json`.

A normal new-session close-out (the `session` block POSTs and creates SES-141).

## 0. Context

- WTK-003 (the phase-specialist substrate Work Task) was created via
  `POST /work-tasks` under WSK-001 and driven
  `Planned → Ready → Claimed(CNV-043) → In Progress → Complete`.
- The decomposer code is on `main` (see the `commits` section). The new
  endpoints `POST /workstreams/{id}/scope` and
  `GET /workstreams/{id}/prior-phase-outputs` go live once the running API is
  restarted onto the new code; this close-out does not require invoking them.

## 1. Pre-flight heads

Next SES-141, CNV-043, DEC-363; WTK-003 exists (Complete), WSK-001 / PRJ-018 /
PI-114 exist. Re-verify and re-key on collision:

```bash
for ep in sessions conversations decisions; do
  curl -s "http://127.0.0.1:8765/$ep/next-identifier" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['next'])"
done
```

## 2. Apply + regenerate snapshots

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_141.json
```
Expected: CNV-043, SES-141, the commit record, DEC-363, the references
(`session_belongs_to_project` hoisted inline, `session_works_work_task`,
`conversation_belongs_to_project`, `decided_in`, `session_follows_from`),
`addresses_planning_items` → `CNV-043 addresses PI-114` (PI-114 stays Draft),
deposit_event DEP-NNN (1 session + 1 conversation + 1 commit + 1 decision).

If the running API still holds pre-decomposer code, regenerate snapshots with the
NEW code:

```bash
cd crmbuilder-v2
CRMBUILDER_V2_DB_PATH=data/engagements/CRMBUILDER.db \
CRMBUILDER_V2_EXPORT_DIR=../PRDs/product/crmbuilder-v2/db-export \
  uv run python -c "from crmbuilder_v2.access.db import force_export; force_export()"
```

## 3. Post-apply verification

```bash
for r in "sessions/SES-141 session_status" "conversations/CNV-043 conversation_status" "decisions/DEC-363 status" "work-tasks/WTK-003 work_task_status" "planning-items/PI-114 status"; do
  set -- $r; curl -s "http://127.0.0.1:8765/$1" | python3 -c "import sys,json;print('$1', json.load(sys.stdin)['data']['$2'])"
done
```

## 4. Commit (governance commit)

```bash
git add PRDs/product/crmbuilder-v2/db-export \
        PRDs/product/crmbuilder-v2/deposit-event-logs \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_141.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-141.md
git commit -m "v2: SES-141 close-out — WTK-003 ADO phase-specialist substrate (DEC-363)"
```
The substrate code/tests are already on `main`. Doug pushes.
