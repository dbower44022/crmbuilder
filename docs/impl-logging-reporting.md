# CRM Builder — Logging & Reporting Implementation Reference

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Requirements:** PRDs/application/app-logging-reporting.md
**Maintained By:** Claude Code

---

## 1. Purpose

This document describes the implementation of CRM Builder's logging
and reporting system — the `Reporter` class, file naming, report
formats, and how reports are integrated into the run and import
workflows.

---

## 2. File Location

```
espo_impl/core/reporter.py
```

---

## 3. Reporter Class

`Reporter` is instantiated per operation with the instance profile
and operation type. It accumulates results during the operation and
writes both report files on completion.

```python
class Reporter:
    def __init__(
        self,
        instance: InstanceProfile,
        operation: str,           # "run", "verify", "import"
        program_file: str | None = None,
        reports_dir: Path | None = None,
    ):
        self.instance = instance
        self.operation = operation
        self.program_file = program_file
        self.reports_dir = reports_dir or Path("reports")
        self.timestamp = datetime.now()
        self.results: list[dict] = []
```

### 3.1 Instantiation

`Reporter` is created lazily in `_start_worker()` in `main_window.py`,
using the instance's `reports_dir` property (or `base_dir/reports/`
as fallback):

```python
reports_dir = self.state.instance.reports_dir or self.base_dir / "reports"
reporter = Reporter(
    instance=self.state.instance,
    operation="run",
    program_file=self.state.program_path.name,
    reports_dir=reports_dir,
)
```

### 3.2 Adding Results

Workers and managers call `reporter.add_result()` after each
processed object:

```python
reporter.add_result({
    "entity": "Contact",
    "object": "contactType",
    "status": "updated",
    "changes": ["label", "options"],
    "error": None,
})
```

### 3.3 Writing Reports

Called once at the end of the operation:

```python
log_path, json_path = reporter.write()
```

Returns the paths of both written files.

---

## 4. Filename Format

```python
def _build_filename(self, ext: str) -> str:
    slug = self.instance.slug
    op = self.operation
    ts = self.timestamp.strftime("%Y%m%d_%H%M%S")
    return f"{slug}_{op}_{ts}.{ext}"
```

Examples:
```
cbm_production_run_20260323_155604.log
cbm_production_run_20260323_155604.json
cbm_production_verify_20260324_090112.log
cbm_production_import_20260325_143022.json
```

The `reports_dir` is created automatically if it does not exist:
```python
self.reports_dir.mkdir(parents=True, exist_ok=True)
```

---

## 5. Log File Format (.log)

### 5.1 Header

```
========================================
CRM Builder — Run Report
========================================
Timestamp     : 2026-03-23 15:56:04
Instance      : CBM Production
URL           : https://cbm.espocloud.com
Program File  : cbm_contact_fields.yaml
Operation     : run
========================================
```

Header fields vary by operation type. Import reports include
`Source File` and `Entity` instead of `Program File`.

### 5.2 Detail Section

One entry per result, written in order of processing:

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

Error entries always include the full HTTP status and response body.

### 5.3 Summary Section

```
===========================================
RUN SUMMARY
===========================================
Total fields processed : 5
  Created              : 2
  Updated              : 1
  Skipped (no change)  : 1
  Errors               : 1
===========================================
Reports written to:
  reports/cbm_production_run_20260323_155604.log
  reports/cbm_production_run_20260323_155604.json
===========================================
```

---

## 6. JSON Report Format (.json)

```json
{
  "run_metadata": {
    "timestamp": "2026-03-23T15:56:04Z",
    "instance": "CBM Production",
    "espocrm_url": "https://cbm.espocloud.com",
    "program_file": "cbm_contact_fields.yaml",
    "operation": "run"
  },
  "summary": {
    "total": 5,
    "created": 2,
    "updated": 1,
    "skipped": 1,
    "errors": 1
  },
  "results": [
    {
      "entity": "Contact",
      "object": "isMentor",
      "status": "created",
      "verified": false,
      "changes": null,
      "error": null
    },
    {
      "entity": "Contact",
      "object": "contactType",
      "status": "updated",
      "verified": false,
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

---

## 7. Run Report Data Models (`core/models.py`)

```python
class FieldStatus(Enum):
    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    VERIFIED = "verified"
    VERIFICATION_FAILED = "verification_failed"
    SKIPPED_TYPE_CONFLICT = "skipped_type_conflict"
    ERROR = "error"

@dataclass
class FieldResult:
    entity: str
    field: str
    status: FieldStatus
    verified: bool = False
    changes: list[str] | None = None
    error: str | None = None

@dataclass
class RunSummary:
    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    verification_failed: int = 0
    errors: int = 0

@dataclass
class RunReport:
    timestamp: str
    instance_name: str
    espocrm_url: str
    program_file: str
    operation: str
    summary: RunSummary
    results: list[FieldResult]
    log_path: Path | None = None
    json_path: Path | None = None
```

---

## 8. Import Report Data Models (`core/models.py`)

```python
class ImportAction(Enum):
    CREATE = "create"
    UPDATE = "update"
    SKIP = "skip"
    ERROR = "error"

@dataclass
class ImportResult:
    source_name: str
    email: str | None
    action: ImportAction
    success: bool
    fields_set: list[str]
    fields_skipped: list[str]
    error_message: str | None = None

@dataclass
class ImportReport:
    timestamp: str
    instance_name: str
    entity: str
    source_file: str
    total: int
    created: int
    updated: int
    skipped: int
    errors: int
    results: list[ImportResult]
    log_path: Path | None = None
    json_path: Path | None = None
```

---

## 9. View Report Integration

After any operation that produces a report, `main_window.py` stores
the log file path in `self.state.last_report_path`. The View Report
button handler opens it:

```python
def _on_view_report_clicked(self):
    if not self.state.last_report_path:
        self._output("No report available.", "yellow")
        return
    import subprocess
    subprocess.Popen(["xdg-open", str(self.state.last_report_path)])
```

---

## 10. Testing

`reporter.py` is covered by `tests/test_reporter.py`:

| Test | Coverage |
|---|---|
| Filename format | Correct slug, operation, timestamp in filename |
| Directory creation | `reports_dir` created if not exists |
| Log file written | Header, detail, summary present |
| JSON file written | Valid JSON, correct schema |
| Both files returned | `write()` returns both paths |

Mocking pattern — `Reporter` is tested with a temp directory:

```python
def test_reporter_writes_files(tmp_path):
    instance = make_instance(name="CBM Test")
    reporter = Reporter(instance, "run", "test.yaml", tmp_path)
    reporter.add_result({...})
    log_path, json_path = reporter.write()
    assert log_path.exists()
    assert json_path.exists()
```
