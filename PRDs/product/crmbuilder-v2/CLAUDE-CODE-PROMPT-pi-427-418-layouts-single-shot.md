# Claude Code session prompt — PI-427 + PI-418 in one shot: layouts emit, publish, and actionability

Last Updated: 09-04-26 00:20 · Revision 1.1 — change log at end.

> **STATUS (09-04-26): IN EXECUTION — do not start a second session from this file.**
> Session **SES-394** (terminal `crmbuilder-58`, conversation CNV-366) holds the claim on
> PI-427 and PI-418 and is building on branch `pi-427-418` in worktree
> `../crmbuilder-wt-pi427-418`. PI-427's emitter is committed (`066e021c`). Decision 3 is
> settled (DEC-1026, confirmed-only emission); decision 1 (DEC-1029, option A: the audit
> fetches the five portal variants; Layout Sets are REQ-559) and decision 2 (DEC-1033,
> the reason rides the row as `capability_reason`) are settled. **Before acting on this
> file, read PI-427 and PI-418 from the store: if `claimed_by` is set and a session for
> them is `in_flight`, the holder is live even when `ListAgents` shows it idle — message
> it, or ask Doug; do not claim, build, record decisions, or edit the worktree** (LSN-076;
> a second session did exactly that on 09-03-26 and its records had to be superseded).

**Give this file to a fresh Claude Code session rooted in `~/Dropbox/Projects/crmbuilder`.
It supersedes `CLAUDE-CODE-PROMPT-pi-418-layout-actionability.md` (the PI-418-only
variant): Doug decided on 2026-09-03 (DEC-1019) that PI-427 and PI-418 are finished in a
single session — that prompt's decision 1, option A, is settled. Everything verified
below was verified by the PI-417 close-out session on 2026-09-03 at main `ca1b3b6b`.**

You are building **two planning items in PRJ-120 (Publish emitter completion), in
order**:

1. **PI-427** — "Emit and publish layout definitions": the EspoCRM adapter renders a
   `layout:` block from layout records so the existing deploy engine applies them
   (REQ-519's layout half; DEC-951).
2. **PI-418** — "Separate writable layouts from portal- and role-bound variants": the
   writable subset gets capture + publish; the unwritable subset stays shown as a
   difference, non-actionable, naming why (REQ-520).

Read PI-427, PI-418, REQ-519, REQ-520, and DEC-1019 from the store before writing any
code — the store record is the authority, this file is orientation. Claim **both** PIs
(In Progress) when you start, not before. Commits are **one PI per commit, never both**:
emitter commits carry `Governed-By: PI-427`, actionability commits `Governed-By: PI-418`.
Both PIs resolve at the same close-out, each with its own resolving conversation.

## Governance position (verified 2026-09-03)

- **Requirement-first is satisfied.** REQ-519 ("An operator can act on role, team,
  layout and filtered tab differences") is `confirmed`; its layout half is the only part
  still open now that PI-417 (roles, teams, filtered tabs) resolved on merge `ca1b3b6b`.
  REQ-520 ("A construct the platform cannot write stays non-actionable and says why")
  is `confirmed` (approved by DEC-943, refines REQ-519). PI-427 implements REQ-519's
  layout half; PI-418 implements REQ-520.
- **Both PIs are `Draft`** with no claimant, no branch, no worktree.
- **DEC-1001 governs this run:** build in an isolated worktree off `main`; nothing
  merges until its increment has been demonstrated to Doug; merges are serial; at most
  two code lanes concurrently. PI-407 may still hold a lane (worktree
  `../crmbuilder-wt-pi407`) — check `git worktree list` and `ListAgents` before you
  take yours.

Standing rules (the SessionStart hook loads them; the load-bearing ones):

- Every code commit: the `Governed-By:` trailer for the one PI that commit implements.
  The PreToolUse hook checks the *command text* for a line starting `Governed-By:` —
  use `git commit -F - -- <paths> <<'EOF' … EOF` with the trailer at column 0, and
  `git add` a **new** file before the pathspec commit or git will not match it. A merge
  commit cannot take a pathspec: `git merge --no-ff --no-commit <branch>` then
  `GVR_OVERRIDE='GVR-235: merge commit — git disallows a pathspec when concluding a
  merge; the merged tree is exactly main plus branch <branch>' git commit -F -`.
- Model A: build on branch `pi-427-418` in a worktree
  (`git worktree add ../crmbuilder-wt-pi427-418 -b pi-427-418 main`), merge to `main`
  locally after the demonstration, **Doug pushes**, and only after his push do you
  resolve the PIs in the store (`resolution_reference: "merge <sha> (pushed)"`,
  verified with `git merge-base --is-ancestor <sha> origin/main`). Resolve-after-push,
  never before — LSN-066. Copy `uv.lock` from the main clone into the worktree before
  `uv sync` (gitignored; a fresh resolve pulls mcp 2.x, which breaks
  `mcp.server.fastmcp`). Remove the worktree at close-out; keep the branch.
- Record governance real-time via the cloud API (`crmbuilder-v2/data/crmbuilder.env`
  → `Authorization: Bearer`, `X-Engagement: ENG-001`). The `crmbuilder-v2` MCP server
  has no token and returns 401 — use the API directly. A session record needs an inline
  `session_belongs_to_project` edge (supply your own `SES-NNN` identifier: list
  `/sessions`, take max+1, retry on 409) and cannot be closed without a
  `conversation_belongs_to_session` edge from a `CNV-NNN` record. Design choices Doug
  rules on become decisions (DEC-NNN) recorded when he answers, not batched.
- **GVR-239 review gate:** Doug reviews the increment before merge — his preference is
  a live demonstration: short scripts under `/tmp/pi427-418/stepN.sh`, one command per
  step, against a scratch SQLite store
  (`CRMBUILDER_V2_DB_PATH=/tmp/pi427-418/v2.db`, `CRMBUILDER_V2_DATABASE_URL=""`),
  never the cloud store and never a live CRM, plus a standing HTML runbook artifact.
  `/tmp/pi417/generate.py` and `step1..7.sh` are the worked pattern from PI-417 — copy
  the seeding and the in-process `TestClient` API calls. The `instruction-discipline`
  skill at `~/.claude/skills/instruction-discipline` governs every step-by-step reply:
  numbered steps, where/what/expected/if-not, no bare code blocks, no multi-line paste.
- Preferences: one decision per message, labelled options A/B/… each with
  advantages/disadvantages and a recommendation, ending with an explicit ask
  (PRF-002/009) — **in plain text, never a popup question widget** (Doug's global
  rule); plain language with identifiers in evidence sections (PRF-010); progress
  updates (PRF-008); full absolute paths (PRF-004).
- Tests: run **slices**, never the whole tree in one pytest process (LSN-069). The
  slices PI-417 needed and you will too: `tests/crmbuilder_v2/adapters`,
  `tests/crmbuilder_v2/publish`, `tests/crmbuilder_v2/access/test_reconcile_compare.py
  test_reconcile_apply.py test_reconcile_access.py test_compared_set.py
  test_conformance.py test_instance_membership.py`, `tests/crmbuilder_v2/api/
  test_reconcile_*.py test_conformance_api.py`, `tests/crmbuilder_v2/introspect`,
  `tests/crmbuilder_v2/test_conformance_check_cli.py`, and with
  `QT_QPA_PLATFORM=offscreen` `tests/crmbuilder_v2/ui/test_reconcile_grid.py
  test_reconcile_access_confirm.py`. Migration heads are `0135` (SQLite) / `0092`
  (PG) — if you add a migration take the next free number on **both** chains and keep
  `tests/crmbuilder_v2/migration/test_single_head.py` green.
- **Safety:** never target INST-002 (CBM Production). Production deploys are human-only
  (GVR-240). A layout publish rewrites what every user of an entity sees; do not run a
  layout **apply** against CBMTEST without Doug watching.
- **LSN-070 (the ruamel/PyYAML `yes`/`no` defect) is fixed** on main `aba5374d`
  (REQ-558 / DEC-1016 / PI-461): `emit.py` quotes the six YAML 1.1 boolean words.
  The rule it left behind, and which your layout emitter must follow: at least one
  emitter test must read the artifact back with the **consumer's** reader —
  `pyyaml.safe_load` and the real `espo_impl` `ConfigLoader` — as
  `tests/crmbuilder_v2/adapters/test_emit_yaml_dialect.py` does. Tests that read
  emitted YAML back with ruamel (the writer's dialect) hide writer/reader
  disagreements.
- **LSN-073:** the full `tests/crmbuilder_v2/ui/` slice can segfault intermittently
  inside pytestqt's event processing. One segfault is not evidence of a broken tree;
  re-run the slice once, with `-v` into a file so the last `PASSED` line is visible.
- **LSN-071:** a new emitted block needs at least one test that starts at
  `publish.service.generate_design_yaml` (or `/reconcile/publish` with a stubbed
  target) and asserts the block appears in the artifact. Unit tests on
  `build_program_model` and the validation gate both passed while the publish rendered
  nothing.

## What exists today (verified in code at main `ca1b3b6b`)

- **Layouts are captured, compared, and held entirely view-only.**
  `access/reconcile_compare.py::_attribute_capabilities` falls through to
  `(False, False)` for `layout`; `_GLOBAL_MEMBER_REPOS` in `reconcile_apply.py` has no
  layout patcher, so there is no capture path either. Pinned by
  `tests/crmbuilder_v2/access/test_reconcile_compare.py::test_layout_attributes_stay_view_only`
  (its docstring cites REQ-520 as the reason — the blanket default PI-418 replaces).
- **The compared set already says otherwise.** `access/compared_set.py` declares
  `layout` in all four construct sets and compares `layout_content` as a sequence
  ("order IS the visible arrangement", DEC-928); `conformance.py` reads
  `layout_content` and does *not* list `layout` in `_UNWRITABLE_MEMBER_TYPES`, so a
  layout difference already reports as `drifted` (exit 1) — a verdict that claims a
  write path the surface does not offer. PI-418 makes the surface and the declaration
  agree; decide which way per subset.
- **The audit reads the 18 ordinary types only.** `introspect/reconcile.py::
  reconcile_layouts` iterates `vocab.LAYOUT_TYPES` (detail/edit/detail_small/
  detail_convert, list/list_small/kanban, filters/mass_update/relationships, four
  side-panel and four bottom-panel maps) through `_LAYOUT_TYPE_TO_ESPO` and
  `espo_client.get_layout` (`/Layout/action/getOriginal?scope=&name=`). It stores the
  CRM's layout JSON **verbatim** in `layout_content` (a detail layout is
  `[{rows: [[{name}, …]], label}]`). **Portal variants and role-bound variants are not
  fetched, not in the vocabulary, and have no records in the store** — the "unwritable
  subset" REQ-520 wants shown as a difference is currently invisible. V1 catalogued the
  five portal types (`espo_impl/core/layout_types.py::PORTAL_LAYOUTS`) and never
  fetched them either; role binding in EspoCRM 9.x is Layout Sets bound to Teams
  (schema §12.5.2, DEC-6), which nothing in V2 reads.
- **The deploy engine writes the 18 ordinary types.** `espo_impl/core/layout_manager.py`
  `process_layouts` applies every `DEPLOYABLE_LAYOUT_TYPES` entry, honours
  `settings.autoPlaceName` (default true) and the c-prefix rules for native-entity
  custom fields, and reports portal variants as deploy-deferred. Cross-file aggregation
  of a native entity's layouts is REQ-403 (`entity_def.layout_field_names`).
- **No `layouts:` block is emitted.** `adapters/espocrm/model.py` has no layout
  reader, `DesignClient` has no `list_layouts`, and `generate_design_yaml` passes no
  layouts — this is PI-427's scope. The translator you need already exists in reverse:
  the V1 audit's `espo_impl/core/reconcile/capture.py::_reverse_detail_layout /
  _reverse_list_layout / _reverse_field_list_layout / _reverse_panel_map_layout` turn
  the CRM's layout JSON (the shape `layout_content` holds) into the YAML layout block
  (`schema §7.1`: PANELS `{panels: [...]}`, COLUMNS `{columns: [...]}`, FIELD_LIST
  `[...]`, PANEL_MAP `{name: cfg}`), with fixtures under `tests/fixtures/layouts/`.
  Field references inside a layout must resolve to *emitted* internal names (the
  `_strict_resolver` / `ref_map` pattern the rules and filtered tabs use) or the
  `validate_program` gate rejects the whole program beside its entity.
- **Store reality:** ENG-001 has no layout records; ENG-002 (CBM) has 257, all
  `candidate`, across 14 types. Under the confirmed-only emission rule nothing would
  emit for CBM until layouts are confirmed — that is a data fact, not a bug, but say so
  in the demonstration.
- **Publish scope:** `reconcile_apply.py::entity_for_member` already routes a layout to
  its entity, so `publish_scope_for_member` works for layouts the moment a block
  exists. A layout's *presence* row should follow the field/filtered-tab precedent
  (view-only — its entity's promote carries it), not the role/team one. Note also the
  per-instance stored feature selection (REQ-546 / PI-444): a bare publish scopes
  itself from `instance_feature_selection`, so a layout rides its entity's program and
  needs no selection plumbing of its own.

## Design decisions to put to Doug (one per message, plain text, options + recommendation)

Decision 1 of the superseded prompt (build PI-427 here?) is **settled: yes — DEC-1019.**
The remaining three:

1. **How the unwritable subset becomes visible.** REQ-520 says a portal- or role-bound
   variant is *shown as a difference, non-actionable, naming why*. Today none is
   captured. Options: (A) extend the audit to fetch the five portal variants
   (`_LAYOUT_TYPE_TO_ESPO` + vocabulary + a migration for the CHECK constraint if the
   type column is constrained) and mark them unwritable by type; (B) also read Layout
   Sets (`/LayoutSet`) and record role/team binding; (C) declare the subset by type
   without new capture and accept that it is empty until the audit grows. Recommend A
   now, B as its own requirement — Layout Sets are a new construct, not a variant.
2. **Where the reason lives.** The non-actionable row must "name why". Options: (A) a
   per-type reason table in `reconcile_compare` surfaced on the row
   (`capability_reason`) and in the UI's refusal noun (`_MEMBER_TYPE_NOUNS` pattern in
   `reconcile_grid.py`); (B) a note on the construct-set declaration only. Recommend A:
   the operator reads the row, not the declaration.
3. **Confirmed-only emission for layouts.** 257 CBM layouts are candidates. Emit only
   `confirmed` (every other construct's rule) or treat audit-captured layouts as
   emit-worthy at candidate? Recommend confirmed-only and a note owed to Doug that
   CBM's layouts need a confirmation pass before a layout publish there means anything.

## Build order

1. Read PI-427, PI-418, REQ-519/520, DEC-943/951/985/1001/1019, LSN-066/069/070/071/073
   from the store; verify the governance position above still holds; claim **both** PIs.
2. Worktree + branch `pi-427-418`; copy `uv.lock`; `uv sync`.
3. **(PI-427)** `list_layouts` on the DesignClient protocol and all three clients
   (parity test `METHODS` count goes to 17 and its seed grows a layout);
   `_apply_layouts` in `model.py` rendering `layout:` per entity from `layout_content`
   via the reverse translators, strict field resolution, `autoPlaceName` respected;
   `generate_design_yaml` passes it; `validate_yaml_text` green on the emitted
   program; the LSN-071 end-to-end test and the LSN-070 consumer-reader test.
   Commit(s) `Governed-By: PI-427`.
4. Decisions 1–3 with Doug as they arise (decision 3 gates the emitter's filter — put
   it to him during step 3, not after).
5. **(PI-418)** split the type: writable subset gets `(True, True)` attribute
   capability and a `layout` entry in `_GLOBAL_MEMBER_REPOS` (get/patch
   `layout_content`); unwritable subset stays `(False, False)` with a reason; presence
   rows view-only; decision 1's capture extension; the compared-set/conformance
   declarations made consistent per subset (an unwritable variant's drift is
   `named_but_unwritable`, an ordinary layout's is `drifted`). Update the pins:
   `test_layout_attributes_stay_view_only`, `test_compared_set.py`,
   `test_conformance.py`, and the API/UI tests that list member capabilities.
   Commit(s) `Governed-By: PI-418`.
6. Demonstration scripts under `/tmp/pi427-418` (must include: an emitted `layout:`
   block on a generated program that passes the validator; a writable layout row
   showing capture and publish; an unwritable variant row showing no action and the
   reason; the publish-scope routing to the entity's program; the conformance verdict
   for each subset), the standing HTML runbook, and Doug's walkthrough.
7. Commit remainder (pathspec + trailer), merge to main after the demonstration,
   re-run the slices on merged main, **Doug pushes**, then resolve PI-427 and PI-418
   in the store (LSN-066 order), close the session, remove the worktree.

## Standing notes owed to Doug (carry forward, no action asked yet)

- The audit stores a captured filtered tab's filter in EspoCRM report-filter form and
  nothing reads it back to the neutral condition, so such tabs defer at emit until a
  reader exists (PI-417 close-out) — needs its own requirement.
- CBM production's `CNetworkStandard.planFingerprint` likely needs its `readOnly`
  lifted before the first stamped publish there (LSN-068).
- V1 `SUPPORTED_FIELD_TYPES` does not cover all new emitter types — needs its own
  requirement.
- Layout Sets (team-bound layout variants) are unrepresented in V2 end to end; if
  decision 1 lands on option A, record the Layout Set gap as a requirement candidate.

---

## Change log

| Rev | Date | Change |
|---|---|---|
| 1.1 | 09-04-26 00:20 | Status banner added: the prompt is in execution by SES-394; PI-427 committed, decisions 1–3 settled (DEC-1026/1029/1033, REQ-559); a claim-check rule placed before the kickoff instruction after a second session ran the file in parallel and had to stand down (LSN-076, DEC-1028/1031 superseded). |
| 1.0 | 09-03-26 | Combined single-shot prompt created from `CLAUDE-CODE-PROMPT-pi-418-layout-actionability.md` (PI-417 close-out session, 09-03-26) per DEC-1019: decision 1 settled as build-together; branch/worktree/demo paths renamed `pi-427-418`; both-PI claim and resolve; LSN-066 resolve-after-push order; REQ-546 feature-selection note added to publish scope; popup-widget prohibition added per Doug's global rules. |
