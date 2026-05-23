# Session kickoff — SQLite transaction-semantics retrospective decision capture

**Last Updated:** 05-23-26 04:30
**Target session:** SES-057 (next-available after SES-056 v0.7 closeout)
**Operating mode:** ARCHITECTURE
**Repo:** `dbower44022/crmbuilder` (sparse-clone `CLAUDE.md`, `PRDs/`, `crmbuilder-v2/`)
**Anticipated deliverable:** one decision record (DEC-168) capturing the v0.7 Slice B SQLite transaction-control change retrospectively, plus the standard close-out payload and apply prompt

---

## Purpose

Author a retrospective decision record for the cross-cutting access-layer transaction-semantics fix that landed mid-v0.7 at commit `6d1c0bd4e101233e54a78bde2af04d11e7e11b2f` (single-file change to `crmbuilder-v2/src/crmbuilder_v2/access/db.py`, 23 lines added).

The change was made operationally during Slice B execution to resolve a Slice A "disaster condition" — governance edge-rule validation failures (post-insert checks like close_out_payload's applied-requires-edge rule) were not rolling back the auto-assigned identifier rows because pysqlite's default autocommit emulation durably committed `RELEASE SAVEPOINT`. The fix is the canonical SQLAlchemy SQLite recipe: `isolation_level=None` to disable autocommit emulation; explicit `BEGIN IMMEDIATE` via an SQLAlchemy `begin` event handler; `PRAGMA busy_timeout=5000` so concurrent writers queue rather than deadlock on lock upgrade.

The change shipped and the full access + API + UI + scripts suite stays green. What's missing is the governance record — future readers asking "why does `access/db.py` configure these specific SQLite settings, and what alternative was considered?" should find a DEC-NNN to navigate to, not just a commit hash buried in v0.7 Slice B history.

This session captures that decision retrospectively. It does not modify code. It produces one decision, one session record, one close-out payload, and one apply prompt.

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. The commit itself: `git show 6d1c0bd4e101233e54a78bde2af04d11e7e11b2f` — message and diff. The message is the most authoritative single source of context; quote from it directly in the decision text.
3. `crmbuilder-v2/src/crmbuilder_v2/access/db.py` — the current state of the file (after the fix), specifically the `_enable_sqlite_pragmas` and `_sqlite_emit_begin` functions and the `_build_engine` event registration.
4. The Slice B prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-B-api-endpoints.md` — does NOT mention the fix; the fix surfaced operationally during Slice B execution and is named in the v0.7 completion report rather than in any pre-existing prompt or plan.
5. Optional context: SES-055 build-planning conversation's close-out payload at `close-out-payloads/ses_055.json` — covers the broader v0.7 planning context; the SQLite fix postdates this payload by one day.

---

## The decision to author (anticipated DEC-168)

Following the eight-element template from Doug's user preferences. The session writes this verbatim into the decision record's structured fields (`context`, `decision`, `rationale`, `alternatives_considered`, `consequences`). Adapt the wording as needed — the structure below is a starting point, not a verbatim mandate.

**1. Plain-language question.** What SQLite connection-level transaction-control settings should the V2 access layer use so that an access-layer validation failure that occurs after an auto-assigned identifier row has been inserted rolls back the partial row cleanly?

**2. Concrete example.** A POST to `/conversations` that auto-assigns identifier CONV-NNN and then fails the post-insert edge-rule validation (e.g., the close_out_payload `applied`-requires-edge check, or an at-most-one rule violation) used to return HTTP 422 to the caller but durably persist the partial CONV-NNN row. Reproduced live during v0.7 Slice A integration testing.

**3. Options considered.**

- **(A) Manual explicit BEGIN/COMMIT/ROLLBACK in every multi-statement repository operation.** Each repository wraps its inserts and validations in an explicit transaction. More code, easy to miss, fragile against future repository additions.
- **(B) SQLAlchemy SQLite recipe at the engine factory** — `isolation_level=None` to disable pysqlite autocommit emulation + `BEGIN IMMEDIATE` via an SQLAlchemy `begin` event listener + `PRAGMA busy_timeout=5000` to handle short contention. One-time configuration in `db.py`; applies uniformly to all repositories without per-repository changes. The canonical fix documented in SQLAlchemy's SQLite dialect docs.
- **(C) Switch driver** — pysqlite to apsw or similar. Larger lift, untested in this codebase, no documented benefit beyond what (B) achieves.
- **(D) Switch database** — SQLite to Postgres. Out of scope at the V2 stage; pre-empts the per-engagement isolation model.

**4. Why this matters.** The transaction-semantics gap is cross-cutting — affects every repository's atomicity guarantee, not just the v0.7 governance ones. Without the fix, any post-insert validation across the access layer can leak partial state on failure. Locking in the choice as a navigable decision record matters because future repository authors (Claude or human) need to understand why `db.py` is configured the way it is and what they'd be changing if they touched it.

**5. Cost of the recommended option.** Slight increase in DB-layer complexity (the engine factory now installs two event listeners rather than one); requires all code paths to use the SQLAlchemy session correctly (no raw pysqlite access); marginal write latency under contention because `BEGIN IMMEDIATE` acquires the RESERVED lock at transaction start rather than upgrading on first write. None of these costs is meaningful at the V2 traffic volume — the full test suite runs faster under explicit transactions, per the commit message.

**6. Recommendation.** Option B (SQLAlchemy SQLite recipe). Already implemented and shipped at commit 6d1c0bd; this decision record locks it in retrospectively as the cross-spec architectural choice.

**7. Follow-on detail.**

- Implementation in `crmbuilder-v2/src/crmbuilder_v2/access/db.py` — three changes documented in the commit diff (busy_timeout PRAGMA, isolation_level=None, BEGIN IMMEDIATE event handler).
- Methodology repositories (the v0.4 ones) never hit the bug because they don't run post-insert validation that requires rollback; the bug surfaced when the v0.7 governance repos introduced edge-required-at-terminal rules.
- The fix is durable across all future repositories that follow the same post-insert-validation pattern.
- No test added specifically for this behavior because the existing access-layer test suite for the v0.7 governance repositories exercises the rollback path implicitly; if a regression reverts the fix, those tests fail.

**8. Decision request.** Approve option B as the recorded architectural decision (already implemented and shipped at commit 6d1c0bd; this is retrospective lock-in, not a change request).

---

## Working pattern for this session

- ARCHITECTURE mode; the decision was made operationally and is being formalized. No new architectural questions expected. If the session uncovers a related concern (e.g., absence of a test specifically targeting the rollback path), surface it but do not let it inflate scope — note it as a follow-on planning item if substantive.
- Plain text discussion; no `ask_user_input` widgets.
- One commit at session close: the close-out payload and apply prompt together.
- Sandbox push at session close (commit AND push together per sandbox convention).
- No code changes. The change shipped at commit 6d1c0bd; this session only authors the governance record.

---

## Close-out

Standard four-section close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_057.json`. Sections:

1. **`label`** — `"SES-057 SQLite transaction-semantics retrospective decision capture closed: 1 session, 1 decision (DEC-168), 0 planning items, N references"`.
2. **`session`** — `identifier: SES-057`, `title: "SQLite transaction-semantics retrospective decision capture for v0.7 Slice B fix at commit 6d1c0bd"`, `session_date: <session date>`, `status: "Complete"`, `conversation_reference`, `topics_covered` (open with the seed prompt verbatim per DEC-025, then a structured summary covering the bug, the four options, the chosen fix, the rationale, why retrospective capture matters), `artifacts_produced` (the close-out payload and apply prompt), `in_flight_at_end` (any follow-ons surfaced; e.g., "test specifically exercising the access-layer rollback path on edge-rule failure" if that emerged as a concern).
3. **`decisions`** — one decision: DEC-168 with the eight elements above mapped into the schema's `context`, `decision`, `rationale`, `alternatives_considered`, `consequences` fields. Plus `identifier: "DEC-168"`, `title`, `decision_date`, `status: "Active"`.
4. **`planning_items`** — empty array unless the session surfaces a substantive follow-on.
5. **`references`** — minimum: one `decided_in` (DEC-168 → SES-057), one `is_about` (SES-057 → DEC-165 or the SES-055 build-planning session as the v0.7 context anchor — choose the more navigable target), and any other references that improve discoverability. The decision text references commit 6d1c0bd; consider whether the references schema admits a commit-SHA target or whether that lives in the decision body only (likely the latter — references between governance entities, not file-system or git artifacts).

Apply prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-057.md` following the canonical pattern from `CLAUDE-CODE-PROMPT-apply-close-out-ses-055.md`. Pre-flight verifies SES-056 has been applied (since DEC-167 was authored there); apply step runs the close-out script against `ses_057.json`; post-apply verification confirms DEC-168 is present and queryable.

---

## Identifier notes

Anticipated identifiers (verified against the database snapshot at this kickoff's authoring time):

- **Session:** `SES-057`. SES-056 was the v0.7 build closeout, authored by Slice F.
- **Decision:** `DEC-168`. DEC-167 was authored at SES-056 closeout.

If a conversation closes between this kickoff's authoring and the SES-057 apply, the identifiers may shift. The session re-verifies via `GET /sessions/next-identifier` and `GET /decisions/next-identifier` at apply time and adjusts the payload before running the apply script.

---

## After this session lands

- Future readers asking "why does `access/db.py` set `isolation_level=None`?" find DEC-168 via the references panel of the desktop UI or via `GET /decisions/DEC-168`.
- The architectural choice is queryable as a first-class governance object rather than a commit-message footnote.
- v0.7's quiet engineering decisions are now part of the formal record alongside the planned ones.

Out of scope for this session: any code changes; any retrospective decision captures for other commits beyond 6d1c0bd; any work on PI-022 phases 2/3/4 or CBM domain work. Single focused decision capture, then stop.

---

*End of kickoff.*
