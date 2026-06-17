# PI-216 — Freeze Enforcement: Architecture

**Wave 1 of the multi-agent release pipeline build** (build plan §19; `blocked_by`
PI-205). Architecture-phase deliverable for **PI-216** — "Build the
freeze-enforcement mechanism." Stacked on the `pi-205-release-entity` branch (it
reads the Release status PI-205 owns).

Governing design: `multi-agent-release-pipeline-architecture.md` §9A
(DEC-488…493, REQ-224…229). Per the DEC-502 ownership boundary: **PI-205 owns the
freeze transition + `release_frozen_at` stamp + the per-release occupancy check;
PI-216 owns the enforcement of *derived* frozen-ness on other records** by reading
the release status. PI-216 stores nothing — frozen-ness is computed (FE-2).

## 1. Derived frozen-ness (FE-2)

A record is frozen by computation from its release's status + the membership
edges, never a stored flag. The release status partitions into three enforcement
bands (`access/freeze.py`):

| Band | Release statuses | Meaning |
|---|---|---|
| **open** | `preliminary_planning`, `development_planning` | pre-freeze — edits free |
| **amend_window** | `reconciliation`, `architecture_planning` | frozen, but a governed amend is allowed (`[freeze, planned-completely)`) |
| **locked** | `ready`, `development`, `qa`, `testing`, `deployment` | past planned-completely — any demand change needs a new release (RW1) |

`shipped` / `cancelled` / `superseded` are **not gated** — terminal/abandoned; a
change to a shipped requirement happens by scheduling it into a *new* release
(where it is `open` again pre-freeze).

A requirement's band is the **most restrictive** band across the releases it is
scheduled into (via `requirement ← planning_item_implements_requirement` →
`planning_item_belongs_to_project` → `project_belongs_to_release`).

## 2. The requirement-edit gate (FE-3 / FE-4)

Hooked into `requirement.update_requirement` / `patch_requirement` at the point a
**substantive** field changes (`_CONTENT_FIELDS` — name / description /
acceptance_summary):

- **open** → allow.
- **amend_window** → allow **only if** the requirement is already in
  `review_state == needs_review` (a `requirement_changed_by_decision` decision via
  `reopen_by_decision` opened the gate); otherwise reject with a pointer to the
  sanctioned amend path. This is the temperature flip: post-freeze, a demand
  change requires a governing decision (FE-3, D-40).
- **locked** → reject unconditionally — the plan is inviolable; the change is a
  new release (FE-4 / RW1).

`reopen_by_decision` itself (the gate-opener) is **not** gated — it only flips
`review_state`, touching no `_CONTENT_FIELDS`.

## 3. The scope-membership gate (FE-3 "membership closed")

Hooked into `references.create` (deferred import to avoid the cycle): adding a
membership edge whose resolved release is **frozen** (amend_window or locked) is
rejected — `project_belongs_to_release`, `planning_item_belongs_to_project`,
`planning_item_implements_requirement`. You cannot add a Project to a frozen
release, move a PI under a frozen-release Project, or attach a new requirement to
a frozen-release PI.

## 4. Read surface

`GET /releases/{id}/freeze` → `{release_identifier, status, freeze_band}` — surfaces
the classification (useful to clients and the build's own tests).

## 5. Scope boundary

PI-216 gates **requirements** (the primary demand) and the three membership
edges. **Process-record** edit-gating follows the *identical* `freeze.py` pattern
and is a thin follow-on once process-in-release scoping is exercised; noted, not
built here, to keep the slice tight. PI-216 does **not** re-implement the freeze
*transition* or occupancy (PI-205) or the reopen reverse (PRJ-034).

## 6. Tests

- band classification for each release status;
- ungoverned edit to an amend_window requirement rejected; the same edit allowed
  after `reopen_by_decision` (needs_review); edit to a locked requirement rejected
  even in needs_review; edit to an open/unscheduled requirement allowed;
- membership-add rejected against a frozen release; allowed against an open one;
- the read endpoint; SQLite + PG.

## 7. Requirement traceability

| REQ | Where |
|---|---|
| FE-1 / REQ-224 gated status, access-layer enforced, not a lock | §2/§3 (access-layer rejects) |
| FE-2 / REQ-225 derived frozen-ness | §1 (computed, no stored flag) |
| FE-3 / REQ-226 frozen release closes membership; amend decision-only | §2, §3 |
| FE-4 / REQ-227 planned-completely closes the amend path (RW1) | §2 (locked band) |
| FE-5 / REQ-228 confirmed-scope freeze; no in-flight reverse | PI-205 (transition); PI-216 reads the resulting status |
| FE-6 / REQ-229 area freeze / reopen | PI-206 (area freeze) + PRJ-034 (reopen); out of PI-216 scope |
