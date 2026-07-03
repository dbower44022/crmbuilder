# ADO Foreign-Repo Spike — 2026-07-02

**Question:** can the ADO runtime build a codebase that is not CRMBuilder itself —
specifically the CBM mentor application (`cbm-custom-mentor-app`) under its own
engagement — and what preparation does that take?
**Pass type:** read-only code investigation (scheduler/dispatcher/resolver source)
plus one read-only cloud-store query. Nothing built or recorded.
**Verdict:** **YES — designed-in, with two small, well-bounded gaps.**
**Companion:** the mentor-auth spike report
(`cbm-custom-mentor-app/prds/CBM_Mentor_App_Spike_Report_Mentor_Authentication.md`,
same date) answers the app-side feasibility question; this report answers the
machinery side. Both feed the delivery-efficiency plan
(`delivery-efficiency-plan-2026-07-02.md`) Phase 2.

---

## 1. Designed-in: foreign-repo targeting is configuration, not new capability

- **`AdoSchedulerConfig`** (`scheduler/ado_scheduler.py`) carries
  `engagement` (default `"CRMBUILDER"`), `repo_root` (default `"."`), and
  `base_branch` (default `"main"`); the CLI exposes `--engagement` and
  `--repo-root`. Driving the mentor app is:
  `… --engagement CBMMENTOR --repo-root <path-to-cbm-custom-mentor-app>`.
- **Worktrees are repo-agnostic** — `Worktree(repo_root=cfg.repo_root, …)`
  runs `git -C <repo_root> worktree add` from the target repo's base branch;
  agents spawn as `claude` CLI processes inside the worktree
  (`spawn_claude_agent`, `coordinating_scheduler.py`). Nothing assumes
  CRMBuilder's codebase.
- **Every governance call carries `X-Engagement`** (`dispatcher._get/_post/_patch`,
  `runtime_auth.auth_headers`) — the PM/Lead/dispatch substrate drives any
  engagement's work tasks.
- **The test runner is generic** — `run_pytest` executes
  `uv run pytest <target> -q` from the worktree root; any uv+pytest project
  qualifies.
- The working-copy build lock (`repo_build_lock.py`,
  `<repo_root>/.git/crmbuilder-build.lock`) and `core.hooksPath` hooks are
  per-clone by construction.
- **The engagement already exists:** the cloud store lists **`CBMMENTOR` —
  "CBM Mentoring Custom App"** (alongside `CBM`, `CRMBUILDER`, `ADOTEST`), so
  the governance container needs no provisioning.

## 2. Gap 1 — the affected-test gate is hardcoded to CRMBuilder's tree

`coordinating_scheduler.select_test_target()` maps touched files to pytest
packages via `_SRC_PREFIX = "crmbuilder-v2/src/crmbuilder_v2/"`,
`_TEST_ROOT = "tests/crmbuilder_v2"`, and `_MIRRORED_SUBTREES`. In a foreign
repo every non-doc change is "un-localizable" → the gate falls back to running
`tests/crmbuilder_v2` — a directory that will not exist in the mentor app — so
**the merge gate would fail every task**.

**Fix (small, localized):** make the test root / source prefix / mirror map
config fields on the scheduler, with a plain `tests/` fallback for repos with
no mirror convention. A legitimate governed PI in CRMBuilder.

## 3. Gap 2 — engagement-scoped *profiles* are never dispatcher-selected

`dispatcher.select_profile_id()` filters `scope == "system"` **only**: an
engagement-overlay `agent_profile` is invisible to dispatch. The resolver
(`registry_resolver.resolve_contract`) *does* merge engagement-scoped
**governance rules and learnings** into a system profile's contract
(`_visible`: `engagement_id IS NULL OR == active`). Two viable configurations:

- **Minimal (no code change):** agents run under the generic system archetype
  prompts; all CBM/mentor-app context rides in as **CBMMENTOR-scoped rules +
  learnings** (the auth spike's reusable lessons, the intake app's Espo gotcha
  catalog, the FastAPI/vanilla-JS house style). Caveat: the system profiles'
  per-area domain blocks describe *CRMBuilder's* codebase
  (`registry_seed_content.area_profile_content()`), which is mildly misleading
  context for mentor-app work — counteracted, not removed, by overlay rules.
- **Cleaner (small code change):** dispatch prefers an engagement-scoped
  profile for the same (area, tier, technology) cell when one exists. The
  right long-term fix — any multi-client future needs it.

## 4. Preparation list for an ADO audition on the mentor app (in order)

1. **Human-paired scaffold first:** uv project + FastAPI skeleton + a green
   `tests/` + a CLAUDE.md carrying house conventions — the ADO must land in a
   repo where `uv run pytest` already passes.
2. **Gap 1 PI** in CRMBuilder (per-repo test-target configuration) — required.
3. **Seed CBMMENTOR-scoped rules + learnings** (registry data entry, no code);
   decide whether to also take the Gap 2 PI.
4. **Install the governance hook** in the mentor-app clone (warn mode) and
   confirm the gate validates CBMMENTOR PIs against the configured cloud store
   (the PI-388/389 work made the gate store-configurable — expected config-only).
5. **Dry-run:** one trivial work task (e.g., "add a /healthz test") through a
   driver pointed at the mentor repo before trusting it with real scope.

## 5. Implication for the who-builds decision

The hybrid/audition option costs roughly the list above — one small scheduler
PI plus registry data entry plus scaffold work that is needed regardless of who
builds. The runtime was built multi-engagement from the start. The escape
hatch (fall back to hand-build, keep the findings as lessons) remains the
audition's bound.
