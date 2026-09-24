"""The five provisioning steps, absorbed from version 1 — PI-556 (REQ-638).

No server is reached and no time passes: :func:`run_remote` is replaced, and
the module's ``time.sleep`` / ``time.monotonic`` are driven by the test so the
polling checks run instantly.

**Where the fixtures come from.** The command output below was carried across
from version 1's own tests for the same steps and from the commands themselves;
it was *not* read off a live server. Lesson LRN-007 says a fixture written from
one side agrees with the code instead of checking it, so these tests hold the
step's decisions — what it reports, what it refuses, what it masks — rather
than claiming the server's answers are proven real. Proving the steps against a
real server is a provisioning run, which is the product owner's step.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from crmbuilder_v2.deploy import ssh as ssh_module
from crmbuilder_v2.deploy.ssh import SelfHostedConfig


def _capture_log() -> tuple[object, list[tuple[str, str]]]:
    """Return ``(log, lines)``; each line is ``(message, level)``."""
    lines: list[tuple[str, str]] = []

    def log(message: str, level: str) -> None:
        lines.append((message, level))

    return log, lines


def _messages(lines: list[tuple[str, str]]) -> list[str]:
    return [message for message, _level in lines]


def _config(**overrides) -> SelfHostedConfig:
    fields = {
        "ssh_host": "203.0.113.10",
        "ssh_port": 22,
        "ssh_username": "root",
        "ssh_credential": "/tmp/deploy.key",
        "ssh_auth_type": "key",
        "domain": "crm.example.com",
        "letsencrypt_email": "ops@example.com",
        "db_password": "db-app-password",
        "db_root_password": "db-root-secret",
        "admin_username": "admin",
        "admin_password": "admin-secret",
        "admin_email": "admin@example.com",
    }
    fields.update(overrides)
    return SelfHostedConfig(**fields)


@pytest.fixture
def instant_clock():
    """Make the polling checks run without waiting.

    ``monotonic`` advances by the sleep the step asked for, so a step that
    polls to its deadline reaches it in as many attempts as it really would.
    """
    now = [0.0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    with patch.object(ssh_module.time, "sleep", side_effect=sleep), patch.object(
        ssh_module.time, "monotonic", side_effect=lambda: now[0]
    ):
        yield now


# ---------------------------------------------------------------------------
# Masking a password before it is logged
# ---------------------------------------------------------------------------

def test_mask_credentials_replaces_every_password_with_its_name():
    config = _config()
    command = (
        f"install.sh --admin-password={config.admin_password} "
        f"--db-password={config.db_password} "
        f"--db-root-password={config.db_root_password}"
    )

    masked = ssh_module.mask_credentials(command, config)

    assert config.admin_password not in masked
    assert config.db_password not in masked
    assert config.db_root_password not in masked
    assert "[admin_password]" in masked
    assert "[db_password]" in masked
    assert "[db_root_password]" in masked


def test_mask_credentials_replaces_the_longest_password_first():
    """A password that contains another one must not leave the shorter one's
    tail behind."""
    config = _config(db_password="secret", admin_password="secret-and-more")
    command = "install.sh --admin-password=secret-and-more --db-password=secret"

    masked = ssh_module.mask_credentials(command, config)

    assert "secret" not in masked
    assert "--admin-password=[admin_password]" in masked
    assert "--db-password=[db_password]" in masked


def test_mask_credentials_ignores_an_empty_password():
    """Replacing the empty string would rewrite the whole command."""
    config = _config(db_password="")

    masked = ssh_module.mask_credentials("install.sh --db-password=", config)

    assert masked == "install.sh --db-password="


# ---------------------------------------------------------------------------
# Preparing the machine
# ---------------------------------------------------------------------------

def _prep_runner(first_boot="0", idle=0, fail_at=None):
    """A stand-in for ``run_remote`` shaped by the 09-23-26 live proof (CNV-398)."""
    seen: list[str] = []

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        seen.append(command)
        if "cloud-init status --wait" in command:
            return 0, f"first-boot:{first_boot}"
        if "python3 -" in command:
            return idle, ""
        if fail_at is not None and "apt-get" in command and len(seen) - 2 == fail_at:
            return 100, "E: Could not get lock /var/lib/apt/lists/lock. It is held by process 1230 (apt-get)"
        return 0, ""

    return fake_run_remote, seen


def test_server_prep_waits_for_first_boot_setup_before_any_package_command():
    """PI-567 (REQ-644): the live proof met apt-get update while first-boot
    setup held the package-list lock. The wait comes first, then packages."""
    log, lines = _capture_log()
    runner, seen = _prep_runner()
    with patch.object(ssh_module, "run_remote", side_effect=runner):
        assert ssh_module.phase_server_prep(MagicMock(), log) == (True, "")
    assert "cloud-init status --wait" in seen[0] and seen[0].startswith("timeout 600 ")
    assert seen[1].startswith("timeout 600 python3 - ") and "/var/lib/apt/lists/lock" in seen[1]
    first_apt = next(i for i, c in enumerate(seen) if "apt-get" in c)
    assert first_apt == 2
    messages = _messages(lines)
    assert "Waiting for the server's first-boot setup to finish..." in messages
    assert any(m.startswith("First-boot setup finished after ") for m in messages)


def test_first_boot_setup_that_never_finishes_fails_naming_it_and_try_again():
    log, _lines = _capture_log()
    runner, seen = _prep_runner(first_boot="124")
    with patch.object(ssh_module, "run_remote", side_effect=runner):
        ok, error = ssh_module.phase_server_prep(MagicMock(), log)
    assert ok is False and "first-boot setup did not finish within 10 minutes" in error
    assert "Try again" in error and "lock" not in error
    assert not any("apt-get update" in c for c in seen)


def test_package_updates_still_running_fail_naming_first_boot_not_apt():
    log, _lines = _capture_log()
    runner, seen = _prep_runner(idle=124)
    with patch.object(ssh_module, "run_remote", side_effect=runner):
        ok, error = ssh_module.phase_server_prep(MagicMock(), log)
    assert ok is False and "first-boot package updates were still running" in error
    assert not any("apt-get update" in c for c in seen)


def test_first_boot_finished_with_recoverable_errors_carries_on():
    log, lines = _capture_log()
    runner, _seen = _prep_runner(first_boot="2")
    with patch.object(ssh_module, "run_remote", side_effect=runner):
        assert ssh_module.phase_server_prep(MagicMock(), log) == (True, "")
    runner, _seen = _prep_runner(first_boot="1")
    with patch.object(ssh_module, "run_remote", side_effect=runner):
        assert ssh_module.phase_server_prep(MagicMock(), log) == (True, "")
    assert any("reported an error" in m for m in _messages(lines))


def test_every_package_command_still_waits_for_the_installer_lock():
    log, _lines = _capture_log()
    runner, seen = _prep_runner()
    with patch.object(ssh_module, "run_remote", side_effect=runner):
        ssh_module.phase_server_prep(MagicMock(), log)
    package_commands = [c for c in seen if "apt-get" in c]
    assert package_commands and all("DPkg::Lock::Timeout=600" in c for c in package_commands)


def test_server_prep_stops_at_the_first_command_that_fails():
    log, _lines = _capture_log()
    seen: list[str] = []

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        seen.append(command)
        if "cloud-init" in command:
            return 0, "first-boot:0"
        return (0, "") if len(seen) <= 3 else (100, "")

    with patch.object(ssh_module, "run_remote", side_effect=fake_run_remote):
        succeeded, error = ssh_module.phase_server_prep(MagicMock(), log)

    assert succeeded is False
    assert "exit 100" in error
    assert len(seen) == 4, "the step kept going after a command failed"


# ---------------------------------------------------------------------------
# Installing the platform
# ---------------------------------------------------------------------------

def test_install_never_writes_a_password_to_the_log():
    """The command carries three passwords; what reaches the log carries none."""
    config = _config()
    log, lines = _capture_log()

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        return 0, ""

    with patch.object(ssh_module, "run_remote", side_effect=fake_run_remote):
        succeeded, error = ssh_module.phase_install_espocrm(MagicMock(), config, log)

    assert (succeeded, error) == (True, "")
    logged = "\n".join(_messages(lines))
    for secret in (config.admin_password, config.db_password, config.db_root_password):
        assert secret not in logged


def test_install_asks_for_a_terminal_only_for_the_installer():
    """The platform's installer needs a terminal; fetching it does not."""
    config = _config()
    log, _lines = _capture_log()
    seen: list[tuple[str, bool]] = []

    def fake_run_remote(_ssh, command, *_args, **kwargs):
        seen.append((command, kwargs.get("get_pty", False)))
        return 0, ""

    with patch.object(ssh_module, "run_remote", side_effect=fake_run_remote):
        ssh_module.phase_install_espocrm(MagicMock(), config, log)

    fetch, install = seen
    assert "wget" in fetch[0] and fetch[1] is False
    assert "install.sh" in install[0] and install[1] is True


def test_install_reports_a_failed_download_without_running_the_installer():
    config = _config()
    log, _lines = _capture_log()
    seen: list[str] = []

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        seen.append(command)
        return 1, ""

    with patch.object(ssh_module, "run_remote", side_effect=fake_run_remote):
        succeeded, error = ssh_module.phase_install_espocrm(MagicMock(), config, log)

    assert succeeded is False
    assert error == "Failed to download EspoCRM installer"
    assert not any("install.sh -y" in c for c in seen)


# ---------------------------------------------------------------------------
# Correcting ownership and reading the certificate
# ---------------------------------------------------------------------------

def _post_install_responses(**overrides):
    """A server on which every post-install command succeeds.

    Ordered most specific first: every command this step runs inside the
    container also contains ``docker compose``, so that marker must be matched
    last or it answers for all of them.
    """
    responses = {
        "crmbuilder_write_test": (0, ""),
        "chown -R www-data": (0, ""),
        "crontab": (0, "* * * * * docker compose -f ... espocrm-cron"),
        "openssl x509 -in": (0, "notAfter=Aug  2 12:00:00 2026 GMT"),
        "docker compose": (0, "espocrm-nginx   Up   0.0.0.0:80->80/tcp"),
    }
    responses.update(overrides)
    return responses


def _post_install_runner(responses, seen: list[str]):
    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        seen.append(command)
        for marker, result in responses.items():
            if marker in command:
                return result
        raise AssertionError(f"unexpected command: {command}")

    return fake_run_remote


def test_post_install_reads_the_certificate_from_disk_not_through_the_web_server():
    config = _config()
    log, _lines = _capture_log()
    seen: list[str] = []

    with patch.object(
        ssh_module, "run_remote",
        side_effect=_post_install_runner(_post_install_responses(), seen),
    ):
        succeeded, error, expiry = ssh_module.phase_post_install(
            MagicMock(), config, log
        )

    assert (succeeded, error, expiry) == (True, "", "2026-08-02")
    assert any(
        "openssl x509 -in /var/www/espocrm/data/nginx/ssl/live/crm.example.com/"
        "fullchain.pem" in c
        for c in seen
    ), seen
    assert not any("openssl s_client" in c for c in seen), seen


def test_post_install_falls_back_to_the_system_certificate_folder():
    """The installer keeps the certificate inside its own installation folder
    (read off the CBM test instance); an older layout used the system folder."""
    config = _config()
    log, _lines = _capture_log()
    seen: list[str] = []
    responses = {
        "/var/www/espocrm/data/nginx/ssl": (1, "No such file"),
        "/etc/letsencrypt/live": (0, "notAfter=Aug  2 12:00:00 2026 GMT"),
    }
    responses.update(_post_install_responses())
    del responses["openssl x509 -in"]

    with patch.object(
        ssh_module, "run_remote", side_effect=_post_install_runner(responses, seen)
    ):
        succeeded, error, expiry = ssh_module.phase_post_install(
            MagicMock(), config, log
        )

    assert (succeeded, error, expiry) == (True, "", "2026-08-02")
    tried = [c for c in seen if "openssl x509 -in" in c]
    assert "/var/www/espocrm/data/nginx/ssl" in tried[0]
    assert "/etc/letsencrypt/live" in tried[1]


def test_install_quotes_every_value_for_the_shell():
    """A quote or a space in a value cannot break or change the command, and
    a password holding a quote still never reaches the log."""
    config = _config()
    config.admin_password = "it's; rm -rf /"
    log, lines = _capture_log()
    seen: list[str] = []

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        seen.append(command)
        return 0, ""

    with patch.object(ssh_module, "run_remote", side_effect=fake_run_remote):
        ssh_module.phase_install_espocrm(MagicMock(), config, log)

    install = seen[1]
    assert "--admin-password='it'\"'\"'s; rm -rf /'" in install
    logged = "\n".join(_messages(lines))
    assert "rm -rf" not in logged
    assert "[admin_password]" in logged


def test_post_install_gives_the_custom_metadata_tree_to_the_web_server_user():
    config = _config()
    log, _lines = _capture_log()
    seen: list[str] = []

    with patch.object(
        ssh_module, "run_remote",
        side_effect=_post_install_runner(_post_install_responses(), seen),
    ):
        ssh_module.phase_post_install(MagicMock(), config, log)

    chown = [c for c in seen if "chown -R www-data:www-data" in c]
    assert chown, seen
    assert "/var/www/html/custom" in chown[0]
    assert seen.index(chown[0]) < next(
        i for i, c in enumerate(seen) if "crmbuilder_write_test" in c
    ), "ownership must be corrected before it is checked"


def test_post_install_stops_with_a_remedy_when_the_web_server_user_cannot_write():
    """The ownership command's own exit status is not the verdict — this is."""
    config = _config()
    log, _lines = _capture_log()
    seen: list[str] = []
    responses = _post_install_responses(**{"crmbuilder_write_test": (1, "")})

    with patch.object(
        ssh_module, "run_remote", side_effect=_post_install_runner(responses, seen)
    ):
        succeeded, error, expiry = ssh_module.phase_post_install(
            MagicMock(), config, log
        )

    assert succeeded is False
    assert expiry is None
    assert "not writable by the web server" in error
    assert "Remedy:" in error
    assert "chown -R www-data:www-data" in error


def test_post_install_stops_when_the_containers_are_not_running():
    config = _config()
    log, _lines = _capture_log()
    seen: list[str] = []
    responses = _post_install_responses(**{"docker compose": (1, "")})

    with patch.object(
        ssh_module, "run_remote", side_effect=_post_install_runner(responses, seen)
    ):
        succeeded, error, expiry = ssh_module.phase_post_install(
            MagicMock(), config, log
        )

    assert (succeeded, error, expiry) == (False, "Docker containers not running", None)


def test_post_install_succeeds_without_an_expiry_when_the_certificate_cannot_be_read():
    """A certificate that cannot be read is a warning naming the path and the
    exit code, not a failed step."""
    config = _config()
    log, lines = _capture_log()
    seen: list[str] = []
    responses = _post_install_responses(**{"openssl x509 -in": (2, "")})

    with patch.object(
        ssh_module, "run_remote", side_effect=_post_install_runner(responses, seen)
    ):
        succeeded, error, expiry = ssh_module.phase_post_install(
            MagicMock(), config, log
        )

    assert (succeeded, error, expiry) == (True, "", None)
    warning = "\n".join(_messages(lines))
    assert "/etc/letsencrypt/live/crm.example.com/fullchain.pem" in warning
    assert "exit code 2" in warning


def test_post_install_warns_rather_than_guessing_when_the_expiry_will_not_parse():
    config = _config()
    log, lines = _capture_log()
    seen: list[str] = []
    responses = _post_install_responses(
        **{"openssl x509 -in": (0, "notAfter=whenever")}
    )

    with patch.object(
        ssh_module, "run_remote", side_effect=_post_install_runner(responses, seen)
    ):
        succeeded, _error, expiry = ssh_module.phase_post_install(
            MagicMock(), config, log
        )

    assert succeeded is True
    assert expiry is None
    assert any("Could not parse cert expiry" in m for m in _messages(lines))


# ---------------------------------------------------------------------------
# Verifying the result
# ---------------------------------------------------------------------------

def _verify_runner(network_queues: dict[str, list[tuple[int, str]]]):
    """A server whose settled checks pass and whose network checks follow a
    queue of answers, the last repeating."""
    counts: dict[str, int] = dict.fromkeys(network_queues, 0)

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        if "docker compose" in command:
            if "mysql" in command or "mariadb" in command:
                return 0, "espocrm-db   Up   3306/tcp"
            return 0, "espocrm-nginx   Up   0.0.0.0:443->443/tcp"
        if "crontab" in command:
            return 0, "* * * * * docker compose -f ... espocrm-cron"
        for marker, queue in network_queues.items():
            if marker in command:
                index = min(counts[marker], len(queue) - 1)
                counts[marker] += 1
                return queue[index]
        raise AssertionError(f"unexpected command: {command}")

    return fake_run_remote, counts


_ALL_NETWORK_CHECKS_PASS = {
    "curl -sI http://": [(0, "HTTP/1.1 301 Moved Permanently")],
    "curl -sI https://": [(0, "HTTP/1.1 200 OK")],
    "openssl s_client": [(0, "notBefore=Aug  2 2026 GMT\nnotAfter=Oct 31 2026 GMT")],
    "curl -sL https://": [(0, "<html><title>EspoCRM</title></html>")],
}


def test_verify_passes_every_check_on_a_healthy_server(instant_clock):
    log, lines = _capture_log()
    runner, _counts = _verify_runner(
        {k: list(v) for k, v in _ALL_NETWORK_CHECKS_PASS.items()}
    )

    with patch.object(ssh_module, "run_remote", side_effect=runner):
        overall, results = ssh_module.phase_verify(MagicMock(), "crm.example.com", log)

    assert overall is True
    assert len(results) == 7
    assert all(result["passed"] for result in results)
    assert not any("Waiting for" in m for m in _messages(lines)), (
        "a run that needed no warm-up must keep a clean log shape"
    )


def test_verify_polls_a_network_check_until_the_web_server_answers(instant_clock):
    """The web server needs a moment after the installer finishes."""
    log, lines = _capture_log()
    queues = {k: list(v) for k, v in _ALL_NETWORK_CHECKS_PASS.items()}
    queues["curl -sI https://"] = [(0, ""), (0, ""), (0, "HTTP/1.1 200 OK")]
    runner, counts = _verify_runner(queues)

    with patch.object(ssh_module, "run_remote", side_effect=runner):
        overall, results = ssh_module.phase_verify(MagicMock(), "crm.example.com", log)

    assert overall is True
    assert counts["curl -sI https://"] == 3
    messages = _messages(lines)
    assert any("Waiting for HTTPS response to come up" in m for m in messages)
    assert any(m.startswith("  PASS: HTTPS response (after ") for m in messages)


def test_verify_records_a_network_check_that_never_comes_up_as_failed(instant_clock):
    log, lines = _capture_log()
    queues = {k: list(v) for k, v in _ALL_NETWORK_CHECKS_PASS.items()}
    queues["curl -sI https://"] = [(7, "curl: (7) Failed to connect")]
    runner, _counts = _verify_runner(queues)

    with patch.object(ssh_module, "run_remote", side_effect=runner):
        overall, results = ssh_module.phase_verify(MagicMock(), "crm.example.com", log)

    assert overall is False
    failed = [r for r in results if not r["passed"]]
    assert [r["check"] for r in failed] == ["HTTPS response"]
    assert "Failed to connect" in failed[0]["detail"]
    assert any("timed out after 60s" in m for m in _messages(lines))


def test_verify_probes_a_settled_check_once_even_when_it_fails(instant_clock):
    """Polling the schedule would only repeat the same answer."""
    log, _lines = _capture_log()
    attempts: list[str] = []

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        attempts.append(command)
        if "crontab" in command:
            return 1, ""
        if "docker compose" in command:
            if "mysql" in command or "mariadb" in command:
                return 0, "espocrm-db   Up"
            return 0, "espocrm-nginx   Up"
        for marker, queue in _ALL_NETWORK_CHECKS_PASS.items():
            if marker in command:
                return queue[0]
        raise AssertionError(f"unexpected command: {command}")

    with patch.object(ssh_module, "run_remote", side_effect=fake_run_remote):
        overall, results = ssh_module.phase_verify(MagicMock(), "crm.example.com", log)

    assert overall is False
    assert [c for c in attempts if "crontab" in c] == [
        "crontab -l 2>/dev/null | grep espocrm"
    ]
    cron = next(r for r in results if r["check"] == "Cron job configured")
    assert cron["passed"] is False


def test_verify_never_shows_the_checks_own_output_in_the_log(instant_clock):
    """A check judges its output rather than showing it, so a command that
    prints a certificate or a page body does not fill the run log."""
    log, lines = _capture_log()
    runner, _counts = _verify_runner(
        {k: list(v) for k, v in _ALL_NETWORK_CHECKS_PASS.items()}
    )

    with patch.object(ssh_module, "run_remote", side_effect=runner) as mocked:
        ssh_module.phase_verify(MagicMock(), "crm.example.com", log)

    assert all(len(call.args) == 2 for call in mocked.call_args_list), (
        "a verification check must not be given the log callback"
    )
    assert not any("<html>" in m for m in _messages(lines))


def test_run_remote_writes_input_to_standard_input_and_closes_it():
    """How a password reaches a command without being on its command line."""
    ssh = MagicMock()
    stdin, stdout, stderr = MagicMock(), MagicMock(), MagicMock()
    stdout.__iter__.return_value = iter(["done\n"])
    stderr.__iter__.return_value = iter([])
    stdout.channel.recv_exit_status.return_value = 0
    ssh.exec_command.return_value = (stdin, stdout, stderr)

    exit_code, output = ssh_module.run_remote(ssh, "cmd", input_text="pw\n")

    assert (exit_code, output) == (0, "done")
    stdin.write.assert_called_once_with("pw\n")
    stdin.channel.shutdown_write.assert_called_once()
    assert "pw" not in ssh.exec_command.call_args.args[0]


# ---------------------------------------------------------------------------
# Installing without a certificate — PI-571 (REQ-648)
# ---------------------------------------------------------------------------

def test_install_without_a_certificate_uses_the_plain_web_mode():
    config = _config()
    log, _lines = _capture_log()
    seen: list[str] = []

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        seen.append(command)
        return 0, ""

    with patch.object(ssh_module, "run_remote", side_effect=fake_run_remote):
        assert ssh_module.phase_install_espocrm(MagicMock(), config, log, secure=False) == (True, "")

    install = seen[-1]
    assert "--ssl" not in install and "--letsencrypt" not in install and "--email" not in install
    assert "--domain=crm.example.com" in install and "--clean" in install


def test_post_install_without_a_certificate_does_not_look_for_one():
    config = _config()
    log, lines = _capture_log()

    with patch.object(ssh_module, "run_remote", side_effect=lambda *_a, **_k: (0, "espocrm Up")):
        assert ssh_module.phase_post_install(MagicMock(), config, log, secure=False) == (True, "", None)
    assert not any("certificate" in m.lower() for m in _messages(lines))


def test_verify_without_a_certificate_checks_the_crm_on_the_server(instant_clock):
    log, _lines = _capture_log()
    seen: list[str] = []

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        seen.append(command)
        if "127.0.0.1" in command:
            return 0, "HTTP/1.1 200 OK"
        return 0, "espocrm-db Up"

    with patch.object(ssh_module, "run_remote", side_effect=fake_run_remote):
        overall, results = ssh_module.phase_verify(MagicMock(), "crm.example.com", log, secure=False)

    assert overall is True
    assert [r["check"] for r in results] == [
        "Docker containers running", "CRM answers on the server", "Database connectivity",
    ]
    assert not any("https://" in c or "s_client" in c for c in seen)
    assert "-H 'Host: crm.example.com' http://127.0.0.1" in seen[1]


def test_the_lock_wait_waits_while_a_lock_is_held_and_not_after(tmp_path):
    """Run on this machine against lock files it creates: the wait returns at
    once when nothing holds them, and waits while another process holds one."""
    import fcntl
    import os
    import subprocess
    import sys
    import time

    locks = [tmp_path / "lists-lock", tmp_path / "dpkg-lock"]
    for lock in locks:
        lock.touch()

    def wait(limit: float) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-", *map(str, locks)], input=ssh_module.PACKAGE_IDLE_SCRIPT,
            text=True, timeout=limit,
        )

    assert wait(5).returncode == 0

    holder = subprocess.Popen(
        [sys.executable, "-c",
         "import fcntl,os,time,sys; fd=os.open(sys.argv[1],os.O_RDWR); "
         "fcntl.lockf(fd,fcntl.LOCK_EX); print('held',flush=True); time.sleep(4)",
         str(locks[0])],
        stdout=subprocess.PIPE, text=True,
    )
    assert holder.stdout.readline().strip() == "held"
    started = time.monotonic()
    assert wait(15).returncode == 0
    assert time.monotonic() - started >= 2, "the wait did not wait for the held lock"
    holder.wait()
    assert os.path.exists(locks[0]) and fcntl  # the lock files are left in place


# ---------------------------------------------------------------------------
# Keeping progress output out of the deploy log — PI-571 (REQ-652)
# ---------------------------------------------------------------------------

#: Raw lines from deploy run DEP-003's log (09-23-26), escape codes and all:
#: a download spinner frame, a completion mark (twice, as the tool redraws
#: it), and a frame header ending in a carriage return.
_DEP003_RAW = [' \x1b[33m⠏\x1b[0m Image espocrm/espocrm:fpm [\x1b[32m⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿\x1b[0m] Pulling                 \x1b[34m26.9s\x1b[0m\r', ' \x1b[32m✔\x1b[0m Image nginx:latest                              \x1b[32mPulled\x1b[0m                  \x1b[34m18.6s\x1b[0m\r', ' \x1b[32m✔\x1b[0m Image nginx:latest                              \x1b[32mPulled\x1b[0m                  \x1b[34m18.6s\x1b[0m\r', '\x1b[?25h\x1b[?25l\x1b[3A\x1b[0G[+] up 28/30\r']

#: Lines from the same run's package steps, as they arrived.
_APT_NOISE = (
    "(Reading database ... (Reading database ... 5% (Reading database ... 10% "
    "(Reading database ... 15% (Reading database ... 100% (Reading database ... 75083 files)",
    "0% [Working] Hit:1 http://mirrors.digitalocean.com/ubuntu noble InRelease",
    "Scanning processes... [======                    ] Scanning processes... [=======  ]",
    "     0K .......... .......... ...... 100% 19.5M=0.001s",
)


def test_progress_frames_are_hidden_and_counted_once():
    log, lines = _capture_log()
    ssh = MagicMock()
    stdout = MagicMock()
    stdout.__iter__.return_value = iter(
        [line + "\n" for line in _DEP003_RAW]
        + [line + "\n" for line in _APT_NOISE]
        + ["The installation has been successfully completed.\n"]
    )
    stdout.channel.recv_exit_status.return_value = 0
    stderr = MagicMock()
    stderr.__iter__.return_value = iter([])
    ssh.exec_command.return_value = (MagicMock(), stdout, stderr)

    code, output = ssh_module.run_remote(ssh, "bash install.sh", log)

    shown = _messages(lines)
    assert len(shown) == 3
    assert shown[0].split() == ["\u2714", "Image", "nginx:latest", "Pulled", "18.6s"]  # codes gone, shown once
    assert shown[1:] == [
        "The installation has been successfully completed.",
        "(7 progress lines not shown)",
    ]
    # What the step reads to judge its command is untouched.
    assert code == 0 and output.split("\n")[0] == _DEP003_RAW[0]


def test_real_output_is_never_taken_for_progress():
    for line in (
        "The installation has been successfully completed.",
        "Get:1 http://mirrors.digitalocean.com/ubuntu noble-updates/main amd64 motd-news-config",
        "Setting up docker-ce (5:29.8.1-1~ubuntu.24.04~noble) ...",
        "E: Could not get lock /var/lib/apt/lists/lock. It is held by process 1230 (apt-get)",
        "Fetched 124 MB in 4s (34.8 MB/s)",
        "  PASS: Docker containers running",
    ):
        assert not ssh_module.is_progress_noise(line, set()), line


def test_clean_terminal_line_keeps_the_last_frame_without_codes():
    assert ssh_module.clean_terminal_line("\x1b[32mone\x1b[0m\rtwo\r") == "two"
    assert ssh_module.clean_terminal_line("plain") == "plain"
