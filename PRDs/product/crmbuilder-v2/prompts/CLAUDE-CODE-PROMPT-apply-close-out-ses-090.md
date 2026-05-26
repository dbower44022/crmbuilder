# SES-090 close-out apply — PI-010 satisfier (entity v0.5+ schema growth)

**Slice:** Apply the SES-090 close-out payload to the V2 governance DB
**Status:** Ready to execute. Requires: live `crmbuilder-v2-api` at 127.0.0.1:8765; migration 0019 already applied to the live CRMBUILDER engagement DB (the build session applied it via `run_engagement_migrations` before authoring this prompt); the entity v0.5+ schema-growth build commit `3b326ce` already on `main`.

---

## Purpose

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_090.json` to the V2 governance DB via the standard apply script. Creates SES-090 + CONV-060 + DEC-301/302/303 + commit record for `3b326ce` + the `decided_in` edges + lazy-creates the close_out_payload (COP-NNN) and deposit_event (DEP-NNN), tees the apply log to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`. The single `resolves_planning_items` entry atomically flips PI-010 from `Open` to `Resolved` via slice A's edge+flip behavior.

**This apply resolves PI-010 — entity-schema v0.5+ extensions covering variants and base-type/kind classification.**

---

## Identifier re-keying

The originally-planned identifiers (SES-089 / CONV-059 / DEC-291–293) were already claimed by an unapplied parallel-sandbox architecture-review draft at `close-out-payloads/ses_089.json`. Per CLAUDE.md's identifier-collision contingency, this session re-keyed to:

| Originally planned | Re-keyed to |
|---|---|
| SES-089 | SES-090 |
| CONV-059 | CONV-060 |
| DEC-291 / DEC-292 / DEC-293 | DEC-301 / DEC-302 / DEC-303 |

This leaves DEC-291–300 + PI-061–073 available for the architecture-review session when it applies.

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. Verify the API server is reachable. Note: the API process running at apply time is on **pre-migration code** — it doesn't know about `entity_kind` or `entity_variant_of_entity` yet. The apply script doesn't depend on those (it writes DECs / sessions / conversations / commits which are unaffected by entity-schema growth). After the apply succeeds, restart the API to surface the new field on REST:
   ```bash
   curl -sf http://127.0.0.1:8765/ | python3 -c "import sys,json; d=json.load(sys.stdin); print('api:', d['name'], d['version'])"
   ```

3. Confirm the new identifiers do not yet exist (no parallel-apply collision):
   ```bash
   for id in SES-090 CONV-060 DEC-301 DEC-302 DEC-303; do
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

4. Confirm PI-010 is still `Open`:
   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-010 \
     | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('  PI-010:', d['status'])"
   # Expect: Open
   ```

5. Confirm the build commit `3b326ce` is on the current branch:
   ```bash
   git log --oneline -1 3b326ce0c306453190db8ab292205f329e33ac43 2>&1 | head -1
   # Expect: 3b326ce v2: PI-010 — entity v0.5+ schema growth ...
   ```

6. Confirm migration 0019 is applied to the CRMBUILDER engagement DB:
   ```bash
   sqlite3 crmbuilder-v2/data/engagements/CRMBUILDER.db \
     "SELECT version_num FROM alembic_version;"
   # Expect: 0019_v0_5_entity_kind_and_variants
   sqlite3 crmbuilder-v2/data/engagements/CRMBUILDER.db \
     "PRAGMA table_info(entities);" | awk -F'|' '{print $2}'
   # Expect: includes entity_kind
   ```

---

## Apply

Run the standard apply script:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_090.json
```

Expected: each record is created successfully (SES-090, CONV-060, DEC-301, DEC-302, DEC-303, three `decided_in` edges, the commit row for `3b326ce`, the `conversation_belongs_to_workstream` edge to WS-003, the `conversation_records_session` edge to SES-090, the `resolves` edge from CONV-060 to PI-010 atomically flipping PI-010 to `Resolved`, the lazy-created close_out_payload + deposit_event with `outcome=success`). The deposit-event log lands at `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`.

---

## Post-apply verification

1. PI-010 status:
   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-010 \
     | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(' status:', d['status'])"
   # Expect: Resolved
   ```

2. Records exist:
   ```bash
   for id in SES-090 CONV-060 DEC-301 DEC-302 DEC-303; do
     case "$id" in
       SES-*) route="sessions" ;;
       CONV-*) route="conversations" ;;
       DEC-*) route="decisions" ;;
     esac
     code=$(curl -o /dev/null -s -w "%{http_code}" "http://127.0.0.1:8765/${route}/${id}")
     printf '  %s -> HTTP %s\n' "$id" "$code"
   done
   # Expect: 200 for all five
   ```

3. References:
   ```bash
   curl -sf "http://127.0.0.1:8765/references?source_type=conversation&source_id=CONV-060" \
     | python3 -c "import sys,json; refs=json.load(sys.stdin)['data']; [print(' ', r['relationship'], '->', r['target_type'], r['target_id']) for r in refs]"
   # Expect: conversation_belongs_to_workstream -> workstream WS-003,
   #         conversation_records_session -> session SES-090,
   #         resolves -> planning_item PI-010
   ```

4. Db-export snapshots regenerated (the apply script regenerates them):
   ```bash
   git status PRDs/product/crmbuilder-v2/db-export/
   # Expect: modified files for status / sessions / conversations / decisions / references / planning_items / deposit_events / close_out_payloads
   ```

5. Deposit-event log file:
   ```bash
   ls -la PRDs/product/crmbuilder-v2/deposit-event-logs/ | tail -3
   # Expect: a new dep_NNN.log file
   ```

---

## Smoke-verify the new entity-schema surface (after API restart)

The API server must be restarted to surface the new entity_kind / variant edges on REST. After restart:

```bash
# 1. entity_kind round-trip.
curl -s -X POST http://127.0.0.1:8765/entities \
  -H 'Content-Type: application/json' \
  -d '{"entity_name":"Smoke person","entity_description":"d","entity_kind":"person"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(d.get('entity_identifier'), d.get('entity_kind'))"

# 2. Invalid kind rejected.
curl -s -X POST http://127.0.0.1:8765/entities \
  -H 'Content-Type: application/json' \
  -d '{"entity_name":"Smoke bad","entity_description":"d","entity_kind":"vegetable"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('errors:', bool(d.get('errors')))"

# 3. Variant edge round-trip (requires two entities).
# 4. Variant cardinality enforced (second outbound from same source rejected).
# 5. Variant self-reference rejected.

# Clean up smoke records:
# curl -s -X DELETE http://127.0.0.1:8765/entities/ENT-NNN
```

---

## Commit

After successful apply:

```bash
git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/dep_*.log \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_090.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-090.md

git commit -m "$(cat <<'EOF'
v2: SES-090 close-out applied — PI-010 → Resolved

Applies ses_090.json: SES-090 + CONV-060 + DEC-301/302/303
(variant mechanism + entity_kind shape + migration story) +
commit record for 3b326ce + decided_in edges +
conversation_belongs_to_workstream to WS-003 +
conversation_records_session to SES-090 + the resolves edge from
CONV-060 to PI-010 that atomically flips PI-010 Open → Resolved.
Lazy-creates close_out_payload + deposit_event with outcome=success.

Identifiers re-keyed from SES-089/CONV-059/DEC-291-293 to
SES-090/CONV-060/DEC-301-303 per CLAUDE.md's parallel-sandbox
identifier-collision contingency (the SES-089 block was already
claimed by an unapplied architecture-review draft).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Notes

- The session uses `addresses_planning_items: []` and `resolves_planning_items: [{"planning_item_identifier": "PI-010"}]` — there is no prior `addresses` edge from this session to PI-010 (the orchestrator session executed the whole PI in one pass), so `resolves` is the only PI edge.
- No new planning items or work tickets are authored in this close-out — the v0.6+ follow-on candidates (kind-inheritance, kind-informed Phase 3 defaults, kind-informed Phase 5 scoring, master-pane Kind column) are noted in the session's `in_flight_at_end` field as candidates for whichever future workstream picks up v0.6+ entity work.
- The conversation has no `conversation_opens_against_work_ticket` edge because there is no kickoff prompt file — the conversation was driven by direct user prompts.
- After this apply, PI-010 joins PI-003 / PI-004 / PI-005 as Resolved. The methodology entity schema design workstream (WS-003) has now landed all four entity types from v0.4 plus their growth slices.
