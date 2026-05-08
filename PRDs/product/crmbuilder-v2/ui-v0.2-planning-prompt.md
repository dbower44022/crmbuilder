# v2 UI v0.2 — Planning Kickoff Prompt

**Last Updated:** 05-09-26 14:00
**Purpose:** Seed prompt for a new Claude.ai conversation that plans v0.2 of the v2 desktop UI.
**Predecessor:** v0.1 shipped 05-09-26 via the eight-prompt v2-ui series (slices A through H).

---

## The task

Plan v0.2 of the v2 desktop UI for the CRM Builder project. Drive a structured architectural discussion that produces three deliverables:

1. **`PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md`** — intent, scope, acceptance criteria, error handling matrix, open questions. Same length and shape as `ui-PRD-v0.1.md`.
2. **`PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md`** — slice breakdown with deliverables and acceptance gates per slice. Same shape as `ui-implementation-plan.md`.
3. **Execution prompts** under `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.2-{A..*}-*.md` — one per implementation slice. Structure matches the v0.1 prompts: purpose, project context, pre-flight, reading order, steps, acceptance gates, out of slice, constraints, reporting.

Cadence matches v0.1: structured architectural discussion, one decision at a time, building toward the PRD first, then the implementation plan, then the execution prompts. The conversation that produces these deliverables is the v0.2 planning session and will be captured as SES-006 at the conversation's close.

---

## Context — what's shipped

**v2 storage system** (SES-003): SQLite + Alembic + access layer + REST API at `http://127.0.0.1:8765` + MCP server. Eight entity types: charter, status, decision, session, risk, planning_item, topic, reference. Decisions are soft-delete; PATCH `supersedes=""` clears the FK; both fixes shipped in v0.1 slice H.

**v2 UI v0.1** (SES-004 planning + SES-005 build): standalone PySide6 desktop application, console script `crmbuilder-v2-ui`. Auto-launches the storage API as a subprocess and shuts it down on close. Sidebar navigation with eight entity panels. Master/detail layout with cross-entity reference links. SHA-256 content-hash-gated file-watch refresh. Soft-delete preserving referential integrity. Full create/read/update/delete for decisions; all other entities are read-only. About dialog. Tiny styling stub (navy `#1F3864`, Arial). 264 v2 tests passing.

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md` — full PRD for what was built.
3. `PRDs/product/crmbuilder-v2/ui-implementation-plan.md` — slice breakdown for how v0.1 was built.
4. The eight execution prompts under `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-A-*.md` through `H-*.md` — for the prompt structure and cadence to match.
5. `PRDs/product/crmbuilder-v2/db-export/sessions.json` — read SES-005 (v0.1 build), specifically the `in_flight_at_end` field which is the canonical v0.2 candidate backlog.
6. `PRDs/product/crmbuilder-v2/db-export/decisions.json` — read DEC-018 through DEC-025 for architectural choices made during v0.1 that v0.2 honors or revisits. DEC-025 specifically establishes the convention for `conversation_reference` and seed-prompt-in-`topics_covered` that applies to SES-006.
7. `PRDs/product/crmbuilder-v2/db-export/status.json` — current state, phase `"v0.1 complete"`. The baseline this work updates to a new phase at v0.2 close.

---

## Candidate scope

From SES-005 `in_flight_at_end`:

- **Write surfaces for non-decision entities.** Sessions are append-only per DEC-013 / DEC-014 and CRUD doesn't apply. Risks, planning items, and topics have natural CRUD shapes that mirror decisions. The dialog pattern from v0.1 slice G generalizes; whether to extract a shared base class or keep per-entity duplicates is a v0.2 design call.
- **Reference rendering on non-Decisions detail panes.** Slice D's rich treatment of inbound references on the decisions detail pane should generalize to Sessions, Risks, Charter, Status, Topics, Planning Items, and References themselves.
- **Charter / Status replace flows with version-history browsing.** v0.1 surfaces only the current version per slice E; v0.2 should let users browse prior versions and replace the current via a dedicated flow.
- **Calendar widget for Decision Date input.** Replaces the plain-text MM-DD-YY input from slice G with a Qt calendar selector. Reduces format errors.
- **QTreeView for Topics.** Replaces the indented-flat QTableView from slice E with a proper hierarchical tree. Better for deep hierarchies.
- **Full styling design pass.** DEC-024 deferred this from v0.1; v0.2 is the natural fit. Establish a coherent visual language: typography hierarchy, accent colors beyond the navy stub, error/warning/info states, button hierarchy, dialog framing.

Open items surfaced during v0.1 build that may merit inclusion:

- **"Show deleted" toggle on Decisions panel.** Slice H deferred this — soft-deleted decisions are hidden with no UI affordance to show them.
- **Worker-wrap synchronous `get_decision` in the Edit-click handler.** Slice G accepted a synchronous client call on the UI thread for the Edit-button refresh; if it becomes laggy in practice, wrap it.

Other candidates not in the captured backlog but worth considering during planning:

- **Search across entities** (global search box).
- **Keyboard shortcuts** for common operations.
- **Export visible panel to CSV/JSON.**
- **Bulk operations** (multi-select delete, etc.).

The planning conversation scopes a coherent subset of these, not all of them.

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

Per DEC-025, when SES-006 is created at the close of the planning conversation:

- `conversation_reference`: descriptive text identifying the conversation by its deliverables. Example template: `"Claude.ai planning conversation that produced ui-PRD-v0.2.md, ui-v0.2-implementation-plan.md, and the CLAUDE-CODE-PROMPT-v2-ui-v0.2 series under PRDs/product/crmbuilder-v2/. No transcript preserved per DEC-025."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of the architectural questions discussed.
- `artifacts_produced`: list of deliverables (PRD, plan, prompts).
- `in_flight_at_end`: anything explicitly deferred to v0.3 or later.

A subsequent session record (SES-007 or whatever's next) captures the v0.2 build itself, once execution begins.

---

## Pre-flight checks for the planning conversation

Before the first architectural question is discussed:

1. Confirm the repo is private (per the discussion that produced DEC-025).
2. Confirm the storage API and v2 test suite are healthy: `uv run pytest tests/crmbuilder_v2/ -v` should show 264 passing.
3. Read items 1 through 7 in the "Read this first" section above.
4. Pull latest: `git pull --rebase origin main`.

---

## What this conversation does NOT do

- Build any code. The build happens later, via Claude Code execution of the prompts produced here.
- Modify the storage system. Storage is settled at v0.1; UI v0.2 plans on top of it.
- Plan beyond v0.2. v0.3 candidates are noted as deferred but not designed.

---

End of kickoff prompt.
