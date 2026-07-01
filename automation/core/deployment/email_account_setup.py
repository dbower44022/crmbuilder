"""Provision an outgoing email account with provider-discovered folders.

REQ-389 (PI-349): the Configure pipeline must be able to set up an email account
on a deployed instance and set its Sent / Trash / Drafts folders to the mail
provider's **real** folder paths, discovered by listing the account's mailboxes
over IMAP — never guessed. A wrong folder makes a delivered message fail to file
with a folder-not-found error even though it was sent.

Two pieces:

* :func:`discover_folders` — connect to the provider over IMAP, ``LIST`` the
  mailboxes, and resolve Sent / Trash / Drafts via
  :mod:`espo_impl.core.email_folders` (SPECIAL-USE first, then well-known names,
  else ``None``).
* :func:`configure_email_account` — discover the folders, then create-or-update
  the EspoCRM ``EmailAccount`` over REST with those folder paths. It **refuses to
  write a folder it could not resolve** — the "never guess" guarantee — reporting
  the unresolved roles instead.

The IMAP client is injectable (``imap_factory``) so the resolution + provisioning
logic unit-tests without a live server; the default uses :mod:`imaplib`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from espo_impl.core.email_folders import (
    ResolvedFolders,
    parse_list_line,
    resolve_special_folders,
)

LogFn = Callable[[str, str], None]

#: EspoCRM ``EmailAccount`` attribute names for each resolved folder role. Kept
#: as one constant so a schema difference across EspoCRM versions is a one-line
#: correction rather than a scattered edit.
_FOLDER_FIELDS: dict[str, str] = {
    "sent": "sentFolder",
    "trash": "trashFolder",
    "drafts": "draftsFolder",
}


@dataclass
class EmailAccountSetupResult:
    """Outcome of an email-account setup."""

    email_address: str
    folders: ResolvedFolders | None = None
    account_id: str | None = None
    created: bool = False
    updated: bool = False
    unresolved: tuple[str, ...] = ()
    error: str | None = None

    @property
    def ok(self) -> bool:
        return (
            self.error is None
            and not self.unresolved
            and (self.created or self.updated)
        )


def discover_folders(
    host: str,
    username: str,
    password: str,
    *,
    port: int = 993,
    use_ssl: bool = True,
    imap_factory: Callable[..., Any] | None = None,
) -> ResolvedFolders:
    """Connect over IMAP, ``LIST`` the mailboxes, and resolve the special folders.

    :param imap_factory: Optional ``(host, port) -> imap`` factory returning an
        object with ``login``, ``list`` and ``logout`` (defaults to
        ``imaplib.IMAP4_SSL`` / ``imaplib.IMAP4``). Injected in tests.
    :returns: The resolved Sent / Trash / Drafts (any of which may be ``None``).
    """
    if imap_factory is None:
        import imaplib

        def imap_factory(h: str, p: int):  # type: ignore[misc]
            return imaplib.IMAP4_SSL(h, p) if use_ssl else imaplib.IMAP4(h, p)

    imap = imap_factory(host, port)
    try:
        imap.login(username, password)
        typ, data = imap.list()
        lines = _decode_list_data(data) if typ == "OK" else []
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001 — logout best-effort
            pass

    mailboxes = [mb for line in lines if (mb := parse_list_line(line)) is not None]
    return resolve_special_folders(mailboxes)


def _decode_list_data(data: list[Any]) -> list[str]:
    """Normalise imaplib ``list()`` data (bytes or str, possibly tuples) to str lines."""
    lines: list[str] = []
    for item in data or []:
        if isinstance(item, tuple):
            item = b" ".join(
                part if isinstance(part, bytes) else str(part).encode()
                for part in item
            )
        if isinstance(item, bytes):
            lines.append(item.decode("utf-8", "replace"))
        elif item is not None:
            lines.append(str(item))
    return lines


def build_email_account_payload(
    email_address: str,
    folders: ResolvedFolders,
    *,
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the ``EmailAccount`` create/update payload with the resolved folders.

    Only folders that resolved to a real path are written; an unresolved folder is
    omitted rather than set to a guessed value. ``base`` carries any other account
    fields the caller wants to set (host, port, security, username, assigned user,
    SMTP settings, ``storeSentEmails: True``, …).
    """
    payload: dict[str, Any] = dict(base or {})
    payload["emailAddress"] = email_address
    for role, field_name in _FOLDER_FIELDS.items():
        value = getattr(folders, role)
        if value is not None:
            payload[field_name] = value
    return payload


def _find_existing_account(client: Any, email_address: str) -> str | None:
    """Return the id of an existing ``EmailAccount`` for ``email_address``, or None."""
    status, body = client.list_records(
        "EmailAccount",
        select=["id", "emailAddress"],
        where=[{"type": "equals", "attribute": "emailAddress", "value": email_address}],
        max_size=1,
    )
    if status == 200 and isinstance(body, dict):
        rows = body.get("list") or []
        if rows:
            return rows[0].get("id")
    return None


def configure_email_account(
    client: Any,
    *,
    email_address: str,
    imap_host: str,
    imap_username: str,
    imap_password: str,
    imap_port: int = 993,
    use_ssl: bool = True,
    account_fields: dict[str, Any] | None = None,
    imap_factory: Callable[..., Any] | None = None,
    log: LogFn | None = None,
) -> EmailAccountSetupResult:
    """Discover the provider's folders and create-or-update the ``EmailAccount``.

    Discovers Sent / Trash / Drafts over IMAP and provisions the account with
    those paths. If any of the three cannot be resolved from the mailbox list, the
    account is **not written** and the result reports the unresolved roles — the
    "never guess" guarantee (REQ-389). Idempotent: an existing account for the
    same address is patched, otherwise a new one is created.

    :param client: An :class:`EspoAdminClient` for the target instance.
    :param account_fields: Extra ``EmailAccount`` fields (host, port, security,
        username, ``assignedUserId``, SMTP settings, ``storeSentEmails: True`` …).
    :returns: An :class:`EmailAccountSetupResult`.
    """
    emit = log or (lambda *_: None)
    result = EmailAccountSetupResult(email_address=email_address)

    try:
        emit(f"[EMAIL]   discovering folders for {email_address} via IMAP...", "white")
        folders = discover_folders(
            imap_host, imap_username, imap_password,
            port=imap_port, use_ssl=use_ssl, imap_factory=imap_factory,
        )
    except Exception as exc:  # noqa: BLE001 — surface any IMAP error as a result
        result.error = f"IMAP discovery failed: {exc}"
        emit(f"[EMAIL]   {result.error}", "red")
        return result

    result.folders = folders
    if folders.unresolved:
        result.unresolved = folders.unresolved
        emit(
            f"[EMAIL]   could not resolve {', '.join(folders.unresolved)} folder(s) "
            f"from the provider — refusing to guess; account not written",
            "red",
        )
        return result

    payload = build_email_account_payload(
        email_address, folders, base=account_fields
    )

    existing_id = _find_existing_account(client, email_address)
    if existing_id:
        status, _body = client.patch_record("EmailAccount", existing_id, payload)
        result.account_id = existing_id
        result.updated = status == 200
    else:
        status, body = client.create_record("EmailAccount", payload)
        result.created = status in (200, 201)
        if isinstance(body, dict):
            result.account_id = body.get("id")

    if not (result.created or result.updated):
        result.error = f"EmailAccount write failed (HTTP {status})"
        emit(f"[EMAIL]   {result.error}", "red")
    else:
        emit(
            f"[EMAIL]   {email_address}: folders set "
            f"sent={folders.sent} trash={folders.trash} drafts={folders.drafts}",
            "green",
        )
    return result
