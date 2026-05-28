# CLAUDE-CODE-PROMPT — Apply close-out SES-110 (CNV-012)

**Run from:** `crmbuilder-v2/` (so the relative payload path resolves)
**Target engagement:** CRMBUILDER
**Push:** No — Claude Code commits the snapshot regen; **Doug pushes after review.** (The payload, this apply prompt, and the kickoff are already on `main` from the sandbox.)

---

## 1. Purpose — Net Effect

Applies `PRDs/product/crmbuilder-v2/close-out-payloads/ses_110.json`. Records that will land:

| Record | What |
|---|---|
| **SES-110** | Session — concurrent-write-safety architecture, draft phase (status `complete`) |
| **CNV-012** | Conversation — collisions → SessionDraftToken design |
| **DEC-325** | Decision — draft-phase write authorization via per-session SessionDraftToken |
| **PI-100** | Planning item — promoted-record concurrency + substrate validation (status `Open`) |
| **WT-056** | Work ticket (`kickoff_prompt`) → `kickoff-concurrency-promoted-records-and-substrate.md` |
| **+4 references** | `session_belongs_to_workstream` (SES-110→WS-012), `conversation_belongs_to_session` (CNV-012→SES-110), `decided_in` (DEC-325→CNV-012), `addresses` (WT-056→PI-100) |
| **+1 deposit_event** | DEP-NNN, lazy-creating COP-108, posted by the apply script |

No code changes. `resolves_planning_items` and `addresses_planning_items` are empty (PI-100 is newly filed, not resolved here).

## 2. Pre-flight

```bash
cd crmbuilder-v2
git rev-parse --show-toplevel                      # confirm crmbuilder repo
git status --porcelain                             # expect clean
git config user.email                              # expect doug@dougbower.com
git pull --rebase
test -f ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_110.json && echo "payload present"
curl -fsS "http://127.0.0.1:8765/sessions?limit=1" >/dev/null && echo "API up"
```

**Pre-apply head capture (live — authoritative over any snapshot):**

```bash
for e in sessions:session_identifier conversations:conversation_identifier decisions:identifier planning-items:identifier work-tickets:work_ticket_identifier; do
  ep=${e%%:*}; key=${e##*:}
  curl -fsS "http://127.0.0.1:8765/${ep}?limit=500" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);rows=d.get('data',d);ids=[r.get('$key') for r in rows if r.get('$key')];n=lambda i:int(str(i).split('-')[-1]);print('$ep head ->', sorted(ids,key=n)[-1] if ids else 'none')"
done
```

**Re-key contingency (this is the whole point of the originating conversation).** The payload assumes heads SES-109 / CNV-011 / DEC-324 / PI-099 / WT-055 → it claims SES-110 / CNV-012 / DEC-325 / PI-100 / WT-056. If any live head has advanced past those, **re-key the payload** to the next free slot for the advanced type(s) and update every internal reference (`decided_in` target, `addresses` source, the two inline membership edges, the filename, and the WT `work_ticket_file_path` references in prose if affected) before applying. Note the re-key in the session record's description.

## 3. Apply

```bash
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_110.json
```

Expected: session OK, conversation OK, 1 work_ticket OK, 1 planning_item OK, 1 decision OK, 2 top-level references OK (inline membership edges land with their parent creates), deposit_event OK. Re-running is safe (409 = already present) — but see the verification below; a 409 on a record you did **not** previously apply means a real collision, so investigate rather than assume idempotency.

## 4. Post-apply verification

```bash
# heads advanced by exactly one each
curl -fsS "http://127.0.0.1:8765/decisions?limit=500" | python3 -c "import sys,json;d=json.load(sys.stdin);print('DEC head', sorted([r['identifier'] for r in d.get('data',d)],key=lambda i:int(i.split('-')[-1]))[-1])"
# spot-check the session and the decision exist and read correctly
curl -fsS "http://127.0.0.1:8765/sessions/SES-110"  | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('data',d).get('session_status'))"
curl -fsS "http://127.0.0.1:8765/decisions/DEC-325" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('data',d).get('status'))"
# decided_in resolves DEC-325 -> CNV-012
curl -fsS "http://127.0.0.1:8765/references?source_id=DEC-325&relationship=decided_in" | python3 -c "import sys,json;d=json.load(sys.stdin);print([r.get('target_id') for r in d.get('data',d)])"
# addresses resolves WT-056 -> PI-100
curl -fsS "http://127.0.0.1:8765/references?target_id=PI-100&relationship=addresses" | python3 -c "import sys,json;d=json.load(sys.stdin);print([r.get('source_id') for r in d.get('data',d)])"
```

Confirm: SES-110 `complete`, DEC-325 `Active`, `decided_in` → `['CNV-012']`, `addresses` → `['WT-056']`, references count up by the expected delta.

## 5. Commit snapshot regeneration (no push)

The apply script regenerated `db-export/*.json` via the `_refresh_snapshot` hook and wrote `deposit-event-logs/dep_NNN.log` — **no standalone exporter is run.** Commit them together:

```bash
cd ..
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-110 close-out applied — DEC-325 (SessionDraftToken draft-phase authorization) + PI-100 filed (promoted-record concurrency + substrate)"
# DO NOT push — Doug reviews and pushes.
```

## 6. Done block

Reply with: heads before/after for SES/CNV/DEC/PI/WT; record counts applied; the DEP-NNN identifier; the snapshot-regen commit SHA; and the next-conversation kickoff path (`PRDs/product/crmbuilder-v2/kickoff-concurrency-promoted-records-and-substrate.md`, opens against PI-100).
