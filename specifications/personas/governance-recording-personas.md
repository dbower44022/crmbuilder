# Governance Recording — Persona Records

| Field | Value |
|-------|-------|
| Version | 0.1 |
| Last Updated | 09-03-26 23:05 |
| Status | DISCUSSION DRAFT — render of persona records PER-013, PER-014, PER-015 (candidate) as of 09-03-26 |
| Audience | Anyone working in or on the CRMBuilder methodology's Governance Recording domain; authors of later domain overviews that reuse these personas; PI-087 and PI-088 authors |
| Governs | Nothing on its own. The persona records and their links in the V2 store are the source (DEC-393, DEC-394, DEC-1021); this file is a render and goes stale between renders |

## Purpose

This document renders the three persona records the Governance Recording domain (DOM-012) names but did not hold as records until PI-086: the Engagement Lead, the Claude Code Agent and the Claude.ai Sandbox Agent. Personas are first-class and cross-domain, so the render lives under `specifications/personas/` rather than inside a domain folder; a later domain that involves one of these personas links to the same record. Each record holds the role summary, responsibilities, Governance Recording duties, the things the persona never does, decision authority, lifecycle and backing facts, so the store can regenerate this file. When this file and the store disagree, the store is right and this file needs re-rendering. Produced under PI-086 (REQ-409) in PRJ-023, session SES-395 / conversation CNV-367. Engagement ENG-001.

## How to read a record

**Role summary** says what the persona is. **Responsibilities** are what it does in any domain. **Governance Recording duties** are the responsibilities this domain adds. **Never** lists the actions the rulebook forbids the persona. **Decision authority** says whose word is final. **Lifecycle** says when the persona is active. **Backing** says which participant seat, if any, stands behind the persona in the engagement, following DEC-1025: a participant record is the seat, not the person, and the person who fills the seat will later be a separate record seated into it. Every claim cites the record it rests on.

## 1. PER-013 Engagement Lead

**Name:** Engagement Lead, glossary term TERM-012, renamed from Engagement Admin (DEC-1009). **Status:** candidate.

**Role summary.** The person who runs one engagement end to end: sets it up, decides what it will and will not do, approves what is built, reviews what is delivered, and is the only human who moves work past the engagement's own gates. One seat per engagement, occupied by Doug in every engagement so far. Reviewing is this persona's responsibility, not a persona of its own (DEC-1010).

**Responsibilities.** Creates the engagement, charter and participants at kickoff (Master PRD section 11). Approves every requirement, governance rule, and new or renamed term (GVR-232). Reviews each demonstrable increment before the next planning item launches (GVR-239; DEC-1010). Reviews the commits the Claude Code Agent lands locally and pushes them (LSN-045). Alone deploys to production (GVR-240 / DEC-907; REQ-477). Is the human an agent or phase halts for on `needs_attention` (GVR-234).

**Governance Recording duties.**
- Bound by the same rules as the agents; no human carve-out (REQ-066; DEC-310).
- Approves a requirement only through an approving decision, never a status edit (GVR-230; REQ-248).
- Gives the go at the user-review checkpoint (GVR-239).
- Pushes; planning-item resolution follows the push, never precedes it (LSN-047; LSN-066).
- Approves the rulebook and engagement overrides (GVR-241); runs the production deploy personally (REQ-477).

**Never.**
- Resolves a planning item by editing its status; only a `resolves` edge does (REQ-090; LSN-043).
- Authors a record through the desktop UI, which is for monitoring (REQ-064).
- Reopens a completed project (GVR-233).
- Re-adds store-owned knowledge to files (GVR-238).

**Decision authority.** Final on every ruling the engagement records; agents surface options with costs, the Engagement Lead answers (GVR-237; PRF-009).

**Lifecycle.** From engagement setup (engagement, charter v0.1, participants, kickoff decisions and session) through every session in every domain, to engagement close.

**Backing.** Participant seat PTC-006 Engagement Lead in ENG-001, filled by Doug Bower, created under PI-086 (DEC-1030). The person record that fills the seat follows the DEC-1025 build. Not realized as a data entity.

**Domains.** DOM-012 Governance Recording (`persona_scopes_to_domain`). Edges to the other domains DEC-311 names belong to those domains' work.

## 2. PER-014 Claude Code Agent

**Name:** Claude Code Agent, glossary term TERM-046 (DEC-1022). **Status:** candidate. Not a pipeline agent (TERM-007); a way of working a session.

**Role summary.** The interactive AI that works a session at the terminal with the live store in reach. It does the session's work (analysis, drafting, code) and records every governance event by direct API write as it happens. It has no authority over content: it surfaces rulings to the Engagement Lead and records the answer.

**Responsibilities.** Orients from the store at session start: the SessionStart hook loads the `claude_code`-audience rules and preferences; TOP-013, reference pointers and lessons on demand (CLAUDE.md "Session bootstrap"). Executes the kickoff anchored on a planning item and work ticket (LSN-040). Builds only against a confirmed requirement with an implementing planning item (GVR-230). Commits with a pathspec and a `Governed-By` trailer while the item is executable (GVR-229; GVR-235; REQ-320).

**Governance Recording duties.**
- Records every decision, planning item, session, conversation and reference by direct POST as it occurs (GVR-231; REQ-095; DEC-383).
- Reads heads and records from the live API, never files (REQ-071; GVR-238).
- Files a planning item for any work that will not ship in the session (REQ-088, REQ-089).
- Keeps branches to code only; bookkeeping lands on `main` after merge (LSN-038, LSN-039).
- Under parallel sessions, commits immediately and uses a worktree (GVR-236; LSN-065).
- Submits to the pre-action rule check and records any override reason (PI-439 / REQ-542).
- Before putting a question from a shared draft to the Engagement Lead, re-reads the store for rulings on the same planning item (LSN-074).

**Never.**
- Pushes (LSN-045).
- Deploys to production (GVR-240).
- Fires `resolves` before the Engagement Lead has pushed (LSN-047; LSN-066).
- Coins a term without approval (GVR-232).
- Batches records to a payload when the store is reachable (GVR-231).
- Continues across a topic boundary (REQ-081).

**Decision authority.** None. Puts each choice to the Engagement Lead as labelled options with advantages, disadvantages and a recommendation (GVR-237; PRF-009) and records the ruling at that moment.

**Lifecycle.** One session, `in_flight` at open, `complete` at close (REQ-078). Open: heads captured live, engagement confirmed, project identified, API health-checked (REQ-067, REQ-068, REQ-072). Conduct: record as it goes; stop at every topic boundary (REQ-081, REQ-082). Close: one conversation per topic with its `addresses` or `resolves` edge, executive summary, transition to `complete` (REQ-083, REQ-099; Master PRD section 11).

**Backing.** None (DEC-1032). Participant seats are for people and the stakeholder-map roles they fill (Master PRD section 11; DEC-1025); this persona is a way of working a session, not a stakeholder seat. PTC-005 Scheduler is an exception to be reviewed, not a precedent. Not realized as a data entity.

**Domains.** DOM-012 Governance Recording.

## 3. PER-015 Claude.ai Sandbox Agent

**Name:** Claude.ai Sandbox Agent, glossary term TERM-047 (DEC-1022). **Status:** candidate. Not the sandbox of the Development and Sandbox domain, which is a test copy of a client CRM. Not a pipeline agent (TERM-007).

**Role summary.** The interactive AI that works a conversation in the claude.ai sandbox, where the store cannot be reached. It does the same kind of work as the Claude Code Agent but records through the fallback path: it authors the close-out payload and apply prompt, and commits and pushes them in the same turn because its container is ephemeral.

**Responsibilities.** Drafts documents and payloads under the same rulebook as every other agent (REQ-066). Reserves identifiers from the heads in its kickoff and marks them for renumbering on collision (REQ-069, REQ-070). Produces the triple-artifact close-out: deliverable, close-out payload, apply prompt (LSN-042; REQ-097, REQ-098).

**Governance Recording duties.**
- Uses the close-out payload only because the store is out of reach; a fallback, not a preference (REQ-096; DEC-383).
- Emits every wire-format constraint so apply does not reject: 200 to 800 character executive summaries, lowercase statuses, `item_type`, `relationship` key, ISO dates (REQ-099 to REQ-104).
- Includes the minimum edges per record (REQ-092); records the seed prompt and what was covered (REQ-105).

**Never.**
- Holds a commit across turns (LSN-045).
- Guesses heads without marking them reserved (REQ-069).
- Runs the apply itself; the Engagement Lead applies on `main` (LSN-038).
- Deploys (GVR-240).

**Decision authority.** None, as for the Claude Code Agent: options with costs to the Engagement Lead, ruling authored in the working material as it is made.

**Lifecycle.** One conversation per turn-sequence. Open: kickoff read, heads taken from it since the API is unreachable. Conduct: decisions authored in the working material as they are made (REQ-085). Close: payload with every section present, empty sections as empty arrays (REQ-097); apply prompt with pre-flight, one `apply_close_out.py` invocation, post-apply verification (REQ-098); commit and push together (LSN-045).

**Backing.** None (DEC-1032), for the same reason as the Claude Code Agent. Not realized as a data entity.

**Domains.** DOM-012 Governance Recording.

## 4. Any other persona

None. The only hint is DEC-310's "Doug or anyone else operating against the V2 governance database". Every human it could mean has a record: the Consultant (PER-005), the customer Project Manager (PER-003), the Engagement Lead (PER-013). REQ-064 rules the desktop UI out of authoring, so a UI user monitors rather than records. TOP-116's REQ-477, REQ-480 and REQ-481 concern the service and credentials, not a human role. No positive evidence, so no record (conduct charter section 11.6.b).

## 5. Rulings applied

The two open questions of the v0.2 draft (SES-388 / CNV-360) are closed:

1. DEC-1030 — the Engagement Lead persona is backed by a participant seat created now in ENG-001 (PTC-006); the person record that fills the seat follows the DEC-1025 build. Alternative rejected: leave the persona unbacked until that build lands.
2. DEC-1032 — participant seats back people and stakeholder-map roles only; the Claude Code Agent and Claude.ai Sandbox Agent carry no participant backing, as the pipeline agents PER-007 to PER-012 already do not; PTC-005 Scheduler is an exception to review. Alternative rejected: seats for both AI personas on the Scheduler precedent.

Earlier rulings carried in: DEC-1009 (one Engagement Lead persona, term renamed), DEC-1010 (no Reviewer persona), DEC-1015 (the pipeline agent personas already link to DOM-012; unchanged here), DEC-1022 (the two AI-agent names).

**Terms.** Every role name in this document has a glossary entry: Engagement Lead TERM-012, Claude Code Agent TERM-046, Claude.ai Sandbox Agent TERM-047, and the established terms TERM-048 to TERM-055 (DEC-1023). No term was coined.

## 6. Store records written under PI-086

| Record | Identifier | Edges |
|---|---|---|
| Persona | PER-013 Engagement Lead | `persona_scopes_to_domain` → DOM-012; `persona_backed_by_participant` → PTC-006 |
| Persona | PER-014 Claude Code Agent | `persona_scopes_to_domain` → DOM-012 |
| Persona | PER-015 Claude.ai Sandbox Agent | `persona_scopes_to_domain` → DOM-012 |
| Participant | PTC-006 Engagement Lead (seat) | backs PER-013 |
| Decision | DEC-1030 | `is_about` → PI-086, DOM-012, PER-013 |
| Decision | DEC-1032 | `is_about` → PI-086, DOM-012, PER-014, PER-015 |
| Domain | DOM-012 | notes appended with the identifiers above |

## 7. What comes next

- **PI-087** defines the Session/Conversation governance Process, the first process record of this domain; its `process_performed_by_persona` edges point at PER-013, PER-014 and PER-015.
- **PI-088** defines the meta process by which process PRDs are produced.
- The review of participant seat PTC-005 Scheduler (retire it, or state why a program holds a seat) is future work for whoever next revisits the ENG-001 stakeholder map (DEC-1032).
- PER-013 to PER-015 move from candidate to confirmed with DOM-012 when the domain overview leaves discussion-draft status.

## Change log

| Version | Date | Change |
|---|---|---|
| 0.1 | 09-03-26 23:05 | First committed render. Personas PER-013, PER-014, PER-015 written to the store under PI-086 (REQ-409) from the SES-388 / CNV-360 v0.2 draft, revised for rulings DEC-1030 and DEC-1032; participant seat PTC-006 created. Authored in SES-395 / CNV-367. |
