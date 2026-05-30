# Apply close-out — SES-122 / CNV-024 (implements + resolves PI-101)

## Purpose

Apply the SES-122 close-out: records the PI-101 implementation (close-out validator hardening) and resolves PI-101.

**Net effect**
- Creates session **SES-122**, conversation **CNV-024**.
- Records commit **947da63** against the session.
- Creates references: `CNV-024 conversation_belongs_to_session SES-122`, `SES-122 session_belongs_to_workstream WS-011`.
- Flips **PI-101** `Open → Resolved`.
- No decisions, work tickets, or new planning items.

Note: this payload is validated by the very checks PI-101 added; it already passes the hardened pre-flight cleanly (0 errors).

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short
git pull --rebase origin main
curl -s http://127.0.0.1:8765/health
for e in sessions conversations; do printf "%s -> " "$e"; curl -s "http://127.0.0.1:8765/$e/next-identifier"; echo; done
# Expect: sessions SES-122, conversations CNV-024. Parallel sessions are active —
# re-key the payload + this prompt if either advanced.
curl -s http://127.0.0.1:8765/planning-items/PI-101 | python3 -c "import sys,json;print('PI-101 status:',json.load(sys.stdin)['data']['status'])"
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_122.json
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_122.json
# Expected OK: 1 session, 1 conversation, 1 commit, 2 references, PI-101 resolved.
```

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -s http://127.0.0.1:8765/planning-items/PI-101 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['identifier'],'|',d['status'])"
curl -s http://127.0.0.1:8765/sessions/SES-122 | python3 -c "import sys,json;print(json.load(sys.stdin)['data'].get('session_status'))"
```

## Commit snapshot regeneration

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_122.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-122.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-122 close-out — implement + resolve PI-101 (validator hardening)"
```
Doug pushes after review (Claude Code push convention).
