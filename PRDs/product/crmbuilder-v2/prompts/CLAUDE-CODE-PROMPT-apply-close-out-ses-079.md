# CLAUDE-CODE-PROMPT — Apply SES-079 close-out payload

**Last Updated:** 05-25-26 22:30
**Purpose:** Apply the SES-079 close-out payload — the establishing close-out for WS-012 (Parallel agent orchestrator and executive summary). Lands SES-079, CONV-049 (with two atomic embedded edges to WS-012 and SES-079), six decisions (DEC-304 through DEC-309), ten planning items (PI-074 through PI-083) in `Open` status, and twenty-one references (six `decided_in` plus fifteen `blocked_by`). WS-012 itself is created out-of-band by the pre-step below.

**Net Effect:**
- +1 workstream (WS-012 from pre-step)
- +1 session (SES-079)
- +1 conversation (CONV-049) with two atomic embedded edges
- +6 decisions (DEC-304..DEC-309)
- +10 planning_items (PI-074..PI-083, all Open)
- +21 payload references (6 `decided_in` + 15 `blocked_by` between the new PIs)
- +1 close_out_payload (lazy-create, COP-077)
- +1 deposit_event (lazy-create, DEP head + 1)
- +~21 `wrote_record` edges from the lazy deposit_event (1 session + 1 conversation + 10 PIs + 6 decisions + lazy COP)
- +1 `close_out_payload_applied_by_deposit_event` edge
- +1 `close_out_payload_produced_by_conversation` edge (if lazy-create wires this)

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_077.json`

**Predecessors:**
- SES-078 must have landed (the most recent close-out per the sandbox's pre-apply head capture).
- The CRMBUILDER engagement must be the active engagement when the apply runs.

**Successor:** WS-012's bootstrap track. Wave 1 (PI-074, PI-076, PI-077, PI-078, PI-080) is fully unblocked and may be dispatched in any order via individual Claude Code prompts.

---

## Scope

Apply `close-out-payloads/ses_077.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains all nine v0.8 sections (some empty):

- **1 session** (SES-079 — orchestrator architecture planning conversation)
- **1 conversation** (CONV-049, status `complete`, embedded edges: `conversation_belongs_to_workstream` → WS-012 and `conversation_records_session` → SES-079)
- **0 work_tickets**
- **10 planning_items** (PI-074 through PI-083, all `pending_work`, status `Open`)
- **0 commits** (planning-only conversation; no code commits authored)
- **6 decisions** (DEC-304 area-level parallelism, DEC-305 multi-valued area, DEC-306 per-agent + orchestrator conv+ses pairs, DEC-307 static waves, DEC-308 exec_summary structured field, DEC-309 bundle exec-summary into WS-012)
- **21 references** (6 `decided_in` for DEC-304..DEC-309 → SES-079; 15 `blocked_by` declaring dependency structure among the new PIs)
- **0 resolves_planning_items** (no PIs resolved by this conversation)
- **0 addresses_planning_items** (no partial-address edges)

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Clean working tree (acknowledge unrelated unstaged work — proceed regardless)
git status

# Pull latest commits
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Git identity
git config user.email
# Expect: doug@dougbower.com

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_077.json

# Confirm WS-012 absence (will be created by the pre-step below)
curl -sf http://127.0.0.1:8765/workstreams/WS-012 >/dev/null 2>&1 \
  && echo "WARN: WS-012 already exists; the pre-step below is a no-op on re-run" \
  || echo "OK: WS-012 absent (pre-step will create it)"

# Capture pre-apply heads
echo "=== Pre-apply heads ==="
echo "Sessions:"
curl -s 'http://127.0.0.1:8765/sessions?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Decisions:"
curl -s 'http://127.0.0.1:8765/decisions?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Planning items:"
curl -s 'http://127.0.0.1:8765/planning-items?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Conversations:"
curl -s 'http://127.0.0.1:8765/conversations?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['conversation_identifier'] for r in d)[-1] if d else 'none')"
echo "Workstreams:"
curl -s http://127.0.0.1:8765/workstreams | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['workstream_identifier'] for r in d)[-1] if d else 'none')"
echo "Close-out payloads:"
curl -s 'http://127.0.0.1:8765/close-out-payloads?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['close_out_payload_identifier'] for r in d)[-1] if d else 'none')"
echo "Deposit events:"
curl -s 'http://127.0.0.1:8765/deposit-events?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['deposit_event_identifier'] for r in d)[-1] if d else 'none')"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=5000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', len(d))"
```

Expected pre-apply state (CRMBUILDER engagement, drafted against snapshot at commit `HEAD`): sessions head **at least SES-078**, decisions head **at least DEC-245**, planning-items head **at least PI-052**, conversations head **at least CONV-048**, workstreams head **WS-011** (WS-012 will be created in the pre-step). If any head has advanced beyond what this payload assumes — for example, sessions head already at SES-079 from a parallel-sandbox claim — halt and re-key the payload identifiers (the conversation's content is the substantive deliverable; the identifiers are mechanical and re-keyable in the same +1 / +6 / +6 / +10 / +21 block-advance pattern as ses-074's re-key documented).

---

## WS-012 pre-step — create the workstream

The close-out payload schema has no `workstreams` section by design (workstreams are upstream of conversations; see methodology §4.0). Per the convention established by ses-074, the workstream is created out-of-band before the close-out apply.

```bash
# Capture WS-012 absence one more time (idempotency guard)
if curl -sf http://127.0.0.1:8765/workstreams/WS-012 >/dev/null 2>&1; then
  echo "WS-012 already exists; skipping creation step (idempotent re-run)"
else
  echo "Creating WS-012..."
  curl -sf -X POST http://127.0.0.1:8765/workstreams \
    -H "Content-Type: application/json" \
    -d '{
      "workstream_identifier": "WS-012",
      "workstream_name": "Parallel agent orchestrator and executive summary",
      "workstream_purpose": "Build a Claude Code orchestrator that spins up multiple parallel agents to process the open planning-item backlog, with the supporting governance metadata (executive_summary field, area field, claimed_by/claimed_at fields, identifier reservation API, ready-batches API, conversation_orchestrates_conversation reference kind) the orchestrator requires.",
      "workstream_description": "The workstream established at SES-079 to add a parallel-agent execution layer on top of the v0.7 governance entity substrate and the v0.8 code-change-lifecycle methodology. Comprises ten planning items in two tracks: bootstrap (PI-074 executive_summary field, PI-075 executive_summary backfill, PI-076 area field, PI-077 claimed_by/claimed_at, PI-080 conversation_orchestrates_conversation reference kind) and orchestrator proper (PI-078 identifier reservation API, PI-079 ready-batches API, PI-081 driver script, PI-082 child kickoff template, PI-083 area backfill). Dependencies declared via blocked_by. Acceptance test is an orchestrator run that dispatches at least two concurrent agents end-to-end, each producing its own close-out payload, with the orchestrator producing a supervising close-out that references both children via conversation_orchestrates_conversation. Architectural decisions captured in DEC-304 through DEC-309 (area-level parallelism, multi-valued area, per-agent conv+ses + orchestrator conv+ses, static waves, executive_summary as structured field, bundle into WS-012). Status remains in_flight until all ten PIs resolve.",
      "workstream_started_at": "2026-05-25T00:00:00",
      "workstream_status": "in_flight"
    }' \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('Created:', d['workstream_identifier'], '-', d['workstream_status'])"
fi
```

Expected output: `Created: WS-012 - in_flight` on first run; `WS-012 already exists; skipping creation step (idempotent re-run)` on re-run.

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_077.json
```

Expected output structure (methodology §4 order: session → conversation → work_tickets → planning_items → commits → decisions → references → resolves_planning_items → addresses_planning_items):

- **`=== session ===`** — 1 OK (SES-079)
- **`=== conversation ===`** — 1 OK (CONV-049 with two embedded edges committed atomically: `conversation_belongs_to_workstream` → WS-012, `conversation_records_session` → SES-079)
- **`=== work_tickets ===`** — 0 (section empty)
- **`=== planning_items ===`** — 10 OK (PI-074..PI-083, all status Open)
- **`=== commits ===`** — 0 (section empty)
- **`=== decisions ===`** — 6 OK (DEC-304..DEC-309)
- **`=== references ===`** — 21 OK (6 `decided_in` + 15 `blocked_by`)
- **`=== resolves_planning_items ===`** — 0 (section empty)
- **`=== addresses_planning_items ===`** — 0 (section empty)
- 1 close_out_payload lazy-created (COP-077)
- 1 deposit_event written at apply close (lazy-created)

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-079):"
curl -s 'http://127.0.0.1:8765/sessions?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-309):"
curl -s 'http://127.0.0.1:8765/decisions?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-083):"
curl -s 'http://127.0.0.1:8765/planning-items?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Conversations (expect CONV-049):"
curl -s 'http://127.0.0.1:8765/conversations?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['conversation_identifier'] for r in d)[-1])"
echo "Workstreams (expect WS-012 — created in pre-step):"
curl -s http://127.0.0.1:8765/workstreams | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['workstream_identifier'] for r in d)[-1])"
echo "Close-out payloads (expect COP-077 lazy-created):"
curl -s 'http://127.0.0.1:8765/close-out-payloads?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1])"
echo "Deposit events (expect DEP head + 1):"
curl -s 'http://127.0.0.1:8765/deposit-events?limit=2000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1])"

# Spot-check SES-079
curl -s http://127.0.0.1:8765/sessions/SES-079 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:100]); print('  status:', d['status'])"

# Spot-check CONV-049 and its two atomic edges
curl -s http://127.0.0.1:8765/conversations/CONV-049 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  CONV-049 status:', d['conversation_status']); print('  CONV-049 purpose opens:', d['conversation_purpose'][:80])"
curl -s 'http://127.0.0.1:8765/references?source_id=CONV-049' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum:
#   CONV-049 -> WS-012 [ conversation_belongs_to_workstream ]
#   CONV-049 -> SES-079 [ conversation_records_session ]

# Spot-check one decision and confirm decided_in resolves
curl -s http://127.0.0.1:8765/decisions/DEC-304 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-304 title:', d['title'][:100]); print('  status:', d['status'])"
curl -s 'http://127.0.0.1:8765/references?source_id=DEC-304' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(' ', r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect: DEC-304 -> SES-079 [ decided_in ]

# Spot-check a blocked_by edge — PI-081 should have nine blockers
echo ""
echo "PI-081 dependency chain (expect 9 blocked_by edges to PI-074..PI-080, PI-082, PI-083):"
curl -s 'http://127.0.0.1:8765/references?source_id=PI-081' | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
by_kind = {}
for r in d:
    by_kind.setdefault(r['relationship'], []).append(r['target_id'])
for kind, targets in sorted(by_kind.items()):
    print(f'  {kind}: {sorted(targets)}')
"

# Spot-check that PI-074 is Open (the entire batch must land Open)
for pi in PI-074 PI-075 PI-076 PI-077 PI-078 PI-079 PI-080 PI-081 PI-082 PI-083; do
  curl -s "http://127.0.0.1:8765/planning-items/$pi" | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
print(f\"  {d['identifier']}: status={d['status']}, title={d['title'][:80]}\")
"
done

# Reference total delta
echo ""
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=5000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
# Expected delta from pre-apply: +44 to +46 references, breakdown:
#   +21 payload references (6 decided_in + 15 blocked_by)
#    +2 conversation block embedded edges (workstream membership + records_session)
#   +19 wrote_record edges from the lazy deposit_event (1 session + 1 conversation + 10 PIs + 6 decisions + 1 lazy COP = 19 records the apply created)
#    +1 close_out_payload_applied_by_deposit_event (DEP-XXX → COP-077)
#    +1 close_out_payload_produced_by_conversation (CONV-049 → COP-077) — if the lazy-create wires this
```

Expected post-apply state: sessions head SES-079, decisions head DEC-309, planning-items head PI-083, conversations head CONV-049, workstreams head WS-012, COP head COP-077 (lazy), DEP head one above pre-apply. Reference total ≈ pre + 44 (give or take depending on lazy-create edges).

---

## Commit snapshot regeneration

The apply script's `_refresh_snapshot` hook regenerates db-export JSON snapshots transactionally on every API write. The snapshots produced by this apply include:

- `db-export/sessions.json` (SES-079 added)
- `db-export/conversations.json` (CONV-049 added)
- `db-export/decisions.json` (DEC-304..DEC-309 added)
- `db-export/planning_items.json` (PI-074..PI-083 added)
- `db-export/workstreams.json` (WS-012 added from the pre-step)
- `db-export/close_out_payloads.json` (COP-077 lazy)
- `db-export/deposit_events.json` (DEP head + 1 lazy)
- `db-export/references.json` (+44 give or take)
- `db-export/change_log.json` (audit rows for every write)
- `deposit-event-logs/dep_NNN.log` (apply stdout tee, where NNN is the new DEP identifier)

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect changed snapshot files
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-079 close-out: WS-012 establishing — parallel agent orchestrator architecture

Records landed via apply_close_out.py against the CRMBUILDER engagement:
- 1 workstream (WS-012 — Parallel agent orchestrator and executive summary,
  in_flight; created by apply prompt's pre-step before the close-out apply)
- 1 session (SES-079 — orchestrator architecture planning conversation)
- 1 conversation (CONV-049, status complete, two atomic embedded edges:
  conversation_belongs_to_workstream to WS-012, conversation_records_session
  to SES-079)
- 6 decisions (DEC-304 area-level parallelism; DEC-305 multi-valued area;
  DEC-306 per-agent conv+ses + orchestrator conv+ses; DEC-307 static waves;
  DEC-308 executive_summary as structured field on PI/DEC/SES; DEC-309
  bundle executive_summary work into WS-012)
- 10 planning_items (PI-074 executive_summary field; PI-075 executive_summary
  backfill; PI-076 area field; PI-077 claimed_by/claimed_at; PI-078 identifier
  reservation API; PI-079 ready-batches API; PI-080 conversation_orchestrates_
  conversation kind; PI-081 orchestrator driver; PI-082 child kickoff template;
  PI-083 area backfill — all Open)
- 21 payload references (6 decided_in + 15 blocked_by between the new PIs)
- 1 close_out_payload (COP-077, lazy-created at apply close)
- 1 deposit_event (lazy-created at apply close)

Planning artifact orchestrator-planning.md v1.0 committed alongside in a
separate commit (sandbox-authored, pushed together with this commit).
"
git push origin main
```

---

## Done

Reply in this thread with:

- Pre-apply heads (sessions / decisions / planning-items / conversations / workstreams / COP / DEP / references count) — captured in pre-flight.
- Pre-step result (`Created: WS-012 - in_flight` on first run, else idempotent skip).
- Apply script output — should be 1+1+10+6+21 = 39 OK records across the section banners, plus 1 lazy COP + 1 lazy DEP.
- Post-apply heads (expect SES-079 / DEC-309 / PI-083 / CONV-049 / WS-012 / COP-077 / DEP head + 1).
- Reference total before and after (expect ~+44 delta).
- Snapshot commit SHA.
- Next-conversation kickoff path: any Wave 1 PI (PI-074, PI-076, PI-077, PI-078, or PI-080) can be opened next via an individual Claude Code prompt.
