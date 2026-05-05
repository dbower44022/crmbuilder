# Claude Code Prompt — `phase_post_install`: read cert expiry from disk instead of nginx port

**Repository:** `dbower44022/crmbuilder`
**Branch:** `main` (commit directly)
**Type:** Bug fix — wrong source for cert expiry read

---

## 1. Problem statement

The `phase_post_install` step of every deploy and reset reads
the SSL certificate expiry by going through the live nginx
port-443 endpoint, then logs a misleading error when that read
fails. Live evidence from the 05-04-26 CBM reset:

```
Reading SSL certificate expiry...
Could not read certificate from <stdin>
Unable to load certificate
WARNING: Could not read SSL certificate expiry
```

Earlier in the same log, the Let's Encrypt installer reported a
successful cert provision:

```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/crm-test.clevelandbusinessmentors.org/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/crm-test.clevelandbusinessmentors.org/privkey.pem
This certificate expires on 2026-08-02.
```

The cert exists on disk with an expiry date. The deploy worker's
attempt to read it failed for two reasons:

1. **Wrong source.** The command pipes
   `openssl s_client -connect {domain}:443 </dev/null` into
   `openssl x509 -noout -enddate`. This reads the cert from the
   *live nginx endpoint*, not from the cert file on disk. The
   live endpoint depends on nginx being up and accepting SSL
   connections — at the moment `phase_post_install` runs,
   nginx has just been started by `docker compose up` and may
   not be responding to SSL handshakes yet.
2. **Swallowed error.** The `2>/dev/null` on the
   `openssl s_client` half of the pipe discards the actual
   error message. When `s_client` fails (because the port isn't
   responding yet), an empty stdin lands in `openssl x509`,
   which prints `Could not read certificate from <stdin>` —
   technically correct but completely misleading. The real
   error was higher up the pipe.

The cert file path is deterministic for any Let's Encrypt-
provisioned instance:
`/etc/letsencrypt/live/{domain}/fullchain.pem`. Reading the file
directly is more reliable, faster, and not subject to nginx
warm-up timing.

## 2. Root cause

`automation/core/deployment/ssh_deploy.py:phase_post_install()`,
line 271–276:

```python
log("Reading SSL certificate expiry...", "info")
cert_cmd = (
    f"openssl s_client -connect {config.domain}:443 "
    f"</dev/null 2>/dev/null | openssl x509 -noout -enddate"
)
exit_code, cert_output = run_remote(ssh, cert_cmd, log)
```

Reads the cert from a live SSL handshake instead of from the
file. Susceptible to the same nginx-warm-up race that bit
Phase 4 verification (just fixed in commit `1d9bd0e`).

## 3. Fix

Read the cert file directly:

```bash
openssl x509 -in /etc/letsencrypt/live/{domain}/fullchain.pem -noout -enddate
```

This:

- Doesn't depend on nginx being up.
- Doesn't depend on a live SSL handshake.
- Returns a clear, parseable error if the file is missing
  (rather than the misleading "Could not read certificate from
  <stdin>" symptom of an upstream pipe failure).
- Is idempotent and safe to run any number of times.

Drop the `2>/dev/null` suppression so the actual error message
is captured if the read fails.

## 4. Required code change

`automation/core/deployment/ssh_deploy.py`, lines 271–287:

Replace:

```python
    log("Reading SSL certificate expiry...", "info")
    cert_cmd = (
        f"openssl s_client -connect {config.domain}:443 "
        f"</dev/null 2>/dev/null | openssl x509 -noout -enddate"
    )
    exit_code, cert_output = run_remote(ssh, cert_cmd, log)
    cert_expiry: str | None = None
    if exit_code == 0 and "notAfter=" in cert_output:
        expiry_str = cert_output.split("notAfter=")[-1].strip()
        try:
            expiry_dt = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
            cert_expiry = expiry_dt.strftime("%Y-%m-%d")
            log(f"SSL certificate expires: {cert_expiry}", "info")
        except ValueError:
            log(f"WARNING: Could not parse cert expiry: {expiry_str}", "warning")
    else:
        log("WARNING: Could not read SSL certificate expiry", "warning")
```

with:

```python
    log("Reading SSL certificate expiry...", "info")
    # Read the cert file directly rather than going through nginx
    # port 443. The file path is deterministic for any Let's Encrypt
    # provisioned instance, and reading from disk doesn't depend on
    # nginx being up — the live-port approach was subject to the
    # same nginx warm-up race that affected Phase 4 verification
    # (fixed in commit 1d9bd0e).
    cert_path = (
        f"/etc/letsencrypt/live/{config.domain}/fullchain.pem"
    )
    cert_cmd = f"openssl x509 -in {cert_path} -noout -enddate"
    exit_code, cert_output = run_remote(ssh, cert_cmd, log)
    cert_expiry: str | None = None
    if exit_code == 0 and "notAfter=" in cert_output:
        expiry_str = cert_output.split("notAfter=")[-1].strip()
        try:
            expiry_dt = datetime.strptime(
                expiry_str, "%b %d %H:%M:%S %Y %Z"
            )
            cert_expiry = expiry_dt.strftime("%Y-%m-%d")
            log(f"SSL certificate expires: {cert_expiry}", "info")
        except ValueError:
            log(
                f"WARNING: Could not parse cert expiry: "
                f"{expiry_str}",
                "warning",
            )
    else:
        log(
            f"WARNING: Could not read SSL certificate expiry "
            f"from {cert_path} (exit code {exit_code})",
            "warning",
        )
```

The warning message now includes the cert path it tried to read
and the exit code, so a real failure (e.g. cert file missing,
permissions issue) is debuggable from the log alone.

## 5. Out of scope

- Do NOT change the cert-renewal cron job at line 268–269.
  That's a separate concern.
- Do NOT change the cert provision step earlier in the deploy
  pipeline. The Let's Encrypt installer already works correctly.
- Do NOT add fallback to the live-port approach if the file
  read fails. The file-read approach is strictly more reliable;
  if it fails, the live-port approach is also overwhelmingly
  likely to fail (or give stale data). Better to surface the
  real error.
- Do NOT change `phase_verify`. The Phase 4 verification's SSL
  cert check (commit `1d9bd0e`) reads via the live port
  intentionally — that's testing whether nginx is serving SSL
  correctly, which is a different question from "what is the
  cert's expiry."
- Do NOT change deploy-engine behavior in any other way.

## 6. Required tests

`phase_post_install` is integration-style code without a
dedicated test file in the suite (analogous to `phase_verify`
before commit `1d9bd0e`). If `tests/test_ssh_deploy.py` exists
(it does, from `1d9bd0e`), add tests there. Otherwise create
a new file.

```python
def test_phase_post_install_reads_cert_from_disk():
    """phase_post_install reads the cert via openssl x509 -in
    /etc/letsencrypt/live/{domain}/fullchain.pem, not via the
    live SSL handshake on port 443."""
    # Mock run_remote to capture the commands run. Mock the
    # docker compose ps and crontab commands to succeed. Mock
    # the cert read to return (0, 'notAfter=Aug  2 12:00:00 2026 GMT').
    # Call phase_post_install. Assert one of the captured
    # commands matches r'openssl x509 -in
    # /etc/letsencrypt/live/{domain}/fullchain.pem -noout -enddate'.
    # Assert no captured command contains 'openssl s_client'.
    # Assert returned cert_expiry is '2026-08-02'.


def test_phase_post_install_logs_path_on_cert_read_failure():
    """When the cert file can't be read, the warning message
    includes the file path and the exit code."""
    # Mock run_remote: docker ps OK, crontab OK, cert read
    # returns (2, 'No such file or directory'). Capture log
    # calls. Assert one log line contains the cert path and
    # exit code 2.


def test_phase_post_install_returns_none_expiry_on_read_failure():
    """A failed cert read still completes the phase successfully
    (it's a warning, not a fatal error) but returns None as the
    cert_expiry."""
    # Mock run_remote: docker ps OK, crontab OK, cert read
    # returns (2, '').
    # Call phase_post_install. Assert returned tuple is
    # (True, '', None).
```

## 7. Verification

1. **Lint:** `uv run ruff check automation/`.
2. **Unit tests:** `uv run pytest tests/test_ssh_deploy.py -v`.
3. **Manual end-to-end (by Doug):** Trigger a Recovery & Reset
   on the CBM test instance. Expected log fragment:

   ```
   Reading SSL certificate expiry...
   SSL certificate expires: 2026-08-02
   ```

   No more `Could not read certificate from <stdin>` or
   `Unable to load certificate`. The expiry date matches what
   the Let's Encrypt installer reported earlier in the same
   log.

## 8. Commit

Single commit. Suggested message:

```
fix(deploy): read cert expiry from disk, not live nginx port

phase_post_install was reading the SSL cert expiry by piping
openssl s_client through openssl x509 -noout -enddate. This
went through nginx on port 443 — and was subject to the same
nginx warm-up race that affected Phase 4 verification (fixed
in 1d9bd0e). When nginx wasn't ready, the live-port read
failed but the 2>/dev/null suppressed the real error,
producing misleading 'Could not read certificate from <stdin>'
output. Live evidence from the 05-04-26 CBM reset.

Fix: read the cert file directly via openssl x509 -in
/etc/letsencrypt/live/{domain}/fullchain.pem -noout -enddate.
The file path is deterministic for any Let's Encrypt
provisioned instance, and reading from disk doesn't depend on
nginx being up. The warning message on failure now includes
the cert path and exit code so a real failure (missing file,
permissions issue) is debuggable from the log.

Three new tests cover: cert read goes through the file path,
not the live port; warning includes path and exit code on
failure; phase still returns success with None expiry on a
read failure (it's a warning, not a fatal error).

phase_verify's SSL cert check at line ~331 is unchanged. That
check intentionally reads via the live port because it's
testing whether nginx is serving SSL correctly — a different
question from 'what does the cert say.'

Third of three engine-bug-backlog cleanup prompts from the
05-04-26 deployment validation pass. Companions: 1464559
(absolute path display), 1d9bd0e (Phase 4 polling).
```
