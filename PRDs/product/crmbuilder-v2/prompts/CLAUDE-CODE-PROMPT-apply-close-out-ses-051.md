# CLAUDE-CODE-PROMPT-apply-close-out-ses-051

**Last Updated:** 05-21-26 23:30
**Operating mode:** DETAIL
**Series:** apply-close-out
**Status:** Ready to execute
**Companion payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_051.json`

---

## Purpose

Apply the SES-051 close-out payload to the CRMBUILDER engagement's database. Lands the SES-051 work_ticket entity schema-design conversation's records (1 session, 6 decisions, 0 planning items, 7 references) so the next per-entity schema-design conversation can open against `PRDs/product/crmbuilder-v2/schema-design-kickoff-close-out-payload.md` with the work_ticket specification's cross-spec precedents and inherited posture (references-edge for parent-child relationships, per-status lifecycle timestamps for workflow-shaped lifecycles, terminal-states-are-terminal discipline, typed-sequencing-frequency-justified introduction, documentary-shape-base-timestamps-only deviation, and the new terminal-state-consumption-requires-inbound-edge precedent established by this conversation) recorded as decisions in the database.

**Audit-and-adopt note.** SES-051 is the audit-and-adopt close-out for the work_ticket schema-design conversation. The deliverable (`governance-schema-specs/work_ticket.md`, 471 lines at v1.0) was present in the local Claude.ai sandbox at session open as an untracked file — authored by a prior sandbox session whose work product was never committed to origin/main. SES-051 audited that draft against the schema spec guide §7.1 completeness gate, the §6 cross-spec consistency requirements, the workstream master plan position-4-of-6 constraints, DEC-117's family-2 classification, and the predecessor specs' (workstream.md, conversation.md, reference_book.md) declarations the spec relies on. The audit concluded the draft is substantively complete and methodologically disciplined; no content changes were required. The draft was adopted as v1.0, committed to origin/main, and this close-out payload and apply prompt authored. The session record's `topics_covered` captures the audit-and-adopt posture honestly. Doug's explicit conversation-opening instruction was to process the entire prompt autonomously using default decisions and not ask for feedback until completion — the audit-and-adopt outcome is the natural application of that directive against a substantively complete pre-existing draft.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-051 created with the work_ticket-entity schema-design conversation's content (one substantive artifact: `governance-schema-specs/work_ticket.md`, 471 lines at v1.0 committed by SES-051).
- **Decisions.** Six decisions created — DEC-141 (WT identifier prefix and format), DEC-142 (boundary discipline with reference_book — intent-at-creation classification, no in-place re-categorization, file_path may coexist across both tables), DEC-143 (workflow-shaped lifecycle with five statuses, truly-terminal terminals, consumed-requires-edge rule establishing new cross-spec precedent, supersession-requires-edge rule), DEC-144 (single-use enforcement rule — at most one inbound consumption edge per work_ticket regardless of status), DEC-145 (field inventory with four per-status lifecycle timestamps; declines tentative `work_ticket_consumed_by_conversation` kind; declines typed `work_ticket_reads_reference_book` kind), DEC-146 (API surface; default UI with Kind column and Status filter combo; soft-delete posture; closed four-value kind enum; sixteen acceptance criteria).
- **Planning items.** None. PI-022 (retroactive backfill, authored by SES-046) covers this conversation's records implicitly; PI-023 (workstream-state reconciliation utility, applied at commit 31e7afa) addresses the class of state-drift question raised in SES-050's close-out. No new planning item.
- **References.** Seven added — six `decided_in` (DEC-141..146 → SES-051) plus one `is_about` (SES-051 → PI-022).

All 14 records (1 session + 6 decisions + 7 references) should report `OK` from the apply script. None should `SKIP` — this is a fresh apply, not a reconciliation.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop and report if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes. The conversation's deliverables (the work_ticket.md spec, this payload, this apply prompt) should already be committed and pushed before this prompt runs; this prompt's commit is snapshot-regeneration only and starts from a clean state.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts. HEAD should be at or past the SES-051 close-out commit (which adds work_ticket.md + this payload + this apply prompt).

5. **Confirm payload file exists:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_051.json
   ```

   Stop if missing.

6. **Confirm the v2 API is running and routed at CRMBUILDER.** Two checks:

   **6a — API up:**

   ```bash
   curl -sf http://127.0.0.1:8765/sessions >/dev/null && echo "API up" || echo "API DOWN"
   ```

   If the API is down, start it:

   ```bash
   fuser -k 8765/tcp 2>/dev/null
   cd crmbuilder-v2
   uv run crmbuilder-v2-api --engagement CRMBUILDER &
   cd ..
   sleep 2
   curl -sf http://127.0.0.1:8765/sessions >/dev/null && echo "API now up" || echo "STILL DOWN"
   ```

   Stop and report if the API still does not come up.

   **6b — API routed at CRMBUILDER (not the empty v2.db or another engagement):**

   ```bash
   curl -s http://127.0.0.1:8765/sessions | python3 -c "
   import sys, json
   data = json.load(sys.stdin)['data']
   if not data:
       print('STOP — API is routed at an empty database. Restart per step 6a.')
   else:
       count = len(data)
       latest = sorted(r['identifier'] for r in data)[-1]
       print(f'API routed correctly: {count} sessions, latest {latest}')
   "
   ```

   Expected: at least 50 sessions returned, latest identifier SES-050 (the predecessor reference_book-entity schema-design conversation, which SES-051 follows). If the count is less than 50 or the latest is not SES-050, the API is misrouted or SES-050 has not yet been applied; stop and re-run step 6a or apply SES-050 first.

7. **Verify SES-051, DEC-141..146 are uncontested and prerequisites are in place** (TOCTOU mitigation per the SES-036 reconciliation precedent):

   ```bash
   # SES-051 must not yet exist
   curl -sf http://127.0.0.1:8765/sessions/SES-051 >/dev/null 2>&1 && echo "SES-051 ALREADY EXISTS — STOP" || echo "SES-051 available"

   # Each new decision identifier must not yet exist
   for id in DEC-141 DEC-142 DEC-143 DEC-144 DEC-145 DEC-146; do
     curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null 2>&1 && echo "$id ALREADY EXISTS — STOP" || echo "$id available"
   done

   # PI-022 must exist (foreign-key target for the SES-051 is_about reference)
   curl -sf http://127.0.0.1:8765/planning-items/PI-022 >/dev/null 2>&1 && echo "PI-022 exists — reference target valid" || echo "PI-022 MISSING — STOP and apply SES-046 first"
   ```

   Expected: "SES-051 available", six lines of "DEC-14X available", and "PI-022 exists — reference target valid". Any other output: stop and report.

8. **Capture pre-state for verification.**

   ```bash
   curl -s http://127.0.0.1:8765/sessions       | python3 -c "import sys, json; print('Pre-state sessions:',       len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/decisions      | python3 -c "import sys, json; print('Pre-state decisions:',      len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Pre-state planning items:', len(json.load(sys.stdin)['data']))"
   curl -s http://127.0.0.1:8765/references     | python3 -c "import sys, json; print('Pre-state references:',     len(json.load(sys.stdin)['data']))"
   ```

   Note the four values. Post-state should be exactly +1 sessions / +6 decisions / +0 planning items / +7 references.

---

## Workflow

### Step 1 — Apply SES-051 payload

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_051.json
cd ..
```

Expected output:

- SES-051 reports `OK` (created).
- DEC-141 through DEC-146 each report `OK` (created). Six lines.
- Six `decided_in` references (DEC-141..146 → SES-051) each report `OK` (created). Six lines.
- One `is_about` reference (SES-051 → PI-022) reports `OK` (created).
- Script exits 0.

Total: 14 `OK` lines. Zero `SKIP` lines. Zero non-`OK` lines.

Stop and report if any record returns `SKIP` or a status other than `OK`, or if the script exits non-zero.

### Step 2 — Verify created records

```bash
echo "--- Session ---"
curl -sf http://127.0.0.1:8765/sessions/SES-051 >/dev/null && echo "SES-051 OK" || echo "SES-051 MISSING"

echo "--- Decisions ---"
for id in DEC-141 DEC-142 DEC-143 DEC-144 DEC-145 DEC-146; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

echo "--- References ---"
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
expected = [
    ('DEC-141', 'SES-051', 'decided_in'),
    ('DEC-142', 'SES-051', 'decided_in'),
    ('DEC-143', 'SES-051', 'decided_in'),
    ('DEC-144', 'SES-051', 'decided_in'),
    ('DEC-145', 'SES-051', 'decided_in'),
    ('DEC-146', 'SES-051', 'decided_in'),
    ('SES-051', 'PI-022',  'is_about'),
]
for src, tgt, kind in expected:
    found = any(r['source_id']==src and r['target_id']==tgt and r['relationship']==kind for r in refs)
    print(f'{src} -> {tgt} {kind}: {found}')
"
```

All seven checks should report `OK` / `True`. Stop and report any `MISSING` or `False`.

### Step 3 — Verify post-state counts

```bash
curl -s http://127.0.0.1:8765/sessions       | python3 -c "import sys, json; print('Post-state sessions:',       len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/decisions      | python3 -c "import sys, json; print('Post-state decisions:',      len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys, json; print('Post-state planning items:', len(json.load(sys.stdin)['data']))"
curl -s http://127.0.0.1:8765/references     | python3 -c "import sys, json; print('Post-state references:',     len(json.load(sys.stdin)['data']))"
```

Deltas from pre-state should be exactly **+1 sessions / +6 decisions / +0 planning items / +7 references**. Stop and report any other delta.

### Step 4 — Verify snapshot regeneration

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications:

- `sessions.json` — SES-051 added
- `decisions.json` — DEC-141, DEC-142, DEC-143, DEC-144, DEC-145, DEC-146 added
- `references.json` — 7 entries added (6 decided_in plus 1 is_about)
- `change_log.json` — corresponding append entries

`planning_items.json` should NOT be modified (no new planning items in this payload).

If `git status` shows no changes in `db-export/`, the snapshot may have written to a wrong location. Run:

```bash
find . -name "sessions.json" -newer PRDs/product/crmbuilder-v2/close-out-payloads/ses_051.json 2>/dev/null
```

Report whatever path turned up; Doug will copy the snapshots to the correct location before commit.

### Step 5 — Commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply SES-051 — work_ticket entity schema designed (audit-and-adopt)

Lands the SES-051 work_ticket-entity schema-design conversation's records
to the CRMBUILDER engagement database:

- 1 session: SES-051 (work_ticket entity schema designed; fourth
  per-entity governance schema specification produced — audit-and-adopt
  posture because the v1.0 spec was authored by a prior Claude.ai
  sandbox session as an untracked file and never committed; SES-051
  audited the draft against the schema spec guide, the workstream
  master plan, and the predecessor specs, adopted the draft as v1.0
  without content changes, committed it to origin/main, and authored
  this close-out)
- 6 decisions:
  - DEC-141 (WT identifier prefix and format; two-letter form per
    DEC-123/DEC-135 precedent; no collision with WS in second character
    or with remaining-two working prefixes COP/DEP)
  - DEC-142 (boundary discipline with reference_book — intent-at-creation
    classification, no in-place re-categorization, file_path may coexist
    as work_ticket_file_path and reference_book_file_path across the two
    tables; uniqueness is per-table not cross-table)
  - DEC-143 (workflow-shaped lifecycle with five statuses, truly-terminal
    terminals, supersession-requires-edge rule inherited from DEC-125,
    and NEW cross-spec precedent — consumed-requires-edge rule: terminal-
    state consumption requires the inbound consumption edge, the inverse-
    direction analogue of supersession-requires-edge, applicable to
    close_out_payload's anticipated applied terminal)
  - DEC-144 (single-use enforcement rule — at most one inbound
    conversation_opens_against_work_ticket edge per work_ticket, regardless
    of status; the schema-level realization of DEC-117's family-2
    definition)
  - DEC-145 (field inventory with eleven columns including four per-status
    lifecycle timestamps for workflow-shape per DEC-126; declines the
    tentative work_ticket_consumed_by_conversation kind named by
    conversation.md \xC2\xA73.3.2 as redundant; declines the typed
    work_ticket_reads_reference_book kind per DEC-133 frequency-justified
    test in favour of the generic references kind)
  - DEC-146 (standard 8-endpoint API with ?kind= and ?status= filters,
    no version-management sub-endpoints because single-use; master-pane
    Kind column as third column and Status filter combo in toolbar;
    default soft-delete with restore; closed four-value kind enum
    [kickoff_prompt, claude_code_prompt, ad_hoc_prompt, other];
    sixteen acceptance criteria)
- 0 planning items: PI-022 (retroactive backfill, authored by SES-046)
  covers this conversation's records implicitly; PI-023 (workstream-state
  reconciliation utility, applied at 31e7afa) covers the state-drift
  question raised in SES-050's close-out
- 7 references: 6 decided_in (DEC-141..146 -> SES-051) plus 1 is_about
  (SES-051 -> PI-022)

Snapshot regeneration only — payload file is unchanged. The schema
specification deliverable (governance-schema-specs/work_ticket.md,
471 lines at v1.0) was committed separately during SES-051.

Next step after this apply lands: open a fresh Claude.ai conversation
against PRDs/product/crmbuilder-v2/schema-design-kickoff-close-out-payload.md.
That conversation designs the close_out_payload entity schema as the
fifth of six per-entity conversations in the workstream, inheriting
six cross-spec precedents — the three from workstream (references-edge
over foreign-key, per-status lifecycle timestamps for workflow-shaped
lifecycles, terminal-states-are-terminal), the one from conversation
(typed sequencing edges introduced when entity-family frequency
justifies), the one from reference_book (documentary-shaped lifecycles
inherit base timestamps only), plus the one new precedent from this
conversation (terminal-state consumption requires the inbound consumption
edge)."
```

### Step 6 — Push

```bash
git push origin main
```

Stop and report if push fails.

---

## Done

After Step 6 completes, the SES-051 close-out has fully landed:

- 14 records (1 session + 6 decisions + 7 references) live in the CRMBUILDER engagement database.
- Snapshot files regenerated and committed.
- The work_ticket entity schema is recorded with its decisions; the close_out_payload entity schema-design conversation can open.

**Next step:** open a fresh Claude.ai conversation against `PRDs/product/crmbuilder-v2/schema-design-kickoff-close-out-payload.md`. That conversation designs the close_out_payload entity schema as the fifth of six per-entity conversations in the workstream.

**Cross-spec precedents now in force, inherited by the remaining two schema-design conversations:**

- References-edge over foreign-key for parent-child governance relationships (DEC-124 from SES-048; reinforced by DEC-130 from SES-049 and DEC-139 from SES-050; reinforced again by the work_ticket spec's all-relationships-in-refs posture).
- Per-status lifecycle timestamps for workflow-shaped governance lifecycles (DEC-126 from SES-048; extended by DEC-131 from SES-049 from four columns to six; scope clarified by DEC-137 from SES-050 to apply only to workflow-shaped lifecycles; reinforced by DEC-143 from this conversation applying it on work_ticket's workflow-shaped facts with four per-status columns).
- Terminal-states-are-terminal discipline for governance entities (DEC-125 from SES-048; inherited verbatim by DEC-131, DEC-137, and DEC-143).
- Typed sequencing edges introduced when entity-family frequency justifies (DEC-133 from SES-049; applied by reference_book spec and by work_ticket spec to defer typed sequencing and typed read-list kinds per the same frequency test).
- Documentary-shaped lifecycles inherit base timestamps only (DEC-137 from SES-050; applied by work_ticket spec which confirms it is workflow-shaped, not documentary, and applies per-status timestamps per DEC-126 instead).
- **NEW** — Terminal-state consumption requires the inbound consumption edge (DEC-143 from this conversation; the consumed-requires-edge rule is the inverse-direction analogue of supersession-requires-edge from DEC-125; generalizes to any governance entity with a terminal state defined by an external act of consumption or application, where the inbound edge naming the consumer or applier is required to be present; close_out_payload's anticipated `applied` terminal is the next case).

**Vocabulary additions named by this spec, aggregated by the build-planning conversation:**

- `REFERENCE_RELATIONSHIPS` — **none** new (every inbound and outbound edge was pre-declared by `conversation.md` or is admitted by the existing generic `references` / `is_about` / `supersedes` kinds).
- `ENTITY_TYPES` — already lists `work_ticket` per `conversation.md` section 3.3.4's additions table; affirmed.
- `_kinds_for_pair` — no new clauses required from this spec; the existing clauses (the conversation→work_ticket clause from `conversation.md`, the same-type rule for `supersedes`, and the defaults for generic `references` / `is_about`) cover every relationship work_ticket needs.
- No matching Alembic migration on `refs.relationship_kind`'s CHECK constraint from this spec.

The work_ticket spec is the second of the six governance entity specs to require no new relationship-kind vocabulary additions (reference_book was the first).

**Tentative kind names flagged for build-planning reconciliation:**

- `work_ticket_consumed_by_conversation` (named tentatively by conversation.md §3.3.2 as an inbound-from-work_ticket-perspective candidate) — **declined** by this conversation per DEC-145. The existing outbound `conversation_opens_against_work_ticket` from conversation.md is the sole canonical edge for the relationship; introducing a parallel inbound name would break the one-edge-per-relationship pattern enforced by source-first naming (DEC-048). Build-planning has no action on this; the decline is final.
- `work_ticket_reads_reference_book` (mentioned as a candidate for the kickoff-prompt read-list citation pattern) — **declined** by this conversation per DEC-145 in application of DEC-133's frequency-justified test. The generic `references` kind covers read-list citations adequately. Build-planning has no action on this in the build planning conversation; if the typed kind is later warranted, a future release adds it.

**PI-022 discharge condition unchanged:** still open; the build-planning conversation decides the resolution path (go-forward only, selective backfill, or full backfill with reconstructed outcomes) and executes (if backfill is chosen). This conversation adds new backfill-pass scope items per spec section 3.8.2 — which historical files become work_ticket records, the methodology workstream master-plan boundary case (resolves as a work_ticket per DEC-142), handling of conversations whose kickoff is missing or unrecoverable, and policy for historical multi-consumer files against the single-use enforcement rule.

---

## Error handling

- **Standard apply script exits non-zero on a non-409 error.** Stop, do not commit, report the full script output to Doug. Most likely causes: API not running, API misrouted, payload file malformed, or a validation error at the API layer (for example, foreign-key target PI-022 missing).

- **One or more `OK`-expected records returns `SKIP` (409 conflict).** This means a record with the same identifier already exists. Stop and report which identifiers conflicted. The pre-flight TOCTOU check should have caught this; a `SKIP` here indicates either a race (unlikely on a single-operator machine) or an inconsistent pre-flight state.

- **Snapshot not regenerated.** The export hook in the access layer may have failed silently. Stop, do not commit. Check the API server logs for errors during snapshot regeneration.

- **Pre-state already past SES-051.** If `Latest SES` from the pre-flight is already `SES-051` or later, the work has already been applied. Report this finding; do not run the apply again (still safe given idempotency, but unnecessary). No commit needed if pre-state already past.

- **Pre-state earlier than SES-050.** If `Latest SES` from the pre-flight is `SES-049` or earlier, the prerequisite reference_book-entity schema-design conversation's records have not landed. Stop and report — SES-050 must apply first.

- **`git status` not clean at start.** Stop and report. Do not stash. Doug decides how to handle the uncommitted changes before re-running.

- **`git pull --rebase` reports conflicts.** Stop and report. The work_ticket.md commit and the SES-051 close-out payload + apply-prompt commit should both be on origin/main by the time this prompt runs; if rebase conflicts surface, something diverged between the close-out commits and the apply.

---

## What this prompt does NOT do

- Does not modify the payload file. It is a read-only input.
- Does not modify the apply script. The script is generic; per-payload variation is in the payload file.
- Does not author additional decisions, planning items, or sessions beyond what the payload file contains. If something is missing from the payload, fix the payload first and re-author it; do not work around in this prompt.
- Does not register any vocabulary additions. The work_ticket spec is the second of the six governance entity specs (after reference_book) to require zero new relationship-kind vocabulary — every needed edge was pre-declared by conversation.md or admitted by existing generic kinds. The build-planning conversation aggregates this nil contribution into its consolidated vocab.py update without action.
- Does not create the `work_tickets` table or any access-layer methods. Those are built from the schema specification during the build phase, which is a separate workstream conversation later (the build-planning conversation, conversation 7 of the governance workstream).
- Does not modify any spec, plan, or methodology document. The only files touched are under `PRDs/product/crmbuilder-v2/db-export/` (snapshot regeneration).
- Does not open the next schema-design conversation (close_out_payload entity). That is a separate fresh Claude.ai chat Doug opens against `schema-design-kickoff-close-out-payload.md` after this apply lands.

---

*End of prompt.*
