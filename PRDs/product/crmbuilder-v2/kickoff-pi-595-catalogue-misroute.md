# Kickoff — rule on PI-595: "Review the build of PI-NNN" opens as Build

| Field | Value |
|---|---|
| Title | Kickoff — rule on PI-595: "Review the build of PI-NNN" opens as Build |
| Last Updated | 10-22-26 22:48 |
| Revision | 1.1 |
| Status | Run on 10-22-26 as SES-455. Doug ruled option (d), a scorer change, recorded as DEC-1204; REQ-667 confirmed, PI-596 queued in PRJ-023. PI-595 stays open until PI-596 is accepted. The catalogue was not edited. |
| Governs | One session: measure the options offline against the live catalogue, put one decision to Doug, apply the ruling in the store, verify it in production, and resolve PI-595. |
| Source | Claude Code session of 10-18-26 (SES-452, SES-454): found while measuring options for PI-593; DEC-1203; PI-595. |

## Opening answer

Paste **only the path of this file** as the first prompt of the new session:

```
/home/doug/Dropbox/Projects/crmbuilder/PRDs/product/crmbuilder-v2/kickoff-pi-595-catalogue-misroute.md
```

> Opening answer: Fix the catalogue misroute PI-595 in PRJ-023 — an opening that names a review of finished work opens as the wrong kind of work; measure the options, then record the ruling.

Previewed in production on 10-18-26 through `GET /sessions/opening?answer=...`: it classifies as PROC-018, "Fix something that is not working", at 1.0. The answer avoids the words "review" and "build" together on purpose. An answer that contains both would itself open as Build, which is the defect this session is about.

Operating mode: DETAIL.

---

## 1. What this session delivers

Doug's ruling on PI-595, recorded as a decision in this session. If the ruling changes the catalogue, the store edit is made and verified in production. PI-595 is resolved by a conversation with a `resolves` reference, never by a status edit.

## 2. The defect (verified offline 10-18-26 against the live nine-entry catalogue)

The session-open operation scores the opening answer against each kind of work's trigger phrases. A phrase scores 1.0 when it appears in the answer word for word. Otherwise it scores the fraction of its tokens found in the answer, but only when it keeps at least two tokens after stopword removal (REQ-666). "and" is a stopword. So the Build phrase "review and build", on PROC-016 "Build a new application or module from approved requirements", keeps the two tokens "review" and "build". Any answer containing both words scores 1.0 for Build.

The answer "Review the build of PI-592" classifies as Build at 1.0, with PROC-019 "Review what has been delivered" at 0.5. That is a wrong match, and it is worse than a miss. A miss asks a follow-up question and records a planning item. A wrong match silently loads the Build phase rules for a review.

## 3. The options to measure

- **(a) Reword or remove "review and build" on PROC-016.** First find which openings the phrase exists to catch. It was added for kickoff prompts that say "review and build" (search `PRDs/` and the session records for openings that used it). A reworded phrase must still catch them.
- **(b) Add a phrase on PROC-019** that also scores 1.0 on "Review the build of PI-592", so the two kinds of work tie and the answer becomes a miss instead of a wrong match.
- **(c) No change.**

Measure each option offline against the live catalogue. Read `GET /processes` into a file, parse each record with `parse_catalogue_entry`, apply the option to the phrase lists in memory, and run `classify` from `crmbuilder_v2.access.repositories.session_opening` over a fixed set of answers. Use at least these answers:

- "Review the build of PI-592"
- "Review and build the kickoff for PI-588"
- "Build the PI-592 scorer rule in PRJ-023"
- "Review what has been delivered for PI-592"
- "Accept PI-592 after the build"
- "What is a deployment grant?"
- this session's own opening answer

Report each answer's result before and after the option. Mark every change as miss→match, match→miss, or match→wrong match.

## 4. The decision

Put one decision to Doug in the consequential decision template: the plain question, a concrete example, each option with its measured effect, why it matters, the cost of the recommendation, the recommendation, follow-on detail, and the request. Wait for his word.

## 5. Applying the ruling

1. Record the decision (`create_decision`) and a `decided_in` reference to this session.
2. If the catalogue changes, `PATCH /processes/PROC-NNN` with the full new `process_triggers` list. This is a store edit with no code, so no commit is needed.
3. Verify in production with `GET /sessions/opening?answer=...` for the answers in section 3. The preview creates no session.
4. Record one conversation in this session. Create it through `POST /conversations` with the `conversation_`-prefixed fields and the `references` array carrying `conversation_belongs_to_session` and `conversation_belongs_to_project` → PRJ-023; the connector's create tool cannot attach the session reference. Then add `resolves` → PI-595.
5. Close the session with an executive summary, status complete.

## 6. Known pitfalls from the previous session

- The connector's `create_planning_item` sets `execution_mode` to `ado` and the connector's update tool does not change it. Use `PATCH /planning-items/PI-NNN` with `{"execution_mode":"interactive"}`.
- `PATCH /sessions/{id}` needs `session_`-prefixed fields. The connector tool `update_session` handles this for you.
- The commit hook blocks a commit without a `Governed-By` trailer even when only Markdown files change. Use `Governed-By: trivial` with an `Exemption-Reason:`.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.1 | 10-22-26 22:48 | Claude (Claude Code) | Marked run (SES-455, CNV-422). Measured result: "review and build" was no longer the cause after DEC-1203 added "build PI"; options (a) and (b) could not make a review open as a review. Doug ruled a fourth option, (d): the scorer caps a token-overlap match at 0.75 so only an exact phrase scores a full match (DEC-1204, REQ-667, PI-596), with the two catalogue edits deferred until that lands. Note: the session opened as Build because the first prompt was "run " plus this file's path, not the bare path. |
| 1.0 | 10-18-26 23:16 | Claude (Claude Code) | First version, written after PI-595 was queued and its opening answer was previewed in production. |
