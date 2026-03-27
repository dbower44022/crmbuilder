# Claude Code Prompt — Add copyToClipboard Field Property

## Context

CRM Builder currently supports these field properties in YAML program files:
`name`, `type`, `label`, `required`, `default`, `readOnly`, `audited`,
`options`, `translatedOptions`, `style`, `isSorted`, `displayAsLabel`,
`min`, `max`, `maxLength`, `category`, `description`.

We need to add `copyToClipboard` — an EspoCRM field property that adds a
copy-to-clipboard button next to a field in the detail view. Useful for
fields like email addresses, phone numbers, account numbers, EIN numbers,
URLs, and any other value a user would frequently want to copy.

EspoCRM API field name: `copyToClipboard` (boolean).

This is a small, targeted change in three files. Read the existing code
in each file before making changes. Make no other modifications.

---

## Task 1 — `espo_impl/core/models.py`

Add `copyToClipboard` to the `FieldDefinition` dataclass, after `audited`:

```python
copyToClipboard: bool | None = None
```

---

## Task 2 — `espo_impl/core/config_loader.py`

In `_parse_field()`, add parsing for `copyToClipboard` alongside the
other optional boolean properties. Follow the same pattern as `audited`:

```python
copyToClipboard=data.get("copyToClipboard"),
```

---

## Task 3 — `espo_impl/core/field_manager.py`

In `_build_field_payload()` (or wherever `audited` is added to the
payload), add `copyToClipboard` following the same pattern:

```python
if field_def.copyToClipboard is not None:
    payload["copyToClipboard"] = field_def.copyToClipboard
```

---

## Task 4 — Add tests

In `tests/test_config_loader.py`, add a test confirming `copyToClipboard`
is parsed correctly from YAML.

In `tests/test_field_manager.py`, add a test confirming `copyToClipboard`
is included in the field payload when set to `True`, and omitted when
`None`.

---

## Task 5 — Update documentation

In `PRDs/crmbuilder-spec-espocrm-impl.md`, add `copyToClipboard` to the
field definition schema table (the table listing all supported field
properties). Add it after `audited`. Description:

> `copyToClipboard` | boolean | no | Adds a copy-to-clipboard button
> next to the field in detail view. Useful for email, phone, URL, EIN,
> and other frequently-copied values. EspoCRM API property:
> `copyToClipboard`.

Bump the spec version by a patch increment.

---

## Confirm after each task before proceeding to the next.
