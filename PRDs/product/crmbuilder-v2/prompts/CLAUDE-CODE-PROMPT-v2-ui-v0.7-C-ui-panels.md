# Claude Code Prompt — v0.7 Slice C: Desktop UI panels

**Last Updated:** 05-22-26 17:30
**Release:** v0.7 (governance entity release)
**Slice:** C — desktop UI panels, sidebar integration, CRUD dialogs
**Predecessor slice:** Slice B (REST API endpoints) — must have shipped
**Successor slice:** Slice D (apply script modifications)
**PRD:** `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md`
**Implementation plan section:** §2.3

---

## Task

Implement the desktop UI panels for the six new governance entity types. Master/detail layout per per-entity specs' §3.6. Six new sidebar entries appended to the existing Governance group in workstream order. Deposit_event panel is read-only audit log (no Create/Edit/Delete dialogs).

## Read this first

1. `crmbuilder/CLAUDE.md`.
2. `PRDs/product/crmbuilder-v2/governance-entity-PRD-v0.1.md` §3.4 (Desktop UI), §4 (sidebar grouping per DEC-163).
3. `PRDs/product/crmbuilder-v2/governance-entity-implementation-plan.md` §2.3 (this slice's deliverables).
4. The six schema specs' §3.6 sections for sidebar position, master pane columns and filters, detail pane field order, dialog patterns, deviations. Special attention: reference_book inline version-history section (§3.6.3); deposit_event read-only audit log with reduced context menu (§3.6.2, §3.6.4).
5. `crmbuilder-v2/src/crmbuilder_v2/ui/panels/domains_panel.py` and `decisions_panel.py` — panel precedents.
6. `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` — base class.
7. `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/entity_crud_dialog.py` — dialog base.
8. `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py` — references-section widget (DEC-031, DEC-033).

## Deliverables

Per implementation plan §2.3:

1. **Panel modules** at `crmbuilder-v2/src/crmbuilder_v2/ui/panels/`:
   - `workstreams_panel.py`, `conversations_panel.py`, `reference_books_panel.py`, `work_tickets_panel.py`, `close_out_payloads_panel.py`, `deposit_events_panel.py`.
   - Each extends `ListDetailPanel` per the v0.4 governance-entity pattern.
   - Reference_book panel renders inline version-history section in detail pane.
   - Deposit_event panel sorts identifier descending; reduced context menu; no Create/Edit/Delete dialogs.

2. **Dialog modules** at `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/`:
   - `workstream_dialog.py`, `conversation_dialog.py`, `reference_book_dialog.py`, `work_ticket_dialog.py`, `close_out_payload_dialog.py`.
   - Each extends `EntityCrudDialog` per the v0.3 governance-entity dialog pattern.
   - Field order per each spec §3.6.4–3.6.6.
   - Status combo restricts to valid transitions plus current value.
   - Reference_book dialog includes inline version-history section.
   - No `deposit_event_dialog.py` (read-only audit log).

3. **Sidebar integration:**
   - Six new entries appended to the existing Governance group in workstream order: Workstreams, Conversations, Reference Books, Work Tickets, Close-Out Payloads, Deposit Events.
   - Icons per the existing icon convention; choose from the existing Lucide-style icon set in `crmbuilder-v2/src/crmbuilder_v2/ui/assets/icons/`. Suggestions: a workflow-arrow icon for Workstreams, a speech-bubble for Conversations, a book for Reference Books, a sticky-note for Work Tickets, an envelope for Close-Out Payloads, a checkmark-list for Deposit Events.

4. **References-section integration:**
   - Shared `ReferencesSection` widget bound on each detail pane.
   - Cascading `ReferenceCreateDialog` (per DEC-033) automatically admits the new relationship kinds via `_kinds_for_pair` — no dialog change needed.
   - Deposit_event panel's references-section disables the Add Reference affordance.

5. **UI tests** at `tests/crmbuilder_v2/ui/panels/` per slice §2.3 acceptance.

## Working style

- Match the v0.4 governance-entity panel precedents (domains, entities, processes, crm_candidates).
- One commit per panel + dialog pair.
- Run UI tests after each commit; full suite before merge.

## Pre-flight

```
curl -sf http://127.0.0.1:8765/health
uv run pytest tests/crmbuilder_v2/ -v
git pull --rebase origin main
```

## Acceptance gate

Per implementation plan §2.3:

- Six sidebar entries appear in Governance group in workstream order.
- Each panel master pane lists records with correct columns, sort, context menu.
- Deposit_event panel master pane sorts identifier descending; context menu has Copy Identifier and Copy Log Path only.
- Each detail pane renders all fields including references-section.
- Reference_book detail pane renders inline version-history section with Add Version affordance.
- Create/Edit/Delete dialogs work end-to-end for the five entities that have them.
- Cascading reference-create dialog admits new relationship kinds for matching pairs.
- File-watch refresh picks up external changes.
- `uv run pytest tests/crmbuilder_v2/ui/` green.

## Out of scope

- Apply script modifications — Slice D.
- Backfill — Slice E.
- Documentation, version bump — Slice F.
