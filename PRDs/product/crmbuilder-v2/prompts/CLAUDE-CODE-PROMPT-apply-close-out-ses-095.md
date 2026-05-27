# CLAUDE-CODE-PROMPT — apply close-out SES-095 (PI-073 architectural-design — Session/Conversation redesign + DEC-314 supersedes DEC-013)

**Last Updated:** 05-27-26
**Operating mode:** DETAIL
**Series:** PI-073 Conversation 1 (architectural design) — first of eight conversations per `pi-073-execution-plan.md`
**Slice:** Apply the SES-095 close-out payload to the V2 governance DB + post-apply PATCH to flip DEC-013 to Superseded
**Status:** Ready to execute. Requires live `crmbuilder-v2-api` at 127.0.0.1:8765. No new migration. No prior commit referenced in `commits[]` (this conversation's substantive artifacts — execution plan, two specs, payload, apply prompt — land in the single post-apply commit).

> **Why this session record exists:** Doug asked Claude Code to review PI-073 and create an execution plan; Claude Code produced `pi-073-execution-plan.md` v0.1 (an eight-conversation plan); Doug confirmed PI-073-first sequencing and chose to conduct Conversation 1 inside this Claude Code session rather than spawning sandbox. Claude Code captured identifier heads, presented design recommendations on PI-073's four open design questions and five execution-plan risks, accepted Doug's redirect to fully supersede DEC-013 (not narrow it), and authored DEC-314 + `session-v2.md` + `conversation-v2.md` + this close-out + this apply prompt autonomously per Doug's authorization.
>
> **Identifier-head capture (per DEC-300):** Live next-identifier responses prior to payload assignment: SES-095, CONV-065, DEC-314, PI-090, WT-056. Live list-heads: SES-094 (Cross Domain Service), CONV-064, DEC-313 (DEC-312 occupies a soft-deleted slot from SES-094's discipline retry; DEC-314 is the next live identifier), PI-088, WT-055. No PIs are authored in this close-out; PI-073 already exists and is the addressed planning item.

---

## Net Effect

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_095.json` to the V2 governance DB via the standard apply script, then PATCH DEC-013 to Superseded as a post-apply step. Creates:

- SES-095 (session, status=Complete) — PI-073 architectural-design conversation
- CONV-065 (conversation, status=complete) with two reference edges (`conversation_belongs_to_workstream` → WS-011, `conversation_records_session` → SES-095)
- DEC-314 (the redesign decision) with `supersedes_id` → DEC-013 set at create time and one `decided_in` → SES-095 reference edge
- 8 reference rows total: 1 `decided_in` (DEC-314 → SES-095) + 7 `blocked_by` cascading from PI-085, PI-086, PI-087, PI-088, PI-024, PI-025, PI-026 → PI-073
- 1 `addresses_planning_items` reference row: CONV-065 → PI-073 (addresses, not resolves — PI-073 resolves at Conversation N+1)
- `close_out_payload` COP-NNN + `deposit_event` DEP-NNN (lazy-created)

**Post-apply (manual PATCH outside the script):** PATCH `/decisions/DEC-013` with `status=Superseded` and `superseded_by=DEC-314`. The apply script's `decisions` section creates the new DEC-314 with `supersedes_id` set, but does NOT reach across rows to update DEC-013's mirror fields. This is documented in `crmbuilder-v2/src/crmbuilder_v2/access/repositories/decisions.py` lines 196–269 (create accepts `supersedes` but only writes the new row's FK; the inverse `superseded_by` requires update on the predecessor row separately).

No work_tickets opened or consumed. No new planning_items created. No PIs resolved.

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. Verify the API server is reachable:
   ```bash
   curl -sf http://127.0.0.1:8765/health || echo "API not running"
   ```

3. Confirm the new identifiers do not yet exist:
   ```bash
   echo "Session (expect 404):"
   curl -o /dev/null -s -w "  SES-095 → HTTP %{http_code}\n" http://127.0.0.1:8765/sessions/SES-095

   echo "Conversation (expect 404):"
   curl -o /dev/null -s -w "  CONV-065 → HTTP %{http_code}\n" http://127.0.0.1:8765/conversations/CONV-065

   echo "Decision (expect 404 for DEC-314; expect 200 with status=Active for DEC-013):"
   curl -o /dev/null -s -w "  DEC-314 → HTTP %{http_code}\n" http://127.0.0.1:8765/decisions/DEC-314
   curl -sf http://127.0.0.1:8765/decisions/DEC-013 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-013 →', d['status'])"
   ```

4. Confirm PI-073 + all seven blocked_by sources exist:
   ```bash
   for pi in PI-073 PI-085 PI-086 PI-087 PI-088 PI-024 PI-025 PI-026; do
     curl -o /dev/null -s -w "  $pi → HTTP %{http_code}\n" http://127.0.0.1:8765/planning-items/$pi
   done
   ```

5. Confirm WS-011 still in_flight (this conversation's workstream membership):
   ```bash
   curl -sf http://127.0.0.1:8765/workstreams/WS-011 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['workstream_identifier'], d['workstream_status'])"
   ```

6. Sanity-check the predecessor session SES-094 is present and Complete:
   ```bash
   curl -sf http://127.0.0.1:8765/sessions/SES-094 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  SES-094:', d['status'])"
   ```

7. Confirm no pre-existing blocked_by edges from the seven downstream PIs targeting PI-073 (the close-out is idempotent on existing edges via 409 → skip, but a count check makes the post-apply delta interpretable):
   ```bash
   for pi in PI-085 PI-086 PI-087 PI-088 PI-024 PI-025 PI-026; do
     count=$(curl -sf "http://127.0.0.1:8765/references?source_type=planning_item&source_id=$pi&target_type=planning_item&target_id=PI-073&relationship=blocked_by" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['data']))")
     echo "  $pi → PI-073 blocked_by existing rows: $count"
   done
   ```

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_095.json
```

Expect:

- **1 session row** created (SES-095)
- **1 conversation row** (CONV-065) created with two conversation reference edges
- **0 commit rows** (empty `commits[]` — the post-apply commit captures everything)
- **0 work_tickets**
- **0 planning_items**
- **1 decision row** created (DEC-314) with `supersedes_id` pointing at DEC-013's row id
- **1 `decided_in` reference row** (DEC-314 → SES-095)
- **7 `blocked_by` reference rows** (PI-085, PI-086, PI-087, PI-088, PI-024, PI-025, PI-026 → PI-073)
- **1 `addresses` reference row** from CONV-065 → PI-073 (auto-generated from `addresses_planning_items`)
- **close_out_payload COP-NNN** + **deposit_event DEP-NNN** lazy-created

---

## Post-apply step — flip DEC-013 to Superseded

The apply script sets DEC-314.supersedes_id but does not update DEC-013's mirror fields. Run this PATCH after the apply succeeds:

```bash
curl -X PATCH http://127.0.0.1:8765/decisions/DEC-013 \
  -H "Content-Type: application/json" \
  -d '{"status": "Superseded", "superseded_by": "DEC-314"}' | python3 -m json.tool
```

Expect 200 with `data.status == "Superseded"` and `data.superseded_by_identifier == "DEC-314"`.

**On classifier block:** if the auto-mode classifier blocks the PATCH citing DEC-310, surface the block to Doug and proceed with the asymmetry documented in DEC-314's consequences paragraph (DEC-314 records the supersession; DEC-013's mirror fields stay stale until apply_close_out.py grows cross-row update support). The asymmetry is non-fatal — the supersession relationship is queryable via DEC-314.supersedes_identifier in either case.

---

## Post-apply verification

```bash
echo "SES-095:"
curl -sf http://127.0.0.1:8765/sessions/SES-095 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status'])"

echo "CONV-065:"
curl -sf http://127.0.0.1:8765/conversations/CONV-065 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['conversation_title'][:80]); print('  status:', d['conversation_status'])"

echo "DEC-314:"
curl -sf http://127.0.0.1:8765/decisions/DEC-314 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status']); print('  supersedes:', d['supersedes_identifier'])"

echo "DEC-013 (expect status=Superseded, superseded_by=DEC-314 after the post-apply PATCH):"
curl -sf http://127.0.0.1:8765/decisions/DEC-013 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  status:', d['status']); print('  superseded_by:', d['superseded_by_identifier'])"

echo "decided_in edge (expect 1):"
curl -sf 'http://127.0.0.1:8765/references?relationship=decided_in&target_type=session&target_id=SES-095' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print('  Count:', len(data))
for r in data:
  print(' ', r['source_type']+'/'+r['source_id'], '→', r['target_type']+'/'+r['target_id'])
"

echo "blocked_by edges to PI-073 (expect 7):"
curl -sf 'http://127.0.0.1:8765/references?relationship=blocked_by&target_type=planning_item&target_id=PI-073' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print('  Count:', len(data))
for r in sorted(data, key=lambda r: r['source_id']):
  print(' ', r['source_id'], '→', r['target_id'])
"

echo "addresses edge (expect 1, CONV-065 → PI-073):"
curl -sf 'http://127.0.0.1:8765/references?relationship=addresses&source_type=conversation&source_id=CONV-065' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print('  Count:', len(data))
for r in data:
  print(' ', r['source_type']+'/'+r['source_id'], '→', r['target_type']+'/'+r['target_id'])
"

echo "PI-073 status (expect still Open — resolved at Conversation N+1):"
curl -sf http://127.0.0.1:8765/planning-items/PI-073 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  status:', d['status'])"

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

After apply + post-apply PATCH succeed, regenerated `db-export/` snapshots and the new `dep_NNN.log` land alongside the spec docs + execution plan + payload + apply prompt in one consolidated commit. Per the standing rule, this commit is **NOT pushed** — Doug pushes after review.

```bash
cd ~/Dropbox/Projects/crmbuilder

git add PRDs/product/crmbuilder-v2/pi-073-execution-plan.md \
        PRDs/product/crmbuilder-v2/governance-schema-specs/session-v2.md \
        PRDs/product/crmbuilder-v2/governance-schema-specs/conversation-v2.md \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_095.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-095.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/

git commit -m "$(cat <<'EOF'
v2: SES-095 close-out applied — PI-073 architectural-design conversation (DEC-314 supersedes DEC-013; session-v2 + conversation-v2 specs)

Applies the SES-095 close-out payload via apply_close_out.py.

Creates:
- SES-095 (session) — PI-073 architectural-design conversation
  conducted in Claude Code at Doug's terminal. Resolves PI-073's four
  open design questions; produces the v1.0 schema specs for the
  redesigned session and conversation entities; locks seven blocked_by
  edges so downstream methodology and backfill PIs wait on PI-073's
  resolution.
- CONV-065 (conversation, status=complete) wired to WS-011 + SES-095
- DEC-314 — Redesign session and conversation entities: session as
  medium-agnostic communication container, conversation as topical
  sub-unit within a session. Supersedes DEC-013 in its entirety
  (sessions are no longer append-only — they are schedulable for the
  future and updateable when they occur). Records resolutions to all
  four PI-073 open design questions and the five execution-plan risks.
- 8 reference rows:
  * decided_in (DEC-314 → SES-095)
  * 7 × blocked_by (PI-085, PI-086, PI-087, PI-088, PI-024, PI-025,
    PI-026 → PI-073) — cascading the wait so downstream methodology
    work and backfill PIs are gated on PI-073's resolution at
    Conversation N+1
- 1 addresses edge (CONV-065 → PI-073) — auto-generated from
  addresses_planning_items
- close_out_payload COP-NNN + deposit_event DEP-NNN

Post-apply PATCH flips DEC-013 status=Active → Superseded and sets
DEC-013.superseded_by_identifier = DEC-314 (the apply script's
decisions section sets DEC-314.supersedes_id but does not reach
across rows to update DEC-013's mirror fields; the inverse is
handled by the manual PATCH documented in the apply prompt).

Substantive artifacts produced in this conversation:
- pi-073-execution-plan.md v0.1 — eight-conversation execution plan
  (1 design + 1 build planning + 6 build/audit slices) with cross-PI
  sequencing analysis
- governance-schema-specs/session-v2.md v1.0 — redesigned session
  entity (medium-agnostic; universal columns + JSON medium-specific
  metadata; five-status lifecycle with optional session_follows_from
  for medium-driven sequencing)
- governance-schema-specs/conversation-v2.md v1.0 — redesigned
  conversation entity (topical sub-unit; new CNV-NNN identifier
  prefix; six-status lifecycle including not_started terminal for
  Q2-resolution; cross-session linkage via conversation_follows_from
  and conversation_relates_to)

PI-073 itself is NOT resolved by this close-out — it resolves at
Conversation N+1 (audit + documentation propagation) per the
execution plan §3.

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
- DEC-314 is governance-recorded and supersedes DEC-013
- The eight-conversation PI-073 workstream has its first conversation closed
- session-v2.md and conversation-v2.md are the authoritative input for Conversation 2 (build planning)
- Seven downstream PIs are blocked_by PI-073 via reference edges
- PI-073 status remains Open — it resolves at Conversation N+1 (the final audit + documentation-propagation conversation per the execution plan)

Next steps (out of scope for this apply):
- Conversation 2 — build planning. Authored in Claude.ai sandbox (recommended) or here. Output: `pi-073-workstream-plan.md` + per-slice kickoff stubs.
- Open items deferred from this conversation to Conversation 2: commits-table FK migration (commit_conversation_id → commit_session_id rename + migrate vs convert to reference edge); per-medium JSON validation strictness; indexed JSON paths; session_scheduled_for timezone handling; auto-flip planned → not_started on session close; conversation_summary required on complete; whether to ship a dedicated PI-073 workstream or keep work under WS-011.
