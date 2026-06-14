# PRJ-027 — Multi-Instance CRM Connection, Audit & Inventory

**Status:** Design pass (PI-184). Requirements queued for human Review-panel approval; no code until they clear.
**Project:** PRJ-027 (sibling to PRJ-025 publish/push and PRJ-024 round-trip completeness).
**Provenance root:** SES-175 / CNV-082 → TOP-091. Decisions: DEC-426, DEC-427, DEC-428.
**Author:** Claude Code design session, 2026-06-14.

---

## 1. Goal

Make the V2 database a **multi-instance CRM design hub**. An engagement defines one or
more **instances**, each connected to a live CRM system. The user can:

- **Audit (pull)** any instance to reverse-engineer its structure into a single
  canonical, engine-neutral design **inventory** held in V2.
- See, for every design object, **which instances contain it** and whether it is
  **present, drifted, or absent** in each.
- **Publish (push)** any subset of the canonical design to any target instance —
  audit instance #1, push the structure to instance #2 (sandbox), then #3
  (production), and so on.

Audit and publish are the two directions over one shared inventory. This document
defines the pull side and the inventory; the push side is PRJ-025's adapter
framework, consumed across a defined seam.

## 2. Relationship to neighboring projects

| Project | Owns | Direction |
|---|---|---|
| **PRJ-027** (this) | Instance entity + EspoCRM client in V2; audit/pull/reconcile; canonical inventory + per-instance membership/drift | Pull |
| **PRJ-025** | Engine-neutral design → pluggable adapters; generate + apply engine-specific config | Push |
| **PRJ-024** | Audit-to-deploy round-trip completeness (gap closure) | Reconciled against this inventory rather than duplicated |

Per **DEC-426**, PRJ-027 is a *sibling* of PRJ-025, not an umbrella absorbing it.
The two share one design model; ownership is split by direction.

## 3. The instance entity

A new first-class, engagement-scoped entity (identifier `INST-NNN`).

| Field | Notes |
|---|---|
| `instance_identifier` | `INST-NNN`, composite PK with `engagement_id` |
| `instance_name` | Human label (e.g. "CBM sandbox", "CBM production") |
| `instance_vendor` | `espocrm` at launch; the value that selects the adapter/introspection driver. Adapter seam for HubSpot etc. later |
| `instance_url` | Base URL of the live CRM |
| `instance_role` | `source` (read/audit only), `target` (write/publish only), or `both` — mirrors V1 `InstanceRole` |
| `instance_auth_method` | e.g. `api_key`, `hmac` |
| secret references | Opaque `crmbuilder:{uuid}` refs into the OS keyring — **never plaintext columns**. Reuses the V1 `automation/core/secrets.py` pattern |
| standard lifecycle | `created_at`, `updated_at`, `deleted_at` (soft delete) |

End-to-end build: model + repository + REST router + dialect-aware migration (SQLite
`migrations/` and Postgres `migrations/pg/`) + `change_log` and `refs` CHECK
extensions + vocab additions + a read/write desktop panel under the sidebar.
This is **PI-186**.

## 4. The canonical inventory

The inventory is the engine-neutral design superset across all audited instances.

Per **DEC-428** (phased scope), the first phase covers **entities, fields, and
relationships**, reusing and extending V2's existing `entity` and `field` records as
the engine-neutral design source. This is consistent with PRJ-025's
*derive-don't-store + scoped overrides* principle: the inventory holds neutral design
intent, not raw engine mechanics. Net-new design families — layouts, then
roles/teams/security, then filtered tabs — are explicit later phases.

The key change to the existing design records is that they become **multi-instance
aware** via the membership join (§5) rather than implicitly belonging to a single
target.

## 5. The instance_membership join (drift model)

Per **DEC-427**, "which instances contain this object" is a **per-(object, instance)
join**, not a tag list on the object.

One `instance_membership` row per (design-object, instance):

| Field | Notes |
|---|---|
| design-object reference | the canonical entity/field/relationship the row is about |
| `instance` reference | the `INST-NNN` it describes |
| `state` | `present` (matches canonical), `drifted` (exists but differs), `absent` (not in this instance) |
| `override` | optional narrowly-scoped per-instance override payload (the engine-/instance-specific deviation, kept sparse) |
| `last_audited_at` | when this state was last observed |
| audit provenance | edge to the deposit/audit event that wrote the state |

This makes drift and per-instance overrides first-class, which the
audit-one/publish-to-another flow requires. The publish side reads this join to
decide what to push to which target. The join + the entities/fields/relationships
reconcile is **PI-185**.

## 6. Reconcile algorithm (the central engineering challenge)

Audit pulls **concrete CRM-specific** structure (for EspoCRM: c-prefixed field/entity
names, layout panels and rows, dynamic logic, role ACL scope matrices, filtered-tab
report filters). The inventory stores **engine-neutral design + sparse overrides**.
Reconcile is the mapping between them:

1. **Introspect** the source instance via the ported EspoCRM client (§7) — scopes,
   entity fields, links, layouts, i18n, client defs, report filters, teams, roles.
2. **Normalize** concrete structure to engine-neutral form using the ported
   `audit_utils` catalogs and classifiers (strip c-prefix, classify
   custom/native/system, drop system fields/scopes).
3. **Match** each normalized object against the canonical inventory (by neutral
   identity). Three outcomes:
   - no canonical match → create a canonical design object; mark membership `present`.
   - canonical match, identical → mark membership `present`.
   - canonical match, differs → mark membership `drifted`; capture the deviation as
     a sparse per-instance `override`.
4. **Absence** — canonical objects with no match in this instance get membership
   `absent` for this instance.
5. **Provenance** — every state write links to the audit/deposit event.

Re-running an audit is idempotent: it recomputes membership state and refreshes
overrides; it does not duplicate canonical objects.

This re-homes the V1 `audit_manager` discovery pipeline as a *reconcile-into-inventory*
routine. Its output is DB records + membership, **not** YAML emission (YAML becomes a
render produced by PRJ-025 on publish).

## 7. Supporting structures ported from V1 (PI-187)

Ported into `crmbuilder_v2/` with tests, as the introspection capability (no reconcile
logic yet — that is PI-185):

- **EspoCRM REST client** — `api_client.py` discovery + security endpoints:
  `get_all_scopes`, `get_entity_field_list`, `get_all_links`, `get_layout`, `get_i18n`,
  `get_client_defs`, `list_report_filters`, `get_teams`, `get_roles`.
- **`audit_utils` catalogs** — `SYSTEM_FIELDS`, `NATIVE_PERSON_FIELDS` /
  `NATIVE_COMPANY_FIELDS` / `NATIVE_EVENT_FIELDS` / `NATIVE_BASE_FIELDS`,
  `_SYSTEM_SCOPES`, and the c-prefix strip/classify helpers.
- **`native_entity_types`** — native-entity → base-type mappings.
- **Keyring secret-storage pattern** — reused by the instance entity (PI-186).

## 8. Publish handoff to PRJ-025 (PI-188)

PI-188 surfaces the inventory + per-instance membership/drift in the desktop app
(which objects exist in which instances, what has drifted) and defines the **handoff
contract** PRJ-025 consumes: given a chosen subset of canonical design objects and a
target `INST-NNN`, PRJ-025 generates the engine-specific artifact (its adapters) and
applies it (the V1 Configure/apply engine — `field_manager`, `layout_manager`,
`relationship_manager`, `role_manager` — re-homed under PRJ-025). PI-188 closes the
first-phase entities/fields/relationships pull→push round-trip.

## 9. Phased scope & planning items

| PI | Title | Depends on |
|---|---|---|
| **PI-184** | Architecture & design pass (this doc) | — |
| **PI-186** | Instance entity end-to-end | PI-184 |
| **PI-187** | Port EspoCRM client + audit catalogs into V2 | PI-184 |
| **PI-185** | instance_membership join + audit-reconcile (entities/fields/relationships) | PI-186, PI-187 |
| **PI-188** | Inventory/drift desktop surface + PRJ-025 publish handoff | PI-185 |

Deferred follow-on phases (new PIs at the time): layouts → roles/teams/security →
filtered tabs.

## 10. ADO note

PI-184 (this design + requirements) is **human-led**: its founding requirements must
clear the Requirements Review panel (human sign-off) before any build. PI-186…188 are
ADO-runnable build PIs after approval — each decomposes into its own delivery-phase
Workstreams via the ADO decomposer; the PM tier dispatches them in `blocked_by` order
(already wired). ADO is currently paused; this is structure, not a launch.

## 11. Founding requirements (queued for review)

Authored as `requirement` records under TOP-091, origin `ai_derived`, status
`candidate`, traced to CNV-082. They confirm only via an approving decision once Doug
signs off in the Review panel.

1. An engagement can define one or more CRM-connected instances, each identifying the
   CRM system it connects to and its role: a source to read from, a target to write
   to, or both.
2. Connection secrets for an instance are stored securely outside the database and
   referenced indirectly; secret values are never held in plaintext columns.
3. Auditing a connected source instance reads its structure and reconciles it into a
   single canonical, engine-neutral design inventory shared across the engagement.
4. The canonical inventory is a superset of design objects across all audited
   instances, and each design object records which instances contain it.
5. For each design object and each instance, the inventory records whether the object
   is present, has drifted from the canonical design, or is absent in that instance.
6. Concrete system-specific structure discovered during an audit is mapped into
   engine-neutral design plus narrowly scoped per-instance overrides, rather than
   stored as raw engine mechanics.
7. Any design object in the canonical inventory can be selected for publishing to any
   target instance.
8. The inventory, and each object's per-instance presence and drift, are visible to
   the user.
9. The first delivered capability covers entities, fields, and relationships
   end-to-end — audit then publish — with layouts, roles and teams, and filtered views
   delivered as later additions.

## 12. Open questions

- **Canonical object identity across instances** — what neutral key matches "the same
  field" across two instances when names differ by engine convention? (Reconcile §6
  step 3 depends on this; to be settled in PI-185 design.)
- **Override granularity** — how fine-grained is a per-instance override (whole object
  vs per-attribute)? Leaning per-attribute to keep overrides sparse.
- **Relationship representation** — relationships as first-class inventory objects vs
  attributes of entities; affects membership rows for relationships.
