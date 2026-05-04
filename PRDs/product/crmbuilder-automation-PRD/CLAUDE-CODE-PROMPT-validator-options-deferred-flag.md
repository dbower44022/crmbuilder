# Claude Code Prompt — Validator: support `optionsDeferred: true` for empty enum option lists

**Repository:** `dbower44022/crmbuilder`
**Branch:** `main` (commit directly)
**Type:** Validator-vs-deploy strictness fix; new YAML schema flag

---

## 1. Problem statement

The validator that runs at the start of every Configure operation
rejects `enum` and `multiEnum` fields with empty `options: []`,
even when the field is a deliberate Phase 9 deferral with a
documented MANUAL-CONFIG.md plan for post-deploy operator
configuration.

Live evidence — after the cross-YAML and native-field validator
fixes (commits `d98db71` and `8345cd8`), a Configure run against
the MN+CR-Account batch reduced from 13 errors to 2 — and both
remaining errors are this same pattern:

```
=== MN/MN-Account.yaml: VALIDATION FAILED (1 error(s)) ===
  - Account.industrySubsector: enum/multiEnum fields must have a non-empty 'options' list

=== MN/MN-Session.yaml: VALIDATION FAILED (1 error(s)) ===
  - Session.topicsCovered: enum/multiEnum fields must have a non-empty 'options' list
```

Both fields are real Phase 9 deferrals:

- `industrySubsector` (`MN-Account.yaml`) — ~100-value taxonomy
  with dependent-enum filtering on `industrySector`. EspoCRM's
  dependent-enum feature has no REST API write path; configured
  post-deploy via admin UI. Tracked in `MN-MC-DD-002`. Phase 9
  deferral recorded in `MN-Y9-EXC-005`.
- `topicsCovered` (`MN-Session.yaml`) — multi-enum for session
  topic taxonomy. CBM has not yet decided between SBA-aligned vs.
  custom taxonomy per `MN-DEC-019`. Phase 9 deferred the values
  pending that internal decision.

The deploy engine itself accepts empty option lists without
complaint — the field is created with no options and the operator
populates it via the EspoCRM admin UI later. Only the validator
treats empty options as a hard error.

The validator's current rule cannot distinguish two semantically
different cases:

- **Forgetfulness** — author meant to write options and forgot.
  Validator should catch this. Default behavior must remain
  strict.
- **Deliberate deferral** — author knows there's no expressible
  list yet, has documented why, intends post-deploy operator
  configuration. Validator is wrong to block this.

## 2. Solution

Add an explicit "I know this is empty, on purpose" marker to the
schema. The author signs the deferral in writing; the validator
honors the signature; the deploy engine doesn't care.

### Functional behavior

The marker is a new boolean property on `enum`/`multiEnum`
fields:

```yaml
optionsDeferred: true
```

Default `false`. Only meaningful on `enum` and `multiEnum`.

**Validator logic** — when `type` is `enum` or `multiEnum` and
`options` is empty:

| `optionsDeferred` value | Validator outcome |
|---|---|
| `true` | Pass. Field accepted with empty options. |
| `false` or absent | Fail with the existing error message. (Unchanged from today.) |

When `options` is non-empty, `optionsDeferred` is ignored entirely
— a non-empty list always wins.

The flag must be a boolean. `optionsDeferred: "yes"` or any other
non-bool value is a separate validation error, mirroring the
existing type-checks on `stream`, `disabled`, and `autoPlaceName`.

`optionsDeferred: true` is also rejected when applied to a
non-enum field type. The flag has no meaning on text, date,
currency, etc.; allowing it would mask author confusion.

**Deploy engine logic** — unchanged. The flag is metadata for the
validator, not deploy-time state. The engine writes the field with
whatever options are provided, including empty.

### Why a separate boolean rather than a sentinel value

Two alternative shapes were considered and rejected:

- **`options: deferred`** (string sentinel where a list is
  expected): changes the type of `options` from "list" to
  "list-or-string," complicates parsing, makes the schema messier.
- **`options: { deferred: true }`** (object where a list is
  expected): same type-coupling problem.

Keeping `options:` always a list and putting the deferral marker
in a separate boolean keeps the schema parse cleanly typed and
mirrors the pattern already used for `stream`, `disabled`, and
`autoPlaceName`.

## 3. Required code changes

### 3.1 `espo_impl/core/models.py`

Extend `FieldDefinition` (around line 88, alongside `options:`):

Insert a new line after `optionDescriptions: dict[str, str] | None = None`:

```python
    options: list[str] | None = None
    optionDescriptions: dict[str, str] | None = None
    optionsDeferred: bool | None = None
```

Update the docstring to mention the new property:

```python
class FieldDefinition:
    """A single field specification from a YAML program file.

    :param name: Internal field name (lowerCamelCase).
    :param type: EspoCRM field type.
    :param label: Display label.
    :param optionsDeferred: When True on an enum/multiEnum field
        with empty `options`, the validator accepts the empty list.
        Used for fields where the value list cannot be expressed
        at Phase 9 generation time and is documented for
        post-deploy operator configuration in MANUAL-CONFIG.md.
        Default None (treated as False).
    """
```

### 3.2 `espo_impl/core/config_loader.py` — `_parse_field`

Update the `FieldDefinition(...)` constructor call in `_parse_field`
(around line 466–494) to read the new property:

Insert immediately after the `optionDescriptions=data.get("optionDescriptions"),`
line:

```python
            options=data.get("options"),
            optionDescriptions=data.get("optionDescriptions"),
            optionsDeferred=data.get("optionsDeferred"),
            translatedOptions=data.get("translatedOptions"),
```

### 3.3 `espo_impl/core/config_loader.py` — empty-options validator

Modify the existing empty-options check at line 754–758:

Replace:

```python
        if field_def.type in ENUM_TYPES:
            if not field_def.options:
                errors.append(
                    f"{prefix}: enum/multiEnum fields must have a non-empty 'options' list"
                )
```

with:

```python
        if field_def.type in ENUM_TYPES:
            if not field_def.options and not field_def.optionsDeferred:
                errors.append(
                    f"{prefix}: enum/multiEnum fields must have a "
                    f"non-empty 'options' list (or set 'optionsDeferred: true' "
                    f"to defer the list to post-deploy operator configuration)"
                )

        # optionsDeferred is only meaningful on enum/multiEnum.
        # Setting it on any other type is author confusion — flag it.
        if field_def.optionsDeferred is True and field_def.type not in ENUM_TYPES:
            errors.append(
                f"{prefix}: 'optionsDeferred' is only valid on "
                f"enum/multiEnum fields"
            )

        # optionsDeferred must be a boolean if present at all.
        if (
            field_def.optionsDeferred is not None
            and not isinstance(field_def.optionsDeferred, bool)
        ):
            errors.append(
                f"{prefix}: 'optionsDeferred' must be a boolean"
            )
```

The error-message extension keeps the original "must have a
non-empty options list" guidance for typo cases and adds the
escape hatch in parentheses for cases that genuinely need the
deferral.

### 3.4 No changes to deploy engine

`field_manager.py` and the rest of the deploy pipeline do not need
any change. The flag is validator-only metadata. Verify by reading
once that no code in `espo_impl/core/field_manager.py` or
`espo_impl/core/comparator.py` looks for `optionsDeferred` — it
shouldn't.

## 4. Schema documentation update

### 4.1 `PRDs/product/app-yaml-schema.md` — Section 6.3

Append `optionsDeferred` to the table in Section 6.3 (Enum and
Multi-Select Properties):

Replace:

```markdown
| Property | Type | Required | Description |
|---|---|---|---|
| `options` | list | yes | Ordered list of allowed values |
| `translatedOptions` | map | no | Display label for each option value |
| `style` | map | no | Color style per option (see Section 6.4) |
| `isSorted` | boolean | no | Sort options alphabetically. Default: `false` |
| `displayAsLabel` | boolean | enum only | Display value as a colored badge. Default: `false` |
```

with:

```markdown
| Property | Type | Required | Description |
|---|---|---|---|
| `options` | list | yes (unless `optionsDeferred: true`) | Ordered list of allowed values |
| `optionsDeferred` | boolean | no | When `true`, allows `options` to be empty. Used when the value list cannot be expressed at YAML-authoring time and is configured post-deploy via the EspoCRM admin UI. Default: `false` |
| `translatedOptions` | map | no | Display label for each option value |
| `style` | map | no | Color style per option (see Section 6.4) |
| `isSorted` | boolean | no | Sort options alphabetically. Default: `false` |
| `displayAsLabel` | boolean | enum only | Display value as a colored badge. Default: `false` |
```

Then add a new subsection immediately after Section 6.4, before
Section 6.5:

```markdown
### 6.4.1 Deferred-Options Pattern

EspoCRM enum and multi-enum fields ordinarily require an explicit
`options:` list. The default validator behavior rejects empty
`options:` to catch authoring mistakes (a dropdown with no values
is almost always an oversight).

In some cases, the value list cannot be expressed at YAML-
authoring time:

- **Schema-gap deferrals** — EspoCRM features like dependent
  enums (where one dropdown's options depend on another field's
  value) have no REST API write path. The `options:` list must be
  configured through the admin UI post-deploy. The YAML records
  the field's existence and type but defers the values.
- **Open-decision deferrals** — the value taxonomy is an open
  decision at YAML-authoring time. The field exists in the schema
  and is needed at deploy, but the actual value list is being
  decided in parallel and will be populated post-deploy.

For these cases, set `optionsDeferred: true` on the field. The
validator accepts the empty list. The deploy engine creates the
field with no options. The operator populates the option list via
the EspoCRM admin UI based on a corresponding `MANUAL-CONFIG.md`
entry.

#### Worked example

```yaml
- name: industrySubsector
  type: enum
  label: "Industry Subsector"
  description: >
    ~100 values, dependent-filtered on industrySector.
    Configure post-deploy per MANUAL-CONFIG.md.
  optionsDeferred: true
  options: []
```

#### Companion artifact

Every field with `optionsDeferred: true` should have a matching
entry in the program's `MANUAL-CONFIG.md` documenting:

- the path the operator follows in the admin UI;
- the source of truth for the value list (taxonomy, master list,
  PRD reference);
- if applicable, dependent-enum configuration steps.

`optionsDeferred: true` without a `MANUAL-CONFIG.md` entry is a
generation-process bug; the methodology requires both halves of
the deferral to be authored together.
```

Also bump the document's `Last Updated` date in the revision
control section to today's date in `MM-DD-YY HH:MM` format, and
add a row to the change-log table documenting the new
`optionsDeferred` flag and Section 6.4.1.

## 5. Required tests

Add to `tests/test_config_loader.py`:

```python
def test_validate_program_accepts_empty_options_when_options_deferred_true():
    """An enum field with options:[] and optionsDeferred:true
    validates cleanly."""
    # Construct a minimal entity with a single enum field that has
    # options: [] and optionsDeferred: true.
    # Validate. Assert no errors related to options.


def test_validate_program_still_rejects_empty_options_when_flag_absent():
    """An enum field with options:[] and no optionsDeferred flag
    is still rejected — default strictness preserved."""
    # Construct a minimal entity with a single enum field that has
    # options: [] and no optionsDeferred field.
    # Validate. Assert the standard 'must have a non-empty options
    # list' error is reported.


def test_validate_program_still_rejects_empty_options_when_flag_false():
    """Explicit optionsDeferred: false does not bypass the check."""
    # Construct a minimal entity with options: [] and
    # optionsDeferred: false.
    # Validate. Assert the standard error is reported.


def test_validate_program_options_deferred_must_be_boolean():
    """optionsDeferred:'yes' or other non-bool values are rejected
    with a type-check error."""
    # Construct a field with options: [] and optionsDeferred: "yes".
    # Validate. Assert error: 'optionsDeferred' must be a boolean.


def test_validate_program_options_deferred_only_on_enum_types():
    """optionsDeferred:true on a non-enum field type (e.g. text)
    is flagged as inappropriate."""
    # Construct a varchar field with optionsDeferred: true.
    # Validate. Assert error: 'optionsDeferred' is only valid on
    # enum/multiEnum fields.


def test_validate_program_non_empty_options_with_options_deferred_validates():
    """When options is non-empty, optionsDeferred is ignored —
    explicit options always win regardless of the flag."""
    # Construct an enum field with both options: ["A", "B"] and
    # optionsDeferred: true.
    # Validate. Assert no errors. Field is treated as a normal
    # enum with two options; the deferred flag has no effect.
```

Existing tests of enum/multiEnum validation continue to pass
without modification — the strict default path is unchanged.

## 6. Out of scope

- Do NOT modify any YAML files in this prompt. Authoring
  `optionsDeferred: true` on `industrySubsector` and
  `topicsCovered` is a follow-up commit by the operator after the
  validator change is in place.
- Do NOT modify the deploy engine. The validator is the single
  enforcement point for the empty-options rule today.
- Do NOT change `optionDescriptions`, `translatedOptions`, or
  any other enum-related validation. Those checks are correct as
  they are.
- Do NOT change behavior for non-enum field types — except the
  new "optionsDeferred only on enum types" check, which is purely
  additive.
- Do NOT change the Phase 9 generator. Whether and how the
  generator authors `optionsDeferred: true` is a separate
  methodology question.

## 7. Verification steps

1. **Unit tests:** `uv run pytest tests/test_config_loader.py -v`.
   All previously passing tests must still pass; the six new
   tests must pass.
2. **Lint:** `uv run ruff check espo_impl/ tests/`.
3. **End-to-end (manual, by Doug):** No live verification of this
   prompt alone. The CBM YAML deployment validation comes after a
   follow-up commit adding `optionsDeferred: true` to
   `industrySubsector` (in `MN-Account.yaml`) and `topicsCovered`
   (in `MN-Session.yaml`). After that commit lands, re-run the
   five-file Configure batch. Expected: all five files validate
   clean and proceed to deploy. Both deferred-options fields are
   created with empty option lists. The corresponding
   `MANUAL-CONFIG.md` entries already exist and tell the operator
   what to do post-deploy.

## 8. Commit

Single commit. Suggested message:

```
feat(validator): support optionsDeferred:true on enum fields

Two CBM YAMLs (MN-Account, MN-Session) ship enum fields with
empty options: [] by deliberate Phase 9 deferral —
industrySubsector (dependent-enum, no REST API write path) and
topicsCovered (open taxonomy decision per MN-DEC-019). Both have
matching MANUAL-CONFIG.md entries telling the operator how to
configure the values post-deploy via the EspoCRM admin UI. The
deploy engine accepts empty options without complaint, but the
validator rejects them — so a documented deferral with operator
follow-up is indistinguishable to the validator from forgotten
options.

Fix: add a new optional field property `optionsDeferred: bool`.
Default false (treated as None). When true on an enum/multiEnum
field with empty options, the validator accepts the empty list.
On any other field type, optionsDeferred:true is itself a
validation error (mirrors the existing 'optionDescriptions only
on enum/multiEnum' rule). Type-check validates the value is
actually a boolean.

The default strictness path is unchanged — fields with empty
options and no flag are still rejected with the same message,
extended with a hint that points to optionsDeferred for
legitimate deferrals.

Schema doc Section 6.3 adds a row for the new property; new
Section 6.4.1 documents the deferred-options pattern with a
worked example and the MANUAL-CONFIG.md companion-artifact rule.

Six new tests cover: flag-true accepts empty options; flag-absent
still rejects; flag-false still rejects; non-bool flag rejected;
flag on non-enum type rejected; non-empty options with flag
ignored.

Validator-only change. Deploy engine behavior unchanged. The two
CBM YAMLs that need the flag will be updated in a follow-up
commit.
```
