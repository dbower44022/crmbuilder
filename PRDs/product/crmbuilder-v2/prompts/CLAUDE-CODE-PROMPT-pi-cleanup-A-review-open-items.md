# CLAUDE-CODE-PROMPT — pi-cleanup A: Review open planning items

**Last Updated:** 05-25-26 18:00
**Operating mode:** DETAIL
**Series:** pi-cleanup (Phase A of two: A = review proposal, B = apply approved resolutions)
**Status:** Authored. Run under Claude Code in Doug's local clone; do not push (Doug pushes after review).

---

## Purpose

Audit every Open planning item in the CRMBUILDER engagement and produce one scannable proposal file recommending **RESOLVE / KEEP / NEEDS-INPUT** per item. Doug reviews the proposal in chat with the next conversation, the Phase B apply prompt is generated from his approvals, and only Phase B mutates governance records.

**This prompt is read-only.** It writes one markdown file and one commit. No PATCH/POST/DELETE calls, no snapshot regeneration, no push.

**Net effect at completion of Phase A:**

- One new file: `PRDs/product/crmbuilder-v2/pi-cleanup/PI-CLEANUP-PROPOSAL.md`
- One commit on the working branch (not pushed)
- No database changes, no API writes

---

## Pre-flight

```bash
cd ~/Dropbox/Projects/crmbuilder || cd ~/crmbuilder
git status --short          # expect clean working tree
git pull --rebase origin main

# Confirm input snapshots are present and current
test -f PRDs/product/crmbuilder-v2/db-export/planning_items.json
test -f PRDs/product/crmbuilder-v2/db-export/sessions.json
test -f PRDs/product/crmbuilder-v2/db-export/decisions.json
test -f PRDs/product/crmbuilder-v2/db-export/references.json
test -f PRDs/product/crmbuilder-v2/db-export/conversations.json

# Output dir (idempotent)
mkdir -p PRDs/product/crmbuilder-v2/pi-cleanup
```

Snapshots are authoritative for this audit. The per-write `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py` keeps `db-export/*.json` current as of the last API write, so we read them directly and do not need the API running. (If `git pull --rebase` brings down newer snapshots than what's locally cached, that's fine — they're the truth source.)

---

## Discovery

Load the five input snapshots in one pass and report the headline count.

```python
import json, pathlib

EXPORT = pathlib.Path('PRDs/product/crmbuilder-v2/db-export')
pis           = json.loads((EXPORT / 'planning_items.json').read_text())
sessions      = json.loads((EXPORT / 'sessions.json').read_text())
decisions     = json.loads((EXPORT / 'decisions.json').read_text())
refs          = json.loads((EXPORT / 'references.json').read_text())
conversations = json.loads((EXPORT / 'conversations.json').read_text())

open_pis = [pi for pi in pis if pi['status'] == 'Open']
print(f'Open planning items to review: {len(open_pis)}')
```

Expected count at authoring time: 37. Report whatever the current count is to the user before proceeding.

---

## Per-item evidence gathering

For each Open PI, gather these signals into a working dict. Do this in Python — don't paste entire snapshots into context.

1. **Description text.** Read the PI's own `description` fully. Self-deferral language is a primary KEEP signal: phrases like "deferred", "target release: v0.5+", "future workstream", "conditional on", "when CBM redo", "TBD", "open question", "next release".

2. **Reference edges where the PI is target.** Filter `refs` for `target_type == 'planning_item' and target_id == <PI-ID>`. Bucket by `relationship_kind`:
   - `resolves` from a session/conversation → **unconditional RESOLVE signal**
   - `is_about` from a session or another PI → conversations/items that touched this PI
   - `addresses` → work that named the PI as an output target
   - `blocked_by` → the PI blocks this incoming source

3. **Reference edges where the PI is source.** Filter for `source_type == 'planning_item' and source_id == <PI-ID>`. An `is_about` outgoing from this PI to a parent PI means it's a child of a tracker.

4. **Originating session.** Find the session whose `topics_covered` first authored the PI — search `sessions.json` for the earliest session whose `topics_covered` text mentions the PI's identifier. Read that session's `artifacts_produced` and `topics_covered`. (This is best-effort; if no clear originator surfaces, skip.)

5. **Later session mentions.** Scan all sessions chronologically after the originating session for any whose `topics_covered` mentions the PI identifier. Capture the verbatim snippet around the mention — ±150 characters. This is the richest evidence source.

6. **Git log evidence.** Run `git log --all --oneline --grep="<PI-ID>"` for each PI. Collect commit subjects. Classify each subject as:
   - **Completion verb**: "resolve", "land", "ship", "complete", "implement", "close" → RESOLVE evidence
   - **Setup verb**: "kickoff", "plan", "scope", "design", "draft", "author" → neutral
   - **Other**: surface in the reason field but don't weight either direction

---

## Recommendation rules

Apply **in order**. First matching rule wins. The default at the bottom is KEEP.

1. **RESOLVE (unconditional):** an incoming `resolves` reference edge exists with this PI as target. Governance graph already says done; the status flip was missed.

2. **RESOLVE (verbatim completion):** a session's `topics_covered` chronologically after the originating session contains, case-insensitive substring: `resolves PI-NNN`, `completes PI-NNN`, `closes PI-NNN`, or `ships PI-NNN` (where NNN is this PI's numeric suffix).

3. **KEEP (self-deferred):** the PI's `description` contains, case-insensitive: `deferred`, `target release: v`, `future workstream`, `conditional on`, `when CBM`, `next release`, `TBD`, `open question`, `v0.5+`, `v0.6+`, `v0.7+`, `v0.8+`, `v0.9+`, `v1.0+`. These items self-mark as future work.

4. **KEEP (parent of open children):** at least one other Open PI has an `is_about` reference targeting this one. Parent trackers stay Open until all children are Resolved.

5. **NEEDS-INPUT (mixed signal):** a later session mentions the PI with partial-completion language — case-insensitive substring `phase 1 of`, `partial`, `in progress`, `started`, `began`, `first pass`, `slice [a-z] complete`. Work has progressed but completion is ambiguous.

6. **NEEDS-INPUT (silent progress):** at least one git commit subject references the PI with a completion verb (rule 6 in evidence gathering) AND the description has no deferral language AND no `resolves` edge exists. Work seems to have shipped but governance didn't catch up.

7. **KEEP (default):** no positive completion signal. The audit's conservative default — burden of evidence is on RESOLVE, never on KEEP.

For each PI, record both the **recommendation** and a **one-line reason** that cites the strongest piece of evidence the rule fired on. Reason examples:

- `resolves edge from SES-067` (rule 1)
- `SES-074 topics_covered: "...completes PI-029 with commit a1b2c3d..."` (rule 2)
- `description: "target release: v0.5 or later"` (rule 3)
- `parent of open PI-024 / PI-025 / PI-026` (rule 4)
- `SES-072 topics_covered: "...Phase 1 of 3 complete..."` (rule 5)
- `commit f8e9d0a "implement PI-031 panel" — no resolves edge` (rule 6)
- `no completion signal found` (rule 7)

---

## Output format

Write `PRDs/product/crmbuilder-v2/pi-cleanup/PI-CLEANUP-PROPOSAL.md` with this exact shape. Sort the table by PI identifier numeric suffix (PI-001, PI-002, …, PI-051). Doug scans in identifier order, not by recommendation.

````markdown
# PI Cleanup Proposal — Phase A Review

**Last Updated:** <MM-DD-YY HH:MM>
**Scope:** all Open planning items in the CRMBUILDER engagement
**Total reviewed:** <N>
**Recommended RESOLVE:** <count>
**Recommended KEEP:** <count>
**NEEDS-INPUT:** <count>

---

## Recommendations

| PI | Title | Recommendation | Reason |
|----|-------|----------------|--------|
| PI-001 | Full styling design pass per DEC-024 | KEEP | description: "Reopened as a parallel workstream by DEC-076"; parent workstream still authoring |
| PI-002 | Make `identifier` optional in POST bodies (SES-010 option C) | KEEP | description: "target release: v0.5 or later" |
| ... | ... | ... | ... |

---

## Method

- **Inputs:** `db-export/{planning_items,sessions,decisions,references,conversations}.json` (current per the per-write `_refresh_snapshot` hook).
- **Evidence per PI:** description text scan, incoming reference edges (`resolves`, `is_about`, `addresses`, `blocked_by`), later-session `topics_covered` mentions, and `git log --all --grep` matches.
- **Recommendation rules:** see `CLAUDE-CODE-PROMPT-pi-cleanup-A-review-open-items.md` §Recommendation rules. Conservative default: KEEP when no positive completion signal.
- **Reversibility:** any RESOLVE Doug spot-flags as wrong stays Open in Phase B; any KEEP that turns out to have been done can be re-resolved later with a one-off UPDATE-PROMPT.

---

## How to respond

Reply in chat with one of:

- "Approve all RESOLVE recommendations" — every row marked RESOLVE flips, every KEEP and NEEDS-INPUT stays Open.
- "Approve RESOLVE except PI-X, PI-Y" — listed exceptions stay Open.
- "Resolve PI-A, PI-B as well" — listed items override their KEEP / NEEDS-INPUT recommendation and flip.
- Any mix of the above.

Phase B (`CLAUDE-CODE-PROMPT-pi-cleanup-B-apply-resolutions.md`) is generated from your reply and runs against the V2 API as a standard close-out (resolutions bundled in a payload, applied via `apply_close_out.py`, snapshots regenerate, one deposit_event recorded).
````

---

## Commit

```bash
git add PRDs/product/crmbuilder-v2/pi-cleanup/PI-CLEANUP-PROPOSAL.md
git commit -m "chore(governance): pi-cleanup phase A — review proposal

Read-only audit recommending RESOLVE / KEEP / NEEDS-INPUT for every
Open planning item in the CRMBUILDER engagement. Phase B applies the
approved resolutions; no database changes in this commit."
```

Do **not** push. Doug pushes after he reviews the proposal.

---

## Done

Reply to Doug in chat with:

- Total Open PIs reviewed.
- Counts of RESOLVE / KEEP / NEEDS-INPUT recommendations.
- Commit SHA of the proposal commit.
- A one-line surprise note flagging anything unexpected the audit surfaced. Examples of what counts as surprise:
  - Any PI that fired rule 1 (`resolves` edge exists but status still Open) — this is a governance integrity issue worth naming.
  - Any PI whose description deferral language contradicts a later session's completion language.
  - Any PI flagged NEEDS-INPUT where the commit evidence is unusually strong (the script's "silent progress" rule firing on a real shipped workstream).
- Confirmation of the proposal file path: `PRDs/product/crmbuilder-v2/pi-cleanup/PI-CLEANUP-PROPOSAL.md`.

Tell Doug: review the table, reply in chat with approvals and exceptions, and Phase B will be generated from his response.
