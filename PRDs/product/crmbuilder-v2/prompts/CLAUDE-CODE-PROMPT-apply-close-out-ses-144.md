# Apply close-out — SES-144 (WTK-006 ADO Project Manager substrate)

**Engagement:** CRMBUILDER. **Branch:** `main` (Model A). **Payload:**
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_144.json`. Normal new-session
close-out.

WTK-006 (the PM substrate) was created via `POST /work-tasks` under WSK-001 and
driven to Complete; the code is on `main` as commit `6e0683e`. It is the last of
the four ADO agent-tier substrates.

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_144.json
```
Creates CNV-046, SES-144, the commit record, DEC-365, the membership /
`session_works_work_task` (→WTK-006) / `decided_in` / `session_follows_from`
edges, and `CNV-046 addresses PI-114` (PI-114 stays Draft). Records DEP-139.
Then `force_export` from the live DB and commit the snapshots + dep log + payload
+ this prompt on `main`. Applied clean 2026-05-31 (DEP-139).
