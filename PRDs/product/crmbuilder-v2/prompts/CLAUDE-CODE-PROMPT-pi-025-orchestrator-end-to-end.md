# CLAUDE-CODE-PROMPT — Apply SES-060/061/062 close-outs and run PI-025 backfill (orchestrated, end-to-end)

**Last Updated:** 05-23-26 23:00
**Purpose:** Single-prompt orchestrator that pulls the latest commits, applies three close-out payloads in order (SES-060 audit-v1.2 planning resolved, SES-061 Code Change Lifecycle methodology drafted, SES-062 PI-025 planning), then runs the PI-025 prior-conversations backfill that lands WS-008, 37 work_tickets, 37 conversations, and ~140 reference edges. Replaces the manual five-prompt sequence with one end-to-end run.

**Halt-on-failure discipline:** every step verifies its outcome before the next step begins. If any verification fails, STOP, print the failure, and do not proceed.

**What lands on success:**
- 3 sessions (SES-060, SES-061, SES-062)
- 16 decisions (DEC-178..190 from SES-060/061, DEC-191..197 from SES-062)
- 1+ planning items (PI-028 commit-entity-schema kickoff from SES-061 close-out)
- 3 deposit_event records (one per close-out applied)
- 1 new workstream (WS-008 Audit feature v1.2)
- 1 workstream PATCH (WS-006 workstream_notes Option IV defer)
- 37 work_ticket records (WT-009..WT-045)
- 37 conversation records (CONV-009..CONV-045)
- ~150 new reference edges total

---

## Step 1 — Pull latest commits

```bash
cd ~/Dropbox/Projects/crmbuilder
git pull --rebase origin main
```

Verify all six required prompt and payload files are present:

```bash
for f in \
    PRDs/product/crmbuilder-v2/close-out-payloads/ses_060.json \
    PRDs/product/crmbuilder-v2/close-out-payloads/ses_061.json \
    PRDs/product/crmbuilder-v2/close-out-payloads/ses_062.json \
    PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-060.md \
    PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-061.md \
    PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-062.md \
    PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-025-prior-conversations-backfill.md \
    ; do
  if [ -f "$f" ]; then echo "  OK  $f"; else echo "  !! MISSING $f"; fi
done
```

If anything reports MISSING, halt — the pull did not bring everything down.

---

## Step 2 — API health and engagement routing

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2

curl -sf http://127.0.0.1:8765/health || { echo "API not running — start with: uv run crmbuilder-v2-api &"; exit 1; }

# Confirm routed to CRMBUILDER engagement (the dogfood DB, not CBM)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions; latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
```

Expect exactly **59 sessions, latest SES-059**. If the count or head is different, the API is routed to the wrong engagement or someone has applied records since this prompt was authored — halt and resolve before continuing.

---

## Step 3 — Capture pre-state heads

```bash
echo "=== Pre-state heads (snapshot taken before any apply) ==="
echo "Sessions:        $(curl -s http://127.0.0.1:8765/sessions        | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])")"
echo "Decisions:       $(curl -s http://127.0.0.1:8765/decisions       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])")"
echo "Planning items:  $(curl -s http://127.0.0.1:8765/planning-items  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])")"
echo "Workstreams:     $(curl -s http://127.0.0.1:8765/workstreams     | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['workstream_identifier'] for r in d)[-1])")"
echo "Conversations:   $(curl -s http://127.0.0.1:8765/conversations   | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['conversation_identifier'] for r in d)[-1])")"
echo "Work_tickets:    $(curl -s http://127.0.0.1:8765/work-tickets    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['work_ticket_identifier'] for r in d)[-1])")"
echo "References tot:  $(curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))")"
```

Expected: SES-059, DEC-177, PI-044, WS-007, CONV-008, WT-008. **Save the references total** — you'll use it at Step 11 to verify the cumulative delta.

---

## Step 4 — Apply SES-060 close-out (audit-v1.2 planning resolved)

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_060.json
```

Verify the head advanced:

```bash
LATEST=$(curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])")
if [ "$LATEST" != "SES-060" ]; then echo "HALT: expected SES-060, got $LATEST"; exit 1; fi
echo "  ✓ Sessions head: SES-060"
```

Commit and push the regenerated snapshots:

```bash
cd ~/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-060 close-out: audit-v1.2 planning resolved"
git pull --rebase origin main
git push
```

---

## Step 5 — Apply SES-061 close-out (Code Change Lifecycle methodology drafted)

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_061.json
```

Verify the head advanced:

```bash
LATEST=$(curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])")
if [ "$LATEST" != "SES-061" ]; then echo "HALT: expected SES-061, got $LATEST"; exit 1; fi
echo "  ✓ Sessions head: SES-061"
```

Commit and push:

```bash
cd ~/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-061 close-out: Code Change Lifecycle methodology drafted"
git pull --rebase origin main
git push
```

---

## Step 6 — Apply SES-062 close-out (PI-025 prior-conversations backfill planned)

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_062.json
```

Verify the head advanced and decisions reached DEC-197:

```bash
LATEST_SES=$(curl -s http://127.0.0.1:8765/sessions  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])")
LATEST_DEC=$(curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])")
if [ "$LATEST_SES" != "SES-062" ]; then echo "HALT: expected SES-062, got $LATEST_SES"; exit 1; fi
if [ "$LATEST_DEC" != "DEC-197" ]; then echo "HALT: expected DEC-197, got $LATEST_DEC"; exit 1; fi
echo "  ✓ Sessions head: SES-062"
echo "  ✓ Decisions head: DEC-197"
```

Commit and push:

```bash
cd ~/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-062 close-out: PI-025 prior-conversations backfill planned

7 decisions land (DEC-191 scope with WS-008 audit-v1.2 fold-in;
DEC-192 WS-006 cross-engagement Option IV defer; DEC-193 born-complete
single-POST pattern; DEC-194 unambiguous succeeds-chain policy;
DEC-195 source-document field defaults; DEC-196 work_ticket backfill
scope (37 work_tickets); DEC-197 sixteen orphan sessions deferred)."
git pull --rebase origin main
git push
```

---

## Step 7 — Author the PI-025 backfill script

Read the PI-025 backfill prompt and execute its **"Author the backfill script"** section only — that section contains the full Python source for `crmbuilder-v2/scripts/backfill_pi_025_prior_conversations.py`. Copy the script verbatim from the fenced ```python block in that prompt into the target script path. **Do not run the script yet — Step 8 runs it.**

Source prompt: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-025-prior-conversations-backfill.md`

Target path: `crmbuilder-v2/scripts/backfill_pi_025_prior_conversations.py`

Verify the script was written and parses cleanly:

```bash
cd ~/Dropbox/Projects/crmbuilder
ls -la crmbuilder-v2/scripts/backfill_pi_025_prior_conversations.py
python3 -c "import ast; ast.parse(open('crmbuilder-v2/scripts/backfill_pi_025_prior_conversations.py').read()); print('  ✓ script parses cleanly')"
```

If the file is missing or the parse fails, halt — Step 7 did not complete.

---

## Step 8 — Run the PI-025 backfill

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/backfill_pi_025_prior_conversations.py 2>&1 | tee /tmp/pi-025-backfill.log
```

Expected: stages A through F complete with these counts (use this as a checklist against the output):

- Stage A: 1 workstream POST OK (WS-008)
- Stage B: 1 workstream PATCH OK (WS-006 notes)
- Stage C: 37 work_ticket POSTs OK (WT-009..WT-045)
- Stage D: 37 conversation POSTs OK (CONV-009..CONV-045)
- Stage E: 74 work_ticket PATCHes OK (drafted → ready, ready → consumed for each of 37)
- Stage F: 29 reference POSTs OK (conversation_succeeds_conversation edges)
- Verification: 8 workstreams, 45 conversations, 45 work_tickets, edge counts as listed

Verify the heads advanced as expected:

```bash
LATEST_WS=$(curl -s http://127.0.0.1:8765/workstreams   | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['workstream_identifier'] for r in d)[-1])")
LATEST_CV=$(curl -s http://127.0.0.1:8765/conversations | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['conversation_identifier'] for r in d)[-1])")
LATEST_WT=$(curl -s http://127.0.0.1:8765/work-tickets  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['work_ticket_identifier'] for r in d)[-1])")
if [ "$LATEST_WS" != "WS-008" ]; then echo "HALT: expected WS-008, got $LATEST_WS"; exit 1; fi
if [ "$LATEST_CV" != "CONV-045" ]; then echo "HALT: expected CONV-045, got $LATEST_CV"; exit 1; fi
if [ "$LATEST_WT" != "WT-045" ]; then echo "HALT: expected WT-045, got $LATEST_WT"; exit 1; fi
echo "  ✓ Workstreams head:   WS-008"
echo "  ✓ Conversations head: CONV-045"
echo "  ✓ Work_tickets head:  WT-045"
```

If any FAIL line appeared in the script output, or any head verification fails, halt. The script is idempotent on re-run (every successful POST will SKIP on retry), so it is safe to fix the underlying issue and re-run the script — but do not proceed to Step 9 until Stage F completes cleanly.

---

## Step 9 — Commit and push the backfill script (commit 1 of 2)

```bash
cd ~/Dropbox/Projects/crmbuilder

git add crmbuilder-v2/scripts/backfill_pi_025_prior_conversations.py
git commit -m "Add PI-025 prior-conversations backfill script

One-off script that creates the WS-008 audit-v1.2 workstream record,
37 work_ticket records (WT-009..WT-045), 37 conversation records
(CONV-009..CONV-045), the WS-006 workstream_notes Option IV defer
update, and the ~140 supporting reference edges. Mirrors
backfill_governance_phase_1.py's and backfill_pi_024_prior_workstreams.py's
idempotency contract (HTTP 409 and 422-duplicate are treated as
already-present; lifecycle PATCHes treat invalid_status_transition
as already-at-target).

Discharges Phase 3 of PI-022 per the kickoff at
PRDs/product/crmbuilder-v2/pi-025-prior-conversations-backfill-kickoff.md
and per DEC-191..197 settled in SES-062."

git pull --rebase origin main
git push
```

---

## Step 10 — Commit and push the regenerated snapshots (commit 2 of 2)

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect what changed (workstreams.json, conversations.json, work_tickets.json,
# references.json, change_log.json)
git status PRDs/product/crmbuilder-v2/db-export/

git add PRDs/product/crmbuilder-v2/db-export/
git commit -m "Apply PI-025 prior-conversations backfill: WS-008, CONV-009..045, WT-009..045

Records landed via backfill_pi_025_prior_conversations.py against
CRMBUILDER engagement:
- 1 new workstream (WS-008 Audit feature v1.2 status complete)
- 1 workstream update (WS-006 workstream_notes Option IV defer
  forward-pointer per DEC-192)
- 37 work_tickets (5 kickoff_prompt, 26 claude_code_prompt, 6 other)
  all status consumed
- 37 conversations (CONV-009..CONV-045) all status complete, born-
  complete via single-POST with the references array carrying the
  workstream-membership, session-record, and work_ticket edges
- ~140 reference edges (37 belongs_to_workstream, 37 records_session,
  37 opens_against_work_ticket, 29 succeeds_conversation)

WS-006 CBM paper test deferred via Option IV per DEC-192. Sixteen
orphan sessions (SES-001..010, SES-046, SES-056, SES-057, SES-059,
SES-061, SES-062) deferred per DEC-197."

git pull --rebase origin main
git push
```

---

## Step 11 — Final verification

```bash
echo ""
echo "=== Final heads ==="
echo "Sessions:        $(curl -s http://127.0.0.1:8765/sessions        | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1], '(total:', len(d), ')')")"
echo "Decisions:       $(curl -s http://127.0.0.1:8765/decisions       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1], '(total:', len(d), ')')")"
echo "Planning items:  $(curl -s http://127.0.0.1:8765/planning-items  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1], '(total:', len(d), ')')")"
echo "Workstreams:     $(curl -s http://127.0.0.1:8765/workstreams     | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['workstream_identifier'] for r in d)[-1], '(total:', len(d), ')')")"
echo "Conversations:   $(curl -s http://127.0.0.1:8765/conversations   | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['conversation_identifier'] for r in d)[-1], '(total:', len(d), ')')")"
echo "Work_tickets:    $(curl -s http://127.0.0.1:8765/work-tickets    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['work_ticket_identifier'] for r in d)[-1], '(total:', len(d), ')')")"
echo "References tot:  $(curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))")"
echo ""
echo "=== WS-008 spot-check ==="
curl -s http://127.0.0.1:8765/workstreams/WS-008 | python3 -m json.tool | head -10
echo ""
echo "=== WS-006 workstream_notes (should mention ENG-002 and DEC-192) ==="
curl -s http://127.0.0.1:8765/workstreams/WS-006 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(d.get('workstream_notes', '(empty)'))"
echo ""
echo "=== WS-008 conversation members (expect 3: CONV-043, CONV-044, CONV-045) ==="
curl -s 'http://127.0.0.1:8765/references?relationship_kind=conversation_belongs_to_workstream&target_id=WS-008' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_id']) for r in sorted(d, key=lambda x: x['source_id'])]"
```

Expected final state:
- Sessions: SES-062 (total 62)
- Decisions: DEC-197 (total 197)
- Workstreams: WS-008 (total 8)
- Conversations: CONV-045 (total 45)
- Work_tickets: WT-045 (total 45)
- References total: pre-state captured at Step 3 plus approximately 165 (3 × 12 from close-out applies + 140 from backfill)
- WS-006 workstream_notes contains "ENG-002" and "DEC-192"
- WS-008 has exactly 3 conversation members

---

## Done — reply with

1. **Pre-state heads** captured at Step 3
2. **Final heads** from Step 11
3. **Reference delta** (final references total minus pre-state references total) — expect approximately +165
4. **Five commit SHAs** in the order they were created:
   - Step 4 snapshot commit (SES-060 apply)
   - Step 5 snapshot commit (SES-061 apply)
   - Step 6 snapshot commit (SES-062 apply)
   - Step 9 backfill script commit
   - Step 10 backfill snapshot commit
5. **Any halt** that occurred and at which step
6. **Next conversation:** PI-026 (PI-022 Phase 4 — historical-applies-as-deposit_events backfill). Kickoff to be authored in the next Claude.ai planning conversation against the freshly-applied governance database state.
