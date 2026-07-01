# Kickoff — continue the open-release review-and-build loop

**Written:** 2026-07-01, at the end of a long session that delivered 5 releases.
**For:** a fresh Claude Code session picking up where that one left off.
**Task in one line:** walk the remaining open V2 releases one at a time —
review each, and for the self-contained autonomously-buildable ones, build them
requirement-first, close them out against the **cloud** governance store, and
mark them delivered; surface the ones that need Doug.

---

## 0. READ THIS FIRST — the governance store moved to the cloud (07-01)

The V2 backend was cut over to the cloud mid-session. **This changes where every
governance read/write goes.**

- The **local API on `127.0.0.1:8765` is down** and no longer authoritative. Do
  **not** start it or write to it.
- Governance now lives in the **cloud**: `https://api.crmbuilder.ai`. Creds are in
  the gitignored `crmbuilder-v2/data/crmbuilder.env`:
  - `CRMBUILDER_V2_API_BASE_URL` = `https://api.crmbuilder.ai`
  - `CRMBUILDER_V2_API_TOKEN` = a bearer token (auth is **ON** in cloud).
- **Every** API call needs both `Authorization: Bearer <token>` **and**
  `X-Engagement: ENG-001`. The token must be assigned to `ENG-001` (Doug granted
  this; if you get `engagement_forbidden`, ask him to re-grant).
- Standard helper for every governance call:
  ```bash
  BASE=$(grep CRMBUILDER_V2_API_BASE_URL crmbuilder-v2/data/crmbuilder.env | cut -d= -f2-)
  TOKEN=$(grep CRMBUILDER_V2_API_TOKEN   crmbuilder-v2/data/crmbuilder.env | cut -d= -f2-)
  H=(-H "Authorization: Bearer $TOKEN" -H "X-Engagement: ENG-001" -H "Content-Type: application/json")
  curl -s "${H[@]}" "$BASE/releases?limit=500" | python3 -c '...'   # unwrap .data
  ```
- The cloud topology + how to mint tokens is in the memory
  `project_cloud_deployment_v2.md`. `REL-067` is the parallel session's active
  cloud-deployment work — **do not touch it.**

Cloud is the source of truth. If you ever build governance and it doesn't show up,
you're probably hitting the dead local API or missing a header.

---

## 1. The loop (what Doug says each turn: "push it and review the next open release")

For each open release, lowest-numbered first that hasn't been dispositioned:

1. **Review it.** Fetch the release, its projects (`project_belongs_to_release`),
   each project's planning items (`planning_item_belongs_to_project`), each PI's
   status + implementing requirement (`planning_item_implements_requirement`) and
   that requirement's `requirement_status`. Characterise honestly: is this a
   self-contained code build, an architecture/methodology task that needs Doug, or
   work already delivered elsewhere?
2. **Bring Doug the disposition** with a recommendation, and (if there's a genuine
   design fork) **one decision at a time** via `AskUserQuestion`. Do not batch
   decisions. Examples of real forks this session: the PI-103 concurrency
   mechanism; the PI-020 panel-order policy.
3. **If building:** confirm requirement-first is already satisfied (a **confirmed**
   requirement + an implementing PI in a project) — it usually is for these
   releases. If not, stop and create it first.
4. Build on a `rel-NNN-...` or `pi-NNN-...` branch → code + tests → ruff → merge
   `--no-ff` to local `main` → delete the branch. **Every code commit carries a
   `Governed-By: PI-NNN` trailer.** Commit with an explicit pathspec. **You commit;
   Doug pushes** (he'll say "push it").
5. **Close out in the cloud** (see §3).
6. **Mark the release delivered** (see §4).
7. Write/update a memory file + the `MEMORY.md` index line.
8. Report; Doug says "push it and review the next open release" and you repeat.

---

## 2. Hard rules (do not violate)

- **Requirement-first.** No code — even on a branch, even one line — before a
  **confirmed** requirement (approved via a decision, never a status edit) and an
  implementing PI exist. (CLAUDE.md "Governance is a precondition".)
- **Never fabricate human review sign-offs.** Manual-mode releases still gate
  `reconciliation → architecture_planning → ready` on **fresh human review
  sign-offs**; only the final ship approval auto-records. You cannot truthfully
  reach `shipped` without Doug's sign-offs. So for work you hand-build and merge
  off the ADO pipeline, the truthful terminal is **`delivered_off_pipeline`**, not
  `shipped`. This was respected all last session (e.g. REL-036/063/017). If Doug
  wants `shipped`, he records the reconciliation + architecture sign-offs.
- **Commit with explicit pathspec** (`git commit -m ... -- <files>`); a parallel
  orchestrator may stage files on main.
- **You commit, Doug pushes.** Wait for "push it".
- **No silent scope caps.** If you cover only part of a surface, say so in the
  delivery note and memory (like PI-384's "planning_claims excluded" and PI-020's
  "single-file re-deploy" note).
- **One issue at a time** in design/planning. Answer Doug's question; don't
  edit-by-surprise.
- A parallel Claude session is **actively pushing to `origin/main`**. Before a
  push, `git fetch` + merge `origin/main` if behind. Identifier sequences in cloud
  advance from the parallel session too — **re-key on collision** (use
  `GET /<entity>/next-identifier`, and if a decision id you wanted is taken by
  someone else's record, let the server assign a fresh one).

---

## 3. Cloud close-out sequence (exact, with the gotchas)

All against `$BASE` with `${H[@]}`. Three records + edges resolve a PI:

**(a) Decision** — records the build. `executive_summary` must be 200–800 chars.
Server-assigns the id (don't send one — avoids colliding with the parallel
session):
```
POST /decisions  {title, decision_date, status:"Active", context, decision,
                  rationale, consequences, executive_summary}
```

**(b) Build session** — needs an explicit identifier (for the inline self-edge),
`session_executive_summary`, and the project-membership edge inline. Get the free
id from `GET /sessions/next-identifier`:
```
POST /sessions {
  session_identifier:"SES-NNN", session_title, session_medium:"chat",
  session_status:"in_flight", session_description, session_executive_summary,
  references:[{source_type:"session", source_id:"SES-NNN",
               target_type:"project", target_id:"PRJ-NNN",
               relationship:"session_belongs_to_project"}]
}
```
Gotchas: the field is `session_identifier` (not `identifier`); the inline edge
needs the full tuple `source_type/source_id/target_type/target_id/relationship`
(not `relationship_kind`).

**(c) Close-out conversation** — needs `conversation_purpose` + `_description` +
`_summary`, belongs to the session, and **`resolves` each PI** (this flips the PI
to Resolved atomically). Id from `GET /conversations/next-identifier`:
```
POST /conversations {
  conversation_identifier:"CNV-NNN", conversation_title, conversation_purpose,
  conversation_description, conversation_status:"complete", conversation_summary,
  references:[
    {source_type:"conversation", source_id:"CNV-NNN",
     target_type:"session", target_id:"SES-NNN",
     relationship:"conversation_belongs_to_session"},
    {source_type:"conversation", source_id:"CNV-NNN",
     target_type:"planning_item", target_id:"PI-NNN", relationship:"resolves"}
  ]
}
```
Then `PATCH /sessions/SES-NNN {session_status:"complete"}`.

Verify: `GET /planning-items/PI-NNN` shows `Resolved`.

---

## 4. Marking a release delivered

- **From `preliminary_planning`** (all the current open ones): direct, gate-free:
  ```
  POST /releases/REL-NNN/transition {to_status:"delivered_off_pipeline", actor:"Doug Bower"}
  ```
- **From `reconciliation`** (a frozen release): `delivered_off_pipeline` is NOT
  reachable. Use the supersede pattern:
  1. `POST /releases/REL-NNN/open-correction {title, description, notes}` → new REL.
  2. `POST /releases/REL-NNN/transition {to_status:"superseded"}` (the correction
     edge satisfies the gate).
  3. Re-home projects to the successor: for each, `POST /references` a new
     `project_belongs_to_release` to the successor (only after the old release is
     terminal), then `POST /references/delete` the old edge (tuple in body; the
     numeric `DELETE /references/{int}` wants the integer pk, not `REF-NNNN`).
  4. `POST /releases/REL-successor/transition {to_status:"delivered_off_pipeline"}`.
  (Worked example last session: REL-010 → REL-066.)
- If a release **actually entered a lane and ran**, retire it with
  `POST /releases/REL-NNN/abandon` instead (preserves the run evidence, GVR-122).

---

## 5. The remaining open releases + disposition (as of 07-01)

Autonomously buildable (self-contained code, confirmed requirements) → good
candidates. The rest need Doug or are someone else's.

| Release | What it is | Disposition |
|---|---|---|
| **REL-012** Multi-User & Concurrency | PI-103 done (edit-locking). **PI-135** (Postgres default) + **PI-136** (per-user identity) still Draft. | **Reconcile, don't rebuild** — PI-135 is effectively done (cloud runs on Managed PG now; overlaps REL-044); PI-136's RBAC substrate exists but "enforce" not flipped. Needs a decision with Doug. |
| **REL-013** Master PRD dogfood | 9 methodology-authoring PIs, all requirement-confirmed. | **Needs Doug** — authoring the CRMBuilder methodology (Domains/Personas/Processes), not autonomous code. PI-095 (candidate→record promotion) is the one mechanical piece. |
| **REL-016** Cross-Engagement Ref Libraries | 6-PI architecture-first program (PI-062 arch first). | **Needs scoping with Doug** — overlaps the built Agent Profile Registry (skills/learnings/cross-eng promotion). Don't duplicate it. |
| **REL-018** claude.ai-web MCP connector | Remote MCP for claude.ai-web. | **Shelved upstream** (Anthropic connector bug, CLAUDE.md PI-045/049). Not buildable now. |
| **REL-035** Role-aware field-level security deploy | PI-051 salvage (REQ-128/129, TOP-088). | Review — engine may be platform-blocked (no REST write path for role-condition layouts). Local-only branches `ado/wtk-197..203` per memory `project_pi051_rbac_security_salvage`. |
| **REL-039** DB as Single Source of Truth | Consolidate CLAUDE.md + memory into the DB. | Review — likely a docs/methodology consolidation, partly a Doug call. |
| **REL-040** User/role entity model | Engagement-participant users/roles. | Review — may overlap PI-γ RBAC principals already built. |
| **REL-044** Postgres flip — dogfood cutover | PI-365 cut store to Docker PG. | **Likely already delivered** by the cloud cutover (store IS Managed PG now). Reconcile-as-delivered; overlaps REL-067. Confirm with Doug before touching (REL-067 is the parallel session's). |
| **REL-067** Cloud deployment | Parallel session's live cloud work. | **DO NOT TOUCH.** |
| **REL-068** Governance-gate crash-on-malformed-trailer | Small bug fix. | Parallel-session territory (they created it). Check with Doug before building; may already be theirs. |

**Best next autonomous build if Doug wants one:** honestly, the cleanest
remaining self-contained code fixes are thin. **REL-035** and **REL-040** are the
most likely to be real code (review them first); **REL-012/013/016** need Doug;
**REL-044/067/068** are the cloud-cutover cluster to leave to Doug/parallel.

---

## 6. What was delivered last session (don't redo)

All merged to local `main`, closed out in cloud (Resolved + `delivered_off_pipeline`):
- **PI-321** (REL-010) agent secret storage → keyring. *Follow-up for Doug: run
  `uv run crmbuilder-v2-migrate-agent-secrets --purge-env-file` on a keyring host
  to move ANTHROPIC_API_KEY out of plaintext (fleet keeps working either way).*
- **PI-103** (REL-012) optimistic lost-update guard (`updated_at` CAS → 409).
- **PI-348/349** (REL-036) Email activity parents + email-account IMAP folder setup.
- **PI-384** (REL-063) per-prefix identifier-assignment lock across all 53 repos.
- **PI-020** (REL-017) cross-file layout aggregation.
Memories: `project_pi321_agent_secret_storage`, `project_pi103_edit_locking`,
`project_cbm_email_engine_fixes`, `project_pg_autoassign_concurrency`,
`project_pi020_layout_aggregation`.

---

## 7. Commands

```bash
uv run pytest tests/ -q                 # or narrow with -k / a path (v2 suite is large; background it)
uv run pytest tests/crmbuilder_v2/access/ -q
uv run ruff check <files>               # --fix for import sorts
git fetch origin && git log --oneline origin/main..main   # what Doug still needs to push
```
Known-flaky: 8 errors in `tests/crmbuilder_v2/api/test_engagement_scope_middleware.py`
are a **pre-existing PG test-DB seeding collision** (`engagements_pkey ENG-001`),
not yours — ignore them.

---

## 8. Start here

1. Load creds (§0), confirm cloud reachable + ENG-001 works:
   `curl -s "${H[@]}" "$BASE/releases/REL-036" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["release_status"])'`
   → should print `delivered_off_pipeline`.
2. List open releases (§0 helper).
3. Tell Doug the state and ask which release to review, or just review the
   lowest-numbered undispositioned one and bring him the disposition.
```
