# PI-031 kickoff — commits panel UI + planning_item resolution display under Governance sidebar

**Last Updated:** 05-25-26 17:00
**Operating mode:** ARCHITECTURE (drops to DETAIL when authoring slice prompts).
**Status:** Ready for a conversation to open. Predecessor commits all on `origin/main`: PI-030 slice A `70d88e6`, slice B `2b5557d`, slice C `c6ff67a`, SES-074 build closure `24c42cf`, SES-074 apply snapshots `4fffbb7`. WS-009 active with `workstream_status: in_flight`. PI-030 status `Resolved`. PI-031 status `Open`.
**Authored at:** the close of SES-074 (PI-030 build closure), commit `24c42cf`.
**Anticipated session at close:** next available SES identifier — at least SES-076 once SES-075 (audit-v1.2 prompt-series close-out, prompt at `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-075.md`) applies, and possibly higher if further parallel-sandbox sessions intervene. Identifier-rebasing rule applies if parallel sandboxes close between this kickoff's authoring and the planning conversation's open, per the SES-073 → SES-074 precedent.

---

## Purpose

PI-031 ships the V2 desktop UI surfaces for the Code Change Lifecycle workstream's read path. Two user-visible surfaces and one prerequisite:

1. **Commits panel** under the Governance sidebar group (appended after Deposit Events per the v0.7 sidebar precedent in DEC-163). Read-only master/detail browser of the `commits` table. Filterable by repository, conversation, and planning_item; detail view shows each commit's edges (`commit_conversation_id`, work_tickets it addresses, planning_items it resolves).

2. **Planning_items panel — resolution-chain detail view.** When a planning_item is `Resolved`, the detail view displays the `resolution_reference` plus a clickable trail back through the resolving session → close-out payload → deposit_event → commits attributed to the resolving conversation. Materialization of the §6.1 audit query as a UI surface.

3. **Prerequisite slice — `commits.json` snapshot regeneration fix.** Surfaced by Doug post the SES-074 apply: `_refresh_snapshot` hook in the access layer is missing `commits` from its entity list, so the snapshot file isn't regenerated despite three commit records being written. Apply script's pretty-printer also doesn't know about `commit_identifier`, surfacing `<unidentified record>` cosmetically. Same root cause. Tiny fix (~10–20 lines + tests) but blocking — the UI reads from the snapshot.

Acceptance per PI-031's description: panels render; UI smoke tests pass; sidebar navigation works; the planning_items panel detail view materially helps a user trace a resolved planning_item back to its delivering commits without leaving the application.

---

## Read this first

- `crmbuilder/CLAUDE.md` is the operative engagement context. Confirm at session open before any work.
- `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` particularly §6 (audit query patterns — the resolution-chain detail view operationalizes §6.1, §6.2, §6.4) and §10 (build-closure pattern from SES-074 — explains why the FK chains exist).
- `PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md` particularly §3.6 (User interface considerations) and §3.7 (Acceptance criteria).
- v0.7 sidebar precedent: open the V2 desktop app and inspect the existing Governance sidebar group's entries (Workstreams, Conversations, Reference Books, Work Tickets, Close-out Payloads, Deposit Events). Commits goes after Deposit Events per DEC-163.
- UI v0.2 base CRUD dialog classes and widget subpackage at `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/` and `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/`. The read-only browser inherits from the v0.2 base classes where possible — DateField and ReferencesSection are likely reusable; HierarchicalEntityPicker is not.
- `_refresh_snapshot` access-layer hook at `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py` — the slice A target. Read its entity list to understand the omission.
- The SES-074 close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_074.json` for the three commit records the UI will display (`CM-0001`, `CM-0002`, `CM-0003`) — useful concrete test data.

---

## Pre-work state checks

The planning conversation runs the following before authoring slice prompts:

1. **Identifier heads** from `db-export/` snapshots (sessions, decisions, planning_items, conversations, workstreams, commits, close_out_payloads, deposit_events). Confirm SES-075's audit-v1.2 close-out has applied (or hasn't) and that PI-031 is still Open.
2. **Snapshot existence.** Confirm `db-export/commits.json` is still missing (or hopefully NOT — slice A regenerates it). If `commits.json` exists at pre-work time, some parallel session may have hand-regenerated it; reconcile before proceeding.
3. **Commits table state.** `GET /commits` returns at least three rows (CM-0001/0002/0003 from SES-074). If zero rows, slice A's API path is broken and PI-030 didn't actually land — halt.
4. **WS-009 status.** Should still be `in_flight`. If `complete`, some parallel work has prematurely flipped it — investigate.
5. **Repo state.** Sparse checkout includes `crmbuilder-v2/src/crmbuilder_v2/ui/` and `crmbuilder-v2/src/crmbuilder_v2/access/`. If not, expand before reading code.

---

## Anticipated slices

Subject to Q1 (snapshot fix scope) and Q5 (work_tickets panel inclusion); the final slice plan is the planning conversation's call:

- **Slice A — Snapshot generator + pretty-printer fix.** `_refresh_snapshot` hook extended with `commits` entity; `apply_close_out.py` pretty-printer extended with `commit_identifier` recognition. Tests cover (a) the snapshot regenerates on commit write, (b) re-apply of the SES-074 payload (idempotent) regenerates with three rows, (c) the apply log no longer shows `<unidentified record>` for commit rows. Backfill of the missing snapshot for the existing SES-074 commits handled by running any commit write or by a one-time direct-API touch on one of the existing rows. Pull request scope: small.

- **Slice B — Commits panel master view.** Sidebar entry under Governance, after Deposit Events. Master list shows: V2 identifier (`CM-NNNN`), short SHA, message first line, repository, committed_at (relative format), conversation identifier. Read-only — no New/Edit/Delete buttons. Subject to Q2 (default sort + grouping) for the master view's initial state.

- **Slice C — Commits panel detail view.** Right-pane detail shows full SHA, full commit message, all metadata fields, plus edges: outbound `commit_conversation_id` link, inbound `addresses` from work_tickets, inbound `resolves` and `addresses` from the same conversation to any planning items. Click-through to the linked records via the existing sidebar navigation pattern. Subject to Q3 (chain rendering).

- **Slice D — Commits panel filters.** Repository (dropdown — values from existing `commit_repository` distinct query), conversation (Q4 — typeahead vs dropdown), planning_item (Q4). Filters compose conjunctively. Clear-all button.

- **Slice E — Planning_items panel resolution-chain detail.** For `Resolved` items: render `resolution_reference` (linkified if it looks like a SHA per Q3-adjacent question), then a vertical chain widget showing session → close-out payload → deposit_event → commits. Each step clickable. Subject to Q3 (chain rendering).

- **Slice F (conditional on Q5) — Work_tickets panel updates.** If Q5 lands in-scope for PI-031: small detail-view updates to show inbound `addresses` from commits. If out-of-scope: defer to a future PI.

5–6 slices is the working estimate. Comparable to UI v0.2's six-slice scope and similar test-count growth (UI v0.2 added 458 - 264 = 194 tests over six slices; PI-031 anticipates roughly the same magnitude).

---

## Surface-and-settle questions

Five consequential questions. Light framing here — full eight-element treatment in the planning conversation per profile preferences. Defaults proposed; the conversation may override.

### Q1 — Slice A scope: targeted `commits` fix, or defensive audit of the whole `_refresh_snapshot` hook?

The hook may be missing other entities too. SES-074's apply regenerated snapshots for sessions, decisions, planning_items, conversations, workstreams, close_out_payloads, deposit_events, and references — so those eight definitely work. But commits was added in v0.8 and missed. Are there other v0.8-or-later entity types pending registration? (Worked example: if `commit` was missed, was `commit_identifier` also missed by the pretty-printer? Yes — confirmed cosmetic. Are there parallel oversights elsewhere?)

**Default: targeted fix** (`commits` plus the pretty-printer; about 10–20 lines). Cheaper. Risk of repeat bug if a future v0.9 entity is added without registering it.
**Alternative: defensive audit** — slice A also adds a test that asserts every registered entity in the access layer has a corresponding snapshot regen line in `_refresh_snapshot`, failing CI on any mismatch. Bigger slice (~50 lines + a meta-test). Prevents the pattern.

### Q2 — Commits panel master view default sort and grouping

The table can be displayed many ways. Three sensible default frames:
- **Chronological** (descending `commit_committed_at`) — like a git log, most-recent-first.
- **Per-conversation** (grouped by `commit_conversation_id`, sub-sorted by chronological) — like the v2 desktop's Conversations panel grouping pattern.
- **Per-repository** (grouped by `commit_repository`, sub-sorted by chronological) — multi-repo view.

**Default: chronological descending** (matches the audit-query mental model: "what's been committed recently"). Per-conversation grouping is a filter-state, not a default. Per-repository is fine as an alternative grouping toggle in the master view header.

### Q3 — Resolution chain rendering: linear stepper, vertical list, or graph subview?

PI-031's description says "clickable chain back through the resolving session, the close-out payload that authored the resolves edge, the deposit_event that applied it, and the commits associated with the resolving conversation." Three rendering options:

- **Linear stepper** (horizontal or vertical) — five steps shown in order: planning_item → session → close-out_payload → deposit_event → commits. Each step a clickable card.
- **Vertical list** — five sections stacked, each with the linked record's key fields and a click-through.
- **Graph subview** — a small node-and-edge widget showing the chain as a directed graph. Most flexible but most build cost.

**Default: vertical list with click-through cards** — matches the existing detail-view aesthetic in UI v0.2; lowest build cost; readable on the narrowest supported window width. Stepper is fine if the chain length is always exactly five steps but breaks when an `addresses` edge from another conversation extends the chain. Graph is overkill for the typical case.

### Q4 — Filter UI: dropdown, typeahead, or text-search?

Per filter dimension:
- **Repository**: small finite set (probably 1–4 values). Dropdown is appropriate.
- **Conversation**: 46 rows today, will grow. Dropdown becomes unwieldy past 100ish. Typeahead with identifier-or-title matching is the right pattern.
- **Planning_item**: 50 rows today, will grow. Same as conversation — typeahead.

**Default: dropdown for repository, typeahead for conversation and planning_item.** The typeahead widget is already in the UI v0.2 widget subpackage (used for HierarchicalEntityPicker's autocomplete); reusable.

### Q5 — Work_tickets panel updates: in PI-031 scope or separate?

PI-031's description names only commits panel + planning_items resolution display. Work_tickets aren't mentioned. But the audit chain §6.1 walks through work_tickets (commit → addresses → work_ticket; work_ticket → addresses → planning_item is an alternate path to resolution). A user clicking through a chain may want to see what work_ticket motivated each commit.

**Default: out of scope for PI-031.** The Work Tickets panel already exists (v0.7 entity); it just doesn't yet display inbound `addresses` edges from commits. Adding that is a small follow-on that can be its own slice in a later PI (or a slice F here if Q5 lands in-scope by Doug's call). Don't grow PI-031's scope; ship what the description named.

---

## Deliverables at close

1. **Close-out payload** at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` — nine-section v0.8 format (now the default). `commits` section enumerates the slice SHAs the planning conversation produces; `resolves_planning_items` flips PI-031; `addresses_planning_items` may include WS-009-adjacent items (PI-032, PI-033) that PI-031's UI implicitly advances.

2. **Apply prompt** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md` — follows the SES-074 template (no workstream pre-step needed; WS-009 already exists).

3. **5–6 slice prompts** at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-031-{A|B|C|D|E|F}-*.md` — DETAIL-mode Claude Code prompts, one per slice. Each authored after the planning conversation settles Q1–Q5 and before Doug executes the corresponding slice.

4. **Methodology amendments** if the planning conversation surfaces any. PI-031 is unlikely to drive methodology change — it's straightforward UI work — but the planning conversation should remain open to the possibility.

5. **Any DECs/PIs from Q1–Q5 settlements** plus any additional surfaces discovered during planning.

---

## Working conventions

- Claude.ai sandbox session. Push the planning conversation's close-out + apply prompt + slice prompts as one bundle at session end per sandbox convention.
- Doug executes each slice prompt at his terminal via Claude Code, then runs the apply prompt at session-end. The "you commit, I push" Claude Code convention applies inside each slice.
- WS-009 stays `in_flight`; the planning conversation does not flip it.
- The planning conversation's CONV record (next available, likely CONV-047 or higher) carries `conversation_belongs_to_workstream` → WS-009 per the convention DEC-237 established. No new workstream needed.
- The planning conversation's `conversation_purpose` opens with `"Planning conversation for PI-031 — "` (note: not "Build closure for SES-NNN — " — that convention is specifically for build closures per §10.2; this is a planning conversation, not a build closure).
- Identifier rebasing on parallel-sandbox collision per the SES-073 → SES-074 precedent.

---

## Successor work

After PI-031 lands, the natural downstream conversations are:

- **Build closure for PI-031.** Per §10's pattern, after the 5–6 Claude Code slice sessions execute, a dedicated build-closure Claude.ai conversation ingests the slice commits, resolves PI-031, and surfaces any methodology drift the executors discovered. Its kickoff is authored at the close of the planning conversation alongside the slice prompts.
- **PI-032** — methodology rollout. Repo `crmbuilder/CLAUDE.md` updates: close-out template documentation, work_ticket authoring rule. SES-074 partially advanced PI-032 via the §10/§5.5/§4.0 amendments; PI-032's tail work is the repo-CLAUDE.md side.
- **PI-033** — historical backfill. The big one. Best done after PI-031 + PI-032 ship so the machinery is fully exercised on live writes before backfill load.

---

## Open uncertainty (not blocking)

The planning conversation may discover that the UI v0.2 base CRUD dialog classes don't quite fit the read-only browser pattern PI-031 needs — UI v0.2 was CRUD-oriented (Risks, Planning Items, Topics) with full create/edit/delete dialogs. The commits panel has no create/edit/delete; it's pure read. Two paths if reuse breaks down:
- Adapt the v0.2 base classes (probably requires extending them with a "read-only mode" toggle) — establishes a pattern usable for all future read-only governance browsers (deposit_events panel under the same governance group is also read-only and already shipped, so a precedent may exist; check that panel's implementation first).
- Build a fresh read-only browser base class — duplicates some scaffolding but isolates the pattern.

This is implementation detail, not methodology; the planning conversation can defer until slice B authoring.

The work_tickets entity may need its existing UI panel updated to display inbound `addresses` edges from the new commits — that's the Q5 scope question. If Q5 settles in-scope, a slice F adds it; if out-of-scope, defer to a future PI.

The `commit_files_changed_count` field is captured but unused in the master view per Q2's default. The detail view shows it. Whether to make it filterable (e.g., "show only commits that touched >10 files") is implicit-out-of-scope unless the planning conversation surfaces a use case.
