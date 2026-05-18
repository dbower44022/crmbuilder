# CLAUDE-CODE-PROMPT-apply-status-update-post-ses-036

**Last Updated:** 05-18-26 13:00
**Operating mode:** detail
**Series:** apply-status-update
**Status:** Ready to execute
**Reason:** Current status entity (id=14, version=14, is_current=true) contains misleading claims about v0.6 build progress ("Slices A-E of v0.6 have shipped"). The actual source code shows v0.6 build has not started. This prompt issues a versioned-replace via `PUT /status` to install a corrected status entity reflecting true state at HEAD `b41fb04`.

---

## Purpose

One substantive operation: `PUT /status` with a corrected payload. The endpoint creates a new status version (will be version 15) that automatically becomes `is_current=true`; the existing version 14 stays in the DB with `is_current=false`. Versioned-replace semantics — history-preserving by design, no UPDATE on the existing row.

Net effect:
- `status.json` snapshot grows from 14 entries to 15.
- Version 14's `is_current` flips from `true` to `false`.
- Version 15 is the new current.
- The new content reflects: v0.5 shipped (correct, unchanged from prior entry); v0.6 BUILD NOT STARTED (corrected — prior entry falsely claimed slices A-E shipped); SES-036 reconciliation noted (new); canonical inventory counts updated (35 sessions, 104 decisions, 139 references per snapshot at HEAD).

---

## Background

The current status entity was authored at some point between commits `e183a32` (verify-pipe typo fix) and the most recent state (HEAD at `b41fb04`). It accurately describes v0.5 as shipped but then claims:

> "v0.6 (UI styling rollout) is in progress in parallel. Slices A-E of v0.6 have shipped (foundation infrastructure, sidebar + master-pane delegate, panel retrofits + sub-sectioned ReferencesSection, dialogs + form controls, status + error + warning + crash banner); slice F (closeout — version 0.6.0 bump, README release note, WCAG contrast test as build gate per DEC-097, full regression + integration smoke) is the only remaining work."

This is false. Source inspection shows:
- `crmbuilder-v2/src/crmbuilder_v2/ui/styling.py` is still the 72-line v0.1 minimal QSS stub from DEC-024.
- No `tokens.py`, no `t()` accessor, no `build_app_stylesheet()`.
- No `ui/assets/` directory (no Inter, no JetBrains Mono, no Lucide).
- No `ui/icons.py`, `ui/elevation.py`, `ui/widgets/modal_backdrop.py`, `ui/widgets/master_pane_delegate.py`.
- `ui/widgets/` contains only v0.5 widgets plus the v0.3-shipped `references_section.py` (not yet rewritten for sub-sectioned plain-list).
- `__version__` is `"0.5.0"` (slice F would bump to `"0.6.0"`).

v0.6 build has not started. Slice A is next.

This prompt corrects the record.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root.

2. **Confirm `git status` is clean.**

3. **Confirm git identity:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest:**

   ```bash
   git pull --rebase origin main
   ```

5. **Confirm v2 API is running:**

   ```bash
   curl -sf http://127.0.0.1:8765/decisions >/dev/null && echo "API up" || echo "API DOWN"
   ```

   If not running, ask Doug to start it (`cd crmbuilder-v2 && uv run crmbuilder-v2-api &`).

6. **Confirm current status entity is version 14:**

   ```bash
   curl -s http://127.0.0.1:8765/status | python3 -c "
   import sys, json
   r = json.load(sys.stdin)['data']
   print(f'Current version: {r.get(\"version\")}')
   print(f'Is current: {r.get(\"is_current\")}')
   "
   ```

   Expected: `Current version: 14`, `Is current: True`. If the version is something other than 14, **stop and report** — another process has already replaced the status entity, and this prompt's pre-state assumption is invalidated; Doug needs to review and re-author.

7. **Confirm the next available status version is 15:**

   ```bash
   curl -s http://127.0.0.1:8765/status/next-identifier | python3 -m json.tool
   ```

   Expected: `{"data": {"next": 15}, ...}`. Stop and report if not 15.

---

## Workflow

### Step 1 — PUT the corrected status payload

Write the new payload via a Python script. Save the script as `/tmp/status_update_post_ses036.py`, then run it.

```bash
cat > /tmp/status_update_post_ses036.py << 'PYEOF'
"""Apply corrected status entity post-b41fb04.

Issues PUT /status with content reflecting true state at HEAD:
v0.5 shipped; v0.6 BUILD NOT STARTED (not slices A-E as falsely
claimed by version 14); SES-036 reconciliation captured; inventory
counts canonical to snapshot.
"""

from __future__ import annotations

import json
import urllib.request

API = "http://127.0.0.1:8765"


ACTIVE_WORK = """v0.5 (engagement management) is shipped and governance-complete. The multi-engagement routing foundation is live: meta DB at crmbuilder-v2/data/engagements.db holds the engagements registry; per-engagement DBs at crmbuilder-v2/data/engagements/{engagement_code}.db hold the methodology and governance content; the two-database API server routes /engagements/* to the meta DB and everything else to the active engagement DB; the desktop top-strip + picker + activation worker orchestrate the kill-relaunch dance to switch engagements; cross-restart active-state persists via current_engagement.json; the dogfood migration rehoused the existing v2.db into engagements/CRMBUILDER.db with backup-first verify-row-counts delete-original discipline. v0.5 governance trail: SES-029 (PRD authoring) + DEC-098..104; SES-030 (slice A launcher-wiring follow-up + slice D follow-up); SES-031..SES-035 (build-execution closeouts). __version__ is 0.5.0.

v0.6 (UI styling rollout) build planning is governance-complete but the build itself has NOT started. Source state at HEAD: ui/styling.py is still the 72-line v0.1 minimal QSS stub from DEC-024 (legacy navy #1F3864 accent, no tokens, no QFontDatabase font loading, no Lucide icons); ui/assets/ does not exist; ui/widgets/master_pane_delegate.py does not exist; ui/icons.py and ui/elevation.py do not exist; ui/widgets/references_section.py is still the v0.3-shipped widget with inbound/outbound grouping (not sub-sectioned plain-list). The styling design pass (SES-027, DEC-087..094) settled tokens, fonts, icons, modal elevation, selected-state vocabulary, and component visual decisions. The build planning (SES-036, DEC-105..107) settled version bundling as separate v0.6 release, six-slice structure A-F, and slice acceptance pattern (per-slice screenshots + closeout WCAG check). Six slice build prompts authored at prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-{A..F}-*.md. None executed yet. Slice A (foundation + About dialog) is next.

PI-001 (full styling design pass per DEC-024) discharges with slice F when __version__ bumps to 0.6.0. The four prior deferral decisions (DEC-026/037/042/076) are settled by virtue of v0.6 build being queued.

The paper-test workstream (DEC-077) is fully unblocked. The next Claude.ai conversation can be the paper-test kickoff against a freshly-created CBM engagement via the single-gesture creation+activation flow shipped in v0.5 slice D.

Identifier reconciliation history: the styling Conversation 2 originally anticipated SES-028 at PRD-authoring time, rebased to SES-030 at close-out artifact authoring (commit 7255667 on 05-16-26) based on snapshot showing SES-029 as latest applied. Between that rebase and Doug's apply-prompt run (05-18-26), a separate v0.5 follow-up conversation independently claimed SES-030 on 05-17-26 by direct API POST without committing a ses_030.json file. When Doug ran the styling Conversation 2's apply prompt (commit cfdd088), the script absorbed the SES-030 conflict as SKIP and DEC-105/106/107 plus four references inserted pointing at the wrong SES-030 record. Reconciled at commit b41fb04: the styling Conversation 2 session content was applied at SES-036 (next available after SES-035), four corrected references added pointing at SES-036, and four orphan references (ids 136, 137, 138, 139) deleted. SES-030 in the DB remains correctly the v0.5 follow-up record. The styling Conversation 2's governance trail is now consistent at SES-036."""


READING_ORDER = """For a new Claude.ai session opening against this project, the recommended reading order at HEAD b41fb04 is: (1) CLAUDE.md at the repo root; (2) the current status entity (this record) for the snapshot of where things stand; (3) the latest charter version for governance philosophy; (4) sessions.json filtered to SES-029..SES-036 to ground in recent v0.5 and v0.6-planning work; (5) the styling design pass at PRDs/product/crmbuilder-v2/styling-design-pass.md if the session involves any visual work; (6) ui-PRD-v0.6.md and ui-v0.6-implementation-plan.md if the session is v0.6 build execution. For paper-test work specifically: also read DEC-077 and the workstream plan reference."""


PAYLOAD = {
    "title": "CRMBuilder v2 status",
    "phase": "Building v0.6",
    "version_label": "0.5+",
    "metadata": {
        "Last Updated": "05-18-26 13:00",
        "Status": "v0.5 shipped; v0.6 build queued (slice A next)",
    },
    "active_work": ACTIVE_WORK,
    "blockers": "None.",
    "live_inventory": {
        "in_database": [
            "104 decisions: DEC-001..DEC-107 with three gaps at DEC-095/096/097 (anticipated by styling Conversation 2 at PRD-authoring time, rebased to DEC-105/106/107 per parallel-workstream coupling discipline in DEC-076)",
            "35 sessions: SES-001..SES-036 with one gap at SES-028 (consumed in flight by parallel v0.5 work; styling Conversation 2 rebased to SES-030 then displaced to SES-036 after reconciliation b41fb04)",
            "2 charter versions (latest is_current)",
            "15 status versions (this one is the new current)",
            "139 references",
            "17 planning_items (PI-001..PI-017)",
            "42 catalog entities + 415 catalog attributes (base entity catalog, established by SES-016)",
            "1 engagement (CRMBUILDER) in the meta DB at crmbuilder-v2/data/engagements.db",
        ],
        "still_markdown": [
            "PRDs/product/crmbuilder-v2/storage-system-PRD-v0.1.md (PRD, not bootstrapped governance content)",
            "PRDs/product/crmbuilder-v2/storage-system-implementation-plan.md",
            "PRDs/product/crmbuilder-v2/prompts/*.md (Claude Code prompt files)",
            "PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md, v0.2.md, v0.3.md, v0.4.md, v0.5.md, v0.6.md (PRDs, not bootstrapped governance content)",
            "PRDs/product/crmbuilder-v2/ui-implementation-plan.md and ui-v0.2-/v0.3-/v0.4-/v0.5-/v0.6-implementation-plan.md",
            "PRDs/product/crmbuilder-v2/styling-design-pass.md and styling-workstream-plan.md",
            "PRDs/product/crmbuilder-v2/v0.5-conversation-1-kickoff.md and styling-conversation-1-kickoff.md",
            "PRDs/product/crmbuilder-v2/close-out-payloads/*.json (apply-script inputs; ephemeral once applied)",
        ],
        "v1_unchanged": [
            "v1 codebase under crmbuilder-v1/ — frozen reference; no v0.5/v0.6 changes touch it",
            "v1 documentation under PRDs/ outside the crmbuilder-v2/ subtree — frozen reference",
            "Cleveland Business Mentors engagement under separate dbower44022/ClevelandBusinessMentoring repo — separate workstream",
            "Operating-mode and decision-template preferences in user profile — methodology-stable across releases",
            "CLAUDE.md repo conventions — unchanged since SES-025 update",
        ],
    },
    "pending": {
        "v0_6_in_progress": [
            "Slice A (foundation + About dialog) — prompt authored at prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-A-foundation.md; execution queued",
        ],
        "planning_paused_until_ui_complete": [
            "Paper-test workstream (DEC-077) — fully unblocked once v0.6 ships; can also proceed against v0.5 if visual polish is acceptable",
            "v0.7+ planning (engagement-record details surfaces, methodology authoring surfaces) — gated on v0.6 ship",
            "Dark-mode theme values authoring — token structure is dark-mode-ready per DEC-089; values deferred to a separate PI",
            "Windows-specific cross-platform polish — deferred per workstream plan §3.2",
        ],
        "post_v0_6_candidates": [
            "Paper-test kickoff against a freshly-created CBM engagement (single-gesture creation+activation flow shipped in v0.5 slice D)",
            "CBM-branded palette theme variant (additive theme dict per DEC-089 structure)",
            "Print-friendly theme variant (same pattern)",
            "Custom brand mark for About dialog (deferred per DEC-094 — modest showcase chosen over full showcase to avoid logo-authoring derail)",
            "Full accessibility audit beyond WCAG AA contrast floor (deferred per design pass §4.6)",
            "Animation and motion design (deferred per design pass §4.6)",
            "Phosphor or expanded Lucide icon set (additive per DEC-092 — icons bundled as components need them)",
            "Spreadsheet-density master pane variant for high-row-count panels (rejected at v0.6 design pass per DEC-093 master-pane posture decision; could be reconsidered if usage patterns change)",
        ],
    },
    "reading_order_for_new_sessions": READING_ORDER,
}


def main() -> None:
    body = json.dumps({"payload": PAYLOAD}).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/status",
        data=body,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    new_version = result.get("data", {}).get("version")
    is_current = result.get("data", {}).get("is_current")
    print(f"PUT /status -> version={new_version} is_current={is_current}")
    if new_version != 15 or not is_current:
        raise SystemExit("Unexpected response — stop and report")


if __name__ == "__main__":
    main()
PYEOF

python3 /tmp/status_update_post_ses036.py
```

Expected output: `PUT /status -> version=15 is_current=True`. Stop and report on anything else.

### Step 2 — Verify post-state

```bash
curl -s http://127.0.0.1:8765/status | python3 -c "
import sys, json
r = json.load(sys.stdin)['data']
print(f'Current version: {r.get(\"version\")}')
print(f'Is current: {r.get(\"is_current\")}')
p = r.get('payload', {})
print(f'Phase: {p.get(\"phase\")}')
print(f'Last Updated: {p.get(\"metadata\", {}).get(\"Last Updated\")}')
print(f'Pending v0_6_in_progress: {p.get(\"pending\", {}).get(\"v0_6_in_progress\")}')
"

# Verify version 14 is no longer current
curl -s http://127.0.0.1:8765/status/versions/14 | python3 -c "
import sys, json
r = json.load(sys.stdin)['data']
print(f'Version 14 is_current: {r.get(\"is_current\")}')
"
```

Expected output:
- `Current version: 15` and `Is current: True`.
- `Phase: Building v0.6`.
- `Last Updated: 05-18-26 13:00`.
- `Pending v0_6_in_progress` contains the slice A entry.
- `Version 14 is_current: False`.

Stop and report on any mismatch.

### Step 3 — Verify snapshot regeneration

```bash
git status PRDs/product/crmbuilder-v2/db-export/
```

Expected modifications: `status.json` (version 15 added; version 14's is_current flipped) and `change_log.json`. If either is unchanged, the export hook may have failed — stop and report.

### Step 4 — Commit

```bash
git add PRDs/product/crmbuilder-v2/db-export/
git status   # confirm only db-export changes are staged
git commit -m "v2: status entity versioned-replace to version 15 — correct v0.6 build claims

Status version 14 falsely claimed 'Slices A-E of v0.6 have shipped'
and that 'slice F (closeout) is the only remaining work.' Source
inspection contradicts this:

- ui/styling.py is still the 72-line v0.1 minimal QSS stub from
  DEC-024 (legacy navy accent; no tokens; no QFontDatabase loading)
- ui/assets/ does not exist (no Inter, no JetBrains Mono, no Lucide)
- ui/widgets/master_pane_delegate.py does not exist
- ui/icons.py and ui/elevation.py do not exist
- __version__ remains '0.5.0' (slice F would bump to '0.6.0')

v0.6 build has not started. Slice A (foundation + About dialog) is
next.

Version 15 corrects the active_work narrative:
- v0.5 shipped and governance-complete (unchanged claim)
- v0.6 BUILD NOT STARTED; slice A is next
- SES-036 reconciliation history captured for the styling Conv 2
  identifier displacement
- Canonical inventory counts updated to snapshot at HEAD b41fb04:
  104 decisions, 35 sessions, 139 references, 15 status versions
- Reading order for new sessions guidance refreshed

Versioned-replace semantics: version 14 stays in the DB with is_-
current flipped to False; version 15 is the new current. No data
loss; history-preserving by design."
```

### Step 5 — Push

```bash
git push origin main
```

Stop and report on any push failure.

---

## Done

After Step 5, the status entity correctly reflects the actual state of the project at HEAD. Anyone (including Doug in a year, or a fresh Claude.ai session) reading the current status will see truthful information.

Next steps after this lands (not in scope for this prompt):
- v0.6 slice A execution via `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-A-foundation.md`.
- Slices B → C → D → E → F in sequence after each completes.
- After slice F lands and `__version__` is at "0.6.0", a follow-up status versioned-replace to "v0.6 complete" via the desktop versioned-replace dialog OR a parallel apply-status-update prompt like this one.
