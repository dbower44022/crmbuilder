# CLAUDE-CODE-PROMPT — Apply SES-088 close-out payload

**Last Updated:** 05-26-26
**Purpose:** Apply the SES-088 close-out payload — PI-005's build closure. Lands SES-088, CONV-058, one commit record (`2bd7428` for the PI-005 build, assigned CM-NNNN at apply time), zero new decisions, zero new planning items, three `is_about` payload references, and one `resolves_planning_items` entry that atomically flips PI-005 to Resolved.

**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_088.json`

**Predecessors:**
- SES-087 must have landed (commit `3c0ccbf`, applied per its apply prompt).
- The PI-005 build commit `2bd7428dd7f5e16bb4bd9a632594257996c4d9b0` must be on `origin/main`.
- WS-003 (Methodology entity schema design) exists from v0.4 — no workstream pre-step required. CONV-058 attaches via the standard `conversation_belongs_to_workstream` edge (matching the SES-082..086 PI-003/PI-004-cohort pattern).
- WT-054 (Build process v2 schema growth end-to-end) exists in status `ready`; CONV-058 consumes it via `conversation_opens_against_work_ticket`.

**Successor:** None planned. Future v0.7+ Process schema growth (structured `process_steps`, process variants, step-as-first-class-record, `process_definition_level` lifecycle, master-pane growth) is CBM-redo-conditional per spec §3.8.3.

---

## Scope

Apply `close-out-payloads/ses_088.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains the v0.8 nine sections:

- **1 session** (SES-088)
- **1 conversation** (CONV-058, status `complete`, embeds three edges: `conversation_belongs_to_workstream` → WS-003, `conversation_records_session` → SES-088, `conversation_opens_against_work_ticket` → WT-054)
- **1 commit** (`2bd7428` — the PI-005 build — assigned CM-NNNN at apply time with `commit_conversation_id = CONV-058`)
- **0 work_tickets**
- **0 decisions**
- **0 planning_items**
- **3 references** (three `is_about` from SES-088 to PI-005, SES-081, DEC-039 — capturing the genealogy)
- **1 resolves_planning_item** (PI-005 — server-side atomic edge+flip; PI-005 status flips Open → Resolved in the same transaction)
- **0 addresses_planning_items**

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

---

## Pre-flight

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2

# Clean working tree (acknowledge unrelated unstaged work — proceed regardless)
git status
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Git identity
git config user.email
# Expect: doug@dougbower.com

# API health
curl -sf http://127.0.0.1:8765/health

# Confirm the PI-005 build commit is on local main
git cat-file -e 2bd7428dd7f5e16bb4bd9a632594257996c4d9b0 \
  && echo "FOUND: PI-005 build commit" \
  || { echo "MISSING build commit"; exit 1; }

# Confirm WT-054 status, PI-005 status
curl -s http://127.0.0.1:8765/planning-items/PI-005 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-005 status:', d['status'])"
# Expect: Open

curl -s http://127.0.0.1:8765/work-tickets/WT-054 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('WT-054 status:', d['work_ticket_status'])"
# Expect: ready

# Capture pre-apply identifier heads
for endpoint in sessions conversations commits; do
  echo "$endpoint head:"
  curl -s "http://127.0.0.1:8765/$endpoint/next-identifier" \
    | python3 -c "import sys,json;print(' ', json.load(sys.stdin)['data']['next'])"
done
```

**Expected pre-apply state:** sessions next at least SES-088, conversations next at least CONV-058, commits next at least CM-0009, PI-005 status `Open`, WT-054 status `ready`. The "at least" hedges accommodate parallel-sandbox claims between this prompt's authoring and the apply.

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2

uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_088.json
```

Expected output: sections processed in order (session → conversation → work_tickets [empty] → planning_items [empty] → commits → decisions [empty] → references → resolves_planning_items → addresses_planning_items [empty]) followed by the deposit_event POST. The atomic resolves edge fires inside the references machinery and flips PI-005 to Resolved in the same transaction. Apply stdout is teed to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` (DEC-164).

---

## Post-apply verification

```bash
# PI-005 should be Resolved
curl -s http://127.0.0.1:8765/planning-items/PI-005 \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('PI-005 status:', d['status'])"
# Expect: Resolved

# Session/conversation linkages
curl -s http://127.0.0.1:8765/sessions/SES-088 | python3 -c "import sys,json; print('SES-088:', json.load(sys.stdin)['data']['title'][:80])"
curl -s http://127.0.0.1:8765/conversations/CONV-058 | python3 -c "import sys,json; print('CONV-058 status:', json.load(sys.stdin)['data']['conversation_status'])"

# Three required edges on CONV-058
curl -s 'http://127.0.0.1:8765/references?source_type=conversation&source_id=CONV-058' | python3 -c "
import sys, json
for r in json.load(sys.stdin)['data']:
    print(' ', r['relationship'], '->', r['target_type'], r['target_id'])
"

# WT-054 should now be consumed (via the conversation_opens_against_work_ticket edge)
curl -s http://127.0.0.1:8765/work-tickets/WT-054 | python3 -c "import sys,json; print('WT-054 status:', json.load(sys.stdin)['data']['work_ticket_status'])"

# Commit attribution
curl -s 'http://127.0.0.1:8765/commits?limit=2000' | python3 -c "
import sys, json
for r in json.load(sys.stdin)['data']:
    if r['commit_sha'].startswith('2bd7428'):
        print('Commit:', r['commit_identifier'], 'conv:', r.get('commit_conversation_id'))
"
```

---

## Apply-commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/ \
  PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log \
  PRDs/product/crmbuilder-v2/close-out-payloads/ses_088.json \
  PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-088.md

git commit -m "$(cat <<'EOF'
v2: SES-088 close-out applied — PI-005 → Resolved

Apply records:
  - SES-088 (PI-005 build closure)
  - CONV-058 (build conversation; attached to WS-003, consumes WT-054)
  - CM-NNNN (the PI-005 build commit 2bd7428)
  - COP-NNN (close-out payload) + DEP-NNN (deposit event)
  - 3 is_about references (SES-088 → PI-005, SES-081, DEC-039)
  - resolves edge CONV-058 → PI-005 (atomic edge+flip; Open → Resolved)

PI-005 fully resolved. WT-054 consumed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Idempotency

Re-running the apply is safe — HTTP 409 SKIPs treated as already-present; the resolves edge re-POST returns 409 and PI-005 stays Resolved; a second deposit_event is emitted for the re-run (deposit_events are append-only).

## Re-key if needed

If `SES-088`, `CONV-058`, or `CM-0009` is claimed by a parallel session between draft and apply, re-key the payload and this prompt per the v2 session-lifecycle identifier-collision contingency. See SES-074's apply prompt for the worked pattern.
