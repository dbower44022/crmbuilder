# Claude Code Prompt — v0.7 Slice F: Documentation, version bump, build closeout

**Last Updated:** 05-22-26 17:30
**Release:** v0.7 (governance entity release)
**Slice:** F — final slice; About-dialog version bump to 0.7.0, README and CLAUDE.md updates, build closeout session, follow-on planning items
**Predecessor slice:** Slice E (PI-022 Phase 1 backfill) — must have shipped
**Successor:** Release shipped; v0.7 closed
**PRD:** `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md`
**Implementation plan section:** §2.6

---

## Task

Close out the v0.7 governance entity release. Bump `__version__` to `"0.7.0"`; update README.md and `crmbuilder/CLAUDE.md` to reflect the release; transition WS-001 to `complete`; author the build closeout session via the standard apply path; author the follow-on planning items for PI-022 Phases 2–4.

## Read this first

1. `crmbuilder/CLAUDE.md`.
2. `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md` §4.4 (About-dialog version bump), §4.5 (documentation updates).
3. `PRDs/product/crmbuilder-v2/governance-entity-implementation-plan.md` §2.6 (this slice's deliverables).
4. `crmbuilder-v2/src/crmbuilder_v2/__init__.py` — current `__version__ = "0.6.0"`.
5. `README.md` and `crmbuilder/CLAUDE.md` v2 sections — current content; identify the insertion points for the v0.7 additions.
6. Prior closeout sessions (e.g., `close-out-payloads/ses_034.json`, `ses_043.json`) as precedent for the closeout-session shape.

## Deliverables

Per implementation plan §2.6:

1. **Version bump:**
   - `crmbuilder-v2/src/crmbuilder_v2/__init__.py`: `__version__ = "0.7.0"`.
   - (Optional) About dialog content augmented with the line "Governance entity release" in the version-info area.

2. **README.md update:**
   - Add a bullet under the v2 feature list: "Governance entity release (v0.7): six new entity types — Workstreams, Conversations, Reference Books, Work Tickets, Close-Out Payloads, Deposit Events — close the gap between V2's governance database role and its actual coverage of the planning-and-execution machinery."

3. **`crmbuilder/CLAUDE.md` updates:**
   - New v0.7 subsection in the v2 release-history section summarizing the governance entity release.
   - Six new entity types added to any entity-type catalog.
   - Reference the new directory `PRDs/product/crmbuilder-v2/deposit-event-logs/`.

4. **WS-001 transition to `complete`:**
   - PATCH `/workstreams/WS-001` with `{"workstream_status": "complete"}`. The access layer sets `_completed_at` automatically.

5. **Build closeout session** via the standard close-out apply path:
   - Author payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` (NNN = next available session identifier verified against the database snapshot at apply time).
   - Author apply prompt at `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`.
   - Payload contents:
     - Session record (`identifier`, `title = "v0.7 governance entity release shipped"`, `conversation_reference`, `topics_covered` listing the six slices executed and the acceptance criteria met, `artifacts_produced` listing the seven new tables, the eight new relationship kinds, the modified apply script, the ten reference_book records and the rest of the Phase 1 backfill, the version bump, the documentation updates, `in_flight_at_end` naming PI-023 / PI-024 / PI-025 as the follow-on backfill phases).
     - Three new planning items (PI-023, PI-024, PI-025) per implementation plan §2.6.
     - References: each PI references PI-022 via `is_about` edge.
   - Apply via `apply_close_out.py` (this run yields the first real captured deposit_event log for the closeout itself, demonstrating end-to-end).

6. **Tag the release** in git: `git tag v0.7.0 && git push --tags`.

## Working style

- Documentation updates first, then version bump, then WS-001 transition, then closeout session.
- One commit for docs + version bump; one for WS-001 transition; the closeout session lands via apply script.
- Run full test suite before tagging: `uv run pytest tests/crmbuilder_v2/`.

## Pre-flight

```
curl -sf http://127.0.0.1:8765/health
uv run pytest tests/crmbuilder_v2/ -v
git pull --rebase origin main
```

## Acceptance gate

Per implementation plan §2.6:

- `__version__` is `"0.7.0"`; About dialog reflects v0.7.
- README.md and `crmbuilder/CLAUDE.md` updated.
- WS-001 at `_status = 'complete'`.
- Closeout session record exists with the expected artifacts list.
- Three follow-on planning items (PI-023, 024, 025) exist; each references PI-022.
- `deposit-event-logs/` contains the captured log for the closeout apply.
- v0.7.0 tag exists on origin/main.
- All earlier slices' acceptance criteria remain passing.
- `uv run pytest tests/crmbuilder_v2/` green.

## After v0.7 ships

- PI-022 remains `Open`; discharge waits on completion of Phases 2–4.
- The desktop UI shows the full governance picture: WS-001 with eight CONVs, eight COPs, eight DEPs, eight WTs, ten RBs all queryable.
- The first end-to-end test of the new entity types against real content is complete. Future work uses these entities as first-class objects rather than as filenames-and-text-mentions.
