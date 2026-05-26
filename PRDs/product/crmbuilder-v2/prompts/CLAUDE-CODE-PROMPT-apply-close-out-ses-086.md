# CLAUDE-CODE-PROMPT — apply close-out SES-086 (PI-004 cohort closer — test_spec build; **RESOLVES PI-004**)

**Last Updated:** 2026-05-26
**Operating mode:** DETAIL
**Series:** PI-004 cohort closer (fourth and final sibling)
**Slice:** Apply the SES-086 close-out payload to the V2 governance DB
**Status:** Ready to execute. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765, migration 0017 already applied (the build session applied it before authoring this prompt), the `test_spec` build commits already landed on main (commits `ae8a237` migration+access+REST and `83d4649` UI panel+dialogs+sidebar).

---

## Purpose

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_086.json` to the V2 governance DB via the standard apply script. Creates SES-086 + CONV-056 + DEC-284..287 + the `addresses` + **`resolves`** + `decided_in` + `is_about` edges + lazy-creates the close_out_payload (COP-NNN) and deposit_event (DEP-NNN), tee'ing the apply log to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`.

**Key apply-time effect:** the `resolves_planning_items` section's atomic edge+flip (PI-030 slice A) flips **PI-004 status Open → Resolved** in the same transaction as the `resolves` reference row is inserted. The `addresses_planning_items` section additionally records the standard cohort-umbrella edge from CONV-056 → PI-004.

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.
2. Verify the API server is reachable and at the new head:
   ```bash
   curl -sf http://127.0.0.1:8765/health || echo "API not running"
   curl -sf http://127.0.0.1:8765/admin/version | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('engagement head:', d['engagement_schema']['current'], '/', d['engagement_schema']['head'])"
   # Expect both at 0017_v0_5_create_test_specs_table
   ```

3. Confirm the new identifiers do not yet exist (no parallel-apply collision):
   ```bash
   for id in SES-086 CONV-056 DEC-284 DEC-285 DEC-286 DEC-287; do
     case "$id" in
       SES-*) route="sessions" ;;
       CONV-*) route="conversations" ;;
       DEC-*) route="decisions" ;;
     esac
     code=$(curl -o /dev/null -s -w "%{http_code}" "http://127.0.0.1:8765/${route}/${id}")
     printf '  %s → HTTP %s\n' "$id" "$code"
   done
   # Expect: 404 for all six
   ```

4. Confirm WT-053 is still `ready` (consumed via the `conversation_opens_against_work_ticket` edge in this apply per the SES-082/SES-083/SES-084/SES-085 precedent; manual PATCH if you want it consumed):
   ```bash
   curl -sf http://127.0.0.1:8765/work-tickets/WT-053 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['work_ticket_status'])"
   # Expect: ready
   ```

5. Confirm PI-004 is still `Open` (the apply will flip it to Resolved):
   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-004 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['identifier'], d['status'])"
   # Expect: PI-004 Open
   ```

6. Confirm PI-004 has the expected 3-prior-sibling addressing-edge baseline (4 conversations + 4 work_tickets = 8, with three sibling-build conversations + one design conversation):
   ```bash
   curl -sf 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=addresses' \
     | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(' ', len(d), 'pre-apply addresses-edges on PI-004')"
   # Expect: 8 (will become 9 after this apply — the addresses_planning_items section adds CONV-056 → PI-004)
   ```

7. Confirm TST-001 smoke artifact left from the build verification is soft-deleted (cleanup confirmed by the build session):
   ```bash
   curl -sf 'http://127.0.0.1:8765/test-specs?include_deleted=true' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' test_specs live:', sum(1 for r in d if r.get('test_spec_deleted_at') is None), 'soft-deleted:', sum(1 for r in d if r.get('test_spec_deleted_at') is not None))"
   # Expect: 0 live, 1 soft-deleted (TST-001)
   ```

8. Confirm `test_specs` table is present and the `/test-specs` endpoint reachable:
   ```bash
   curl -sf http://127.0.0.1:8765/test-specs | python3 -c "import sys,json; d=json.load(sys.stdin); print(' test-specs endpoint reachable, returns', len(d['data']), 'live records')"
   ```

---

## Apply

Run the apply script. The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` automatically:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_086.json
```

Expect:

- **1 session row** created (SES-086)
- **1 conversation row** (CONV-056) created with three reference edges (`conversation_belongs_to_workstream` → WS-003, `conversation_records_session` → SES-086, `conversation_opens_against_work_ticket` → WT-053)
- **0 work_tickets** (WT-053 was authored in SES-081's apply chain; this apply does not transition it; consumes-via-edge is the documented pattern and prior sibling applies left WT-049..052 also `ready` — manual PATCH `?work_ticket_status=consumed` if desired)
- **0 planning_items** (no new PIs surfaced by this build)
- **0 commits** (the build commits `ae8a237` and `83d4649` land on main separately; commits section left empty here per the SES-082/SES-083/SES-084/SES-085 precedent)
- **4 decision rows** created (DEC-284..287) with `decided_in` → SES-086 edges
- **3 `is_about` payload reference rows** (SES-086 → PI-004 / SES-086 → SES-081 / SES-086 → WT-053)
- **1 `addresses` reference row** (CONV-056 → PI-004 per `addresses_planning_items`) — standard cohort-umbrella edge
- **1 `resolves` reference row** (SES-086 → PI-004 per `resolves_planning_items`) — the slice A atomic edge+flip flips PI-004 status `Open` → `Resolved` in the same transaction as the edge row insert
- **close_out_payload COP-NNN** lazy-created
- **deposit_event DEP-NNN** recorded with `outcome=success` plus `wrote_record` back-edges to every record the apply POSTed

---

## Post-apply verification

```bash
echo "SES-086:"
curl -sf http://127.0.0.1:8765/sessions/SES-086 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80])"

echo "CONV-056:"
curl -sf http://127.0.0.1:8765/conversations/CONV-056 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  status:', d['conversation_status'])"

echo "DEC-284..287:"
for n in 284 285 286 287; do
  curl -sf http://127.0.0.1:8765/decisions/DEC-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-$n:', d['title'][:80])"
done

echo "PI-004 status (expect Resolved — atomic edge+flip):"
curl -sf http://127.0.0.1:8765/planning-items/PI-004 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['identifier'], d['status'])"

echo "PI-004 resolves-edge count after apply (expect 1):"
curl -sf 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=resolves' \
  | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(' ', len(d), 'edges')"

echo "PI-004 addresses-edge count after apply (expect 9 — was 8, +1 from CONV-056):"
curl -sf 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=addresses' \
  | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(' ', len(d), 'edges')"

echo "PI-005 status (expect Open — not touched):"
curl -sf http://127.0.0.1:8765/planning-items/PI-005 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['identifier'], d['status'])"

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

After the apply succeeds, the regenerated `db-export/` snapshots, the new `dep_NNN.log`, and the (already-created at build time) close-out payload + apply prompt land in one consolidated commit:

```bash
cd ~/Dropbox/Projects/crmbuilder

git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/ \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_086.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-086.md

git commit -m "$(cat <<'EOF'
v2: SES-086 close-out applied — PI-004 cohort closer (test_spec shipped, PI-004 RESOLVED)

Applies the SES-086 close-out payload via apply_close_out.py. **PI-004
resolves on this apply** — slice A's atomic edge+flip behaviour flips
PI-004 status Open → Resolved in the same transaction as the
SES-086 → PI-004 `resolves` reference row is inserted.

Creates:
- SES-086 (session) — PI-004 cohort closer `test_spec` build, end-to-end
- CONV-056 (conversation, status=complete) wired to WS-003 + SES-086 + WT-053
- DEC-284..287 (four decisions) per test_spec.md §3.9.1:
  * DEC-284 — TST prefix and format
  * DEC-285 — field inventory, dual-axis state, three plain-text body
    fields, v0.5+ minimum-viable scope
  * DEC-286 — dual-axis state: methodology lifecycle (restricted) and
    execution outcome (unrestricted) on the same row, with §3.4.4
    cross-field invariant on last_run_at — the first v2 entity to ship
    with two independent enum axes; spec frames it as a v0.5+
    convention candidate for any future verification-like entity
  * DEC-287 — API surface (ships POST /test-specs/{id}/record-run
    convenience endpoint per §3.8.1; resolves the open question in the
    affirmative for v0.5+), three outbound references, five-column
    master with color-cued Last Run, three-section detail pane,
    sidebar mid-Methodology position
- 3 is_about payload reference rows (SES-086 → PI-004 / SES-081 / WT-053)
- 1 addresses reference (CONV-056 → PI-004 — standard cohort-umbrella edge)
- 1 resolves reference (SES-086 → PI-004 — slice A atomic edge+flip;
  flips PI-004 status Open → Resolved)
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

PI-004 is now RESOLVED. The v0.5+ methodology entity tranche for
field / requirement / manual_config / test_spec is complete. PI-005
(process schema growth) remains Open and is the next active workstream.

The apply tees stdout to PRDs/product/crmbuilder-v2/deposit-event-logs/
dep_NNN.log per DEC-164 (git-tracked).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Doug pushes after review.
