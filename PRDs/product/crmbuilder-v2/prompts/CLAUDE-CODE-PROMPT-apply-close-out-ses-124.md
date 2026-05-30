# Apply close-out — SES-124 / CNV-026 (backfill PI-107 + PI-031 kickoff tickets)

## Purpose

Apply the SES-124 governance-backfill close-out: creates the kickoff work tickets PI-107 and PI-031 never had (companion to SES-123, which did PI-101).

**Net effect**
- Creates session **SES-124**, conversation **CNV-026**.
- Creates work tickets **WT-059** (`kickoff_prompt`, `ready`, → `prompts/CLAUDE-CODE-PROMPT-kickoff-pi-107.md`) and **WT-060** (`kickoff_prompt`, `ready`, → `prompts/CLAUDE-CODE-PROMPT-kickoff-pi-031.md`).
- Creates references: `CNV-026 conversation_belongs_to_session SES-124`, `SES-124 session_belongs_to_workstream WS-011`, `WT-059 addresses PI-107`, `WT-060 addresses PI-031`.
- No code change, no decisions, no planning-item status change (both stay Resolved).

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short
git pull --rebase origin main
curl -s http://127.0.0.1:8765/health
for e in sessions conversations work-tickets; do printf "%s -> " "$e"; curl -s "http://127.0.0.1:8765/$e/next-identifier"; echo; done
# Expect: sessions SES-124, conversations CNV-026, work-tickets WT-059.
# Parallel sessions are active — re-key the payload + this prompt if any advanced.
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_124.json
ls PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-kickoff-pi-107.md
ls PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-kickoff-pi-031.md
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_124.json
# Expected OK: 1 session, 1 conversation, 2 work_tickets, 3 references.
```

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
for pi in PI-107 PI-031; do
  printf "%s addresses: " "$pi"
  curl -s "http://127.0.0.1:8765/references/touching/planning_item/$pi" | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print([(r['relationship'],r['source_id']) for r in d['as_target'] if r['relationship']=='addresses'])"
done
# Expect WT-059 addresses PI-107 and WT-060 addresses PI-031.
```

## Commit snapshot regeneration

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_124.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-124.md \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-kickoff-pi-107.md \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-kickoff-pi-031.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-124 close-out — backfill PI-107 + PI-031 kickoff tickets (WT-059, WT-060)"
```
Doug pushes after review (Claude Code push convention).
