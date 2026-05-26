# CLAUDE-CODE-PROMPT — Apply SES-082 close-out payload

**Last Updated:** 05-25-26 (drafted at PI-003 build close)
**Purpose:** Apply the SES-082 close-out payload — PI-003's build closure. Lands SES-082, CONV-052, one commit record (the PI-003 build commit — assigned CM-NNNN at apply time), five new decisions (DEC-263..267 per persona.md §3.9.1), three `is_about` payload references (SES-082 → PI-003, SES-082 → SES-081, SES-082 → WT-049), one `resolves_planning_items` entry that atomically flips PI-003 to Resolved via slice A's server-side atomic edge+flip, and the conversation's three required edges (`conversation_belongs_to_workstream` → WS-003; `conversation_records_session` → SES-082; `conversation_opens_against_work_ticket` → WT-049 consuming the kickoff ticket).

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_082.json`

**Predecessors:**
- SES-081 must have landed (commit `4e518fe` on origin/main; the design-phase close-out that produced WT-049 and the build prompt).
- The PI-003 build commit must be on local main — Doug commits before running this apply.
- WS-003 ("Methodology entity schema design") is reused as the conversation's parent workstream per SES-081's precedent (CONV-051 also attached to WS-003 even though WS-003's primary v0.4 scope is `complete` — the v0.5+ extension work is a coherent continuation per SES-081's `in_flight_at_end`).

**Successor:** None planned for PI-003 directly. The five remaining v0.5+ methodology-entity build prompts (WT-050..054) await execution: field (PI-004 portion) next, then requirement / manual_config / test_spec, then process-v2 last.

---

## Pre-publication TODOs (Doug fills these in before running the apply)

Before running this prompt, the following placeholders in the payload (`ses_082.json`) need to be filled in with concrete values:

1. **`<COMMIT_SHA_TBD>`** — the SHA of the PI-003 build commit on `origin/main`. Replace in:
   - `close-out-payloads/ses_082.json` → `commits[0].commit_sha`
2. **`<COMMIT_DATE_TBD>`** — the ISO 8601 commit timestamp (`git log -1 --format=%cI <SHA>`). Replace in:
   - `close-out-payloads/ses_082.json` → `commits[0].commit_committed_at`
3. **`<COMMIT_PARENT_SHA_TBD>`** — the single parent SHA (`git log -1 --format='%P' <SHA>`). Replace in:
   - `close-out-payloads/ses_082.json` → `commits[0].commit_parent_shas`
4. **`commits[0].commit_files_changed_count`** — currently set to 19 (the modified/added file count at draft time). Confirm with `git show --stat <SHA> | tail -1`. If the actual count differs slightly (e.g., 20 or 18), update accordingly.

After filling in, the placeholders should be gone — search `grep -n 'TBD' PRDs/product/crmbuilder-v2/close-out-payloads/ses_082.json` to verify.

---

## Scope

Apply `close-out-payloads/ses_082.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains the v0.8 nine sections:

- **1 session** (SES-082)
- **1 conversation** (CONV-052, status `complete`, embeds the three required edges atomically: `conversation_belongs_to_workstream` → WS-003, `conversation_records_session` → SES-082, `conversation_opens_against_work_ticket` → WT-049)
- **1 commit** (the PI-003 build commit — assigned CM-NNNN at apply time with `commit_conversation_id = CONV-052`)
- **0 work_tickets** (WT-049 is consumed via the `conversation_opens_against_work_ticket` edge above, not authored fresh)
- **5 decisions** (DEC-263..267 per persona.md §3.9.1: identifier prefix; field inventory; lifecycle; affiliation/realization mechanisms; API surface + UI defaults + create-dialog flow choice)
- **0 planning_items** (this build creates no new PIs; the three v0.6+ deferred items in persona.md §3.8.3 are deliberately not authored)
- **3 references** (three `is_about` from SES-082 to PI-003, SES-081, and WT-049 — surfacing the genealogy of the work)
- **1 resolves_planning_item** (PI-003 — server-side atomic edge+flip via slice A; PI-003 status flips Open → Resolved in the same transaction; WT-049 transitions ready → consumed via the conversation edge)
- **0 addresses_planning_items**

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

# Verify the payload file exists and has no TBD placeholders
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_082.json
grep -n 'TBD' ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_082.json || echo "OK: no TBD placeholders remain"

# Confirm the PI-003 commit is on local main (replace <SHA> with the actual SHA from commits[0].commit_sha)
git cat-file -e <SHA> 2>/dev/null \
  && echo "FOUND: <SHA> — $(git log -1 --format=%s <SHA>)" \
  || { echo "MISSING: <SHA> — HALT (commit the PI-003 build first)"; exit 1; }

# Confirm PI-003 still Open (target of resolves edge — flip happens in this apply)
curl -s http://127.0.0.1:8765/planning-items/PI-003 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-003 status:', d['status'])"
# Expect: Open. If Resolved, a parallel apply has already landed this closure — halt and investigate.

# Confirm WT-049 still ready (target of conversation_opens_against_work_ticket — consumed in this apply)
curl -s http://127.0.0.1:8765/work-tickets/WT-049 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('WT-049 status:', d['work_ticket_status'])"
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

# Spot-check that the persona surface is reachable (smoke validates the build-commit code is loaded)
curl -sf http://127.0.0.1:8765/personas | python3 -c "import sys,json; d=json.load(sys.stdin); print('GET /personas:', 'OK envelope' if d.get('errors') is None and isinstance(d.get('data'), list) else 'UNEXPECTED', '/ count:', len(d.get('data') or []))"
curl -s http://127.0.0.1:8765/personas/next-identifier | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('next:', d.get('next'))"
```

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_082.json
```

The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` automatically. Expect:
- 1 session row created (SES-082)
- 1 conversation row created (CONV-052) with three reference edges
- 1 commit row created (CM-NNNN) tied to CONV-052
- 5 decision rows created (DEC-263..267) with `decided_in` → SES-082 edges
- 3 `is_about` payload reference rows created
- 1 `resolves` reference row created (SES-082 → PI-003 wired via session→planning_item or conversation→planning_item — the script handles the edge type; either way the resolves transition flips PI-003 to Resolved)
- WT-049 transitions ready → consumed via the `conversation_opens_against_work_ticket` edge processing
- close_out_payload `COP-NNN` lazy-created
- deposit_event `DEP-NNN` recorded with `outcome=success` plus `wrote_record` back-edges to every record the apply POSTed

---

## Post-apply verification

```bash
# Confirm the new identifiers landed
echo "SES-082:"
curl -s http://127.0.0.1:8765/sessions/SES-082 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80])"
echo "CONV-052:"
curl -s http://127.0.0.1:8765/conversations/CONV-052 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  status:', d['conversation_status'])"
echo "DEC-263..267:"
for n in 263 264 265 266 267; do
  curl -s http://127.0.0.1:8765/decisions/DEC-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-$n:', d['title'][:60])"
done

# Confirm PI-003 flipped to Resolved
echo "PI-003 status:"
curl -s http://127.0.0.1:8765/planning-items/PI-003 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['status'])"
# Expect: Resolved

# Confirm WT-049 transitioned to consumed
echo "WT-049 status:"
curl -s http://127.0.0.1:8765/work-tickets/WT-049 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['work_ticket_status'])"
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

# Spot-check the persona surface still works after apply (regression check — the apply
# shouldn't touch the persona table, but verify the API surface is unaffected)
curl -sf http://127.0.0.1:8765/personas > /dev/null && echo "GET /personas: OK"
curl -s http://127.0.0.1:8765/personas/next-identifier | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('next persona:', d.get('next'))"
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
#   new file: PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log
```

The build commit (containing the migration + code + tests + payload + apply prompt) was committed before the apply ran. After the apply, the db-export snapshots and the deposit-event log file are uncommitted; they go in a follow-up commit:

```bash
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log
git commit -m "$(cat <<'EOF'
v2: SES-082 apply — db-export snapshots + dep_NNN.log after PI-003 close-out

Applied ses_082.json via apply_close_out.py. Lands SES-082, CONV-052,
CM-NNNN, DEC-263..267, three is_about edges, resolves PI-003
(Open → Resolved), consumes WT-049 (ready → consumed), creates
COP-NNN, DEP-NNN. Persona methodology entity type is shipped.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

**Note:** in many SES close-outs (e.g., SES-078) the build commit and the apply commit are squashed by committing everything together at the end of the build session — payload + apply prompt + code + dep_NNN.log + db-export snapshots in one commit. The choice between two-commit (build-then-apply) and one-commit (build-and-apply-together) is a style preference; per the build prompt this build chose the one-commit pattern, so this apply step's resulting db-export + dep_NNN.log changes go in a small follow-up commit only if the apply runs after the build commit has already landed. If the build runs the apply before the build commit (the build-prompt-recommended order), the entire output goes in the single commit.

---

## Done

Reply with:
- Pre-apply Alembic head: `0013_v0_8_create_personas_table`
- New SES identifier: `SES-082`
- New CONV identifier: `CONV-052`
- New DEC identifiers: `DEC-263` through `DEC-267`
- New CM identifier: `CM-NNNN`
- New COP identifier: `COP-NNN`
- New DEP identifier: `DEP-NNN`
- PI-003 status post-apply: `Resolved`
- WT-049 status post-apply: `consumed`
- Total tests: 1618 passed, 3 skipped (delta +76 from baseline of 1542)
- Open items for next session: none for PI-003 itself; the five remaining v0.5+ build prompts (WT-050..054) await execution.
