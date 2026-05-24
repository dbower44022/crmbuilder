# PI-029 Slice B — Commit Access Layer and REST Endpoints — Kickoff Prompt

**Last Updated:** 05-23-26 23:30
**Work ticket kind:** kickoff_prompt
**Status:** ready
**Workstream:** Code Change Lifecycle (established in SES-057)
**Planning item this conversation contributes to:** PI-029 (slice B; slice A landed in commit `9c1d3b7`)
**Predecessor conversation:** SES-063 (PI-028 commit entity schema spec; settled DEC-198 status-free documentary lifecycle, DEC-199 FK-over-references-edge deviation, DEC-200 four new cross-spec precedents). Commit spec at `PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md` v1.0 is the authoritative input.
**Spec authority for this slice:** `governance-schema-specs/commit.md` §3.2 (validation), §3.4.3 (administrative correction), §3.4.4 (soft-delete semantics), §3.5 (REST endpoints), §3.8.1 (derived endpoint URL shapes), §3.8.2 (SHA-256 anticipation deferred).

---

## Goal

Settle the build-planning design questions in commit.md §3.8.1, §3.8.5, and a small number of access-layer ergonomics calls that the spec did not fully specify, then author the slice B Claude Code prompt that will land:

1. The access-layer module for commits (`crmbuilder-v2/src/crmbuilder_v2/access/commit.py`) — CRUD methods plus the `get_by_sha` natural-key lookup plus the access-layer validations from commit.md §3.2 (SHA format, parent_shas array shape, repository format, FK existence).
2. The REST endpoints (`crmbuilder-v2/src/crmbuilder_v2/api/commits.py`) — the nine-endpoint standard set from commit.md §3.5.1 plus the new `GET /commits/by-sha/{sha}` with the four-case behavior (full SHA, unambiguous prefix, ambiguous prefix → 409, miss → 404).
3. The tests covering acceptance criteria 4-11 from commit.md §3.7 (FK existence enforcement, SHA validation, SHA uniqueness, parent_shas validation, repository validation, by-sha four-case behavior, soft-delete cycle).

Slice A landed migration 0012 (commits table, refs CHECK extensions, blocks→blocked_by data migration, vocab.py updates) and the commit ORM model. Slice B builds on top.

---

## Pre-decided by commit.md (do not re-litigate)

These are settled by the v1.0 spec and the slice B prompt records them verbatim:

* Field set, types, validations, defaults per commit.md §3.2
* Standard endpoint URL paths per §3.5.1 (`/commits`, `/commits/{identifier}`, `/commits/by-sha/{sha}`, `/commits/next-identifier`, plus POST/PATCH/PUT/DELETE/restore)
* Client-side identifier assignment per §3.5.2 (apply script computes; helper exists for symmetry)
* Identifier collision returns HTTP 422 with `identifier_collision` envelope
* SHA collision returns HTTP 409 with `commit_sha_duplicate` and the existing identifier
* Soft-delete-with-restore semantics per §3.4.4 (DELETE sets `commit_deleted_at`, restore clears it, SHA uniqueness applies across soft-deleted)
* Identity fields (`commit_identifier`, `commit_sha`) are not updatable via PATCH or PUT per §3.5.1
* `commit_conversation_id` IS updatable for administrative correction per §3.4.3
* Default V2 envelope `{data, meta, errors}` per existing convention
* Default list-endpoint pagination per V2 convention (the existing access-layer pagination helper handles this)
* By-sha endpoint excludes soft-deleted by default; `?include_deleted=true` includes them per §3.5.1

---

## Design questions for the conversation to settle

### Question 1 — Derived endpoints to ship in slice B

The spec's §3.8.1 names two candidate derived endpoints and defers the URL-shape decision to build-planning:

(a) `GET /conversations/{conversation_identifier}/commits` — list every commit produced by a specific conversation. Equivalent to `GET /commits?commit_conversation_id=<id>` against the standard list endpoint; the derived URL is just more discoverable.

(b) `GET /workstreams/{workstream_identifier}/commits` — list every commit produced by any conversation belonging to the workstream. Two-hop query (workstream → conversations → commits). Either implemented as a two-step query at the endpoint or by denormalizing workstream linkage onto the commits table.

Recommended: ship (a) in slice B (one-line derived endpoint over the existing list query); defer (b) to slice C or later. The two-hop query benefits from cross-entity visibility this slice doesn't need, and the operational use case ("show me every commit in workstream X") is not yet documented as critical. Settle the call; alternatives may include shipping both, shipping neither (rely on `?commit_conversation_id=<id>`), or shipping (a) plus a stub for (b).

### Question 2 — By-sha endpoint prefix-matching specifics

The spec's §3.5.1 names "any prefix of any length 4+" for `GET /commits/by-sha/{sha}` and the four-case behavior. Three sub-questions:

(a) **Minimum prefix length.** Spec says 4+. Confirm: 4 hex characters is enough? Git's own `--short` default is 7. Recommended: 4 (per spec); reject prefixes of 1-3 hex chars with HTTP 422 `prefix_too_short`. Alternative: bump to 7 to match git's `--short` convention.

(b) **Case normalization.** The schema stores lowercase per §3.2.1. What does the endpoint do if the caller supplies uppercase or mixed case (e.g., `GET /commits/by-sha/ABC123`)? Recommended: lowercase the input before query; return the matched record. Rejecting uppercase as HTTP 422 is a worse API ergonomic. Confirm.

(c) **Ambiguous-prefix 409 response body shape.** Spec §3.5.1 sketches `{"data": null, "meta": ..., "errors": [{"code": "ambiguous_sha_prefix", "candidates": ["<sha-1>", "<sha-2>", ...]}]}`. Confirm the field name (`candidates`) and that candidates are returned as full 40-char SHAs (vs identifier strings or both). Recommended: full 40-char SHAs only; the caller already has them as the natural key.

### Question 3 — `commit_parent_shas` updatability via PATCH

The spec §3.2.4 says `commit_parent_shas` is the parent-SHA list, intrinsic to the commit object. Spec §3.4.3 (administrative correction posture) admits PATCH for "any correction that doesn't change the commit's identity" — but the parent SHAs are arguably part of identity (they define the commit's position in the git DAG). 

Recommended: parent_shas IS updatable via PATCH, on the grounds that mis-ingestion (e.g., apply script bug capturing wrong parent SHAs from `git log --format=%P`) is the rare-correction case the spec's PATCH path was designed for. The narrow identity-fields-only restriction stays on `commit_identifier` and `commit_sha`. Confirm or surface alternatives.

### Question 4 — `commit_files_changed_count` and other denormalized field updatability

Spec is silent on whether the denormalized count field updates via PATCH. Parallel question to Q3. Recommended: yes, updatable, same administrative-correction rationale. Cosmetic decision; settle in passing.

### Question 5 — List endpoint sort parameters

Spec §3.6.2 names default UI sort `commit_committed_at` descending. What does the list endpoint's default sort look like at the API level? Recommended: API default is also `commit_committed_at` descending (matches the UI; matches the audit-log convention deposit_event established). Allow `?sort=<column>` and `?order=asc|desc` query params per V2's existing list-endpoint pattern. Settle in passing.

### Question 6 — Test scope target

Slice A landed 34 passed + 2 skipped across migration, vocab, and ORM model tests. Slice B's tests cover the full access-layer + REST surface. Rough estimate: 30-40 new tests. The acceptance criteria 4-11 from commit.md §3.7 are the minimum coverage gate; broader coverage of edge cases (empty lists, pagination boundaries, malformed input) is welcome.

Recommended: hit acceptance criteria 4-11 verbatim plus the four sub-questions above (Q1's derived endpoint behavior, Q2's prefix-matching cases, Q3/Q4's updatability allowances, Q5's sort param behavior). Settle target test count in passing.

---

## Deliverable

One file:

**`PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-B-commit-access-layer-and-rest.md`** — the Claude Code prompt that lands the access layer, REST endpoints, and tests. Standard structure paralleling slice A's prompt: Purpose + Net Effect block; Pre-flight (clean tree, git identity, pull, restart the API to pick up v0.8 vocab — Doug's PID 3226223 is still holding pre-v0.8 vocab and needs a restart before tests can validate end-to-end); Implementation steps; Run tests; Commit.

The Claude.ai planning conversation produces the prompt; Doug runs it via Claude Code in a subsequent session.

---

## Read list (required before drafting)

1. `PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md` v1.0 — authoritative input. §3.2 (validation rules), §3.4.3-§3.4.4 (correction posture, soft-delete), §3.5 (endpoints), §3.8.1 (derived endpoints), §3.8.5 (sub-grouping deferred).
2. `crmbuilder-v2/src/crmbuilder_v2/access/work_ticket.py` — closest existing access-layer module pattern (similar audit-grain governance entity, similar CRUD shape).
3. `crmbuilder-v2/src/crmbuilder_v2/access/close_out_payload.py` — second-closest pattern; contains the lazy-create-on-deposit_event flow that may inform how the commit access layer interacts with the apply script in PI-030.
4. `crmbuilder-v2/src/crmbuilder_v2/api/work_tickets.py` (or whichever endpoint module is the current name) — REST endpoint pattern.
5. `crmbuilder-v2/src/crmbuilder_v2/access/commit.py` if slice A's commit `9c1d3b7` already created a stub — verify what's there; the slice B prompt extends what slice A left in place.

Optional but useful:

6. `crmbuilder-v2/tests/crmbuilder_v2/api/test_work_tickets.py` — test patterns for the REST layer.
7. `crmbuilder-v2/tests/crmbuilder_v2/access/test_work_ticket.py` — test patterns for the access layer.

---

## Close-out expectations

* **1 session record** — the slice B planning conversation.
* **Decisions** — one per consequential design call. Estimate: 2-3 decisions. Q1's derived endpoint scope is the most consequential (commits the API to a URL shape that future workstreams inherit). Q2's by-sha specifics may bundle into one decision. Q3/Q4/Q5 are likely "decide and announce" rather than separate decision records.
* **Planning items** — likely zero. PI-029 stays Open; PI-033 resolves retroactively.
* **References** — one `decided_in` per decision; one `is_about` from the session to PI-029.
* **Artifacts produced** — the slice B Claude Code prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-029-B-commit-access-layer-and-rest.md`.
* **In flight at end** — slice B prompt queued for Claude Code execution; slice C (apply script integration — actually PI-030, separate planning item) and slice D (Commits panel UI — actually PI-031, separate planning item) remain Open.

---

## What is explicitly NOT in scope for this conversation

* The Commits panel UI — that's PI-031.
* The `apply_close_out.py` integration that wires the new `commits` close-out payload section — that's PI-030.
* Historical commit back-fill — that's PI-033.
* The two-hop `GET /workstreams/{id}/commits` derived endpoint (deferred per Q1's recommendation, settle differently if you choose).
* SHA-256 migration anticipation — deferred per spec §3.8.2.

---

## Operating mode

ARCHITECTURE inherited from project default. Q1 is the only question likely to pass the two-part stop-the-flow test (real downstream impact AND two viable options producing meaningfully different outcomes — ship one derived endpoint or two or zero). Q2/Q3/Q4/Q5 are decide-and-announce.
