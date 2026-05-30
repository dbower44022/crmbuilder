# Apply close-out — SES-123 / CNV-025 (backfill PI-101 kickoff work ticket)

## Purpose

Apply the SES-123 governance-backfill close-out: creates the kickoff work ticket PI-101 never had.

**Net effect**
- Creates session **SES-123**, conversation **CNV-025**.
- Creates work ticket **WT-058** (`kickoff_prompt`, `ready`) pointing at `prompts/CLAUDE-CODE-PROMPT-kickoff-pi-101.md`.
- Creates references: `CNV-025 conversation_belongs_to_session SES-123`, `SES-123 session_belongs_to_workstream WS-011`, `WT-058 addresses PI-101`.
- No code change, no decisions, no planning-item status change (PI-101 stays Resolved).

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short
git pull --rebase origin main
curl -s http://127.0.0.1:8765/health
for e in sessions conversations work-tickets; do printf "%s -> " "$e"; curl -s "http://127.0.0.1:8765/$e/next-identifier"; echo; done
# Expect: sessions SES-123, conversations CNV-025, work-tickets WT-058.
# Parallel sessions are active — re-key the payload + this prompt if any advanced.
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_123.json
ls PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-kickoff-pi-101.md
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_123.json
# Expected OK: 1 session, 1 conversation, 1 work_ticket, 2 references.
```

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -s http://127.0.0.1:8765/work-tickets/WT-058 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['work_ticket_identifier'],'|',d['work_ticket_status'],'|',d['work_ticket_kind'])"
curl -s http://127.0.0.1:8765/references/touching/planning_item/PI-101 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print([(r['relationship'],r['source_id']) for r in d['as_target']])"
# Expect WT-058 addresses PI-101 among the edges.
```

## Commit snapshot regeneration

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_123.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-123.md \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-kickoff-pi-101.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-123 close-out — backfill PI-101 kickoff work ticket (WT-058)"
```
Doug pushes after review (Claude Code push convention).
