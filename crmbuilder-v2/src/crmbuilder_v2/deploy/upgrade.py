"""Upgrading a running instance in place — PI-557 (REQ-639, DEC-1141).

Absorbed from version 1's ``automation.core.deployment.upgrade_ssh``. Version 2
stored the version an instance is on, the latest release, the last upgrade time
and the backup folders, and had no code that produced any of them.

Two readings and four steps:

* :func:`get_current_version` — what the instance is running now.
* :func:`get_latest_version` — what the platform has published.
* :func:`phase1_pre_upgrade_checks` — refuse to start unless the instance is
  running, its version can be read, and there is room to work in.
* :func:`phase2_backup` — a database dump and an archive of the data directory,
  into a dated folder, keeping the three most recent.
* :func:`phase3_run_upgrade` — give the platform's files to the web-server user,
  then run the platform's own upgrade command inside the container.
* :func:`phase4_verify_upgrade` — the instance answers, its sign-in page
  renders, and a version reads back.

Each step reports what it learned and writes nothing. The two entry points at
the end of this module — :func:`check_for_upgrade` and :func:`upgrade_instance`
— are what open the remote login, drive the steps and write the version, the
upgrade time and the backup folders through the repository that owns those
columns (DEC-1141). Whether an upgrade should also be a recorded, resumable run
of its own is left open by that decision, and belongs with the screens that
drive one.

**Never rebuild an instance from clean to upgrade it** (GVR-162). The installer's
clean mode destroys data; the upgrade path is the platform's own upgrader, run
inside the container, which is what :func:`phase3_run_upgrade` does.

**The platform upgrades one step at a time.** Two releases apart is two runs,
and nothing here loops: an operator may deliberately lag the newest release.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime

import paramiko

from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.deploy.errors import DeployPhaseError
from crmbuilder_v2.deploy.keys import private_key_file
from crmbuilder_v2.deploy.ssh import (
    COMPOSE_FILE,
    Log,
    SelfHostedConfig,
    connect_ssh,
    mask_secrets,
    run_remote,
)
from crmbuilder_v2.segments.operate.repositories import instance_deploy_config

logger = logging.getLogger("crmbuilder_v2.deploy.upgrade")

#: Where the installer keeps the container definition and the data directory.
COMPOSE_DIR = "/var/www/espocrm"

#: Where a backup taken before an upgrade is written.
BACKUP_ROOT = "/var/backups/espocrm"

#: How many dated backup folders are kept; older ones are removed.
BACKUP_RETENTION = 3

#: The platform publishes every release as a tag, and this excludes
#: prereleases, so its tag name is the latest stable one. The older address on
#: the platform's own site was retired and now answers with a page saying so.
RELEASE_INFO_URL = "https://api.github.com/repos/espocrm/espocrm/releases/latest"

#: How little free space is too little to back up and upgrade safely, in
#: megabytes.
MINIMUM_FREE_MB = 2048


# ---------------------------------------------------------------------------
# Comparing versions
# ---------------------------------------------------------------------------

def parse_version(value: str) -> tuple[int, int, int] | None:
    """Read a version such as ``8.4.0`` or ``v8.4.1`` into three numbers.

    :returns: ``(major, minor, patch)``, or None when the text holds no version.
    """
    if not value:
        return None
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def is_upgrade_available(current: str | None, latest: str | None) -> bool:
    """Is ``latest`` newer than ``current``?

    False when either is missing or unreadable: an unknown version is not a
    reason to offer an upgrade.
    """
    running = parse_version(current) if current else None
    published = parse_version(latest) if latest else None
    if running is None or published is None:
        return False
    return published > running


def is_major_upgrade(current: str | None, latest: str | None) -> bool:
    """Is the gap a whole version rather than a smaller step?

    The caller warns before one of these; it is the jump most likely to need
    attention. False when either version is missing or unreadable.
    """
    running = parse_version(current) if current else None
    published = parse_version(latest) if latest else None
    if running is None or published is None:
        return False
    return published[0] > running[0]


# ---------------------------------------------------------------------------
# Reading what is running, and what has been published
# ---------------------------------------------------------------------------

_PHP_KEY_PATTERN = (
    r"['\"](?:version|currentVersion)['\"]"
    r"\s*=>\s*"
    r"['\"](\d+\.\d+\.\d+)['\"]"
)
_PHP_CONST_PATTERN = r"\bVERSION\b[^=\n]*=\s*['\"](\d+\.\d+\.\d+)['\"]"

#: Where the running version may be recorded, in order of authority. The
#: newest form of the platform keeps it in the first; the oldest, in the last.
_VERSION_PROBES: tuple[tuple[str, str], ...] = (
    ("data/state.php", _PHP_KEY_PATTERN),
    ("data/config-internal.php", _PHP_KEY_PATTERN),
    ("application/Espo/Core/Application.php", _PHP_CONST_PATTERN),
    ("data/config.php", _PHP_KEY_PATTERN),
)


def get_current_version(
    ssh: paramiko.SSHClient, log: Log | None = None
) -> str | None:
    """Read the version the instance is running, from inside the container.

    Each candidate file is read whole and searched here rather than on the
    server. **The contents never reach the log**: the last of them holds the
    database credentials.

    When none of them answers, the container's own layout is written to the log
    instead, so the reason is visible rather than left as an unexplained
    failure.

    :param log: Told which file answered, or which did not; never given a
        file's contents.
    :returns: A version such as ``8.4.0``, or None when none could be read.
    """
    for path, pattern in _VERSION_PROBES:
        # No log callback: the output may carry credentials.
        exit_code, output = run_remote(
            ssh, f"docker compose -f {COMPOSE_FILE} exec -T espocrm cat {path}"
        )
        if exit_code != 0:
            if log:
                log(f"{path}: not present in container", "info")
            continue
        match = re.search(pattern, output)
        if match:
            parsed = parse_version(match.group(1))
            if parsed is None:
                continue
            version = f"{parsed[0]}.{parsed[1]}.{parsed[2]}"
            if log:
                log(f"Version found in {path}: {version}", "info")
            return version
        if log:
            log(f"{path}: present but no version pattern matched", "info")

    if log:
        log("Version not found in known files — dumping container layout:", "warning")
        run_remote(
            ssh,
            f"docker compose -f {COMPOSE_FILE} exec -T espocrm sh -c "
            "'pwd; echo ---data---; ls -la data/ 2>&1 | head -25; "
            "echo ---application/Espo/Core---; "
            "ls -la application/Espo/Core/Application.php 2>&1'",
            log,
        )
    return None


def get_latest_version(timeout: int = 10) -> str | None:
    """Read the latest published release of the platform.

    Unauthenticated requests here are limited to sixty an hour for one address;
    the caller falls back to the version it last stored.

    :returns: A version such as ``9.3.6``, or None when it could not be read.
    """
    request = urllib.request.Request(
        RELEASE_INFO_URL, headers={"Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        logger.warning("Failed to fetch latest EspoCRM version: %s", exc)
        return None

    tag = data.get("tag_name") if isinstance(data, dict) else None
    if not tag:
        return None
    parsed = parse_version(str(tag))
    if not parsed:
        return None
    return f"{parsed[0]}.{parsed[1]}.{parsed[2]}"


# ---------------------------------------------------------------------------
# Step 1 — refuse to start on an instance that is not ready
# ---------------------------------------------------------------------------

def phase1_pre_upgrade_checks(
    ssh: paramiko.SSHClient, log: Log
) -> tuple[bool, str, str | None]:
    """Check the instance is running, readable, and has room to work in.

    :returns: ``(ready, why it is not, the version it is running)``.
    """
    log("Checking Docker containers...", "info")
    exit_code, output = run_remote(ssh, f"docker compose -f {COMPOSE_FILE} ps", log)
    if exit_code != 0:
        return False, "Docker compose not available or compose file missing", None
    if "espocrm" not in output.lower():
        return False, "EspoCRM container is not running", None

    log("Reading current EspoCRM version...", "info")
    current = get_current_version(ssh, log)
    if current is None:
        return False, (
            "Could not read current EspoCRM version from data/state.php, "
            "data/config-internal.php, Application.php, or data/config.php. "
            "See the diagnostic dump above for what is actually in the container."
        ), None
    log(f"Current version: {current}", "info")

    log("Checking free disk space...", "info")
    exit_code, output = run_remote(
        ssh, "df -BM --output=avail / | tail -1 | tr -dc '0-9'", log
    )
    if exit_code == 0 and output.strip().isdigit():
        free_mb = int(output.strip())
        if free_mb < MINIMUM_FREE_MB:
            return False, (
                f"Only {free_mb} MB free on /. Need at least 2 GB to safely "
                "back up and upgrade. Free disk space and retry."
            ), current
        log(f"Free space: {free_mb} MB", "info")
    else:
        # Not knowing is not the same as knowing there is too little; a
        # readable instance is not held back by a reading that did not work.
        log("WARNING: Could not determine free disk space — proceeding", "warning")

    return True, "", current


# ---------------------------------------------------------------------------
# Step 2 — back up before anything is changed
# ---------------------------------------------------------------------------

def phase2_backup(
    ssh: paramiko.SSHClient,
    db_root_password: str,
    existing_backup_paths: list[str] | None,
    log: Log,
) -> tuple[bool, str, list[str]]:
    """Dump the database and archive the data directory into a dated folder.

    :param db_root_password: Passed to the database in the environment rather
        than on the command line, and replaced before the command is logged.
    :param existing_backup_paths: What the store already records, kept if the
        server cannot be listed.
    :returns: ``(succeeded, why it did not, the backup folders now on the
        server — newest last)``.
    """
    kept = list(existing_backup_paths or [])
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_dir = f"{BACKUP_ROOT}/{timestamp}"

    log(f"Creating backup directory: {backup_dir}", "info")
    exit_code, _ = run_remote(ssh, f"mkdir -p {backup_dir}", log)
    if exit_code != 0:
        return False, f"Could not create backup directory {backup_dir}", kept

    log("Dumping database...", "info")
    dump = (
        f"docker compose -f {COMPOSE_FILE} exec -T "
        f"-e MYSQL_PWD={db_root_password} espocrm-db "
        "mariadb-dump --single-transaction --routines --triggers "
        f"-u root espocrm | gzip > {backup_dir}/db.sql.gz"
    )
    log(f"$ {mask_secrets(dump, [db_root_password])[:160]}", "info")
    # No log callback: the command's own output would carry the password.
    exit_code, _ = run_remote(ssh, dump)
    if exit_code != 0:
        return False, "Database backup (mariadb-dump) failed", kept

    log("Archiving data volume...", "info")
    exit_code, _ = run_remote(
        ssh,
        f"tar -czf {backup_dir}/data.tar.gz -C {COMPOSE_DIR} data 2>&1 | tail -20",
        log,
    )
    if exit_code != 0:
        return False, "Data volume archive (tar) failed", kept

    remaining = prune_old_backups(ssh, kept + [backup_dir], log)
    log(f"Backup complete: {backup_dir}", "info")
    return True, "", remaining


def prune_old_backups(
    ssh: paramiko.SSHClient, known_paths: list[str], log: Log
) -> list[str]:
    """Remove all but the most recent :data:`BACKUP_RETENTION` backup folders.

    What is on the server decides, not what the store remembers — a folder
    removed by hand should not be counted, and one taken by another run should.
    When the server cannot be listed, nothing is removed and what was known is
    returned unchanged.

    :returns: The folders that remain, newest last.
    """
    exit_code, output = run_remote(
        ssh, f"ls -1d {BACKUP_ROOT}/*/ 2>/dev/null | sort", log
    )
    if exit_code != 0 or not output.strip():
        return list(known_paths)

    paths = [line.rstrip("/") for line in output.strip().splitlines()]
    if len(paths) <= BACKUP_RETENTION:
        return paths

    for path in paths[: len(paths) - BACKUP_RETENTION]:
        log(f"Pruning old backup: {path}", "info")
        run_remote(ssh, f"rm -rf {path}", log)

    return paths[-BACKUP_RETENTION:]


# ---------------------------------------------------------------------------
# Step 3 — run the platform's own upgrader
# ---------------------------------------------------------------------------

#: What the upgrader says when it believes there is nothing to do. It can say
#: one of these and still exit as though it had succeeded, so the words are the
#: only signal — see :func:`_output_says_no_upgrade`.
_NO_UPGRADE_PHRASES: tuple[str, ...] = (
    "no upgrade",
    "up to date",
    "up-to-date",
    "already on the latest",
    "nothing to upgrade",
    "no new version",
)


def _output_says_no_upgrade(output: str) -> bool:
    """Did the upgrader report that there was nothing to upgrade?

    The upgrader can report being up to date and exit as though it succeeded:
    its own view of what is available disagrees with the published release the
    caller compared against. Reading that as success would leave the log
    claiming an upgrade that never happened.
    """
    lowered = output.lower()
    return any(phrase in lowered for phrase in _NO_UPGRADE_PHRASES)


def phase3_run_upgrade(
    ssh: paramiko.SSHClient, previous_version: str | None, log: Log
) -> tuple[bool, str, str | None, datetime | None]:
    """Upgrade the instance in place, one version step.

    Nothing loops here on purpose: the platform upgrades one step at a time, so
    two releases apart is two runs, and an operator may want to lag the newest
    release.

    :param previous_version: What step 1 read, so a version that does not move
        can be reported as an upgrade that did not happen.
    :returns: ``(succeeded, why it did not, the new version, the moment it
        was upgraded)``.
    """
    # The platform's own files are baked into the image as root, because the
    # image build runs as root. The upgrader runs as the web-server user, so
    # that its cache writes stay readable to the process serving the pages —
    # which means it cannot overwrite those files without this first.
    log("Ensuring source tree is writable by www-data...", "info")
    exit_code, _ = run_remote(
        ssh,
        f"docker compose -f {COMPOSE_FILE} exec -T -u root espocrm "
        "chown -R www-data:www-data /var/www/html",
        log,
    )
    if exit_code != 0:
        return False, (
            "Could not adjust source-tree ownership inside the container "
            f"(exit {exit_code}). Upgrade aborted before any changes."
        ), None, None

    log("Running EspoCRM upgrade...", "info")
    exit_code, output = run_remote(
        ssh,
        f"docker compose -f {COMPOSE_FILE} exec -T -u www-data "
        "espocrm php command.php upgrade -y",
        log,
        get_pty=True,
    )

    if _output_says_no_upgrade(output):
        return False, (
            "EspoCRM's in-container upgrader reports no upgrade is available. "
            "The public release feed may be ahead of the auto-upgrade channel — "
            "wait a day or two, or apply the newer version manually."
        ), None, None

    if exit_code != 0:
        if "permission" in output.lower():
            return False, (
                "Upgrade failed with a permission error. Check that the data "
                "volume is owned by www-data."
            ), None, None
        return False, f"EspoCRM upgrade command failed (exit {exit_code})", None, None

    log("Clearing application cache...", "info")
    run_remote(
        ssh,
        f"docker compose -f {COMPOSE_FILE} exec -T -u www-data "
        "espocrm php command.php clear-cache",
        log,
    )

    new_version = get_current_version(ssh, log)
    if new_version is None:
        return False, (
            "Upgrade command completed but the new version could not be read "
            "back. Investigate the container state before retrying."
        ), None, None
    if previous_version and new_version == previous_version:
        return False, (
            f"Upgrade command completed but the version is still {new_version}. "
            "The upgrader appears to have run without applying a change."
        ), None, None

    upgraded_at = datetime.now(UTC)
    log(f"Upgrade applied. New version: {new_version}", "info")
    return True, "", new_version, upgraded_at


# ---------------------------------------------------------------------------
# Step 4 — check the upgrade landed
# ---------------------------------------------------------------------------

def phase4_verify_upgrade(
    ssh: paramiko.SSHClient, domain: str, log: Log
) -> tuple[bool, list[dict]]:
    """Check the instance answers, renders, and reports a version.

    Every check is probed once. Unlike the check after a fresh install, the web
    server here was already serving before the upgrade began, so there is no
    warm-up to wait through.

    :returns: ``(every check passed, one result per check)``.
    """
    results: list[dict] = []

    def run_check(
        name: str, command: str, passed_when: Callable[[int, str], bool]
    ) -> bool:
        log(f"Verifying: {name}", "info")
        exit_code, output = run_remote(ssh, command, log)
        passed = passed_when(exit_code, output)
        log(f"  {'PASS' if passed else 'FAIL'}: {name}", "info" if passed else "error")
        results.append(
            {
                "check": name,
                "passed": passed,
                "detail": output[:200] if not passed else "",
            }
        )
        return passed

    run_check(
        "Containers running",
        f"docker compose -f {COMPOSE_FILE} ps",
        lambda code, out: code == 0 and "espocrm" in out.lower(),
    )
    run_check(
        "HTTPS response",
        f"curl -sI https://{domain} | head -1",
        lambda code, out: "200" in out,
    )
    run_check(
        "Login page renders",
        f"curl -sL https://{domain} | head -100",
        lambda code, out: "espocrm" in out.lower(),
    )

    # Read separately rather than through run_check, because what is judged is
    # a value read across several commands, not one command's output.
    log("Verifying: Version reads back", "info")
    version = get_current_version(ssh, log)
    passed = version is not None
    log(
        f"  {'PASS' if passed else 'FAIL'}: Version reads back",
        "info" if passed else "error",
    )
    results.append(
        {
            "check": "Version reads back",
            "passed": passed,
            "detail": "" if passed else "could not detect version",
        }
    )

    return all(result["passed"] for result in results), results


# ---------------------------------------------------------------------------
# Driving the steps against a registered instance
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class UpgradeOutcome:
    """What an upgrade attempt did, for a caller that has to report it.

    :ivar succeeded: Every step completed and the version moved.
    :ivar error: Why it did not, in the words the failing step used.
    :ivar previous_version: What the instance was running before.
    :ivar new_version: What it is running now, when the upgrade applied.
    :ivar backup_paths: The backup folders on the server, newest last.
    :ivar checks: One result per verification check, empty when the upgrade
        never reached the verification step.
    """

    succeeded: bool
    error: str = ""
    previous_version: str | None = None
    new_version: str | None = None
    backup_paths: list[str] = dataclasses.field(default_factory=list)
    checks: list[dict] = dataclasses.field(default_factory=list)


def _require_deploy_config(instance_identifier: str) -> dict:
    with session_scope() as session:
        config = instance_deploy_config.get_deploy_config(session, instance_identifier)
    if config is None:
        raise DeployPhaseError(
            "connect",
            f"{instance_identifier} has no recorded server connection, so it "
            "cannot be reached. Record its address and credentials first.",
        )
    if not config.get("ssh_host"):
        raise DeployPhaseError(
            "connect",
            f"{instance_identifier} has no server address recorded, so it "
            "cannot be reached.",
        )
    return config


@contextmanager
def _connected(config: dict, resolve_secret: Callable[[str], str]) -> Iterator:
    """Open the remote login the steps run through, and close it afterwards.

    A key is held in the store as its text and has to exist as a file for the
    length of the session; a password is used as it stands.
    """
    credential_ref = config.get("ssh_credential_ref")
    if not credential_ref:
        raise DeployPhaseError(
            "connect",
            "No remote-login credential is recorded for this instance.",
        )
    credential = resolve_secret(credential_ref)
    auth_type = config.get("ssh_auth_type") or "key"

    with ExitStack() as stack:
        if auth_type == "key":
            credential = stack.enter_context(private_key_file(credential))
        client = connect_ssh(
            SelfHostedConfig(
                ssh_host=config["ssh_host"],
                ssh_port=config.get("ssh_port") or 22,
                ssh_username=config.get("ssh_username") or "root",
                ssh_credential=credential,
                ssh_auth_type=auth_type,
                domain=config.get("domain") or "",
                letsencrypt_email=config.get("letsencrypt_email") or "",
                db_password="",
                db_root_password="",
                admin_username=config.get("admin_username") or "",
                admin_password="",
                admin_email=config.get("admin_email") or "",
            )
        )
        stack.callback(_close_quietly, client)
        yield client


def _close_quietly(client) -> None:
    try:
        client.close()
    except Exception:  # pragma: no cover - best effort
        logger.debug("closing the remote login raised", exc_info=True)


def check_for_upgrade(
    instance_identifier: str,
    log: Log,
    *,
    resolve_secret: Callable[[str], str] = secrets.get_secret,
) -> tuple[str | None, str | None]:
    """Read what the instance is running and what the platform has published.

    Both are written to the store, so the screen that renders them stops
    rendering nothing. The published version is only written when it could be
    read: a rate limit or a broken connection must not erase what is known.

    :returns: ``(the version running, the version published)``, either of which
        may be None when it could not be read.
    """
    config = _require_deploy_config(instance_identifier)
    with _connected(config, resolve_secret) as client:
        current = get_current_version(client, log)
    latest = get_latest_version()
    if latest is None:
        log(
            "Could not read the latest published release; keeping the one "
            "already recorded.",
            "warning",
        )

    fields: dict[str, object] = {}
    if current is not None:
        fields["current_espocrm_version"] = current
    if latest is not None:
        fields["latest_espocrm_version"] = latest
    if fields:
        with session_scope() as session:
            instance_deploy_config.upsert_deploy_config(
                session, instance_identifier, **fields
            )
    return current, latest


def upgrade_instance(
    instance_identifier: str,
    log: Log,
    *,
    resolve_secret: Callable[[str], str] = secrets.get_secret,
) -> UpgradeOutcome:
    """Upgrade one registered instance by one version step, and record it.

    The four steps run in order and the first failure ends the attempt: a
    backup that did not complete must never be followed by an upgrade. What
    each step learned is written to the store as soon as it is known, so a
    failure part way still leaves the record true — a backup taken before an
    upgrade that then failed is still a backup the operator has.

    :param resolve_secret: How a stored reference becomes its value; replaced
        in tests.
    """
    config = _require_deploy_config(instance_identifier)
    domain = config.get("domain") or ""
    db_root_password_ref = config.get("db_root_password_ref")
    if not db_root_password_ref:
        return UpgradeOutcome(
            succeeded=False,
            error=(
                "No database administrator password is recorded for this "
                "instance, so no backup can be taken and the upgrade will not "
                "start."
            ),
        )
    db_root_password = resolve_secret(db_root_password_ref)

    with _connected(config, resolve_secret) as client:
        ready, error, previous = phase1_pre_upgrade_checks(client, log)
        if previous is not None:
            _record(instance_identifier, current_espocrm_version=previous)
        if not ready:
            return UpgradeOutcome(False, error, previous_version=previous)

        backed_up, error, backup_paths = phase2_backup(
            client, db_root_password, decode_backup_paths(config.get("last_backup_paths")), log
        )
        _record(
            instance_identifier, last_backup_paths=encode_backup_paths(backup_paths)
        )
        if not backed_up:
            return UpgradeOutcome(
                False, error, previous_version=previous, backup_paths=backup_paths
            )

        upgraded, error, new_version, upgraded_at = phase3_run_upgrade(
            client, previous, log
        )
        if not upgraded:
            return UpgradeOutcome(
                False, error, previous_version=previous, backup_paths=backup_paths
            )
        _record(
            instance_identifier,
            current_espocrm_version=new_version,
            last_upgrade_at=upgraded_at,
        )

        verified, checks = phase4_verify_upgrade(client, domain, log)

    if not verified:
        failed = ", ".join(c["check"] for c in checks if not c["passed"])
        return UpgradeOutcome(
            False,
            f"The upgrade applied but the instance did not pass every check: {failed}.",
            previous_version=previous,
            new_version=new_version,
            backup_paths=backup_paths,
            checks=checks,
        )
    return UpgradeOutcome(
        True,
        "",
        previous_version=previous,
        new_version=new_version,
        backup_paths=backup_paths,
        checks=checks,
    )


def _record(instance_identifier: str, **fields) -> None:
    """Write what a step learned to the instance's recorded server details."""
    with session_scope() as session:
        instance_deploy_config.upsert_deploy_config(
            session, instance_identifier, **fields
        )


def decode_backup_paths(stored: str | None) -> list[str]:
    """Read the backup folders out of the single column that holds them.

    The column is text and holds the folders as a list written in the same
    form version 1 wrote it, because the column and its contents are the ones
    version 1 left behind. Text that is not a list of folders reads as none
    rather than raising: a column nobody has written yet, or written by hand,
    must not stop an upgrade.
    """
    if not stored:
        return []
    try:
        decoded = json.loads(stored)
    except json.JSONDecodeError:
        logger.warning("last_backup_paths is not readable as a list: %r", stored)
        return []
    if not isinstance(decoded, list):
        logger.warning("last_backup_paths is not a list: %r", stored)
        return []
    return [str(item) for item in decoded]


def encode_backup_paths(paths: list[str]) -> str:
    """Write the backup folders into the single column that holds them."""
    return json.dumps(list(paths))
