# Kickoff — accept PI-596: a token-overlap match is capped at 0.75

| Field | Value |
|---|---|
| Title | Kickoff — accept PI-596: a token-overlap match is capped at 0.75 |
| Last Updated | 10-26-26 12:04 |
| Revision | 1.0 |
| Status | Ready to run once section 0 is done. PI-596 is In Review in PRJ-023; commit `86ea4ecc` is in production; PROC-019 is edited; PROC-016 is not. |
| Governs | One session: the session's own opening is the first acceptance check. Finish the one store edit still due, repeat the production verification, record Doug's acceptance as the conversation that resolves PI-596 and PI-595, add the CLAUDE.md sentence. |
| Source | SES-456 on 10-22-26: CNV-423, commit `86ea4ecc`, kickoff `kickoff-pi-596-token-overlap-cap.md` rev 1.1. Ruling DEC-1204, requirement REQ-667. |

## 0. Before the session — the PROC-016 edit, by Doug

The Claude Code permission classifier refused this write twice in SES-456, so Doug runs it by hand. One step, in the terminal whose prompt ends in `crmbuilder$`, at `~/Dropbox/Projects/crmbuilder`. Paste the block below and press Enter. You should see one line of JSON beginning `{"data":` with no `"errors":[`. If not, stop and paste what you see into the session. What it does: writes PROC-016's full trigger list with `review and build` removed, the first of the two catalogue edits DEC-1204 orders. To undo, run it again with the phrase added back.

```
set -a; source crmbuilder-v2/data/crmbuilder.env; set +a; curl -s -X PATCH -H "Authorization: Bearer $CRMBUILDER_V2_API_TOKEN" -H "X-Engagement: ENG-001" -H "Content-Type: application/json" "$CRMBUILDER_V2_API_BASE_URL/processes/PROC-016" --data '{"process_triggers":"[\"build a new application\", \"build a new module\", \"build from approved requirements\", \"new application from requirements\", \"implement the approved design\", \"build the app\", \"develop the module\", \"start the build\", \"build the following prompt\", \"build this prompt\", \"build the prompt\", \"build the kickoff\", \"run the kickoff prompt\", \"kickoff prompt\", \"build PI\"]"}'
```

If the session is allowed to make the write itself, it may instead run this same request as its first act and record that it did.

## Opening answer

Paste **only the path of this file** as the first prompt of the new session, nothing before it. A word in front of the path, such as `run`, stops the hook reading the file (PI-597).

```
/home/doug/Dropbox/Projects/crmbuilder/PRDs/product/crmbuilder-v2/kickoff-pi-596-acceptance.md
```

The answer below contains the exact phrase "review the build", which joined PROC-019 in SES-456, and the words "build" and "PI", which before the cap scored PROC-016 a full match through `build PI`. The opening is correct when the confirmation line names **Review what has been delivered**.

> Opening answer: Review the build of PI-596 in PRJ-023 — confirm that this session opened on the kind of work Review what has been delivered, finish the PROC-016 edit if still due, repeat the nine-answer verification, then record the acceptance conversation that resolves PI-596 and PI-595.

Previewed in production on 10-22-26 with the cap live and PROC-019 edited: "Review the build of PI-592" opened as PROC-019 at 1.0.

Operating mode: DETAIL. Stopping points: after section 3's table is reported, for Doug's acceptance word; nothing else pauses.

---

## 1. What this session delivers

Doug's acceptance of PI-596, recorded as a conversation that resolves PI-596 and PI-595; the CLAUDE.md sentence; the session closed. Or, if a check fails, a record of what failed and the one planning item that follows.

## 2. Where the work stands (verified 10-26-26 through the production API)

- **Commit `86ea4ecc`** on `main`, `Governed-By: PI-596`: `TOKEN_OVERLAP_CAP = 0.75` in `crmbuilder-v2/src/crmbuilder_v2/access/repositories/session_opening.py`; `_phrase_score` returns the token fraction capped at it; two tests in `tests/crmbuilder_v2/api/test_session_opening_api.py`. Pushed and rolled out by Doug on 10-22-26; the droplet's API restarted at 03:11 UTC on 10-23-26 with the new code.
- **PROC-019** holds twelve trigger phrases, the eleven as read plus `review the build` (edited 10-22-26, CNV-423).
- **PROC-016** still holds sixteen, including `review and build`. Section 0 removes it.
- **Verification** of the nine answers passed in production on 10-22-26 in that half-state. It is repeated here after section 0 because DEC-1204 orders both edits and the table is the measured result with both.
- **PI-596** In Review, addressed by CNV-423. **PI-595** Draft, addressed by CNV-422. Both resolve by edges from one conversation, never by a status edit.

## 3. The checks

1. The opening: the confirmation line names Review what has been delivered. Read SES-NNN's `medium_metadata.classification` to record the score and the runner-up.
2. `GET /processes`: PROC-016 has fifteen phrases without `review and build`; PROC-019 has twelve with `review the build`. If PROC-016 still has sixteen, stop and ask Doug to run section 0.
3. `GET /sessions/opening?answer=...` for each row; the result is under `preview` (`kind_of_work`, `confidence`). Every row must match. The preview carries no runner-up; the runner-up claim in row one rests on the unit test `test_exact_phrase_outranks_a_full_token_overlap_on_another_entry`.

| Answer | Expected | Expected score |
|---|---|---|
| Review the build of PI-592 | PROC-019 | 1.0 |
| Accept PI-592 after the build | PROC-019 | 1.0 |
| Review the build of PI-588 and accept it | PROC-019 | 1.0 |
| Review and build the kickoff for PI-588 | PROC-016 | 1.0 |
| please review and build the following prompt /home/doug/x.md | PROC-016 | 1.0 |
| Build the PI-592 scorer rule in PRJ-023 | PROC-016 | 0.75 |
| Build PI-575 — the store's engagement row becomes the application record | PROC-016 | 1.0 |
| What is a deployment grant? | PROC-020 | 1.0 |
| Fix the catalogue misroute PI-595 in PRJ-023 | PROC-018 | 1.0 |

Any difference is a defect to record, not to explain away. "Review the design before we build PI-600" and "Build the review screen for PI-601" are expected misses, not defects.

Report the three checks, then stop for Doug's word.

## 4. Governance records

- One conversation through `POST /conversations` (`conversation_`-prefixed fields; `references` with `source_type` `conversation` and `source_id` from `GET /conversations/next-identifier`): `conversation_belongs_to_session` → this session, `conversation_belongs_to_project` → PRJ-023, and after Doug's word `resolves` → PI-596 and `resolves` → PI-595. The connector's create tool cannot attach the session edge.
- If a check fails: the conversation carries `addresses` → PI-596 instead, and one planning item in PRJ-023 names the failure.
- One sentence in the "Session bootstrap" paragraph of `CLAUDE.md`, after the PI-592 sentence, naming REQ-667, the 0.75 cap, the two catalogue edits and the acceptance date. Commit with `Governed-By: trivial` and an `Exemption-Reason:`; mark this kickoff run in the same commit.
- Close the session: executive summary, status complete.

## 5. Out of scope

- PI-597, the `run ` plus path opening defect; its own ruling to come.
- Any further catalogue phrase.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 10-26-26 12:04 | Claude (Claude Code) | First version, written at the close of SES-456 after the build, rollout, the PROC-019 edit and the production verification; the PROC-016 edit carried forward as section 0 because the permission classifier refused it. |
