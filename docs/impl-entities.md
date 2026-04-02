# CRM Builder — Entity Management Implementation Reference

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Requirements:** PRDs/features/feat-entities.md
**Maintained By:** Claude Code

---

## 1. Purpose

This document describes the implementation of entity management in
CRM Builder — the `EntityManager` class, EspoCRM API endpoints,
entity name mapping, and how entity operations fit into the run
workflow.

---

## 2. File Location

```
espo_impl/core/entity_manager.py
```

---

## 3. API Endpoints

All entity management endpoints use POST for both create and delete
operations. Note: these use the `EntityManager` controller, not
`Admin/entityManager`.

| Operation | Method | Endpoint | Notes |
|---|---|---|---|
| Check exists | GET | `/api/v1/Metadata?key=scopes.{EspoEntityName}` | Returns entity metadata if exists |
| Create | POST | `/api/v1/EntityManager/action/createEntity` | Uses natural name; EspoCRM adds C prefix |
| Delete | POST | `/api/v1/EntityManager/action/removeEntity` | Uses C-prefixed name |
| Rebuild cache | POST | `/api/v1/Admin/rebuild` | Required after create or delete |

---

## 4. EntityManager Class

```python
class EntityManager:
    def __init__(self, client: EspoAdminClient, output_cb: Callable):
        self.client = client
        self.output = output_cb    # output_cb(message, color)
```

### 4.1 Core Methods

```python
def process_entity(self, entity_def: EntityDefinition) -> bool:
    """Dispatches to create, delete, or delete_and_create."""

def _create_entity(self, entity_def: EntityDefinition) -> bool:
    """Checks existence, skips if exists, creates if not."""

def _delete_entity(self, entity_def: EntityDefinition) -> bool:
    """Checks existence, skips if not found, deletes if exists."""

def rebuild_cache(self) -> bool:
    """POST /api/v1/Admin/rebuild."""
```

### 4.2 Create Flow

```python
def _create_entity(self, entity_def):
    espo_name = get_espo_entity_name(entity_def.name)
    self.output(f"[ENTITY]  {entity_def.name} ... CHECKING", "white")

    status, body = self.client.check_entity_exists(espo_name)
    if status == 200 and body:
        self.output(f"[ENTITY]  {entity_def.name} ... EXISTS", "gray")
        self.output(f"[ENTITY]  {entity_def.name} ... SKIPPED", "gray")
        return True

    self.output(f"[ENTITY]  {entity_def.name} ... NOT FOUND", "white")
    self.output(f"[ENTITY]  {entity_def.name} ... CREATING", "white")

    payload = {
        "name": entity_def.name,          # natural name — EspoCRM adds C prefix
        "type": entity_def.type,
        "labelSingular": entity_def.labelSingular,
        "labelPlural": entity_def.labelPlural,
        "stream": entity_def.stream,
        "disabled": entity_def.disabled,
    }
    status, body = self.client.create_entity(payload)
    if status == 200:
        self.output(f"[ENTITY]  {entity_def.name} ... CREATED OK", "green")
        return True
    else:
        self.output(f"[ENTITY]  {entity_def.name} ... ERROR (HTTP {status})", "red")
        return False
```

### 4.3 Delete Flow

```python
def _delete_entity(self, entity_def):
    espo_name = get_espo_entity_name(entity_def.name)
    self.output(f"[ENTITY]  {entity_def.name} ... CHECKING", "white")

    status, body = self.client.check_entity_exists(espo_name)
    if not (status == 200 and body):
        self.output(f"[ENTITY]  {entity_def.name} ... NOT FOUND", "gray")
        self.output(f"[ENTITY]  {entity_def.name} ... SKIPPED", "gray")
        return True

    self.output(f"[ENTITY]  {entity_def.name} ... EXISTS", "white")
    self.output(f"[ENTITY]  {entity_def.name} ... DELETING", "white")

    status, body = self.client.remove_entity(espo_name)  # C-prefixed name
    if status == 200:
        self.output(f"[ENTITY]  {entity_def.name} ... DELETED OK", "green")
        return True
    else:
        self.output(f"[ENTITY]  {entity_def.name} ... ERROR (HTTP {status})", "red")
        return False
```

### 4.4 Delete-and-Create Flow

```python
def _delete_and_create(self, entity_def):
    deleted = self._delete_entity(entity_def)
    if not deleted:
        return False
    # Cache rebuild happens in RunWorker between phases
    return self._create_entity(entity_def)
```

---

## 5. Error Handling

| Error Condition | Behavior |
|---|---|
| HTTP 401 | Raises `EntityManagerError` — aborts entire run |
| HTTP 403 | Logs error, returns False, continues |
| HTTP 4xx/5xx | Logs error and response body, returns False, continues |
| Network error | Logs error, returns False, continues |
| Delete fails in delete_and_create | Create is not attempted; returns False |

```python
class EntityManagerError(Exception):
    """Raised on HTTP 401 to abort the entire run."""
```

---

## 6. Entity Name Mapping

See `impl-yaml-schema.md` Section 5.1 for the full `ENTITY_NAME_MAP`,
`NATIVE_ENTITIES`, and `get_espo_entity_name()` function.

**Known placement issue:** `ENTITY_NAME_MAP` and `get_espo_entity_name()`
currently live in `confirm_delete_dialog.py`. They are imported from
there by other modules. This should be refactored to
`core/entity_manager.py` in a future cleanup pass.

---

## 7. Run Orchestration

Entity operations are orchestrated by `RunWorker` in
`workers/run_worker.py`. The sequence is:

```python
def _run_full(self):
    # Phase 1 — Deletions
    delete_entities = [e for e in program.entities
                       if e.action in (EntityAction.DELETE,
                                       EntityAction.DELETE_AND_CREATE)]
    for entity_def in delete_entities:
        entity_mgr._delete_entity(entity_def)

    if delete_entities:
        entity_mgr.rebuild_cache()
        self.output_line.emit("[CACHE]   Rebuilding cache ... OK", "green")

    # Phase 2 — Creations
    create_entities = [e for e in program.entities
                       if e.action in (EntityAction.CREATE,
                                       EntityAction.DELETE_AND_CREATE)]
    for entity_def in create_entities:
        entity_mgr._create_entity(entity_def)

    if create_entities:
        entity_mgr.rebuild_cache()
        self.output_line.emit("[CACHE]   Rebuilding cache ... OK", "green")

    # Phase 3 — Fields, layouts, relationships follow
```

---

## 8. API Client Methods

These methods on `EspoAdminClient` are used by `EntityManager`:

```python
def check_entity_exists(self, espo_name: str) -> tuple[int, dict | None]:
    return self._request("GET",
        f"Metadata?key=scopes.{espo_name}")

def create_entity(self, payload: dict) -> tuple[int, dict | None]:
    return self._request("POST",
        "EntityManager/action/createEntity",
        json=payload)

def remove_entity(self, espo_name: str) -> tuple[int, dict | None]:
    return self._request("POST",
        "EntityManager/action/removeEntity",
        json={"name": espo_name})

def rebuild(self) -> tuple[int, dict | None]:
    return self._request("POST", "Admin/rebuild")
```

---

## 9. Testing

`entity_manager.py` is covered by `tests/test_entity_manager.py`:

| Test Area | Cases |
|---|---|
| Create — entity not found | POST called, success logged |
| Create — entity exists | POST not called, skipped logged |
| Delete — entity exists | POST called with C-prefixed name, success logged |
| Delete — entity not found | POST not called, skipped logged |
| Delete-and-create | Delete then create called in sequence |
| Delete-and-create — delete fails | Create not attempted |
| HTTP 401 | `EntityManagerError` raised |
| HTTP 5xx | Error logged, returns False, does not raise |
| Cache rebuild | POST to Admin/rebuild called |
| Entity name mapping | C-prefixed name used for delete and check |

Mocking pattern:

```python
def test_create_entity_not_found(tmp_path):
    client = MagicMock()
    client.check_entity_exists.return_value = (404, None)
    client.create_entity.return_value = (200, {})

    output_lines = []
    mgr = EntityManager(client, lambda msg, color: output_lines.append(msg))

    entity_def = EntityDefinition(
        name="Engagement",
        action=EntityAction.CREATE,
        type="Base",
        labelSingular="Engagement",
        labelPlural="Engagements",
        fields=[],
    )
    result = mgr._create_entity(entity_def)

    assert result is True
    client.create_entity.assert_called_once()
    assert any("CREATED OK" in line for line in output_lines)
```
