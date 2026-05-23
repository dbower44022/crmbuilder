# CLAUDE-CODE-PROMPT — Apply SES-066 close-out payload

**Last Updated:** 05-23-26 23:50
**Purpose:** Apply the SES-066 close-out payload — the ARCHITECTURE-mode planning conversation that scoped the PI-026 historical-applies-as-deposit-events backfill, settled five governing decisions (DEC-206 references included in wrote_record edges; DEC-207 sequential identifier allocation Option A; DEC-208 reference-resolution forward-then-reverse-then-skip with data-quality logging; DEC-209 apply_context conventions for backfilled DEPs; DEC-210 24-record scope after orphan-CONV constraint excluded SES-001 and SES-046), and authored the Claude Code prompt that will land 24 close_out_payload records, 24 deposit_event records, and 269 reference edges out-of-band.
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_066.json`
**Predecessor sessions:** SES-065 (PI-045 V2 remote-access deployment planning, committed to origin at 9a465a0). Its close-out must be applied before this prompt runs — DEP-018 and COP-065 must be present from that apply. If `curl -sf http://127.0.0.1:8765/sessions/SES-065` returns 404, apply the SES-065 close-out first via `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-065.md` and return here.
**Successor prompt:** After this apply lands, run the PI-026 backfill prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-026-historical-applies-deposit-events-backfill.md` to land the 24 close_out_payload records (COP-009..COP-032), 24 deposit_event records (DEP-020..DEP-043), 24 placeholder log files, and 269 supporting reference edges. The backfill prompt depends on DEC-206..210 (landed by this apply) being present for its commit messages to reference; running it before this apply does not break correctness, but the dependency is more legible when applied in order.

---

## Scope

Apply `close-out-payloads/ses_066.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-066)
- 5 decisions (DEC-206 through DEC-210)
- 0 planning items
- 5 references (5 `decided_in` linking each decision to SES-066)

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

This payload does NOT author any close_out_payload records, deposit_event records, log files, or wrote_record / applies_close_out_payload / produced_by_conversation edges for the PI-026 historical inventory. Those land via the backfill prompt named above, which installs `crmbuilder-v2/scripts/backfill_pi_026_historical_applies_deposit_events.py` and runs it. The close-out payload's session record's `artifacts_produced` and `in_flight_at_end` fields note this explicitly.

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

# Pull latest commits from origin/main (SES-066 payload and the PI-026
# backfill prompt were pushed from the planning sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_066.json

# Verify the backfill prompt also exists (same sandbox push)
ls -la ../PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-026-historical-applies-deposit-events-backfill.md

# Verify the API is routed to the CRMBUILDER engagement (the dogfood DB, not CBM)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect 65 sessions, latest SES-065 (after PI-045's SES-065 apply has landed). After this apply, expect 66 sessions, latest SES-066.

# Verify SES-065 has been applied (the immediate predecessor — PI-045's close-out)
curl -sf http://127.0.0.1:8765/sessions/SES-065 | head -5
# If this returns 404, the SES-065 (PI-045) close-out has not been applied.
# Apply it first via
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-065.md
# then return to this prompt.

# Capture pre-apply identifier heads for post-apply verification
echo "=== Pre-apply heads ==="
echo "Sessions:"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Decisions:"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Planning items:"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Close-out payloads (expect COP-065 from PI-045's apply):"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1] if d else 'none')"
echo "Deposit events (expect DEP-018 from PI-045's apply):"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1] if d else 'none')"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected pre-apply heads (after the PI-045 SES-065 close-out apply has landed): SES-065, DEC-205, PI-045, COP-065, DEP-018. Reference count varies; capture for delta verification.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_066.json
```

Expected output structure:

- 1 session OK (SES-066)
- 5 decisions OK (DEC-206 through DEC-210)
- 0 planning items
- 5 references OK
- 1 deposit_event written at apply close (DEP-019 lazy-created against a lazy-created COP-066)

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

Note: the apply script lazy-creates COP-066 (the close_out_payload for SES-066 itself) and writes a deposit_event (DEP-019). The DEP head advances from DEP-018 to DEP-019; the COP head advances from COP-065 to COP-066. (Pre-apply state expected: DEP-018 and COP-065 — both lazy-created by the earlier PI-045 SES-065 close-out apply, which must already have landed before this prompt runs.) PI-026's backfill prompt allocates DEPs starting at DEP-020 and COPs starting at COP-009 (the latter fills the gap between Phase 1's COP-008 and the real-time COP-056..COP-066 range), so no allocation collision with the lazy-created records.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-066):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-210):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-045 — unchanged):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Close-out payloads (expect COP-066 lazy-created):"
curl -s http://127.0.0.1:8765/close-out-payloads | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1])"
echo "Deposit events (expect DEP-019 lazy-created):"
curl -s http://127.0.0.1:8765/deposit-events | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1])"

# Spot check SES-066
curl -s http://127.0.0.1:8765/sessions/SES-066 | python3 -m json.tool | head -20

# Spot check DEC-206 (references-in-wrote_record decision) — confirm DEC-206 landed
curl -s http://127.0.0.1:8765/decisions/DEC-206 | python3 -m json.tool | head -20

# Spot check DEC-210 (24-record scope decision) — confirm DEC-210 landed
curl -s http://127.0.0.1:8765/decisions/DEC-210 | python3 -m json.tool | head -20

# Spot check a decided_in reference: find DEC-206 → SES-066 reference and confirm it resolves
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-206' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship_kind'], ']') for r in d]"
# Expect at minimum: DEC-206 -> SES-066 [ decided_in ]

# Confirm reference total delta is +12 from pre-apply
# (5 payload decided_in refs + 5 wrote_record edges from the apply script's deposit_event POST + 1 applies_close_out_payload edge to the lazy-created COP-066 + 1 close_out_payload_produced_by_conversation edge that the apply path may auto-author; if the apply script doesn't auto-author the produced_by_conversation edge for the lazy-created COP-066, this drops to +11)
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected: sessions head SES-066, decisions head DEC-210, planning_items head PI-045 (unchanged), close_out_payloads head COP-066 (lazy-created), deposit_events head DEP-019 (lazy-created), reference total +11 or +12 from pre-apply.

---

## Commit snapshot regeneration

The apply script transactionally regenerates the engagement's db-export JSON snapshots on every API write via the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`. The `change_log.json` file also gets one audit row per write with before/after payloads. After a successful apply, commit the regenerated snapshots together with the deposit-event log:

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect what changed (should be sessions.json, decisions.json, references.json,
# close_out_payloads.json, deposit_events.json, change_log.json, plus the deposit-event log)
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit the snapshot regeneration in a single commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-066 close-out: PI-026 historical-applies-as-deposit-events backfill planned

Records landed via apply_close_out.py against CRMBUILDER engagement:
- 1 session (SES-066)
- 5 decisions (DEC-206 references included in wrote_record edges,
  departing from Phase 1 precedent;
  DEC-207 sequential identifier allocation Option A continues
  Phase 1 pattern;
  DEC-208 reference resolution forward-then-reverse-then-skip with
  data-quality logging;
  DEC-209 apply_context conventions for backfilled DEPs;
  DEC-210 24-record scope after orphan-CONV constraint excluded
  SES-001 and SES-046)
- 0 planning items
- 5 references (5 decided_in)
- 1 close_out_payload lazy-created (COP-066)
- 1 deposit_event lazy-created (DEP-019)

24 close_out_payload records (COP-009..COP-032), 24 deposit_event
records (DEP-020..DEP-043), 24 placeholder log files, and 269
supporting reference edges (24 close_out_payload_produced_by_
conversation, 24 deposit_event_applies_close_out_payload, 221
deposit_event_wrote_record covering 24 session + 63 decision + 9
planning_item + 125 reference targets) land out-of-band via the
backfill prompt at PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-
PROMPT-pi-026-historical-applies-deposit-events-backfill.md, applied
next."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-apply heads: SES-065, DEC-205, PI-045, COP-065, DEP-018, references = N (captured)
- Post-apply heads: SES-066, DEC-210, PI-045 (unchanged), COP-066 (lazy-created), DEP-019 (lazy-created), references = N + 11 or +12
- Record counts (expect 1 session OK, 5 decisions OK, 0 planning items, 5 references OK, 0 SKIPs on first run, 1 lazy-created COP, 1 lazy-created DEP)
- Snapshot commit SHA from the commit-snapshot-regeneration step
- Next prompt to run: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-026-historical-applies-deposit-events-backfill.md` — installs and runs the backfill script that lands the 24 close_out_payload records (COP-009..COP-032), 24 deposit_event records (DEP-020..DEP-043), 24 placeholder log files, and 269 supporting reference edges
