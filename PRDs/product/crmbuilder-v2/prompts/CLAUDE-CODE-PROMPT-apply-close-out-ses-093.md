# CLAUDE-CODE-PROMPT — apply close-out SES-093 (dogfood reframe — DEC-311 + PI-085..088 supersede PI-084)

**Last Updated:** 05-26-26
**Operating mode:** DETAIL
**Series:** Standalone governance session (continuation of the SES-089/SES-092 Claude.ai chat)
**Slice:** Apply the SES-093 close-out payload to the V2 governance DB
**Status:** Ready to execute. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765. No new migration. One commit (`e357bfc5d8d75bbc776d05dd4c542afebd3528eb` — kickoff prompt for PI-085 drafting) already on origin/main. Payload is governance-only (one DEC + four PIs + eleven references + one commit row).

> **Why this session record exists:** During the post-SES-092 follow-on discussion, Doug surfaced that PI-084's "create a standalone rules document" approach didn't dogfood the CRMBuilder methodology properly. Per DEC-295, CRMBuilder should produce its governance recording artifacts as Domain Overview + Persona entities + Process PRDs — using its own methodology against itself. SES-093 captures the reframe: DEC-311 records the shape change; PI-085 supersedes PI-084 (Domain Overview as the direct successor); PI-086 (Personas), PI-087 (Session/Conversation Process PRD, which contains the rules content), PI-088 (meta Process PRD Definition Process) expand the scope.
>
> **Identifier-head capture per DEC-300:** Doug provided fresh heads from live V2 API before the sandbox assigned identifiers: SES-092, CONV-062, DEC-310, PI-084. Next available: SES-093, CONV-063, DEC-311, PI-085+. The fact that SES-092 had been applied during the conversation (PI-084 now live in V2) ruled out in-place payload amendment and required this new session record.

---

## Net Effect

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_093.json` to the V2 governance DB via the standard apply script. Creates:

- SES-093 (session, dogfood reframe)
- CONV-063 (conversation, status=complete) with two reference edges (`conversation_belongs_to_workstream` → WS-011, `conversation_records_session` → SES-093)
- DEC-311 (dogfood reframe — produce as Domain Overview + Personas + Process PRDs; supersedes PI-084's standalone rules document approach; DEC-310's rules-required mandate stays in force)
- PI-085 (Domain Overview)
- PI-086 (Personas — separate first-class entities)
- PI-087 (Session/Conversation governance Process PRD — contains the rules content)
- PI-088 (Meta Process PRD Definition Process)
- 11 reference rows:
  - `decided_in` DEC-311 → SES-093
  - `addresses` PI-085 → DEC-311
  - `addresses` PI-086 → DEC-311
  - `addresses` PI-087 → DEC-311
  - `addresses` PI-088 → DEC-311
  - `addresses` PI-087 → DEC-310 (the rules-required mandate is fulfilled by the Session/Conversation Process PRD)
  - `supersedes` PI-085 → PI-084 (Domain Overview supersedes the rules document approach as the direct successor)
  - `blocked_by` PI-086 → PI-085 (Personas defined after Domain identifies which are involved)
  - `blocked_by` PI-087 → PI-085 (Process defined within the named Domain)
  - `blocked_by` PI-087 → PI-086 (Process uses Personas)
  - `blocked_by` PI-088 → PI-087 (Meta Process formalized after observing concrete Process)
- 1 commit row (`e357bfc5...`) — kickoff prompt for PI-085 Domain Overview drafting session
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

No work tickets opened or consumed. No existing planning items resolved or addressed (note: `addresses` references in `references[]` link PIs to DECs, not the `addresses_planning_items[]` section which links the conversation to PIs being worked).

PI-084 itself is not status-updated; its supersession is marked by the reference graph (`supersedes` PI-085 → PI-084).

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. Verify the API server is reachable:
   ```bash
   curl -sf http://127.0.0.1:8765/health || echo "API not running"
   ```

3. Pull the latest from origin:
   ```bash
   git fetch origin && git pull --ff-only origin main
   git log --oneline -3
   # Top two commits should be: this commit (adds ses_093.json + apply prompt) and e357bfc5 (kickoff prompt for PI-085).
   ```

4. Confirm the new identifiers do not yet exist:
   ```bash
   echo "Session (expect 404):"
   curl -o /dev/null -s -w "  SES-093 → HTTP %{http_code}\n" http://127.0.0.1:8765/sessions/SES-093

   echo "Conversation (expect 404):"
   curl -o /dev/null -s -w "  CONV-063 → HTTP %{http_code}\n" http://127.0.0.1:8765/conversations/CONV-063

   echo "Decision (expect 404):"
   curl -o /dev/null -s -w "  DEC-311 → HTTP %{http_code}\n" http://127.0.0.1:8765/decisions/DEC-311

   echo "Planning items (expect 404 for all):"
   for n in 085 086 087 088; do
     curl -o /dev/null -s -w "  PI-$n → HTTP %{http_code}\n" http://127.0.0.1:8765/planning-items/PI-$n
   done
   ```

5. Sanity-check predecessor records — PI-084 (being superseded), DEC-310 (rules mandate, still active), SES-092 (predecessor session):
   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-084 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  PI-084:', d['status'], '|', d['title'][:75])"
   curl -sf http://127.0.0.1:8765/decisions/DEC-310 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-310:', d['status'], '|', d['title'][:75])"
   curl -sf http://127.0.0.1:8765/sessions/SES-092 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  SES-092:', d['status'], '|', d['title'][:75])"
   ```

6. Confirm WS-011 still in_flight:
   ```bash
   curl -sf http://127.0.0.1:8765/workstreams/WS-011 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['workstream_identifier'], d['workstream_status'], '|', d['workstream_name'])"
   ```

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_093.json
```

Expect:

- **1 session row** created (SES-093)
- **1 conversation row** (CONV-063) created with two conversation reference edges
- **1 commit row** created (e357bfc5d8d75bbc776d05dd4c542afebd3528eb) with full ten-field schema
- **0 work_tickets**
- **4 planning_items** created (PI-085..PI-088, all status=Open, all item_type=pending_work)
- **1 decision row** created (DEC-311) with one `decided_in` → SES-093 edge
- **5 `addresses` reference rows** (PI-085, PI-086, PI-087, PI-088 → DEC-311; plus PI-087 → DEC-310)
- **1 `supersedes` reference row** (PI-085 → PI-084)
- **4 `blocked_by` reference rows** (PI-086 → PI-085; PI-087 → PI-085; PI-087 → PI-086; PI-088 → PI-087)
- **close_out_payload COP-NNN** lazy-created
- **deposit_event DEP-NNN** recorded with `outcome=success`

---

## Post-apply verification

```bash
echo "SES-093:"
curl -sf http://127.0.0.1:8765/sessions/SES-093 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status'])"

echo "CONV-063:"
curl -sf http://127.0.0.1:8765/conversations/CONV-063 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['conversation_title'][:80]); print('  status:', d['conversation_status'])"

echo "DEC-311:"
curl -sf http://127.0.0.1:8765/decisions/DEC-311 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status'])"

echo "PI-085..088:"
for n in 085 086 087 088; do
  curl -sf http://127.0.0.1:8765/planning-items/PI-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  PI-$n:', d['status'], '|', d['title'][:80])"
done

echo "Commit e357bfc5:"
curl -sf 'http://127.0.0.1:8765/commits/e357bfc5d8d75bbc776d05dd4c542afebd3528eb' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  first_line:', d['commit_message_first_line'][:75])"

echo "decided_in edge (expect 1):"
curl -sf 'http://127.0.0.1:8765/references?relationship_kind=decided_in&target_type=session&target_id=SES-093' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print('  Count:', len(data))
"

echo "supersedes edge (expect PI-085 → PI-084):"
curl -sf 'http://127.0.0.1:8765/references?relationship_kind=supersedes&source_type=planning_item&source_id=PI-085' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
for r in data:
  print(' ', r['source_type']+'/'+r['source_id'], 'supersedes', r['target_type']+'/'+r['target_id'])
"

echo "addresses edges from new PIs (expect 5 — four to DEC-311, one to DEC-310):"
for n in 085 086 087 088; do
  curl -sf "http://127.0.0.1:8765/references?relationship_kind=addresses&source_type=planning_item&source_id=PI-$n" | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
for r in data:
  print(' ', r['source_type']+'/'+r['source_id'], 'addresses', r['target_type']+'/'+r['target_id'])
"
done

echo "blocked_by edges (expect 4):"
for n in 085 086 087 088; do
  curl -sf "http://127.0.0.1:8765/references?relationship_kind=blocked_by&source_type=planning_item&source_id=PI-$n" | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
for r in data:
  print(' ', r['source_type']+'/'+r['source_id'], 'blocked_by', r['target_type']+'/'+r['target_id'])
"
done

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

After apply succeeds, regenerated `db-export/` snapshots and the new `dep_NNN.log` land in one consolidated commit. Per the standing rule, this commit is **NOT pushed** — Doug pushes after review.

```bash
cd ~/Dropbox/Projects/crmbuilder

git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/

git commit -m "$(cat <<'EOF'
v2: SES-093 close-out applied — dogfood reframe (DEC-311 + PI-085..088 supersede PI-084)

Applies the SES-093 close-out payload via apply_close_out.py.

Creates:
- SES-093 (session) — dogfood reframe of governance recording; rather
  than producing a standalone rules document (PI-084's original
  scope), produce CRMBuilder methodology artifacts: Domain Overview +
  Personas + Process PRDs
- CONV-063 (conversation, status=complete) wired to WS-011 + SES-093
- DEC-311 — Produce governance recording as Domain Overview + Persona
  entities + Process PRDs; supersedes PI-084's standalone rules
  document approach. DEC-310's rules-required mandate stays in force.
- PI-085 — Define the CRMBuilder Domain that owns governance
  recording (Domain Overview document). Supersedes PI-084.
- PI-086 — Define the Personas referenced by the Domain (separate
  first-class entities, not nested under Domain). Blocked by PI-085.
- PI-087 — Define the Session/Conversation governance Process PRD
  (contains the rules content originally planned for PI-084).
  Blocked by PI-085 and PI-086.
- PI-088 — Define the standard Process PRD Definition Process (meta
  Process PRD, formalized from observed practice). Blocked by PI-087.
- 1 commit row (e357bfc5d8d75bbc776d05dd4c542afebd3528eb) — kickoff
  prompt for the PI-085 Domain Overview drafting session
- 11 reference rows:
  * decided_in (DEC-311 → SES-093)
  * addresses (PI-085/086/087/088 → DEC-311)
  * addresses (PI-087 → DEC-310; the rules-required mandate is
    fulfilled by the Session/Conversation Process PRD)
  * supersedes (PI-085 → PI-084)
  * blocked_by (PI-086 → PI-085; PI-087 → PI-085; PI-087 → PI-086;
    PI-088 → PI-087)
- close_out_payload COP-NNN + deposit_event DEP-NNN

No work tickets opened or consumed. PI-084's status is not changed;
its supersession is marked by the reference graph.

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
- DEC-311 + four new PIs are governance-recorded
- PI-084's supersession is visible in the reference graph
- The kickoff prompt for the new Claude.ai session (executing PI-085) is on origin and ready to use

Next steps (out of scope for this apply):
- Open a new Claude.ai conversation, paste the seed prompt from `PRDs/product/crmbuilder-v2/pi-085-domain-overview-drafting-kickoff.md`, and execute PI-085 (Domain Overview drafting).
- After PI-085: PI-086 (Personas) and PI-087 (Session/Conversation Process PRD) become unblocked.
- After PI-087: PI-088 (Meta Process PRD Definition Process) becomes unblocked.
- Deferred items from prior sessions still pending PI authoring: commits[] schema fix; Section 3 disposition + revision; Section 5 disposition + revision; broader retroactive audit. These can be picked up as future small close-outs or folded into ongoing sessions per the discipline.
