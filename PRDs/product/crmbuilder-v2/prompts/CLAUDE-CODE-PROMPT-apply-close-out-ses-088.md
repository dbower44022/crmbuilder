# CLAUDE-CODE-PROMPT — apply close-out SES-088 (PI-005 — process v2 schema growth)

**Last Updated:** 2026-05-26
**Operating mode:** DETAIL
**Series:** PI-005 satisfier (final of the PI-003/004/005 design-phase trio)
**Slice:** Apply the SES-088 close-out payload to the V2 governance DB
**Status:** Ready to execute. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765, migration 0018 already applied (the build session applied it before authoring this prompt), the `process v2 schema growth` build commit `2bd7428` already landed on `main`.

---

## Purpose

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_088.json` to the V2 governance DB via the standard apply script. Creates SES-088 + CONV-058 + DEC-288/289/290 + commit record for `2bd7428` + the `decided_in` edges + lazy-creates the close_out_payload (COP-NNN) and deposit_event (DEP-NNN), tees the apply log to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`. The single `resolves_planning_items` entry atomically flips PI-005 from `Open` to `Resolved` via slice A's edge+flip behavior.

**This apply resolves PI-005 — the final planning item in the PI-003/004/005 design-phase trio.**

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. Verify the API server is reachable and at head `0018`:
   ```bash
   curl -sf http://127.0.0.1:8765/ | python3 -c "import sys,json; d=json.load(sys.stdin); print('api:', d['name'], d['version'])"
   curl -sf http://127.0.0.1:8765/admin/version 2>/dev/null \
     | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('engagement head:', d.get('engagement_schema',{}).get('current','?'), '/', d.get('engagement_schema',{}).get('head','?'))" \
     || echo "(admin/version not exposed — fall back to direct DB inspection)"
   ```

3. Confirm the new identifiers do not yet exist (no parallel-apply collision):
   ```bash
   for id in SES-088 CONV-058 DEC-288 DEC-289 DEC-290; do
     case "$id" in
       SES-*) route="sessions" ;;
       CONV-*) route="conversations" ;;
       DEC-*) route="decisions" ;;
     esac
     code=$(curl -o /dev/null -s -w "%{http_code}" "http://127.0.0.1:8765/${route}/${id}")
     printf '  %s -> HTTP %s\n' "$id" "$code"
   done
   # Expect: 404 for all five
   ```

4. Confirm WT-054 is still `ready` (consumed via the `conversation_opens_against_work_ticket` edge in this apply per the SES-082..086 precedent; manual PATCH if you want it consumed):
   ```bash
   curl -sf http://127.0.0.1:8765/work-tickets/WT-054 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['work_ticket_status'])"
   # Expect: ready
   ```

5. Confirm PI-005 is still `Open` (will flip to `Resolved` atomically on apply):
   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-005 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['identifier'], d['status'])"
   # Expect: PI-005 Open
   ```

6. Confirm the build commit `2bd7428` is on the current branch:
   ```bash
   git log --oneline 2bd7428 -1
   # Expect: 2bd7428 v2: PI-005 - process v2 schema growth (six TEXT columns + three vocab kinds + UI)
   ```

7. Confirm the migration 0018 has landed in the engagement DB and the `processes` table carries the six new columns:
   ```bash
   curl -sf 'http://127.0.0.1:8765/processes/PROC-001' \
     | python3 -c "
   import sys, json
   d = json.load(sys.stdin)['data']
   missing = [f for f in ('process_steps','process_triggers','process_outcomes','process_edge_cases','process_frequency','process_duration_estimate') if f not in d]
   print('  v0.8 fields present:', not missing)
   if missing: print('  missing:', missing)
   "
   # Expect: 'v0.8 fields present: True'
   ```

---

## Apply

Run the apply script. The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` automatically:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_088.json
```

Expect:

- **1 session row** created (SES-088)
- **1 conversation row** (CONV-058) created with three reference edges (`conversation_belongs_to_workstream` -> WS-003, `conversation_records_session` -> SES-088, `conversation_opens_against_work_ticket` -> WT-054)
- **1 commit row** (CM-NNNN) created for `2bd7428` with `commit_conversation_id = CONV-058`
- **0 work_tickets** (WT-054 was authored in SES-081's apply chain; this apply does not transition it; consumes-via-edge is the documented pattern and prior sibling applies left WT-049/WT-050/WT-051/WT-052/WT-053 also `ready` — manual PATCH if desired)
- **0 planning_items** (no new PIs surfaced by this build)
- **3 decision rows** created (DEC-288, DEC-289, DEC-290) with `decided_in` -> SES-088 edges
- **0 references** (the payload's `references` section is empty)
- **1 `resolves` reference row** (CONV-058 -> PI-005 per `resolves_planning_items`) — **PI-005 status atomically flips Open -> Resolved in the same transaction** (slice A of PI-030)
- **0 `addresses` reference rows** (the payload's `addresses_planning_items` section is empty)
- **close_out_payload COP-NNN** lazy-created
- **deposit_event DEP-NNN** recorded with `outcome=success` plus `wrote_record` back-edges to every record the apply POSTed

---

## Post-apply verification

```bash
echo "SES-088:"
curl -sf http://127.0.0.1:8765/sessions/SES-088 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80])"

echo "CONV-058:"
curl -sf http://127.0.0.1:8765/conversations/CONV-058 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  status:', d['conversation_status'])"

echo "DEC-288..290:"
for n in 288 289 290; do
  curl -sf http://127.0.0.1:8765/decisions/DEC-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-$n:', d['title'][:70])"
done

echo "PI-005 status (expect Resolved):"
curl -sf http://127.0.0.1:8765/planning-items/PI-005 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['identifier'], d['status'])"

echo "PI-003/PI-004/PI-005 all resolved? (expect 3 Resolved):"
for pi in PI-003 PI-004 PI-005; do
  curl -sf http://127.0.0.1:8765/planning-items/$pi | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['identifier'], d['status'])"
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

echo "Commit row for 2bd7428:"
curl -sf 'http://127.0.0.1:8765/commits' | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
match = [c for c in data if str(c.get('commit_sha','')).startswith('2bd7428')]
if match:
    c = match[0]
    print(' ', c.get('commit_identifier'), '/', c.get('commit_sha'), '/', c.get('commit_conversation_id'))
else:
    print('  (no match)')
"
```

---

## Commit the apply outputs

After the apply succeeds, the regenerated `db-export/` snapshots, the new `dep_NNN.log`, and the (already-created at build time) close-out payload + apply prompt land in one consolidated commit:

```bash
cd ~/Dropbox/Projects/crmbuilder

git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/ \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_088.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-088.md

git commit -m "$(cat <<'EOF'
v2: SES-088 close-out applied — PI-005 RESOLVED (process v2 schema growth shipped)

Applies the SES-088 close-out payload via apply_close_out.py.

Creates:
- SES-088 (session) — PI-005 satisfier; process v2 schema growth, end-to-end
- CONV-058 (conversation, status=complete) wired to WS-003 + SES-088 + WT-054
- Commit row CM-NNNN for the build commit 2bd7428 (PI-005 build) wired
  to CONV-058 via commit_conversation_id
- DEC-288 — six plain-TEXT Phase 3 content columns; structured shapes
  deferred to v0.7+ pending CBM-redo signal
- DEC-289 — three new outbound vocabulary kinds
  (process_performed_by_persona, process_touches_field,
  process_touches_entity); process_touches_entity promoted from
  v0.4-anticipated to live registration
- DEC-290 — UI surface growth — Edit dialog includes Phase 3 editors,
  Create dialog excludes them (per spec §3.6.4); bundled-widget
  refactor declined for v0.8
- 0 payload references (the references section is empty)
- 1 resolves reference (CONV-058 -> PI-005) — atomic edge+flip
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

PI-005 atomically flips Open -> Resolved via slice A's edge+flip.

After this apply: PI-003 (persona), PI-004 (the four-sibling cohort:
field, requirement, manual_config, test_spec), and PI-005 (process v2
schema growth) are all Resolved — the three-PI design-phase trio is
complete.

The apply tees stdout to PRDs/product/crmbuilder-v2/deposit-event-logs/
dep_NNN.log per DEC-164 (git-tracked).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Doug pushes after review.
