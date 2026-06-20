# PI-214 — Blast-Radius-Sized Reopen Approval: Architecture

**Wave 3 of the multi-agent release pipeline build** (build plan §19; `blocked_by`
PI-212, merged). Architecture-phase deliverable for **PI-214** — "Blast-radius-sized
reopen approval." Project **PRJ-034**. Branched off `main` (Waves 0–2 merged),
stacked on `pi-wave3` (after PI-213).

Governing design: `multi-agent-release-pipeline-architecture.md` §14.4 / §16.8
(DEC-494…498, REQ-230…234 / RA-1…5) — already designed; this PI translates it onto
PI-212's `area_reopens` + PI-213's cascade.

## 1. Blast radius (RA-1)

Deterministic: the blast radius of reopening area X = `downstream_areas(X)` (the
PI-212/213 cascade — the strictly-higher-rank spine areas). No estimate.

## 2. Tiers (RA-3) — `reopen_tier(release, area)`

`tier = max(breadth-implied, depth-implied)` then a repeat-escalation:

- **breadth** (count of downstream areas): 0 → `lead_auto`; 1–2 → `lead`; 3+ → `pm`.
- **depth** override: the foundational area (lowest rank — `storage`) → `human`.
- **repeat** (RA-4): a second-or-later reopen of the same area in the release
  escalates the computed tier by one (capped at `human`).

`REOPEN_APPROVAL_TIERS = {lead_auto, lead, pm, human}`. Thresholds are module
defaults with a clear seam; per-engagement override is a thin follow-on.

## 3. Approval gate (RA-2)

`reopen_area` now requires a **recorded approval decision** for any tier above
`lead_auto`; `lead_auto` (empty radius) is Lead-self-authorized, no decision. The
tier, the approving `DEC-`, and the triggering `FND-` are recorded on the
`area_reopens` row. (Authority — that the `DEC-` was made by a Lead/PM/Human — is
RBAC's concern, off by default; PI-214 records the tier + approval, hard-enforced
when RBAC is on.)

## 4. Impact report (RA-5)

`reopen_impact(release, area)` → `{reopen_point, downstream_areas, count, tier,
is_repeat}` — surfaced before the decision so the approver sees the cost. A reopen
references its triggering finding (`FND-`) when supplied.

## 5. Schema / migration

`area_reopens` gains `approval_tier`, `approval_decision_identifier` (nullable —
null for `lead_auto`), `triggering_finding_identifier` (nullable). SQLite `0071` +
PG `0028` (guarded add-column). Vocab `REOPEN_APPROVAL_TIERS`.

## 6. API

- `GET /releases/{id}/reopen-impact?area=` → the impact report (preview).
- `POST /releases/{id}/area-reopens` gains `approval_decision_identifier?`,
  `triggering_finding_identifier?` (beside `area`, `reason`).

## 7. Tests

- `reopen_tier`: empty → lead_auto; shallow (api → 2) → lead; moderate (access →
  3) → pm; foundational (storage) → human; repeat escalates one tier.
- gate: a tier>lead_auto reopen without an approval decision is rejected; with one
  it proceeds and records tier+decision; a lead_auto reopen needs no decision.
- impact report shape; SQLite + PG.

## 8. Requirement traceability

| REQ | Where |
|---|---|
| RA-1 / REQ-230 blast radius computed deterministically | §1 (`downstream_areas`) |
| RA-2 / REQ-231 reopen gated by an approval decision at the tier | §3 |
| RA-3 / REQ-232 tiers keyed on radius + depth override | §2 (`max(breadth, depth)`) |
| RA-4 / REQ-233 configurable thresholds; repeat escalates one tier | §2 (defaults + repeat) |
| RA-5 / REQ-234 structured request + finding + impact report | §4 |
