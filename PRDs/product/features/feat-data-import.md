# CRM Builder — Data Import

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Depends On:** feat-entities.md, feat-fields.md

---

## 1. Purpose

This document defines the requirements for the data import feature in
CRM Builder — the ability to import records from an external source
file into a CRM entity.

Data import addresses the common situation where an organization is
migrating to a new CRM and has existing contact or record data in
another system. The import feature moves that data into the newly
configured CRM instance without overwriting information that has
already been entered directly.

---

## 2. Design Principles

**Preview before commit.** The user sees exactly what will happen to
each record before any changes are made. No records are created or
modified until the user explicitly proceeds.

**Never overwrite existing data.** If a matching record already exists
in the CRM and a field already has a value, that value is never
overwritten by the import. Only empty fields are populated.

**Match by email.** Records are matched to existing CRM records by
email address. A record with no email address cannot be matched and
is skipped with an error.

**Continue on error.** An error on one record does not abort the
import. All records are processed and all errors are reported together
in the summary.

---

## 3. Import Source Format

### 3.1 Supported Format

The import source is a JSON file. The file must contain a top-level
object with at least one array of records. The tool detects the array
key automatically.

Each record in the array must have:
- An `id` field — the source system identifier (stored for reference,
  not used as the CRM record ID)
- A `name` field — the display name from the source system
- A `fields` object — a flat dictionary of human-readable field names
  to string values

```json
{
  "metadata": { ... },
  "contacts": [
    {
      "id": "source-system-id",
      "name": "Jane Smith",
      "url": "https://source-system.example.com/contacts/123",
      "fields": {
        "Contact Name": "Jane Smith",
        "Email": "jane.smith@example.com",
        "Phone": "(216) 555-1234",
        "Gender": "Female"
      }
    }
  ]
}
```

Field keys in the `fields` object use human-readable labels from the
source system, not CRM field names. The import wizard handles the
mapping from source labels to CRM field names.

### 3.2 Supported Entities

The import feature initially supports importing into the Contact entity.
The architecture must allow additional entity types to be added in
future releases without redesigning the wizard.

---

## 4. Import Wizard

The import runs as a four-step wizard dialog. The user must complete
each step before advancing. The wizard is modal — no other application
actions can be taken while it is open.

### 4.1 Step 1 — Setup

The user configures what to import:

**JSON File selection**
- File path input with a Browse button opening the OS file picker
- On selection, the file is parsed and the record count is shown
- Parsing errors are shown inline if the file is not valid

**Entity Type**
- Dropdown selecting which CRM entity to import into
- Initially only Contact is available
- The CRM field list is fetched when the entity type is confirmed

**Fixed-Value Fields**
- A list of field/value pairs applied identically to every imported record
- Each row has a field dropdown (populated from the CRM entity's field
  list) and a value text input
- Rows can be added and removed
- Fixed-value fields are excluded from the field mapping dropdown in Step 2
- Example use: set `Contact Type = Mentor` and `Is Mentor = true` for
  every record in a mentor import file

The Next button is enabled once a file is selected and an entity type
is chosen.

### 4.2 Step 2 — Field Mapping

The user maps each source field key to a CRM field:

**Mapping table**
- Left column: every field key found across all records in the source file
- Right column: a dropdown for each row with all CRM fields for the
  selected entity
- The first option in every dropdown is `(skip)` — selecting skip
  excludes that source field from the import entirely
- Fields set as fixed-value fields in Step 1 are excluded from the
  dropdown options
- The tool attempts auto-mapping on entry (see Section 5)

**Unmapped Fields panel**
- Displayed below the mapping table
- Lists source field keys that are set to `(skip)` or have no auto-map
- Updates live as the user changes dropdown selections
- Informational only — the user is not required to map every field

The Next button is enabled once at least one field is mapped. The user
is not required to map all fields.

### 4.3 Step 3 — Preview

For each record in the source file, the tool checks the CRM instance
and determines what action will be taken:

| Action | Condition |
|---|---|
| **CREATE** | No existing CRM record found with matching email |
| **UPDATE** | Existing record found; at least one mapped field is empty |
| **SKIP** | Existing record found; all mapped fields already have values |
| **ERROR** | No email address in the record; cannot match |

The preview displays each record's name, email, determined action,
and the specific fields that will be set or skipped. A summary count
is shown at the bottom.

The Import button is enabled if at least one record has action CREATE
or UPDATE. The button label makes clear it is the point of no return.

### 4.4 Step 4 — Execute

The import runs in the background with real-time output streamed to
the step's output area, following the same color coding and message
format defined in `app-ui-patterns.md` and `app-logging-reporting.md`.

A summary is shown on completion with counts of created, updated,
skipped, and errored records.

A Close button is enabled once the import completes. A View Report
button opens the import report file.

---

## 5. Auto-Mapping

When the mapping table is first built, the tool attempts to auto-map
source field keys to CRM field names using the following approach, in
order:

1. **Exact label match** — source key matches a CRM field label
   exactly (case-insensitive)
2. **Normalized match** — strip punctuation, compare lowercased tokens
3. **Known alias table** — hardcoded mappings for common source system
   field names to standard CRM field names

Auto-mapping is a starting point only. The user can override any
auto-mapped field in the mapping table.

Fields with no auto-map candidate default to `(skip)` and appear in
the Unmapped Fields panel.

---

## 6. Record Matching

Records are matched to existing CRM records by email address:

- The email address used for matching is taken from the field mapped
  to the CRM email field, or from a fixed-value field if email is
  set as a fixed value
- If a record has no email address after mapping, it is logged as
  ERROR and skipped
- If multiple CRM records share the same email address, the first
  match is used and a warning is logged about the duplicate

---

## 7. Never-Overwrite Rule

When an existing CRM record is found, the tool fetches the full record
and checks each mapped field individually before including it in the
update payload:

- If the CRM field value is empty (null or empty string) → include
  in the update
- If the CRM field already has a non-empty value → exclude from the
  update and record as skipped

This rule applies to both mapped fields and fixed-value fields. A
fixed-value field will not overwrite an existing value even if
explicitly specified.

---

## 8. Data Handling

### 8.1 Phone Number Cleaning

Phone numbers are cleaned to a standard format before being sent to
the CRM. US 10-digit numbers are formatted to the international E.164
standard.

### 8.2 Name Derivation

First and last name are derived from the source record's display name
if they are not explicitly mapped:

- The display name is parsed (stripping common salutations such as
  Mr., Mrs., Ms., Dr.)
- As a fallback, names are parsed from the email address local part
  (e.g., `jane.smith@example.com` → Jane / Smith)

### 8.3 Boolean Conversion

Fixed-value fields entered as the strings `"true"` or `"false"` are
converted to the appropriate boolean type before being sent to the CRM.

### 8.4 Empty Value Filtering

Empty string values are excluded from the import payload — they are
treated as absent rather than as a value to be set.

---

## 9. Import Button Placement

The Import Data button is located in the main window action bar. It:

- Is enabled when an instance is selected and no operation is in
  progress
- Does not require a program file to be selected
- Opens the import wizard as a modal dialog

---

## 10. Reporting

After each import, two report files are written to the instance's
`reports/` directory following the conventions in
`app-logging-reporting.md`:

- `import_{timestamp}.log` — human-readable log with per-record details
- `import_{timestamp}.json` — machine-readable structured report

The log includes for each record: the action taken, the fields set,
the fields skipped (with reasons), and any errors. The JSON report
mirrors this structure in machine-readable form.

---

## 11. Validation

Import files are validated on selection in Step 1:

- File must be valid JSON
- File must contain at least one top-level array with at least one
  record
- Each record must have a `fields` object

Structural errors are shown inline in Step 1 and prevent advancing
to Step 2.

Field mapping validation in Step 2:
- At least one field must be mapped (not set to skip) to advance

---

## 12. Future Considerations

- **Additional entity types** — the wizard is designed to support
  entities beyond Contact. Adding a new entity type requires defining
  its auto-mapping alias table and any entity-specific data handling
  rules.
- **Additional source formats** — CSV import is a likely future
  addition. The architecture should not assume JSON is the only source
  format.
- **Duplicate handling options** — the current match-by-email approach
  assumes email is unique per record. Future versions may support
  configurable match fields or more sophisticated deduplication.
- **Import scheduling** — recurring imports from external systems are
  a potential future capability for organizations with ongoing data
  sync needs.
