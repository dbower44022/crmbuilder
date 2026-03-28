# CRM Builder — Field Management Implementation Reference

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Requirements:** PRDs/features/feat-fields.md
**Maintained By:** Claude Code

---

## 1. Purpose

This document describes the implementation of field management in
CRM Builder — the `FieldManager` and `Comparator` classes, EspoCRM
API endpoints, payload construction, and the check/compare/act cycle.

---

## 2. File Locations

```
espo_impl/core/field_manager.py    # Field CHECK→ACT orchestration
espo_impl/core/comparator.py       # Field spec vs API state comparison
```

---

## 3. API Endpoints

| Operation | Method | Endpoint | Notes |
|---|---|---|---|
| Read field | GET | `/api/v1/Metadata?key=entityDefs.{Entity}.fields.{field}` | Primary lookup |
| Read field (fallback) | GET | `/api/v1/Admin/fieldManager/{Entity}/{field}` | Fallback if Metadata returns empty |
| Create field | POST | `/api/v1/Admin/fieldManager/{Entity}` | Body includes `isCustom: true` |
| Update field | PUT | `/api/v1/Admin/fieldManager/{Entity}/{field}` | Full field definition |

Entity names in all endpoints use the C-prefixed internal name
(e.g., `CEngagement`, `Contact`). Field names in GET and PUT use
the c-prefixed name (e.g., `cContactType`). Field names in POST
payloads use the natural name (e.g., `contactType`) — EspoCRM adds
the prefix automatically on creation.

---

## 4. FieldManager Class

```python
class FieldManager:
    def __init__(self, client: EspoAdminClient, output_cb: Callable):
        self.client = client
        self.output = output_cb
        self.comparator = Comparator()
```

### 4.1 Main Entry Point

```python
def run(self, program: ProgramFile) -> RunReport:
    """
    Process all fields in all entities in the program file.
    Skips entities with action DELETE (no fields to process).
    Returns a RunReport with results for all fields.
    """
```

### 4.2 Field Resolution

Fields are looked up using both the c-prefixed and natural names
because native EspoCRM fields (like `name`, `emailAddress`) don't
have a c-prefix:

```python
def _get_field_resolved(
    self, espo_entity: str, field_name: str
) -> tuple[int, dict | None, str]:
    """
    Returns (status_code, body, resolved_name).
    Tries c-prefixed name first, then natural name fallback.
    """
    c_name = _custom_field_name(field_name)
    status, body = self.client.get_field(espo_entity, c_name)

    if status == 200 and body:
        return status, body, c_name

    # Fallback to natural name for native/system fields
    status, body = self.client.get_field(espo_entity, field_name)
    return status, body, field_name
```

### 4.3 Field Processing Cycle

```python
def _process_field(
    self, espo_entity: str, field_def: FieldDefinition
) -> FieldResult:

    self.output(f"[CHECK]   {espo_entity}.{field_def.name} ...", "white")
    status, current, resolved_name = self._get_field_resolved(
        espo_entity, field_def.name
    )

    if status == 404 or not current:
        # Field does not exist — create
        return self._create_field(espo_entity, field_def)

    if status != 200:
        self.output(f"... ERROR (HTTP {status})", "red")
        return FieldResult(espo_entity, field_def.name, FieldStatus.ERROR,
                           error=f"HTTP {status}")

    # Field exists — compare
    result = self.comparator.compare(field_def, current)

    if result.type_conflict:
        self.output(f"... TYPE CONFLICT", "yellow")
        return FieldResult(espo_entity, field_def.name,
                           FieldStatus.SKIPPED_TYPE_CONFLICT)

    if result.matches:
        self.output(f"... MATCHES", "gray")
        self.output(f"[SKIP]    {espo_entity}.{field_def.name} "
                    f"... NO CHANGES NEEDED", "gray")
        return FieldResult(espo_entity, field_def.name, FieldStatus.SKIPPED)

    self.output(f"... DIFFERS ({', '.join(result.differences)})", "white")
    return self._update_field(espo_entity, field_def, resolved_name)
```

### 4.4 Create

```python
def _create_field(self, espo_entity, field_def) -> FieldResult:
    self.output(f"[CREATE]  {espo_entity}.{field_def.name} ...", "white")
    payload = self._build_payload(field_def)
    payload["isCustom"] = True     # required for all custom field creates

    status, body = self.client.create_field(espo_entity, payload)

    if status == 200:
        self.output("... OK", "green")
        return FieldResult(espo_entity, field_def.name, FieldStatus.CREATED)

    if status == 409:
        # Field already exists under c-prefixed name — fall back to update
        c_name = self._extract_field_name_from_409(body)
        if c_name:
            return self._update_field(espo_entity, field_def, c_name)

    self.output(f"... ERROR (HTTP {status})", "red")
    return FieldResult(espo_entity, field_def.name, FieldStatus.ERROR,
                       error=f"HTTP {status}: {body}")
```

### 4.5 409 Conflict Recovery

When a CREATE returns HTTP 409, the field already exists under its
c-prefixed name. EspoCRM returns the actual field name in the error
response:

```python
def _extract_field_name_from_409(self, body: dict) -> str | None:
    try:
        return body["messageTranslation"]["data"]["field"]
        # e.g., "cContactType"
    except (KeyError, TypeError):
        return None
```

If extraction succeeds, the operation falls back to an UPDATE using
the returned c-prefixed name. If extraction fails, the error is logged
and the field is marked as ERROR.

### 4.6 Update

```python
def _update_field(self, espo_entity, field_def, resolved_name) -> FieldResult:
    self.output(f"[UPDATE]  {espo_entity}.{field_def.name} ...", "white")
    payload = self._build_payload(field_def)
    status, body = self.client.update_field(espo_entity, resolved_name, payload)

    if status == 200:
        self.output("... OK", "green")
        return FieldResult(espo_entity, field_def.name, FieldStatus.UPDATED)

    self.output(f"... ERROR (HTTP {status})", "red")
    return FieldResult(espo_entity, field_def.name, FieldStatus.ERROR,
                       error=f"HTTP {status}: {body}")
```

### 4.7 Payload Construction

```python
def _build_payload(self, field_def: FieldDefinition) -> dict:
    payload = {
        "name": field_def.name,
        "type": field_def.type,
        "label": field_def.label,
    }
    # Only include optional properties if explicitly set in YAML
    if field_def.required is not None:
        payload["required"] = field_def.required
    if field_def.default is not None:
        payload["default"] = field_def.default
    if field_def.readOnly is not None:
        payload["readOnly"] = field_def.readOnly
    if field_def.audited is not None:
        payload["audited"] = field_def.audited
    if field_def.options is not None:
        payload["options"] = field_def.options
    if field_def.translatedOptions is not None:
        payload["translatedOptions"] = field_def.translatedOptions
    if field_def.style is not None:
        payload["style"] = field_def.style
    if field_def.isSorted is not None:
        payload["isSorted"] = field_def.isSorted
    if field_def.displayAsLabel is not None:
        payload["displayAsLabel"] = field_def.displayAsLabel
    if field_def.min is not None:
        payload["min"] = field_def.min
    if field_def.max is not None:
        payload["max"] = field_def.max
    if field_def.maxLength is not None:
        payload["maxLength"] = field_def.maxLength
    return payload
```

Note: `description` and `category` are not included in the API
payload — they exist only in the YAML for documentation and layout
purposes.

---

## 5. Inline Verification

Inline verification (re-reading the field after create/update) is
**disabled**. EspoCRM's cache may return stale data or HTTP 500
immediately after a write. The standalone Verify button should be
used after the cache settles.

---

## 6. Comparator (`core/comparator.py`)

### 6.1 ComparisonResult

```python
@dataclass
class ComparisonResult:
    matches: bool
    differences: list[str]
    type_conflict: bool
```

### 6.2 compare()

```python
def compare(
    self, spec: FieldDefinition, current: dict
) -> ComparisonResult:
    """
    Compares a FieldDefinition (desired) against the API response dict
    (current). Returns ComparisonResult.
    """
```

### 6.3 Comparison Rules

1. **Type check first** — if `spec.type != current.get("type")`,
   return `ComparisonResult(matches=False, differences=[], type_conflict=True)`

2. **Only compare specified properties** — if a property is `None`
   in the spec, it is not compared:

```python
COMPARABLE_PROPERTIES = [
    "label", "required", "default", "readOnly", "audited",
    "min", "max", "maxLength",
]

for prop in COMPARABLE_PROPERTIES:
    spec_val = getattr(spec, prop)
    if spec_val is None:
        continue    # not specified in YAML — skip comparison
    current_val = current.get(prop)
    if spec_val != current_val:
        differences.append(prop)
```

3. **Enum/multiEnum additional properties** — compared only when
   the field type is `enum` or `multiEnum`:

```python
if spec.type in ("enum", "multiEnum"):
    if spec.options is not None and spec.options != current.get("options"):
        differences.append("options")
    if spec.translatedOptions is not None and \
       spec.translatedOptions != current.get("translatedOptions"):
        differences.append("translatedOptions")
    if spec.style is not None and spec.style != current.get("style"):
        differences.append("style")
```

4. **Options order is significant** — `["A", "B"] != ["B", "A"]`

---

## 7. API Client Methods

```python
def get_field(self, entity: str, field_name: str) -> tuple[int, dict | None]:
    status, body = self._request("GET",
        f"Metadata?key=entityDefs.{entity}.fields.{field_name}")
    if status == 200 and body:
        return status, body
    # Fallback
    return self._request("GET",
        f"Admin/fieldManager/{entity}/{field_name}")

def create_field(self, entity: str, payload: dict) -> tuple[int, dict | None]:
    return self._request("POST", f"Admin/fieldManager/{entity}", json=payload)

def update_field(
    self, entity: str, field_name: str, payload: dict
) -> tuple[int, dict | None]:
    return self._request("PUT",
        f"Admin/fieldManager/{entity}/{field_name}", json=payload)
```

---

## 8. Error Handling

| Error | Behavior |
|---|---|
| HTTP 401 | Raises `FieldManagerError` — aborts entire run |
| HTTP 403 | Logs error, marks as ERROR, continues |
| HTTP 409 on CREATE | Attempts 409 recovery (see Section 4.5) |
| HTTP 4xx/5xx on POST/PUT | Logs error and response body, marks as ERROR, continues |
| Type mismatch | Logs warning, marks as SKIPPED_TYPE_CONFLICT, continues |
| Network error (-1) | Logs error, marks as ERROR, continues |

```python
class FieldManagerError(Exception):
    """Raised on HTTP 401 to abort the entire run."""
```

---

## 9. Testing

`field_manager.py` is covered by `tests/test_field_manager.py` and
`comparator.py` by `tests/test_comparator.py`:

**FieldManager tests:**

| Test Area | Cases |
|---|---|
| Create flow | 404 on GET → POST called, CREATED result |
| Update flow | 200 on GET, differs → PUT called, UPDATED result |
| Skip flow | 200 on GET, matches → no PUT, SKIPPED result |
| 409 recovery | 409 on POST → name extracted → PUT called |
| Type conflict | Type differs → SKIPPED_TYPE_CONFLICT, no PUT |
| HTTP 401 | `FieldManagerError` raised |
| HTTP 5xx | ERROR result, continues to next field |

**Comparator tests:**

| Test Area | Cases |
|---|---|
| Exact match | All specified properties match → matches=True |
| Label differs | label mismatch → differences=["label"] |
| Options differs | options mismatch (order sensitive) → differences=["options"] |
| Type conflict | type mismatch → type_conflict=True |
| None properties skipped | Unspecified YAML props not compared |

Mocking pattern:

```python
def test_field_create_flow():
    client = MagicMock()
    client.get_field.return_value = (404, None)
    client.create_field.return_value = (200, {})

    output = []
    mgr = FieldManager(client, lambda m, c: output.append(m))

    field_def = FieldDefinition(name="isMentor", type="bool", label="Is Mentor")
    result = mgr._process_field("Contact", field_def)

    assert result.status == FieldStatus.CREATED
    client.create_field.assert_called_once()
    payload = client.create_field.call_args[0][1]
    assert payload["isCustom"] is True
```
