# Apply close-out — SES-142 (WTK-005 ADO PI Lead substrate)

**Engagement:** CRMBUILDER. **Branch:** `main` (Model A). **Payload:**
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_142.json`. Normal new-session
close-out. Apply with the second of the parallel pair, SES-143 (WTK-004 UI panels).

WTK-005 was created via `POST /work-tasks` under WSK-001 and driven to Complete;
the PI Lead code is on `main` as commit `0b1a386`. The other session (the UI
panels) ran concurrently in an isolated worktree; both governance close-outs are
applied here, on `main`, by the orchestrating session (the worktree did no
governance, so no identifier collisions).

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_142.json
```
Creates CNV-044, SES-142, the commit record, DEC-364, the membership /
`session_works_work_task` (→WTK-005) / `decided_in` / `session_follows_from`
edges, and `CNV-044 addresses PI-114` (PI-114 stays Draft). Records DEP-137.
Then `force_export` from the live DB and commit the snapshots + dep log + payload
+ this prompt on `main`. Applied clean 2026-05-31 (DEP-137).
