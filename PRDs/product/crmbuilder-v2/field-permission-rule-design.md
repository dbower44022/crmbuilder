# `field_permission_rule` — Design Model

> Status: design surface (v(N+1)). One of the per-entity design fragments
> authored under workstream **WSK-166** ("Security rule data model & process
> design") from **REQ-254** — "Deploy role-based field visibility and
> field-level permissions". This fragment is the access-area design for the
> **`field_permission_rule`** entity only (WTK-197). Its siblings:
> `field_visibility_rule` (WTK-198), the Role persona + rule→role scoping
> associations (WTK-199), the `deploy_security_configuration` process and its
> deploy associations (WTK-200), and the program-file schema (WTK-201). No
> code, schema, or migration is produced here — that is a later Development
> workstream gated on its own confirmed requirement + implementing PI.

## Revision Control

| Version | Date | Author | Change |
|---|---|---|---|
| v0.1 | 2026-06-22 | ADO Area Specialist (access, WTK-197) | Initial design surface for `field_permission_rule`. |

## 1. Purpose

`field_permission_rule` is a composite design construct — a sibling of the
existing `rule` (`RUL-NNN`) design record — that declares **the access level a
given role has to a given field**, captured in the engine-neutral design model
so it can be deployed to the target CRM automatically rather than configured by
hand. It closes the half of REQ-254 covering *field-level permissions*; its
sibling `field_visibility_rule` (WTK-198) closes the *role-aware visibility*
half.

This entity exists because the engine-neutral design model v0.1 explicitly
deferred it: `engine-neutral-design-model-and-adapters.md` §12 lists
"**Roles / field-level permissions** (EspoCRM §12) — out of scope for the
design-model v0.1; revisit." This is the revisit.

It is a **design record**, not a runtime permission check: it states the
intended permission so an adapter can render it into the target engine's
security configuration, and so verification can confirm the rendered state
matches the intent.

## 2. Position in the design model

Per `engine-neutral-design-model-and-adapters.md` §8 (composite design
constructs), `field_permission_rule` joins `association`, `rule`, `dedup_rule`,
and `view` as a neutral record type rendered by the adapter layer. It differs
from the existing `rule` in two ways:

* `rule` carries a neutral **condition AST** and a required/visible/valid
  **effect** — it gates a field or entity by data conditions. A
  `field_permission_rule` carries no condition: it is an unconditional
  **(role × field) → permission level** declaration.
* `rule` scopes itself to a design *subject* (a field or an entity). A
  `field_permission_rule` scopes itself to a **role** (the security principal)
  *and* a **target field** (the protected attribute) together.

It therefore gets its own record type rather than overloading `rule_effect`.

## 3. Permission semantics

A `field_permission_rule` answers one question: *what may this role do with
this field?* The neutral `permission_level` axis has three mutually exclusive
values, ordered from most to least access:

| `permission_level` | Meaning |
|---|---|
| `read_write` | The role may read and edit the field. |
| `read_only` | The role may read the field but not edit it. |
| `no_access` | The field is hidden from the role entirely (no read, no edit). |

These are the engine-neutral access levels; §7 maps them onto each backend.
Absence of a rule for a (role, field) pair means *no override* — the target
CRM's default field permission for that role applies. A rule is written only to
*restrict or grant* away from default.

## 4. Lifecycle — two orthogonal axes

Like other status-bearing design records (e.g. `test_spec`, which carries a
design lifecycle plus an independent execution-outcome axis), a
`field_permission_rule` carries **two orthogonal status axes**:

### 4.1 Design lifecycle (`status`)

The standard three-status propose-verify gate shared by every design entity
(`domain`, `entity`, `field`, `rule`, …): `candidate → confirmed | deferred`,
with `rejected` reachable from `candidate`/`deferred` only, and a one-way gate
out of `candidate` (once confirmed, never regress to candidate). New rows
default to `candidate`. This governs whether the *design intent* is agreed.

### 4.2 Deployment status (`deployment_status`)

An independent axis tracking whether the confirmed intent has been applied to —
and still matches — the target CRM. This mirrors the `instance_membership`
present/drifted/absent vocabulary, adapted to a per-rule deploy outcome:

| `deployment_status` | Meaning |
|---|---|
| `not_deployed` | The rule has never been pushed to the target (the default). |
| `deployed` | Last deploy succeeded and post-deploy verification confirmed the rule is active in the target. |
| `drifted` | The rule was deployed but a later audit found the target's field permission no longer matches the design. |
| `failed` | The last deploy or verification attempt failed. |

The two axes are independent: a rule may be `confirmed` (design agreed) yet
`not_deployed` (not yet pushed); only a `confirmed` rule is eligible to deploy.
The `deploy_security_configuration` process (WTK-200) is the writer of
`deployment_status`; the audit/drift path (PRJ-027) flips `deployed → drifted`.

## 5. Scoping to a role and a field

The rule is anchored to exactly one **role** and one **target field**:

* **role** — a `ROL-NNN` reference to the engine-neutral Role
  (`roles` table / `/roles`). The rule applies to records seen through this
  role. The *association* semantics of the rule→role scoping (cardinality,
  cascade on role delete, naming) are owned by **WTK-199**; this fragment only
  declares that the column exists and references a live role.
* **target_field** — a `FLD-NNN` reference to the protected field
  (`fields` table / `/fields`).

Following the established `rule` pattern (DEC-046 / `models.py` Rule), both
references are carried as **plain prefixed-identifier string columns** validated
at the access layer (exists, is live, correct type) at write time — *not* as
`refs` edges. This matches how `rule_subject_identifier` resolves its `FLD-NNN`
subject and keeps the security-rule records queryable by a simple indexed
column rather than a graph traversal. (If WTK-199 instead specifies the rule→
role scoping as a vocab `refs` edge, the `role` reference here defers to that
decision; the `target_field` column stays a plain column either way.)

## 6. Invariants

1. **Confirmed-before-deploy.** A rule must be `status = confirmed` before
   `deployment_status` may leave `not_deployed`. The deploy process refuses a
   `candidate`/`deferred`/`rejected` rule.
2. **Live subjects.** Both `role` and `target_field` must resolve to live
   (non-soft-deleted) records of the correct type at write time, exactly as
   `rule` validates its subject.
3. **One permission level per (role, field).** A given role has at most one
   live `field_permission_rule` for a given field — two conflicting levels for
   the same pair is a validation error (uniqueness on
   `(role, target_field)` among non-deleted rows). The deploy process therefore
   never has to reconcile contradictory intents for one cell.
4. **No condition.** Unlike `rule`, a `field_permission_rule` carries no
   condition AST; permission is unconditional. Conditional visibility is the
   `field_visibility_rule` / `rule` (`visible_when`) concern, not this one.
5. **Soft-delete round-trip.** Standard `deleted_at` soft-delete with restore,
   as every design record.

## 7. Dual-engine mapping

Following the §6/§7/§8 dual-engine mapping convention of the engine-neutral
design doc:

| Neutral | EspoCRM | HubSpot-style object model |
|---|---|---|
| `field_permission_rule` (role, target_field, permission_level) | A `fieldLevelData` entry in the Role's scope-access matrix: per (entity, field) a `{read, edit}` pair. | Per-field property-level permission within a permission set / role. |
| `permission_level = read_write` | `read: yes`, `edit: yes` | property readable + editable |
| `permission_level = read_only` | `read: yes`, `edit: no` | property readable, not editable |
| `permission_level = no_access` | `read: no`, `edit: no` | property hidden |
| `deployment_status` | derived from post-deploy read-back of the Role's `fieldLevelData` vs. the design intent | same, against the permission set |

The disposition (per §3 of the engine-neutral doc) is **neutral**: the rule is
authored once in neutral form and the adapter compiles it to each engine's
field-permission shape. The EspoCRM field-permission write path is the
historically-deferred §12 mechanism (REQ-128/129 in PRJ-024); whether that path
exists via REST or needs a metadata/disk write is a **Development / automation**
concern (WTK-200), not settled here.

## 8. Proposed record shape

Mirrors the `source-mapping-design.md` §8 record-shape convention and the
existing `Rule` model's parent-prefix column naming (DEC-046). Proposed
identifier prefix: **`FPR-NNN`** (`field_permission_rule`), pending the
identifier-allocation review at build time; not yet reserved.

```
field_permission_rule
  field_permission_rule_identifier        PK, "FPR-NNN" (^FPR-\d{3}$)
  field_permission_rule_name              human label, non-empty
  field_permission_rule_role              ROL-NNN  → roles (live, correct type)
  field_permission_rule_target_field      FLD-NNN  → fields (live, correct type)
  field_permission_rule_permission_level  read_write | read_only | no_access
  field_permission_rule_status            candidate | confirmed | deferred | rejected   (default candidate)
  field_permission_rule_deployment_status not_deployed | deployed | drifted | failed    (default not_deployed)
  field_permission_rule_description        TEXT, nullable
  field_permission_rule_notes              TEXT, nullable
  field_permission_rule_created_at         DATETIME
  field_permission_rule_updated_at         DATETIME
  field_permission_rule_deleted_at         DATETIME, nullable
```

Indexes (mirroring `rules`): on `status`, on `deployment_status`, on
`(role, target_field)` (also the uniqueness anchor for invariant 6.3 among
live rows), and on `deleted_at`.

CHECK constraints (mirroring `rules`): identifier format, and membership of
`permission_level`, `status`, `deployment_status` in their vocab sets.

## 9. Proposed vocabulary additions

To be added to `access/vocab.py` at build time (Development workstream), named
to match the existing `RULE_*` families:

```python
FIELD_PERMISSION_LEVELS = frozenset({"read_write", "read_only", "no_access"})

FIELD_PERMISSION_RULE_STATUSES = frozenset(
    {"candidate", "confirmed", "deferred", "rejected"}
)
FIELD_PERMISSION_RULE_STATUS_TRANSITIONS = {  # same one-way propose-verify gate
    "candidate": frozenset({"confirmed", "deferred", "rejected"}),
    "confirmed": frozenset({"deferred"}),
    "deferred": frozenset({"confirmed", "rejected"}),
    "rejected": frozenset(),
}

FIELD_DEPLOYMENT_STATUSES = frozenset(
    {"not_deployed", "deployed", "drifted", "failed"}
)
```

`FIELD_PERMISSION_LEVELS` and `FIELD_DEPLOYMENT_STATUSES` are deliberately
shared with `field_visibility_rule` (WTK-198) where applicable — the deployment
axis is identical for both security-rule types, so WTK-198 should reuse
`FIELD_DEPLOYMENT_STATUSES` rather than define its own.

## 10. Associations (handoff to siblings)

This entity participates in these associations, **specified elsewhere** in the
same workstream to keep area boundaries clean:

* `field_permission_rule → role` — the rule→role scoping. Owned by **WTK-199**.
* `field_permission_rule → target_field` — declared here (§5, §8) as the
  protected-field reference.
* `deploy_security_configuration → field_permission_rule` — the deploy process
  reads confirmed rules and writes `deployment_status`. Owned by **WTK-200**.
* program-file declaration of a `field_permission_rule` — input format owned by
  **WTK-201**.

## 11. Open questions / deferred

* **Identifier prefix.** `FPR-` is proposed but not reserved; confirm against
  the live prefix registry at build time (no existing collision found:
  RUL/ROL/VEW/ENT/FLD/DOM are taken; FPR is free as of this writing).
* **Role-scoping as column vs. edge.** §5 carries `role` as a plain column to
  match `rule`'s subject pattern; WTK-199 may instead model the scoping as a
  vocab `refs` edge. If so, this design adopts that and drops the `role` column
  in favour of the edge — the `target_field` column is unaffected.
* **`drifted` granularity.** Whether `drifted` records which attribute drifted
  (read vs. edit) or is a single boolean-style flag is left to the PRJ-027 audit
  integration; the field-permission cell is small enough that a single
  `drifted` value is likely sufficient.
* **Build authorization.** Turning this design into an access-layer model,
  migration, repository, and REST surface requires its own confirmed
  requirement + implementing PI per the governance precondition; it is not
  authorized by this Design fragment.
