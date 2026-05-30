# Apply close-out — SES-121 / CNV-023 (universal timestamp visibility setup)

## Purpose

Land the governance scaffolding for the universal created/last-edited timestamp visibility work.

**Net effect (records that will land):**
- **WS-013** (workstream) — *already created via direct API POST during the authoring session; not in this payload.*
- **REQ-002** (requirement) — *already created via direct API POST during the authoring session; not in this payload.*
- **SES-121** (session, `complete`) + **CNV-023** (conversation, `complete`).
- **PI-108** (planning item, `Open`, `pending_work`) — the implementation work item.
- **WT-057** (work ticket, `kickoff_prompt`, `ready`) → file `PRDs/product/crmbuilder-v2/universal-timestamp-visibility-kickoff.md`.
- **6 references**: CNV-023→SES-121 (`conversation_belongs_to_session`), CNV-023→WS-013 (`conversation_belongs_to_workstream`), SES-121→WS-013 (`session_belongs_to_workstream`), WT-057→PI-108 (`addresses`), PI-108→REQ-002 (`is_about`), PI-108→WS-013 (`is_about`), REQ-002→WS-013 (`is_about`).
- No decisions, no commits, no resolved/addressed PI status flips (PI-108 is filed Open).

## Identifier note — re-keyed

This session was re-keyed from **SES-120/CNV-022 → SES-121/CNV-023** because an unapplied PI-031 close-out (`close-out-payloads/ses_120.json` + its apply prompt) already claims SES-120/CNV-022/DEC-332. **Do not apply this payload as a substitute for that one** — they are independent. PI-108 and WT-057 were unaffected by the re-key (the PI-031 payload creates neither).

## Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git status --short                       # expect the new kickoff, payload, apply prompt untracked
curl -s http://127.0.0.1:8765/health     # expect {"data":{"ok":true},...}
# Confirm WS-013 and REQ-002 already exist (created via direct POST):
curl -s http://127.0.0.1:8765/workstreams/WS-013 | python3 -c "import sys,json;print((json.load(sys.stdin).get('data') or {}).get('workstream_identifier'))"
curl -s http://127.0.0.1:8765/requirements/REQ-002 | python3 -c "import sys,json;print((json.load(sys.stdin).get('data') or {}).get('requirement_identifier'))"
# Pre-apply heads (expect SES-120, CNV-022, PI-108, WT-057 — note SES/CNV still at 120/022 due to the pending PI-031 payload):
for t in sessions conversations planning-items work-tickets; do printf "%-16s " "$t"; curl -s http://127.0.0.1:8765/$t/next-identifier | python3 -c "import sys,json;print(json.load(sys.stdin).get('data'))"; done
```

## Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_121.json
```

Expected: SES-121 + CNV-023 + PI-108 + WT-057 + 6 references inserted; close_out_payload + deposit_event lazy-created; `db-export/*.json` snapshots regenerated; `deposit-event-logs/dep_NNN.log` written.

## Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -s http://127.0.0.1:8765/sessions/SES-121 | python3 -c "import sys,json;print((json.load(sys.stdin).get('data') or {}).get('session_title'))"
curl -s http://127.0.0.1:8765/planning-items/PI-108 | python3 -c "import sys,json;d=json.load(sys.stdin).get('data') or {};print(d.get('status'),'|',d.get('title'))"
curl -s http://127.0.0.1:8765/work-tickets/WT-057 | python3 -c "import sys,json;d=json.load(sys.stdin).get('data') or {};print(d.get('work_ticket_status'),'|',d.get('work_ticket_file_path'))"
# WT-057 addresses PI-108 resolves:
curl -s "http://127.0.0.1:8765/references/from/work_ticket/WT-057" | python3 -c "import sys,json;[print(r['relationship_kind'],'->',r['target_type'],r['target_id']) for r in (json.load(sys.stdin).get('data') or [])]"
```

## Commit

Commit the regenerated snapshots + new artifacts together:

```bash
git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/ \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_121.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-121.md \
        PRDs/product/crmbuilder-v2/universal-timestamp-visibility-kickoff.md
git commit -m "v2: SES-121 close-out — establish WS-013 + REQ-002, file PI-108/WT-057 (universal timestamp visibility)"
```

Doug pushes after review (Claude Code push convention).
