# Claude Code Prompt — Error Handling Series, Prompt A

**Series:** error-handling (defensive error handling across the run pipeline)
**Prompt ID:** A
**Descriptor:** api-client-and-managers
**Filename:** `CLAUDE-CODE-PROMPT-error-handling-A-api-client-and-managers.md`
**Repository:** `crmbuilder`
**Depends on:** Nothing — this is the first prompt in a new series.
**Last Updated:** 05-02-26 14:30
**Version:** 1.0

---

## Status

A live FU-Contribution Configure run against the CBM Test instance failed mid-pipeline at the Saved Views step with a single bare line of output:

```
[WRITE] Contribution savedViews metadata ...
Error: Expecting value: line 1 column 1 (char 0)
```

The run aborted before reaching `=== FIELD OPERATIONS ===`. None of the 18 fields on the new `CContribution` entity were created, and a subsequent Verify pass returned HTTP 500 on every field (because the fields don't exist and the EspoCRM Metadata endpoint returns 500 — not 404 — when asked for a missing field on a custom entity).

The bare `Error: Expecting value: line 1 column 1 (char 0)` is a `json.JSONDecodeError` from `requests.Response.json()` raised inside `EspoAdminClient._request()`:

```python
# espo_impl/core/api_client.py, line 96
body = resp.json() if resp.content else None
```

Only `requests.exceptions.ConnectionError` and `requests.exceptions.Timeout` are caught. Any other exception — `JSONDecodeError`, `SSLError`, `ChunkedEncodingError`, etc. — propagates up through every manager that called `_request`, escapes the `Manager`-specific exception types that `RunWorker` catches, hits the catch-all `except Exception` in `RunWorker.run()`, and is emitted via `finished_error.emit(str(exc))`. The user sees a one-line Python error message and no diagnostic detail about what HTTP status was returned, what URL was called, or what the server actually said in the response body.

This is brittle and obstructive. EspoCRM is known to return non-JSON bodies on certain error paths (HTML 500 pages, empty 502/503 responses behind reverse proxies, plain-text auth errors from misconfigured nginx). Every one of these will currently kill the run with no diagnostic.

After Prompt A: `_request()` catches all reasonable response-parsing failures, attaches the raw response text to a sentinel body dict so callers can surface it in error messages, and never propagates a parse exception. Every manager in `espo_impl/core/` is audited and updated to surface the raw text when present in error logging.

After Prompt B (separate prompt): the worker layer is hardened with per-step exception handling so a failure in one step doesn't kill the entire run.

---

## What this prompt accomplishes

1. **Harden `EspoAdminClient._request()`** in `espo_impl/core/api_client.py`:
   - Catch `(json.JSONDecodeError, ValueError)` around the `resp.json()` call.
   - On parse failure, decode the raw response bytes as UTF-8 (with `errors="replace"`), truncate to a configurable length (default 2000 chars), and return a sentinel body dict of the form `{"_parse_failed": True, "_raw_text": "<truncated text>", "_status_code": <status>}`.
   - Catch `requests.exceptions.RequestException` as a broad fallback (covers `SSLError`, `ChunkedEncodingError`, `TooManyRedirects`, etc.) — return `(-1, {"_request_failed": True, "_error": str(exc), "_exception_type": type(exc).__name__})`.
   - Log a `logger.warning(...)` for parse failures and `logger.error(...)` for request failures, including method, URL, status code, and raw text snippet.
   - Preserve the existing `(status_code, body)` return shape — body is still `dict | None`, callers that just check status codes are unaffected.

2. **Add a helper `_format_error_detail(body)`** as a top-level function in `api_client.py` (not a method) that takes a body dict and returns a human-readable one-line error description:
   - If `body is None`: returns `"(no response body)"`.
   - If `body.get("_parse_failed")`: returns `"non-JSON response: {first 200 chars of _raw_text}"`.
   - If `body.get("_request_failed")`: returns `"request failed: {_exception_type}: {_error}"`.
   - If `body.get("messageTranslation")`: returns the message (EspoCRM's localized error key).
   - If `body.get("message")`: returns the message.
   - Otherwise: returns `repr(body)` truncated to 200 chars.

3. **Audit every manager in `espo_impl/core/`** for places that:
   - Emit error output via `output_fn` after a failed `_request`-derived call. Replace any pattern that does `body.get("message", "")` followed by `body or "..."` with a single call to `_format_error_detail(body)` and emit that. The result is consistent error formatting and the raw-text fallback gets surfaced automatically.
   - Specific files to audit and update:
     - `entity_manager.py` (lines around 184: `body.get("message", "")` after entity create failure)
     - `entity_settings_manager.py`
     - `field_manager.py` (`_handle_act_result` lines 519–525)
     - `relationship_manager.py`
     - `saved_view_manager.py`
     - `workflow_manager.py`
     - `layout_manager.py`
     - `duplicate_check_manager.py`
     - `email_template_manager.py`
     - `tooltip_manager.py`
   - Each manager: search for `body.get("message"`, `f"          {msg or body}"`, and similar patterns. Replace with `_format_error_detail(body)`.

4. **Update `automation/core/deployment/connectivity.py`** (line 104, the `about_resp.json()` call): the existing `except Exception: pass` is acceptable because the function tolerates a missing version. Add a `logger.warning` inside the except so we at least know the parse failed. No behavioral change.

5. **Audit search.** Run `grep -rn "\.json()" espo_impl/ automation/` and confirm only the two known sites exist (`api_client.py:96`, `connectivity.py:104`). If any new sites appear, wrap them in the same parse-failure pattern and log a warning. Document the audit result in the prompt's commit message.

6. **Tests**:
   - In `tests/core/test_api_client.py` (create file if it doesn't exist): unit tests using `unittest.mock.patch` on `requests.Session.request`:
     - Test: `_request` returns `(500, {"_parse_failed": True, "_raw_text": "<html>...", "_status_code": 500})` when server returns non-JSON 500 page.
     - Test: `_request` returns `(-1, {"_request_failed": True, ...})` when `requests.exceptions.SSLError` is raised.
     - Test: `_request` returns `(200, {"key": "value"})` for normal JSON responses (regression test).
     - Test: `_request` returns `(204, None)` when `resp.content` is empty (regression test for the existing `if resp.content` guard).
     - Test: `_format_error_detail` returns expected strings for all five branches (None, parse_failed, request_failed, message, fallback).
   - In `tests/core/test_field_manager.py`, `tests/core/test_saved_view_manager.py`, `tests/core/test_entity_manager.py`: add at least one test per manager that asserts the manager emits a useful error line (containing the raw text snippet) when given a `_parse_failed` body. Mock the API client to return the sentinel body.

7. **No changes to the YAML schema, no changes to the `_run_full` orchestration**, no changes to the worker thread. Those are scope of Prompt B.

---

## What this prompt does NOT do

- **Does not fix the root cause** of the FU-Contribution saved-view write failure. After Prompt A, the next Configure run on FU-Contribution will still fail at the same step — but it will fail with a useful error line showing the actual HTTP status and the raw response text from EspoCRM. That diagnostic is the point of this prompt; the actual saved-view payload fix is a follow-up that depends on what the diagnostic reveals.
- **Does not change the worker's run-abort behavior.** A manager that raises a `*ManagerError` will still abort the run. A manager that catches a `_parse_failed` body and emits an `[ERROR]` line but returns normally will still allow the run to continue (this is the existing field_manager behavior — it processes all fields even if some fail). Worker-level resilience for manager-level non-Manager exceptions is Prompt B's scope.
- **Does not refactor `RunWorker.run()`'s catch-all `except Exception`.** That stays as-is; Prompt B replaces it.
- **Does not add structured logging to a file.** Existing `logging` calls write to stderr/wherever the caller has logging configured. Don't introduce new log handlers.
- **Does not change the public API of any `*Manager` class.** All edits are internal: error message formatting only.
- **Does not modify `EspoAdminClient`'s public methods** (`get_field`, `create_field`, etc.). Only `_request` is hardened; the public methods inherit the safety because they all delegate to `_request`.

---

## Constraints and conventions

- **Backward compatibility of `_request` return shape is mandatory.** `tuple[int, dict | None]` stays. The sentinel dicts (`_parse_failed`, `_request_failed`) ARE dicts, so `body is None` checks in callers won't accidentally take the "no body" branch when we have diagnostic info. Callers that look up specific keys (`body.get("message")`) get None for those keys when the body is a sentinel — that's fine, `_format_error_detail` handles the fallback.
- **`_format_error_detail` is a module-level function, not a method.** Make it importable: `from espo_impl.core.api_client import _format_error_detail`. (Note the leading underscore — it's package-internal.) Each manager that needs it imports it.
- **Truncation lengths**: 2000 chars for `_raw_text`, 200 chars for the format-detail snippet. Make these module-level constants `_RAW_TEXT_TRUNCATION = 2000` and `_DETAIL_TRUNCATION = 200` so they're tunable.
- **UTF-8 decode with `errors="replace"`**: never let a decode error escape. The point of this prompt is that nothing escapes.
- **Logger names**: use `logger = logging.getLogger(__name__)` at the top of each modified file (most already have this). Don't introduce a new logger hierarchy.
- **Python 3.11+, type hints, docstrings, pytest** — same conventions as the rest of the codebase.
- **No changes to PRD documents.** This prompt is purely code + tests.

---

## Detailed implementation

### Step 1 — `api_client.py` `_request()`

Replace the current `_request` implementation with this approximate shape:

```python
import json

_RAW_TEXT_TRUNCATION = 2000
_DETAIL_TRUNCATION = 200


def _format_error_detail(body: dict[str, Any] | None) -> str:
    """Format a body dict (possibly a sentinel) as a human-readable error detail.

    :param body: The body returned by ``_request``.
    :returns: A one-line error description suitable for end-user output.
    """
    if body is None:
        return "(no response body)"
    if body.get("_request_failed"):
        return (
            f"request failed: "
            f"{body.get('_exception_type', 'Exception')}: "
            f"{body.get('_error', '')}"
        )
    if body.get("_parse_failed"):
        snippet = (body.get("_raw_text") or "")[:_DETAIL_TRUNCATION]
        return f"non-JSON response: {snippet}"
    msg = body.get("messageTranslation") or body.get("message")
    if msg:
        return str(msg)
    return repr(body)[:_DETAIL_TRUNCATION]


# Inside EspoAdminClient:

def _request(
    self, method: str, url: str, **kwargs: Any
) -> tuple[int, dict[str, Any] | None]:
    headers = kwargs.pop("headers", {})
    headers.update(self._hmac_header(method, url))

    try:
        resp = self.session.request(
            method, url, headers=headers, timeout=self.timeout, **kwargs
        )
    except requests.exceptions.ConnectionError as exc:
        logger.error("Connection error: %s %s: %s", method, url, exc)
        return -1, {
            "_request_failed": True,
            "_error": str(exc),
            "_exception_type": "ConnectionError",
        }
    except requests.exceptions.Timeout as exc:
        logger.error("Request timeout: %s %s: %s", method, url, exc)
        return -1, {
            "_request_failed": True,
            "_error": str(exc),
            "_exception_type": "Timeout",
        }
    except requests.exceptions.RequestException as exc:
        logger.error(
            "Request failed: %s %s: %s: %s",
            method, url, type(exc).__name__, exc,
        )
        return -1, {
            "_request_failed": True,
            "_error": str(exc),
            "_exception_type": type(exc).__name__,
        }

    if not resp.content:
        return resp.status_code, None

    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raw = resp.content.decode("utf-8", errors="replace")
        truncated = raw[:_RAW_TEXT_TRUNCATION]
        logger.warning(
            "Non-JSON response from %s %s: status=%d, body=%r, parse_error=%s",
            method, url, resp.status_code, truncated, exc,
        )
        return resp.status_code, {
            "_parse_failed": True,
            "_raw_text": truncated,
            "_status_code": resp.status_code,
        }

    if not isinstance(body, dict):
        # JSON parsed but is a list or scalar — still wrap so callers
        # always get a dict or None.
        return resp.status_code, {
            "_unexpected_shape": True,
            "_value": body,
            "_status_code": resp.status_code,
        }

    return resp.status_code, body
```

The `_unexpected_shape` branch is added because EspoCRM occasionally returns JSON arrays (e.g., GET on certain admin endpoints) and the existing `tuple[int, dict | None]` annotation is wrong for those. Wrapping gives us a consistent dict shape; if any caller actually depends on a list response today, we'll catch it in tests.

### Step 2 — Audit and update each manager

For each manager file listed above, find the pattern that currently looks roughly like:

```python
if body:
    msg = body.get("message", "")
    self.output_fn(f"          {msg or body}", "red")
```

and replace it with:

```python
self.output_fn(
    f"          {_format_error_detail(body)}", "red"
)
```

The output indentation (`"          "` = 10 spaces) matches the existing convention so the error detail aligns under the `[ERROR]` or `[CREATE]` line. Don't change the indent.

Some managers may be using slight variations (`response_body` vs `body`, conditional emission on `body` truthy, etc.). Normalize them all to the same pattern: emit a single error-detail line, always (because `_format_error_detail(None)` returns `"(no response body)"` which is informative on its own).

### Step 3 — Tests

Create `tests/core/test_api_client.py` if it doesn't exist. Use `unittest.mock.patch` on the `Session.request` method to inject responses with controlled `status_code`, `content`, and `json()` behavior. Reference the existing test files in `tests/core/` for style and fixture conventions.

For each manager test file that you touch, add tests that mock the underlying API client method to return a `_parse_failed` sentinel and assert that the manager emits an output line containing `"non-JSON response:"` or the raw text snippet. The exact assertion target depends on each manager's output format; match the existing test idiom in that file.

### Step 4 — Verification

After implementing, run:

```bash
pytest tests/ -x -v 2>&1 | tail -60
ruff check espo_impl/core/ tests/core/
mypy espo_impl/core/api_client.py
```

All existing tests must pass. `ruff` and `mypy` must be clean for the modified files (matching the repo's existing standard).

Then do a manual smoke test if possible: trigger a Configure run against any reachable EspoCRM instance (CBM Test if available) and visually confirm the output formatting still looks correct on a successful run. The point is that we haven't broken the success path while hardening the failure path.

---

## Acceptance criteria

- [ ] `_request` catches `JSONDecodeError`, `ValueError`, and `RequestException`. No bare exceptions propagate from `_request` other than `AuthenticationError` (which isn't raised here anyway — that's at the manager layer).
- [ ] `_format_error_detail` exists as a module-level function in `api_client.py` and handles all five branches (None, parse_failed, request_failed, message, fallback).
- [ ] Every manager file in `espo_impl/core/` that emits HTTP error details uses `_format_error_detail` for that emission.
- [ ] `tests/core/test_api_client.py` exists with at minimum the four `_request` tests and the five `_format_error_detail` tests listed above.
- [ ] At least one test per modified manager asserts useful error output for `_parse_failed` bodies.
- [ ] All existing tests still pass.
- [ ] `ruff check` is clean for all modified files.
- [ ] `mypy` is clean for `api_client.py`.
- [ ] A grep for `\.json()` outside of a `try/except` block returns no hits in `espo_impl/` or `automation/core/` (the `connectivity.py` call already has a broad `except Exception` and gets a `logger.warning` added).

---

## Commit message

```
fix(api_client): defensive error handling for non-JSON and request failures

EspoAdminClient._request() previously caught only ConnectionError and
Timeout. Any other failure (JSONDecodeError on non-JSON 500 pages, SSL
errors, chunked-encoding errors) propagated through every manager and
killed the run with a bare Python exception message and no diagnostic
detail.

This commit:
- Catches JSONDecodeError/ValueError around resp.json() and returns a
  sentinel body containing the truncated raw response text.
- Catches RequestException as a broad fallback, returning a sentinel
  body with the exception type and message.
- Adds _format_error_detail() helper for consistent error formatting.
- Updates all managers in espo_impl/core/ to use _format_error_detail
  when emitting HTTP error output, surfacing raw-text snippets when
  the server returns non-JSON.
- Adds unit tests for _request and _format_error_detail.

The next Configure run that hits a non-JSON server response will now
print the actual response text (HTML page snippet, plain-text error,
etc.) instead of "Error: Expecting value: line 1 column 1 (char 0)".

This is Prompt A in the error-handling series. Prompt B will address
worker-level resilience so unexpected manager exceptions don't kill
the entire run.
```
