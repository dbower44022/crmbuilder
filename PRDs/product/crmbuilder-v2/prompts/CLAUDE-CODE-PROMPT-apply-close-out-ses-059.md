# CLAUDE-CODE-PROMPT — Apply SES-059 close-out payload

**Last Updated:** 05-23-26 22:00
**Purpose:** Apply the SES-059 close-out payload — the ARCHITECTURE-mode planning conversation that scoped the PI-024 prior-workstreams backfill, settled three governing decisions (DEC-175 inventory, DEC-176 lifecycle-date strategy, DEC-177 master-plan bundling), and authored the Claude Code prompt that will land the six workstream records and three master-plan reference_book records out-of-band.
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_059.json`
**Predecessor session:** SES-058 (Audit feature v1.2 workstream established). The SES-058 close-out should already be applied per its own apply prompt. If `curl -sf http://127.0.0.1:8765/sessions/SES-058` returns 404, apply SES-058's close-out first and then return here.
**Successor prompt:** After this apply lands, run the PI-024 backfill prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-024-prior-workstreams-backfill.md` to land the six workstream records and three master-plan reference_book records. The backfill prompt depends on DEC-175, DEC-176, DEC-177 (landed by this apply) being present for its commit messages to reference; running it before this apply does not break correctness, but the dependency is more legible when applied in order.

---

## Scope

Apply `close-out-payloads/ses_059.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-059)
- 3 decisions (DEC-175, DEC-176, DEC-177)
- 0 planning items
- 3 references (3 `decided_in` linking each decision to SES-059)

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

This payload does NOT author the six workstream records (WS-002 through WS-007), the three reference_book records (RB-011 through RB-013), or the three `workstream_planned_in_reference_book` edges. Those land via the backfill prompt named above, which installs `crmbuilder-v2/scripts/backfill_pi_024_prior_workstreams.py` and runs it. The close-out payload's session record's `artifacts_produced` and `in_flight_at_end` fields note this explicitly.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Confirm clean working tree
git status

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Pull latest commits from origin/main (SES-059 payload and the PI-024
# backfill prompt were pushed from the planning sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_059.json

# Verify the backfill prompt also exists (it should — same sandbox push)
ls -la ../PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-024-prior-workstreams-backfill.md

# Verify the API is routed to the CRMBUILDER engagement (the dogfood DB, not CBM)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect 58 sessions, latest SES-058. After this apply, expect 59 sessions, latest SES-059.

# Verify SES-058 has been applied (the predecessor)
curl -sf http://127.0.0.1:8765/sessions/SES-058 | head -5
# If this returns 404, SES-058 has not been applied. Apply its close-out first via
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-058.md
# Return to this prompt after SES-058 lands.

# Capture pre-apply identifier heads for post-apply verification
echo "=== Pre-apply heads ==="
echo "Sessions:"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Decisions:"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Planning items:"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "References (count, since these are auto-identified):"
curl -s 'http://127.0.0.1:8765/references?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected pre-apply heads: SES-058, DEC-174, PI-044. Reference count varies; capture for delta verification.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_059.json
```

Expected output structure:

- 1 session OK (SES-059)
- 3 decisions OK (DEC-175, DEC-176, DEC-177)
- 0 planning items
- 3 references OK
- 1 deposit_event written at apply close

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-059):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-177):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-044 — unchanged):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"

# Spot check SES-059
curl -s http://127.0.0.1:8765/sessions/SES-059 | python3 -m json.tool | head -20

# Spot check DEC-175 (inventory decision) — confirm strict-six rationale
curl -s http://127.0.0.1:8765/decisions/DEC-175 | python3 -m json.tool | head -20

# Spot check DEC-176 (lifecycle-date strategy) — confirm Option B with Option C fallback
curl -s http://127.0.0.1:8765/decisions/DEC-176 | python3 -m json.tool | head -20

# Spot check a decided_in reference: find one DEC-175 → SES-059 reference and confirm it resolves
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-175' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship_kind'], ']') for r in d]"
# Expect at minimum: DEC-175 -> SES-059 [ decided_in ]

# Confirm reference total delta is +8 from pre-apply (3 payload refs + 4 wrote_record + 1 applies_close_out_payload)
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected: sessions head SES-059, decisions head DEC-177, planning_items head PI-044 (unchanged), reference total +8 from pre-apply (3 payload `decided_in` refs + 4 `wrote_record` edges from the apply script's deposit_event POST + 1 `applies_close_out_payload` edge to the lazy-created COP-059).

---

## Commit snapshot regeneration

The apply script transactionally regenerates the engagement's db-export JSON snapshots on every API write via the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`. The `change_log.json` file also gets one audit row per write with before/after payloads. After a successful apply, commit the regenerated snapshots together with the deposit-event log:

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect what changed (should be sessions.json, decisions.json, references.json,
# change_log.json, plus the deposit-event log)
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit the snapshot regeneration in a single commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-059 close-out: PI-024 prior-workstreams backfill planned

Records landed via apply_close_out.py against CRMBUILDER engagement:
- 1 session (SES-059)
- 3 decisions (DEC-175 inventory — strict six, defer three questionable
  candidates to Code Change Lifecycle workstream; DEC-176 lifecycle-date
  reconstruction — session-date range with document-timestamp fallback;
  DEC-177 master-plan reference_book bundling — three clean cases only)
- 0 planning items
- 3 references (3 decided_in)
- 1 deposit_event

Workstream records (WS-002 through WS-007) and reference_book records
(RB-011 through RB-013) arrive out-of-band via the backfill prompt at
PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-024-prior-
workstreams-backfill.md, applied next."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-apply heads: SES-058, DEC-174, PI-044, references = N (captured)
- Post-apply heads: SES-059, DEC-177, PI-044, references = N + 8 (3 payload refs + 4 wrote_record edges + 1 applies_close_out_payload edge)
- Record counts (expect 1 session OK, 3 decisions OK, 0 planning items, 3 references OK, 0 SKIPs on first run)
- Snapshot commit SHA from the commit-snapshot-regeneration step
- Next prompt to run: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-024-prior-workstreams-backfill.md` — installs and runs the backfill script that lands the six workstream records, three reference_book records, and three master-plan edges
