# Claude Code Prompt — Layout c-prefix fix for custom entities

**Repository:** `dbower44022/crmbuilder`
**Branch:** `main` (commit directly)
**Type:** Bug fix (single prompt, not part of a series)

---

## 1. Problem statement

The Configure flow generates broken detail/edit/list layouts for any
**custom entity** (e.g., `Contribution`, `Engagement`, `Session`,
`Workshop`, `Dues`, `Event`, `EventRegistration`,
`PartnershipAgreement`).

**Observed behavior:**

- Field creation succeeds. EspoCRM stores the fields with their
  natural names (e.g., `amount`/Currency, `applicationDate`/Date,
  `contributionType`/Enum). Verified directly in
  `Administration → Entity Manager → {Entity} → Fields`.
- Layout generation writes panel rows that reference c-prefixed
  field names (e.g., `cAmount`, `cStatus`, `cContributionType`,
  `cNotes`).
- These references do not match any real field, so EspoCRM renders
  every cell in the detail/edit form as a generic plain-text input.
  No date pickers, no enum dropdowns, no currency formatting, no
  WYSIWYG editor.
- The required system `name` field is never placed on the panel
  (because the layout used some other custom field as the title
  slot), so saving a new record fails with
  `Field: name, Validation: required`.

**Affected scope:** every custom entity layout. Native-entity layouts
(custom fields on `Contact`, `Account`, etc.) are not affected.

## 2. Root cause

`espo_impl/core/layout_manager.py`, the `_resolve_field_name`
static method (lines 521–533):

```python
@staticmethod
def _resolve_field_name(
    name: str, custom_field_names: set[str]
) -> str:
    if name in custom_field_names:
        return f"c{name[0].upper()}{name[1:]}"
    return name
```

The flawed assumption: *any field declared in the YAML's `fields:`
block is a custom field, and EspoCRM stores all custom fields with
a `c` prefix.*

What EspoCRM actually does: it auto-applies the `c` prefix to
custom fields **only when the parent entity is native** (Contact,
Account, Lead, etc.). When custom fields are added to a custom
entity (e.g., `CContribution`), they are stored with their natural
names — no `c` prefix. This is consistent with the rest of the
codebase: `field_manager._get_field_resolved` and
`tooltip_manager._get_field_resolved` both try the c-prefixed name
first, then fall back to the raw name precisely because the actual
storage form depends on the parent entity type. `layout_manager`
has no such fallback and produces broken references for every
custom-entity layout.

## 3. Fix

The minimal correct change is at the **input** to layout generation,
not at every call site of `_resolve_field_name`.

Currently, `process_layouts()` builds the c-prefix candidate set
unconditionally:

```python
custom_field_names = {f.name for f in field_definitions}
```

Change this to populate the set **only when the parent entity is
native**. For custom entities, pass an empty set, so
`_resolve_field_name` short-circuits on every cell and returns the
natural name.

This single-point fix preserves the existing `_resolve_field_name`
contract (`"if name is in this set, c-prefix it"`) and requires
no changes to the twelve helper signatures that thread
`custom_field_names` through. Existing tests at the helper level
remain valid.

## 4. Required code changes

### 4.1 `espo_impl/core/layout_manager.py`

**Change 1 — extend the import** at line 24:

Replace:

```python
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name
```

with:

```python
from espo_impl.ui.confirm_delete_dialog import (
    NATIVE_ENTITIES,
    get_espo_entity_name,
)
```

**Change 2 — the actual fix** in `process_layouts()` at line 66.

Replace:

```python
        results: list[LayoutResult] = []
        espo_name = get_espo_entity_name(entity_def.name)
        custom_field_names = {f.name for f in field_definitions}
```

with:

```python
        results: list[LayoutResult] = []
        espo_name = get_espo_entity_name(entity_def.name)

        # EspoCRM auto-applies the 'c' prefix to custom fields only
        # when their parent entity is native (Contact, Account, Lead,
        # etc.). On custom entities — already C-prefixed at the entity
        # level (CEngagement, CContribution, ...) — custom fields are
        # stored with their natural names, no per-field prefix.
        # Build the c-prefix candidate set accordingly: populated for
        # native parents, empty for custom parents. With an empty set,
        # `_resolve_field_name` short-circuits on every cell and the
        # layout references the actual stored field names.
        if entity_def.name in NATIVE_ENTITIES:
            custom_field_names = {f.name for f in field_definitions}
        else:
            custom_field_names = set()
```

**Change 3 — clarify the docstring** on `_resolve_field_name`
(lines 521–533).

Replace the existing docstring with:

```python
    @staticmethod
    def _resolve_field_name(
        name: str, custom_field_names: set[str]
    ) -> str:
        """Apply c-prefix to custom field names, pass other names through.

        :param name: Field name from YAML.
        :param custom_field_names: Names that should be c-prefixed.
            Callers must populate this set only when the parent entity
            is native (Contact, Account, etc.). For custom entities,
            pass an empty set — EspoCRM stores custom fields on
            custom entities under their natural names, with no
            per-field prefix.
        :returns: API field name.
        """
```

(The body of the method does not change.)

## 5. Required test changes

### 5.1 `tests/test_layout_manager.py`

The existing tests pass `custom_fields` directly to helper methods
and so still validate the helper contract correctly. They do not
need changes.

**Add four new tests** at the end of the file, before any final
trailing newline. These exercise the new entry-point logic in
`process_layouts()`:

```python
# --- Custom-entity c-prefix entry-point tests ---


def test_native_entity_layout_uses_c_prefix():
    """Custom fields on a native entity (Contact) are c-prefixed in
    layout cells, matching EspoCRM's auto-prefix behavior."""
    client = MagicMock(spec=EspoAdminClient)
    # Force a non-match so save_layout is invoked.
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contact",
        fields=make_fields(("contactType", "enum", "info")),
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(label="General", rows=[["contactType"]]),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    assert saved_payload[0]["rows"] == [[{"name": "cContactType"}]]


def test_custom_entity_layout_skips_c_prefix():
    """Custom fields on a custom entity (Contribution) are NOT
    c-prefixed — EspoCRM stores them under their natural names."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
            ("contributionType", "enum", "ident"),
            ("notes", "wysiwyg", "ack"),
        ),
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Identification",
                        rows=[["amount", "contributionType"]],
                    ),
                    PanelSpec(label="Acknowledgment", rows=[["notes"]]),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    assert saved_payload[0]["rows"] == [
        [{"name": "amount"}, {"name": "contributionType"}]
    ]
    assert saved_payload[1]["rows"] == [[{"name": "notes"}]]


def test_custom_entity_list_layout_skips_c_prefix():
    """List layout columns on a custom entity use natural names."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
            ("status", "enum", "ident"),
        ),
        layouts={
            "list": LayoutSpec(
                layout_type="list",
                columns=[
                    ColumnSpec(field="name", width=30),
                    ColumnSpec(field="amount", width=20),
                    ColumnSpec(field="status", width=20),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    assert saved_payload == [
        {"name": "name", "width": 30},
        {"name": "amount", "width": 20},
        {"name": "status", "width": 20},
    ]


def test_custom_entity_dynamic_logic_skips_c_prefix():
    """visibleWhen / dynamicLogicVisible attribute references on a
    custom entity layout use natural field names, not c-prefixed."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("contributionType", "enum", "ident"),
            ("nextGrantDeadline", "date", "grant"),
        ),
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Grant Details",
                        rows=[["nextGrantDeadline"]],
                        dynamicLogicVisible={
                            "attribute": "contributionType",
                            "value": "Grant",
                        },
                    ),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    panel = saved_payload[0]
    assert panel["dynamicLogicVisible"] == {
        "conditionGroup": [
            {
                "type": "equals",
                "attribute": "contributionType",
                "value": "Grant",
            }
        ]
    }
```

> **Note on the `client.save_layout.call_args.args[2]` access pattern:**
> `EspoAdminClient.save_layout(entity, layout_type, payload)` is the
> three-argument signature in this codebase. If your local copy
> uses a different positional order, adjust the index — the
> assertion target is the payload dict/list, not the entity name.
> Check `espo_impl/core/api_client.py` for the actual signature
> before running the tests.

## 6. Out of scope

- Do NOT refactor `_resolve_field_name`'s signature. The fix lives
  at the entry point.
- Do NOT touch `field_manager` or `tooltip_manager`. They already
  resolve field names correctly via the try-c-prefix-then-fallback
  pattern.
- Do NOT touch `relationship_manager`. Its c-prefix handling is for
  link names on the foreign side, a separate concern.
- Do NOT change YAML files in any client repository
  (`ClevelandBusinessMentoring` etc.). The YAML is correct as
  written; only the layout writer was wrong.
- Do NOT update `CLAUDE.md`'s "Key Patterns" section. The existing
  bullet about c-prefix is still correct in spirit; this fix
  refines the *trigger condition* without changing the principle.

## 7. Verification steps

After applying the fix:

1. **Unit tests:** `uv run pytest tests/test_layout_manager.py -v`.
   All existing tests must still pass; the four new tests must
   pass.
2. **Lint:** `uv run ruff check espo_impl/ tests/test_layout_manager.py`.
3. **End-to-end (manual, run by Doug):** Re-run Configure on
   `FU-Contribution.yaml` against the live CBM instance. Open
   `Administration → Entity Manager → Contribution → Layouts → Detail`
   and confirm panel rows now show non-prefixed field names
   (`amount`, `status`, `contributionType`, `notes`, ...) instead of
   `cAmount`, `cStatus`, etc. Open the Contributions list, click
   `+ Create`, and confirm date fields render as date pickers, the
   Type/Status fields render as enum dropdowns, the Amount field
   renders as currency, and the Notes field renders as a WYSIWYG
   editor. Saving a record should succeed without a backend
   validation error.

## 8. Commit

Single commit, message:

```
fix(layout): skip c-prefix for fields on custom entities

EspoCRM auto-applies the 'c' prefix to custom fields only when
the parent entity is native (Contact, Account, etc.). When custom
fields are added to a custom entity such as Contribution or
Engagement, they are stored under their natural names with no
per-field prefix.

LayoutManager.process_layouts() unconditionally treated every YAML
field as a c-prefix candidate, producing layout panel rows that
referenced names like cAmount, cStatus, cContributionType for
custom entities — names that do not match any real field. EspoCRM
fell back to rendering each cell as a generic plain-text input
(no date pickers, no enum dropdowns, no currency formatting), and
the required system `name` field was never placed, so saving a
new record failed with a backend validation error.

Fix: in process_layouts(), build the custom_field_names set only
when the parent entity is in NATIVE_ENTITIES. For custom entities,
pass an empty set so _resolve_field_name short-circuits on every
cell and the layout references the actual stored field names.

This mirrors the pattern already used by FieldManager and
TooltipManager (try c-prefixed, fall back to raw) but at the
entry point rather than per-call, since EspoCRM's behavior here
is deterministic by parent-entity type.

Adds four entry-point tests covering native-entity c-prefix,
custom-entity panel rows, custom-entity list columns, and
custom-entity dynamic logic.
```
