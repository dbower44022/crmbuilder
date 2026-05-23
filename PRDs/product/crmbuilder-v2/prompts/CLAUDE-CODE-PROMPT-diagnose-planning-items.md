# CLAUDE-CODE-PROMPT — Diagnose planning_items resolution patterns

**Last Updated:** 05-22-26 18:30
**Purpose:** Run the `diagnose_planning_items.py` diagnostic against the CRMBUILDER engagement's V2 SQLite database and report structured findings on why only one planning item shows status `resolved` despite many completed sessions.
**Diagnostic script:** `tools/diagnostics/diagnose_planning_items.py` (committed in `dde4eb4`)

This is an investigation prompt, not an apply prompt. It produces no commits and no governance records. The deliverable is the structured report at the end.

---

## Scope

Identify whether the under-resolved planning_items table is:

- A **close-out discipline gap** — the schema supports resolution but close-outs don't routinely transition prior planning items;
- A **schema vocabulary gap** — no `relationship_kind` (or status value) exists for "this planning item is resolved by that session/decision";
- Or an **outlier read** — the one resolved record is a create-and-resolve-in-same-session case, and most "completed" work was simply never tracked as a planning item in the first place.

Do NOT modify the database. Do NOT propose code changes. Observe, analyze, recommend.

---

## Pre-flight

```bash
# Working directory — the repo root, since the script lives at tools/diagnostics/
cd ~/Dropbox/Projects/crmbuilder

# On main, clean, up to date
git status
git pull --rebase origin main

# Confirm the diagnostic script is present (committed in dde4eb4)
ls -la tools/diagnostics/diagnose_planning_items.py

# API health (the diagnostic reads SQLite directly, but routing check still useful)
curl -sf http://127.0.0.1:8765/health

# Confirm the API is routed to the CRMBUILDER engagement — the dogfood DB, not CBM
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), '- latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect the latest SES-NNN to match the most recent applied close-out.
# If the API is down, ask Doug to start it; do not start it yourself.
```

---

## Locate the CRMBUILDER engagement SQLite file

The per-engagement DB is typically at `crmbuilder-v2/data/CRMBUILDER.db` per the engagements.db precedent, but verify rather than assume. Acceptable methods:

```bash
# Direct candidate path
ls -la crmbuilder-v2/data/CRMBUILDER.db

# If not there, find any *.db under crmbuilder-v2/data/ and identify the CRMBUILDER one
ls -la crmbuilder-v2/data/*.db 2>/dev/null

# Cross-check against engagements.db to confirm CRMBUILDER's expected db_filename
python3 - <<'PY'
import sqlite3, os
meta = "crmbuilder-v2/data/engagements.db"
if not os.path.exists(meta):
    print("engagements.db not found at", meta)
else:
    conn = sqlite3.connect(meta)
    conn.row_factory = sqlite3.Row
    for r in conn.execute("SELECT * FROM engagements"):
        cols = r.keys()
        ident = r['identifier'] if 'identifier' in cols else r[0]
        print(ident, "->", {k: r[k] for k in cols})
    conn.close()
PY
```

Report the resolved CRMBUILDER DB path before running the diagnostic.

---

## Run the diagnostic

```bash
python3 tools/diagnostics/diagnose_planning_items.py <resolved_path>
```

Capture the full stdout. Include the raw output as an appendix in your report (collapsed/quoted is fine; the structured findings come first).

---

## Analyze and report

Produce a report with these sections, in order:

**1. DB path used.** The full path Claude Code resolved and ran against, plus a one-line sanity check that this is the CRMBUILDER engagement (e.g., latest SES-NNN matches expectation).

**2. Status distribution.** Every status value with its count and the total. Flag any status values that look like typos or one-offs.

**3. Non-open records.** For each non-open planning_item, give:
- identifier and title
- status
- any timestamp or context columns that hint at when/how it transitioned
- whether it has any references pointing to it (from section 5/6 of the diagnostic output) and what `relationship_kind` they use

**4. Relationship-kind patterns for references targeting planning_items.** List with counts. Specifically call out whether any of these or similar are present: `resolves`, `resolved_in`, `resolved_by`, `completed_by`, `closes`, `closed_by`, `addresses`. If none of those exist, that is a finding.

**5. All relationship_kinds in the references table (top 20).** Verbatim from the diagnostic. This is context for whether a resolution-style relationship exists in the wider vocabulary but isn't being applied to planning_items.

**6. Diagnosis.** Pick the most likely cause from the three options in Scope, with one paragraph of reasoning. If the evidence is mixed, name both and explain what additional check would disambiguate.

**7. Recommended next step.** One concrete action. Examples (pick whichever the evidence supports, or propose your own):
- Add a `resolves` (or `resolved_in`) entry to the references-table relationship_kind vocab + close-out payload format, with a back-fill conversation to retro-resolve completed planning items;
- Add a `status` transition mechanism to the apply script's close-out flow (the current apply path is insert-only for planning_items);
- Establish a methodology rule that every close-out enumerates which prior PI-NNNs the conversation resolved, and surfaces them as a new payload section;
- Or: the discrepancy is acceptable because completed work is captured in `sessions.artifacts_produced` and the planning_items table is intentionally forward-looking only — in which case the schema/methodology gap is documentation, not data.

**8. Appendix.** Raw diagnostic output, fenced as a code block.

---

## Done

Reply in the chat with the eight-section report above. No commits, no file writes, no DB modifications. If anything in the pre-flight or DB-location step fails, stop and surface the failure rather than guessing.
