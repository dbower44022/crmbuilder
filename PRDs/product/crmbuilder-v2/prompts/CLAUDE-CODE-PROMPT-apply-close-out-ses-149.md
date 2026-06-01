# Apply close-out — SES-149 (ADO agent-layer evolution, design-complete)

**Engagement:** CRMBUILDER. **Branch:** `main` (Model A). **Payload:**
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_149.json`. Records the design
conversation that evolved the ADO agent layer to design-complete, captured in
`PRDs/product/crmbuilder-v2/agent-delivery-organization-evolution.md` (v0.2).

This close-out records seven design decisions as governance anchors pointing to
the doc sections: DEC-367 (reconciliation mechanism — Reconcile-as-Work-Task +
`finding` entity + coarse design gate), DEC-368 (expert taxonomy — disciplines =
the area vocab, (area × tier) profiles, three tiers for build disciplines),
DEC-369 (learning loop — registry as living institutional-knowledge base),
DEC-370 (release model — `REL-` entity + coarse all-or-nothing design gate),
DEC-371 (four core passes — Plan/Design/Develop/Test), DEC-372 (standing-agent
runtime — spawn-on-demand scheduler + invoked judgment-agents), DEC-373 (registry
scope — SYSTEM-level service with engagement overlays + unified multi-engagement-DB
direction). Session SES-149 / conversation CNV-051 under PRJ-018; addresses
(advances) PI-114 without resolving it. No code/migration — design only.

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_149.json
```
Applied 2026-06-01 (DEP-144) in a clean window (parallel PRJ-016 session quiet;
`force_export` produced 0 diff pre-apply, confirming the live DB matched the
committed snapshot; HEAD unchanged during apply). Then `force_export` from the
live DB and commit snapshots + dep log + payload + this prompt. Re-verify heads /
re-key on collision (SES-149/CNV-051/DEC-367..373 were next-free at authoring).
