"""Self-hosted deployment logic — SSH, DNS, EspoCRM installer.

Ported from ``espo_impl/core/deploy_manager.py``.  Pure Python, no Qt.

L2 PRD v1.16 §14.12.5.1.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from collections.abc import Callable
from datetime import datetime

import dns.resolver
import paramiko

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class SelfHostedConfig:
    """Configuration captured by the self-hosted wizard path.

    Mirrors the subset of the legacy ``DeployConfig`` that the wizard
    collects, without coupling to the legacy data model.
    """

    ssh_host: str
    ssh_port: int
    ssh_username: str
    ssh_credential: str          # password or key path
    ssh_auth_type: str           # "password" or "key"
    domain: str
    letsencrypt_email: str
    db_password: str
    db_root_password: str
    admin_username: str
    admin_password: str
    admin_email: str


# ---------------------------------------------------------------------------
# DNS
# ---------------------------------------------------------------------------

def check_dns(domain: str, expected_ip: str) -> tuple[bool, str]:
    """Check whether *domain* resolves to *expected_ip*.

    :returns: ``(True, "")`` on success; ``(False, message)`` on failure.
    """
    try:
        answers = dns.resolver.resolve(domain, "A")
        resolved = [rdata.address for rdata in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return False, f"{domain} does not resolve (NXDOMAIN)"
    except dns.resolver.NoAnswer:
        return False, f"{domain} has no A record"
    except dns.exception.DNSException as exc:
        return False, f"DNS lookup failed for {domain}: {exc}"

    if expected_ip in resolved:
        return True, ""
    return (
        False,
        f"{domain} resolves to {', '.join(resolved)} but expected {expected_ip}",
    )


def wait_for_dns(
    domain: str,
    expected_ip: str,
    log: Callable[[str, str], None],
    *,
    timeout: int = 600,
    interval: int = 30,
) -> bool:
    """Poll DNS until *domain* resolves to *expected_ip*.

    :param log: ``(message, level)`` callback.
    :param timeout: Total wait time in seconds.
    :param interval: Seconds between retries.
    :returns: True if DNS resolved within the timeout.
    """
    elapsed = 0
    while elapsed < timeout:
        ok, msg = check_dns(domain, expected_ip)
        if ok:
            log("DNS validated successfully", "info")
            return True
        remaining = timeout - elapsed
        log(
            f"DNS not ready: {msg}. Retrying in {interval}s "
            f"({remaining}s remaining)...",
            "warning",
        )
        time.sleep(interval)
        elapsed += interval
    log("DNS validation timed out after 10 minutes", "error")
    return False


# ---------------------------------------------------------------------------
# SSH helpers
# ---------------------------------------------------------------------------

def connect_ssh(config: SelfHostedConfig) -> paramiko.SSHClient:
    """Open an SSH connection.

    Supports both key-based and password authentication.

    :returns: Connected ``SSHClient``.
    :raises paramiko.SSHException: On connection failure.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: dict = {
        "hostname": config.ssh_host,
        "port": config.ssh_port,
        "username": config.ssh_username,
        "timeout": 30,
    }
    if config.ssh_auth_type == "key":
        kwargs["key_filename"] = config.ssh_credential
    else:
        kwargs["password"] = config.ssh_credential
    client.connect(**kwargs)
    return client


def run_remote(
    ssh: paramiko.SSHClient,
    command: str,
    log: Callable[[str, str], None] | None = None,
    *,
    get_pty: bool = False,
) -> tuple[int, str]:
    """Execute a command on the remote server, streaming output.

    :returns: ``(exit_code, full_output)``.
    """
    _stdin, stdout, stderr = ssh.exec_command(
        command, timeout=600, get_pty=get_pty,
    )
    lines: list[str] = []
    for line in stdout:
        text = line.rstrip("\n")
        lines.append(text)
        if log:
            log(text, "info")
    for line in stderr:
        text = line.rstrip("\n")
        lines.append(text)
        if log:
            log(text, "info")
    return stdout.channel.recv_exit_status(), "\n".join(lines)


def mask_credentials(command: str, config: SelfHostedConfig) -> str:
    """Replace credential values with placeholder strings for logging."""
    replacements = [
        (config.db_password, "[db_password]"),
        (config.db_root_password, "[db_root_password]"),
        (config.admin_password, "[admin_password]"),
    ]
    replacements = [(v, lbl) for v, lbl in replacements if v]
    replacements.sort(key=lambda x: len(x[0]), reverse=True)
    safe = command
    for val, label in replacements:
        safe = safe.replace(val, label)
    return safe


# ---------------------------------------------------------------------------
# Deployment phases
# ---------------------------------------------------------------------------

def phase_server_prep(
    ssh: paramiko.SSHClient,
    log: Callable[[str, str], None],
) -> tuple[bool, str]:
    """Server preparation — packages, Docker, swap, firewall.

    :returns: ``(success, error_message)``.
    """
    commands = [
        "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
        "apt-get install -y curl ca-certificates gnupg",
        "install -m 0755 -d /etc/apt/keyrings && "
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg "
        "-o /etc/apt/keyrings/docker.asc && "
        "chmod a+r /etc/apt/keyrings/docker.asc",
        'echo "deb [arch=$(dpkg --print-architecture) '
        "signed-by=/etc/apt/keyrings/docker.asc] "
        "https://download.docker.com/linux/ubuntu "
        '$(. /etc/os-release && echo "$VERSION_CODENAME") stable" '
        "| tee /etc/apt/sources.list.d/docker.list > /dev/null",
        "apt-get update && "
        "apt-get install -y docker-ce docker-ce-cli containerd.io "
        "docker-buildx-plugin docker-compose-plugin",
        "if [ ! -f /swapfile ]; then "
        "fallocate -l 2G /swapfile && chmod 600 /swapfile && "
        "mkswap /swapfile && swapon /swapfile && "
        'echo "/swapfile none swap sw 0 0" >> /etc/fstab; fi',
        "ufw allow 22 && ufw allow 80 && ufw allow 443 && "
        "echo y | ufw enable",
    ]
    for cmd in commands:
        log(f"$ {cmd[:120]}", "info")
        exit_code, _ = run_remote(ssh, cmd, log)
        if exit_code != 0:
            return False, f"Command failed (exit {exit_code}): {cmd[:80]}"
    return True, ""


def phase_install_espocrm(
    ssh: paramiko.SSHClient,
    config: SelfHostedConfig,
    log: Callable[[str, str], None],
) -> tuple[bool, str]:
    """Download and run the official EspoCRM installer.

    :returns: ``(success, error_message)``.
    """
    dl_cmd = (
        "wget -N https://github.com/espocrm/espocrm-installer/"
        "releases/latest/download/install.sh"
    )
    log(f"$ {dl_cmd}", "info")
    exit_code, _ = run_remote(ssh, dl_cmd, log)
    if exit_code != 0:
        return False, "Failed to download EspoCRM installer"

    install_cmd = (
        f"sudo bash install.sh -y --clean --ssl --letsencrypt "
        f"--domain={config.domain} "
        f"--email={config.letsencrypt_email} "
        f"--admin-username={config.admin_username} "
        f"--admin-password={config.admin_password} "
        f"--db-password={config.db_password} "
        f"--db-root-password={config.db_root_password}"
    )
    safe_cmd = mask_credentials(install_cmd, config)
    log(f"$ {safe_cmd}", "info")
    exit_code, _ = run_remote(ssh, install_cmd, log, get_pty=True)
    if exit_code != 0:
        return False, f"EspoCRM installer failed (exit {exit_code})"
    return True, ""


def phase_post_install(
    ssh: paramiko.SSHClient,
    config: SelfHostedConfig,
    log: Callable[[str, str], None],
) -> tuple[bool, str, str | None]:
    """Post-install — verify containers, read cert expiry.

    :returns: ``(success, error_message, cert_expiry_date or None)``.
    """
    log("Checking Docker containers...", "info")
    exit_code, output = run_remote(
        ssh, "docker compose -f /var/www/espocrm/docker-compose.yml ps", log,
    )
    if exit_code != 0:
        return False, "Docker containers not running", None

    log("Checking cron configuration...", "info")
    run_remote(ssh, "crontab -l 2>/dev/null | grep espocrm", log)

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

    return True, "", cert_expiry


def phase_verify(
    ssh: paramiko.SSHClient,
    domain: str,
    log: Callable[[str, str], None],
) -> tuple[bool, list[dict]]:
    """Run verification checks against the deployed instance.

    :returns: ``(overall_pass, list of check result dicts)``.
    """
    results: list[dict] = []

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

    run_check(
        "Docker containers running",
        "docker compose -f /var/www/espocrm/docker-compose.yml ps",
        lambda ec, out: ec == 0 and "espocrm" in out.lower(),
    )
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
    run_check(
        "Cron job configured",
        "crontab -l 2>/dev/null | grep espocrm",
        lambda ec, out: ec == 0 and "espocrm" in out.lower(),
    )
    run_check(
        "Database connectivity",
        "docker compose -f /var/www/espocrm/docker-compose.yml ps "
        "| grep -iE 'mysql|mariadb|espocrm-db'",
        lambda ec, out: ec == 0 and "up" in out.lower(),
    )

    return all(r["passed"] for r in results), results


def cleanup_phase1(
    ssh: paramiko.SSHClient,
    log: Callable[[str, str], None],
) -> None:
    """Best-effort cleanup for a failed server prep."""
    log("Running Phase 1 cleanup...", "warning")
    for cmd in [
        "apt-get remove -y docker-ce docker-ce-cli containerd.io || true",
        "rm -f /etc/apt/sources.list.d/docker.list || true",
    ]:
        try:
            run_remote(ssh, cmd, log)
        except Exception as exc:
            log(f"Cleanup error: {exc}", "error")


def cleanup_phase2(
    ssh: paramiko.SSHClient,
    log: Callable[[str, str], None],
) -> None:
    """Best-effort cleanup for a failed EspoCRM install."""
    log("Running Phase 2 cleanup...", "warning")
    for cmd in [
        "docker compose -f /var/www/espocrm/docker-compose.yml down --volumes || true",
        "rm -f install.sh || true",
    ]:
        try:
            run_remote(ssh, cmd, log)
        except Exception as exc:
            log(f"Cleanup error: {exc}", "error")
