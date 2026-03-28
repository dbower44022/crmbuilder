"""SSH execution, phase logic, and deploy config read/write."""

import json
import logging
import socket
import ssl
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import dns.resolver
import paramiko

from espo_impl.core.models import DeployConfig

logger = logging.getLogger(__name__)


# ── Config file read/write ─────────────────────────────────────────────


def load_deploy_config(
    instances_dir: Path, slug: str
) -> DeployConfig | None:
    """Load deployment config for an instance.

    :param instances_dir: Directory containing instance files.
    :param slug: Instance slug.
    :returns: DeployConfig or None if not found.
    """
    path = instances_dir / f"{slug}_deploy.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return DeployConfig(**data)
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        logger.warning("Failed to load deploy config %s: %s", path, exc)
        return None


def save_deploy_config(
    instances_dir: Path, slug: str, config: DeployConfig
) -> None:
    """Save deployment config for an instance.

    :param instances_dir: Directory containing instance files.
    :param slug: Instance slug.
    :param config: Deployment configuration.
    """
    instances_dir.mkdir(parents=True, exist_ok=True)
    path = instances_dir / f"{slug}_deploy.json"
    data = asdict(config)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ── DNS validation ─────────────────────────────────────────────────────


def check_dns(domain: str, expected_ip: str) -> tuple[bool, str]:
    """Check whether domain resolves to expected_ip.

    :param domain: Fully qualified domain name.
    :param expected_ip: Expected IPv4 address.
    :returns: (True, "") on success; (False, message) on failure.
    """
    try:
        answers = dns.resolver.resolve(domain, "A")
        resolved_ips = [rdata.address for rdata in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return False, f"{domain} does not resolve (NXDOMAIN)"
    except dns.resolver.NoAnswer:
        return False, f"{domain} has no A record"
    except dns.exception.DNSException as exc:
        return False, f"DNS lookup failed for {domain}: {exc}"

    if expected_ip in resolved_ips:
        return True, ""

    return (
        False,
        f"{domain} resolves to {', '.join(resolved_ips)} "
        f"but expected {expected_ip}",
    )


# ── SSH helpers ────────────────────────────────────────────────────────


def connect_ssh(
    host: str, username: str, key_path: str
) -> paramiko.SSHClient:
    """Open an SSH connection using key-based authentication.

    :param host: Remote host IP or hostname.
    :param username: SSH username.
    :param key_path: Path to private key file.
    :returns: Connected SSHClient.
    :raises paramiko.SSHException: On connection failure.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username=username,
        key_filename=key_path,
        timeout=30,
    )
    return client


def mask_credentials(command: str, config: DeployConfig) -> str:
    """Replace credential values with placeholder strings.

    :param command: Raw command string.
    :param config: Deploy config containing credential values.
    :returns: Command with credentials masked.
    """
    safe = command
    for val, label in [
        (config.db_password, "[db_password]"),
        (config.db_root_password, "[db_root_password]"),
        (config.admin_password, "[admin_password]"),
    ]:
        if val:
            safe = safe.replace(val, label)
    return safe


def run_remote(
    ssh: paramiko.SSHClient,
    command: str,
    log_callback: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    """Execute a command on the remote server.

    Streams stdout and stderr line by line to log_callback if provided.

    :param ssh: Connected SSH client.
    :param command: Command to execute.
    :param log_callback: Optional line callback.
    :returns: (exit_code, full_output).
    """
    _stdin, stdout, stderr = ssh.exec_command(command, timeout=600)
    output_lines: list[str] = []

    for line in stdout:
        text = line.rstrip("\n")
        output_lines.append(text)
        if log_callback:
            log_callback(text)

    for line in stderr:
        text = line.rstrip("\n")
        output_lines.append(text)
        if log_callback:
            log_callback(text)

    exit_code = stdout.channel.recv_exit_status()
    return exit_code, "\n".join(output_lines)


# ── Deployment phases ──────────────────────────────────────────────────


def phase1_server_prep(
    ssh: paramiko.SSHClient,
    config: DeployConfig,
    log_callback: Callable[[str], None],
) -> tuple[bool, str]:
    """Phase 1 — Server Preparation.

    Updates packages, installs Docker, configures swap and firewall.

    :param ssh: Connected SSH client.
    :param config: Deploy config.
    :param log_callback: Line callback for live output.
    :returns: (success, error_message).
    """
    commands = [
        # System update
        "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
        # Docker prerequisites
        "apt-get install -y curl ca-certificates gnupg",
        # Docker GPG key
        "install -m 0755 -d /etc/apt/keyrings && "
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg "
        "-o /etc/apt/keyrings/docker.asc && "
        "chmod a+r /etc/apt/keyrings/docker.asc",
        # Docker apt repository
        'echo "deb [arch=$(dpkg --print-architecture) '
        "signed-by=/etc/apt/keyrings/docker.asc] "
        "https://download.docker.com/linux/ubuntu "
        '$(. /etc/os-release && echo "$VERSION_CODENAME") stable" '
        "| tee /etc/apt/sources.list.d/docker.list > /dev/null",
        # Install Docker
        "apt-get update && "
        "apt-get install -y docker-ce docker-ce-cli containerd.io "
        "docker-buildx-plugin docker-compose-plugin",
        # Swap (2 GB)
        "if [ ! -f /swapfile ]; then "
        "fallocate -l 2G /swapfile && chmod 600 /swapfile && "
        "mkswap /swapfile && swapon /swapfile && "
        'echo "/swapfile none swap sw 0 0" >> /etc/fstab; fi',
        # Firewall
        "ufw allow 22 && ufw allow 80 && ufw allow 443 && "
        "echo y | ufw enable",
    ]

    for cmd in commands:
        log_callback(f"$ {cmd[:120]}")
        exit_code, output = run_remote(ssh, cmd, log_callback)
        if exit_code != 0:
            return False, f"Command failed (exit {exit_code}): {cmd[:80]}"

    return True, ""


def phase2_install_espocrm(
    ssh: paramiko.SSHClient,
    config: DeployConfig,
    log_callback: Callable[[str], None],
) -> tuple[bool, str]:
    """Phase 2 — EspoCRM Installation via official installer script.

    :param ssh: Connected SSH client.
    :param config: Deploy config.
    :param log_callback: Line callback for live output.
    :returns: (success, error_message).
    """
    # Download installer
    dl_cmd = (
        "wget -N https://github.com/espocrm/espocrm-installer/"
        "releases/latest/download/install.sh"
    )
    log_callback(f"$ {dl_cmd}")
    exit_code, _ = run_remote(ssh, dl_cmd, log_callback)
    if exit_code != 0:
        return False, "Failed to download EspoCRM installer"

    # Run installer
    install_cmd = (
        f"sudo bash install.sh -y --ssl --letsencrypt "
        f"--domain={config.full_domain} "
        f"--email={config.letsencrypt_email} "
        f"--admin-username={config.admin_username} "
        f"--admin-password={config.admin_password} "
        f"--db-password={config.db_password} "
        f"--db-root-password={config.db_root_password}"
    )
    safe_cmd = mask_credentials(install_cmd, config)
    log_callback(f"$ {safe_cmd}")
    exit_code, output = run_remote(ssh, install_cmd, log_callback)
    if exit_code != 0:
        return False, f"EspoCRM installer failed (exit {exit_code})"

    return True, ""


def phase3_post_install(
    ssh: paramiko.SSHClient,
    config: DeployConfig,
    log_callback: Callable[[str], None],
) -> tuple[bool, str]:
    """Phase 3 — Post-Install Configuration.

    Verifies containers, cron, and reads SSL certificate expiry.
    Updates config.cert_expiry_date in place.

    :param ssh: Connected SSH client.
    :param config: Deploy config (cert_expiry_date updated in place).
    :param log_callback: Line callback for live output.
    :returns: (success, error_message).
    """
    # Check Docker containers
    log_callback("Checking Docker containers...")
    exit_code, output = run_remote(
        ssh,
        "docker compose -f /var/www/espocrm/docker-compose.yml ps",
        log_callback,
    )
    if exit_code != 0:
        return False, "Docker containers not running"

    for name in ("espocrm", "espocrm-db", "espocrm-nginx"):
        if name not in output.lower():
            return False, f"Container '{name}' not found in docker compose ps"

    # Check cron
    log_callback("Checking cron configuration...")
    exit_code, output = run_remote(
        ssh, "crontab -l 2>/dev/null | grep espocrm", log_callback
    )
    if exit_code != 0:
        log_callback("WARNING: No EspoCRM cron entry found")

    # Read SSL certificate expiry
    log_callback("Reading SSL certificate expiry...")
    cert_cmd = (
        f"openssl s_client -connect {config.full_domain}:443 "
        f"</dev/null 2>/dev/null | openssl x509 -noout -enddate"
    )
    exit_code, output = run_remote(ssh, cert_cmd, log_callback)
    if exit_code == 0 and "notAfter=" in output:
        expiry_str = output.split("notAfter=")[-1].strip()
        try:
            expiry_dt = datetime.strptime(
                expiry_str, "%b %d %H:%M:%S %Y %Z"
            )
            config.cert_expiry_date = expiry_dt.strftime("%Y-%m-%d")
            log_callback(
                f"SSL certificate expires: {config.cert_expiry_date}"
            )
        except ValueError:
            log_callback(f"WARNING: Could not parse cert expiry: {expiry_str}")
    else:
        log_callback("WARNING: Could not read SSL certificate expiry")

    config.deployed_at = datetime.now(UTC).isoformat()
    return True, ""


def phase4_verify(
    ssh: paramiko.SSHClient,
    config: DeployConfig,
    log_callback: Callable[[str], None],
) -> tuple[bool, list[dict]]:
    """Phase 4 — Verification.

    Runs all verification checks.

    :param ssh: Connected SSH client.
    :param config: Deploy config.
    :param log_callback: Line callback for live output.
    :returns: (overall_pass, list of check result dicts).
    """
    results: list[dict] = []

    def run_check(
        name: str, command: str, check_fn: Callable[[int, str], bool]
    ) -> bool:
        log_callback(f"Verifying: {name}")
        exit_code, output = run_remote(ssh, command, log_callback)
        passed = check_fn(exit_code, output)
        status = "PASS" if passed else "FAIL"
        log_callback(f"  {status}: {name}")
        results.append({
            "check": name,
            "passed": passed,
            "detail": output[:200] if not passed else "",
        })
        return passed

    # Docker containers running
    run_check(
        "Docker containers running",
        "docker compose -f /var/www/espocrm/docker-compose.yml ps",
        lambda ec, out: ec == 0 and "espocrm" in out.lower(),
    )

    # HTTP redirect
    run_check(
        "HTTP redirect to HTTPS",
        f"curl -sI http://{config.full_domain} | head -1",
        lambda ec, out: "301" in out or "302" in out,
    )

    # HTTPS response
    run_check(
        "HTTPS response",
        f"curl -sI https://{config.full_domain} | head -1",
        lambda ec, out: "200" in out,
    )

    # SSL certificate valid
    run_check(
        "SSL certificate valid",
        f"openssl s_client -connect {config.full_domain}:443 "
        f"</dev/null 2>/dev/null | openssl x509 -noout -dates",
        lambda ec, out: ec == 0 and "notAfter" in out,
    )

    # EspoCRM login page
    run_check(
        "EspoCRM login page present",
        f"curl -sL https://{config.full_domain} | head -100",
        lambda ec, out: "espocrm" in out.lower() or "EspoCRM" in out,
    )

    # Cron job
    run_check(
        "Cron job configured",
        "crontab -l 2>/dev/null | grep espocrm",
        lambda ec, out: ec == 0 and "espocrm" in out.lower(),
    )

    # DB connectivity
    run_check(
        "Database connectivity",
        "docker exec espocrm-db mariadb-admin ping 2>/dev/null",
        lambda ec, out: ec == 0 and "alive" in out.lower(),
    )

    overall = all(r["passed"] for r in results)
    return overall, results


# ── Cleanup helpers ────────────────────────────────────────────────────


def cleanup_phase1(
    ssh: paramiko.SSHClient,
    log_callback: Callable[[str], None],
) -> None:
    """Best-effort cleanup for a failed Phase 1.

    :param ssh: Connected SSH client.
    :param log_callback: Line callback.
    """
    log_callback("Running Phase 1 cleanup...")
    for cmd in [
        "apt-get remove -y docker-ce docker-ce-cli containerd.io || true",
        "rm -f /etc/apt/sources.list.d/docker.list || true",
    ]:
        try:
            run_remote(ssh, cmd, log_callback)
        except Exception as exc:
            log_callback(f"Cleanup error: {exc}")


def cleanup_phase2(
    ssh: paramiko.SSHClient,
    log_callback: Callable[[str], None],
) -> None:
    """Best-effort cleanup for a failed Phase 2.

    :param ssh: Connected SSH client.
    :param log_callback: Line callback.
    """
    log_callback("Running Phase 2 cleanup...")
    for cmd in [
        "docker compose -f /var/www/espocrm/docker-compose.yml down --volumes || true",
        "rm -f install.sh || true",
    ]:
        try:
            run_remote(ssh, cmd, log_callback)
        except Exception as exc:
            log_callback(f"Cleanup error: {exc}")


# ── Certificate expiry helpers ─────────────────────────────────────────


def get_cert_expiry(domain: str) -> str | None:
    """Check SSL certificate expiry for domain.

    :param domain: Fully qualified domain name.
    :returns: ISO date string (YYYY-MM-DD) or None on failure.
    """
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                expiry_str = cert["notAfter"]
                expiry_dt = datetime.strptime(
                    expiry_str, "%b %d %H:%M:%S %Y %Z"
                )
                return expiry_dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def cert_days_remaining(expiry_date_str: str | None) -> int | None:
    """Return days until certificate expiry.

    :param expiry_date_str: ISO date string (YYYY-MM-DD) or None.
    :returns: Days remaining (negative if expired), or None.
    """
    if expiry_date_str is None:
        return None
    try:
        expiry = datetime.strptime(expiry_date_str, "%Y-%m-%d").replace(
            tzinfo=UTC
        )
        delta = expiry - datetime.now(UTC)
        return delta.days
    except ValueError:
        return None
