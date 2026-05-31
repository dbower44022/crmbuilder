# Apply close-out — SES-147 (scope the Agent Profile Registry as PI-122)

**Engagement:** CRMBUILDER. **Branch:** `main` (Model A). **Payload:**
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_147.json`. Normal close-out
that creates a Planning Item (PI-122) — no code commit.

Applied 2026-05-31 (DEP-142) in a clean window: the parallel session's SES-146
was committed first (`2f20e2a`) so the committed db-export matched the live DB,
heads were re-verified next-free (SES-147/CNV-049/DEC-366/PI-122), and HEAD did
not move during the apply. Creates CNV-049, SES-147, PI-122 (Draft, "Build the
Agent Profile Registry"), DEC-366, the membership / decided_in /
session_follows_from / planning_item_belongs_to_project (PRJ-018) edges, and
`CNV-049 addresses PI-114` (PI-114 stays Draft).

```bash
cd crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_147.json
```
Then `force_export` from the live DB and commit snapshots + dep log + payload +
this prompt on `main`. If re-applying after parallel activity, re-verify heads
and re-key on any collision (the payload label carries the gate note).
