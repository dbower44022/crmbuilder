# CLAUDE-CODE-PROMPT — Apply SES-058 close-out payload

**Last Updated:** 05-23-26 01:37
**Purpose:** Apply the SES-058 close-out payload — the planning conversation that established the audit feature v1.2 workstream, captured four design decisions (DEC-171 through DEC-174), and decomposed the workstream into eleven sequential Claude Code prompts (PI-034 through PI-044) corresponding to the audit-v1.2 A through K prompt series.
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_058.json`
**Predecessor session:** SES-057 (Code Change Lifecycle workstream established). The SES-057 payload should already be applied per its own apply prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-057.md`. If `curl -sf http://127.0.0.1:8765/sessions/SES-057` returns 404, apply SES-057's close-out first and then return here.

---

## Scope

Apply `close-out-payloads/ses_058.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-058)
- 4 decisions (DEC-171 through DEC-174)
- 11 planning items (PI-034 through PI-044)
- 15 references (4 `decided_in` linking each decision to SES-058; 11 `is_about` linking SES-058 to each of the 11 new planning items)

Net effect on the CRMBUILDER engagement database after apply:

- Sessions head advances from SES-057 to SES-058
- Decisions head advances from DEC-170 to DEC-174
- Planning items head advances from PI-033 to PI-044
- Total reference count increases by 15
- One deposit_event written at apply close per the v0.7 governance convention

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present. On first run, every record should return OK; if any record returns 409 SKIP on first run, halt and investigate.

This payload does NOT author the audit-v1.2-planning.md document as a reference_book record, the eleven CLAUDE-CODE-PROMPT files as work_ticket records, or any commit records. The close-out payload format does not yet support those sections — extending it is part of the Code Change Lifecycle workstream established in SES-057 (PI-030). The planning document lives as a markdown file at `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` and will be back-filled as a reference_book record via PI-033 (the historical back-fill PI) after PI-030 ships the payload format extension.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Working tree clean
git status --porcelain
# Expected: empty output

# Git identity
git config user.name
git config user.email
# Expected: Doug / doug@dougbower.com

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Pull latest commits from origin/main (SES-058 payload and planning doc were pushed from the sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_058.json

# Verify the planning document exists (it should — produced in the same sandbox push as the payload)
ls -la ../PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md

# Verify the API is routed to the CRMBUILDER engagement (the dogfood DB, not CBM)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect 57 sessions, latest SES-057. After this apply, expect 58 sessions, latest SES-058.

# Verify SES-057 has been applied (the predecessor)
curl -sf http://127.0.0.1:8765/sessions/SES-057 | head -5
# If this returns 404, SES-057 has not been applied. Apply its close-out first via
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-057.md
# Return to this prompt after SES-057 lands.

# Capture pre-apply identifier heads for post-apply verification
echo "=== Pre-apply heads ==="
echo "Sessions:"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Decisions:"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Planning items:"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "References (count, since these are auto-identified):"
curl -s 'http://127.0.0.1:8765/references?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected pre-apply heads: SES-057, DEC-170, PI-033. Reference count will vary; capture for delta verification (should increase by exactly 15 after apply).

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_058.json
```

Expected output structure:

- 1 session OK (SES-058)
- 4 decisions OK (DEC-171, DEC-172, DEC-173, DEC-174)
- 11 planning items OK (PI-034 through PI-044)
- 15 references OK (4 decided_in plus 11 is_about)
- 1 deposit_event written at apply close

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-058):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-174):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-044):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"

# Reference count delta (expect exactly +15 vs the pre-apply count)
echo "References (post-apply count):"
curl -s 'http://127.0.0.1:8765/references?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"

# Spot check SES-058
curl -s http://127.0.0.1:8765/sessions/SES-058 | python3 -m json.tool | head -20

# Spot check DEC-172 (the Option B roles/teams full round-trip decision — the linchpin decision of the workstream)
curl -s http://127.0.0.1:8765/decisions/DEC-172 | python3 -m json.tool | head -20

# Spot check PI-034 (the first prompt in the audit-v1.2 series — the next conversation's deliverable)
curl -s http://127.0.0.1:8765/planning-items/PI-034 | python3 -m json.tool | head -10

# Spot check a decided_in reference: find all DEC-172 references and confirm one resolves to SES-058 with relationship decided_in
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-172' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum: DEC-172 -> SES-058 [ decided_in ]

# Spot check the is_about references for SES-058: all 11 should appear
curl -s 'http://127.0.0.1:8765/references?source_type=session&source_id=SES-058&relationship=is_about' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f'Found {len(d)} is_about references from SES-058'); [print(' ', r['source_id'], '->', r['target_id']) for r in d]"
# Expect 11 references, one per PI-034 through PI-044

# Spot check planning_items status — all 11 new PIs should be Open
echo "=== New PI statuses (expect all Open) ==="
for pi in PI-034 PI-035 PI-036 PI-037 PI-038 PI-039 PI-040 PI-041 PI-042 PI-043 PI-044; do
  status=$(curl -s "http://127.0.0.1:8765/planning-items/${pi}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['status'])")
  echo "  ${pi}: ${status}"
done
```

---

## Commit snapshot regeneration

The apply script transactionally regenerates the engagement's `db-export/` JSON snapshots after the apply succeeds (per the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`). A row is also appended to `db-export/change_log.json` capturing before/after payloads for this apply event. Do NOT invoke any standalone exporter — none exists.

Verify the snapshots reflect the new records:

```bash
cd ~/Dropbox/Projects/crmbuilder
git status --porcelain PRDs/product/crmbuilder-v2/db-export/
# Expected: changes to sessions.json, decisions.json, planning_items.json, references.json, change_log.json, plus the deposit_events.json and close_out_payloads.json snapshots if the v0.7 governance entity tables are wired in

# Quick smoke test on the regenerated sessions snapshot
python3 -c "
import json
with open('PRDs/product/crmbuilder-v2/db-export/sessions.json') as f:
    data = json.load(f)
sessions = data if isinstance(data, list) else data.get('data', data.get('sessions', []))
ids = sorted([s.get('identifier','') for s in sessions if s.get('identifier','').startswith('SES-')])
print(f'Sessions in snapshot: {len(ids)}, highest: {ids[-1]}')
"
# Expect highest SES-058
```

Commit the regenerated snapshots and change_log as a single commit:

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git commit -m "Apply SES-058 close-out — audit-v1.2 workstream established

Lands the planning conversation's governance records into the CRMBUILDER
engagement database: SES-058 session record, four decisions (DEC-171
users out of audit scope, DEC-172 roles/teams full round-trip,
DEC-173 all five parts of Section 12 in scope, DEC-174 pre-flight
entity-picker discovery), eleven planning items (PI-034 through
PI-044 corresponding to audit-v1.2 prompts A through K), and fifteen
references (four decided_in plus eleven is_about).

Snapshot regeneration committed alongside the apply per the
_refresh_snapshot hook convention; change_log.json captures the
apply event payload."

git push origin main
```

---

## Done

Report back to Doug with:

- Pre-apply heads (SES, DEC, PI) and post-apply heads (expect SES-058, DEC-174, PI-044)
- Record counts from the apply (expect 1 session OK + 4 decisions OK + 11 planning items OK + 15 references OK + 1 deposit_event)
- Snapshot regeneration commit SHA
- Next-conversation kickoff: a fresh Claude.ai conversation against the planning document at `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` to author `CLAUDE-CODE-PROMPT-audit-v1.2-A-roles-teams-recognition.md` as the PI-034 deliverable
