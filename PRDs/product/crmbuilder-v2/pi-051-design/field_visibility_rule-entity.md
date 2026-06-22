# Design — `field_visibility_rule` entity

**Workstream:** WSK-166 (Design) — *Security rule data model & process design*
**Work task:** WTK-198 (area `access`)
**Planning item:** PI-051 — RBAC Deploy Support (§12.5 Role-Aware Visibility alongside §12.7 Field-Level Permissions)
**Requirements traced:** REQ-254 (deploy role-aware field visibility and field-level permissions); REQ-128 (§12.5 audit + deploy role-aware visibility, PRJ-024)
**Status:** Design only. This document specifies the entity; no schema, model, or deploy code is written by this slice. The Develop phase (WSK-167) implements it.

This is one slice of the PI-051 RBAC-deploy design surface. Sibling slices specify the
companion `field_permission_rule` entity (WTK-197), the Role persona and the rule→role
scoping associations (WTK-199), the `deploy_security_configuration` process (WTK-200), and
the program-file schema that declares these rules (WTK-201). This slice owns **only** the
`field_visibility_rule` entity and its fields; cross-slice concerns are referenced, not
specified here.

---

## 1. Purpose

`field_visibility_rule` is the structured, single-source-of-truth record of **one decision:
whether one field is visible to one role** in the target CRM's UI. It is the data-model
counterpart of the §12.5 Role-Aware Visibility surface of the YAML program-file schema
(`PRDs/product/app-yaml-schema.md` §12.5) — specifically the field-level `visibleWhen:`
`role:` leaf clause (§12.5.1) reduced to its atomic `(role, field) → visible?` form.

Each rule answers exactly one question, so a field that is visible to two roles and hidden
from a third is three `field_visibility_rule` records, not one record with a list. This
keeps the entity flat, makes the deploy and audit round-trip a per-rule operation, and lets
`deployment_status` be tracked at the granularity at which deployment actually succeeds or
fails on the target CRM.

**Visibility is a UX concern, not a security boundary** (§12.5). A field hidden from a role
by a `field_visibility_rule` may still be reachable through the API by a user who knows the
field name. The companion `field_permission_rule` entity (WTK-197) is the security-boundary
counterpart — it governs read/edit *access*, not interface *visibility*. The two entities are
deliberately separate because they map to two different EspoCRM mechanics (Dynamic Logic /
layout scoping versus role `fieldData` permissions) with different deployability (see §5).

---

## 2. Fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `visible` | boolean | yes | — | Whether the `target_field` is shown to the `role` in the UI. `true` = visible, `false` = hidden. No third "inherit/unspecified" state — absence of a rule already means "default visibility"; the rule exists precisely to override that default in one direction. |
| `role` | reference → role | yes | — | The CRM security Role whose viewing context the rule scopes. Realized as the `field_visibility_rule_applies_to_role` association (see §3); the Role persona itself is specified by WTK-199. |
| `target_field` | reference → field | yes | — | The field whose visibility this rule controls. Realized as the `field_visibility_rule_targets_field` association (see §3). Identifies both the owning entity and the field (a field is unique only within its entity), so the reference resolves to a specific entity-field, mirroring the `(entity, field)` resolution the §11/§12.5 validator already performs via `ProgramContext`. |
| `deployment_status` | enum | yes | `pending` | Lifecycle state of this rule against the target CRM (see §4). Tracks whether the rule is awaiting deploy, deployed, not deployable on the current platform, drifted, or errored. |

### 2.1 `visible` (boolean)

Two-valued by design. The deliberate omission of a null/tri-state value is the same modeling
choice §12.5 makes: a layout or field with no role-aware clause is visible to everyone, so a
rule is only ever authored to *change* the default. A `visible: true` rule is meaningful (it
re-asserts visibility for a role inside a layout that otherwise hides the field for that role
via a sibling variant) and is therefore retained rather than collapsed away.

### 2.2 `role` and `target_field` (references)

Both are modeled as reference associations rather than scalar string columns so the rule
participates in the same graph the rest of the V2 model uses, and so a rename or delete of a
Role or field is a graph operation rather than a string-rewrite. The association *kinds* and
their direction are specified in §3. The Role end is the same Role entity that
`field_permission_rule.role` (WTK-197) points at and that the rule→role scoping associations
(WTK-199) describe — there is one Role concept shared across both rule entities.

`target_field` carries entity context. EspoCRM field identity is `(entity, field)`; a bare
field name (`emailAddress`) is ambiguous across entities. The reference therefore targets the
specific field record (which already belongs to its entity), so no separate `target_entity`
field is needed on `field_visibility_rule`. This matches the §12.5.1 validator, which resolves
a `role:`/`field:` leaf clause against the field set of the entity the clause is attached to.

### 2.3 `deployment_status` (enum) — see §4 for the value set and lifecycle.

---

## 3. Associations (reference edges)

The two reference fields are realized as directed reference edges. Naming follows the V2
reference-vocabulary convention `<source>_<verb>_<target>` (see
`crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`). The rule is always the **source**; the
Role and field are **targets** — the rule is the dependent record that scopes itself to an
existing Role and an existing field.

| Association (reference kind) | Source → Target | Cardinality | Meaning |
|---|---|---|---|
| `field_visibility_rule_applies_to_role` | `field_visibility_rule` → `role` | many rules → one role | Scopes this rule to a single Role's viewing context. |
| `field_visibility_rule_targets_field` | `field_visibility_rule` → `field` | many rules → one field | Identifies the single field whose visibility this rule controls. |

**Uniqueness.** The pair (`applies_to_role`, `targets_field`) is unique per rule — at most one
`field_visibility_rule` may exist for a given `(role, field)` combination. Two rules disagreeing
on `visible` for the same `(role, field)` is a contradiction the Develop phase must reject (the
§12.5.2 "doubly matched role" coverage rule is the analogous existing guard). This uniqueness
constraint is stated here as a design requirement; its enforcement mechanism (DB constraint vs
access-layer check) is a Develop-phase decision.

**Vocabulary impact (for the Develop phase, not done here).** Adding these two kinds requires
the standard two-point vocab update called out in `CLAUDE.md`: add each kind to
`REFERENCE_RELATIONSHIPS` and add its `(source_type, target_type)` constraint to
`_kinds_for_pair`, plus the `refs.relationship_kind` CHECK migration. Direction above is the
binding contract for that work. The sibling `field_permission_rule` entity uses the parallel
kinds `field_permission_rule_applies_to_role` and `field_permission_rule_targets_field`
(WTK-197) — the two entities are symmetric in their association shape and differ only in their
discriminating field (`visible` boolean here vs `permission_level` enum there).

---

## 4. `deployment_status` enum

Tracks where a single rule sits in its journey to the target CRM. The value set is grounded in
the existing v1 engine per-item outcome vocabulary (`SavedViewStatus`, `WorkflowStatus`,
`FilteredTabStatus` in `espo_impl/core/models.py` all use `created/updated/skipped/drift/
error/not_supported`) and in the §12.5 deploy reality (`NOT_SUPPORTED` on EspoCRM 9.x per
DEC-243). Because a `field_visibility_rule` is a persisted record with a lifecycle rather than
a transient per-run result, the rule-level enum adds the explicit pre-deploy and human-handoff
states the run-level enums leave implicit.

| Value | Meaning | Terminal? |
|---|---|---|
| `pending` | Rule authored/captured but not yet pushed to the target CRM. The default for a new rule. | no |
| `deployed` | Rule successfully applied to the target CRM and verified active. | no (can drift) |
| `not_supported` | The target platform has no deploy mechanism for this rule. On EspoCRM 9.x, role-aware field visibility is `NOT_SUPPORTED` per DEC-243 (Dynamic Logic has no `current-user-role` condition; Layout Sets bind to Teams, not Roles). The rule is recorded honestly but cannot deploy. | yes (until platform changes) |
| `manual_required` | A deploy path exists only as a manual operator step (e.g. Dynamic Handler JavaScript, or a Layout Set bound to a mirror-Team). The rule is surfaced in the MANUAL CONFIGURATION REQUIRED advisory, not auto-applied. | yes (until done manually) |
| `drift` | Previously `deployed`, but the target CRM's live state no longer matches the rule (detected by audit/verify). Informational, not a failure. | no |
| `error` | A deploy attempt failed unexpectedly (API/transport error, validation rejection at the target). Carries diagnostic detail for the operator. | no (retryable) |

**Default and transitions.** A new rule is `pending`. The `deploy_security_configuration`
process (WTK-200) is the writer of every other value: it moves `pending → deployed` on a
verified apply, `pending → not_supported` when the platform offers no path (the §12.5 / DEC-243
case — this is the expected steady state for role-aware visibility on EspoCRM 9.x today),
`pending → manual_required` when only an out-of-engine path exists, and `* → error` on
failure. `drift` is written by the audit/verify round-trip. `not_supported` and
`manual_required` are platform-determined, not authored — a rule author never sets them; the
deploy process derives them from the target platform's capabilities.

**Relationship to engine `StepStatus`.** `deployment_status` is per-*rule*; the pipeline's
`StepStatus` (`ok/failed/skipped/no_work`) is per-*step*. A security step whose rules are all
`not_supported` is **not** a step failure — it mirrors the existing precedent where
`NOT_SUPPORTED` items are platform constraints that do not count as deployment errors
(`CLAUDE.md`, "Three features have no public REST API write path"). The Develop phase rollup
from rule `deployment_status` to step `StepStatus` must preserve that: `not_supported` and
`manual_required` rules do not downgrade a step to `failed`.

---

## 5. Mapping to §12.5 and the deploy adjudication

`field_visibility_rule` is the normalized, deploy-trackable form of the §12.5.1 field-level
`role:` leaf clause. The authoring surfaces (§12.5.1 `role:` leaf clauses, §12.5.2 `forRoles:`
layout variants) and the program-file schema that carries them are owned by WTK-201; this
entity is what those declarations compile *into* for storage, deploy, and audit.

Per DEC-243 and the §12.5 "Deploy Support" note, role-aware field visibility is currently
`NOT_SUPPORTED` at deploy on EspoCRM 9.x. The entity is designed to record that honestly:
the rule is captured, traced to its role and field, and parked at `deployment_status =
not_supported` (or `manual_required` if the engagement opts into an out-of-engine path). When a
real deploy mechanism lands — the v1.4 workstream the §12.5 note anticipates — only the
`deploy_security_configuration` process (WTK-200) changes; the `field_visibility_rule` entity
and its associations do not. This separation is the point of modeling the rule as data rather
than as transient validator output.

---

## 6. Out of scope for this slice

- The Role entity/persona definition and the rule→role scoping semantics — WTK-199.
- The `field_permission_rule` entity (read/edit access levels) — WTK-197.
- The `deploy_security_configuration` process that reads, deploys, verifies, and sets
  `deployment_status` — WTK-200.
- The program-file (YAML) schema that declares the rules an author writes — WTK-201.
- Any schema migration, SQLAlchemy model, repository, REST endpoint, or vocab change — the
  Develop phase (WSK-167). §3's association directions and §4's enum value set are the binding
  contract handed to that phase.
