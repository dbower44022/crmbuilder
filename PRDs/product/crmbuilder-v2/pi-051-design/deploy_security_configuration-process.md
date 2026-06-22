# Design — `deploy_security_configuration` process

**Workstream:** WSK-166 (Design) — *Security rule data model & process design*
**Work task:** WTK-200 (area `automation`)
**Planning item:** PI-051 — RBAC Deploy Support (§12.5 Role-Aware Visibility alongside §12.7 Field-Level Permissions)
**Requirements traced:** REQ-254 (deploy role-aware field visibility and field-level permissions to the target CRM with no manual administrator setup, and verify they are active)
**Status:** Design only. This document specifies the deploy *process* and its two
deploy associations; no pipeline, manager, or deploy code is written by this slice. The
Develop phase (WSK-167) implements it.

This is one slice of the PI-051 RBAC-deploy design surface. Sibling slices specify the
`field_permission_rule` entity (WTK-197), the `field_visibility_rule` entity (WTK-198),
the Role persona and the rule→role scoping associations (WTK-199), and the program-file
schema that declares these rules (WTK-201). This slice owns **only** the
`deploy_security_configuration` process and the two associations from it to the rule
entities; the rule entities themselves and the program-file authoring surface are
referenced, not specified here.

---

## 1. Purpose

`deploy_security_configuration` is the automation-area process that takes the confirmed
security-rule records — `field_permission_rule` (WTK-197) and `field_visibility_rule`
(WTK-198) — declared in a program file (WTK-201) and **applies them to the target CRM
without any manual administrator step, then reads the target back to confirm each rule is
active.** It is the process half of REQ-254: the rule entities are the *what*, this
process is the *how it reaches the target and how we know it took*.

It is the security-rule counterpart of the existing field / layout / relationship deploy
managers (`espo_impl/core/field_manager.py`, `layout_manager.py`,
`relationship_manager.py`) and slots into the existing 12-step deploy pipeline
(`espo_impl/core/deploy_pipeline.py`) as an **extension of Step 11 — "Security (teams
and roles)"**. That step today reconciles whole Role records' entity-scope `data` blocks
and Team records via `RoleManager.process_roles` / `TeamManager.process_teams`;
`deploy_security_configuration` adds the per-field security surface those managers
explicitly leave for v1.4 (`role_manager.py` line 28: *"Field-level permissions
(`fieldData`) — v1.4 deferred"*).

The process is the **sole writer of each rule's `deployment_status`**. A rule author
never sets a deployed/drift/error value; the process derives it from what actually
happened against the target. This is the design reason both rule entities carry a
`deployment_status` axis independent of their design-lifecycle `status` (WTK-197 §4,
WTK-198 §4): design agreement and deploy outcome are different facts, written by
different actors at different times.

---

## 2. Inputs and preconditions

| Input | Source | Role in the process |
|---|---|---|
| Confirmed `field_permission_rule` records | Program file (WTK-201), loaded + validated | The (role × field) → access-level intents to apply. |
| Confirmed `field_visibility_rule` records | Program file (WTK-201), loaded + validated | The (role × field) → visible? intents to apply. |
| Target instance + admin client | The active instance's `EspoAdminClient` | The CRM the rules deploy to and are verified against. |
| Deployed Roles and fields | Already on the target (earlier pipeline steps / prior deploy) | The records the rules attach to — see ordering below. |

**Confirmed-before-deploy.** Only a rule whose design-lifecycle `status = confirmed`
is eligible. A `candidate` / `deferred` / `rejected` rule is skipped, never deployed
(WTK-197 invariant §6.1). This is a hard precondition the process checks before any
write — it never deploys an unagreed intent.

**Ordering precondition.** Field-level permissions write into a *Role* record's
`fieldData`, keyed by *(entity, field)*. Both the Role and the field must already exist
on the target before this process runs. The pipeline already guarantees this by position:
entities (Step 2) → fields (Step 7) → relationships (Step 9) all precede Security
(Step 11). `deploy_security_configuration` therefore runs **after** the field/role steps
and assumes their subjects are live, exactly as the current Security step assumes its
entities exist (`role_manager.py` line 26–27). A rule whose role or target field is
missing on the target resolves to a per-rule `error`/`failed`, not a process abort.

---

## 3. Deploy associations (this slice owns these)

The process relates to the two rule entities through two directed associations. Naming
follows the V2 reference-vocabulary convention `<source>_<verb>_<target>`
(`crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`). The process is the **source**; each
rule entity is a **target** — the process is the actor that reads the rules and writes
their deploy outcome.

| Association (reference kind) | Source → Target | Cardinality | Meaning |
|---|---|---|---|
| `deploy_security_configuration_deploys_field_permission_rule` | `deploy_security_configuration` → `field_permission_rule` | one process → many rules | The process reads each confirmed `field_permission_rule`, renders it into the target Role's `fieldData`, verifies it, and writes its `deployment_status`. |
| `deploy_security_configuration_deploys_field_visibility_rule` | `deploy_security_configuration` → `field_visibility_rule` | one process → many rules | The process reads each confirmed `field_visibility_rule`, applies it via the §12.5 deploy path available on the target (or records `not_supported` / `manual_required`), verifies it where deployable, and writes its `deployment_status`. |

**Direction is the binding contract.** The rule is the dependent record; the process is
the operator over it. The process never *creates* a rule (rules originate from the
program file / design model) — it *deploys* one and stamps its outcome. The verb
`deploys` is chosen over `reads`/`writes` because it names the whole read→render→verify→
stamp cycle the association represents.

**Whether these are persisted `refs` edges is a Develop-phase decision.** WTK-198 models
its rule→role / rule→field associations as `refs` edges, while WTK-197 carries its
role/field references as plain prefixed-identifier columns and flags the divergence as an
open question (WTK-197 §11, §5). The two process associations here are at a different
altitude — they relate a *process* to the rules it operates on, which may be expressed
purely in the process specification rather than persisted as graph edges, since the
process is engine code rather than a stored design row. This slice fixes the **direction,
naming, and cardinality** as the contract; the Develop phase decides realization
(`refs` vocab kinds vs. spec-only relationship) once it knows whether
`deploy_security_configuration` is itself a stored `process` design record (PRC-NNN) or a
named engine pipeline step. If realized as vocab kinds, the standard two-point update
applies (add each kind to `REFERENCE_RELATIONSHIPS` and its `(source_type, target_type)`
pair to `_kinds_for_pair`, plus the `refs.relationship_kind` CHECK migration) — see
`CLAUDE.md`.

---

## 4. Process phases (CHECK → ACT → VERIFY)

The process mirrors the CHECK→ACT orchestration every existing deploy manager uses
(`RoleManager.process_roles`, `FieldManager`, etc.), extended with an explicit VERIFY
phase because REQ-254's acceptance test is *"verification confirms the rules are active"* —
verification is part of the deliverable, not an afterthought.

### 4.1 CHECK — read intent and current target state

1. Collect the confirmed rules of both kinds from the loaded program (skip non-confirmed).
2. Group `field_permission_rule` records by their `role` — all field permissions for one
   role land in that one Role record's `fieldData`, so the write unit is *per role*, not
   *per rule* (a single PATCH carries every field-permission for a role).
3. Fetch the current target Role records (reusing `RoleManager`'s existing
   `_fetch_server_roles` CHECK) and read each Role's current `fieldData`.
4. Diff intended vs. current to classify each rule: needs-create / needs-update /
   already-matches (no-op) — the same CHECK-then-ACT idempotence the field and role
   managers already implement (`role_manager.py` `_update_or_skip_role`).

### 4.2 ACT — render and apply, with no manual step

The two rule kinds have **different deployability**, and the process treats them
honestly rather than pretending parity:

* **`field_permission_rule` → Role `fieldData` (fully automatable via REST).** This is
  the path that delivers REQ-254's "no manual steps" promise for field-level permissions.
  EspoCRM stores field-level permissions on the Role record in a `fieldData` JSON column
  parallel to the entity-scope `data` column the current `RoleManager` already writes
  (`_translate_data_block`, line 89). The neutral `permission_level` maps to the
  EspoCRM `{read, edit}` pair per WTK-197 §7:

  | `permission_level` | `fieldData[<entity>][<field>]` |
  |---|---|
  | `read_write` | `{"read": "yes", "edit": "yes"}` |
  | `read_only`  | `{"read": "yes", "edit": "no"}`  |
  | `no_access`  | `{"read": "no",  "edit": "no"}`  |

  The process renders all of a role's confirmed field-permission rules into one
  `fieldData` block and PATCHes the Role record — exactly the wire mechanism
  `RoleManager` already uses for `data`, extended to the second column. **No admin UI step
  is required**; this closes the v1.4-deferred gap named in `role_manager.py` line 28.
  Entities/fields omitted from `fieldData` keep the target's default (whitelist
  semantics, matching the entity-scope behavior in `role_manager.py` lines 22–23 and the
  "absence = no override" rule of WTK-197 §3).

* **`field_visibility_rule` → §12.5 role-aware visibility (platform-constrained).** Per
  DEC-243, EspoCRM 9.x Dynamic Logic has **no role-condition type**, so there is no REST
  write path to make a field visible-to-role-A / hidden-from-role-B. The process applies
  the best path the target actually offers, in this order, and records the outcome
  honestly (it does **not** silently no-op):
  1. **REST Dynamic Logic with a role condition** — if a future EspoCRM exposes one, the
     rule deploys via REST and is verifiable. Not available on 9.x today.
  2. **Generated Dynamic Handler JavaScript** (PI-051 candidate 1) — emit
     `client/custom/src/views/<entity>/record/detail.js` with role-aware show/hide logic.
     This is a **file-system write, not REST**, so it sits at the edge of the API-only
     model; if the engagement enables it, the rule deploys with no *admin UI* step but
     does require engine-side file generation + cache rebuild. Verifiable only by
     re-reading the generated artifact, not by API state (NOT_AUDITABLE via REST).
  3. **Layout Sets bound to auto-generated mirror-Teams** (PI-051 candidate 4) — usable
     for layout-level role scoping even while leaf-clause role conditions stay
     unsupported; conflates Team and Role semantics and surfaces operator-visible
     auto-teams, so it is opt-in.
  4. **None available** → the rule is recorded `not_supported` (steady state on EspoCRM
     9.x today, per WTK-198 §4 and DEC-243) or `manual_required` if only an out-of-engine
     path exists, and surfaced in the run's **MANUAL CONFIGURATION REQUIRED** advisory
     block (the existing `emit_manual_config_block` precedent in `deploy_pipeline.py`).

### 4.3 VERIFY — read back and confirm active

After ACT, the process re-reads the target to confirm each deployed rule is live, then
writes the per-rule `deployment_status`:

* **`field_permission_rule`:** re-GET the Role record and compare its `fieldData` cell for
  `(entity, field)` against the intended `{read, edit}` pair. Match → `deployed`;
  mismatch → `drifted`/`failed`. This is the read-back WTK-197 §7 names as the source of
  `deployment_status`.
* **`field_visibility_rule`:** verifiable only where a deploy path produced
  API-observable state. For REST Dynamic Logic, read it back. For generated Dynamic
  Handler JS, "verification" is confirming the artifact was written (the surface is
  NOT_AUDITABLE via API, per PI-051 candidate 1) — the process records `deployed` against
  the artifact, not against live API state, and says so. For `not_supported` /
  `manual_required`, there is nothing to verify and the status is terminal.

The VERIFY phase reuses the polling discipline the deploy/verify code already established
(`phase_verify` polls network-dependent checks on a backoff rather than probing once —
`CLAUDE.md` commit `1d9bd0e`): a freshly-PATCHed Role may not read back instantly after a
metadata rebuild, so the read-back polls with a short backoff before declaring `drifted`.

---

## 5. `deployment_status` writing and the step-status rollup

The process writes each rule's `deployment_status` (the entity-level enum defined by
WTK-197 §4 / WTK-198 §4). It is the only writer of every value except the design author's
default and the audit/drift path:

| Transition | Trigger |
|---|---|
| default `not_deployed` / `pending` → `deployed` | ACT succeeded **and** VERIFY confirmed the rule active on the target. |
| → `not_supported` | The target platform offers no deploy path (the §12.5 / DEC-243 case for visibility on EspoCRM 9.x). Platform-determined, not authored. |
| → `manual_required` | Only an out-of-engine path exists; surfaced in the MANUAL CONFIGURATION REQUIRED block. |
| `deployed` → `drifted` | VERIFY (or the PRJ-027 audit round-trip) found the target no longer matches. The audit path also writes this outside a deploy run. |
| → `failed` / `error` | An ACT or VERIFY attempt failed unexpectedly (transport error, target rejection, missing role/field). Retryable. |

**Step-status rollup.** The process contributes to the pipeline's Step 11 `StepStatus`,
and it must preserve the existing platform-constraint semantics: a security rule resolving
to `not_supported` or `manual_required` is **not** a step failure — it mirrors the
established precedent that `NOT_SUPPORTED` items are platform constraints that don't count
as deployment errors (`CLAUDE.md`, "Three features have no public REST API write path";
WTK-198 §4 "Relationship to engine `StepStatus`"). Only genuine `failed`/`error` rules
downgrade the step to `FAILED`. An all-`not_supported` security run reports
`OK` with a MANUAL CONFIGURATION REQUIRED advisory, never `FAILED`.

---

## 6. Position in the deploy pipeline

`deploy_security_configuration` extends **Step 11 — Security** of the 12-step pipeline in
`espo_impl/core/deploy_pipeline.py`. Concretely, the Develop phase wires it so the
existing Security step (which today calls `team_mgr.process_teams` then
`role_mgr.process_roles`) gains a third sub-phase that processes the field-level security
rules into the Role records the role step just reconciled — teams first, then role
entity-scope, then **field-level security rules** last, because the field-permission
write targets the very Role records the role sub-step creates/updates. This keeps the
single `run_step("security", …)` wrapper, its `failure_check`, and its
`DeployOutcome.security_role_results` accumulation intact, so the truthful STEP SUMMARY
and MANUAL CONFIGURATION REQUIRED reporting the pipeline already produces extend to
security rules with no new step machinery.

A dedicated `SecurityRuleManager` (sibling to `RoleManager` / `TeamManager`,
`espo_impl/core/`) is the natural home for the CHECK→ACT→VERIFY logic, reusing
`RoleManager._fetch_server_roles` for CHECK and the `EspoAdminClient` PATCH path for ACT
rather than duplicating Role I/O. Manager-class injection follows the existing
`DeployManagers` dataclass pattern (`deploy_pipeline.py` line 129). All of this is the
Develop phase's to build; this section fixes only *where the process lives and what it
reuses* so that phase doesn't re-litigate placement.

---

## 7. Reconciling REQ-254's "no manual steps" with the §12.5 platform reality

REQ-254 asks for deploy "with no manual steps." The process delivers this **fully for
field-level permissions** (`field_permission_rule` → Role `fieldData` via REST — the v1.4
gap closed) and **as far as the platform allows for role-aware visibility**
(`field_visibility_rule`). The honest position, carried from DEC-243 and WTK-198, is:

* Field-level permissions: **fully automated, no manual step, verifiable.** This is the
  larger and more security-significant half of REQ-254 and it is unblocked.
* Role-aware visibility on EspoCRM 9.x: **no pure-REST path exists.** The process applies
  the best available mechanism (generated Dynamic Handler JS is the most "no-manual-admin"
  of the candidates, at the cost of a file-system write) and otherwise records
  `not_supported`/`manual_required` truthfully. When EspoCRM ships a Dynamic Logic
  role-condition (the upstream feature request, PI-051 candidate 3), **only this process
  changes** — the rule entities and their associations do not. That is precisely why
  visibility is modeled as a tracked rule with a `deployment_status` rather than as
  transient validator output (WTK-198 §5).

This asymmetry is a design fact to surface to the human reviewer, not a defect to hide:
the requirement's acceptance is met for the deployable surface and honestly parked for the
platform-blocked one.

---

## 8. Open questions / deferred

* **`deployment_status` vocab divergence between the two rule entities.** WTK-197 uses
  `{not_deployed, deployed, drifted, failed}`; WTK-198 uses `{pending, deployed,
  not_supported, manual_required, drift, error}`. The process writes both, so the two
  vocabularies should be reconciled into one shared `FIELD_DEPLOYMENT_STATUSES` set (WTK-197
  §9 already proposes sharing it) before the Develop phase — otherwise the process needs
  two status-writing code paths for what is one deploy outcome. **Recommendation:** adopt
  the WTK-198 superset (it has the `not_supported`/`manual_required` states the §12.5
  reality requires) for both entities. Flagged for the WSK-166 reconciliation, not decided
  here.
* **Is `deploy_security_configuration` a stored `process` (PRC-NNN) design record or a
  named engine pipeline step?** This determines whether the §3 associations are persisted
  `refs` edges or spec-only relationships. Resolve at Develop kickoff (see §3).
* **Dynamic Handler JS generation scope.** Whether candidate-2 file generation is in
  scope for the first Develop slice or deferred behind field-permission deploy. Field
  permissions are the unblocked, higher-value half and should land first; visibility
  deploy can be a follow-on slice.
* **Build authorization.** Turning this process design into pipeline/manager/migration
  code requires its own confirmed requirement + implementing PI per the governance
  precondition (`CLAUDE.md`, "Governance is a precondition, not a postscript"). REQ-254 is
  confirmed; the implementing PI for the *build* is a Develop-phase concern, not authorized
  by this Design fragment.

---

## 9. Out of scope for this slice

- The `field_permission_rule` and `field_visibility_rule` entities themselves — WTK-197,
  WTK-198. This slice consumes their field/status contracts; it does not define them.
- The Role persona and rule→role scoping associations — WTK-199.
- The program-file (YAML) schema that declares the rules an author writes — WTK-201.
- The PRJ-027 audit/drift round-trip that flips `deployed → drifted` outside a deploy run.
- Any pipeline code, `SecurityRuleManager`, schema migration, REST endpoint, or vocab
  change — the Develop phase (WSK-167). §3's association directions/naming, §4's phase
  contract, §5's status transitions, and §6's pipeline placement are the binding contract
  handed to that phase.
