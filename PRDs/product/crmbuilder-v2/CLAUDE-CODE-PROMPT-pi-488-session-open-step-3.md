# CLAUDE-CODE-PROMPT: Step 3 of the phase-specific governance plan — the session-open and segment-advance operations, the catalogue of kinds of work, and the session fields that record them (PI-488)

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 09-05-26 07:40 |
| Written by | Claude (Claude Code, SES-407) for Doug |
| Governs | One Claude Code session (or a short series) executing Step 3 of `PRDs/product/crmbuilder-v2/phase-governance-plan.md` |
| Planning item | PI-488 (in PRJ-023, release REL-013); PI-494 is a prerequisite and is closed inside Part A |

Operating mode: DETAIL. Read `CLAUDE.md` at the repository root first, then `PRDs/product/crmbuilder-v2/phase-governance-plan.md` in full. The plan's Parts 4, 6 and 7 are the specification for this prompt; do not re-derive them. Then read the Step 2 outcome recorded on PI-487's resolution note, because this step builds on the two profiles Step 2 created.

## Purpose

This is the first step of the plan that changes code. After it, a Claude Code session that opens with the words "define new business processes" loads the Requirements Interviewer contract instead of the flat audience query, and its session record shows the words as given, the kind of work chosen, the confirmation line said back, and the phase segments run. The same two server operations serve the claude.ai connector and the desktop application, so one implementation carries all three surfaces.

Because code changes, the requirement-first rule applies in full: every requirement below is authored through the requirement-authoring gate (SKL-102), confirmed by the product owner through an approving decision, and implemented by PI-488, before any file under `crmbuilder-v2/src/` is edited. The order is fixed: terms, decisions, requirements, approval, then code.

**Vocabulary used in this prompt.** Four terms are not yet glossary terms; they are defined here so the prompt can be read, and their approval is the first gate in Part A. A *phase profile* is an agent profile that holds the rules and skills for one engagement phase (Step 2 created two: the Requirements Interviewer, AGP-039, and the Release Operator, AGP-040). A *kind of work* is a catalogue entry naming what a user wants to do, in the user's own words, composed of phase segments. A *phase segment* is one phase's portion of a kind of work; entering it loads that phase's profile. The *opening answer* is the user's verbatim reply to the session's opening question, "What do you want to do today?".

**Net Effect (expected; Part A confirms or corrects it before anything is written):**
- 4 glossary terms recorded (PI-494 closed), or fewer if the product owner renames or rejects any
- 1 child topic under Session Lifecycle & Gating (TOP-018) holding this step's requirements, if none exists yet
- About 9 requirements authored and confirmed by one approving decision; PI-488 implements them
- 2 to 4 decisions recorded for the design gates in Part A
- 1 new migration adding the session fields; 1 new cross-cutting profile (system scope) bound to the rules that load in every segment
- 9 catalogue entries written as process records (the plan's Part 6, version 0.1)
- 2 new API operations, 2 new connector tools, 2 changed Claude Code hooks, 1 new desktop dialog, with tests
- PI-488 moved to In Progress at start and Resolved after Doug pushes (never before: LSN-047 / LSN-066)

Every record write goes through the cloud API in real time (the governance-recording rule). Nothing is batched into a close-out payload. Use the cloud API at `https://api.crmbuilder.ai` with the token from `crmbuilder-v2/data/crmbuilder.env` and the header `X-Engagement: ENG-001`; the local API on port 8765 is a stale development store and was not running when Step 2 ran.

---

## Pre-flight

```bash
cd ~/Dropbox/Projects/crmbuilder && pwd
git status
git pull --rebase origin main
set -a; . crmbuilder-v2/data/crmbuilder.env; set +a
H=(-H "Authorization: Bearer $CRMBUILDER_V2_API_TOKEN" -H "X-Engagement: ENG-001")
curl -s "$CRMBUILDER_V2_API_BASE_URL/health" "${H[@]}"; echo
curl -s "$CRMBUILDER_V2_API_BASE_URL/sessions/next-identifier" "${H[@]}"; echo
# Expected: SES-408 or later. If SES-407 is still next, Step 2's session was not written — stop and say so.
for p in PI-488 PI-494 PI-495; do curl -s "$CRMBUILDER_V2_API_BASE_URL/planning-items/$p" "${H[@]}" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(d['identifier'], d['status'], d['title'][:70])"; done
# Expected: PI-488 Draft, PI-494 Draft, PI-495 Draft.
for a in AGP-039 AGP-040; do curl -s "$CRMBUILDER_V2_API_BASE_URL/agent-profiles/$a/contract" "${H[@]}" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(d['profile_id'], d['area'], len(d['advisory_rules'])+len(d['enforced_ruleset']), 'rules')"; done
# Expected: AGP-039 requirements-capture 7 rules; AGP-040 release-to-production 11 rules.
ls crmbuilder-v2/migrations/versions | tail -1
# Note the current head; a new migration must chain from it (dual-head lesson: never two heads).
```

Open the session record now (session medium `claude_code`, belonging to PRJ-023, following from SES-407) and one conversation for this work (addressing PI-488 and PI-494), before any other write. Move PI-488 and PI-494 to In Progress.

---

## Part A — five gates, one per turn, then stop at each

Read-only except for the records each gate produces once the product owner has answered. Never use a question widget; discuss in plain text. Each gate is one question with its options, what each does well, what each costs, one recommendation, and a request to choose. Nothing follows the question. Record the ruling as a decision record before opening the next gate (Gate 1 records term records instead).

**Gate 1 — the four terms (closes PI-494).** Put the four definitions above to the product owner as one gate (one semantic decision: adopt this vocabulary), inlining each definition. On approval, create the four term records and correct the plan's wording for any term that was renamed. Cost of approval: four more terms to keep defined; cost of rejection: the plan and this prompt are rewritten before Gate 2.

**Gate 2 — where the phase-segment sequence lives on a process record.** The plan puts the catalogue in process records, but a kind of work such as "add or change a field in an existing application" crosses five phases and a process record belongs to one domain. Read the process model in `crmbuilder-v2/src/crmbuilder_v2/access/models.py` (the `Process` class) before drafting. Option 1: the process record belongs to the domain where the request enters (the first segment's domain) and its steps field carries the ordered segments, each naming a domain record and a phase profile — no schema change, but the domain on the record describes the entry point, not the whole journey. Option 2: a new record type for catalogue entries — honest, at the cost of a new table, migration, API, connector tools and desktop panel before the first catalogue entry can be written. Recommendation: Option 1 now; a kind of work belongs where a user's request arrives, and the segments make the journey explicit.

**Gate 3 — how the opening answer is classified.** Read the plan's Part 4 and Part 7. Option 1: the server matches the answer against trigger phrases stored on each catalogue entry and returns the best entry with a confidence; below the threshold it returns "no confident match", and the calling surface's model asks the one follow-up question in the user's words — no model call inside the API, deterministic and testable, at the cost of a phrase list that has to be curated as the catalogue grows. Option 2: the server calls a language model with the catalogue as context — better at paraphrase, at the cost of a provider credential in the API path, a cost per session open, and a classification that cannot be reproduced in a test. Option 3: the calling surface's model classifies and passes the kind-of-work identifier; the server only validates and records — the simplest server, at the cost of three surfaces each carrying classification logic and no single place to improve it. Recommendation: Option 1, with the follow-up question owned by the surface, because the plan's guard against misreading is the confirmation line the server returns and that line must be reproducible.

**Gate 4 — how a Claude Code session supplies its opening answer.** The session-start hook runs before the user types anything, so it cannot ask a question. Read `crmbuilder-v2/src/crmbuilder_v2/session_context.py` and `.claude/settings.json` before drafting. Option 1: the session-start hook loads only the cross-cutting rules and prints the opening question; a second hook on the first user prompt submission takes that prompt as the opening answer, calls the session-open operation, and injects the first segment's contract — the user types once, the record is written before the model reads the prompt, at the cost of a second hook and the rule that the first prompt is the answer even when the user pastes a long kickoff prompt (the hook must then take the first line or a marked line as the answer). Option 2: the session-start hook loads the cross-cutting rules and instructs the model to ask the question and call the operation itself through the connector — no new hook, at the cost of relying on the model to do it every time, which the plan's fallback rule was written to avoid. Recommendation: Option 1, with Option 2 as the documented manual fallback when the hook cannot reach the store.

**Gate 5 — the requirement set, for approval.** Author the requirements listed under "Requirements to author" below, adjusted for the rulings in Gates 1 to 4, through the requirement-authoring gate (SKL-102: positive statements, no identifiers or history words in the statement, about four sentences, an objectively verifiable acceptance summary, rationale in the notes). Give each its provenance: defined in this session's conversation, belonging to the child topic under TOP-018 (create it if absent). Then present the full set inline to the product owner as one gate — statement and acceptance summary for each — and ask for approval. Do not create the approving decision until the product owner has approved. On approval: create one decision record, write a `requirement_approved_by_decision` reference from each requirement to it (the store activates the requirement on that edge; never edit a status field), and write `planning_item_implements_requirement` from PI-488 to each. If the product owner strikes a requirement, leave it candidate and note why in the decision.

Do not proceed to Part B until Gate 5 is approved and every requirement reads `confirmed`.

### Requirements to author (candidates; adjust to the rulings)

1. **The session record carries the opening answer and what followed from it.** The session stores the opening answer as given, the kind of work chosen, the confirmation line the system said back, and the ordered list of phase segments with the profile each loaded and the moments each was entered and left. Acceptance: a session opened through the operation shows all of these on read; a session opened without an answer shows the answer empty and the segments empty.
2. **The catalogue of kinds of work is stored as process records.** Each catalogue entry is a process record whose steps carry the ordered phase segments, each naming a lifecycle domain and a phase profile, plus the trigger phrases used to recognise the entry; the nine entries in the plan's Part 6 exist at version 0.1. Acceptance: reading the catalogue returns nine entries, each with at least one segment and at least three trigger phrases; every segment's profile resolves to an active agent profile.
3. **A session-open operation classifies the answer and returns the first contract.** The operation takes an engagement and an opening answer, classifies the answer against the catalogue, creates the session record with the answer and the kind of work, returns a confirmation line in the user's own terms, and returns the first segment's resolved profile contract merged with the cross-cutting rules. Acceptance: opening with "define new business processes" returns the Requirements Interviewer contract, a confirmation line, and a session record carrying both.
4. **A session opened without an answer loads only the cross-cutting rules and says so.** When the operation receives no answer or no confident match, it creates the session with the answer as given, returns the cross-cutting contract only, and returns a first line stating that no kind of work was chosen. Acceptance: an empty answer returns exactly the cross-cutting rules and the stated first line; the session record shows no kind of work.
5. **An unrecognised answer produces one follow-up question and a recorded miss.** When no catalogue entry matches with confidence, the operation returns a single follow-up question in plain words that never asks for a phase or a role name, and records the miss as a planning item so the catalogue grows from use. Acceptance: an answer outside the catalogue returns one question and creates one planning item naming the answer.
6. **A segment-advance operation moves the session to its next segment.** The operation closes the current segment with its leaving time, opens the next with its entering time, and returns the next segment's contract merged with the cross-cutting rules; after the last segment it returns a completed state and no contract. Acceptance: advancing a two-segment session twice yields the second contract, then the completed state, and the session record shows both segments with times.
7. **The cross-cutting rules are one named set that loads in every segment.** A system-scope profile holds the rules that apply whatever the phase — governance recording, the four writing standards, terminology governance, and commit hygiene — and both operations merge its contract into every segment's contract. Acceptance: the cross-cutting profile resolves to exactly that set, and every contract returned by either operation contains it.
8. **The Claude Code surface opens the session through the operation.** The session-start hook loads the cross-cutting rules and prints the opening question; the first user prompt is taken as the opening answer, the session-open operation is called, and the first segment's contract is placed in context before the model reads the prompt; the pre-command rule check reads the enforced rules from that contract. Acceptance: a Claude Code session whose first prompt is "define new business processes" has the Requirements Interviewer rules in context and a session record carrying the answer. (Adjust to the Gate 4 ruling.)
9. **The connector and the desktop application call the same two operations.** The claude.ai connector exposes a tool for each operation, and the desktop application asks the opening question in a dialog when a session is created and calls the same operations, so no surface classifies on its own. Acceptance: each surface, given the same answer, produces a session record identical in answer, kind of work and first segment.

---

## Part B — build, in slices, without further confirmation

Work on a branch named `pi-488` (Model A: the branch carries code only; governance records are written to the store as they occur). Commit each slice with an explicit pathspec and the trailer `Governed-By: PI-488`. Doug pushes. If the work spans more than one session, PI-488 stays In Progress and each session opens its own session record following from the last.

**B1. Session fields.** One Alembic migration chaining from the current head adds the opening answer, the kind of work, the confirmation line and the segments to the session table; the model, the session schemas, the session repository and the read-back payload carry them. Run the migration against a copy, never the live store (the production deploy is Doug's step).

**B2. The cross-cutting profile.** Create the system-scope profile through the API (tier as the phase profiles carry it until PI-495 lands) and bind the cross-cutting rules: the governance-recording rules, the four writing standards (GVR-242 to GVR-245), terminology governance (GVR-246), and the commit-hygiene rules (GVR-229, GVR-235, GVR-236). Verify its contract is exactly that set.

**B3. The catalogue.** Write the nine process records from the plan's Part 6 in the shape Gate 2 ruled, with trigger phrases for each. Segments name domain records DOM-004 to DOM-010 and the profiles that exist (AGP-039, AGP-040); a segment whose profile does not yet exist (Solution Designer, Application Developer, Maintainer) names the profile by its planned area and is marked pending, so the catalogue is complete and the missing profiles are visible.

**B4. The two operations.** Add the session-open and segment-advance operations to the API and the access layer in the shape Gate 3 ruled, with the classification, the confirmation line, the follow-up question, the recorded miss, the fallback, and the merge with the cross-cutting contract. Tests cover the acceptance summary of every confirmed requirement, including the empty answer and the unrecognised answer.

**B5. The Claude Code hooks.** Change `session_context.py` and add the prompt-submission hook in the shape Gate 4 ruled; register both in `.claude/settings.json`; keep the snapshot fallback; make the pre-command check read the enforced rules from the contract the session received. Keep the hook module standard-library only.

**B6. The connector tools.** Add the two tools to `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tools.py` beside the existing session tools, with descriptions a reader who has not read the store can act on.

**B7. The desktop dialog.** Extend the session-create dialog (`crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/session_create.py`) so it asks the opening question with three or four examples drawn from the catalogue, shows the confirmation line back, and creates the session through the operation. Follow the existing dialog tests' pattern of stubbing any dialog an affordance opens (LSN-079).

**B8. Verify end to end.** With the API running locally against the migrated copy: open a session with "define new business processes" from a shell and from the hook, and confirm the record and the contract; open one with an empty answer; open one with an answer outside the catalogue; advance a two-segment kind of work to completion. Record the outputs.

**B9. Close.** Close the conversation and the session with executive summaries in the 200-to-800-character range, naming the commits. Leave PI-488 In Progress with a note that resolution waits on Doug's push and the production deploy; PI-494 is resolved in Part A once the terms exist. Do not deploy.

---

## Done

Reply with the review list and nothing else: the term identifiers, the decisions from Gates 2 to 4, the requirement identifiers and the approving decision, the cross-cutting profile identifier and its rule count, the nine catalogue process identifiers, the migration file name, the commit SHAs by slice, the end-to-end outputs from B8 in one line each, and the session and conversation identifiers. Then **To continue, I need**: Doug's push of `pi-488` and the production deploy (migration and API restart), after which PI-488 can be resolved and Step 4 (PI-489, the dogfood on three real sessions) can start.

## Change log

| Version | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-05-26 07:40 | Claude (Claude Code, SES-407) | First version, written after Step 2 landed (AGP-039, AGP-040, SKL-125..128, PI-495). |
