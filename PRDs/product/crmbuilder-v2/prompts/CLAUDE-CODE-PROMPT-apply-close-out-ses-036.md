# CLAUDE-CODE-PROMPT-apply-close-out-ses-036

**Last Updated:** 05-18-26 12:00
**Operating mode:** detail
**Series:** apply-close-out
**Status:** Ready to execute
**Companion payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_036.json`
**Reconciliation context:** This is a reconciliation apply prompt, not a normal close-out. It exists to correct an identifier-displacement issue from the styling Conversation 2's original close-out apply (commit `cfdd088` on 05-18-26).

---

## Purpose

Reconcile the styling Conversation 2's session-record displacement from SES-030 to SES-036. Two-part operation:

1. **Apply the SES-036 payload** — insert the displaced session content at the correct identifier; re-insert DEC-105/106/107 (which will SKIP via 409 because they're already present); add four corrected references (DEC-105/106/107 → SES-036 decided_in; SES-036 → PI-001 is_about).
2. **DELETE four orphan references** — the four references applied during the original commit `cfdd088` that point at the wrong SES-030 record. Reference IDs to delete: 136, 137, 138, 139.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-036 created with the styling Conversation 2 build-planning content (PRD authoring, implementation plan, six slice prompts, identifier rebase forensics, reconciliation note prepended).
- **Decisions.** No change — DEC-105/106/107 already in DB from the original apply; the script SKIPs them via 409.
- **References.** +4 net (4 added pointing at SES-036; 4 deleted pointing at SES-030). Total stays at 139 (or whatever the pre-state was; +4 −4 = 0 net).

The orphan-delete step is hard-coded by reference ID (136, 137, 138, 139) per the database snapshot at the time this prompt was authored (`PRDs/product/crmbuilder-v2/db-export/references.json`, captured 05-18-26 ~10:33 UTC per the `created_at` timestamps on those records). The pre-flight step verifies those four IDs still match the expected source/target/relationship_kind tuples before issuing the DELETEs — protects against the snapshot drifting between this prompt's authoring and its run.

---

## Background

The styling Conversation 2 (this conversation's predecessor) authored ses_030.json on 05-16-26 (commit `501cac8`) targeting SES-030, calculated from a database snapshot showing SES-029 as the latest applied session. Between that commit and Doug's run of the apply prompt (05-18-26 at commit `cfdd088`), a separate v0.5 follow-up conversation independently claimed SES-030 by direct API POST on 05-17-26, without committing a ses_030.json file. The styling Conversation 2's apply hit a 409 on SES-030 and absorbed it as SKIP — the script's documented idempotent behavior for partial prior runs. DEC-105/106/107 inserted cleanly along with four references, but those references now `decided_in` / `is_about` the wrong SES-030 record (which contains v0.5 follow-up content, not styling Conversation 2 content).

This reconciliation:
- Inserts the displaced session content at SES-036 (next available after SES-035, verified in pre-flight).
- Adds four correct references pointing at SES-036.
- Deletes the four orphan references pointing at SES-030.

DEC-105/106/107 themselves are unaffected — they are correctly applied, and their `decided_in` references will now correctly point at SES-036 once both halves of this reconciliation complete.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts.

5. **Confirm payload file exists:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_036.json
   ```

   Stop if missing.

6. **Confirm v2 API is running:**

   ```bash
   curl -sf http://127.0.0.1:8765/decisions >/dev/null && echo "API up" || echo "API DOWN"
   ```

   If the API is not running, ask Doug to start it (`cd crmbuilder-v2 && uv run crmbuilder-v2-api &`) before proceeding. Do not start it yourself.

7. **Verify SES-036 is still uncontested:**

   ```bash
   curl -sf http://127.0.0.1:8765/sessions/SES-036 >/dev/null && echo "SES-036 ALREADY EXISTS — STOP" || echo "SES-036 available"
   ```

   If SES-036 already exists, **stop and report** — another parallel process has claimed it (same race-condition pattern that displaced SES-030 in the first place). Doug will need to re-rebase to the next available identifier.

8. **Verify the four orphan reference IDs match expected source/target/relationship tuples.** This protects against the snapshot drifting. The verify-pipe uses `r['relationship']` per the live API field name (the snapshot file uses `relationship_kind` but the API serializes as `relationship`):

   ```bash
   curl -s http://127.0.0.1:8765/references | python3 -c "
   import sys, json
   refs = json.load(sys.stdin)['data']
   expected = {
       136: ('DEC-105', 'SES-030', 'decided_in'),
       137: ('DEC-106', 'SES-030', 'decided_in'),
       138: ('DEC-107', 'SES-030', 'decided_in'),
       139: ('SES-030', 'PI-001', 'is_about'),
   }
   all_match = True
   for rid, (exp_src, exp_tgt, exp_rel) in expected.items():
       found = next((r for r in refs if r.get('id') == rid), None)
       if found is None:
           print(f'id={rid}: MISSING (already deleted or never inserted)')
           all_match = False
           continue
       actual = (found.get('source_id'), found.get('target_id'), found.get('relationship'))
       if actual == (exp_src, exp_tgt, exp_rel):
           print(f'id={rid}: OK ({exp_src} -> {exp_tgt} {exp_rel})')
       else:
           print(f'id={rid}: MISMATCH — expected {(exp_src, exp_tgt, exp_rel)}, got {actual}')
           all_match = False
   print('ALL MATCH' if all_match else 'STOP — orphan IDs drifted from snapshot')
   "
   ```

   If any ID does not match or is missing, **stop and report**. Doug will need to manually identify the current orphan reference IDs and update this prompt before re-running.

9. **Capture pre-state for verification:**

   ```bash
   curl -s http://127.0.0.1:8765/references | python3 -c "import sys, json; print('Refs total:', len(json.load(sys.stdin)['data']))"
   ```

   Report the value. Post-state should be the same (+4 inserts and −4 deletes net to zero).

---

## Workflow

### Step 1 — Apply SES-036 payload (session + 4 new references; DEC-105/106/107 SKIP)

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_036.json
cd ..
```

Expected output:
- SES-036 reports `OK` (created).
- DEC-105, DEC-106, DEC-107 each report `SKIP` (409 — already present from prior apply).
- 4 references each report `OK` (created).
- Script exits 0.

Stop and report if any record returns anything other than `OK` or `SKIP`, or if the script exits non-zero.

### Step 2 — Verify SES-036 + new references

```bash
# Session exists
curl -sf http://127.0.0.1:8765/sessions/SES-036 >/dev/null && echo "SES-036 OK" || echo "SES-036 MISSING"

# New references
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
for dec in ['DEC-105','DEC-106','DEC-107']:
    found = any(r['source_id']==dec and r['target_id']=='SES-036' and r['relationship']=='decided_in' for r in refs)
    print(f'{dec}->SES-036 decided_in:', found)
is_about_found = any(r['source_id']=='SES-036' and r['target_id']=='PI-001' and r['relationship']=='is_about' for r in refs)
print(f'SES-036->PI-001 is_about:', is_about_found)
"
```

All four checks should report `True`. Stop and report if any are `False`.

### Step 3 — DELETE the four orphan references

```bash
for rid in 136 137 138 139; do
  status=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE http://127.0.0.1:8765/references/$rid)
  echo "DELETE /references/$rid -> HTTP $status"
done
```

Expected output: each DELETE returns HTTP 200 (or 204). Stop and report if any return 4xx/5xx.

The references endpoint hard-deletes by integer primary key per `crmbuilder-v2/src/crmbuilder_v2/access/repositories/references.py` — there is no soft-delete for references.

### Step 4 — Verify orphans deleted

```bash
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
ids_to_check = [136, 137, 138, 139]
remaining = [r for r in refs if r.get('id') in ids_to_check]
if not remaining:
    print('All 4 orphan references successfully deleted.')
else:
    print(f'STOP — {len(remaining)} orphan references still present:')
    for r in remaining:
        print(f'  id={r[\"id\"]} {r[\"source_id\"]} -> {r[\"target_id\"]} ({r[\"relationship\"]})')
# Confirm no other references still point at the v0.5 follow-up SES-030 from styling Conv 2's DECs
ses_conv2_to_ses030 = [r for r in refs if r.get('source_id') in ('DEC-105','DEC-106','DEC-107','SES-036') and (r.get('target_id')=='SES-030' or r.get('source_id')=='SES-030') and r.get('source_id') in ('DEC-105','DEC-106','DEC-107')]
if ses_conv2_to_ses030:
    print('WARNING — styling Conv 2 DECs still reference SES-030:')
    for r in ses_conv2_to_ses030:
        print(f'  id={r[\"id\"]} {r[\"source_id\"]} -> {r[\"target_id\"]}')
else:
    print('No stray references from styling Conv 2 DECs to SES-030.')
print('Final refs total:', len(refs))
"
```

Expected output:
- "All 4 orphan references successfully deleted."
- "No stray references from styling Conv 2 DECs to SES-030."
- Refs total should match the pre-state count (+4 inserts in Step 1, −4 deletes in Step 3 = net 0).

Stop and report if either assertion fails.

### Step 5 — Verify snapshot regeneration

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications: `sessions.json` (SES-036 added), `references.json` (4 added, 4 removed), and `change_log.json`. (`decisions.json` and `planning_items.json` unchanged.) Stop and report if any expected file is unchanged.

### Step 6 — Commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply SES-036 reconciliation — styling Conv 2 displacement fix

Resolves the SES-030 identifier displacement from commit cfdd088:

- Styling Conversation 2 originally targeted SES-028 at PRD-authoring
  time, rebased to SES-030 at close-out artifact authoring (commit
  7255667) based on snapshot showing SES-029 as latest applied
- Between that rebase and Doug's apply-prompt run (05-18-26), v0.5
  follow-up conversation independently claimed SES-030 on 05-17-26
  via direct API POST without committing a ses_030.json file
- Styling Conv 2's apply hit 409 on SES-030, absorbed as SKIP
- DEC-105/106/107 + 4 references inserted but pointing at wrong
  SES-030 record

This reconciliation:
- Inserts styling Conv 2 session content at SES-036 (next available
  after SES-035; verified uncontested in pre-flight)
- Re-inserts DEC-105/106/107 (SKIP via 409 — already present)
- Adds 4 correct references: DEC-105/106/107 -> SES-036 decided_in;
  SES-036 -> PI-001 is_about
- DELETEs 4 orphan references (ids 136, 137, 138, 139) pointing at
  the wrong SES-030 record

Snapshot regeneration only — payload file is unchanged.

The underlying design weakness this exposed: snapshot-derived 'next
available identifier' is a TOCTOU race. Parallel conversations
calculating next-available concurrently can arrive at the same
answer; first-to-POST wins; loser silently absorbs the 409. The
file-level coordination mechanism (commit a ses_NNN.json before
applying) only works if BOTH parallel processes use it. The v0.5
follow-up conversation bypassed the file mechanism. Future
mitigation considerations: lock-and-claim API endpoint, or
mandatory ses_NNN.json file commit BEFORE any API write.

DEC-105/106/107 are unaffected: correctly applied and now correctly
linked to SES-036."
```

### Step 7 — Push

```bash
git push origin main
```

Stop and report if push fails for any reason.

---

## Done

After Step 7 completes, the SES-030 displacement is fully reconciled:

- SES-036 contains the styling Conversation 2 build-planning content.
- DEC-105/106/107 reference SES-036 via `decided_in`.
- SES-036 references PI-001 via `is_about`.
- The four orphan references that pointed at the displaced SES-030 are deleted.
- The v0.5 follow-up SES-030 record is unaffected (still describes v0.5 work, which is correct).

Doug pulls locally; no further action required against this prompt.

**Next governance step (separate from this reconciliation):** the current status entity is misleading — it claims v0.6 slices A-E have shipped when in fact v0.6 build has not started. Update via the desktop versioned-replace dialog to reflect: v0.5 shipped + v0.6 build queued + slice A is next.

**Next build step (separate from this reconciliation):** begin v0.6 slice A via the prompt at `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-A-foundation.md`.
