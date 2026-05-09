# CLAUDE-CODE-PROMPT-v2-ui-v0.3-E-closeout

**Last Updated:** 05-09-26 17:30
**Series:** v2-ui-v0.3
**Slice:** E (5 of 5)
**Status:** Ready to execute (after slice D is reported complete)
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.3-D (Sessions create dialog)

## Purpose

This is the fifth and final slice of the v0.3 build series. This prompt builds slice **E — Closeout**.

Slice E ships v0.3:

- Micro-visual adjustments observed during slices A–D (per DEC-037, in-scope adjustments are allowed even though the full styling pass is deferred).
- Version bump to `0.3.0` in `pyproject.toml`; About dialog renders the new version.
- README update reflecting v0.3's new write surfaces.
- Friction polish for any rough edges noticed during the build.
- Closeout governance records: SES-009 (the v0.3 build session record) per DEC-014, status update bumping to version `1.0` and phase `"v0.3 complete"`.
- Final test pass.

After this slice, v0.3 is shipped. The user-facing acceptance test for v0.3 is then operative: the next planning conversation can be captured by Doug, in the app, with no script runs.

This slice is intentionally light on hard requirements and heavy on synthesis — the polish items are determined by what the build actually surfaced.

## Project context

Slices A through D landed:
- The `ListDetailPanel` factory refactor and Topics migration (slice A).
- Right-click context menus across all eight existing panels (slice B).
- The full References write surface (slice C).
- The Sessions create-only dialog and panel integration (slice D).
- Planning records SES-008, DEC-032 through DEC-037, six references, PI-NNN, status v0.9.

Test suite is at ~579 tests passing as of slice D's report.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity: `git config user.name` returns `Doug`; `git config user.email` returns `doug@dougbower.com`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice D landed:
   - `dialogs/session_create.py` exists.
   - Sessions panel has `New Session` toolbar button and whitespace right-click `New session`.
   - Sessions panel detail pane has no Edit / Delete / Restore button.
6. Confirm storage system is operational. Verify-first: `curl -sf http://127.0.0.1:8765/health` — if 200, proceed. If it fails, start the API in the background (`uv run crmbuilder-v2-api &`), wait ~3 seconds, re-check; if still failing, stop and report.
7. Confirm test suite passes: `uv run pytest tests/crmbuilder_v2/ -v`. Expected ~579 passing.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md` §6 (Acceptance Criteria) — to verify the full PRD is satisfied.
3. `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md` §4 Step E.
4. The reports from slices A through D, captured in chat or in the slice's commit messages — surfaces specific polish items observed during build.
5. `crmbuilder-v2/README.md` — current "User interface" section, to be updated.
6. `crmbuilder-v2/pyproject.toml` — current version field.
7. `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/about.py` — confirm the version is read via `importlib.metadata` (no code change needed if so) or if a hardcoded version string exists, plan the bump.

## Step 1 — Micro-visual adjustments

Per DEC-037, scope-driven micro-adjustments are allowed in v0.3. Plausible candidates surfaced during planning:

- **Colored pill on the relationship-kind label inside `ReferencesSection`.** A small visual element that makes the relationship kind stand out from the entity identifier. If reading the `ReferencesSection` widget felt cluttered during slice C/D testing, add a small `QLabel`-with-stylesheet rendering the kind in a pill shape. Use the existing navy stub color (`#1F3864`) on a light tint background; rounded corners via `border-radius: 8px`. Keep it subtle.
- **`Add reference` button placement in `ReferencesSection`.** Slice C picked button-at-bottom; if testing surfaced friction (e.g., users not noticing it because the section scrolls past it), consider a `+` icon in the section header instead. Discussion in the slice C reporting should inform this.
- **Right-click menu separator between read and write actions** on panels where both are present (Decisions, Risks, Planning Items, Topics, References). A `menu.addSeparator()` between Edit/Delete and Show-references-style actions. Light visual hierarchy.
- **`View payload` modal for Charter/Status** if it was deferred from slice B with a TODO. Simple modal: `QDialog` with `QPlainTextEdit` showing the version's pretty-printed JSON, read-only, Close button. ~30 lines.

For each adjustment considered, only land it if the build actually surfaced friction motivating it. Do not add micro-adjustments speculatively — that is what DEC-037's full styling pass is for.

If any adjustment is added, include a small test (1–3 assertions) confirming the change.

## Step 2 — Version bump and About dialog

### `pyproject.toml`

Open `crmbuilder-v2/pyproject.toml`. Update the `version` field:

```toml
version = "0.3.0"
```

The version was previously `0.2.0` (or similar) per slice F of the v0.2 closeout. Adjust based on what the actual current version is.

### About dialog

Open `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/about.py`.

If the dialog reads the version via `importlib.metadata.version("crmbuilder-v2")`, no code change is needed — it picks up the new version from `pyproject.toml` automatically.

If the dialog has a hardcoded version string, update it to `"0.3.0"`.

### Test

Add or update `tests/crmbuilder_v2/ui/test_about_dialog.py`:

```python
def test_about_dialog_shows_version_0_3_0(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    # Find the QLabel containing the version
    text = dialog.findChild(QLabel, "version_label").text()  # or whatever attribute
    assert "0.3.0" in text
```

(Adapt to the actual About dialog implementation.)

## Step 3 — README update

Open `crmbuilder-v2/README.md`. Find the "User interface" section (added in v0.1, updated in v0.2).

Add a paragraph reflecting v0.3's surfaces:

```
## User interface (v0.3)

The CRMBuilder v2 desktop UI is a standalone PySide6 application that
consumes the storage system REST API. It provides full create/edit/delete
support for Decisions, Risks, Planning Items, and Topics; versioned-replace
with version-history browsing for Charter and Status; full create/delete
support for the references graph (with strict RELATIONSHIP_TYPES vocab
compliance); and append-only create support for Sessions.

Right-click context menus are uniform across every entity row; the menu
actions parallel the toolbar and detail-pane buttons. Reference creation
is reachable from both the References panel toolbar and an "Add reference"
affordance on every detail pane's references section.

See `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md` for the v0.3 specification
and `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md` for the
build plan.
```

(Adjust phrasing to match the existing README's voice. Replace v0.2's prior section, don't append to it — the README describes the current state, not the historical sequence.)

## Step 4 — Friction polish

For any rough edges noticed during slices A–D that didn't fit cleanly into their owning slice, address them here. Examples of plausible items:

- A panel toolbar that's becoming visually crowded after the new buttons (Sessions and References each gained a button in v0.3); reordering or grouping might help.
- An error message somewhere that reads differently from the rest of the application's error voice.
- A test fixture that's been duplicated across slice C and slice D test files; consolidate to `conftest.py`.
- A docstring that drifted out of sync with the implementation.

Small commits per polish item (or one combined polish commit at the end), prefixed `v2:` per convention.

If no friction items surfaced, skip this step.

## Step 5 — Closeout governance records

### SES-009 — UI v0.3 build session record

Per DEC-014, every v2 conversation produces a session record. The build session — the work across slices A through E executed via Claude Code — is captured as SES-009.

Per DEC-025, the `conversation_reference` is descriptive text. The `topics_covered` opens with the verbatim seed prompt for the build conversation.

Use the dialog itself (the slice D feature) to write SES-009 — this is the user-facing acceptance test for v0.3 in action. Open `New Session` and fill:

- `identifier`: `"SES-009"` (auto-assigned; verify it computes correctly)
- `session_date`: today's date (auto-defaulted)
- `status`: `"Complete"` (auto-defaulted)
- `title`: `"UI v0.3 build"`
- `summary`:

```
The v0.3 build executed five Claude Code prompts (slices A through E) per the v0.3 implementation plan. Slice A landed planning records (SES-008, DEC-032 through DEC-037, PI-NNN), the ListDetailPanel master-widget and context-menu factory refactor, and the Topics panel migration to the new factory. Slice B swept right-click context menus across every existing entity panel. Slice C delivered the full References write surface — EntityIdentifierPicker widget, ReferenceCreateDialog with source-first cascading filters, ReferenceDeleteDialog, panel toolbar New Reference button, and detail-pane Add reference affordance with right-click delete. Slice D delivered the Sessions create-only dialog with auto-assigned identifier, sensible defaults, DEC-025-aware placeholder text, and panel toolbar/right-click integration. Slice E shipped v0.3 — micro-visual adjustments observed during build, version bump to 0.3.0, About dialog refresh, README update, SES-009 (this record, written through the new Sessions create dialog as the user-facing acceptance test), and status update to v1.0 phase "v0.3 complete".
```

- `topics_covered`:

```
Seed prompt: "Execute the v2-ui-v0.3 build series in sequence: slice A foundation and factory refactor, slice B right-click context menus, slice C references write surface, slice D sessions create dialog, slice E closeout. Each slice has its own prompt under PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.3-{A..E}-*.md and is acceptance-gated independently. Do not skip ahead; do not collapse slices."

The build worked through five execution slices in order:

A — Foundation and factory refactor. Wrote planning records (SES-008, DEC-032 through DEC-037, PI-NNN, six decided_in references, status v0.9) per DEC-014 / DEC-025. Refactored ListDetailPanel with _create_master_widget and _build_context_menu factory methods. Migrated TopicsPanel to override _create_master_widget; removed the v0.2 self._table = self._tree workaround. Added per-panel parity tests for master-widget type and context-menu factory return type.

B — Right-click context menus across existing panels. Each of the eight existing entity panels (Decisions, Sessions, Risks, Planning Items, Topics, References, Charter, Status) overrode _build_context_menu with action sets paralleling the existing toolbar and detail-pane buttons. Action handlers reused existing slots — no new business logic introduced. Sweep test in test_context_menus.py asserts action-set parity per panel.

C — References write surface. New EntityIdentifierPicker widget under widgets/ for autocomplete identifier selection. ReferenceCreateDialog with source-first cascading filters and strict RELATIONSHIP_TYPES vocab compliance. ReferenceDeleteDialog with edge-text confirmation and cannot-be-undone notice. Cascading-filter framework strategy resolved: [Option 1 — extended FieldSchema with depends_on / compute_options OR Option 2 — parallel CascadingDialog base — fill in the actual choice made by the slice]. Storage-layer additions [if any — DELETE /references/{id} endpoint, RELATIONSHIP_TYPES vocab reshape, refresh map extension]. Panel and detail-pane integration: New Reference toolbar button, Add reference affordance on every detail pane's ReferencesSection, right-click Delete reference on rows in both surfaces.

D — Sessions create-only dialog. SessionCreateDialog as instance of EntityCrudDialog with the nine-field schema per PRD §2.4: identifier (auto-assigned, read-only), session_date (default today), status (default Complete), title, summary, topics_covered (with DEC-025 placeholder), artifacts_produced, in_flight_at_end (optional), conversation_reference (with DEC-025 placeholder). Sessions panel toolbar New Session button; whitespace right-click New session. Detail pane verified to have no Edit, Delete, or Restore button — append-only stays strict per DEC-013 / DEC-034.

E — Closeout. [List the actual micro-adjustments landed, polish items addressed, and version/README updates per the actual slice E execution.] SES-009 written through the new Sessions create dialog as the user-facing acceptance test for v0.3. Status update to version_label 1.0, phase "v0.3 complete".
```

(Replace the bracketed `[fill in]` placeholders with the actual decisions made during slices C and E. The `topics_covered` field is meant to be a faithful summary of what was done.)

- `artifacts_produced`:

```
- Code: ListDetailPanel factory refactor; TopicsPanel migration; right-click _build_context_menu overrides on all eight panels; EntityIdentifierPicker widget; ReferenceCreateDialog and ReferenceDeleteDialog; SessionCreateDialog; references panel write integration; ReferencesSection extensions; sessions panel write integration; About 0.3.0; README update.
- Tests: per-panel factory parity tests; context-menu sweep test; entity_identifier_picker tests; reference_create_dialog and reference_delete_dialog tests; references_panel_writes tests; session_create_dialog tests; sessions_panel_writes tests; references_section extension tests. Approximately 120 new tests across the series.
- Storage layer: [list any storage-layer changes made — DELETE /references/{id}, RELATIONSHIP_TYPES vocab reshape, refresh map extensions]
- Governance records: SES-009 (this record), status update to version_label 1.0 phase "v0.3 complete".
```

- `in_flight_at_end`:

```
v0.4 candidates: full styling design pass per DEC-024 and PI-NNN; reference filtering by relationship type on detail-pane sections; JSON diff view for Charter/Status replace; methodology entity panels (gated on schema design); global search across entities; keyboard shortcuts beyond Qt defaults; export visible panel to CSV/JSON; bulk operations (multi-row select + delete, multi-row update); reimplementation of v1 saved-views / duplicate-checks / workflow managers if their no-public-REST-API constraint is resolved.
```

- `conversation_reference`:

```
Claude Code build conversation that executed the five-prompt v2-ui-v0.3 series under PRDs/product/crmbuilder-v2/prompts/. The build was acceptance-gated per slice. No transcript preserved per DEC-025.
```

Click Save. Verify SES-009 lands in `db-export/sessions.json` via file-watch refresh.

### Status update

Append a new status version. The new payload should:

- Set `phase` to `"v0.3 complete"`.
- Set `sub_step` to `""` or remove the field (per the existing v0.2 closeout convention).
- Set `active_work` to the appropriate next-target description per the v0.4 candidates (or `"Awaiting v0.4 planning"` if a v0.4 conversation hasn't been planned).
- Update `live_inventory.in_database` counts to reflect the new SES-009 and any references created during the build (the planning prompts didn't create governance references, only the planning records in slice A; slice E's closeout adds one more session record).
- Remove `pending.ui_v0_3_remaining_slices` (or set it to empty).
- Add or extend `pending.ui_v0_4_candidates` listing the items in `in_flight_at_end` above.
- Update `metadata.Last Updated` to today's date.
- Set `version_label` to `"1.0"`.

This status update is the final commit of v0.3.

### Verify

After both writes:

- `db-export/sessions.json` contains SES-009 with the content above.
- `db-export/status.json` shows `version_label: "1.0"` and `phase: "v0.3 complete"`.
- `db-export/change_log.json` reflects both writes.

## Step 6 — Final test pass

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: ~579 from slice D + ~5 polish-related tests. Total ~584+ passing.

If any earlier-slice test breaks: debug. Slice E's polish should not affect existing behavior on any panel.

## Step 7 — Manual final verification

Run `uv run crmbuilder-v2-ui` and walk through every PRD §6 acceptance criterion:

- [ ] AC#1 — v0.2 surface continues to work end-to-end.
- [ ] AC#2 — Topics panel uses `_create_master_widget` (no `self._table = self._tree`); other panels use the default factory.
- [ ] AC#3 — Right-click context menus work on every panel with the documented action sets.
- [ ] AC#4 — `New Reference` button on References panel opens the dialog with all fields empty; cascade works; Save creates the reference.
- [ ] AC#5 — `Add reference` affordance on a detail pane's `ReferencesSection` opens the dialog with source pre-filled and disabled.
- [ ] AC#6 — Right-click `Delete reference` on References panel opens confirmation modal; confirm hard-deletes.
- [ ] AC#7 — Right-click `Delete reference` on `ReferencesSection` row opens the same modal; confirm hard-deletes.
- [ ] AC#8 — No Edit affordance on references anywhere.
- [ ] AC#9 — `New Session` opens the dialog with auto-assigned identifier, today's date, default Complete status; required validation works; Save creates the session.
- [ ] AC#10 — Sessions panel has no Edit, Delete, or Restore; right-click row only shows `Go to references` / `Copy identifier`.
- [ ] AC#11 — Vocab compliance is strict in the references dialog; invalid combinations unrepresentable.
- [ ] AC#12 — File-watch refreshes on writes via MCP / curl for both references and sessions.
- [ ] AC#13 — Inline validation works for both new dialogs.
- [ ] AC#14 — Planning records present from slice A.
- [ ] AC#15 — Closeout artifacts: SES-009, status v1.0, About 0.3.0, README updated.
- [ ] AC#16 — Full v2 test suite passes.

If any criterion fails, fix and re-test before final commit.

## Step 8 — Commit, push, report

Commits in this slice:

```
v2: ui v0.3 — micro-visual adjustments + friction polish
v2: ui v0.3 — version bump to 0.3.0 + README
v2: ui v0.3 — closeout, SES-009 + status v1.0
```

(Adjust commit count and content based on what was actually changed. If a step did nothing — e.g., no micro-adjustments needed — skip the commit.)

Push:

```
git pull --rebase origin main
git push origin main
```

## Acceptance gates

- [ ] Any micro-visual adjustments landed are tested.
- [ ] `pyproject.toml` shows `version = "0.3.0"`.
- [ ] About dialog renders `0.3.0`.
- [ ] README "User interface" section reflects v0.3.
- [ ] Friction polish items addressed (or none surfaced; document in reporting).
- [ ] SES-009 present in `db-export/sessions.json` with the documented content.
- [ ] `db-export/status.json` shows `version_label: "1.0"` and `phase: "v0.3 complete"`.
- [ ] All 16 PRD acceptance criteria verified manually.
- [ ] Full v2 test suite passes (~584+ tests).
- [ ] Commits pushed.

## Out of slice

- Anything labelled "deferred to v0.4 or later" in PRD §2.
- Full styling design pass per DEC-024 / PI-NNN.

## Constraints

- Do not introduce new functional features in slice E. The slice is closeout — micro-adjustments and polish only, plus version/README/governance updates.
- Do not skip the manual verification of PRD §6 acceptance criteria. Manual verification is the final acceptance gate before the v0.3 release.
- Do not write SES-009 via script. Use the new Sessions create dialog. Writing SES-009 through the dialog is the user-facing acceptance test for v0.3 — if the dialog can author this record, the testability gap is closed.

## Reporting

After all eight steps complete, report:

- Confirmation that all 16 PRD acceptance criteria are checked.
- The list of micro-visual adjustments landed (or "none" if no friction surfaced).
- The list of friction polish items addressed (or "none").
- The final test count.
- Confirmation that SES-009 was written through the Sessions create dialog and not via script.
- Status update content summary.
- Any deviations or surprises.

After this slice is reported complete, v0.3 is shipped. The next planning conversation engages PI-NNN explicitly when scoping v0.4.
