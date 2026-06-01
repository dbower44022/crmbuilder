# Apply close-out — SES-148 (ADO planning loop for PI-122)

**Engagement:** CRMBUILDER. **Branch:** `main` (Model A). **Payload:**
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_148.json`. Records the planning
session; no PI/decision created here (PI-122 already exists).

This close-out records the orchestrating session for the first real ADO planning
run: the PM dispatched PI-122 (Draft -> In Progress), the decomposer created six
phase Workstreams (WSK-002..007), and six real phase-specialist agents scoped
them into 18 Work Tasks (WTK-007..024) across four active phases, with Data
Migration + Deployment Not Applicable. Those Workstreams/Work Tasks are
operational records already in the live DB (written by the substrate endpoints);
this apply adds the session/conversation + `addresses PI-122` and the db-export
snapshot captures the whole tree.

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_148.json
```
Applied 2026-05-31 (DEP-143) in a clean window (parallel PRJ-016 session quiet,
HEAD unchanged during apply). Then `force_export` from the live DB and commit
snapshots + dep log + payload + this prompt. Re-verify heads / re-key on collision.
