# Kickoff — Universal created/last-edited timestamp visibility (WT-057 → PI-108)

**Workstream:** WS-013 — Universal created/last-edited timestamp visibility
**Anchors:** PI-108 (implementation work item)
**Realizes:** REQ-002 — Universal created and last-edited timestamps, stored and visible in the UI
**Template precedent:** PI-107 / SES-118, commit `f690bde` (the Planning Items panel)

---

## Pre-flight (every v2 session)

1. Read `crmbuilder/CLAUDE.md`.
2. Read `specifications/governance-recording-rules.md` before authoring any governance record.
3. Capture identifier heads via curl against `http://127.0.0.1:8765` — Sessions, Conversations, Decisions, Planning Items, Work Tickets, Workstreams.
4. Parent workstream: **WS-013**.
5. API health check (`GET /health`).
6. `git pull --ff-only origin main`.

---

## Why (the requirement)

REQ-002 requires that **every first-class object type** — each governance and methodology entity that has a browsable desktop UI panel — persist a created datetime and a last-edited datetime *and surface both in the UI*. PI-107 proved the pattern on one panel (Planning Items). This work item makes it universal.

**Scope (SES-120 decisions):**
- **First-class UI entities only.** Subsidiary catalog reference tables (synonyms, presence rows), internal edge tables (`references`), and log tables (`change_log`) are out of scope — they have no panel.
- **Immutable types show created + em-dash for edited.** `deposit_event`, `reference`, `topic`, `charter`, `status`, `reference_book_version` are created-only by design. Display their created timestamp and render last-edited as `—`. Do **not** add an `updated_at` column to these tables.

## Starting state (audit at SES-120)

- **Storage is ~95% done.** All 24 first-class governance + methodology entities carry `created_at`; 23 carry `updated_at` (the created-only set above is intentional). Timestamps are application-set via `_utcnow` (`default`/`onupdate`) in `crmbuilder-v2/src/crmbuilder_v2/access/models.py`. **No migration is expected for in-scope first-class types** — confirm during the work; only add a column if a browsable type genuinely lacks one.
- **UI is the gap.** Only `PlanningItemsPanel` displays formatted Created / Last Updated (PI-107). A few panels (Sessions, Workstreams, Conversations) show a *raw, unformatted* ISO `updated_at` and no Created. Everything else shows nothing.

## The reusable pattern (from PI-107, commit `f690bde`)

The helper already exists — **reuse it, do not re-create:**
`crmbuilder-v2/src/crmbuilder_v2/ui/widgets/datetime_format.py` → `format_timestamp(value)` renders an ISO string / datetime as `YYYY-MM-DD HH:MM` in local time, em dash for missing/unparseable, naive-assumed-UTC.

Per panel:
1. Add a synthetic display field in `fetch_records()` — `record["created_at_display"] = format_timestamp(record.get("<prefix>_created_at"))` (note prefixed column names on methodology/governance entities, e.g. `domain_created_at`).
2. Add a `ColumnSpec(field="created_at_display", title="Created", width=140)` to the list columns.
3. Add `Created` and `Last Updated` dim rows in `render_detail()` via the helper.
4. For immutable types, the Last Updated row renders `—` automatically (no `updated_at` value → helper returns em dash).

## Work tasks (suggested batches — split into separate WTs/commits if preferred)

- **Task 1 — Governance panels showing raw ISO `updated_at`:** replace raw with `format_timestamp` and add a Created column — Sessions, Workstreams, Conversations. (Also Commit panel: surface governance `commit_created_at` / `commit_updated_at`, keeping the git `commit_committed_at` distinct.)
- **Task 2 — Governance panels showing nothing:** Decision, Risk, Topic (created-only), ReferenceBook, WorkTicket, CloseOutPayload, DepositEvent (created-only), Charter & Status (singleton detail views only).
- **Task 3 — Methodology panels (none show timestamps):** Domain, Entity, Field, Requirement, Persona, Process, ManualConfig, TestSpec, CrmCandidate, Engagement.
- **Task 4 — Storage gap sweep:** confirm every in-scope browsable type has `created_at` (and `updated_at` unless immutable). Add an Alembic migration only if a gap is found. Audit at SES-120 expects none.
- **Task 5 — Tests:** per-panel coverage mirroring `tests/crmbuilder_v2/ui/test_planning_items_timestamps.py` (Created column present + formatted not raw ISO; detail rows present; immutable types render em dash). Keep the full UI suite green; ruff clean.

## Open questions for the implementing session

- Should the **list** Created column appear on every panel, or only the detail view on lower-traffic entities (to avoid column clutter)? PI-107 added both; default to both unless a panel is already column-dense.
- Singleton panels (Charter, Status) have no list — detail-only surfacing.
- Confirm whether the Commit panel should show two distinct timestamps (git commit time vs. governance record time) or just one.

## Deliverable shape

One or more commits replicating the PI-107 pattern across the in-scope panels, per-panel tests, the full UI suite green, and a close-out that **resolves PI-108** (final delivering session) — intermediate slices `addresses` PI-108. Belongs to WS-013.
