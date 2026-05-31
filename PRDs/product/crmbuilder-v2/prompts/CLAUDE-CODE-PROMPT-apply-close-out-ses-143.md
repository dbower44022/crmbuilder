# Apply close-out — SES-143 (WTK-004 Workstream + Work Task UI panels)

**Engagement:** CRMBUILDER. **Branch:** `main` (Model A). **Payload:**
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_143.json`. Normal new-session
close-out; apply AFTER SES-142 (it `session_follows_from` SES-142).

WTK-004 (the UI panels) was built by a parallel Claude Code session in an
isolated git worktree (code only, no governance), driven to Complete via the API,
and the worktree branch cherry-picked onto `main` as commit `6014e33`. This
close-out (no decision — the panels mirror existing ones) is authored on `main`
by the orchestrating session.

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_143.json
```
Creates CNV-045, SES-143, the commit record, the membership /
`session_works_work_task` (→WTK-004) / `session_follows_from` edges, and
`CNV-045 addresses PI-114` (PI-114 stays Draft). Records DEP-138. Then
`force_export` and commit. Applied clean 2026-05-31 (DEP-138).
