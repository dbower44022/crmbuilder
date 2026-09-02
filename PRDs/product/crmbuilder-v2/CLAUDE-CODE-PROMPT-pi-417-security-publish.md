# Claude Code session prompt — PI-417: emit and publish role, team and filtered-tab definitions

**Written 2026-09-02 by the PI-408 session (crmbuilder-66). Give this file to a fresh
Claude Code session rooted in `~/Dropbox/Projects/crmbuilder`.**

You are building **PI-417** ("Emit and publish role, team and filtered tab
definitions") in PRJ-110 (Chapter-network conformance requirements). Read the PI
and both requirements from the store before writing any code — the store record
is the authority, this file is orientation.

## Governance position (verified 2026-09-02)

- **Requirement-first is already satisfied.** REQ-519 ("An operator can act on
  role, team, layout and filtered tab differences" — this PI implements its
  *publish* direction) and REQ-521 ("A publish that changes access is confirmed
  before it proceeds") are both `confirmed`. PI-417 implements them.
- **PI-417 is already `In Progress`** (status set 2026-09-02T05:18Z, claimant
  unknown, no `pi-417` branch or worktree exists and no code was found). Do not
  re-set the status; verify no peer session is mid-build (`git branch -a`,
  `git worktree list`, ListAgents) and proceed.
- The PI was formerly **blocked by PI-414** (emitter rewrite). PI-414 is
  resolved and merged — the block is lifted.
- **Layouts are NOT this PI.** REQ-519 names layouts too, but layout publish is
  tracked separately (PI-427, and PI-418 for the writable-vs-variant split).
  Scope here is roles, teams, filtered tabs.

Standing rules (the SessionStart hook loads them; the load-bearing ones):

- Every code commit: `Governed-By: PI-417` trailer. The PreToolUse hook checks
  the *command text* for a line starting `Governed-By:` — use
  `git commit -F - -- <paths> <<'EOF' … EOF` with the trailer at column 0. A
  merge commit cannot take a pathspec: use
  `GVR_OVERRIDE='GVR-235: merge commit — git disallows a pathspec when
  concluding a merge; the merged tree is exactly branch pi-417' git commit -F -`.
- Model A: build on branch `pi-417` in a **worktree**
  (`git worktree add ../crmbuilder-wt-pi417 -b pi-417 main`), merge to `main`
  locally, **Doug pushes**, and only after his push do you resolve PI-417 in the
  store (`resolution_reference: "merge <sha> (pushed)"` — verify with
  `git merge-base --is-ancestor`). Copy `uv.lock` from the main clone into the
  worktree before `uv sync` (it is gitignored; a fresh resolve pulls mcp 2.x,
  which breaks `mcp.server.fastmcp`).
- Record governance real-time via the cloud API (`crmbuilder-v2/data/crmbuilder.env`
  → `Authorization: Bearer`, `X-Engagement: ENG-001`). Design choices Doug rules
  on become decisions (DEC-NNN) recorded when he answers, not batched.
- **GVR-239 review gate:** Doug reviews each PI's increment before the next PI
  launches — he chose per-PI review. Offer a live demonstration (his preference
  so far): short scripts under `/tmp/pi417/stepN.sh`, one command per step, plus
  a standing HTML artifact runbook. The `instruction-discipline` skill at
  `~/.claude/skills/instruction-discipline` governs every step-by-step reply:
  numbered steps, where/what/expected/if-not, no bare code blocks, no
  multi-line paste (terminal wrap has broken even single-line `python -c`).
- Preferences: one decision per message, labelled options A/B/… each with
  advantages/disadvantages and a recommendation, ending with an explicit ask
  (PRF-002/009); plain language with identifiers in evidence sections (PRF-010);
  progress updates (PRF-008); full absolute paths (PRF-004).
- Tests: run **slices**, never the whole tree in one pytest process — the UI
  region produces false reds / interpreter crashes single-process (LSN-069). A
  red in a slice is always real. If you add migrations: dual Alembic chains
  (SQLite `migrations/versions/`, PG `migrations/pg/versions/`), heads were
  `0135` / `0092` at PI-408 — take the next free number on **both** chains and
  keep `tests/crmbuilder_v2/migration/test_single_head.py` green (a parallel
  session may take a number under you; renumber if so).
- **Safety:** never target INST-002 (CBM Production). The demonstrable target is
  CBMTEST (credentials in
  `~/Dropbox/Projects/ClevelandBusinessMentors/.crmbuilder/CBM.db`, table
  `Instance`, `code='CBMTEST'` — never print or log them). Production deploys
  are human-only (GVR-240). Given this PI's blast radius is *people losing
  access to a live CRM*, do not run any role/team **apply** against CBMTEST
  without Doug watching in a review-gate walkthrough.

## What exists today (verified in code, post PI-408 merge a92da3f7)

- **The V1 deploy engine can already apply all three constructs.** The Configure
  pipeline (`espo_impl/core/deploy_pipeline.py`) has a Security step using
  `RoleManager`, `TeamManager`, `SecurityRuleManager`
  (`espo_impl/core/role_manager.py` etc., fed by `security/security.yaml`) and a
  filtered-tab path (`espo_impl/core/filtered_tab_manager.py`, fed by
  `filteredTabs:` blocks). The gap is upstream: the V2 **emitter renders none of
  it**, so a publish never hands the engine these constructs.
- **Emitter:** `crmbuilder-v2/src/crmbuilder_v2/adapters/espocrm/model.py` +
  `emit.py` + `adapter.py`. Roles enter `build_program_model` today only to
  resolve role names for field-permission/visibility rules. The design-client
  protocol (`adapters/espocrm/client.py`) already declares `list_roles` and a
  stubbed `list_teams` ("for the security program's `teams:` block") — check
  which methods `AccessDesignClient` actually implements and extend for teams /
  filtered tabs (store repositories exist: `access/repositories/roles.py`,
  `teams.py`, `filtered_tabs.py`).
- **PI-408's construct-set declaration must move with you.**
  `access/compared_set.py` `CONSTRUCT_SETS` currently declares role, team and
  filtered_tab as `(captured, compared)` with the note "emit/apply is PI-417's
  scope". When the publish direction lands, update them to all four sets and
  update the pinning tests (`tests/crmbuilder_v2/access/test_compared_set.py`,
  `tests/crmbuilder_v2/api/test_reconcile_compare_api.py`).
- **Conformance honesty must move too.** `access/conformance.py`
  `_UNWRITABLE_MEMBER_TYPES` includes role/team/filtered_tab; once a write path
  exists, remove them (workflow stays), so their drift reports as `drifted`
  (CLI exit 1) instead of `named_but_unwritable` (exit 3). Update
  `tests/crmbuilder_v2/access/test_conformance.py` and the CLI tests.
- **Publish fences to extend** (`crmbuilder_v2/publish/service.py`):
  - Plan fingerprint (REQ-496): the new blocks change generated artifacts, so
    fingerprints change — that is by design, nothing to do beyond tests.
  - Additive-only fence (REQ-497 / DEC-982): `automatic_apply_declines` /
    `screen_automatic` must treat an access **removal or narrowing** as a
    declined change on an automatic apply.
  - **REQ-521 goes beyond DEC-982:** an access-*removing* change is never
    applied automatically **and** needs a deliberate *separate* confirmation
    even on a reviewed (fingerprint-approved) run, and any access-changing
    publish states its target and effect before proceeding. The mechanism
    (e.g. a preview section enumerating access effects + an explicit
    `confirm_access_changes` parameter distinct from the plan fingerprint) is a
    design decision — put it to Doug.

## Design decisions to put to Doug (one per message, options + recommendation)

The PI names these open questions; do not decide them silently:

1. **Where do instance-wide blocks live?** Publish granularity is one entity
   per program file, but roles/teams/filtered tabs are instance-wide (a role
   spans entities; a team and the tab list have no parent entity). V1 precedent:
   audit v1.2 emitted `security/security.yaml` as a dedicated file (DEC-182)
   and `filteredTabs:` blocks. A dedicated `security/security.yaml` companion
   program is the natural candidate — but it changes the publish unit, so Doug
   rules.
2. **Publish scope for a parentless member** — what does "publish this role"
   select, and how does the per-instance stored feature selection (REQ-546 /
   PI-444) interact with security constructs?
3. **The REQ-521 confirmation mechanism** — how target+effect are stated, and
   what the separate access-removal confirmation looks like in API and UI.

## Suggested build order

1. Read PI-417, REQ-519, REQ-521, DEC-921/982/989 and lessons
   (`GET /lessons?category=process`) from the store; verify the governance
   position above still holds.
2. Worktree + branch `pi-417`; copy `uv.lock`; `uv sync`.
3. Decision 1 with Doug (block placement) — it shapes everything downstream.
4. Emitter: render `roles:` / `teams:` / `filteredTabs:` per the ruled
   placement; validator coverage (`validate_program` must accept the new
   output); adapter/client reads for teams + filtered tabs.
5. Publish service: carry the new artifacts through publish; REQ-521 fences
   (decisions 2–3 with Doug as they arise); serialize outcomes in
   `_serialize_publish_result` and surface in the publish check.
6. Compared-set `CONSTRUCT_SETS` + conformance `_UNWRITABLE_MEMBER_TYPES` +
   capability-table/API updates; test sweep (slices).
7. Commit (pathspec + trailer), merge to main, re-run affected slices on merged
   main, GVR-239 demonstration for Doug (must include: the emitted security
   artifact; a publish preview stating target and effect; an access-removal
   being refused without the separate confirmation). After Doug pushes, resolve
   PI-417 in the store.

## Standing notes owed to Doug (carry forward, no action asked yet)

- CBM production's `CNetworkStandard.planFingerprint` likely needs its
  `readOnly` lifted before the first stamped publish there (LSN-068).
- V1 `SUPPORTED_FIELD_TYPES` does not cover all new emitter types — needs its
  own requirement.
