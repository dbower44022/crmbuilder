"""EspoCRM in-place upgrade orchestration.

Runs the EspoCRM CLI upgrader (``php command.php upgrade``) inside the
running container, after taking a database + data-volume backup.
Mirrors the four-phase pattern of ``ssh_deploy.py``.

Takes ``InstanceDeployConfig`` (post-deploy persistent layer) rather
than the deploy-time ``SelfHostedConfig``. Pure Python, no Qt.

See PRDs/product/features/feat-server-management.md §6.3.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime

import paramiko

from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.core.deployment.ssh_deploy import run_remote

logger = logging.getLogger(__name__)


COMPOSE_FILE = "/var/www/espocrm/docker-compose.yml"
COMPOSE_DIR = "/var/www/espocrm"
BACKUP_ROOT = "/var/backups/espocrm"
BACKUP_RETENTION = 3
RELEASE_INFO_URL = "https://www.espocrm.com/downloads/release-info.json"

# Log callback type matches ssh_deploy.py: (message, level)
LogCallback = Callable[[str, str], None]


# ── Version helpers ────────────────────────────────────────────────────


def parse_version(value: str) -> tuple[int, int, int] | None:
    """Parse a semantic version string into a (major, minor, patch) tuple.

    :param value: Version string such as ``"8.4.0"`` or ``"v8.4.1"``.
    :returns: Tuple of ints or None if unparseable.
    """
    if not value:
        return None
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def is_upgrade_available(current: str | None, latest: str | None) -> bool:
    """Return True iff a parseable ``latest`` is greater than ``current``."""
    cur = parse_version(current) if current else None
    lat = parse_version(latest) if latest else None
    if cur is None or lat is None:
        return False
    return lat > cur


def is_major_upgrade(current: str | None, latest: str | None) -> bool:
    """Return True iff latest is a major version bump above current."""
    cur = parse_version(current) if current else None
    lat = parse_version(latest) if latest else None
    if cur is None or lat is None:
        return False
    return lat[0] > cur[0]


def mask_secrets(command: str, secret_values: list[str]) -> str:
    """Replace secret strings with placeholder text for safe logging.

    Sorts replacements longest-first so a shorter secret that is a
    substring of a longer one does not corrupt the masking pass.
    """
    pairs = [(v, "[secret]") for v in secret_values if v]
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    safe = command
    for value, label in pairs:
        safe = safe.replace(value, label)
    return safe


# ── Version detection ─────────────────────────────────────────────────


def get_current_version(
    ssh: paramiko.SSHClient,
    log: LogCallback | None = None,
) -> str | None:
    """Read the EspoCRM version from inside the running container.

    :param ssh: Connected SSH client.
    :param log: Optional ``(message, level)`` callback.
    :returns: Version string (e.g., ``"8.4.0"``) or None if not detectable.
    """
    cmd = (
        f"docker compose -f {COMPOSE_FILE} exec -T espocrm "
        "grep -oE \"'version'\\s*=>\\s*'[^']+'\" data/config.php "
        "| head -1 | sed -E \"s/.*'([^']+)'\\$/\\1/\""
    )
    exit_code, output = run_remote(ssh, cmd, log)
    if exit_code != 0:
        return None
    text = output.strip().splitlines()[-1].strip() if output.strip() else ""
    parsed = parse_version(text)
    if parsed is None:
        return None
    return f"{parsed[0]}.{parsed[1]}.{parsed[2]}"


def get_latest_version(timeout: int = 10) -> str | None:
    """Fetch the latest stable EspoCRM version from the official release feed.

    :param timeout: HTTP timeout in seconds.
    :returns: Latest version string or None on failure.
    """
    try:
        with urllib.request.urlopen(
            RELEASE_INFO_URL, timeout=timeout
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        logger.warning("Failed to fetch latest EspoCRM version: %s", exc)
        return None

    for key in ("version", "stable", "latest"):
        value = data.get(key) if isinstance(data, dict) else None
        if value:
            parsed = parse_version(str(value))
            if parsed:
                return f"{parsed[0]}.{parsed[1]}.{parsed[2]}"
    return None


# ── Phase 1: Pre-upgrade checks ───────────────────────────────────────


def phase1_pre_upgrade_checks(
    ssh: paramiko.SSHClient,
    config: InstanceDeployConfig,
    log: LogCallback,
) -> tuple[bool, str]:
    """Phase 1 — Verify the system is ready for upgrade.

    Confirms the EspoCRM container is up, reads the current version,
    and checks free disk space. Mutates ``config.current_espocrm_version``
    in place on success.

    :returns: (success, error_message).
    """
    log("Checking Docker containers...", "info")
    exit_code, output = run_remote(
        ssh, f"docker compose -f {COMPOSE_FILE} ps", log
    )
    if exit_code != 0:
        return False, "Docker compose not available or compose file missing"
    if "espocrm" not in output.lower():
        return False, "EspoCRM container is not running"

    log("Reading current EspoCRM version...", "info")
    current = get_current_version(ssh, log)
    if current is None:
        return False, (
            "Could not read current EspoCRM version from data/config.php. "
            "The container may not be fully initialised."
        )
    config.current_espocrm_version = current
    log(f"Current version: {current}", "info")

    log("Checking free disk space...", "info")
    exit_code, output = run_remote(
        ssh,
        "df -BM --output=avail / | tail -1 | tr -dc '0-9'",
        log,
    )
    if exit_code == 0 and output.strip().isdigit():
        free_mb = int(output.strip())
        if free_mb < 2048:
            return False, (
                f"Only {free_mb} MB free on /. Need at least 2 GB to "
                "safely back up and upgrade. Free disk space and retry."
            )
        log(f"Free space: {free_mb} MB", "info")
    else:
        log(
            "WARNING: Could not determine free disk space — proceeding",
            "warning",
        )

    return True, ""


# ── Phase 2: Backup ───────────────────────────────────────────────────


def phase2_backup(
    ssh: paramiko.SSHClient,
    config: InstanceDeployConfig,
    log: LogCallback,
) -> tuple[bool, str]:
    """Phase 2 — Take a database + data-volume backup.

    Writes a timestamped folder under ``/var/backups/espocrm/`` and
    prunes older backups beyond ``BACKUP_RETENTION``. Mutates
    ``config.last_backup_paths`` in place.

    :returns: (success, error_message).
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_dir = f"{BACKUP_ROOT}/{timestamp}"

    log(f"Creating backup directory: {backup_dir}", "info")
    exit_code, _ = run_remote(ssh, f"mkdir -p {backup_dir}", log)
    if exit_code != 0:
        return False, f"Could not create backup directory {backup_dir}"

    log("Dumping database...", "info")
    dump_cmd = (
        f"docker compose -f {COMPOSE_FILE} exec -T "
        f"-e MYSQL_PWD={config.db_root_password} espocrm-db "
        "mariadb-dump --single-transaction --routines --triggers "
        f"-u root espocrm | gzip > {backup_dir}/db.sql.gz"
    )
    safe = mask_secrets(dump_cmd, [config.db_root_password])
    log(f"$ {safe[:160]}", "info")
    exit_code, _ = run_remote(ssh, dump_cmd)
    if exit_code != 0:
        return False, "Database backup (mariadb-dump) failed"

    log("Archiving data volume...", "info")
    tar_cmd = (
        f"tar -czf {backup_dir}/data.tar.gz -C {COMPOSE_DIR} data 2>&1 "
        "| tail -20"
    )
    exit_code, _ = run_remote(ssh, tar_cmd, log)
    if exit_code != 0:
        return False, "Data volume archive (tar) failed"

    config.last_backup_paths = (config.last_backup_paths or []) + [backup_dir]
    config.last_backup_paths = prune_old_backups(ssh, config, log)

    log(f"Backup complete: {backup_dir}", "info")
    return True, ""


def prune_old_backups(
    ssh: paramiko.SSHClient,
    config: InstanceDeployConfig,
    log: LogCallback,
) -> list[str]:
    """Delete all but the most recent ``BACKUP_RETENTION`` backups.

    :returns: Updated list of remaining backup paths, newest last.
    """
    exit_code, output = run_remote(
        ssh,
        f"ls -1d {BACKUP_ROOT}/*/ 2>/dev/null | sort",
        log,
    )
    if exit_code != 0 or not output.strip():
        return list(config.last_backup_paths or [])

    paths = [line.rstrip("/") for line in output.strip().splitlines()]
    if len(paths) <= BACKUP_RETENTION:
        return paths

    to_delete = paths[: len(paths) - BACKUP_RETENTION]
    for path in to_delete:
        log(f"Pruning old backup: {path}", "info")
        run_remote(ssh, f"rm -rf {path}", log)

    return paths[-BACKUP_RETENTION:]


# ── Phase 3: Run upgrade ──────────────────────────────────────────────


def phase3_run_upgrade(
    ssh: paramiko.SSHClient,
    config: InstanceDeployConfig,
    log: LogCallback,
) -> tuple[bool, str]:
    """Phase 3 — Run the EspoCRM CLI upgrader inside the container.

    Mutates ``config.current_espocrm_version`` and
    ``config.last_upgrade_at`` in place on success.

    :returns: (success, error_message).
    """
    log("Running EspoCRM upgrade...", "info")
    upgrade_cmd = (
        f"docker compose -f {COMPOSE_FILE} exec -T -u www-data "
        "espocrm php command.php upgrade -y"
    )
    exit_code, output = run_remote(ssh, upgrade_cmd, log, get_pty=True)
    if exit_code != 0:
        out_lower = output.lower()
        if "no upgrade" in out_lower or "up to date" in out_lower:
            return False, "EspoCRM reports no upgrade is available"
        if "permission" in out_lower:
            return False, (
                "Upgrade failed with a permission error. Check that the "
                "data volume is owned by www-data."
            )
        return False, f"EspoCRM upgrade command failed (exit {exit_code})"

    log("Clearing application cache...", "info")
    cache_cmd = (
        f"docker compose -f {COMPOSE_FILE} exec -T -u www-data "
        "espocrm php command.php clear-cache"
    )
    run_remote(ssh, cache_cmd, log)

    new_version = get_current_version(ssh, log)
    if new_version:
        config.current_espocrm_version = new_version
        log(f"Upgrade applied. New version: {new_version}", "info")
    config.last_upgrade_at = datetime.now(UTC).isoformat()
    return True, ""


# ── Phase 4: Verify upgrade ───────────────────────────────────────────


def phase4_verify_upgrade(
    ssh: paramiko.SSHClient,
    config: InstanceDeployConfig,
    log: LogCallback,
) -> tuple[bool, list[dict]]:
    """Phase 4 — Confirm the upgrade landed cleanly.

    :returns: (overall_pass, list of check result dicts).
    """
    results: list[dict] = []

    def run_check(
        name: str, command: str, check_fn: Callable[[int, str], bool]
    ) -> bool:
        log(f"Verifying: {name}", "info")
        exit_code, output = run_remote(ssh, command, log)
        passed = check_fn(exit_code, output)
        status = "PASS" if passed else "FAIL"
        log(f"  {status}: {name}", "info" if passed else "error")
        results.append({
            "check": name,
            "passed": passed,
            "detail": output[:200] if not passed else "",
        })
        return passed

    run_check(
        "Containers running",
        f"docker compose -f {COMPOSE_FILE} ps",
        lambda ec, out: ec == 0 and "espocrm" in out.lower(),
    )

    run_check(
        "HTTPS response",
        f"curl -sI https://{config.domain} | head -1",
        lambda ec, out: "200" in out,
    )

    run_check(
        "Login page renders",
        f"curl -sL https://{config.domain} | head -100",
        lambda ec, out: "espocrm" in out.lower(),
    )

    run_check(
        "Version reads back",
        f"docker compose -f {COMPOSE_FILE} exec -T espocrm "
        "grep -oE \"'version'\\s*=>\\s*'[^']+'\" data/config.php | head -1",
        lambda ec, out: ec == 0 and "version" in out.lower(),
    )

    overall = all(r["passed"] for r in results)
    return overall, results
