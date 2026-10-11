# Kickoff — PI-592: a one-token trigger phrase gets no token-overlap score

| Field | Value |
|---|---|
| Title | Kickoff — PI-592: a one-token trigger phrase gets no token-overlap score |
| Last Updated | 10-11-26 12:05 |
| Revision | 1.0 |
| Status | Ready to run. PI-592 is Draft in PRJ-023, ruled on 10-11-26: fix the scorer, do not edit the store. |
| Governs | One session: author the requirement, confirm it by decision, make PI-592 implement it, then build and test. |
| Source | SES-450 and the Claude Code session that followed it on 10-11-26: DEC-1201, PI-592. |

## Opening answer

> Opening answer: Build the PI-592 scorer rule in PRJ-023 — a catalogue trigger phrase that keeps one token after stopword removal gets no token-overlap score, so "what is" on PROC-020 stops matching every answer containing "what".

Operating mode: DETAIL.

---

## 1. What this session delivers

A confirmed requirement under TOP-118, PI-592 implementing it, the scorer change with tests, merged to `main` with `Governed-By: PI-592`.

## 2. The defect, verified 10-11-26

In `crmbuilder-v2/src/crmbuilder_v2/access/repositories/session_opening.py`, `_phrase_score` first checks the normalised phrase as a substring of the answer (score 1.0), then falls back to the fraction of the phrase's tokens found in the answer. `_tokens` drops stopwords. The PROC-020 phrase `what is` keeps one token, `what`, so any answer containing that word scores 1.0 on PROC-020 through the fallback. Consequences seen: an answer beginning "Review what has been delivered" ties PROC-019 and PROC-020 at 1.0 and matches neither; "Build what the readiness list needs for Boston" classifies as a question. `show me`, `explain` and `where is` on PROC-020 have the same shape.

Removing the phrase was measured and rejected (ruling on PI-592): "What is a deployment grant?" would stop matching, because only the exact-phrase rule catches it and no rewording keeps more than one token.

## 3. The requirement to author

One requirement under TOP-118, in the store's wording conventions: the token-overlap fallback applies only to a phrase that keeps at least two tokens after stopword removal; a one-token phrase scores through the exact-phrase rule alone. Provenance: defined in this session's conversation, belongs to TOP-118. Confirm it by a decision (`requirement_approved_by_decision`, then `activate_by_decision`), never a status edit. Then `planning_item_implements_requirement` from PI-592.

## 4. The build

- Change `_phrase_score` so the fallback returns 0.0 when the phrase has fewer than two tokens.
- Tests in `tests/crmbuilder_v2/` for: a one-token phrase still matches exactly; a one-token phrase no longer scores on a mere word hit; "Review what has been delivered …" classifies to PROC-019 against the live phrase lists; "What is a deployment grant?" still classifies to PROC-020.
- Run `uv run pytest tests/crmbuilder_v2/test_session_open*.py -q` and the classifier's own tests.
- Commit with an explicit pathspec, trailer `Governed-By: PI-592`. No store change; no rollout, since the hook runs from the repository on Doug's machine — but the classifier also runs inside the cloud API's session-open operation, so a production rollout of the API is needed for the change to take effect there. Check which one the session-open hook calls before declaring done.

## 5. Out of scope

- Any change to the exact-phrase rule, the threshold (0.6) or the ambiguity margin (0.15).
- Any edit to the catalogue phrases themselves.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 10-11-26 12:05 | Claude (Claude Code) | First version, after Doug ruled on PI-592 to fix the scorer rather than edit the store. |
