# CRM Builder — Governance Recording Rules

**Version:** 0.1 DISCUSSION DRAFT
**Last Updated:** 05-27-26 05:30
**Purpose:** Normative rules for authoring governance records in V2 — workstreams, sessions, conversations, decisions, planning items, references, work tickets, and close-out payloads. Applies equally to AI agents (Claude.ai sandbox conversations, Claude Code instances) and human agents operating against any V2-tracked engagement.
**Scope:** All sessions and conversations operating against any V2-tracked engagement, present and future (CRMBUILDER dogfood, Cleveland Business Mentors, anything to come). Authoritative for record-authoring discipline; non-authoritative for stakeholder-facing interview conduct (see `PRDs/process/conduct/charter.md`).
**See also:** `PRDs/process/conduct/charter.md` (interview conduct — orthogonal scope), `PRDs/process/conduct/kickoff.md` (interview pre-session priming), `PRDs/process/conduct/question-library.md` (interview worked examples).

---

## 0. Purpose, Scope, and Applicability

**What this document is.** A normative reference for how governance records get authored in V2. Every record type V2 tracks has rules — when it is created, what fields are required, what status values are legal, how it connects to other records. This document collects those rules in one place so every Claude.ai conversation, every Claude Code instance, and every human operator has the same operating manual.

**What this document is not.**
- Not a Domain definition. Governance recording fails the "mission stops, mission survives" test — it is operational discipline, not a domain of the work.
- Not a formal Cross-Domain Service definition. V2 has no Cross-Domain Service object yet; formal modeling is premature. The eventual home — likely a Cross-Domain Service called "Conversation Management" or similar — is future architecture, acknowledged but not in scope here.
- Not a wrapper for the Master CRMBuilder PRD or any Domain Overview. This document is location-neutral working content until V2 supports the proper consolidating wrapper.

**Who it governs.** AI agents (Claude.ai sandbox conversations, Claude Code instances) and human agents (Doug, future operators) equally, per DEC-310. There is no AI-only carve-out and no human-only carve-out.

**Core principle: API and MCP only.** All record creation and modification goes through the V2 REST API or its MCP adapter. The V2 desktop UI is for **monitoring and scheduling**, not for authoring records. Every section below assumes this; no section repeats it. Exceptions, if any ever exist, must be named explicitly in this document.

**Core principle: Mandatory logging.** Every Claude.ai chat thread, every Claude Code execution, and more broadly every *session* (in the post-DEC-299 sense — see §3) that operates against a V2-tracked engagement is logged. **There is no off-the-record communication.** A session that produces no governance content beyond the session record itself still gets a session record; the closing turn states the absence of further content explicitly, and that statement is the log. The Mandatory Logging principle is what makes the V2 database an actual source of truth rather than a partial mirror of what people remembered to write down.

**Engagement targeting.** Every governance record lands against a specific engagement's database. CRMBUILDER dogfood work targets the CRMBUILDER engagement. Client work (e.g., Cleveland Business Mentors) targets the client's engagement. The target engagement is determined from the conversation's subject matter and confirmed in the session-opening handshake.

---

## 1. Identifier Discipline

**Capture heads at session start.** Per DEC-300, every session opens by capturing the current head identifier for every record type that may be created or referenced during the session. The canonical capture is the curl block in the session's kickoff prompt against `http://127.0.0.1:8765` — Sessions, Conversations, Decisions, Planning Items, Work Tickets, Workstreams.

**Re-check before mid-session amendment.** If a session pauses, branches, or otherwise risks heads advancing between the original capture and the next identifier-issuing moment, re-capture before issuing. No head-guessing. A guessed head that collides with a freshly-created record produces a payload that fails on apply.

**Renumbering protocol.** When a session has reserved identifiers (e.g., DEC-318 and DEC-319) and a heads-advancement reveals the reservation has collided with newer records (DEC-318 was used elsewhere), the session renumbers its own reserved identifiers to the next available slots and updates every internal reference in the working payload. The renumbering is captured in `topics_covered` so the close-out reflects what actually happened.

**Kickoff prompt pre-flight requirements.** Every v2 session kickoff prompt's pre-flight section must direct the agent to:
1. Read the engagement's `CLAUDE.md` (repo-level — `crmbuilder/CLAUDE.md` for dogfood, the client repo's `CLAUDE.md` for client work).
2. Read **this document** (`specifications/governance-recording-rules.md`) before authoring any governance record.
3. Capture identifier heads via the canonical curl block against `http://127.0.0.1:8765` — Sessions, Conversations, Decisions, Planning Items, Work Tickets, Workstreams.
4. Identify the parent workstream (WS-NNN) the conversation belongs to.
5. Run an API health check (any 200 OK against the engagement's API).
6. `git pull --ff-only origin main` (or rebase if a divergent local branch exists).

A canonical kickoff prompt template that bakes these in by default is a follow-on item, not in scope for v0.1 of this document. Until that template exists, the responsibility rests on the author of each individual kickoff.

---

## 2. Workstream Authoring

**When created.** A workstream is created at the moment a coherent multi-session body of work is recognized — orchestrator development, audit feature v1.2, catalog ingestion. One workstream may span weeks and many sessions. Workstreams sit above sessions and conversations in the V2 hierarchy.

**Mechanism.** Direct API POST or MCP call. Workstreams are not bundled into close-out payloads under current convention (zero of 68 payloads in the snapshot mention workstreams). They are written directly via `POST /workstreams`. The desktop V2 UI is monitoring-only for workstreams as for everything else.

**Required fields.** `workstream_identifier` (WS-NNN, next available head), `workstream_name`, `workstream_purpose`, `workstream_description`, `workstream_status` (initial: `in_flight`), `workstream_started_at`.

**Lifecycle.** `in_flight` → `complete`. Terminal states also include `cancelled` and `superseded`, each with a corresponding timestamp field.

**Conversation parentage.** Every conversation record carries a `conversation_belongs_to_workstream` reference to its parent workstream. The parent workstream identifier is captured at session-opening handshake alongside identifier heads.

**Scope-change decisions.** When a session decides to widen, narrow, or merge workstream scope (precedent: DEC-309 bundled executive-summary work into WS-012 rather than creating a separate workstream), the change is authored as a Decision in the normal moment-of-decision flow. The workstream record's `workstream_purpose` or `workstream_description` is updated in the same session via direct API PATCH.

---

## 3. Session Record Authoring

**What a session is (per DEC-299).** A session is a discrete unit of communication in any medium — one Claude.ai chat thread, one Claude Code execution, one email, one phone call, one Zoom meeting, one in-person interview. One Claude.ai chat = one session. One session contains one or more conversations as its topical sub-units (see §4). DEC-299 directs that documentation describe sessions and conversations in this post-redesign shape **even before PI-073's schema migration completes**; the conceptual model leads, the schema follows.

**When created.** The session record is initialized at session start (the opening of the Claude.ai chat, Claude Code execution, etc.) and finalized at close-out. Pre-PI-073 schema: the SES record is authored at close-out time bundled into the close-out payload. Post-PI-073 schema: the session record is created via API at session open and updated as conversations complete; close-out finalizes status and bundles outputs. Both pre and post, the bundle-in-payload mechanism remains operative for the close-out moment — not via a desktop New Session dialog.

**Required fields.** `identifier` (SES-NNN), `title`, `session_date`, `status` (only `Complete` is emitted at close-out), `conversation_reference` (descriptive text fallback — partially superseded once `conversation` is a first-class entity per PI-073), `topics_covered`, `artifacts_produced`, `in_flight_at_end`, `summary`.

**`topics_covered` opens with the verbatim seed prompt** rendered as:
```
Seed prompt: "<task statement>"
```
followed by a structured summary of what the session actually covered, in order. Topics that surfaced and were deferred get a one-liner each so the trail is preserved. When the session contained multiple conversations, `topics_covered` organizes by conversation.

**`artifacts_produced`** is concrete: files written, prompts authored, draft documents created. "Discussion" is not an artifact. A planning item filed is not an artifact (the PI itself is the record); the artifact is what the PI captures.

**`in_flight_at_end`** carries anything genuinely unresolved at session close that did not become a Planning Item or Decision. This field is not a workaround for forgetting to author a PI — see §10.

**Session date format.** Use `YYYY-MM-DD` for new sessions. The CRMBUILDER snapshot contains heterogeneous historical formats (older sessions store `MM-DD-YY`); any script reading `session_date` normalizes on read.

**Medium classifier.** Per PI-073, sessions carry a medium-type classifier (`claude_ai_chat`, `claude_code`, `email`, `phone_call`, `zoom`, `in_person`, etc.) and medium-specific metadata. The classifier and metadata schema are open design questions in PI-073; until resolved, set medium-type best-guess in the session record's notes / description fields and revise once PI-073 lands.

---

## 4. Conversation Record Authoring

**What a conversation is (per DEC-299).** A focused topical discussion that takes place *within* a session. One session contains one or more conversations. Conversations are session-scoped — they do not span sessions. Cross-session topical continuity is expressed via the `conversation_follows_from` and `conversation_relates_to` reference edges, not by reusing conversation identifiers.

**The stop-and-log discipline.** When a topic shift becomes apparent within an open session, Claude **stops before proceeding**. At the boundary, Claude does one of two things:

1. **Close the current conversation and open a new one in the same session.** Author the current CONV record (transition to `concluded` status) via direct API POST. Then open a new CONV with appropriate fields and continue in the same Claude.ai chat thread. The new CONV becomes the next topical sub-unit of the current session.
2. **Suggest starting a new session.** If the new topic is large or unrelated enough that grouping it into the current session would muddy the close-out, Claude proposes closing out the current session and starting a fresh Claude.ai chat for the new topic.

Claude does **not** continue mid-thread as if no boundary existed. Topic shifts that aren't logged produce muddled CONV records that no one can later parse.

**Conversation boundary heuristics.** A boundary has been crossed when one or more apply:
- The user introduces a topic that doesn't fit the current conversation's deliverable or reasoning thread.
- The conversation's parent PI or workstream would change.
- The decision-context shifts so that the current reasoning no longer applies.
- The user explicitly signals a switch ("now let's switch to…", "different topic — …").
- The deliverable changes type (was drafting a document, now debugging code; was discussing architecture, now authoring a kickoff prompt).

Unclear cases get clarified, not assumed. The cost of asking is one turn; the cost of conflating two conversations into one CONV record is permanent.

**Required fields.** `conversation_identifier` (CONV-NNN), `conversation_title`, `conversation_purpose`, `conversation_description`, `conversation_status`, and lifecycle timestamps.

**Lifecycle.** `planned` → `started` → `concluded`, with `not_started` available for conversations that were planned but never opened during the session. Terminal: `cancelled`, `superseded`. The status transition to `concluded` is the authoring moment that triggers the direct API POST.

**Authoring mechanism.** Direct API POST at the boundary moment, not bundled into the close-out payload. The close-out payload references conversations via the references section (each conversation already exists in the live DB by the time close-out runs). The transitional v0.8 payload schema carries a singular `conversation` block at top level — see §9 — that is being plural-ized by PI-073.

**Required references at authoring time.**
- `conversation_belongs_to_session` → parent SES-NNN (captured at session open).
- `conversation_belongs_to_workstream` → parent workstream WS-NNN (inherited from the session's workstream by default; override only when a conversation legitimately addresses different workstream).
- For continuation conversations: `conversation_follows_from` → the prior CONV-NNN in the prior session whose topic this conversation continues.

**Transcript capture infeasibility (DEC-025).** Per-conversation transcript export from Claude.ai is not currently available. Conversation content is captured by structured prose in the conversation's `conversation_description` and in the parent session's `topics_covered`, not by transcript ingestion.

---

## 5. Decision Authoring

**Moment-of-decision authoring (DEC-310, DEC-311).** Decisions are authored at the moment they are made, not batched at session close-out. When a discussion produces a decision, the DEC record is drafted in the working payload before the conversation moves on. Batching decisions to close-out invites omission (the SES-089 precedent: ten decisions, two of which produced downstream work that never got recorded as Planning Items).

**Eight-element template.** Decisions surfaced through the consequential-decision flow follow the eight-element template defined in the userPreferences `consequential decision template` section: plain-language question, concrete example, options with concrete behavior, why it matters, cost of recommendation, recommendation, follow-on detail, decision request. The DEC record's `context`, `decision`, `rationale`, `alternatives_considered`, and `consequences` fields are populated from the corresponding template elements.

**Decision-disposition pairing.** Every Decision that supersedes, withdraws, deletes, or otherwise materially affects an existing artifact carries the disposition explicitly. The disposition is captured in `consequences` and reified via References (see §7) — typically a `supersedes` or `withdraws` reference to the affected record.

**Status values — what is legal.** `Active`, `Deleted`, `Superseded`, `Withdrawn`. The DB constraint accepts only these four. **Never emit `Final`** — this fails apply (SES-067 precedent). Use `Active` for an in-force decision; use `Superseded` only when an explicit superseding decision exists and `superseded_by_id` is populated.

**`decision_date`** is the date the decision was made, in `YYYY-MM-DD` format. If the decision spans a session that started one day and concluded the next, use the date of conclusion.

---

## 6. Planning Item Authoring

**When to file a PI.** Any work surfaced by the session that will not ship in this session and is not already captured as an existing PI. Includes: a decision's downstream implementation work, a follow-on document drafting task, a deferred analysis, a discovered bug not in scope for this session.

**Prose-vs-PI rule.** If the work is sufficiently routine that it will be executed in the same session, it stays in prose (the session summary captures it). If the work crosses a session boundary, it gets a PI. The fail mode is "captured only in `consequences` or `in_flight_at_end`" — that pattern means the work is invisible to backlog views and is forbidden. Every cross-session work item gets its own PI.

**Required fields.** `identifier` (PI-NNN), `title`, `description`, `item_type`, `status` (initial: typically `Open` or `Planning`).

**`item_type` values.** The universal value accepted across the apply path is `pending_work`. The CRMBUILDER engagement requires `item_type: "pending_work"` on every PI in a close-out payload — without it the apply errors with HTTP 422 (SES-069 precedent: PI-048 first apply 422'd). Other `item_type` values may exist for engagement-specific use, but `pending_work` is the safe default and the required value for close-out apply.

**Resolution.** When a PI's work completes, its `status` advances to `Resolved` and `resolution_reference` carries the SES that produced the resolution. The session whose work resolves a PI emits the status update in its close-out payload.

---

## 7. Reference Authoring

**What a reference does.** Links two governance records with a typed relationship. The universal references table avoids junction-table proliferation; every cross-record link goes through it.

**Required four-tuple plus relationship.** `source_type`, `source_id`, `target_type`, `target_id`, `relationship`. Field-key gotcha: the **API payload uses `relationship`**; the **DB column is `relationship_kind`**. Apply scripts that filter or read references match on `relationship`; raw DB queries match on `relationship_kind` (SES-051 / SES-052 precedent — SES-052's first apply 422'd on this exact mismatch).

**Minimum references per session.** Every Decision authored in the session emits a `decided_in` reference back to the session's SES. Every Conversation record emits `conversation_belongs_to_workstream` to its parent workstream. Every supersession or withdrawal Decision emits a `supersedes` or `withdraws` reference to the affected record. Beyond these minima, add `is_about` and other governance references as the conversation surfaces them.

**Common relationship vocabulary.** `decided_in`, `is_about`, `supersedes`, `withdraws`, `resolved_by`, `conversation_belongs_to_workstream`, `workstream_planned_in_reference_book`. The full vocabulary is registered in the V2 access layer's `vocab.py`; new relationship kinds require a vocab-registration step.

---

## 8. Work Ticket Authoring

**What triggers a WT.** A unit of operational work scoped to a single file or single artifact — a Claude Code prompt to author, a CLAUDE-CODE-PROMPT-*.md file to deliver, a SQL diagnostic script to run. Work tickets are finer-grained than Planning Items; one PI may spawn multiple WTs.

**Required fields.** `work_ticket_identifier` (WT-NNN), `work_ticket_title`, `work_ticket_description`, `work_ticket_kind`, **`work_ticket_file_path`**, `work_ticket_status`.

**`work_ticket_file_path` is always required**, including for `work_ticket_kind: 'other'`. The PI-025 backfill rejected six `wt_kind='other'` records that omitted the field. For backfilled or path-less tickets, use a placeholder path (e.g., `n/a`) or an empty string — never omit the key. The work_ticket.md spec's "omits path-existence validation" language refers to whether the value points to a real file on disk, not to whether the field is required in the record.

**Lifecycle.** `Ready` → `Consumed` (when the work has been picked up and executed) → terminal. Other states: `Cancelled`, `Superseded`, `Deleted`.

---

## 9. Close-Out Payload Authoring

**When emitted.** Every session that produces governance records ends with a close-out. Per the Mandatory Logging principle in §0, every session also produces a close-out even when no decisions, PIs, or other records were authored — in that case the close-out's session block explicitly states the absence and the other sections are empty. Empty sections are still listed, never omitted.

**v0.8 ten-element payload shape.** The close-out payload is a JSON object with one top-level label and nine record sections:

1. `label` — short identifier for the payload run.
2. `session` — the SES record itself, bundled into the payload.
3. `conversation` — the conversation record (singular under v0.8 schema; see transitional note below).
4. `work_tickets` — array of WT records authored or status-updated in the session.
5. `planning_items` — array of PI records created or status-updated in the session.
6. `commits` — array of git commit records the session produced (where applicable).
7. `decisions` — array of DEC records authored in the session.
8. `references` — array of reference records linking the above, plus governance references the session surfaced.
9. `resolves_planning_items` — array of PI identifiers this session resolves (atomic flip to `Resolved` per slice A of PI-030).
10. `addresses_planning_items` — array of PI identifiers this session advances without resolving.

Empty sections are present as empty arrays, never omitted. The session block bundles the SES record itself — not written separately through any other path.

**Transitional note (v0.8 → post-PI-073).** Under v0.8, the `conversation` section is **singular** — one conversation record per payload, matching the 1:0..1 SES↔CONV schema of v0.7/v0.8. PI-073 pluralizes this to a `conversations` array as part of the redesign decided in DEC-299. Until PI-073 lands, a session containing multiple conversations under the new conceptual model handles the singular constraint by: (a) authoring the additional conversations directly via API POST mid-session (per §4 stop-and-log), so each conversation exists in the live DB; (b) including only the final / primary conversation in the payload's `conversation` slot at close-out; (c) using the `references` section to link the session to each additional conversation explicitly. Post-PI-073, all conversations appear in the `conversations` array and the references-only workaround is retired.

**Payload location.** `{repo}/{target-engagement-close-outs-directory}/ses_NNN.json` where NNN is the SES identifier and the target engagement is determined from the conversation's subject matter. Repo-level CLAUDE.md documents the close-outs-directory path per engagement (CRMBUILDER: `PRDs/product/crmbuilder-v2/close-out-payloads/`).

**Apply prompt structure.**
1. **Purpose** with a Net Effect block listing the records that will land.
2. **Pre-flight** — working-directory check, clean-status check, git identity, `git pull --rebase`, payload-exists check, API health check, pre-apply identifier-head capture against the target engagement's database.
3. **Apply** — single `apply_close_out.py` invocation against the target engagement with expected-OK record counts.
4. **Post-apply verification** — identifier-head advancement, reference count delta, spot-check the session and one decision, spot-check `decided_in` reference resolution.
5. **Commit snapshot regeneration** — the apply script transactionally regenerates the engagement's `db-export/` JSON snapshots via the `_refresh_snapshot` hook (no standalone exporter is invoked); commit the snapshot files and `change_log.json` together with the standard message format.
6. **Done block** — reply with heads-before-and-after, record counts, snapshot-commit SHA, next-conversation kickoff path.

**Sandbox commit convention.** In Claude.ai sandbox conversations, the close-out payload and the apply prompt are **committed and pushed together in the same turn**. The sandbox container is ephemeral; a held commit is a lost commit. In Claude Code at Doug's terminal, Doug pushes after review.

---

## 10. Failure Modes

A short catalog of patterns that produce broken governance records and how to avoid them.

**Heads advanced mid-session without re-check.** A session reserves DEC-312 at start, runs for two hours during which another session uses DEC-312, and then emits a payload colliding on that identifier. Mitigation: re-capture heads before any mid-session amendment that issues identifiers. See §1.

**Decision reached but not authored at moment-of-decision.** A discussion produces a decision; the conversation moves on; the close-out is written hours later from memory; the decision is omitted or its alternatives_considered is reconstructed inaccurately. Mitigation: author the DEC in the working payload at the moment the decision is made. See §5.

**Cross-session work captured only in `consequences` or `in_flight_at_end`.** A decision implies work that will not ship in this session, but no PI is filed; the work shows up in the SES's `in_flight_at_end` and is then invisible to backlog views. Mitigation: every cross-session work item gets its own PI. See §6.

**PI filed against the wrong category.** What should have been authored as a Decision (a choice between alternatives with a rationale) gets filed as a PI (a pending work item). Mitigation: ask "is there a choice being made here, or is there only work to be scheduled?" Choice → DEC. Work-to-schedule → PI.

**Conversation authored without parent workstream reference.** A CONV record exists in V2 but `conversation_belongs_to_workstream` is missing; orphan conversation. Mitigation: capture the parent workstream identifier at session-opening handshake, alongside identifier heads.

**Topic shift without stop-and-log.** A session begins on topic A, drifts into topic B without authoring the topic-A conversation record, and emits a single CONV at close-out that conflates both topics. The governance record loses the boundary; later readers cannot tell where A ended and B began, and decisions made in B are attributed to A's conversation. Mitigation: recognize the boundary heuristics in §4 and stop. Author the current CONV as `concluded` before continuing, or suggest a new session.

**Multiple conversations conflated under v0.8 singular-conversation constraint.** A session contained three conversations under the new conceptual model, but only one shows up in the close-out payload's singular `conversation` slot, and the other two are nowhere in the payload (not authored mid-session, not linked via references). Mitigation: per §9 transitional guidance, author additional conversations via direct API POST mid-session and link them via the payload's references section until PI-073 pluralizes the schema.

**Off-the-record session.** A Claude.ai chat thread operates against a V2 engagement, produces material content, and ends without any session record being authored. The governance record is silent on a session that actually happened. Mitigation: per the Mandatory Logging principle in §0, every session against a V2 engagement is logged. Even content-free sessions get a session record stating the absence of further content.

**Snapshot lag between sandbox commits and post-apply commits.** A sandbox conversation pushes its close-out payload and apply prompt to GitHub; Doug runs the apply locally, regenerating snapshots in his local clone; if Doug has not yet pushed the snapshot-regen commit, the GitHub snapshot lags the live API. A subsequent sandbox conversation that reads only GitHub will see stale heads. Mitigation: every sandbox session re-captures live identifier heads at session start via the curl block, regardless of what the GitHub snapshot says.

**Heterogeneous date formats.** `session.session_date` in the CRMBUILDER engagement stores `MM-DD-YY` for older sessions and `YYYY-MM-DD` for newer; any script substituting `session_date` into an ISO datetime must normalize on read (PI-025 Stage D precedent). Author new sessions with `YYYY-MM-DD`.

**`Final` emitted as Decision status.** The DB constraint accepts only `Active`, `Deleted`, `Superseded`, `Withdrawn`. Emitting `Final` fails apply (SES-067). Mitigation: use `Active` for an in-force decision.

**`item_type` omitted on Planning Item.** PI emitted to close-out payload without `item_type: "pending_work"` 422s on apply (SES-069 / PI-048). Mitigation: every PI in a close-out payload carries `item_type: "pending_work"` unless an engagement-specific value applies.

**`work_ticket_file_path` omitted on WT of kind `'other'`.** Rejected at access layer; the field is required for every WT regardless of kind (PI-025 backfill Stage C). Mitigation: use a placeholder path or empty string, never omit the key.

---

## Revision History

| Version | Date | Notes |
|---|---|---|
| 0.1 | 05-27-26 04:30 | Initial discussion draft. |
| 0.1 | 05-27-26 04:55 | Added "Kickoff prompt pre-flight requirements" sub-section to §1, listing the six steps every v2 kickoff must direct the agent to perform. Same-session amendment, no version bump. |
| 0.1 | 05-27-26 05:30 | Aligned §0/§3/§4/§9 with DEC-299's post-redesign conceptual model: Session = medium-agnostic communication unit (1 Claude.ai chat = 1 session); Conversation = focused topical sub-unit (1:N within session). Added Mandatory Logging core principle to §0. Added stop-and-log discipline and conversation boundary heuristics to §4. Corrected §9 to actual v0.8 ten-element payload schema (label + 9 record sections) with transitional note about singular `conversation` slot pluralizing under PI-073. Added two failure modes to §10 (topic shift without stop-and-log; off-the-record session) plus a transitional-state pattern. |
