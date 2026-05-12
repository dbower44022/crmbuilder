# CLAUDE-CODE-PROMPT-v2-ui-v0.4-F-closeout

**Last Updated:** 05-12-26 10:30
**Series:** v2-ui-v0.4
**Slice:** F (6 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.4-E (CRM Candidates panel — fourth methodology entity type complete; the Methodology sidebar group is fully populated)

## Purpose

This is the sixth and final slice of v0.4. Slice F is mechanical closeout — no new feature work, no new tests, no schema changes. Four deliverables:

1. **Version bump.** `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` set to `"0.4.0"`.
2. **README release note.** A v0.4 entry in `crmbuilder-v2/README.md` matching v0.3's format.
3. **Final regression test pass.** `uv run pytest tests/crmbuilder_v2/ -v` returns green across the cumulative suite (v0.3 tests + all new v0.4 tests from slices A–E).
4. **Final integration smoke verification.** Open the desktop app and confirm the Methodology sidebar group renders all four entries; each panel is operable; the About dialog shows `0.4.0`.

After this slice, v0.4 is shipped. Doug authors closing artifacts (SES-016 session record, six DEC-NNN records for the planning conversation's architectural decisions, status-entity update from "v0.3 complete" to "v0.4 complete") through the desktop UI per the session-record-at-close pattern.

## Project context

Slices A–E delivered the v0.4 feature scope:
- Slice A: foundation infrastructure (vocab, refs CHECK migration, sidebar group container, eight retrofitted next-identifier helpers, spec guide section 6 amendment).
- Slice B: Domains panel end-to-end.
- Slice C: Entities panel end-to-end + `entity_scopes_to_domain` exercised.
- Slice D: Processes panel end-to-end + `process_classification` lifecycle + `process_hands_off_to_process` bidirectional.
- Slice E: CRM Candidates panel end-to-end + singleton-`selected` enforcement.

Slice F closes the release.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. Any uncommitted changes mean a prior slice didn't close cleanly — stop and report to Doug.
3. Confirm git identity:
   - `git config user.name` → `Doug Bower`
   - `git config user.email` → `dbower44022@users.noreply.github.com`
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice E is at HEAD or recently committed.
6. API health: `curl -sf http://127.0.0.1:8765/health` returns 200; start via `uv run crmbuilder-v2-api &` if not.
7. Confirm the cumulative test suite passes BEFORE making any changes: `uv run pytest tests/crmbuilder_v2/ -v`. Record the test count; this is the baseline for verification at the end of the slice.

## Reading order

Before producing any code, read:

1. `crmbuilder/CLAUDE.md` — universal entry. Pay particular attention to the v2 version-source convention (line 50): `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` is the single source of truth.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md` section 5 (Cross-cutting concerns) and section 6 (Acceptance Criteria, Slice F entries F1–F5).
3. `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md` section 4 Step F.
4. `crmbuilder-v2/README.md` — read the existing v0.3 release-note entry; the v0.4 entry matches that format.
5. `crmbuilder-v2/src/crmbuilder_v2/__init__.py` — confirm the current `__version__` value and where it sits in the file.

## Step 1 — Version bump

Modify `crmbuilder-v2/src/crmbuilder_v2/__init__.py` to set `__version__ = "0.4.0"`. The change is a single line replacement; use `str_replace` to preserve surrounding code exactly.

The About dialog reads from `importlib.metadata` first with `__version__` as fallback. No other file needs the version string per the v2 version-source convention.

## Step 2 — README v0.4 release note

Modify `crmbuilder-v2/README.md` to add a v0.4 release-note entry above the v0.3 entry (or in whatever position matches the existing pattern; if release notes appear in reverse-chronological order, v0.4 goes at the top of the release-notes section).

Format the entry to match v0.3's shape. Suggested content (revise to match v0.3's actual format):

```markdown
### v0.4 (05-12-26 or actual ship date)

Four new methodology entity types complete v2's coverage of evolved-methodology Phase 1 output. The desktop application now supports `domain`, `entity`, `process`, and `crm_candidate` records under a new Methodology sidebar group. With v0.4, v2 hosts both governance and methodology content as the system of record for a CRM-implementation engagement; the CBM redo runs end-to-end on v2.

Release highlights:

- New Methodology sidebar group with four entry panels: Domains, Entities, Processes, CRM Candidates.
- Two new reference relationship kinds: `entity_scopes_to_domain` (entity → domain affiliation), `process_hands_off_to_process` (process → process directional handoff). Both registered in `vocab.py` and admitted by the `refs` table's CHECK constraints.
- Field-naming and source-first relationship-kind conventions captured in the methodology-entity-schema-spec guide section 6 amendment. Conventions apply forward only; v0.3 governance entities retain their pre-workstream conventions until the PI-006 retrofit.
- `GET /<entity>/next-identifier` helper endpoints retrofitted to all eight existing prefixed-identifier governance entity types per the SES-010 identifier-asymmetry resolution.
- Process classification lifecycle implements the methodology's Principle 3 priority taxonomy: unclassified → mission-critical / supporting / deferred, with one-way out of unclassified.
- CRM Candidate lifecycle implements engagement-scoped candidate-set evolution: active → selected (singleton-enforced) / declined / removed.

PRD: `PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md`
Implementation plan: `PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md`
```

Pull the exact format and tone from the v0.3 entry. The above is illustrative; the final entry should mirror v0.3's structure faithfully.

## Step 3 — Final regression test pass

Run the cumulative v2 test suite: `uv run pytest tests/crmbuilder_v2/ -v`.

Expected: green across all tests (v0.3 baseline + all v0.4 additions from slices A–E). The test count should match or exceed the pre-slice-F baseline recorded during pre-flight step 7.

If any test fails, stop and report to Doug. The fix happens in the slice that owns the failing test, not in slice F.

## Step 4 — Final integration smoke

Open the desktop application: `uv run crmbuilder-v2`. Verify the following manually:

1. **About dialog shows `0.4.0`.** Open Help → About (or whatever menu path leads to the About dialog). Confirm the version string reads `0.4.0`.

2. **Methodology sidebar group renders with four entries.** Look at the sidebar; below the existing Governance group, the Methodology group renders with a section header and four panel entries: Domains, Entities, Processes, CRM Candidates. Order is the workstream order from slices B–E.

3. **Each panel opens and renders.** Click each of the four entries; confirm the panel opens, the master pane renders (empty or with whatever sample records exist from prior slice tests), and the detail pane renders for a selected row (or shows empty-detail state if no row is selected).

4. **A full happy-path CRUD on at least one panel.** Pick any methodology panel; create a record through New; edit it; soft-delete it; toggle `?include_deleted=true`; restore it. Confirm each step works without errors.

5. **References cross-rendering on Entity + Domain panels.** If sample records exist from slice B and C tests (or you create some), attach an `entity_scopes_to_domain` reference from an entity to a domain via the entity's "Add reference" affordance. Confirm the reference appears on the entity's detail pane under outgoing and on the domain's detail pane under inbound.

6. **Process classification + handoff rendering.** If sample records exist from slice D tests, view a process's detail pane and confirm the classification combo restricts to valid successors of the current classification. View a process with handoff references and confirm "Hands off to" / "Receives from" sub-sections render correctly.

7. **CRM Candidate singleton enforcement.** If sample records exist from slice E tests, attempt to transition a second record to `selected` while another is already `selected` — confirm the inline error fires.

If any verification step fails, stop and report. Slice F does not attempt to fix the failure; the responsible upstream slice does.

## Step 5 — Cumulative acceptance check

PRD section 6 enumerates the cumulative acceptance criteria:

- Slice A (A1–A8): foundation infrastructure
- Domain (14 criteria from `domain.md` section 3.7)
- Entity (16 criteria from `entity.md` section 3.7)
- Process (15 criteria from `process.md` section 3.7)
- CRM Candidate (12 criteria from `crm_candidate.md` section 3.7)
- Slice F (F1–F5): closeout

Confirm all criteria pass. The test suite green from Step 3 covers most; the manual smoke from Step 4 covers F4 (sidebar group renders + each panel operable end-to-end). F1 (version), F2 (README), F3 (test pass) are immediate after Steps 1–3. F5 (cumulative roll-up) is the sum of the prior verifications.

## Acceptance verification

1. **Test suite green.** `uv run pytest tests/crmbuilder_v2/ -v` returns no failures.
2. **About dialog shows 0.4.0.** Manually confirmed in Step 4.
3. **README has v0.4 release note.** Diff includes the entry.
4. **Methodology sidebar group has all four entries operable.** Manually confirmed in Step 4.

If any check fails, stop and report.

## Commit

```bash
git add crmbuilder-v2/src/crmbuilder_v2/__init__.py \
        crmbuilder-v2/README.md
git commit -m "v2: v0.4 slice F — closeout (version 0.4.0, README release note)"
```

Doug pushes. Do NOT push.

## After commit — what Doug does next

This prompt ends with the commit. The remaining closing work is operator-authored, not Claude Code work:

1. **Doug pushes** the slice F commit to origin.
2. **Doug writes session records** through the desktop New Session dialog at the close of each Claude Code execution conversation that contributed to v0.4 build (one per slice, six total for v0.4 build conversations). Each session record uses DEC-025 conventions: `conversation_reference` is descriptive text, `topics_covered` opens with the verbatim seed prompt.
3. **Doug writes SES-016** — the session record for the v0.4-build-planning conversation that produced this PRD, plan, and the six slice prompts. SES-016 uses the same DEC-025 conventions. `conversation_reference`: descriptive text per the PRD's section 11. `topics_covered`: opens with the verbatim kickoff prompt followed by a structured summary of the cross-spec consistency check outcome and the six architectural decisions.
4. **Doug writes DEC-065 through DEC-070** — the six architectural decision records from the v0.4-build-planning conversation. Verbatim body text per the planning conversation's record. Each decision authored via direct API or MCP.
5. **Doug writes six `decided_in` references** from SES-016 to each of DEC-065 through DEC-070.
6. **Doug updates the status entity** from "v0.3 complete" to "v0.4 complete" through the desktop versioned-replace dialog. Version number incremented per the existing pattern.

None of these are Claude Code work; all are operator-authored after this slice's commit.

## What NOT to do

- Do NOT write SES-016 or any DEC-NNN records. Operator-authored per the session-record-at-close pattern.
- Do NOT update the status entity. Operator-authored through the versioned-replace dialog.
- Do NOT bump version anywhere other than `crmbuilder-v2/src/crmbuilder_v2/__init__.py`. The v2 convention has a single source of truth.
- Do NOT add new tests. Slice F is no-feature; the cumulative test pass is the gate.
- Do NOT modify any schema, access-layer method, REST endpoint, panel, dialog, or widget. The feature scope is closed.
- Do NOT add migration files. No schema change in slice F.
- Do NOT push. Doug pushes.
- Do NOT add anything to the changelog or release notes beyond the v0.4 entry called for in Step 2. PI-006, PI-008, and other deferred work belong in their own future release notes.

---

*End of prompt.*

*End of v0.4 build prompt series.*
