# CLAUDE-CODE-PROMPT-apply-close-out-ses-053

**Last Updated:** 05-22-26 22:00
**Operating mode:** DETAIL
**Series:** apply-close-out
**Status:** Ready to execute
**Companion payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_053.json`

---

## Purpose

Apply the SES-053 close-out payload to the CRMBUILDER engagement's database. Lands the SES-053 records (1 session, 2 decisions, 0 planning items, 2 references) so the next Claude.ai conversation — drafting `app-yaml-schema.md` v1.2 Category 6 sections per `PRDs/product/UPDATE-PROMPT-yaml-schema-v1.2-category-6.md` — opens with the Category 6 reordering decisions recorded as governance database entries.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-053 created. Substantive artifacts from this conversation already on origin from prior commits in the same conversation: gap-analysis Section 6 amendment at `eb1d7e7`; UPDATE-PROMPT initial commit at `f152181`; UPDATE-PROMPT SHA correction at `4ff2e43`.
- **Decisions.** Two decisions created — DEC-153 (YAML security scope is definitions only; user-to-role and user-to-team assignments are runtime data managed in the target CRM UI, not in YAML) and DEC-154 (Category 6 reordered: v1.2 ships scope-level entity access + teams + system permissions + panel/layout role-aware visibility as Parts A–E; v1.3 ships the deferred field-level permissions and permission presets).
- **Planning items.** None. The next-conversation kickoff (UPDATE-PROMPT for v1.2 Category 6 drafting) is committed as a work artifact at `f152181` / `4ff2e43`; no deferred open question from this conversation warrants durable tracking as a PI.
- **References.** Two added — both `decided_in` (DEC-153 → SES-053 and DEC-154 → SES-053).

All 5 records (1 session + 2 decisions + 2 references) should report `OK` from the apply script. None should `SKIP` — this is a fresh apply, not a reconciliation.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop and report if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes. The conversation's deliverables (gap-analysis amendment, UPDATE-PROMPT, SHA fix, this payload, this apply prompt) should already be committed and pushed before this prompt runs; this prompt's commit is snapshot-regeneration only and starts from a clean state.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts. HEAD should be at or past the SES-053 close-out commit (which adds `ses_053.json` and this apply prompt; the three substantive commits — `eb1d7e7`, `f152181`, `4ff2e43` — should already be on origin from earlier in the same conversation).

5. **Confirm payload file exists:**

   ```bash
   test -f PRDs/product/crmbuilder-v2/close-out-payloads/ses_053.json && echo "payload present" || echo "MISSING"
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

   Expected heads: **SES-052, DEC-152, PI-023**.

   If the heads are more advanced (e.g., SES-053 already present, or DEC-153+ already present), stop and report — this would indicate a prior partial apply that needs reconciliation before continuing.

   If the heads are less advanced (e.g., SES-051 head, DEC-146 head), some prior close-out has not yet been applied and must land before this one.

---

## Apply

Run the standard apply script against the payload:

```bash
uv run python crmbuilder-v2/scripts/apply_close_out.py \
  PRDs/product/crmbuilder-v2/close-out-payloads/ses_053.json
```

Expected behaviour:

- The script POSTs each section in fixed order: `session` → `decisions` → `planning_items` → `references`.
- All 1 session, 2 decisions, 0 planning items, and 2 references report `OK`.
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

   Expected: **SES-053, DEC-154**. Planning-items head remains PI-023 (no new PI).

2. **Confirm reference count delta is +2:**

   ```bash
   curl -sf 'http://127.0.0.1:8765/references?include_meta=true' | jq '.meta.total_count'
   ```

   Should be 2 greater than the pre-apply count.

3. **Spot-check the SES-053 session record:**

   ```bash
   curl -sf 'http://127.0.0.1:8765/sessions/SES-053' | jq '.data | {identifier, title, status, session_date}'
   ```

   Should show `status: "Complete"`, `session_date: "05-22-26"`, title beginning "YAML schema Category 6 (Role-Based Access Control) reordered".

4. **Spot-check one decision record:**

   ```bash
   curl -sf 'http://127.0.0.1:8765/decisions/DEC-154' | jq '.data | {identifier, title, status}'
   ```

   Should show `status: "Active"`, title containing "Category 6 reordering" and "v1.2" and "v1.3".

5. **Confirm `decided_in` references resolve correctly for one decision:**

   ```bash
   curl -sf 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-154' | jq '.data[] | select(.relationship == "decided_in") | {target_type, target_id}'
   ```

   Should return `{"target_type": "session", "target_id": "SES-053"}`.

---

## Commit snapshot regeneration

The apply script transactionally regenerates the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` (`sessions.json`, `decisions.json`, `planning_items.json`, `references.json`) as part of the write transaction. After verification passes, commit the snapshot regeneration as a single commit:

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export/ files changed
git diff --stat PRDs/product/crmbuilder-v2/db-export/
```

The diff should show three files modified (`sessions.json`, `decisions.json`, `references.json`) with additions corresponding to SES-053 + DEC-153 + DEC-154 + the 2 references. The `planning_items.json` snapshot should be unchanged (no new PI from this close-out).

```bash
git commit -m "v2: apply SES-053 — YAML schema Category 6 reordered across v1.2 and v1.3

Lands 1 session (SES-053), 2 decisions (DEC-153, DEC-154), 0 planning
items, 2 references (both decided_in).

Substantive artifacts from this conversation already on origin from
prior commits in the same conversation:
- PRDs/product/yaml-schema-gap-analysis-MR-pilot.md Section 6 amendment
  at eb1d7e7 (Option C reordering applied to gap-analysis Section 6)
- PRDs/product/UPDATE-PROMPT-yaml-schema-v1.2-category-6.md initial
  commit at f152181 (next-conversation kickoff for app-yaml-schema.md
  v1.2 Category 6 drafting)
- UPDATE-PROMPT SHA correction at 4ff2e43 (post-rebase fix to stale
  predecessor-commit reference)

Next: app-yaml-schema.md v1.2 sections drafting per the committed
UPDATE-PROMPT (path PRDs/product/UPDATE-PROMPT-yaml-schema-v1.2-category-6.md)."
git push origin main
```

Stop and report if the diff includes files outside `PRDs/product/crmbuilder-v2/db-export/` — that would indicate snapshot drift from a prior unapplied close-out or an unrelated working-tree change.

---

## Done

Reply to Doug with: identifier heads before and after, the count of records applied at each section (1/2/0/2), the snapshot-regeneration commit SHA, and the next-conversation kickoff path (`PRDs/product/UPDATE-PROMPT-yaml-schema-v1.2-category-6.md`).
