# Kickoff — PI-101: Harden the close-out pre-flight validator

> **Retroactive backfill (2026-05-30).** PI-101 was picked up ad hoc in
> conversation and implemented directly from its planning-item description,
> without a kickoff work ticket authored at session open. This document is a
> backfilled kickoff record so the work has the standard `planning_item` →
> `work_ticket` (kickoff_prompt) → session trail. It is authored *after* the
> work shipped (commit `947da63`, resolved by SES-122 / CNV-024). Work ticket:
> **WT-058**, `addresses` PI-101.

## Planning item

**PI-101 — Harden the close-out pre-flight validator to reject missing required
fields and wrong-case status values.**

The PI-090 close-out validator (`crmbuilder-v2/scripts/closeout_validator.py`)
let all three SES-110 apply defects through as warnings only: two missing
required fields (`executive_summary`, now NOT NULL on decisions/planning_items/
sessions since PI-075) and one wrong-case status value (`work_ticket_status`
"Ready" vs the lowercase enum "ready"). Those are exactly the class of error the
validator exists to prevent; each one cost a recent close-out an extra manual
apply pass.

## Goal

Extend the validator so pre-flight **rejects**:

- (a) any record missing a required field, including `executive_summary` on
  decisions / planning_items / sessions; and
- (b) any status value not matching its (lowercase, where applicable) enum, for
  every status-bearing entity.

## Scope delivered

1. **executive_summary required** (not merely length-checked) on session,
   decision, planning_item — absent/null/empty is a hard error
   (`executive_summary_required`).
2. **check_status_values** (check 11): validate session/conversation/
   work_ticket/planning_item status against the live vocab sets imported from
   `vocab.py` (case-encoding catches the "Ready" defect).
3. **check_required_fields** (check 12): identifier/title/status presence on
   decisions and planning_items.

## Acceptance

- A payload with a missing decision `executive_summary`, `work_ticket_status`
  "Ready", a wrong-case PI status, and a missing PI title yields targeted
  pre-flight errors; a clean compliant payload yields none.
- Validator + scripts test suites green; ruff clean.

## Resolution

Implemented in commit `947da63`; resolved by **SES-122 / CNV-024** (close-out
`ses_122.json`, deposit event DEP-114).
