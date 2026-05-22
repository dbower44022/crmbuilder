# CLAUDE-CODE-PROMPT-apply-close-out-ses-052

**Last Updated:** 05-22-26 14:30
**Operating mode:** DETAIL
**Series:** apply-close-out
**Status:** Ready to execute
**Companion payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_052.json`

---

## Purpose

Apply the SES-052 close-out payload to the CRMBUILDER engagement's database. Lands the SES-052 close_out_payload entity schema-design conversation's records (1 session, 6 decisions, 0 planning items, 7 references) so the next per-entity schema-design conversation can open against `PRDs/product/crmbuilder-v2/schema-design-kickoff-deposit-event.md` with the close_out_payload specification's cross-spec precedents and inherited posture recorded as decisions in the database.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-052 created with the close_out_payload-entity schema-design conversation's content (substantive artifacts: `governance-schema-specs/close_out_payload.md` at v1.0 (440 lines) committed at `87c7c16`; `crmbuilder/CLAUDE.md` Working conventions section committed at `536df25`; `ClevelandBusinessMentoring/CLAUDE.md` parallel Working conventions section committed at `00c0bda`).
- **Decisions.** Six decisions created — DEC-147 (COP identifier prefix and format), DEC-148 (content representation as file_path pointer only, no payload_content column; cross-spec precedent inherited from DEC-139 and DEC-145), DEC-149 (workflow-shaped lifecycle with five statuses, truly terminal terminals, applied-requires-edge realizing DEC-143's inverse-pattern precedent, supersession-requires-edge mirroring DEC-125, production-edge required at all statuses), DEC-150 (production-linkage via references-edge with new kind close_out_payload_produced_by_conversation; declines typed sequencing kind per DEC-133's frequency test), DEC-151 (eleven-column field inventory including four per-status lifecycle timestamps; declines kind enum and schema_version column), DEC-152 (standard API surface, default UI with Status filter combo addition, soft-delete posture distinct from cancelled lifecycle status and applied terminal status, sixteen acceptance criteria).
- **Planning items.** None. PI-022 (retroactive backfill, authored by SES-046) covers close_out_payload records implicitly as it does for the other governance entity types; PI-023 (workstream-state reconciliation utility) addresses an orthogonal concern. No new planning item from this conversation.
- **References.** Seven added — six `decided_in` (DEC-147..152 → SES-052) plus one `is_about` (SES-052 → PI-022).

All 14 records (1 session + 6 decisions + 7 references) should report `OK` from the apply script. None should `SKIP` — this is a fresh apply, not a reconciliation.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop and report if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes. The conversation's deliverables (the close_out_payload.md spec, the two CLAUDE.md edits, this payload, this apply prompt) should already be committed and pushed before this prompt runs; this prompt's commit is snapshot-regeneration only and starts from a clean state.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts. HEAD should be at or past the SES-052 close-out commit (which adds ses_052.json and this apply prompt; the spec and the two CLAUDE.md edits should already be on origin from earlier commits in the same conversation).

5. **Confirm payload file exists:**

   ```bash
   test -f PRDs/product/crmbuilder-v2/close-out-payloads/ses_052.json && echo "payload present" || echo "MISSING"
   ```

   Stop and report if missing.

6. **Confirm API is up:**

   ```bash
   curl -sf http://127.0.0.1:8765/health | jq .
   ```

   Should return `{"status": "ok", ...}`. If the API is not running, start it with `crmbuilder-v2-api &` and re-check.

7. **Capture pre-apply identifier heads** (envelope-unwrap discipline per the CLAUDE.md `{data, meta, errors}` note):

   ```bash
   curl -sf 'http://127.0.0.1:8765/sessions?limit=1&order=desc' | jq -r '.data[0].identifier'
   curl -sf 'http://127.0.0.1:8765/decisions?limit=1&order=desc' | jq -r '.data[0].identifier'
   curl -sf 'http://127.0.0.1:8765/planning-items?limit=1&order=desc' | jq -r '.data[0].identifier'
   ```

   Expected heads: SES-051, DEC-146, PI-023.

   If the heads are more advanced (e.g., SES-052 already present, or DEC-147+ already present), stop and report — this would indicate a prior partial apply that needs reconciliation before continuing.

   If the heads are less advanced (e.g., SES-050 head, DEC-140 head), some prior close-out has not yet been applied and must land before this one.

---

## Apply

Run the standard apply script against the payload:

```bash
uv run python crmbuilder-v2/scripts/apply_close_out.py \
  PRDs/product/crmbuilder-v2/close-out-payloads/ses_052.json
```

Expected behaviour:

- The script POSTs each section in fixed order: `session` → `decisions` → `planning_items` → `references`.
- All 1 session, 6 decisions, 0 planning items, and 7 references report `OK`.
- The script's idempotency guarantees that HTTP 409 conflicts are treated as already-present and continue; no SKIPs are expected on a fresh apply against the expected heads.
- The script internally unwraps the `{data, meta, errors}` envelope; no manual unwrap is needed.

If any record returns a non-OK, non-409 result, stop and report the full error response. Do not proceed to the post-apply verification or commit step.

---

## Post-apply verification

1. **Confirm post-apply identifier heads** advance to the expected values:

   ```bash
   curl -sf 'http://127.0.0.1:8765/sessions?limit=1&order=desc' | jq -r '.data[0].identifier'
   curl -sf 'http://127.0.0.1:8765/decisions?limit=1&order=desc' | jq -r '.data[0].identifier'
   ```

   Expected: SES-052, DEC-152. Planning-items head remains PI-023 (no new PI).

2. **Confirm reference count delta is +7:**

   ```bash
   curl -sf 'http://127.0.0.1:8765/references?include_meta=true' | jq '.meta.total_count'
   ```

   Should be 7 greater than the pre-apply count.

3. **Spot-check the SES-052 session record:**

   ```bash
   curl -sf 'http://127.0.0.1:8765/sessions/SES-052' | jq '.data | {identifier, title, status, session_date}'
   ```

   Should show `status: "Complete"`, `session_date: "05-22-26"`, title beginning "close_out_payload entity schema designed".

4. **Spot-check one decision record:**

   ```bash
   curl -sf 'http://127.0.0.1:8765/decisions/DEC-148' | jq '.data | {identifier, title, status}'
   ```

   Should show `status: "Active"`, title containing "file_path pointer only".

5. **Confirm `decided_in` references resolve correctly for one decision:**

   ```bash
   curl -sf 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-148' | jq '.data[] | select(.relationship == "decided_in") | {target_type, target_id}'
   ```

   Should return `{"target_type": "session", "target_id": "SES-052"}`.

---

## Commit snapshot regeneration

The apply script transactionally regenerates the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` (`sessions.json`, `decisions.json`, `planning_items.json`, `references.json`) as part of the write transaction. After verification passes, commit the snapshot regeneration as a single commit:

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export/ files changed
git diff --stat PRDs/product/crmbuilder-v2/db-export/
```

The diff should show four files modified with additions corresponding to SES-052 + DEC-147..152 + the 7 references.

```bash
git commit -m "v2: apply SES-052 — close_out_payload entity schema designed

Lands 1 session (SES-052), 6 decisions (DEC-147..152), 0 planning items,
7 references (6 decided_in + 1 is_about SES-052 -> PI-022).

Substantive artifacts from this conversation already on origin from
prior commits in the same conversation:
- governance-schema-specs/close_out_payload.md v1.0 at 87c7c16
- crmbuilder/CLAUDE.md Working conventions section at 536df25
- ClevelandBusinessMentoring/CLAUDE.md parallel section at 00c0bda

Next: deposit_event schema-design conversation (6th and final
per-entity conversation in the governance entity schema-design
workstream).
"
git push origin main
```

Stop and report if the diff includes files outside `PRDs/product/crmbuilder-v2/db-export/` — that would indicate snapshot drift from a prior unapplied close-out or an unrelated working-tree change.

---

## Done

Reply to Doug with: identifier heads before and after, the count of records applied at each section (1/6/0/7), the snapshot-regeneration commit SHA, and the next-conversation kickoff path (`PRDs/product/crmbuilder-v2/schema-design-kickoff-deposit-event.md`).
