# Apply close-out — SES-120 / CNV-022 (implements + resolves PI-031)

## Purpose

Apply the SES-120 close-out: records the PI-031 implementation, authors DEC-332 (schema reconciliation), and resolves PI-031.

**Net effect**
- Creates session **SES-120**, conversation **CNV-022**, decision **DEC-332**.
- Records commit **f5381966** against the session.
- Creates references: `CNV-022 conversation_belongs_to_session SES-120`, `SES-120 session_belongs_to_workstream WS-011`, `DEC-332 decided_in CNV-022`, `DEC-332 is_about PI-031`.
- Flips **PI-031** `Open → Resolved`.

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short
git pull --rebase origin main
curl -s http://127.0.0.1:8765/health
for e in sessions conversations decisions; do printf "%s -> " "$e"; curl -s "http://127.0.0.1:8765/$e/next-identifier"; echo; done
# Expect: sessions SES-120, conversations CNV-022, decisions DEC-332.
# Parallel sessions are active — if any advanced, re-key the payload + this prompt.
curl -s http://127.0.0.1:8765/planning-items/PI-031 | python3 -c "import sys,json;print('PI-031 status:',json.load(sys.stdin)['data']['status'])"
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_120.json
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_120.json
# Expected OK: 1 session, 1 conversation, 1 decision, 1 commit, 4 references, PI-031 resolved.
```

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -s http://127.0.0.1:8765/planning-items/PI-031 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['identifier'],'|',d['status'])"
curl -s http://127.0.0.1:8765/decisions/DEC-332 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['identifier'],'|',d['status'],'|',d['title'][:60])"
curl -s http://127.0.0.1:8765/sessions/SES-120 | python3 -c "import sys,json;print(json.load(sys.stdin)['data'].get('session_status'))"
```

## Commit snapshot regeneration

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_120.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-120.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-120 close-out — implement + resolve PI-031 (commits UI), author DEC-332"
```
Doug pushes after review (Claude Code push convention).
