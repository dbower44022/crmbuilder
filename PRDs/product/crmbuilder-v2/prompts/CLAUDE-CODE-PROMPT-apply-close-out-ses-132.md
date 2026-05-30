# Apply close-out — SES-132 / CNV-034 (governance & delivery redesign — 5 decisions + migration PI)

Run from Claude Code at the repo root with the v2 API up. Identifiers are provisional and re-verify at apply; re-key on collision.

## Net effect

Lands in the **CRMBUILDER** engagement:

- 1 session — **SES-132** (status `complete`)
- 1 conversation — **CNV-034** (status `complete`), belongs to SES-132 and to Project WS-014
- 1 **new Project — WS-014** "Governance & Delivery Redesign" (created in the pre-step, not by the payload)
- 5 decisions — **DEC-340..DEC-344** (drop area version prefix; rename `workstream`→`Project`; two-tier areas + relocate area onto Work Task; adopt three-tier agent-delivery target; shelve WS-012), each `decided_in` CNV-034
- 1 planning item — **PI-112** (the migration umbrella), status `Open`
- 1 work ticket — **WT-063** (kickoff for PI-112, status `ready`), `addresses` PI-112
- 8 references total

**Not changed by this apply:** PI-081 and PI-083 remain `Open`. They are governed-as-shelved per DEC-344; a clean status change to `Deferred` is deferred until the Planning Item lifecycle lands (part of PI-112). No code commits in this close-out.

## Pre-flight

```bash
cd crmbuilder-v2
curl -s http://127.0.0.1:8765/health
# Re-verify heads haven't advanced in parallel; re-key the payload + this prompt on collision.
for ep in sessions conversations decisions planning-items work-tickets; do
  curl -s "http://127.0.0.1:8765/$ep/next-identifier"; echo; done
# Expect: SES-132, CNV-034, DEC-340, PI-112, WT-063 (or later — re-key on collision).

# Confirm the payload is present:
ls -1 ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_132.json
```

**Pre-step — create the new Project WS-014 out-of-band** (mirrors the SES-079 pattern that created WS-012; a Project/`workstream` is not created by the close-out payload). Verify the field names against the live `/workstreams` POST schema before running:

```bash
# VERIFY FIELD NAMES against the current workstreams schema, then:
curl -s -X POST http://127.0.0.1:8765/workstreams \
  -H 'Content-Type: application/json' \
  -d '{"workstream_identifier":"WS-014","workstream_title":"Governance & Delivery Redesign","workstream_description":"Migrate the governance & delivery model to the target data model per PRDs/product/crmbuilder-v2/governance-redesign-target-model.md: Project rename, two-tier System/Engagement areas with area relocated onto a single-area Work Task, Planning Item lifecycle, Workstream-as-delivery-phase, and the three-tier pull-based agent-delivery target. Opened at SES-132.","workstream_status":"active"}'
# Re-key to the next free WS- identifier if WS-014 is taken; update the two CNV-034->WS-014 references in the payload to match.
```

## Apply

```bash
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_132.json
# Expect OK: 1 session, 1 conversation, 5 decisions, 1 planning_item, 1 work_ticket, 8 references.
```

## Post-apply verification

```bash
curl -s http://127.0.0.1:8765/sessions/SES-132 | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['session_status'])"            # complete
curl -s http://127.0.0.1:8765/planning-items/PI-112 | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['status'])"               # Open
curl -s "http://127.0.0.1:8765/references/from/decision/DEC-340" | python3 -c "import sys,json;[print(r['relationship'],r['target_type'],r['target_id']) for r in json.load(sys.stdin)['data']]"   # decided_in conversation CNV-034
curl -s "http://127.0.0.1:8765/references/from/work_ticket/WT-063" | python3 -c "import sys,json;[print(r['relationship'],r['target_id']) for r in json.load(sys.stdin)['data']]"                  # addresses PI-112
curl -s "http://127.0.0.1:8765/references/from/conversation/CNV-034" | python3 -c "import sys,json;[print(r['relationship'],r['target_id']) for r in json.load(sys.stdin)['data']]"               # belongs_to_session SES-132, belongs_to_workstream WS-014
```

## Commit snapshot

The apply transactionally regenerates the `db-export/` JSON snapshots and appends the deposit-event log. Commit them with the design doc, payload, and this prompt in one commit:

```bash
git add ../PRDs/product/crmbuilder-v2/db-export \
        ../PRDs/product/crmbuilder-v2/deposit-event-logs \
        ../PRDs/product/crmbuilder-v2/governance-redesign-target-model.md \
        ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_132.json \
        ../PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-132.md
git commit -m "v2: SES-132 close-out — governance & delivery redesign (DEC-340..344); open WS-014 + migration PI-112"
```

## Done

Reply with: heads before/after, applied record counts, the snapshot-commit SHA, and the next kickoff path (`PRDs/product/crmbuilder-v2/governance-redesign-target-model.md`, the kickoff artifact for PI-112).
