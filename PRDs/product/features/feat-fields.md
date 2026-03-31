# CRM Builder — Field Management

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Depends On:** app-yaml-schema.md, feat-entities.md

---

## 1. Purpose

This document defines the requirements for field management in CRM
Builder — the creation, updating, and verification of custom fields
on CRM entities.

Fields are the individual data elements that make up an entity. They
define what information the CRM stores and how it is presented to
users. Field management is the core configuration capability of
CRM Builder.

---

## 2. What Is a Field

A field is a named data element belonging to an entity. Each field has
a type that determines what kind of data it stores, a display label
shown in the CRM UI, and a set of properties that control its behavior.

### 2.1 Custom Fields vs Native Fields

**Native fields** are built into the CRM platform's entity definitions.
They exist without any configuration and cannot be deleted by CRM
Builder. CRM Builder does not create or delete native fields but may
reference them in layout definitions.

**Custom fields** are created by CRM Builder based on the field
definitions in the YAML program file. CRM Builder manages their full
lifecycle: creation, updates, and verification.

### 2.2 Field Naming

Field names in YAML program files use lowerCamelCase without any
platform-specific prefix (e.g., `contactType`, `mentorStatus`). The
tool applies any required platform-specific naming transformations at
deployment time.

No two fields within the same entity may share the same name.

---

## 3. Supported Field Types

CRM Builder supports the following field types:

| Type | Display Name | Description |
|---|---|---|
| `varchar` | Text | Single-line text input |
| `text` | Text (multi-line) | Multi-line plain text input |
| `wysiwyg` | Rich Text | HTML rich text editor |
| `bool` | Boolean | Checkbox, true or false |
| `int` | Integer | Whole number |
| `float` | Decimal | Decimal number |
| `date` | Date | Date picker |
| `datetime` | Date/Time | Date and time picker |
| `currency` | Currency | Monetary value |
| `url` | URL | Web address |
| `email` | Email | Email address |
| `phone` | Phone | Phone number |
| `enum` | Enum | Single-select dropdown from a defined list of values |
| `multiEnum` | Multi-select | Multi-select from a defined list of values |

---

## 4. Field Properties

### 4.1 Common Properties

These properties apply to all field types:

| Property | Required | Description |
|---|---|---|
| `name` | yes | Internal field name in lowerCamelCase |
| `type` | yes | One of the supported field types (Section 3) |
| `label` | yes | Display label shown in the CRM UI |
| `description` | recommended | Business rationale and PRD reference for this field |
| `category` | no | UI grouping used for layout tab assignment (see feat-layouts.md) |
| `required` | no | Whether the field is required. Default: false |
| `default` | no | Default value for the field |
| `readOnly` | no | Whether the field is read-only. Default: false |
| `audited` | no | Whether changes are tracked in the audit log. Default: false |

The `description` property is optional but strongly recommended on all
fields. Fields without a description are flagged in the documentation
generator output.

### 4.2 Enum and Multi-Select Properties

These additional properties apply to `enum` and `multiEnum` fields:

| Property | Required | Description |
|---|---|---|
| `options` | yes | Ordered list of allowed values. Must be non-empty |
| `translatedOptions` | no | Display label for each option value |
| `style` | no | Color style per option value (see Section 4.3) |
| `isSorted` | no | Sort options alphabetically. Default: false |
| `displayAsLabel` | no | Display value as a colored badge. Default: false. Enum only |

### 4.3 Enum Style Values

Each option in an enum or multi-select field may be assigned a color
style that is displayed in the CRM UI:

| Style | Display |
|---|---|
| omitted or null | Default (no color) |
| `default` | Gray |
| `primary` | Blue |
| `success` | Green |
| `danger` | Red |
| `warning` | Orange |
| `info` | Light blue |

### 4.4 Numeric Field Properties

These additional properties apply to `int` and `float` fields:

| Property | Description |
|---|---|
| `min` | Minimum allowed value |
| `max` | Maximum allowed value |

### 4.5 Text Field Properties

This additional property applies to `varchar` fields:

| Property | Description |
|---|---|
| `maxLength` | Maximum character length |

---

## 5. Field Operations

### 5.1 The Check → Compare → Act Cycle

Every field in the program file is processed through the same three-step
cycle during a Run:

**Check** — the current state of the field is read from the CRM instance.
If the field does not exist, processing moves to Create. If it exists,
processing moves to Compare.

**Compare** — the current field state is compared to the desired spec.
If all compared properties match, the field is skipped. If any
properties differ, processing moves to Update.

**Act** — the field is created or updated as determined by the Check
and Compare steps.

This cycle ensures operations are idempotent. Running the same program
file twice produces no changes on the second run if the first succeeded.

### 5.2 Create

When a field does not exist on the CRM instance, it is created with
all properties specified in the YAML definition.

### 5.3 Update

When a field exists but differs from the spec, it is updated. Only
the properties that differ need to be changed, though the full field
definition is sent in the update payload.

**Type conflicts** — if the existing field's type differs from the
type specified in the YAML, the field is not updated. A type conflict
is logged as a warning and the field is skipped. Type changes require
manual intervention (the field must be deleted and recreated, which
destroys its data).

### 5.4 Skip

When a field exists and all compared properties match the spec, no
API call is made and the field is recorded as skipped.

### 5.5 Compared Properties

The following properties are compared between the current CRM state
and the YAML spec:

- `label`
- `required`
- `default`
- `readOnly`
- `audited`
- `options` (enum/multiEnum — order sensitive)
- `translatedOptions` (enum/multiEnum)
- `style` (enum/multiEnum)
- `min`, `max` (int/float)
- `maxLength` (varchar)

Only properties explicitly specified in the YAML are compared. If a
property is omitted from the YAML, it is not checked against the
current CRM state.

---

## 6. Verify

The Verify action re-reads every field defined in the program file from
the live CRM instance and confirms each matches its spec. Verify makes
no changes. It can be run at any time to check whether manual changes
have caused configuration drift.

Verify uses the same comparison rules as the Run cycle (Section 5.5).
Each field is reported as verified or as a verification failure.

---

## 7. Field Description Requirement

Every field definition is strongly recommended to include a `description`
property. The description should explain:

- The business purpose of the field
- What decision or process it supports
- A reference to the PRD section that defines it

Fields without a description are not a validation failure but are
flagged as informational warnings in the documentation generator output.
This encourages complete documentation without blocking deployment.

---

## 8. Output and Reporting

### 8.1 Output Panel Messages

Field operations emit messages to the output panel following the
conventions in `app-ui-patterns.md`:

```
[CHECK]    Contact.contactType ... EXISTS
[COMPARE]  Contact.contactType ... DIFFERS (label, options)
[UPDATE]   Contact.contactType ... OK

[CHECK]    Contact.isMentor ... NOT FOUND
[CREATE]   Contact.isMentor ... OK

[CHECK]    Contact.mentorStatus ... EXISTS
[COMPARE]  Contact.mentorStatus ... MATCHES
[SKIP]     Contact.mentorStatus ... NO CHANGES NEEDED

[CHECK]    Contact.badField ... EXISTS
[COMPARE]  Contact.badField ... TYPE CONFLICT (yaml: varchar, crm: enum)
[SKIP]     Contact.badField ... SKIPPED (type conflict)
```

### 8.2 Verify Messages

```
[VERIFY]   Contact.contactType ... VERIFIED
[VERIFY]   Contact.isMentor ... VERIFIED
[VERIFY]   Contact.badField ... VERIFICATION FAILED
```

### 8.3 Summary Block

```
===========================================
FIELD SUMMARY
===========================================
Total fields processed  : 15
  Created               :  4
  Updated               :  2
  Skipped (no change)   :  8
  Type conflicts        :  1
  Errors                :  0
===========================================
```

### 8.4 Report Status Values

Field results use the following status values in the JSON report:

| Status | Meaning |
|---|---|
| `created` | Field did not exist and was successfully created |
| `updated` | Field existed and was successfully updated |
| `skipped` | Field exists and matches spec — no change needed |
| `verified` | Field confirmed to match spec (Verify operation) |
| `verification_failed` | Field does not match spec (Verify operation) |
| `skipped_type_conflict` | Field exists with a different type — skipped |
| `error` | Operation failed due to an API or network error |

---

## 9. Error Handling

Field-level errors follow the continue-and-log pattern defined in
`app-logging-reporting.md`. An error on one field does not stop
processing of subsequent fields.

The one exception is an authentication failure (HTTP 401), which
aborts the entire run immediately.

All error responses from the CRM API are logged in full, including
the HTTP status code and the complete response body, to provide
enough information to diagnose the problem.

---

## 10. Validation Rules

The following rules are checked during Validate before any API calls
are made:

- Every field must have `name`, `type`, and `label`
- `type` must be one of the supported field types (Section 3)
- `enum` and `multiEnum` fields must have a non-empty `options` list
- No two fields within the same entity may share the same `name`
- Field names must be in lowerCamelCase

Validation failures are reported individually and prevent the Run
action from proceeding.

---

## 11. Future Considerations

- **Dynamic Logic on fields** — conditional visibility and required
  rules on individual fields (as opposed to panels) are planned but
  not yet implemented. When implemented, they will be defined as
  additional properties on the field definition.
- **Formula fields** — calculated fields that derive their value from
  other fields are planned for a future phase.
- **Additional field types** — as additional CRM platforms are
  supported, platform-specific field types may be added to the
  supported type list.
