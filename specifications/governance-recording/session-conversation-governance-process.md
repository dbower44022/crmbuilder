# Session/Conversation Governance Process — Process PRD

| Field | Value |
|-------|-------|
| Version | 0.3 |
| Last Updated | 09-04-26 00:45 |
| Status | DISCUSSION DRAFT — render of process record PROC-010 (mission_critical, domain DOM-012) as of 09-04-26 |
| Audience | Anyone opening, conducting or closing a session against a V2-tracked engagement; PI-088 authors |
| Governs | Nothing on its own. The process record PROC-010 and its links in the V2 store are the source (DEC-393, DEC-394, DEC-1021); this file is a render and goes stale between renders |

## Purpose

This document renders the Session/Conversation Governance Process as recorded in the V2 store: the first concrete process of the Governance Recording domain (DOM-012), fulfilling DEC-310's mandate that the recording rules are encoded as a process's steps, edge cases and acceptance criteria rather than a separate rules document. It exists so a reader of the repository can review the process without opening the store. When this file and the store disagree, the store is right and this file needs re-rendering. Produced under PI-087 (REQ-410) per DEC-311; rulings DEC-1034 to DEC-1038 applied. Engagement ENG-001, project PRJ-023.

## 1. Process metadata

| Field | Value |
|---|---|
| Name | Session/Conversation Governance Process |
| Domain | DOM-012 Governance Recording (candidate) |
| Owner persona | Engagement Lead (PER-013, TERM-012) |
| Performing personas | Claude Code Agent (PER-014), Claude.ai Sandbox Agent (PER-015), Engagement Lead (PER-013), Consultant (PER-005), Scheduler (PER-006) |
| Classification | `mission_critical` from the first write (DEC-1038): if this process stops, the store stops being the source of truth. The process record has no status field (process spec §3.4); "candidate" is carried by this draft's status. |
| Version | 0.2 |
| Medium coverage | One process, four variants of the recording mechanism |

**One process, four variants.** The rules bind every agent and medium alike (REQ-066); what differs is only how the record reaches the store. Each step below is tagged for the variants it applies to: **[CC]** Claude Code Agent with the live store (real-time writes, REQ-095); **[SB]** Claude.ai Sandbox Agent without it (close-out payload, REQ-096..098); **[HU]** a session with no AI agent — an email, a call, a meeting (REQ-077) — recorded afterwards by the Engagement Lead or Consultant through the API/MCP (REQ-064); **[PL]** a pipeline session, opened by the Scheduler against a work task, with the pipeline agents recording under their contracts (DEC-1037). Two or more records would duplicate every step but a handful and need hand-off edges between things that never hand off. The pipeline's own mechanics — reconciliation, planning, phase batches, gates — stay in PROC-009 Release Pipeline and are referenced, not repeated.
*Evidence: REQ-066, REQ-077, REQ-096, DEC-383, DEC-1022, DEC-1037.*

**Owner: Engagement Lead.** The owner must hold authority over the rules, be present in every variant, and own the one step no agent may perform. The Lead approves the rulebook and its overrides (GVR-241), is the only persona in all four variants (in [PL] as the human a `needs_attention` flag halts for), and alone pushes — the act that gates resolution (LSN-045, LSN-066). Ownership is stated in `process_notes` and carried by a `process_performed_by_persona` edge; no owner field or kind exists and none is proposed.
*Evidence: GVR-241, LSN-045, LSN-066, DEC-1009, DEC-1022.*

**Domain Overview §5 candidates absorbed as steps:** (2) session open / kickoff pre-flight → steps 1–5; (3) scheduled session handoff → steps 4 and 18; (4) triple-artifact close-out → the [SB] variant of steps 16–20; (6) planning-item resolution after push → steps 17–18; (12) compliance verification → step 16 and section 9. The rule: a candidate is a step when it happens inside one session, every time, by the session's own personas. **Kept separate:** (5) Model A build-closure spans branch, merge and a later build-closure conversation (TERM-055) and invokes this process twice; (7) project open/close outlives any session — only its membership edges appear here; (8) rule authoring, (10) terminology and (11) knowledge capture have their own record lifecycles, for which this process stops at step 14; (9) release close-out belongs to a release; the pipeline run itself is PROC-009.

## 2. Trigger

A unit of communication begins against a V2-tracked engagement in any medium: from a kickoff prompt, from a planned session handed forward, ad hoc, or — [PL] — when the Scheduler opens a session with a `session_works_work_task` edge to dispatch a work task inside a frozen release (PROC-009).
*Evidence: REQ-065, REQ-077, REQ-079, DEC-1037.*

## 3. Inputs

The engagement identifier; the rulebook (TOP-013 and children, effective rules and preferences for the session's audience — `claude_code`, `sandbox` or `ado_agent`); the kickoff work ticket and its planning item, the planned session, or [PL] the work task; identifier heads read live ([SB]: supplied in the kickoff by the Lead); the parent project; prior sessions and decisions on the same planning item; the working-tree state; reference pointers and lessons on demand.
*Evidence: REQ-067, REQ-068, REQ-071, REQ-072, GVR-238, LSN-040, TERM-042.*

## 4. Steps

**Agent** = whichever of Claude Code Agent, Claude.ai Sandbox Agent, Engagement Lead or Consultant runs the session; in [PL] the Scheduler opens and closes, the pipeline agent records in between. **Lead** = Engagement Lead only. A step with no variant tag applies to all four.

### Open

| # | Step | Persona | Condition | Recorded | Evidence |
|---|---|---|---|---|---|
| 1 | Read the rulebook and confirm the engagement. [CC] the SessionStart hook loads the claude_code-audience rules and preferences; then TOP-013 and children, pointers, lessons the task touches. [SB] the kickoff carries them. [PL] the agent contract resolves the ado_agent-audience rules. Name the engagement on every request. | Agent | Always, before any record | Nothing | REQ-067, REQ-072, GVR-238, GVR-241, PI-437 |
| 2 | Capture identifier heads live. [CC] `GET /<type>/next-identifier` per type. [SB] from the kickoff; every issued identifier is marked reserved, never guessed. [PL] n/a — identifiers are server-assigned. | Agent | [CC] [SB] [HU] | Heads noted in the session description | REQ-068, REQ-071, DEC-300 |
| 3 | Anchor: identify the project; fetch the work ticket and its planning item ([PL] the work task and its planning item); health-check the API; bring the working tree current (a worktree when the clone is shared). A build with no confirmed requirement and implementing planning item stops here until they exist ([PL] the freeze already guarantees this). | Agent | Always | Nothing | REQ-072, LSN-040, GVR-230, REQ-248, LSN-065, GVR-017 |
| 4 | Open the session: create it (`in_flight`, medium, executive summary 200–800 chars from the kickoff) or transition the planned one `planned → in_flight`. Medium: [CC] `claude_code` — the value is being built under REQ-561 (second slice of PI-462); until it lands, `chat` is recorded (DEC-1035); [SB] `chat`. Check the create succeeded before any edge. Edges: `session_belongs_to_project`; `session_opens_against_work_ticket` or [PL] `session_works_work_task`; `session_follows_from` when continuing. | Agent ([PL] Scheduler) | Always; a session that will produce nothing is still opened | Session (ENT-045); edges to Project (ENT-048), Work Ticket (ENT-052) or work task | REQ-065, REQ-075, REQ-078, REQ-079, REQ-099, REQ-102, LSN-041, LSN-056, DEC-1035, DEC-1037 |
| 5 | Open the first conversation with its purpose and the verbatim seed prompt ([PL] the dispatched task). Edges: `conversation_belongs_to_session`, `conversation_belongs_to_project`, `addresses` → planning item, `conversation_follows_from` when continuing. | Agent | Always | Conversation (ENT-046); edges to Session, Project, Planning Item (ENT-040) | REQ-080, REQ-083, REQ-090, REQ-105 |

### Conduct

| # | Step | Persona | Condition | Recorded | Evidence |
|---|---|---|---|---|---|
| 6 | Do the substantive work under the conduct charter and the phase guide ([PL] the agent's phase batch under its contract, PROC-009). | Agent | Always | Nothing directly | Master PRD §11; PROC-009 |
| 7 | **Decision point.** Before asking: re-read the store for rulings `is_about` the same planning item since the draft was read, and check for a live peer session on it. Ask as labelled options with costs. When the Lead rules, author the decision *now*: eight-element template, executive summary, status Active; edges `decided_in` → session, `is_about` → planning item and each affected record. Work named in its consequences that crosses the session gets a planning item at once (step 8). **n/a in [PL]** — a pipeline agent raises `needs_attention` and halts; the ruling is recorded by the Lead's own session under [CC] or [HU]. | Agent asks and records; Lead rules | [CC] [SB] [HU], each ruling | Decision (ENT-047); edges; often a Planning Item | REQ-085, REQ-086, REQ-089, REQ-092, REQ-099, REQ-100, GVR-237, LSN-074, DEC-1037 |
| 8 | **Work surfacing.** Cross-session work without a planning item gets one when it surfaces: `item_type: pending_work`, executive summary, `planning_item_belongs_to_project`, `planning_item_implements_requirement` where one exists, `blocked_by` where sequenced; the conversation's `addresses` edge. Work finished in the session stays in prose. [PL] surfaced work is a `needs_attention` flag or a finding; the human session files the item. | Agent | Each surfacing, including "we should also", "follow-up:", "this needs" | Planning Item; edges | REQ-088, REQ-089, REQ-101, PROC-009 |
| 9 | **Disposition of an existing artifact.** The decision states it in consequences and carries the `supersedes` or `withdraws` edge; Superseded status only with `superseded_by` populated. The `withdraws` kind (decision → artifact) is being registered under REQ-560 / PI-462; until it lands a withdrawal is status-only, Withdrawn, with the disposition in consequences (DEC-1034). The revision work is a planning item. **n/a in [PL].** | Agent records; Lead rules | [CC] [SB] [HU], each disposition | Decision; edge; Planning Item | REQ-087, REQ-092, REQ-100, DEC-1034 |
| 10 | **Requirement approval record.** The approving decision plus `requirement_approved_by_decision`; never a status edit. **n/a in [PL]** — the pipeline consumes approved requirements and never approves. | Lead approves; Agent records | [CC] [SB] [HU], each approval | Decision; edge | GVR-230, REQ-248, DEC-1011, GVR-017 |
| 11 | **Commit capture.** Confirm the branch; commit with a pathspec and `Governed-By: PI-NNN` naming an executable planning item (or `Governed-By: trivial` + `Exemption-Reason:`). [CC] [PL] `POST /commits` with the ten required fields and `commit_session_id`; no push. [SB] `commits[]` in the payload, pushed the same turn. Commit at once under a parallel session. A code branch carries only code; the build's bookkeeping lands on `main` after merge, re-keyed to current heads. | Agent commits; Lead pushes | Each commit touching code | Commit (ENT-051) | GVR-229, GVR-235, GVR-236, REQ-320, LSN-038, LSN-039, LSN-045 |
| 12 | **Topic boundary.** When the topic no longer fits the deliverable, the planning item or project would change, the decision context shifts, the user signals a switch, or the deliverable changes type: stop. Conclude the conversation (summary, `complete`, its `addresses` edge), open the next with `conversation_follows_from`, or propose a new session. Ask when unclear. [PL] n/a — one work task is one topic and one session. | Agent | [CC] [SB] [HU], each boundary | Conversation closed; Conversation opened | REQ-080, REQ-081, REQ-082 |
| 13 | **Re-check heads** before any amendment touching identifier slots and after any pause. On collision: renumber, update every internal reference, record it. | Agent | [SB] always; [CC] [HU] only when identifiers were reserved; [PL] n/a | Renumbering note | REQ-069, REQ-070, DEC-300 |
| 14 | **Stop for the separate processes.** New term: flag and wait. Learned hazard or how-to: a lesson with `lesson_derived_from`. Rule change: its own decision. Project scope change: a decision and the project updated in the same session. [PL] n/a — anything learned goes in the PI report for the human session. | Agent proposes; Lead approves | As they arise | Lesson (ENT-057); Decision; Project | GVR-232, GVR-238, REQ-076, REQ-543 |
| 15 | **Rule violation noticed mid-session.** Record it where it happened and correct the record; never paper over it. [PL] raise `needs_attention`. | Agent | On noticing | Lesson or note | DEC-310, LSN-056, PROC-009 |

### Close

| # | Step | Persona | Condition | Recorded | Evidence |
|---|---|---|---|---|---|
| 16 | Run the close-out completeness audit (section 9) against the session's records; fix what it finds. [PL] the Scheduler runs it on the agent's records before the next dispatch. | Agent ([PL] Scheduler) | Always, before anything is sealed | Corrections | DEC-310, DEC-1037 |
| 17 | Conclude each conversation: executive summary from content, within limits; `complete`; an `addresses` edge. The final delivering conversation gets `resolves` instead — **only after the Lead has pushed**, verified in-session with `git merge-base --is-ancestor <sha> origin/main`. If the push has not landed when the session ends, the planning item stays executable and the resolve is handed forward (step 18); the Lead does not record it and no hook fires it (DEC-1036). [PL] the conversation is concluded under the agent contract; the planning item advances through PROC-009's gates, not this step. | Agent; Lead pushes | Always | Conversations; `resolves` flips the Planning Item | REQ-090, REQ-099, REQ-102, LSN-043, LSN-047, LSN-066, DEC-1036 |
| 18 | Hand work forward: a `planned` session carrying the kickoff, edged to the project (and work task); a planning item for everything else. A pending resolve is named in the handoff, and the **next session opened against the item** verifies the push (`git merge-base --is-ancestor` against `origin/main`) and fires `resolves` from its own delivering conversation (DEC-1036). [PL] n/a — the Scheduler dispatches the next work task. | Agent | When work remains | Session (planned); Planning Items | REQ-079, REQ-088, LSN-041, DEC-1036 |
| 19 | Complete the session: final executive summary, ordered coverage summary with deferred topics, concrete artifacts only; `complete`. A content-free session says so. | Agent ([PL] Scheduler) | Always | Session | REQ-065, REQ-078, REQ-105 |
| 20 | [SB] only: author the close-out payload (label plus every section, empty ones as empty arrays) and the apply prompt (pre-flight, one `apply_close_out.py` run, post-apply verification); commit and push with the deliverable in the same turn. The Lead applies on `main`; the apply lazy-creates the payload and deposit event; the deposit log is committed with the deliverables. A pre-created session is patched to `complete` after the apply. | Sandbox Agent; Lead applies | [SB] | Close-out Payload (ENT-053), Deposit Event (ENT-054) | REQ-096, REQ-097, REQ-098, LSN-016, LSN-038, LSN-042, LSN-045 |

## 5. Entities touched

| Entity | Open | Conduct | Close |
|---|---|---|---|
| Engagement ENT-049; Governance Rule ENT-055; Preference ENT-056; Reference Pointer ENT-058 | read | read on demand | — |
| Lesson ENT-057 | read on demand | create (14, 15) | — |
| Project ENT-048; Work Ticket ENT-052 | read (3) | Project updated (14) | — |
| Session ENT-045 | create or update (4) | — | update (19); create planned (18) |
| Conversation ENT-046 | create (5) | update, create (12) | update (17) |
| Planning Item ENT-040 | read (3) | create (7, 8, 9) | flipped by `resolves` (17, or 18 in the next session); create (18) |
| Decision ENT-047 | — | create (7, 9, 10, 14) | — |
| Reference ENT-050 | create (4, 5) | create (7–12, 14) | create (17, 18) |
| Commit ENT-051 | — | create (11) | — |
| Close-out Payload ENT-053; Deposit Event ENT-054 | — | — | [SB] lazy-created (20) |

## 6. Personas involved

Engagement Lead PER-013: owner; rules at 7, 9, 10; approves at 14; pushes at 17; applies at 20; the human a [PL] `needs_attention` halts for. Claude Code Agent PER-014: steps 1–19 [CC]. Claude.ai Sandbox Agent PER-015: steps 1–20 [SB]. Consultant PER-005: [HU] in a client session. Scheduler PER-006: opens (1–4), audits and closes (16, 19) every [PL] session; the pipeline agents PER-007..PER-012 record steps 5, 6, 8, 11, 15 under their contracts. Project Manager (customer) PER-003 rules in a client session; recording the ruling is the agent's.
*Evidence: DEC-1009, DEC-1015, DEC-1022, DEC-1037; PI-086 persona records.*

## 7. Exception handling

- **Store unreachable at open.** Proceed on the irreducible core (requirement-first, `Governed-By`, pathspec commit, no new term); the SessionStart hook prints the last snapshot under a banner; the rule check fails open with a warning. Nothing authored offline is a record until reconciled with the live store. *CLAUDE.md bootstrap; PI-437, PI-439.*
- **Identifier collision.** Re-query, renumber, update every internal reference, record it; on a push conflict the Lead keeps the already-applied close-outs canonical. *REQ-070, DEC-300.*
- **A peer session mid-ruling.** A ruling recorded since the draft was read is already answered; a live peer on the same item is messaged before the Lead is asked; if two rulings land, the earlier stands and the later is superseded by decision. *LSN-074, DEC-1024.*
- **A failed create.** The API returns 200 with `errors`; assert the identifier matches `^[A-Z]{2,4}-[0-9]+$` before any edge, abort the edge loop otherwise, audit for dangling edges. *LSN-056.*
- **Apply failure [SB].** Read the deposit event for the diagnostic, patch the payload, re-apply. *ENT-054.*
- **No push yet at close.** The planning item stays executable; the closing session names the pending resolve in its handoff (step 18); the next session opened against the item verifies the push with `git merge-base --is-ancestor` against `origin/main` and fires `resolves` from its own delivering conversation. The Lead does not record it; no hook resolves. *LSN-047, LSN-066, DEC-1036.*
- **A planning item that must stay open.** `addresses`, never `resolves`, never a status edit. *REQ-090, LSN-043.*
- **A closed project.** Never reopen; new project, move the items; re-enumerate live before closing any project. *GVR-233.*
- **[PL] anything a pipeline agent cannot resolve** — mis-scoped task, duplicate work, missing dependency, absent done-condition, a rule violation — is a `needs_attention` flag; the pipeline halts for the Lead. *PROC-009, DEC-1037.*

## 8. Anti-patterns

| Anti-pattern | Recorded by |
|---|---|
| Batching decisions or work to close-out when the store is reachable | REQ-085, GVR-231, DEC-310 |
| Work named only in a consequences paragraph or `in_flight_at_end` | REQ-089 |
| Edges written from an unchecked create response | LSN-056 |
| Asking the Lead a draft's question without re-reading the store | LSN-074 |
| Resolving before the push, or by status edit; the Lead or a hook firing the resolve | LSN-047, LSN-066, REQ-090, DEC-1036 |
| Build first, backfill the requirement later | LSN-039, GVR-230 |
| Continuing across a topic boundary | REQ-081 |
| Guessing heads, or trusting a committed export | REQ-069, REQ-071, DEC-300 |
| Bare commit, or a commit on an unchecked branch, in a shared clone | GVR-235, LSN-065 |
| A held sandbox commit, or a Claude Code push | LSN-045 |
| An executive summary made by truncating the description (PI-087's own ends mid-sentence at "1.") | REQ-099 |
| Decisions tied to their conversation by `conversation_relates_to` alone, no `decided_in`; a conversation without its project edge — both true of CNV-360 / DEC-1003 at this reading | REQ-075, REQ-083, REQ-092 |
| A withdrawal recorded as a status flip with no disposition in consequences | REQ-087, DEC-1034 |
| Re-adding store-owned knowledge to files | GVR-238 |
| A term coined in a draft without flagging it | GVR-232 |

## 9. Acceptance criteria — the close-out completeness audit

A reviewer runs this against a finished session from the store alone. Items marked [PL] apply to pipeline sessions; items 3, 4 and 5 are n/a there.

1. The session is `complete`, medium set ([CC] `claude_code` once REQ-561 lands, `chat` until then), executive summary 200–800 chars from content, `session_belongs_to_project` present; [PL] `session_works_work_task` present. *REQ-065, REQ-075, REQ-078, REQ-099, DEC-1035, DEC-1037.*
2. Every conversation has `conversation_belongs_to_session`, `conversation_belongs_to_project`, an `addresses` or `resolves` edge, status `complete`; a continued topic has `conversation_follows_from`. *REQ-083, REQ-090.*
3. Every decision made in the session has `decided_in` → this session, a legal status, an executive summary; every disposition has its `supersedes` or `withdraws` edge — until the `withdraws` kind lands (REQ-560 / PI-462), a withdrawal shows status Withdrawn and the disposition in consequences. *REQ-087, REQ-092, REQ-100, DEC-1034.*
4. Work named in any decision's consequences that crosses the session is a planning item; every planning item filed has an originating decision or conversation edge. *REQ-088, REQ-089.*
5. Every placeholder phrase in the summaries has a planning item. *PI-087.*
6. Every code commit is a commit row with the ten required fields and a `Governed-By` trailer naming a planning item executable at commit time. *GVR-229, REQ-320.*
7. No reference touching the session's records has a `source_id` or `target_id` failing `^[A-Z]{2,4}-[0-9]+$`. *LSN-056.*
8. Every `resolves` edge post-dates the push that carried the delivering commits, and was fired from a delivering conversation — of this session, or of the next session opened against the item — never by the Lead or a hook. *LSN-066, DEC-1036.*
9. No conversation or session is left `in_flight`; a planned session exists where work continues, and a pending resolve is named in it. *REQ-078, REQ-079, DEC-1036.*
10. [SB] The payload has every section, the deposit event succeeded, the deposit log is committed on `main` with the deliverables. *REQ-097, REQ-098, LSN-038.*
11. The seed prompt and an ordered coverage summary are on the record; artifacts named are concrete. *REQ-105.*
12. [PL] Every `needs_attention` raised in the session is recorded and was resolved by a human before the pipeline continued. *PROC-009, DEC-1037.*

## 10. Outputs

The session's governance records: session, conversations, decisions, planning items, references, commit rows, lessons; a planned session where work is handed forward, naming any pending resolve; deliverables committed under `Governed-By`; [SB] payload, apply prompt and deposit log committed and pushed; the planning item advanced or, after the verified push, resolved.

## 11. Rulings applied

1. **DEC-1034** — a `withdraws` reference kind (decision → artifact) is registered under REQ-560 / PI-462 (Draft, PRJ-123); step 9 and audit item 3 keep "supersedes or withdraws", withdrawals are status-only until the kind lands.
2. **DEC-1035** — `session_medium` gains `claude_code` under REQ-561, the second slice of PI-462; step 4 records `claude_code` for [CC], `chat` until the value lands.
3. **DEC-1036** — when the push lands after the session ends, the closing session hands the pending resolve forward and the next session opened against the item verifies the push (`git merge-base --is-ancestor` against `origin/main`) and fires `resolves` from its own delivering conversation; the Lead does not record it, no hook resolves (steps 17, 18; exception "No push yet at close").
4. **DEC-1037** — pipeline sessions are a fourth variant [PL], performed by the Scheduler (PER-006) with the pipeline agents recording; every step carries its [PL] applicability, steps 7, 9, 10 are n/a there; the mechanics stay in PROC-009.
5. **DEC-1038** — the process record is created `mission_critical` at first write.

Personas PER-013 Engagement Lead, PER-014 Claude Code Agent and PER-015 Claude.ai Sandbox Agent now exist (PI-086 resolved); the payload's persona edges name them, plus PER-005 and PER-006.

**Open questions:** none. **[TERM NEEDS APPROVAL]:** none. [CC], [SB], [HU] and [PL] are document markup, not terms; "close-out completeness audit" is PI-087's own phrase, used descriptively.

## Change log

| Version | Date | Change |
|---|---|---|
| 0.1 | 09-03-26 | Discussion draft authored in SES-388 / CNV-360 under PI-087 per DEC-311, with five open questions. |
| 0.2 | 09-04-26 | Rulings DEC-1034 to DEC-1038 applied: withdraws edge kind and claude_code medium as REQ-560 / REQ-561 under PI-462; resolve-after-push ownership; the pipeline variant [PL]; mission_critical at first write. |
| 0.3 | 09-04-26 00:45 | First committed render. Process record PROC-010 and twenty-four links written to the store on Doug's approval; PI-087 resolved (SES-388 / CNV-360). |
