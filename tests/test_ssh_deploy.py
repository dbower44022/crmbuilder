"""Tests for automation.core.deployment.ssh_deploy.

Covers the polling behavior added to phase_verify's run_check inner
helper. Network-dependent checks (HTTP redirect, HTTPS response, SSL
cert, login page) poll on a backoff schedule until they pass or a
per-check timeout elapses; stable checks (containers, cron, database)
keep the original single-probe behavior.

No real SSH and no real waiting — run_remote is mocked, and the
ssh_deploy module's time.sleep/time.monotonic are patched so tests
run instantly.
"""

import re
from unittest.mock import MagicMock, patch

from automation.core.deployment import ssh_deploy
from automation.core.deployment.ssh_deploy import SelfHostedConfig


def _capture_log() -> tuple[MagicMock, list[tuple[str, str]]]:
    """Return ``(log_callable, lines)`` where lines accumulates as the
    log is invoked. Each line is ``(message, level)``."""
    lines: list[tuple[str, str]] = []

    def log(message: str, level: str) -> None:
        lines.append((message, level))

    return log, lines


def _msgs(lines: list[tuple[str, str]]) -> list[str]:
    return [m for m, _ in lines]


# ── poll=True: passes after retries ───────────────────────────────────


def test_phase_verify_poll_passes_after_retries():
    """When a network-dependent check fails twice then passes, the
    log shows the 'Waiting...' line plus a 'PASS ... (after Ns)'
    line, and the check is recorded as passed."""
    ssh = MagicMock()
    log, lines = _capture_log()

    # Stable checks (containers, db, cron) pass on first probe;
    # network-dependent checks fail twice then pass.
    network_responses = {
        "curl -sI http://": [(1, ""), (1, ""), (0, "HTTP/1.1 301 Moved")],
        "curl -sI https://": [(0, "HTTP/1.1 200 OK")],
        "openssl s_client": [(0, "notAfter=Jan 1 2027 GMT")],
        "curl -sL https://": [(0, "<html>EspoCRM login</html>")],
    }
    counter: dict[str, int] = dict.fromkeys(network_responses, 0)

    def fake_run_remote(_ssh, command, *args, **kwargs):
        if "docker compose" in command and "ps" in command:
            if "mysql" in command or "mariadb" in command:
                return 0, "espocrm-db Up"
            return 0, "espocrm-nginx Up"
        if "crontab" in command:
            return 0, "* * * * * espocrm-cron"
        for prefix, queue in network_responses.items():
            if prefix in command:
                idx = min(counter[prefix], len(queue) - 1)
                counter[prefix] += 1
                return queue[idx]
        raise AssertionError(f"unexpected command: {command}")

    monotonic_clock = [0.0]

    def fake_monotonic():
        return monotonic_clock[0]

    def fake_sleep(seconds):
        monotonic_clock[0] += seconds

    with patch.object(ssh_deploy, "run_remote", side_effect=fake_run_remote), \
         patch.object(ssh_deploy.time, "sleep", side_effect=fake_sleep), \
         patch.object(ssh_deploy.time, "monotonic", side_effect=fake_monotonic):
        overall, results = ssh_deploy.phase_verify(ssh, "crm.example.com", log)

    assert overall is True
    assert all(r["passed"] for r in results)

    msgs = _msgs(lines)
    # The HTTP redirect check polled — Waiting line and PASS-after line
    # should both be present for that check.
    assert any("Waiting for HTTP redirect to HTTPS to come up" in m for m in msgs)
    assert any(
        m.startswith("  PASS: HTTP redirect to HTTPS (after ")
        for m in msgs
    )


# ── poll=True: times out ──────────────────────────────────────────────


def test_phase_verify_poll_times_out_recorded_as_failed():
    """When a network-dependent check never passes, polling stops at
    the per-check deadline and the check is recorded as failed with a
    'timed out after Ns' line."""
    ssh = MagicMock()
    log, lines = _capture_log()

    def fake_run_remote(_ssh, command, *args, **kwargs):
        if "docker compose" in command and "ps" in command:
            if "mysql" in command or "mariadb" in command:
                return 0, "espocrm-db Up"
            return 0, "espocrm-nginx Up"
        if "crontab" in command:
            return 0, "* * * * * espocrm-cron"
        # Every network-dependent probe fails.
        return 1, ""

    monotonic_clock = [0.0]

    def fake_monotonic():
        return monotonic_clock[0]

    def fake_sleep(seconds):
        monotonic_clock[0] += seconds

    with patch.object(ssh_deploy, "run_remote", side_effect=fake_run_remote), \
         patch.object(ssh_deploy.time, "sleep", side_effect=fake_sleep), \
         patch.object(ssh_deploy.time, "monotonic", side_effect=fake_monotonic):
        overall, results = ssh_deploy.phase_verify(ssh, "crm.example.com", log)

    assert overall is False
    by_name = {r["check"]: r for r in results}
    # The four network-dependent checks should all be failed.
    for name in [
        "HTTP redirect to HTTPS",
        "HTTPS response",
        "SSL certificate valid",
        "EspoCRM login page present",
    ]:
        assert by_name[name]["passed"] is False, name

    # The three stable checks should all have passed.
    for name in [
        "Docker containers running",
        "Cron job configured",
        "Database connectivity",
    ]:
        assert by_name[name]["passed"] is True, name

    msgs = _msgs(lines)
    assert any(
        "FAIL: HTTP redirect to HTTPS (timed out after 60s)" in m
        for m in msgs
    )


# ── poll=True: passes immediately, no Waiting line ────────────────────


def test_phase_verify_poll_passes_immediately_no_waiting_line():
    """When a polling check passes on its first probe, no 'Waiting...'
    line is emitted and no '(after Ns)' suffix is added — the log
    shape matches the non-polling path."""
    ssh = MagicMock()
    log, lines = _capture_log()

    def fake_run_remote(_ssh, command, *args, **kwargs):
        if "docker compose" in command and "ps" in command:
            if "mysql" in command or "mariadb" in command:
                return 0, "espocrm-db Up"
            return 0, "espocrm-nginx Up"
        if "crontab" in command:
            return 0, "* * * * * espocrm-cron"
        if "curl -sI http://" in command:
            return 0, "HTTP/1.1 301 Moved"
        if "curl -sI https://" in command:
            return 0, "HTTP/1.1 200 OK"
        if "openssl s_client" in command:
            return 0, "notAfter=Jan 1 2027 GMT"
        if "curl -sL https://" in command:
            return 0, "<html>EspoCRM login</html>"
        raise AssertionError(f"unexpected command: {command}")

    sleep_mock = MagicMock()
    monotonic_clock = [0.0]

    def fake_monotonic():
        return monotonic_clock[0]

    with patch.object(ssh_deploy, "run_remote", side_effect=fake_run_remote), \
         patch.object(ssh_deploy.time, "sleep", sleep_mock), \
         patch.object(ssh_deploy.time, "monotonic", side_effect=fake_monotonic):
        overall, _ = ssh_deploy.phase_verify(ssh, "crm.example.com", log)

    assert overall is True
    msgs = _msgs(lines)
    # No 'Waiting...' line for any check — they all passed first try.
    assert not any("Waiting for" in m for m in msgs)
    # No '(after Ns)' suffix on any PASS line either.
    assert not any("(after " in m for m in msgs)
    # And we never slept, since each probe passed first try.
    sleep_mock.assert_not_called()
    # The HTTP-redirect PASS line is exactly the legacy shape.
    assert ("  PASS: HTTP redirect to HTTPS", "info") in lines


# ── poll=False default: stable checks probe once ──────────────────────


def test_phase_verify_stable_checks_probe_once_when_failing():
    """The three stable checks (containers, cron, database) keep the
    legacy single-probe behavior. When they fail, run_remote is
    called exactly once for each, no 'Waiting...' line is emitted,
    and time.sleep is never invoked for them."""
    ssh = MagicMock()
    log, lines = _capture_log()

    call_log: list[str] = []

    def fake_run_remote(_ssh, command, *args, **kwargs):
        call_log.append(command)
        # Stable checks: fail. Network-dependent checks: pass on first
        # probe (so polling doesn't sleep either).
        if "docker compose" in command and "ps" in command:
            return 1, "no such file"
        if "crontab" in command:
            return 1, ""
        if "curl -sI http://" in command:
            return 0, "HTTP/1.1 301 Moved"
        if "curl -sI https://" in command:
            return 0, "HTTP/1.1 200 OK"
        if "openssl s_client" in command:
            return 0, "notAfter=Jan 1 2027 GMT"
        if "curl -sL https://" in command:
            return 0, "<html>EspoCRM login</html>"
        raise AssertionError(f"unexpected command: {command}")

    sleep_mock = MagicMock()
    monotonic_clock = [0.0]

    def fake_monotonic():
        return monotonic_clock[0]

    with patch.object(ssh_deploy, "run_remote", side_effect=fake_run_remote), \
         patch.object(ssh_deploy.time, "sleep", sleep_mock), \
         patch.object(ssh_deploy.time, "monotonic", side_effect=fake_monotonic):
        overall, results = ssh_deploy.phase_verify(ssh, "crm.example.com", log)

    assert overall is False
    by_name = {r["check"]: r for r in results}
    assert by_name["Docker containers running"]["passed"] is False
    assert by_name["Cron job configured"]["passed"] is False
    # The two docker compose ps probes for containers and database
    # occur once each, plus one crontab probe — three total stable
    # probes, each called once.
    docker_ps_calls = [
        c for c in call_log if "docker compose" in c and "ps" in c
    ]
    assert len(docker_ps_calls) == 2  # containers + database
    crontab_calls = [c for c in call_log if "crontab" in c]
    assert len(crontab_calls) == 1
    # No 'Waiting...' lines for the stable failures.
    msgs = _msgs(lines)
    assert not any(
        "Waiting for Docker containers running" in m for m in msgs
    )
    assert not any("Waiting for Cron job configured" in m for m in msgs)
    assert not any("Waiting for Database connectivity" in m for m in msgs)
    # Sleep is never called — network checks pass first try, stable
    # checks don't poll.
    sleep_mock.assert_not_called()


# ── phase_post_install: cert expiry read from disk ────────────────────


def _make_self_hosted_config(**overrides) -> SelfHostedConfig:
    defaults = {
        "ssh_host": "1.2.3.4",
        "ssh_port": 22,
        "ssh_username": "root",
        "ssh_credential": "ssh-secret",
        "ssh_auth_type": "password",
        "domain": "crm.example.com",
        "letsencrypt_email": "ops@example.com",
        "db_password": "db-app-password",
        "db_root_password": "db-root-secret",
        "admin_username": "admin",
        "admin_password": "admin-secret",
        "admin_email": "admin@example.com",
    }
    defaults.update(overrides)
    return SelfHostedConfig(**defaults)


def test_phase_post_install_reads_cert_from_disk():
    """phase_post_install reads the cert via openssl x509 -in
    /etc/letsencrypt/live/{domain}/fullchain.pem, not via the live
    SSL handshake on port 443."""
    ssh = MagicMock()
    log, _ = _capture_log()
    config = _make_self_hosted_config()
    captured: list[str] = []

    def fake_run_remote(_ssh, command, *args, **kwargs):
        captured.append(command)
        if "docker compose" in command and "ps" in command:
            return 0, "espocrm-nginx Up"
        if "chown -R www-data" in command:
            return 0, ""
        if "crmbuilder_write_test" in command:
            return 0, ""
        if "crontab" in command:
            return 0, "* * * * * espocrm-cron"
        if "openssl x509 -in" in command:
            return 0, "notAfter=Aug  2 12:00:00 2026 GMT"
        raise AssertionError(f"unexpected command: {command}")

    with patch.object(ssh_deploy, "run_remote", side_effect=fake_run_remote):
        success, error, cert_expiry = ssh_deploy.phase_post_install(
            ssh, config, log
        )

    assert success is True
    assert error == ""
    assert cert_expiry == "2026-08-02"

    cert_path = (
        "/etc/letsencrypt/live/crm.example.com/fullchain.pem"
    )
    expected_re = re.compile(
        r"openssl x509 -in "
        + re.escape(cert_path)
        + r" -noout -enddate"
    )
    assert any(expected_re.search(c) for c in captured), captured
    assert not any("openssl s_client" in c for c in captured), captured


def test_phase_post_install_logs_path_on_cert_read_failure():
    """When the cert file can't be read, the warning message includes
    the file path and the exit code."""
    ssh = MagicMock()
    log, lines = _capture_log()
    config = _make_self_hosted_config()

    def fake_run_remote(_ssh, command, *args, **kwargs):
        if "docker compose" in command and "ps" in command:
            return 0, "espocrm-nginx Up"
        if "chown -R www-data" in command:
            return 0, ""
        if "crmbuilder_write_test" in command:
            return 0, ""
        if "crontab" in command:
            return 0, "* * * * * espocrm-cron"
        if "openssl x509 -in" in command:
            return 2, "No such file or directory"
        raise AssertionError(f"unexpected command: {command}")

    with patch.object(ssh_deploy, "run_remote", side_effect=fake_run_remote):
        ssh_deploy.phase_post_install(ssh, config, log)

    cert_path = (
        "/etc/letsencrypt/live/crm.example.com/fullchain.pem"
    )
    msgs = _msgs(lines)
    assert any(
        cert_path in m and "exit code 2" in m and "WARNING" in m
        for m in msgs
    ), msgs


# ── phase_post_install: custom-tree ownership + writability (REQ-328/329) ──


def test_phase_post_install_chowns_custom_tree_to_www_data():
    """REQ-328: post-install chowns the custom metadata tree to www-data so a
    fresh instance cannot silently block custom-entity creation."""
    ssh = MagicMock()
    log, _ = _capture_log()
    config = _make_self_hosted_config()
    captured: list[str] = []

    def fake_run_remote(_ssh, command, *args, **kwargs):
        captured.append(command)
        if "docker compose" in command and "ps" in command:
            return 0, "espocrm-nginx Up"
        if "chown -R www-data" in command:
            return 0, ""
        if "crmbuilder_write_test" in command:
            return 0, ""
        if "crontab" in command:
            return 0, "* * * * * espocrm-cron"
        if "openssl x509 -in" in command:
            return 0, "notAfter=Aug  2 12:00:00 2026 GMT"
        raise AssertionError(f"unexpected command: {command}")

    with patch.object(ssh_deploy, "run_remote", side_effect=fake_run_remote):
        success, error, _ = ssh_deploy.phase_post_install(ssh, config, log)

    assert success is True and error == ""
    assert any(
        "chown -R www-data:www-data /var/www/html/custom" in c
        for c in captured
    ), captured


def test_phase_post_install_aborts_when_custom_dir_unwritable():
    """REQ-329: if the custom metadata directory is not writable by www-data,
    the deploy fails fast with a diagnostic naming the path and the remedy."""
    ssh = MagicMock()
    log, _ = _capture_log()
    config = _make_self_hosted_config()

    def fake_run_remote(_ssh, command, *args, **kwargs):
        if "docker compose" in command and "ps" in command:
            return 0, "espocrm-nginx Up"
        if "chown -R www-data" in command:
            return 0, ""
        if "crmbuilder_write_test" in command:
            return 1, "Permission denied"  # still not writable
        raise AssertionError(f"unexpected command: {command}")

    with patch.object(ssh_deploy, "run_remote", side_effect=fake_run_remote):
        success, error, cert = ssh_deploy.phase_post_install(ssh, config, log)

    assert success is False
    assert cert is None
    assert "/var/www/html/custom/Espo/Custom/Resources" in error
    assert "www-data" in error
    assert "chown" in error  # the remedy


def test_phase_post_install_returns_none_expiry_on_read_failure():
    """A failed cert read still completes the phase successfully (it's
    a warning, not a fatal error) but returns None as the cert_expiry."""
    ssh = MagicMock()
    log, _ = _capture_log()
    config = _make_self_hosted_config()

    def fake_run_remote(_ssh, command, *args, **kwargs):
        if "docker compose" in command and "ps" in command:
            return 0, "espocrm-nginx Up"
        if "chown -R www-data" in command:
            return 0, ""
        if "crmbuilder_write_test" in command:
            return 0, ""
        if "crontab" in command:
            return 0, "* * * * * espocrm-cron"
        if "openssl x509 -in" in command:
            return 2, ""
        raise AssertionError(f"unexpected command: {command}")

    with patch.object(ssh_deploy, "run_remote", side_effect=fake_run_remote):
        result = ssh_deploy.phase_post_install(ssh, config, log)

    assert result == (True, "", None)
