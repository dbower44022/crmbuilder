# Apply close-out — SES-130 / CNV-032 (implement + resolve PI-111: /health heartbeat)

## Purpose

Apply the SES-130 close-out for the `/health` heartbeat (PI-111), the deferred follow-on to PI-110 / DEC-333. Code shipped in commit `01c948d` (on `main`).

**Net effect**
- Creates session **SES-130**, conversation **CNV-032**.
- Creates work ticket **WT-062** (`kickoff_prompt`, `ready`, → `prompts/CLAUDE-CODE-PROMPT-kickoff-pi-111.md`), anchoring PI-111.
- Records commits **01c948d** (heartbeat) and **9fd649c** (incidental 3-test fix for PI-108's stale columns).
- Creates references: `CNV-032 conversation_belongs_to_session SES-130`, `CNV-032 conversation_belongs_to_workstream WS-011`, `SES-130 session_belongs_to_workstream WS-011`, `WT-062 addresses PI-111`, plus the `CNV-032 resolves PI-111` edge (atomic flip).
- No new planning items, no decisions. **PI-111 → Resolved.**

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short
git pull --rebase origin main
curl -s http://127.0.0.1:8765/health
for e in sessions conversations work-tickets; do printf "%s -> " "$e"; curl -s "http://127.0.0.1:8765/$e/next-identifier"; echo; done
# Expect: sessions SES-130, conversations CNV-032, work-tickets WT-062.
# Parallel sessions have been active — re-key the payload + this prompt if any head advanced.
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_130.json
ls PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-kickoff-pi-111.md
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_130.json
# Expected OK: 1 session, 1 conversation, 1 work_ticket, 0 planning_items, 2 commits,
#   0 decisions, ~4 references (3 explicit + auto), 1 resolves_planning_items (CNV-032 resolves PI-111).
```

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
printf "PI-111 status: "; curl -s http://127.0.0.1:8765/planning-items/PI-111 | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['status'])"
# Expect Resolved.
printf "WT-062 addresses PI-111: "; curl -s "http://127.0.0.1:8765/references/touching/planning_item/PI-111" | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print([(r['relationship'],r['source_id']) for r in d['as_target']])"
printf "SES-130: "; curl -s http://127.0.0.1:8765/sessions/SES-130 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['session_status'],'|',d['session_title'])"
```

## Commit snapshot regeneration

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_130.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-130.md \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-kickoff-pi-111.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-130 close-out — implement + resolve PI-111 (/health heartbeat)"
```
Doug pushes after review (Claude Code push convention).
