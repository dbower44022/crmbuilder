# CLAUDE-CODE-PROMPT — apply close-out SES-089 (architecture review — Master CRMBuilder PRD consolidation direction-setting)

**Last Updated:** 05-26-26
**Operating mode:** DETAIL
**Series:** Strategic-direction architecture review (standalone, not part of a build cohort)
**Slice:** Apply the SES-089 close-out payload to the V2 governance DB
**Status:** Ready to execute. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765. No new migration; pure governance content (session + conversation + planning items + decisions + references). The five session content commits (CLAUDE.md direction-setting, Master CRMBuilder PRD v0.1, discussion-draft marker, glossary v0.1, glossary v0.2) are already on origin/main from earlier in this conversation.

> **Why SES-089 and not SES-085 or SES-087:** the sandbox went through two rounds of identifier-collision recovery while authoring this close-out:
> - **Round 1.** Originally authored as SES-085 + CONV-055 + DEC-279..287 against origin/main's static db-export head (SES-084). Push collided on `ses_085.json` because Claude Code had locally applied SES-085 (PI-004 manual_config) and SES-086 (PI-004 test_spec) without pushing. Doug resolved with `--ours` keeping those as canonical SES-085/SES-086; sandbox renumbered to SES-087 + CONV-057 + DEC-288..296 (commit `3c0ccbff`).
> - **Round 2.** During amendment authoring (to fold the recovery work into the same session and add the identifier-capture protocol decision), origin advanced with two more locally-applied close-outs: SES-087 (PI-052 Slice A terminal proof-of-concept) and SES-088 (PI-005 process v2 schema growth closure), consuming the just-renumbered slots and DEC-288/289/290. Doug provided fresh heads from his live V2 API (SES-088, CONV-058, DEC-290, PI-060, WT-054); sandbox renumbered a second time to final identifiers SES-089 + CONV-059 + DEC-291..DEC-300.
>
> Planning items PI-061..PI-073 were not consumed by any of the parallel applies and remain valid in the original numbering. The zombie `ses_087.json` and `CLAUDE-CODE-PROMPT-apply-close-out-ses-087.md` files are deleted by this same commit and must not be applied. The identifier-capture protocol established by DEC-300 (and reinforced by the second collision) requires asking Doug for fresh heads at the start of close-out authoring AND before any mid-conversation amendment that touches identifier slots.

---

## Net Effect

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_089.json` to the V2 governance DB via the standard apply script. Creates SES-089 + CONV-059 + 13 planning items (PI-061..PI-073) + 10 decisions (DEC-291..DEC-300) + 10 `decided_in` reference edges + 5 commit rows + the standard conversation reference edges (`conversation_belongs_to_workstream` → WS-011, `conversation_records_session` → SES-089) + lazy-creates the close_out_payload (COP-NNN) and deposit_event (DEP-NNN), tee'ing the apply log to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`.

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
   # Top commit should be the one that adds ses_089.json + SES-089 apply prompt and deletes the zombie SES-087 files.
   ```

4. Confirm the zombie SES-087 files are gone from the working tree:
   ```bash
   ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_087.json 2>/dev/null && echo "ERROR: zombie SES-087 payload still present" || echo "OK: zombie ses_087.json removed"
   ls PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-087.md 2>/dev/null && echo "ERROR: zombie SES-087 apply prompt still present" || echo "OK: zombie SES-087 apply prompt removed"
   ```

5. Confirm the new identifiers do not yet exist (no parallel-apply collision — round three would not be fun):
   ```bash
   echo "Sessions (expect 404):"
   curl -o /dev/null -s -w "  SES-089 → HTTP %{http_code}\n" http://127.0.0.1:8765/sessions/SES-089

   echo "Conversations (expect 404):"
   curl -o /dev/null -s -w "  CONV-059 → HTTP %{http_code}\n" http://127.0.0.1:8765/conversations/CONV-059

   echo "Decisions (expect 404 for all):"
   for n in 291 292 293 294 295 296 297 298 299 300; do
     curl -o /dev/null -s -w "  DEC-$n → HTTP %{http_code}\n" http://127.0.0.1:8765/decisions/DEC-$n
   done

   echo "Planning items (expect 404 for all):"
   for n in 061 062 063 064 065 066 067 068 069 070 071 072 073; do
     curl -o /dev/null -s -w "  PI-$n → HTTP %{http_code}\n" http://127.0.0.1:8765/planning-items/PI-$n
   done
   ```

6. Sanity-check the prior-applied PI-004 / PI-052 / PI-005 close-out sessions are all present and `Complete`:
   ```bash
   for n in 085 086 087 088; do
     curl -sf http://127.0.0.1:8765/sessions/SES-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  SES-$n:', d['status'], '|', d['title'][:75])"
   done
   ```

7. Confirm WS-011 (V2 storage API refinements) is present and in_flight (this conversation's workstream membership):
   ```bash
   curl -sf http://127.0.0.1:8765/workstreams/WS-011 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['workstream_identifier'], d['workstream_status'], '|', d['workstream_name'])"
   # Expect: WS-011 in_flight | V2 storage API refinements
   ```

---

## Apply

Run the apply script. The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` automatically:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_089.json
```

Expect:

- **1 session row** created (SES-089)
- **1 conversation row** (CONV-059) created with two reference edges (`conversation_belongs_to_workstream` → WS-011, `conversation_records_session` → SES-089)
- **5 commit rows** created (09f8f62d, cfaec293, e9d30e0b, d9337607, 794d5f41)
- **0 work_tickets** (no WT opened or consumed by this conversation — strategic-direction work without a build-prompt deliverable)
- **13 planning_items** created (PI-061..PI-073), all status=Open, all item_type=pending_work
- **10 decision rows** created (DEC-291..DEC-300) with `decided_in` → SES-089 edges
- **0 `is_about` payload reference rows** (no is_about edges in the payload)
- **0 `addresses` reference rows** (no addresses_planning_items entries)
- **0 `resolves` rows** (no resolves_planning_items entries)
- **close_out_payload COP-NNN** lazy-created
- **deposit_event DEP-NNN** recorded with `outcome=success` plus `wrote_record` back-edges to every record the apply POSTed

---

## Post-apply verification

```bash
echo "SES-089:"
curl -sf http://127.0.0.1:8765/sessions/SES-089 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status'])"

echo "CONV-059:"
curl -sf http://127.0.0.1:8765/conversations/CONV-059 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['conversation_title'][:80]); print('  status:', d['conversation_status'])"

echo "DEC-291..300:"
for n in 291 292 293 294 295 296 297 298 299 300; do
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

echo "decided_in edges (expect 10 — one per DEC pointing to SES-089):"
curl -sf 'http://127.0.0.1:8765/references?relationship_kind=decided_in&target_type=session&target_id=SES-089' | python3 -c "
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

After the apply succeeds, the regenerated `db-export/` snapshots and the new `dep_NNN.log` land in one consolidated commit. Per the standing rule, this commit is **NOT pushed** — Doug pushes after review.

```bash
cd ~/Dropbox/Projects/crmbuilder

git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/

git commit -m "$(cat <<'EOF'
v2: SES-089 close-out applied — architecture review; Master CRMBuilder PRD consolidation direction-setting

Applies the SES-089 close-out payload via apply_close_out.py.

Creates:
- SES-089 (session) — architecture review establishing Master CRMBuilder
  PRD consolidation direction, three-category conceptual model, Phase 1
  client-led-intake redesign, glossary v0.2 with five terms
- CONV-059 (conversation, status=complete) wired to WS-011 + SES-089
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
- 10 decisions (DEC-291..DEC-300):
  * DEC-291 — Consolidate V1+V2 under single Master CRMBuilder PRD
  * DEC-292 — New specifications/ directory at repo root
  * DEC-293 — MD for internal docs, format-flexible for client deliverables
  * DEC-294 — Master CRMBuilder PRD end-to-end scope
  * DEC-295 — CRMBuilder dogfood first, CBM second, discovery-driven
  * DEC-296 — Three-category conceptual model
  * DEC-297 — Phase 1 as client-led intake
  * DEC-298 — Glossary as canonical store; MD initial, V2 future
  * DEC-299 — Session/Conversation redesign direction (1:N, medium-agnostic)
  * DEC-300 — Sandbox close-out identifier-capture protocol (surfaced
    by two rounds of mid-session collision recovery: SES-085→SES-087
    after PI-004 cohort applies; SES-087→SES-089 after PI-052 Slice A
    + PI-005 process v2 schema growth applies during amendment)
- 10 decided_in reference rows (one per DEC pointing to SES-089)
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

No work tickets opened or consumed. No existing planning items
addressed or resolved. No new migration applied.

The apply tees stdout to PRDs/product/crmbuilder-v2/deposit-event-logs/
dep_NNN.log per DEC-164 (git-tracked).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Doug pushes after review.

---

## Done

After commit succeeds, the SES-089 close-out is fully applied:
- 13 new Planning Items queued for future work
- 10 architectural Decisions recorded
- Strategic direction (Master CRMBuilder PRD consolidation) is now governance-recorded, not just present in scattered methodology MD updates
- Identifier-capture protocol (DEC-300) is in force going forward

Next steps (out of scope for this apply):
- Resume work on the Master CRMBuilder PRD v0.1 (still DISCUSSION DRAFT) — Phase 1 in particular needs revision per DEC-297's client-led-intake reframe.
- Pick up the highest-priority PI from PI-061..PI-073 for the next working session.
- Consider whether a dedicated workstream for "Master CRMBuilder PRD consolidation" should be created (current workstream assignment WS-011 V2 storage API refinements is provisional).
