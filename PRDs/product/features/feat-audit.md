# CRM Builder — CRM Audit

**Version:** 1.2
**Status:** Implemented
**Last Updated:** 05-25-26 01:38
**Depends On:** app-yaml-schema.md, feat-fields.md, feat-layouts.md, feat-relationships.md, feat-entities.md

---

**What's New in v1.2**

- **Security audit** — Roles and Teams are discovered alongside
  entities, with `scope_access:` and `system_permissions:` per
  Section 12.1–12.4 of the YAML schema. Emitted to
  `<output_dir>/security/security.yaml`. See §2.2 and §5.4 for
  capture and output details
- **Filtered-tab audit** — EspoCRM's three-artifact filtered-tab
  pattern (Report Filter + scopes JSON + clientDefs JSON +
  i18n label patch) is reverse-engineered into structured
  `filteredTabs:` blocks in the per-entity YAML output. See
  §2.2 and §4.8
- **Entity picker** — Operators choose which entities to audit
  via a scrollable list with Select All / Select None buttons.
  Pre-flight discovery on dialog open. See §8.1
- **Section 12.5 role-aware visibility — NOT_AUDITABLE in v1.3.**
  EspoCRM 9.x Dynamic Logic has no role-condition type;
  Layout Sets bind to Teams, not Roles. The YAML schema can
  still express role-aware visibility intent (loader validates,
  audit round-trips the rest of §12). Deployment of §12.5 is
  deferred to v1.4 alongside §12.7 field-level permissions.
  See §6.4 and §10

---

## 1. Purpose

The Audit feature reads the current configuration of a live CRM instance
and produces a set of YAML program files that represent its state. This
gives teams a declarative starting point when adopting CRM Builder on an
instance that was configured manually, capturing a baseline before making
changes, or migrating configuration from one instance to another.

The output is identical in format to hand-authored program files
(see `app-yaml-schema.md`), so audited YAML can be immediately edited
and re-applied through the existing Configure engine.

---

## 2. Core Concepts

### 2.1 Source vs Target Instances

CRM Builder distinguishes between two instance roles:

| Role | Purpose | Operations Allowed |
|------|---------|-------------------|
| `source` | Read-only instance to audit | Audit |
| `target` | Instance to deploy and configure | Deploy, Configure |
| `both` | Same instance for audit and configuration | All operations |

Each instance profile carries a `role` field. Existing profiles default
to `target` when the field is introduced. Source-only instances do not
require a deployment configuration and are excluded from the Deploy and
Configure entry pickers.

All three roles use the same `InstanceProfile` model and are stored as
`{slug}.json` in `data/instances/`. The Instance panel displays a role
indicator for each entry so users can distinguish them at a glance.

### 2.2 Audit Scope

An audit discovers the following from the source instance:

| Object | What Is Captured |
|--------|-----------------|
| **Custom entities** | Entity type, labels, stream flag |
| **Custom fields** | All field properties (type, label, required, default, options, style, etc.) |
| **Native entity fields** | Custom fields added to native entities (Contact, Account, etc.) |
| **Detail layouts** | Panels, rows, tabs, field placement, dynamic logic |
| **List layouts** | Columns and widths |
| **Relationships** | Link type, link names, labels, related entities |
| **Role** *(v1.2; Section 12.1)* | Name, description, `scope_access` (per-entity access matrix), `system_permissions` (Section 12.4). Persona metadata is NOT captured (documentation-only in YAML per DEC-178; operators reattach manually after import) |
| **Team** *(v1.2; Section 12.2)* | Name, description. Team-to-user membership is not captured (runtime data per Section 12.2) |
| **Filtered tab** *(v1.2)* | Per-entity navigation tabs backed by Report Filter records. Scope name, label, filter criteria, ACL strategy. Tabs without recognizable filter criteria are captured with label and scope but no `filter:` block (operator hand-writes after import) |

System fields (`id`, `createdAt`, `modifiedAt`, `assignedUserId`,
`createdById`, compound data fields) are excluded automatically. Native
fields that exist by virtue of entity type (e.g., `firstName`,
`lastName` on Person entities) are excluded unless explicitly requested.

#### What is NOT captured

The following are intentionally outside the audit's reach in v1.3:

| Object | Reason |
|--------|--------|
| Section 12.5 role-aware visibility | EspoCRM 9.x Dynamic Logic has no role-condition type; manually-configured role-aware visibility (via Dynamic Handler JS or Layout Sets + Teams) is operator-written code, not reverse-engineerable structured metadata. Audit log emits a NOT_AUDITABLE advisory per run. Deferred to v1.4 |
| Section 12.7 field-level permissions | Deferred to v1.4 |
| Workflows | Existing v1.1 limitation; no public REST API write path |
| Saved views, duplicate-check rules | Existing v1.1 limitations |

### 2.3 Reverse Name Mapping

YAML program files use natural names with no platform prefix. The
configure engine applies the c-prefix at deployment time. The audit
reverses this:

| API Name | YAML Name | Rule |
|----------|-----------|------|
| `cContactType` | `contactType` | Strip leading `c`, lowercase next character |
| `CEngagement` | `Engagement` | Strip leading `C` from custom entity names |
| `Contact` | `Contact` | Native entity — no change |
| `firstName` | *(excluded)* | Native field on Person entity |

For entities with known name mappings (e.g., `CSessions` → `Session`),
the audit uses the inverse of the entity name map. For unknown custom
entities, it falls back to stripping the `C` prefix.

### 2.4 Output Artifacts

The audit produces two categories of output:

1. **YAML program files** — Written to
   `{project_folder}/programs/audit-{YYYYMMDD-HHMMSS}/`. One file per
   entity with custom fields, plus a `relationships.yaml` for all
   discovered relationships. Timestamped folders preserve audit history.

2. **Database records** — Entity, Field, FieldOption, Relationship,
   LayoutPanel, LayoutRow, LayoutTab, and ListColumn rows inserted into
   the client database with appropriate `is_native` flags.

---

## 3. Instance Role Management

### 3.1 Role Field

The `InstanceProfile` model gains a `role` field with three possible
values: `source`, `target`, or `both`. The field is stored in the
instance JSON file alongside existing fields.

### 3.2 Instance Dialog Changes

The Add/Edit Instance dialog includes a role selector (radio group)
below the authentication fields:

- **Source** — This instance will be audited (read-only operations)
- **Target** — This instance will receive deployments and configurations
- **Both** — This instance supports all operations

The default selection for new instances is `target` to preserve existing
behavior.

### 3.3 Instance Panel Changes

The Instance panel displays a role badge next to each instance name:

| Role | Badge |
|------|-------|
| `source` | `[SRC]` |
| `target` | `[TGT]` |
| `both` | `[S+T]` |

### 3.4 Entry Visibility by Role

| Sidebar Entry | Visible Roles |
|---------------|---------------|
| Instances | All |
| Deploy | `target`, `both` |
| Configure | `target`, `both` |
| **Audit** | `source`, `both` |
| Run History | All |
| Output | All |

When the active instance's role excludes an entry, the entry shows an
explanatory message (consistent with the never-disable-buttons pattern)
rather than being hidden or grayed out.

---

## 4. Audit Operations

### 4.1 Discovery Phase

The audit begins by querying the CRM Metadata API for all entity scopes.
Each scope is classified:

1. **Custom entity** — `isCustom == true` in scope metadata. Included
   with `action: create` in the YAML output.
2. **Native entity with custom fields** — Known entity (Contact,
   Account, etc.) that has fields with the c-prefix. Included without
   an `action` field, listing only custom fields.
3. **System entity** — Not customizable or purely internal (Preferences,
   AuthToken, ScheduledJob, etc.). Excluded from output.

### 4.2 Field Extraction

For each included entity, the audit fetches all field definitions and
classifies each field:

| Classification | Rule | Action |
|----------------|------|--------|
| Custom field | Name starts with `c` + uppercase, or `isCustom == true` | Include, strip c-prefix |
| Native field | Exists by default on the entity type | Exclude (unless option enabled) |
| System field | In the system fields exclusion set | Always exclude |

**System fields exclusion set:**

```
id, deleted, createdAt, modifiedAt, createdById, createdByName,
modifiedById, modifiedByName, assignedUserId, assignedUserName,
teamsIds, teamsNames, followersIds, followersNames,
emailAddressData, phoneNumberData, addressMap
```

**Person-type native fields** (excluded on Person entities):

```
salutationName, firstName, lastName, middleName, name,
emailAddress, phoneNumber, addressStreet, addressCity,
addressState, addressCountry, addressPostalCode, description
```

Extracted field properties map directly to the YAML field schema:

| API Property | YAML Property | Notes |
|-------------|---------------|-------|
| `type` | `type` | Direct mapping |
| `label` | `label` | May require translation API fallback |
| `required` | `required` | Boolean |
| `default` | `default` | String or null |
| `readOnly` | `readOnly` | Boolean |
| `audited` | `audited` | Boolean |
| `options` | `options` | Enum/multiEnum only |
| `translatedOptions` | `translatedOptions` | If differs from options |
| `style` | `style` | Enum/multiEnum badge colors |
| `isSorted` | `isSorted` | Enum/multiEnum |
| `displayAsLabel` | `displayAsLabel` | Enum/multiEnum |
| `maxLength` | `maxLength` | Varchar |
| `min` | `min` | Numeric types |
| `max` | `max` | Numeric types |

Properties that are documentation-only in the YAML schema (`description`,
`tooltip`, `category`, `optionDescriptions`) are not available from the
API and are omitted from audit output. Users fill these in manually.

### 4.3 Layout Extraction

**Detail layouts** are read from the Layout API and reverse-mapped:

1. Each panel's `customLabel` becomes the panel `label`
2. Row field names are reverse-mapped (strip c-prefix for custom fields)
3. `false` entries in rows (empty cells) become `null`
4. `tabBreak`, `tabLabel`, `style`, `hidden` properties are preserved
5. `dynamicLogicVisible` is reverse-mapped from the full conditionGroup
   format to the YAML shorthand (`{attribute: fieldName, value: "Value"}`)

**List layouts** are simpler: each column's field name is reverse-mapped
and its `width` is preserved.

### 4.4 Relationship Discovery

Relationships are discovered by reading all link definitions across
audited entities:

1. For each entity, fetch all links from the Metadata API
2. Classify each link by its `type` property:
   - `hasMany` with foreign `belongsTo` → `oneToMany`
   - `belongsTo` with foreign `hasMany` → `manyToOne`
   - `hasMany` with `relationName` → `manyToMany`
3. Deduplicate: each relationship appears on both participating entities.
   Track recorded pairs using sorted entity+link tuples.
4. Reverse-map entity names and link names (strip C/c-prefix as needed)
5. Recover labels from the translation system or Admin API where possible

### 4.5 YAML Generation

Each entity produces a YAML file following the `app-yaml-schema.md`
format exactly:

```yaml
version: "1.0"
content_version: "1.0.0"
description: >
  Audit snapshot of Contact captured from https://crm.example.com
  on 2026-04-14T10:30:00Z.

entities:
  Contact:
    fields:
      - name: contactType
        type: multiEnum
        label: "Contact Type"
        required: true
        options:
          - "Mentor"
          - "Mentee"
        style:
          Mentor: success
          Mentee: primary

    layout:
      detail:
        panels:
          - label: "Overview"
            rows:
              - [contactType, null]
              - [status, region]
      list:
        columns:
          - field: contactType
            width: 20
```

The relationships file collects all discovered relationships:

```yaml
version: "1.0"
content_version: "1.0.0"
description: >
  Relationships audit snapshot captured from https://crm.example.com
  on 2026-04-14T10:30:00Z.

relationships:
  - name: contactToDues
    entity: Contact
    entityForeign: Dues
    linkType: oneToMany
    link: duesRecords
    linkForeign: contact
    label: "Dues Records"
    labelForeign: "Contact"
```

**YAML output style requirements:**
- Block style for multi-line strings and descriptions
- Flow style avoided for lists (use block sequence)
- Keys ordered to match `app-yaml-schema.md` conventions
- No trailing whitespace; single newline at end of file

### 4.6 Database Record Insertion

After YAML files are written, the audit inserts corresponding records
into the client database:

| Table | Source | Key Fields |
|-------|--------|------------|
| `Entity` | Scope metadata | name, type, is_native, label_singular, label_plural |
| `Field` | Field metadata | entity_id, name, type, label, is_native, required |
| `FieldOption` | Enum options | field_id, value, label, sort_order, style |
| `Relationship` | Link metadata | entity_id, foreign_entity_id, link_type, link, link_foreign |
| `LayoutPanel` | Detail layout | entity_id, label, sort_order, tab_break, tab_label |
| `LayoutRow` | Panel rows | panel_id, sort_order, field_left, field_right |
| `LayoutTab` | Tab definitions | entity_id, label, category |
| `ListColumn` | List layout | entity_id, field_name, width, sort_order |

Records are checked for existence before insertion (idempotent).
A `ConfigurationRun` record is created with `operation: 'audit'` to
provide an audit trail.

### 4.7 Security Audit (v1.2)

The security audit step runs alongside entity/field/layout discovery
and emits a single `security/security.yaml` covering everything it
captured. It walks the source instance's roles and teams and
translates each into the schema's structured form:

- `client.get_roles()` fetches all Role records via REST
- `client.get_teams()` fetches all Team records via REST
- `AuditManager._reverse_scope_access()` translates each Role's
  `data` field — keyed by EspoCRM wire-name (e.g., `CEngagement`)
  — to YAML `scope_access` keyed by natural name (e.g.,
  `Engagement`)
- `AuditManager._reverse_system_permissions()` reads the five
  schema-managed permission columns (`assignmentPermission`,
  `userPermission`, `exportPermission`, `massUpdatePermission`,
  `portalPermission`) and translates to the schema's
  `system_permissions:` block

Three EspoCRM-only permissions on the v1.2 preservation list
(`followerManagementPermission`, `groupEmailAccountPermission`,
`dataPrivacyPermission`) are NOT captured — the schema has no
representation for them. They are preserved on subsequent deploys
(see §9.2).

Output: `<output_dir>/security/security.yaml` containing
`teams:` and `roles:` blocks. The file is only emitted when
something was captured (no empty placeholder file).

Per DEC-179, roles with empty `scope_access:` emit an
informational warning in the audit log; the role is still
emitted in YAML.

### 4.8 Filtered-Tab Audit (v1.2)

The filtered-tab audit reverse-engineers EspoCRM's three-artifact
filtered-tab pattern. For each audited entity:

1. `client.get_all_scopes()` (called once at start) enumerates
   custom tab-scopes (filter: `isCustom: true` AND `tab: true`
   AND `entity: false`)
2. `client.get_client_defs(scope_name)` per tab-scope recovers
   the entity binding and Report Filter ID
3. `client.list_report_filters(entity_wire_name)` per entity
   fetches the Report Filter records; HTTP 404 means Advanced
   Pack is not installed and the audit logs an informational
   note and continues
4. `AuditManager._reverse_where_items()` inverts the deploy
   side's `_to_where_items()` translation: EspoCRM where-items
   (with `{type, attribute, value}` shape) become parsed
   condition AST nodes; compound `and`/`or` groups become
   `AllNode`/`AnyNode`; `currentUser`/`notCurrentUser` map to
   the `$user` sentinel

Output: per-entity YAML files include a `filteredTabs:` block
when the entity has any filtered tabs.

Two limitations documented for v1.3:

- Unknown where-item types poison the entire filter — the tab is
  captured with label and scope but no `filter:` block; operator
  hand-writes after import. Better than silently dropping
  conditions and changing the operator's intent
- Relative-date tokens (Section 11) are not reverse-engineered;
  post-deploy values are absolute `YYYY-MM-DD` strings; operators
  manually convert back to relative form if desired

---

## 5. Output and Reporting

### 5.1 Output Panel Messages

The audit emits progress messages to the Output entry:

```
[AUDIT]    Discovering entities ...
[AUDIT]    Found 8 custom entities, 3 native entities with custom fields
[AUDIT]    Contact — extracting 12 custom fields ...
[AUDIT]    Contact — reading detail layout (3 panels, 14 rows)
[AUDIT]    Contact — reading list layout (8 columns)
[AUDIT]    Engagement — extracting 6 custom fields ...
[AUDIT]    Discovering relationships ...
[AUDIT]    Found 15 relationships (8 after deduplication)
[AUDIT]    Writing YAML files to programs/audit-20260414-103000/ ...
[AUDIT]    Inserting database records ...
```

### 5.2 Summary Block

```
===========================================
AUDIT SUMMARY
===========================================
Source instance         : CBM Production
Source URL              : https://crm.cbmentors.org
Audit timestamp         : 2026-04-14 10:30:00

Entities discovered     : 11
  Custom entities       :  8
  Native with customs   :  3
Custom fields extracted : 67
Detail layouts captured : 11
List layouts captured   : 11
Relationships found     :  8

YAML files written      : 12
  Entity files          : 11
  Relationship file     :  1
Database records        : 142

Output folder           : programs/audit-20260414-103000/
===========================================
```

### 5.3 Report Status Values

| Status | Meaning |
|--------|---------|
| `discovered` | Entity or relationship found in source CRM |
| `extracted` | Fields or layout successfully read from API |
| `written` | YAML file generated successfully |
| `inserted` | Database record created |
| `skipped` | System entity or field excluded by classification rules |
| `warning` | Non-fatal issue (e.g., label not found in translation API) |
| `error` | API call failed; object could not be read |

### 5.4 Security YAML Output (v1.2)

When the security audit captures any roles or teams, the audit
writes `<output_dir>/security/security.yaml`. Structure:

```yaml
teams:
  - name: Mentor Administrators
    description: Members can manage mentor onboarding
  - name: System Administrators
    description: null

roles:
  - name: Mentor
    description: Active mentors
    persona: null  # Always null on capture; operator reattaches
    scope_access:
      Engagement:
        create: true
        read: own
        edit: own
        delete: no
        stream: own
    system_permissions:
      assignment_permission: team
      user_permission: team
      export: false
      mass_update: false
      portal: false
```

---

## 6. Validation Rules

The following rules are applied during audit execution:

- Source instance must have a valid URL and credentials
- Connection to the source instance is tested before starting
- Entity names must be resolvable through the reverse name map or
  C-prefix stripping
- Fields with unrecognized types are included with a `# WARNING`
  comment in the YAML output
- Relationships referencing entities outside the audit scope are
  included but marked with a comment noting the foreign entity was
  not audited
- Output folder must not exist (timestamp ensures uniqueness); if it
  does, the audit aborts with an error rather than overwriting

### 6.4 Role-Aware Visibility (v1.2)

Section 12.5 role-aware visibility validates at parse time but is
NOT_SUPPORTED for deploy on EspoCRM 9.x:

- Field-level `visibleWhen:` containing `role:` clauses: loader
  validates against `ProgramContext.role_names`; deploy emits
  NOT_SUPPORTED for the dynamic-logic visible block (field still
  deploys without visibility control)
- Layout-level `forRoles:` variant form: loader validates the
  coverage rule (every role in `program.roles` appears in exactly
  one variant's `forRoles:`); deploy emits NOT_SUPPORTED for the
  whole layout

The MANUAL CONFIGURATION REQUIRED advisory block at the end of
each deploy run lists affected fields and layouts so the operator
can configure them manually post-deploy.

[Screenshot: `PRDs/product/features/feat-audit-v1.2-manual-config-block.png`
— terminal/log capture of a deploy run with §12.5 NOT_SUPPORTED
items in the MANUAL CONFIGURATION REQUIRED block. TODO: capture
manually.]

See `PRDs/product/app-yaml-schema.md` §12.5 "Deploy Support" for
the workaround paths available to operators (Dynamic Handler JS;
Layout Sets + Teams).

---

## 7. Error Handling

| Error | Behavior |
|-------|----------|
| Connection failure | Abort audit, display connection error message |
| Authentication failure (401) | Abort audit, suggest checking API key |
| Single entity metadata failure | Log warning, skip entity, continue |
| Single field read failure | Log warning, skip field, continue |
| Layout API failure | Log warning, omit layout section for entity, continue |
| Relationship read failure | Log warning, skip relationship, continue |
| File write failure | Abort audit, display filesystem error |
| Database insert failure | Log error, continue (YAML files already written) |

The audit follows a best-effort strategy: individual object failures
produce warnings but do not abort the entire operation. Only connection,
authentication, and filesystem errors are fatal.

---

## 8. UI Integration

### 8.1 Sidebar Entry

The Audit feature adds a new entry to the Deployment window sidebar
between Run History and Output:

```
Instances | Deploy | Configure | Run History | Audit | Output
```

The Audit entry contains:

1. **Source instance picker** — Dropdown filtered to instances with
   role `source` or `both`. Shows instance name and URL.
2. **Entity picker (v1.2)** — Scrollable list of all entities
   discovered on the active instance via a pre-flight
   `get_all_scopes()` call when the entry is first shown for that
   instance. Each entity has a checkbox (default checked). Two
   buttons above the list: **Select All** and **Select None**. When
   the operator switches to a different instance, the picker
   re-discovers from the new source. If pre-flight fails (HTTP
   error), the picker stays empty and the loading label switches
   to an error message; the audit can still run with default
   all-entities behavior.
3. **Scope options** — Checkboxes (all checked by default):
   - Include custom entity fields
   - Include native entity custom fields
   - Include detail layouts
   - Include list layouts
   - Include relationships
   - **Security (teams and roles)** *(v1.2; default checked per
     DEC-180)*
   - **Filtered tabs** *(v1.2; default checked per DEC-180)*
4. **Include native fields checkbox** — Unchecked by default. When
   checked, native fields on native entities are included in output.
5. **Start Audit button** — Initiates the audit. Follows the
   never-disable pattern: if no source instance is selected,
   clicking shows an explanatory message. If no entities are
   selected, clicking shows a "no work to do" message and does not
   launch the progress dialog.
6. **Last audit info** — Shows timestamp and output folder of the
   most recent audit for the selected source instance.

[Screenshot: `PRDs/product/features/feat-audit-v1.2-audit-entry.png`
— full Audit entry view with picker populated and all checkboxes
visible. TODO: capture manually.]

### 8.2 Progress Dialog

A modal progress dialog appears during audit execution:

- Progress bar showing entity-level progress (e.g., "Entity 4 of 11")
- Scrolling log of `[AUDIT]` messages
- Cancel button to abort the audit (best-effort cleanup of partial files)

### 8.3 Post-Audit Actions

After a successful audit, the user is offered:

- **Open output folder** — Opens the timestamped audit folder in the
  system file manager
- **View in Configure** — Switches to the Configure entry where the
  new YAML files are visible in the program list (if a target instance
  is also selected)

### 8.4 Overwrite Confirmation (v1.2)

When the operator clicks **Start Audit** and the output directory
already contains audit YAML output (any `*.yaml` at the program
root OR any `security/*.yaml` under the subdirectory), a
confirmation dialog fires per DEC-181:

> Output directory contains N existing audit YAML file(s); running
> this audit will overwrite them. Proceed?

Default focus is Cancel; the operator must explicitly choose
Proceed to continue. Cancel returns to the audit-entry view
without starting the audit.

Under the current `audit-{timestamp}` naming convention, this
dialog rarely fires in practice — only on second-runs within the
same second (timestamp collision). The check is in place for any
future move to a fixed-name output directory.

[Screenshot: `PRDs/product/features/feat-audit-v1.2-overwrite-dialog.png`
— overwrite-confirmation QMessageBox with Cancel button focused.
TODO: capture manually.]

---

## 9. Implementation Reference

All seven development phases are complete. This section documents the
final file inventory and key implementation details.

### 9.1 File Inventory

| Layer | File | Purpose |
|-------|------|---------|
| Model | `espo_impl/core/models.py` | `InstanceRole` enum (`source`, `target`, `both`) and `role` field on `InstanceProfile` |
| Model | `espo_impl/ui/instance_dialog.py` | Radio button group (Target / Source / Both) in Add/Edit Instance dialog |
| Model | `espo_impl/ui/instance_panel.py` | Role badges `[SRC]`/`[TGT]`/`[S+T]` in list, JSON serialization of `role` field |
| API | `espo_impl/core/api_client.py` | Four new methods: `get_all_scopes()`, `get_entity_full_metadata()`, `get_all_links()`, `get_language_translations()` |
| Core | `espo_impl/core/audit_utils.py` | Reverse c-prefix mapping, entity/field classification enums, system field exclusion sets |
| Core | `espo_impl/core/audit_manager.py` | `AuditManager` orchestrator — entity discovery, field/layout extraction, relationship dedup, YAML serialization |
| DB | `espo_impl/core/audit_db.py` | `insert_audit_records()` — idempotent insertion of Entity, Field, FieldOption, Relationship, LayoutPanel, LayoutRow, ListColumn records |
| DB | `automation/db/client_schema.py` | `ConfigurationRun` CHECK constraint updated to allow `'audit'` operation |
| DB | `automation/db/migrations.py` | `_client_v7` migration — rebuilds `ConfigurationRun` table for updated CHECK |
| Worker | `espo_impl/workers/audit_worker.py` | `AuditWorker(QThread)` — background thread with `output_line`, `progress`, `finished_ok`, `finished_error` signals |
| UI | `automation/ui/deployment/audit_entry.py` | `AuditEntry` sidebar widget + `AuditProgressDialog` modal |
| UI | `automation/ui/deployment/deployment_window.py` | Audit registered as 5th sidebar entry (`_IDX_AUDIT = 4`) |
| Core | `espo_impl/core/team_manager.py` *(v1.2)* | `TeamManager` CHECK→ACT for team deploy |
| Core | `espo_impl/core/role_manager.py` *(v1.2)* | `RoleManager` CHECK→ACT for role deploy, including `_preflight_scope_access` per DEC-178 |
| API | `espo_impl/core/api_client.py` *(v1.2 additions)* | `get_teams()`, `get_roles()` for audit-side discovery; `get_client_defs()`, `list_report_filters()` for filtered-tab discovery; team / role CRUD endpoints for deploy |
| DB | `automation/db/migrations.py` *(v1.2 additions)* | `_client_v15` adds `Role` / `Team` tables; `_client_v16` adds `FilteredTab` table |
| Audit | `espo_impl/core/audit_manager.py` *(v1.2 extension)* | `_discover_teams`, `_discover_roles`, `_discover_filtered_tabs`; `_reverse_scope_access`, `_reverse_system_permissions`, `_reverse_where_items` / `_reverse_where_item`; new dataclasses `RoleAuditResult`, `TeamAuditResult`, `FilteredTabAuditResult` (`LayoutVariant` lives in `models.py`) |
| Pipeline | `espo_impl/workers/run_worker.py` *(v1.2 extension)* | New Step 11 "Security" inserted between Workflows (Step 10) and Filtered tabs (renumbered Step 12); `_emit_manual_config_block` surfaces §12.5 NOT_SUPPORTED items |
| UI | `automation/ui/deployment/audit_entry.py` *(v1.2 extension)* | Entity-picker `QListWidget`, Select All / Select None, Security / Filtered tabs checkboxes, overwrite-confirmation dialog |
| UI | `automation/ui/deployment/configure_progress.py` *(v1.2 extension)* | Multi-file queue stable-sort placing security YAMLs last per Section 12.6 |
| Schema | `PRDs/product/app-yaml-schema.md` *(v1.2 patches)* | §12.5 NOT_SUPPORTED on EspoCRM 9.x (deferred to v1.4); §12.6 deploy ordering corrected to security-last |

### 9.2 Architecture Decisions

**Instance role on InstanceProfile, not a separate model.** The `role`
field was added directly to `InstanceProfile` rather than creating a
separate source-instance model. Existing JSON files without a `role`
key load as `target` — no migration script required.

**audit_db.py as a separate module.** Database insertion logic was
extracted from `AuditManager` into `espo_impl/core/audit_db.py` to
keep the manager focused on API orchestration and YAML generation.
The manager calls `insert_audit_records()` via a lazy import after
YAML files are written.

**AuditProgressDialog embedded in audit_entry.py.** Rather than a
separate `audit_progress.py` file, the progress dialog is co-located
with the entry widget since it is only used from that entry. This
matches the principle of keeping related code together.

**ConfigurationRun table rebuild for 'audit' operation.** SQLite
cannot ALTER CHECK constraints, so `_client_v7` uses the 12-step
table redefinition pattern (same approach as `_master_v3`) to rebuild
`ConfigurationRun` with the updated CHECK allowing `'audit'`.

**Deduplication via frozenset.** Relationship deduplication uses
`frozenset({entity.link, foreign.link})` to ensure each relationship
pair is recorded exactly once regardless of which side is encountered
first.

**§12.5 deploy is NOT_SUPPORTED on EspoCRM 9.x (v1.2).** EspoCRM
9.x Dynamic Logic has no role-condition type; Layout Sets bind to
Teams not Roles. Section 12.5 role-aware visibility ships at the
YAML/loader/validator/audit-passthrough surface but not at deploy.
Operators using EspoCRM 9.x configure role-aware visibility
manually via Dynamic Handler JavaScript or Layout Sets + Teams.
Deferred to v1.4 alongside §12.7 field-level permissions.

**Deploy ordering is security-LAST (v1.2).** Files declaring
`roles:` or `teams:` deploy after files declaring entities so the
scope_access pre-flight in `role_manager._preflight_scope_access`
can validate against server state. Earlier drafts of the schema
spec prescribed security-first; investigation confirmed no
write-time validation in EspoCRM (references resolve at view-time),
so the pre-flight design dictates the order. Schema §12.6
corrected at v1.2.

**Pre-flight server-state validation (DEC-178).** `role_manager`
fetches the current scope list at the start of role deploy and
validates that every `scope_access:` entity reference resolves on
the target. Roles with unresolvable references receive a clear
pre-deploy error rather than the silent-accept-or-confusing-HTTP-
error behavior EspoCRM provides at write time.

**`audit_log` removed from §12.4 (DEC-176).** The schema's earlier
`audit_log:` permission was based on an EspoCRM 8.0 column that
9.x no longer manages via Role records. Removed entirely from the
v1.3 schema rather than carrying a vestigial field.

**Three EspoCRM-only permissions preserved on PATCH (DEC-177).**
`followerManagementPermission`, `groupEmailAccountPermission`, and
`dataPrivacyPermission` are not in the v1.3 schema but exist on
the EspoCRM Role record. `role_manager` PATCH operations preserve
them rather than nulling them out — operators who configure these
manually on the target retain their settings across deploys.

**Empty-`scope_access` warning (DEC-179).** Roles captured with no
resolved scope entries (e.g., a role that grants only system
permissions) are still emitted to YAML, but the audit log emits an
informational warning so the operator notices and can confirm the
empty matrix was intentional.

**Default-on security and filtered-tabs (DEC-180).** The new
`AuditOptions.include_security` and `AuditOptions.include_filtered_tabs`
booleans default to `True` to keep the audit's identity as
"capture the full configuration of a source instance for
round-trip deploy." First v1.2 audit run produces `security.yaml`
and `filteredTabs:` blocks without operator intervention.

**Overwrite confirmation guard (DEC-181).** When the output
directory already contains audit YAML output, the entry shows a
confirmation dialog (default-Cancel) before launching. Trigger
pattern matches `*.yaml` at the program root OR `security/*.yaml`
under the subdirectory — covers both per-entity YAMLs and the
single security YAML.

**Security YAML co-located in `security/` subdirectory (DEC-182).**
`security.yaml` is emitted to `<output_dir>/security/security.yaml`
rather than at the program root. Anchoring security-related files
in a dedicated subdirectory keeps the program root focused on
per-entity YAMLs and pre-positions for v1.4 §12.7 permission-preset
files. The deploy-side loader scan covers both root and `security/`.

### 9.3 Key Classes and Functions

**`InstanceRole`** (`models.py`) — Enum with values `SOURCE`,
`TARGET`, `BOTH`. Default on `InstanceProfile` is `TARGET`.

**`AuditManager`** (`audit_manager.py`) — Orchestrator class.
Constructor accepts `EspoAdminClient`, `AuditOptions`, and a progress
callback `(str, str) -> None`. Main entry point is
`run_audit(output_dir, db_conn=None, instance_id=None)`.

**`AuditOptions`** (`audit_manager.py`) — Dataclass with six boolean
toggles controlling what the audit captures. All default to `True`
except `include_native_fields` which defaults to `False`.

**`AuditReport`** (`audit_manager.py`) — Aggregate results dataclass
containing `entities`, `relationships`, `files_written`, `errors`,
`warnings`.

**`classify_entity(scope_name, scope_meta)`** (`audit_utils.py`) —
Returns `EntityClass.CUSTOM`, `NATIVE`, or `SYSTEM`. Uses
`_SYSTEM_SCOPES` set (60+ internal entity names) and `NATIVE_ENTITIES`
from `confirm_delete_dialog.py`.

**`classify_field(field_name, field_meta, entity_type)`**
(`audit_utils.py`) — Returns `FieldClass.CUSTOM`, `NATIVE`, or
`SYSTEM`. Uses `SYSTEM_FIELDS` set, c-prefix heuristic, and
per-entity-type native field sets (`NATIVE_PERSON_FIELDS`,
`NATIVE_COMPANY_FIELDS`, `NATIVE_EVENT_FIELDS`, `NATIVE_BASE_FIELDS`).

**`insert_audit_records(conn, report, instance_id)`**
(`audit_db.py`) — Inserts all DB records from an `AuditReport`.
Returns total records inserted. Idempotent: checks for existing
records by natural key before each INSERT.

**`AuditWorker`** (`audit_worker.py`) — QThread subclass. Tests
connection before starting. Opens optional DB connection from path.
Emits formatted summary block on completion.

**`AuditEntry`** (`audit_entry.py`) — Sidebar widget with source
instance info group, six scope checkboxes, Start Audit and Open
Output Folder buttons. `refresh()` follows the standard
`(conn, instance, project_folder, has_instances)` signature.

**`AuditProgressDialog`** (`audit_entry.py`) — Modal dialog with
indeterminate progress bar, color-coded log output, and Cancel/Close
buttons. Mirrors log lines to `OutputEntry` if provided.

### 9.4 Sidebar Entry Registration

The Deployment window sidebar now has six entries:

```
_ENTRIES = ["Instances", "Deploy", "Configure", "Run History", "Audit", "Output"]

_IDX_INSTANCES   = 0
_IDX_DEPLOY      = 1
_IDX_CONFIGURE   = 2
_IDX_RUN_HISTORY = 3
_IDX_AUDIT       = 4
_IDX_OUTPUT      = 5
```

The Audit entry is refreshed with the same context signature as
Configure and Run History:
`refresh(conn, instance, project_folder, has_instances)`.

### 9.5 Database Migration

Client schema version 7 (`_client_v7` in `migrations.py`) rebuilds
the `ConfigurationRun` table to update the `operation` CHECK
constraint from `('run', 'verify')` to `('run', 'verify', 'audit')`.
The migration is idempotent — if the table does not exist (pre-v5
databases), it is skipped and v5 will create it with the correct
CHECK on first creation.

---

## 10. Future Considerations

### Done in v1.2

- **Selective entity audit** — Operators pick which entities to audit
  via the entity picker (§8.1).
- **Audit-trail `ConfigurationRun` history** — Every audit run is
  recorded in `ConfigurationRun` with `operation: 'audit'` (§4.6).

### Deferred

- **Section 12.5 deploy support (v1.4).** Role-aware field/panel
  visibility and layout-level `forRoles` variants need a real deploy
  mechanism. Candidates: Dynamic Handler JS generation, Teams-as-
  proxies-for-Roles, or an EspoCRM upstream feature request for
  role-condition Dynamic Logic.
- **Section 12.7 field-level permissions (v1.4).** Field-level
  read / write / require / hide permissions per role, paired with
  the §12.5 deferred work.
- **Diff-aware overwrite confirmation.** The
  `(instance_id, entity_yaml_name, tab_id)` unique-key triple in the
  `FilteredTab` client-DB table supports per-file diff rendering
  before overwrite. Current implementation per DEC-181 is a simple
  existence check. Candidate enhancement if operator feedback warrants.
- **Refresh-entity-list button.** The current picker re-discovers
  scope only when the operator switches instances. A manual refresh
  button would handle mid-session server-side changes without
  requiring an instance switch.
- **Migration workflow** — Select a source instance and a target
  instance, audit the source, review/edit the YAML, then configure
  the target. The Audit entry could surface both pickers.
- **Differential audit** — Compare a previous audit snapshot to the
  current CRM state and highlight what changed.
- **Data record export** — Extend the audit to capture record data
  (not just schema), producing CSV or import-ready files.
- **Audit-to-Configure pipeline** — After auditing, automatically
  populate the Configure program list and offer a one-click
  "apply to target" workflow.
