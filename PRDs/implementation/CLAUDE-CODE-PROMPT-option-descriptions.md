# Claude Code Prompt — Add optionDescriptions Field Property

## Context

CRM Builder YAML files currently support `options` (the list of values),
`translatedOptions` (display labels), and `style` (color per value) for
enum and multiEnum fields.

We are adding `optionDescriptions` — an optional map that provides a
plain-language description for each enum option value. This is
**documentation only** — it is never deployed to EspoCRM (EspoCRM has no
field-level storage for per-option descriptions). It appears in generated
PRD documentation and helps YAML authors and reviewers understand what
each status or dropdown value means.

The full specification is in `PRDs/crmbuilder-spec-espocrm-impl.md` v2.0,
Section 5.2. Read it before writing any code.

---

## Task 1 — `espo_impl/core/models.py`

Add `optionDescriptions` to `FieldDefinition` after `options`:

```python
optionDescriptions: dict[str, str] | None = None
```

---

## Task 2 — `espo_impl/core/config_loader.py`

In `_parse_field()`, add parsing for `optionDescriptions`:

```python
optionDescriptions=data.get("optionDescriptions"),
```

Add validation in `validate_program()`:

- If `optionDescriptions` is present, `type` must be `enum` or `multiEnum`
- If `optionDescriptions` is present and `options` is also present, every
  key in `optionDescriptions` must exist in `options`. Keys in `options`
  that are not in `optionDescriptions` are allowed — descriptions are
  optional per-value.
- If `optionDescriptions` is present but `options` is absent, emit a
  warning (not an error) — the descriptions will be stored but cannot
  be cross-referenced.

---

## Task 3 — Confirm NOT deployed

In `espo_impl/core/field_manager.py`, confirm that `optionDescriptions`
is **not** included in any field payload. It must never be sent to the
EspoCRM API. Add a comment near the payload-building code:

```python
# optionDescriptions is documentation-only — never included in API payloads
```

---

## Task 4 — Add tests

In `tests/test_config_loader.py`:

- `optionDescriptions` parsed correctly from YAML
- All keys in `optionDescriptions` exist in `options` → valid
- Key in `optionDescriptions` not in `options` → validation error
- `optionDescriptions` on a non-enum field → validation error
- `optionDescriptions` present without `options` → warning, not error
- Field with no `optionDescriptions` → `optionDescriptions` is `None`

In `tests/test_field_manager.py`:

- Confirm `optionDescriptions` is never present in field API payloads
  (add assertion that the built payload dict does not contain the key
  `optionDescriptions`)

---

## Task 5 — Update spec and user guide

### `PRDs/crmbuilder-spec-espocrm-impl.md`

Already updated to v2.0 with full specification. No further changes needed.

### `docs/user-guide.md`

Add a subsection under the YAML authoring chapter covering:

- What `optionDescriptions` is for
- That it is documentation-only and never deployed
- The key-matching rule (keys must match values in `options`)
- A short example showing a status field with descriptions

---

## Implementation Order

1. Task 1 — models.py
2. Task 2 — config_loader.py
3. Task 4 — tests (confirm passing)
4. Task 3 — confirm not in field_manager payload
5. Task 5 — user-guide.md update

Confirm with me after Task 4 tests are passing before proceeding to Task 5.
