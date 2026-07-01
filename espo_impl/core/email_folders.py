"""Resolve an email account's Sent / Trash / Drafts folders from its mailboxes.

REQ-389 (PI-349): when the Configure pipeline provisions an outgoing email
account, its ``sentFolder`` / ``trashFolder`` / ``draftsFolder`` must be set to
the mail provider's **real** folder paths — discovered by listing the account's
mailboxes over IMAP — and **never guessed**. A wrong folder makes a delivered
message fail to file with a folder-not-found error.

This module is the pure, deterministic core: given the parsed IMAP ``LIST``
output, resolve each special folder. Resolution prefers the RFC 6154 SPECIAL-USE
attributes (``\\Sent`` / ``\\Trash`` / ``\\Drafts``) the server advertises, and
falls back to a fixed set of well-known folder names (matched case-insensitively
on the mailbox's final path segment). If neither a SPECIAL-USE flag nor a known
name matches, the folder resolves to ``None`` — the caller reports it rather than
writing a guessed value.

The IMAP I/O (connecting and issuing ``LIST``) lives in
``automation/core/deployment/email_account_setup.py``; this module takes plain
data so it unit-tests without a live server.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: RFC 6154 SPECIAL-USE attribute for each folder role we resolve.
_SPECIAL_USE = {
    "sent": "\\sent",
    "trash": "\\trash",
    "drafts": "\\drafts",
}

#: Well-known mailbox names per role, matched case-insensitively against a
#: mailbox's final path segment (after the server's hierarchy delimiter). Ordered
#: from most to least specific; the first match wins. Covers Gmail, Outlook/
#: Exchange, Dovecot/cPanel, and generic IMAP conventions.
_KNOWN_NAMES = {
    "sent": ("sent mail", "sent items", "sent"),
    "trash": ("deleted messages", "deleted items", "trash", "deleted"),
    "drafts": ("drafts", "draft"),
}


@dataclass(frozen=True)
class Mailbox:
    """One parsed IMAP ``LIST`` entry: its SPECIAL-USE flags and full name."""

    flags: tuple[str, ...]
    name: str

    def has_flag(self, flag: str) -> bool:
        return any(f.lower() == flag for f in self.flags)


@dataclass(frozen=True)
class ResolvedFolders:
    """The resolved special-folder paths (any of which may be ``None``)."""

    sent: str | None
    trash: str | None
    drafts: str | None

    @property
    def all_resolved(self) -> bool:
        return None not in (self.sent, self.trash, self.drafts)

    @property
    def unresolved(self) -> tuple[str, ...]:
        """Roles that could not be resolved from the mailbox list."""
        return tuple(
            role for role in ("sent", "trash", "drafts")
            if getattr(self, role) is None
        )


#: An IMAP ``LIST`` response line, e.g. ``(\HasNoChildren \Sent) "/" "[Gmail]/Sent Mail"``
#: or ``(\HasNoChildren) "." INBOX.Sent``. The mailbox name is quoted or a bare atom.
_LIST_RE = re.compile(
    r'^\((?P<flags>[^)]*)\)\s+'          # (flag list)
    r'(?:"(?P<delim>[^"]*)"|(?P<delim2>NIL|\S+))\s+'  # "delim" | NIL | atom
    r'(?:"(?P<name>[^"]*)"|(?P<name2>\S+))\s*$'       # "name" | atom
)


def parse_list_line(line: str) -> Mailbox | None:
    """Parse one IMAP ``LIST`` response line into a :class:`Mailbox`.

    Returns ``None`` for a line that does not match the ``LIST`` grammar (e.g. a
    tagged status line). The delimiter is captured but not needed here — only the
    flags and full mailbox name drive resolution.
    """
    match = _LIST_RE.match(line.strip())
    if match is None:
        return None
    flags = tuple(f for f in match.group("flags").split() if f)
    name = match.group("name")
    if name is None:
        name = match.group("name2")
    if not name:
        return None
    return Mailbox(flags=flags, name=name)


def _final_segment(name: str) -> str:
    """The mailbox's leaf name, splitting on either common hierarchy delimiter."""
    return re.split(r"[/.]", name)[-1]


def _resolve_role(role: str, mailboxes: list[Mailbox]) -> str | None:
    """Resolve one folder role, SPECIAL-USE first then known-name fallback."""
    special = _SPECIAL_USE[role]
    for mb in mailboxes:
        if mb.has_flag(special):
            return mb.name
    for known in _KNOWN_NAMES[role]:
        for mb in mailboxes:
            if _final_segment(mb.name).lower() == known:
                return mb.name
    return None


def resolve_special_folders(mailboxes: list[Mailbox]) -> ResolvedFolders:
    """Resolve Sent / Trash / Drafts from a parsed IMAP mailbox list.

    Each role prefers the SPECIAL-USE attribute the server advertises, then falls
    back to a well-known name, then resolves to ``None`` (never guessed). The
    fallback also refuses to reuse a mailbox already claimed by SPECIAL-USE for a
    different role, so a server that flags ``\\Sent`` but also has a folder named
    literally "Trash" still resolves each role to the right mailbox.
    """
    resolved = {role: _resolve_role(role, mailboxes) for role in _SPECIAL_USE}
    return ResolvedFolders(
        sent=resolved["sent"],
        trash=resolved["trash"],
        drafts=resolved["drafts"],
    )
