# v2 UI v0.3 — Planning Kickoff Prompt

**Last Updated:** 05-09-26 17:00
**Purpose:** Seed prompt for a new Claude.ai conversation that plans v0.3 of the v2 desktop UI.
**Predecessor:** v0.2 shipped 05-09-26 via the six-prompt v2-ui-v0.2 series (slices A through F).
**Goal posture:** v0.3 should pack as much value as fits in a coherent release, prioritized toward making the v2 system testable end-to-end as a real governance tool. The user wants to begin actually using v2 to drive governance work after this release.

---

## The task

Plan v0.3 of the v2 desktop UI for the CRM Builder project. Drive a structured architectural discussion that produces three deliverables:

1. **`PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md`** — intent, scope, acceptance criteria, error handling matrix, open questions. Same shape as `ui-PRD-v0.1.md` and `ui-PRD-v0.2.md`.
2. **`PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md`** — slice breakdown with deliverables and acceptance gates per slice.
3. **Execution prompts** under `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.3-{A..*}-*.md` — one per implementation slice, structure matching the v0.1 and v0.2 prompts.

Cadence matches v0.1 / v0.2: structured architectural discussion driven one decision at a time, building toward the PRD first, then the implementation plan, then the execution prompts. The conversation that produces these deliverables is the v0.3 planning session and will be captured as SES-008 at the conversation's close.

---

## Context — what's shipped

**v2 storage system** (SES-003 + later additions): SQLite + Alembic + access layer + REST API at `http://127.0.0.1:8765` + MCP server. Eight entity types: charter, status, decision, session, risk, planning_item, topic, reference. Soft-delete and FK-empty-string-clear semantics on decisions (slice H) and topics (slice F).

**v2 UI v0.1** (SES-004 planning + SES-005 build, 264 tests at ship): standalone PySide6 desktop application, console script `crmbuilder-v2-ui`. Sidebar navigation across eight entity panels. Master/detail layout with cross-entity reference links. SHA-256 content-hash-gated file-watch refresh. Lifecycle-managed API subprocess. Full CRUD for Decisions only.

**v2 UI v0.2** (SES-006 planning + SES-007 build, 458 tests at ship): foundation refactor extracting `EntityCrudDialog` / `EntityCrudDeleteDialog` base classes plus the `widgets/` subpackage (`DateField`, `ReferencesSection`, `HierarchicalEntityPicker`); CRUD for Risks, Planning Items, and Topics; versioned replace + history with `VersionedReplaceDialog` and Make Current for Charter and Status; reference rendering on every detail pane; QTreeView master panel for Topics; Show-deleted toggle and Restore on Decisions; About dialog showing 0.2.0; topic `parent_topic` empty-string clearing fix; `_select_by_identifier` promoted to base; JSON editor inline schema-error rendering on Save failure.

**Cumulative:** 31 decisions DEC-001 through DEC-031, 7 sessions SES-001 through SES-007, status v0.8 phase `"v0.2 complete"`.

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md` and `ui-PRD-v0.2.md` — full PRDs for what was built.
3. `PRDs/product/crmbuilder-v2/ui-implementation-plan.md` and `ui-v0.2-implementation-plan.md` — slice breakdowns.
4. The fourteen execution prompts under `PRDs/product/crmbuilder-v2/prompts/` — for the prompt structure and cadence to match (eight v0.1 + six v0.2).
5. `PRDs/product/crmbuilder-v2/db-export/sessions.json` — read SES-007 (v0.2 build), specifically `in_flight_at_end` which is the canonical v0.3 candidate backlog.
6. `PRDs/product/crmbuilder-v2/db-export/decisions.json` — read DEC-018 through DEC-031. DEC-024 (full styling deferred), DEC-025 (transcript capture deferred — applies to SES-008's `conversation_reference`), DEC-027 (entity scope: References deferred to v0.3) are the most relevant.
7. `PRDs/product/crmbuilder-v2/db-export/status.json` — current state, phase `"v0.2 complete"`.

---

## Candidate scope

Prioritized for the testability-first framing. The planning conversation scopes a coherent subset; lower-priority items are deferred to v0.4 or later.

### Priority 1 — Testability-blocking

These are the gaps that prevent the user from using v2 for real governance work without leaving the UI.

- **References write surface.** Currently the only way to create a reference (e.g., `decided_in` linking a decision to its session) is via direct API calls or governance scripts. The UI renders references read-only via `ReferencesSection` on every detail pane. v0.3 needs CRUD: create new references with a relationship vocabulary picker (the controlled `RELATIONSHIP_TYPES` vocab from access/vocab.py), source/target entity pickers, and edge deletion. This is the largest single piece of v0.3 — likely two or three slices.
- **Sessions create-only surface.** Sessions are append-only per DEC-013 / DEC-014 (no edit, no delete), but POST is allowed at the API. Currently the only path to create a session is via Python scripts (e.g., `apply_dec_025.py`). For real-use testing, the user needs to record sessions through the UI. Create-only dialog; no edit or delete buttons; details pane treatment unchanged. One slice.

### Priority 2 — Architecturally-overdue

These are friction items that v0.2 carried forward and that should be cleaned up before more panels accrete.

- **`ListDetailPanel` master-pane factory refactor.** Slice F deferred this from v0.2 because the override-and-alias workaround in `TopicsPanel` is functional and a clean factory refactor risks regressions across six panels. v0.3 is the right venue for the focused refactor with proper test discipline. One slice or one slice-step.
- **Any other base-class friction observed during v0.2 use.** Likely small.

### Priority 3 — Independent quality investment

- **Full styling design pass per DEC-024.** Establish a coherent visual language: typography hierarchy, accent colors beyond the navy stub, error/warning/info states, button hierarchy, dialog framing, table row spacing. This is genuine design work — could be one focused slice or could be deferred again to a dedicated styling release.

### Priority 4 — Nice-to-have if scope permits

From SES-007's `in_flight_at_end`:

- Reference filtering by relationship type if reference volume warrants it.
- Diff-with-current view for the JSON payload editor in `VersionedReplaceDialog`.
- Methodology entity panels (post-schema-design, may not apply to v0.3).
- Global search across entities.
- Keyboard shortcuts beyond Qt defaults.
- Export visible panel to CSV / JSON.
- Bulk operations (multi-select delete, etc.).

These are deferred unless they slot in cleanly.

---

## Working style

Per the user's preferences:

- Discuss one architectural decision at a time. Wait for explicit approval before moving to the next.
- Plain text discussion. Bold section headings acceptable. Avoid bullet-point overload.
- Terse approvals ("yes", "confirm", "a", "1 good") are sufficient — do not re-summarize or re-confirm.
- Once a plan or PRD is complete, execute the script without per-step confirmation.
- Propose document structures and outlines; the user approves before drafting begins.
- For repo work, use sparse checkout: `git clone --filter=blob:none --sparse https://oauth2:{PAT}@github.com/dbower44022/crmbuilder.git`, then `git sparse-checkout set --skip-checks CLAUDE.md PRDs/ crmbuilder-v2/`.
- Set git identity before first commit: `git config user.email "doug@dougbower.com"` and `git config user.name "Doug"`.
- Always `git pull --rebase origin main` before pushing.

---

## Governance — at conversation close

Per DEC-025, when SES-008 is created at the close of the planning conversation:

- `conversation_reference`: descriptive text identifying the conversation by deliverables. Example template: `"Claude.ai planning conversation that produced ui-PRD-v0.3.md, ui-v0.3-implementation-plan.md, and the CLAUDE-CODE-PROMPT-v2-ui-v0.3 series under PRDs/product/crmbuilder-v2/. No transcript preserved per DEC-025."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of the architectural questions discussed.
- `artifacts_produced`: list of deliverables (PRD, plan, prompts).
- `in_flight_at_end`: anything explicitly deferred to v0.4 or later.

A subsequent session record (SES-009) captures the v0.3 build itself once execution begins.

---

## Pre-flight checks for the planning conversation

Before the first architectural question is discussed:

1. Confirm the storage API and v2 test suite are healthy: `uv run pytest tests/crmbuilder_v2/ -v` should show 458 passing.
2. Read items 1 through 7 in the "Read this first" section above.
3. Pull latest: `git pull --rebase origin main`.

---

## What this conversation does NOT do

- Build any code. The build happens later, via Claude Code execution of the prompts produced here.
- Modify the storage system architecture beyond additive endpoints required by new write surfaces (e.g., POST/DELETE /references). v0.3 does not revisit DEC-013/DEC-014 (sessions append-only) or otherwise alter v0.2's storage shape.
- Plan beyond v0.3. v0.4 candidates are noted as deferred but not designed.
- Add new entities. The eight v2 entity types are settled.

---

## Why this is structured for testability

After v0.3 ships, the user intends to begin using v2 as a real governance tool — recording sessions, decisions, risks, planning items, topics, references — for ongoing CRM Builder work and any other workstream that benefits from structured governance. The two Priority 1 items (References write surface, Sessions create surface) are what's between the current state and "complete enough to drive real governance work without leaving the UI." Priority 2 (factory refactor) and Priority 3 (styling) make the testing experience better but aren't strictly testability-blocking. The planning conversation should scope v0.3 to the priority tiers in order, dropping Priority 3 and Priority 4 items as needed to keep the slice count manageable.

---

End of kickoff prompt.
