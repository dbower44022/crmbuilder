# Kickoff — build PI-596: a token-overlap match is capped at 0.75, then the two catalogue edits

| Field | Value |
|---|---|
| Title | Kickoff — build PI-596: a token-overlap match is capped at 0.75, then the two catalogue edits |
| Last Updated | 10-22-26 22:58 |
| Revision | 1.0 |
| Status | Ready to run. PI-596 is Draft in PRJ-023; REQ-667 is confirmed (DEC-1204). Nothing is built. |
| Governs | One session for the code and its commit. The two store edits and the production verification happen after Doug's rollout, in this session if the rollout is done while it runs, otherwise in the acceptance session. |
| Source | SES-455 on 10-22-26: DEC-1204 (Doug's ruling on PI-595), REQ-667, PI-596, CNV-422. |

## Opening answer

Paste **only the path of this file** as the first prompt of the new session, nothing before it. A word in front of the path, such as `run`, stops the hook reading the file and classifies the raw text instead (PI-597, found when SES-455 opened that way).

```
/home/doug/Dropbox/Projects/crmbuilder/PRDs/product/crmbuilder-v2/kickoff-pi-596-token-overlap-cap.md
```

> Opening answer: Build PI-596 in PRJ-023 — cap the session-open token-overlap score at 0.75 so only an exact trigger phrase scores a full match, then apply the two catalogue edits after the rollout.

Previewed in production on 10-22-26 through `GET /sessions/opening?answer=...`: PROC-016, "Build a new application or module from approved requirements", at 1.0 through the exact phrase "build PI"; the runners-up are at 0.5.

Operating mode: DETAIL.

---

## 1. What this session delivers

The scorer change REQ-667 specifies, with tests, committed on `main` under `Governed-By: PI-596`, and PI-596 moved to In Review. If Doug runs the production rollout during the session, also the two catalogue edits and the production verification of section 5. PI-596 and PI-595 are resolved only by the acceptance conversation after the verification passes, never by a status edit.

## 2. Where the work stands (verified 10-22-26 through the production API)

- **DEC-1204** is Doug's ruling on PI-595: a trigger phrase scores a full match only as an exact phrase; a token-overlap match is capped at 0.75; after the rollout, "review and build" leaves PROC-016 and "review the build" joins PROC-019. The catalogue is not edited before the rollout, because the PROC-019 phrase applied alone turns three correct matches into misses.
- **REQ-667** is confirmed under TOP-118, defined in CNV-422, approved by DEC-1204. Its notes carry the detail of the rule and the measurement that chose 0.75 over 0.5.
- **PI-596** implements REQ-667, belongs to PRJ-023, Draft, interactive. **PI-595** stays Draft and is addressed by CNV-422; one conversation resolves both after acceptance.
- **The code** is `_phrase_score` in `crmbuilder-v2/src/crmbuilder_v2/access/repositories/session_opening.py`. Today it returns 1.0 when the normalised phrase is a substring of the normalised answer, 0.0 when the phrase keeps fewer than two tokens after stopword removal (REQ-666), otherwise the fraction of the phrase's tokens found in the answer. `MATCH_THRESHOLD` is 0.6 and `AMBIGUITY_MARGIN` is 0.15, both module constants.
- **The classifier runs inside the cloud API.** The Claude Code hook calls `POST /sessions/open` at `https://api.crmbuilder.ai`, so the change takes effect for openings only after Doug runs `scripts/deploy-production.sh` and sees `DEPLOY OK` with the new commit.

## 3. The build

1. Move PI-596 to In Progress (the connector tool `update_planning_item`, status `In Progress`).
2. In `session_opening.py`, add a module constant beside the other two, named for what it is, holding 0.75, with a comment naming REQ-667 and DEC-1204. In `_phrase_score`, keep the exact-phrase return of 1.0 and the one-token return of 0.0 unchanged, and return the token fraction capped at that constant. Update the function's docstring in the same plain register as the REQ-666 sentence already there.
3. Tests, in `tests/crmbuilder_v2/api/test_session_opening_api.py` next to `test_one_token_phrase_scores_only_by_exact_match`, calling `so._phrase_score` and `so.classify` directly as that test does:
   - "build PI" on the tokens and text of "review the build of pi 592" scores 0.75, not 1.0.
   - "review the build" on the same text scores 1.0.
   - "review the delivery" on "review what has been delivered for the boston test system" still scores 0.5.
   - With a two-entry list, PROC-016 holding `["build PI", "build the kickoff"]` and PROC-019 holding `["review the build", "accept PI"]`: "Review the build of PI-592" classifies to PROC-019 at 1.0 with the runner-up at 0.75; "Review and build the kickoff for PI-588" classifies to PROC-016; "Build the PI-592 scorer rule in PRJ-023" classifies to PROC-016 at 0.75; "Accept PI-592 after the build" classifies to PROC-019.
4. Run `uv run pytest tests/crmbuilder_v2/api/test_session_opening_api.py tests/crmbuilder_v2/api/test_kind_of_work_catalogue.py -q` and `uv run ruff check crmbuilder-v2/src/crmbuilder_v2/access/repositories/session_opening.py tests/crmbuilder_v2/api/`. All existing tests must still pass; a test that asserted a token-overlap score of 1.0 is a test of the old rule and is changed, with REQ-667 named in the change.
5. Commit on `main` with an explicit pathspec naming the two files, subject prefixed `v2:`, trailer `Governed-By: PI-596`. Do not push; Doug pushes (LSN-045).
6. Move PI-596 to In Review and record the conversation (section 6).

## 4. After Doug's rollout — the two store edits

Only after `DEPLOY OK` names the new commit. Each is a `PATCH /processes/PROC-NNN` carrying the **full** new `process_triggers` list as a JSON string; read the current list first with `GET /processes` and change one entry.

- **PROC-016**: the list as read, minus `"review and build"`.
- **PROC-019**: the list as read, plus `"review the build"` at the end.

Record the edit in the session's conversation. No commit: the store is the source.

## 5. Verification in production

Through `GET /sessions/opening?answer=...`, which creates no session, after the rollout and the two edits. Expected kind of work for each answer:

| Answer | Expected | Expected score |
|---|---|---|
| Review the build of PI-592 | PROC-019 | 1.0, runner-up PROC-016 at 0.75 |
| Accept PI-592 after the build | PROC-019 | 1.0 |
| Review the build of PI-588 and accept it | PROC-019 | 1.0 |
| Review and build the kickoff for PI-588 | PROC-016 | 1.0 |
| please review and build the following prompt /home/doug/x.md | PROC-016 | 1.0 |
| Build the PI-592 scorer rule in PRJ-023 | PROC-016 | 0.75 |
| Build PI-575 — the store's engagement row becomes the application record | PROC-016 | 1.0 |
| What is a deployment grant? | PROC-020 | 1.0 |
| Fix the catalogue misroute PI-595 in PRJ-023 | PROC-018 | 1.0 |

These are the measured results of SES-455 with the cap and both edits; any difference is a defect to record, not to explain away. Two phrasings are expected misses and are not defects: "Review the design before we build PI-600" and "Build the review screen for PI-601".

## 6. Governance records

- One conversation in this session through `POST /conversations`: `conversation_`-prefixed fields, and a `references` array in which every edge carries `source_type` `conversation` and `source_id` set to the identifier from `GET /conversations/next-identifier`, with `conversation_belongs_to_session` → this session, `conversation_belongs_to_project` → PRJ-023, `addresses` → PI-596. The connector's create tool cannot attach the session edge.
- The acceptance, when the section 5 table matches in production: Doug's word in plain text first, then one conversation (this one or the acceptance session's) adds `resolves` → PI-596 and `resolves` → PI-595. The store moves both to Resolved through the edges.
- One sentence in the "Session bootstrap" paragraph of `CLAUDE.md` after acceptance, naming REQ-667, the cap, the two catalogue edits and the date, as a documentation-only commit.
- Close the session: executive summary, status complete.

## 7. Out of scope

- The threshold, the margin, the exact-phrase rule and the one-token rule.
- Any catalogue phrase other than the two named in section 4.
- PI-597, the "run " plus path opening defect; it has its own ruling to come.

## 8. Known pitfalls

- The connector's `create_planning_item` sets `execution_mode` to `ado`; `PATCH /planning-items/PI-NNN` with `{"execution_mode":"interactive"}` changes it.
- A requirement statement over about 75 words, or one reading as several ideas, is refused when the approval reference is created; REQ-667 already passed, so no new requirement is needed here.
- The commit hook blocks a commit without a `Governed-By` trailer even when only Markdown changes; documentation commits use `Governed-By: trivial` with an `Exemption-Reason:`.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 10-22-26 22:58 | Claude (Claude Code) | First version, written in SES-455 after DEC-1204, REQ-667 and PI-596 were recorded and the opening answer was previewed in production. |
