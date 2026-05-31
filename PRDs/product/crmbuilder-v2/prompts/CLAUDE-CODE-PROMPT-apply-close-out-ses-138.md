# Apply close-out — SES-138 / CNV-040 (Model A branch-governance, RE-KEYED)

**Session:** SES-138 (Claude.ai → applied in Claude Code). **Conversation:** CNV-040.
**Parent Project:** PRJ-014 (Governance & Delivery Redesign).

## Why this is re-keyed

This is the governance close-out for the **Model A branch-governance** decision
("governance applies + db-export snapshot commits occur only on `main`"). It was
originally authored in Claude.ai (committed to `origin/main` as `47981d5`) using
**SES-137 / CNV-039 / DEC-356 / PI-114** — the same identifiers a parallel Claude
Code session had just used for the **Agent Delivery Organization** design and
**applied to the live DB**. To resolve the collision, the Model-A line was
re-keyed to next-free identifiers:

| Original (origin/main) | Re-keyed (here) |
|---|---|
| SES-137 | **SES-138** |
| CNV-039 | **CNV-040** |
| DEC-356 | **DEC-360** |
| PI-114 | **PI-115** |
| WT-064 | **WT-064** (was free; unchanged) |

The Model-A **guard code** (`b7e4a17d`, `3a2f4324`) was already an ancestor on
`main` — only this governance record needed re-homing.

## Apply

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_138.json
```

## Post-apply (observed)

- All 13 operations landed (deposit event **DEP-133**). Verified: `PI-115` →
  **Resolved**; `DEC-360` = "Model A …"; `SES-138 --session_belongs_to_project-->
  PRJ-014`; `WT-064` ready. A `planning_item_belongs_to_project` edge
  (PI-115 → PRJ-014) was added — the original Model-A payload lacked it.
- `main` is then reconciled with `origin/main` via a `-s ours` merge: the
  original `47981d5` `ses_137.json` (Model-A) is superseded — its content now
  lives at `ses_138.json`, and `ses_137.json` on `main` is the Agent Delivery
  Organization design.
