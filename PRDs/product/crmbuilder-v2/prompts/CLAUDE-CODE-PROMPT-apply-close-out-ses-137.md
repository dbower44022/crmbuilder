# Apply close-out — SES-137 / CNV-039 (Agent Delivery Organization design)

**Session:** SES-137 (Claude Code, design). **Conversation:** CNV-039.
**Parent Project:** PRJ-018 (Agent Delivery Organization — created as the apply
pre-step). **Follows from:** SES-136.

## What this records

The design session that specified the **Agent Delivery Organization (ADO)** — the
team of role-specialized agents that DEC-343 adopted but left unspecified, now
that PI-112 has locked the data model it operates on.

- **Content deliverable (already committed):**
  `agent-delivery-organization-design.md` — v0.1 (`b0b213b`) → v0.2 (`520c460`,
  resolved the eight forks) → v0.3 (`11a1818`, renamed from "Agent-Delivery
  Runtime"). Ingested via the `commits` section.
- **New Project PRJ-018** "Agent Delivery Organization" (apply pre-step).
- **Bootstrap PI-114** "Build the Agent Delivery Organization" (`Draft`),
  `belongs_to` PRJ-018. The design session **addresses** it (the design phase is
  done; building remains) — it is *not* resolved.
- **Four decisions:** DEC-356 (adopt the design), DEC-357 (four-tier
  PM / PI Lead / Phase Specialist / Area Specialist), DEC-358 (always-all-phases +
  specialist scoping + `Not Applicable`), DEC-359 (Needs Attention as a flag).

## Apply

```bash
cd crmbuilder-v2
# pre-step: PRJ-018 created via POST /projects.
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_137.json
```

## Post-apply (observed)

- All 18 operations landed (the `apply_close_out` session-section skip seen at
  SES-135 did **not** recur here). Deposit event **DEP-132**.
- Verified: `SES-137 --session_belongs_to_project--> PRJ-018`;
  `PI-114 --planning_item_belongs_to_project--> PRJ-018` (so PRJ-018 rolls up
  PI-114 in the UI — the new containment kind in action); DEC-356-359
  `decided_in` CNV-039.
- Snapshots regenerated; committed with the payload, this prompt, and
  `dep_132.log`.

## Note

This is the governed record of the design conversation, authored *after* the user
corrected a governance lapse (work must be defined by a Work Task). The build of
the ADO (PI-114) is bootstrapped session-style — the organization cannot govern
its own construction — and once built will govern every PI after it.
