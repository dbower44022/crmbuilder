# PI-030 — apply_close_out.py Integration for the Commits Close-Out Payload Section — Kickoff Prompt

**Last Updated:** 05-24-26 16:00
**Work ticket kind:** kickoff_prompt
**Status:** ready
**Workstream:** Code Change Lifecycle (established in SES-057)
**Planning item this conversation contributes to:** PI-030
**Predecessor planning items:** PI-028 (commit entity schema spec, completed in SES-063 with DEC-198..200); PI-029 (commit access layer and REST endpoints, slice A completed in commit `9c1d3b7`, slice B completed in commits c578503/a9cfe13/8e51195/9269095/4b0ac9f with the four DEC-211..214 build-planning decisions in SES-067)
**Spec authority for this slice:**
- `governance-schema-specs/commit.md` v1.0 — entity schema; especially §3.4.3 (administrative correction posture), §3.5.2 (client-side identifier assignment), §3.5.3 (four-digit zero-padded `CM-NNNN` identifier scheme)
- `methodology-code-change-lifecycle.md` v1.0 — methodology authority; especially §5 (commit attribution to conversations) and §5.6 (the manual-commits-between-sessions concern)
- `crmbuilder-v2/scripts/apply_close_out.py` — current implementation; the file PI-030 modifies

---

## Goal

Settle the architectural questions for wiring commits into the close-out lifecycle, then author the PI-030 Claude Code prompt(s) that will land:

1. The close-out payload schema extension — a new top-level `commits` array parallel to the existing `decisions` / `planning_items` / `references` sections, with the field shape determined by the architecture decision below.
2. The `apply_close_out.py` script changes — admit the new payload section, integrate POSTs through `POST /commits` in the standard fixed apply order with idempotent HTTP 409 SKIP on duplicate `commit_sha`, lazy-create supporting records as needed.
3. The helper layer that computes commit metadata from the git repository — author name, author email, committed-at timestamp, message first line and full body, parent SHAs, files-changed count, repository, branch. The location and trigger of this helper depends on the architecture decision.
4. The conversation-attribution rule that maps each commit to its producing conversation, in particular for the manual-commit-between-sessions case methodology §5.6 calls out.
5. Tests covering the new payload section, the apply ordering, the idempotency behavior, and the conversation-attribution edge cases.

After this slice lands:
- Close-out payloads can carry a `commits` section that the apply script lands through the new endpoints from PI-029 slice B.
- The sandbox or local helper (architecture TBD) bundles every commit produced between the predecessor close-out and the current one into the new section, attributing each to a conversation.
- The conversation → commits walk on the governance graph is populated for every close-out applied from this point forward.

This slice does NOT include:
- The Commits panel UI — that's PI-031.
- Historical back-fill of every commit predating PI-030's first apply — that's PI-033, downstream of this slice's machinery.
- Cross-repo commit linking (e.g., a commit in `dbower44022/crmbuilder` that references a commit in `dbower44022/ClevelandBusinessMentoring`) — that's a future workstream; this slice ships per-repo only.

---

## Pre-decided by PI-029 and commit.md (do not re-litigate)

These are settled and the PI-030 prompts inherit them verbatim:

- The nine commit endpoints exist at `/commits`, `/commits/{identifier}`, `/commits/by-sha/{sha}`, `/commits/next-identifier`, plus POST / PUT / PATCH / DELETE / `/commits/{id}/restore`, and the derived `/conversations/{conversation_identifier}/commits` per DEC-211
- Identifier scheme is four-digit `CM-NNNN` per commit.md §3.5.3
- SHA format is lowercase 40-char hex; uniqueness enforced across soft-deleted per slice B's implementation
- `commit_parent_shas` is 0/1/2 entries; merge commits have 2 (the only case)
- `commit_conversation_id` FK existence is enforced at the access layer
- POST body shape and required fields per slice B's `CommitCreateIn` Pydantic schema
- Idempotency: HTTP 409 on duplicate `commit_sha` is the SKIP signal; apply scripts treat HTTP 409 as already-present, not as a failure

---

## Architecture question (likely stop-the-flow under the two-part test)

The biggest decision in this conversation is **where the git-metadata lookup happens** — at close-out emission time, at apply time, or split between them. The three options each shift different costs and integration surfaces:

### Option A — Emitter-time discovery

The close-out emitter (the Claude.ai planning conversation, or a sandbox helper invoked at close-out emission) walks `git log` in the producing repository, computes all commit metadata, and bundles full commit records into the close-out payload's new `commits` array. The apply script becomes a dumb POSTer: read the array, POST each entry through `POST /commits` in fixed order.

- **Pro:** Apply script stays simple; the apply has no git dependency; the payload is fully self-describing for audit.
- **Con:** The sandbox's git access is limited to repos it explicitly clones for the conversation; it may not see local-only or unpushed commits Doug has on his clone. For commits the sandbox didn't help author (manual rebases, hotfix commits Doug made offline), the emitter would have to be supplied the SHAs and metadata externally. The fidelity of bundled metadata depends entirely on what the emitter could see.

### Option B — Apply-time discovery

The close-out emitter records only commit SHAs (a manifest list) in the payload's `commits` array. The apply script, running in Doug's local clone where the full git history is authoritative, looks up each SHA's metadata via `git log -1 --format='%P %an %ae %aI %s' <sha>` and `git diff-tree --name-only -r --no-commit-id <sha> | wc -l`, then POSTs the full record.

- **Pro:** Best metadata fidelity; the apply runs against the canonical git history. No dependency on sandbox visibility into the producing repository. Identical behavior regardless of where the commit was made.
- **Con:** The apply script couples to git (subprocess calls to the `git` CLI in Doug's clone, working-directory-sensitive). Less testable in isolation; harder to reason about for apply-time failures. The payload no longer self-describes its commits — auditing requires both the payload and a git checkout.

### Option C — Hybrid manifest plus apply-time backfill

The close-out emitter records SHAs **plus the producing conversation attribution** in the payload's `commits` array — the part only the emitter knows. The apply script's helper backfills the observable git metadata (parents, author, files-changed count, message) from git at apply time, then POSTs the full record.

- **Pro:** Separates concerns cleanly. The emitter does what only it can do (decide which commits and which conversation produced them). The apply does what only it can do (look up canonical git metadata). Either side can be tested independently.
- **Con:** Most moving parts. Both the payload schema and the apply script change. Slightly more risk of payload/apply version drift if the schema evolves.

**Recommended:** Option C — hybrid manifest plus apply-time backfill. The clean separation of concerns matches how the rest of the v2 governance machinery already works (close-out payloads carry decisions and references that are authored at emission; apply just POSTs). The fidelity argument for Option B applies to the metadata, which the apply backfills; the attribution argument for Option A applies to the conversation linkage, which the emitter records. Costs of moving parts are real but bounded — the schema and the helper script are both small.

Alternatives worth surfacing in the planning conversation: ship Option B first as a simpler MVP and migrate to C later if attribution-at-apply turns out to be inadequate; or ship Option A and accept the sandbox-visibility limitation for v0.8.

---

## Open questions for the conversation to settle

### Question 1 — Architecture (the architecture question above)

Three options A / B / C as named. Recommended Option C. Likely stop-the-flow under the two-part test (real downstream impact on the apply script's complexity and the helper layer's location AND three viable options with meaningfully different audit and integration profiles).

### Question 2 — Conversation-attribution rule for manual commits

For commits Doug makes manually between sessions (methodology §5.6's concern: a hotfix between Wednesday's planning conversation and Thursday's apply, or a rebase to fix a typo), how does the helper decide which conversation produced them? Three candidate rules:

(a) **Time window**: each conversation has a `[opened_at, closed_at]` interval; a commit's `committed_at` falls into one interval or none. Commits with no matching interval are unassigned and surface as a warning at apply time. Simple; fails for manual commits between sessions because they fall outside any conversation's window.

(b) **Explicit claim**: the close-out emitter authoritatively lists the SHAs that belong to its session. Any SHA not in any close-out's manifest is unassigned. Requires the close-out to enumerate every relevant commit, including manual ones. Forces explicit triage.

(c) **Hybrid window plus explicit claim**: the close-out's `commits` array authoritatively claims its commits; manual commits between sessions are claimed by whichever close-out next runs (the close-out has a `claims_inter_session_commits_from: <timestamp>` field naming the start of its claim window). Default behavior: the next close-out claims all commits since the predecessor close-out's apply.

Recommended: Option (c). It admits manual commits without requiring per-conversation enumeration, while still letting an emitter explicitly claim or disclaim specific commits.

### Question 3 — Helper script location and trigger

Where does the helper live and when does it run?

(a) **In `apply_close_out.py`**: same script, gets a `--with-git-metadata` flag (or auto-detects the new payload section). Single entry point; one execution surface for Doug to run.

(b) **Separate `scripts/bundle_commits.py`**: pre-step Doug runs before `apply_close_out.py`. Composable; testable in isolation; the payload file is mutated before apply.

(c) **Inside the apply script as a sub-step**: a function in apply_close_out.py invoked when the payload contains a `commits` section in manifest form. No flag; the script detects manifest vs full-record entries and backfills accordingly.

Recommended: Option (c) — least friction for Doug, no new entry points to remember.

### Question 4 — Payload schema versioning

When the payload schema gains a `commits` section, do older payloads still apply? Older payloads will have no `commits` key; the apply script should treat absent or empty as "no commits to process," not as an error.

Recommended: no version bump. Treat the section as optional; absent means empty.

### Question 5 — Apply ordering

Current apply order: sessions → decisions → planning_items → references → deposit_event (lazy-created at apply close). References go last because they depend on every other entity type existing. Where do commits go?

Recommended: sessions → decisions → planning_items → commits → references → deposit_event. Commits before references because references may target commits (e.g., a `decision is_about commit` reference); commits after planning_items for the same reason (a commit might reference a planning_item via `addresses`).

### Question 6 — Idempotency on re-run

The apply script's existing pattern: HTTP 409 on duplicate identifier is treated as SKIP, not failure. For commits, the natural-key conflict is on `commit_sha` (returned as 409 with the existing identifier per slice B's implementation), distinct from identifier collisions. The apply script needs to recognize both as SKIP signals when the corresponding record's content matches what was already POSTed.

Recommended: treat HTTP 409 from `POST /commits` as SKIP regardless of which constraint fired (identifier or SHA). Idempotent re-runs land the same records.

### Question 7 — Multi-repo handling within a single close-out

A close-out conversation may produce commits in multiple repositories (e.g., a methodology change that lands in both `dbower44022/crmbuilder` and `dbower44022/ClevelandBusinessMentoring`). The payload's `commits` array carries `commit_repository` per entry, so the schema admits multi-repo natively. The helper, however, needs to know which repos to walk.

Recommended: the helper accepts a `--repos` argument (or auto-detects from the working directory's git configuration) and walks each in turn. The payload's `commits` array is unified across repos; entries are distinguished by `commit_repository`.

### Question 8 — Test scope target

The slice B baseline is 1481 passed + 3 skipped. PI-030 adds tests for:
- Apply ordering with the new section
- The HTTP 409 SKIP behavior on duplicate commit_sha
- The helper's git-metadata extraction
- The conversation-attribution rule (especially the manual-commit case from Q2)
- The payload schema versioning posture (older payloads with no commits section still apply)

Rough estimate: 20-30 new tests. Settle target in passing.

---

## Deliverable

The planning conversation produces:

1. **PI-030 Claude Code prompt(s)** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-030-{slice-letter-or-descriptor}.md`. The slicing depends on the Question 1 architecture decision:
   - If Option C: one prompt for the payload schema + apply script changes (slice A), one prompt for the helper script (slice B). Or one combined prompt if the changes are small.
   - If Option A or B: likely a single prompt covering schema + apply + helper together.
2. **A close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`** for the planning conversation itself, with the architecture decision and the conversation-attribution rule captured as governance decisions, and the corresponding `decided_in` references plus one `is_about` from the session to PI-030.
3. **The matching apply prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`** so Doug can run the close-out before running the slice prompts.

All three files commit and push from the sandbox in the same turn at session close (the ephemeral-container push convention).

---

## Read list (required before drafting the slice prompt)

1. `PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md` v1.0 — entity schema; §3.5.2 client-side identifier assignment is the part most relevant to apply-script integration.
2. `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` v1.0 — methodology authority; §5 commit attribution is the part most relevant to Q2.
3. `crmbuilder-v2/scripts/apply_close_out.py` — current implementation. Look in particular at how `references` is handled as the last section (the existing pattern PI-030 extends).
4. `crmbuilder-v2/src/crmbuilder_v2/access/repositories/commits.py` — the access layer PI-030 POSTs through; in particular the `create_commit` signature, the SHA uniqueness behavior, and the `commit_conversation_id` FK check.
5. `crmbuilder-v2/src/crmbuilder_v2/api/routers/commits.py` — the REST endpoints; the POST status code (201) and the error envelope shape for HTTP 409.
6. At least one prior close-out payload as reference for the existing payload shape — `PRDs/product/crmbuilder-v2/close-out-payloads/ses_067.json` is the most recent and reflects current conventions.

Optional but useful:

7. `tests/crmbuilder_v2/access/test_commit.py` and `tests/crmbuilder_v2/api/test_commit_api.py` — the slice B tests; PI-030's tests parallel their pattern.

---

## Close-out expectations

- **1 session record** — the PI-030 planning conversation.
- **Decisions** — likely 2-4. Question 1 (architecture) is the most consequential and likely the only stop-the-flow under the two-part test. Question 2 (conversation-attribution rule) is the second-most-consequential and may pass the stop-the-flow test. Questions 3-8 are likely decide-and-announce; some may bundle into single decision records.
- **Planning items** — likely zero new planning items; PI-030 stays Open until the slice prompts execute, and PI-031 / PI-033 already exist.
- **References** — one `decided_in` per decision; one `is_about` from the session to PI-030.
- **Artifacts produced** — the PI-030 Claude Code prompt(s).
- **In flight at end** — PI-030 prompts queued for Claude Code execution; PI-031 (Commits panel UI) and PI-033 (historical back-fill) remain Open and inherit PI-030's machinery.

Use status value `Active` on every newly-authored decision (the API enum is `Active` / `Deleted` / `Superseded` / `Withdrawn` — not `Final`; see memory edit #25 for the SES-067 precedent on this).

---

## What is explicitly NOT in scope for this conversation

- The Commits panel UI — that's PI-031.
- Historical commit back-fill against existing repo history — that's PI-033, downstream of PI-030's machinery.
- Cross-repo commit linking (one repo's commit referencing another repo's commit) — future workstream.
- Anything touching the existing slice B implementation (`commits.py` access layer, REST router, derived endpoint). Those are settled by DEC-211..214.
- Changes to the methodology document beyond what the architecture and attribution-rule decisions explicitly require.

---

## Operating mode

ARCHITECTURE inherited from project default. Question 1 (architecture) and possibly Question 2 (conversation-attribution rule) are the questions likely to pass the two-part stop-the-flow test (real downstream impact AND multiple viable options producing meaningfully different outcomes). Questions 3-8 are decide-and-announce. The eight-element consequential-decision template applies to whichever questions stop the flow.

Apply prompts authored at close-out must NOT include `git push` in the snapshot-regeneration commit step — that violates the "you commit, I push" Claude Code convention. Per memory edit #25 (the SES-067 precedent), only sandbox commits push together. The close-out's matching apply prompt should commit the snapshot regeneration as a single commit with the standard message format and stop there.
