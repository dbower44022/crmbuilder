# Claude Code Prompt — Remove `ENTITY_NAME_MAP` override; let custom entities resolve to `f"C{name}"`

**Repository:** `dbower44022/crmbuilder`
**Branch:** `main` (commit directly)
**Type:** Bug fix — remove broken hardcoded override

---

## 1. Problem statement

Three of five entries in
`espo_impl/ui/confirm_delete_dialog.py:ENTITY_NAME_MAP` encode
incorrect mappings from YAML entity names to EspoCRM internal
names. The mappings drive every downstream operation against the
entity (existence check, fieldManager URLs, layout URLs,
relationship URLs, metadata cache polling) — so when a YAML name
is in the map but the map's value is wrong, every operation
against that entity fails:

```python
ENTITY_NAME_MAP: dict[str, str] = {
    "Engagement": "CEngagement",                # plain C prefix — fine
    "Session": "CSessions",                     # WRONG — actual server name is CSession
    "Workshop": "CWorkshops",                   # suspect — likely should be CWorkshop
    "WorkshopAttendance": "CWorkshopAttendee",  # suspect — likely should be CWorkshopAttendance
    "NpsSurveyResponse": "CNpsSurveyResponse",  # plain C prefix — fine
}
```

Live evidence from a Configure run that just deployed
`MN-Session.yaml`: the engine sends `name: Session` to EspoCRM's
EntityManager createEntity, EspoCRM creates the entity as
`CSession`, the engine then assumes it's at `CSessions` (per the
map), every downstream operation fails. The newly-added
`wait_for_metadata_ready` correctly polled
`GET /Metadata?key=entityDefs.CSessions` for 30 full seconds and
got an empty body each time — the entity at `CSessions` doesn't
exist; the entity at `CSession` does. After timeout, the run
proceeds: 7 of 7 fields HTTP 500, 2 of 2 layouts HTTP 403, 3 of
3 relationships HTTP 500.

The user verified manually in EspoCRM Entity Manager that the
broken entity's actual internal name was `CSession`, not
`CSessions`.

## 2. Root cause

The current EspoCRM behavior — verified empirically — is:

> A YAML-declared custom entity with `name: X` is created by
> EspoCRM with internal name `f"C{X}"`. No pluralization, no
> renaming, no special-casing. `Session` → `CSession`.
> `Workshop` → `CWorkshop`. `WorkshopAttendance` →
> `CWorkshopAttendance`. Every custom entity follows this rule.

The `get_espo_entity_name` function already encodes this rule as
its fallback path:

```python
def get_espo_entity_name(yaml_name: str) -> str:
    if yaml_name in NATIVE_ENTITIES:
        return yaml_name
    if yaml_name in ENTITY_NAME_MAP:
        return ENTITY_NAME_MAP[yaml_name]
    return f"C{yaml_name}"
```

The fallback is correct. The problem is that three of the five
override entries shadow the correct fallback with wrong values,
and the other two redundantly encode what the fallback would
return anyway. The map is a **workaround mechanism for a problem
that doesn't exist** — and is actively breaking deployment.

`espo_impl/core/audit_utils.py` derives a symmetric
`INVERSE_ENTITY_NAME_MAP` (line 16) used by `strip_entity_c_prefix`
(line 222). It encodes the same wrong mappings in reverse:
`CSessions → Session`, `CWorkshops → Workshop`, etc. The
fallback at line 237 (`if api_name.startswith("C") and ...:
return api_name[1:]`) is correct and handles every custom entity
the same way. The inverse map is also redundant-or-wrong.

## 3. Fix

Delete `ENTITY_NAME_MAP` and `INVERSE_ENTITY_NAME_MAP` entirely.
Simplify `get_espo_entity_name` and `strip_entity_c_prefix` to
just native check + universal C-prefix rule.

This is the simplest, smallest, most-targeted fix. It removes a
class of bug (hardcoded override entries that drift from
EspoCRM's actual behavior) rather than patching a single
instance.

### Risk assessment

- **`Engagement`** is currently deployed on the test instance.
  Map returned `CEngagement`; fallback returns `CEngagement`. No
  change in behavior.
- **`Session`** is not currently deployed (broken entity manually
  deleted). Next deploy will create it as `CSession`, which is
  what EspoCRM actually names it.
- **`Workshop`** and **`WorkshopAttendance`** have no YAML in the
  current CBM program set. When YAML is authored later, they'll
  resolve correctly.
- **`NpsSurveyResponse`** has no YAML in the current set.

No deployed entity changes its expected name as a result of this
fix.

## 4. Required code changes

### 4.1 `espo_impl/ui/confirm_delete_dialog.py`

Replace the entire block at lines 19–46:

```python
# Entity name mapping: YAML natural name → EspoCRM internal name (C-prefixed)
ENTITY_NAME_MAP: dict[str, str] = {
    "Engagement": "CEngagement",
    "Session": "CSessions",
    "Workshop": "CWorkshops",
    "WorkshopAttendance": "CWorkshopAttendee",
    "NpsSurveyResponse": "CNpsSurveyResponse",
}

# Native entities that do not get the C prefix
NATIVE_ENTITIES: set[str] = {
    "Contact", "Account", "Lead", "Opportunity", "Case",
    "Task", "Meeting", "Call", "Email", "Document",
    "Campaign", "TargetList", "User", "Team",
}


def get_espo_entity_name(yaml_name: str) -> str:
    """Map a YAML entity name to the EspoCRM internal name.

    :param yaml_name: Entity name from the YAML program file.
    :returns: EspoCRM internal name (C-prefixed for custom, unchanged for native).
    """
    if yaml_name in NATIVE_ENTITIES:
        return yaml_name
    if yaml_name in ENTITY_NAME_MAP:
        return ENTITY_NAME_MAP[yaml_name]
    return f"C{yaml_name}"
```

with:

```python
# Native entities that do not get the C prefix
NATIVE_ENTITIES: set[str] = {
    "Contact", "Account", "Lead", "Opportunity", "Case",
    "Task", "Meeting", "Call", "Email", "Document",
    "Campaign", "TargetList", "User", "Team",
}


def get_espo_entity_name(yaml_name: str) -> str:
    """Map a YAML entity name to the EspoCRM internal name.

    EspoCRM stores custom entities with a ``C`` prefix applied to
    the YAML-declared name. There is no pluralization, no
    renaming, and no special-casing: ``Session`` is stored as
    ``CSession``, ``Workshop`` as ``CWorkshop``,
    ``WorkshopAttendance`` as ``CWorkshopAttendance``. Every
    custom entity follows the same rule.

    Native entities (Contact, Account, Lead, etc.) keep their
    natural names with no prefix.

    :param yaml_name: Entity name from the YAML program file.
    :returns: EspoCRM internal name (C-prefixed for custom,
        unchanged for native).
    """
    if yaml_name in NATIVE_ENTITIES:
        return yaml_name
    return f"C{yaml_name}"
```

### 4.2 `espo_impl/core/audit_utils.py`

Update the import at line 10–13:

Replace:

```python
from espo_impl.ui.confirm_delete_dialog import (
    ENTITY_NAME_MAP,
    NATIVE_ENTITIES,
)

# Inverse of ENTITY_NAME_MAP: EspoCRM internal name → YAML natural name
INVERSE_ENTITY_NAME_MAP: dict[str, str] = {v: k for k, v in ENTITY_NAME_MAP.items()}
```

with:

```python
from espo_impl.ui.confirm_delete_dialog import NATIVE_ENTITIES
```

(Drop the `INVERSE_ENTITY_NAME_MAP` line entirely.)

Update `strip_entity_c_prefix` at line 222–239:

Replace:

```python
def strip_entity_c_prefix(api_name: str) -> str:
    """Reverse the C-prefix on a custom entity name.

    ``CEngagement`` → ``Engagement``

    Uses the inverse entity name map for known special cases,
    falls back to stripping the ``C`` prefix.

    :param api_name: Entity name from the EspoCRM API.
    :returns: YAML natural entity name.
    """
    if api_name in NATIVE_ENTITIES:
        return api_name
    if api_name in INVERSE_ENTITY_NAME_MAP:
        return INVERSE_ENTITY_NAME_MAP[api_name]
    if api_name.startswith("C") and len(api_name) > 1 and api_name[1].isupper():
        return api_name[1:]
    return api_name
```

with:

```python
def strip_entity_c_prefix(api_name: str) -> str:
    """Reverse the C-prefix on a custom entity name.

    ``CEngagement`` → ``Engagement``,
    ``CSession`` → ``Session``,
    ``CWorkshopAttendance`` → ``WorkshopAttendance``.

    Native entity names are returned unchanged. Names that don't
    follow the ``C{Uppercase}...`` pattern are returned unchanged
    (including names where the second character isn't uppercase,
    which would never be a valid custom entity name).

    :param api_name: Entity name from the EspoCRM API.
    :returns: YAML natural entity name.
    """
    if api_name in NATIVE_ENTITIES:
        return api_name
    if (
        api_name.startswith("C")
        and len(api_name) > 1
        and api_name[1].isupper()
    ):
        return api_name[1:]
    return api_name
```

## 5. Required test updates

Six existing tests assume the old (wrong) mappings. Update them
to expect the corrected names produced by the fallback rule.

### 5.1 `tests/test_relationship_manager.py`

Line 53:

Replace:

```python
    assert payload["entityForeign"] == "CSessions"
```

with:

```python
    assert payload["entityForeign"] == "CSession"
```

### 5.2 `tests/test_entity_manager.py`

Lines 246–248 (the "Session maps to ..." block in the delete-
entity test):

Replace:

```python
    # Session maps to CSessions per the mapping table
    client.check_entity_exists.assert_called_once_with("CSessions")
    client.remove_entity.assert_called_once_with("CSessions")
```

with:

```python
    # Session resolves to CSession via the universal C-prefix rule
    client.check_entity_exists.assert_called_once_with("CSession")
    client.remove_entity.assert_called_once_with("CSession")
```

In the four `wait_for_metadata_ready` tests (lines 272–355), the
in-test fixture name `CSessions` is used as a mock return value
or call-log target — these are arbitrary fixture names, not
encoded mappings. Update them all to `CSession` for consistency
with the corrected rule:

- Line 279: `(200, {"name": "CSessions", "fields": {}})` →
  `(200, {"name": "CSession", "fields": {}})`
- Line 335 (comment): `# CSessions: empty on first 2 calls, ready on 3rd`
  → `# CSession: empty on first 2 calls, ready on 3rd`
- Line 337: `1 for n in call_log if n == "CSessions"` →
  `1 for n in call_log if n == "CSession"`
- Line 341: `return (200, {"name": "CSessions", "fields": {}})` →
  `return (200, {"name": "CSession", "fields": {}})`
- Line 353: `sessions_calls = sum(1 for n in call_log if n == "CSessions")`
  → `sessions_calls = sum(1 for n in call_log if n == "CSession")`

These edits are mechanical: every literal `CSessions` in the
test file becomes `CSession`. The test logic does not change.

## 6. New test

Add one new test at the end of `tests/test_entity_manager.py`
(or the most natural place if a more specific test file covers
`get_espo_entity_name`):

```python
def test_get_espo_entity_name_universal_c_prefix_rule():
    """Custom entity names always resolve to f'C{name}', with no
    pluralization or renaming. Native entities are unchanged."""
    from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

    # Custom entities — universal C prefix rule
    assert get_espo_entity_name("Engagement") == "CEngagement"
    assert get_espo_entity_name("Session") == "CSession"
    assert get_espo_entity_name("Workshop") == "CWorkshop"
    assert get_espo_entity_name("WorkshopAttendance") == "CWorkshopAttendance"
    assert get_espo_entity_name("NpsSurveyResponse") == "CNpsSurveyResponse"
    assert get_espo_entity_name("Contribution") == "CContribution"

    # Native entities — unchanged
    assert get_espo_entity_name("Contact") == "Contact"
    assert get_espo_entity_name("Account") == "Account"
    assert get_espo_entity_name("Lead") == "Lead"
    assert get_espo_entity_name("Meeting") == "Meeting"
```

This test guards the universal rule against any future
reintroduction of an override mechanism.

## 7. Out of scope

- Do NOT modify any YAML files.
- Do NOT change `wait_for_metadata_ready` itself. It worked
  correctly — polled what it was told to poll, timed out
  cleanly when the target never appeared. The 30-second wait is
  still useful for the genuine async-rebuild case.
- Do NOT change `NATIVE_ENTITIES`. That set is correct.
- Do NOT change deploy-engine logic. Only the name-resolution
  shims at the boundary between YAML names and EspoCRM names
  change.

## 8. Verification steps

1. **Unit tests:** `uv run pytest tests/test_entity_manager.py
   tests/test_relationship_manager.py -v`. All previously
   passing tests must still pass after the literal updates; the
   new universal-C-prefix test must pass.
2. **Lint:** `uv run ruff check espo_impl/ tests/`.
3. **End-to-end (manual, by Doug):** With the broken `Session`
   entity already deleted from the test instance, re-run the
   five-file Configure batch (CR-Account, MN-Account, MN-Contact,
   MN-Engagement, MN-Session). Expected:
   - First four files: same idempotent / NO_WORK behavior as the
     previous run.
   - **MN-Session: full clean deploy.** Entity creates as
     `CSession`. Cache rebuild triggered. `wait_for_metadata_ready`
     polls `GET /Metadata?key=entityDefs.CSession` and gets
     `(200, dict)` quickly. `[WAIT] Session (CSession) ... ready`
     appears. Settings, fields, layouts, relationships all
     succeed.

## 9. Commit

Single commit. Suggested message:

```
fix(entity-name): remove ENTITY_NAME_MAP; use universal C-prefix rule

The hardcoded override map at espo_impl/ui/confirm_delete_dialog.py
encoded incorrect mappings for three of its five entries:

  Session            -> CSessions    (actual: CSession)
  Workshop           -> CWorkshops   (likely actual: CWorkshop)
  WorkshopAttendance -> CWorkshopAttendee (likely actual:
                                           CWorkshopAttendance)

Live evidence: MN-Session.yaml deploy created the entity as
CSession on the EspoCRM side (verified via Entity Manager admin
UI), but the engine assumed CSessions per the map. The newly-
added wait_for_metadata_ready polled GET /Metadata?key=
entityDefs.CSessions for 30 seconds and got an empty body each
time. After timeout, downstream operations fired against the
wrong URL: 7 of 7 fields HTTP 500, 2 of 2 layouts HTTP 403, 3
of 3 relationships HTTP 500.

EspoCRM applies a simple rule for custom entities: f"C{name}".
No pluralization, no renaming, no special-casing. The fallback
in get_espo_entity_name already encoded this rule correctly.
The override map shadowed it with wrong values for the special
cases.

Fix: delete ENTITY_NAME_MAP entirely. get_espo_entity_name now
has two paths: native entities (unchanged) and custom entities
(C prefix). Same shape applied to strip_entity_c_prefix in
audit_utils.py, which previously consulted the symmetrically-
wrong INVERSE_ENTITY_NAME_MAP.

Updated six existing tests that asserted the old (wrong)
CSessions name to assert CSession. Added one new test asserting
the universal C-prefix rule for Engagement, Session, Workshop,
WorkshopAttendance, NpsSurveyResponse, and Contribution, plus
native passthrough for Contact, Account, Lead, Meeting.

The wait_for_metadata_ready logic itself is unchanged. It
correctly timed out on the wrong-name target; the 30-second
wait is still useful for the genuine async-rebuild case.
```
