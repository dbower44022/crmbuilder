# CRM Builder — Data Import Implementation Reference

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Requirements:** PRDs/features/feat-data-import.md
**Maintained By:** Claude Code

---

## 1. Purpose

This document describes the implementation of the data import feature
in CRM Builder — the `ImportManager` class, import wizard dialog,
background workers, field mapping, auto-mapping, record matching, and
data transformations.

---

## 2. File Locations

```
espo_impl/core/import_manager.py       # CHECK and ACT business logic
espo_impl/ui/import_dialog.py          # Four-step wizard dialog (PySide6)
espo_impl/workers/import_worker.py     # QThread background worker
```

---

## 3. API Endpoints

| Operation | Method | Endpoint | Notes |
|---|---|---|---|
| Get entity field list | GET | `/api/v1/Metadata?key=entityDefs.{Entity}.fields` | All field definitions |
| Search by email | GET | `/api/v1/{Entity}?where[0][type]=equals&where[0][attribute]=emailAddress&where[0][value]={email}&maxSize=2` | maxSize=2 detects duplicates |
| Get single record | GET | `/api/v1/{Entity}/{id}` | Fetch full record for never-overwrite check |
| Create record | POST | `/api/v1/{Entity}` | Full payload |
| Patch record | PATCH | `/api/v1/{Entity}/{id}` | Partial payload — only empty fields |

---

## 4. Data Models

```python
class ImportAction(Enum):
    CREATE = "create"
    UPDATE = "update"
    SKIP = "skip"
    ERROR = "error"

@dataclass
class RecordPlan:
    source_name: str
    email: str | None
    action: ImportAction
    espo_id: str | None          # set if existing record found
    fields_to_set: dict          # payload for CREATE or PATCH
    fields_skipped: list[str]    # fields with existing values
    error_message: str | None = None

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

## 5. ImportManager Class

```python
class ImportManager:
    def __init__(self, client: EspoAdminClient):
        self.client = client
```

### 5.1 CHECK Phase

```python
def check(
    self,
    entity: str,
    records: list[dict],
    field_mapping: dict[str, str],    # source_key → espo_field_name
    fixed_values: dict[str, any],     # espo_field_name → value
    output_cb: Callable,
) -> list[RecordPlan]:
    """
    For each record, determine action (CREATE/UPDATE/SKIP/ERROR).
    Returns list of RecordPlan — no API writes are made.
    """
```

For each source record:

1. Build candidate payload from `field_mapping` and `fixed_values`
2. Apply data transformations (see Section 8)
3. Find email address from payload
4. If no email → `RecordPlan(action=ERROR, error="no email address")`
5. `GET /api/v1/{Entity}?where...email={email}&maxSize=2`
6. If 0 results → `CREATE` with full payload
7. If 2 results → use first, log WARNING about duplicate
8. If 1 result → `GET /api/v1/{Entity}/{id}` for full record
9. Compare each mapped field against existing record:
   - `None` or `""` → include in `fields_to_set`
   - Non-empty → add to `fields_skipped`
10. If all fields skipped → `SKIP`; else → `UPDATE`

### 5.2 ACT Phase

```python
def execute(
    self,
    entity: str,
    plans: list[RecordPlan],
    output_cb: Callable,
) -> ImportReport:
    """
    Execute pre-computed RecordPlan objects.
    Returns ImportReport with results for all records.
    """
```

For each plan:
- `CREATE` → `POST /api/v1/{entity}` with `fields_to_set`
- `UPDATE` → `PATCH /api/v1/{entity}/{espo_id}` with `fields_to_set`
- `SKIP` / `ERROR` → logged, no API call

Errors on individual records do not abort the import. Each record's
outcome is logged with full field=value detail.

---

## 6. Field Mapping

### 6.1 Field List Fetch

The entity field list is fetched once when the entity type is selected
in Step 1 and cached for the duration of the wizard session:

```python
status, body = client.get_entity_field_list(entity)
# body is a dict of {fieldName: {type, label, readOnly, notStorable, ...}}
```

### 6.2 Non-Writable Field Exclusion

The following are excluded from the mapping dropdown:

```python
NON_WRITABLE_TYPES = {
    "personName", "address", "map", "foreign",
    "linkParent", "autoincrement",
}

def is_writable(field_name: str, field_meta: dict) -> bool:
    return (
        field_meta.get("type") not in NON_WRITABLE_TYPES
        and not field_meta.get("readOnly", False)
        and not field_meta.get("notStorable", False)
    )
```

### 6.3 Dropdown Display Format

Each field option in the mapping dropdown is shown as:
```
{label} — {internalName}
# e.g., "Email Address — emailAddress"
```

Dropdowns are searchable — `setEditable(True)` with
`QCompleter.MatchContains` for type-to-filter search.

---

## 7. Auto-Mapping

Auto-mapping runs when the Step 2 mapping table is first built.
Three steps in order:

**Step 1 — Exact label match (case-insensitive):**
```python
for source_key in source_keys:
    for field_name, meta in crm_fields.items():
        if source_key.lower() == meta["label"].lower():
            mapping[source_key] = field_name
            break
```

**Step 2 — Normalized match:**
```python
def normalize(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())

for source_key in unmapped:
    norm_key = normalize(source_key)
    for field_name, meta in crm_fields.items():
        if norm_key == normalize(meta["label"]):
            mapping[source_key] = field_name
            break
```

**Step 3 — Known alias table (Contact entity):**
```python
CONTACT_ALIASES = {
    "Contact Name":    "name",
    "Preferred Name":  "firstName",
    "Email":           "emailAddress",
    "SCORE Email":     "emailAddress",
    "Phone":           "phoneNumber",
    "Personal Email":  None,          # → skip
    "Mailing Address": "address",
    "Birth Year":      "cBirthYear",
    "Gender":          "cGender",
}
```

Fields with no match default to `(skip)` and appear in the Unmapped
Fields panel. Auto-mapping is always overridable by the user.

---

## 8. Data Transformations

### 8.1 Phone Number Cleaning

```python
def clean_phone(raw: str) -> str | None:
    digits = re.sub(r'\D', '', raw)
    if len(digits) == 10:
        return f"+1{digits}"           # US 10-digit
    if len(digits) == 11 and digits[0] == '1':
        return f"+{digits}"            # US 11-digit with country code
    return raw                          # pass through unchanged
```

### 8.2 Name Derivation

Applied when `firstName` or `lastName` are not explicitly mapped:

```python
SALUTATIONS = {"mr", "mrs", "ms", "miss", "dr", "prof"}

def derive_name(display_name: str, email: str | None) -> tuple[str, str]:
    """Returns (first_name, last_name)."""
    parts = display_name.strip().split()

    # Strip salutation
    if parts and parts[0].rstrip('.').lower() in SALUTATIONS:
        parts = parts[1:]

    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])

    # Fallback: parse from email
    if email:
        local = email.split("@")[0]
        if "." in local:
            first, *rest = local.split(".")
            return first.capitalize(), rest[-1].capitalize()

    return display_name, ""
```

### 8.3 Boolean Conversion

Fixed-value strings `"true"` and `"false"` are converted before
being added to the payload:

```python
def convert_fixed_value(value: str) -> any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value
```

### 8.4 Empty Value Filtering

Empty string values are excluded from payloads — treated as absent:

```python
payload = {k: v for k, v in raw_payload.items() if v != "" and v is not None}
```

---

## 9. Import Dialog (`ui/import_dialog.py`)

### 9.1 Structure

A `QDialog` with a `QStackedWidget` containing four pages:

| Step | Widget | Background Worker |
|---|---|---|
| 1 — Setup | File picker, entity combo, fixed-value table | None (sync field fetch) |
| 2 — Mapping | Mapping table with searchable combos, unmapped list | None |
| 3 — Preview | Scroll area with per-record plans, summary counts | `CheckWorker` (QThread) |
| 4 — Execute | Output panel, summary, View Report | `ImportWorker` (QThread) |

The dialog is fully self-contained — it does not interact with the
main window's `UIState`. The `EspoAdminClient` is passed in at
instantiation.

### 9.2 Step 1 — Fixed-Value Table

The fixed-value table is a `QTableWidget` with two columns: Field
(combo box) and Value (line edit). `[+ Add Field]` appends a new row;
`[✕]` on each row removes it.

The Field combo box is populated from the CRM field list fetched when
the entity type is selected. Fixed-value fields are excluded from the
mapping dropdown in Step 2.

### 9.3 Step 2 — Mapping Table

The mapping table is a `QTableWidget`. The right column uses
`QComboBox` with `setEditable(True)` and a `QCompleter` set to
`MatchContains` for searchable dropdowns.

The Unmapped Fields panel below is a `QListWidget` that updates live
as the user changes dropdown selections, connected via the combo
`currentIndexChanged` signal.

### 9.4 Step 3 — Preview

The preview is built by `CheckWorker` running `import_manager.check()`
in a background thread. Each `RecordPlan` is rendered as a collapsible
or scrollable card in the scroll area. Summary counts update when
`CheckWorker` completes.

### 9.5 Step 4 — Execute

`ImportWorker` runs `import_manager.execute()` in a background thread,
emitting `output_line` signals for each record processed. A progress
bar updates based on records completed vs total.

---

## 10. Background Workers

### 10.1 CheckWorker

```python
class CheckWorker(QThread):
    output_line = Signal(str, str)
    finished_ok = Signal(list)     # list[RecordPlan]
    finished_error = Signal(str)

    def run(self):
        try:
            plans = self.import_mgr.check(
                self.entity, self.records,
                self.field_mapping, self.fixed_values,
                lambda msg, color: self.output_line.emit(msg, color)
            )
            self.finished_ok.emit(plans)
        except Exception as e:
            self.finished_error.emit(str(e))
```

### 10.2 ImportWorker

```python
class ImportWorker(QThread):
    output_line = Signal(str, str)
    finished_ok = Signal(object)    # ImportReport
    finished_error = Signal(str)

    def run(self):
        try:
            report = self.import_mgr.execute(
                self.entity, self.plans,
                lambda msg, color: self.output_line.emit(msg, color)
            )
            self.finished_ok.emit(report)
        except Exception as e:
            self.finished_error.emit(str(e))
```

---

## 11. API Client Methods

```python
def get_entity_field_list(
    self, entity: str
) -> tuple[int, dict | None]:
    return self._request("GET",
        f"Metadata?key=entityDefs.{entity}.fields")

def search_by_email(
    self, entity: str, email: str
) -> tuple[int, dict | None]:
    encoded = urllib.parse.quote(email)
    return self._request("GET",
        f"{entity}?where[0][type]=equals"
        f"&where[0][attribute]=emailAddress"
        f"&where[0][value]={encoded}"
        f"&maxSize=2")

def get_record(
    self, entity: str, record_id: str
) -> tuple[int, dict | None]:
    return self._request("GET", f"{entity}/{record_id}")

def create_record(
    self, entity: str, payload: dict
) -> tuple[int, dict | None]:
    return self._request("POST", entity, json=payload)

def patch_record(
    self, entity: str, record_id: str, payload: dict
) -> tuple[int, dict | None]:
    return self._request("PATCH", f"{entity}/{record_id}", json=payload)
```

---

## 12. Error Handling

| Error | Behavior |
|---|---|
| Record has no email | Logged as ERROR, record skipped |
| Duplicate email in CRM | Warning logged, first result used |
| HTTP 4xx on CREATE/PATCH | Error logged with full response body, continues |
| Network error | Error logged, record marked as ERROR, continues |
| JSON parse error on source file | Shown in Step 1, prevents advance to Step 2 |

Import operations use continue-and-log — no individual record error
aborts the import.

---

## 13. Testing

`import_manager.py` is covered by `tests/test_import_manager.py`:

| Test Area | Cases |
|---|---|
| CHECK — no existing record | CREATE plan, full payload |
| CHECK — existing, empty fields | UPDATE plan, only empty fields in payload |
| CHECK — existing, all fields set | SKIP plan |
| CHECK — no email | ERROR plan |
| CHECK — duplicate email | WARNING logged, first result used |
| ACT — CREATE | POST called, result recorded |
| ACT — UPDATE | PATCH called with partial payload |
| ACT — SKIP/ERROR | No API call |
| Phone cleaning | 10-digit → +1, 11-digit → +, unchanged otherwise |
| Name derivation | Salutation stripped, email fallback |
| Boolean conversion | "true"→True, "false"→False |
| Empty filtering | Empty strings excluded from payload |

Mocking pattern:

```python
def test_check_creates_when_not_found():
    client = MagicMock()
    client.search_by_email.return_value = (200, {"list": [], "total": 0})

    mgr = ImportManager(client)
    records = [{"name": "Jane Smith", "fields": {"Email": "jane@example.com"}}]
    mapping = {"Email": "emailAddress"}
    fixed = {}

    plans = mgr.check("Contact", records, mapping, fixed, lambda m, c: None)

    assert len(plans) == 1
    assert plans[0].action == ImportAction.CREATE
    assert "emailAddress" in plans[0].fields_to_set
```
