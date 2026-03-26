# CRM Builder — Data Import Specification

**Version:** 1.0  
**Status:** Draft  
**Target:** Claude Code implementation  
**Last Updated:** March 2026

---

## 1. Overview

The Data Import feature allows an administrator to import records from a
JSON file into an EspoCRM instance. It is designed to migrate existing
contact data (initially mentors, later clients) from external systems into
EspoCRM without overwriting data that has already been entered directly in
the CRM.

The import follows the same CHECK→ACT pattern used throughout CRM Builder:
the user previews exactly what will happen before committing any changes.

---

## 2. JSON Input File Format

The import file is a JSON file with the following top-level structure:

```json
{
  "metadata": { ... },
  "contacts": [
    {
      "id": "0030b00002QhqCVAAZ",
      "name": "Ms. Deb S Myers",
      "url": "https://...",
      "fields": {
        "Contact Name": "Ms. Deb S Myers",
        "Preferred Name": "Deb",
        "Email": "deb.myers@scorevolunteer.org",
        "Phone": "(216) 407-2836",
        "Gender": "Female",
        "Birth Year": "1953",
        ...
      }
    }
  ]
}
```

The tool reads the top-level array key automatically — in the current file
it is `contacts`, but the import logic should detect any array key that
contains records with a `fields` sub-object.

Each record has:
- `id` — source system identifier (stored for reference, not used as EspoCRM ID)
- `name` — display name from source system
- `url` — source system URL
- `fields` — a flat dict of human-readable field names → string values

Field keys use human-readable labels (e.g. `"Contact Name"`, `"SCORE Email"`)
rather than EspoCRM internal names. The mapping step translates these.

---

## 3. Import Wizard — Four Steps

The import runs as a four-step wizard dialog launched from the main window.
The user must complete each step before advancing.

### Step 1 — Setup

The user configures what to import:

**JSON File**
- File path input + Browse button (OS file picker, filter: `*.json`)
- On selection, the file is parsed and validated; record count is shown

**Entity Type**
- Dropdown: the EspoCRM entity to import into (initially only `Contact`
  is supported; architecture should allow adding more in future)

**Fixed-Value Fields**
- A list of field/value pairs that will be applied identically to every record
- Each row has:
  - **Field** dropdown — populated from EspoCRM field list (label + internal
    name) for the selected entity, fetched via the API
  - **Value** text input — the value to set for all records
- [+ Add Field] button adds a new row; [✕] removes a row
- Example use: set `Contact Type` = `Mentor` and `Is Mentor` = `true`
  for every record in a mentor import file
- Fixed-value fields are excluded from the field mapping dropdown in Step 2

**[Next] button** — enabled once a file is selected and entity type is chosen.
API call to fetch entity fields happens when entity type is selected (or
confirmed), before the user advances to Step 2.

---

### Step 2 — Field Mapping

The user maps JSON field keys to EspoCRM field names.

**Layout:**

```
┌──────────────────────────────────────────────────────────────────┐
│  Field Mapping                                                   │
├──────────────────────────────────────────────────────────────────┤
│  JSON Field                      EspoCRM Field                  │
│  ─────────────────────────────── ─────────────────────────────  │
│  Contact Name                    [firstName             ▼]      │
│  Preferred Name                  [firstName             ▼]      │
│  Email                           [emailAddress          ▼]      │
│  SCORE Email                     [(skip)                ▼]      │
│  Phone                           [phoneNumber           ▼]      │
│  Personal Email                  [(skip)                ▼]      │
│  Gender                          [cGender               ▼]      │
│  ...                                                            │
├──────────────────────────────────────────────────────────────────┤
│  Unmapped Fields (not available in EspoCRM)                     │
│  ─────────────────────────────────────────────────────────────  │
│  Topyx User ID                                                  │
│  Topyx Username                                                 │
│  Certified Co-Mentor Topyx                                      │
│  Last Modified By                                               │
│  ...                                                            │
└──────────────────────────────────────────────────────────────────┘
```

**Mapping table:**
- Left column: every JSON field key found across all records in the file
- Right column: dropdown for each row
  - Options include all EspoCRM fields for the selected entity
    (internal name + label, e.g. "emailAddress — Email Address")
  - First option is always `(skip)` — selecting skip excludes that JSON
    field entirely from the import
  - Fields already used as Fixed-Value Fields in Step 1 are excluded
    from the dropdown options
- The tool attempts auto-mapping based on name similarity (see Section 4)

**Unmapped Fields panel:**
- Displayed below the mapping table
- Lists all JSON field keys that have no reasonable auto-map candidate
  and that the user has not manually mapped
- This panel updates live as the user changes dropdown selections
- A field moves out of "Unmapped" as soon as its dropdown is set to
  anything other than `(skip)`
- The panel is informational only — the user is not required to map
  every field to proceed

**[Back] / [Next] buttons** — Next is enabled once at least one field is
mapped (not counting fixed-value fields). The user is not required to map
all fields.

---

### Step 3 — Preview (CHECK)

Displays a per-record preview of what the import will do.

**For each record:**
1. Identify the email address from the mapped email field
2. Search EspoCRM for an existing record with that email address
3. Determine action:
   - **CREATE** — no existing record found; full payload will be posted
   - **UPDATE** — existing record found; only empty/null fields will be patched
   - **SKIP** — existing record found but all mapped fields already have values
   - **ERROR** — no email address in record (cannot match); skip this record

**Preview display:**

```
Record 1 of 72 — Deb S Myers (deb.myers@scorevolunteer.org)
  Action: UPDATE (existing record found)
  Will set: firstName, phoneNumber, cGender, cBirthYear
  Will skip (already has value): lastName, emailAddress
  Fixed values: cContactType = "Mentor", cIsMentor = true

Record 2 of 72 — John A Smith (john.smith@scorevolunteer.org)
  Action: CREATE (no existing record)
  Will set: firstName, lastName, emailAddress, phoneNumber, cGender
  Fixed values: cContactType = "Mentor", cIsMentor = true

Record 3 of 72 — Jane Doe
  Action: ERROR — no email address found; record will be skipped
```

**Summary counts** shown at the bottom:
```
  To create : 14
  To update : 55
  To skip   :  2
  Errors    :  1
  ───────────────
  Total     : 72
```

**[Back] / [Import] buttons** — Import button is enabled if at least one
record has action CREATE or UPDATE. It is labeled clearly as the
point-of-no-return.

---

### Step 4 — Execute (ACT)

Executes the import and displays real-time output in the same style as
the main window output panel.

```
[IMPORT]  Deb S Myers ... CHECKING
[IMPORT]  Deb S Myers ... EXISTS (id: abc123)
[IMPORT]  Deb S Myers ... PATCHING (firstName, phoneNumber, cGender)
[IMPORT]  Deb S Myers ... OK

[IMPORT]  John A Smith ... CHECKING
[IMPORT]  John A Smith ... NOT FOUND
[IMPORT]  John A Smith ... CREATING
[IMPORT]  John A Smith ... OK

[IMPORT]  Jane Doe ... SKIP (no email address)
```

**Summary at completion:**
```
===========================================
IMPORT SUMMARY
===========================================
Total records processed : 72
  Created               : 14
  Updated               : 55
  Skipped               : 2
  Errors                : 1
===========================================
```

**[Close] button** — enabled once the import completes (success or failure).
A **[View Report]** button opens the import report file (same format as
run reports).

---

## 4. Auto-Mapping Logic

When the mapping table is first built (on entering Step 2), the tool
attempts to auto-map JSON field keys to EspoCRM field names using the
following approach:

1. **Exact label match** — if a JSON key matches an EspoCRM field label
   exactly (case-insensitive), map it
2. **Normalized match** — strip punctuation and compare lowercased tokens
   (e.g. `"Phone"` → `phoneNumber`, `"Email"` → `emailAddress`)
3. **Known alias table** — hardcoded common mappings for the Contact entity:

| JSON Field Key | EspoCRM Field |
|---|---|
| `Contact Name` | `name` |
| `Preferred Name` | `firstName` |
| `Email` | `emailAddress` |
| `SCORE Email` | `emailAddress` |
| `Phone` | `phoneNumber` |
| `Personal Email` | *(skip)* |
| `Mailing Address` | `address` |
| `Birth Year` | `cBirthYear` |
| `Gender` | `cGender` |

4. **No match** → field defaults to `(skip)` and appears in Unmapped Fields

Auto-mapping is a starting point only. The user can override any mapping.

---

## 5. Match-by-Email Logic

Records are matched to existing EspoCRM records by email address.

- The email field used for matching is the one mapped to `emailAddress`
  in the field mapping, or set as a fixed-value field
- If a record has no email value after mapping, it cannot be matched
  and is logged as ERROR / skipped
- If multiple EspoCRM records match the same email, use the first result
  and log a WARNING

---

## 6. Never-Overwrite Rule

When an existing EspoCRM record is found, the tool fetches the full record
and checks each field individually before patching:

- If the EspoCRM field value is `null`, `""`, or absent → include in patch
- If the EspoCRM field already has a non-empty value → exclude from patch

This rule applies to both mapped fields and fixed-value fields. Even if a
fixed-value field is specified, it will not overwrite an existing value.

---

## 7. New API Endpoints

The following endpoints are additions to the existing `EspoAdminClient`.
They should be added as methods on that class.

| Operation | Method | Endpoint |
|---|---|---|
| Get entity field list | GET | `/api/v1/Metadata?key=entityDefs.{Entity}.fields` |
| Search records by email | GET | `/api/v1/{Entity}?where[0][type]=equals&where[0][attribute]=emailAddress&where[0][value]={email}&maxSize=2` |
| Get single record | GET | `/api/v1/{Entity}/{id}` |
| Create record | POST | `/api/v1/{Entity}` |
| Patch record | PATCH | `/api/v1/{Entity}/{id}` |

**Note on maxSize=2:** Fetching 2 results intentionally — if 2 are returned
it means there are duplicate email addresses in EspoCRM, which should be
logged as a WARNING.

---

## 8. New Files

| File | Purpose |
|---|---|
| `espo_impl/ui/import_dialog.py` | Four-step wizard dialog (PySide6) |
| `espo_impl/core/import_manager.py` | CHECK and ACT business logic |
| `espo_impl/workers/import_worker.py` | QThread background worker |

---

## 9. Modified Files

| File | Change |
|---|---|
| `espo_impl/core/api_client.py` | Add 5 new data-level methods |
| `espo_impl/ui/main_window.py` | Add Import Data button to bottom bar |

---

## 10. Import Data Button

Added to the bottom bar of the main window, between **Generate Docs** and
**Clear Output**.

- Label: `Import Data`
- Enabled when: an instance is selected and no operation is in progress
- Clicking opens the import wizard dialog (modal)
- The button does not require a program file to be selected

---

## 11. Import Worker

Follows the same `QThread` pattern as `run_worker.py`:

- `output_line` signal: `(message: str, color: str)`
- `finished_ok` signal: `(report: ImportReport)`
- `finished_error` signal: `(error_msg: str)`

The worker calls `import_manager.execute()` and forwards output via signals.

---

## 12. Import Report

After a successful or failed import, a report is written to the instance's
`reports/` directory using the same timestamped naming convention as run
reports.

**Log file format:**
```
========================================
CRM Builder — Import Report
========================================
Timestamp     : 2026-03-25 14:32:00
Instance      : CBM Production
Entity        : Contact
Source File   : contacts.json
Total Records : 72
  Created     : 14
  Updated     : 55
  Skipped     : 2
  Errors      : 1
========================================

[CREATED]  John A Smith (john.smith@scorevolunteer.org)
  Fields set: firstName, lastName, emailAddress, phoneNumber, cGender
  Fixed values: cContactType=Mentor, cIsMentor=true

[UPDATED]  Deb S Myers (deb.myers@scorevolunteer.org)
  Fields patched: firstName, phoneNumber, cGender, cBirthYear
  Fields skipped (had value): lastName, emailAddress
  Fixed values: cContactType=Mentor, cIsMentor=true

[SKIPPED]  Jane Doe — no email address found
...
```

**JSON report** mirrors the same structure in machine-readable form.

---

## 13. Notes for Implementer

- The import dialog is fully self-contained — it does not interact with the
  main window's state machine (UIState). The main window Import Data button
  simply opens the dialog.
- The API call to fetch entity fields (for Step 1 dropdowns and Step 2
  mapping) should be made once when the entity type is selected, and the
  result cached for the duration of the wizard session.
- The `Metadata?key=entityDefs.{Entity}.fields` endpoint returns a dict
  of `{fieldName: {type, label, ...}}`. Use the `label` property to build
  human-readable dropdown entries alongside the internal name.
- The match-by-email search uses the standard EspoCRM list endpoint with
  a `where` filter. Parse the `list` array in the response body.
- PATCH (not PUT) is used for partial updates. EspoCRM's PATCH endpoint
  accepts a partial field dict and updates only the specified fields.
- Records with errors during ACT (e.g. HTTP 4xx from EspoCRM) should be
  logged individually and counted in the error total. The import continues
  with remaining records rather than aborting on first error.
- The wizard should be resizable; the mapping table (Step 2) and preview
  list (Step 3) should use scrollable areas to handle large record sets.
