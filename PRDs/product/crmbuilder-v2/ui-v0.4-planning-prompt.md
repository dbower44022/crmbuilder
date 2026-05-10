# v2 UI v0.4 — Planning Kickoff Prompt

**Last Updated:** 05-10-26 00:30
**Purpose:** Seed prompt for a new Claude.ai conversation that plans v0.4 of the v2 desktop UI.
**Predecessor:** v0.3 shipped 05-09-26 via the five-prompt v2-ui-v0.3 series (slices A through E).
**Goal posture:** Deliberately open. v0.4's frame is the first architectural question of the planning conversation. PI-001 (the styling pass deferred three times — DEC-024, DEC-026, DEC-037) is a forcing function: v0.4 must engage it explicitly. How v0.4 engages — primary frame, secondary work alongside another frame, or fourth deferral with new tracking mechanism — is what the planning conversation decides.

---

## The task

Plan v0.4 of the v2 desktop UI for the CRM Builder project. Drive a structured architectural discussion that produces three deliverables:

1. **`PRDs/product/crmbuilder-v2/ui-PRD-v0.4.md`** — intent, scope, acceptance criteria, error handling matrix, open questions. Same shape as `ui-PRD-v0.1.md`, `ui-PRD-v0.2.md`, and `ui-PRD-v0.3.md`.
2. **`PRDs/product/crmbuilder-v2/ui-v0.4-implementation-plan.md`** — slice breakdown with deliverables and acceptance gates per slice.
3. **Execution prompts** under `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-{A..*}-*.md` — one per implementation slice, structure matching the v0.1, v0.2, and v0.3 prompts.

Cadence matches v0.1 / v0.2 / v0.3: structured architectural discussion driven one decision at a time, building toward the PRD first, then the implementation plan, then the execution prompts. The conversation that produces these deliverables is the v0.4 planning session and will be captured as the next available SES-NNN at the conversation's close.

---

## Context — what's shipped

**v2 storage system** (SES-003 + later additions): SQLite + Alembic + access layer + REST API at `http://127.0.0.1:8765` + MCP server. Eight entity types: charter, status, decision, session, risk, planning_item, topic, reference. Soft-delete and FK-empty-string-clear semantics on decisions and topics.

**v2 UI v0.1** (SES-004 planning + SES-005 build, 264 tests at ship): standalone PySide6 desktop application, console script `crmbuilder-v2-ui`. Sidebar navigation across eight entity panels. Master/detail layout with cross-entity reference links. SHA-256 content-hash-gated file-watch refresh. Lifecycle-managed API subprocess. Full CRUD for Decisions only.

**v2 UI v0.2** (SES-006 planning + SES-007 build, 458 tests at ship): foundation refactor extracting `EntityCrudDialog` / `EntityCrudDeleteDialog` base classes plus the `widgets/` subpackage (`DateField`, `ReferencesSection`, `HierarchicalEntityPicker`); CRUD for Risks, Planning Items, and Topics; versioned replace + history with `VersionedReplaceDialog` and Make Current for Charter and Status; reference rendering on every detail pane; QTreeView master panel for Topics; Show-deleted toggle and Restore on Decisions; About 0.2.0; topic `parent_topic` empty-string clearing fix.

**v2 UI v0.3** (SES-008 planning + SES-009 build, ~613 tests at ship): `ListDetailPanel` master-widget and context-menu factory refactor with Topics migration; right-click context menus uniform across every entity row; full References write surface with `EntityIdentifierPicker` widget, source-first cascading `ReferenceCreateDialog` (cascading-filter framework via extended `FieldSchema.depends_on`/`compute_options` + new `identifier_picker` widget kind), `ReferenceDeleteDialog` with edge-text confirmation, panel toolbar `New Reference` button, detail-pane `Add reference` affordance with right-click delete, `RELATIONSHIP_RULES` tuple-keyed dict driving strict vocab compliance via seven semantic rules; Sessions create-only dialog with auto-assigned identifier and DEC-025-aware placeholders; `EntityCrudDialog` framework extensions (`FieldSchema.read_only`, placeholder support on text widgets, default support on line widgets in create mode); naming alignment Option B variant (`relationship` canonical in API/UI, `relationship_kind` in DB, single translation point at `_row_dict`); About 0.3.0.

**Cumulative through v0.3:** 37 decisions DEC-001 through DEC-037; 9+ sessions through SES-009 (plus any production-use conversations Doug records between v0.3 close and v0.4 planning); 1 planning item PI-001 (styling pass deferred); status v1.0 phase `"v0.3 complete"`.

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md`, `ui-PRD-v0.2.md`, and `ui-PRD-v0.3.md` — full PRDs for what was built.
3. `PRDs/product/crmbuilder-v2/ui-implementation-plan.md`, `ui-v0.2-implementation-plan.md`, and `ui-v0.3-implementation-plan.md` — slice breakdowns.
4. The nineteen execution prompts under `PRDs/product/crmbuilder-v2/prompts/` — for the prompt structure and cadence to match (eight v0.1 + six v0.2 + five v0.3).
5. `PRDs/product/crmbuilder-v2/db-export/sessions.json` — read SES-008 (v0.3 planning, especially the `topics_covered` summary of v0.3's nine architectural questions) and SES-009 (v0.3 build, especially `in_flight_at_end` which is the canonical v0.4 candidate backlog). Read any sessions written between SES-009 and now — those are production-use friction points.
6. `PRDs/product/crmbuilder-v2/db-export/decisions.json` — read DEC-032 through DEC-037 (v0.3's six). DEC-024 / DEC-026 / DEC-037 are the three styling deferrals; DEC-013 / DEC-014 / DEC-025 / DEC-034 govern session conventions.
7. `PRDs/product/crmbuilder-v2/db-export/planning_items.json` — read PI-001. This is the forcing function for v0.4.
8. `PRDs/product/crmbuilder-v2/db-export/status.json` — current state.

---

## Candidate scope

The candidates fall into four buckets. The planning conversation's first architectural question is which buckets to combine into v0.4's coherent frame.

### Bucket A — Liability discharge (forcing function)

- **PI-001: full styling design pass per DEC-024.** Three deferrals — DEC-024 (v0.1 → v0.2), DEC-026 (v0.2 → v0.3), DEC-037 (v0.3 → "future styling release"). PI-001 was created at v0.3 planning specifically so the third deferral did not silently drift to a fourth. v0.4's planning conversation MUST engage PI-001 — either by adopting it as the primary frame, including partial styling that addresses real-use pain points, or making a fourth deferral explicit with a new tracking mechanism and rationale. A silent rollover is not acceptable.

### Bucket B — Polish from v0.3 deferrals

From SES-009's `in_flight_at_end` (the canonical v0.4 candidate backlog):

- Reference filtering by relationship type on detail-pane `ReferencesSection`. Only earns its place if real-use friction surfaces it — reference volume on individual entities being high enough that the unfiltered list is hard to read.
- JSON diff view for Charter/Status `VersionedReplaceDialog`. Only earns its place if real-use friction surfaces it — replace-without-comparison having caused real bugs or near-misses.
- Global search across entities. Cross-cutting affordance; useful as the entity counts grow.
- Keyboard shortcuts beyond Qt defaults. Power-user QoL.
- Export visible panel to CSV / JSON. Cross-cutting affordance.
- Bulk operations (multi-row select + delete on Decisions / Risks / Planning Items / Topics, multi-row update). Cross-cutting affordance.

### Bucket C — Forward expansion

- **Methodology entity schema design.** Personas, processes, fields, requirements, manual-config items, test specs — all need their own v2 entity types before v2 can host the methodology work currently living in markdown PRDs. This is a separate planning conversation in its own right (designing six new entity schemas is non-trivial). v0.4 may take it on as its primary frame OR explicitly defer it to a dedicated methodology-schema-design conversation that runs in parallel with or after v0.4. The planning conversation decides.
- **First methodology entity panel** (gated on schema design). Likely v0.5 if schema design lands in v0.4.

### Bucket D — Reimplementation workstream

- Saved views / duplicate-check rules / workflow managers. Currently no public REST API write path exists for these in EspoCRM. If that constraint is resolved, reimplementation lands in a future release. Not actionable in v0.4 unless the constraint changes.

### Production-use friction (highest weight, populated dynamically)

Anything Doug discovers from using v0.3 for real governance work between v0.3 close and v0.4 planning. Read recent session records (post-SES-009) for friction points — those are the highest-priority candidates because they reflect actual use rather than speculation.

Known friction inputs at kickoff time:

- **SES-010 — identifier auto-assignment asymmetry between dialog and direct-API consumers.** The desktop dialog's `compute_next_session_identifier` hides identifier computation from end users, but `POST /sessions` (and `POST /decisions`, `POST /planning_items`, etc.) requires the identifier in the body — direct-API consumers (curl, MCP, scripts) hit `request_validation_error: body.identifier — Field required` if they don't compute and supply it. v0.4 may engage one of three resolutions: (A) document the pattern only — already done in `crmbuilder/CLAUDE.md` post-SES-010; (B) add `GET /<entity>/next-identifier` helper endpoints for each prefixed-identifier entity type; (C) make `identifier` optional in POST bodies and have the API auto-assign when omitted (changes API semantics; affects all prefixed-identifier entities consistently). Decision is v0.4's to make.

---

## On timing

Some v0.4 candidates only earn their place once real-use data exists. If this planning conversation runs immediately after v0.3 ships (no production use yet), the planning conversation must make its scope decisions on incomplete information — which is acceptable but suboptimal. Consider running v0.4 planning after some weeks of v0.3 production use so production-use friction is part of the input. This is advisory, not blocking — the kickoff is ready whenever Doug is ready.

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

Per DEC-013, one Claude.ai conversation produces one session record. The v0.4 planning session record is written **at the actual close of this Claude.ai conversation, not in slice A of the build**. v0.3's planning conversation deviated from this pattern — SES-008 was written in slice A's planning records, which captured only the v0.3 planning portion of the conversation; subsequent work in the same chat (slice review, prompt amendments, v0.5 kickoff prep) was uncovered by SES-008 and required a supplemental record. v0.4 closes this gap.

**Session-record-at-close pattern:**

- **Slice A of the v0.4 build writes only** the decisions (DEC-NNN through DEC-MMM), the references from the planning session record to those decisions, the planning item(s) for any deferred work, and the status update. **Slice A does NOT write the session record** — the references it writes use the planning session's identifier (e.g., `source_id: "SES-NNN"`) but the session record itself is created later.
- **The session record is written at the close of THIS Claude.ai planning conversation**, by Doug, through the v0.3 desktop application's `New Session` dialog. The conversation's last action is dialog open → fields filled → Save. This is the production dogfood for v0.3, continuing the SES-009 pattern.
- **A subsequent session record captures the v0.4 build itself** at slice E close, also through the dialog.

**Per DEC-025, when the v0.4 planning session record is created:**

- `identifier`: the next available SES-NNN at conversation close. The dialog auto-assigns by querying `client.list_sessions()` and incrementing.
- `conversation_reference`: descriptive text identifying the conversation by deliverables. Example template: `"Claude.ai planning conversation that produced ui-PRD-v0.4.md, ui-v0.4-implementation-plan.md, and the CLAUDE-CODE-PROMPT-v2-ui-v0.4 series under PRDs/product/crmbuilder-v2/. No transcript preserved per DEC-025."`
- `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement at the top of this document>"`, followed by a structured summary of the architectural questions discussed and decisions made.
- `artifacts_produced`: list of deliverables (PRD, plan, prompts).
- `in_flight_at_end`: anything explicitly deferred to v0.5 or later.

If PI-001 is fully discharged in v0.4, mark its status accordingly and note the discharge in the v0.4 planning session record. If PI-001 is partially addressed or deferred again, document the rationale and (if deferred) the new tracking mechanism.

**The session record is the conversation's last action.** If post-record work happens in the same chat (e.g., review of subsequent slice reports, amendments to slice prompts, kickoff prep for v0.5), those are governance-uncovered and should either be done in a separate Claude.ai conversation (which produces its own session record) or captured in a supplemental record at THIS conversation's actual end. Prefer separate conversations for clarity.

---

## Pre-flight checks for the planning conversation

Before the first architectural question is discussed:

1. Confirm the storage API is healthy: verify-first via `curl -sf http://127.0.0.1:8765/health`; start the API in the background only if the check fails.
2. Confirm the v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v` should show ~613 passing (608 from slice D + ~5 from slice E polish).
3. Read items 1 through 8 in the "Read this first" section above.
4. Pull latest: `git pull --rebase origin main`.

---

## What this conversation does NOT do

- Build any code. The build happens later, via Claude Code execution of the prompts produced here.
- Modify the storage system architecture beyond additive endpoints required by new write surfaces. v0.4 does not revisit DEC-013/DEC-014 (sessions append-only), DEC-018/DEC-019 (UI consumes REST API), DEC-022 (file-watch refresh), or otherwise alter v0.3's storage shape.
- Plan beyond v0.4. v0.5 candidates are noted as deferred but not designed.
- Add new fundamental v2 entity types. The eight entity types are settled. Methodology entities (personas, processes, fields, requirements, manual-config items, test specs) are a separate schema design conversation; v0.4 may scope or defer that conversation but does not execute it inline.

---

## Why the frame is open

v0.3's frame was clear because the gap between "viewer over v2" and "operational tool for v2" was specific and load-bearing. v0.4 has no analogous single-frame forcing function. PI-001 is the closest, but discharging the styling pass alone may not be enough work to fill a release on its own — depending on how the planning conversation scopes it. The planning conversation has to decide:

- Is v0.4 primarily a styling release with secondary polish?
- Is v0.4 primarily a polish release that includes partial styling work?
- Is v0.4 primarily a methodology-schema-design release with PI-001 deferred again (with explicit new tracking)?
- Is v0.4 some hybrid?

Production-use friction (if available by the time this conversation runs) is the strongest signal. The scope decision should be guided by what real use of v0.3 reveals, not by what looked appealing during v0.3 planning.

---

End of kickoff prompt.
