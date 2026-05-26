# CLAUDE-CODE-PROMPT — apply close-out SES-087 (architecture review — Master CRMBuilder PRD consolidation direction-setting)

**Last Updated:** 05-26-26
**Operating mode:** DETAIL
**Series:** Strategic-direction architecture review (standalone, not part of a build cohort)
**Slice:** Apply the SES-087 close-out payload to the V2 governance DB
**Status:** Ready to execute. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765. No new migration; pure governance content (session + conversation + planning items + decisions + references). The five session content commits (CLAUDE.md direction-setting, Master CRMBuilder PRD v0.1, discussion-draft marker, glossary v0.1, glossary v0.2) are already on origin/main from the sandbox.

> **Why SES-087 and not SES-085:** the sandbox originally authored this close-out as SES-085 with identifier ranges based on origin/main's db-export snapshot (which showed SES-084 as the head). At the same time, Claude Code was applying SES-085 (PI-004 manual_config) and SES-086 (PI-004 test_spec) locally, consuming SES-085, SES-086, CONV-055, CONV-056, DEC-279..287, and WT-052/WT-053. The sandbox push collided with those local applies on `ses_085.json` and the apply prompt; the merge kept Doug's local SES-085/SES-086 close-outs (manual_config + test_spec). This file is the rebuilt version of the architecture-review close-out using the true next-available identifiers (SES-087, CONV-057, DEC-288..296). Planning items PI-061..PI-073 were not consumed by the parallel applies and remain valid in the original numbering.

---

## Net Effect

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_087.json` to the V2 governance DB via the standard apply script. Creates SES-087 + CONV-057 + 13 planning items (PI-061..PI-073) + 9 decisions (DEC-288..DEC-296) + 9 `decided_in` reference edges + 5 commit rows + the standard conversation reference edges (`conversation_belongs_to_workstream` → WS-011, `conversation_records_session` → SES-087) + lazy-creates the close_out_payload (COP-NNN) and deposit_event (DEP-NNN), tee'ing the apply log to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`.

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
   # Top commit should be the one that adds ses_087.json + the SES-087 apply prompt
   ```

4. Confirm the new identifiers do not yet exist (no parallel-apply collision):
   ```bash
   echo "Sessions (expect 404):"
   curl -o /dev/null -s -w "  SES-087 → HTTP %{http_code}\n" http://127.0.0.1:8765/sessions/SES-087

   echo "Conversations (expect 404):"
   curl -o /dev/null -s -w "  CONV-057 → HTTP %{http_code}\n" http://127.0.0.1:8765/conversations/CONV-057

   echo "Decisions (expect 404 for all):"
   for n in 288 289 290 291 292 293 294 295 296; do
     curl -o /dev/null -s -w "  DEC-$n → HTTP %{http_code}\n" http://127.0.0.1:8765/decisions/DEC-$n
   done

   echo "Planning items (expect 404 for all):"
   for n in 061 062 063 064 065 066 067 068 069 070 071 072 073; do
     curl -o /dev/null -s -w "  PI-$n → HTTP %{http_code}\n" http://127.0.0.1:8765/planning-items/PI-$n
   done
   ```

5. Confirm SES-085 and SES-086 (the parallel-applied PI-004 manual_config and test_spec close-outs) are present and `Complete` — sanity check that the local applies completed cleanly before this one stacks on top:
   ```bash
   for n in 085 086; do
     curl -sf http://127.0.0.1:8765/sessions/SES-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  SES-$n:', d['status'], '|', d['title'][:70])"
   done
   ```

6. Confirm WS-011 (V2 storage API refinements) is present and in_flight (this conversation's workstream membership):
   ```bash
   curl -sf http://127.0.0.1:8765/workstreams/WS-011 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['workstream_identifier'], d['workstream_status'], '|', d['workstream_name'])"
   # Expect: WS-011 in_flight | V2 storage API refinements
   ```

---

## Apply

Run the apply script. The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` automatically:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_087.json
```

Expect:

- **1 session row** created (SES-087)
- **1 conversation row** (CONV-057) created with two reference edges (`conversation_belongs_to_workstream` → WS-011, `conversation_records_session` → SES-087)
- **5 commit rows** created (09f8f62d, cfaec293, e9d30e0b, d9337607, 794d5f41)
- **0 work_tickets** (no WT opened or consumed by this conversation — it was strategic-direction work without a build-prompt deliverable)
- **13 planning_items** created (PI-061..PI-073), all status=Open, all item_type=pending_work
- **9 decision rows** created (DEC-288..DEC-296) with `decided_in` → SES-087 edges
- **0 `is_about` payload reference rows** (no is_about edges in the payload)
- **0 `addresses` reference rows** (no addresses_planning_items entries)
- **0 `resolves` rows** (no resolves_planning_items entries)
- **close_out_payload COP-NNN** lazy-created
- **deposit_event DEP-NNN** recorded with `outcome=success` plus `wrote_record` back-edges to every record the apply POSTed

---

## Post-apply verification

```bash
echo "SES-087:"
curl -sf http://127.0.0.1:8765/sessions/SES-087 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status'])"

echo "CONV-057:"
curl -sf http://127.0.0.1:8765/conversations/CONV-057 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['conversation_title'][:80]); print('  status:', d['conversation_status'])"

echo "DEC-288..296:"
for n in 288 289 290 291 292 293 294 295 296; do
  curl -sf http://127.0.0.1:8765/decisions/DEC-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-$n:', d['title'][:80])"
done

echo "PI-061..073:"
for n in 061 062 063 064 065 066 067 068 069 070 071 072 073; do
  curl -sf http://127.0.0.1:8765/planning-items/PI-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  PI-$n:', d['status'], '|', d['title'][:75])"
done

echo "Commits (5 expected from this session):"
for sha in 09f8f62d cfaec293 e9d30e0b d9337607 794d5f41; do
  curl -sf "http://127.0.0.1:8765/commits/$sha" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  '+'$sha'+':', d['commit_message_first_line'][:75])" 2>/dev/null || echo "  $sha: (not found via short SHA — check the full 40-char SHA)"
done

echo "decided_in edges (expect 9 — one per DEC pointing to SES-087):"
curl -sf 'http://127.0.0.1:8765/references?relationship_kind=decided_in&target_type=session&target_id=SES-087' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print('  Count:', len(data))
for r in sorted(data, key=lambda x: x['source_id']):
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

After the apply succeeds, the regenerated `db-export/` snapshots, the new `dep_NNN.log`, and the (already-on-main from sandbox) close-out payload + apply prompt land in one consolidated commit. Per the standing rule, this commit is **NOT pushed** — Doug pushes after review.

```bash
cd ~/Dropbox/Projects/crmbuilder

git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/

git commit -m "$(cat <<'EOF'
v2: SES-087 close-out applied — architecture review; Master CRMBuilder PRD consolidation direction-setting

Applies the SES-087 close-out payload via apply_close_out.py.

Creates:
- SES-087 (session) — architecture review establishing Master CRMBuilder
  PRD consolidation direction, three-category conceptual model, Phase 1
  client-led-intake redesign, glossary v0.2 with five terms
- CONV-057 (conversation, status=complete) wired to WS-011 + SES-087
- 5 commit rows: 09f8f62d (Master CRMBuilder PRD direction +
  transitional headers), cfaec293 (Master CRMBuilder PRD v0.1),
  e9d30e0b (discussion-draft marker), d9337607 (glossary v0.1),
  794d5f41 (glossary v0.2)
- 13 planning items (PI-061..PI-073), all Open, covering V2
  architectural cleanup: glossary V2 migration, cross-engagement
  reference store, Skills/Patterns/Inventories libraries, Skill
  trigger mechanism, cross-ref tooling, specifications README,
  iterative Master PRD drafting, transitional-header retirement,
  client-provided info storage, Engagement Level Setup process,
  Session/Conversation entity redesign (detailed)
- 9 decisions (DEC-288..DEC-296):
  * DEC-288 — Consolidate V1+V2 under single Master CRMBuilder PRD
  * DEC-289 — New specifications/ directory at repo root
  * DEC-290 — MD for internal docs, format-flexible for client deliverables
  * DEC-291 — Master CRMBuilder PRD end-to-end scope
  * DEC-292 — CRMBuilder dogfood first, CBM second, discovery-driven
  * DEC-293 — Three-category conceptual model
  * DEC-294 — Phase 1 as client-led intake
  * DEC-295 — Glossary as canonical store; MD initial, V2 future
  * DEC-296 — Session/Conversation redesign direction (1:N, medium-agnostic)
- 9 decided_in reference rows (one per DEC pointing to SES-087)
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

No work tickets opened or consumed. No existing planning items
addressed or resolved. No new migration applied.

Originally drafted as SES-085 in the sandbox; identifier collided
with the parallel-applied SES-085 (PI-004 manual_config) and
SES-086 (PI-004 test_spec) close-outs from Claude Code. Renumbered
to SES-087 against the post-collision db-export head; content
unchanged.

The apply tees stdout to PRDs/product/crmbuilder-v2/deposit-event-logs/
dep_NNN.log per DEC-164 (git-tracked).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Doug pushes after review.

---

## Done

After commit succeeds, the SES-087 close-out is fully applied:
- 13 new Planning Items queued for future work
- 9 architectural Decisions recorded
- Strategic direction (Master CRMBuilder PRD consolidation) is now governance-recorded, not just present in scattered methodology MD updates

Next steps (out of scope for this apply):
- Resume work on the Master CRMBuilder PRD v0.1 (still DISCUSSION DRAFT) — Phase 1 in particular needs revision per DEC-294's client-led-intake reframe.
- Pick up the highest-priority PI from PI-061..PI-073 for the next working session.
- Consider whether a dedicated workstream for "Master CRMBuilder PRD consolidation" should be created (current workstream assignment WS-011 V2 storage API refinements is provisional).
