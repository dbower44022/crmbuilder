# Claude Code Prompt — Validator: resolve field references across sibling YAMLs

**Repository:** `dbower44022/crmbuilder`
**Branch:** `main` (commit directly)
**Type:** Bug fix — validator scope correction

---

## 1. Problem statement

The validator that runs at the start of every Configure operation
rejects every multi-YAML deployment to a native entity. Live
evidence: a Configure run against `programs/MN/MN-Account.yaml`
returned eight validation errors, seven of which are variations of
the same misdiagnosis:

```
=== MN/MN-Account.yaml: VALIDATION FAILED (8 error(s)) ===
- Account.organizationType.visibleWhen: Field 'accountType' not found in entity fields
- Account.businessStage.requiredWhen: Field 'accountType' not found in entity fields
- Account.businessStage.visibleWhen: Field 'accountType' not found in entity fields
- Account.industrySector.visibleWhen: Field 'accountType' not found in entity fields
- Account.industrySubsector.visibleWhen: Field 'accountType' not found in entity fields
- Account.clientNotes.visibleWhen: Field 'accountType' not found in entity fields
- Account.layout.detail.panel[Client Profile].visibleWhen: Field 'accountType' not found in entity fields
- Account.industrySubsector: enum/multiEnum fields must have a non-empty 'options' list
```

Seven of those eight errors are wrong. `accountType` is a real
field — declared in `programs/CR/CR-Account.yaml`'s entity block.
CR is the owner of the discriminator; MN, MR, and FU all extend
the same native Account entity with type-conditional fields that
reference `accountType`. The same is true for `contactType` on
the native Contact entity, declared in MR-Contact.yaml and
referenced by MN-Contact, FU-Contact, and CR-Contact.

The validator's mental model is wrong: it assumes a one-YAML-per-
entity world, where every field reference must resolve within the
single file under validation. The actual design is many-YAMLs-
per-native-entity, where domain YAMLs collectively contribute
custom fields to native Contact, Account, etc. — and reference
each others' fields through `requiredWhen`, `visibleWhen`, panel
conditions, savedView filters, filteredTab conditions, and
workflow conditions.

The deploy engine itself is fine — it processes each YAML in
sequence, and by the time `MN-Account.yaml` is configured,
`CR-Account.yaml` has already declared `accountType`. The validator
just runs first and rejects the second-and-later YAMLs without
considering the rest of the program directory.

The eighth error (`industrySubsector` empty `options:`) is a
separate validator-vs-deploy-strictness discrepancy, addressed in
a companion prompt; it is **out of scope here**.

## 2. Root cause

`espo_impl/core/config_loader.py`. The validator builds the set
of valid field references with this single line, repeated at
eight call sites (lines 559, 834, 882, 965, 1095, 1240, 1472,
1744):

```python
field_names = {f.name for f in entity.fields}
```

This set drives validation of:

- field-level `requiredWhen` / `visibleWhen` (line 882 et al.)
- panel-level `visibleWhen` (line 559)
- savedView filter conditions (line 965)
- filteredTab conditions (line 1095, 1240, 1472, 1744)
- workflow `where` conditions

In every case, `field_names` should also include any **fields
contributed by sibling YAML files in the same program directory
to the same parent entity**.

`validate_program(program)` is called per-file by
`automation/ui/deployment/configure_progress.py:214`. The UI
iterates `self._files` (the list of YAML files the operator
selected) and validates each in isolation. There is no current
concept of a "program directory" or "deployment batch" the
validator can consult.

## 3. Fix

Two-part change. The first establishes the cross-file context.
The second wires it into validation.

### 3.1 New `ProgramContext` value object

Add a value object to `espo_impl/core/models.py` that carries
information about all programs in a deployment batch:

```python
@dataclass(frozen=True)
class ProgramContext:
    """Cross-file context used during validation.

    A deployment batch is a set of YAML program files all targeting
    the same EspoCRM instance. Domain-owned YAMLs commonly extend
    a shared native entity (Contact, Account, etc.) with
    domain-specific fields, and reference each others' fields via
    requiredWhen, visibleWhen, panel conditions, savedView filters,
    filteredTab conditions, and workflow conditions.

    `ProgramContext` exposes the union of field names per entity
    across the entire batch, so single-file validation can resolve
    references that are satisfied by sibling files.

    :param fields_by_entity: Mapping of entity natural name (e.g.
        'Contact', 'Account', 'Engagement') to the set of all
        field names declared for that entity across the batch.
        Custom-entity names appear in their natural form (without
        the 'C' prefix EspoCRM applies on the wire).
    """

    fields_by_entity: dict[str, frozenset[str]]

    def field_names_for(self, entity_name: str) -> frozenset[str]:
        """Return the union of declared field names for `entity_name`,
        or an empty frozenset if no sibling file declares any.
        """
        return self.fields_by_entity.get(entity_name, frozenset())

    @classmethod
    def from_programs(cls, programs: list["ProgramFile"]) -> "ProgramContext":
        """Build a context from a list of parsed programs.

        Iterates every entity in every program and unions field
        names by entity natural name. Self-referential — a single
        program counted in this context will have all of its own
        fields available too, so callers can pass a single
        program and use the same code path.
        """
        from collections import defaultdict
        fields_by_entity: dict[str, set[str]] = defaultdict(set)
        for program in programs:
            for entity in program.entities:
                for field_def in entity.fields:
                    fields_by_entity[entity.name].add(field_def.name)
        return cls(
            fields_by_entity={
                k: frozenset(v) for k, v in fields_by_entity.items()
            }
        )
```

### 3.2 New `validate_program_with_context` entry point

Add a second validation method on `ConfigLoader` in
`espo_impl/core/config_loader.py` that takes a `ProgramContext`
parameter. The existing `validate_program(program)` keeps working
exactly as today (single-file fallback for callers that haven't
been updated and for any future single-file workflows). The new
method delegates to existing private validators with the context
threaded through:

```python
def validate_program_with_context(
    self,
    program: ProgramFile,
    context: ProgramContext,
) -> list[str]:
    """Validate `program`, resolving field references against the
    union of field names from all programs represented in `context`.

    See `ProgramContext` for why a deployment batch must validate
    field references against the union rather than the single file.

    :param program: Parsed program file to validate.
    :param context: Cross-file context built from all programs in
        the deployment batch.
    :returns: List of error messages. Empty list means valid.
    """
    self._active_context = context
    try:
        return self.validate_program(program)
    finally:
        self._active_context = None
```

The existing `validate_program(program)` method gets a
self-context fallback at the top:

```python
def validate_program(self, program: ProgramFile) -> list[str]:
    """Validate a parsed program file.

    When called without prior `validate_program_with_context`, the
    validator builds a single-file context internally. This
    preserves backward-compatible single-file validation for any
    caller that hasn't migrated. Multi-file callers should use
    `validate_program_with_context` to benefit from cross-file
    field resolution.

    :param program: Parsed program file to validate.
    :returns: List of error messages. Empty list means valid.
    """
    if getattr(self, "_active_context", None) is None:
        self._active_context = ProgramContext.from_programs([program])

    # ... existing body unchanged ...
```

The `_active_context` attribute is consulted by the eight
field-name builder sites:

```python
field_names = {f.name for f in entity.fields} | self._active_context.field_names_for(entity.name)
```

This is **purely additive** at every call site. Single-file
validation behavior is unchanged when the context contains only
the current program (the field set is identical to today's). Cross-
file references resolve when the context covers siblings.

### 3.3 Update the configure UI to thread the context

In `automation/ui/deployment/configure_progress.py`, around line
206-217, change the validation pass to:

1. First, parse every selected file into a `ProgramFile` (or
   record a parse error). Same as today.
2. Then build one `ProgramContext` from the union of successfully
   parsed programs.
3. Then validate each program against that shared context.

Replace:

```python
loader = ConfigLoader()
validation_failures: list[tuple[YamlFileInfo, list[str]]] = []

for f in self._files:
    try:
        program = loader.load_program(Path(f.path))
    except Exception as exc:
        self._append_log(f"Failed to load {f.name}: {exc}", "error")
        self._record_validation_failure(f, [f"Parse error: {exc}"])
        continue

    errors = loader.validate_program(program)
    if errors:
        validation_failures.append((f, errors))
        continue

    self._pending.append((f, program))
    self._total_ops += _count_operations(program)
```

with:

```python
loader = ConfigLoader()
validation_failures: list[tuple[YamlFileInfo, list[str]]] = []

# Pass 1: parse every file. Parse errors are terminal for that
# file; we record them and exclude the file from validation.
parsed: list[tuple[YamlFileInfo, ProgramFile]] = []
for f in self._files:
    try:
        program = loader.load_program(Path(f.path))
    except Exception as exc:
        self._append_log(f"Failed to load {f.name}: {exc}", "error")
        self._record_validation_failure(f, [f"Parse error: {exc}"])
        continue
    parsed.append((f, program))

# Build the cross-file validation context from every successfully
# parsed program. Domain YAMLs commonly extend a shared native
# entity (Contact, Account) with custom fields, and reference
# each others' fields via requiredWhen / visibleWhen / panel
# conditions / savedView filters / filteredTab conditions /
# workflow conditions. Without a cross-file context, the validator
# rejects every YAML that references a field declared by a sibling.
context = ProgramContext.from_programs([p for _, p in parsed])

# Pass 2: validate each program against the shared context.
for f, program in parsed:
    errors = loader.validate_program_with_context(program, context)
    if errors:
        validation_failures.append((f, errors))
        continue

    self._pending.append((f, program))
    self._total_ops += _count_operations(program)
```

(Add `from espo_impl.core.models import ProgramContext` to the
imports at the top of the file alongside `ProgramFile`.)

## 4. What this does NOT change

- **Deploy ordering** — unchanged. The deploy engine already runs
  each program in sequence and does the right thing when
  `accountType` exists by the time MN-Account is configured. This
  fix only adjusts validation.
- **Single-file validation** — unchanged. `validate_program(program)`
  with no context now builds a single-program context internally
  on entry and behaves exactly as today. Tests that exercise
  single-file validation pass without modification.
- **Field type validation** — out of scope. The `industrySubsector
  empty options` error from the live evidence is a separate
  validator-strictness issue and gets its own prompt. Do not touch
  it here.
- **Native field synthesis** — out of scope. The validator's
  treatment of native fields (`name`, `description`, `createdAt`,
  etc.) is whatever it is today, and remains unchanged.
- **Self-referential validation** — single-program cases still go
  through the same code path with a one-program context. There's
  no separate code path for "single file mode" vs "batch mode";
  the implementation falls naturally out of the union construction.

## 5. Required code changes — summary

| File | Change | Approx. lines |
|---|---|---|
| `espo_impl/core/models.py` | Add `ProgramContext` dataclass | +35 |
| `espo_impl/core/config_loader.py` | Add `_active_context` attribute, `validate_program_with_context` method, self-context fallback in `validate_program`, and union the context's fields into `field_names` at all eight call sites | +25, eight 1-line edits |
| `automation/ui/deployment/configure_progress.py` | Two-pass validation flow with shared context | +15 net |
| `tests/test_config_loader.py` | Tests for cross-file resolution and single-file backward compatibility | +5 tests |

Total: ~80 lines of code change plus tests.

## 6. Required tests

Add to `tests/test_config_loader.py`:

```python
def test_program_context_unions_fields_across_programs():
    """ProgramContext.from_programs builds a union of field names
    by entity across every program passed in."""
    # Construct two ProgramFile instances both targeting Account,
    # one declaring accountType and one declaring organizationType.
    # Build context. Assert field_names_for("Account") has both.


def test_validate_program_with_context_resolves_cross_file_field_refs():
    """A program that references a field declared by a sibling
    YAML validates clean when the sibling is in the context."""
    # Construct a CR-Account-like program declaring accountType,
    # and an MN-Account-like program with a visibleWhen referencing
    # accountType. Build context from both. Validate the MN-style
    # program against the context. Assert no errors related to
    # accountType.


def test_validate_program_without_context_uses_single_file_fallback():
    """Calling validate_program(program) with no prior context
    builds a single-program context and behaves as before."""
    # Construct a single program with internally-consistent
    # references. Validate. Assert no errors.


def test_validate_program_without_context_still_catches_real_typos():
    """The single-program-context fallback does not mask references
    to genuinely unknown fields."""
    # Construct a single program with a visibleWhen referencing
    # a field that does NOT exist in this program AND is not a
    # native field. Validate. Assert the appropriate "not found"
    # error is reported.


def test_validate_program_with_context_still_catches_real_typos():
    """Cross-file context unions known fields but does NOT cover
    typos. A reference to a name that no sibling declares is
    still flagged."""
    # Build a context covering accountType. Construct a program
    # with a visibleWhen referencing 'acountType' (typo). Validate.
    # Assert the appropriate "not found" error is reported.
```

Existing tests of `validate_program(program)` with a single
program continue to pass without modification — the single-program
context fallback is transparent.

## 7. Out of scope

- Do NOT touch the `industrySubsector empty options` validation.
  That is a separate prompt.
- Do NOT change deploy-engine behavior. The fix is validator-only.
- Do NOT change `condition_expression.py`. Its `validate_condition`
  signature is fine — it already accepts a field-names set; we're
  just feeding it a richer set.
- Do NOT modify any YAML files. Once this fix lands, the existing
  CBM YAML set deploys without YAML edits.

## 8. Verification steps

1. **Unit tests:** `uv run pytest tests/test_config_loader.py -v`.
   All previously passing tests must still pass; the five new
   tests must pass.
2. **Lint:** `uv run ruff check espo_impl/ automation/ tests/`.
3. **End-to-end (manual, by Doug):** Re-run Configure on
   `programs/MN/MN-Account.yaml` against the live CBM test
   instance, with `MN-Account.yaml` selected alongside
   `CR-Account.yaml` (and any other Account-extending YAMLs the
   user wants in scope). Expected: validation passes for both
   files; configure proceeds. The `industrySubsector empty
   options` error from the original failure remains, since this
   prompt does not address it. Doug will see one validation
   error instead of eight.

   If Doug runs Configure on `MN-Account.yaml` alone (without
   selecting `CR-Account.yaml`), the `accountType not found`
   errors will reappear — that is correct behavior, because the
   selected batch genuinely does not declare the discriminator.
   Document this in any user-facing release notes.

## 9. Commit

Single commit. Suggested message:

```
fix(validator): resolve field references across sibling YAMLs in batch

The validator that runs before Configure rejected every YAML that
referenced a field declared by a sibling YAML in the same
deployment batch. Live evidence: MN-Account.yaml's seven
visibleWhen/requiredWhen references to `accountType` (declared in
CR-Account.yaml) all surfaced as 'Field not found in entity
fields' validation errors.

Cause: validate_program built `field_names` only from the entity
under validation, ignoring the rest of the deployment batch. The
deploy engine itself processes batches correctly — by the time
MN-Account is configured, CR-Account has already declared
accountType — but validation runs file-by-file before any
deployment and rejected the second-and-later domain YAMLs.

Fix: introduce ProgramContext, a value object carrying the union
of field names per entity across a deployment batch. Add
validate_program_with_context as the new public entry point;
single-file validate_program preserves prior behavior via a
self-context fallback. The eight field_names construction sites
in config_loader.py now union the context's contribution. Configure
UI builds one shared context from all selected files, then validates
each against it.

Five new tests cover cross-file resolution, single-file fallback,
typo detection in both modes, and ProgramContext.from_programs.

Validator-only change; deploy engine behavior unchanged. The
companion `industrySubsector empty options` validation error is
addressed in a separate prompt.
```
