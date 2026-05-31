# Apply close-out — SES-135 / CNV-037 (RBAC, RE-KEYED)

**Session:** SES-135 (Claude.ai, planning). **Conversation:** CNV-037.
**Parent Project:** PRJ-017 (YAML Schema v1.3 — Role-Based Access Control).

## Why this is re-keyed

This is the governance close-out for the **YAML schema v1.3 Section 12 (RBAC)**
drafting session. It was originally authored on `origin/main` (commit
`b1fe1fea`) as **SES-133 / CNV-035** with **DEC-345/346/347** and a Project
**WS-015** — in parallel with the PI-112 governance redesign, which had already
claimed those exact identifiers for entirely different content (the §11
decisions and the `workstream→Project` rename). To resolve the collision, the
RBAC line was re-keyed to next-free identifiers and reshaped to the post-rename
Project model:

| Original (origin/main) | Re-keyed (here) |
|---|---|
| SES-133 | **SES-135** |
| CNV-035 | **CNV-037** |
| DEC-345 / 346 / 347 | **DEC-350 / 351 / 352** |
| Project WS-015 | **Project PRJ-017** |
| `conversation_belongs_to_workstream` → WS-015 | `conversation_belongs_to_project` → PRJ-017 |
| *(no session membership edge)* | added `session_belongs_to_project` SES-135 → PRJ-017 |

The RBAC **schema content** (`app-yaml-schema.md` Section 12, commit `06c3605`)
was already an ancestor on `main`; only this governance record needed re-homing.

## Decisions recorded (RBAC)

- **DEC-350** — Section 12 placement: a new top-level section.
- **DEC-351** — no file-type discriminator: `roles:`/`teams:` are optional
  top-level keys, not a new program-file type.
- **DEC-352** — content-based loader discovery for deploy ordering.

## Apply

```bash
cd crmbuilder-v2
# pre-step: PRJ-017 created via POST /projects (YAML Schema v1.3 RBAC).
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_135.json
```

## Notes from the actual apply

- DEC-350-352, CNV-037, the references, and deposit_event **DEP-128** landed via
  the script. The script's `session` section was silently skipped here (a latent
  quirk — SES-134's apply created its session fine), so **SES-135 was created by
  a direct `POST /sessions`** with the inline `session_belongs_to_project` edge.
  Final graph verified consistent: SES-135 → PRJ-017, CNV-037 → SES-135,
  DEC-350-352 `decided_in` CNV-037.
- This close-out reconciles the parallel `origin/main` RBAC line into `main`
  (the original `b1fe1fea` SES-133/WS-015 version is superseded by this re-key).
