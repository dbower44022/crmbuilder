# Claude Code session prompt — PI-086: persona records for the Governance Recording domain

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 09-03-26 20:05 |
| Status | Ready to run |
| Audience | A fresh Claude Code session rooted in `~/Dropbox/Projects/crmbuilder` |
| Governs | Execution of PI-086 (REQ-409) in PRJ-023 |

**Written 2026-09-03 by the PI-085 session (crmbuilder-50, SES-392). Give this file to a
fresh Claude Code session. Read the PI, the requirement and the decisions named below from
the store before doing anything; the store is the authority and this file is orientation.**

You are executing **PI-086** ("Define the Personas referenced by the CRMBuilder
governance-recording Domain") in **PRJ-023** (Master CRMBuilder PRD consolidation + dogfood).
It implements **REQ-409** (confirmed): each persona the Governance Recording domain references
gets its own first-class record, reusable across domains. Output: three persona records in the
store, their links, and a committed render.

## 1. Before you start: two sessions may be near this item

The open-PI completion run (session **crmbuilder-bb**, SES-388 / CNV-360) drafted the persona
records on 2026-09-03 and holds PI-087 and PI-088 next in the chain. On 2026-09-03 it agreed to
hold PI-086 writes until Doug says which session runs PI-086. Doug giving you this prompt is
that word. Do this first, in order:

1. Run `ListAgents`. If crmbuilder-bb is listed, send it one message: you are running PI-086
   from this prompt, it should not write PI-086 records, and it may keep PI-087 and PI-088.
   Wait for no reply; proceed.
2. Read `GET /references?target_id=PI-086` and list every decision that `is_about` it and every
   conversation that `addresses` it. Anything recorded after 2026-09-03 23:30 UTC is new since
   this prompt was written: read it before asking Doug anything (lesson **LSN-074**: two
   sessions asked Doug the same PI-085 questions seven hours apart and the later rulings had to
   be superseded by DEC-1024).
3. Confirm `GET /personas` still lists only PER-002 to PER-012 and that no Engagement Lead,
   Claude Code Agent or Claude.ai Sandbox Agent record exists. If one exists, PI-086 was run
   elsewhere: stop and tell Doug.

## 2. Governance position (verified 2026-09-03 23:30 UTC)

- **Requirement-first is satisfied.** REQ-409 is `confirmed`; PI-086 implements it
  (`planning_item_implements_requirement`). No code is involved; this is records and a render.
- **PI-086 is `Draft`.** Its `blocked_by PI-085` edge is satisfied: PI-085 is `Resolved`
  (domain DOM-012 written, render committed as 75f906b9). Its `blocked_by PI-073` edge is
  satisfied (PI-073 Resolved). Move PI-086 to `In Progress` when you start, through the API.
- **The domain exists.** DOM-012 Governance Recording (candidate). Read its record: the notes
  field holds the whole overview, including the persona section. Render:
  `specifications/governance-recording/domain-overview.md` v0.3.
- **The names are settled; do not re-ask them.**
  - Engagement Lead: one persona, TERM-012 (renamed from Engagement Admin) — DEC-1009.
  - No Reviewer persona; reviewing is an Engagement Lead responsibility — DEC-1010.
  - Claude Code Agent (TERM-046) and Claude.ai Sandbox Agent (TERM-047) — DEC-1022.
  - Every pipeline agent persona PER-006..PER-012, plus PER-003 and PER-005, is already linked
    to DOM-012 — DEC-1015. Do not add or remove those links.
- **Glossary is complete for this work** (DEC-1023, TERM-048..055). A term you find yourself
  needing that has no entry is a new term: surface it to Doug, do not coin it (GVR-232).
- **Record as you go** (GVR-231): open a session (`session_belongs_to_project` PRJ-023,
  `session_follows_from` SES-392) and one conversation (`conversation_belongs_to_session`,
  `conversation_belongs_to_project`, `addresses` PI-086, `conversation_belongs_to_topic`
  TOP-013) before the first question to Doug. Inline edges on the create body need the
  identifier you are about to take: read the head, add one, pass it as `session_identifier`
  / `conversation_identifier` and as `source_id` in each edge. Executive summaries are
  200–800 characters.
- **Commits** are docs-only here (a markdown render and a manifest row). The pre-action hook
  still checks the commit text: use `Governed-By: PI-086` while PI-086 is executable
  (In Progress), and commit with an explicit pathspec after `git add` of any new file
  (GVR-235). Do not push; Doug pushes (LSN-045).

## 3. The two decisions Doug must make, one at a time

Both come from the v0.2 draft's open questions. Put each to Doug on its own, as labelled
options with the advantages and disadvantages of each and a recommendation (PRF-002, PRF-009),
in plain language (PRF-010), no question widget. Record each ruling as a decision the moment
it is given, with `is_about` edges to PI-086 and DOM-012 and a `conversation_relates_to`
edge from your conversation. Draft the options from the store facts, not from this file.

**Decision 1 — a participant record for Doug.** The Engagement Lead persona wants a
`persona_backed_by_participant` link to a participant record for the person who fills the
seat in ENG-001. On 2026-09-03 `GET /participants` returned only PTC-001..PTC-005 and none is
Doug. Re-verify. The choices the draft saw: create the participant now under PI-086 and link;
or create no participant and leave the persona unbacked until the engagement's stakeholder
map is revisited. The draft's payload assumes the first. Check what a participant record
needs (`ParticipantCreateIn` in the API schema) before you present the cost.

**Decision 2 — backing for the two AI personas.** Participants are meant to be the real
people and roles from the stakeholder map (Master PRD §11), yet PTC-005 is the Scheduler, an
agent. Choices: back the Claude Code Agent and Claude.ai Sandbox Agent with participant
records on the PTC-005 precedent; or keep participant backing for people and leave the two
AI personas unbacked, noting PTC-005 as an exception to be reviewed. The draft's payload
assumes the second.

If Doug's answer to either changes the draft, revise the affected section before writing.

## 4. Write, then render

After both rulings:

1. `POST /personas` three times (fields: `persona_name`, `persona_role_summary`,
   `persona_responsibilities`, `persona_notes`, `persona_status: candidate`), with the
   content of sections 1 to 3 below, revised for the rulings. Put the "Governance Recording
   duties" and "Never" lists in `persona_responsibilities` and the lifecycle, authority and
   backing facts in `persona_notes`, so the record holds everything the render shows.
2. `POST /references`: `persona_scopes_to_domain` from each new persona to DOM-012;
   `persona_backed_by_participant` as ruled; `is_about` from each ruling decision to the
   persona it affects. No `persona_realized_as_entity` — none of the three is tracked as data.
3. Append to DOM-012's `domain_notes` (PATCH) the three persona identifiers and the decision
   identifiers, so the domain record stays the source of its overview.
4. Render. The store is the source (DEC-393, DEC-394, DEC-1021); the file is a dated render.
   Personas are first-class and cross-domain, so the render lives outside the domain folder:
   `specifications/personas/governance-recording-personas.md` v0.1, with the frontmatter table
   (Version, Last Updated MM-DD-YY HH:MM, Status, Audience, Governs), a Purpose paragraph and a
   change log, and a row in `specifications/README.md`. Announce this path to Doug as a routine
   choice; it is not a decision to put to him unless he objects.
5. Bump the domain overview render to v0.4: `specifications/governance-recording/domain-overview.md`
   section 4 now names PER identifiers for the three personas; add a change-log row. The
   crmbuilder-bb session agreed on 2026-09-03 that whoever runs PI-086 does this bump. Do not
   edit v0.3 in place without the version and change-log row.
6. Commit the three files with an explicit pathspec and `Governed-By: PI-086`.
7. Tell Doug what to push. After he confirms the push, add the `resolves` edge from your
   conversation to PI-086 and set PI-086 to `Resolved` with a `resolution_reference` naming
   the persona identifiers and the commit. Never before the push (LSN-047, LSN-066).
8. Close your conversation and session as `complete` with summaries. State the next step:
   PI-087 (Session/Conversation governance Process), held by crmbuilder-bb unless Doug says
   otherwise.

## 5. The v0.2 persona draft (SES-388 / CNV-360, 2026-09-03; base material, not yet written)

Every claim below cites its record. Re-verify a citation before relying on it; treat the
draft as a starting point Doug has not yet accepted.

## 1. Engagement Lead

**Name:** settled (DEC-1009; TERM-012). Status: candidate.

**Role summary.** The person who runs one engagement end to end: sets it up, decides what it will and will not do, approves what is built, reviews what is delivered, and is the only human who moves work past the engagement's own gates. One seat, occupied by Doug in every engagement so far.

**Responsibilities.** Creates the engagement, charter and participants at kickoff (Master PRD §11). Approves every requirement, governance rule, and new or renamed term (GVR-232). Reviews each demonstrable increment before the next planning item launches (GVR-239; DEC-1010). Reviews the commits Claude Code lands locally and pushes them (LSN-045). Alone deploys to production (GVR-240 / DEC-907; REQ-477). Is the human an agent or phase halts for on `needs_attention` (GVR-234).

**Decision authority.** Final on every ruling the engagement records; agents surface options with costs, the Lead answers (GVR-237; PRF-009).

**Lifecycle.** From engagement setup (engagement, charter v0.1, participants, kickoff decisions and session) through every session in every domain, to engagement close.

**Governance Recording duties.**
- Bound by the same rules as the agents; no human carve-out (REQ-066; DEC-310).
- Approves a requirement only through an approving decision, never a status edit (GVR-230; REQ-248).
- Gives the go at the user-review checkpoint (GVR-239).
- Pushes; planning-item resolution follows the push, never precedes it (LSN-047; LSN-066).
- Approves the rulebook and engagement overrides (GVR-241); runs the production deploy himself (REQ-477).

**Never.** Resolves a planning item by editing its status — only a `resolves` edge does (REQ-090; LSN-043). Authors a record through the desktop UI, which is for monitoring (REQ-064). Reopens a completed project (GVR-233). Re-adds store-owned knowledge to files (GVR-238).

**Participant backing.** `persona_backed_by_participant` to a participant record for Doug in ENG-001. None exists — `GET /participants` returns only PTC-001..PTC-005 — so it must be created first (open question 1).

## 2. Claude Code Agent

**Name:** settled (DEC-1022; TERM-046). Status: candidate.

**Role summary.** The interactive AI that works a session at the terminal with the live store in reach. It does the session's work — analysis, drafting, code — and records every governance event by direct API write as it happens. It has no authority over content: it surfaces rulings to the Engagement Lead and records the answer.

**Responsibilities.** Orients from the store at session start — the SessionStart hook loads the `claude_code`-audience rules and preferences; TOP-013, pointers and lessons on demand (CLAUDE.md "Session bootstrap"). Executes the kickoff anchored on a planning item and work ticket (LSN-040). Builds only against a confirmed requirement with an implementing planning item (GVR-230). Commits with a pathspec and a `Governed-By` trailer while the item is executable (GVR-229; GVR-235; REQ-320).

**Decision authority.** None. Puts each choice to the Lead as labelled options (GVR-237; PRF-009) and records the ruling at that moment.

**Lifecycle.** One session, `in_flight` at open, `complete` at close (REQ-078). Open: heads captured live, engagement confirmed, project identified, API health-checked (REQ-067, REQ-068, REQ-072). Conduct: record as it goes; stop at every topic boundary (REQ-081, REQ-082). Close: one conversation per topic with its `addresses` or `resolves` edge, executive summary, transition to `complete` (REQ-083, REQ-099; Master PRD §11).

**Governance Recording duties.**
- Records every decision, planning item, session, conversation and reference by direct POST as it occurs (GVR-231; REQ-095; DEC-383).
- Reads heads and records from the live API, never files (REQ-071; GVR-238).
- Files a planning item for any work that will not ship in the session (REQ-088, REQ-089).
- Keeps branches to code only; bookkeeping lands on `main` after merge (LSN-038, LSN-039).
- Under parallel sessions, commits immediately and uses a worktree (GVR-236; LSN-065).
- Submits to the pre-action rule check and records any override reason (PI-439 / REQ-542).

**Never.** Pushes (LSN-045). Deploys to production (GVR-240). Fires `resolves` before the Lead has pushed (LSN-047; LSN-066). Coins a term without approval (GVR-232). Batches records to a payload when the store is reachable (GVR-231). Continues across a topic boundary (REQ-081).

**Participant backing.** None proposed. Participants are the real people and roles from the stakeholder map (Master PRD §11); this persona is a tool surface. PTC-005 Scheduler is a precedent the other way (open question 2).

## 3. Claude.ai Sandbox Agent

**Name:** settled (DEC-1022; TERM-047). Status: candidate.

**Role summary.** The interactive AI that works a conversation in the claude.ai sandbox, where the store cannot be reached. It does the same kind of work as its Claude Code counterpart but records through the fallback path: it authors the close-out payload and apply prompt, and commits and pushes them in the same turn because its container is ephemeral.

**Responsibilities.** Drafts documents and payloads under the same rulebook (REQ-066). Reserves identifiers from the heads in its kickoff and marks them for renumbering on collision (REQ-069, REQ-070). Produces the triple-artifact close-out: deliverable, payload, apply prompt (LSN-042; REQ-097, REQ-098).

**Decision authority.** None, as in section 2.

**Lifecycle.** One conversation per turn-sequence. Open: kickoff read, heads taken from it since the API is unreachable. Conduct: decisions authored in the working material as they are made (REQ-085). Close: payload with every section present, empty sections as empty arrays (REQ-097); apply prompt with pre-flight, one `apply_close_out.py` invocation, post-apply verification (REQ-098); commit and push together (LSN-045).

**Governance Recording duties.**
- Uses the payload only because the store is out of reach — a fallback, not a preference (REQ-096; DEC-383).
- Emits every wire-format constraint so apply does not reject: 200–800-char executive summaries, lowercase statuses, `item_type`, `relationship` key, ISO dates (REQ-099..104).
- Includes the minimum edges per record (REQ-092); records the seed prompt and what was covered (REQ-105).

**Never.** Holds a commit across turns (LSN-045). Guesses heads without marking them reserved (REQ-069). Runs the apply itself — the Lead applies on `main` (LSN-038). Deploys (GVR-240).

**Participant backing.** None proposed (as section 2).

## 4. Any other persona

None. The only hint is DEC-310's "Doug or anyone else operating against the V2 governance database". Every human it could mean has a record: the Consultant (PER-005), the customer Project Manager (PER-003), the Engagement Lead. REQ-064 rules the desktop UI out of authoring, so a UI user monitors rather than records. TOP-116's REQ-477/480/481 concern the service and credentials, not a human role. No positive evidence, so no record (charter §11.6.b).

## Names

Both AI-agent names were ruled by Doug in a parallel session (DEC-1022): Claude Code Agent (TERM-046) and Claude.ai Sandbox Agent (TERM-047); the glossary entries carry the note distinguishing them from pipeline agents (TERM-007).

## Edges

- `persona_scopes_to_domain` → DOM-012 for each new persona (persona → domain; valid in vocab.py).
- `persona_backed_by_participant` Engagement Lead → the Doug participant, once created (persona → participant; valid).
- No `persona_realized_as_entity`: none is tracked as data.
- Engagement Lead edges to other domains (DEC-311 names several) belong to those domains' work.

## Open questions

1. Create a participant for Doug in ENG-001 so the backing edge can be written? The payload assumes yes.
2. Back the two AI personas with participant records (PTC-005 Scheduler precedent), or keep backing for stakeholder-map people? The payload assumes no.
3. (Closed by DEC-1022/DEC-1023: TERM-046 and TERM-047 exist.)

## Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 09-03-26 20:05 | Written by the PI-085 session (SES-392) on Doug's request for a new-session prompt; carries the SES-388 v0.2 persona draft and its two open questions forward. |
