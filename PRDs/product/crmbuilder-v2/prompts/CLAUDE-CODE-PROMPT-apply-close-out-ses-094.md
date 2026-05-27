# CLAUDE-CODE-PROMPT — apply close-out SES-094 (Cross Domain Service object — DEC-313 + PI-089, discipline retry)

**Last Updated:** 05-26-26
**Operating mode:** DETAIL
**Series:** Standalone governance session
**Slice:** Apply the SES-094 close-out payload to the V2 governance DB
**Status:** Ready to execute. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765. No new migration. No prior commit referenced in `commits[]` (governance-only session). Payload is one DEC + one PI + two references.

> **Why this session record exists:** Doug asked Claude Code to author a decision (V2 lacks a Cross Domain Service object) and a Planning Item (add one). Claude Code first attempted via direct REST POSTs and created orphan records DEC-312 + PI-089 before the auto-mode classifier blocked the reference-edge POST citing DEC-310's discipline. Doug chose to back out the orphans and redo properly. PI-089 was hard-deleted (HTTP 200, row removed); DEC-312 was soft-deleted (HTTP 200, status flipped to 'Deleted', row retained). This payload re-authors the same substantive content as DEC-313 (skipping the soft-deleted DEC-312 slot) and PI-089 (identifier now reusable) via the canonical session/close-out flow.
>
> **Identifier-head capture:** Live API next-identifier helper responses prior to payload authoring: SES-094, CONV-064, DEC-313, PI-089. The list-endpoint heads (which exclude soft-deleted rows) showed DEC-311 — the discrepancy between list-head DEC-311 and next-identifier DEC-313 is a correct outcome of the soft-deleted DEC-312 row occupying its sequence slot. The PI list-head reverted to PI-088 cleanly after the hard-delete, so PI-089 is reusable.

---

## Net Effect

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_094.json` to the V2 governance DB via the standard apply script. Creates:

- SES-094 (session, discipline-correction Cross Domain Service authoring)
- CONV-064 (conversation, status=complete) with two reference edges (`conversation_belongs_to_workstream` → WS-011, `conversation_records_session` → SES-094)
- DEC-313 (V2 needs a Cross Domain Service object; authorize a PI to add it)
- PI-089 (implementation scope for the Cross Domain Service entity addition)
- 2 reference rows: `decided_in` (DEC-313 → SES-094) and `addresses` (PI-089 → DEC-313)
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

No work tickets are opened or consumed. No existing planning items are addressed or resolved. No commits in `commits[]` (governance-only session — the payload + apply prompt are the only artifacts and don't include themselves recursively). The soft-deleted DEC-312 row is left in place as a permanent deletion trail.

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. Verify the API server is reachable:
   ```bash
   curl -sf http://127.0.0.1:8765/health || echo "API not running"
   ```

3. Confirm the new identifiers do not yet exist (note: DEC-313 is the live one; DEC-312 is the soft-deleted orphan from the direct-POST attempt and should still be reachable as Deleted):
   ```bash
   echo "Session (expect 404):"
   curl -o /dev/null -s -w "  SES-094 → HTTP %{http_code}\n" http://127.0.0.1:8765/sessions/SES-094

   echo "Conversation (expect 404):"
   curl -o /dev/null -s -w "  CONV-064 → HTTP %{http_code}\n" http://127.0.0.1:8765/conversations/CONV-064

   echo "Decision (expect 404 for DEC-313; expect 200 with status=Deleted for DEC-312):"
   curl -o /dev/null -s -w "  DEC-313 → HTTP %{http_code}\n" http://127.0.0.1:8765/decisions/DEC-313
   curl -sf http://127.0.0.1:8765/decisions/DEC-312 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-312 →', d['status'])"

   echo "Planning item (expect 404):"
   curl -o /dev/null -s -w "  PI-089 → HTTP %{http_code}\n" http://127.0.0.1:8765/planning-items/PI-089
   ```

4. Confirm WS-011 still in_flight (this conversation's workstream membership):
   ```bash
   curl -sf http://127.0.0.1:8765/workstreams/WS-011 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['workstream_identifier'], d['workstream_status'], '|', d['workstream_name'])"
   ```

5. Sanity-check the predecessor session SES-093 is present and Complete:
   ```bash
   curl -sf http://127.0.0.1:8765/sessions/SES-093 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  SES-093:', d['status'], '|', d['title'][:75])"
   ```

---

## Apply

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_094.json
```

Expect:

- **1 session row** created (SES-094)
- **1 conversation row** (CONV-064) created with two conversation reference edges
- **0 commit rows** (empty `commits[]`)
- **0 work_tickets**
- **1 planning_item** created (PI-089, status=Open, item_type=pending_work)
- **1 decision row** created (DEC-313) with one `decided_in` → SES-094 edge
- **1 `addresses` reference row** (PI-089 → DEC-313)
- **close_out_payload COP-NNN** lazy-created
- **deposit_event DEP-NNN** recorded with `outcome=success`

---

## Post-apply verification

```bash
echo "SES-094:"
curl -sf http://127.0.0.1:8765/sessions/SES-094 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status'])"

echo "CONV-064:"
curl -sf http://127.0.0.1:8765/conversations/CONV-064 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['conversation_title'][:80]); print('  status:', d['conversation_status'])"

echo "DEC-313:"
curl -sf http://127.0.0.1:8765/decisions/DEC-313 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status'])"

echo "PI-089:"
curl -sf http://127.0.0.1:8765/planning-items/PI-089 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80]); print('  status:', d['status']); print('  item_type:', d['item_type'])"

echo "decided_in edge (expect 1):"
curl -sf 'http://127.0.0.1:8765/references?relationship_kind=decided_in&target_type=session&target_id=SES-094' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print('  Count:', len(data))
for r in data:
  print(' ', r['source_type']+'/'+r['source_id'], '→', r['target_type']+'/'+r['target_id'])
"

echo "addresses edge (expect 1, PI-089 → DEC-313):"
curl -sf 'http://127.0.0.1:8765/references?relationship_kind=addresses&source_type=planning_item&source_id=PI-089' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
print('  Count:', len(data))
for r in data:
  print(' ', r['source_type']+'/'+r['source_id'], '→', r['target_type']+'/'+r['target_id'])
"

echo "DEC-312 (orphan, should still be status=Deleted):"
curl -sf http://127.0.0.1:8765/decisions/DEC-312 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-312 →', d['status'])"

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

git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_094.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-094.md \
        PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/

git commit -m "$(cat <<'EOF'
v2: SES-094 close-out applied — Cross Domain Service object (DEC-313 + PI-089, discipline retry)

Applies the SES-094 close-out payload via apply_close_out.py.

Creates:
- SES-094 (session) — discipline-correction governance authoring. Doug
  asked Claude Code to author a DEC + PI for adding a Cross Domain
  Service object to V2; Claude Code first attempted via direct REST
  POSTs and created orphan DEC-312 + PI-089 before the auto-mode
  classifier blocked the reference-edge POST citing DEC-310. Doug
  chose option 1 (back out and redo properly). PI-089 hard-deleted,
  DEC-312 soft-deleted. This session re-authors the same content via
  the canonical close-out flow.
- CONV-064 (conversation, status=complete) wired to WS-011 + SES-094
- DEC-313 — V2 needs a Cross Domain Service object; authorize a
  Planning Item to add one. Scope of work for the PI is migration,
  access layer, REST endpoints, desktop panel, edge-rule semantics,
  reference vocabulary updates. Cross Domain Services are a key
  methodology artifact per Phase 6 of the document production
  process. (DEC-312 occupies the soft-deleted slot.)
- PI-089 — Add a Cross Domain Service entity to V2 (Alembic
  migration with CDS-NNN identifier prefix, access-layer module,
  REST endpoints under the {data, meta, errors} envelope, desktop
  panel, reference relationship vocabulary updates, db-export
  emitter, tests). Addresses DEC-313.
- 2 reference rows:
  * decided_in (DEC-313 → SES-094)
  * addresses (PI-089 → DEC-313)
- close_out_payload COP-NNN + deposit_event DEP-NNN

No work tickets opened or consumed. No existing planning items
addressed or resolved. No commits in commits[] (governance-only
session). The soft-deleted DEC-312 row is left in place as a
permanent deletion trail of the original direct-POST attempt.

First worked example of the option-1 back-out-and-retry path for a
DEC-310 discipline violation — documents the cleanup pattern (DEC
soft-delete, PI hard-delete, next-identifier helper handles the
soft-delete slot correctly) for future occurrences.

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
- DEC-313 and PI-089 are governance-recorded
- The orphan DEC-312 (status=Deleted) remains as a permanent deletion trail
- The Cross Domain Service object is queued as PI-089 ready for implementation
- The option-1 cleanup pattern (delete orphans, re-author via close-out) is documented as a worked example for future DEC-310 violations

Next steps (out of scope for this apply):
- Schedule PI-089 implementation (probably a Claude Code work session against the crmbuilder-v2 codebase — Alembic migration + access layer + API + panel + vocab + tests, sliced if needed)
- Consider the deferred items surfaced in SES-094: DEC soft-delete vs PI hard-delete asymmetry; whether list endpoints should expose soft-deleted rows; whether a hard-delete capability for cleanup is warranted; identifier-sequence behavior consistency (soft-delete consumes slot, hard-delete releases slot). These are foundational consistency questions worthy of their own DECs and PIs.
