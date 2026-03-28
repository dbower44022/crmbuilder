# CRM Builder — Relationship Management Implementation Reference

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Requirements:** PRDs/features/feat-relationships.md
**Maintained By:** Claude Code

---

## 1. Purpose

This document describes the implementation of relationship management
in CRM Builder — the `RelationshipManager` class, EspoCRM API
endpoints, link type mapping, payload construction, and the
check/act cycle.

---

## 2. File Location

```
espo_impl/core/relationship_manager.py
```

---

## 3. API Endpoints

All endpoints confirmed via network traffic observation on EspoCRM
v9.3.3.

| Operation | Method | Endpoint | Notes |
|---|---|---|---|
| Check exists | GET | `/api/v1/Metadata?key=entityDefs.{EspoEntity}.links.{linkName}` | Returns link object or empty |
| Create | POST | `/api/v1/EntityManager/action/createLink` | Full relationship payload |
| Delete | POST | `/api/v1/EntityManager/action/removeLink` | Not used in normal flow |

Both entity names in all endpoints use the C-prefixed internal name.

---

## 4. Link Type Mapping

The `createLink` API uses a different type vocabulary than the
Metadata check endpoint:

| YAML `linkType` | API `linkType` | Primary side (Metadata `type`) | Foreign side (Metadata `type`) |
|---|---|---|---|
| `oneToMany` | `oneToMany` | `hasMany` | `belongsTo` |
| `manyToOne` | `manyToOne` | `belongsTo` | `hasMany` |
| `manyToMany` | `manyToMany` | `hasMany` | `hasMany` |

When checking whether a relationship exists (via the Metadata
endpoint), the returned `type` field reflects the primary side's
perspective (`hasMany` or `belongsTo`), not the YAML `linkType`.
The comparison must account for this mapping.

---

## 5. RelationshipManager Class

```python
class RelationshipManager:
    def __init__(self, client: EspoAdminClient, output_cb: Callable):
        self.client = client
        self.output = output_cb

    # Metadata type → YAML linkType mapping for check comparison
    METADATA_TYPE_TO_LINK_TYPE = {
        "hasMany":   {"oneToMany", "manyToMany"},
        "belongsTo": {"manyToOne"},
    }
```

### 5.1 Main Entry Point

```python
def run(
    self, relationships: list[RelationshipDefinition]
) -> list[RelationshipResult]:
    results = []
    for rel in relationships:
        result = self._process_relationship(rel)
        results.append(result)
    return results
```

### 5.2 Relationship Processing Cycle

```python
def _process_relationship(
    self, rel: RelationshipDefinition
) -> RelationshipResult:

    tag = f"{rel.entity} → {rel.entity_foreign} ({rel.link})"

    # Handle action: skip
    if rel.action == "skip":
        self.output(f"[RELATIONSHIP]  {tag} ... SKIP (action: skip)", "gray")
        return RelationshipResult(rel.name, rel.entity, rel.entity_foreign,
                                  rel.link, RelationshipStatus.SKIPPED_ACTION)

    self.output(f"[RELATIONSHIP]  {tag} ... CHECKING", "white")

    espo_entity = get_espo_entity_name(rel.entity)
    status, body = self.client.get_link(espo_entity, rel.link)

    if status == 200 and body:
        return self._handle_existing(rel, tag, body)

    if status in (200, 404):
        # Link does not exist — create
        return self._create_relationship(rel, tag)

    self.output(f"[RELATIONSHIP]  {tag} ... ERROR (HTTP {status})", "red")
    return RelationshipResult(rel.name, rel.entity, rel.entity_foreign,
                              rel.link, RelationshipStatus.ERROR,
                              message=f"HTTP {status}")
```

### 5.3 Handling Existing Relationships

```python
def _handle_existing(
    self, rel: RelationshipDefinition, tag: str, current: dict
) -> RelationshipResult:

    self.output(f"[RELATIONSHIP]  {tag} ... EXISTS", "white")

    # Verify type matches
    current_type = current.get("type")
    expected_types = self.METADATA_TYPE_TO_LINK_TYPE.get(current_type, set())

    if rel.link_type not in expected_types:
        self.output(
            f"[RELATIONSHIP]  {tag} ... EXISTS BUT DIFFERS", "yellow")
        self.output(
            f"[RELATIONSHIP]  {tag} ... WARNING "
            f"(cannot update — manual correction required)", "yellow")
        return RelationshipResult(rel.name, rel.entity, rel.entity_foreign,
                                  rel.link, RelationshipStatus.WARNING,
                                  message="Type mismatch — manual correction required")

    self.output(f"[RELATIONSHIP]  {tag} ... SKIPPED (no changes needed)", "gray")
    return RelationshipResult(rel.name, rel.entity, rel.entity_foreign,
                              rel.link, RelationshipStatus.SKIPPED)
```

### 5.4 Create

```python
def _create_relationship(
    self, rel: RelationshipDefinition, tag: str
) -> RelationshipResult:

    self.output(f"[RELATIONSHIP]  {tag} ... NOT FOUND", "white")
    self.output(f"[RELATIONSHIP]  {tag} ... CREATING", "white")

    payload = self._build_payload(rel)
    status, body = self.client.create_link(payload)

    if status == 200:
        self.output(f"[RELATIONSHIP]  {tag} ... CREATED OK", "green")

        # Verify
        verified = self._verify(rel)
        if verified:
            self.output(f"[RELATIONSHIP]  {tag} ... VERIFIED", "green")
        else:
            self.output(f"[RELATIONSHIP]  {tag} ... VERIFY FAILED", "yellow")

        return RelationshipResult(rel.name, rel.entity, rel.entity_foreign,
                                  rel.link, RelationshipStatus.CREATED,
                                  verified=verified)

    self.output(f"[RELATIONSHIP]  {tag} ... ERROR (HTTP {status})", "red")
    if body:
        self.output(f"  Response: {body}", "red")
    return RelationshipResult(rel.name, rel.entity, rel.entity_foreign,
                              rel.link, RelationshipStatus.ERROR,
                              message=f"HTTP {status}: {body}")
```

### 5.5 Payload Construction

```python
def _build_payload(self, rel: RelationshipDefinition) -> dict:
    return {
        "entity":                   get_espo_entity_name(rel.entity),
        "entityForeign":            get_espo_entity_name(rel.entity_foreign),
        "link":                     rel.link,
        "linkForeign":              rel.link_foreign,
        "label":                    rel.label,
        "labelForeign":             rel.label_foreign,
        "linkType":                 rel.link_type,
        "relationName":             rel.relation_name,
        "linkMultipleField":        False,
        "linkMultipleFieldForeign": False,
        "audited":                  rel.audited,
        "auditedForeign":           rel.audited_foreign,
        "layout":                   None,
        "layoutForeign":            None,
        "selectFilter":             None,
        "selectFilterForeign":      None,
    }
```

### 5.6 Verify

```python
def _verify(self, rel: RelationshipDefinition) -> bool:
    espo_entity = get_espo_entity_name(rel.entity)
    status, body = self.client.get_link(espo_entity, rel.link)
    if status != 200 or not body:
        return False

    current_type = body.get("type")
    expected_types = self.METADATA_TYPE_TO_LINK_TYPE.get(current_type, set())
    espo_foreign = get_espo_entity_name(rel.entity_foreign)

    return (
        rel.link_type in expected_types
        and body.get("entity") == espo_foreign
        and body.get("foreign") == rel.link_foreign
    )
```

---

## 6. Data Models

```python
class RelationshipStatus(Enum):
    CREATED = "created"
    SKIPPED = "skipped"
    SKIPPED_ACTION = "skipped_action"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class RelationshipResult:
    name: str
    entity: str
    entity_foreign: str
    link: str
    status: RelationshipStatus
    verified: bool = False
    message: str | None = None
```

---

## 7. API Client Methods

```python
def get_link(
    self, entity: str, link_name: str
) -> tuple[int, dict | None]:
    return self._request("GET",
        f"Metadata?key=entityDefs.{entity}.links.{link_name}")

def create_link(self, payload: dict) -> tuple[int, dict | None]:
    return self._request("POST",
        "EntityManager/action/createLink", json=payload)

def remove_link(
    self, entity: str, link_name: str
) -> tuple[int, dict | None]:
    return self._request("POST",
        "EntityManager/action/removeLink",
        json={"entity": entity, "link": link_name})
```

---

## 8. Known Quirk — linkForeign C-Prefix

When the foreign entity is a custom entity (C-prefix), the
`linkForeign` value in the YAML must include the c-prefix on the
foreign link name. For example, if the foreign link on `CEngagement`
is `npsSurveyResponses`, the YAML must specify
`linkForeign: cNpsSurveyResponses`.

When the primary entity is native (Account, Contact), the `link`
name is specified without a c-prefix in the YAML and EspoCRM handles
it correctly.

This asymmetry is a known EspoCRM behavior quirk, not a CRM Builder
bug. It is documented here so it does not get reported as a defect.

---

## 9. Existing Relationship Inventory

The following 11 relationships are defined for the CBM client. The
first 6 were created manually before the tool was built and use
`action: skip`. The final 5 are deployed by the tool.

| # | Primary | Foreign | Type | Link | Link Foreign | Status |
|---|---|---|---|---|---|---|
| 1 | Engagement | Account | manyToOne | assignedEngagement | cCompanyRequestionHelp | skip |
| 2 | Engagement | Contact | manyToOne | assignedMentor | cEngagements | skip |
| 3 | Engagement | Contact | manyToMany | contacts | cEngagementContacts | skip |
| 4 | Engagement | Contact | manyToMany | cBMContacts | cCoMentorEngagements | skip |
| 5 | Engagement | Session | oneToMany | engagementSessionses | sessionEngagement | skip |
| 6 | Workshop | WorkshopAttendance | oneToMany | workshopAttendees | workshopAttended | skip |
| 7 | NpsSurveyResponse | Engagement | manyToOne | engagement | npsSurveyResponses | deploy |
| 8 | WorkshopAttendance | Contact | manyToOne | contact | workshopAttendances | deploy |
| 9 | WorkshopAttendance | Engagement | manyToOne | engagement | workshopAttendances | deploy |
| 10 | Dues | Contact | manyToOne | mentor | duesRecords | deploy |
| 11 | Session | Contact | manyToMany | mentorAttendees | attendedSessions | deploy |

Note on #8 and #9: both use `workshopAttendances` as the foreign
link name, but on different foreign entities (Contact and Engagement
respectively). No collision.

---

## 10. Error Handling

| Error | Behavior |
|---|---|
| HTTP 401 | Raises `RelationshipManagerError` — aborts entire run |
| HTTP 403 | Logs error, marks as ERROR, continues |
| HTTP 4xx/5xx on POST | Logs error and full response body, marks as ERROR, continues |
| Link exists but type differs | Logs warning, marks as WARNING, continues |
| Network error | Logs error, marks as ERROR, continues |

```python
class RelationshipManagerError(Exception):
    """Raised on HTTP 401 to abort the entire run."""
```

---

## 11. Testing

`relationship_manager.py` is covered by
`tests/test_relationship_manager.py`:

| Test Area | Cases |
|---|---|
| action: skip | No API calls made, SKIPPED_ACTION result |
| Link not found | POST called, CREATED result |
| Link exists, type matches | POST not called, SKIPPED result |
| Link exists, type differs | POST not called, WARNING result |
| Create fails HTTP 4xx | ERROR result, continues |
| Verify after create | GET called, verified=True on match |
| HTTP 401 | `RelationshipManagerError` raised |
| Payload construction | All fields present, C-prefixed entity names |

Mocking pattern:

```python
def test_relationship_create():
    client = MagicMock()
    client.get_link.side_effect = [
        (200, None),       # check — not found
        (200, {            # verify
            "type": "belongsTo",
            "entity": "CEngagement",
            "foreign": "npsSurveyResponses",
        }),
    ]
    client.create_link.return_value = (200, {})

    output = []
    mgr = RelationshipManager(client, lambda m, c: output.append(m))

    rel = RelationshipDefinition(
        name="npsToEngagement",
        entity="NpsSurveyResponse",
        entity_foreign="Engagement",
        link_type="manyToOne",
        link="engagement",
        link_foreign="npsSurveyResponses",
        label="Engagement",
        label_foreign="NPS Survey Responses",
    )
    result = mgr._process_relationship(rel)

    assert result.status == RelationshipStatus.CREATED
    assert result.verified is True
    client.create_link.assert_called_once()
```
