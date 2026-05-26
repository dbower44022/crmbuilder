# CLAUDE-CODE-PROMPT — Apply SES-083 close-out payload

**Last Updated:** 05-26-26 (drafted at PI-004 first slice build close)
**Purpose:** Apply the SES-083 close-out payload — PI-004 first slice (`field`) build close-out. Lands SES-083, CONV-053, one commit record (the PI-004-field build commit `8445933070381...` — assigned CM-NNNN at apply time), six new decisions (DEC-268..273 per field.md §3.9.1, re-keyed from spec's planned DEC-246..251), seven new planning items (PI-054..060 per field.md §3.8.3, re-keyed from spec's planned PI-053..059), three `is_about` payload references (SES-083 → PI-004, SES-083 → SES-081, SES-083 → WT-050), one `addresses_planning_items` entry (PI-004 — does NOT resolve; last sibling resolves per DEC-232 / SES-074 build-closure pattern), and the conversation's three required edges (`conversation_belongs_to_workstream` → WS-003; `conversation_records_session` → SES-083; `conversation_opens_against_work_ticket` → WT-050 consuming the kickoff ticket).

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_083.json`

**Predecessors:**
- SES-082 must have landed (commit `3af99a7` on origin/main; the PI-003 persona build apply).
- The PI-004-field build commit `8445933070381...` must be on local main (already landed at apply time).
- WS-003 ("Methodology entity schema design") is reused as the conversation's parent workstream per SES-081's precedent (CONV-051 / CONV-052 also attached to WS-003).

**Successor:** None planned for PI-004 directly — PI-004 only resolves when the LAST of the four sibling builds (`field` shipped here, plus `requirement` / `manual_config` / `test_spec`) lands its close-out with `resolves_planning_items` per the DEC-232 / SES-074 build-closure pattern.

**Identifier re-keying note:** field.md §3.9.1 planned DEC-246..251 (with disclaimer that re-keying applies if parallel work has claimed them). At the time of this build, DEC-245 was no longer the head — DEC-268 was the next available. Similarly PI-053 was claimed by an unapplied SES-081 staged payload, so the seven new PIs land at PI-054..060. SES head advanced past SES-079 (the spec's planned session) to SES-082 (PI-003 persona apply), so this is SES-083. CONV head likewise advanced to CONV-053.

---

## Scope

Apply `close-out-payloads/ses_083.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains the v0.8 nine sections:

- **1 session** (SES-083)
- **1 conversation** (CONV-053, status `complete`, embeds the three required edges atomically: `conversation_belongs_to_workstream` → WS-003, `conversation_records_session` → SES-083, `conversation_opens_against_work_ticket` → WT-050)
- **1 commit** (the PI-004-field build commit `8445933070381...` — assigned CM-NNNN at apply time with `commit_conversation_id = CONV-053`)
- **0 work_tickets** (WT-050 is consumed via the `conversation_opens_against_work_ticket` edge above, not authored fresh)
- **7 planning_items** (PI-054..060 per field.md §3.8.3: re-parenting UX; richer field_type vocab; default_value + filters; richer required-ness; field-to-field dependencies; derived-field lineage; entity-soft-delete cascade posture — all Open)
- **6 decisions** (DEC-268..273 per field.md §3.9.1: identifier prefix; field inventory + per-entity uniqueness; lifecycle; affiliation mechanism with cardinality enforcement; field_type vocab + POST atomicity; API surface + UI defaults + master-pane deferral + sidebar position re-key)
- **3 references** (three `is_about` from SES-083 to PI-004, SES-081, and WT-050 — surfacing the genealogy of the work)
- **0 resolves_planning_items** (PI-004 is addressed only; the LAST PI-004 sibling resolves it)
- **1 addresses_planning_items** (PI-004 — non-resolving edge per DEC-232 / SES-074 pattern)

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2

# Clean working tree (acknowledge unrelated unstaged work — proceed regardless)
cd .. && git status && cd crmbuilder-v2

# Pull latest commits
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Git identity
git config user.email
# Expect: doug@dougbower.com

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   /home/doug/Dropbox/Projects/crmbuilder/.venv/bin/crmbuilder-v2-api &

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_083.json

# Confirm the PI-004-field build commit is on local main
git cat-file -e 84459330703814418c9bdc9e8ec33aca33495335 2>/dev/null \
  && echo "FOUND: 8445933 — $(git log -1 --format=%s 84459330703814418c9bdc9e8ec33aca33495335)" \
  || { echo "MISSING — HALT (commit the PI-004-field build first)"; exit 1; }

# Confirm PI-004 still Open (target of addresses edge — addresses is non-resolving)
curl -s http://127.0.0.1:8765/planning-items/PI-004 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-004 status:', d['status'])"
# Expect: Open. PI-004 should REMAIN Open after this apply.

# Confirm WT-050 still ready (target of conversation_opens_against_work_ticket — consumed in this apply)
curl -s http://127.0.0.1:8765/work-tickets/WT-050 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('WT-050 status:', d['work_ticket_status'])"
# Expect: ready. If consumed, a parallel apply has already landed this closure — halt and investigate.

# Capture pre-apply heads
echo "=== Pre-apply heads ==="
for endpoint in sessions decisions planning-items; do
  echo "$endpoint:"
  curl -s "http://127.0.0.1:8765/$endpoint?limit=1000" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
done
echo "Conversations:"
curl -s 'http://127.0.0.1:8765/conversations?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['conversation_identifier'] for r in d)[-1] if d else 'none')"
echo "Workstreams:"
curl -s http://127.0.0.1:8765/workstreams | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', sorted(r['workstream_identifier'] for r in d)[-1] if d else 'none')"

# Spot-check that the field surface is reachable (smoke validates the build-commit code is loaded)
curl -sf http://127.0.0.1:8765/fields | python3 -c "import sys,json; d=json.load(sys.stdin); print('GET /fields:', 'OK envelope' if d.get('errors') is None and isinstance(d.get('data'), list) else 'UNEXPECTED', '/ count:', len(d.get('data') or []))"
curl -s http://127.0.0.1:8765/fields/next-identifier | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('next:', d.get('next'))"
```

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_083.json
```

The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` automatically. Expect:
- 1 session row created (SES-083)
- 1 conversation row created (CONV-053) with three reference edges
- 1 commit row created (CM-NNNN) tied to CONV-053
- 6 decision rows created (DEC-268..273) with `decided_in` → SES-083 edges
- 7 planning_item rows created (PI-054..060), all status Open
- 3 `is_about` payload reference rows created
- 1 `addresses` reference row created (CONV-053 → PI-004 — non-resolving)
- WT-050 transitions ready → consumed via the `conversation_opens_against_work_ticket` edge processing
- PI-004 status REMAINS Open (addresses is non-resolving)
- close_out_payload `COP-NNN` lazy-created
- deposit_event `DEP-NNN` recorded with `outcome=success` plus `wrote_record` back-edges to every record the apply POSTed

---

## Post-apply verification

```bash
# Confirm the new identifiers landed
echo "SES-083:"
curl -s http://127.0.0.1:8765/sessions/SES-083 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80])"
echo "CONV-053:"
curl -s http://127.0.0.1:8765/conversations/CONV-053 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  status:', d['conversation_status'])"
echo "DEC-268..273:"
for n in 268 269 270 271 272 273; do
  curl -s http://127.0.0.1:8765/decisions/DEC-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-$n:', d['title'][:60])"
done
echo "PI-054..060:"
for n in 054 055 056 057 058 059 060; do
  curl -s http://127.0.0.1:8765/planning-items/PI-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  PI-$n:', d['status'], '/', d['title'][:60])"
done

# Confirm PI-004 REMAINS Open (addresses-only; not resolved by this apply)
echo "PI-004 status:"
curl -s http://127.0.0.1:8765/planning-items/PI-004 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['status'])"
# Expect: Open. (PI-004 resolves only when the LAST sibling — requirement / manual_config / test_spec — ships.)

# Confirm WT-050 transitioned to consumed
echo "WT-050 status:"
curl -s http://127.0.0.1:8765/work-tickets/WT-050 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['work_ticket_status'])"
# Expect: consumed

# Confirm the deposit_event and close_out_payload landed
echo "Latest deposit_event:"
curl -s 'http://127.0.0.1:8765/deposit-events?limit=10' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
latest = sorted(data, key=lambda x: x['deposit_event_identifier'])[-1]
print(' ', latest['deposit_event_identifier'], '/', latest['deposit_event_outcome'])
"
echo "Latest close_out_payload:"
curl -s 'http://127.0.0.1:8765/close-out-payloads?limit=10' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
latest = sorted(data, key=lambda x: x['close_out_payload_identifier'])[-1]
print(' ', latest['close_out_payload_identifier'], '/', latest['close_out_payload_status'])
"

# Spot-check the field surface still works after apply (regression check — the apply
# shouldn't touch the field table, but verify the API surface is unaffected)
curl -sf http://127.0.0.1:8765/fields > /dev/null && echo "GET /fields: OK"
curl -s http://127.0.0.1:8765/fields/next-identifier | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('next field:', d.get('next'))"
```

---

## Commit the apply artifacts

After the apply succeeds:

```bash
cd ~/Dropbox/Projects/crmbuilder
git status
# Expected changed files:
#   modified: PRDs/product/crmbuilder-v2/db-export/change_log.json
#   modified: PRDs/product/crmbuilder-v2/db-export/sessions.json
#   modified: PRDs/product/crmbuilder-v2/db-export/conversations.json
#   modified: PRDs/product/crmbuilder-v2/db-export/decisions.json
#   modified: PRDs/product/crmbuilder-v2/db-export/planning_items.json
#   modified: PRDs/product/crmbuilder-v2/db-export/references.json
#   modified: PRDs/product/crmbuilder-v2/db-export/work_tickets.json
#   modified: PRDs/product/crmbuilder-v2/db-export/close_out_payloads.json
#   modified: PRDs/product/crmbuilder-v2/db-export/deposit_events.json
#   modified: PRDs/product/crmbuilder-v2/db-export/commits.json
#   modified: PRDs/product/crmbuilder-v2/db-export/fields.json  (new file — fields table snapshot, currently empty after the smoke-test cleanup)
#   new file: PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log
```

The build commit (containing the migration + code + tests + close-out payload + this apply prompt) was committed before the apply ran. After the apply, the db-export snapshots and the deposit-event log file are uncommitted; they go in a follow-up commit:

```bash
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log
git commit -m "$(cat <<'EOF'
v2: SES-083 apply — db-export snapshots + dep_NNN.log after PI-004 first slice close-out

Applied ses_083.json via apply_close_out.py. Lands SES-083, CONV-053,
CM-NNNN, DEC-268..273, PI-054..060 (all Open), three is_about edges,
addresses (non-resolving) PI-004, consumes WT-050 (ready → consumed),
creates COP-NNN, DEP-NNN. Field methodology entity type is shipped;
PI-004 remains Open (resolves when the last of requirement /
manual_config / test_spec lands).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Done

Reply with:
- Pre-apply Alembic head: `0014_v0_8_create_fields_table`
- New SES identifier: `SES-083`
- New CONV identifier: `CONV-053`
- New DEC identifiers: `DEC-268` through `DEC-273`
- New PI identifiers: `PI-054` through `PI-060`
- New CM identifier: `CM-NNNN`
- New COP identifier: `COP-NNN`
- New DEP identifier: `DEP-NNN`
- PI-004 status post-apply: `Open` (addresses-only; not resolved)
- WT-050 status post-apply: `consumed`
- Total tests: 1659 passed, 3 skipped (delta +41 from baseline of 1618)
- Open items for next session: PI-004 still has three siblings (requirement, manual_config, test_spec) outstanding before it can resolve. The four remaining v0.5+ build prompts (WT-051..054) await execution.
