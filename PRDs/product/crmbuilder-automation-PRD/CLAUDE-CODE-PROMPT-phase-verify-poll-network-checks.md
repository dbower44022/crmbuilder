# Claude Code Prompt — `phase_verify`: poll network-dependent checks instead of probing once

**Repository:** `dbower44022/crmbuilder`
**Branch:** `main` (commit directly)
**Type:** Bug fix — async race condition

---

## 1. Problem statement

The post-deploy / post-reset verification phase fires its
network-dependent probes immediately after `docker compose up`
returns, when nginx has typically been alive less than a second
and SSL handshakes have not yet warmed. The result is that a
**successful** reset or deploy shows "Failed checks: HTTP redirect
to HTTPS, HTTPS response, SSL certificate valid, EspoCRM login
page present" — a confusing log that looks like a deploy
failure but is actually probe-too-early.

Live evidence from the 05-04-26 reset against the CBM test
instance:

```
Phase 4 started: Verification
=== Phase 4: Verification ===
Verifying: Docker containers running
  PASS: Docker containers running
Verifying: HTTP redirect to HTTPS
  FAIL: HTTP redirect to HTTPS
Verifying: HTTPS response
  FAIL: HTTPS response
Verifying: SSL certificate valid
  FAIL: SSL certificate valid
Verifying: EspoCRM login page present
  FAIL: EspoCRM login page present
Verifying: Cron job configured
  PASS: Cron job configured
Verifying: Database connectivity
  PASS: Database connectivity
=== Verification Results ===
  ... (4 FAIL, 3 PASS)
Phase 4 failed: Failed checks: ...
```

`docker compose ps` output earlier in the same log:

```
espocrm-nginx       ... Up Less than a second
```

The user logged in to https://crm-test.clevelandbusinessmentors.org
moments later — the instance was healthy, the verification
phase just probed too early and reported false failures.

The same `phase_verify` function is called from two paths:

- `automation/ui/deployment/recovery_worker.py:220` — Recovery & Reset
- `automation/ui/deployment/deploy_wizard/deploy_worker.py:160` — fresh deploy

Both are affected by the same race. Fixing `phase_verify` itself
fixes both call sites simultaneously.

## 2. Root cause

`automation/core/deployment/ssh_deploy.py:phase_verify()` runs each
check **once** with no retry. There is no warm-up delay between
"docker compose up returned" (which only confirms the container
process is running) and "nginx is accepting HTTPS connections,
SSL handshakes succeed, the PHP backend has booted enough to
serve the login page."

Three of the seven checks are network-dependent and subject to
this race:

- **HTTP redirect to HTTPS** — nginx has to be listening on :80
- **HTTPS response** — nginx has to have completed SSL setup on :443
- **SSL certificate valid** — same as HTTPS response, plus the
  cert files have to be readable
- **EspoCRM login page present** — adds the requirement that
  PHP-FPM has booted, and the EspoCRM front-controller responds
  with HTML containing "espocrm"

The other three checks are stable as soon as `docker compose up`
returns:

- **Docker containers running** — checks `docker compose ps`,
  process state is immediate
- **Cron job configured** — checks crontab, no async
- **Database connectivity** — checks docker ps with grep on
  the db container, immediate

## 3. Fix

Wrap the four network-dependent checks in a polling loop with a
hard timeout. Each check polls until it passes OR the global
deadline elapses. This matches the pattern already established
for `EntityManager.wait_for_metadata_ready` (commit `e5f18fe`):
backoff schedule, hard upper bound, yellow-warn on timeout.

The three stable checks (containers, cron, database) keep their
current single-probe behavior — there's nothing to wait for.

### Polling parameters

- **Per-check timeout: 60 seconds.** Reset on a fresh droplet
  takes 5–15s for nginx + 10–30s for PHP-FPM + EspoCRM
  bootstrap. 60s is a generous upper bound.
- **Backoff: 1s, 1s, 2s, 2s, 3s, 3s, 5s, 5s, 5s, 5s, 5s, 5s, 5s, 5s, 5s.**
  ~50 seconds across 15 attempts. Ramps up so we don't slam the
  endpoint.
- **Per-check independence: each check has its own deadline.**
  If "HTTP redirect to HTTPS" passes immediately but "EspoCRM
  login page present" needs 25 seconds, the second one's wait
  doesn't extend the first's. Total worst case: 4 × 60s = 240s.
  In practice, once the first network-dependent check passes,
  the others usually pass within a few seconds.

### Output behavior

The current single-line emission:

```
Verifying: HTTP redirect to HTTPS
  PASS: HTTP redirect to HTTPS
```

becomes, on a check that needs to wait:

```
Verifying: HTTP redirect to HTTPS
  Waiting for HTTP redirect to HTTPS to come up ...
  PASS: HTTP redirect to HTTPS (after 4s)
```

On a check that times out:

```
Verifying: HTTP redirect to HTTPS
  Waiting for HTTP redirect to HTTPS to come up ...
  FAIL: HTTP redirect to HTTPS (timed out after 60s)
```

On a check that passes immediately, the output is unchanged from
today — no `Waiting...` line, no `(after Ns)` suffix:

```
Verifying: HTTP redirect to HTTPS
  PASS: HTTP redirect to HTTPS
```

That keeps clean runs visually identical to today's logs while
the new output only appears when the polling actually fired.

## 4. Required code changes

### 4.1 `automation/core/deployment/ssh_deploy.py`

Add `time` to imports near the top of the file if not already
imported.

Modify the `run_check` inner helper inside `phase_verify` to
accept an optional `poll: bool = False` parameter. When `poll=True`,
the helper polls with the backoff schedule above; when False (the
default), it preserves single-probe behavior.

Replace the existing `run_check` (lines 303–314):

```python
    def run_check(
        name: str, command: str, check_fn: Callable[[int, str], bool],
    ) -> bool:
        log(f"Verifying: {name}", "info")
        exit_code, output = run_remote(ssh, command)
        passed = check_fn(exit_code, output)
        log(f"  {'PASS' if passed else 'FAIL'}: {name}", "info" if passed else "error")
        results.append({
            "check": name, "passed": passed,
            "detail": output[:200] if not passed else "",
        })
        return passed
```

with:

```python
    def run_check(
        name: str,
        command: str,
        check_fn: Callable[[int, str], bool],
        poll: bool = False,
        timeout_seconds: float = 60.0,
    ) -> bool:
        """Run a single verification check.

        :param name: Human-readable check name.
        :param command: SSH command to run on the droplet.
        :param check_fn: Callable that returns True iff the check
            passed given (exit_code, output).
        :param poll: When True, poll the check on a backoff
            schedule until it passes or the timeout elapses.
            When False (default), probe once. Network-dependent
            checks pass True; stable checks (containers, cron,
            database state) pass False.
        :param timeout_seconds: Per-check polling deadline. Only
            used when poll=True.
        :returns: True iff the check passed (eventually).
        """
        log(f"Verifying: {name}", "info")

        if not poll:
            exit_code, output = run_remote(ssh, command)
            passed = check_fn(exit_code, output)
            log(
                f"  {'PASS' if passed else 'FAIL'}: {name}",
                "info" if passed else "error",
            )
            results.append({
                "check": name, "passed": passed,
                "detail": output[:200] if not passed else "",
            })
            return passed

        # Polling path for network-dependent checks.
        backoff_pattern = [1.0, 1.0, 2.0, 2.0, 3.0, 3.0] + [5.0] * 20
        deadline = time.monotonic() + timeout_seconds
        attempt = 0
        first_attempt = True

        while time.monotonic() < deadline:
            exit_code, output = run_remote(ssh, command)
            passed = check_fn(exit_code, output)
            if passed:
                if first_attempt:
                    # No warm-up needed — preserve clean-run log shape.
                    log(f"  PASS: {name}", "info")
                else:
                    elapsed = int(timeout_seconds - (deadline - time.monotonic()))
                    log(f"  PASS: {name} (after {elapsed}s)", "info")
                results.append({
                    "check": name, "passed": True, "detail": "",
                })
                return True

            if first_attempt:
                log(
                    f"  Waiting for {name} to come up ...",
                    "info",
                )
                first_attempt = False

            delay = backoff_pattern[
                min(attempt, len(backoff_pattern) - 1)
            ]
            time.sleep(delay)
            attempt += 1

        # Timeout exhausted.
        elapsed = int(timeout_seconds)
        log(
            f"  FAIL: {name} (timed out after {elapsed}s)",
            "error",
        )
        # Use the last-attempt's output for the failure detail.
        results.append({
            "check": name, "passed": False,
            "detail": output[:200] if output else "(no output)",
        })
        return False
```

Then update the four network-dependent check calls (lines
321–341) to pass `poll=True`:

Replace:

```python
    run_check(
        "HTTP redirect to HTTPS",
        f"curl -sI http://{domain} | head -1",
        lambda ec, out: "301" in out or "302" in out,
    )
    run_check(
        "HTTPS response",
        f"curl -sI https://{domain} | head -1",
        lambda ec, out: "200" in out,
    )
    run_check(
        "SSL certificate valid",
        f"openssl s_client -connect {domain}:443 "
        f"</dev/null 2>/dev/null | openssl x509 -noout -dates",
        lambda ec, out: ec == 0 and "notAfter" in out,
    )
    run_check(
        "EspoCRM login page present",
        f"curl -sL https://{domain} | head -100",
        lambda ec, out: "espocrm" in out.lower() or "EspoCRM" in out,
    )
```

with:

```python
    run_check(
        "HTTP redirect to HTTPS",
        f"curl -sI http://{domain} | head -1",
        lambda ec, out: "301" in out or "302" in out,
        poll=True,
    )
    run_check(
        "HTTPS response",
        f"curl -sI https://{domain} | head -1",
        lambda ec, out: "200" in out,
        poll=True,
    )
    run_check(
        "SSL certificate valid",
        f"openssl s_client -connect {domain}:443 "
        f"</dev/null 2>/dev/null | openssl x509 -noout -dates",
        lambda ec, out: ec == 0 and "notAfter" in out,
        poll=True,
    )
    run_check(
        "EspoCRM login page present",
        f"curl -sL https://{domain} | head -100",
        lambda ec, out: "espocrm" in out.lower() or "EspoCRM" in out,
        poll=True,
    )
```

The three stable checks (Docker containers running, Cron job
configured, Database connectivity) keep their default
`poll=False` behavior. Single-probe is right for them.

### 4.2 No changes to call sites

`recovery_worker.py:220` and `deploy_worker.py:160` both call
`phase_verify(ssh, domain, log)` with positional arguments. The
function signature is unchanged. No call-site edits.

## 5. Required tests

`phase_verify` is integration-style code (talks to SSH, runs
commands on a droplet) and isn't unit-tested in the current
suite. Look for an existing test file for this module; if one
exists, add the tests below. If no test file exists for
`ssh_deploy`, create one at `tests/test_ssh_deploy.py` and add
the tests there with appropriate mocking of `run_remote` and
`time.sleep` / `time.monotonic`.

```python
def test_run_check_polls_until_passing():
    """When poll=True, run_check polls run_remote until check_fn
    passes, then returns True with a 'PASS ... (after Ns)' line."""
    # Mock run_remote to return (1, '') on first 2 calls, then
    # (0, 'HTTP/1.1 301 Moved Permanently') on 3rd. Patch time.sleep
    # to no-op. Verify run_check returns True. Verify emitted lines
    # include 'Waiting for ... to come up ...' and 'PASS: ... (after Ns)'.


def test_run_check_polls_with_timeout():
    """When poll=True and the check never passes, run_check times
    out and returns False with a 'timed out after Ns' line."""
    # Mock run_remote to always return (1, ''). Patch time.sleep to
    # no-op AND patch time.monotonic to advance past the deadline
    # after a few calls. Verify run_check returns False. Verify
    # emitted lines include 'FAIL: ... (timed out after Ns)'.


def test_run_check_passes_immediately_no_waiting_line():
    """When poll=True and the first probe passes, no 'Waiting ...'
    line is emitted — the log shape matches the non-polling path."""
    # Mock run_remote to return (0, 'HTTP/1.1 301 ...') on first
    # call. Verify run_check returns True. Verify emitted lines
    # are exactly: ['Verifying: ...', '  PASS: ...'] — no
    # 'Waiting ...' line, no '(after Ns)' suffix.


def test_run_check_no_polling_when_poll_false():
    """When poll=False (default), run_check probes once and returns
    immediately, regardless of whether the check passes."""
    # Mock run_remote to return (1, ''). Verify run_check returns
    # False. Verify run_remote called exactly once. No 'Waiting ...'
    # line emitted.
```

Existing tests that exercise `phase_verify` end-to-end (if any)
should continue to pass — the default behavior for stable checks
is unchanged.

## 6. Out of scope

- Do NOT change the cert-expiry-read failure (`Could not read
  certificate from <stdin>`). That's a separate bug, addressed
  in a companion prompt.
- Do NOT change the absolute-path log-display fix (already
  landed in commit `1464559`).
- Do NOT change which checks run, the order they run in, or
  what each check tests. Only the polling behavior changes.
- Do NOT add polling to the three stable checks (containers,
  cron, database). They don't need it.
- Do NOT change `recovery_worker.py` or
  `deploy_wizard/deploy_worker.py`. The fix is entirely inside
  `phase_verify`.

## 7. Verification

1. **Lint:** `uv run ruff check automation/`.
2. **Unit tests:** `uv run pytest tests/test_ssh_deploy.py -v`
   (or wherever the new tests land).
3. **Manual end-to-end (by Doug):** Trigger a Recovery & Reset
   on the CBM test instance. Expected log shape:

   ```
   === Phase 4: Verification ===
   Verifying: Docker containers running
     PASS: Docker containers running
   Verifying: HTTP redirect to HTTPS
     Waiting for HTTP redirect to HTTPS to come up ...
     PASS: HTTP redirect to HTTPS (after 5s)
   Verifying: HTTPS response
     PASS: HTTPS response (after 1s)
   Verifying: SSL certificate valid
     PASS: SSL certificate valid (after 1s)
   Verifying: EspoCRM login page present
     PASS: EspoCRM login page present (after 1s)
   Verifying: Cron job configured
     PASS: Cron job configured
   Verifying: Database connectivity
     PASS: Database connectivity
   ```

   Total Phase 4 duration: ~10–30s typical, where today it was
   instant-and-wrong. Phase 4 succeeds; the run summary
   reports clean.

   If the user runs Recovery & Reset against an instance where
   nginx genuinely isn't going to come up (e.g. corrupted
   config), the log shows `FAIL: ... (timed out after 60s)` for
   each affected check after the 60s wait, and the operator gets
   a clear actionable error rather than a misleading instant
   failure.

## 8. Commit

Single commit. Suggested message:

```
fix(deploy): poll network-dependent verification checks

Phase 4 verification of a Recovery & Reset (and of a fresh
deploy) probed network-dependent checks immediately after
docker compose up returned, when nginx had typically been
alive less than a second. The result was misleading: a
correctly-completed reset reported 'Failed checks: HTTP
redirect to HTTPS, HTTPS response, SSL certificate valid,
EspoCRM login page present' even though the instance came up
healthy seconds later.

Live evidence from the 05-04-26 reset of the CBM test instance:
docker compose ps showed espocrm-nginx 'Up Less than a second'
when Phase 4 fired its probes; user logged in to the instance
moments later.

Fix: extend ssh_deploy.run_check with an optional poll=True
parameter that polls the check on a backoff schedule
(1/1/2/2/3/3/5s+) until it passes or a 60s per-check timeout
elapses. The four network-dependent checks (HTTP redirect,
HTTPS response, SSL cert, login page) now poll. The three
stable checks (Docker containers, cron, database) keep their
single-probe behavior.

When a check passes on the first probe, the log shape is
unchanged — no 'Waiting...' line, no '(after Ns)' suffix, so
clean runs read identically to before. Only when polling
actually fires does the log show the wait.

Same change benefits both phase_verify call sites:
recovery_worker.py:220 (Recovery & Reset) and
deploy_wizard/deploy_worker.py:160 (fresh deploy).

Four new tests cover: poll passes after retries; poll times
out; poll passes immediately (no Waiting line); poll=False
default preserves single-probe behavior.

The cert-expiry openssl-pipe issue from the same failure log
is a separate bug, addressed in a companion prompt.
```
