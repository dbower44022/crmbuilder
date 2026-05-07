# CLAUDE-CODE-PROMPT-v2-ui-B-server-lifecycle

**Last Updated:** 05-07-26 22:00
**Series:** v2-ui
**Slice:** B (2 of 8)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-implementation-plan.md`
**Predecessor slice:** v2-ui-A (commit `2e9c7ce`)

## Purpose

Slice B adds the API subprocess lifecycle layer to the UI scaffold delivered by slice A. After this slice, the UI:

- Probes `GET /health` at startup; if the API responds, uses it; if not, spawns `crmbuilder-v2-api` as a managed subprocess and waits for readiness.
- Tracks ownership ("external" / "owned") so it terminates only subprocesses it spawned itself.
- Shows the splash from slice A only as long as the readiness check is in progress, dismissing it on `ready`.
- Surfaces a non-modal banner with a Reconnect button when an owned subprocess crashes mid-session.
- Cleanly terminates owned subprocesses on window close.

This slice does not introduce any HTTP client beyond the small probe call required for the lifecycle itself. The full `StorageClient`, the canonical worker pattern, and per-entity panel content land in slices C through E.

## Project context

Slice A landed at commit `2e9c7ce`. The UI scaffold exists with populated `app.py`, `main_window.py`, `sidebar.py`, `splash.py`, and `styling.py`. The `crash_banner.py` and `server_lifecycle.py` modules are empty docstring stubs ready to be filled in. The `GET /health` endpoint is live in the API.

The integration point in `app.py` is the block at line 108–114 — currently a 500ms `QTimer.singleShot` that shows the main window and dismisses the splash as a smoke check. Slice B replaces that block with lifecycle-driven dismissal.

The implementation plan section 4 / Step B specifies the deliverables and acceptance gates. PRD sections 4.1, 4.2, 4.3, and the relevant parts of section 4.11 (ConnectionError handling) are the authoritative behavior spec.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report.
3. Confirm git identity is set: `Doug <doug@dougbower.com>`. If not, configure.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice A is on `main`: `git log --oneline -5` should show `2e9c7ce` and the two earlier slice-A commits (`00dcb88`, `b3f134b`).
6. Confirm the existing UI smoke tests pass: `uv run pytest tests/crmbuilder_v2/ui/ -v`.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md` — re-read sections 4.1, 4.2, 4.3, and 4.11.
3. `PRDs/product/crmbuilder-v2/ui-implementation-plan.md` — re-read Step B in section 4.
4. Slice A's actual code:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` (the integration point at lines 108–114)
   - `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` (no `closeEvent` yet; needs one)
   - `crmbuilder-v2/src/crmbuilder_v2/ui/splash.py` (already constructed; lifecycle just dismisses it via `splash.finish(window)`)
   - `crmbuilder-v2/src/crmbuilder_v2/ui/server_lifecycle.py` (stub — slice B fills this in)
   - `crmbuilder-v2/src/crmbuilder_v2/ui/crash_banner.py` (stub — slice B fills this in)
   - `crmbuilder-v2/src/crmbuilder_v2/cli.py` (defines `run_api`; B will spawn this via `sys.executable -c`)
5. **Tier 2 orientation** (per DEC-011): current charter, current status (now v5), SES-004, DEC-023.

## Step 1 — Implement `server_lifecycle.py`

The full lifecycle module. The class is a `QObject` so it can emit signals and is cleanly testable.

### Class shape

```python
class ServerLifecycle(QObject):
    ready = Signal()              # fired on probe success or successful spawn
    crashed = Signal(str)         # fired when an owned subprocess exits unexpectedly; arg is captured stderr (may be "")
    spawn_failed = Signal(str)    # fired when initial spawn does not become ready within the deadline; arg is captured stderr
    terminated = Signal()         # fired after our own .terminate() completes

    def __init__(self, base_url: str, parent: QObject | None = None): ...
    def start(self) -> None:      # public entry point — orchestrates probe → spawn → readiness
    def terminate(self) -> None:  # called from main window closeEvent
    @property
    def ownership(self) -> str:   # "unknown" | "external" | "owned" | "terminated"
```

### Probe-and-spawn orchestration

`start()` does the following, in order:

1. Synchronous one-shot probe of `GET {base_url}/health` with `httpx.get(..., timeout=1.0)`. One second on the UI thread on app startup is acceptable (the splash is visible during this window).
   - If 200, set ownership to `"external"`, emit `ready`, return.
   - If any exception (connection refused, timeout, etc.), proceed to spawn.

2. Spawn the API subprocess via `QProcess`:
   - Program: `sys.executable`
   - Arguments: `["-c", "from crmbuilder_v2.cli import run_api; run_api()"]`
   - Process channel mode: `QProcess.MergedChannels` (capture stdout+stderr together; we want both in the log and in the failure message if any).
   - Wire `QProcess.errorOccurred` → log + emit `spawn_failed` with the error string.
   - Wire `QProcess.finished` (the post-readiness handler) → only treat as `crashed` if `ownership == "owned"` and we are not in the middle of a deliberate `terminate()`.
   - Set ownership to `"owned"` when the process is started.
   - Start the process via `QProcess.start()`.

3. Once the process is started, begin readiness polling. Use a `QTimer` with 250ms interval, scheduled from the UI thread. On each tick:
   - Run a one-shot `httpx.get(..., timeout=0.25)` to `/health`.
   - If 200, stop the timer, emit `ready`. Done.
   - Track elapsed wall-clock time since start of polling.
   - If elapsed exceeds 10 seconds, stop the timer, capture whatever the subprocess has written to its stdout/stderr so far via `QProcess.readAllStandardOutput()`, emit `spawn_failed(stderr_text)`. Do NOT terminate the subprocess automatically — the caller will decide whether to retry or exit.

   The polling runs on the UI thread but each httpx call has a tight timeout, so it cannot block longer than 250ms. If the API genuinely takes longer than 250ms to respond on its first ready /health, the next tick will catch it.

### `terminate()` semantics

- If ownership is `"external"`, do nothing (the API was running before us; not ours to stop).
- If ownership is `"owned"`:
  - Mark internal flag `_intentional_terminate = True` so the subsequent `QProcess.finished` signal is not treated as a crash.
  - Call `QProcess.terminate()` (graceful — SIGTERM on Unix).
  - If `QProcess.waitForFinished(3000)` returns False, call `QProcess.kill()` (SIGKILL).
  - Emit `terminated`.
  - Set ownership to `"terminated"`.

### Crash detection

Independent of `terminate()`, when `QProcess.finished(exit_code, exit_status)` fires:
- If `_intentional_terminate` is True, ignore (we caused this).
- Else if ownership was `"owned"`, capture `readAllStandardOutput()`, emit `crashed(stderr_text)`.

### Configuration

The lifecycle reads its base URL from the constructor argument. The caller (in `app.py`) resolves the URL from `crmbuilder_v2.config.get_settings()` so the UI and the API agree by construction.

### Logging

Use `logging.getLogger("crmbuilder_v2.ui.lifecycle")`. Log: probe result, spawn invocation, readiness polling start, ready time (with elapsed seconds), terminate invocation, crash detection. Do not log /health response bodies.

## Step 2 — Implement `crash_banner.py`

A simple non-modal banner widget.

```python
class CrashBanner(QWidget):
    reconnect_requested = Signal()

    def __init__(self, parent: QWidget | None = None): ...
    def show_with_message(self, message: str) -> None: ...
    def hide(self) -> None: ...
```

### Visual

- Horizontal layout: a `QLabel` on the left (text from `show_with_message` argument; default `"Storage server stopped."`), spacer, a `QPushButton` labeled `"Reconnect"` on the right.
- Background color: a warning shade (use `#7A1F1F` — a deep red that pairs with the navy accent without clashing). White text on the label and button.
- Fixed height around 36px.
- Hidden by default. Shown only via `show_with_message()`.

### Signal

Clicking Reconnect emits `reconnect_requested` and hides the banner. The receiver decides what to do (retry probe, then spawn, etc.).

## Step 3 — Wire the lifecycle into `app.py`

Replace the slice-A integration block (currently `QTimer.singleShot(_SPLASH_SMOKE_TEST_MS, _show_window)` at lines 110–114) with lifecycle wiring.

### New shape of `main()`

```
1. Parse args, configure logging, build_application(), construct splash, splash.show(), processEvents.
2. Resolve base_url from get_settings().
3. Construct ServerLifecycle(base_url).
4. Construct MainWindow(lifecycle=lifecycle). The window holds a reference to the lifecycle so its closeEvent can call terminate().
5. Connect lifecycle.ready → show_window_and_dismiss_splash slot
6. Connect lifecycle.spawn_failed → show_spawn_failure_dialog slot which shows a modal QMessageBox and calls app.quit() with non-zero exit code.
7. Connect lifecycle.crashed → main_window.handle_crash slot (defined in step 4 below).
8. Call lifecycle.start().
9. Run app.exec(), return exit code.
```

### Spawn failure dialog

When `spawn_failed(stderr)` fires, show a modal `QMessageBox.critical()`:
- Title: `"Storage server failed to start"`
- Text: `"crmbuilder-v2-ui could not start the storage API and no API was already running."`
- Detailed text: the captured stderr.
- After the user dismisses, call `app.quit()` and return exit code `1`.

### Remove the slice-A smoke-test constant

Delete `_SPLASH_SMOKE_TEST_MS = 500` and the `_show_window` closure. The lifecycle drives splash dismissal now.

## Step 4 — Wire lifecycle and crash banner into `main_window.py`

### Constructor change

```python
def __init__(self, lifecycle: ServerLifecycle):
```

The lifecycle is required (no default). The window owns the reference for the duration of its life; on close it calls `lifecycle.terminate()`.

### Crash banner installation

Add a `CrashBanner` instance at the top of the central widget, above the sidebar+stack horizontal layout. Use a vertical outer layout: banner (collapsible) on top, then the existing horizontal sidebar+stack below.

The banner is hidden by default. When `lifecycle.crashed(stderr)` fires, the window's `handle_crash(stderr)` slot:
- Shows the banner with the default message.
- Disables the sidebar and the content stack (visually grayed; per PRD section 4.3 "all entity panels show a disabled state with a 'No connection' overlay" — for slice B the disabled-state is sufficient; the explicit overlay can land in slice C alongside the panels).
- Logs the captured stderr at WARNING level.

When `crash_banner.reconnect_requested` fires, the window calls `lifecycle.start()` again. On `lifecycle.ready`, the window hides the banner and re-enables the sidebar and stack. On a second `spawn_failed` after a reconnect, fall back to the same modal error dialog as initial-startup spawn failure (factor it into a shared function).

### closeEvent

Add an override that calls `self._lifecycle.terminate()` before accepting the event. Block on the synchronous terminate (it includes `waitForFinished(3000)`); the user cannot interact with the window during this short window because Qt is closing it.

### Default sidebar selection

Unchanged — still Decisions on launch.

## Step 5 — Tests

### `tests/crmbuilder_v2/ui/test_server_lifecycle.py` (new)

Use `pytest-qt`'s `qtbot` for signal waiting and a small test fixture that lets us substitute a mock `httpx.get` and a mock `QProcess`. Real `QProcess` invocation in tests is brittle — mock it.

Tests:

1. **Probe success → external ownership, no spawn.** Mock `httpx.get` to return a 200 response. Call `lifecycle.start()`. Assert `lifecycle.ownership == "external"` and no `QProcess` was constructed. `qtbot.waitSignal(lifecycle.ready)` succeeds within 100ms.

2. **Probe failure → spawn → ready.** Mock `httpx.get` to first raise `httpx.ConnectError`, then on subsequent calls return 200. Mock `QProcess.start` to do nothing. Call `lifecycle.start()`. Assert `lifecycle.ownership == "owned"`. `qtbot.waitSignal(lifecycle.ready)` succeeds within 1 second (the readiness polling should converge quickly with the mocked /health).

3. **Spawn failure deadline.** Mock `httpx.get` to always raise `httpx.ConnectError`. Mock `QProcess.start` to do nothing. Call `lifecycle.start()`. `qtbot.waitSignal(lifecycle.spawn_failed, timeout=11000)` succeeds (allow 11 seconds — slightly over the 10s readiness deadline).

4. **Terminate-only-owned semantics.** Probe-success path → ownership is "external". Call `lifecycle.terminate()`. Assert no `QProcess.terminate` was invoked. Ownership remains `"external"`.

5. **Crash detection.** Probe-failure → spawn → ready path completed. Then simulate `QProcess.finished` firing without a prior `terminate()` call. Assert `lifecycle.crashed` signal fires with whatever stderr was captured.

6. **Crash suppression during deliberate terminate.** Probe-failure → spawn → ready path completed. Call `lifecycle.terminate()`. Then simulate `QProcess.finished` firing. Assert `crashed` is NOT emitted (the `_intentional_terminate` flag suppresses it).

### `tests/crmbuilder_v2/ui/test_smoke.py` (extend)

Add one test: construct `MainWindow(lifecycle=lifecycle_stub)` with a stub lifecycle that has `terminate` callable, assert it constructs without raising and the crash banner is hidden by default.

The existing tests must continue to pass — the construction signature change (lifecycle now required) means existing tests need to pass a stub.

### `tests/crmbuilder_v2/ui/conftest.py` (extend)

Add a `lifecycle_stub` fixture: a minimal object with the methods/signals the main window references. Either a real `ServerLifecycle` constructed against an unreachable URL with `start()` not called, or a `Mock` from `unittest.mock`. Use whichever produces simpler tests.

## Step 6 — Verify and commit

Run:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: 100 prior tests + 6 lifecycle tests + ~1 main-window construction test = ~107 total, all passing.

Manual verification (optional but recommended):

1. With no API running: `uv run crmbuilder-v2-ui`. Splash should show, then dismiss within a few seconds, with the main window appearing. (Lifecycle spawned its own API subprocess.)
2. With the API already running in another terminal: `uv run crmbuilder-v2-ui`. Splash should show, dismiss almost immediately. (Lifecycle detected existing API.)
3. While the UI is running with an owned API: kill the API subprocess from outside (e.g., `pkill -f "crmbuilder_v2.cli"`). The crash banner should appear at the top of the window. Click Reconnect — the API should respawn and the banner disappear.
4. Close the UI. The owned subprocess should not survive. With the externally-launched API, that API should still be running.

Commit shape: one commit covering all of slice B.

```
git commit -m "v2: ui server lifecycle — detect, spawn, splash, crash banner

Implements DEC-023 detect-then-launch subprocess management:

- ServerLifecycle (server_lifecycle.py): synchronous one-shot probe of
  GET /health on startup; if no response, spawns crmbuilder-v2-api as a
  managed QProcess and polls /health every 250ms for up to 10 seconds.
  Tracks ownership (external/owned) to terminate only its own
  subprocesses on shutdown. Emits ready/crashed/spawn_failed/terminated
  signals.

- CrashBanner (crash_banner.py): non-modal banner shown when an owned
  subprocess exits unexpectedly. Reconnect button re-runs the lifecycle
  start sequence.

- app.py: replaces the slice-A 500ms timer-based splash dismissal with
  lifecycle-driven wiring. Spawn failures show a modal error dialog
  with captured stderr and exit with code 1.

- main_window.py: requires a lifecycle in its constructor; installs the
  crash banner above the sidebar+stack layout; calls lifecycle.terminate()
  on closeEvent for graceful subprocess shutdown.

- 6 new lifecycle unit tests covering probe success, probe failure with
  spawn-and-ready, spawn-failure deadline, terminate-only-owned
  semantics, crash detection, and crash suppression during deliberate
  terminate.

PRD §4.1, §4.2, §4.3 acceptance criteria addressed."
```

Push:

```
git push origin main
```

## Acceptance gates

This slice is complete when all of the following are true:

1. Launching the UI with no API running spawns the API and dismisses the splash when ready. (PRD AC#2)
2. Launching the UI with the API already running uses the existing instance, does not spawn a duplicate, dismisses the splash on the first probe success. (PRD AC#2)
3. Killing an owned API subprocess while the UI runs surfaces the crash banner. Clicking Reconnect successfully respawns the API and clears the banner. (PRD AC#3)
4. Closing the UI cleanly terminates an owned subprocess; an externally-launched API stays running. (PRD AC#13, partially)
5. Spawn failure (deliberately broken environment, e.g., bad command) shows a modal error dialog with the captured stderr and exits with code 1.
6. The full v2 test suite passes, including the six new lifecycle tests.
7. One commit on `origin/main` with the message shape above.

## Out of slice

The following are explicitly NOT in scope for slice B:

- Any populated entity panels — slices D and E.
- The full `StorageClient` with typed exceptions and worker pattern — slice C. Slice B's lifecycle uses a thin `httpx.get` directly; the formal client comes later.
- File-watch refresh — slice F.
- Decision dialogs — slice G.
- About dialog content — slice H.
- The "No connection" panel overlay — defer to slice C alongside the formal client; for slice B, the `setEnabled(False)` on the sidebar and stack is the disabled-state surface.

Resist the urge to start any of the above. The lifecycle layer is a self-contained slice.

## Constraints

- **No new external dependencies.** `httpx` and `PySide6` are already deps. Tests use `pytest-qt` (already a dev dep) and stdlib `unittest.mock`.
- **Do not modify the API.** The `/health` endpoint is already in place from slice A. No other API changes.
- **Do not modify access-layer code, schema, migrations, or vocab.**
- **Do not introduce a global lifecycle singleton.** The `ServerLifecycle` instance is constructed in `main()` and owned by the main window. Avoid module-level state that would leak across test runs.
- **Stop and ask if uncertain.** If the PRD or plan leaves a substantive question unresolved, surface it rather than choosing silently.

## Reporting

After execution, produce a completion report covering:

- **Acceptance gates** — pass/fail for each of the seven gates above.
- **Files modified or created** — full list, organized by step.
- **Test results** — output summary from `uv run pytest tests/crmbuilder_v2/ -v`.
- **Manual verification** — short report on whichever of the four manual scenarios you ran (at minimum scenario 1 and 2; scenarios 3 and 4 are recommended but optional).
- **Deviations from this prompt** — anything that diverged, with reason.
- **Open questions or surprises** — anything that came up during execution that should be captured as a new DEC, surfaced for slice C, or noted for the slice-H polish backlog.
- **What slice C will need** — any context, naming choices, or interface shapes from B that C should respect.
