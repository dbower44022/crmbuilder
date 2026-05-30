# Apply close-out — SES-118 / CNV-020 (implements + resolves PI-107)

## Purpose

Apply the SES-118 close-out, which records the PI-107 implementation and resolves PI-107.

**Net effect**
- Creates session **SES-118**, conversation **CNV-020**.
- Records commit **f690bde** against the session.
- Creates 2 references: `CNV-020 conversation_belongs_to_session SES-118`, `SES-118 session_belongs_to_workstream WS-011`.
- Flips **PI-107** `Open → Resolved` (`resolves_planning_items`).
- No decisions, no work tickets, no new planning items.

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short
git pull --rebase origin main
curl -s http://127.0.0.1:8765/health
for e in sessions conversations; do printf "%s -> " "$e"; curl -s "http://127.0.0.1:8765/$e/next-identifier"; echo; done
# Expect: sessions SES-118, conversations CNV-020. Re-key the payload if advanced.
curl -s http://127.0.0.1:8765/planning-items/PI-107 | python3 -c "import sys,json;print('PI-107 status:',json.load(sys.stdin)['data']['status'])"
# Expect: Open (will become Resolved).
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_118.json
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_118.json
# Expected OK: 1 session, 1 conversation, 1 commit, 2 references, PI-107 resolved.
```

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -s http://127.0.0.1:8765/planning-items/PI-107 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['identifier'],'|',d['status'],'|',d.get('resolution_reference'))"
# Expect: PI-107 | Resolved | (SES-118 / resolution reference)
curl -s http://127.0.0.1:8765/sessions/SES-118 | python3 -c "import sys,json;print(json.load(sys.stdin)['data'].get('session_status'))"
```

## Commit snapshot regeneration

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_118.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-118.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-118 close-out — implement + resolve PI-107 (PI timestamps in UI)"
```
Doug pushes after review (Claude Code push convention).
