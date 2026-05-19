# Multi-tenancy Routing Fix — Planning Conversation Kickoff

**Last Updated:** 05-19-26 13:15
**Status:** Ready to run — open as fresh Claude.ai conversation
**Operating mode:** ARCHITECTURE (design work; eight-element consequential decision template for each architectural choice)
**Companion:** `multi-tenancy-routing-investigation-report.md` (the diagnostic input this conversation consumes)

---

## Purpose

Produce the design, slice plan, and Claude Code prompts for fixing the two multi-tenancy routing bugs discovered during the SES-001 paper-test apply attempt on 05-19-26. The investigation report (companion document) captures the code paths, root cause, proposed fix shape, and edge-case questions. This conversation is where the architectural decisions on those edge cases get made, the slice plan gets locked in, and the per-slice Claude Code prompts get authored.

The output of this conversation is:

1. PI-018 created in the CRMBUILDER engagement, scoping the workstream.
2. A slice plan committed as a Markdown document at `PRDs/product/crmbuilder-v2/multi-tenancy-routing-fix-slice-plan.md`.
3. One or more `CLAUDE-CODE-PROMPT-*` files per slice committed to `PRDs/product/crmbuilder-v2/prompts/`.
4. A session record (SES-044 in CRMBUILDER) plus the decisions captured at close-out via the standard `apply_close_out.py` pattern.

The build conversations that execute the slices open separately, after this planning conversation closes.

---

## Read first

1. `crmbuilder/CLAUDE.md` — v2 build governance, commit conventions, push convention. Confirm with Doug which CLAUDE.md to load at conversation open.
2. `PRDs/product/crmbuilder-v2/multi-tenancy-routing-investigation-report.md` — the diagnostic input. Sections A–G specifically. The proposed-fix shapes in §E and the workstream framing in §F are the starting point for the design.
3. The source files named in the investigation report by `file:line` reference. Particularly: `cli.py:17-49`, `config.py:22-46`, `access/db.py:64-140`, `access/exporter.py:113-129`, `ui/app.py:226-253`, `ui/active_engagement_context.py:32-138`, `migration/lazy_migration.py:43-51`.
4. The slice D PRD (if one exists in `PRDs/product/crmbuilder-v2/`) to understand the original multi-tenancy design intent and what was deliberately deferred.

---

## Pre-flight

1. **Active engagement is CRMBUILDER.** This is v2 product work; governance records go in the dogfood engagement, not CBM. If the desktop UI currently shows CBM as active, switch via the Engagements panel before starting.
2. **API is running and routed to CRMBUILDER.db.** Per the recovery sequence at the end of the paper-test conversation: `fuser -k 8765/tcp && cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2 && CRMBUILDER_V2_DB_PATH=/home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2/data/engagements/CRMBUILDER.db uv run crmbuilder-v2-api &`. Verify with `curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), '- latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"` → expect `42 - latest: SES-043`. If not, restore before starting.
3. **Working trees clean in both repos.** This conversation produces design documents and Claude Code prompts only — no source code changes — so the gate is mostly so close-out commits land cleanly.
4. **CBM repo state:** two pre-paper-test stashes remain unpopped (Dropbox-synced MN-Account, programs/ WIP); Dropbox sync may be paused. Neither blocks this conversation, but worth knowing.

---

## The task

This planning conversation runs in two phases.

### Phase 1 — Architectural decisions

Each question below passes the two-part test (real downstream impact + multiple viable options) and warrants the eight-element consequential decision template per the user's profile preferences. Surface each as an explicit decision; do not silently default.

**Decision 1 — Fresh-install behavior when no `current_engagement.json` exists.** Investigation §E "Failure mode coverage" raised this. Two options: (a) auto-pick the lone engagement if there's exactly one; (b) fail loudly with a "no active engagement; activate one via the UI's Engagements panel first" error. A third hybrid is possible — auto-pick on first invocation only, then require explicit activation thereafter.

**Decision 2 — Missing `engagement_export_dir` behavior.** Investigation §E "Edge cases" for Bug 2. Two options: (a) refuse the write until operator sets `engagement_export_dir` via the UI's Edit Engagement dialog; (b) fall back to a per-engagement scratch dir under `data/engagements/{code}/db-export/`. Today's silent-fallback-to-global-default is the bug; the question is which replacement.

**Decision 3 — Env var vs direct Settings override.** Investigation §E suggests `route_settings_to_engagement(code)` sets `CRMBUILDER_V2_EXPORT_DIR` and resets the cache so subsequent `get_settings()` re-resolves. Alternative: `Settings` becomes engagement-aware directly — adds an `active_engagement_code` field and computes `db_path` / `export_dir` from it. The env var pattern matches what's already in place for `CRMBUILDER_V2_DB_PATH`; the direct-Settings pattern eliminates the env-var-roundtrip but requires a deeper refactor.

**Decision 4 — Should `--engagement <code>` land as a CLI flag on `crmbuilder-v2-api`?** Investigation §G.5 surfaced this. The flag would let operators verify routing without setting env vars manually; it would also support apply-prompt pre-flight checks more naturally. Worth landing now (alongside the helper) or deferred to a separate small workstream.

**Decision 5 — Should `/active-engagement` and/or `/admin/runtime-info` land as API endpoints?** Investigation §G.6 surfaced this. The endpoint would replace the file-read in pre-flight scripts and surface runtime state for diagnostics. Marginal — fine to land alongside the routing fix or defer as quality-of-life.

**Decision 6 — Catalog exports, force_export, bootstrap/migrate scope.** Investigation §G.1, §G.2, §G.3 listed three downstream consumers of `Settings.export_dir`. §G.1 (catalog exports) clearly has the same bug. §G.2 (force_export) currently isn't invoked but inherits the bug. §G.3 (bootstrap/migrate.py:64) needs confirmation. Three options: (a) fix all three implicitly via the Settings-route helper (no code change at consumer sites); (b) add explicit per-engagement guards at each consumer; (c) defer §G.2 and §G.3 since they aren't on the active path. Recommend (a) as the lightest touch.

**Decision 7 — Fail-loud vs auto-create at write time.** Investigation §G.7 surfaced that `access/exporter.py:115` silently creates the target directory tree. After the fix, the helper should either fail-loud (won't create the directory; refuses to write if it doesn't exist) or continue auto-creating. Fail-loud is safer post-fix because it catches mis-routing immediately; auto-create matches today's behavior but masks bugs.

### Phase 2 — Slice plan and Claude Code prompt authoring

Once Phase 1's decisions are settled, produce:

**A. The slice plan document.** `PRDs/product/crmbuilder-v2/multi-tenancy-routing-fix-slice-plan.md`. Standard slice plan structure (per the v0.5 / v0.6 precedents): per-slice scope, acceptance criteria, file:line touch points, test plan, dependency chain between slices. Investigation §F estimates two slices but expect this to shift based on Decision 1–7 outcomes (e.g., Decision 4 might add a small Slice C for the CLI flag + API endpoint).

**B. The per-slice Claude Code prompts.** Following the existing pattern: `CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-{A,B,...}-{descriptor}.md` in `PRDs/product/crmbuilder-v2/prompts/`. Each prompt is DETAIL-mode and pure-execution — pre-flight, workflow steps, post-conditions, test invocation, commit message scaffold. The build conversations execute these one at a time.

**C. The planning item record.** PI-018 in CRMBUILDER, opened at close-out via the standard `apply_close_out.py` pattern. Title: "Complete v0.5 multi-tenancy routing: API startup engagement resolution + per-engagement export_dir." Description: link to this kickoff, the investigation report, and the slice plan. Status: Open.

---

## Close-out

Per the v0.4-closeout precedent and DEC-025. The close-out produces a single `close-out-payloads/ses_044.json` payload and a `CLAUDE-CODE-PROMPT-apply-close-out-ses-044.md` apply prompt, both committed in the crmbuilder repo.

**Session record.** SES-044 (next in CRMBUILDER's sequence after SES-043). Title: "Multi-tenancy routing fix — planning." `session_date`: the date the conversation closes. `topics_covered`: open with the seed prompt reference (this file), then a structured summary of the Phase 1 decisions made and the Phase 2 outputs produced. `artifacts_produced`: the slice plan path, the per-slice Claude Code prompt paths, this kickoff, the investigation report.

**Decisions.** One per Phase 1 question (DEC-108, DEC-109, …, up to DEC-114 depending on how many were settled). Each follows the standard decision record shape (`identifier`, `title`, `context`, `decision`, `rationale`, `alternatives_considered`, `consequences`, `decision_date`, `status`). For decisions where the question collapses to "implementation detail follows from a prior decision," fold into a single record rather than splitting.

**Planning item.** PI-018 per above.

**References.** One `decided_in` reference per decision (decision → SES-044). Plus an `is_about` reference from PI-018 to SES-044 (planning item created in this session).

**Commit.** One commit in the crmbuilder repo containing: the slice plan, the Claude Code prompts, the payload JSON, the apply prompt. Doug pushes; the apply runs in a separate Claude Code session after push.

---

## What this conversation does NOT do

- Does not modify any source code. Source changes happen in the build conversations that execute the slice prompts.
- Does not run the API, post to it, or trigger any DB writes outside the standard close-out apply.
- Does not commit the slice prompts or apply them — those are inputs to the build conversations.
- Does not open the build conversations. They open after the apply lands and Doug picks up the next slice.
- Does not address cross-engagement references, snapshot replay/restore, or engagement deletion (per investigation "What I did not do"). Those are separate workstreams.

---

*End of kickoff.*
