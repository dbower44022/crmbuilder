# Claude Code Prompt — Engine Pluggability Series, Prompt A

**Series:** engine pluggability architecture
**Prompt ID:** A
**Descriptor:** protocol and registry
**Filename:** `CLAUDE-CODE-PROMPT-engine-A-protocol-and-registry.md`
**Repository:** `crmbuilder`
**Related planning document:** `PRDs/product/crmbuilder-automation-PRD/engine-pluggability-planning.md` v1.0
**Last Updated:** 04-30-26 25:15
**Version:** 1.0

---

## Status

This is the first prompt in a multi-prompt series implementing engine pluggability for CRM Builder Automation. The full series is described in `engine-pluggability-planning.md` §5; the planning document is the design authority for this and all subsequent prompts in the series.

This prompt produces working, testable code that does not change application behavior. It introduces the engine abstraction layer (protocol and registry) without registering or using any engines yet. The application continues to function exactly as it does today — EspoCRM-only, with deployment code importing directly from `espo_impl/` — until Prompts C and D update the call sites and register the EspoCRM engine.

After Prompt A: a new module `automation/core/engine/` exists with the abstraction; everything else is unchanged.

---

## What this prompt accomplishes

Creates the engine abstraction layer. Specifically:

1. **`automation/core/engine/__init__.py`** — package init.
2. **`automation/core/engine/protocol.py`** — defines the `Engine` protocol and `EngineMetadata` dataclass. The protocol's eight methods are declared but no implementations exist yet.
3. **`automation/core/engine/registry.py`** — defines `EngineRegistry` with `register()`, `get()`, `is_registered()`, and `registered_platforms()` methods. The registry is a singleton accessible via a module-level function `get_registry()`.
4. **`tests/test_engine_protocol.py`** — tests verifying `EngineMetadata` dataclass validation and protocol contract behavior.
5. **`tests/test_engine_registry.py`** — tests for the registry: registration, lookup, unknown-platform handling, double-registration prevention, listing platforms.

---

## What this prompt does NOT do

- **No engine implementations.** Neither EspoCRM nor Attio is implemented in this prompt. The protocol and registry exist; no engine is registered.
- **No changes to existing code.** Nothing in `automation/ui/`, `espo_impl/`, or anywhere else changes. The new `automation/core/engine/` module is purely additive.
- **No database schema changes.** Schema migration to add `Instance.crm_platform` is Prompt B.
- **No documentation updates beyond the new module.** The L2 PRD will be updated in a later prompt once the abstraction is fully integrated.

---

## Constraints and conventions

Per memory and existing repository conventions:

- **Python 3.11+ syntax.** Use `|` for union types, `list[T]` over `List[T]`, etc.
- **Type hints on all public APIs.** Both arguments and return values.
- **Docstrings on public APIs.** Use `:param name:` / `:returns:` style consistent with existing modules (see `espo_impl/core/api_client.py` for examples).
- **Tests use pytest.** Existing tests in `tests/` use pytest conventions.
- **No external dependencies beyond what's already in the repo.** The protocol and registry should use only standard library plus already-imported packages (see `pyproject.toml` or `requirements*.txt`).
- **Testing strategy: 100% coverage of new modules.** The registry is small enough that full coverage is achievable. The protocol itself is a contract, so its tests verify the contract's shape.

---

## Detailed implementation

### 1. `automation/core/engine/__init__.py`

A package init that exports the public API. Keep it minimal:

```python
"""Engine abstraction layer for CRM platform pluggability.

This package defines the protocol that engine implementations
implement and the registry that the deployment code uses to
dispatch to the correct engine for a given platform.

Engine implementations live in their own packages outside this
module (e.g. `espo_impl`, `attio_impl`). Each implementation
registers itself with the registry at module-load time.
"""

from automation.core.engine.protocol import Engine, EngineMetadata
from automation.core.engine.registry import EngineRegistry, get_registry

__all__ = ["Engine", "EngineMetadata", "EngineRegistry", "get_registry"]
```

### 2. `automation/core/engine/protocol.py`

The protocol module defines:

- **`EngineMetadata` dataclass** with these fields:
  - `platform: str` — the canonical platform name (e.g., `"EspoCRM"`, `"Attio"`). Must match the value used in `Client.crm_platform`, `Instance.crm_platform`, and `DeploymentRun.crm_platform` CHECK constraints.
  - `display_name: str` — human-readable name shown in the UI (often equal to `platform` but may differ for branding).
  - `description: str` — one-sentence description for documentation and tooltips.
  - `supported_versions: list[str]` — list of supported platform versions; can be empty if version-checking is not applicable for this engine.
  - `default_url_pattern: str | None` — a hint for the URL format the user should provide (e.g., `"https://{instance}.example.com"`); can be `None` if no pattern hint is appropriate.
  - `documentation_url: str | None` — a URL to engine-specific documentation; can be `None`.

- **`Engine` protocol** as a `typing.Protocol` (runtime-checkable via `@runtime_checkable`) with these eight methods:

  ```python
  def engine_metadata(self) -> EngineMetadata:
      """Return metadata about this engine."""

  def auth_methods(self) -> list[str]:
      """Return the auth method identifiers this engine supports.

      Examples: ["api_key", "hmac", "basic"] for EspoCRM;
      ["bearer_token"] for Attio.
      """

  def supported_scenarios(self) -> list[str]:
      """Return the deployment scenarios this engine supports.

      Scenarios are from SCENARIOS in
      automation/core/deployment/wizard_logic.py:
      "self_hosted", "cloud_hosted", "bring_your_own".
      """

  def test_connection(
      self, profile: object
  ) -> tuple[bool, str]:
      """Verify the engine can reach and authenticate against the instance.

      :param profile: An engine-specific instance profile.
      :returns: (success, message) tuple.
      """

  def load_program(self, yaml_path: object) -> object:
      """Parse a YAML program file.

      :param yaml_path: Path to the YAML program file.
      :returns: An engine-specific representation of the program.
      """

  def apply_program(
      self,
      program: object,
      profile: object,
      options: object | None = None,
  ) -> object:
      """Apply a program file to an instance.

      :param program: Program returned by load_program.
      :param profile: Engine-specific instance profile.
      :param options: Engine-specific options (or None for defaults).
      :returns: An engine-specific run result.
      """

  def audit_program(
      self,
      profile: object,
      options: object | None = None,
  ) -> object:
      """Read the current state of an instance and produce an audit document.

      :param profile: Engine-specific instance profile.
      :param options: Engine-specific options (or None for defaults).
      :returns: An engine-specific audit result.
      """

  def compare_programs(
      self,
      source_profile: object,
      target_profile: object,
      options: object | None = None,
  ) -> object:
      """Compare two instances of the same engine.

      :param source_profile: Source instance profile.
      :param target_profile: Target instance profile.
      :param options: Engine-specific options (or None for defaults).
      :returns: An engine-specific comparison result.
      """
  ```

  **Note on argument types.** The protocol uses `object` for engine-specific types (profile, program, options, results) rather than introducing protocol-level generic types. This is deliberate: each engine's profile/program/options/result types are different (EspoCRM uses `InstanceProfile`; Attio will use a different shape). The protocol signature must be type-compatible with all engines, and `object` is the most permissive base type. Type-narrowing happens inside each engine's implementation.

  **An alternative considered and not chosen:** parameterizing the protocol with type variables (`Engine[ProfileT, ProgramT, ...]`). This produces stronger typing but tangles the engine abstraction with generic-type plumbing in every call site. The simpler `object` typing was preferred for the initial iteration; type tightening can come later.

- **Module-level docstring** explaining that `Engine` is a `typing.Protocol`, that engines are duck-typed (any class with the right methods is an engine), and that engine implementations live in their own packages.

### 3. `automation/core/engine/registry.py`

The registry module defines:

- **`EngineRegistry` class** with:
  - `_engines: dict[str, Engine]` — internal mapping from platform name to engine instance.
  - `register(self, engine: Engine) -> None` — register an engine. The platform name is taken from `engine.engine_metadata().platform`. Raises `ValueError` if the platform is already registered (prevents accidental double-registration).
  - `get(self, platform: str) -> Engine` — return the registered engine for a platform. Raises `KeyError` (with a helpful message including the list of registered platforms) if the platform is not registered.
  - `is_registered(self, platform: str) -> bool` — return whether a platform has an engine registered.
  - `registered_platforms(self) -> list[str]` — return a sorted list of registered platform names.
  - `unregister(self, platform: str) -> None` — remove an engine from the registry. Raises `KeyError` if not registered. Primarily for test cleanup; production code should not call this.

- **Module-level singleton:**
  - `_GLOBAL_REGISTRY = EngineRegistry()` — module-level singleton instance.
  - `get_registry() -> EngineRegistry` — return the singleton. This is the function that production code calls; it returns the same registry instance across the application.

- **Module-level docstring** explaining the singleton pattern, that engine implementations register themselves at module-load time (in their `__init__.py` or an explicit registration call), and that the deployment code uses `get_registry().get(platform)` to dispatch.

### 4. `tests/test_engine_protocol.py`

Tests for `EngineMetadata` and the `Engine` protocol:

- **`test_engine_metadata_required_fields`** — verify `EngineMetadata` requires `platform`, `display_name`, `description`, `supported_versions`. Verify `default_url_pattern` and `documentation_url` are optional (default `None`).
- **`test_engine_metadata_immutability`** — verify `EngineMetadata` is `frozen=True` (a dataclass with `frozen=True` raises `FrozenInstanceError` on attribute modification). This is a deliberate constraint: metadata should not be mutable after engine registration.
- **`test_engine_protocol_runtime_checkable`** — verify that a class implementing all eight protocol methods satisfies `isinstance(obj, Engine)` checks. Use a minimal stub class for this.
- **`test_engine_protocol_missing_method`** — verify that a class missing one or more protocol methods does NOT satisfy `isinstance(obj, Engine)`. Note: Python's `Protocol` runtime check is structural; this test confirms that behavior.
- **`test_engine_metadata_used_in_protocol`** — verify a stub engine's `engine_metadata()` returns an `EngineMetadata` instance.

### 5. `tests/test_engine_registry.py`

Tests for `EngineRegistry`:

- **`test_register_engine_succeeds`** — create a stub engine, call `registry.register(engine)`, verify `is_registered("StubPlatform")` returns `True`.
- **`test_register_engine_double_raises`** — registering the same platform twice raises `ValueError`.
- **`test_get_engine_returns_registered`** — after registration, `registry.get("StubPlatform")` returns the same engine instance.
- **`test_get_engine_unknown_raises_helpful_error`** — `registry.get("Unknown")` raises `KeyError` with a message that includes the list of registered platforms (verify this with a substring match).
- **`test_is_registered_unknown_returns_false`** — `is_registered("NotRegistered")` returns `False`.
- **`test_registered_platforms_sorted`** — register stub engines for two platforms in non-alphabetical order; verify `registered_platforms()` returns them sorted.
- **`test_unregister_removes_engine`** — register, then unregister, then verify `is_registered` returns `False`.
- **`test_unregister_unknown_raises`** — unregister an unregistered platform raises `KeyError`.
- **`test_get_registry_returns_singleton`** — verify `get_registry()` returns the same instance on multiple calls.
- **`test_global_registry_isolated_in_tests`** — use a fixture that creates a fresh registry per test (or clears the global registry before/after each test) so that registrations from one test don't leak into another.

The fixture for registry isolation can be implemented as either (a) a fixture that returns a fresh `EngineRegistry()` for tests that don't need the singleton, or (b) a fixture that monkey-patches the global registry to a fresh instance for the duration of the test. Either is acceptable; choose whichever produces cleaner test code.

### 6. Stub engine for tests

Both test files need a minimal stub engine for testing. Provide a small helper class in a shared test fixture or as a private helper at the top of each test file:

```python
class _StubEngine:
    """Minimal Engine implementation for protocol/registry tests."""

    def __init__(self, platform: str = "StubPlatform") -> None:
        self._platform = platform

    def engine_metadata(self) -> EngineMetadata:
        return EngineMetadata(
            platform=self._platform,
            display_name=self._platform,
            description="Stub engine for tests.",
            supported_versions=[],
            default_url_pattern=None,
            documentation_url=None,
        )

    def auth_methods(self) -> list[str]:
        return ["stub_auth"]

    def supported_scenarios(self) -> list[str]:
        return ["bring_your_own"]

    def test_connection(self, profile: object) -> tuple[bool, str]:
        return True, "stub connection ok"

    def load_program(self, yaml_path: object) -> object:
        return None

    def apply_program(
        self,
        program: object,
        profile: object,
        options: object | None = None,
    ) -> object:
        return None

    def audit_program(
        self,
        profile: object,
        options: object | None = None,
    ) -> object:
        return None

    def compare_programs(
        self,
        source_profile: object,
        target_profile: object,
        options: object | None = None,
    ) -> object:
        return None
```

This stub is a test helper only; it does not need to live in the production code. Place it in either a shared `tests/conftest.py` fixture or as a top-of-file helper in the test files that use it.

---

## Acceptance criteria

The prompt is complete when:

1. **All five new files exist** and have content matching the specification:
   - `automation/core/engine/__init__.py`
   - `automation/core/engine/protocol.py`
   - `automation/core/engine/registry.py`
   - `tests/test_engine_protocol.py`
   - `tests/test_engine_registry.py`
2. **All tests pass.** Run `pytest tests/test_engine_protocol.py tests/test_engine_registry.py -v` and verify all tests pass.
3. **Existing tests still pass.** Run the full test suite (`pytest tests/ -v` or whatever the standard test command is) and verify no existing tests broke. (None should — this prompt is purely additive — but the verification is essential.)
4. **No type errors.** If the project uses a type checker (mypy, pyright), run it and verify no new type errors. If no type checker is configured, skip this step.
5. **Linter passes.** Run whatever linter is standard (ruff, flake8, etc.) on the new files and verify no warnings.
6. **No imports of the new module from existing code.** `grep -rn "from automation.core.engine" automation/ espo_impl/` should return only the test files. The application's existing code does not yet use the abstraction.

If any acceptance criterion fails, the failure should be reported back with detail rather than worked around silently.

---

## Risks and mitigations

**Risk: protocol method signatures with `object` typing reduce type-checker effectiveness.** Mitigation accepted as a deliberate design choice — see protocol.py implementation note. Type tightening can come in a future iteration.

**Risk: the test fixture for registry isolation is non-trivial to get right.** Mitigation: keep the fixture simple (fresh `EngineRegistry()` per test for non-singleton tests; monkey-patch the global for singleton tests). Avoid clever fixture machinery; clarity beats elegance for the foundation.

**Risk: `typing.Protocol` runtime checking has subtle behavior.** Specifically, `@runtime_checkable` only checks that methods exist on the instance, not their signatures. A class with method `engine_metadata(self, extra)` would still pass the runtime check. Mitigation accepted: the runtime check is a sanity check, not a guarantee. Static type checkers (when run) catch signature mismatches; the runtime check catches the most common error (missing method).

**Risk: a future engine implementation may need methods not in this protocol.** Mitigation: when that happens, add the method to the protocol and require it in subsequent implementations. The protocol is not frozen forever; it's frozen for the duration of the prompt series. Major changes to the protocol after the series completes would be a separate refactoring effort.

---

## After this prompt

The next prompt is **Prompt B — Schema migration for `Instance.crm_platform` column.** It adds the engine type column to the `Instance` table, backfills existing rows with `'EspoCRM'`, and updates `Instance` row models. It does not depend on Prompt A's results conceptually but executes after Prompt A in the series.

After both Prompt A and Prompt B are complete, **Prompt C — EspoCRM engine adapter** wraps the existing `espo_impl/` modules in the `Engine` protocol and registers them. After Prompt C, the abstraction is real (one engine registered) but unused (call sites still import `espo_impl/` directly). **Prompt D — Refactor `automation/ui/deployment/` to use the registry** is what makes the abstraction load-bearing.

---

*End of prompt.*
