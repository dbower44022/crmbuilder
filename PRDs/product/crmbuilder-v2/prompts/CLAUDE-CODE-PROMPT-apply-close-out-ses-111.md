# CLAUDE-CODE-PROMPT — Apply close-out SES-111 (CNV-013)

**Run from:** `crmbuilder-v2/`
**Target engagement:** CRMBUILDER
**Push:** No — Claude Code commits the snapshot regen; **Doug pushes after review.**

---

## 1. Purpose — Net Effect

Applies `PRDs/product/crmbuilder-v2/close-out-payloads/ses_111.json`, then PATCHes one existing record. Records that land:

| Record | What |
|---|---|
| **SES-111** | Session — file SES-110 follow-ups + split edit-locking (status `complete`) |
| **CNV-013** | Conversation — the filing/split work |
| **PI-101** | Harden the close-out pre-flight validator (missing-field + wrong-case) — `Open` |
| **PI-102** | Reconcile executive_summary nullability (models vs live DB) — `Open` |
| **PI-103** | Edit-locking for promoted records (version-check vs advisory lease) — `Open` |
| **+3 references** | `session_belongs_to_workstream` (SES-111→WS-012), `conversation_belongs_to_session` (CNV-013→SES-111), `addresses` (WT-056→PI-103) |
| **+1 deposit_event** | DEP-NNN, lazy-creating COP-111 |
| **PATCH PI-100** | Narrow title + description to **storage-substrate validation only** (edit-locking now lives in PI-103) |

No decisions, no code. Every record carries `executive_summary`; all statuses are lowercase (lessons from SES-110).

## 2. Pre-flight

```bash
cd crmbuilder-v2
git rev-parse --show-toplevel
git status --porcelain                 # expect clean
git config user.email                  # expect doug@dougbower.com
git pull --rebase
test -f ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_111.json && echo "payload present"
curl -fsS "http://127.0.0.1:8765/sessions?limit=1" >/dev/null && echo "API up"
```

**Pre-apply head capture (live):**

```bash
for e in sessions:session_identifier conversations:conversation_identifier planning-items:identifier; do
  ep=${e%%:*}; key=${e##*:}
  curl -fsS "http://127.0.0.1:8765/${ep}?limit=500" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);rows=d.get('data',d);ids=[r.get('$key') for r in rows if str(r.get('$key','')).split('-')[-1].isdigit()];print('$ep head ->', sorted(ids,key=lambda i:int(i.split('-')[-1]))[-1] if ids else 'none')"
done
```

**Re-key contingency.** The payload assumes heads SES-110 / CNV-012 / PI-100 → it claims SES-111 / CNV-013 / PI-101–103. If any have advanced, re-key the payload and its internal references (filename, inline membership edges, the `addresses` edge target) before applying, and note it in the session description.

## 3. Apply

```bash
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_111.json
```

Expected: session OK, conversation OK, 3 planning_items OK, 1 reference OK (the two membership edges land inline with their parents), deposit_event OK. (No decisions, no work_tickets, no commits.)

## 4. PATCH PI-100 — narrow to substrate only

```bash
curl -fsS -X PATCH "http://127.0.0.1:8765/planning-items/PI-100" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Validate the storage substrate at target concurrent-writer scale",
    "description": "Decide whether SQLite-per-engagement holds at the target peak number of concurrent writers against a single engagement, or whether a different store (e.g. Postgres with row-level MVCC) is required. The engine is SQLite with serialized writers (BEGIN IMMEDIATE, busy_timeout=5000, isolation_level=None, no WAL) and one DB file per engagement, so write concurrency is per-engagement: cross-engagement scales horizontally for free; within one engagement everything funnels through a single serialized writer. Distinguish logical concurrency (many area-partitioned agents, short writes - SQLite survives) from throughput concurrency (sustained rate beyond a single writer, or long-held write transactions - SQLite does not). First input needed: order-of-magnitude peak concurrent writers against one engagement, and whether their work partitions cleanly or contends on shared records. The edit-locking / modify-modify mechanism was split out to PI-103; this item is substrate-adequacy only."
  }' | python3 -c "import sys,json;d=json.load(sys.stdin);print('PI-100 now:', d.get('data',d).get('title'))"
```

## 5. Post-apply verification

```bash
curl -fsS "http://127.0.0.1:8765/planning-items?limit=500" | python3 -c "import sys,json;d=json.load(sys.stdin);print('PI head', sorted([r['identifier'] for r in d.get('data',d)],key=lambda i:int(i.split('-')[-1]))[-1])"
curl -fsS "http://127.0.0.1:8765/sessions/SES-111"  | python3 -c "import sys,json;d=json.load(sys.stdin);print('SES-111', d.get('data',d).get('session_status'))"
curl -fsS "http://127.0.0.1:8765/planning-items/PI-103" | python3 -c "import sys,json;d=json.load(sys.stdin);x=d.get('data',d);print('PI-103', x.get('status'),'exec_len',len(x.get('executive_summary') or ''))"
curl -fsS "http://127.0.0.1:8765/references?target_id=PI-103&relationship=addresses" | python3 -c "import sys,json;d=json.load(sys.stdin);print('addresses PI-103 from', [r.get('source_id') for r in d.get('data',d)])"
```

Confirm: PI-101/102/103 `Open` with `executive_summary` populated; SES-111 `complete`; `addresses` PI-103 ← `['WT-056']`; PI-100 title now substrate-only.

## 6. Commit snapshot regeneration (no push)

```bash
cd ..
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-111 close-out applied — PI-101/102/103 filed + PI-100 narrowed to substrate (edit-locking split to PI-103)"
# DO NOT push — Doug reviews and pushes.
```

## 7. Done block

Reply with: PI head before/after; SES/CNV created; DEP-NNN; PI-100's new title (confirming the PATCH); snapshot-regen commit SHA. The promoted-record kickoff (`kickoff-concurrency-promoted-records-and-substrate.md`) now opens against **PI-103 (edit-locking)** and **PI-100 (substrate)**.
