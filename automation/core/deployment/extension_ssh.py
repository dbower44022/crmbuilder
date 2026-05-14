"""EspoCRM extension install + re-install orchestration.

Drives the EspoCRM CLI extension command
(``php command.php extension --file=...``) inside the running container,
after taking the same database + data-volume backup that the upgrade
path uses. Pure Python, no Qt.

The CLI command handles re-installs transparently — when a newer version
of the same extension is supplied, EspoCRM uninstalls the prior version
and installs the new one inside the same call. Step 1 of the install
flow simply needs to detect the version delta so the UI can label the
button correctly; the SSH-side work is identical for first install and
re-install.

Uninstall is intentionally not exposed. EspoCRM keeps the extension
available for re-install when the same name is re-uploaded, which is
all the v1 flow promises.

Companion to ``upgrade_ssh.py``; reuses ``phase2_backup`` outright.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
import zipfile
from collections.abc import Callable
from pathlib import Path

import paramiko

from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.core.deployment.ssh_deploy import run_remote
from automation.core.deployment.upgrade_ssh import (
    COMPOSE_FILE,
    phase2_backup,
)

logger = logging.getLogger(__name__)


LogCallback = Callable[[str, str], None]


# Where uploaded zips land on the host before being copied into the
# container. /tmp is fine — the file is small (<2 MB) and short-lived.
HOST_UPLOAD_DIR = "/tmp"

# In-container path the extension command reads from.
CONTAINER_UPLOAD_DIR = "/tmp"


# ── Manifest parsing ───────────────────────────────────────────────────


@dataclasses.dataclass
class ExtensionManifest:
    """Subset of an EspoCRM extension manifest.json needed by the app."""

    name: str
    version: str
    acceptable_versions: list[str] = dataclasses.field(default_factory=list)
    description: str | None = None
    author: str | None = None
    release_date: str | None = None


def parse_extension_manifest(zip_path: str | Path) -> ExtensionManifest:
    """Read manifest.json from an EspoCRM extension zip.

    EspoCRM extensions are zip archives containing a top-level
    ``manifest.json`` plus the module payload. This helper extracts the
    fields the install flow needs without unpacking the rest.

    :param zip_path: Path to the extension .zip file.
    :returns: Parsed ExtensionManifest.
    :raises FileNotFoundError: If ``zip_path`` does not exist.
    :raises ValueError: If the zip has no manifest.json or it is
        malformed.
    """
    path = Path(zip_path)
    if not path.exists():
        raise FileNotFoundError(f"Extension zip not found: {path}")

    with zipfile.ZipFile(path) as zf:
        # EspoCRM extensions ship manifest.json at the archive root, but
        # the entry name has a leading slash in the packs we've seen
        # ('/manifest.json'). Match on basename to handle either form.
        manifest_entry = next(
            (n for n in zf.namelist() if n.lstrip("/") == "manifest.json"),
            None,
        )
        if manifest_entry is None:
            raise ValueError(
                f"{path.name} has no manifest.json — not a valid "
                "EspoCRM extension zip"
            )
        raw = zf.read(manifest_entry)

    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path.name} manifest.json is not valid JSON: {exc}"
        ) from exc

    name = data.get("name")
    version = data.get("version")
    if not name or not version:
        raise ValueError(
            f"{path.name} manifest.json missing required "
            "'name' or 'version' field"
        )

    acceptable = data.get("acceptableVersions") or []
    if not isinstance(acceptable, list):
        acceptable = [str(acceptable)]

    return ExtensionManifest(
        name=str(name),
        version=str(version),
        acceptable_versions=[str(v) for v in acceptable],
        description=data.get("description"),
        author=data.get("author"),
        release_date=data.get("releaseDate"),
    )


# ── Phase result type ──────────────────────────────────────────────────


@dataclasses.dataclass
class InstallResult:
    """Outcome of an end-to-end extension install attempt.

    ``failed_phase`` is the integer phase number (1–4) when the run
    aborts; None on success.
    """

    success: bool
    failed_phase: int | None = None
    error: str = ""
    manifest: ExtensionManifest | None = None
    backup_paths: list[str] = dataclasses.field(default_factory=list)


# ── Phase 1: pre-check ─────────────────────────────────────────────────


def phase_pre_check(
    ssh: paramiko.SSHClient,
    config: InstanceDeployConfig,
    manifest: ExtensionManifest,
    log: LogCallback,
) -> tuple[bool, str]:
    """Phase 1 — Confirm the container is running and reachable.

    Mirrors the front of ``phase1_pre_upgrade_checks`` but skips the
    free-disk-space check used for full version upgrades — extension
    installs are small (<10 MB after unpack).
    """
    log("Checking Docker containers...", "info")
    exit_code, output = run_remote(
        ssh, f"docker compose -f {COMPOSE_FILE} ps", log,
    )
    if exit_code != 0:
        return False, "Docker compose not available or compose file missing"
    if "espocrm" not in output.lower():
        return False, "EspoCRM container is not running"

    log(
        f"Installing {manifest.name} v{manifest.version}...",
        "info",
    )
    return True, ""


# ── Phase 2: backup ────────────────────────────────────────────────────
#
# Reuses upgrade_ssh.phase2_backup unchanged. Re-exported here so the
# orchestrator stays self-contained and the worker code can import all
# four phases from the same module.

phase_backup = phase2_backup


# ── Phase 3: install ───────────────────────────────────────────────────


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(zip_path: str | Path) -> str:
    """Sanitize an extension filename for use in shell command paths.

    EspoCRM zips arrive named like ``advanced-pack-3.12.1.zip`` — the
    characters are already shell-safe, but defensively strip anything
    outside ``[A-Za-z0-9._-]`` to keep the install command interpolation
    injection-proof against future filenames.
    """
    return _SAFE_NAME_RE.sub("_", Path(zip_path).name)


def phase_install(
    ssh: paramiko.SSHClient,
    config: InstanceDeployConfig,
    manifest: ExtensionManifest,
    zip_path: str | Path,
    log: LogCallback,
) -> tuple[bool, str]:
    """Phase 3 — Upload the zip, run the CLI install, clear cache.

    SFTPs the zip to the host's ``/tmp``, copies it into the espocrm
    container, runs ``php command.php extension --file=...``, then
    clears the cache. Removes the temporary files on the host and
    inside the container after the command returns regardless of
    outcome (best-effort cleanup).

    :returns: (success, error_message).
    """
    local_path = Path(zip_path)
    if not local_path.exists():
        return False, f"Local zip not found: {local_path}"

    safe_name = _safe_filename(local_path)
    host_path = f"{HOST_UPLOAD_DIR}/{safe_name}"
    container_path = f"{CONTAINER_UPLOAD_DIR}/{safe_name}"

    log(f"Uploading {local_path.name} to {host_path}...", "info")
    try:
        sftp = ssh.open_sftp()
        try:
            sftp.put(str(local_path), host_path)
        finally:
            sftp.close()
    except Exception as exc:
        return False, f"SFTP upload failed: {exc}"

    try:
        log(
            f"Copying zip into espocrm container at {container_path}...",
            "info",
        )
        cp_cmd = (
            f"docker compose -f {COMPOSE_FILE} cp "
            f"{host_path} espocrm:{container_path}"
        )
        exit_code, _ = run_remote(ssh, cp_cmd, log)
        if exit_code != 0:
            return False, "docker compose cp into espocrm container failed"

        log(
            f"Installing {manifest.name} via EspoCRM CLI...",
            "info",
        )
        install_cmd = (
            f"docker compose -f {COMPOSE_FILE} exec -T -u www-data "
            f"espocrm php command.php extension --file={container_path}"
        )
        exit_code, output = run_remote(ssh, install_cmd, log, get_pty=True)
        if exit_code != 0:
            lower = output.lower()
            if "incompatible" in lower or "not compatible" in lower:
                return False, (
                    f"{manifest.name} v{manifest.version} reports it is "
                    "not compatible with the current EspoCRM version. "
                    "Upgrade EspoCRM first or supply a matching extension "
                    "version."
                )
            return False, (
                f"EspoCRM extension install failed (exit {exit_code}). "
                "Review the log for the CLI's stderr output."
            )

        log("Clearing application cache...", "info")
        cache_cmd = (
            f"docker compose -f {COMPOSE_FILE} exec -T -u www-data "
            "espocrm php command.php clear-cache"
        )
        run_remote(ssh, cache_cmd, log)
    finally:
        _cleanup_uploads(ssh, host_path, container_path, log)

    return True, ""


def _cleanup_uploads(
    ssh: paramiko.SSHClient,
    host_path: str,
    container_path: str,
    log: LogCallback,
) -> None:
    """Best-effort removal of the temporary zip in container and on host."""
    run_remote(
        ssh,
        f"docker compose -f {COMPOSE_FILE} exec -T espocrm "
        f"rm -f {container_path}",
    )
    run_remote(ssh, f"rm -f {host_path}")


# ── Phase 4: verify ────────────────────────────────────────────────────


def phase_verify(
    ssh: paramiko.SSHClient,
    config: InstanceDeployConfig,
    manifest: ExtensionManifest,
    log: LogCallback,
) -> tuple[bool, str]:
    """Phase 4 — Confirm the site still responds.

    Mirrors the HTTPS smoke check from ``phase4_verify_upgrade``. A
    container-side check that the extension's Module.json shows up
    under ``application/Espo/Modules/`` would be tighter but couples
    us to EspoCRM internals; the CLI's exit code in phase 3 already
    confirms install success, so this phase is the post-install
    liveness gate.
    """
    log("Confirming site responds on HTTPS...", "info")
    exit_code, output = run_remote(
        ssh, f"curl -sI https://{config.domain} | head -1", log,
    )
    if exit_code != 0 or "200" not in output:
        return False, (
            f"HTTPS smoke check failed for https://{config.domain}. "
            "The extension installer may have left the site in a bad "
            "state — investigate before retrying."
        )

    log("Verifying EspoCRM container still healthy...", "info")
    exit_code, output = run_remote(
        ssh, f"docker compose -f {COMPOSE_FILE} ps", log,
    )
    if exit_code != 0 or "espocrm" not in output.lower():
        return False, "EspoCRM container not reporting after install"

    return True, ""


# ── Orchestrator ───────────────────────────────────────────────────────


def install_extension(
    ssh: paramiko.SSHClient,
    config: InstanceDeployConfig,
    zip_path: str | Path,
    log: LogCallback,
    *,
    skip_backup: bool = False,
) -> InstallResult:
    """Run all four extension-install phases in sequence.

    Aborts on the first failed phase and returns the phase number plus
    error in the result. ``skip_backup`` is exposed so a UI batch flow
    that installs N extensions in one session can take a single backup
    up front and pass True on subsequent calls — there is no
    correctness reason to back up between extensions in the same
    session.

    :returns: InstallResult capturing outcome, backup paths, and parsed
        manifest. The caller is expected to write the corresponding
        ExtensionInstall row via ``extension_repo.record_install`` on
        success.
    """
    try:
        manifest = parse_extension_manifest(zip_path)
    except (FileNotFoundError, ValueError) as exc:
        log(f"Manifest read failed: {exc}", "error")
        return InstallResult(
            success=False, failed_phase=0, error=str(exc),
        )

    log("=== Phase 1: Pre-check ===", "info")
    ok, err = phase_pre_check(ssh, config, manifest, log)
    if not ok:
        return InstallResult(
            success=False, failed_phase=1, error=err, manifest=manifest,
        )

    if not skip_backup:
        log("=== Phase 2: Backup ===", "info")
        ok, err = phase_backup(ssh, config, log)
        if not ok:
            return InstallResult(
                success=False, failed_phase=2, error=err,
                manifest=manifest,
            )
    else:
        log("=== Phase 2: Backup skipped (batch run) ===", "info")

    log("=== Phase 3: Install ===", "info")
    ok, err = phase_install(ssh, config, manifest, zip_path, log)
    if not ok:
        return InstallResult(
            success=False, failed_phase=3, error=err, manifest=manifest,
            backup_paths=list(config.last_backup_paths or []),
        )

    log("=== Phase 4: Verify ===", "info")
    ok, err = phase_verify(ssh, config, manifest, log)
    if not ok:
        return InstallResult(
            success=False, failed_phase=4, error=err, manifest=manifest,
            backup_paths=list(config.last_backup_paths or []),
        )

    log(
        f"{manifest.name} v{manifest.version} installed successfully.",
        "info",
    )
    return InstallResult(
        success=True, manifest=manifest,
        backup_paths=list(config.last_backup_paths or []),
    )
