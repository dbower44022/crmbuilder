# Claude Code Prompt — Validator: include EspoCRM native fields in the field-name set

**Repository:** `dbower44022/crmbuilder`
**Branch:** `main` (commit directly)
**Type:** Bug fix — extends commit `d98db71` with native-field awareness

---

## 1. Problem statement

After commit `d98db71` (cross-YAML field resolution), a Configure
run against the MN domain still produced 11 validation errors,
all from the same root cause: the validator's notion of "fields
that exist on this entity" still excludes EspoCRM native fields
that ship with the entity by virtue of its base type.

Live evidence:

```
=== CR/CR-Account.yaml: VALIDATION FAILED (1 error(s)) ===
- Account.duplicateChecks[account-website]: field 'website' not found on entity 'Account'

=== MN/MN-Engagement.yaml: VALIDATION FAILED (10 error(s)) ===
- Engagement.savedViews[engagement-submitted].columns: field 'name' not found on entity 'Engagement'
- Engagement.savedViews[engagement-submitted].columns: field 'createdAt' not found on entity 'Engagement'
- Engagement.savedViews[engagement-submitted].orderBy: field 'createdAt' not found on entity 'Engagement'
- Engagement.savedViews[engagement-pending-acceptance].columns: field 'name' not found on entity 'Engagement'
- Engagement.savedViews[engagement-pending-acceptance].columns: field 'modifiedAt' not found on entity 'Engagement'
- Engagement.savedViews[engagement-pending-acceptance].orderBy: field 'modifiedAt' not found on entity 'Engagement'
- Engagement.savedViews[engagement-active].columns: field 'name' not found on entity 'Engagement'
- Engagement.savedViews[engagement-dormant-inactive].columns: field 'name' not found on entity 'Engagement'
- Engagement.savedViews[engagement-on-hold].columns: field 'name' not found on entity 'Engagement'
- Engagement.savedViews[engagement-completed].columns: field 'name' not found on entity 'Engagement'
```

Every flagged field is a real EspoCRM field present on the named
entity:

- `website` is a native field on every Company-type entity
  (Account, Lead in some configurations).
- `name` and `description` are present on every entity (Base,
  Person, Company, Event, plus all natives).
- `createdAt` and `modifiedAt` are present on every entity as
  system fields.

The deploy engine accepts saved views and duplicate checks against
these fields without complaint — they're real fields. Validation
just doesn't know they exist.

## 2. Root cause

The fix in `d98db71` extended the validator to know about fields
contributed by sibling YAMLs. It still does not know about fields
contributed by **EspoCRM itself** (system fields like `id`,
`createdAt`, `modifiedAt`, plus base-type natives like `name`,
`description`, `website`, `dateStart`, `phoneNumber`, etc.).

The catalog of native fields already exists in the codebase at
`espo_impl/core/audit_utils.py`:

- `SYSTEM_FIELDS` (line 36): the universal system fields present
  on every entity (`id`, `deleted`, `createdAt`, `modifiedAt`,
  `createdById`, `assignedUserId`, etc.).
- `NATIVE_PERSON_FIELDS` (line 64): natives on Person-type
  entities (`firstName`, `lastName`, `name`, `emailAddress`,
  `phoneNumber`, `addressStreet`, ..., `title`, `website`).
- `NATIVE_COMPANY_FIELDS` (line 84): natives on Company-type
  entities (`name`, `emailAddress`, `phoneNumber`, `website`,
  address fields, `sicCode`, `industry`, `type`, etc.).
- `NATIVE_EVENT_FIELDS` (line 111): natives on Event-type
  entities (`name`, `status`, `dateStart`, `dateEnd`, `duration`,
  `description`, etc.).
- `NATIVE_BASE_FIELDS` (line 136): natives on Base-type custom
  entities (`name`, `description`).
- `_TYPE_NATIVE_FIELDS` mapping (line 142): keyed by
  `Person | Company | Event | Base`.
- `get_native_fields_for_type(entity_type)` helper (line 311):
  returns the appropriate native-field set for the given type
  string.

The validator at `espo_impl/core/config_loader.py` does not
consult any of these. The eight `field_names = {...}` construction
sites today (post-`d98db71`) read:

```python
field_names = {f.name for f in entity.fields} | self._active_context.field_names_for(entity.name)
```

That captures custom fields and cross-YAML contributions, but
not native fields.

The validator also has no notion of "what type is this entity?"
For custom entities, the YAML declares `type:` directly
(`type: Base`, `type: Event`). For native entities like Contact,
Account, Lead, Meeting, the YAML omits `type:` because the type
is determined by EspoCRM itself, not by the YAML — and the
validator must infer it from the entity name.

## 3. Fix

Two pieces, in this order:

### 3.1 Add a native-fields-by-entity lookup

`espo_impl/ui/confirm_delete_dialog.py` already declares
`NATIVE_ENTITIES` (line 29). That set is what
`get_espo_entity_name(...)` uses to decide whether to apply the
`C` prefix. We need the analog: a mapping from native entity
name to the EspoCRM base type that drives its native fields.

Add a new module `espo_impl/core/native_entity_types.py`:

```python
"""Canonical mapping from EspoCRM native entity names to their
base types, used to resolve native field sets during validation
and in any other context that needs to know what built-in fields
ship with a native entity.

This complements ``espo_impl.ui.confirm_delete_dialog.NATIVE_ENTITIES``
(which lists *which* entities are native) by recording *which
base type* each native entity uses, so the field catalog in
``espo_impl.core.audit_utils`` can be looked up.
"""

from __future__ import annotations

# Native entity name -> base type string used by
# audit_utils._TYPE_NATIVE_FIELDS.
NATIVE_ENTITY_BASE_TYPE: dict[str, str] = {
    "Contact": "Person",
    "Lead": "Person",
    "User": "Person",
    "Account": "Company",
    "Opportunity": "Base",
    "Case": "Base",
    "Document": "Base",
    "Campaign": "Base",
    "TargetList": "Base",
    "Team": "Base",
    "Task": "Base",
    "Meeting": "Event",
    "Call": "Event",
    "Email": "Base",
}


def get_base_type(entity_name: str) -> str | None:
    """Return the EspoCRM base type for the named native entity.

    :param entity_name: Entity natural name (e.g. ``Contact``).
    :returns: Base type string (``Person | Company | Event | Base``)
        if `entity_name` is a known native entity, otherwise None.
        Custom entities resolve to None — callers should use the
        entity's declared ``type`` field for those.
    """
    return NATIVE_ENTITY_BASE_TYPE.get(entity_name)
```

Note that `Email` is set to `Base` even though emails have
event-like fields, because EspoCRM treats the Email entity as
its own special class. If a CBM YAML ever extends Email and
references native event fields like `dateStart`, that's a
miss to handle later; nothing in the current CBM YAML set
extends Email, so a conservative `Base` is fine.

### 3.2 Make the validator consult the native-field catalog

In `espo_impl/core/config_loader.py`, add a private helper on
`ConfigLoader`:

```python
def _native_field_names(self, entity: EntityDefinition) -> frozenset[str]:
    """Return EspoCRM-native field names that exist on this entity
    by virtue of its base type.

    For custom entities, uses the YAML-declared ``type`` field.
    For native entities (Contact, Account, Lead, Meeting, etc.),
    consults ``native_entity_types.NATIVE_ENTITY_BASE_TYPE`` to
    infer the base type, then looks up the native-field set in
    ``audit_utils._TYPE_NATIVE_FIELDS``.

    System fields (id, createdAt, modifiedAt, etc.) are included
    unconditionally — every entity has them.

    :param entity: Entity definition under validation.
    :returns: Frozenset of native field names. Never raises.
    """
    from espo_impl.core.audit_utils import (
        SYSTEM_FIELDS,
        get_native_fields_for_type,
    )
    from espo_impl.core.native_entity_types import get_base_type

    # System fields are universal.
    result: set[str] = set(SYSTEM_FIELDS)

    # Determine base type. Custom entity: YAML-declared type.
    # Native entity: lookup in NATIVE_ENTITY_BASE_TYPE.
    base_type: str | None
    if entity.type:
        base_type = entity.type
    else:
        base_type = get_base_type(entity.name)

    if base_type is not None:
        result.update(get_native_fields_for_type(base_type))

    return frozenset(result)
```

Then update the eight `field_names = ...` sites in the same file
to union the native fields:

```python
field_names = (
    {f.name for f in entity.fields}
    | self._active_context.field_names_for(entity.name)
    | self._native_field_names(entity)
)
```

(Same pattern at all eight call sites: lines 605, 880, 928, 1011,
1141, 1286, 1518, 1790.)

### 3.3 Cross-YAML context also includes native fields

`ProgramContext.field_names_for(entity_name)` returns custom
field unions across the batch, so the validator's existing call
catches CR-Account's contributions to the Account entity. But
when MN-Account references `accountType` (declared by CR-Account)
on the Account entity, the validator looks up native fields for
`Account` via `_native_field_names(MN-Account's Account entity
def)`. That works because both YAMLs declare the same
`entity.name` — `Account` — so the helper resolves to the same
`Company` base type and the same native fields.

There's no change to `ProgramContext` needed. The native-field
piece lives entirely on `_native_field_names`.

## 4. Required code changes — summary

| File | Change | Lines |
|---|---|---|
| `espo_impl/core/native_entity_types.py` | New module with `NATIVE_ENTITY_BASE_TYPE` and `get_base_type()` | +35 |
| `espo_impl/core/config_loader.py` | New `_native_field_names()` helper; eight call-site unions extended | +25, eight 2-line edits |
| `tests/test_config_loader.py` | New tests for native-field resolution | +4 tests |

Total ~80 lines plus tests.

## 5. Required tests

Add to `tests/test_config_loader.py`:

```python
def test_validate_program_resolves_native_system_fields():
    """A savedView referencing createdAt and modifiedAt validates
    cleanly — those are universal system fields on every entity.
    """
    # Construct a minimal Engagement custom entity (type: Base) with
    # one custom field. Add a savedView with columns referencing
    # createdAt and modifiedAt and an orderBy on modifiedAt.
    # Validate. Assert no errors related to createdAt/modifiedAt.


def test_validate_program_resolves_native_base_fields():
    """A savedView on a Base-type custom entity referencing the
    native 'name' and 'description' fields validates cleanly.
    """
    # Construct a minimal Engagement custom entity (type: Base).
    # Add a savedView with columns ['name', 'description'].
    # Validate. Assert no errors related to name/description.


def test_validate_program_resolves_native_company_fields_for_account():
    """A duplicateCheck on the native Account entity referencing
    the native 'website' field validates cleanly.
    """
    # Construct a minimal Account entity with no `type:` declared
    # (because Account is a native entity). Add a duplicateCheck
    # with field='website'. Validate.
    # Assert no errors related to website.


def test_validate_program_resolves_native_person_fields_for_contact():
    """A savedView on the native Contact entity referencing the
    native 'firstName' and 'emailAddress' fields validates cleanly.
    """
    # Construct a minimal Contact entity with no `type:` declared.
    # Add a savedView with columns ['firstName', 'emailAddress'].
    # Validate. Assert no errors.


def test_validate_program_still_catches_typo_on_native_field():
    """Misspelled native references are still flagged — adding the
    native-field catalog does not weaken typo detection.
    """
    # Construct a Base-type custom entity. Add a savedView with a
    # column 'creatdAt' (typo of createdAt). Validate.
    # Assert error mentions creatdAt as not found.
```

The five `d98db71` tests for cross-YAML resolution remain valid;
no changes needed there.

## 6. Out of scope

- Do NOT touch the `industrySubsector empty options:[]` /
  `topicsCovered empty options:[]` validator-strictness issue.
  That is a separate prompt.
- Do NOT change deploy-engine behavior. Validator-only fix.
- Do NOT change `condition_expression.py` or `audit_utils.py` —
  the catalog there is already correct; only the validator's
  consumption of it changes.
- Do NOT modify any YAML files. The CBM YAML set is correct as
  written; the validator was wrong to reject it.

## 7. Verification steps

1. **Unit tests:** `uv run pytest tests/test_config_loader.py -v`.
   All previously passing tests must still pass; the five new
   tests must pass.
2. **Lint:** `uv run ruff check espo_impl/ tests/`.
3. **End-to-end (manual, by Doug):** Re-run Configure on the
   five-file MN+CR-Account batch (`programs/CR/CR-Account.yaml`,
   `programs/MN/MN-Account.yaml`, `programs/MN/MN-Contact.yaml`,
   `programs/MN/MN-Engagement.yaml`, `programs/MN/MN-Session.yaml`).
   Expected outcomes:
   - **CR-Account.yaml**: validation passes (the `website not found`
     error from the prior run is gone).
   - **MN-Engagement.yaml**: validation passes (all 10
     `name/createdAt/modifiedAt not found` errors are gone).
   - **MN-Contact.yaml**: validation passes (already passed last
     run).
   - **MN-Account.yaml**: validation now reports only the single
     remaining `industrySubsector empty options` error, addressed
     in a separate prompt.
   - **MN-Session.yaml**: validation now reports only the single
     remaining `topicsCovered empty options` error, addressed in
     the same separate prompt.

## 8. Commit

Single commit. Suggested message:

```
fix(validator): resolve EspoCRM native fields during validation

After d98db71 added cross-YAML field resolution, a Configure run
against the MN domain still produced 11 validation errors of
shape "field 'X' not found on entity 'Y'" where X was a
universal native field — name, description, createdAt, modifiedAt,
website. The deploy engine accepts these references without
complaint; the validator just didn't know they existed.

Cause: the validator's `field_names` set was the union of
custom-declared fields and cross-YAML siblings' contributions, but
omitted native fields contributed by EspoCRM itself based on
entity base type.

Fix: extend the validator's `field_names` construction to union
the native field set for the entity's base type. Custom entities
use the YAML-declared `type:` field; native entities (Contact,
Account, Lead, Meeting, etc.) infer their base type from a new
`NATIVE_ENTITY_BASE_TYPE` mapping at
`espo_impl/core/native_entity_types.py`. The native-field catalog
itself already existed at `espo_impl/core/audit_utils.py`
(SYSTEM_FIELDS, NATIVE_PERSON_FIELDS, NATIVE_COMPANY_FIELDS,
NATIVE_EVENT_FIELDS, NATIVE_BASE_FIELDS, get_native_fields_for_type);
the new helper `_native_field_names` consumes it.

All eight `field_names = {...}` sites in config_loader.py union
the new helper's output. No change to `ProgramContext` — native
fields are entity-type-derived, not batch-derived.

Five new tests cover system fields (createdAt/modifiedAt) on a
Base entity, native Base fields (name/description), native
Company fields (website on Account), native Person fields
(firstName/emailAddress on Contact), and continued typo
detection. The five d98db71 cross-YAML tests remain valid
without modification.

Validator-only change. Deploy engine behavior unchanged. The
`industrySubsector empty options` / `topicsCovered empty
options` validator-strictness issues are addressed separately.
```
