"""Rescuing a self-hosted instance — PI-562 (REQ-640) and PI-563 (REQ-641).

Absorbed from version 1's ``automation.core.deployment.recovery_ssh`` and the
order its recovery worker drove. Two operations, each a set of steps and one
entry point, in the shape of :mod:`crmbuilder_v2.deploy.upgrade` (DEC-1141):
the steps report what they learned and write nothing; the entry points open the
remote login, drive the steps and write through the repositories that own the
columns.

**Resetting an administrator's password** (DEC-1144). Version 1 wrote an
unsalted MD5 value into the platform's user table. The platform accepts only
bcrypt, or its own salted legacy hash, so that value never matched: the command
exited cleanly and the lock-out remained. This runs the platform's own
``set-password`` command for an account the operator names, feeds it the
password on standard input, then signs in with the new password to prove it.

* :func:`set_admin_password` — run the platform's command.
* :func:`check_sign_in` — does the new password sign in, as an administrator?
* :func:`reset_admin_password` — the entry point.

**Rebuilding an instance from clean.** This destroys every record on the
instance. Version 1 deleted the installation folder and then ran the installer,
so a failed install left nothing to restore. Here the platform's installer does
the clean itself: it stops the containers, copies the whole installation aside,
deletes it, and copies it back if its install fails (DEC-1142). Version 2's own
database dump is taken first, and a rebuild that cannot take it stops before
anything is destroyed unless the caller passes ``skip_backup`` (DEC-1149,
REQ-647). The caller must pass the instance's domain name as confirmation
(DEC-1143).

* :func:`confirmation_matches` — does the confirmation name this instance?
* :func:`list_installer_copies` — the copies the installer has left.
* :func:`rebuild_instance` — the entry point.

Whether a rebuild should be a recorded, resumable run is left open, as DEC-1141
left it for the upgrade; it belongs with the screens that drive one.
"""

from __future__ import annotations

import base64
import dataclasses
import logging
import secrets as token_source
import shlex
from collections.abc import Callable

import paramiko
import requests

from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.deploy.ssh import (
    COMPOSE_FILE,
    Log,
    SelfHostedConfig,
    mask_secrets,
    phase_install_espocrm,
    phase_post_install,
    phase_verify,
    run_remote,
)
from crmbuilder_v2.deploy.upgrade import (
    _connected,
    _record,
    _require_deploy_config,
    decode_backup_paths,
    encode_backup_paths,
    get_current_version,
    phase2_backup,
)
from crmbuilder_v2.segments.operate.repositories import (
    instance_deploy_config,
    instances,
)

logger = logging.getLogger("crmbuilder_v2.deploy.recovery")

#: What the platform's command prints once the password is stored. Its exit
#: status alone is not trusted: a reset that reports success and changes
#: nothing is the defect this module replaces.
_PASSWORD_CHANGED = "has been changed"

#: The account types the platform counts as administrators.
_ADMIN_TYPES = frozenset({"admin", "super-admin"})

#: Where the installer copies an installation before it cleans it: a folder
#: beside the installer script, which the install step fetches into the remote
#: login's home folder.
INSTALLER_COPY_ROOT = "$HOME/espocrm-backup"

#: The certificate authority's limit on requests for the same set of names.
DUPLICATE_CERTIFICATES_PER_WEEK = 5


# ---------------------------------------------------------------------------
# Resetting an administrator's password
# ---------------------------------------------------------------------------

def password_problem(password: str) -> str:
    """Why ``password`` cannot be set, or an empty string when it can.

    The platform's command trims what it reads, so a password that begins or
    ends with whitespace would be stored as something other than what the
    operator typed.
    """
    if not password:
        return "A new password is required."
    if password != password.strip():
        return (
            "The new password begins or ends with whitespace, which the "
            "platform would silently remove. Choose one that does not."
        )
    if "\n" in password or "\r" in password:
        return "The new password cannot contain a line break."
    return ""


def set_admin_password(
    ssh: paramiko.SSHClient, username: str, password: str, log: Log
) -> tuple[bool, str]:
    """Set ``username``'s password with the platform's own command.

    The password is written to the command's standard input, never onto a
    command line, so nobody listing processes on the server can read it. It is
    also replaced before anything the command prints reaches the log.

    :returns: ``(the platform stored the password, why it did not)``.
    """
    if not username:
        return False, "Name the account to reset; none is chosen for you."
    problem = password_problem(password)
    if problem:
        return False, problem

    command = (
        f"docker compose -f {COMPOSE_FILE} exec -T -u www-data espocrm "
        f"php command.php set-password {shlex.quote(username)}"
    )
    log(f"$ {command}", "info")
    exit_code, output = run_remote(ssh, command, input_text=password + "\n")
    shown = mask_secrets(output, [password])
    for line in shown.splitlines():
        # The command turns echo off around the password; with no terminal
        # that fails harmlessly and says so, which is noise here.
        if line.strip() and not line.startswith("stty:"):
            log(line, "info")

    if exit_code != 0:
        reason = next(
            (line for line in shown.splitlines() if "not found" in line.lower()),
            f"exit {exit_code}",
        )
        return False, f"The platform did not change the password: {reason}"
    if _PASSWORD_CHANGED not in output:
        return False, (
            "The platform's command exited without saying the password was "
            "changed, so the reset is not treated as done."
        )
    return True, ""


def check_sign_in(
    instance_url: str, username: str, password: str, timeout: int = 20
) -> tuple[bool | None, str]:
    """Sign in to the instance and report whether the account is an administrator.

    :returns: ``(True, "")`` when it signs in as an administrator, ``(False,
        why)`` when it is refused or is not one, and ``(None, why)`` when the
        instance could not be asked.
    """
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    url = f"{instance_url.rstrip('/')}/api/v1/App/user"
    try:
        response = requests.get(
            url, headers={"Espo-Authorization": token}, timeout=timeout
        )
    except requests.RequestException as exc:
        return None, f"the instance did not answer ({type(exc).__name__})"
    if response.status_code == 401:
        return False, "the instance refused the new password"
    if response.status_code != 200:
        return None, f"the instance answered HTTP {response.status_code}"
    try:
        user = response.json().get("user") or {}
    except (ValueError, AttributeError):
        return None, "the instance's answer could not be read"
    if user.get("type") not in _ADMIN_TYPES:
        return False, (
            f"the account signs in but is not an administrator "
            f"(its type is {user.get('type')!r})"
        )
    return True, ""


@dataclasses.dataclass
class ResetOutcome:
    """What a password reset did, for a caller that has to report it.

    :ivar succeeded: The platform stored the password and it signs in as an
        administrator.
    :ivar error: Why not, in the words of the step that said so.
    :ivar platform_changed: The platform reported the password changed. When
        this is true and ``succeeded`` is not, the old password no longer works.
    :ivar signed_in: True when the new password signed in as an administrator,
        False when it was refused, None when it could not be checked.
    :ivar store_updated: Which stored credentials now hold the new password.
    """

    succeeded: bool
    error: str = ""
    platform_changed: bool = False
    signed_in: bool | None = None
    store_updated: list[str] = dataclasses.field(default_factory=list)


def reset_admin_password(
    instance_identifier: str,
    username: str,
    new_password: str,
    log: Log,
    *,
    resolve_secret: Callable[[str], str] = secrets.get_secret,
    store_secret: Callable[..., str] = secrets.put_secret,
    sign_in: Callable[[str, str, str], tuple[bool | None, str]] = check_sign_in,
) -> ResetOutcome:
    """Reset one administrator's password on a registered instance.

    Once the platform has stored the new password the old one is gone, so the
    store is brought in line whether or not the sign-in check then passes. A
    store write that fails after that point is reported as such, because the
    instance and the store now disagree.

    :param resolve_secret: How a stored reference becomes its value; replaced
        in tests.
    :param store_secret: How a value is written under a reference; replaced in
        tests.
    :param sign_in: How the new password is proved; replaced in tests.
    """
    if not username:
        return ResetOutcome(False, "Name the account to reset; none is chosen for you.")
    problem = password_problem(new_password)
    if problem:
        return ResetOutcome(False, problem)

    config = _require_deploy_config(instance_identifier)
    with session_scope() as session:
        instance = instances.get_instance(session, instance_identifier)

    with _connected(config, resolve_secret) as client:
        changed, error = set_admin_password(client, username, new_password, log)
    if not changed:
        return ResetOutcome(False, error)
    log(f"The platform stored a new password for {username!r}.", "info")

    outcome = ResetOutcome(False, platform_changed=True)
    try:
        outcome.store_updated = _store_new_password(
            instance, config, username, new_password, resolve_secret, store_secret, log
        )
    except Exception as exc:  # the instance already has the new password
        logger.exception("storing the reset password failed")
        outcome.error = (
            f"The instance now has the new password for {username!r}, but "
            f"writing it to the store failed ({type(exc).__name__}). Version 2 "
            "may be unable to reach the instance until the stored credential "
            "is corrected."
        )
        return outcome

    url = (instance or {}).get("instance_url") or f"https://{config.get('domain')}"
    signed_in, why = sign_in(url, username, new_password)
    outcome.signed_in = signed_in
    if signed_in is True:
        log(f"Signed in as {username!r} with the new password.", "info")
        outcome.succeeded = True
        return outcome
    if signed_in is False:
        outcome.error = f"The password was stored, but {why}. The reset did not work."
    else:
        outcome.error = (
            f"The password was stored, but signing in could not be checked: {why}. "
            "Treat the reset as unchecked until someone signs in."
        )
    log(outcome.error, "error")
    return outcome


def _store_new_password(
    instance: dict | None,
    config: dict,
    username: str,
    new_password: str,
    resolve_secret: Callable[[str], str],
    store_secret: Callable[..., str],
    log: Log,
) -> list[str]:
    """Write the new password under every stored credential for ``username``.

    A deploy run stores the recorded administrator password and the instance's
    own sign-in password under one reference, so writing it once updates both;
    where they are separate, each is written. The value is written under the
    reference already recorded, so nothing has to be re-pointed.

    :returns: Which credentials now hold the new password.
    """
    updated: list[str] = []
    written: set[str] = set()

    if instance and instance.get("instance_auth_method") == "basic":
        name_ref = instance.get("instance_secret_ref")
        password_ref = instance.get("instance_secret_key_ref")
        stored_name = None
        if name_ref:
            try:
                stored_name = resolve_secret(name_ref)
            except (KeyError, ValueError):
                log("The instance's stored sign-in name could not be read.", "warning")
        if stored_name == username and password_ref:
            store_secret(new_password, ref=password_ref)
            written.add(password_ref)
            updated.append("instance sign-in credential")

    admin_ref = config.get("admin_password_ref")
    if config.get("admin_username") == username and admin_ref:
        if admin_ref not in written:
            store_secret(new_password, ref=admin_ref)
        updated.append("recorded administrator password")

    if updated:
        log(f"Stored the new password in: {', '.join(updated)}.", "info")
    else:
        log(
            f"Version 2 does not reach this instance as {username!r}, so no "
            "stored credential was changed.",
            "info",
        )
    return updated


# ---------------------------------------------------------------------------
# Rebuilding an instance from clean
# ---------------------------------------------------------------------------

def _normalise_domain(value: str | None) -> str:
    return (value or "").strip().lower().rstrip(".")


def confirmation_matches(domain: str | None, confirmation: str | None) -> bool:
    """Does ``confirmation`` name the instance's recorded domain?

    Letter case and a trailing dot are ignored. An instance with no recorded
    domain matches nothing.
    """
    expected = _normalise_domain(domain)
    return bool(expected) and _normalise_domain(confirmation) == expected


def list_installer_copies(ssh: paramiko.SSHClient, log: Log | None = None) -> list[str]:
    """The copies of old installations the installer has left, oldest first.

    The installer names each copy by the moment it was taken, so sorting by
    name sorts by age. The installer never removes them.
    """
    exit_code, output = run_remote(
        ssh, f'ls -1d "{INSTALLER_COPY_ROOT}"/*/ 2>/dev/null | sort', log
    )
    if exit_code != 0 or not output.strip():
        return []
    return [line.rstrip("/") for line in output.strip().splitlines()]


def generate_password() -> str:
    """A new database password: long, random, and safe in any shell."""
    return token_source.token_hex(16)


@dataclasses.dataclass
class RebuildOutcome:
    """What a rebuild did, for a caller that has to report it.

    :ivar succeeded: The platform installed, and every check passed.
    :ivar error: Why not, in the words of the step that said so.
    :ivar installed: The installer finished. From here the old records are
        gone and the new credentials are the ones that work.
    :ivar backup_paths: The backups on the server, including the installer's
        copy of the old installation when it could be found.
    :ivar installer_copy: That copy's folder, or None when none was found.
    :ivar new_version: The version the rebuilt instance runs.
    :ivar cert_expiry: The certificate's expiry date, when it could be read.
    :ivar checks: One result per verification check.
    """

    succeeded: bool
    error: str = ""
    installed: bool = False
    backup_paths: list[str] = dataclasses.field(default_factory=list)
    installer_copy: str | None = None
    new_version: str | None = None
    cert_expiry: str | None = None
    checks: list[dict] = dataclasses.field(default_factory=list)


def rebuild_instance(
    instance_identifier: str,
    confirmation: str,
    admin_username: str,
    admin_password: str,
    log: Log,
    *,
    resolve_secret: Callable[[str], str] = secrets.get_secret,
    store_secret: Callable[..., str] = secrets.put_secret,
    new_password: Callable[[], str] = generate_password,
    skip_backup: bool = False,
) -> RebuildOutcome:
    """Reinstall the platform on a registered instance's server, from clean.

    **This destroys every record on the instance.** It refuses before any
    remote login is opened unless ``confirmation`` is the instance's recorded
    domain name (DEC-1143).

    What each step learns is written to the store as soon as it is known, so a
    failure part way leaves the record true: backups taken before a failed
    install are still backups, and credentials are replaced only once the
    installer has finished, because until then the old ones may still be the
    ones that work.

    :param confirmation: The instance's domain name, typed by the caller.
    :param admin_username: The administrator login the rebuilt instance gets.
    :param admin_password: Its password.
    :param new_password: How the two database passwords are made; replaced in
        tests.
    :param skip_backup: Go ahead without version 2's own dump, for a database
        too broken to dump or with no recorded administrator password. Without
        it, a dump that cannot be taken stops the rebuild before anything is
        destroyed (DEC-1149).
    """
    config = _require_deploy_config(instance_identifier)
    domain = config.get("domain") or ""
    if not domain:
        return RebuildOutcome(False, (
            f"{instance_identifier} has no domain recorded, so it cannot be "
            "confirmed or reinstalled. Record its domain first."
        ))
    if not confirmation_matches(domain, confirmation):
        return RebuildOutcome(False, (
            f"The rebuild was not confirmed. To destroy every record on "
            f"{instance_identifier}, pass its domain name, {domain}, as the "
            "confirmation."
        ))
    if not config.get("letsencrypt_email"):
        return RebuildOutcome(False, (
            "No certificate contact address is recorded for this instance, and "
            "the installer needs one to request a certificate."
        ))
    if not admin_username:
        return RebuildOutcome(False, "An administrator login name is required.")
    problem = password_problem(admin_password)
    if problem:
        return RebuildOutcome(False, problem)

    log(
        f"Rebuilding {domain} from clean. Every record on it will be destroyed. "
        "A new certificate will be requested, because the installer keeps the "
        "certificate inside the folder it replaces; the certificate authority "
        f"allows {DUPLICATE_CERTIFICATES_PER_WEEK} requests for the same name "
        "a week.",
        "warning",
    )

    outcome = RebuildOutcome(False)
    backups = decode_backup_paths(config.get("last_backup_paths"))

    with _connected(config, resolve_secret) as client:
        if skip_backup:
            log(
                "Skipping version 2's own dump, as the caller asked. No portable "
                "dump is taken before this rebuild; the installer's copy of the "
                "installation will be its only backup.",
                "warning",
            )
        else:
            dumped, error, backups = _portable_dump(
                client, config, backups, resolve_secret, log
            )
            _record(instance_identifier, last_backup_paths=encode_backup_paths(backups))
            if not dumped:
                outcome.backup_paths = backups
                outcome.error = (
                    f"{error} Nothing has been destroyed and the stored "
                    "credentials are unchanged. To rebuild without version 2's "
                    "own dump, pass skip_backup=True."
                )
                return outcome
        outcome.backup_paths = backups
        copies_before = set(list_installer_copies(client))

        install_config = SelfHostedConfig(
            ssh_host=config["ssh_host"],
            ssh_port=config.get("ssh_port") or 22,
            ssh_username=config.get("ssh_username") or "root",
            ssh_credential="",
            ssh_auth_type=config.get("ssh_auth_type") or "key",
            domain=domain,
            letsencrypt_email=config["letsencrypt_email"],
            db_password=new_password(),
            db_root_password=new_password(),
            admin_username=admin_username,
            admin_password=admin_password,
            admin_email=config.get("admin_email") or "",
        )
        log("=== Installing the platform from clean ===", "info")
        installed, error = phase_install_espocrm(client, install_config, log)

        copy = _find_new_copy(client, copies_before, log)
        if copy:
            backups = backups + [copy]
            outcome.installer_copy = copy
            outcome.backup_paths = backups
            _record(instance_identifier, last_backup_paths=encode_backup_paths(backups))

        if not installed:
            outcome.error = (
                f"{error}. The installer puts its copy of the old installation "
                "back when its install step fails"
                + (f"; that copy is at {copy}." if copy else
                   ", but no copy could be found on the server.")
                + " The stored credentials are unchanged."
            )
            return outcome

        outcome.installed = True
        _store_rebuilt_credentials(
            instance_identifier, install_config, store_secret, log
        )

        log("=== Post-install ===", "info")
        post_ok, post_error, cert_expiry = phase_post_install(client, install_config, log)
        outcome.cert_expiry = cert_expiry
        if cert_expiry:
            _record(instance_identifier, cert_expiry_date=cert_expiry)
        if not post_ok:
            outcome.error = f"The platform installed, but {post_error}"
            return outcome

        version = get_current_version(client, log)
        outcome.new_version = version
        _record(instance_identifier, current_espocrm_version=version)

        log("=== Verification ===", "info")
        verified, checks = phase_verify(client, domain, log)
        outcome.checks = checks

    if not verified:
        failed = ", ".join(c["check"] for c in checks if not c["passed"])
        outcome.error = (
            f"The platform installed but did not pass every check: {failed}."
        )
        return outcome
    outcome.succeeded = True
    return outcome


def _portable_dump(
    client: paramiko.SSHClient,
    config: dict,
    backups: list[str],
    resolve_secret: Callable[[str], str],
    log: Log,
) -> tuple[bool, str, list[str]]:
    """Take version 2's own database dump and data archive.

    It needs the database administrator password and a database that answers.
    Without either, no dump is taken and the caller stops the rebuild, unless
    it was told to go ahead without one (DEC-1149).

    :returns: ``(the dump was taken, why it was not, the backup folders now on
        the server — newest last)``.
    """
    ref = config.get("db_root_password_ref")
    if not ref:
        return False, (
            "No database administrator password is recorded, so version 2 "
            "cannot take its own dump before the rebuild."
        ), backups
    try:
        db_root_password = resolve_secret(ref)
    except (KeyError, ValueError):
        return False, (
            "The recorded database administrator password could not be read, "
            "so version 2 cannot take its own dump before the rebuild."
        ), backups
    dumped, error, remaining = phase2_backup(client, db_root_password, backups, log)
    if not dumped:
        return False, f"Version 2's own dump failed ({error}).", remaining
    return True, "", remaining


def _find_new_copy(
    client: paramiko.SSHClient, before: set[str], log: Log
) -> str | None:
    """The copy the installer took during this rebuild, when it can be found."""
    new = [path for path in list_installer_copies(client) if path not in before]
    if not new:
        log(
            "The installer's copy of the old installation could not be found "
            f"under {INSTALLER_COPY_ROOT}.",
            "warning",
        )
        return None
    log(f"The installer's copy of the old installation: {new[-1]}", "info")
    return new[-1]


def _store_rebuilt_credentials(
    instance_identifier: str,
    install_config: SelfHostedConfig,
    store_secret: Callable[..., str],
    log: Log,
) -> None:
    """Bring the store in line with the instance the installer just built.

    The new credentials replace the old ones, including the one version 2 signs
    in with; an API key the old instance held went with its database, so the
    instance is reached by the new administrator login from here on. What
    described the old instance and cannot be read back from the new one is
    cleared rather than left looking current.
    """
    admin_ref = store_secret(install_config.admin_password)
    with session_scope() as session:
        instance_deploy_config.upsert_deploy_config(
            session,
            instance_identifier,
            admin_username=install_config.admin_username,
            admin_password_ref=admin_ref,
            db_password_ref=store_secret(install_config.db_password),
            db_root_password_ref=store_secret(install_config.db_root_password),
            last_upgrade_at=None,
            cert_expiry_date=None,
            current_espocrm_version=None,
        )
        instances.patch_instance(
            session,
            instance_identifier,
            auth_method="basic",
            secret_ref=store_secret(install_config.admin_username),
            secret_key_ref=admin_ref,
        )
        instances.record_stamp_reading(
            session,
            instance_identifier,
            standard_version=None,
            plan_fingerprint=None,
            read_at=None,
        )
    log(
        "Stored the rebuilt instance's new credentials. Version 2 now signs in "
        f"as {install_config.admin_username!r}.",
        "info",
    )
    log(
        "The rebuilt instance holds none of the design version 2 had published "
        "onto it, so the recorded design reading is cleared. Publish the design "
        "again.",
        "warning",
    )


__all__ = [
    "INSTALLER_COPY_ROOT",
    "RebuildOutcome",
    "ResetOutcome",
    "check_sign_in",
    "confirmation_matches",
    "generate_password",
    "list_installer_copies",
    "password_problem",
    "rebuild_instance",
    "reset_admin_password",
    "set_admin_password",
]
