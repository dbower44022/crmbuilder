# Design — program-file schema for role-aware visibility and field-level permission rules

**Workstream:** WSK-166 (Design) — *Security rule data model & process design*
**Work task:** WTK-201 (area `programs`)
**Planning item:** PI-051 — RBAC Deploy Support (§12.5 Role-Aware Visibility alongside §12.7 Field-Level Permissions)
**Requirements traced:** REQ-254 (deploy role-aware field visibility and field-level permissions to the target CRM with no manual administrator setup, and verify they are active)
**Status:** Design only. This document specifies the **input program-file format** — the authoring surface an operator writes — that declares the security rules the deploy process consumes. It writes no loader, validator, or schema-spec code, and it does not amend the authoritative YAML schema spec (`PRDs/product/app-yaml-schema.md`); folding this surface into that spec at its next revision is a Develop-phase concern (WSK-167), consistent with the §12.7 "Naming note" that the doc-revision number is fixed only when a feature ships.

This is one slice of the PI-051 RBAC-deploy design surface. Sibling slices specify the
`field_permission_rule` entity (WTK-197), the `field_visibility_rule` entity (WTK-198), the
Role persona and the rule→role scoping associations (WTK-199), and the
`deploy_security_configuration` process and its deploy associations (WTK-200). This slice owns
**only** the program-file authoring format and the rules by which it compiles into those rule
entities; the entities, the Role persona, and the deploy process are referenced as binding
contracts, not specified here.

---

## 1. Purpose

The two rule entities are the *stored, deploy-trackable* form of a security decision;
this slice defines *how an operator writes that decision down* in a program file so it
compiles into those records. It is the **input half** of REQ-254: the author declares
intent in YAML, the loader compiles each declaration into a `field_permission_rule`
(WTK-197) or `field_visibility_rule` (WTK-198) record, and `deploy_security_configuration`
(WTK-200) carries the confirmed records to the target CRM.

The guiding constraint is **continuity with the shipped v1.3 schema**. Role-aware
visibility already has a complete authoring surface in `app-yaml-schema.md` §12.5 — the
`role:` leaf clause (§12.5.1) and the `forRoles:` layout variant (§12.5.2) — that the
loader parses today (it only stops short at deploy, emitting `NOT_SUPPORTED` per DEC-243).
Field-level permissions have a *sketched-but-deferred* surface in §12.7 (the optional
per-field `permissions:` clause). This slice therefore does two distinct things:

1. **Formalizes the §12.7 `permissions:` clause** from a deferred sketch into a precise
   authoring contract that compiles into `field_permission_rule` records — the new surface.
2. **Pins the compilation** of the *existing* §12.5 surface into `field_visibility_rule`
   records — naming the deterministic reduction from author-facing condition clauses /
   layout variants to the atomic `(role, field) → visible?` rows WTK-198 §1 describes.

No new top-level keys are introduced for the common case; the field-level surface attaches
to a field exactly where §12.7 anticipated, and the visibility surface is the one already
shipped. This keeps the authoring vocabulary an operator already knows and avoids a second,
parallel way to say the same thing.

---

## 2. Two authoring surfaces, two target entities

| Author writes | In | Compiles into | Spec basis |
|---|---|---|---|
| `permissions:` clause on a field (per-role `read:` / `edit:`) | a field's `fields:` entry | one `field_permission_rule` per (role, field) | §12.7 (formalized here) |
| `role:` leaf clause inside a `visibleWhen:` | a field's or panel's `visibleWhen:` | one `field_visibility_rule` per (role, field) | §12.5.1 (existing) |
| `forRoles:` layout variant | a `layout.{detail,list}` variant | one `field_visibility_rule` per (role, field) the variant's field set diverges on | §12.5.2 (existing) |

The split is the same split the entities draw (WTK-198 §1): **permissions are a security
boundary** (read/edit access, enforced server-side) and **visibility is a UX concern**
(interface decluttering, reachable via API regardless). An author chooses the surface by
the intent, and the loader routes each to the correct entity. The two never collapse into
one declaration even when they coincide on the same `(role, field)` — a field can be both
`read_only` *and* hidden, producing one `field_permission_rule` and one
`field_visibility_rule`.

---

## 3. Field-level permission surface (`permissions:`)

### 3.1 Shape

A field declares per-role read/edit access via an optional `permissions:` map keyed by
role name. This is the §12.7 "What field-level permissions would add" sketch made precise:

```yaml
entities:
  Contact:
    fields:
      backgroundCheckCompleted:
        type: bool
        permissions:
          "Mentor Administrator": { read: yes, edit: yes }
          "Mentor":               { read: no,  edit: no }

      professionalBio:
        type: text
        permissions:
          "Mentor": { read: yes, edit: read_only_until_active }   # see §3.4
```

| Key | Type | Required | Semantics |
|---|---|---|---|
| `permissions:` | map | no | Per-role field-access overrides. Keys are role names (the `name:` strings from §12.1, case-sensitive, must resolve in-batch). Absence of the whole clause = no field-level override; the field inherits the role's entity-scope default from `scope_access:` (§12.3). |
| `<role name>` | map | — | The two-key access map for one role. A role not listed inherits default (whitelist-by-omission, matching §12.3 and WTK-197 §3 "absence = no override"). |
| `read:` | `yes` / `no` | yes within a role map | Whether the role may read the field. |
| `edit:` | `yes` / `no` | yes within a role map | Whether the role may edit the field. |

### 3.2 The `(read, edit)` pair maps to the neutral `permission_level`

The author writes the two booleans EspoCRM's `fieldData` actually carries (WTK-197 §7); the
loader reduces them to the neutral `permission_level` WTK-197 §3 defines. The mapping is the
inverse of WTK-197 §7 / WTK-200 §4.2:

| `read:` | `edit:` | → `permission_level` |
|---|---|---|
| `yes` | `yes` | `read_write` |
| `yes` | `no`  | `read_only` |
| `no`  | `no`  | `no_access` |
| `no`  | `yes` | **invalid** — edit-without-read is not a representable access level; hard-reject at validation. |

The author writes `read`/`edit` rather than `permission_level` directly because the two
booleans match the target-CRM mental model and the §12.7 sketch operators have already
seen; the neutral three-value axis is an internal storage form, not an authoring vocabulary.

### 3.3 Compilation to `field_permission_rule`

Each `(field, role)` entry compiles to exactly one `field_permission_rule` record
(WTK-197 §8 shape):

- `field_permission_rule_role` ← the resolved Role (`ROL-NNN`).
- `field_permission_rule_target_field` ← the resolved field (`FLD-NNN`), carrying its
  owning-entity context — the field is identified by `(entity, field)`, exactly as the
  containing `fields:` entry already fixes both (WTK-198 §2.2).
- `field_permission_rule_permission_level` ← the §3.2 reduction.
- `field_permission_rule_name` ← a generated human label, e.g. `Contact.backgroundCheckCompleted — Mentor` (the deterministic shape is a Develop-phase detail; the contract is that it is non-empty and stable).
- `field_permission_rule_status` ← `candidate` on first authoring (WTK-197 §4.1 default); the propose→confirm gate is the human review, not a YAML keyword (§6).
- `field_permission_rule_deployment_status` ← `not_deployed` (WTK-197 §4.2 default); the deploy process is its only other writer (WTK-200 §5).

**One rule per `(role, field)`** is the same atomization WTK-198 §1 makes for visibility and
WTK-197 invariant §6.3 enforces for permissions: a field with overrides for three roles is
three records, never one record with a role list. The program file's nested map is the
*compact authoring form*; the flat per-(role, field) record is the *storage form*.

### 3.4 Conditional edit — handled by the existing condition surface, not a new one

§12.7's MR-MC-AC-002 pattern ("Mentor may edit `professionalBio` only when their own
`mentorStatus` is `Active`") is a *state-dependent* permission. WTK-197 §3 / invariant §6.4
are explicit that `field_permission_rule` carries **no condition** — it is an unconditional
`(role, field) → level`. Conditional behaviour is therefore **not** expressed in the
`permissions:` clause. It is expressed where the schema already expresses
condition-gated editability: a `requiredWhen:`/`visibleWhen:`-style condition on the field
(Section 11 / Categories 3–5), which compiles to the existing `rule` (`RUL-NNN`) construct
(WTK-197 §3 names `rule`/`visible_when` as the conditional home).

Concretely, the unconditional floor goes in `permissions:` (e.g. Mentor `read: yes,
edit: no`) and the conditional grant is a separate condition clause. The
`read_only_until_active` token shown in §3.1 is **illustrative of intent, not literal
syntax** — at validation it is rejected inside `permissions:` (only `yes`/`no` are valid
booleans there) with an error pointing the author to the condition surface. This is called
out as the one place an author is most likely to over-reach the clause's purpose; the
design deliberately keeps `permissions:` unconditional to match the entity it compiles into.

---

## 4. Role-aware visibility surface (existing §12.5, pinned to `field_visibility_rule`)

This surface is **already shipped** in v1.3 (`app-yaml-schema.md` §12.5). This slice does
not add syntax; it pins how the two existing forms compile into `field_visibility_rule`
records (WTK-198) so the Develop phase has a deterministic reduction.

### 4.1 `role:` leaf clause (§12.5.1) → `field_visibility_rule`

A `role:` clause inside a field-level or panel-level `visibleWhen:` (the only contexts
§12.5.1 permits) names a viewing role and an operator (`equals`/`notEquals`/`in`/`notIn`).
The reduction to atomic `(role, field) → visible?` rows:

| Clause form | Compiles to |
|---|---|
| `{ role: equals, value: R }` on field F | one `field_visibility_rule` (`visible: true`) for `(R, F)`. |
| `{ role: in, value: [R1, R2] }` on field F | one rule (`visible: true`) per role, for `(R1, F)` and `(R2, F)`. |
| `{ role: notEquals, value: R }` / `{ role: notIn, value: [...] }` on field F | one rule (`visible: false`) per *named* role — the clause hides the field from those roles. The complement (roles not named) keeps default visibility and produces no row, matching WTK-198 §2.1 "a rule is only ever authored to change the default." |
| panel-level `visibleWhen:` with a `role:` clause | one rule per `(role, field)` for **every field the panel contains**, since hiding the panel hides its fields — the loader expands the panel to its field set (the field membership is known from the same layout block). |

**Mixed `role:`/`field:` compound clauses** (§12.5.1 "Mixing role and field clauses") are
the open edge: a `visibleWhen:` of `any: [ {role: in, ...}, {field: mentorStatus, ...} ]`
is *role-aware AND record-state-aware*. The `field_visibility_rule` entity is unconditional
`(role, field) → visible?` (WTK-198 §2.1 — no condition axis). The reduction therefore
**captures only the role dimension** into `field_visibility_rule` records and leaves the
record-state dimension to the existing condition `rule` (`RUL-NNN`) it already compiles
into. The two coexist on the same field exactly as a permission floor and a conditional
grant coexist in §3.4. This decomposition — role part → `field_visibility_rule`, condition
part → `rule` — is flagged for the WSK-166 reconciliation (§8) because it is the one case
where a single authored clause spans two stored entities.

### 4.2 `forRoles:` layout variant (§12.5.2) → `field_visibility_rule`

A `layout.{detail,list}` expressed as `forRoles:` variants gives different roles
structurally different field sets. The reduction: for each variant, the fields **present in
that variant but absent from another role's variant** are the fields whose visibility
differs by role. The loader compiles, per role R covered by variant V:

- For each field F that appears in V: no row needed if F appears in *every* role's variant
  (visible to all — default), one `(R, F) visible: true` row only where F is absent from at
  least one other variant (i.e. F is role-differentiated).
- For each field F absent from V but present in another role's variant: one
  `(R, F) visible: false` row.

The §12.5.2 **coverage rule** (every role in exactly one variant; no unmatched, no
doubly-matched) is a *pre-existing loader guard* and a precondition of this reduction — it
guarantees each role resolves to exactly one field set, so the per-role diff is
well-defined. This slice does not restate or change that guard; it relies on it.

### 4.3 Deploy reality is unchanged and honest

Per DEC-243 / §12.5 "Deploy Support" / WTK-198 §4, role-aware visibility is `not_supported`
at deploy on EspoCRM 9.x. The compiled `field_visibility_rule` records are still created and
traced — they are the durable, audit-able record of intent — and parked at
`deployment_status = not_supported` by the deploy process (WTK-200 §4.2). The **program-file
surface is therefore deploy-honest by construction**: it captures the author's full intent,
the loader compiles it to records, and the deploy outcome (`not_supported` until a v1.4
mechanism lands) is recorded against those records rather than swallowed. The authoring
format does not change when the platform gains a deploy path — only the process does
(WTK-198 §5).

---

## 5. Permission presets (`permissionPresets:`) — optional authoring shorthand

§12.7 "What permission presets would add" sketches a top-level `permissionPresets:` block
of named bundles so a field can reference a preset instead of repeating per-role maps. This
slice specifies it as **pure authoring sugar that expands before compilation** — a preset
introduces no new entity and no new stored concept:

```yaml
permissionPresets:
  admin-only:
    "Mentor Administrator": { read: yes, edit: yes }
    "Mentor":               { read: no,  edit: no }

entities:
  Contact:
    fields:
      backgroundCheckCompleted:
        type: bool
        permissions: { preset: admin-only }     # expands to the bundle above
```

- A field's `permissions:` may be either the inline per-role map (§3.1) **or** a single
  `{ preset: <name> }` reference — not both (hard-reject if mixed).
- `preset:` must resolve to a `permissionPresets:` key declared in the same batch
  (cross-file resolution via `ProgramContext`, parallel to role-name and field-name
  resolution). Unresolved preset name → hard-reject.
- The loader **expands** a `preset:` reference to its per-role map *before* the §3.3
  compilation, so a preset produces exactly the same `field_permission_rule` records the
  inline form would. Presets leave no trace past load time — they are not a stored entity,
  not referenced by the rule records, and never reach the deploy process.

Presets are **deferrable within this slice** (§12.7 notes they are valuable only once
field-level permissions exist, and the MR pilot's two AC items can ship without them). The
recommendation (§8) is to land the inline `permissions:` clause first and presets as a
fast-follow once authoring volume justifies the deduplication; the design is specified here
so the Develop phase need not redesign it.

---

## 6. The confirm gate is review, not a YAML keyword

Both rule entities default a freshly-authored rule to `status = candidate` (WTK-197 §4.1,
WTK-198) and require `status = confirmed` before deploy (WTK-197 invariant §6.1, WTK-200 §2
"Confirmed-before-deploy"). The program file is the *authoring* act — it produces
`candidate` records. **There is no `status:`/`confirmed:` keyword in the program-file
surface**: an author cannot self-confirm a rule by typing a field, because confirmation is
the human-review gate (`CLAUDE.md`, "human-reviewed and approved, never by editing the
status field"; the requirements-provenance approving-decision path). The program file
declares intent; promotion `candidate → confirmed` happens through the review surface, not
the YAML. This keeps the authoring format incapable of bypassing the gate, which is the
correct security posture for a file that grants and restricts access.

This is the most important boundary of the authoring surface and is stated explicitly so the
Develop phase does not add a convenience `confirmed: true` key that would defeat it.

---

## 7. Validation rules (handed to the Develop phase)

The loader/validator (Develop phase) must enforce, at pre-flight, hard-reject on failure
(consistent with the existing `validate_program()` discipline — a file with any error is
excluded from the batch, the rest run; `CLAUDE.md`, "YAML Schema Rules"):

1. **Role-name resolution.** Every role name in a `permissions:` map key, a `role:` clause
   `value`, or a `forRoles:` list must resolve to a `roles:` entry in the batch (§12.1),
   case-sensitive, via `ProgramContext` (the same cross-file resolution §12.5/§12.6 already
   use). Unresolved → reject.
2. **Field resolution.** The field a `permissions:` clause attaches to must exist in its
   entity (already guaranteed — it *is* a `fields:` entry); a `role:` clause's host field
   and a `forRoles:` variant's listed fields resolve against the batch field set
   (`ProgramContext`), exactly as §11/§12.5.1 validation already resolves them.
3. **`read`/`edit` vocabulary.** Only `yes`/`no` (and their quoted/bare YAML-1.1 forms,
   normalized as §12.3 does) inside a `permissions:` role map. The `read: no, edit: yes`
   combination is rejected (§3.2). No condition expressions inside `permissions:` (§3.4) —
   reject with a pointer to the condition surface.
4. **Preset integrity.** `permissions:` is *either* inline *or* `{ preset: <name> }`, never
   both; `preset:` resolves to a declared `permissionPresets:` key (§5).
5. **`role:` clause context and operator restrictions are pre-existing** (§12.5.1: only
   `visibleWhen:`; only `equals`/`notEquals`/`in`/`notIn`). This slice does not relax them.
6. **`forRoles:` coverage is pre-existing** (§12.5.2: every role in exactly one variant).
   This slice does not relax it.
7. **No contradictory permission for one `(role, field)`.** Two `permissions:` entries that
   resolve to conflicting `permission_level`s for the same `(role, field)` across the batch
   (e.g. a duplicate field declaration in two files) is the authoring-side counterpart of
   WTK-197 invariant §6.3 and is rejected at load, before any record is written.

**Whitelist-by-omission** is preserved throughout (§12.3, WTK-197 §3): a field with no
`permissions:` clause, or a role absent from a field's clause, means *no override* — the
role's entity-scope default applies. The surface only ever *changes* a default, never
restates it, mirroring WTK-198 §2.1's modeling choice on the visibility side.

---

## 8. Open questions / for the WSK-166 reconciliation

* **Compound `visibleWhen:` spanning two entities (§4.1).** A mixed `role:`/`field:` clause
  decomposes into a `field_visibility_rule` (role part) *and* a `rule` (`RUL-NNN`, condition
  part). This is the one authored construct that compiles into two stored entities. Confirm
  at reconciliation that the deploy process (WTK-200) and audit round-trip (PRJ-027) treat
  the pair coherently, and that a round-trip from records back to YAML re-emits one clause,
  not two.
* **Presets in-scope-now vs. fast-follow (§5).** Recommendation: inline `permissions:`
  first, `permissionPresets:` as a follow-on. Decide at reconciliation whether the first
  Develop slice includes presets.
* **Generated rule names (§3.3).** The deterministic shape of
  `field_permission_rule_name` / `field_visibility_rule_name` is left to Develop; the
  contract is non-empty, stable, and human-legible. Flagged only so two slices don't invent
  two schemes.
* **Schema-spec amendment.** This surface should fold into `app-yaml-schema.md` — formalizing
  §12.7 and cross-linking §12.5 to the rule entities — at the schema spec's next revision.
  That edit (and its revision-number bump) is a Develop-phase deliverable, per the §12.7
  "Naming note"; this design fragment is the source for it, not the edit itself.
* **`deployment_status` vocab reconciliation.** Inherited from WTK-200 §8 — the two rule
  entities propose different `deployment_status` sets; the program-file surface is agnostic
  to which set wins (it never writes `deployment_status`), but the reconciliation should
  settle it before Develop so the audit round-trip re-emits consistently.

---

## 9. Out of scope for this slice

- The `field_permission_rule` and `field_visibility_rule` entities themselves — WTK-197,
  WTK-198. This slice consumes their field/status contracts and compiles YAML into them; it
  does not define them.
- The Role persona and rule→role scoping associations — WTK-199.
- The `deploy_security_configuration` process that reads the compiled rules, deploys them,
  verifies them, and writes `deployment_status` — WTK-200.
- The actual loader, validator, `ProgramContext` extension, condition-expression context
  flags, and any amendment to `app-yaml-schema.md` — the Develop phase (WSK-167). §2's
  surface-to-entity routing, §3's `permissions:` clause shape and `(read,edit) →
  permission_level` mapping, §4's §12.5-to-`field_visibility_rule` reduction, §5's preset
  expansion semantics, §6's no-self-confirm boundary, and §7's validation rules are the
  binding contract handed to that phase.
- Build authorization. Turning this authoring-surface design into loader/validator code
  requires its own confirmed requirement + implementing PI per the governance precondition
  (`CLAUDE.md`, "Governance is a precondition, not a postscript"). REQ-254 authorizes the
  design; the implementing PI for the build is a Develop-phase concern.
