# CLAUDE-CODE-PROMPT — apply close-out SES-097 (PI-074 implementation — executive_summary column)

**Last Updated:** 05-27-26
**Operating mode:** DETAIL
**Series:** WS-012 (Parallel agent orchestrator and executive summary) — first delivering session
**Slice:** Apply the SES-097 close-out payload to the V2 governance DB
**Status:** **Multi-step apply with a schema-migration pre-step.** Requires merging the `pi-074-executive-summary` branch to `main`, running `alembic upgrade head` against the live CRMBUILDER engagement DB, and restarting the API before running the apply script — the payload itself dogfoods the new `executive_summary` column on its session record, so the API must already know about the column.

> **Why this session record exists.** PI-074 (in WS-012) called for a nullable `executive_summary` TEXT column on `planning_items`, `decisions`, and `sessions` with CHECK length 200-800. PI-074 has no `blocked_by` edge to PI-073 in the planning graph, but the two PIs overlap on the `sessions` table; the conflict is deliberately deferred to merge time. PI-074's session also delivered an unplanned engine fix — a dedicated migration engine in `migrations/env.py` with `foreign_keys=OFF`, resolving a SQLite batch_alter_table FK-enforcement collision that surfaced when this build's first migration run failed at `DROP TABLE decisions`.

> **Identifier-head capture per DEC-300.** Heads captured at session start (live API query at apply-prompt authoring time): SES-096, CONV-066, DEC-318, PI-090, WT-055. This payload reserves SES-097, CONV-067, no DECs (build session — no architectural decisions), no PIs (resolves PI-074), no WTs. Pre-flight below MUST re-verify before apply.

---

## Net Effect

Apply `PRDs/product/crmbuilder-v2/close-out-payloads/ses_097.json` to the V2 governance DB via the standard apply script. Creates:

- **SES-097** — session record for the PI-074 implementation, including a populated `executive_summary` (601 chars) — the first session to dogfood the new field
- **CONV-067** — conversation record (status=`complete`) with two embedded reference edges (`conversation_belongs_to_workstream` → WS-012; `conversation_records_session` → SES-097)
- **1 commit row** for `6ae82c3` (the PI-074 implementation commit on the `pi-074-executive-summary` branch)
- **1 resolves edge** — `resolves` CONV-067 → PI-074 (atomic with status flip `Open → Resolved` per slice A of PI-030)
- close_out_payload COP-NNN + deposit_event DEP-NNN (lazy-created)

No new decisions, no new planning items, no work tickets opened or consumed. `addresses_planning_items[]` is empty.

---

## Cross-PI conflict awareness — PI-073

PI-073 (Session/Conversation redesign) is in flight on its own branch (`pi-073-redesign`) and **renames** the `sessions` table to a new shape with parent-prefix column naming (`session_identifier`, `session_title`, etc.). PI-074's `executive_summary` column lands on the **legacy** `sessions` table.

When PI-073 eventually merges, the merger absorbs the rebase:

- If PI-074 lands on `main` first (this apply does that): PI-073's Phase A migration must be regenerated against the post-PI-074 schema, and the new `sessions` table created by PI-073 must include `session_executive_summary` per the post-PI-073 parent-prefix convention.
- If PI-073 lands first: PI-074's column placement shifts to the renamed table; the migration body stays nearly the same (still 200-800 CHECK constraint, still nullable).

Neither path needs a coordination step before this apply.

---

## Pre-flight

1. `pwd` → repo clone root (`~/Dropbox/Projects/crmbuilder`). Stop if unexpected.

2. Branch state:
   ```bash
   git branch --show-current   # expect pi-074-executive-summary
   git status --porcelain
   ```
   Stop if working tree is non-empty (other than the close-out payload + this apply prompt, which are committed in the final close-out commit after apply).

3. Git identity:
   ```bash
   git config user.email   # expect doug@dougbower.com
   git config user.name    # expect Doug Bower
   ```

4. Payload and apply prompt exist:
   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_097.json
   ls -la PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-097.md
   ```

5. **Pre-apply identifier-head capture per DEC-300** (re-verify against live API):
   ```bash
   curl -sf http://127.0.0.1:8765/sessions       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(s['identifier'] for s in d); print('SES head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/conversations  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(c['conversation_identifier'] for c in d); print('CONV head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/decisions      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(dc['identifier'] for dc in d); print('DEC head:', ids[-1])"
   curl -sf http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(p['identifier'] for p in d); print('PI head:', ids[-1])"
   ```
   Expected heads (sandbox-captured at session start): SES-096, CONV-066, DEC-318, PI-090. If `SES head` is now ≥ SES-097 or `CONV head` is now ≥ CONV-067, the payload must be **renumbered** before apply — see Renumbering below.

6. Confirm PI-074 is currently `Open` (the apply flips it to `Resolved`):
   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-074 | python3 -c "import sys,json; p=json.load(sys.stdin)['data']; print('PI-074 status:', p['status'])"
   ```
   Expect `Open`. If already `Resolved`, the apply will fail at the resolves edge — investigate why before re-running.

---

## Schema-migration pre-steps (CRITICAL — apply will fail without these)

The payload's session record carries a populated `executive_summary` field (601 chars). The API on `main` does not yet know about this field; POST will return 422 with `extra="forbid"`. Before running the apply, the PI-074 branch must be merged to `main`, the migration must run against the live CRMBUILDER DB, and the API must be restarted.

1. Merge `pi-074-executive-summary` to `main`:
   ```bash
   git checkout main
   git pull --rebase origin main
   git merge --no-ff pi-074-executive-summary
   ```
   Expect a fast-forward or a clean non-ff merge. If `pi-073-redesign` has already merged, expect conflicts in `crmbuilder-v2/src/crmbuilder_v2/access/models.py` (Session class) and `crmbuilder-v2/migrations/versions/`. Resolve per the "Cross-PI conflict awareness — PI-073" section above.

2. Run the migration against the live CRMBUILDER engagement DB:
   ```bash
   cd crmbuilder-v2
   CRMBUILDER_V2_DB_PATH="$(pwd)/data/engagements/CRMBUILDER.db" uv run alembic upgrade head
   cd ..
   ```
   Expect `Running upgrade 0019_v0_5_entity_kind_and_variants -> 0020_pi_074_executive_summary`. Verify the column lands on all three tables:
   ```bash
   sqlite3 crmbuilder-v2/data/engagements/CRMBUILDER.db "PRAGMA table_info(planning_items);" | grep executive_summary
   sqlite3 crmbuilder-v2/data/engagements/CRMBUILDER.db "PRAGMA table_info(decisions);" | grep executive_summary
   sqlite3 crmbuilder-v2/data/engagements/CRMBUILDER.db "PRAGMA table_info(sessions);" | grep executive_summary
   ```
   Each should print one row with `TEXT` and `notnull=0`.

3. Restart the API so it picks up the new Pydantic schemas:
   - If running under systemd / launchd: restart the service.
   - If running ad-hoc via `uv run crmbuilder-v2-api &`: kill the process and re-launch.
   - Verify the new schema is live:
     ```bash
     curl -sf http://127.0.0.1:8765/health
     # Optional: confirm the field is now accepted by posting a probe with a too-short summary; expect 422 with executive_summary error
     ```

4. Re-run the CBM engagement migration if the CBM engagement DB is also targeted (the apply targets CRMBUILDER only by default, so this is optional):
   ```bash
   cd crmbuilder-v2
   CRMBUILDER_V2_DB_PATH="$(pwd)/data/engagements/CBM.db" uv run alembic upgrade head
   cd ..
   ```
   Skip if CBM is at a divergent head per the PI-073 plan notes (CBM lags behind CRMBUILDER on schema head).

---

## Renumbering (if heads have advanced)

If pre-flight step 5 reveals SES head ≥ SES-097 or CONV head ≥ CONV-067:

1. Compute new heads: `new_ses = live_ses_head + 1`, `new_conv = live_conv_head + 1`.
2. Edit `ses_097.json` and update **every** internal reference:
   - `session.identifier`
   - `conversation.conversation_identifier`
   - The two embedded `conversation.references[]` entries' `source_id`
   - `session.conversation_reference` mentions of CONV-067
3. Rename the payload to `ses_NNN.json` matching the new SES identifier.
4. Rename this apply prompt to `CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`.
5. Repeat pre-flight step 5 to confirm the new identifiers are higher than current heads.
6. Proceed to Apply.

---

## Apply

Run the standard close-out apply script:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_097.json
```

Expected OK counts on success:

- 1 session created (SES-097, with `executive_summary` populated)
- 1 conversation created (CONV-067)
- 0 decisions, 0 planning_items, 0 work_tickets
- 1 commit row ingested (6ae82c3)
- 0 top-level references created
- 2 embedded conversation references created (`conversation_belongs_to_workstream` → WS-012, `conversation_records_session` → SES-097)
- 1 resolves edge — CONV-067 → PI-074 — atomically flips PI-074 `Open → Resolved`
- 1 close_out_payload lazy-created (COP-NNN)
- 1 deposit_event lazy-created (DEP-NNN)

Any 4xx response halts the apply — read the error and either correct the payload or surface to Doug. The most likely failure is `executive_summary` field rejection (422) if the schema-migration pre-steps were skipped or the API was not restarted.

---

## Post-apply verification

1. Identifier-head advancement:
   ```bash
   curl -sf http://127.0.0.1:8765/sessions       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(s['identifier'] for s in d); print('SES head after:', ids[-1])"
   curl -sf http://127.0.0.1:8765/conversations  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(c['conversation_identifier'] for c in d); print('CONV head after:', ids[-1])"
   ```
   Expect `SES head after: SES-097` and `CONV head after: CONV-067` (or higher if renumbered).

2. PI-074 is now Resolved:
   ```bash
   curl -sf http://127.0.0.1:8765/planning-items/PI-074 | python3 -c "import sys,json; p=json.load(sys.stdin)['data']; print('PI-074:', p['status'], '|', p.get('resolution_reference'))"
   ```
   Expect `Resolved`. The `resolution_reference` should point at the resolves edge.

3. The executive_summary field round-trips:
   ```bash
   curl -sf http://127.0.0.1:8765/sessions/SES-097 | python3 -c "import sys,json; s=json.load(sys.stdin)['data']; es=s.get('executive_summary',''); print('SES-097.executive_summary len:', len(es) if es else 'NULL')"
   ```
   Expect `SES-097.executive_summary len: 601`.

4. Resolves edge present:
   ```bash
   curl -sf "http://127.0.0.1:8765/references?source_id=CONV-067&relationship=resolves" | python3 -m json.tool
   ```
   Expect one row, `target_type=planning_item`, `target_id=PI-074`.

5. Conversation membership in WS-012:
   ```bash
   curl -sf "http://127.0.0.1:8765/references?source_id=CONV-067&relationship=conversation_belongs_to_workstream" | python3 -m json.tool
   ```
   Expect one row, `target_id=WS-012`.

---

## Commit snapshot regeneration

The apply script's `_refresh_snapshot` hook regenerates `PRDs/product/crmbuilder-v2/db-export/` JSON snapshots on every write. After apply completes, commit all snapshot updates plus the payload, this apply prompt, and the deposit-event log file together in **one** commit on `main`:

```bash
cd ~/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/db-export/
git add PRDs/product/crmbuilder-v2/close-out-payloads/ses_097.json
git add PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-097.md
git add PRDs/product/crmbuilder-v2/deposit-event-logs/ 2>/dev/null || true
git commit -m "v2: SES-097 close-out applied — PI-074 implementation (executive_summary column on planning_items, decisions, sessions; resolves PI-074)"
```

Optional cleanup:

```bash
# Delete the working branch once main carries the work
git branch -d pi-074-executive-summary
# Remove the branch-isolated DB copies — gitignored, no commit needed
rm -rf crmbuilder-v2/data/branch-pi-074
```
