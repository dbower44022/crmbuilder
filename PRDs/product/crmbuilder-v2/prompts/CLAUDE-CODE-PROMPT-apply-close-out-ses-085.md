# CLAUDE-CODE-PROMPT — apply close-out SES-085 (PI-004 cohort — manual_config build)

**Last Updated:** 2026-05-26
**Operating mode:** DETAIL
**Series:** PI-004 cohort, third sibling
**Slice:** Apply the SES-085 close-out payload to the V2 governance DB
**Status:** Ready to execute. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765, migration 0016 already applied (the build session applied it before authoring this prompt), the `manual_config` build commit already landed on main.

---

## Purpose

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_085.json` to the V2 governance DB via the standard apply script. Creates SES-085 + CONV-055 + DEC-279..283 + the `addresses` + `decided_in` + `is_about` edges + lazy-creates the close_out_payload (COP-NNN) and deposit_event (DEP-NNN), tee'ing the apply log to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`.

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.
2. Verify the API server is reachable and at the new head:
   ```bash
   curl -sf http://127.0.0.1:8765/health || echo "API not running"
   curl -sf http://127.0.0.1:8765/admin/version | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('engagement head:', d['engagement_schema']['current'], '/', d['engagement_schema']['head'])"
   # Expect both at 0016_v0_8_create_manual_configs_table
   ```

3. Confirm the new identifiers do not yet exist (no parallel-apply collision):
   ```bash
   for id in SES-085 CONV-055 DEC-279 DEC-280 DEC-281 DEC-282 DEC-283; do
     case "$id" in
       SES-*) route="sessions" ;;
       CONV-*) route="conversations" ;;
       DEC-*) route="decisions" ;;
     esac
     code=$(curl -o /dev/null -s -w "%{http_code}" "http://127.0.0.1:8765/${route}/${id}")
     printf '  %s → HTTP %s\n' "$id" "$code"
   done
   # Expect: 404 for all seven
   ```

4. Confirm WT-052 is still `ready` (consumed via the `conversation_opens_against_work_ticket` edge in this apply per the SES-082/SES-083/SES-084 precedent; manual PATCH if you want it consumed):
   ```bash
   curl -sf http://127.0.0.1:8765/work-tickets/WT-052 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['work_ticket_status'])"
   # Expect: ready
   ```

5. Confirm PI-004 is still `Open`:
   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-004 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['identifier'], d['status'])"
   # Expect: PI-004 Open
   ```

6. Confirm MCF-001 / MCF-002 smoke artifacts left from the build verification are soft-deleted (cleanup confirmed by the build session):
   ```bash
   curl -sf 'http://127.0.0.1:8765/manual-configs?include_deleted=true' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' manual_configs live:', sum(1 for r in d if r.get('manual_config_deleted_at') is None), 'soft-deleted:', sum(1 for r in d if r.get('manual_config_deleted_at') is not None))"
   # Expect: 0 live, 2 soft-deleted (MCF-001, MCF-002)
   ```

7. Confirm `manual_configs` table is present and the four new relationship kinds are in the vocab:
   ```bash
   curl -sf http://127.0.0.1:8765/manual-configs | python3 -c "import sys,json; d=json.load(sys.stdin); print(' manual-configs endpoint reachable, returns', len(d['data']), 'live records')"
   ```

---

## Apply

Run the apply script. The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` automatically:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_085.json
```

Expect:

- **1 session row** created (SES-085)
- **1 conversation row** (CONV-055) created with three reference edges (`conversation_belongs_to_workstream` → WS-003, `conversation_records_session` → SES-085, `conversation_opens_against_work_ticket` → WT-052)
- **0 work_tickets** (WT-052 was authored in SES-081's apply chain; this apply does not transition it; consumes-via-edge is the documented pattern and prior sibling applies left WT-049/WT-050/WT-051 also `ready` — manual PATCH `?work_ticket_status=consumed` if desired)
- **0 planning_items** (no new PIs surfaced by this build)
- **0 commits** (the build commit lands on main separately; commits section left empty here per the SES-082/SES-083/SES-084 precedent)
- **5 decision rows** created (DEC-279..283) with `decided_in` → SES-085 edges
- **3 `is_about` payload reference rows** (SES-085 → PI-004 / SES-085 → SES-081 / SES-085 → WT-052)
- **1 `addresses` reference row** (CONV-055 → PI-004 per `addresses_planning_items`) — PI-004 stays Open per the cohort umbrella pattern
- **0 `resolves` rows** (PI-004 is NOT resolved by this slice; one cohort sibling — test_spec — remains)
- **close_out_payload COP-NNN** lazy-created
- **deposit_event DEP-NNN** recorded with `outcome=success` plus `wrote_record` back-edges to every record the apply POSTed

---

## Post-apply verification

```bash
echo "SES-085:"
curl -sf http://127.0.0.1:8765/sessions/SES-085 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80])"

echo "CONV-055:"
curl -sf http://127.0.0.1:8765/conversations/CONV-055 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  status:', d['conversation_status'])"

echo "DEC-279..283:"
for n in 279 280 281 282 283; do
  curl -sf http://127.0.0.1:8765/decisions/DEC-$n | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  DEC-$n:', d['title'][:70])"
done

echo "PI-004 status (expect Open — cohort umbrella):"
curl -sf http://127.0.0.1:8765/planning-items/PI-004 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['identifier'], d['status'])"

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

echo "PI-004 addresses-edge count after apply (expect 8 — was 7, +1 from CONV-055):"
curl -sf 'http://127.0.0.1:8765/references?target_id=PI-004&relationship_kind=addresses' \
  | python3 -c "import sys, json; d = json.load(sys.stdin)['data']; print(' ', len(d), 'edges')"
```

---

## Commit the apply outputs

After the apply succeeds, the regenerated `db-export/` snapshots, the new `dep_NNN.log`, and the (already-created at build time) close-out payload + apply prompt land in one consolidated commit:

```bash
cd ~/Dropbox/Projects/crmbuilder

git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/ \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_085.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-085.md

git commit -m "$(cat <<'EOF'
v2: SES-085 close-out applied — PI-004 cohort (manual_config shipped, PI-004 addressed)

Applies the SES-085 close-out payload via apply_close_out.py.

Creates:
- SES-085 (session) — PI-004 cohort `manual_config` build, end-to-end
- CONV-055 (conversation, status=complete) wired to WS-003 + SES-085 + WT-052
- DEC-279..283 (five decisions) per manual_config.md §3.9.1:
  * DEC-279 — MCF prefix and format
  * DEC-280 — field inventory, seven-value category enum, v0.5 scope
  * DEC-281 — four-status lifecycle (deviation) with terminal `completed`
    and §3.5.3 cross-field invariant via the new
    CompletedStatusRequiresCompletionFieldsError + handler
  * DEC-282 — four outbound kinds via references; all four pairs active
    unconditionally (no TODOs — all four target entity types live)
  * DEC-283 — API surface, five-column master pane (Category shipping
    by default per AC-12), status-combo-driven Mark-Completed UX,
    sidebar tail position, 16 acceptance criteria
- 3 is_about payload reference rows (SES-085 → PI-004 / SES-081 / WT-052)
- 1 addresses reference (CONV-055 → PI-004; non-resolving — cohort
  umbrella; one sibling remains: test_spec)
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

PI-004 remains Open with another addresses-edge from CONV-055;
resolution waits for the last remaining PI-004 sibling (test_spec) to
ship its build-closure session per DEC-232 / SES-074 pattern.

The apply tees stdout to PRDs/product/crmbuilder-v2/deposit-event-logs/
dep_NNN.log per DEC-164 (git-tracked).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Doug pushes after review.
