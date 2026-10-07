# Kickoff — accept PI-589: the session-open hook reads a pasted kickoff file path

| Field | Value |
|---|---|
| Title | Kickoff — accept PI-589: the session-open hook reads a pasted kickoff file path |
| Last Updated | 10-07-26 00:56 |
| Revision | 1.0 |
| Status | Ready to run. PI-589 is In Review; its build is merged to main as commit `9b39501b`. |
| Governs | One session: the session's own opening is the acceptance test. Record the result as the conversation that resolves PI-589, or record what failed. |
| Source | SES-445 and SES-446 on 09-30-26: DEC-1199, REQ-665, DEC-1200, commit `9b39501b`. |

## Opening answer

This file is the test. Paste **only the path of this file** as the first prompt of the new session, nothing else:

```
/home/doug/Dropbox/Projects/crmbuilder/PRDs/product/crmbuilder-v2/kickoff-pi-589-acceptance.md
```

The hook should read this file and take the line below as the opening answer.

> Opening answer: Accept PI-589 — confirm that this session opened on the kickoff's work from a pasted file path, then record the acceptance conversation that resolves PI-589 in PRJ-023.

Operating mode: DETAIL.

---

## 1. What this session delivers

Doug's acceptance of PI-589, recorded in the store as a conversation that resolves the item. Or, if the opening missed, a record of what happened and the one planning item that follows.

## 2. Where the work stands (verified 09-30-26 through the production API)

- **REQ-665** is confirmed (DEC-1200) under topic TOP-118: a first prompt that is exactly a path to an existing Markdown file under the working directory supplies the opening answer from that file.
- **PI-589** implements REQ-665, belongs to PRJ-023 "Master CRMBuilder PRD consolidation + dogfood", and is In Review. CNV-415 addresses it.
- **Commit `9b39501b`** on main carries the build with trailer `Governed-By: PI-589`: `prompt_file` and `resolve_opening_answer` in `crmbuilder-v2/src/crmbuilder_v2/session_open.py`, the session's medium metadata gaining `opening_answer_file`, and four tests in `tests/crmbuilder_v2/test_session_open_hooks.py`. It also fixes the marked-line match, which had never stripped a leading `>` and so had never matched a kickoff's quoted `> Opening answer:` line.
- No production rollout was needed. The hook runs on Doug's machine from the repository; the store is unchanged.

## 3. The acceptance test is the opening itself

Before the first reply, check what the hook put in context and what Claude Code displayed:

1. **The session opened on the kickoff's work.** The hook's context block begins `# Session opened — SES-NNN (opening answer: "Accept PI-589 — ...")`. The opening answer must be the quoted line from section "Opening answer" above, not the file path.
2. **The file is recorded.** Read the session record (`get_session` on the connector, or `GET /sessions/SES-NNN`). Its `session_medium_metadata` carries `opening_answer_file` equal to this file's path.
3. **The session is filed where the answer says.** The answer names PI-589 and PRJ-023, so the session should be filed under PRJ-023 (DEC-1192), not under Unfiled sessions (PRJ-132). Read `GET /references?source_id=SES-NNN` and look for `session_belongs_to_project`.
4. **A kind of work may or may not match.** The catalogue has no entry for "accept a planning item"; a follow-up question or a recorded catalogue miss on *this* answer is a classification result, not a failure of PI-589. Note it; do not treat it as a defect of the hook.

State the result of each check in the first reply, in one line each, before anything else.

## 4. If all of checks 1 to 3 pass — accept

1. Put the acceptance to Doug in plain text: the three checks passed, and the expected labels were seen. Wait for his word.
2. On his acceptance, create one conversation in this session (`conversation_belongs_to_session`, `conversation_belongs_to_project` → PRJ-023) with the result, and add a `resolves` reference from that conversation to PI-589. The store moves PI-589 to Resolved through that edge; never edit its status.
3. Add one sentence to the "Session bootstrap" paragraph of `CLAUDE.md` saying PI-589 was accepted and when, as a documentation-only commit on `main`, with an explicit pathspec. Prefix the commit command with `GVR_OVERRIDE='GVR-229: documentation-only commit, auto-exempt paths'` if the rule check matches the command string.
4. Close this session: executive summary, status complete.

## 5. If a check fails

- **Check 1 fails** (the answer is the path, or the heading, or the first line of the table): the hook did not read the file or did not match the marked line. Read `crmbuilder-v2/data/session-open/` for this session's marker, and run `uv run pytest tests/crmbuilder_v2/test_session_open_hooks.py -q`. Record what was seen as a conversation that addresses PI-589, leave PI-589 In Review, and stop. The fix is a later session under PI-589.
- **Check 2 fails** while check 1 passes: the answer was read but the file was not recorded. Same treatment: record, leave In Review, stop.
- **Check 3 fails** while 1 and 2 pass: the filing rule (DEC-1192, PI-582) did not follow PI-589 to PRJ-023. That is not PI-589's defect. Record it as a new catalogue-or-filing planning item in PRJ-023 and continue with section 4.

## 6. Out of scope

- Any change to the catalogue of kinds of work (PROC-012..PROC-020) or its trigger phrases.
- Any change to how a session without a kind of work is opened (REQ-571, REQ-572).
- Any further work on deployment grants; PRJ-133 is complete (DEC-1198).

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 10-07-26 00:56 | Claude (Claude Code) | First version, written after PI-589 merged to main as `9b39501b` and moved to In Review. |
