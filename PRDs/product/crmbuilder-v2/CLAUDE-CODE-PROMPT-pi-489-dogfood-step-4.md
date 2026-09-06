# CLAUDE-CODE-PROMPT: Step 4 of the phase-specific governance plan — dogfood the opening prompt on three real sessions (PI-489)

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 09-05-26 18:05 |
| Written by | Claude (Claude Code, SES-408) for Doug |
| Governs | The next three real Claude Code sessions in the CRMBUILDER engagement, then one close-out session executing Part C |
| Planning item | PI-489 (in PRJ-023, release REL-013); PI-488 is resolved in Part A once the deploy is verified |

Operating mode: DETAIL. Read `CLAUDE.md` at the repository root first (its session-bootstrap section describes the two-hook opening this step exercises), then the Step 3 outcome on PI-488's resolution note and SES-408's notes, which list six findings this step must confirm or close.

## Purpose

Step 3 built the front door: a session opens from the user's plain-language answer, the server classifies it into a kind of work, the session record carries the answer, the kind of work, the confirmation line and the phase segments, and the first segment's rules load. Step 4 proves it on real work. The exit test is three session records showing the answer as given, the classification, the confirmation line and the segments run, with every miss recorded as a planning item.

**Vocabulary.** *Opening answer* (TERM-060): the user's verbatim reply to "What do you want to do today?". *Kind of work* (TERM-058): a catalogue entry, one of the nine process records PROC-012 to PROC-020. *Phase segment* (TERM-059): one phase's portion of a kind of work. *Phase profile* (TERM-057): the agent profile a segment loads. *Catalogue miss*: an opening answer no entry matched with confidence; the operation asks one follow-up question and records a planning item titled "Catalogue miss: …".

**Net Effect (expected):**
- PI-488 resolved after the production deploy is verified
- 3 session records opened through the prompt hook, each carrying the four values
- 0 or more "Catalogue miss" planning items, each dispositioned in Part C (a phrase added to an entry, a new entry, or the item deferred with a reason)
- 1 to 3 requirements authored and confirmed for the fixes Step 3 surfaced (below), implemented under PI-489 or a new planning item
- PI-489 resolved

---

## Part A — verify the deploy, resolve PI-488 (one close-out session, before the three sessions)

Everything here is a check; nothing is deployed from here (production deploy is human-only, GVR-240).

1. **Where:** a terminal at the repository root on `main`. **Do:** `git pull --rebase origin main`, then confirm `git log --oneline -1` shows `2d78337f` or later. **Expect:** main carries the merge of `pi-488`. **If not:** stop; the merge did not land.
2. **Where:** the same terminal. **Do:** source `crmbuilder-v2/data/crmbuilder.env` and run `curl -s "$CRMBUILDER_V2_API_BASE_URL/sessions/opening" -H "Authorization: Bearer $CRMBUILDER_V2_API_TOKEN" -H "X-Engagement: ENG-001"`. **Expect:** a JSON body whose `catalogue` has nine entries and whose `cross_cutting.profile_id` is `AGP-041`. **If it returns a 404 naming a session "opening":** the API has not been restarted on the new code; the deploy is incomplete — stop and say so.
3. **Where:** the same terminal. **Do:** `curl -s "$CRMBUILDER_V2_API_BASE_URL/sessions/SES-408" …` and read `session_phase_segments`. **Expect:** the field exists (an empty list). **If the field is absent:** migration 0096 has not been applied to the live store — stop and say so.
4. **Where:** the store. **Do:** verify each of REQ-568 to REQ-576's acceptance summary against production the way Step 3 verified them against the copy, reading only (the three real sessions are the writes). Then move PI-488 to Resolved with a resolution note naming the merge commit `2d78337f`, the deploy, and the verification. **Expect:** PI-488 Resolved; `uv run python -m crmbuilder_v2.record_drift` reports no drift for it.

## Part B — the three real sessions (Doug operates; the hooks do the recording)

For each of the next three Claude Code sessions in this repository, whatever their work:

1. **Where:** a new Claude Code session at the repository root. **Do:** read the context the start hook printed; it ends with the opening question and three or four examples. **Expect:** a "Cross-cutting rules (14)" heading and the question. **If it says SNAPSHOT or NO SESSION CONTEXT:** the store was unreachable; the session still runs, but it will not be one of the three — note it and try again later.
2. **Where:** the first prompt of that session. **Do:** type what you want to do, in your own words, as the first line — for example `define new business processes` or `add a field to the intake screen` — then, if you are running a prompt file, the run instruction on the next line. **Expect:** before the model's first reply, a block headed "Session opened — SES-NNN" with the confirmation line, or a follow-up question. **If the block says SESSION NOT OPENED:** the operation could not be reached; ask the model to open the session through the connector tool `open_session` with the same words, and note the failure for Part C.
3. **Where:** the same session. **Do:** work as normal. When the work moves to the next phase of the kind of work, ask the model to call `advance_session_segment` on the session. **Expect:** a line saying which segment was entered. **If the segment's profile is pending:** only the cross-cutting rules load; that is expected for Solution Designer, Application Developer and Maintainer until Steps 5 and 6.
4. **Where:** the end of the session. **Do:** close the session and conversation as usual, and add to the session notes one line: whether the classification matched what you meant, and whether the confirmation line read as your own words.

## Part C — close-out session (after the third session)

1. Read the three session records and every "Catalogue miss" planning item created since 09-05-26. For each miss, decide with the product owner (one gate per miss): add a trigger phrase to an existing entry, add a new kind of work, or defer with a reason. Apply the phrase changes through `python -m crmbuilder_v2.kind_of_work_catalogue` after editing the module, so the catalogue stays reproducible; record the decision.
2. Author, through the requirement-authoring gate (SKL-102), the requirements for the fixes Step 3 surfaced, and put them to the product owner as one gate:
   - the prompt hook ignores a first prompt that is a system notification or markup (finding 5 on SES-408: it took `<task-notification>` as an answer);
   - a session-membership edge left behind for an unassigned session identifier must not break the next session create on that identifier (finding 1: the operation hit "exactly one edge required" on a copy that held such orphans — check the live store for them first);
   - a first prompt of the form "run <prompt file>" is not an opening answer (finding 4): either the run line is skipped and the next line taken, or the convention in Part B step 2 is recorded as a governance rule.
   Implement the confirmed ones under a planning item, on a branch, with tests, as Step 3 did.
3. Record on the plan (`PRDs/product/crmbuilder-v2/phase-governance-plan.md`, version 0.2) what the dogfood showed: match rate over three sessions, misses and their disposition, and the size of the interviewer contract placed in context (finding 2: about 98 KB at the first prompt).
4. Resolve PI-489 with a note naming the three session identifiers and the misses. Close the conversation and session with executive summaries. Name the next step: Step 5 (PI-490, the Maintainer and Application Developer profiles).

## Done

Reply with the review list and nothing else: PI-488's resolution note, the three session identifiers with their kind of work and whether each matched, the miss planning items and their disposition, the requirement identifiers and the approving decision from Part C, the plan version written, and the session and conversation identifiers. Then **What next**: Step 5 (PI-490) or the Part C fixes first, with a recommendation.

## Change log

| Version | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-05-26 18:05 | Claude (Claude Code, SES-408) | First version, written after Step 3 merged (pi-488 → main 2d78337f), before the production deploy. |
