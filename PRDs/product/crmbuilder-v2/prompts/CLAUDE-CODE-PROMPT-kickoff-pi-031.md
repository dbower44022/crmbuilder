# Kickoff — PI-031: Commits panel + planning_item resolution chain in the V2 UI

> **Retroactive backfill (2026-05-30).** PI-031 was picked up ad hoc in
> conversation and implemented directly from its planning-item description,
> without a kickoff work ticket. This document is a backfilled kickoff record so
> the work has the standard `planning_item` → `work_ticket` (kickoff_prompt) →
> session trail. Authored *after* the work shipped (commit `f5381966`, resolved
> by SES-120 / CNV-022). Work ticket: **WT-060**, `addresses` PI-031.

## Planning item

**PI-031 — Implement commits panel and planning_item resolution display in the
V2 desktop UI.**

A read-only Commits panel under the Governance sidebar group, plus a
resolution-chain affordance on resolved planning items. The PI's description
predates the PI-073 session-grain redesign; the implementation reconciles it to
the current schema (recorded in **DEC-332**).

## Goal

Give operators a browse surface for commits and a clickable trace from a
resolved planning item back to its delivering commits.

## Scope delivered

1. **Commits panel** (read-only master/detail): Repository/Session filters,
   four-case by-SHA lookup, producing-session rendered as the prominent
   identity link, no write affordance (commits ingested via close-out).
2. **Resolution chain** on `PlanningItemsPanel`: traces PI ←resolves←
   conversation → deposit_event → session → commits, each node clickable, with
   a "Resolved without a governance trace (see PI-033)" degraded state.
3. Supporting client commit accessors; `ReferencesSection.set_add_enabled`;
   sidebar/nav registration.

## Acceptance

- Commits panel renders with the named columns/filters/by-SHA cases; resolved
  items show the chain; full UI suite green.

## Resolution

Implemented in commit `f5381966` (schema reconciliation in DEC-332); resolved by
**SES-120 / CNV-022** (close-out `ses_120.json`).
