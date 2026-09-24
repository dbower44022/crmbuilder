"""The five steps that build a server, run over a remote login — PI-556 (REQ-638, DEC-1140).

Absorbed from version 1's ``automation.core.deployment.ssh_deploy`` so version 2
provisions a server without reaching into version 1. Nothing in version 1's
deployment layer can be deleted while version 2 imports it, so this move is what
opens that door; the frozen list in
``tests/crmbuilder_v2/test_version_one_imports.py`` is the gate made visible.

The surface is deliberately unchanged from the one :mod:`crmbuilder_v2.deploy.runner`
already calls — :class:`SelfHostedConfig`, :func:`connect_ssh`, and the four
``phase_*`` functions — so the runner's own tests keep holding the behaviour
across the move.

Two things version 1 offers are not here, both by DEC-1140:

* **Undoing a half-finished attempt** (version 1's ``cleanup_phase1`` /
  ``cleanup_phase2``). A failed run keeps everything it built and names it in the
  log, so a retry resumes from the checkpoint (DEC-945).
* **Waiting for a domain name to resolve** (version 1's ``check_dns`` /
  ``wait_for_dns``). The runner asks three public resolvers directly, because a
  locally cached negative answer had blocked a run for the zone's negative
  caching time — see ``runner.resolve_a_public``.
"""

from __future__ import annotations

import dataclasses
import logging
import shlex
import time
from collections.abc import Callable
from datetime import datetime

import paramiko

logger = logging.getLogger("crmbuilder_v2.deploy.ssh")

#: ``(message, level)`` — the log callback every step writes progress through.
Log = Callable[[str, str], None]

#: Where the installer puts the container definition it manages.
COMPOSE_FILE = "/var/www/espocrm/docker-compose.yml"


@dataclasses.dataclass
class SelfHostedConfig:
    """Everything a provisioning step needs to reach and configure one server.

    :ivar ssh_host: The server's address.
    :ivar ssh_port: The remote-login port.
    :ivar ssh_username: The account the steps run as.
    :ivar ssh_credential: A private-key path, or a password — which one is
        decided by ``ssh_auth_type``.
    :ivar ssh_auth_type: ``key`` or ``password``.
    :ivar domain: The name the certificate is issued for and the checks probe.
    :ivar letsencrypt_email: The address the certificate authority notifies.
    :ivar db_password: The application's own database password.
    :ivar db_root_password: The database administrator's password.
    :ivar admin_username: The CRM administrator's login name.
    :ivar admin_password: The CRM administrator's password.
    :ivar admin_email: The CRM administrator's address.
    """

    ssh_host: str
    ssh_port: int
    ssh_username: str
    ssh_credential: str
    ssh_auth_type: str
    domain: str
    letsencrypt_email: str
    db_password: str
    db_root_password: str
    admin_username: str
    admin_password: str
    admin_email: str


# ---------------------------------------------------------------------------
# Reaching the server
# ---------------------------------------------------------------------------

def connect_ssh(config: SelfHostedConfig) -> paramiko.SSHClient:
    """Open the remote login the steps run through.

    The server's host key is accepted on sight. A run reaches a machine created
    minutes earlier by the run itself, so there is no key to have known; the
    address came from the provider's own API in the same run.

    :raises paramiko.SSHException: The connection could not be made.
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
    log: Log | None = None,
    *,
    get_pty: bool = False,
    input_text: str | None = None,
) -> tuple[int, str]:
    """Run one command on the server and read its output back.

    Both output streams are read to exhaustion before the exit status is
    collected, so a command that writes more than the channel's buffer cannot
    deadlock against a status read.

    :param log: Written to line by line as output arrives; omitted where the
        caller judges the output itself rather than showing it.
    :param get_pty: Ask for a terminal. The platform's installer needs one.
    :param input_text: Written to the command's standard input, which is then
        closed. This is how a password reaches a command without appearing on
        any command line a process listing could show.
    :returns: ``(exit_code, the two streams joined by newlines)``.
    """
    stdin, stdout, stderr = ssh.exec_command(command, timeout=600, get_pty=get_pty)
    if input_text is not None:
        stdin.write(input_text)
        stdin.flush()
        stdin.channel.shutdown_write()
    lines: list[str] = []
    for stream in (stdout, stderr):
        for line in stream:
            text = line.rstrip("\n")
            lines.append(text)
            if log:
                log(text, "info")
    return stdout.channel.recv_exit_status(), "\n".join(lines)


def mask_credentials(command: str, config: SelfHostedConfig) -> str:
    """Replace every password in ``command`` with a name before it is logged.

    The longest value is replaced first, so a password that contains another
    one cannot leave the shorter one's tail behind. An empty value is skipped,
    because replacing the empty string would rewrite the whole command.
    """
    replacements = [
        (config.db_password, "[db_password]"),
        (config.db_root_password, "[db_root_password]"),
        (config.admin_password, "[admin_password]"),
    ]
    replacements = [(value, label) for value, label in replacements if value]
    replacements.sort(key=lambda pair: len(pair[0]), reverse=True)
    safe = command
    for value, label in replacements:
        safe = safe.replace(value, label)
    return safe


def mask_secrets(command: str, secret_values: list[str]) -> str:
    """Replace each given value in ``command`` with ``[secret]`` before logging.

    The same rule as :func:`mask_credentials`, for callers that hold loose
    values rather than a whole configuration — the upgrade and recovery steps,
    which carry one password each. Longest first, empty values skipped.
    """
    pairs = [(value, "[secret]") for value in secret_values if value]
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    safe = command
    for value, label in pairs:
        safe = safe.replace(value, label)
    return safe


# ---------------------------------------------------------------------------
# The five steps
# ---------------------------------------------------------------------------

def phase_server_prep(ssh: paramiko.SSHClient, log: Log) -> tuple[bool, str]:
    """Prepare the machine: packages, the container runtime, swap, the firewall.

    :returns: ``(succeeded, why it did not)``.
    """
    commands = [
        # Wait for the package lock rather than fail against it: a freshly
        # created machine runs its own unattended upgrade for its first
        # minutes and holds the lock throughout (PI-419 live proof, DEP-003 —
        # "Could not get lock").
        "apt-get -o DPkg::Lock::Timeout=600 update && "
        "DEBIAN_FRONTEND=noninteractive "
        "apt-get -o DPkg::Lock::Timeout=600 upgrade -y",
        "apt-get -o DPkg::Lock::Timeout=600 install -y curl ca-certificates gnupg",
        "install -m 0755 -d /etc/apt/keyrings && "
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg "
        "-o /etc/apt/keyrings/docker.asc && "
        "chmod a+r /etc/apt/keyrings/docker.asc",
        'echo "deb [arch=$(dpkg --print-architecture) '
        "signed-by=/etc/apt/keyrings/docker.asc] "
        "https://download.docker.com/linux/ubuntu "
        '$(. /etc/os-release && echo "$VERSION_CODENAME") stable" '
        "| tee /etc/apt/sources.list.d/docker.list > /dev/null",
        "apt-get -o DPkg::Lock::Timeout=600 update && "
        "apt-get -o DPkg::Lock::Timeout=600 install -y "
        "docker-ce docker-ce-cli containerd.io "
        "docker-buildx-plugin docker-compose-plugin",
        "if [ ! -f /swapfile ]; then "
        "fallocate -l 2G /swapfile && chmod 600 /swapfile && "
        "mkswap /swapfile && swapon /swapfile && "
        'echo "/swapfile none swap sw 0 0" >> /etc/fstab; fi',
        "ufw allow 22 && ufw allow 80 && ufw allow 443 && echo y | ufw enable",
    ]
    for command in commands:
        log(f"$ {command[:120]}", "info")
        exit_code, _ = run_remote(ssh, command, log)
        if exit_code != 0:
            return False, f"Command failed (exit {exit_code}): {command[:80]}"
    return True, ""


def phase_install_espocrm(
    ssh: paramiko.SSHClient, config: SelfHostedConfig, log: Log, *, secure: bool = True
) -> tuple[bool, str]:
    """Fetch and run the platform's own installer.

    :param secure: Install with a Let's Encrypt certificate. ``False`` installs
        the installer's plain web mode for the same address, for a server whose
        web address does not point at it yet; the self-healing certificate job
        switches it to the secure mode later (PI-571 / REQ-648, REQ-651).
    :returns: ``(succeeded, why it did not)``.
    """
    download = (
        "wget -N https://github.com/espocrm/espocrm-installer/"
        "releases/latest/download/install.sh"
    )
    log(f"$ {download}", "info")
    exit_code, _ = run_remote(ssh, download, log)
    if exit_code != 0:
        return False, "Failed to download EspoCRM installer"

    # Every value is quoted for the shell, so a quote or a space in one cannot
    # break the command or change it (PI-563, REQ-641).
    options = [
        ("domain", config.domain, None),
        *([("email", config.letsencrypt_email, None)] if secure else []),
        ("admin-username", config.admin_username, None),
        ("admin-password", config.admin_password, "[admin_password]"),
        ("db-password", config.db_password, "[db_password]"),
        ("db-root-password", config.db_root_password, "[db_root_password]"),
    ]
    prefix = "sudo bash install.sh -y --clean" + (" --ssl --letsencrypt" if secure else "")
    install = " ".join(
        [prefix] + [f"--{name}={shlex.quote(value)}" for name, value, _ in options]
    )
    # The command carries three passwords; what reaches the log carries none.
    # The logged line is built with the names in place of the passwords rather
    # than by replacing them, because quoting can split a password that holds a
    # quote into pieces a replacement would not find.
    shown = " ".join(
        [prefix]
        + [
            f"--{name}={label if label else shlex.quote(value)}"
            for name, value, label in options
        ]
    )
    log(f"$ {shown}", "info")
    exit_code, _ = run_remote(ssh, install, log, get_pty=True)
    if exit_code != 0:
        return False, f"EspoCRM installer failed (exit {exit_code})"
    return True, ""


def phase_post_install(
    ssh: paramiko.SSHClient, config: SelfHostedConfig, log: Log, *, secure: bool = True
) -> tuple[bool, str, str | None]:
    """Correct file ownership, prove it took, and read the certificate's expiry.

    :returns: ``(succeeded, why it did not, the expiry date or None)``.
    """
    log("Checking Docker containers...", "info")
    exit_code, _output = run_remote(
        ssh, f"docker compose -f {COMPOSE_FILE} ps", log
    )
    if exit_code != 0:
        return False, "Docker containers not running", None

    # REQ-328: give the web-server user the custom metadata tree. The image is
    # built as root, and later root-run work can leave that tree root-owned —
    # which blocks every custom-object-type creation silently, because the web
    # server cannot write the metadata files.
    log("Ensuring custom metadata tree is owned by www-data...", "info")
    chown = (
        f"docker compose -f {COMPOSE_FILE} exec -T -u root espocrm sh -c "
        "'mkdir -p /var/www/html/custom/Espo/Custom/Resources && "
        "chown -R www-data:www-data /var/www/html/custom'"
    )
    # The exit status is not judged here on purpose: the writability check
    # immediately below is the real verdict, and it reports a remedy.
    run_remote(ssh, chown, log)

    # REQ-329: prove the web-server user can write there before the instance is
    # used, so a failure arrives now with a remedy rather than later as an
    # opaque server error that leaves a half-created object type behind.
    log("Verifying custom metadata directory is writable by www-data...", "info")
    writable = (
        f"docker compose -f {COMPOSE_FILE} exec -T -u www-data espocrm sh -c "
        "'d=/var/www/html/custom/Espo/Custom/Resources; "
        "touch \"$d/.crmbuilder_write_test\" && rm -f \"$d/.crmbuilder_write_test\"'"
    )
    exit_code, _ = run_remote(ssh, writable, log)
    if exit_code != 0:
        return False, (
            "Custom metadata directory is not writable by the web server "
            "user (www-data) at /var/www/html/custom/Espo/Custom/Resources — "
            "custom-entity creation would fail. Remedy: docker compose -f "
            f"{COMPOSE_FILE} exec -u root espocrm chown -R www-data:www-data "
            "/var/www/html/custom"
        ), None

    # Shown, not judged: the scheduler is checked for real by phase_verify.
    log("Checking cron configuration...", "info")
    run_remote(ssh, "crontab -l 2>/dev/null | grep espocrm", log)

    # Read the certificate from the file rather than through the web server.
    # Reading it does not wait on the web server coming up — the live-port
    # approach met the same warm-up race the verification step polls around.
    # The installer keeps the certificate inside its own installation folder;
    # the system certificate folder is kept as a fallback for older layouts.
    # Looking only in the second had found no certificate on any instance this
    # installer built (read off the CBM test instance, PI-563).
    if not secure:
        # Plain web mode: there is no certificate yet to read (PI-571).
        return True, "", None

    log("Reading SSL certificate expiry...", "info")
    exit_code, cert_output, cert_path = 1, "", ""
    for cert_path in certificate_paths(config.domain):
        exit_code, cert_output = run_remote(
            ssh, f"openssl x509 -in {cert_path} -noout -enddate", log
        )
        if exit_code == 0:
            break
    cert_expiry: str | None = None
    if exit_code == 0 and "notAfter=" in cert_output:
        expiry_text = cert_output.split("notAfter=")[-1].strip()
        try:
            cert_expiry = datetime.strptime(
                expiry_text, "%b %d %H:%M:%S %Y %Z"
            ).strftime("%Y-%m-%d")
            log(f"SSL certificate expires: {cert_expiry}", "info")
        except ValueError:
            log(f"WARNING: Could not parse cert expiry: {expiry_text}", "warning")
    else:
        log(
            "WARNING: Could not read SSL certificate expiry from "
            f"{' or '.join(certificate_paths(config.domain))} "
            f"(exit code {exit_code})",
            "warning",
        )

    return True, "", cert_expiry


def certificate_paths(domain: str) -> tuple[str, ...]:
    """Where the certificate for ``domain`` may be kept, most likely first."""
    return (
        f"/var/www/espocrm/data/nginx/ssl/live/{domain}/fullchain.pem",
        f"/etc/letsencrypt/live/{domain}/fullchain.pem",
    )


#: How long to keep polling one network-dependent check before calling it failed.
VERIFY_POLL_SECONDS = 60.0

#: The waits between attempts, in order; the last value repeats once exhausted.
VERIFY_BACKOFF: tuple[float, ...] = (1.0, 1.0, 2.0, 2.0, 3.0, 3.0) + (5.0,) * 20


def phase_verify(
    ssh: paramiko.SSHClient, domain: str, log: Log, *, secure: bool = True
) -> tuple[bool, list[dict]]:
    """Check the built server answers, is secured, and keeps its schedule.

    With ``secure=False`` — a server installed in plain web mode because its
    web address does not point at it yet (PI-571) — the checks that need the
    web address or the certificate are not run: they would fail for a reason
    already reported as an open item. The CRM is checked on the server itself
    instead, by asking its web server for the page under the right host name.

    A check that depends on the network is polled on a backoff to a deadline,
    because the web server needs a moment after the installer finishes. A check
    of state already settled — the containers, the schedule, the database — is
    probed once, since polling it would only repeat the same answer.

    :returns: ``(every check passed, one result per check)``.
    """
    results: list[dict] = []

    def run_check(
        name: str,
        command: str,
        passed_when: Callable[[int, str], bool],
        poll: bool = False,
        timeout_seconds: float = VERIFY_POLL_SECONDS,
    ) -> bool:
        log(f"Verifying: {name}", "info")

        if not poll:
            exit_code, output = run_remote(ssh, command)
            passed = passed_when(exit_code, output)
            log(
                f"  {'PASS' if passed else 'FAIL'}: {name}",
                "info" if passed else "error",
            )
            results.append(
                {
                    "check": name,
                    "passed": passed,
                    "detail": output[:200] if not passed else "",
                }
            )
            return passed

        start = time.monotonic()
        deadline = start + timeout_seconds
        attempt = 0
        first_attempt = True
        output = ""

        while time.monotonic() < deadline:
            exit_code, output = run_remote(ssh, command)
            if passed_when(exit_code, output):
                if first_attempt:
                    # No warm-up was needed; keep a clean run's log shape.
                    log(f"  PASS: {name}", "info")
                else:
                    log(
                        f"  PASS: {name} (after {int(time.monotonic() - start)}s)",
                        "info",
                    )
                results.append({"check": name, "passed": True, "detail": ""})
                return True

            if first_attempt:
                log(f"  Waiting for {name} to come up ...", "info")
                first_attempt = False

            time.sleep(VERIFY_BACKOFF[min(attempt, len(VERIFY_BACKOFF) - 1)])
            attempt += 1

        log(f"  FAIL: {name} (timed out after {int(timeout_seconds)}s)", "error")
        results.append(
            {
                "check": name,
                "passed": False,
                "detail": output[:200] if output else "(no output)",
            }
        )
        return False

    run_check(
        "Docker containers running",
        f"docker compose -f {COMPOSE_FILE} ps",
        lambda code, out: code == 0 and "espocrm" in out.lower(),
    )
    if not secure:
        run_check(
            "CRM answers on the server",
            f"curl -sI -H 'Host: {domain}' http://127.0.0.1 | head -1",
            lambda code, out: any(s in out for s in ("200", "301", "302")),
            poll=True,
        )
        run_check(
            "Database connectivity",
            f"docker compose -f {COMPOSE_FILE} ps "
            "| grep -iE 'mysql|mariadb|espocrm-db'",
            lambda code, out: code == 0 and "up" in out.lower(),
        )
        return all(result["passed"] for result in results), results

    run_check(
        "HTTP redirect to HTTPS",
        f"curl -sI http://{domain} | head -1",
        lambda code, out: "301" in out or "302" in out,
        poll=True,
    )
    run_check(
        "HTTPS response",
        f"curl -sI https://{domain} | head -1",
        lambda code, out: "200" in out,
        poll=True,
    )
    run_check(
        "SSL certificate valid",
        f"openssl s_client -connect {domain}:443 "
        f"</dev/null 2>/dev/null | openssl x509 -noout -dates",
        lambda code, out: code == 0 and "notAfter" in out,
        poll=True,
    )
    run_check(
        "EspoCRM login page present",
        f"curl -sL https://{domain} | head -100",
        lambda code, out: "espocrm" in out.lower(),
        poll=True,
    )
    run_check(
        "Cron job configured",
        "crontab -l 2>/dev/null | grep espocrm",
        lambda code, out: code == 0 and "espocrm" in out.lower(),
    )
    run_check(
        "Database connectivity",
        f"docker compose -f {COMPOSE_FILE} ps "
        "| grep -iE 'mysql|mariadb|espocrm-db'",
        lambda code, out: code == 0 and "up" in out.lower(),
    )

    return all(result["passed"] for result in results), results
