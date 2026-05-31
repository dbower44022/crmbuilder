# PI-112 — Governance & Delivery Model Migration — Execution Plan

**Status:** v0.2 — execution in progress. Branch: `pi-112-migration`.

## Progress log

- **Phase 0** ✅ committed `76fe4c6` — this plan.
- **Phase 1a (code rename)** ✅ committed `a0977a9` — `workstream`→`Project`,
  `WS-`→`PRJ-` across access/api/exporter/ui + the shelved orchestrator + tests.
  Surgical (entity tokens only; prose preserved). Full v2 suite **2206 passed,
  0 failed**. Tests build via `create_all`, so this is green without the live
  migration. Notable fixes beyond the mechanical rename: router `_FIELD_PREFIX`
  (`"workstream_"`→`"project_"`), the `import workstreams` forms, ~54 `WS-NNN`
  test literals, the exporter test's `workstreams.json`→`projects.json`, and
  URL-query `source_type=workstream` literals.
- **Phase 1b (live-data migration)** ✅ — Alembic `0027` written and applied.
  Validated on a copy of the live engagement DB (`CRMBUILDER.db`): upgrade →
  downgrade → re-upgrade all clean, schema parity with `create_all` confirmed,
  new-code `list_projects` reads it. Surfaced + fixed a Phase 1a bug: two model
  index names were half-renamed (`ix_workstreams_project_*`) because the column
  replacement corrupted the index-name token before its own rule ran — now
  `ix_projects_project_*`. Applied to the live DB (UI/API stopped first; DB
  backed up to `data/engagements/CRMBUILDER.db.pre-pi112-*.bak`): 14 rows
  `WS-001..014`→`PRJ-001..014`, 120 refs re-typed, 4 `workstream_master_plan`
  reference-books → `project_master_plan`. Snapshots regenerated
  (`workstreams.json` deleted, `projects.json` added, `references.json` /
  `reference_books.json` updated). `WS-` mentions remaining in
  `sessions.json`/`decisions.json`/`change_log.json` are historical *prose* in
  text/audit fields, intentionally not rewritten. **The desktop app must now be
  relaunched from the `pi-112-migration` branch** — `main`'s code expects the
  old `workstreams` table and is incompatible with the migrated DB until merge.

  ~~⏳ NEXT — mutates the live gitignored~~
  `v2.db`. Write Alembic `0027`: `op.rename_table workstreams→projects`; batch-
  rename `workstream_*`→`project_*` columns; rebuild CHECKs (`PRJ-` GLOB, status,
  names); **data rewrite** `WS-NNN`→`PRJ-NNN` on the projects PK, on
  `refs.source_id`/`target_id` referencing a project (incl. live WS-001..014 and
  the SES-132/133 membership edges to WS-014), on `identifier_reservations`
  rows with `entity_type='workstream'`, and rename the three relationship kinds
  + `workstream_master_plan` reference-book-kind on live rows. Reversible
  downgrade. Validate against a **copy** of the live DB (catalog gitignored, can't
  rebuild the chain from scratch). Then regenerate db-export snapshots
  (`workstreams.json`→`projects.json`; `WS-`→`PRJ-` inside sessions/conversations/
  references snapshots) and commit. **Touches Doug's real governance DB —
  confirm before running.**

**Kickoff artifact:** `governance-redesign-target-model.md` v0.4 (the locked target model).
**Decisions baked in:** DEC-340..344 (target model) + DEC-345..349 (the §11 resolutions).
**Opened against:** WT-063 (kickoff_prompt, was `ready`).

This plan sequences §9 of the target-model doc into committed, test-green phases,
modeled on the PI-073 redesign (phase commits on a branch, close-out at the end).
Each phase leaves the database and test suite internally consistent. It is written
to be **resumable** — a power failure mid-phase can pick up from the last green commit.

## Ground truth (verified at plan time)

- **Alembic head:** `0026_pi_078_identifier_reservations`. Next migration: `0027`.
- **DB build in tests:** `tests/crmbuilder_v2/conftest.py` (+ api/ + ui/ conftests). 168 v2 test files.
  Baseline green before any change (133 workstream/area/planning tests pass).
- **Catalog data gitignored** — the full alembic chain can't run from scratch; migrations
  validate via `create_all`/conftest and a copy of the live engagement DB (see project memory).
- **MCP surface does NOT expose workstream tools** — `mcp_server/tools.py` omits governance
  entities; UI + REST are the consumers. (Less blast radius than feared.)
- **Live data to migrate:** 14 Project rows `WS-001..WS-014`; reference edges with
  `source_id`/`target_id` in `WS-*`; the kinds `conversation_belongs_to_workstream`,
  `session_belongs_to_workstream`, `workstream_planned_in_reference_book`.

## Blast-radius map (Phase 1 targets — exact locations)

| Layer | File | What |
|---|---|---|
| Model | `access/models.py:1082-1134` | class `Workstream`, table `workstreams`, cols `workstream_*`, CHECK `WS-[0-9]{3}`, status CHECK, 2 indexes |
| Vocab statuses | `access/vocab.py:321-330` | `WORKSTREAM_STATUSES`, `WORKSTREAM_STATUS_TRANSITIONS` |
| Vocab kinds | `access/vocab.py:444,445,543` | `conversation_belongs_to_workstream`, `workstream_planned_in_reference_book`, `session_belongs_to_workstream` |
| Vocab pair rules | `access/vocab.py:_kinds_for_pair` (~719,727,828) | clauses keyed on `"workstream"` source/target; also `ENTITY_TYPES` membership |
| Repo | `access/repositories/workstreams.py` | `_ENTITY_TYPE`, `_IDENTIFIER_PREFIX="WS"`, `_IDENTIFIER_RE`, `_STATUS_TIMESTAMP`, all fns |
| Gov helpers | `access/repositories/_governance.py` | generic; referenced not entity-named |
| API router | `api/routers/workstreams.py:24` | prefix `/workstreams`, 8 endpoints |
| API schemas | `api/schemas.py:1016-1043` | `WorkstreamCreateIn/ReplaceIn/PatchIn` |
| Exporter | `access/exporter.py:93` | `("workstreams", Workstream)` → snapshot filename `workstreams.json` |
| UI | `ui/panels/workstreams.py`, `ui/dialogs/workstream_crud.py`, `ui/dialogs/_workstream_schema.py`, `ui/sidebar.py`, `ui/main_window.py`, `ui/styling.py`, `ui/client.py` | panel, CRUD dialog, form schema, sidebar entry, client methods, labels |
| Cross-refs | `api/routers/sessions.py`, `api/routers/conversations.py`, `access/repositories/sessions.py`, `_governance.py`, `catalog/write.py` | membership-edge enforcement referencing `workstream` |
| db-export | `PRDs/product/crmbuilder-v2/db-export/workstreams.json` | committed snapshot → renamed to `projects.json` |
| Tests | `tests/crmbuilder_v2/**` | rename refs; the data-migration test |

## Phasing

### Phase 1 — Rename `workstream` → `Project`, `WS-` → `PRJ-`
Pure rename of the existing container; the new "Workstream-as-phase" entity does NOT exist
yet, so a blanket `workstream→project` / `Workstream→Project` rename is unambiguous here.

Sub-steps (commit as one phase when green):
1. **Vocab** — rename `WORKSTREAM_*` → `PROJECT_*`; rename the three `*_workstream*` kinds to
   `*_project*` (`conversation_belongs_to_project`, `project_planned_in_reference_book`,
   `session_belongs_to_project`); swap `"workstream"` → `"project"` in `ENTITY_TYPES` and every
   `_kinds_for_pair` clause. **Keep the old kind strings admitted-but-retired** in
   `REFERENCE_RELATIONSHIPS` (mirroring the PI-073 legacy-kind handling) so historical edges
   validate until the data migration renames them.
2. **Model** — class `Project`, table `projects`, cols `project_*`, CHECK `PRJ-[0-9]{3}`,
   constraint/index names `*_project_*`.
3. **Repo** — `workstreams.py` → `projects.py`; `_ENTITY_TYPE="project"`, `_IDENTIFIER_PREFIX="PRJ"`,
   `_IDENTIFIER_RE=^PRJ-\d{3}$`, `_STATUS_TIMESTAMP` keys → `project_*`.
4. **API** — `routers/workstreams.py` → `routers/projects.py`, prefix `/projects`, tag `projects`;
   schemas → `ProjectCreateIn/ReplaceIn/PatchIn`; register in `api/main.py`.
   **Decision: keep a `/workstreams` alias?** No — clean rename (DEC-345 spirit). Update all callers.
5. **Exporter** — `("projects", Project)`; snapshot becomes `projects.json`.
6. **UI** — rename the 7 UI files/labels; sidebar entry "Workstreams" → "Projects".
7. **Migration 0027** — `op.rename_table("workstreams","projects")`; batch-rename columns
   (SQLite batch mode); rebuild CHECKs with new names + `PRJ-` GLOB; **data migration**:
   `WS-NNN` → `PRJ-NNN` on the projects PK, on `refs.source_id`/`target_id` where they reference
   a project, on `identifier_reservations` (0026) if present, and rename the three relationship
   kinds on live `refs` rows. Downgrade reverses.
8. **db-export** — regenerate; `git mv workstreams.json projects.json` effectively (the export
   writes `projects.json`; delete the stale `workstreams.json`). Rewrite `WS-`→`PRJ-` inside
   sessions/conversations/references snapshots (the export handles this once DB is migrated).
9. **Tests** — rename test refs; add a migration test asserting `WS-014` → `PRJ-014` and an edge
   rewrite. Run full `tests/crmbuilder_v2` green.

**Risk:** WS-014 is the live parent of SES-132/SES-133/CNV-034/CNV-035 — its rename must
cascade to those membership edges. Covered by sub-step 7's `refs` rewrite.

> **Phase 2 ✅ done** (commit pending) — `AREAS` (18 prefixed) replaced by
> `SYSTEM_AREA_RANKS`/`SYSTEM_AREAS` (13, prefix dropped, layer ranks per
> DEC-347). New `engagement_areas` table + `EngagementArea` model + repository
> with the session-aware `valid_area_names(session)` = System ∪ Engagement;
> `planning_items`/`orchestration` validate through it. Exporter + new
> `test_engagement_areas.py`. Migration `0028` (prefix-drop existing area data +
> seed engagement areas from `cbm-*`) validated upgrade/downgrade on a live-DB
> copy incl. the synthetic `cbm-*` seeding path; schema parity with `create_all`
> confirmed; applied to the live DB (`v2-access`→`access`); snapshots regen'd.
> REST API + UI for engagement-area management deferred to engagement-init work
> (nothing surfaces areas in UI today). Shelved `backfill_pi_083_area.py`
> updated to System labels. Full suite green (2211).

### Phase 2 — Restructure the area vocabulary (System / Engagement)
- Drop version prefix: `v2-storage`→`storage`, `v1-espo`→`espo`, etc. (13 System areas).
- Split: immutable **System** areas (frozenset, DEC-006 gate) + per-engagement **Engagement**
  areas in a new per-engagement table, **fully user-defined, no Domain link** (DEC-348).
- Migrate `cbm-*` → CBM engagement's Engagement areas (`mn/mr/cr/fu/services`).
- Add **layer rank** ordinal to System areas (storage 1 → access 2 → api 3 → mcp/ui 4; rest null) (DEC-347).
- Validation: a value must be in (System ∪ that engagement's Engagement areas).
- Area stays on `planning_item` at this stage (relocation is Phase 4). Migrate existing tags.

> **Phase 3 ✅ done** (commit pending) — `PLANNING_ITEM_STATUSES` →
> {Draft, Decomposed, Ready, In Progress, In Review, Resolved, Deferred,
> Cancelled} with `PLANNING_ITEM_STATUS_TRANSITIONS` (forward progression;
> Resolved/Deferred/Cancelled reachable from every active state so the
> close-out `resolves` edge still flips from any non-terminal; In Review→In
> Progress rework bounce; Deferred resume; Resolved/Cancelled terminal).
> `planning_items.update` now enforces transitions via `check_transition`;
> `create` defaults to Draft; the dialog schema default is Draft. The
> orchestrator's ready-trigger changed `Open`→`Ready` (DEC-346). Migration
> `0029` (drop CHECK → `Open`→`Draft` data rewrite → recreate 8-value CHECK)
> validated upgrade/downgrade on a live-DB copy, schema parity confirmed,
> applied to the live DB (55 Open → Draft), snapshots regenerated. Test ripple
> resolved by context-classifying planning `Open`→`Draft` (orchestrator
> candidates →`Ready`) while preserving risk `Open`. Full suite green.

### Phase 3 — Planning Item six-state lifecycle (DEC-346)
- `PLANNING_ITEM_STATUSES` → Draft, Decomposed, Ready, In Progress, In Review, Resolved,
  Deferred, Cancelled (phase-agnostic). Add `PLANNING_ITEM_STATUS_TRANSITIONS`.
- CHECK rebuild; repo/router transition enforcement (currently unrestricted — add `check_transition`).
- **Back-compat:** map existing `Open`→`Draft`? or keep `Open` as an alias? Decide at phase start;
  likely migrate `Open`→`Draft`, `Resolved`→`Resolved`, `Deferred`→`Deferred`.
- Gives PI-081/PI-083 a clean `Deferred` (per DEC-344).

> **Phase 4a ✅** (commit `45d1654` + fixes) — new **Workstream** delivery-phase
> entity (`WSK-`): vocab (phase types incl. Design, statuses, transitions),
> model, repo, `/workstreams` API, exporter, `workstream_belongs_to_planning_item`
> + `(workstream,workstream) blocked_by` kinds, migration `0031`, 8 tests. Applied
> to live DB. (A concurrent session added `0030_changelog` mid-phase — a Phase-1
> follow-on migrating `change_log` `workstream`→`project`; mine chained as `0031`.)
>
> **Phase 4b ✅** (commit `a8199d2`) — new **Work Task** entity (`WTK-`): single
> `area` field (validated System ∪ Engagement), claim, statuses+transitions,
> model, repo (+ claim/release), `/work-tasks` API, exporter,
> `work_task_belongs_to_workstream` + `(work_task,work_task) blocked_by`,
> migration `0032`, 7 tests. Applied to live DB. **Area now lives on the
> single-area Work Task — the relocation's goal (DEC-342) is achieved.**
>
> **Phase 4c — dropping the now-redundant `planning_item.area` column: DEFERRED.**
> Area's authoritative home is the Work Task (4b). The only remaining live reader
> of `planning_item.area` is the **shelved** WS-012 orchestrator (DEC-344), whose
> partitioning *is* area-clustering — dropping the column would gut it and its
> large test suite. That cleanup belongs to the orchestrator's formal retirement
> (target-model §9 **step 6**), not here. The column remains as a superseded
> vestige until then.

### Phase 4 — Workstream (`WSK-`) + Work Task (`WTK-`) entities; relocate area
- New **Workstream** entity (delivery phase): belongs_to one Planning Item; phase-type vocab
  {Design, Development, Testing, Documentation, Data Migration, Deployment} (DEC-349);
  lifecycle Planned→In Progress→Complete(+Blocked); identifier `WSK-`.
- New **Work Task** entity: belongs_to one Workstream; single `area`; `claimed_by`/`claimed_at`;
  lifecycle Planned→Ready→Claimed→In Progress→Complete(+Blocked/Failed); identifier `WTK-`.
- **Relocate `area`** from `planning_item` onto Work Task (single-valued). Drop the
  planning_item.area column + its CHECK; orchestrator (`orchestration.py`) updated to read
  task areas. New reference kinds: `workstream_belongs_to_planning_item`,
  `work_task_belongs_to_workstream`, `work_task_has_area` (+ blocked_by variants).
- Out of scope (per design §5/§12): the runtime agent organization; WS-012 retirement (DEC-344).

### Close-out
Author `close-out-payloads/ses_NNN.json` + apply prompt; ingest the phase commits via `commits`;
`resolves_planning_items: [PI-112]`; consume WT-063 (`session_opens_against_work_ticket`);
regenerate snapshots; merge `pi-112-migration` → main.

## Open verification items (resolve as encountered)
- [ ] `identifier_reservations` (0026) schema — does it store `WS-` values needing rewrite?
- [ ] Any consumer reads the literal `workstreams.json` snapshot filename (apply scripts,
      file-fallback orientation, docs)? Grep before deleting it.
- [ ] `catalog/write.py` workstream reference — confirm it's a seed/bootstrap, adjust.
- [ ] Phase 3 `Open`→`Draft` data-migration call: confirm desired mapping with Doug.
