# CLAUDE-CODE-PROMPT — Apply SES-080 close-out payload

**Last Updated:** 05-25-26 23:30
**Purpose:** Apply the SES-080 close-out payload — records the PI-052 chat-UI design + slicing session conducted as a Claude Code conversation against work_ticket WT-047. Lands SES-080, CONV-050, zero commits (design session — no implementation code), one new work_ticket (WT-048 = Slice-A terminal-spike kickoff body, status ready), eleven decisions (DEC-252 through DEC-262 settling Q1–Q10 + tool surface + auth + model + slicing + methodology), zero new planning items (future PI-053 candidates noted in the design doc but not authored as PIs), 16 payload references (11 `decided_in` + 4 inter-decision `references` + 1 `is_about`), zero resolves edges (PI-052 stays Open through Slices A–C; resolves on Slice D close), one addresses edge (CONV-050 → PI-052).

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_080.json`
**Predecessors:**
- SES-077 close-out must have landed (DEC-244, DEC-245, PI-052, WS-010 all need to exist before this session's decisions and edges can reference them).
- SES-078 close-out (PI-002 build closure) must have landed if applied — this session is SES-080 because SES-078 was consumed by that parallel work; the apply does NOT depend on SES-078's contents but the head advancement check assumes SES-078 is present.
- WT-047 must be in `ready` status (this conversation consumes it).
- The design document `PRDs/product/crmbuilder-v2/pi-052-chat-ui-design.md` and the Slice-A kickoff body `PRDs/product/crmbuilder-v2/pi-052-slice-a-terminal-spike-kickoff.md` must be present in the working tree.

**Successor:** PI-052 Slice A implementation session opens against WT-048. Produces `crmbuilder-v2/scripts/chat_spike.py` and closes as SES-081.

---

## Scope

Apply `close-out-payloads/ses_080.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains:

- **1 session** (SES-080)
- **1 conversation** (CONV-050, status `complete`, embeds three required edges: `conversation_belongs_to_workstream` to WS-010, `conversation_records_session` to SES-080, `conversation_opens_against_work_ticket` to WT-047 — consumes WT-047)
- **0 commits** (design + planning session; no implementation code was written)
- **1 work_ticket** (WT-048 — Slice-A terminal-spike kickoff body, kind `kickoff_prompt`, status `ready`, `work_ticket_file_path` pointing at `PRDs/product/crmbuilder-v2/pi-052-slice-a-terminal-spike-kickoff.md`)
- **0 planning_items** (future PI candidates noted in the design doc §14 but not authored as PIs)
- **11 decisions** (DEC-252 PySide6 production surface, DEC-253 all 44 tools registered, DEC-254 ANTHROPIC_API_KEY auth model, DEC-255 tool-call confirmation policy, DEC-256 JSON-file persistence, DEC-257 streaming + QThread + asyncio, DEC-258 sidebar multi-conv UX, DEC-259 cost+token visibility, DEC-260 Opus 4.7 default + model picker, DEC-261 four-slice plan, DEC-262 hybrid kickoff pattern)
- **16 payload references** (11 `decided_in` from DEC-252–256 → SES-080, 4 inter-decision `references`, 1 `is_about` SES-080 → PI-052)
- **0 resolves_planning_items** (PI-052 not resolved by a design session — Slices A–D execute against the design)
- **1 addresses_planning_items** (CONV-050 → PI-052)

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2

# Clean working tree expected on the crmbuilder-v2 side (other repo paths may have uncommitted snapshot edits — proceed regardless)
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
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_080.json

# Verify the design doc and Slice-A kickoff body are present
ls -la ../PRDs/product/crmbuilder-v2/pi-052-chat-ui-design.md
ls -la ../PRDs/product/crmbuilder-v2/pi-052-slice-a-terminal-spike-kickoff.md

# Confirm WT-047 is still ready (this conversation consumes it)
curl -s http://127.0.0.1:8765/work-tickets/WT-047 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('WT-047 status:', d.get('work_ticket_status'))"
# Expect: ready

# Confirm WT-048 absence (will be created by the payload)
curl -sf http://127.0.0.1:8765/work-tickets/WT-048 >/dev/null 2>&1 \
  && echo "WARN: WT-048 already exists; apply will SKIP it idempotently" \
  || echo "OK: WT-048 absent (payload will create it)"

# Confirm WS-010 exists (the workstream this conversation belongs to)
curl -s http://127.0.0.1:8765/workstreams/WS-010 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('WS-010:', d.get('workstream_status'))"
# Expect: in_flight

# Confirm PI-052 still Open
curl -s http://127.0.0.1:8765/planning-items/PI-052 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-052 status:', d['status'])"
# Expect: Open

# Capture pre-apply heads
echo "=== Pre-apply heads ==="
echo "Sessions:"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1])"
echo "Decisions:"
curl -s 'http://127.0.0.1:8765/decisions?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1])"
echo "Planning items:"
curl -s 'http://127.0.0.1:8765/planning-items?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1])"
echo "Conversations:"
curl -s 'http://127.0.0.1:8765/conversations?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['conversation_identifier'] for r in d)[-1])"
echo "Workstreams:"
curl -s http://127.0.0.1:8765/workstreams | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['workstream_identifier'] for r in d)[-1])"
echo "Work tickets:"
curl -s 'http://127.0.0.1:8765/work-tickets?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['work_ticket_identifier'] for r in d)[-1])"
echo "Commits:"
curl -s 'http://127.0.0.1:8765/commits?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['commit_identifier'] for r in d)[-1] if d else 'none')"
echo "Close-out payloads:"
curl -s 'http://127.0.0.1:8765/close-out-payloads?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['close_out_payload_identifier'] for r in d)[-1])"
echo "Deposit events:"
curl -s 'http://127.0.0.1:8765/deposit-events?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['deposit_event_identifier'] for r in d)[-1])"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=5000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', len(d))"
```

Expected pre-apply state at apply time: sessions head SES-078, decisions head DEC-245 (still — DEC-252 lands here), planning-items head PI-052, conversations head CONV-048, workstreams head WS-010, work_tickets head WT-047, commits head CM-0005 (or thereabouts after SES-078 apply), COP head COP-078, DEP head depends on prior applies, references count grows by ~25 on this apply.

---

## No workstream pre-step

Unlike SES-077 which created WS-010 out-of-band before the apply, this session belongs to WS-010 which is already present. No pre-step needed.

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_080.json
```

Expected output:

- **`=== session ===`** — 1 OK (SES-080)
- **`=== conversation ===`** — 1 OK (CONV-050 with three embedded edges)
- **`=== work_tickets ===`** — 1 OK (WT-048, status ready)
- **`=== planning_items ===`** — 0 (section empty)
- **`=== commits ===`** — 0 (section empty)
- **`=== decisions ===`** — 11 OK (DEC-252 through DEC-262)
- **`=== references ===`** — 16 OK
- **`=== resolves_planning_items ===`** — 0 (section empty)
- **`=== addresses_planning_items ===`** — 1 OK (PI-052)
- 1 close_out_payload lazy-created (COP-079)
- 1 deposit_event written at apply close (DEP head + 1)

On re-run, every record should SKIP idempotently (409 = already present).

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-080):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-262):"
curl -s 'http://127.0.0.1:8765/decisions?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-052 unchanged):"
curl -s 'http://127.0.0.1:8765/planning-items?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Conversations (expect CONV-050):"
curl -s 'http://127.0.0.1:8765/conversations?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['conversation_identifier'] for r in d)[-1])"
echo "Workstreams (expect WS-010 unchanged):"
curl -s http://127.0.0.1:8765/workstreams | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['workstream_identifier'] for r in d)[-1])"
echo "Work tickets (expect WT-048):"
curl -s 'http://127.0.0.1:8765/work-tickets?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['work_ticket_identifier'] for r in d)[-1])"
echo "Close-out payloads (expect COP-079 lazy):"
curl -s 'http://127.0.0.1:8765/close-out-payloads?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['close_out_payload_identifier'] for r in d)[-1])"
echo "Deposit events (expect DEP head + 1):"
curl -s 'http://127.0.0.1:8765/deposit-events?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['deposit_event_identifier'] for r in d)[-1])"

# Spot-check WT-047 is now consumed
echo ""
echo "WT-047 status (expect 'consumed'):"
curl -s http://127.0.0.1:8765/work-tickets/WT-047 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d.get('work_ticket_status'))"

# Spot-check WT-048 is ready with the file_path
echo ""
echo "WT-048 (expect ready + file_path):"
curl -s http://127.0.0.1:8765/work-tickets/WT-048 | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
print('  status:', d['work_ticket_status'])
print('  file_path:', d['work_ticket_file_path'])
print('  kind:', d['work_ticket_kind'])"

# Spot-check CONV-050 outbound edges
echo ""
echo "CONV-050 outbound edges:"
curl -s 'http://127.0.0.1:8765/references?source_id=CONV-050&limit=100' | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
for r in d:
    print(f'  {r[\"source_id\"]} -[{r[\"relationship\"]}]-> {r[\"target_id\"]}')"
# Expect: belongs_to_workstream WS-010, records_session SES-080, opens_against_work_ticket WT-047, addresses PI-052

# Spot-check the eleven decisions
echo ""
echo "Decisions DEC-252..DEC-262 titles:"
for dec in DEC-252 DEC-253 DEC-254 DEC-255 DEC-256 DEC-257 DEC-258 DEC-259 DEC-260 DEC-261 DEC-262; do
  curl -s "http://127.0.0.1:8765/decisions/$dec" | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
print(f'  {d[\"identifier\"]}: {d[\"title\"][:90]}')"
done

# Confirm PI-052 still Open (NOT resolved — addresses edges are not status-flipping)
echo ""
echo "PI-052 status (expect Open):"
curl -s http://127.0.0.1:8765/planning-items/PI-052 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['status'])"

# Reference total delta
echo ""
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=5000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
# Expected delta from pre-apply: roughly +25 references:
#   + 16 payload references (11 decided_in + 4 inter-decision references + 1 is_about)
#   + 3 CONV-050 embedded refs (workstream membership, records session, opens_against WT)
#   + 1 addresses edge
#   + ~5 wrote_record edges from the lazy deposit_event (1 session + 1 conversation + 1 work_ticket + 11 decisions; some of these may be elided depending on the apply_close_out implementation)
#   + 1 close_out_payload_applied_by_deposit_event
#   + 1 close_out_payload_produced_by_conversation
#   = roughly 25-32 total refs added (exact count depends on apply_close_out lazy-edge generation)
```

Expected post-apply state: sessions head SES-080, decisions head DEC-262, planning-items head PI-052 (unchanged), conversations head CONV-050, workstreams head WS-010 (unchanged), work_tickets head WT-048, commits head unchanged (SES-080 has no commits), COP head COP-079 (lazy), DEP head incremented by 1. WT-047 status `consumed`. WT-048 status `ready`. PI-052 still `Open`. Reference total ≈ pre + 25–32.

---

## Commit snapshot + design doc + Slice-A kickoff

The apply script's `_refresh_snapshot` hook regenerates `db-export/*.json` snapshots on every write. In addition, this session produced two new markdown files in the working tree (`pi-052-chat-ui-design.md` and `pi-052-slice-a-terminal-spike-kickoff.md`) that need to land in the same commit as the snapshot writes for log-time consistency.

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect changed files
git status PRDs/product/crmbuilder-v2/db-export/ \
           PRDs/product/crmbuilder-v2/deposit-event-logs/ \
           PRDs/product/crmbuilder-v2/pi-052-chat-ui-design.md \
           PRDs/product/crmbuilder-v2/pi-052-slice-a-terminal-spike-kickoff.md \
           PRDs/product/crmbuilder-v2/close-out-payloads/ses_080.json \
           PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-080.md

# Commit
git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/ \
        PRDs/product/crmbuilder-v2/pi-052-chat-ui-design.md \
        PRDs/product/crmbuilder-v2/pi-052-slice-a-terminal-spike-kickoff.md \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_080.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-080.md

git commit -m "$(cat <<'EOF'
Apply SES-080 close-out: PI-052 chat-UI design + slicing — eleven decisions settled (DEC-252..DEC-262)

Records landed via apply_close_out.py against the CRMBUILDER engagement:
- 1 session (SES-080 — PI-052 chat-UI design + slicing session, ARCHITECTURE working mode)
- 1 conversation (CONV-050 — this Claude Code conversation; member of WS-010; records SES-080; consumes WT-047)
- 0 commits (design + planning session; no implementation code)
- 1 work_ticket (WT-048 — Slice-A terminal-spike kickoff body, kind kickoff_prompt, status ready, file_path pi-052-slice-a-terminal-spike-kickoff.md)
- 11 decisions:
  * DEC-252 — PySide6 chat tab as the production UI surface (resolves DEC-245 Phase 2 deferred)
  * DEC-253 — All 44 tools registered, partitioned by name-prefix for the mode toggle
  * DEC-254 — ANTHROPIC_API_KEY env primary + system keyring fallback, never in settings.json
  * DEC-255 — Tool-call confirmation policy: auto-execute + inline disclosure + per-session 'Ask before write' toggle
  * DEC-256 — Persistence to JSON files under ~/.crmbuilder-v2/chats/; first-class governance treatment deferred
  * DEC-257 — Streaming on by default; QThread + private asyncio loop, no qasync dep
  * DEC-258 — Multi-conversation UX: claude.ai-web sidebar pattern, single active chat
  * DEC-259 — Cost + token visibility: per-turn footer + per-session header, three-tier cache-hit display
  * DEC-260 — Model selection: Opus 4.7 default; Sonnet 4.6 + Haiku 4.5 selectable in header
  * DEC-261 — Slicing plan: four slices A (terminal spike), B (PySide6 MVP), C (full surface + caching), D (polish)
  * DEC-262 — Hybrid kickoff pattern (WT summary + file pointer + file-is-canonical) established as standard
- 0 planning items (future PI candidates noted in design doc but not authored)
- 16 payload references (11 decided_in + 4 inter-decision references + 1 is_about)
- 0 resolves edges (PI-052 not resolved by a design session)
- 1 addresses edge (CONV-050 → PI-052)
- 1 close_out_payload lazy-created (COP-079)
- 1 deposit_event lazy-created

Files added to the working tree:
- PRDs/product/crmbuilder-v2/pi-052-chat-ui-design.md (canonical design doc, 16 sections + Appendix A, ~840 lines)
- PRDs/product/crmbuilder-v2/pi-052-slice-a-terminal-spike-kickoff.md (WT-048's file_path body)
- PRDs/product/crmbuilder-v2/close-out-payloads/ses_080.json (this payload)
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-080.md (this apply prompt)

PI-052 remains Open. WT-047 is consumed. WT-048 is the next active
implementation kickoff — the Slice-A terminal spike opens against it
in a follow-on Claude Code session.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git pull --rebase origin main
# (Doug pushes per push convention)
```

---

## Done

Reply with:

- Pre-apply heads (sessions / decisions / planning_items / conversations / workstreams / work_tickets / commits / COP / DEP / refs)
- Apply output record counts (1 session OK, 1 conv OK, 1 WT OK, 0 PIs, 0 commits, 11 decisions OK, 16 refs OK, 0 resolves, 1 addresses, 0 SKIPs on first run)
- Post-apply heads (SES-080, DEC-262, PI-052 unchanged, CONV-050, WS-010 unchanged, WT-048, COP-079 lazy, DEP head+1)
- WT-047 status confirmed `consumed`
- WT-048 status confirmed `ready` with file_path pointing at `pi-052-slice-a-terminal-spike-kickoff.md`
- PI-052 status confirmed `Open` (unchanged)
- CONV-050 outbound edges (belongs_to_workstream WS-010, records_session SES-080, opens_against_work_ticket WT-047, addresses PI-052)
- DEC-252..DEC-262 titles spot-checked
- Snapshot + design doc + Slice-A kickoff commit SHA
- Next: PI-052 Slice A implementation session against WT-048 — produces `crmbuilder-v2/scripts/chat_spike.py`, ~80 LOC, closes as SES-081. Separate Claude Code session.
