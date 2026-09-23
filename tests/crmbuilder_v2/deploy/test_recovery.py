"""Rescuing a self-hosted instance — PI-562 (REQ-640) and PI-563 (REQ-641).

No server is reached: :func:`run_remote` is replaced throughout, and so is the
sign-in check. The entry-point tests use the real store through the ``v2_env``
fixture, so what they assert about stored credentials, backups and cleared
readings is read back out of the store.

**Where the fixtures come from.** Read off a real instance (the CBM test
instance, 9.3.6, on 09-23-26, read-only): the list of the platform's console
commands, which includes ``set-password``; where the installer keeps the
certificate (inside its installation folder); and that the installation folder
holds only bind-mounted data, no named volumes. Read from the platform's own
source: the set-password command's words ("Password for user '…' has been
changed.", "User '…' not found."), that it reads the password from standard
input, and that the installer's clean mode copies the installation to
``espocrm-backup`` beside the installer before deleting it. *Not* read off a
live instance: the exact output of a real set-password run, the installer's
copy-folder listing, and the shape of the sign-in answer's ``user.type``.
Lesson LRN-007 says a fixture written from one side agrees with the code
instead of checking it, so these tests hold the steps' decisions — what they
refuse, what they report, what they keep out of the log and what they write to
the store. Proving this against a real instance is the product owner's step.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.deploy import recovery
from crmbuilder_v2.deploy import upgrade as upgrade_module
from crmbuilder_v2.deploy.errors import DeployPhaseError
from crmbuilder_v2.segments.operate.repositories import (
    instance_deploy_config,
    instances,
)

CHANGED = "Enter a new password:\nPassword for user 'admin' has been changed."
STATE_PHP = "<?php\nreturn [\n  'version' => '9.3.6',\n];\n"


def _capture_log():
    lines: list[tuple[str, str]] = []

    def log(message: str, level: str) -> None:
        lines.append((message, level))

    return log, lines


def _logged(lines) -> str:
    return "\n".join(message for message, _level in lines)


# ---------------------------------------------------------------------------
# The password a reset will accept
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("password", "refused"),
    [
        ("correct horse", False),
        ("", True),
        (" leading", True),
        ("trailing ", True),
        ("two\nlines", True),
    ],
)
def test_a_password_the_platform_would_alter_is_refused(password, refused):
    assert bool(recovery.password_problem(password)) is refused


# ---------------------------------------------------------------------------
# Running the platform's own command
# ---------------------------------------------------------------------------

def test_the_password_goes_on_standard_input_never_on_a_command_line():
    log, lines = _capture_log()
    calls: list[tuple[str, dict]] = []

    def fake_run_remote(_ssh, command, *_args, **kwargs):
        calls.append((command, kwargs))
        return 0, CHANGED

    with patch.object(recovery, "run_remote", side_effect=fake_run_remote):
        ok, error = recovery.set_admin_password(MagicMock(), "admin", "s3cret!", log)

    assert (ok, error) == (True, "")
    command, kwargs = calls[0]
    assert "php command.php set-password admin" in command
    assert "s3cret!" not in command
    assert kwargs["input_text"] == "s3cret!\n"
    assert "s3cret!" not in _logged(lines)


def test_the_account_name_is_quoted_for_the_shell():
    log, _lines = _capture_log()
    seen: list[str] = []

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        seen.append(command)
        return 0, CHANGED

    with patch.object(recovery, "run_remote", side_effect=fake_run_remote):
        recovery.set_admin_password(MagicMock(), "a'b; reboot", "pw", log)

    assert seen[0].endswith("set-password 'a'\"'\"'b; reboot'")


def test_a_missing_account_is_reported_in_the_platforms_words():
    log, _lines = _capture_log()
    with patch.object(
        recovery, "run_remote", return_value=(1, "User 'ghost' not found.")
    ):
        ok, error = recovery.set_admin_password(MagicMock(), "ghost", "pw", log)

    assert ok is False
    assert "User 'ghost' not found." in error


def test_a_clean_exit_that_does_not_say_the_password_changed_is_not_a_reset():
    """Version 1's defect: a command that exits cleanly and changes nothing."""
    log, _lines = _capture_log()
    with patch.object(recovery, "run_remote", return_value=(0, "Enter a new password:")):
        ok, error = recovery.set_admin_password(MagicMock(), "admin", "pw", log)

    assert ok is False
    assert "not treated as done" in error


def test_no_account_is_chosen_for_the_operator():
    log, _lines = _capture_log()
    with patch.object(recovery, "run_remote") as run:
        ok, error = recovery.set_admin_password(MagicMock(), "", "pw", log)

    assert ok is False
    assert "none is chosen for you" in error
    run.assert_not_called()


# ---------------------------------------------------------------------------
# Proving the new password signs in
# ---------------------------------------------------------------------------

class _Answer:
    def __init__(self, status: int, body=None):
        self.status_code = status
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (_Answer(200, {"user": {"type": "admin"}}), True),
        (_Answer(200, {"user": {"type": "regular"}}), False),
        (_Answer(401), False),
        (_Answer(502), None),
        (_Answer(200), None),
    ],
)
def test_the_sign_in_check_tells_refused_from_unchecked(answer, expected):
    with patch.object(recovery.requests, "get", return_value=answer) as get:
        signed_in, _why = recovery.check_sign_in("https://crm.example.com/", "admin", "pw")

    assert signed_in is expected
    url = get.call_args.args[0]
    assert url == "https://crm.example.com/api/v1/App/user"


def test_an_instance_that_does_not_answer_is_unchecked():
    with patch.object(
        recovery.requests, "get", side_effect=recovery.requests.ConnectionError()
    ):
        signed_in, why = recovery.check_sign_in("https://crm.example.com", "a", "b")

    assert signed_in is None
    assert "did not answer" in why


# ---------------------------------------------------------------------------
# Driving a reset against a registered instance
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


@pytest.fixture
def provisioned_instance(v2_env):
    """An instance as a provisioning run leaves it: the recorded administrator
    password and the instance's sign-in password share one stored secret."""
    password_ref = secrets.put_secret("old-password")
    with session_scope() as session:
        instance = instances.create_instance(
            session,
            name="Rescue target",
            url="https://crm.example.com",
            vendor="espocrm",
            role="both",
            auth_method="basic",
            secret_ref=secrets.put_secret("admin"),
            secret_key_ref=password_ref,
        )
        identifier = instance["instance_identifier"]
        instance_deploy_config.upsert_deploy_config(
            session,
            identifier,
            scenario="self_hosted",
            ssh_host="203.0.113.10",
            ssh_port=22,
            ssh_username="root",
            ssh_auth_type="key",
            ssh_credential_ref=secrets.put_secret("PRIVATE KEY TEXT"),
            domain="crm.example.com",
            letsencrypt_email="ops@example.com",
            db_root_password_ref=secrets.put_secret("old-root-password"),
            db_password_ref=secrets.put_secret("old-db-password"),
            admin_username="admin",
            admin_password_ref=password_ref,
            current_espocrm_version="9.3.4",
        )
        instances.record_stamp_reading(
            session,
            identifier,
            standard_version="1.4.0",
            plan_fingerprint="abc123",
            read_at=None,
        )
    return identifier


@pytest.fixture
def fake_login():
    """Stand in for opening the remote login, so no server is reached."""
    with patch.object(upgrade_module, "connect_ssh", return_value=MagicMock()), patch.object(
        upgrade_module, "private_key_file"
    ) as key_file:
        key_file.return_value.__enter__.return_value = "/tmp/key"
        yield


def _instance(identifier: str) -> dict:
    with session_scope() as session:
        return instances.get_instance(session, identifier)


def _config(identifier: str) -> dict:
    with session_scope() as session:
        return instance_deploy_config.get_deploy_config(session, identifier)


def test_a_reset_stores_the_new_password_where_version_2_signs_in(
    provisioned_instance, fake_login
):
    log, lines = _capture_log()
    with patch.object(recovery, "run_remote", return_value=(0, CHANGED)):
        outcome = recovery.reset_admin_password(
            provisioned_instance, "admin", "new-password", log,
            sign_in=lambda *_: (True, ""),
        )

    assert outcome.succeeded is True, outcome.error
    assert outcome.signed_in is True
    instance = _instance(provisioned_instance)
    assert secrets.get_secret(instance["instance_secret_key_ref"]) == "new-password"
    config = _config(provisioned_instance)
    assert secrets.get_secret(config["admin_password_ref"]) == "new-password"
    assert "new-password" not in _logged(lines)


def test_a_password_that_does_not_sign_in_is_a_failed_reset(
    provisioned_instance, fake_login
):
    log, _lines = _capture_log()
    with patch.object(recovery, "run_remote", return_value=(0, CHANGED)):
        outcome = recovery.reset_admin_password(
            provisioned_instance, "admin", "new-password", log,
            sign_in=lambda *_: (False, "the instance refused the new password"),
        )

    assert outcome.succeeded is False
    assert outcome.platform_changed is True
    assert outcome.signed_in is False
    assert "did not work" in outcome.error


def test_a_reset_that_cannot_be_checked_is_reported_as_unchecked(
    provisioned_instance, fake_login
):
    log, _lines = _capture_log()
    with patch.object(recovery, "run_remote", return_value=(0, CHANGED)):
        outcome = recovery.reset_admin_password(
            provisioned_instance, "admin", "new-password", log,
            sign_in=lambda *_: (None, "the instance did not answer"),
        )

    assert outcome.succeeded is False
    assert outcome.signed_in is None
    assert "unchecked" in outcome.error
    # The old password is gone either way, so the store follows the instance.
    assert secrets.get_secret(_config(provisioned_instance)["admin_password_ref"]) == (
        "new-password"
    )


def test_resetting_another_account_leaves_version_2s_credential_alone(
    provisioned_instance, fake_login
):
    log, lines = _capture_log()
    with patch.object(recovery, "run_remote", return_value=(0, CHANGED)):
        outcome = recovery.reset_admin_password(
            provisioned_instance, "someone.else", "new-password", log,
            sign_in=lambda *_: (True, ""),
        )

    assert outcome.succeeded is True
    assert outcome.store_updated == []
    assert secrets.get_secret(_config(provisioned_instance)["admin_password_ref"]) == (
        "old-password"
    )
    assert "no stored credential was changed" in _logged(lines)


def test_a_store_write_that_fails_after_the_platform_changed_is_reported(
    provisioned_instance, fake_login
):
    log, _lines = _capture_log()

    def broken_store(*_args, **_kwargs):
        raise RuntimeError("store unavailable")

    with patch.object(recovery, "run_remote", return_value=(0, CHANGED)):
        outcome = recovery.reset_admin_password(
            provisioned_instance, "admin", "new-password", log,
            store_secret=broken_store, sign_in=lambda *_: (True, ""),
        )

    assert outcome.succeeded is False
    assert outcome.platform_changed is True
    assert "now has the new password" in outcome.error
    assert "writing it to the store failed" in outcome.error


def test_a_refused_reset_changes_nothing_in_the_store(provisioned_instance, fake_login):
    log, _lines = _capture_log()
    with patch.object(recovery, "run_remote", return_value=(1, "User 'admin' not found.")):
        outcome = recovery.reset_admin_password(
            provisioned_instance, "admin", "new-password", log,
            sign_in=lambda *_: pytest.fail("no sign-in after a refused reset"),
        )

    assert outcome.succeeded is False
    assert outcome.platform_changed is False
    assert secrets.get_secret(_config(provisioned_instance)["admin_password_ref"]) == (
        "old-password"
    )


# ---------------------------------------------------------------------------
# The rebuild's confirmation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("confirmation", "matches"),
    [
        ("crm.example.com", True),
        ("CRM.Example.com.", True),
        ("  crm.example.com ", True),
        ("crm-test.example.com", False),
        ("INST-001", False),
        ("", False),
        (None, False),
    ],
)
def test_only_the_domain_name_confirms_a_rebuild(confirmation, matches):
    assert recovery.confirmation_matches("crm.example.com", confirmation) is matches


def test_an_instance_with_no_domain_matches_nothing():
    assert recovery.confirmation_matches(None, "") is False
    assert recovery.confirmation_matches("", "") is False


# ---------------------------------------------------------------------------
# Driving a rebuild against a registered instance
# ---------------------------------------------------------------------------

def _rebuild_runner(
    *,
    install_exit=0,
    dump_exit=0,
    copies_before="",
    copies_after="/root/espocrm-backup/2026-09-23_101500/\n",
    seen=None,
):
    """A server on which a rebuild runs, answering by what each command is."""
    installed: list[bool] = []

    def fake_run_remote(_ssh, command, *args, **kwargs):
        if seen is not None:
            seen.append(command)
        if "espocrm-backup" in command:
            listing = copies_after if installed else copies_before
            return 0, listing
        if "mariadb-dump" in command:
            return dump_exit, ""
        if command.startswith(("mkdir -p", "tar -czf")):
            return 0, ""
        if command.startswith("ls -1d /var/backups"):
            return 0, "/var/backups/espocrm/20260923_101400/\n"
        if command.startswith("wget"):
            return 0, ""
        if "install.sh -y" in command:
            installed.append(True)
            return install_exit, ""
        if "crmbuilder_write_test" in command or "chown -R" in command:
            return 0, ""
        if "openssl x509 -in" in command:
            return 0, "notAfter=Dec 22 10:15:00 2026 GMT"
        if "crontab" in command:
            return 0, "* * * * * espocrm cron"
        if "cat data/state.php" in command:
            return 0, STATE_PHP
        if "exec -T espocrm cat" in command:
            return 1, ""
        if "curl -sI http://" in command:
            return 0, "HTTP/1.1 301 Moved Permanently"
        if "curl -sI https://" in command:
            return 0, "HTTP/1.1 200 OK"
        if "openssl s_client" in command:
            return 0, "notAfter=Dec 22 10:15:00 2026 GMT"
        if "curl -sL" in command:
            return 0, "<html>EspoCRM</html>"
        if "docker compose" in command:
            return 0, "espocrm   Up\nespocrm-db  Up"
        raise AssertionError(f"unexpected command: {command}")

    return fake_run_remote


def _passwords():
    values = iter(["generated-db-password", "generated-root-password"])
    return lambda: next(values)


def test_an_unconfirmed_rebuild_never_opens_a_remote_login(provisioned_instance):
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "connect_ssh") as connect:
        outcome = recovery.rebuild_instance(
            provisioned_instance, "INST-001", "admin", "new-admin-password", log
        )

    assert outcome.succeeded is False
    assert "pass its domain name, crm.example.com" in outcome.error
    connect.assert_not_called()


def test_an_instance_with_no_recorded_server_cannot_be_rebuilt(v2_env):
    with session_scope() as session:
        instance = instances.create_instance(
            session, name="Never provisioned", url="https://nowhere.example.com",
            vendor="espocrm", role="both", auth_method="basic",
        )
    log, _lines = _capture_log()

    with pytest.raises(DeployPhaseError):
        recovery.rebuild_instance(
            instance["instance_identifier"], "nowhere.example.com", "a", "b", log
        )


def test_a_whole_rebuild_leaves_the_store_describing_the_rebuilt_instance(
    provisioned_instance, fake_login
):
    log, lines = _capture_log()
    seen: list[str] = []
    runner = _rebuild_runner(seen=seen)
    with patch.object(recovery, "run_remote", side_effect=runner), \
            patch.object(upgrade_module, "run_remote", side_effect=runner), \
            patch("crmbuilder_v2.deploy.ssh.run_remote", side_effect=runner), \
            patch("crmbuilder_v2.deploy.ssh.time.sleep"):
        outcome = recovery.rebuild_instance(
            provisioned_instance, "crm.example.com", "newadmin", "new-admin-password",
            log, new_password=_passwords(),
        )

    assert outcome.succeeded is True, outcome.error
    assert outcome.installer_copy == "/root/espocrm-backup/2026-09-23_101500"
    assert outcome.new_version == "9.3.6"
    assert outcome.cert_expiry == "2026-12-22"

    config = _config(provisioned_instance)
    assert config["admin_username"] == "newadmin"
    assert secrets.get_secret(config["admin_password_ref"]) == "new-admin-password"
    assert secrets.get_secret(config["db_password_ref"]) == "generated-db-password"
    assert secrets.get_secret(config["db_root_password_ref"]) == "generated-root-password"
    assert config["current_espocrm_version"] == "9.3.6"
    assert config["cert_expiry_date"] == "2026-12-22"
    assert config["last_upgrade_at"] is None
    assert upgrade_module.decode_backup_paths(config["last_backup_paths"]) == [
        "/var/backups/espocrm/20260923_101400",
        "/root/espocrm-backup/2026-09-23_101500",
    ]

    instance = _instance(provisioned_instance)
    assert instance["instance_auth_method"] == "basic"
    assert secrets.get_secret(instance["instance_secret_ref"]) == "newadmin"
    assert instance["instance_secret_key_ref"] == config["admin_password_ref"]
    assert instance["instance_standard_version"] is None
    assert instance["instance_plan_fingerprint"] is None

    logged = _logged(lines)
    for secret in ("new-admin-password", "generated-db-password", "generated-root-password"):
        assert secret not in logged
    assert "Publish the design again" in logged
    assert "requests for the same name a week" in logged
    assert not any(c.startswith("rm -rf /var/www/espocrm") for c in seen), (
        "version 2 must leave the clean to the installer, which copies first"
    )


def test_a_failed_install_keeps_the_old_credentials_and_names_the_copy(
    provisioned_instance, fake_login
):
    log, _lines = _capture_log()
    runner = _rebuild_runner(install_exit=1)
    with patch.object(recovery, "run_remote", side_effect=runner), \
            patch.object(upgrade_module, "run_remote", side_effect=runner), \
            patch("crmbuilder_v2.deploy.ssh.run_remote", side_effect=runner):
        outcome = recovery.rebuild_instance(
            provisioned_instance, "crm.example.com", "newadmin", "new-admin-password",
            log, new_password=_passwords(),
        )

    assert outcome.succeeded is False
    assert outcome.installed is False
    assert "/root/espocrm-backup/2026-09-23_101500" in outcome.error
    assert "stored credentials are unchanged" in outcome.error

    config = _config(provisioned_instance)
    assert config["admin_username"] == "admin"
    assert secrets.get_secret(config["admin_password_ref"]) == "old-password"
    assert config["current_espocrm_version"] == "9.3.4"
    assert "/root/espocrm-backup/2026-09-23_101500" in upgrade_module.decode_backup_paths(
        config["last_backup_paths"]
    )


def test_a_failed_dump_is_a_warning_not_a_refusal(provisioned_instance, fake_login):
    log, lines = _capture_log()
    runner = _rebuild_runner(dump_exit=2)
    with patch.object(recovery, "run_remote", side_effect=runner), \
            patch.object(upgrade_module, "run_remote", side_effect=runner), \
            patch("crmbuilder_v2.deploy.ssh.run_remote", side_effect=runner), \
            patch("crmbuilder_v2.deploy.ssh.time.sleep"):
        outcome = recovery.rebuild_instance(
            provisioned_instance, "crm.example.com", "newadmin", "new-admin-password",
            log, new_password=_passwords(),
        )

    assert outcome.succeeded is True, outcome.error
    assert "The portable dump failed" in _logged(lines)


def test_with_no_recorded_database_password_the_installer_copy_is_the_backup(
    provisioned_instance, fake_login
):
    with session_scope() as session:
        instance_deploy_config.upsert_deploy_config(
            session, provisioned_instance, db_root_password_ref=None
        )
    log, lines = _capture_log()
    seen: list[str] = []
    runner = _rebuild_runner(seen=seen)
    with patch.object(recovery, "run_remote", side_effect=runner), \
            patch.object(upgrade_module, "run_remote", side_effect=runner), \
            patch("crmbuilder_v2.deploy.ssh.run_remote", side_effect=runner), \
            patch("crmbuilder_v2.deploy.ssh.time.sleep"):
        outcome = recovery.rebuild_instance(
            provisioned_instance, "crm.example.com", "newadmin", "new-admin-password",
            log, new_password=_passwords(),
        )

    assert outcome.succeeded is True, outcome.error
    assert not any("mariadb-dump" in c for c in seen)
    assert "no portable dump is taken" in _logged(lines)
    assert outcome.backup_paths == ["/root/espocrm-backup/2026-09-23_101500"]


def test_a_rebuild_refuses_a_password_the_installer_would_alter(provisioned_instance):
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "connect_ssh") as connect:
        outcome = recovery.rebuild_instance(
            provisioned_instance, "crm.example.com", "newadmin", " padded", log
        )

    assert outcome.succeeded is False
    connect.assert_not_called()
