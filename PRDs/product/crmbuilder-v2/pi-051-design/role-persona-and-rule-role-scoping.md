# Design — CRM security Role persona & the rule→role scoping associations

**Workstream:** WSK-166 (Design) — *Security rule data model & process design*
**Work task:** WTK-199 (area `access`)
**Planning item:** PI-051 — RBAC Deploy Support (§12.5 Role-Aware Visibility alongside §12.7 Field-Level Permissions)
**Requirements traced:** REQ-254 (deploy role-based field visibility and field-level permissions); REQ-128/REQ-129 (§12.5 / §12.7 role-aware visibility + field-level permissions, PRJ-024)
**Status:** Design only. No schema, model, migration, repository, REST endpoint, or vocab change is produced by this slice. The Develop phase (WSK-167) implements the binding contract stated here under its own confirmed requirement + implementing PI.

This is one slice of the PI-051 RBAC-deploy design surface. It owns **two cross-cutting
concerns** that the per-entity slices deliberately delegated here to keep area boundaries clean
and to avoid the two rule entities disagreeing:

1. the **CRM security Role persona** — the principal the security rules scope to (§1–§3); and
2. the **`field_permission_rule → role` and `field_visibility_rule → role` scoping
   associations** — *how* a rule is anchored to its Role (§4–§6).

Sibling slices: `field_permission_rule` entity (WTK-197), `field_visibility_rule` entity
(WTK-198), the `deploy_security_configuration` process (WTK-200), and the program-file schema
(WTK-201). Cross-slice concerns are referenced, not re-specified here.

## Revision Control

| Version | Date | Author | Change |
|---|---|---|---|
| v0.1 | 2026-06-22 | ADO Area Specialist (access, WTK-199) | Initial design surface for the Role persona and the rule→role scoping; reconciles the WTK-197 column / WTK-198 edge disagreement on role scoping. |

---

## 1. The Role persona — it already exists; this slice positions it

The "CRM security Role persona" this slice names is **not a new entity**. It is the existing
engine-neutral **`Role`** design record — table `roles`, identifier prefix **`ROL-NNN`**,
served at `/roles`, repository `access/repositories/roles.py` — introduced by **PI-194 under
PRJ-027** (the multi-instance audit/inventory work). WTK-197 §5 and WTK-198 §2.2 both already
point their `role` reference at *this* record; this slice confirms that there is **one Role
concept shared across both rule entities** and describes what it is in the security-rule
context.

The `Role` record as built (see `access/models.py::Role`):

```
roles
  role_identifier        PK, "ROL-NNN" (^ROL-\d{3}$)
  role_name              human label, non-empty
  role_scope_access      JSON | NULL   (per-(entity,action) scope-access matrix, audit-captured)
  role_system_permissions JSON | NULL  (cross-cutting system permissions, audit-captured)
  role_description        TEXT | NULL
  role_status            candidate | confirmed | deferred | rejected   (default candidate)
  role_notes             TEXT | NULL
  role_created_at / role_updated_at / role_deleted_at
```

It carries the standard four-status propose-verify lifecycle (`ROLE_STATUSES` =
`{candidate, confirmed, deferred, rejected}` in `vocab.py`) shared by every design family, and
is engagement-scoped (`EngagementScopedPKMixin`) and soft-deletable like every design record.

**No change to the `Role` entity is proposed or needed.** A `field_permission_rule` and a
`field_visibility_rule` scope themselves to a Role; the Role already exists, is already a
first-class confirmable/publishable design record, and is already round-tripped by the PRJ-027
audit. This slice's contribution to the persona is *positional* (§2–§3), not structural.

## 2. "Role persona" vs. the methodology `Persona` — they are different records

The word "persona" is overloaded in this codebase, and conflating the two would be a real
modeling error, so it is settled here explicitly:

| | Methodology **`Persona`** (`PER-NNN`, `personas`) | Security **`Role`** (`ROL-NNN`, `roles`) |
|---|---|---|
| What it models | A *human role or actor* in the client's organization captured in discovery (Phase 2/3) — "Program Manager", "Volunteer Mentor". | An *engine-neutral CRM security role* — a named bundle of scope-access + system permissions a CRM user account is granted. |
| Origin | Authored in requirements interviews; reconciled into the Persona Inventory. | Captured by audit from a live CRM, or authored as design intent for deploy. |
| Distinguishing data | `persona_role_summary`, `persona_responsibilities`. | `role_scope_access`, `role_system_permissions` (JSON matrices). |
| Relationship | A `Persona` may be *served by* one or more `Role`s in the deployed CRM, but the two are not the same row and are not merged. | — |

The security rules in PI-051 scope to the **`Role`**, not the `Persona`. A field permission or
visibility rule is about what a *CRM security role* may see/do, which is the deployable,
audit-round-trippable concept; the `Persona` is the upstream human-intent concept that
motivates which Roles exist. **This slice does not introduce a `persona → role` association** —
that link is a separate methodology concern (Persona Inventory → Role realization) outside the
PI-051 security-deploy scope and is explicitly out of scope here (§7).

## 3. Mapping the Role persona across engines (positional)

Following the §6/§7/§8 dual-engine convention of
`engine-neutral-design-model-and-adapters.md`, the Role persona maps as:

| Neutral | EspoCRM | HubSpot-style object model |
|---|---|---|
| `Role` (`role_scope_access`, `role_system_permissions`) | A `Role` record (scope-level access matrix + system-level permissions). | A permission set / user role. |
| A rule scoped to a `Role` | A `fieldLevelData` entry (permission rule) or a Dynamic-Logic / Layout-Set scoping (visibility rule) **on that Role**. | A property-level permission **within that permission set**. |

The disposition (per §3 of the engine-neutral doc) is **neutral**: the Role and its scoping
rules are authored once in neutral form and an adapter compiles them to each engine. Whether a
given engine has a deploy mechanism for a given rule is a Develop/automation concern (WTK-200);
on EspoCRM 9.x field-level *visibility* is `NOT_SUPPORTED` per DEC-243, while field-level
*permissions* map to the Role's `fieldLevelData` (WTK-197 §7).

---

## 4. The rule→role scoping associations — the decision this slice owns

WTK-197 §11 and WTK-198 §6 both explicitly **defer the rule→role scoping decision to this
slice**, and they currently disagree on its shape:

* **WTK-197** (`field_permission_rule`) carries `role` as a **plain validated
  prefixed-identifier string column** (`field_permission_rule_role`), matching the
  `Rule.rule_subject_identifier` / `Association` endpoint pattern (DEC-046).
* **WTK-198** (`field_visibility_rule`) models `role` as a **`refs` edge**
  (`field_visibility_rule_applies_to_role`).

As the designated owner of this cross-cutting concern, this slice **settles it one way for both
rule entities** so the Develop phase has a single binding contract.

### 4.1 Decision

**The rule→role scoping is a plain, access-layer-validated prefixed-identifier string column on
the rule, not a `refs` edge.** Concretely, both rule entities carry:

```
field_permission_rule_role   ROL-NNN  → roles (live, correct type), NOT NULL
field_visibility_rule_role   ROL-NNN  → roles (live, correct type), NOT NULL
```

resolved exactly as `Rule.rule_subject_identifier` resolves its subject: the access layer
validates at write time that the value is a well-formed `ROL-NNN`, resolves to a **live**
(non-soft-deleted) row, and is of type `role`.

This **confirms WTK-197's column choice** and **supersedes WTK-198 §3's
`field_visibility_rule_applies_to_role` edge for the role scoping specifically.** (The
`target_field` reference is owned by each entity's own slice and is out of this slice's scope —
§7; this decision governs the **role** end only. The Develop phase should apply the same
column-vs-edge reasoning to `target_field` for consistency, but that call belongs to WTK-197 /
WTK-198, not here.)

### 4.2 Why a column, not an edge

1. **Dominant family convention.** Every composite design construct in the model —
   `Association` (source/target entities), `Rule` (subject), `dedup_rule`, `view` — carries its
   referenced design records as **plain validated string columns, not `refs` edges**, by
   deliberate decision DEC-046. The security rules are composite design constructs in exactly
   this family; modeling their principal as an edge would make them the lone exception. The
   `Association` docstring states the rationale directly: the construct *is* the relationship,
   so "the access layer validates both endpoints exist and are live at write time rather than
   holding an FK." A `field_*_rule` is likewise the relationship between a Role and a field — it
   is not a node that *has* edges to them.
2. **The uniqueness invariant is a column constraint.** Both siblings require **at most one live
   rule per `(role, target_field)`** (WTK-197 §6.3, WTK-198 §3 "uniqueness"). With both
   references as columns this is a single partial UNIQUE index on
   `(…_role, …_target_field)` among non-deleted rows — the same shape `field_permission_rule`
   already proposes (WTK-197 §8). Modeled as edges, the same guarantee needs a graph-level
   "no second edge-pair for this `(role, field)`" check the access layer would have to hand-roll
   on every write. The column form makes the contradiction *unrepresentable at the storage
   layer*; the edge form only makes it *checkable*.
3. **Queryability.** "Which rules scope to `ROL-005`?" and the deploy/audit per-role sweep are a
   simple indexed `WHERE …_role = 'ROL-005' AND …_deleted_at IS NULL`, not a `refs` traversal.
   The deploy process (WTK-200) reads rules **by role** (it deploys a Role's whole field matrix
   at once); an indexed column is the natural access path for that read.
4. **Symmetry with `target_field`.** Both siblings agree `target_field` resolves like
   `rule_subject_identifier`. Keeping `role` a column too makes a rule a flat
   `(role, target_field, discriminator)` row — the shape WTK-197 §8 already drew and the shape
   the §12.5 validator's `(role, field)` leaf-clause resolution mirrors.

### 4.3 Addressing WTK-198's rationale for an edge

WTK-198 §2.2 chose edges so a rule "participates in the same graph" and so a Role/field
"rename or delete is a graph operation rather than a string-rewrite." Both concerns are
answered without an edge:

* **Rename.** `ROL-NNN` is a **stable primary key**, not a mutable label. A Role is renamed by
  editing `role_name`; its identifier never changes (the model has soft-delete + restore, no
  renumber). So there is no "string-rewrite on rename" — the column holds the stable key, and
  the human label is free to change without touching any rule.
* **Delete.** Invariant: a rule may only reference a **live** Role (validated at write time,
  exactly as `Rule` validates its subject and `Association` its endpoints). Deploy and audit
  reads filter live rows. A Role is soft-deleted, so a stale reference is detectable
  (the resolve finds a `role_deleted_at IS NOT NULL` row) rather than dangling — the same
  integrity story `Association`/`Rule` already rely on. A referential-integrity sweep over the
  column is identical in cost to one over the edge table.

The edge buys generic graph participation the security-deploy read path does not use; the
column buys storage-level uniqueness and a direct per-role read path the deploy process does
use. The column wins on the concerns that are actually exercised.

---

## 5. The two associations — binding contract for the Develop phase

| Association | Carrier on the rule | Source → Target | Cardinality | Meaning |
|---|---|---|---|---|
| `field_permission_rule → role` | `field_permission_rule_role` (`ROL-NNN` column, NOT NULL) | many rules → one role | A `field_permission_rule` scopes its `permission_level` to exactly one Role. |
| `field_visibility_rule → role` | `field_visibility_rule_role` (`ROL-NNN` column, NOT NULL) | many rules → one role | A `field_visibility_rule` scopes its `visible` flag to exactly one Role. |

**Direction & cardinality.** The rule is always the *dependent* record; the Role is the
*referenced* record. A Role is referenced by zero-or-many rules; a rule references exactly one
Role (`NOT NULL`). The Role has no back-pointer column to its rules — the relationship is read
from the rule side by the indexed column (§4.2.3).

**Invariants the Develop phase must enforce** (access layer, mirroring `Rule`/`Association`):

1. **Well-formed & live.** Each `*_role` value matches `^ROL-\d{3}$`, resolves to a live
   `roles` row in the active engagement, and is of type `role`. Reject (422) otherwise.
2. **Engagement-local.** A rule and its Role are in the same engagement (both are
   engagement-scoped); cross-engagement references are rejected.
3. **`(role, target_field)` uniqueness** among live rows, per rule entity — the partial UNIQUE
   index of §4.2.2. Enforced at the DB layer (constraint), backed by an access-layer pre-check
   for a clean 409.
4. **No cascade hard-delete.** Soft-deleting a Role does not soft-delete its rules; instead a
   later write or audit surfaces the stale reference (invariant 1). Whether a Role with live
   referencing rules may be soft-deleted at all is a WTK-200 / Develop-phase guard decision; the
   conservative default is to **block** soft-deleting a Role while live rules reference it, mirroring
   how the model protects referenced design records elsewhere.

**No new reference-vocabulary kinds.** Because the scoping is a column, the Develop phase does
**not** add `field_permission_rule_applies_to_role` / `field_visibility_rule_applies_to_role`
to `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair`, and does **not** add a
`refs.relationship_kind` CHECK migration for them. (This deletes the WTK-198 §3 "Vocabulary
impact" task for the role end.) The only vocab touch from the role scoping is that `role`
already exists as a design entity type — nothing to add.

## 6. Proposed shape — where the column sits on each rule

This slice does not redraw the full record shapes (WTK-197 §8 and WTK-198 §2 own those); it
fixes only the role column:

```
# on field_permission_rule (WTK-197 §8 — confirmed as already drawn):
field_permission_rule_role        ROL-NNN  → roles (live), NOT NULL
  index: part of UNIQUE(field_permission_rule_role, field_permission_rule_target_field) among live rows
  index: ix on field_permission_rule_role (per-role deploy read)

# on field_visibility_rule (supersedes WTK-198 §3 edge for the role end):
field_visibility_rule_role        ROL-NNN  → roles (live), NOT NULL
  index: part of UNIQUE(field_visibility_rule_role, field_visibility_rule_target_field) among live rows
  index: ix on field_visibility_rule_role (per-role deploy read)
```

CHECK / format validation for the `ROL-NNN` format reuses `_IdentifierFormatCheck` exactly as
`Role`/`Rule` do; live-and-correct-type resolution reuses the same access-layer helper that
`Rule` uses to validate `rule_subject_identifier` (the Develop phase should promote/reuse that
helper rather than duplicate it).

## 7. Out of scope for this slice

- The `field_permission_rule` entity body and its `target_field`/`permission_level`/lifecycle —
  WTK-197.
- The `field_visibility_rule` entity body and its `target_field`/`visible`/`deployment_status` —
  WTK-198. (This slice overrides only WTK-198 §3's **role** edge, not the rest of WTK-198.)
- The `target_field` reference shape on either rule — owned by WTK-197 / WTK-198. §4.2 notes the
  consistency argument but does not decide it.
- The `deploy_security_configuration` process that reads rules by role and writes
  `deployment_status` — WTK-200.
- The program-file (YAML) schema that declares rules and roles — WTK-201.
- Any `persona → role` realization link (methodology Persona Inventory → security Role) — a
  separate methodology concern, not part of PI-051 security deploy.
- Any schema migration, SQLAlchemy model, repository, REST endpoint, or vocab change — the
  Develop phase (WSK-167). §4's column decision and §5's invariants are the binding contract
  handed to that phase.

## 8. Open questions / deferred

- **`target_field` column-vs-edge consistency.** §4.2.4 argues `target_field` should be a column
  too, for symmetry; that decision is WTK-197 / WTK-198's to make, not this slice's. If they
  retain `target_field` as an edge while `role` is a column, the `(role, target_field)`
  uniqueness invariant (§5.3) spans a column and an edge and must be enforced in the access
  layer rather than as a single DB index — a wrinkle the Develop phase should weigh when settling
  `target_field`.
- **Role soft-delete guard.** §5.4 proposes blocking soft-delete of a Role with live referencing
  rules; the exact UX (block vs. cascade-orphan-then-warn) is a WTK-200 / Develop-phase call.
- **Build authorization.** Turning this design into model/migration/repository/REST requires its
  own confirmed requirement + implementing PI per the governance precondition; it is not
  authorized by this Design fragment.
