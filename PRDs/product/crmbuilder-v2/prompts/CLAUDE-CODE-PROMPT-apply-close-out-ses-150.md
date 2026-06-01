# Apply close-out — SES-150 (scope the unified-DB migration as PI-123)

**Engagement:** CRMBUILDER. **Branch:** `main` (Model A). **Payload:**
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_150.json`. Closes the ADO
evolution's (`agent-delivery-organization-evolution.md`) §10 NEXT list.

Scopes the last evolution item: the unified multi-engagement-DB migration. A new
project **PRJ-019 "Production Architecture"** was created first via **direct
`POST /projects`** (the recording-rules mechanism for projects — projects are not
bundled into close-out payloads). This close-out then creates **PI-123** (the
migration, Draft) under PRJ-019, wires **PI-122 `blocked_by` PI-123** (the
registry build waits on the production-DB foundation that makes cross-engagement
learning practical, DEC-373), and records the project-home choice as **DEC-374**.

```bash
# PRJ-019 created out-of-band first:
#   POST /projects  {project_name: "Production Architecture", ...}  -> PRJ-019
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_150.json
```
Applied 2026-06-01 (DEP-145) in a clean window (parallel PRJ-016 session quiet;
the only pre-apply `force_export` diff was the just-created PRJ-019, confirmed via
change_log to be the sole new entity; HEAD stable). Then `force_export` and commit
snapshots + dep log + payload + this prompt. Re-verify heads / re-key on collision
(SES-150/CNV-052/DEC-374/PI-123/PRJ-019 were next-free at authoring).
