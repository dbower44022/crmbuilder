"""Tests for IMAP special-folder resolution (REQ-389 / PI-349).

The heart of the "never guess" guarantee: given a parsed IMAP LIST, resolve
Sent / Trash / Drafts by SPECIAL-USE flags first, then well-known names, else
None.
"""

from __future__ import annotations

from espo_impl.core.email_folders import (
    Mailbox,
    parse_list_line,
    resolve_special_folders,
)

# -- parse_list_line ---------------------------------------------------------


def test_parse_quoted_name_and_flags():
    mb = parse_list_line(r'(\HasNoChildren \Sent) "/" "[Gmail]/Sent Mail"')
    assert mb is not None
    assert mb.name == "[Gmail]/Sent Mail"
    assert mb.has_flag("\\sent")


def test_parse_bare_atom_name():
    mb = parse_list_line(r'(\HasNoChildren) "." INBOX.Sent')
    assert mb is not None
    assert mb.name == "INBOX.Sent"
    assert mb.flags == ("\\HasNoChildren",)


def test_parse_nil_delimiter():
    mb = parse_list_line(r'(\Noselect) NIL "Archive"')
    assert mb is not None
    assert mb.name == "Archive"


def test_parse_non_list_line_returns_none():
    assert parse_list_line("A1 OK LIST completed") is None
    assert parse_list_line("") is None


# -- resolve_special_folders: SPECIAL-USE ------------------------------------


def test_resolves_by_special_use_flags():
    mailboxes = [
        Mailbox(("\\HasNoChildren",), "INBOX"),
        Mailbox(("\\Sent",), "[Gmail]/Sent Mail"),
        Mailbox(("\\Trash",), "[Gmail]/Bin"),
        Mailbox(("\\Drafts",), "[Gmail]/Drafts"),
    ]
    r = resolve_special_folders(mailboxes)
    assert r.sent == "[Gmail]/Sent Mail"
    assert r.trash == "[Gmail]/Bin"
    assert r.drafts == "[Gmail]/Drafts"
    assert r.all_resolved
    assert r.unresolved == ()


def test_special_use_beats_name():
    # A server flags \Sent on a differently-named box AND has a box literally
    # named "Sent" — SPECIAL-USE wins.
    mailboxes = [
        Mailbox(("\\Sent",), "Verzonden"),   # Dutch "Sent", flagged
        Mailbox((), "Sent"),                  # a decoy named Sent, unflagged
    ]
    assert resolve_special_folders(mailboxes).sent == "Verzonden"


# -- resolve_special_folders: known-name fallback ----------------------------


def test_resolves_by_known_name_when_no_flags():
    mailboxes = [
        Mailbox((), "INBOX"),
        Mailbox((), "Sent Items"),
        Mailbox((), "Deleted Items"),
        Mailbox((), "Drafts"),
    ]
    r = resolve_special_folders(mailboxes)
    assert r.sent == "Sent Items"
    assert r.trash == "Deleted Items"
    assert r.drafts == "Drafts"


def test_known_name_matches_final_segment_case_insensitive():
    mailboxes = [
        Mailbox((), "INBOX.Sent"),
        Mailbox((), "INBOX.Trash"),
        Mailbox((), "INBOX.Drafts"),
    ]
    r = resolve_special_folders(mailboxes)
    assert r.sent == "INBOX.Sent"
    assert r.trash == "INBOX.Trash"
    assert r.drafts == "INBOX.Drafts"


# -- never guess -------------------------------------------------------------


def test_unresolvable_folder_is_none_not_guessed():
    # Only a Sent folder exists; Trash and Drafts must resolve to None, not to
    # some arbitrary other mailbox.
    mailboxes = [
        Mailbox((), "INBOX"),
        Mailbox(("\\Sent",), "Sent"),
        Mailbox((), "Some Custom Folder"),
    ]
    r = resolve_special_folders(mailboxes)
    assert r.sent == "Sent"
    assert r.trash is None
    assert r.drafts is None
    assert not r.all_resolved
    assert set(r.unresolved) == {"trash", "drafts"}


def test_empty_mailbox_list_resolves_all_none():
    r = resolve_special_folders([])
    assert (r.sent, r.trash, r.drafts) == (None, None, None)
    assert r.unresolved == ("sent", "trash", "drafts")
