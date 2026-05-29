# Apply close-out — SES-117 / CNV-019 (files PI-107)

## Purpose

Apply the SES-117 close-out payload, which files a single planning item.

**Net effect**
- Creates session **SES-117**, conversation **CNV-019**.
- Creates planning item **PI-107** — "Surface planning_item created/updated timestamps in the Planning Items UI panel" (`item_type: pending_work`, `status: Open`).
- Creates 2 references: `CNV-019 conversation_belongs_to_session SES-117`, and `SES-117 session_belongs_to_workstream WS-011`.
- No decisions, no work tickets, no commits.

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short                 # expect clean (or only this payload + prompt staged)
git pull --rebase origin main
curl -s http://127.0.0.1:8765/health
# Pre-apply heads — re-verify the payload's identifiers are still free:
for e in sessions conversations planning-items; do
  printf "%s -> " "$e"; curl -s "http://127.0.0.1:8765/$e/next-identifier"; echo
done
# Expect: sessions SES-117, conversations CNV-019, planning-items PI-107.
# If any has advanced, re-key the payload (and this prompt) to the next free slot before applying.
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_117.json
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_117.json
# Expected OK: 1 session, 1 conversation, 1 planning_item, 2 references.
```

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -s http://127.0.0.1:8765/planning-items/PI-107 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['identifier'],'|',d['status'],'|',d['title'])"
curl -s http://127.0.0.1:8765/sessions/SES-117 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d.get('session_identifier'),'|',d.get('session_status'))"
# Confirm the session->workstream and conversation->session references resolved.
```

## Commit snapshot regeneration

The apply script regenerates `PRDs/product/crmbuilder-v2/db-export/*.json` and writes `deposit-event-logs/dep_NNN.log`. Commit them with the payload, this prompt, and the regenerated snapshots:

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_117.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-117.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-117 close-out — file PI-107 (surface PI timestamps in UI)"
```
Doug pushes after review (Claude Code push convention).
