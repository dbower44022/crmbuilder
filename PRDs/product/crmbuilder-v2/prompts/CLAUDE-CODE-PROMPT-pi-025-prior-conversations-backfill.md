# CLAUDE-CODE-PROMPT — PI-025 prior-conversations backfill

**Last Updated:** 05-23-26 22:30
**Purpose:** PI-025 Phase 3 backfill. Create the WS-008 audit-v1.2 workstream record, 37 work_ticket records (WT-009..WT-045), 37 conversation records (CONV-009..CONV-045), and the supporting reference edges (~140) in the CRMBUILDER engagement's V2 governance database. Discharges Phase 3 of PI-022 per the kickoff at `PRDs/product/crmbuilder-v2/pi-025-prior-conversations-backfill-kickoff.md` and per DEC-191..197 settled in SES-062.
**Script file:** `crmbuilder-v2/scripts/backfill_pi_025_prior_conversations.py` (this prompt authors it from the embedded source below, then runs it).
**Predecessor:** The SES-062 close-out (the conversation that produced this prompt) **must be applied before this prompt runs**. SES-062 lands the seven governing decisions (DEC-191..197) that justify the records this prompt creates. Apply order: SES-062 close-out -> this backfill prompt.

---

## Net effect

Records that land in the CRMBUILDER engagement on successful apply:

- **1 new workstream:** WS-008 Audit feature v1.2, status complete, started 2026-05-22, completed 2026-05-23. Establishes audit-v1.2 as a first-class workstream per DEC-191's fold-in.
- **1 update to existing workstream:** WS-006 (CBM paper test) gets its `workstream_notes` field set to the Option IV defer forward-pointer per DEC-192.
- **37 work_ticket records:** 5 of kind `kickoff_prompt` (the planning kickoffs that have a committed file in the v2 root directory), 26 of kind `claude_code_prompt` (the slice-implementation prompts in `prompts/`), 6 of kind `other` (sessions opened ad hoc without a committed kickoff file). All status=consumed at the script's close.
- **37 conversation records:** CONV-009 through CONV-045 covering sessions across WS-002, WS-003, WS-004, WS-005, WS-007, and WS-008. All status=complete, born-complete via single-POST with the references array carrying the workstream-membership, session-record, and work_ticket edges atomically per DEC-193.
- **~140 reference edges total:** 37 conversation_belongs_to_workstream, 37 conversation_records_session, 37 conversation_opens_against_work_ticket (all created as part of the conversation POST's references array), 29 conversation_succeeds_conversation (authored in a separate stage; the 8 records without a succeeds-edge are the 6 workstream-opening conversations plus the 2 ambiguous-insertion follow-ups per DEC-194).

WS-006 (CBM paper test) lands no conversation records per DEC-192's Option IV defer. Sixteen orphan sessions (SES-001..010, SES-046, SES-056, SES-057, SES-059, SES-061, SES-062) get no conversation records per DEC-197.

Idempotent on re-run: HTTP 409 and 422-duplicate are treated as already-present and skipped; lifecycle PATCHes treat `invalid_status_transition` as already-at-target.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Confirm clean working tree (the script will be committed in two steps:
# script file pre-run, regenerated snapshots post-run)
git status

# Pull latest commits from origin/main (this prompt was pushed from the
# PI-025 sandbox along with the SES-062 close-out artifacts)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Confirm the API is routed to the CRMBUILDER engagement (the dogfood DB)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect 62 sessions, latest SES-062 (the SES-062 close-out must already
# have been applied before running this prompt). If latest is SES-061,
# apply SES-062's close-out first via
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-062.md
# and return to this prompt.

# Capture pre-apply identifier heads and counts for delta verification
echo "=== Pre-apply heads ==="
echo "Workstreams (expect WS-007):"
curl -s http://127.0.0.1:8765/workstreams | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['workstream_identifier'] for r in d)[-1] if d else 'none', '- total:', len(d))"
echo "Conversations (expect CONV-008):"
curl -s http://127.0.0.1:8765/conversations | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['conversation_identifier'] for r in d)[-1] if d else 'none', '- total:', len(d))"
echo "Work_tickets (expect WT-008):"
curl -s http://127.0.0.1:8765/work-tickets | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['work_ticket_identifier'] for r in d)[-1] if d else 'none', '- total:', len(d))"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected pre-apply state: 7 workstreams (WS-001..007), 8 conversations (CONV-001..008), 8 work_tickets (WT-001..008), N references (capture).

---

## Author the backfill script

Create `crmbuilder-v2/scripts/backfill_pi_025_prior_conversations.py` with the exact content below. Keep file header, ordering, and idempotency semantics as written — they mirror `backfill_governance_phase_1.py` and `backfill_pi_024_prior_workstreams.py` so anyone familiar with the prior phases reads this script the same way.

```python
#!/usr/bin/env python3
"""PI-025 Phase 3 backfill — prior conversations.

One-off script that creates the WS-008 audit-v1.2 workstream record, 37
work_ticket records (WT-009..WT-045 by allocation order), 37 conversation
records (CONV-009..CONV-045), and the supporting reference edges:

- 1 new workstream: WS-008 Audit feature v1.2 (status complete).
- 1 PATCH to WS-006 workstream_notes (Option IV defer forward-pointer
  per DEC-192).
- 37 work_ticket records: 5 kickoff_prompt, 26 claude_code_prompt, 6
  other (for sessions opened ad hoc without a committed kickoff file).
- 37 conversation records, all status=complete, each with the four
  required edges authored in the same POST body:
    * conversation_belongs_to_workstream (required at create)
    * conversation_records_session (required for status=complete)
    * conversation_opens_against_work_ticket (required for status
      kickoff_drafted or later)
    * conversation_succeeds_conversation (optional; authored for 29 of
      the 37 records — every CONV except the 6 workstream-openers and
      the 2 ambiguous-insertion follow-ups, per DEC-194).
- 37 work_ticket lifecycle transitions: each WT walks drafted -> ready
  -> consumed after the conversation POST creates the inbound edge.

Idempotent on re-run: each POST treats HTTP 409 (and 422 duplicate) as
already-present; lifecycle PATCHes treat invalid_status_transition as
already-at-target.

Discharges Phase 3 of PI-022 per the kickoff at
PRDs/product/crmbuilder-v2/pi-025-prior-conversations-backfill-kickoff.md
and per DEC-191..197 settled in SES-062.

Run with the V2 API up at http://127.0.0.1:8765 (or override with --base).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

BASE = "http://127.0.0.1:8765"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

# WS-008 audit-v1.2 workstream (the fold-in per DEC-191).
_WS_008: dict[str, Any] = {
    "workstream_identifier": "WS-008",
    "workstream_name": "Audit feature v1.2",
    "workstream_purpose": (
        "Deliver the v1.2 plan for the role-aware audit feature — roles and teams "
        "top-level recognition, structured scope_access and system_permissions "
        "parsing, role-aware audit, role-aware configure, condition-expression "
        "role: leaf clause, deploy ordering, role-aware visibility, and "
        "security.yaml emission."
    ),
    "workstream_description": (
        "A three-session audit-v1.2 workstream. SES-053 reordered YAML schema "
        "Category 6 (Role-Based Access Control) work across v1.2 and v1.3 and "
        "drafted the audit-v1.2 gap-analysis Section 9. SES-058 established "
        "audit-v1.2 as a workstream and captured four foundational design "
        "decisions plus the v1.0 plan document. SES-060 resolved the Section 9 "
        "open questions and the security.yaml placement question, bumping the "
        "plan doc to v1.3. The implementation Prompts A through K are queued "
        "separately as planning items PI-034 through PI-044 and are not part "
        "of this workstream's content scope."
    ),
    "workstream_status": "complete",
    "timestamps": {
        "workstream_started_at": "2026-05-22T00:00:00",
        "workstream_completed_at": "2026-05-23T00:00:00",
    },
}


# WS-006 workstream_notes update — Option IV defer forward-pointer per DEC-192.
_WS_006_NOTES_UPDATE = (
    "Paper-test conversations live in the CBM engagement (ENG-002). CONV records "
    "to be authored when CBM engagement state is committed or a cross-engagement "
    "edge convention is settled — see SES-062 close-out and DEC-192."
)


# Per-session date map (sourced from sessions.json snapshot at PI-025
# planning time, plus SES-060 hardcoded for the not-yet-applied case).
_SES_DATE: dict[str, str] = {
    "SES-016": "05-14-26",
    "SES-011": "05-11-26",
    "SES-012": "05-11-26",
    "SES-013": "05-12-26",
    "SES-014": "05-12-26",
    "SES-015": "05-12-26",
    "SES-017": "05-12-26",
    "SES-018": "05-14-26",
    "SES-019": "05-14-26",
    "SES-020": "05-14-26",
    "SES-021": "05-14-26",
    "SES-022": "05-14-26",
    "SES-023": "05-15-26",
    "SES-024": "05-15-26",
    "SES-025": "05-16-26",
    "SES-026": "05-16-26",
    "SES-029": "05-16-26",
    "SES-030": "05-17-26",
    "SES-031": "05-17-26",
    "SES-032": "05-17-26",
    "SES-033": "05-17-26",
    "SES-034": "05-17-26",
    "SES-035": "05-17-26",
    "SES-027": "05-16-26",
    "SES-036": "05-16-26",
    "SES-037": "05-18-26",
    "SES-038": "05-18-26",
    "SES-039": "05-18-26",
    "SES-040": "05-18-26",
    "SES-041": "05-18-26",
    "SES-042": "05-18-26",
    "SES-043": "05-18-26",
    "SES-044": "05-19-26",
    "SES-045": "05-20-26",
    "SES-053": "05-22-26",
    "SES-058": "2026-05-23",
    "SES-060": "2026-05-23",
}


# 37 conversation+work_ticket pairs (CONV-009..CONV-045). The order in
# this list is the apply order; conversation_succeeds_conversation edges
# in stage F refer back to predecessors that have already been created.
_ITEMS: list[dict[str, Any]] = [
    {
        "conv_id": "CONV-014",
        "ses": "SES-016",
        "ws": "WS-002",
        "succeeds": None,
        "title": "v2-C catalog ingestion build — 42-entry base entity catalog into the v2 database",
        "purpose": "Execute the catalog-ingestion build defined by the catalog-ingestion PRD, landing nine SQLAlchemy tables and the four read-only MCP tools.",
        "description": "Single Claude Code-driven build session implementing the catalog-ingestion workstream (WS-002). Took the catalog-ingestion PRD authored on 05-09-26 as input and produced the nine SQLAlchemy tables, the one-time Alembic data migration, the catalog access layer, the REST endpoints, and the four read-only MCP tools (catalog_search, catalog_get_entity, catalog_get_cross_system_map, catalog_gap_check). End-state: V2's UI, API, and MCP server serve the 42-entry base entity catalog without external file dependencies.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-C-catalog-ingestion.md",
        "wt_title": "Kickoff: v2-C catalog ingestion build",
        "wt_desc": "Claude Code prompt that authored and ran the catalog ingestion build. Single-use seed for SES-016 within the catalog-ingestion workstream (WS-002).",
    },
    {
        "conv_id": "CONV-009",
        "ses": "SES-011",
        "ws": "WS-003",
        "succeeds": None,
        "title": "v0.4 planning — methodology entity schema-design workstream kickoff",
        "purpose": "Establish the methodology entity schema-design workstream as v0.4's release arc and scope the four per-entity schemas to design (domain, entity, process, crm_candidate).",
        "description": "Workstream-establishing planning conversation for WS-003. Mid-planning, redirected v0.4 from a UI-polish release to methodology entity schema design after the conversation surfaced that preparing V2 to serve as the system of record for CBM redo (governance plus methodology content) was the higher-leverage next step. Scoped four per-entity schemas (domain, entity, process, crm_candidate), established the schema-spec methodology guide template, and named the cross-spec precedents that all later schema workstreams inherit (parent-prefix field naming per DEC-046, source-first relationship-kind naming per DEC-048).",
        "wt_kind": "kickoff_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/ui-v0.4-planning-prompt.md",
        "wt_title": "Kickoff: v0.4 planning — methodology entity schema-design workstream",
        "wt_desc": "Planning prompt that opened SES-011 (the v0.4 planning conversation that established WS-003).",
    },
    {
        "conv_id": "CONV-010",
        "ses": "SES-012",
        "ws": "WS-003",
        "succeeds": "CONV-009",
        "title": "domain schema design — methodology entity schema workstream conversation #1",
        "purpose": "Produce the domain entity schema specification — first of four per-entity schemas in the methodology entity schema-design workstream.",
        "description": "First per-entity schema-design conversation in WS-003. Produced the domain.md schema specification covering identity, content, classification, and lifecycle fields plus the relationship inventory inbound and outbound. Locked the schema-spec methodology guide template against real content and established the per-entity-schema conversation cadence the three successor conversations follow.",
        "wt_kind": "kickoff_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/schema-design-kickoff-domain.md",
        "wt_title": "Kickoff: domain entity schema design",
        "wt_desc": "Per-entity schema-design kickoff for the first methodology entity (domain).",
    },
    {
        "conv_id": "CONV-011",
        "ses": "SES-013",
        "ws": "WS-003",
        "succeeds": "CONV-010",
        "title": "entity schema design — methodology entity schema workstream conversation #2",
        "purpose": "Produce the entity schema specification — second of four per-entity schemas in WS-003.",
        "description": "Second per-entity schema-design conversation in WS-003. Produced entity.md covering the entity-as-noun-of-the-domain concept, its field inventory, and the domain-membership relationship inherited from the domain spec. Refined the schema-spec methodology guide based on the domain conversation's signal.",
        "wt_kind": "kickoff_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/schema-design-kickoff-entity.md",
        "wt_title": "Kickoff: entity entity schema design",
        "wt_desc": "Per-entity schema-design kickoff for the second methodology entity (entity).",
    },
    {
        "conv_id": "CONV-012",
        "ses": "SES-014",
        "ws": "WS-003",
        "succeeds": "CONV-011",
        "title": "process schema design — methodology entity schema workstream conversation #3",
        "purpose": "Produce the process schema specification — third of four per-entity schemas in WS-003.",
        "description": "Third per-entity schema-design conversation in WS-003. Produced process.md covering the business-process-as-noun-of-the-domain concept, persona involvement, trigger and outcome fields, and the relationship inventory binding process to domain, entity, and persona records.",
        "wt_kind": "kickoff_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/schema-design-kickoff-process.md",
        "wt_title": "Kickoff: process entity schema design",
        "wt_desc": "Per-entity schema-design kickoff for the third methodology entity (process).",
    },
    {
        "conv_id": "CONV-013",
        "ses": "SES-015",
        "ws": "WS-003",
        "succeeds": "CONV-012",
        "title": "crm_candidate schema design — methodology entity schema workstream conversation #4",
        "purpose": "Produce the crm_candidate schema specification — fourth and final per-entity schema in WS-003.",
        "description": "Fourth and final per-entity schema-design conversation in WS-003. Produced crm_candidate.md covering the candidate-CRM-product evaluation entity, its scoring fields, and the methodology-entity inventory that the upcoming Phase 10 CRM Selection step consumes.",
        "wt_kind": "kickoff_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/schema-design-kickoff-crm_candidate.md",
        "wt_title": "Kickoff: crm_candidate entity schema design",
        "wt_desc": "Per-entity schema-design kickoff for the fourth methodology entity (crm_candidate).",
    },
    {
        "conv_id": "CONV-015",
        "ses": "SES-017",
        "ws": "WS-003",
        "succeeds": "CONV-013",
        "title": "v0.4 build planning",
        "purpose": "Integrate the four per-entity schemas into a coherent v0.4 release plan with implementation slices and a release PRD.",
        "description": "Build-planning conversation in WS-003 — the integrating conversation that took the four per-entity schema specifications as input and produced the v0.4 release PRD plus the six-slice implementation plan (slices A through F). Resolved cross-spec tensions where the four specs had drifted on shared decisions (the relationship-kind naming convention, the references-edge versus FK posture) and locked the consolidated vocab.py addition list for the release.",
        "wt_kind": "kickoff_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/ui-PRD-v0.4-build-planning-kickoff.md",
        "wt_title": "Kickoff: v0.4 build planning",
        "wt_desc": "Kickoff that opened SES-017 (the v0.4 build-planning conversation that integrated the four schema specs into a release plan).",
    },
    {
        "conv_id": "CONV-016",
        "ses": "SES-018",
        "ws": "WS-003",
        "succeeds": "CONV-015",
        "title": "v0.4 PRD reconciliation and approval",
        "purpose": "Reconcile the v0.4 release PRD against the four schema specs, settle remaining open questions, and approve the PRD for implementation.",
        "description": "Reconciliation conversation in WS-003 between the v0.4 build-planning PRD and the four per-entity schema specifications. Settled the last open cross-spec questions, approved the release PRD for implementation, and unblocked the six implementation slices.",
        "wt_kind": "other",
        "wt_path": None,
        "wt_title": "Kickoff: v0.4 PRD reconciliation (ad-hoc continuation)",
        "wt_desc": "No committed kickoff file — conversation opened ad hoc continuing from SES-017's in_flight_at_end content.",
    },
    {
        "conv_id": "CONV-017",
        "ses": "SES-019",
        "ws": "WS-003",
        "succeeds": "CONV-016",
        "title": "v0.4 slice A — foundation",
        "purpose": "Implement the v0.4 release's foundation slice — schema migrations, access layer, and the integrating skeleton.",
        "description": "First implementation slice of the v0.4 release. Created the four-entity SQLAlchemy table definitions, the Alembic migration, the access layer foundation, and the registration of the four entity types in vocab.py.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-A-foundation.md",
        "wt_title": "Kickoff: v0.4 slice A foundation",
        "wt_desc": "Claude Code prompt driving v0.4 slice A implementation.",
    },
    {
        "conv_id": "CONV-018",
        "ses": "SES-020",
        "ws": "WS-003",
        "succeeds": "CONV-017",
        "title": "v0.4 slice B — Domains panel",
        "purpose": "Implement the Domains master/detail panel in the V2 desktop UI as the first methodology-entity panel.",
        "description": "Second implementation slice of v0.4. Built the Domains panel with the master pane, the detail pane, and the New / Edit / Delete dialogs using the LIstDetailPanel pattern established in v0.3.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-B-domains-panel.md",
        "wt_title": "Kickoff: v0.4 slice B Domains panel",
        "wt_desc": "Claude Code prompt driving v0.4 slice B implementation.",
    },
    {
        "conv_id": "CONV-019",
        "ses": "SES-021",
        "ws": "WS-003",
        "succeeds": "CONV-018",
        "title": "v0.4 slice C — Entities panel",
        "purpose": "Implement the Entities master/detail panel in the V2 desktop UI.",
        "description": "Third implementation slice of v0.4. Built the Entities panel covering the methodology-entity table records, the domain-membership relationship widget, and the field-list rendering within the detail pane.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-C-entities-panel.md",
        "wt_title": "Kickoff: v0.4 slice C Entities panel",
        "wt_desc": "Claude Code prompt driving v0.4 slice C implementation.",
    },
    {
        "conv_id": "CONV-020",
        "ses": "SES-022",
        "ws": "WS-003",
        "succeeds": "CONV-019",
        "title": "v0.4 slice D — Processes panel",
        "purpose": "Implement the Processes master/detail panel in the V2 desktop UI.",
        "description": "Fourth implementation slice of v0.4. Built the Processes panel with persona-involvement rendering, trigger and outcome fields, and the relationship-section widget for process-to-entity and process-to-domain bindings.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-D-processes-panel.md",
        "wt_title": "Kickoff: v0.4 slice D Processes panel",
        "wt_desc": "Claude Code prompt driving v0.4 slice D implementation.",
    },
    {
        "conv_id": "CONV-021",
        "ses": "SES-023",
        "ws": "WS-003",
        "succeeds": "CONV-020",
        "title": "v0.4 slice E — CRM Candidates panel",
        "purpose": "Implement the CRM Candidates master/detail panel — the last new entity panel in v0.4.",
        "description": "Fifth implementation slice of v0.4. Built the CRM Candidates panel with the scoring fields, the evaluation-result detail-pane treatment, and the methodology-coverage inventory rendering.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-E-crm-candidates-panel.md",
        "wt_title": "Kickoff: v0.4 slice E CRM Candidates panel",
        "wt_desc": "Claude Code prompt driving v0.4 slice E implementation.",
    },
    {
        "conv_id": "CONV-022",
        "ses": "SES-024",
        "ws": "WS-003",
        "succeeds": "CONV-021",
        "title": "v0.4 slice F — closeout",
        "purpose": "Close out the v0.4 release — version bump, README, smoke test, and the SES-024 close-out payload.",
        "description": "Sixth and final implementation slice of v0.4. Bumped the v2 __version__ constant to 0.4.0, updated README release notes, ran the end-to-end smoke test confirming all four new panels render and persist across application restart, and authored the SES-024 close-out payload bundling the release-shipped decision.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-F-closeout.md",
        "wt_title": "Kickoff: v0.4 slice F closeout",
        "wt_desc": "Claude Code prompt driving v0.4 slice F closeout.",
    },
    {
        "conv_id": "CONV-023",
        "ses": "SES-025",
        "ws": "WS-004",
        "succeeds": None,
        "title": "v0.5 orientation — engagement management workstream kickoff, PI-001 reopening, paper-test deferral",
        "purpose": "Establish the v0.5 release arc — multi-engagement architecture — to close the gap that v0.4 left between dogfood and client content.",
        "description": "Workstream-establishing orientation conversation for WS-004. Opened immediately after v0.4 shipped to address the architectural gap that v0.4's methodology entity schemas needed to live in client-specific databases (not the CRMBuilder dogfood) for the CBM paper test to be meaningful. Reopened PI-001, deferred the CBM paper test until engagement isolation closes the gap, and named the three planning/architecture conversations that follow.",
        "wt_kind": "other",
        "wt_path": None,
        "wt_title": "Kickoff: v0.5 orientation (ad-hoc continuation)",
        "wt_desc": "No committed kickoff file — conversation opened ad hoc continuing from SES-024's in_flight_at_end content immediately after v0.4 shipped.",
    },
    {
        "conv_id": "CONV-024",
        "ses": "SES-026",
        "ws": "WS-004",
        "succeeds": "CONV-023",
        "title": "v0.5 Conversation 1 — multi-engagement architecture and engagement schema",
        "purpose": "Design the multi-engagement architecture and the engagement entity schema.",
        "description": "First v0.5 planning conversation. Settled the multi-engagement architecture (per-engagement SQLite files with a meta database tracking engagements), drafted the engagement entity schema, and produced the architectural decisions that the slice implementations execute against.",
        "wt_kind": "kickoff_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/v0.5-conversation-1-kickoff.md",
        "wt_title": "Kickoff: v0.5 Conversation 1 multi-engagement architecture",
        "wt_desc": "Planning kickoff that opened SES-026 (the v0.5 architecture conversation).",
    },
    {
        "conv_id": "CONV-026",
        "ses": "SES-029",
        "ws": "WS-004",
        "succeeds": "CONV-024",
        "title": "v0.5 Conversation 2 — build planning (release PRD, implementation plan, five slice build prompts)",
        "purpose": "Translate the v0.5 architecture into a release PRD, an implementation plan, and the five slice build prompts.",
        "description": "Second v0.5 planning conversation. Took the multi-engagement architecture as input and produced the v0.5 release PRD, the implementation plan, and the five Claude Code build prompts (slices A through E). Settled the release sequencing and the slice dependency order.",
        "wt_kind": "kickoff_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/v0.5-conversation-2-kickoff.md",
        "wt_title": "Kickoff: v0.5 Conversation 2 build planning",
        "wt_desc": "Planning kickoff that opened SES-029 (the v0.5 build-planning conversation).",
    },
    {
        "conv_id": "CONV-027",
        "ses": "SES-030",
        "ws": "WS-004",
        "succeeds": None,
        "title": "v0.5 slice A follow-up (launcher wiring) + slice D follow-up (route API at active engagement, fix latching)",
        "purpose": "Resolve two follow-up items that surfaced from v0.5 slice A and slice D implementations.",
        "description": "Follow-up conversation addressing two items from v0.5 implementation: slice A's launcher wiring (the desktop application launcher needed to route to the active engagement at startup rather than the meta database) and slice D's engagement-switching API routing (which had a latching bug where the API still pointed at the prior engagement after a switch). Both follow-ups produced patches against the slice implementations.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-A-followup-launcher-wiring.md",
        "wt_title": "Kickoff: v0.5 slice A follow-up — launcher wiring",
        "wt_desc": "Claude Code prompt driving the v0.5 slice A launcher-wiring follow-up. The companion slice D follow-up shared this conversation but did not have its own committed prompt.",
    },
    {
        "conv_id": "CONV-028",
        "ses": "SES-031",
        "ws": "WS-004",
        "succeeds": "CONV-026",
        "title": "v0.5 slice A — foundation infrastructure and dogfood migration",
        "purpose": "Implement v0.5 slice A — engagement-isolation foundation and migration of the existing dogfood content into ENG-001.",
        "description": "First implementation slice of v0.5. Built the engagement-isolation foundation (per-engagement SQLite file layout, meta database for engagement tracking) and migrated the existing single-database dogfood content into the new CRMBUILDER engagement (ENG-001).",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-A-foundation-and-dogfood-migration.md",
        "wt_title": "Kickoff: v0.5 slice A foundation and dogfood migration",
        "wt_desc": "Claude Code prompt driving v0.5 slice A implementation.",
    },
    {
        "conv_id": "CONV-029",
        "ses": "SES-032",
        "ws": "WS-004",
        "succeeds": "CONV-028",
        "title": "v0.5 slice B — engagement schema, access layer, REST API",
        "purpose": "Implement the engagement entity schema, the access layer, and the REST API endpoints for engagement management.",
        "description": "Second implementation slice of v0.5. Built the engagement entity SQLAlchemy table, the engagement access layer (CRUD plus listing), and the REST API endpoints (GET, POST, PATCH, DELETE) routing through the meta database.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-B-engagement-schema-and-api.md",
        "wt_title": "Kickoff: v0.5 slice B engagement schema and API",
        "wt_desc": "Claude Code prompt driving v0.5 slice B implementation.",
    },
    {
        "conv_id": "CONV-030",
        "ses": "SES-033",
        "ws": "WS-004",
        "succeeds": "CONV-029",
        "title": "v0.5 slice C — engagement management panel UI",
        "purpose": "Implement the engagement management panel in the V2 desktop UI.",
        "description": "Third implementation slice of v0.5. Built the engagement management panel — the master/detail UI for browsing, creating, editing, and deleting engagements.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-C-engagement-management-panel.md",
        "wt_title": "Kickoff: v0.5 slice C engagement management panel",
        "wt_desc": "Claude Code prompt driving v0.5 slice C implementation.",
    },
    {
        "conv_id": "CONV-031",
        "ses": "SES-034",
        "ws": "WS-004",
        "succeeds": "CONV-030",
        "title": "v0.5 slice D — engagement switching, top-strip, picker, single-gesture creation+activation",
        "purpose": "Implement engagement switching, the top-strip picker, and the single-gesture engagement creation-plus-activation flow.",
        "description": "Fourth implementation slice of v0.5. Built the engagement-switching mechanism, the top-strip engagement picker widget, and the single-gesture create-plus-activate flow (creating a new engagement also activates it in one step).",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-D-engagement-switching.md",
        "wt_title": "Kickoff: v0.5 slice D engagement switching",
        "wt_desc": "Claude Code prompt driving v0.5 slice D implementation.",
    },
    {
        "conv_id": "CONV-032",
        "ses": "SES-035",
        "ws": "WS-004",
        "succeeds": "CONV-031",
        "title": "v0.5 slice E — closeout (version 0.5.0, README release note, end-to-end integration smoke, full regression)",
        "purpose": "Close out the v0.5 release — version bump to 0.5.0, README update, integration smoke test, and regression.",
        "description": "Fifth and final implementation slice of v0.5. Bumped __version__ to 0.5.0, updated README with the v0.5 release note, ran the end-to-end integration smoke test against two engagements (CRMBUILDER and a test engagement), and the full regression suite.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.5-E-closeout.md",
        "wt_title": "Kickoff: v0.5 slice E closeout",
        "wt_desc": "Claude Code prompt driving v0.5 slice E closeout.",
    },
    {
        "conv_id": "CONV-025",
        "ses": "SES-027",
        "ws": "WS-005",
        "succeeds": None,
        "title": "Styling Conversation 1 — design pass: tokens, component visual decisions, application priorities, acceptance criteria",
        "purpose": "Capture the design pass for v0.6 — design tokens, component-level visual decisions, application priorities, and the release's acceptance criteria.",
        "description": "Workstream-establishing design-pass conversation for WS-005. Captured design tokens (color, spacing, typography), component-level visual decisions (sidebar, master pane, detail pane, dialogs, form controls, status treatments), application priorities (which panels get the design pass first), and the WCAG-AA contrast acceptance criteria.",
        "wt_kind": "kickoff_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/styling-conversation-1-kickoff.md",
        "wt_title": "Kickoff: Styling Conversation 1 design pass",
        "wt_desc": "Styling kickoff that opened SES-027 (the v0.6 design-pass conversation).",
    },
    {
        "conv_id": "CONV-033",
        "ses": "SES-036",
        "ws": "WS-005",
        "succeeds": "CONV-025",
        "title": "Styling Conversation 2 — build planning: ui-PRD-v0.6, implementation plan, six slice prompts, version planning",
        "purpose": "Translate the v0.6 design pass into a release PRD, implementation plan, and six slice build prompts.",
        "description": "Build-planning conversation for WS-005. Took the design-pass output and produced the ui-PRD-v0.6 release PRD, the implementation plan, and the six Claude Code build prompts (slices A through F). Settled the slice dependency order and the release sequencing.",
        "wt_kind": "other",
        "wt_path": None,
        "wt_title": "Kickoff: Styling Conversation 2 build planning (ad-hoc continuation)",
        "wt_desc": "No committed kickoff file — conversation opened ad hoc continuing from SES-027's in_flight_at_end content.",
    },
    {
        "conv_id": "CONV-034",
        "ses": "SES-037",
        "ws": "WS-005",
        "succeeds": "CONV-033",
        "title": "v0.6 slice A — foundation infrastructure + About dialog",
        "purpose": "Implement the v0.6 foundation slice — design-token infrastructure and the About dialog.",
        "description": "First implementation slice of v0.6. Built the design-token infrastructure (token definitions, application via Qt stylesheets) and the About dialog showcasing the token-driven visual identity.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-A-foundation.md",
        "wt_title": "Kickoff: v0.6 slice A foundation",
        "wt_desc": "Claude Code prompt driving v0.6 slice A implementation.",
    },
    {
        "conv_id": "CONV-035",
        "ses": "SES-038",
        "ws": "WS-005",
        "succeeds": "CONV-034",
        "title": "v0.6 slice B — sidebar + master-pane delegate",
        "purpose": "Implement the v0.6 styling for the sidebar and the master-pane Qt delegate.",
        "description": "Second implementation slice of v0.6. Styled the sidebar navigation and the master-pane list/table delegate to match the design tokens — typography, spacing, hover and selection states.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-B-sidebar-and-master-pane.md",
        "wt_title": "Kickoff: v0.6 slice B sidebar and master-pane",
        "wt_desc": "Claude Code prompt driving v0.6 slice B implementation.",
    },
    {
        "conv_id": "CONV-036",
        "ses": "SES-039",
        "ws": "WS-005",
        "succeeds": "CONV-035",
        "title": "v0.6 slice C — panel retrofits + ReferencesSection sub-section rewrite",
        "purpose": "Retrofit existing panels for the v0.6 design tokens and rewrite the ReferencesSection sub-section widget.",
        "description": "Third implementation slice of v0.6. Retrofitted each existing panel to consume the design tokens (no inline styles, no hard-coded colors) and rewrote the ReferencesSection widget for visual consistency with the rest of the detail pane.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-C-panel-retrofits.md",
        "wt_title": "Kickoff: v0.6 slice C panel retrofits",
        "wt_desc": "Claude Code prompt driving v0.6 slice C implementation.",
    },
    {
        "conv_id": "CONV-037",
        "ses": "SES-040",
        "ws": "WS-005",
        "succeeds": None,
        "title": "v0.6 slice A follow-up — force Fusion style + explicit light palette to neutralize OS theme bleed-through",
        "purpose": "Resolve OS-theme bleed-through in v0.6 slice A by forcing the Fusion Qt style and applying an explicit light palette.",
        "description": "Follow-up conversation patching v0.6 slice A. The design-token application via Qt stylesheets was still receiving OS-theme bleed-through (e.g., dark-mode users were getting dark backgrounds inside light-styled panels). Patch forces the Fusion Qt style at startup and applies an explicit light QPalette to neutralize the OS theme.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-A-followup-force-light-palette.md",
        "wt_title": "Kickoff: v0.6 slice A follow-up — force light palette",
        "wt_desc": "Claude Code prompt driving the v0.6 slice A follow-up patch.",
    },
    {
        "conv_id": "CONV-038",
        "ses": "SES-041",
        "ws": "WS-005",
        "succeeds": "CONV-036",
        "title": "v0.6 slice D — dialogs and form controls (button categories, edit-dialog context strip, delete-confirm dialog)",
        "purpose": "Style v0.6 dialogs and form controls — button categories, edit-dialog context strip, delete-confirm dialog.",
        "description": "Fourth implementation slice of v0.6. Styled the dialog family — button categories (primary, secondary, destructive), the edit-dialog context strip (showing which record is being edited), and the delete-confirm dialog with explicit destructive-action visual treatment.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-D-dialogs-and-form-controls.md",
        "wt_title": "Kickoff: v0.6 slice D dialogs and form controls",
        "wt_desc": "Claude Code prompt driving v0.6 slice D implementation.",
    },
    {
        "conv_id": "CONV-039",
        "ses": "SES-042",
        "ws": "WS-005",
        "succeeds": "CONV-038",
        "title": "v0.6 slice E — status, error, warning + crash banner",
        "purpose": "Style v0.6 status, error, and warning treatments and add the crash banner.",
        "description": "Fifth implementation slice of v0.6. Styled the status, error, and warning indicators throughout the UI and added a crash banner that surfaces unhandled exceptions to the user with a copy-to-clipboard diagnostic block.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-E-status-and-crash-banner.md",
        "wt_title": "Kickoff: v0.6 slice E status and crash banner",
        "wt_desc": "Claude Code prompt driving v0.6 slice E implementation.",
    },
    {
        "conv_id": "CONV-040",
        "ses": "SES-043",
        "ws": "WS-005",
        "succeeds": "CONV-039",
        "title": "v0.6 slice F — closeout (release 0.6.0): version bump, README, WCAG contrast build gate, design pass",
        "purpose": "Close out v0.6 — version bump to 0.6.0, README, WCAG contrast build gate, and the final design-pass review.",
        "description": "Sixth and final implementation slice of v0.6. Bumped __version__ to 0.6.0, updated README with the v0.6 release note, added the WCAG-AA contrast build gate to CI, and ran the final design-pass review confirming all panels render to the captured design tokens.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-F-closeout.md",
        "wt_title": "Kickoff: v0.6 slice F closeout",
        "wt_desc": "Claude Code prompt driving v0.6 slice F closeout.",
    },
    {
        "conv_id": "CONV-041",
        "ses": "SES-044",
        "ws": "WS-007",
        "succeeds": None,
        "title": "Multi-tenancy routing fix — planning: seven architectural decisions, two-slice build plan, slice prompts authored",
        "purpose": "Diagnose engagement-routing bugs exposed by the CBM paper test and produce a two-slice fix plan.",
        "description": "Workstream-establishing planning conversation for WS-007. Diagnosed engagement-routing bugs that the CBM paper test surfaced (the API still pointed at the prior engagement after switching, the desktop launcher did not re-route on engagement change). Settled seven architectural decisions and produced a two-slice build plan (helpers + CLI gate, UI refactor + affordances).",
        "wt_kind": "kickoff_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/multi-tenancy-routing-fix-planning-kickoff.md",
        "wt_title": "Kickoff: Multi-tenancy routing fix planning",
        "wt_desc": "Planning kickoff that opened SES-044 (the multi-tenancy routing-fix planning conversation).",
    },
    {
        "conv_id": "CONV-042",
        "ses": "SES-045",
        "ws": "WS-007",
        "succeeds": "CONV-041",
        "title": "Fix engagement switching (in-process re-route) + connection/version introspection",
        "purpose": "Implement the two-slice multi-tenancy routing fix — in-process re-route on engagement switch plus connection and version introspection.",
        "description": "Implementation conversation for WS-007. Executed the two-slice fix plan: in-process re-route ensuring the API session and the access layer rebind to the new engagement's database file on switch, and connection/version introspection adding a status-bar indicator of the currently-active engagement.",
        "wt_kind": "claude_code_prompt",
        "wt_path": "PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-A-helpers-cli-gate.md",
        "wt_title": "Kickoff: Multi-tenancy routing fix slice A",
        "wt_desc": "Claude Code prompt driving the first of two multi-tenancy routing fix slices. The companion slice B prompt (CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-B-ui-refactor-affordances.md) shared this conversation.",
    },
    {
        "conv_id": "CONV-043",
        "ses": "SES-053",
        "ws": "WS-008",
        "succeeds": None,
        "title": "YAML schema Category 6 (Role-Based Access Control) reordered across v1.2 and v1.3; gap-analysis Section 9 drafted",
        "purpose": "Reorder YAML schema Category 6 work across v1.2 and v1.3, draft the audit-v1.2 gap-analysis Section 9.",
        "description": "First conversation in WS-008. Reordered the YAML schema Category 6 (Role-Based Access Control) work between v1.2 and v1.3 — pulling role-aware audit and configure into v1.2 and deferring field-level permissions to v1.3. Drafted Section 9 (open questions and deferred decisions) of the audit-v1.2 gap-analysis document.",
        "wt_kind": "other",
        "wt_path": None,
        "wt_title": "Kickoff: audit-v1.2 Category 6 reordering (ad-hoc)",
        "wt_desc": "No committed kickoff file — conversation opened ad hoc to capture a Category 6 reordering decision that emerged from review of the prior YAML schema work.",
    },
    {
        "conv_id": "CONV-044",
        "ses": "SES-058",
        "ws": "WS-008",
        "succeeds": "CONV-043",
        "title": "Audit feature v1.2 workstream established: planning conversation captured four design decisions, authored the v1.0 plan doc",
        "purpose": "Establish audit-v1.2 as a workstream, settle the four foundational design decisions, and draft the v1.0 plan document.",
        "description": "Workstream-establishing planning conversation for WS-008. Captured the four design decisions defining audit-v1.2's scope — role-aware audit, role-aware configure, team-membership recognition, and the security.yaml emission. Authored the v1.0 audit-v1.2 plan document and named the eleven implementation prompts (Prompts A through K) that the release executes against.",
        "wt_kind": "other",
        "wt_path": None,
        "wt_title": "Kickoff: audit-v1.2 workstream establishment (ad-hoc)",
        "wt_desc": "No committed kickoff file — conversation opened ad hoc continuing from SES-053's in_flight_at_end content and from accumulated audit-feature signal across prior work.",
    },
    {
        "conv_id": "CONV-045",
        "ses": "SES-060",
        "ws": "WS-008",
        "succeeds": "CONV-044",
        "title": "audit-v1.2 planning resolved: §9 open questions and security.yaml placement decided, planning doc v1.1 through v1.3 authored",
        "purpose": "Resolve the four §9 open questions and the security.yaml placement question; bump the audit-v1.2 plan doc to v1.3.",
        "description": "Resolution conversation for WS-008. Settled the four open §9 questions from the audit-v1.2 gap analysis (role-aware audit decisions, condition-expression role: leaf clause, deploy ordering, role-aware visibility), settled the security.yaml file placement question, and authored versions 1.1 through 1.3 of the audit-v1.2 plan document. WS-008's content workstream closes here; the implementation Prompts A through K are queued separately as PI-034 through PI-044.",
        "wt_kind": "other",
        "wt_path": None,
        "wt_title": "Kickoff: audit-v1.2 planning resolution (ad-hoc)",
        "wt_desc": "No committed kickoff file — conversation opened ad hoc continuing from SES-058's in_flight_at_end content to resolve the remaining open §9 questions.",
    },
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _request(method: str, path: str, body: Any = None) -> tuple[int, Any]:
    """Issue an HTTP request and return (status_code, parsed_json)."""
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw) if raw else None
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return exc.code, raw
    except urllib.error.URLError as exc:
        print(f"  ! URL error for {method} {url}: {exc}", file=sys.stderr)
        return 0, None


def _log_result(label: str, status: int, payload: Any) -> bool:
    """Log the result of an API call. Return True if OK or duplicate-skip."""
    if 200 <= status < 300:
        print(f"  OK   {label} (HTTP {status})")
        return True
    if status == 409:
        print(f"  SKIP {label} (HTTP 409 — already present)")
        return True
    # 422 with duplicate/already-present semantics: skip
    if status == 422 and isinstance(payload, dict):
        err = (payload.get("errors") or {})
        if isinstance(err, list):
            err_str = str(err)
        else:
            err_str = json.dumps(err)
        if any(k in err_str.lower() for k in ("duplicate", "already", "exists")):
            print(f"  SKIP {label} (HTTP 422 — duplicate)")
            return True
    print(f"  FAIL {label} (HTTP {status}): {payload}", file=sys.stderr)
    return False


def _patch_status_with_skip(path: str, body: dict[str, Any], label: str) -> bool:
    """PATCH a status transition; treat invalid_status_transition as skip."""
    status, payload = _request("PATCH", path, body)
    if 200 <= status < 300:
        print(f"  OK   {label} (HTTP {status})")
        return True
    if status == 422 and isinstance(payload, dict):
        err_str = json.dumps(payload).lower()
        if "invalid_status_transition" in err_str:
            print(f"  SKIP {label} (HTTP 422 — already at target)")
            return True
        if any(k in err_str for k in ("duplicate", "already", "exists")):
            print(f"  SKIP {label} (HTTP 422 — duplicate)")
            return True
    print(f"  FAIL {label} (HTTP {status}): {payload}", file=sys.stderr)
    return False


# ---------------------------------------------------------------------------
# Stage A — Create WS-008 audit-v1.2 workstream
# ---------------------------------------------------------------------------


def create_ws_008() -> bool:
    status, payload = _request("POST", "/workstreams", _WS_008)
    return _log_result("workstream WS-008 (Audit feature v1.2)", status, payload)


# ---------------------------------------------------------------------------
# Stage B — Update WS-006 workstream_notes (Option IV defer forward-pointer)
# ---------------------------------------------------------------------------


def update_ws_006_notes() -> bool:
    body = {"workstream_notes": _WS_006_NOTES_UPDATE}
    status, payload = _request("PATCH", "/workstreams/WS-006", body)
    return _log_result("WS-006 workstream_notes update (Option IV defer)", status, payload)


# ---------------------------------------------------------------------------
# Stage C — Create 37 work_tickets as status=drafted
# ---------------------------------------------------------------------------


def create_work_tickets() -> bool:
    ok = True
    for i, item in enumerate(_ITEMS):
        wt_id = f"WT-{i + 9:03d}"
        body: dict[str, Any] = {
            "work_ticket_identifier": wt_id,
            "work_ticket_title": item["wt_title"],
            "work_ticket_description": item["wt_desc"],
            "work_ticket_kind": item["wt_kind"],
            "work_ticket_status": "drafted",
        }
        if item["wt_path"]:
            body["work_ticket_file_path"] = item["wt_path"]
        status, payload = _request("POST", "/work-tickets", body)
        ok &= _log_result(f"work_ticket {wt_id} ({item['conv_id']})", status, payload)
    return ok


# ---------------------------------------------------------------------------
# Stage D — Create 37 conversations born-complete with references array
# ---------------------------------------------------------------------------


def create_conversations() -> bool:
    ok = True
    for i, item in enumerate(_ITEMS):
        wt_id = f"WT-{i + 9:03d}"
        conv_id = item["conv_id"]
        ses_date = _SES_DATE.get(item["ses"], "2026-05-23")
        kickoff_at = f"{ses_date}T00:00:00"
        ready_at = f"{ses_date}T00:00:01"
        started_at = f"{ses_date}T00:00:02"
        completed_at = f"{ses_date}T23:59:00"

        refs: list[dict[str, Any]] = [
            {
                "source_type": "conversation", "source_id": conv_id,
                "target_type": "workstream", "target_id": item["ws"],
                "relationship": "conversation_belongs_to_workstream",
            },
            {
                "source_type": "conversation", "source_id": conv_id,
                "target_type": "session", "target_id": item["ses"],
                "relationship": "conversation_records_session",
            },
            {
                "source_type": "conversation", "source_id": conv_id,
                "target_type": "work_ticket", "target_id": wt_id,
                "relationship": "conversation_opens_against_work_ticket",
            },
        ]

        body = {
            "conversation_identifier": conv_id,
            "conversation_title": item["title"],
            "conversation_purpose": item["purpose"],
            "conversation_description": item["description"],
            "conversation_status": "complete",
            "timestamps": {
                "conversation_kickoff_drafted_at": kickoff_at,
                "conversation_ready_at": ready_at,
                "conversation_started_at": started_at,
                "conversation_completed_at": completed_at,
            },
            "references": refs,
        }
        status, payload = _request("POST", "/conversations", body)
        ok &= _log_result(f"conversation {conv_id} ({item['ses']}, {item['ws']})", status, payload)
    return ok


# ---------------------------------------------------------------------------
# Stage E — Walk each work_ticket through drafted -> ready -> consumed
# ---------------------------------------------------------------------------


def consume_work_tickets() -> bool:
    ok = True
    for i, item in enumerate(_ITEMS):
        wt_id = f"WT-{i + 9:03d}"
        ses_date = _SES_DATE.get(item["ses"], "2026-05-23")
        # Drafted -> ready
        ok &= _patch_status_with_skip(
            f"/work-tickets/{wt_id}",
            {"work_ticket_status": "ready"},
            f"{wt_id} -> ready",
        )
        # Ready -> consumed
        ok &= _patch_status_with_skip(
            f"/work-tickets/{wt_id}",
            {"work_ticket_status": "consumed"},
            f"{wt_id} -> consumed",
        )
    return ok


# ---------------------------------------------------------------------------
# Stage F — Create 29 conversation_succeeds_conversation edges
# ---------------------------------------------------------------------------


def create_succeeds_edges() -> bool:
    ok = True
    count = 0
    for item in _ITEMS:
        if not item["succeeds"]:
            continue
        body = {
            "source_type": "conversation", "source_id": item["conv_id"],
            "target_type": "conversation", "target_id": item["succeeds"],
            "relationship": "conversation_succeeds_conversation",
        }
        status, payload = _request("POST", "/references", body)
        ok &= _log_result(
            f"{item['conv_id']} succeeds {item['succeeds']}", status, payload
        )
        count += 1
    print(f"  ({count} succeeds-edges authored)")
    return ok


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify() -> None:
    print("\n=== Verification ===")
    expectations = [
        ("/workstreams", 8),
        ("/conversations", 45),
        ("/work-tickets", 45),
    ]
    for path, expected in expectations:
        status, payload = _request("GET", path)
        data = payload.get("data") if isinstance(payload, dict) else None
        n = len(data) if isinstance(data, list) else 0
        marker = "\u2713" if n >= expected else "\u26a0"
        print(f"  {marker} GET {path}: {n} records (expected >= {expected})")

    # Spot-check WS-008
    status, payload = _request("GET", "/workstreams/WS-008")
    if status == 200:
        d = payload.get("data") or {}
        print(
            f"  \u2713 WS-008: status={d.get('workstream_status')} "
            f"started={d.get('workstream_started_at', '')[:10]} "
            f"completed={d.get('workstream_completed_at', '')[:10]}"
        )
    else:
        print(f"  \u26a0 WS-008: GET failed (HTTP {status})")

    # Spot-check WS-006 notes were updated
    status, payload = _request("GET", "/workstreams/WS-006")
    if status == 200:
        d = payload.get("data") or {}
        notes = d.get("workstream_notes") or ""
        if "ENG-002" in notes and "DEC-192" in notes:
            print("  \u2713 WS-006 workstream_notes carries the Option IV forward-pointer")
        else:
            print(f"  \u26a0 WS-006 workstream_notes does not look updated: {notes[:80]}")
    else:
        print(f"  \u26a0 WS-006: GET failed (HTTP {status})")

    # Edge counts
    for kind, expected in [
        ("conversation_belongs_to_workstream", 45),  # 8 from Phase 1 + 37 new
        ("conversation_records_session", 45),
        ("conversation_opens_against_work_ticket", 45),
        ("conversation_succeeds_conversation", 36),  # 7 from Phase 1 + 29 new
    ]:
        status, payload = _request("GET", f"/references?relationship_kind={kind}")
        data = payload.get("data") if isinstance(payload, dict) else None
        n = len(data) if isinstance(data, list) else 0
        marker = "\u2713" if n >= expected else "\u26a0"
        print(f"  {marker} edges {kind}: {n} (expected >= {expected})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    global BASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default=BASE,
        help=f"API base URL (default: {BASE})",
    )
    args = parser.parse_args()
    BASE = args.base

    print(f"PI-025 prior-conversations backfill against {BASE}\n")

    stages: list[tuple[str, Any]] = [
        ("Stage A — Create WS-008 audit-v1.2 workstream", create_ws_008),
        ("Stage B — Update WS-006 workstream_notes (Option IV defer)", update_ws_006_notes),
        ("Stage C — Create 37 work_tickets (status drafted)", create_work_tickets),
        ("Stage D — Create 37 conversations (born complete)", create_conversations),
        ("Stage E — Walk work_tickets drafted -> ready -> consumed", consume_work_tickets),
        ("Stage F — Create 29 conversation_succeeds_conversation edges", create_succeeds_edges),
    ]

    all_ok = True
    for label, fn in stages:
        print(f"\n--- {label} ---")
        all_ok &= fn()

    verify()

    if not all_ok:
        print("\n\u2717 One or more stages failed. See errors above.", file=sys.stderr)
        return 1
    print("\n\u2713 PI-025 backfill complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

After authoring, run the script:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/backfill_pi_025_prior_conversations.py
```

Expected output:

- Stage A: 1 workstream POST OK (WS-008)
- Stage B: 1 workstream PATCH OK (WS-006 notes)
- Stage C: 37 work_ticket POSTs OK (WT-009..WT-045)
- Stage D: 37 conversation POSTs OK (CONV-009..CONV-045), each carrying 3 inline reference edges
- Stage E: 74 work_ticket PATCHes OK (drafted -> ready, ready -> consumed for each of 37)
- Stage F: 29 reference POSTs OK (conversation_succeeds_conversation edges)
- Verification:
  * workstreams=8, conversations=45, work_tickets=45 total
  * WS-008 status=complete, started=2026-05-22, completed=2026-05-23
  * WS-006 workstream_notes contains "ENG-002" and "DEC-192"
  * conversation_belongs_to_workstream edges: 45 (8 prior + 37 new)
  * conversation_records_session edges: 45 (8 prior + 37 new)
  * conversation_opens_against_work_ticket edges: 45 (8 prior + 37 new)
  * conversation_succeeds_conversation edges: 36 (7 prior + 29 new)

If any record returns 409 or 422-duplicate on first run, halt and investigate — first run should have zero skips. On re-run, every record should skip idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Workstreams (expect WS-008, total 8):"
curl -s http://127.0.0.1:8765/workstreams | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['workstream_identifier'] for r in d)[-1], '- total:', len(d))"
echo "Conversations (expect CONV-045, total 45):"
curl -s http://127.0.0.1:8765/conversations | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['conversation_identifier'] for r in d)[-1], '- total:', len(d))"
echo "Work_tickets (expect WT-045, total 45):"
curl -s http://127.0.0.1:8765/work-tickets | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['work_ticket_identifier'] for r in d)[-1], '- total:', len(d))"

# Spot-check a CONV from each workstream
for conv_id in CONV-014 CONV-009 CONV-024 CONV-025 CONV-041 CONV-043 CONV-045; do
  curl -s http://127.0.0.1:8765/conversations/$conv_id \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f\"$conv_id: status={d['conversation_status']} completed={d['conversation_completed_at'][:10]}\")"
done

# Spot-check that WS-008 has 3 members
curl -s 'http://127.0.0.1:8765/references?relationship_kind=conversation_belongs_to_workstream&target_id=WS-008' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f'WS-008 members: {len(d)} (expect 3)')"

# Spot-check WS-006 still has 0 conversation members (defer per DEC-192)
curl -s 'http://127.0.0.1:8765/references?relationship_kind=conversation_belongs_to_workstream&target_id=WS-006' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f'WS-006 members: {len(d)} (expect 0 per DEC-192)')"

# Reference delta — expect roughly +140 from pre-apply
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected: 8 workstreams total, 45 conversations total (8 prior + 37 new), 45 work_tickets total (8 prior + 37 new), reference delta approximately +140.

---

## Commit (two commits)

**Commit 1 — script file.** Before the snapshot regeneration, commit the script itself so the repo records the backfill code that was run:

```bash
cd ~/Dropbox/Projects/crmbuilder

git add crmbuilder-v2/scripts/backfill_pi_025_prior_conversations.py
git commit -m "Add PI-025 prior-conversations backfill script

One-off script that creates the WS-008 audit-v1.2 workstream record,
37 work_ticket records (WT-009..WT-045), 37 conversation records
(CONV-009..CONV-045), the WS-006 workstream_notes Option IV defer
update, and the ~140 supporting reference edges. Mirrors
backfill_governance_phase_1.py's and backfill_pi_024_prior_workstreams.py's
idempotency contract (HTTP 409 and 422-duplicate are treated as
already-present; lifecycle PATCHes treat invalid_status_transition
as already-at-target).

Discharges Phase 3 of PI-022 per the kickoff at
PRDs/product/crmbuilder-v2/pi-025-prior-conversations-backfill-kickoff.md
and per DEC-191..197 settled in SES-062."
```

**Commit 2 — regenerated snapshots.** The script's POSTs and PATCHes trigger `_refresh_snapshot` on every API write, regenerating the db-export JSON snapshots. After the script completes successfully, commit the regenerated snapshots and the change_log audit:

```bash
# Inspect what changed (workstreams.json, conversations.json, work_tickets.json,
# references.json, change_log.json)
git status PRDs/product/crmbuilder-v2/db-export/

# Commit the snapshot regeneration in a single commit
git add PRDs/product/crmbuilder-v2/db-export/
git commit -m "Apply PI-025 prior-conversations backfill: WS-008, CONV-009..045, WT-009..045

Records landed via backfill_pi_025_prior_conversations.py against
CRMBUILDER engagement:
- 1 new workstream (WS-008 Audit feature v1.2 status complete)
- 1 workstream update (WS-006 workstream_notes Option IV defer
  forward-pointer per DEC-192)
- 37 work_tickets (5 kickoff_prompt, 26 claude_code_prompt, 6 other)
  all status consumed
- 37 conversations (CONV-009..CONV-045) all status complete, born-
  complete via single-POST with the references array carrying the
  workstream-membership, session-record, and work_ticket edges
- ~140 reference edges (37 belongs_to_workstream, 37 records_session,
  37 opens_against_work_ticket, 29 succeeds_conversation)

WS-006 CBM paper test deferred via Option IV per DEC-192. Sixteen
orphan sessions (SES-001..010, SES-046, SES-056, SES-057, SES-059,
SES-061, SES-062) deferred per DEC-197."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-apply heads: WS-007, CONV-008, WT-008, references = N (captured)
- Post-apply heads: WS-008, CONV-045, WT-045, references = N + ~140
- Record counts (expect 1 workstream OK, 1 workstream PATCH OK, 37 work_tickets OK, 37 conversations OK, 74 work_ticket PATCHes OK, 29 succeeds-edges OK, 0 skips on first run)
- Script-file commit SHA and snapshot commit SHA
- Next conversation: PI-026 (PI-022 Phase 4 — historical-applies-as-deposit_events backfill — ~38 prior close-out payload JSONs become deposit_event records). Kickoff to be authored at PI-025's close; path TBD.
