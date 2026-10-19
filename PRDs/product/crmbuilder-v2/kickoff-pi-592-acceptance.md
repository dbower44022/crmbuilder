# Kickoff — accept PI-592: a one-token trigger phrase gets no token-overlap score

| Field | Value |
|---|---|
| Title | Kickoff — accept PI-592: a one-token trigger phrase gets no token-overlap score |
| Last Updated | 10-18-26 23:16 |
| Revision | 1.1 |
| Status | Run and accepted 10-18-26 in SES-452: all three checks passed; CNV-420 resolves PI-592. Section 6's PI-593 was ruled the same night (DEC-1203, SES-454). Kept as the record of the test. |
| Governs | One session: the session's own opening is the acceptance test. Record the result as the conversation that resolves PI-592, or record what failed. |
| Source | SES-451 on 10-13-26: REQ-666, DEC-1202, CNV-419, commit `0f1e59e1`. |

## Opening answer

This file is the test. Paste **only the path of this file** as the first prompt of the new session, nothing else:

```
/home/doug/Dropbox/Projects/crmbuilder/PRDs/product/crmbuilder-v2/kickoff-pi-592-acceptance.md
```

The hook reads this file and takes the line below as the opening answer. The answer contains the word "what" without the phrase "what is", which before the fix tied PROC-019 and PROC-020 at 1.0 and matched neither.

> Opening answer: Review what has been delivered for PI-592 in PRJ-023 — confirm that this session opened on the kind of work Review what has been delivered, then record the acceptance conversation that resolves PI-592.

Operating mode: DETAIL.

---

## 1. What this session delivers

Doug's acceptance of PI-592, recorded in the store as a conversation that resolves the item. Or, if the opening missed, a record of what happened and the one planning item that follows.

## 2. Where the work stands (verified 10-13-26 through the production API)

- **REQ-666** is confirmed (DEC-1202) under topic TOP-118: the token-overlap fallback applies only to a phrase that keeps at least two tokens after stopword removal; a one-token phrase scores through the exact-phrase rule alone.
- **PI-592** implements REQ-666, belongs to PRJ-023, and is In Review. CNV-419 addresses it.
- **Commit `0f1e59e1`** on `main` carries the build with trailer `Governed-By: PI-592`: `_phrase_score` in `crmbuilder-v2/src/crmbuilder_v2/access/repositories/session_opening.py` and tests in `tests/crmbuilder_v2/api/test_session_opening_api.py` and `tests/crmbuilder_v2/api/test_kind_of_work_catalogue.py`.
- **A production rollout is required.** The classifier runs inside the cloud API's session-open operation. Before this session, Doug runs `scripts/deploy-production.sh` and sees `DEPLOY OK: commit 0f1e59e1` or later.

## 3. The acceptance test is the opening itself

Before the first reply, check what the hook put in context and what Claude Code displayed:

1. **The session opened on the kind of work.** The hook's context block begins `# Session opened — SES-NNN (opening answer: "Review what has been delivered for PI-592 ...")` and the line after it begins `It sounds like you want to review what has been delivered`. Before the fix this answer scored 1.0 on both PROC-019 and PROC-020 and the line read `No kind of work was chosen for this session`.
2. **The session is filed under PRJ-023.** The answer names PI-592 and PRJ-023. Read `GET /references?source_type=session&source_id=SES-NNN` and look for `session_belongs_to_project` → PRJ-023.
3. **The one-token phrases still match exactly.** Through the production API, `POST /sessions/open` with the opening answer `What is a deployment grant?` returns `kind_of_work` PROC-020. Delete or cancel the session that call creates, or leave it noted as a test session.

State the result of each check in the first reply, in one line each, before anything else.

## 4. If all three checks pass — accept

1. Put the acceptance to Doug in plain text: the three checks passed. Wait for his word.
2. On his acceptance, create one conversation in this session (`conversation_belongs_to_session`, `conversation_belongs_to_project` → PRJ-023) with the result, and add a `resolves` reference from that conversation to PI-592. The store moves PI-592 to Resolved through that edge; never edit its status.
3. Add one sentence to the "Session bootstrap" paragraph of `CLAUDE.md` saying PI-592 was accepted and when, as a documentation-only commit on `main` with an explicit pathspec.
4. Close this session: executive summary, status complete.

## 5. If a check fails

- **Check 1 fails** with the no-kind-of-work line: first confirm the rollout happened (`curl -s https://api.crmbuilder.ai/` and the droplet's copy of `session_opening.py` carries `if len(ptoks) < 2`). If the rollout happened and the line still misses, record what was seen as a conversation that addresses PI-592, leave PI-592 In Review, and stop. The fix is a later session under PI-592.
- **Check 3 fails**: a one-token phrase no longer matches exactly. Same treatment: record, leave In Review, stop.

## 6. Also open

PI-593 records this build session's own opening answer, "Build the PI-592 scorer rule in PRJ-023", as a catalogue miss: PROC-016 and PROC-019 tie at 0.5 because no phrase covers "build PI". It needs Doug's ruling, in the shape of DEC-1201: a phrase on PROC-016, or no change.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.1 | 10-18-26 23:16 | Claude (Claude Code) | Status: run and accepted in SES-452 (CNV-420); PI-593 ruled in SES-454 (DEC-1203). |
| 1.0 | 10-18-26 23:05 | Claude (Claude Code) | First version, written after commit `0f1e59e1` was pushed and PI-592 moved to In Review. |
