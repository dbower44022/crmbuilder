# CRM Builder — Governance Recording Rules

**Version:** 0.1 DISCUSSION DRAFT
**Last Updated:** 05-27-26 04:30
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

**Engagement targeting.** Every governance record lands against a specific engagement's database. CRMBUILDER dogfood work targets the CRMBUILDER engagement. Client work (e.g., Cleveland Business Mentors) targets the client's engagement. The target engagement is determined from the conversation's subject matter and confirmed in the session-opening handshake.

---

## 1. Identifier Discipline

**Capture heads at session start.** Per DEC-300, every session opens by capturing the current head identifier for every record type that may be created or referenced during the session. The canonical capture is the curl block in the session's kickoff prompt against `http://127.0.0.1:8765` — Sessions, Conversations, Decisions, Planning Items, Work Tickets, Workstreams.

**Re-check before mid-session amendment.** If a session pauses, branches, or otherwise risks heads advancing between the original capture and the next identifier-issuing moment, re-capture before issuing. No head-guessing. A guessed head that collides with a freshly-created record produces a payload that fails on apply.

**Renumbering protocol.** When a session has reserved identifiers (e.g., DEC-318 and DEC-319) and a heads-advancement reveals the reservation has collided with newer records (DEC-318 was used elsewhere), the session renumbers its own reserved identifiers to the next available slots and updates every internal reference in the working payload. The renumbering is captured in `topics_covered` so the close-out reflects what actually happened.

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

**When created.** The SES record is authored at session close-out time, bundled into the close-out payload — not via a desktop New Session dialog. The bundle-in-payload mechanism is the operative path per the SES-046 through SES-052 precedent. The desktop-dialog framing in earlier kickoff prompts was descriptive of one available mechanism, not prescriptive.

**Required fields.** `identifier` (SES-NNN), `title`, `session_date`, `status` (only `Complete` is emitted at close-out), `conversation_reference` (descriptive text since per-conversation Claude.ai export is infeasible — DEC-025), `topics_covered`, `artifacts_produced`, `in_flight_at_end`, `summary`.

**`topics_covered` opens with the verbatim seed prompt** rendered as:
```
Seed prompt: "<task statement>"
```
followed by a structured summary of what the session actually covered, in order. Topics that surfaced and were deferred get a one-liner each so the trail is preserved.

**`artifacts_produced`** is concrete: files written, prompts authored, draft documents created. "Discussion" is not an artifact. A planning item filed is not an artifact (the PI itself is the record); the artifact is what the PI captures.

**`in_flight_at_end`** carries anything genuinely unresolved at session close that did not become a Planning Item or Decision. This field is not a workaround for forgetting to author a PI — see §10.

**Session date format.** Use `YYYY-MM-DD` for new sessions. The CRMBUILDER snapshot contains heterogeneous historical formats (older sessions store `MM-DD-YY`); any script reading `session_date` normalizes on read.

---

## 4. Conversation Record Authoring

**What it captures.** One CONV record per Claude.ai conversation (or Claude Code session). Carries `conversation_identifier` (CONV-NNN), `conversation_title`, `conversation_purpose`, `conversation_description`, `conversation_status`, and lifecycle timestamps.

**Required references at authoring time.**
- `conversation_belongs_to_workstream` → parent workstream WS-NNN (captured at session-opening handshake).
- One reference linking the CONV to its parent SES (typically created in the close-out payload's references section).

**Relation to SES.** A session may contain multiple conversations (e.g., a kickoff-drafting conversation and a follow-up execution conversation). The CONV-to-SES relationship is many-to-one. The SES is the unit of governance close-out; the CONV is the unit of Claude.ai chat.

**Transcript capture infeasibility (DEC-025).** Per-conversation transcript export from Claude.ai is not currently available. Conversation content is captured by descriptive prose in the parent SES's `topics_covered` and `conversation_reference`, not by transcript ingestion.

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

**When emitted.** Every session that produces governance records ends with a close-out. Clarification chats and planning-only discussions that produce no governance content do not need a close-out — but the absence is itself a choice, named explicitly in the session's closing turn.

**Four-section shape** (per SES-046 through SES-052 precedent):
1. `label` — short identifier for the payload run.
2. `session` — the SES record itself, bundled into the payload.
3. `decisions` — array of DEC records authored in the session.
4. `planning_items` — array of PI records created or status-updated in the session.
5. `references` — array of reference records linking the above, plus governance references the session surfaced.

The session block carrying the SES record itself is the operative bundle-in-payload mechanism. Do not write the SES separately through any other path.

**Payload location.** `{repo}/{target-engagement-close-outs-directory}/ses_NNN.json` where NNN is the SES identifier and the target engagement is determined from the conversation's subject matter. Repo-level CLAUDE.md documents the close-outs-directory path per engagement.

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
