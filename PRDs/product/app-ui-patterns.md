# CRM Builder — UI Patterns & Conventions

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Applies To:** All features and UI components

---

## 1. Purpose

This document defines the UI patterns, conventions, and behaviors that
apply across the entire CRM Builder application. All feature-specific UI
components must follow these conventions to ensure a consistent user
experience. Feature PRDs reference this document rather than redefining
these patterns independently.

---

## 2. Application Window

### 2.1 Single Window

The application presents a single main window. All primary interaction
happens within this window. Feature-specific operations that require
additional input open as modal dialogs over the main window.

### 2.2 Layout Regions

The main window is divided into four regions:

**Top-left — Instance Panel**
Displays the list of saved CRM instance profiles. Allows the user to
select, add, edit, and delete instances.

**Top-right — Program File Panel**
Displays the YAML program files available for the selected instance.
Allows the user to select, add, edit, and delete program files.

**Middle — Action Bar**
Contains the primary workflow action buttons: Validate, Run, Verify.

**Bottom — Output Panel**
A scrollable, read-only log of all operation output. Persists across
operations within a session.

**Bottom Bar — Utility and Action Buttons**
Below the output panel. Buttons are organized into three groups
separated by visual dividers:

```
[Clear Output]  [Preview YAML]  [View Report]  |  [Generate Docs]  [Open Reference Docs]  |  [Import Data]
```

| Group | Buttons | Purpose |
|---|---|---|
| Output utilities | Clear Output, Preview YAML, View Report | Local actions — no API calls |
| Documentation | Generate Docs, Open Reference Docs | Produce or open the reference manual |
| Data | Import Data | Import records into the CRM instance |

### 2.3 Responsive Resizing

The window is resizable. The output panel expands to fill available
vertical space. Panels and dialogs that contain lists or tables use
scrollable areas to handle large content sets.

---

## 3. Output Panel

### 3.1 Purpose

The output panel is the primary feedback mechanism for all operations.
It displays real-time progress, results, warnings, and errors as
operations execute.

### 3.2 Behavior

- Uses a monospace font for clean alignment of structured log output
- Scrolls automatically to the latest output during active operations
- Is read-only — the user cannot edit its contents
- Is **not** cleared between operations in the same session; the full
  history of the session remains visible
- The **Clear Output** button resets the panel manually

### 3.3 Color Coding

All output messages use consistent color coding across all features:

| Color | Meaning |
|---|---|
| White (default) | Informational — progress, status |
| Green | Success — created, updated, verified, completed |
| Gray | No change — skipped, already correct |
| Yellow | Warning — skipped due to conflict, duplicate detected |
| Red | Error — operation failed, verification failed |

Every feature that emits output to the panel must use these colors
consistently. No feature may introduce new colors or repurpose existing
color meanings.

### 3.4 Message Format

Output messages follow a consistent bracketed-tag format:

```
[TAG]  Entity.fieldOrObject ... STATUS
```

Examples:
```
[CHECK]       Contact.contactType ... EXISTS
[COMPARE]     Contact.contactType ... DIFFERS (label, options)
[UPDATE]      Contact.contactType ... OK
[VERIFY]      Contact.contactType ... VERIFIED
[LAYOUT]      Contact.detail ... UPDATED OK
[RELATIONSHIP] Session → Engagement (sessionEngagement) ... CREATED OK
[IMPORT]      Deb S Myers ... UPDATED OK
```

Tags are defined per feature. Within a feature, tags must be used
consistently for the same type of operation.

### 3.5 Summary Blocks

At the end of every operation, a summary block is emitted:

```
===========================================
OPERATION SUMMARY
===========================================
Total processed : 12
  Created       :  4
  Updated       :  3
  Skipped       :  5
  Errors        :  0
===========================================
```

The specific counters vary by feature but the block format is consistent.

---

## 4. Button Behavior

### 4.1 Never-Disable Pattern

Buttons in the main window are **never disabled**. Instead, clicking a
button that has unmet preconditions emits an explanatory message to the
output panel and takes no further action.

Examples:
- Clicking Run before Validate: outputs "Validate a program file first"
- Clicking Validate with no instance selected: outputs "Select an instance first"
- Clicking any action while an operation is in progress: outputs "An operation is already in progress"

This pattern keeps the UI responsive and provides immediate feedback
without the user needing to understand why a button is greyed out.

### 4.2 Operation Progress

When a long-running operation is in progress:
- A spinner or progress indicator is shown
- All action buttons respond with "An operation is already in progress"
  if clicked
- The output panel streams progress in real-time

### 4.3 Primary Workflow Buttons

The three primary workflow buttons follow a logical sequence:

| Button | Preconditions | Effect |
|---|---|---|
| **Validate** | Instance selected, program file selected | Parses YAML, previews changes, no API calls |
| **Run** | Validate has passed | Applies configuration to the instance |
| **Verify** | Run has completed | Re-reads instance and confirms all objects match spec |

### 4.4 Bottom Bar Buttons

Bottom bar buttons are organized into three groups. Each button
follows the never-disable pattern — clicking with unmet preconditions
emits a message to the output panel rather than disabling the button.

**Output utilities group:**

| Button | Preconditions | Effect |
|---|---|---|
| **Clear Output** | None | Clears the output panel |
| **Preview YAML** | Program file selected | Opens the YAML preview dialog (see Section 4.6) |
| **View Report** | None | Opens the most recent run or import report log file |

**Documentation group:**

| Button | Preconditions | Effect |
|---|---|---|
| **Generate Docs** | Instance selected with project folder and at least one YAML file | Generates the CRM Reference Manual |
| **Open Reference Docs** | Instance selected with project folder containing generated docs | Opens the generated `.docx` reference manual |

**Data group:**

| Button | Preconditions | Effect |
|---|---|---|
| **Import Data** | Instance selected, no operation in progress | Opens the data import wizard |

### 4.5 Primary Workflow Buttons

The three primary workflow buttons follow a logical sequence:

| Button | Preconditions | Effect |
|---|---|---|
| **Validate** | Instance selected, program file selected | Parses YAML, previews changes, no API calls |
| **Run** | Validate has passed | Applies configuration to the instance |
| **Verify** | Run has completed | Re-reads instance and confirms all objects match spec |

### 4.6 Preview YAML

The **Preview YAML** button opens a dialog showing a sortable,
searchable grid of all fields defined across the selected YAML
program file. It allows the user to inspect and review the full
field configuration before running Validate or Run.

The grid displays one row per field with all field properties as
columns. The user can:
- Sort by any column
- Search/filter to find specific fields
- Review field descriptions, types, categories, and enum values

Preview YAML makes no API calls — it reads only from the local
YAML file. It is particularly useful for reviewing a large
configuration before deployment and for cross-referencing with
the generated reference manual.

---

## 5. Modal Dialogs

### 5.1 When to Use Dialogs

Modal dialogs are used for:
- Collecting input for a new or edited object (instances, program files)
- Confirming destructive operations before they execute
- Multi-step wizards for complex features (data import, etc.)

### 5.2 Add / Edit Dialogs

Add and Edit dialogs for managed objects (instances, program files, etc.)
follow this pattern:
- Pre-populated with current values when editing
- Validated inline before saving
- **Save** / **Cancel** buttons
- Cancel discards all changes with no prompt

### 5.3 Destructive Operation Confirmation

Any operation that permanently deletes or irreversibly modifies CRM
objects requires a confirmation dialog before any API calls are made —
including non-destructive operations in the same batch.

The confirmation dialog must:
- List all objects that will be affected, using their CRM internal names
- State clearly that the action cannot be undone
- Require the user to type a confirmation keyword (e.g., `DELETE`) to
  enable the Proceed button
- Provide a Cancel option that returns to the main window with no changes

The Proceed button remains disabled until the exact confirmation keyword
is entered (case-sensitive).

### 5.4 Multi-Step Wizards

Features that involve a sequence of distinct steps use a wizard dialog
pattern:
- Each step is presented in sequence; the user cannot skip ahead
- **Back** and **Next** / **Proceed** buttons navigate between steps
- **Next** is only enabled when the current step's requirements are met
- A final action button (e.g., **Import**, **Deploy**) is labeled to
  clearly indicate it is the point of no return
- **Close** or **Cancel** is available at any step and discards the
  operation

---

## 6. List Panels

### 6.1 Managed Object Lists

Lists of managed objects (instances, program files) follow a consistent
pattern:
- Single-click to select
- Selection persists until changed or the list is refreshed
- **+ Add**, **Edit**, and **Delete** buttons manage the selected item
- Delete prompts for confirmation before removing

### 6.2 Selection Feedback

When an item is selected in a list panel, any dependent panels or fields
update immediately. For example, selecting an instance loads its program
files into the program file panel.

---

## 7. Background Operations

### 7.1 Threading Requirement

All operations that contact the CRM API must execute in a background
thread to keep the UI responsive during long-running operations. The
UI must never block or become unresponsive while an operation is in
progress.

### 7.2 Output Streaming

Background operations communicate progress to the output panel via
thread-safe signals. Output appears in real-time as the operation
progresses, not as a batch at the end.

### 7.3 Operation Completion

When a background operation completes (success or failure), the UI
returns to its ready state and the View Report button activates if a
report was produced. The output panel retains all output from the
completed operation.

---

## 8. Error Presentation

### 8.1 Field and Object Errors

Errors on individual objects during a Run or Verify operation are
logged to the output panel in red and counted in the summary block.
An error on one object does not abort processing of subsequent objects
— the operation continues and all errors are reported together.

### 8.2 Fatal Errors

Certain errors abort the entire operation immediately:
- Authentication failure (HTTP 401) — the user's credentials are
  invalid; no further API calls are made
- Connection failure — the instance is unreachable

Fatal errors are reported to the output panel in red with a clear
explanation, and the operation terminates.

### 8.3 YAML Errors

YAML parse errors and validation failures are shown in the output panel
during Validate. Each error is reported individually with enough detail
for the user to locate and fix it. The Run button remains unavailable
until a clean Validate pass.

---

## 9. Instance and Project Folder Awareness

### 9.1 Instance Context

All operations are performed against the currently selected instance.
The selected instance is always visible to the user. Switching instances
mid-session is permitted but does not affect any operation already in
progress.

### 9.2 Project Folder

Each instance may be associated with a project folder on the local
filesystem. When a project folder is configured:
- Program files are loaded from the folder's `programs/` subdirectory
- Reports are written to the folder's `reports/` subdirectory
- Generated documentation is written to the folder's
  `Implementation Docs/` subdirectory

When no project folder is configured, the application falls back to
its own internal directories for programs and reports. Features that
require a project folder (such as Generate Docs) show an explanatory
message prompting the user to configure one.

### 9.3 Automatic Directory Creation

When an instance with a project folder is saved, the required
subdirectories (`programs/`, `reports/`, `Implementation Docs/`) are
created automatically if they do not exist.

---

## 10. Authentication Display

Credentials stored in instance profiles are never shown in plain text
in the UI. Password and API key fields display masked values (e.g.,
`••••••••••••`). The user may reveal a credential field explicitly
if the UI provides a show/hide toggle.

---

## 11. Accessibility and Usability

- All dialogs are keyboard-navigable
- Tab order follows logical reading order
- Confirmation dialogs default focus to the Cancel button, not Proceed
- Destructive actions are never the default action in any dialog
- Error messages describe what went wrong and, where possible, what the
  user should do to resolve it
