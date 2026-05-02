# Claude Code Prompt — Deployment Record Series, Prompt H

**Series:** deployment-record (productize the Deployment Record artifact)
**Prompt ID:** H
**Descriptor:** generator-output-cleanup
**Filename:** `CLAUDE-CODE-PROMPT-deployment-record-H-generator-output-cleanup.md`
**Repository:** `crmbuilder`
**Depends on:** Prompts A, B, C, E, F, G merged (this prompt closes content gaps observed during the post-G smoke test)
**Reference document:** `ClevelandBusinessMentoring/PRDs/deployment/CBM-Test-Instance-Deployment-Record.docx` v1.3 — the fidelity target the application-generated output should match
**Last Updated:** 05-02-26 16:30
**Version:** 1.0

---

## Status

A focused fix prompt addressing four content issues in the Python Deployment Record generator (`automation/core/deployment/record_generator.py`), discovered during the post-Prompt-G smoke-test execution against the live CBM Test instance. The smoke test validated the functional pipeline end-to-end (SSH → inspection → generation → file written to disk); these are content-quality gaps in the generated `.docx` itself, not pipeline failures.

The most serious issue is that the EspoCRM version is rendered as `"unknown"` in Section 6.1 — the headline fact about the application is missing, even though the version (9.3.4 for CBM Test) is reliably retrievable from the running container. The other three issues are more minor: the document title uses the Instance code rather than the human-readable client name, the "Public IPv4" row label is missing the "(SSH Host)" parenthetical from v1.3, and (possibly) the Last Updated date rendering may not match the standard `MM-DD-YY HH:MM` format.

After Prompt H: the application-generated Deployment Record's substantive content matches v1.3's content-quality bar. Future smoke tests against new deploys produce documentation indistinguishable in content from a hand-produced reference.

---

## What this prompt accomplishes

1. **Fix `_read_espocrm_version()`** in `record_generator.py` to use a robust multi-strategy retrieval that works against the standard EspoCRM Docker installation. The existing implementation greps `data/config.php` for a `'version' => '...'` pattern, but this file does not contain the version in the production EspoCRM Docker image (it's the user-config file, not the runtime-version file). Replace with strategy-based retrieval that tries the most reliable PHP-eval-based lookup first and falls back to alternatives.

2. **Fix `client_name` resolution in `inspect_server_for_record_values()`**. The existing code reads `getattr(instance, "name", "")` from the `Instance` row, but `Instance.name` is the technical instance name (e.g., "CBMTEST"), not the human-readable client name (e.g., "Cleveland Business Mentors"). Extend the function signature to accept a `client_name: str` parameter and have callers (the deploy worker in `deploy_worker.py` and the regeneration worker in `regenerate_record_worker.py`) pass it in by querying the master database.

3. **Update the "Public IPv4" row labels in Section 2 and Section 3.1** to read "Public IPv4 (SSH Host)", matching v1.3's relabel that explicitly connects the captured value to the wizard's SSH Host input field.

4. **Verify and (if needed) fix the `document_last_updated` rendering** to match the format `MM-DD-YY HH:MM` (e.g., `05-02-26 20:14`) — that's a single space between the date and the time. The current format string in `record_generator.py` line 327 reads `"%m-%d-%y %H:%M"` which Python should render correctly. If a manual smoke-test review of the generated file shows a hyphen between date and time, investigate where the substitution happens. If the format renders correctly already, this becomes a no-op verification.

---

## What this prompt does NOT do

- **No changes to wizard pages, dialogs, schema, or migrations.** Prompts A–G's surfaces are unchanged.
- **No changes to the JS generator** at `ClevelandBusinessMentoring/PRDs/deployment/generate-deployment-record.js`. Out of scope.
- **No new fields in `DeploymentRecordValues`.** All fixes work with existing fields.
- **No changes to the procedure document** (`cbm-test-instance-backfill-procedure.md`).

---

## Constraints and conventions

- **Verify the EspoCRM version retrieval against the live system before declaring victory.** Claude Code can SSH to the live CBM Test Droplet using the key at `~/Dropbox/Projects/ClevelandBusinessMentors/ssh` to test which retrieval strategy actually returns 9.3.4. The expected value is 9.3.4 — if the strategy returns anything other than that exact string, iterate.
- **The version retrieval must be idempotent and side-effect-free.** Read-only, no writes to anything on the server.
- **Strategy fallback order matters.** Try the most reliable / least invasive strategy first; fall through on empty / error.
- **Match existing error / log conventions in `record_generator.py`.** Use the same `_run` and `log` patterns already established in the inspection helpers.
- **Test additions must use the existing fixture file** (`tests/fixtures/deployment_record_values_cbmtest.json`). Update the fixture if needed to reflect the v1.3 `(SSH Host)` label change, but do not introduce a second fixture file.
- **Python 3.11+, type hints, docstrings, pytest.** Same conventions as the rest of the codebase.

---

## Detailed implementation

### Issue 1 — `_read_espocrm_version()` returns `"unknown"`

Current implementation (around line 429 of `record_generator.py`):

```python
def _read_espocrm_version(
    ssh: paramiko.SSHClient,
    log: Callable[[str, str], None],
) -> str | None:
    """Read EspoCRM's version from inside the running container."""
    cmd = (
        "docker compose -f /var/www/espocrm/docker-compose.yml exec -T "
        "espocrm grep -oE \"'version'\\s*=>\\s*'[^']+'\" data/config.php "
        "| head -1 | sed -E \"s/.*'([^']+)'$/\\1/\""
    )
    out = _run(ssh, cmd, log).strip()
    if not out:
        return None
    last = out.splitlines()[-1].strip()
    match = re.search(r"(\d+\.\d+\.\d+)", last)
    return match.group(1) if match else None
```

The bug is that `data/config.php` does not contain a `'version'` key in the standard EspoCRM Docker image. The runtime version lives in `data/config-internal.php` (an EspoCRM-managed file that holds runtime state, distinct from the user-edited `config.php`).

Replacement strategy — try multiple paths in order, falling through on empty result:

```python
def _read_espocrm_version(
    ssh: paramiko.SSHClient,
    log: Callable[[str, str], None],
) -> str | None:
    """Read EspoCRM's version from inside the running container.

    Tries multiple retrieval strategies in order of reliability,
    falling through on empty or error result. Returns None if all
    strategies fail; the caller renders the field as "unknown".

    Strategies, in order:
      1. PHP eval against data/config-internal.php (the EspoCRM
         runtime config; most reliable in production Docker
         installations).
      2. PHP eval against data/config.php (legacy fallback).
      3. Application class constant (if defined in this version).
    """
    strategies = [
        # data/config-internal.php is the runtime config managed by
        # the application; contains the active 'version' key.
        (
            "config-internal",
            'docker exec espocrm php -r '
            '\'echo (require "/var/www/html/data/config-internal.php")'
            '["version"] ?? "";\'',
        ),
        # data/config.php is the user-editable config; the version
        # may also appear here on some installations.
        (
            "config",
            'docker exec espocrm php -r '
            '\'echo (require "/var/www/html/data/config.php")'
            '["version"] ?? "";\'',
        ),
        # Application::VERSION class constant on newer EspoCRM versions.
        (
            "class-constant",
            'docker exec espocrm php -r '
            '\'require "/var/www/html/bootstrap.php"; '
            'echo defined("Espo\\\\Core\\\\Application::VERSION") '
            '? Espo\\\\Core\\\\Application::VERSION : "";\'',
        ),
    ]

    for strategy_name, cmd in strategies:
        try:
            out = _run(ssh, cmd, log).strip()
        except Exception as exc:
            log(
                f"Version retrieval strategy '{strategy_name}' "
                f"failed: {exc}",
                "warning",
            )
            continue
        if not out:
            log(
                f"Version retrieval strategy '{strategy_name}' "
                f"returned empty.",
                "info",
            )
            continue
        last_line = out.splitlines()[-1].strip()
        match = re.search(r"(\d+\.\d+\.\d+)", last_line)
        if match:
            log(
                f"EspoCRM version {match.group(1)} retrieved via "
                f"strategy '{strategy_name}'.",
                "info",
            )
            return match.group(1)
        log(
            f"Version retrieval strategy '{strategy_name}' returned "
            f"output but no version pattern: {last_line[:80]}",
            "warning",
        )

    log(
        "All EspoCRM version retrieval strategies failed; "
        "rendering 'unknown'.",
        "warning",
    )
    return None
```

The exact PHP-eval syntax may need adjustment based on actual shell-quoting behavior. Verify by running each strategy manually against the live CBM Test Droplet during implementation:

```bash
ssh -i ~/Dropbox/Projects/ClevelandBusinessMentors/ssh \
    root@crm-test.clevelandbusinessmentors.org \
    'docker exec espocrm php -r '\''echo (require "/var/www/html/data/config-internal.php")["version"] ?? "";'\'''
```

The expected output is `9.3.4` (with no surrounding whitespace or quotes). If a strategy returns the version, that strategy works; use it. If shell-quoting issues cause empty output despite the file containing the version, adjust quote handling or use a different invocation pattern (e.g., heredoc to a temp script then exec). Iterate against the live system until at least one strategy reliably returns 9.3.4.

### Issue 2 — `client_name` resolution

Current implementation (line 329 of `record_generator.py`):

```python
client_name=getattr(instance, "name", ""),
```

`instance.name` is the Instance row's `name` field (e.g., "CBMTEST"), not the client's name. The actual client name lives in the master database's `Client` table.

Fix — extend the function signature to accept the client name as an explicit parameter:

```python
def inspect_server_for_record_values(
    ssh: paramiko.SSHClient,
    instance: InstanceRow,
    deploy_config: InstanceDeployConfig,
    administrator_inputs: AdministratorInputs,
    client_name: str,                     # NEW required parameter
) -> DeploymentRecordValues:
    ...
```

In the function body, use the new `client_name` parameter directly:

```python
client_name=client_name,
```

Then update the two callers:

- **`deploy_worker.py`** — wherever `inspect_server_for_record_values` is called inside `SelfHostedWorker._run_phases` after a successful deploy. The deploy worker has access to a master DB connection; query the `Client` table for the active client's `name` and pass it through.
- **`regenerate_record_worker.py`** — same pattern. The worker has access to the per-client database; resolve the client name via the master DB connection that's available to the dialog.

The exact mechanism for resolving the client name from a master DB depends on existing patterns in the codebase. Look at how `wizard_dialog.py` displays the active client's name and reuse that pattern. If the master database has a `Client` table with `(id, name, ...)` columns, a simple SELECT works. If the master connection is not directly available to the worker, propagate it through (preferred: pass the client_name string through the worker's constructor so the worker doesn't need to query anything itself).

### Issue 3 — "Public IPv4" → "Public IPv4 (SSH Host)"

Two edits needed in `record_generator.py`. Find the literal string `"Public IPv4"` in the table-row construction code.

Search for the two occurrences:

```bash
grep -n '"Public IPv4"' automation/core/deployment/record_generator.py
```

Each occurrence appears in a row tuple like `("Public IPv4", values.public_ipv4)` or similar. Replace both with `"Public IPv4 (SSH Host)"`. The fixture file (`tests/fixtures/deployment_record_values_cbmtest.json`) does not need updating because the label is hardcoded in the generator, not part of the values bag.

### Issue 4 — `document_last_updated` rendering

Verify the smoke-test report (`05-02-26-20:14` with hyphen instead of space) reflects what's actually in the document. The format string at `record_generator.py:327` reads `"%m-%d-%y %H:%M"`, which Python's strftime renders with a literal space.

Steps:

1. Generate a fresh document with the existing code (run the CLI: `uv run python -m automation.core.deployment.record_generator --values tests/fixtures/deployment_record_values_cbmtest.json --output /tmp/test.docx`).
2. Open the file and read the Last Updated value.
3. If it shows space (e.g., `05-02-26 20:14`), the report from the smoke test was a transcription artifact — no fix needed; document the verification in the prompt's commit message and move on.
4. If it shows a hyphen (e.g., `05-02-26-20:14`), trace the substitution. Possible culprits: a typography auto-correct in `python-docx` (unlikely), an explicit replace somewhere in the generator (search for `.replace`), or a non-breaking space character in the format string. Fix at the source.

### Tests

Update `tests/test_record_generator.py`:

- **`test_public_ipv4_label_includes_ssh_host`** — generate a document with the existing fixture, open it with `python-docx`, search the table contents for the string "Public IPv4 (SSH Host)" and assert it appears at least twice (Section 2 and Section 3.1).
- **`test_espocrm_version_retrieval_strategies`** — unit test the multi-strategy `_read_espocrm_version` helper with patched SSH responses. Cases: first strategy returns `9.3.4` (expected return `"9.3.4"`); first returns empty, second returns `9.3.4` (expected return `"9.3.4"`); all return empty (expected return `None`).
- **`test_inspect_server_uses_provided_client_name`** — call `inspect_server_for_record_values` with `client_name="Cleveland Business Mentors"` and assert the returned `DeploymentRecordValues.client_name` equals that string regardless of what the `Instance.name` field is set to.
- **Update existing tests** that call `inspect_server_for_record_values` to pass the new `client_name` parameter. If any test mocks the function, update those mocks accordingly.

Also update fixtures and tests in `tests/test_deploy_worker.py` and `tests/test_regenerate_record_worker.py` if they construct `DeploymentRecordValues` or call `inspect_server_for_record_values` — both will need the new `client_name` argument supplied.

---

## Acceptance criteria

- Running the smoke-test command (`uv run python -m automation.core.deployment.record_generator --values tests/fixtures/deployment_record_values_cbmtest.json --output /tmp/test.docx`) produces a document with EspoCRM version `9.3.4` rendered in Section 6.1 (not `unknown`).
- The same document's title block shows `Cleveland Business Mentors` (per the fixture's client_name value), not `CBMTEST`.
- The same document contains `Public IPv4 (SSH Host)` as the row label in both Section 2 and Section 3.1.
- The same document's Last Updated metadata field renders with the format `MM-DD-YY HH:MM` (single space between date and time).
- All existing tests in `tests/test_record_generator.py`, `tests/test_deploy_worker.py`, `tests/test_regenerate_record_worker.py`, and `tests/test_regenerate_record_dialog.py` continue to pass.
- New tests added by this prompt pass.
- `uv run ruff check` is clean on touched files.
- No changes to files outside `automation/core/deployment/record_generator.py`, `automation/ui/deployment/deploy_wizard/deploy_worker.py`, `automation/ui/deployment/regenerate_record_worker.py`, the corresponding test files, and (if needed) the JSON fixture.

---

## Notes for the implementer

- The EspoCRM version retrieval is the load-bearing fix in this prompt. If the strategy approach doesn't reliably return `9.3.4` against the live CBM Test Droplet during testing, treat that as a blocker: iterate until it does, even if it requires a fundamentally different approach (e.g., calling the EspoCRM API endpoint, or reading from a class constant). A document that says `unknown` for the version is materially incomplete; do not ship the fix without confirming the version renders correctly.
- The `client_name` fix requires propagating a new value through two callers. Be careful not to break the test fixtures, which do supply the client_name in JSON form.
- The Last Updated investigation may turn out to be a no-op (the format string is correct; the smoke-test report may have been a transcription artifact). Don't fabricate a fix for a problem that doesn't exist. Verify first; only fix if the issue is reproducible.
- After this prompt, the application-generated Deployment Record should be content-equivalent to the v1.3 hand-produced reference in all substantive ways. Cosmetic divergences (slight differences in paragraph spacing, table-cell padding) from `python-docx` vs the JS `docx` library are acceptable and out of scope.
