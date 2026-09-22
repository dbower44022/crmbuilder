"""Upgrading a running instance in place — PI-557 (REQ-639).

No server is reached: :func:`run_remote` is replaced throughout. The tests for
the two entry points use the real store through the ``v2_env`` fixture, so what
they assert about the recorded version, upgrade time and backup folders is read
back out of the store rather than out of a stand-in.

**Where the fixtures come from.** The command output below was carried across
from version 1's own tests for the same steps and from the commands themselves;
it was *not* read off a live instance. Lesson LRN-007 says a fixture written
from one side agrees with the code instead of checking it, so these tests hold
the step's decisions — what it refuses, what it reports, what it keeps out of
the log — rather than claiming the instance's answers are proven real. Proving
this against a real instance is an upgrade, which is the product owner's step.
"""

from __future__ import annotations

import json
import urllib.error
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.deploy import upgrade as upgrade_module
from crmbuilder_v2.deploy.errors import DeployPhaseError
from crmbuilder_v2.segments.operate.repositories import (
    instance_deploy_config,
    instances,
)


def _capture_log():
    lines: list[tuple[str, str]] = []

    def log(message: str, level: str) -> None:
        lines.append((message, level))

    return log, lines


def _messages(lines) -> list[str]:
    return [message for message, _level in lines]


# The shapes these files really have, reduced to the line that carries the
# version. The last one is the reason a file's contents never reach the log.
STATE_PHP = "<?php\nreturn [\n  'version' => '9.3.4',\n];\n"
CONFIG_INTERNAL_PHP = "<?php\nreturn [\n  'version' => '8.4.0',\n];\n"
APPLICATION_PHP = "<?php\nclass Application {\n  public const VERSION = '7.5.6';\n}\n"
CONFIG_PHP = (
    "<?php\nreturn [\n  'database' => ['password' => 'the-root-password'],\n"
    "  'version' => '7.4.10',\n];\n"
)


# ---------------------------------------------------------------------------
# Comparing versions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("8.4.0", (8, 4, 0)),
        ("v9.3.6", (9, 3, 6)),
        ("EspoCRM 9.3.6 stable", (9, 3, 6)),
        ("", None),
        ("nine point three", None),
        ("9.3", None),
    ],
)
def test_parse_version(value, expected):
    assert upgrade_module.parse_version(value) == expected


@pytest.mark.parametrize(
    ("current", "latest", "available", "major"),
    [
        ("9.3.4", "9.3.6", True, False),
        ("8.4.0", "9.0.0", True, True),
        ("9.3.6", "9.3.6", False, False),
        ("9.3.7", "9.3.6", False, False),
        (None, "9.3.6", False, False),
        ("9.3.4", None, False, False),
        ("unreadable", "9.3.6", False, False),
    ],
)
def test_version_comparison(current, latest, available, major):
    """An unknown version is never a reason to offer an upgrade."""
    assert upgrade_module.is_upgrade_available(current, latest) is available
    assert upgrade_module.is_major_upgrade(current, latest) is major


# ---------------------------------------------------------------------------
# Reading the running version
# ---------------------------------------------------------------------------

def _version_runner(files: dict[str, str], seen: list[str] | None = None):
    """A container in which only the named files exist."""

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        if seen is not None:
            seen.append(command)
        for path, contents in files.items():
            if f"cat {path}" in command:
                return 0, contents
        if "cat " in command:
            return 1, "cat: No such file or directory"
        return 0, ""

    return fake_run_remote


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"data/state.php": STATE_PHP}, "9.3.4"),
        ({"data/config-internal.php": CONFIG_INTERNAL_PHP}, "8.4.0"),
        ({"application/Espo/Core/Application.php": APPLICATION_PHP}, "7.5.6"),
        ({"data/config.php": CONFIG_PHP}, "7.4.10"),
    ],
)
def test_the_version_is_read_from_each_place_it_may_live(files, expected):
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "run_remote", side_effect=_version_runner(files)):
        assert upgrade_module.get_current_version(MagicMock(), log) == expected


def test_the_most_authoritative_file_wins_when_several_answer():
    """An old instance upgraded in place can carry a stale version in the file
    the newest form no longer uses."""
    log, _lines = _capture_log()
    files = {
        "data/state.php": STATE_PHP,
        "data/config.php": CONFIG_PHP,
    }
    with patch.object(upgrade_module, "run_remote", side_effect=_version_runner(files)):
        assert upgrade_module.get_current_version(MagicMock(), log) == "9.3.4"


def test_a_version_files_contents_never_reach_the_log():
    """One of the four holds the database credentials."""
    log, lines = _capture_log()
    files = {"data/config.php": CONFIG_PHP}
    calls: list[tuple] = []

    def fake_run_remote(_ssh, command, *args, **_kwargs):
        calls.append((command, args))
        return _version_runner(files)(_ssh, command)

    with patch.object(upgrade_module, "run_remote", side_effect=fake_run_remote):
        upgrade_module.get_current_version(MagicMock(), log)

    logged = "\n".join(_messages(lines))
    assert "the-root-password" not in logged
    reads = [args for command, args in calls if "cat " in command]
    assert reads and all(args == () for args in reads), (
        "a file that may hold credentials must not be given the log callback"
    )


def test_when_no_file_answers_the_container_layout_is_shown():
    """The reason is made visible rather than left as an unexplained failure."""
    log, lines = _capture_log()
    seen: list[str] = []
    with patch.object(
        upgrade_module, "run_remote", side_effect=_version_runner({}, seen)
    ):
        assert upgrade_module.get_current_version(MagicMock(), log) is None

    assert any("dumping container layout" in m for m in _messages(lines))
    assert any("ls -la data/" in command for command in seen), seen


def test_a_file_that_is_present_but_holds_no_version_is_said_so():
    log, lines = _capture_log()
    files = {"data/state.php": "<?php\nreturn [];\n"}
    with patch.object(upgrade_module, "run_remote", side_effect=_version_runner(files)):
        assert upgrade_module.get_current_version(MagicMock(), log) is None

    assert any(
        "data/state.php: present but no version pattern matched" in m
        for m in _messages(lines)
    )


# ---------------------------------------------------------------------------
# Reading the published release
# ---------------------------------------------------------------------------

class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None


def test_the_published_release_is_read_from_the_release_tag():
    payload = json.dumps({"tag_name": "9.3.6", "prerelease": False}).encode()
    with patch.object(
        upgrade_module.urllib.request, "urlopen", return_value=_Response(payload)
    ):
        assert upgrade_module.get_latest_version() == "9.3.6"


@pytest.mark.parametrize(
    "payload",
    [b"{}", b'{"tag_name": ""}', b'{"tag_name": "latest"}', b"not json"],
)
def test_a_release_answer_that_carries_no_version_reads_as_unknown(payload):
    with patch.object(
        upgrade_module.urllib.request, "urlopen", return_value=_Response(payload)
    ):
        assert upgrade_module.get_latest_version() is None


def test_a_release_lookup_that_fails_reads_as_unknown_rather_than_raising():
    """Sixty unauthenticated requests an hour is the limit; the caller keeps
    what it already stored."""
    with patch.object(
        upgrade_module.urllib.request,
        "urlopen",
        side_effect=urllib.error.URLError("rate limited"),
    ):
        assert upgrade_module.get_latest_version() is None


# ---------------------------------------------------------------------------
# Step 1 — refusing to start
# ---------------------------------------------------------------------------

def _step1_runner(
    *, compose_exit=0, compose_output="espocrm-nginx Up", files=None, free_mb="8192"
):
    files = files if files is not None else {"data/state.php": STATE_PHP}

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        if "docker compose" in command and command.rstrip().endswith("ps"):
            return compose_exit, compose_output
        if "df -BM" in command:
            return (0, free_mb) if free_mb is not None else (1, "")
        return _version_runner(files)(_ssh, command)

    return fake_run_remote


def test_step1_refuses_when_the_container_definition_is_missing():
    log, _lines = _capture_log()
    with patch.object(
        upgrade_module, "run_remote", side_effect=_step1_runner(compose_exit=1)
    ):
        ready, error, version = upgrade_module.phase1_pre_upgrade_checks(MagicMock(), log)
    assert ready is False
    assert "compose file missing" in error
    assert version is None


def test_step1_refuses_when_the_instance_is_not_running():
    log, _lines = _capture_log()
    with patch.object(
        upgrade_module,
        "run_remote",
        side_effect=_step1_runner(compose_output="no containers"),
    ):
        ready, error, version = upgrade_module.phase1_pre_upgrade_checks(MagicMock(), log)
    assert (ready, error, version) == (False, "EspoCRM container is not running", None)


def test_step1_refuses_when_the_version_cannot_be_read():
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "run_remote", side_effect=_step1_runner(files={})):
        ready, error, version = upgrade_module.phase1_pre_upgrade_checks(MagicMock(), log)
    assert ready is False
    assert "Could not read current EspoCRM version" in error
    assert version is None


def test_step1_refuses_when_there_is_too_little_room_to_work_in():
    log, _lines = _capture_log()
    with patch.object(
        upgrade_module, "run_remote", side_effect=_step1_runner(free_mb="512")
    ):
        ready, error, version = upgrade_module.phase1_pre_upgrade_checks(MagicMock(), log)
    assert ready is False
    assert "Only 512 MB free" in error
    assert version == "9.3.4", "the version it read is reported even on refusal"


def test_step1_proceeds_when_free_space_cannot_be_read():
    """Not knowing is not the same as knowing there is too little."""
    log, lines = _capture_log()
    with patch.object(
        upgrade_module, "run_remote", side_effect=_step1_runner(free_mb=None)
    ):
        ready, error, version = upgrade_module.phase1_pre_upgrade_checks(MagicMock(), log)
    assert (ready, error, version) == (True, "", "9.3.4")
    assert any("Could not determine free disk space" in m for m in _messages(lines))


# ---------------------------------------------------------------------------
# Step 2 — backing up
# ---------------------------------------------------------------------------

def _step2_runner(*, dump_exit=0, tar_exit=0, mkdir_exit=0, listing=None, seen=None):
    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        if seen is not None:
            seen.append(command)
        if command.startswith("mkdir -p"):
            return mkdir_exit, ""
        if "mariadb-dump" in command:
            return dump_exit, ""
        if command.startswith("tar -czf"):
            return tar_exit, ""
        if command.startswith("ls -1d"):
            return (0, listing) if listing is not None else (1, "")
        if command.startswith("rm -rf"):
            return 0, ""
        raise AssertionError(f"unexpected command: {command}")

    return fake_run_remote


def test_the_database_password_never_reaches_the_log():
    log, lines = _capture_log()
    calls: list[tuple] = []

    def fake_run_remote(_ssh, command, *args, **kwargs):
        calls.append((command, args))
        return _step2_runner()(_ssh, command, *args, **kwargs)

    with patch.object(upgrade_module, "run_remote", side_effect=fake_run_remote):
        ok, error, _paths = upgrade_module.phase2_backup(
            MagicMock(), "the-root-password", None, log
        )

    assert (ok, error) == (True, "")
    assert "the-root-password" not in "\n".join(_messages(lines))
    assert any("[secret]" in m for m in _messages(lines))
    dump = [args for command, args in calls if "mariadb-dump" in command]
    assert dump and dump[0] == (), (
        "the dump's own output would carry the password, so it is not logged"
    )


def test_a_failed_dump_stops_before_the_data_directory_is_archived():
    log, _lines = _capture_log()
    seen: list[str] = []
    with patch.object(
        upgrade_module, "run_remote", side_effect=_step2_runner(dump_exit=1, seen=seen)
    ):
        ok, error, paths = upgrade_module.phase2_backup(
            MagicMock(), "pw", ["/var/backups/espocrm/20260101_000000"], log
        )
    assert ok is False
    assert error == "Database backup (mariadb-dump) failed"
    assert paths == ["/var/backups/espocrm/20260101_000000"], (
        "what the store already knew is kept when the backup did not complete"
    )
    assert not any(c.startswith("tar -czf") for c in seen), seen


def test_a_failed_archive_is_reported_and_no_backup_is_claimed():
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "run_remote", side_effect=_step2_runner(tar_exit=2)):
        ok, error, _paths = upgrade_module.phase2_backup(MagicMock(), "pw", None, log)
    assert (ok, error) == (False, "Data volume archive (tar) failed")


def test_a_directory_that_cannot_be_created_stops_the_backup():
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "run_remote", side_effect=_step2_runner(mkdir_exit=1)):
        ok, error, _paths = upgrade_module.phase2_backup(MagicMock(), "pw", None, log)
    assert ok is False
    assert "Could not create backup directory" in error


def test_only_the_three_most_recent_backups_are_kept():
    log, _lines = _capture_log()
    listing = "\n".join(
        f"/var/backups/espocrm/2026010{n}_000000/" for n in range(1, 6)
    )
    seen: list[str] = []
    with patch.object(
        upgrade_module, "run_remote", side_effect=_step2_runner(listing=listing, seen=seen)
    ):
        remaining = upgrade_module.prune_old_backups(MagicMock(), [], log)

    assert remaining == [
        "/var/backups/espocrm/20260103_000000",
        "/var/backups/espocrm/20260104_000000",
        "/var/backups/espocrm/20260105_000000",
    ]
    removed = [c for c in seen if c.startswith("rm -rf")]
    assert len(removed) == 2
    assert "20260101_000000" in removed[0] and "20260102_000000" in removed[1]


def test_nothing_is_removed_when_there_are_three_or_fewer():
    log, _lines = _capture_log()
    listing = "/var/backups/espocrm/20260101_000000/\n/var/backups/espocrm/20260102_000000/"
    seen: list[str] = []
    with patch.object(
        upgrade_module, "run_remote", side_effect=_step2_runner(listing=listing, seen=seen)
    ):
        remaining = upgrade_module.prune_old_backups(MagicMock(), [], log)
    assert len(remaining) == 2
    assert not any(c.startswith("rm -rf") for c in seen)


def test_nothing_is_removed_when_the_server_cannot_be_listed():
    """What the store already knew is returned unchanged rather than emptied."""
    log, _lines = _capture_log()
    known = ["/var/backups/espocrm/20260101_000000"]
    seen: list[str] = []
    with patch.object(
        upgrade_module, "run_remote", side_effect=_step2_runner(listing=None, seen=seen)
    ):
        assert upgrade_module.prune_old_backups(MagicMock(), known, log) == known
    assert not any(c.startswith("rm -rf") for c in seen)


# ---------------------------------------------------------------------------
# Step 3 — running the upgrader
# ---------------------------------------------------------------------------

def _step3_runner(
    *,
    chown_exit=0,
    upgrade_exit=0,
    upgrade_output="Upgrade complete.",
    files_after=None,
    seen=None,
):
    files_after = (
        files_after if files_after is not None else {"data/state.php": CONFIG_INTERNAL_PHP}
    )

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        if seen is not None:
            seen.append(command)
        if "chown -R www-data:www-data /var/www/html" in command:
            return chown_exit, ""
        if "command.php upgrade" in command:
            return upgrade_exit, upgrade_output
        if "command.php clear-cache" in command:
            return 0, "Cache cleared"
        return _version_runner(files_after)(_ssh, command)

    return fake_run_remote


def test_the_files_are_given_to_the_web_server_user_before_the_upgrader_runs():
    """The image is built as root; the upgrader runs as the web-server user."""
    log, _lines = _capture_log()
    seen: list[str] = []
    with patch.object(upgrade_module, "run_remote", side_effect=_step3_runner(seen=seen)):
        ok, error, new_version, upgraded_at = upgrade_module.phase3_run_upgrade(
            MagicMock(), "9.3.4", log
        )

    assert (ok, error, new_version) == (True, "", "8.4.0")
    assert upgraded_at is not None
    chown_at = next(i for i, c in enumerate(seen) if "chown -R www-data" in c)
    upgrade_at = next(i for i, c in enumerate(seen) if "command.php upgrade" in c)
    assert chown_at < upgrade_at


def test_a_failed_ownership_change_stops_before_anything_is_upgraded():
    log, _lines = _capture_log()
    seen: list[str] = []
    with patch.object(
        upgrade_module, "run_remote", side_effect=_step3_runner(chown_exit=1, seen=seen)
    ):
        ok, error, new_version, _at = upgrade_module.phase3_run_upgrade(
            MagicMock(), "9.3.4", log
        )
    assert ok is False
    assert "Upgrade aborted before any changes" in error
    assert new_version is None
    assert not any("command.php upgrade" in c for c in seen), seen


@pytest.mark.parametrize("exit_code", [0, 1])
@pytest.mark.parametrize(
    "output",
    [
        "EspoCRM is already up to date.",
        "No upgrade is available.",
        "Nothing to upgrade.",
        "You are already on the latest version.",
    ],
)
def test_an_upgrader_that_reports_it_is_up_to_date_is_not_a_successful_upgrade(
    exit_code, output
):
    """It can say this and still exit as though it had succeeded."""
    log, _lines = _capture_log()
    with patch.object(
        upgrade_module,
        "run_remote",
        side_effect=_step3_runner(upgrade_exit=exit_code, upgrade_output=output),
    ):
        ok, error, new_version, _at = upgrade_module.phase3_run_upgrade(
            MagicMock(), "9.3.4", log
        )
    assert ok is False
    assert "reports no upgrade is available" in error
    assert new_version is None


def test_a_version_that_does_not_move_is_reported_as_an_upgrade_that_did_not_happen():
    log, _lines = _capture_log()
    with patch.object(
        upgrade_module,
        "run_remote",
        side_effect=_step3_runner(files_after={"data/state.php": STATE_PHP}),
    ):
        ok, error, new_version, _at = upgrade_module.phase3_run_upgrade(
            MagicMock(), "9.3.4", log
        )
    assert ok is False
    assert "the version is still 9.3.4" in error
    assert new_version is None


def test_a_version_that_cannot_be_read_back_is_reported_rather_than_assumed():
    log, _lines = _capture_log()
    with patch.object(
        upgrade_module, "run_remote", side_effect=_step3_runner(files_after={})
    ):
        ok, error, new_version, _at = upgrade_module.phase3_run_upgrade(
            MagicMock(), "9.3.4", log
        )
    assert ok is False
    assert "could not be read back" in error
    assert new_version is None


def test_a_permission_failure_says_what_to_look_at():
    log, _lines = _capture_log()
    with patch.object(
        upgrade_module,
        "run_remote",
        side_effect=_step3_runner(
            upgrade_exit=1, upgrade_output="Error: Permission denied writing to data/"
        ),
    ):
        ok, error, _version, _at = upgrade_module.phase3_run_upgrade(
            MagicMock(), "9.3.4", log
        )
    assert ok is False
    assert "permission error" in error
    assert "owned by www-data" in error


def test_the_upgrader_runs_once_and_does_not_loop_toward_the_latest_release():
    """Two releases apart is two runs; an operator may want to lag the newest."""
    log, _lines = _capture_log()
    seen: list[str] = []
    with patch.object(upgrade_module, "run_remote", side_effect=_step3_runner(seen=seen)):
        upgrade_module.phase3_run_upgrade(MagicMock(), "9.3.4", log)
    assert len([c for c in seen if "command.php upgrade" in c]) == 1


def test_an_upgrade_from_an_unknown_previous_version_still_reports_the_new_one():
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "run_remote", side_effect=_step3_runner()):
        ok, error, new_version, _at = upgrade_module.phase3_run_upgrade(
            MagicMock(), None, log
        )
    assert (ok, error, new_version) == (True, "", "8.4.0")


# ---------------------------------------------------------------------------
# Step 4 — checking the result
# ---------------------------------------------------------------------------

def _step4_runner(*, https="HTTP/1.1 200 OK", page="<html>EspoCRM</html>", files=None):
    files = files if files is not None else {"data/state.php": STATE_PHP}

    def fake_run_remote(_ssh, command, *_args, **_kwargs):
        if "docker compose" in command and command.rstrip().endswith("ps"):
            return 0, "espocrm-nginx Up"
        if "curl -sI" in command:
            return 0, https
        if "curl -sL" in command:
            return 0, page
        return _version_runner(files)(_ssh, command)

    return fake_run_remote


def test_step4_passes_on_an_instance_that_came_back_up():
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "run_remote", side_effect=_step4_runner()):
        overall, checks = upgrade_module.phase4_verify_upgrade(
            MagicMock(), "crm.example.com", log
        )
    assert overall is True
    assert [c["check"] for c in checks] == [
        "Containers running",
        "HTTPS response",
        "Login page renders",
        "Version reads back",
    ]


def test_step4_names_the_check_that_failed():
    log, _lines = _capture_log()
    with patch.object(
        upgrade_module, "run_remote", side_effect=_step4_runner(https="HTTP/1.1 502 Bad Gateway")
    ):
        overall, checks = upgrade_module.phase4_verify_upgrade(
            MagicMock(), "crm.example.com", log
        )
    assert overall is False
    failed = [c for c in checks if not c["passed"]]
    assert [c["check"] for c in failed] == ["HTTPS response"]
    assert "502" in failed[0]["detail"]


def test_step4_fails_when_no_version_reads_back():
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "run_remote", side_effect=_step4_runner(files={})):
        overall, checks = upgrade_module.phase4_verify_upgrade(
            MagicMock(), "crm.example.com", log
        )
    assert overall is False
    version_check = next(c for c in checks if c["check"] == "Version reads back")
    assert version_check["passed"] is False
    assert version_check["detail"] == "could not detect version"


# ---------------------------------------------------------------------------
# Driving the steps against a registered instance
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


@pytest.fixture
def registered_instance(v2_env):
    """An instance with recorded server details, as a provisioning run leaves it."""
    with session_scope() as session:
        instance = instances.create_instance(
            session,
            name="Upgrade target",
            url="https://crm.example.com",
            vendor="espocrm",
            role="both",
            auth_method="basic",
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
            db_root_password_ref=secrets.put_secret("the-root-password"),
            current_espocrm_version="9.3.4",
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


def _stored(identifier: str) -> dict:
    with session_scope() as session:
        return instance_deploy_config.get_deploy_config(session, identifier)


def _upgrade_runner(**overrides):
    """A whole upgrade on an instance that goes from 9.3.4 to 8.4.0.

    The version the instance reports changes once the upgrade command has run,
    as it would on a real one. The two numbers are the two sample files, not a
    real upgrade path; what is under test is that the version moved, not which
    way it moved.
    """
    step1 = _step1_runner()
    step2 = _step2_runner(listing="/var/backups/espocrm/20260101_000000/", **overrides)
    step4 = _step4_runner()
    upgraded = []

    def fake_run_remote(ssh, command, *args, **kwargs):
        if "df -BM" in command or (
            "docker compose" in command and command.rstrip().endswith("ps")
        ):
            return step1(ssh, command, *args, **kwargs)
        if (
            command.startswith(("mkdir -p", "tar -czf", "ls -1d", "rm -rf"))
            or "mariadb-dump" in command
        ):
            return step2(ssh, command, *args, **kwargs)
        if "chown -R www-data:www-data /var/www/html" in command:
            return 0, ""
        if "command.php upgrade" in command:
            upgraded.append(True)
            return 0, "Upgrade complete."
        if "command.php clear-cache" in command:
            return 0, "Cache cleared"
        if "curl" in command:
            return step4(ssh, command, *args, **kwargs)
        now = CONFIG_INTERNAL_PHP if upgraded else STATE_PHP
        return _version_runner({"data/state.php": now})(ssh, command)

    return fake_run_remote


def test_a_whole_upgrade_records_the_version_the_time_and_the_backup(
    registered_instance, fake_login
):
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "run_remote", side_effect=_upgrade_runner()):
        outcome = upgrade_module.upgrade_instance(registered_instance, log)

    assert outcome.succeeded is True, outcome.error
    assert outcome.previous_version == "9.3.4"
    assert outcome.new_version == "8.4.0"
    assert outcome.checks and all(c["passed"] for c in outcome.checks)

    stored = _stored(registered_instance)
    assert stored["current_espocrm_version"] == "8.4.0"
    assert stored["last_upgrade_at"] is not None
    assert upgrade_module.decode_backup_paths(stored["last_backup_paths"]) == [
        "/var/backups/espocrm/20260101_000000"
    ]


def test_an_upgrade_that_fails_after_the_backup_still_records_the_backup(
    registered_instance, fake_login
):
    """A backup taken before an upgrade that then failed is still a backup the
    operator has."""
    log, _lines = _capture_log()

    def runner(ssh, command, *args, **kwargs):
        if "command.php upgrade" in command:
            return 0, "EspoCRM is already up to date."
        return _upgrade_runner()(ssh, command, *args, **kwargs)

    with patch.object(upgrade_module, "run_remote", side_effect=runner):
        outcome = upgrade_module.upgrade_instance(registered_instance, log)

    assert outcome.succeeded is False
    assert "reports no upgrade is available" in outcome.error
    stored = _stored(registered_instance)
    assert upgrade_module.decode_backup_paths(stored["last_backup_paths"]) == [
        "/var/backups/espocrm/20260101_000000"
    ]
    assert stored["current_espocrm_version"] == "9.3.4", "the version did not move"
    assert stored["last_upgrade_at"] is None


def test_a_refused_pre_check_never_reaches_the_backup(registered_instance, fake_login):
    log, _lines = _capture_log()
    seen: list[str] = []

    def runner(ssh, command, *args, **kwargs):
        seen.append(command)
        if "docker compose" in command and command.rstrip().endswith("ps"):
            return 0, "no containers"
        return _upgrade_runner()(ssh, command, *args, **kwargs)

    with patch.object(upgrade_module, "run_remote", side_effect=runner):
        outcome = upgrade_module.upgrade_instance(registered_instance, log)

    assert outcome.succeeded is False
    assert outcome.error == "EspoCRM container is not running"
    assert not any("mariadb-dump" in c for c in seen), seen
    assert _stored(registered_instance)["last_backup_paths"] is None


def test_an_instance_with_no_recorded_database_password_is_refused_before_connecting(
    registered_instance, fake_login
):
    with session_scope() as session:
        instance_deploy_config.upsert_deploy_config(
            session, registered_instance, db_root_password_ref=None
        )
    log, _lines = _capture_log()

    outcome = upgrade_module.upgrade_instance(registered_instance, log)

    assert outcome.succeeded is False
    assert "No database administrator password is recorded" in outcome.error


def test_an_instance_with_no_recorded_server_cannot_be_upgraded(v2_env):
    with session_scope() as session:
        instance = instances.create_instance(
            session,
            name="Never provisioned",
            url="https://nowhere.example.com",
            vendor="espocrm",
            role="both",
            auth_method="basic",
        )
    log, _lines = _capture_log()

    with pytest.raises(DeployPhaseError) as raised:
        upgrade_module.upgrade_instance(instance["instance_identifier"], log)

    assert "no recorded server connection" in str(raised.value)


def test_checking_for_an_upgrade_records_both_versions(registered_instance, fake_login):
    log, _lines = _capture_log()
    payload = json.dumps({"tag_name": "9.3.6"}).encode()
    with patch.object(
        upgrade_module, "run_remote",
        side_effect=_version_runner({"data/state.php": STATE_PHP}),
    ), patch.object(
        upgrade_module.urllib.request, "urlopen", return_value=_Response(payload)
    ):
        current, latest = upgrade_module.check_for_upgrade(registered_instance, log)

    assert (current, latest) == ("9.3.4", "9.3.6")
    stored = _stored(registered_instance)
    assert stored["current_espocrm_version"] == "9.3.4"
    assert stored["latest_espocrm_version"] == "9.3.6"
    assert upgrade_module.is_upgrade_available(current, latest) is True


def test_a_release_lookup_that_fails_does_not_erase_what_is_already_recorded(
    registered_instance, fake_login
):
    with session_scope() as session:
        instance_deploy_config.upsert_deploy_config(
            session, registered_instance, latest_espocrm_version="9.3.5"
        )
    log, lines = _capture_log()

    with patch.object(
        upgrade_module, "run_remote",
        side_effect=_version_runner({"data/state.php": STATE_PHP}),
    ), patch.object(
        upgrade_module.urllib.request,
        "urlopen",
        side_effect=urllib.error.URLError("rate limited"),
    ):
        current, latest = upgrade_module.check_for_upgrade(registered_instance, log)

    assert (current, latest) == ("9.3.4", None)
    assert _stored(registered_instance)["latest_espocrm_version"] == "9.3.5"
    assert any("keeping the one already recorded" in m for m in _messages(lines))


# ---------------------------------------------------------------------------
# The one column the backup folders live in
# ---------------------------------------------------------------------------

def test_the_backup_folders_survive_a_round_trip_through_their_column():
    paths = ["/var/backups/espocrm/20260101_000000", "/var/backups/espocrm/20260102_000000"]
    written = upgrade_module.encode_backup_paths(paths)
    assert isinstance(written, str), "the column is text, so what is written must be"
    assert upgrade_module.decode_backup_paths(written) == paths


@pytest.mark.parametrize("stored", [None, "", "not a list", "{}", '"a string"', "42"])
def test_a_column_that_does_not_hold_a_list_of_folders_reads_as_none(stored):
    """A column nobody has written, or written by hand, must not stop an upgrade."""
    assert upgrade_module.decode_backup_paths(stored) == []


def test_an_upgrade_carries_forward_the_folders_already_recorded(
    registered_instance, fake_login
):
    """What the store already knew is passed to the step that prunes, so a
    folder taken by an earlier run is counted."""
    with session_scope() as session:
        instance_deploy_config.upsert_deploy_config(
            session,
            registered_instance,
            last_backup_paths=upgrade_module.encode_backup_paths(
                ["/var/backups/espocrm/20251231_000000"]
            ),
        )
    log, _lines = _capture_log()
    seen: list[list[str]] = []
    real_phase2 = upgrade_module.phase2_backup

    def spy(client, password, existing, logger_):
        seen.append(list(existing))
        return real_phase2(client, password, existing, logger_)

    with patch.object(upgrade_module, "run_remote", side_effect=_upgrade_runner()), patch.object(
        upgrade_module, "phase2_backup", side_effect=spy
    ):
        upgrade_module.upgrade_instance(registered_instance, log)

    assert seen == [["/var/backups/espocrm/20251231_000000"]]


def test_the_upgrade_step_reports_a_moment_not_text():
    """The column that holds it is a date and time. A step that returned text
    was refused by the store outright, so the type is part of the contract."""
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "run_remote", side_effect=_step3_runner()):
        _ok, _error, _version, upgraded_at = upgrade_module.phase3_run_upgrade(
            MagicMock(), "9.3.4", log
        )
    assert isinstance(upgraded_at, datetime)
    assert upgraded_at.tzinfo is not None, "the moment carries its time zone"


def test_the_recorded_upgrade_time_reads_back_as_a_moment(
    registered_instance, fake_login
):
    log, _lines = _capture_log()
    with patch.object(upgrade_module, "run_remote", side_effect=_upgrade_runner()):
        upgrade_module.upgrade_instance(registered_instance, log)

    recorded = _stored(registered_instance)["last_upgrade_at"]
    assert datetime.fromisoformat(recorded)
