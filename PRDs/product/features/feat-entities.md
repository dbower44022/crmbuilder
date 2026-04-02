# CRM Builder — Entity Management

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Depends On:** app-yaml-schema.md

---

## 1. Purpose

This document defines the requirements for entity management in CRM
Builder — the creation, deletion, and maintenance of entity types in
a CRM instance.

Entities are the foundational objects of a CRM configuration. All other
configuration — fields, layouts, relationships, security — is defined
relative to entities. Entity management must therefore be the first
phase of any configuration run.

---

## 2. What Is an Entity

An entity is a named object type in the CRM that represents a category
of real-world things the organization tracks. Examples include Contact,
Account, Engagement, Session, and Workshop.

CRM platforms provide a set of **native entities** built into the
platform. Organizations extend the CRM by creating **custom entities**
for things the platform does not natively support.

### 2.1 Native Entities

Native entities are provided by the CRM platform and cannot be created
or deleted by CRM Builder. CRM Builder may add custom fields and layouts
to native entities but does not manage their existence.

For EspoCRM, native entities include: Account, Contact, Lead,
Opportunity, Case, Task, Meeting, Call, Email, and Document.

### 2.2 Custom Entities

Custom entities are created by CRM Builder based on the entity
definitions in the YAML program file. CRM Builder manages their full
lifecycle: creation, field and layout configuration, and deletion.

---

## 3. Entity Types

Custom entities are created with one of four base types. The type
determines what built-in fields and behaviors the entity has by default:

| Type | Description | Use When |
|---|---|---|
| `Base` | General-purpose entity with name and description | Tracking activities, records, or transactions |
| `Person` | Includes first/last name, email, phone, address | Tracking individual people not covered by Contact |
| `Company` | Includes email, phone, billing/shipping address | Tracking organizations not covered by Account |
| `Event` | Includes start/end dates, duration, status, parent | Tracking time-bound activities or appointments |

---

## 4. Entity Operations

### 4.1 Create

Creates a new custom entity on the CRM instance. If the entity already
exists, the create operation is skipped — no error is raised and
processing continues with the entity's fields and layout.

A create operation requires: entity type, singular label, and plural
label. All other properties are optional.

After creation, a cache rebuild is required before field operations on
the new entity can proceed.

### 4.2 Delete

Permanently removes a custom entity and all its custom fields from the
CRM instance. If the entity does not exist, the delete operation is
skipped.

Delete is a destructive operation and requires explicit user confirmation
before execution. See Section 5 for confirmation requirements.

After deletion, a cache rebuild is required.

### 4.3 Delete and Recreate

Deletes an existing custom entity and immediately recreates it. This is
the standard approach for clean configuration rebuilds on development or
test instances.

Delete-and-recreate is treated as a destructive operation and requires
the same confirmation as a plain delete.

After the delete phase, a cache rebuild is required before the create
phase proceeds. A second cache rebuild is required after recreation
before field operations can begin.

### 4.4 Fields Only (Default)

When no action is specified for an entity block, CRM Builder performs
field and layout operations only. No entity creation or deletion is
attempted. This is the correct behavior for native entities and for
custom entities that have already been created.

---

## 5. Destructive Operation Confirmation

Any run that contains one or more delete or delete-and-recreate
operations must pause before any API calls are made — including
non-destructive operations in the same program file — and present
the user with a confirmation dialog.

The confirmation dialog must:

- List every entity that will be deleted by its CRM internal name
- State clearly that the deletion cannot be undone
- Require the user to type a confirmation keyword before proceeding
- Provide a Cancel option that returns to the main window with no
  changes made

No API calls of any kind are made until the user explicitly confirms.
Cancelling returns the application to its ready state.

See `app-ui-patterns.md` Section 5.3 for the full confirmation dialog
requirements.

---

## 6. Cache Rebuild

The CRM platform maintains an internal cache of entity and field
metadata. After any entity creation or deletion, the cache must be
rebuilt before subsequent operations on the affected entity are
attempted. CRM Builder triggers the cache rebuild automatically as
part of the run sequence.

The cache rebuild is logged in the output panel and included in the
run report.

---

## 7. Processing Order

Within a configuration run, entity operations are processed in the
following order:

1. All entity deletions (across all entities in the program file)
2. Cache rebuild (if any deletions occurred)
3. All entity creations (across all entities in the program file)
4. Cache rebuild (if any creations occurred)
5. Field, layout, and relationship operations (see their respective
   feature PRDs)

This ordering ensures that by the time field and layout operations
begin, all entities are in their correct state.

---

## 8. Entity Description Requirement

Every entity block in a YAML program file — both native and custom —
must include a `description` property. The description must explain:

- The business purpose of the entity
- Its role in the data model
- A reference to the PRD section that defines it

This is a validation requirement. Program files with entity blocks
missing a description will fail validation and cannot be run.

---

## 9. Output and Reporting

### 9.1 Output Panel Messages

Entity operations emit messages to the output panel following the
conventions in `app-ui-patterns.md`:

```
[ENTITY]  Engagement ... CHECKING
[ENTITY]  Engagement ... NOT FOUND
[ENTITY]  Engagement ... CREATING
[ENTITY]  Engagement ... CREATED OK

[ENTITY]  Session ... CHECKING
[ENTITY]  Session ... EXISTS
[ENTITY]  Session ... SKIPPED (already exists)

[ENTITY]  Workshop ... CHECKING
[ENTITY]  Workshop ... EXISTS
[ENTITY]  Workshop ... DELETING
[ENTITY]  Workshop ... DELETED OK

[CACHE]   Rebuilding cache ... OK
```

### 9.2 Summary Block

The entity operations summary is included within the overall run
summary block:

```
===========================================
ENTITY SUMMARY
===========================================
Total entities processed :  5
  Created                :  3
  Deleted                :  1
  Skipped (exists)       :  1
  Errors                 :  0
===========================================
```

### 9.3 Report Entries

Each entity operation is recorded in the run report with its name,
action attempted, and outcome. See `app-logging-reporting.md` for
the full report format requirements.

---

## 10. Validation Rules

The following rules are checked during Validate before any API calls
are made:

- Every entity block must have a `description`
- `create` and `delete_and_create` actions require `type`,
  `labelSingular`, and `labelPlural`
- `type` must be one of: `Base`, `Person`, `Company`, `Event`
- `delete` actions must not contain `fields` or `layout` blocks
- No two entity blocks in the same program file may have the same name

Validation failures are reported individually and prevent the Run
action from proceeding.

---

## 11. Future Considerations

- **Entity update** — modifying the labels or type of an existing
  custom entity is not currently supported. Changes to entity
  metadata require delete-and-recreate.
- **Native entity creation** — creating entities that mirror a
  platform's native entity type (e.g., a Person-type entity to
  supplement Contact) may require special handling per platform.
- **Cross-platform entity types** — as additional CRM platforms are
  supported, entity type mappings will be defined per platform in
  the relevant implementation documentation.
