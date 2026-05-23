# CLAUDE-CODE-PROMPT — Apply SES-057 close-out payload

**Last Updated:** 05-23-26 19:00
**Purpose:** Apply the SES-057 close-out payload — the diagnostic-and-design conversation that establishes the Code Change Lifecycle workstream, adopts Option III (first-class commit entities), and authors seven planning items (PI-027 through PI-033) plus three decisions (DEC-168 through DEC-170) plus the workstream-establishing kickoff document.
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_057.json`
**Predecessor session:** SES-056 (v0.7 governance entity release shipped). The SES-056 payload should already be applied per its own apply prompt. If `curl -sf http://127.0.0.1:8765/sessions/SES-056` returns 404, apply SES-056's close-out first and then return here.

---

## Scope

Apply `close-out-payloads/ses_057.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-057)
- 3 decisions (DEC-168 through DEC-170)
- 7 planning items (PI-027 through PI-033)
- 10 references (3 `decided_in` linking each decision to SES-057; 7 `is_about` linking SES-057 to each of the 7 new planning items)

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

This payload does NOT author the workstream record, the kickoff document as a work_ticket record, or any commit records. The close-out payload format does not yet support those sections — extending it is part of the workstream this payload establishes (PI-030). The kickoff document lives as a markdown file at `PRDs/product/crmbuilder-v2/code-change-lifecycle-workstream-establishing-kickoff.md` and will be back-filled as a WT-NNN record via PI-033 after PI-030 ships.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Pull latest commits from origin/main (SES-057 payload was pushed from the diagnostic-and-design sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_057.json

# Verify the kickoff document exists (it should — produced in the same sandbox push)
ls -la ../PRDs/product/crmbuilder-v2/code-change-lifecycle-workstream-establishing-kickoff.md

# Verify the API is routed to the CRMBUILDER engagement (the dogfood DB, not CBM)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect 56 sessions, latest SES-056. After this apply, expect 57 sessions, latest SES-057.

# Verify SES-056 has been applied (the predecessor)
curl -sf http://127.0.0.1:8765/sessions/SES-056 | head -5
# If this returns 404, SES-056 has not been applied. Apply its close-out first via
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-056.md
# Return to this prompt after SES-056 lands.

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

Expected pre-apply heads: SES-056, DEC-167, PI-026. Reference count will vary; capture for delta verification.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_057.json
```

Expected output structure:

- 1 session OK (SES-057)
- 3 decisions OK (DEC-168, DEC-169, DEC-170)
- 7 planning items OK (PI-027 through PI-033)
- 10 references OK
- 1 deposit_event written at apply close

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-057):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-170):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-033):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"

# Spot check SES-057
curl -s http://127.0.0.1:8765/sessions/SES-057 | python3 -m json.tool | head -20

# Spot check DEC-168 (the Option III adoption decision)
curl -s http://127.0.0.1:8765/decisions/DEC-168 | python3 -m json.tool | head -20

# Spot check PI-027 (the methodology drafting planning item)
curl -s http://127.0.0.1:8765/planning-items/PI-027 | python3 -m json.tool | head -10

# Spot check a decided_in reference: find one DEC-168 → SES-057 reference and confirm it resolves
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-168' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum: DEC-168 -> SES-057 [ decided_in ]

# Spot check planning_items status — all 7 new PIs should be Open
for pi in PI-027 PI-028 PI-029 PI-030 PI-031 PI-032 PI-033; do
  status=$(curl -s http://127.0.0.1:8765/planning-items/$pi | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['status'])")
  echo "$pi: $status"
done
# Expect all seven to print Open.

# Confirm the planning_items table now has 33 records
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('total planning_items:', len(d))"
# Expect 33 (was 26 before this apply).
```

---

## Commit snapshot regeneration

The apply script transactionally regenerates the engagement's db-export JSON snapshots on every API write via the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`. The `change_log.json` file also gets one audit row per write with before/after payloads. After a successful apply, commit the regenerated snapshots together with the deposit-event log:

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect what changed (should be the seven governance tables plus change_log plus the deposit-event log)
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit the snapshot regeneration in a single commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-057 close-out: Code Change Lifecycle workstream established

Records landed via apply_close_out.py against CRMBUILDER engagement:
- 1 session (SES-057)
- 3 decisions (DEC-168 adopt Option III, DEC-169 methodology-first
  sequencing, DEC-170 seven-PI workstream decomposition)
- 7 planning items (PI-027 methodology; PI-028 commit schema spec;
  PI-029 schema/vocab/access/API; PI-030 close-out payload + apply +
  git ingestion; PI-031 UI; PI-032 methodology rollout; PI-033 back-fill)
- 10 references (3 decided_in, 7 is_about)
- 1 deposit_event"

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-apply heads: SES-056, DEC-167, PI-026, references = N (captured)
- Post-apply heads: SES-057, DEC-170, PI-033, references = N + 10
- Record counts (expect 1 session OK, 3 decisions OK, 7 planning items OK, 10 references OK, 0 SKIPs on first run)
- Snapshot commit SHA from the commit-snapshot-regeneration step
- Next-conversation kickoff path: `PRDs/product/crmbuilder-v2/code-change-lifecycle-workstream-establishing-kickoff.md` — open a new Claude.ai conversation against that kickoff to begin PI-027 (the methodology drafting conversation)
