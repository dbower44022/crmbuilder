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
RELEASE_INFO_URL = "https://api.github.com/repos/espocrm/espocrm/releases/latest"

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


_PHP_KEY_PATTERN = (
    r"['\"](?:version|currentVersion)['\"]"
    r"\s*=>\s*"
    r"['\"](\d+\.\d+\.\d+)['\"]"
)
_PHP_CONST_PATTERN = r"\bVERSION\b[^=\n]*=\s*['\"](\d+\.\d+\.\d+)['\"]"


def get_current_version(
    ssh: paramiko.SSHClient,
    log: LogCallback | None = None,
) -> str | None:
    """Read the EspoCRM version from inside the running container.

    Probes the files where the version may live, in order of authority:

    1. ``data/state.php`` — per-install state (EspoCRM 8.x+).
    2. ``data/config-internal.php`` — system-managed config (EspoCRM 8.x+).
    3. ``application/Espo/Core/Application.php`` — the ``VERSION`` class
       constant.
    4. ``data/config.php`` — user-editable config (EspoCRM 7.x and older).

    Each file is ``cat``'d through the SSH channel and parsed in Python.
    The file contents are deliberately NOT routed through the UI log
    callback (``data/config.php`` contains DB credentials).

    On total failure, dumps a container directory listing to the log so
    the operator can see what is actually in the image.

    :param ssh: Connected SSH client.
    :param log: Optional ``(message, level)`` callback.
    :returns: Version string (e.g., ``"8.4.0"``) or None if not detectable.
    """
    probes = [
        ("data/state.php", _PHP_KEY_PATTERN),
        ("data/config-internal.php", _PHP_KEY_PATTERN),
        ("application/Espo/Core/Application.php", _PHP_CONST_PATTERN),
        ("data/config.php", _PHP_KEY_PATTERN),
    ]
    for path, pattern in probes:
        cmd = (
            f"docker compose -f {COMPOSE_FILE} exec -T espocrm "
            f"cat {path}"
        )
        # No log callback — contents may include credentials.
        exit_code, output = run_remote(ssh, cmd)
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
        log(
            "Version not found in known files — dumping container layout:",
            "warning",
        )
        diag_cmd = (
            f"docker compose -f {COMPOSE_FILE} exec -T espocrm sh -c "
            "'pwd; echo ---data---; ls -la data/ 2>&1 | head -25; "
            "echo ---application/Espo/Core---; "
            "ls -la application/Espo/Core/Application.php 2>&1'"
        )
        run_remote(ssh, diag_cmd, log)
    return None


def get_latest_version(timeout: int = 10) -> str | None:
    """Fetch the latest stable EspoCRM version from GitHub's releases API.

    EspoCRM publishes every release as a GitHub tag, and ``releases/latest``
    deliberately excludes prereleases, so its ``tag_name`` is the canonical
    latest stable. The older ``espocrm.com/downloads/release-info.json``
    endpoint was retired and now serves a 404 HTML page.

    :param timeout: HTTP timeout in seconds.
    :returns: Latest version string or None on failure.
    """
    request = urllib.request.Request(
        RELEASE_INFO_URL,
        headers={"Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
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
            "Could not read current EspoCRM version from data/state.php, "
            "data/config-internal.php, Application.php, or data/config.php. "
            "See the diagnostic dump above for what is actually in the "
            "container."
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


_NO_UPGRADE_PHRASES = (
    "no upgrade",
    "up to date",
    "up-to-date",
    "already on the latest",
    "nothing to upgrade",
    "no new version",
)


def _output_says_no_upgrade(output: str) -> bool:
    """Return True if the upgrader's output indicates no upgrade was applied.

    EspoCRM's CLI sometimes reports "up to date" with exit code 0 — its
    own check disagrees with the external release feed we pre-flighted
    against. Treating that as success would leave the run log claiming a
    successful upgrade when nothing actually changed.
    """
    out_lower = output.lower()
    return any(phrase in out_lower for phrase in _NO_UPGRADE_PHRASES)


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
    # The EspoCRM source tree (``application/``, ``client/``, etc.) is
    # baked into the image and root-owned, since Docker COPY runs as
    # root. The upgrader runs as www-data so cache writes don't strand
    # PHP-FPM with unreadable files — but that means www-data cannot
    # overwrite the source tree without help. chown it first.
    log("Ensuring source tree is writable by www-data...", "info")
    chown_cmd = (
        f"docker compose -f {COMPOSE_FILE} exec -T -u root espocrm "
        "chown -R www-data:www-data /var/www/html"
    )
    chown_exit, chown_output = run_remote(ssh, chown_cmd, log)
    if chown_exit != 0:
        return False, (
            "Could not adjust source-tree ownership inside the container "
            f"(exit {chown_exit}). Upgrade aborted before any changes."
        )

    log("Running EspoCRM upgrade...", "info")
    upgrade_cmd = (
        f"docker compose -f {COMPOSE_FILE} exec -T -u www-data "
        "espocrm php command.php upgrade -y"
    )
    exit_code, output = run_remote(ssh, upgrade_cmd, log, get_pty=True)

    if _output_says_no_upgrade(output):
        return False, (
            "EspoCRM's in-container upgrader reports no upgrade is "
            "available. The public release feed may be ahead of the "
            "auto-upgrade channel — wait a day or two, or apply the "
            "newer version manually."
        )

    if exit_code != 0:
        out_lower = output.lower()
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
    if new_version is None:
        return False, (
            "Upgrade command completed but the new version could not be "
            "read back. Investigate the container state before retrying."
        )
    previous = config.current_espocrm_version
    if previous and new_version == previous:
        return False, (
            f"Upgrade command completed but the version is still "
            f"{new_version}. The upgrader appears to have run without "
            "applying a change."
        )
    config.current_espocrm_version = new_version
    config.last_upgrade_at = datetime.now(UTC).isoformat()
    log(f"Upgrade applied. New version: {new_version}", "info")
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

    log("Verifying: Version reads back", "info")
    version_read = get_current_version(ssh, log)
    version_passed = version_read is not None
    log(
        f"  {'PASS' if version_passed else 'FAIL'}: Version reads back",
        "info" if version_passed else "error",
    )
    results.append({
        "check": "Version reads back",
        "passed": version_passed,
        "detail": "" if version_passed else "could not detect version",
    })

    overall = all(r["passed"] for r in results)
    return overall, results
