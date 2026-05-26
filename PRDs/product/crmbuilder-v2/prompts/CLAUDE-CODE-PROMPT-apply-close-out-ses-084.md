# CLAUDE-CODE-PROMPT — apply close-out SES-084 (PI-004 cohort — requirement build)

**Last Updated:** 2026-05-26
**Operating mode:** DETAIL
**Series:** PI-004 cohort, second sibling
**Slice:** Apply the SES-084 close-out payload to the V2 governance DB
**Status:** Ready to execute. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765, migration 0015 already applied (the build session applied it before authoring this prompt), the `requirement` build commit already landed on main.

---

## Purpose

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_084.json` to the V2 governance DB via the standard apply script. Creates SES-084 + CONV-054 + DEC-274..278 + the addresses + decided_in + is_about edges + lazy-creates the close_out_payload (COP-NNN) and deposit_event (DEP-NNN), tee'ing the apply log to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`.

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.
2. Verify the API server is reachable and at the new head:
   ```bash
   curl -sf http://127.0.0.1:8765/health || echo "API not running"
   curl -sf http://127.0.0.1:8765/admin/version | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('engagement head:', d['engagement_schema']['current'], '/', d['engagement_schema']['head'])"
   # Expect both at 0015_v0_8_create_requirements_table
   ```

3. Confirm the new identifiers do not yet exist (no parallel-apply collision):
   ```bash
   for id in SES-084 CONV-054 DEC-274 DEC-275 DEC-276 DEC-277 DEC-278; do
     code=$(curl -o /dev/null -s -w "%{http_code}" http://127.0.0.1:8765/${id%-*}s/${id})
     printf '  %s → HTTP %s\n' "$id" "$code"
   done
   # Expect: 404 for all six (route paths use plural, except some)
   ```

4. Confirm WT-051 is still `ready` (consumed via the `conversation_opens_against_work_ticket` edge in this apply, per the SES-082/SES-083 precedent; manual PATCH if you want it consumed):
   ```bash
   curl -sf http://127.0.0.1:8765/work-tickets/WT-051 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['work_ticket_status'])"
   # Expect: ready
   ```

5. Confirm PI-004 is still `Open`:
   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-004 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' ', d['identifier'], d['status'])"
   # Expect: PI-004 Open
   ```

6. Confirm REQ-001 / DOM-003 / REF-1066 smoke artifacts left from the build verification are soft-deleted / hard-deleted (cleanup confirmed by the build session):
   ```bash
   curl -sf 'http://127.0.0.1:8765/requirements?include_deleted=true' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' requirements live:', sum(1 for r in d if r.get('requirement_deleted_at') is None), 'soft-deleted:', sum(1 for r in d if r.get('requirement_deleted_at') is not None))"
   # Expect: 0 live, 1 soft-deleted (REQ-001)
   ```

---

## Apply

Run the apply script. The script tees stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` automatically:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_084.json
```

Expect:

- **1 session row** created (SES-084)
- **1 conversation row** (CONV-054) created with three reference edges (`conversation_belongs_to_workstream` → WS-003, `conversation_records_session` → SES-084, `conversation_opens_against_work_ticket` → WT-051)
- **0 work_tickets** (WT-051 was authored in SES-081's apply; this apply does not transition it; consumes-via-edge is the documented pattern and prior sibling applies left WT-049/WT-050 also `ready` — manual PATCH `?work_ticket_status=consumed` if desired)
- **0 planning_items** (no new PIs surfaced by this build)
- **0 commits** (the build commit lands on main separately; commits section left empty here per the SES-082/SES-083 precedent)
- **5 decision rows** created (DEC-274..278) with `decided_in` → SES-084 edges
- **3 `is_about` payload reference rows** (SES-084 → PI-004 / SES-084 → SES-081 / SES-084 → WT-051)
- **1 `addresses` reference row** (CONV-054 → PI-004 per `addresses_planning_items`) — PI-004 stays Open per the cohort umbrella pattern
- **0 `resolves` rows** (PI-004 is NOT resolved by this slice; two cohort siblings — manual_config, test_spec — remain)
- **close_out_payload COP-NNN** lazy-created
- **deposit_event DEP-NNN** recorded with `outcome=success` plus `wrote_record` back-edges to every record the apply POSTed

---

## Post-apply verification

```bash
echo "SES-084:"
curl -sf http://127.0.0.1:8765/sessions/SES-084 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  title:', d['title'][:80])"

echo "CONV-054:"
curl -sf http://127.0.0.1:8765/conversations/CONV-054 | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  status:', d['conversation_status'])"

echo "DEC-274..278:"
for n in 274 275 276 277 278; do
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
```

---

## Commit the apply outputs

After the apply succeeds, the regenerated `db-export/` snapshots, the new `dep_NNN.log`, and the (already-created at build time) close-out payload + apply prompt land in one consolidated commit:

```bash
cd ~/Dropbox/Projects/crmbuilder

git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/ \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_084.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-084.md

git commit -m "$(cat <<'EOF'
v2: SES-084 close-out applied — PI-004 cohort (requirement shipped, PI-004 addressed)

Applies the SES-084 close-out payload via apply_close_out.py.

Creates:
- SES-084 (session) — PI-004 cohort `requirement` build, end-to-end
- CONV-054 (conversation, status=complete) wired to WS-003 + SES-084 + WT-051
- DEC-274..278 (five decisions) per requirement.md §3.9.1:
  * DEC-274 — REQ prefix and format
  * DEC-275 — field inventory, MoSCoW priority enum with default `should`
    and unconstrained transitions, global name uniqueness, v0.5 scope
  * DEC-276 — three-status propose-verify lifecycle, independent of
    priority and affiliation statuses
  * DEC-277 — five outbound kinds via references; four pairs active,
    `(requirement, test_spec)` held as TODO pending sibling build
  * DEC-278 — API surface, five-column master pane shipping by default
    per AC-11, sidebar position #4, 15 acceptance criteria
- 3 is_about payload reference rows (SES-084 → PI-004 / SES-081 / WT-051)
- 1 addresses reference (CONV-054 → PI-004; non-resolving — cohort
  umbrella)
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

PI-004 remains Open with another addresses-edge from CONV-054;
resolution waits for the last of the two remaining PI-004 siblings
(manual_config, test_spec) to ship its build-closure session per
DEC-232 / SES-074 pattern.

The apply tees stdout to PRDs/product/crmbuilder-v2/deposit-event-logs/
dep_NNN.log per DEC-164 (git-tracked).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Doug pushes after review.
