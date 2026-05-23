# UPDATE-PROMPT — PI-022 description refresh: Phase 1 complete

**Last Updated:** 05-23-26 04:15
**Operating mode:** DETAIL
**Series:** update-prompt
**Status:** Executed 05-23-26 04:06:43 (PATCH applied; commit 0beffaa on local main, pushed after review). Template-level snapshot-refresh section corrected post-execution to drop a hallucinated exporter-script invocation; the per-write `_refresh_snapshot` hook in `engagement.py` already regenerates `db-export/<table>.json` automatically. Future UPDATE-PROMPTs should follow the corrected pattern.

---

## Purpose

Refresh PI-022's description in the dogfood CRMBUILDER database to reflect the resolution of its original question (whether to backfill retroactively → resolved by DEC-166 as phased backfill) and the completion of Phase 1 via v0.7 Slice E. PI-022 remains **Open** as the parent tracker; status does not change. PI-024 / PI-025 / PI-026 (already authored at SES-056 closeout with is_about edges to PI-022) track Phases 2 / 3 / 4 respectively.

The current description was authored at SES-046 (PI-022's authoring conversation, 05-20-26) and predates the workstream's completion. Reading it post-v0.7 is confusing — it still frames the backfill question as open and future-tense.

This prompt updates the description text only. All other PI-022 fields (status, title, identifier, resolution_reference, timestamps) are unchanged.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder || cd ~/crmbuilder
git pull --rebase origin main
cd crmbuilder-v2

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start it: uv run crmbuilder-v2-api &

# Verify current PI-022 state — should be Open with the stale description
curl -s http://127.0.0.1:8765/planning-items/PI-022 | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
print(f'identifier: {d[\"identifier\"]}')
print(f'status: {d[\"status\"]}')
print(f'title: {d[\"title\"][:80]}')
print(f'description (first 200 chars): {d[\"description\"][:200]}')
"
```

Expected: status `Open`, description opening with "DEC-117 through DEC-120 introduce six new entity types..." (the stale text).

---

## Apply

PATCH `/planning-items/PI-022` with the new description. Send only the `description` field — leave all other fields unchanged.

```bash
curl -X PATCH http://127.0.0.1:8765/planning-items/PI-022 \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "description": "DEC-117 through DEC-120 (later expanded through DEC-160 across the seven-conversation governance entity schema-design workstream, SES-046 through SES-054) introduced six new entity types: workstream, conversation, reference book, work ticket, close-out payload, deposit event. The v0.7 governance entity release (SES-055 build-planning conversation; built across Slices A through F per `governance-entity-implementation-plan.md`; closed at SES-056) shipped these entity types live in the dogfood CRMBUILDER database. The retroactive-migration question this planning item originally posed was resolved by DEC-166 (SES-055) as: yes, phased backfill, executed per child planning item scope at operational discretion.\n\n**Phase 1: Complete (v0.7 Slice E).** The governance entity schema-design workstream's own records backfilled live against CRMBUILDER.db via `crmbuilder-v2/scripts/backfill_governance_phase_1.py`: 1 workstream (WS-001), 8 conversations (CONV-001..008 covering SES-047 through SES-055), 10 reference books (RB-001..010, with RB-005 and RB-007 each carrying two version rows), 8 work tickets (WT-001..008 for the eight kickoff prompts), 8 close-out payloads (COP-001..008), 8 deposit events (DEP-001..008 historical reconstructions, plus DEP-009 from the SES-056 closeout apply), and ~70 reference edges connecting them. The backfill script is idempotent on re-run.\n\n**Phases 2 through 4: Tracked in child planning items, deferred to operational signal.** PI-024 — Phase 2: backfill prior workstreams (methodology entity schema-design, v0.5 engagement management, v0.6 styling, multi-tenancy routing fix, Cleveland Business Mentors paper test, catalog ingestion). PI-025 — Phase 3: backfill prior conversations SES-001 through SES-045 and their kickoffs as work_tickets where reconstructable. PI-026 — Phase 4: backfill historical applies as deposit_events for the ~38 pre-v0.7 close-out payload files. Each child carries an is_about reference edge to this parent (created at SES-056 closeout).\n\n**Status posture.** This planning item remains Open as the parent tracker; discharge waits on completion of all three child phases. The original question this item posed is resolved; what remains is the per-phase execution work scoped under the child items. When all three phases ship, this parent's status moves to Resolved with resolution_reference pointing at the conversation that closes the final phase."
}
EOF
```

Expected response: HTTP 200 with the envelope `{"data": {...updated record...}, "meta": {...}, "errors": null}`.

If the PATCH returns HTTP 422 with a validation error about `description` field constraints, stop and report — the field is documented as free-form text but may have a length cap that needs to be checked against the new value (currently ~1700 characters).

---

## Post-apply verification

```bash
# Verify the new description is in place
curl -s http://127.0.0.1:8765/planning-items/PI-022 | python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
print(f'identifier: {d[\"identifier\"]}')
print(f'status: {d[\"status\"]}')  # should still be 'Open'
print(f'updated_at: {d.get(\"updated_at\", d.get(\"_updated_at\", \"?\"))}')
print(f'description opening: {d[\"description\"][:150]}')
print()
if 'v0.7 governance entity release' in d['description']:
    print('✓ Description refreshed.')
else:
    print('✗ Description did NOT update.')
"
```

Expected: status remains `Open`; description opens with "DEC-117 through DEC-120 (later expanded through DEC-160 across the seven-conversation governance entity schema-design workstream...)"; checkmark confirmation prints.

---

## Verify snapshot and change_log, then commit

**Snapshot regeneration is automatic.** The per-write `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py` regenerates the `db-export/<table>.json` snapshots on every write through the V2 API, and appends an audit row to `db-export/change_log.json` with the full before/after payload. There is no standalone exporter script to invoke. Just confirm both files reflect the change and commit them together.

```bash
cd ..

# Confirm the snapshot picked up the description change
grep -c "v0.7 governance entity release" PRDs/product/crmbuilder-v2/db-export/planning_items.json
# Expected: 1 (the PI-022 row now carries the refreshed description)

# Confirm change_log.json has a new audit row for this PATCH
python3 -c "
import json
with open('PRDs/product/crmbuilder-v2/db-export/change_log.json') as f:
    rows = json.load(f)
latest = rows[-1]
print(f'Latest change_log id: {latest[\"id\"]}')
print(f'entity_type: {latest[\"entity_type\"]}, entity_identifier: {latest[\"entity_identifier\"]}, action: {latest[\"action\"]}')"
# Expected: entity_type 'planning_item', entity_identifier 'PI-022', action 'updated'

# Commit the snapshot AND change_log audit row together
git add PRDs/product/crmbuilder-v2/db-export/planning_items.json \
        PRDs/product/crmbuilder-v2/db-export/change_log.json
git commit -m "PI-022 description refresh post-v0.7: Phase 1 complete, parent stays Open

Description text updated to reflect:
- The original retroactive-migration question is resolved by DEC-166 (SES-055)
  as phased backfill executed per child planning item scope.
- Phase 1 complete via v0.7 Slice E (governance workstream's own records
  backfilled: 1 WS, 8 CONVs, 10 RBs with 12 version rows, 8 WTs, 8 COPs,
  8 DEPs from backfill + DEP-009 from SES-056 closeout, ~70 reference edges).
- Phases 2/3/4 tracked in PI-024 / PI-025 / PI-026 (already authored at SES-056
  closeout with is_about edges to PI-022).
- PI-022 remains Open as parent tracker; discharge waits on completion of all
  three child phases.

PATCH /planning-items/PI-022 applied; snapshot + change_log audit row
regenerated automatically by the access-layer _refresh_snapshot hook;
no other records affected. Status unchanged (Open). Applied via
UPDATE-PROMPT-PI-022-phase-1-complete.md."
```

---

## On completion

Do **not** push automatically — Doug pushes after reviewing the commit and the description content. Print a short summary:

- The new description (echoed from the PATCH response or the snapshot).
- Confirmation that status is still `Open`.
- The commit SHA of the snapshot refresh.
- Reminder to `git push origin main`.

---

## On disaster

If the PATCH fails (HTTP 4xx/5xx other than 404), stop and report:

- The HTTP status and response body.
- Whether the description field appears to have constraints (length cap, character restrictions).
- Whether the planning-items router supports PATCH at all (404 on PATCH would suggest the router only supports POST + GET).
- Recommended next step (e.g., adjust description length; route through a direct database UPDATE if the API doesn't expose PATCH).

If 404 on the PATCH endpoint specifically (vs the record), that's a finding worth recording — it means the planning_items router lacks PATCH support, which would block this and any future PI description updates. Recommend either (a) extending the router with PATCH support as a small follow-on slice, or (b) using a one-off direct SQLite UPDATE for this specific record with the snapshot refresh capturing the change.

---

*End of update prompt.*
