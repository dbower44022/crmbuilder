# CLAUDE-CODE-PROMPT — apply close-out SES-092 (governance recording rules — decision + PI)

**Last Updated:** 05-26-26
**Operating mode:** DETAIL
**Series:** Standalone governance session (continuation of the SES-089 architecture-review chat)
**Slice:** Apply the SES-092 close-out payload to the V2 governance DB
**Status:** Ready to execute. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765. No new migration. Single commit (91c760e5) already on origin/main. Payload is governance-only (one DEC + one PI + two references + one commit row).

> **Why this session record exists:** SES-089 was a Claude.ai chat that produced the architecture review for the Master CRMBuilder PRD consolidation direction. After SES-089's payload was applied (commit `c5227814`), the same Claude.ai chat continued through several substantive threads — most importantly a meta-discussion that surfaced the recurring pattern of substantive content failing to land as queryable V2 governance records. That meta-discussion produced DEC-310 (canonical rules document required) and PI-084 (create the document). Under current V2's one-chat-equals-one-session model, the cleanest way to record the post-SES-089 governance content in this chat is a second session record; this is it.
>
> **Identifier-head capture per DEC-300:** Doug provided fresh heads from his live V2 API before the sandbox assigned identifiers: SES-091, CONV-061, DEC-309, PI-083, WT-055. Next available: SES-092, CONV-062, DEC-310, PI-084. WT was not consumed by this session (no build work).

---

## Net Effect

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_092.json` to the V2 governance DB via the standard apply script. Creates:
- SES-092 (session, governance-discipline thread)
- CONV-062 (conversation, status=complete) with two reference edges (`conversation_belongs_to_workstream` → WS-011, `conversation_records_session` → SES-092)
- DEC-310 (rules document required for every session and conversation on any V2-tracked engagement)
- PI-084 (create the rules document at `specifications/governance-recording-rules.md`)
- Two reference rows: `decided_in` (DEC-310 → SES-092) and `addresses` (PI-084 → DEC-310)
- One commit row (`91c760e5...`) with the full ten-field schema (full SHA, author, committer time, repository, branch, parent SHAs, files-changed count)
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

No work tickets are opened or consumed. No existing planning items are addressed or resolved. No new migration to apply.

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. Verify the API server is reachable:
   ```bash
   curl -sf http://127.0.0.1:8765/health || echo "API not running"
   ```

3. Pull the latest from origin to make sure the sandbox commits are present locally:
   ```bash
   git fetch origin && git pull --ff-only origin main
   git log --oneline -3
   # Top commit should be the one that adds ses_092.json and this apply prompt.
   ```

4. Confirm the new identifiers do not yet exist:
   ```bash
   echo "Session (expect 404):"
   curl -o /dev/null -s -w "  SES-092 → HTTP %{http_code}\n" http://127.0.0.1:8765/sessions/SES-092

   echo "Conversation (expect 404):"
   curl -o /dev/null -s -w "  CONV-062 → HTTP %{http_code}\n" http://127.0.0.1:8765/conversations/CONV-062

   echo "Decision (expect 404):"
   curl -o /dev/null -s -w "  DEC-310 → HTTP %{http_code}\n" http://127.0.0.1:8765/decisions/DEC-310

   echo "Planning item (expect 404):"
   curl -o /dev/null -s -w "  PI-084 → HTTP %{http_code}\n" http://127.0.0.1:8765/planning-items/PI-084
   ```

5. Sanity-check the prior session (SES-089 the architecture review, SES-091 the most-recent applied session) are present and Complete:
   ```bash
   for n in 089 091; do
     curl -sf http://127.0.0.1:8765/sessions/SES-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  SES-$n:', d['status'], '|', d['title'][:75])"
   done
   ```

6. Confirm WS-011 (V2 storage API refinements) is present and in_flight (this conversation's workstream membership, carried over from SES-089 and provisional):
   ```bash
   curl -sf http://127.0.0.1:8765/workstreams/WS-011 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['workstream_identifier'], d['workstream_status'], '|', d['workstream_name'])"
   ```

---

## Apply

Run the apply script. The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` automatically:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_092.json
```

Expect:

- **1 session row** created (SES-092)
- **1 conversation row** (CONV-062) created with two reference edges (`conversation_belongs_to_workstream` → WS-011, `conversation_records_session` → SES-092)
- **1 commit row** created (91c760e560f3ded397f16b12b080a6ce22e1add1) with the full ten-field schema — should land on first try without the in-flight patching SES-089 needed
- **0 work_tickets** (no WT opened or consumed)
- **1 planning_item** created (PI-084, status=Open, item_type=pending_work)
- **1 decision row** created (DEC-310) with one `decided_in` → SES-092 edge
- **1 `addresses` reference row** (PI-084 → DEC-310)
- **0 `is_about` rows** (no is_about edges in the payload)
- **0 `resolves` rows** (no resolves_planning_items entries)
- **close_out_payload COP-NNN** lazy-created
- **deposit_event DEP-NNN** recorded with `outcome=success`

---

## Post-apply verification

```bash
echo "SES-092:"
curl -sf http://127.0.0.1:8765/sessions/SES-092 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status'])"

echo "CONV-062:"
curl -sf http://127.0.0.1:8765/conversations/CONV-062 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['conversation_title'][:80]); print('  status:', d['conversation_status'])"

echo "DEC-310:"
curl -sf http://127.0.0.1:8765/decisions/DEC-310 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status'])"

echo "PI-084:"
curl -sf http://127.0.0.1:8765/planning-items/PI-084 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status']); print('  item_type:', d['item_type'])"

echo "Commit 91c760e5:"
curl -sf 'http://127.0.0.1:8765/commits/91c760e560f3ded397f16b12b080a6ce22e1add1' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  first_line:', d['commit_message_first_line'][:75]); print('  author:', d['commit_author_name'])"

echo "decided_in edge (expect 1):"
curl -sf 'http://127.0.0.1:8765/references?relationship_kind=decided_in&target_type=session&target_id=SES-092' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print('  Count:', len(data))
for r in data:
  print(' ', r['source_type']+'/'+r['source_id'], '→', r['target_type']+'/'+r['target_id'])
"

echo "addresses edge (expect 1, PI-084 → DEC-310):"
curl -sf 'http://127.0.0.1:8765/references?relationship_kind=addresses&source_type=planning_item&source_id=PI-084' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print('  Count:', len(data))
for r in data:
  print(' ', r['source_type']+'/'+r['source_id'], '→', r['target_type']+'/'+r['target_id'])
"

echo "Latest deposit_event:"
curl -sf 'http://127.0.0.1:8765/deposit-events' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
latest = sorted(data, key=lambda x: x['deposit_event_identifier'])[-1]
print(' ', latest['deposit_event_identifier'], '/', latest['deposit_event_outcome'])
"

echo "Latest close_out_payload:"
curl -sf 'http://127.0.0.1:8765/close-out-payloads' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
latest = sorted(data, key=lambda x: x['close_out_payload_identifier'])[-1]
print(' ', latest['close_out_payload_identifier'], '/', latest['close_out_payload_status'])
"
```

---

## Commit the apply outputs

After the apply succeeds, regenerated `db-export/` snapshots and the new `dep_NNN.log` land in one consolidated commit. Per the standing rule, this commit is **NOT pushed** — Doug pushes after review.

```bash
cd ~/Dropbox/Projects/crmbuilder

git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/

git commit -m "$(cat <<'EOF'
v2: SES-092 close-out applied — governance recording rules required for all sessions and conversations

Applies the SES-092 close-out payload via apply_close_out.py.

Creates:
- SES-092 (session) — governance-discipline continuation of the SES-089
  Claude.ai chat; surfaced the recurring pattern of substantive
  content failing to land in V2 (SES-089 missing Section 3/Section 5
  PIs, identifier collisions despite DEC-300, commits[] schema gap,
  ongoing chat content uncaptured) and reached the foundational
  decision that every session and conversation against any V2-tracked
  engagement must follow a canonical documented set of process rules
- CONV-062 (conversation, status=complete) wired to WS-011 + SES-092
- DEC-310 — All sessions and conversations operating against any
  V2-tracked engagement must follow a documented set of process
  rules; the rules apply equally to AI and human agents
- PI-084 — Create the canonical governance-recording rules document
  at specifications/governance-recording-rules.md with the 10-section
  structure proposed in the conversation
- 1 commit row (91c760e560f3ded397f16b12b080a6ce22e1add1) with the
  full ten-field schema
- 1 decided_in reference (DEC-310 → SES-092)
- 1 addresses reference (PI-084 → DEC-310)
- close_out_payload COP-NNN + deposit_event DEP-NNN

No work tickets opened or consumed. No existing planning items
addressed or resolved. No new migration applied.

Items surfaced in the session but deferred to future close-outs per
the new discipline: (a) PI for sandbox close-out commits[] schema
fix; (b) Section 3 disposition decision + revision PI for SES-089
gap; (c) Section 5 disposition decision + revision PI; (d) broader
retroactive audit of prior session records for un-PI'd work.

The apply tees stdout to PRDs/product/crmbuilder-v2/deposit-event-logs/
dep_NNN.log per DEC-164 (git-tracked).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Doug pushes after review.

---

## Done

After commit succeeds:
- DEC-310 and PI-084 are governance-recorded
- The post-SES-089 governance content in the Claude.ai chat is now reflected in V2
- The discipline is in force going forward; the rules document drafting is the next concrete work item

Next steps (out of scope for this apply):
- Begin drafting `specifications/governance-recording-rules.md` v0.1 per PI-084. Either as a continuation of the current Claude.ai chat or as the focus of a new dedicated session — Doug decides.
- Author the deferred PIs surfaced in this session: commits[] schema fix; Section 3 disposition + revision; Section 5 disposition + revision; retroactive audit.
- Consider whether a dedicated workstream for governance-recording-rules work should be created (current WS-011 V2 storage API refinements is provisional).
