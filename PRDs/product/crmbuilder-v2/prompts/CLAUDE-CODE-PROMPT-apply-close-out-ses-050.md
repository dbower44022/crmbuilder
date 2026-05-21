# CLAUDE-CODE-PROMPT-apply-close-out-ses-050

**Last Updated:** 05-21-26 15:30
**Operating mode:** DETAIL
**Series:** apply-close-out
**Status:** Ready to execute
**Companion payload:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_050.json`

---

## Purpose

Apply the SES-050 close-out payload to the CRMBUILDER engagement's database. Lands the SES-050 reference-book entity schema-design conversation's records (1 session, 6 decisions, 0 planning items, 7 references) so the next per-entity schema-design conversation can open against `PRDs/product/crmbuilder-v2/schema-design-kickoff-work-ticket.md` with the reference_book specification's cross-spec precedents and inherited posture (references-edge for parent-child relationships, per-status lifecycle timestamps for workflow-shaped lifecycles, terminal-states-are-terminal discipline, typed-sequencing-frequency-justified introduction, and the new documentary-shape-base-timestamps-only precedent established by this conversation) recorded as decisions in the database.

**Audit-and-finalize note.** SES-050 is the audit-and-finalize close-out for the reference_book schema-design conversation. The deliverable (`governance-schema-specs/reference_book.md`, 467 lines at v1.0, plus a v1.1 patch correcting a kind-enum provenance misnarration) was authored in two stages: the v1.0 spec was committed by a prior Claude.ai sandbox session at `c1d007e` on 05-21-26 14:55 whose close-out was never run; SES-050 audited that spec against the schema spec guide and the workstream master plan, found one substantive factual error (the three kind-enum values misidentified as DEC-117 additions in three provenance-narration paragraphs), authored the v1.1 patch reconciling the narration with the enum, and authored this close-out payload and apply prompt. The session record's `topics_covered` captures this honestly. The substantive design content of the spec is unchanged from v1.0; the v1.1 patch is a provenance-narration correction only.

Net effect on the v2 database after this prompt completes:

- **Session.** SES-050 created with the reference_book-entity schema-design conversation's content (one substantive artifact: `governance-schema-specs/reference_book.md`, 467 lines at v1.0 committed during the conversation at `c1d007e`, plus a v1.1 patch in the same file committed by SES-050).
- **Decisions.** Six decisions created — DEC-135 (RB identifier prefix and format, two-letter form, no collision with REF or remaining-three working prefixes), DEC-136 (parent-plus-child versioning model distinct from charter/status singleton-with-payload pattern), DEC-137 (documentary-shaped lifecycle with three statuses and base timestamps only; new cross-spec precedent for documentary-vs-workflow distinction), DEC-138 (eleven-value closed kind enum covering DEC-117's seven plus three observed additions plus an `other` sentinel), DEC-139 (field inventory, repo-relative file path semantics, no engagement-scoping flag, soft-delete posture), DEC-140 (API surface plus three version-management sub-endpoints plus default UI with Kind column and inline version-history plus sixteen acceptance criteria).
- **Planning items.** None. PI-022 (retroactive backfill, authored by SES-046) covers this conversation's records implicitly; no new planning item.
- **References.** Seven added — six `decided_in` (DEC-135..140 → SES-050) plus one `is_about` (SES-050 → PI-022).

All 14 records (1 session + 6 decisions + 7 references) should report `OK` from the apply script. None should `SKIP` — this is a fresh apply, not a reconciliation.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root (typically `~/Dropbox/Projects/crmbuilder`). Stop and report if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes. The conversation's deliverables (the v1.0 spec at `c1d007e`, the v1.1 spec patch, this payload, this apply prompt) should already be committed and pushed before this prompt runs; this prompt's commit is snapshot-regeneration only and starts from a clean state.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts. HEAD should be at or past the SES-050 close-out commit (which adds the v1.1 spec patch + this payload + this apply prompt on top of `c1d007e`).

5. **Confirm payload file exists:**

   ```bash
   ls -la PRDs/product/crmbuilder-v2/close-out-payloads/ses_050.json
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

   Expected: at least 49 sessions returned, latest identifier SES-049 (the predecessor conversation-entity schema-design conversation, which SES-050 follows). If the count is less than 49 or the latest is not SES-049, the API is misrouted or SES-049 has not yet been applied; stop and re-run step 6a or apply SES-049 first.

7. **Verify SES-050, DEC-135..140 are uncontested and prerequisites are in place** (TOCTOU mitigation per the SES-036 reconciliation precedent):

   ```bash
   # SES-050 must not yet exist
   curl -sf http://127.0.0.1:8765/sessions/SES-050 >/dev/null 2>&1 && echo "SES-050 ALREADY EXISTS — STOP" || echo "SES-050 available"

   # Each new decision identifier must not yet exist
   for id in DEC-135 DEC-136 DEC-137 DEC-138 DEC-139 DEC-140; do
     curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null 2>&1 && echo "$id ALREADY EXISTS — STOP" || echo "$id available"
   done

   # PI-022 must exist (foreign-key target for the SES-050 is_about reference)
   curl -sf http://127.0.0.1:8765/planning-items/PI-022 >/dev/null 2>&1 && echo "PI-022 exists — reference target valid" || echo "PI-022 MISSING — STOP and apply SES-046 first"
   ```

   Expected: "SES-050 available", six lines of "DEC-13X available", and "PI-022 exists — reference target valid". Any other output: stop and report.

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

### Step 1 — Apply SES-050 payload

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_050.json
cd ..
```

Expected output:

- SES-050 reports `OK` (created).
- DEC-135 through DEC-140 each report `OK` (created). Six lines.
- Six `decided_in` references (DEC-135..140 → SES-050) each report `OK` (created). Six lines.
- One `is_about` reference (SES-050 → PI-022) reports `OK` (created).
- Script exits 0.

Total: 14 `OK` lines. Zero `SKIP` lines. Zero non-`OK` lines.

Stop and report if any record returns `SKIP` or a status other than `OK`, or if the script exits non-zero.

### Step 2 — Verify created records

```bash
echo "--- Session ---"
curl -sf http://127.0.0.1:8765/sessions/SES-050 >/dev/null && echo "SES-050 OK" || echo "SES-050 MISSING"

echo "--- Decisions ---"
for id in DEC-135 DEC-136 DEC-137 DEC-138 DEC-139 DEC-140; do
  curl -sf http://127.0.0.1:8765/decisions/$id >/dev/null && echo "$id OK" || echo "$id MISSING"
done

echo "--- References ---"
curl -s http://127.0.0.1:8765/references | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
expected = [
    ('DEC-135', 'SES-050', 'decided_in'),
    ('DEC-136', 'SES-050', 'decided_in'),
    ('DEC-137', 'SES-050', 'decided_in'),
    ('DEC-138', 'SES-050', 'decided_in'),
    ('DEC-139', 'SES-050', 'decided_in'),
    ('DEC-140', 'SES-050', 'decided_in'),
    ('SES-050', 'PI-022',  'is_about'),
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

- `sessions.json` — SES-050 added
- `decisions.json` — DEC-135, DEC-136, DEC-137, DEC-138, DEC-139, DEC-140 added
- `references.json` — 7 entries added (6 decided_in plus 1 is_about)
- `change_log.json` — corresponding append entries

`planning_items.json` should NOT be modified (no new planning items in this payload).

If `git status` shows no changes in `db-export/`, the snapshot may have written to a wrong location. Run:

```bash
find . -name "sessions.json" -newer PRDs/product/crmbuilder-v2/close-out-payloads/ses_050.json 2>/dev/null
```

Report whatever path turned up; Doug will copy the snapshots to the correct location before commit.

### Step 5 — Commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: apply SES-050 — reference book entity schema designed (audit-and-finalize)

Lands the SES-050 reference-book entity schema-design conversation's records
to the CRMBUILDER engagement database:

- 1 session: SES-050 (reference book entity schema designed; third
  per-entity governance schema specification produced — audit-and-finalize
  posture because the v1.0 spec was committed at c1d007e by a prior
  Claude.ai sandbox session whose close-out was never run; SES-050
  audited the spec, authored a v1.1 patch correcting a kind-enum
  provenance misnarration, and authored this close-out)
- 6 decisions:
  - DEC-135 (RB identifier prefix and format; two-letter form; no
    collision with REF or remaining-three working prefixes)
  - DEC-136 (parent-plus-child versioning model distinct from
    charter/status singleton-with-payload pattern; establishes the
    documentary-entity versioning shape)
  - DEC-137 (documentary-shaped lifecycle with three statuses and base
    timestamps only; new cross-spec precedent — documentary-shaped
    lifecycles inherit base timestamps only, deviating from DEC-126's
    per-status-timestamps-for-workflow-shapes precedent; remaining three
    specs apply the documentary-vs-workflow distinction on their own
    facts)
  - DEC-138 (eleven-value closed kind enum covering DEC-117's seven plus
    three observed additions — architecture_document, conduct_framework,
    investigation_report — plus an other sentinel)
  - DEC-139 (field inventory of seven content/classification fields plus
    two denormalized version pointers plus three base timestamps;
    repo-relative file path with no leading slash and no .. segments;
    no engagement-scoping flag — per-engagement isolation makes scoping
    implicit; default soft-delete with restore distinct from archived
    and superseded status outcomes)
  - DEC-140 (standard 8-endpoint API plus three version-management
    sub-endpoints realizing in-force-at-time-T semantics; master-pane
    Kind column as third column; inline version-history section in the
    detail pane; sixteen acceptance criteria)
- 0 planning items: PI-022 (retroactive backfill, authored by SES-046)
  covers this conversation's records implicitly
- 7 references: 6 decided_in (DEC-135..140 -> SES-050) plus 1 is_about
  (SES-050 -> PI-022)

Snapshot regeneration only — payload file is unchanged. The schema
specification deliverable (governance-schema-specs/reference_book.md,
467 lines at v1.0 plus the v1.1 audit patch) was committed separately —
v1.0 at c1d007e during the prior conversation, v1.1 patch by SES-050.

Next step after this apply lands: open a fresh Claude.ai conversation
against PRDs/product/crmbuilder-v2/schema-design-kickoff-work-ticket.md.
That conversation designs the work_ticket entity schema as the fourth
of six per-entity conversations in the workstream, inheriting five
cross-spec precedents — the three from workstream (references-edge over
foreign-key, per-status lifecycle timestamps for workflow-shaped
lifecycles, terminal-states-are-terminal), the one from conversation
(typed sequencing edges introduced when entity-family frequency
justifies), plus the one new precedent from this conversation
(documentary-shaped lifecycles inherit base timestamps only)."
```

### Step 6 — Push

```bash
git push origin main
```

Stop and report if push fails.

---

## Done

After Step 6 completes, the SES-050 close-out has fully landed:

- 14 records (1 session + 6 decisions + 7 references) live in the CRMBUILDER engagement database.
- Snapshot files regenerated and committed.
- The reference_book entity schema is recorded with its decisions; the work_ticket entity schema-design conversation can open.

**Next step:** open a fresh Claude.ai conversation against `PRDs/product/crmbuilder-v2/schema-design-kickoff-work-ticket.md`. That conversation designs the work_ticket entity schema as the fourth of six per-entity conversations in the workstream.

**Cross-spec precedents now in force, inherited by the remaining three schema-design conversations:**

- References-edge over foreign-key for parent-child governance relationships (DEC-124 from SES-048; reinforced by DEC-130 from SES-049; reinforced again by the reference_book spec's all-relationships-in-refs posture).
- Per-status lifecycle timestamps for workflow-shaped governance lifecycles (DEC-126 from SES-048; extended by DEC-131 from SES-049 from four columns to six; **scope clarified** by DEC-137 from this conversation — applies only to workflow-shaped lifecycles, not documentary-shaped).
- Terminal-states-are-terminal discipline for governance entities with workflow lifecycles (DEC-125 from SES-048; inherited verbatim by DEC-131; inherited again by DEC-137 for documentary-shaped terminals).
- Typed sequencing edges introduced when entity-family frequency justifies (DEC-133 from SES-049; applied by reference_book spec to defer reference-book sequencing per the same frequency test).
- **NEW** — Documentary-shaped lifecycles inherit base timestamps only (DEC-137 from this conversation; the workflow-vs-documentary distinction is now the locked precedent for the remaining three schema-design conversations to apply on their own facts).

**Vocabulary additions named by this spec, aggregated by the build-planning conversation:**

- `REFERENCE_RELATIONSHIPS` — **none** new (every inbound and outbound edge was pre-declared by `workstream.md` or is admitted by the existing generic `references` / `is_about` / `supersedes` kinds).
- `ENTITY_TYPES` — already lists `reference_book` per `workstream.md` section 3.3.4's additions table; affirmed.
- `_kinds_for_pair` — no new clauses required from this spec; the existing same-type rule admits `(reference_book, reference_book)` for `supersedes` once `reference_book` is in `ENTITY_TYPES`.
- No matching Alembic migration on `refs.relationship_kind`'s CHECK constraint from this spec.

The reference_book spec is the first of the six governance entity specs to require no new relationship-kind vocabulary additions.

**Tentative kind names flagged for build-planning reconciliation:**

- `workstream_planned_in_reference_book` — inherited from workstream.md, not refined here (the spec accepted the inherited name; the past-participle `planned_in` mirrors documentary-shape semantics naturally). Build-planning has explicit reconciliation responsibility per spec guide §6 cross-spec consistency check; if the build-planning conversation has cause to refine the kind name (e.g., for verb-tense consistency with work_ticket's inbound kinds), it does so once with both source-side and target-side specs visible.

**PI-022 discharge condition unchanged:** still open; the build-planning conversation decides the resolution path (go-forward only, selective backfill, or full backfill with reconstructed outcomes) and executes (if backfill is chosen). This conversation adds new backfill-pass scope items per spec section 3.8.2 — which historical documents become reference_book records, version row populating policy from each file's internal Revision Control table, and kind assignment for ambiguous documents.

**Open-and-flagged for Doug's planning-item decision (NOT in this payload):** authorize a workstream-state reconciliation utility (`tools/workstream_reconcile.py`) invoked from every kickoff prompt's pre-flight, plus the matching one-line additions to `crmbuilder/CLAUDE.md` and the kickoff-prompt template, to prevent the class of state-drift that produced SES-050's audit-and-finalize posture. If accepted as a planning item, it would land at the next close-out (SES-051) rather than retroactively in this one.

---

## Error handling

- **Standard apply script exits non-zero on a non-409 error.** Stop, do not commit, report the full script output to Doug. Most likely causes: API not running, API misrouted, payload file malformed, or a validation error at the API layer (for example, foreign-key target PI-022 missing).

- **One or more `OK`-expected records returns `SKIP` (409 conflict).** This means a record with the same identifier already exists. Stop and report which identifiers conflicted. The pre-flight TOCTOU check should have caught this; a `SKIP` here indicates either a race (unlikely on a single-operator machine) or an inconsistent pre-flight state.

- **Snapshot not regenerated.** The export hook in the access layer may have failed silently. Stop, do not commit. Check the API server logs for errors during snapshot regeneration.

- **Pre-state already past SES-050.** If `Latest SES` from the pre-flight is already `SES-050` or later, the work has already been applied. Report this finding; do not run the apply again (still safe given idempotency, but unnecessary). No commit needed if pre-state already past.

- **Pre-state earlier than SES-049.** If `Latest SES` from the pre-flight is `SES-048` or earlier, the prerequisite conversation-entity schema-design conversation's records have not landed. Stop and report — SES-049 must apply first.

- **`git status` not clean at start.** Stop and report. Do not stash. Doug decides how to handle the uncommitted changes before re-running.

- **`git pull --rebase` reports conflicts.** Stop and report. The reference_book.md v1.0 commit (`c1d007e`), the v1.1 patch commit, and the SES-050 close-out payload + apply-prompt commit should all be on origin/main by the time this prompt runs; if rebase conflicts surface, something diverged between the close-out commits and the apply.

---

## What this prompt does NOT do

- Does not modify the payload file. It is a read-only input.
- Does not modify the apply script. The script is generic; per-payload variation is in the payload file.
- Does not author additional decisions, planning items, or sessions beyond what the payload file contains. If something is missing from the payload, fix the payload first and re-author it; do not work around in this prompt.
- Does not register any vocabulary additions. The reference_book spec is the first of the six governance entity specs to require zero new relationship-kind vocabulary — every needed edge was pre-declared by workstream.md or admitted by existing generic kinds. The build-planning conversation aggregates this nil contribution into its consolidated vocab.py update without action.
- Does not create the `reference_books` table, the `reference_book_versions` child table, or any access-layer methods. Those are built from the schema specification during the build phase, which is a separate workstream conversation later (the build-planning conversation, conversation 7 of the governance workstream).
- Does not modify any spec, plan, or methodology document. The only files touched are under `PRDs/product/crmbuilder-v2/db-export/` (snapshot regeneration).
- Does not open the next schema-design conversation (work_ticket entity). That is a separate fresh Claude.ai chat Doug opens against `schema-design-kickoff-work-ticket.md` after this apply lands.
- Does not create the workstream-state reconciliation utility flagged for Doug's planning-item decision. That utility, if accepted, would be authored as part of a future planning-item discharge — not retroactively added to this payload.

---

*End of prompt.*
