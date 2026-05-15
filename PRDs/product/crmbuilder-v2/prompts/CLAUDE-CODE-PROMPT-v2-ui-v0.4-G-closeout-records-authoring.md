# CLAUDE-CODE-PROMPT-v2-ui-v0.4-G-closeout-records-authoring.md

**Last Updated:** 05-15-26 10:30
**Slice:** G — closeout records authoring (post-build operator work, automated)
**Position:** v0.4 records authoring, after slice F closeout commit + push
**Companion docs:**
- `PRDs/product/crmbuilder-v2/v0.4-closeout-session-record-drafts.md` (the source of truth — every field value to write lives there)
- `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` section 11 (canonical record list and renumbering note)

---

## Purpose

Author the v0.4 closeout records — eight session records, seven decision records, four planning items, the reference set linking them, and the status-entity versioned-replace update from "v0.3 complete" to "v0.4 complete" — by reading the pre-curated drafts file and POSTing each record through the v2 access layer.

This prompt exists because per-slice session-record authoring was not inlined in slices A through E's build prompts (a process gap surfaced at the close of slice E). The drafts file produced during the 05-14-26 reconciliation conversation continuation captures all field values for every record; this prompt automates the writes that would otherwise require manual paste through the desktop dialogs.

Established precedent: the catalog ingestion build (SES-016) authored its own DEC-065/066/067 and session record directly via the access layer from a Claude Code session. The "operator-authored" framing across DEC-013/014/025/029 isn't about who types the API call; it's about Doug being the source of truth for what gets recorded. Doug authored and approved the drafts file content; this prompt executes the writes against that approved content.

After this slice closes, v0.4 is fully shipped.

---

## Project context

v0.4 build is complete: storage, REST, MCP-adjacent (via storage), and desktop UI for the four MVS methodology entity types (`domain`, `entity`, `process`, `crm_candidate`) shipped across slices A–F. The Methodology sidebar group renders all four entries. Cumulative test count 1087.

The remaining v0.4 closeout work is governance-record authoring. The drafts file at `PRDs/product/crmbuilder-v2/v0.4-closeout-session-record-drafts.md` contains:

- **Section 1** — Eight SES drafts (017 v0.4-build-planning, 018 reconciliation/approval, 019–024 for slices A–F)
- **Section 2** — Seven DEC drafts (068 cross-spec consistency, 069 six-slice breakdown, 070 create-then-attach, 071 Slice A retrofit scope, 072 crm_candidate sort, 073 PI-006/008 deferrals, 074 v0.4 approval)
- **Section 3** — Four PI drafts (013 Cross-Domain Service, 014 Catalog FK, 015 Renderers, 016 router-level vocab enforcement)
- **Section 4** — Reference records (`decided_in` from each DEC to its source SES; `is_about` from SES-018 to PI-013/014/015 and SES-021 to PI-016)
- **Section 5** — Status update

Decision posture for this slice:
- **PI-016 included.** All four PIs author. (Decided in this conversation, 05-15-26.)
- **Lenient idempotency.** If a target identifier already exists in the database, skip with a note in the result summary rather than failing. The summary names exactly which records were created vs skipped — nothing is silently masked.

---

## Pre-flight

Before any writes:

1. `git status` shows a clean working tree, on `main`.
2. `git log -1` shows the slice F closeout commit on origin (slice F's two commits `cc0e3b7` + `d331471` pushed).
3. `uv run pytest tests/crmbuilder_v2/ -v` is green (run batched if the monolithic-run flake hits; the v2 test surface stability is tracked separately as a candidate PI).
4. `sqlite3 v2.db "SELECT COUNT(*) FROM sessions"` returns 16 (sessions SES-001 through SES-016, all `Complete`; SES-017 onward not yet authored).
5. The drafts file exists at `PRDs/product/crmbuilder-v2/v0.4-closeout-session-record-drafts.md` and is at the version committed in `974a05c` (or whatever revision has SES-024 appended by slice F's step 5).
6. `git pull --rebase origin main` is clean.

---

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry, v2 conventions.
2. `PRDs/product/crmbuilder-v2/v0.4-closeout-session-record-drafts.md` — **read this end-to-end**. Every value to write is in this file. Sections 1–5 in order.
3. `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` section 11 — the renumbering note and the canonical list. If anything in the drafts file looks inconsistent with PRD §11, PRD §11 is the source of truth; flag the inconsistency and stop.
4. `crmbuilder-v2/src/crmbuilder_v2/access/repositories/sessions.py` — `create()` signature, field names, validation.
5. `crmbuilder-v2/src/crmbuilder_v2/access/repositories/decisions.py` — same.
6. `crmbuilder-v2/src/crmbuilder_v2/access/repositories/planning_items.py` — same.
7. `crmbuilder-v2/src/crmbuilder_v2/access/repositories/references.py` — `create()` signature, vocab requirements per DEC-006.
8. `crmbuilder-v2/src/crmbuilder_v2/access/repositories/status.py` — `replace()` and `make_version_current()` semantics for the v0.3 → v0.4 transition.
9. `crmbuilder-v2/src/crmbuilder_v2/access/exporter.py` (or the equivalent module — find by `grep -r "export.*json" crmbuilder-v2/src/crmbuilder_v2/access/`) — the JSON-snapshot exporter used at slice closeouts.

---

## Step 1 — Parse the drafts file

Read `PRDs/product/crmbuilder-v2/v0.4-closeout-session-record-drafts.md` and build an in-memory representation of every record. The file uses `**field_name:** value` markers for scalar fields and multi-line content under labels for narrative fields (`summary`, `topics_covered`, `artifacts_produced`, `in_flight_at_end`, `description`, etc.). Section boundaries are markdown `## SES-NNN — …` / `## DEC-NNN — …` / `## PI-NNN — …` headers. Sections 4 and 5 are descriptive prose with bullets for the references and the status update.

Build the in-memory structure as Python dicts:

```python
parsed = {
    "sessions": [
        {"identifier": "SES-017", "title": "...", "session_date": "05-12-26",
         "status": "Complete", "conversation_reference": "...",
         "summary": "...", "topics_covered": "...",
         "artifacts_produced": "...", "in_flight_at_end": "..."},
        # ... 8 total
    ],
    "decisions": [
        {"identifier": "DEC-068", "title": "...", "decision_date": "05-12-26",
         "status": "Active", "decision": "...",
         "context": "...", "rationale": "...",
         "alternatives_considered": "...", "consequences": "..."},
        # ... 7 total
    ],
    "planning_items": [
        {"identifier": "PI-013", "title": "...", "status": "Open",
         "target_version": "v0.5+", "description": "..."},
        # ... 4 total (013, 014, 015, 016)
    ],
    "references": [
        {"source_type": "decision", "source_id": "DEC-068",
         "target_type": "session", "target_id": "SES-017",
         "kind": "decided_in"},
        # ... 7 decided_in + 4 is_about = 11 total
    ],
    "status_update": {
        "phase": "v0.4 complete",
        # plus any other fields the drafts file Section 5 calls for
    },
}
```

Be tolerant of field shape variations between the drafts file's markdown and the access-layer `create()` signature — e.g., `target_version` in the drafts file may map to a different column name in the planning_items repository, or may not exist as a column at all and need to be expressed in `description`. Read each `create()` signature first, then map drafts fields to its expected kwargs. If a drafts field has no home in the repository signature, fold its content into the closest narrative field (typically `description` for PI; `summary` or `consequences` for DEC; `summary` for SES) and note the fold in the result summary at the end.

---

## Step 2 — Print parse summary and validate

Print a compact summary before any writes happen:

```
v0.4 closeout records — parse summary
=====================================

Sessions to write: 8
  SES-017 — v0.4 build planning (05-12-26)
  SES-018 — v0.4 PRD reconciliation and approval (05-14-26)
  SES-019 — v0.4 slice A — foundation (05-14-26)
  SES-020 — v0.4 slice B — Domains panel (05-14-26)
  SES-021 — v0.4 slice C — Entities panel (05-14-26)
  SES-022 — v0.4 slice D — Processes panel (05-14-26)
  SES-023 — v0.4 slice E — CRM Candidates panel (05-15-26)
  SES-024 — v0.4 slice F — closeout (05-15-26)

Decisions to write: 7
  DEC-068 — cross-spec consistency check accepted
  DEC-069 — v0.4 slice breakdown
  DEC-070 — create-then-attach reference flow
  DEC-071 — Slice A scope includes next-identifier retrofit
  DEC-072 — crm_candidate identifier-ascending sort in v0.4
  DEC-073 — PI-006 and PI-008 deferred
  DEC-074 — v0.4 PRD approval pass with renumbering deltas

Planning items to write: 4
  PI-013 — Cross-Domain Service representation
  PI-014 — Catalog FK integration for methodology entities
  PI-015 — Methodology entity renderers
  PI-016 — Router-level per-pair vocab enforcement on /references

References to write: 11
  decided_in: DEC-068→SES-017, DEC-069→SES-017, DEC-070→SES-017,
              DEC-071→SES-017, DEC-072→SES-017, DEC-073→SES-017,
              DEC-074→SES-018
  is_about:   SES-018→PI-013, SES-018→PI-014, SES-018→PI-015,
              SES-021→PI-016

Status update: v0.3 complete → v0.4 complete
```

Then validate against the database before writing:

- For each SES/DEC/PI identifier, check via `repository.get()`. Build a `to_create` set and a `to_skip` set (lenient idempotency).
- For each reference, check existence (references repository has no identifier-based `get`; use `list_touching` or equivalent to determine whether a matching (source_type, source_id, target_type, target_id, kind) row already exists).
- Print the validated counts:

```
Validation:
  Sessions: 8 to create, 0 already exist
  Decisions: 7 to create, 0 already exist
  Planning items: 4 to create, 0 already exist
  References: 11 to create, 0 already exist
  Status update: pending (current phase: "v0.3 complete")
```

If the existence check shows mismatches that look serious (e.g., a record with the target identifier exists but has different content than the draft, suggesting a re-run after partial state changes), print a warning and STOP. Doug investigates manually. Otherwise proceed.

---

## Step 3 — Author SES records

For each SES draft in `parsed["sessions"]` (in identifier order: 017, 018, 019, 020, 021, 022, 023, 024):

1. If the identifier is in `to_skip` (already exists), print `SES-NNN: already exists, skipping` and continue.
2. Otherwise, call `sessions.create(session, identifier=..., title=..., ...)` with the parsed fields mapped to the repository signature.
3. Verify the returned dict's `identifier` matches the draft's identifier and that `status` is "Complete".
4. Print `SES-NNN: created`.

Use a single SQLAlchemy `Session` per repository call (or batched within a single transaction — match the existing pattern in apply scripts under `crmbuilder-v2/scripts/` if convenient). Commit the transaction after the full batch to keep the writes atomic per-step.

DEC-025 conventions for `topics_covered`: planning-conversation seeds (SES-017, SES-018) reference the kickoff prompt by file path because the prompt files are durably in git. Execution-conversation `topics_covered` (SES-019 through SES-024) follow the practical convention SES-016 used: comma-separated topic list. The drafts file already follows this pattern; no transformation needed.

---

## Step 4 — Author DEC records

For each DEC draft in `parsed["decisions"]` (in identifier order: 068, 069, 070, 071, 072, 073, 074):

1. If identifier in `to_skip`, print and continue.
2. Otherwise, `decisions.create(session, identifier=..., title=..., decision_date=..., status="Active", decision=..., context=..., rationale=..., alternatives_considered=..., consequences=...)`.
3. Verify return.
4. Print `DEC-NNN: created`.

If any field is missing from the draft (the sketches at section 2's "Section 2 — Decision records" intro acknowledge fuller text would come from v0.4-build-planning working notes if available), default to the short form from PRD §11. Don't invent content beyond what's in the draft.

---

## Step 5 — Author PI records

For each PI draft in `parsed["planning_items"]` (in identifier order: 013, 014, 015, 016):

1. If identifier in `to_skip`, print and continue.
2. Otherwise, `planning_items.create(session, identifier=..., title=..., description=..., status="Open", ...)`. Map `target_version` per the repo signature (likely either a `target_version` column or a `version` column; if no such column exists, fold the target-version note into `description`).
3. Verify return.
4. Print `PI-NNN: created`.

---

## Step 6 — Author reference records

For each reference in `parsed["references"]`:

1. Check existence via `references.list_touching(...)` or equivalent for the (source_type, source_id, target_type, target_id, kind) tuple.
2. If exists, print `REF (DEC-068→SES-017/decided_in): already exists, skipping` and continue.
3. Otherwise, `references.create(session, source_type=..., source_id=..., target_type=..., target_id=..., kind=...)`.
4. Verify return.
5. Print `REF (DEC-068→SES-017/decided_in): created`.

Vocab requirements per DEC-006: each (source_type, target_type, kind) tuple must satisfy `RELATIONSHIP_RULES`. The `decided_in` and `is_about` kinds are existing v0.3 vocab and should pass without trouble. If a vocab violation surfaces (likely because of a typo in the drafts file), print the violation and STOP — don't write a vocab-violating reference.

---

## Step 7 — Author status update

Per drafts file Section 5, the status entity transitions from phase `"v0.3 complete"` to phase `"v0.4 complete"` via versioned-replace.

1. Read the current status: `status.get_current(session)`. Confirm `phase == "v0.3 complete"`. If not, print the actual current phase and STOP — Doug investigates manually.
2. Build the new status payload by copying the current status dict and updating `phase` to `"v0.4 complete"`. Preserve all other fields (the versioned-replace pattern is "edit the current snapshot, save as new version, mark new version current").
3. Call `status.replace(session, payload=new_payload)`. The return is the new version row.
4. Verify the return's `phase` is `"v0.4 complete"` and that it became current.
5. Print `Status: v0.3 complete → v0.4 complete (version N → N+1)`.

If the version-label format requires increment in source code (per the existing v2 versioned-replace pattern), follow the established convention from prior status updates.

---

## Step 8 — Re-export JSON snapshots

The git-tracked JSON exports under `PRDs/product/crmbuilder-v2/db-export/` are the durable, diffable record of database state. After all writes complete, re-export so the new records appear in the snapshots.

Find the exporter — likely `crmbuilder-v2/src/crmbuilder_v2/access/exporter.py` or `crmbuilder-v2/scripts/export_v2_to_json.py` or similar. Run it. Confirm the affected snapshots updated:

- `db-export/sessions.json` — gains SES-017 through SES-024
- `db-export/decisions.json` — gains DEC-068 through DEC-074
- `db-export/planning_items.json` — gains PI-013/014/015/016
- `db-export/references.json` — gains 11 new reference rows
- `db-export/status.json` — phase updated to "v0.4 complete"
- `db-export/change_log.json` — gains the writes from this slice if change_log is enabled for these entity types (some entity types skip change_log per DEC-067 — verify against the existing pattern)

---

## Step 9 — Result summary

Print a final summary block:

```
v0.4 closeout records authoring — complete
==========================================

Created:
  Sessions: SES-017, SES-018, SES-019, SES-020, SES-021, SES-022, SES-023, SES-024
  Decisions: DEC-068 through DEC-074
  Planning items: PI-013, PI-014, PI-015, PI-016
  References: 11 (7 decided_in + 4 is_about)
  Status: v0.3 complete → v0.4 complete

Skipped (already existed):
  [list any, or "none"]

JSON exports refreshed:
  sessions.json, decisions.json, planning_items.json,
  references.json, status.json[, change_log.json]

v0.4 closeout is complete. v0.4 is fully shipped.
```

If anything was skipped or any non-fatal warning surfaced (field foldings, missing-but-defaulted fields, etc.), name each one in the summary.

---

## Step 10 — Commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git commit -m "v2: v0.4 closeout records authored — SES-017 through SES-024, DEC-068 through DEC-074, PI-013/014/015/016, references, v0.4 complete status"
```

The commit message body should name the authoring source as this prompt and reference the drafts file:

```
Authored via CLAUDE-CODE-PROMPT-v2-ui-v0.4-G-closeout-records-authoring.md
against PRDs/product/crmbuilder-v2/v0.4-closeout-session-record-drafts.md.

This slice closes v0.4. The Methodology sidebar group is in production,
the storage surface is in place, and the governance records reflect the
build sequence. Next workstream candidate per SES-018: paper-test the
four MVS schemas against CBM domain content before opening v0.5+ work.
```

Doug pushes. Do NOT push.

---

## Acceptance verification

1. **All eight SES records exist** in `v2.db` with the expected identifiers and `Complete` status.
2. **All seven DEC records exist** with `Active` status.
3. **All four PI records exist** with `Open` status.
4. **All 11 references exist** in the references table with the expected (source, target, kind) tuples.
5. **Status entity** shows phase `"v0.4 complete"` as the current version.
6. **JSON exports under `db-export/`** are updated to reflect the new records.
7. **The commit** contains only `db-export/` changes — no source code, no PRD changes, no test changes.

If any check fails, stop and report.

---

## What NOT to do

- Do NOT modify source code in `crmbuilder-v2/src/`. This slice is data-authoring only.
- Do NOT modify any of the build prompts under `prompts/`. The v0.4 build is closed.
- Do NOT modify the drafts file. The drafts file is the read-only source of truth for this slice's writes.
- Do NOT skip the parse-summary step (Step 2). Doug needs to see the count and identifier list before any writes happen so that a malformed parse is caught before it corrupts state.
- Do NOT proceed past Step 2 if the parse summary shows unexpected counts (more or fewer than 8/7/4/11/1) or unexpected identifiers. Stop and report.
- Do NOT proceed past Step 7 if the status transition from "v0.3 complete" fails the precondition check (current phase mismatch). Stop and report — manual investigation required.
- Do NOT push. Doug pushes.
- Do NOT add new tests, new migrations, new schema, new routes, new repositories, or new exporter logic. This slice uses existing infrastructure end-to-end.
- Do NOT invent content beyond what's in the drafts file. If a DEC field is sketched short, write it short.
- Do NOT batch all writes into a single mega-transaction — each step's writes should commit as their own batch so that a failure in Step N leaves Steps 1..N-1 intact and re-runnable under lenient idempotency.

---

*End of v0.4 closeout records authoring prompt.*
