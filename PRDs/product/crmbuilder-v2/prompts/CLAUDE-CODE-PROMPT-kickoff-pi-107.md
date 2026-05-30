# Kickoff — PI-107: Surface planning_item timestamps in the UI

> **Retroactive backfill (2026-05-30).** PI-107 was picked up ad hoc in
> conversation and implemented directly from its planning-item description,
> without a kickoff work ticket. This document is a backfilled kickoff record so
> the work has the standard `planning_item` → `work_ticket` (kickoff_prompt) →
> session trail. Authored *after* the work shipped (commit `f690bde`, resolved
> by SES-118 / CNV-020). Work ticket: **WT-059**, `addresses` PI-107.

## Planning item

**PI-107 — Surface planning_item created/updated timestamps in the Planning
Items UI panel.**

The `planning_items` table already carries `created_at` / `updated_at` columns
(default/onupdate `_utcnow`) and the REST API already returns both — the only
gap is the desktop UI not displaying them. UI-only task; no schema migration,
no API change.

## Goal

Show each planning item's creation and last-edited datetime in the V2 desktop
Planning Items panel.

## Scope delivered

1. Reusable `ui/widgets/datetime_format.py` `format_timestamp()` helper —
   ISO/`datetime` → local `YYYY-MM-DD HH:MM`, em dash for missing/unparseable,
   naive-assumed-UTC.
2. `PlanningItemsPanel`: a formatted "Created" list column (via a synthetic
   display field) plus Created / Last Updated dim rows in the detail form.

## Acceptance

- Opening a planning item shows its created and last-updated datetimes matching
  the API; no schema migration introduced; full UI test suite green.

## Resolution

Implemented in commit `f690bde`; resolved by **SES-118 / CNV-020** (close-out
`ses_118.json`).
