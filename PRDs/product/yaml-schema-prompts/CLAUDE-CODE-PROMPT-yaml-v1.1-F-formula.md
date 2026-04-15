# CLAUDE-CODE-PROMPT — yaml-v1.1-F — Field-Level `formula:` Block

**Repo:** `crmbuilder`
**Series:** `yaml-v1.1` (eight-prompt sequence implementing
`PRDs/product/app-yaml-schema.md` v1.1)
**Last Updated:** 04-15-26 04:35
**Spec:** `PRDs/product/app-yaml-schema.md` v1.1 — Section 6.1.3
(`formula:` — aggregate, arithmetic, concat); Section 10
"Field-level" validation rules for `formula:`.
**Foundation:** Prompt A established `condition_expression.py`
(reused by aggregate `where:` clauses) and `relative_date.py`
(reused by `where:` relative-date values). Prompt A stashed
`formula_raw` on `FieldDefinition`.

## Position in the Series

Implements gap-analysis Category 8 (Calculated Field Formulas).
This is the largest single prompt in the series because it
introduces three distinct formula types, an arithmetic mini-parser,
multi-hop join validation, and aggregate `where:` clause
integration with Prompt A's condition-expression module.

## Scope

In scope:

1. Parse `formula_raw` into a typed `Formula` model (with
   subtype-specific dataclasses or a tagged-union approach) on
   each `FieldDefinition` that carries a formula.
2. Three mutually-exclusive formula types per spec Section 6.1.3:
   - **`aggregate`** — seven functions (`count`, `sum`, `avg`,
     `min`, `max`, `first`, `last`), `relatedEntity`, `via`,
     optional `join:` for multi-hop, optional `where:` (parsed
     via `parse_condition`).
   - **`arithmetic`** — `expression:` string parsed by a small
     recursive-descent parser into an AST. Tokens: field
     references, integer/float literals, `+`, `-`, `*`, `/`,
     parentheses.
   - **`concat`** — ordered list of `parts:`, each one of
     `{ literal: "..." }`, `{ field: <name> }`, or
     `{ lookup: { via: <rel>, field: <name> } }`.
3. Full validation per spec Section 10 "Field-level" formula
   rules:
   - `formula:` requires `readOnly: true` on the field.
   - Exactly one of the three types.
   - Aggregate: function-specific required-clause checks (see
     spec Section 6.1.3 aggregate functions table); `where:`
     field references validated via `validate_condition` against
     the **related** entity's fields; multi-hop `join:` entries
     validated hop-by-hop (`from`, `link`, `to` must be valid).
   - Arithmetic: expression must parse; every field reference
     must exist on the same entity.
   - Concat: every `field:` reference on the same entity; every
     `lookup.via:` must name a valid relationship from this
     entity; every `lookup.field:` must exist on the related
     entity reached via that relationship.
4. New module(s) for formula parsing. Recommended split:
   - `espo_impl/core/formula_parser.py` — the arithmetic
     recursive-descent parser (tokenizer + parser + AST nodes).
   - Formula-type parsing (aggregate, concat) can live in the
     same module or in `config_loader.py` helpers — implementer's
     call based on size.
5. Translation of parsed formulas into the target CRM's formula
   syntax during deploy. Extend `field_manager.py` to include
   the formula payload in the field's API call. Each CRM
   expresses calculated fields differently; the deploy manager
   translates the structured YAML into the target's syntax.
6. Drift detection: compare the parsed formula against the CRM's
   current calculated-field configuration.
7. Tests covering all three formula types, the arithmetic parser,
   multi-hop join validation, aggregate `where:` integration,
   and deploy translation.

Out of scope:

- Formula functions beyond the seven aggregate functions listed
  in spec Section 6.1.3 (`min`/`max`/`abs`/`round`/`coalesce`
  as arithmetic-expression functions) — deferred to v1.2.
- `format:` clauses on concat parts — deferred to v1.2 per spec
  Section 6.1.3 "Numeric and date conversion".
- Dotted-path `via:` strings for multi-hop traversals — spec
  explicitly requires `join:` lists in v1.1.
- Any UI changes — none planned in v1.1.

## Spec Authority

This prompt implements `app-yaml-schema.md` v1.1. Where this
prompt and the spec disagree, the spec wins. In particular:

- The three formula types and their clauses are defined in spec
  Section 6.1.3.
- The seven aggregate functions and their required clauses are
  defined in the "Aggregate functions" and "Aggregate clauses"
  tables.
- Arithmetic expression syntax (field refs, literals, four
  operators, parens) is defined in Section 6.1.3 "Expression
  syntax (v1.1)".
- Concat part types are defined in the "Part types" table.
- Multi-hop `join:` format is defined in "Multi-hop traversal".
- All validation rules are in spec Section 10 "Field-level" and
  Section 6.1.3 "Validation".

## Cross-Cutting Concerns

- **Pure-logic discipline.** All new logic lives in
  `espo_impl/core/` with no GUI dependencies. The arithmetic
  parser is a small self-contained recursive-descent
  implementation — no external parsing libraries.
- **Validator integration.** Formula validation is added to
  `config_loader.py`'s `_validate_field` path, so failures are
  reported alongside existing field errors.
- **Drift detection.** `field_manager.py`'s CHECK→ACT loop is
  extended to include formula payloads.
- **Field reference validation.** Aggregate `where:` clauses
  delegate to `validate_condition` from Prompt A with
  `related_entity_field_names` set to the target related entity's
  fields. Arithmetic expressions and concat `field:` references
  are validated against the same entity's fields. Concat
  `lookup:` references require relationship validation (the
  `via:` must name a known relationship, and `field:` must exist
  on the related entity).
- **Backward compatibility.** v1.0 YAML files have no `formula:`
  blocks; their behavior is unchanged.

## Arithmetic Parser Design Guidance

The arithmetic parser is the only nontrivial parser in the series.
Recommended approach: a small recursive-descent parser operating
on a tokenized stream.

**Tokenizer:** split the expression string into tokens — field
names (runs of `[a-zA-Z_][a-zA-Z0-9_]*`), numeric literals
(integer or float), operators (`+`, `-`, `*`, `/`), and
parentheses (`(`, `)`). Whitespace is a separator, not a token.

**Grammar (for reference — not prescriptive):**

```
expr     → term (('+' | '-') term)*
term     → factor (('*' | '/') factor)*
factor   → '(' expr ')' | NUMBER | FIELD_REF
```

**AST nodes:** at minimum, `NumberLiteral`, `FieldRef`,
`BinaryOp(left, op, right)`. The AST is walked for field-
reference extraction (validation) and for rendering into the
target CRM's formula syntax (deploy).

The parser should produce clear error messages including the
position in the expression string where parsing failed.

## Relationship Validation for Aggregates and Concat Lookups

Both aggregate formulas (`via:`, `join:`) and concat `lookup:`
parts reference relationships. Validation requires access to the
program's `relationships` list (on `ProgramFile`) to confirm that
a named `via:` or `link:` exists and connects the expected
entities.

For multi-hop aggregates, each `join:` entry's `from`, `link`, and
`to` must be validated independently:
- `from` must be a known entity in the program.
- `link` must be a relationship link connecting `from` to `to`.
- The chain must be contiguous (each entry's `from` matches the
  prior entry's `to`, or the owning entity for the first hop).

The implementer should determine whether this validation happens
inside `config_loader.py` (which has access to both entities and
relationships) or in a dedicated helper. Either way, the
relationships list must be available at validation time.

## Files to Create

1. `espo_impl/core/formula_parser.py` — arithmetic tokenizer,
   recursive-descent parser, and AST nodes. Optionally also
   aggregate and concat parsing helpers if they grow large
   enough to warrant separation from config_loader.
2. `tests/test_formula.py` — all three formula types, arithmetic
   parser, validation, deploy translation.

## Files to Modify

1. `espo_impl/core/models.py` — add formula-related dataclasses:
   a `Formula` base or tagged-union type with subtype-specific
   fields for aggregate, arithmetic, and concat. Arithmetic AST
   node classes may live in `formula_parser.py` or `models.py` —
   implementer's call. Add a typed field on `FieldDefinition`:
   - `formula: Formula | None = None`

   The existing `formula_raw` field stays populated.

2. `espo_impl/core/config_loader.py` — parse `formula_raw` into
   the typed field during `load_program`. Add formula validation
   to `_validate_field` per spec Section 10 and Section 6.1.3
   "Validation".

3. `espo_impl/core/field_manager.py` — extend the CHECK→ACT loop
   to include the formula payload in the field's API call. Use
   the parsed formula AST to render the target CRM's formula
   syntax.

## Test Coverage Areas

For `tests/test_formula.py`:

**Aggregate formulas:**
- Each of the seven functions parses correctly with its required
  clauses.
- `count` must not specify `field:`; `sum`/`avg`/`min`/`max`
  must specify `field:`; `first`/`last` require both `pickField:`
  and `orderBy:`.
- `where:` clause parsed via `parse_condition`; field references
  validated against the related entity.
- Multi-hop `join:` validates hop-by-hop; invalid `from`/`link`/
  `to` produce clear errors.
- `via:` references validated against relationships.
- Missing `relatedEntity` or `via` produce errors.

**Arithmetic formulas:**
- Simple expressions: `"a + b"`, `"a - b"`, `"a * b"`, `"a / b"`.
- Precedence: `"a + b * c"` parses as `a + (b * c)`.
- Parentheses: `"(a + b) * c"` groups correctly.
- Numeric literals: integers and floats.
- Mixed: `"maximumClientCapacity - currentActiveClients"` (the
  spec example).
- Error cases: unknown field reference; unbalanced parentheses;
  empty expression; trailing operator; consecutive operators.

**Concat formulas:**
- All three part types: `literal`, `field`, `lookup`.
- `field:` reference validated against same entity.
- `lookup.via:` validated against relationships; `lookup.field:`
  validated against the related entity.
- Empty `parts:` list is an error.

**Cross-type validation:**
- `formula:` without `readOnly: true` produces an error.
- `formula.type` not one of the three → error.
- More than one type key → error (if applicable to the
  dataclass design).

**Deploy translation:**
- Each formula type renders to the expected CRM API payload.

No specific test counts are required; the coverage areas above
are the bar.

## Acceptance Criteria

1. New files exist at the paths listed under "Files to Create".
2. `FieldDefinition` carries a typed `formula: Formula | None`
   field in addition to the existing raw field.
3. The arithmetic parser handles the spec Section 6.1.3
   expression syntax (field refs, literals, four operators,
   parens) with clear error messages.
4. `ConfigLoader.load_program` parses all three formula types and
   populates the typed field; `validate_program` enforces every
   Section 10 and Section 6.1.3 "Validation" rule.
5. Multi-hop `join:` validation works hop-by-hop with clear error
   messages.
6. Aggregate `where:` clauses delegate to Prompt A's
   `validate_condition` with `related_entity_field_names`.
7. `field_manager.py` includes formula payloads in CHECK→ACT.
8. All existing tests continue to pass.
9. New tests cover the coverage areas above.
10. `uv run ruff check espo_impl/ tests/` passes clean.
11. `uv run pytest tests/ -v` passes.
12. Commit and push to `main` with a clear message referencing
    this prompt and the spec.

## Reporting Back

When finished, report:

- New file paths and line counts
- New tests added (counts and brief coverage summary)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompts G–H, especially
  whether the arithmetic parser's AST is reusable for
  `setField.value:` expressions in Prompt G
