# CLAUDE-CODE-PROMPT-apply-close-out-ses-054

**Last Updated:** 05-22-26 17:00
**Operating mode:** DETAIL
**Series:** apply-close-out
**Status:** Ready to execute
**Companion payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_054.json`

---

## Purpose

Apply the SES-054 close-out payload to the CRMBUILDER engagement's database. Lands the SES-054 deposit_event entity schema-design conversation's records (1 session, 6 decisions, 0 planning items, 7 references) so the **next workstream conversation** — the seventh and final build-planning conversation — can open against `PRDs/product/crmbuilder-v2/governance-schema-build-planning-kickoff.md` with the complete set of six schema specifications backed by their decisions in the database.

SES-054 is the **sixth and final per-entity schema-design conversation** of the governance-entity schema-design workstream. After this apply, all six governance entity schemas (workstream, conversation, reference_book, work_ticket, close_out_payload, deposit_event) are designed and their decisions are recorded; only the build-planning integration conversation remains in the workstream.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-054 created with the deposit_event-entity schema-design conversation's content (substantive artifacts: `governance-schema-specs/deposit_event.md` at v1.0 and `governance-schema-build-planning-kickoff.md` at v1.0, both committed in the same session-close commit).
- **Decisions.** Six decisions created — DEC-155 (DEP identifier prefix and format), DEC-156 (born-terminal append-only lifecycle with diagnostic log capture; **new cross-spec precedent: born-terminal append-only with creation as the event-recording moment** — a third lifecycle category alongside workflow-shaped and documentary), DEC-157 (references-table edges with one new generic-verb kind `deposit_event_wrote_record` spanning four target types; rejects per-target-type variants, JSON column, dedicated table, and target-side columns), DEC-158 (multi-event-per-payload; **new cross-spec precedent: born-terminal append-only entities admit multi-event-per-target-record**; relaxes close_out_payload's at-most-one default), DEC-159 (nine-column field inventory; `_outcome` over `_status`; declines `_notes`, `_updated_at`, `_deleted_at`, denormalized total count), DEC-160 (reduced API surface POST + GET only; read-only UI audit log with no Create/Edit/Delete dialogs; descending master-pane sort as documented audit-log deviation; fifteen acceptance criteria).
- **Planning items.** None. PI-022 (retroactive backfill, authored by SES-046) covers deposit_event records implicitly as it does for the other governance entity types. No new planning item from this conversation.
- **References.** Seven added — six `decided_in` (DEC-155..160 → SES-054) plus one `is_about` (SES-054 → PI-022).

All 14 records (1 session + 6 decisions + 0 planning items + 7 references) should report `OK` from the apply script. None should `SKIP` — this is a fresh apply, not a reconciliation.

**Cross-spec consistency finding surfaced by this conversation** (for awareness only — not addressed by this apply prompt): the close_out_payload spec's at-most-one inbound `deposit_event_applies_close_out_payload` edge default needs to be relaxed to zero-or-more, per Decision 4 of this conversation. The relaxation is the build-planning conversation's section 7.2 reconciliation responsibility per the kickoff's no-inline-amendment rule.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop and report if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes. The conversation's deliverables (the deposit_event.md spec, the build-planning kickoff, this payload, this apply prompt) should already be committed and pushed before this prompt runs; this prompt's commit is snapshot-regeneration only and starts from a clean state.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts. HEAD should be at or past the SES-054 close-out commit (which adds the spec, the build-planning kickoff, the payload, and this apply prompt — all four artifacts in one commit from the sandbox per the sandbox push convention).

5. **Confirm payload file exists:**

   ```bash
   test -f PRDs/product/crmbuilder-v2/close-out-payloads/ses_054.json && echo "payload present" || echo "MISSING"
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

   Expected heads: **SES-053, DEC-154, PI-023**.

   If the heads are more advanced (e.g., SES-054 already present, or DEC-155+ already present), stop and report — this would indicate a prior partial apply that needs reconciliation before continuing.

   If the heads are less advanced (e.g., SES-052 head, DEC-152 head), some prior close-out has not yet been applied and must land before this one.

---

## Apply

Run the standard apply script against the payload:

```bash
uv run python crmbuilder-v2/scripts/apply_close_out.py \
  PRDs/product/crmbuilder-v2/close-out-payloads/ses_054.json
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

   Expected: **SES-054, DEC-160**. Planning-items head remains **PI-023** (no new PI).

2. **Confirm reference count delta is +7:**

   ```bash
   curl -sf 'http://127.0.0.1:8765/references?include_meta=true' | jq '.meta.total_count'
   ```

   Should be 7 greater than the pre-apply count.

3. **Spot-check the SES-054 session record:**

   ```bash
   curl -sf 'http://127.0.0.1:8765/sessions/SES-054' | jq '.data | {identifier, title, status, session_date}'
   ```

   Should show `status: "Complete"`, `session_date: "05-22-26"`, title beginning "deposit_event entity schema designed".

4. **Spot-check one decision record (DEC-156 — the primary architectural decision):**

   ```bash
   curl -sf 'http://127.0.0.1:8765/decisions/DEC-156' | jq '.data | {identifier, title, status}'
   ```

   Should show `status: "Active"`, title containing "born-terminal append-only".

5. **Confirm `decided_in` references resolve correctly for one decision:**

   ```bash
   curl -sf 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-156' | jq '.data[] | select(.relationship == "decided_in") | {target_type, target_id}'
   ```

   Should return `{"target_type": "session", "target_id": "SES-054"}`.

---

## Commit snapshot regeneration

The apply script transactionally regenerates the JSON snapshots under `PRDs/product/crmbuilder-v2/db-export/` (`sessions.json`, `decisions.json`, `planning_items.json`, `references.json`) as part of the write transaction. After verification passes, commit the snapshot regeneration as a single commit:

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export/ files changed
git diff --stat PRDs/product/crmbuilder-v2/db-export/
```

The diff should show four files modified with additions corresponding to SES-054 + DEC-155..160 + the 7 references.

```bash
git commit -m "v2: apply SES-054 — deposit_event entity schema designed; governance schema-design workstream concluded

Lands 1 session (SES-054), 6 decisions (DEC-155..160), 0 planning items,
7 references (6 decided_in + 1 is_about SES-054 -> PI-022).

Sixth and final per-entity schema-design conversation in the
governance-entity schema-design workstream. Establishes two new
cross-spec precedents: (1) born-terminal append-only with creation
as the event-recording moment (a third lifecycle category alongside
workflow-shaped and documentary), (2) born-terminal append-only
entities admit multi-event-per-target-record. Surfaces one cross-spec
consistency finding for the build-planning conversation's section
7.2 reconciliation: close_out_payload at-most-one inbound edge
default relaxes to zero-or-more per DEC-158.

Substantive artifacts from this conversation already on origin from
the session-close commit:
- governance-schema-specs/deposit_event.md v1.0
- governance-schema-build-planning-kickoff.md v1.0

Next: build-planning conversation. Kickoff at
PRDs/product/crmbuilder-v2/governance-schema-build-planning-kickoff.md.
The build-planning conversation consumes all six governance schema
specifications and produces the integrating Product Requirements
Document, implementation plan, per-slice Claude Code build prompts,
and PI-022 refinement. Schema-design phase of the workstream is now
complete.
"
git push origin main
```

Stop and report if the diff includes files outside `PRDs/product/crmbuilder-v2/db-export/` — that would indicate snapshot drift from a prior unapplied close-out or an unrelated working-tree change.

---

## Done

Reply to Doug with: identifier heads before and after, the count of records applied at each section (1/6/0/7), the snapshot-regeneration commit SHA, and the next-conversation kickoff path (`PRDs/product/crmbuilder-v2/governance-schema-build-planning-kickoff.md`).
