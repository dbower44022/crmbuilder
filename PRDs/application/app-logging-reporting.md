# CRM Builder — Logging & Reporting

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Applies To:** All features that produce operation output or reports

---

## 1. Purpose

This document defines the logging and reporting conventions that apply
across the entire CRM Builder application. All features that perform
operations against a CRM instance must follow these conventions to
ensure consistent output, consistent report formats, and a predictable
audit trail.

---

## 2. Two Output Channels

Every CRM Builder operation produces output in two channels:

**Real-time output panel** — streamed to the UI as the operation
progresses. Provides immediate feedback to the user. See
`app-ui-patterns.md` for color coding and message format conventions.

**Written reports** — persisted to the filesystem after the operation
completes. Provides a permanent audit record. Defined in this document.

Both channels record the same events. The output panel is transient
(cleared when the session ends or the user clicks Clear Output); the
written reports are permanent.

---

## 3. Report Files

### 3.1 Format Pairs

Every operation that modifies or inspects a CRM instance produces
two report files:

- **`.log`** — human-readable text report
- **`.json`** — machine-readable structured report

Both files are produced for every operation. Neither is optional.

### 3.2 Storage Location

Report files are written to the instance's `reports/` directory
(within the project folder). If no project folder is configured,
reports fall back to the application's internal `reports/` directory.

Reports are never written to a temporary location and then moved —
they are written directly to their final location.

### 3.3 Filename Format

```
{instance_slug}_{operation}_{YYYYMMDD_HHMMSS}.{ext}
```

| Component | Description |
|---|---|
| `instance_slug` | Lowercase, underscored form of the instance name |
| `operation` | The operation type: `run`, `verify`, `import`, `deploy` |
| `YYYYMMDD_HHMMSS` | Local timestamp at the start of the operation |
| `ext` | `log` or `json` |

Examples:
```
cbm_production_run_20260323_155604.log
cbm_production_run_20260323_155604.json
cbm_production_verify_20260324_090112.log
cbm_production_import_20260325_143022.json
```

### 3.4 File Retention

Report files are never automatically deleted by the application.
Management of old reports (archiving, deletion) is left to the user.

---

## 4. Log File Format (.log)

### 4.1 Structure

Every log file contains three sections in order:

1. **Header** — operation metadata
2. **Detail** — per-object narrative log
3. **Summary** — totals and report file paths

### 4.2 Header

```
========================================
CRM Builder — {Operation Type} Report
========================================
Timestamp     : 2026-03-23 15:56:04
Instance      : CBM Production
URL           : https://cbm.espocloud.com
Program File  : cbm_contact_fields.yaml
Operation     : run
========================================
```

The fields present in the header vary by operation type. All headers
include at minimum: Timestamp, Instance, and Operation. Additional
fields (URL, Program File, Source File, etc.) are included as relevant
to the operation.

### 4.3 Detail Section

The detail section records each object processed, one entry per object.
The format varies by feature but follows the same general pattern:

```
[STATUS]  Object identifier
  Detail line 1
  Detail line 2
```

Examples from different features:

```
[CREATED]  Contact.isMentor
  Type: bool
  Label: Is Mentor

[UPDATED]  Contact.contactType
  Changed: label, options

[SKIPPED]  Contact.mentorStatus
  Reason: No changes needed

[ERROR]    Contact.badField
  HTTP 400: Field type not supported
  Response: {"error": "Field 'badField' type 'unknown' is not valid"}
```

Error entries must always include the HTTP status code and the full
response body from the CRM API so the user has enough information to
diagnose the problem.

### 4.4 Summary Section

```
===========================================
{OPERATION TYPE} SUMMARY
===========================================
Total processed : 12
  Created       :  4
  Updated       :  3
  Skipped       :  4
  Errors        :  1
===========================================
Reports written to:
  reports/cbm_production_run_20260323_155604.log
  reports/cbm_production_run_20260323_155604.json
===========================================
```

The specific counters in the summary vary by operation. All summaries
include at minimum: total processed and errors. The report file paths
are always listed at the end.

---

## 5. JSON Report Format (.json)

### 5.1 Structure

Every JSON report contains three top-level keys:

```json
{
  "run_metadata": { ... },
  "summary": { ... },
  "results": [ ... ]
}
```

### 5.2 Metadata Object

```json
{
  "run_metadata": {
    "timestamp": "2026-03-23T15:56:04Z",
    "instance": "CBM Production",
    "espocrm_url": "https://cbm.espocloud.com",
    "program_file": "cbm_contact_fields.yaml",
    "operation": "run"
  }
}
```

Fields present in `run_metadata` vary by operation type. All metadata
objects include: `timestamp` (ISO 8601), `instance`, and `operation`.
Additional fields are included as relevant.

### 5.3 Summary Object

```json
{
  "summary": {
    "total": 12,
    "created": 4,
    "updated": 3,
    "skipped": 4,
    "errors": 1
  }
}
```

The counters present in `summary` match those shown in the log file
summary section. All summary objects include at minimum: `total` and
`errors`.

### 5.4 Results Array

```json
{
  "results": [
    {
      "entity": "Contact",
      "object": "isMentor",
      "status": "created",
      "verified": true,
      "changes": null,
      "error": null
    },
    {
      "entity": "Contact",
      "object": "contactType",
      "status": "updated",
      "verified": true,
      "changes": ["label", "options"],
      "error": null
    },
    {
      "entity": "Contact",
      "object": "badField",
      "status": "error",
      "verified": false,
      "changes": null,
      "error": "HTTP 400: Field type not supported"
    }
  ]
}
```

Each result object represents one processed item. The fields present
vary by feature. All result objects include at minimum: a status string
and an error field (null if no error).

### 5.5 Status Values

Status values in the results array use lowercase strings. Each feature
defines its own set of valid status values, but the following are
standard across all features:

| Status | Meaning |
|---|---|
| `created` | Object did not exist and was successfully created |
| `updated` | Object existed and was successfully updated |
| `skipped` | Object was not changed (already correct, or intentionally skipped) |
| `verified` | Object was confirmed to match the spec (Verify operation) |
| `error` | Operation failed; see `error` field for details |

Features may define additional status values as needed
(e.g., `verification_failed`, `skipped_type_conflict`). Additional
values must be documented in the relevant feature PRD.

---

## 6. Error Logging Requirements

### 6.1 What Must Be Logged

Every error must be logged with sufficient detail to diagnose the
problem without needing to reproduce it:

- The object that failed (entity name, field name, or equivalent)
- The operation that was attempted (create, update, verify, etc.)
- The HTTP status code returned by the CRM API
- The full response body from the CRM API

### 6.2 Continue-and-Log

Errors on individual objects do not abort an operation. The operation
continues with the next object and all errors are reported together in
the summary. The only exceptions are fatal errors (see Section 6.3).

### 6.3 Fatal Errors

The following conditions abort the entire operation immediately and
are reported as a fatal error in the output panel and log file:

- **HTTP 401 Unauthorized** — credentials are invalid or expired
- **Connection failure** — the CRM instance is unreachable

When a fatal error occurs, the log file is still written with whatever
was completed before the abort, and the summary clearly indicates that
the operation did not complete.

---

## 7. Operation Coverage

The following operations produce reports. Each feature PRD defines
the specific fields and counters for its operation type.

| Operation | Trigger | Log Label |
|---|---|---|
| Run | User clicks Run | `run` |
| Verify | User clicks Verify | `verify` |
| Import | User completes import wizard | `import` |
| Deploy | CRM Deployment phase completes | `deploy` |

Additional operation types may be added as new features are introduced.
Each must follow the conventions defined in this document.

---

## 8. Report Access

### 8.1 View Report Button

After any operation that produces a report, the **View Report** button
in the main window becomes active. Clicking it opens the `.log` file
for the most recently completed operation in the system's default
text viewer.

### 8.2 Report Discovery

Reports are stored with predictable filenames in the instance's
`reports/` directory. Users can browse and open historical reports
directly from the filesystem. The application does not provide a
built-in report browser.
