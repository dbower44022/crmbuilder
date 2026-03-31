# CRM Builder — Security & Access Control

**Version:** 1.0
**Status:** Draft — Planned Feature
**Last Updated:** March 2026
**Depends On:** app-yaml-schema.md, feat-entities.md, feat-fields.md

---

## 1. Purpose

This document defines the requirements for security and access control
management in CRM Builder — the configuration of roles, permissions,
and field-level access rules on a CRM instance.

Access control determines what each user can see and do within the CRM.
Without appropriate security configuration, all users have the same
level of access, which is inappropriate for most organizations. CRM
Builder manages access control declaratively, applying the same
check/act/verify pattern used for all other configuration.

---

## 2. Status

Security and access control is a planned feature. The requirements in
this document define the intended behavior. Implementation has not yet
begun.

The current tool has no access control management capability. All
configuration operations require admin-level credentials, and the
tool does not restrict what API users can do within the CRM.

---

## 3. Core Concepts

### 3.1 Roles

A **role** is a named set of permissions that can be assigned to users
or teams. Roles define what actions a user can perform (create, read,
update, delete) on each entity, and optionally on each field within
an entity.

Roles are additive — a user with multiple roles has the combined
permissions of all their roles.

### 3.2 Permission Levels

CRM Builder supports the following permission levels for entity-level
access:

| Level | Meaning |
|---|---|
| `all` | Full access to all records of this entity |
| `team` | Access to records belonging to the user's team |
| `own` | Access to records owned by the user |
| `no` | No access |

Not all CRM platforms support all permission levels. Platform-specific
constraints are noted in the implementation documentation.

### 3.3 Action Types

For each entity, a role specifies the permitted action for each of
the following operations:

| Action | Meaning |
|---|---|
| `create` | Create new records |
| `read` | View existing records |
| `edit` | Modify existing records |
| `delete` | Delete existing records |
| `stream` | Access the activity feed for records |

### 3.4 Field-Level Security

In addition to entity-level permissions, a role may define access
rules for individual fields within an entity:

| Level | Meaning |
|---|---|
| `yes` | Field is visible and editable |
| `read` | Field is visible but not editable |
| `no` | Field is not visible |

Field-level rules override the entity-level read/edit permissions for
specific fields. This allows, for example, salary fields to be visible
only to HR staff while remaining hidden from other roles.

---

## 4. Role Definitions in YAML

Roles are defined in a top-level `roles` block in the YAML program
file, separate from entities and relationships.

```yaml
roles:
  - name: MentorCoordinator
    description: >
      Staff members who manage mentor relationships and engagements.
      Can view and edit all mentor and engagement records but cannot
      configure the CRM or access financial data.
    permissions:
      Contact:
        create: all
        read: all
        edit: all
        delete: no
        stream: all
      Engagement:
        create: all
        read: all
        edit: all
        delete: own
        stream: all
      Account:
        create: all
        read: all
        edit: all
        delete: no
    fieldPermissions:
      Contact:
        - field: ssn
          level: no
        - field: salary
          level: no

  - name: MentorVolunteer
    description: >
      Volunteer mentors who access their own engagement records and
      client information. Read-only access to most data.
    permissions:
      Contact:
        create: no
        read: own
        edit: own
        delete: no
      Engagement:
        create: no
        read: own
        edit: own
        delete: no
```

### 4.1 Role Properties

| Property | Required | Description |
|---|---|---|
| `name` | yes | Role name. Must be unique within the file |
| `description` | yes | Business rationale — who this role is for and what they can do |
| `permissions` | yes | Map of entity name → action permissions (see Section 4.2) |
| `fieldPermissions` | no | Map of entity name → list of field-level rules (see Section 4.3) |

### 4.2 Entity Permission Block

For each entity listed under `permissions`, specify the permission
level for each action:

| Property | Required | Values |
|---|---|---|
| `create` | no | `all`, `team`, `own`, `no` |
| `read` | no | `all`, `team`, `own`, `no` |
| `edit` | no | `all`, `team`, `own`, `no` |
| `delete` | no | `all`, `team`, `own`, `no` |
| `stream` | no | `all`, `team`, `own`, `no` |

Omitting an action means the role's permission for that action is
inherited from the CRM's default role or left at the platform default.

### 4.3 Field Permission Block

For each entity listed under `fieldPermissions`, provide a list of
field-level rules:

| Property | Required | Description |
|---|---|---|
| `field` | yes | Field name — natural name, no prefix |
| `level` | yes | `yes`, `read`, or `no` |

Only fields that require non-default access need to be listed. Fields
not listed inherit the entity-level read/edit permissions.

---

## 5. Role Operations

### 5.1 The Check → Compare → Act Cycle

Role operations follow the same three-step cycle as other configuration:

**Check** — the current state of the role is read from the CRM instance.
If the role does not exist, processing moves to Create. If it exists,
processing moves to Compare.

**Compare** — the current role's permissions are compared to the
desired spec. If all permissions match, the role is skipped. If any
differ, processing moves to Update.

**Act** — the role is created or updated as determined by the Check
and Compare steps.

### 5.2 Create

When a role does not exist on the CRM instance, it is created with
all permissions specified in the YAML definition.

### 5.3 Update

When a role exists but its permissions differ from the spec, the role
is updated to match the spec.

### 5.4 Delete

A role with `action: delete` is removed from the CRM instance. Role
deletion is a destructive operation and requires explicit user
confirmation before execution.

Deleting a role that is currently assigned to users removes those
permissions from the affected users immediately. This should be done
with caution on production instances.

---

## 6. Role Assignment

Role assignment — associating roles with specific CRM users or teams
— is outside the scope of CRM Builder's configuration management.
User and team management involves organizational data (real people and
their credentials) that belongs to the CRM instance administrator,
not to a declarative configuration file.

CRM Builder creates and configures the roles themselves. Assigning
roles to users is performed manually in the CRM administration UI
after the roles have been deployed.

---

## 7. Processing Order

Role operations are processed after all entity, field, layout, and
relationship operations have completed. This ensures that all entities
and fields referenced in role permission and field permission blocks
exist before access rules are applied.

---

## 8. Security Description Requirement

Every role definition must include a `description` property. The
description must explain:

- Who this role is intended for
- What level of access they should have and why
- A reference to the PRD section that defines the access requirements

This is a validation requirement. Program files with role definitions
missing a description will fail validation and cannot be run.

---

## 9. Output and Reporting

### 9.1 Output Panel Messages

Role operations emit messages to the output panel following the
conventions in `app-ui-patterns.md`:

```
[ROLE]  MentorCoordinator ... CHECKING
[ROLE]  MentorCoordinator ... NOT FOUND
[ROLE]  MentorCoordinator ... CREATING
[ROLE]  MentorCoordinator ... CREATED OK

[ROLE]  MentorVolunteer ... CHECKING
[ROLE]  MentorVolunteer ... EXISTS
[ROLE]  MentorVolunteer ... DIFFERS (Contact.delete, Engagement.edit)
[ROLE]  MentorVolunteer ... UPDATED OK

[ROLE]  LegacyRole ... CHECKING
[ROLE]  LegacyRole ... EXISTS
[ROLE]  LegacyRole ... MATCHES
[ROLE]  LegacyRole ... SKIPPED (no changes needed)
```

### 9.2 Summary Block

```
===========================================
ROLE SUMMARY
===========================================
Total roles processed :  3
  Created             :  1
  Updated             :  1
  Skipped (matches)   :  1
  Errors              :  0
===========================================
```

### 9.3 Report Status Values

Role results use the following status values in the JSON report:

| Status | Meaning |
|---|---|
| `created` | Role did not exist and was successfully created |
| `updated` | Role existed and permissions were successfully updated |
| `skipped` | Role exists and matches spec — no change needed |
| `deleted` | Role was successfully deleted |
| `error` | Operation failed due to an API or network error |

---

## 10. Validation Rules

The following rules are checked during Validate before any API calls
are made:

- Every role must have `name`, `description`, and `permissions`
- Permission levels must be one of: `all`, `team`, `own`, `no`
- Field permission levels must be one of: `yes`, `read`, `no`
- Entity names in `permissions` and `fieldPermissions` must exist in
  the program file's entity definitions or be recognized native entities
- Field names in `fieldPermissions` must exist in the referenced
  entity's field list
- No two roles in the same program file may share the same `name`

Validation failures are reported individually and prevent the Run
action from proceeding.

---

## 11. Future Considerations

- **Team-based permissions** — configuring CRM teams and their
  membership is a related area that may be added as a future feature.
- **Permission inheritance** — some CRM platforms support role
  hierarchies where child roles inherit permissions from parent roles.
  This may be added when a supported platform requires it.
- **Portal roles** — roles for external portal users (e.g., client
  self-service portals) may require a separate permission model.
- **API user roles** — configuring permissions for API integration
  users is a distinct use case from staff user roles and may be
  addressed separately.
