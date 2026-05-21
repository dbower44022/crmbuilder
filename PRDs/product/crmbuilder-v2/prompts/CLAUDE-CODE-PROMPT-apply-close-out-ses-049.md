# CLAUDE-CODE-PROMPT-apply-close-out-ses-049

**Last Updated:** 05-21-26 06:30
**Operating mode:** DETAIL
**Series:** apply-close-out
**Status:** Ready to execute
**Companion payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_049.json`

---

## Purpose

Apply the SES-049 close-out payload to the CRMBUILDER engagement's database. Lands the SES-049 conversation-entity schema-design conversation's records (1 session, 6 decisions, 0 planning items, 7 references) so the next per-entity schema-design conversation can open against `PRDs/product/crmbuilder-v2/schema-design-kickoff-reference-book.md` with the conversation specification's cross-spec precedents and inherited posture (references-edge for parent-child relationships, per-status lifecycle timestamps for workflow-shaped lifecycles, terminal-states-are-terminal discipline, and the new typed-sequencing-frequency-justified precedent established by this conversation) recorded as decisions in the database.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-049 created with the conversation-entity schema-design conversation's content (one substantive artifact: `governance-schema-specs/conversation.md`, 459 lines, committed at `6580a32` during the conversation).
- **Decisions.** Six decisions created — DEC-129 (CONV identifier prefix), DEC-130 (conversation-to-session via references-table edge per the SES-048 precedent; new kind `conversation_records_session`), DEC-131 (seven-status lifecycle with truly terminal terminals, forward-only planning lifecycle, complete-requires-session-edge and supersession-requires-edge rules), DEC-132 (conversation-to-kickoff via references-table edge with tentative new kind `conversation_opens_against_work_ticket`), DEC-133 (`conversation_succeeds_conversation` introduced for predecessor-successor chaining; new cross-spec precedent that typed sequencing edges are introduced when entity-family frequency justifies), DEC-134 (field inventory, list-endpoint filters, master-pane Workstream column, soft-delete posture, eighteen acceptance criteria).
- **Planning items.** None. PI-022 (retroactive backfill, authored by SES-046) covers this conversation's records implicitly; no new planning item.
- **References.** Seven added — six `decided_in` (DEC-129..134 → SES-049) plus one `is_about` (SES-049 → PI-022).

All 14 records (1 session + 6 decisions + 7 references) should report `OK` from the apply script. None should `SKIP` — this is a fresh apply, not a reconciliation.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop and report if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes. The conversation's deliverable (`governance-schema-specs/conversation.md`) was already committed at `6580a32` during the conversation; this prompt's commit is snapshot-regeneration only and starts from a clean state.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts. HEAD should be at or past `6580a32` (the conversation.md commit) plus the subsequent commit of this payload and prompt.

5. **Confirm payload file exists:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_049.json
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

   Expected: at least 48 sessions returned, latest identifier SES-048 (the predecessor workstream schema-design conversation, which SES-049 follows). If the count is less than 48 or the latest is not SES-048, the API is misrouted or SES-048 has not yet been applied; stop and re-run step 6a or apply SES-048 first.

7. **Verify SES-049, DEC-129..134 are uncontested and prerequisites are in place** (TOCTOU mitigation per the SES-036 reconciliation precedent):

   ```bash
   # SES-049 must not yet exist
   curl -sf http://127.0.0.1:8765/sessions/SES-049 >/dev/null 2>&1 && echo "SES-049 ALREADY EXISTS — STOP" || echo "SES-049 available"

   # Each new decision identifier must not yet exist
   for id in DEC-129 DEC-130 DEC-131 DEC-132 DEC-133 DEC-134; do
     curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null 2>&1 && echo "$id ALREADY EXISTS — STOP" || echo "$id available"
   done

   # PI-022 must exist (foreign-key target for the SES-049 is_about reference)
   curl -sf http://127.0.0.1:8765/planning-items/PI-022 >/dev/null 2>&1 && echo "PI-022 exists — reference target valid" || echo "PI-022 MISSING — STOP and apply SES-046 first"
   ```

   Expected: "SES-049 available", six lines of "DEC-12X / DEC-13X available", and "PI-022 exists — reference target valid". Any other output: stop and report.

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

### Step 1 — Apply SES-049 payload

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_049.json
cd ..
```

Expected output:

- SES-049 reports `OK` (created).
- DEC-129 through DEC-134 each report `OK` (created). Six lines.
- Six `decided_in` references (DEC-129..134 → SES-049) each report `OK` (created). Six lines.
- One `is_about` reference (SES-049 → PI-022) reports `OK` (created).
- Script exits 0.

Total: 14 `OK` lines. Zero `SKIP` lines. Zero non-`OK` lines.

Stop and report if any record returns `SKIP` or a status other than `OK`, or if the script exits non-zero.

### Step 2 — Verify created records

```bash
echo "--- Session ---"
curl -sf http://127.0.0.1:8765/sessions/SES-049 >/dev/null && echo "SES-049 OK" || echo "SES-049 MISSING"

echo "--- Decisions ---"
for id in DEC-129 DEC-130 DEC-131 DEC-132 DEC-133 DEC-134; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

echo "--- References ---"
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
expected = [
    ('DEC-129', 'SES-049', 'decided_in'),
    ('DEC-130', 'SES-049', 'decided_in'),
    ('DEC-131', 'SES-049', 'decided_in'),
    ('DEC-132', 'SES-049', 'decided_in'),
    ('DEC-133', 'SES-049', 'decided_in'),
    ('DEC-134', 'SES-049', 'decided_in'),
    ('SES-049', 'PI-022',  'is_about'),
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

- `sessions.json` — SES-049 added
- `decisions.json` — DEC-129, DEC-130, DEC-131, DEC-132, DEC-133, DEC-134 added
- `references.json` — 7 entries added (6 decided_in plus 1 is_about)
- `change_log.json` — corresponding append entries

`planning_items.json` should NOT be modified (no new planning items in this payload).

If `git status` shows no changes in `db-export/`, the snapshot may have written to a wrong location. Run:

```bash
find . -name "sessions.json" -newer PRDs/product/crmbuilder-v2/close-out-payloads/ses_049.json 2>/dev/null
```

Report whatever path turned up; Doug will copy the snapshots to the correct location before commit.

### Step 5 — Commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply SES-049 — conversation entity schema designed

Lands the SES-049 conversation-entity schema-design conversation's records
to the CRMBUILDER engagement database:

- 1 session: SES-049 (conversation entity schema designed; second
  per-entity governance schema specification produced)
- 6 decisions:
  - DEC-129 (CONV identifier prefix and format)
  - DEC-130 (conversation-to-session via references-table edge per
    the SES-048 cross-spec precedent; new kind conversation_records_session;
    resolves the kickoff's drift toward an FK column on the sessions
    table in favour of the precedent; preserves append-only sessions
    table shape per DEC-013)
  - DEC-131 (seven-status lifecycle with truly terminal terminals,
    forward-only planning lifecycle, complete-requires-session-edge
    rule realising the conversation-to-session linkage, and
    supersession-requires-edge rule inherited from workstream)
  - DEC-132 (conversation-to-kickoff via references-table edge with
    tentative new kind conversation_opens_against_work_ticket; work_ticket
    schema-design conversation may refine; build-planning reconciles)
  - DEC-133 (conversation_succeeds_conversation introduced for
    predecessor-successor chaining; new cross-spec precedent that typed
    sequencing edges are introduced when entity-family frequency
    justifies; diverges from workstream's defer-sequencing posture)
  - DEC-134 (field inventory, two new list-endpoint filters for
    workstream_identifier and status, master-pane Workstream column
    as fifth column, soft-delete posture, eighteen acceptance criteria)
- 0 planning items: PI-022 (retroactive backfill, authored by SES-046)
  covers this conversation's records implicitly
- 7 references: 6 decided_in (DEC-129..134 -> SES-049) plus 1 is_about
  (SES-049 -> PI-022)

Snapshot regeneration only — payload file is unchanged. The schema
specification deliverable (governance-schema-specs/conversation.md, 459
lines) was committed separately during the conversation at 6580a32.

Next step after this apply lands: open a fresh Claude.ai conversation
against PRDs/product/crmbuilder-v2/schema-design-kickoff-reference-book.md.
That conversation designs the reference_book entity schema as the third
of six per-entity conversations in the workstream, inheriting four
cross-spec precedents — the three from workstream (references-edge over
foreign-key, per-status lifecycle timestamps, terminal-states-are-terminal)
plus the one new precedent from this conversation (typed sequencing edges
introduced when entity-family frequency justifies)."
```

### Step 6 — Push

```bash
git push origin main
```

Stop and report if push fails.

---

## Done

After Step 6 completes, the SES-049 close-out has fully landed:

- 14 records (1 session + 6 decisions + 7 references) live in the CRMBUILDER engagement database.
- Snapshot files regenerated and committed.
- The conversation entity schema is recorded with its decisions; the reference_book entity schema-design conversation can open.

**Next step:** open a fresh Claude.ai conversation against `PRDs/product/crmbuilder-v2/schema-design-kickoff-reference-book.md`. That conversation designs the reference_book entity schema as the third of six per-entity conversations in the workstream.

**Cross-spec precedents now in force, inherited by the remaining four schema-design conversations:**

- References-edge over foreign-key for parent-child governance relationships (DEC-124 from SES-048; reinforced by DEC-130 in this conversation).
- Per-status lifecycle timestamps for workflow-shaped governance lifecycles (DEC-126 from SES-048; extended by DEC-131 in this conversation from four columns to six).
- Terminal-states-are-terminal discipline for governance entities with workflow lifecycles (DEC-125 from SES-048; inherited verbatim by DEC-131).
- **NEW** — Typed sequencing edges introduced when entity-family frequency justifies (DEC-133 from this conversation; diverges from workstream's defer-sequencing posture on the strength of conversation-sequencing frequency).

**Vocabulary additions named by this spec, aggregated by the build-planning conversation:**

- `REFERENCE_RELATIONSHIPS` += `conversation_belongs_to_workstream` (registered here per workstream.md's deferral), `conversation_records_session`, `conversation_opens_against_work_ticket`, `conversation_succeeds_conversation`
- `ENTITY_TYPES` += `conversation` (already named in workstream.md's additions table; affirmed), `work_ticket` (new — required because `conversation_opens_against_work_ticket` names it as target)
- `_kinds_for_pair` gains four clauses tying the new kinds to their valid pairs
- Matching Alembic migration on `refs.relationship_kind` CHECK constraint

The existing generic `supersedes` kind is reused for the `(conversation, conversation)` supersession edge — no new typed kind required for that relationship.

**Tentative kind names flagged for build-planning reconciliation:**

- `conversation_opens_against_work_ticket` — the work_ticket schema-design conversation (fourth in the workstream) may refine the verb tense for consistency with work_ticket's other inbound kinds (for example, if work_ticket ends up with a uniform "consumed-by" verb pattern across multiple inbound kinds, this kind might shift to `conversation_consumes_work_ticket` for symmetry). Build-planning reconciles.

**PI-022 discharge condition unchanged:** still open; the build-planning conversation decides the resolution path (go-forward only, selective backfill, or full backfill with reconstructed outcomes) and executes (if backfill is chosen). This conversation adds new backfill-pass scope items per spec section 3.8.2 — historical lifecycle timestamps for ~50 prior conversations, status assignment for prior conversations including the ad-hoc SES-046, predecessor-successor edges reconstructed from in_flight_at_end text, and kickoff-to-work_ticket edges reconstructed from seed-prompt filenames.

---

## Error handling

- **Standard apply script exits non-zero on a non-409 error.** Stop, do not commit, report the full script output to Doug. Most likely causes: API not running, API misrouted, payload file malformed, or a validation error at the API layer (for example, foreign-key target PI-022 missing).

- **One or more `OK`-expected records returns `SKIP` (409 conflict).** This means a record with the same identifier already exists. Stop and report which identifiers conflicted. The pre-flight TOCTOU check should have caught this; a `SKIP` here indicates either a race (unlikely on a single-operator machine) or an inconsistent pre-flight state.

- **Snapshot not regenerated.** The export hook in the access layer may have failed silently. Stop, do not commit. Check the API server logs for errors during snapshot regeneration.

- **Pre-state already past SES-049.** If `Latest SES` from the pre-flight is already `SES-049` or later, the work has already been applied. Report this finding; do not run the apply again (still safe given idempotency, but unnecessary). No commit needed if pre-state already past.

- **Pre-state earlier than SES-048.** If `Latest SES` from the pre-flight is `SES-047` or earlier, the prerequisite workstream schema-design conversation's records have not landed. Stop and report — SES-048 must apply first.

- **`git status` not clean at start.** Stop and report. Do not stash. Doug decides how to handle the uncommitted changes before re-running.

- **`git pull --rebase` reports conflicts.** Stop and report. The schema specification commit (`6580a32`) plus the close-out payload and apply prompt commit should be on origin/main by the time this prompt runs; if rebase conflicts surface, something diverged between the conversation's commits and the apply.

---

## What this prompt does NOT do

- Does not modify the payload file. It is a read-only input.
- Does not modify the apply script. The script is generic; per-payload variation is in the payload file.
- Does not author additional decisions, planning items, or sessions beyond what the payload file contains. If something is missing from the payload, fix the payload first and re-author it; do not work around in this prompt.
- Does not register the vocabulary additions (`conversation_belongs_to_workstream`, `conversation_records_session`, `conversation_opens_against_work_ticket`, `conversation_succeeds_conversation`, the new `work_ticket` ENTITY_TYPES entry, the four new `_kinds_for_pair` clauses, the Alembic migration on `refs.relationship_kind`). Those are aggregated by the build-planning conversation after all six governance entity schemas exist and applied as one consolidated migration during the build.
- Does not create the `conversations` table or any access-layer methods. Those are built from the schema specification during the build phase, which is a separate workstream conversation later (the build-planning conversation, conversation 7 of the governance workstream).
- Does not modify any spec, plan, or methodology document. The only files touched are under `PRDs/product/crmbuilder-v2/db-export/` (snapshot regeneration).
- Does not open the next schema-design conversation (reference_book entity). That is a separate fresh Claude.ai chat Doug opens against `schema-design-kickoff-reference-book.md` after this apply lands.

---

*End of prompt.*
