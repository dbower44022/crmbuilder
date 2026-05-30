# Apply close-out — SES-125 / CNV-027 (harden v2 API lifecycle: rotating logs + UI auto-restart)

## Purpose

Apply the SES-125 close-out for the API-lifecycle hardening work (rotating logs + UI auto-restart on connection loss), shipped in commit `9f8ec27` (PR #3, merged `07b9313`).

**Net effect**
- Creates session **SES-125**, conversation **CNV-027**.
- Creates planning items **PI-110** (the work; created Open then flipped to **Resolved** by this session) and **PI-111** (deferred `/health` heartbeat follow-on, **Open**).
- Creates work ticket **WT-061** (`kickoff_prompt`, `ready`, → `prompts/CLAUDE-CODE-PROMPT-kickoff-pi-110.md`), anchoring PI-110.
- Creates decision **DEC-333** (self-resolution scope choice).
- Records commit **9f8ec27**.
- Creates references: `CNV-027 conversation_belongs_to_session SES-125`, `CNV-027 conversation_belongs_to_workstream WS-011`, `SES-125 session_belongs_to_workstream WS-011`, `WT-061 addresses PI-110`, `DEC-333 decided_in CNV-027`, `DEC-333 is_about PI-110`, plus the `CNV-027 resolves PI-110` edge (atomic flip).

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short
git pull --rebase origin main
curl -s http://127.0.0.1:8765/health
for e in sessions conversations planning-items work-tickets decisions; do printf "%s -> " "$e"; curl -s "http://127.0.0.1:8765/$e/next-identifier"; echo; done
# Expect: sessions SES-125, conversations CNV-027, planning-items PI-110, work-tickets WT-061, decisions DEC-333.
# If any head advanced (parallel work), re-key the payload + this prompt before applying.
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_125.json
ls PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-kickoff-pi-110.md
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_125.json
# Expected OK: 1 session, 1 conversation, 1 work_ticket, 2 planning_items, 1 commit,
#   1 decision, 6 references, 1 resolves_planning_items (CNV-027 resolves PI-110).
```

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
# PI-110 resolved, PI-111 open.
for pi in PI-110 PI-111; do printf "%s status: " "$pi"; curl -s "http://127.0.0.1:8765/planning-items/$pi" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['status'])"; done
# Expect PI-110 Resolved, PI-111 Open.
printf "WT-061 addresses: "; curl -s "http://127.0.0.1:8765/references/touching/planning_item/PI-110" | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print([(r['relationship'],r['source_id']) for r in d['as_target']])"
printf "DEC-333: "; curl -s "http://127.0.0.1:8765/decisions/DEC-333" | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['status'], '|', d['title'])"
```

## Commit snapshot regeneration

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add CLAUDE.md \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_125.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-125.md \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-kickoff-pi-110.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: SES-125 close-out — harden API lifecycle (rotating logs + UI auto-restart), resolve PI-110"
```
Doug pushes after review (Claude Code push convention).
