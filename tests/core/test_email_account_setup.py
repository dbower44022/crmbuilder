"""Tests for the email-account setup orchestrator (REQ-389 / PI-349).

IMAP and the REST client are faked; the discovery -> resolve -> provision
sequence, idempotent upsert, and the "never guess" refusal are exercised.
"""

from __future__ import annotations

from automation.core.deployment import email_account_setup as eas


class FakeIMAP:
    """Minimal imaplib-like stub returning a fixed LIST response."""

    def __init__(self, list_lines, *, fail_login=False):
        self._lines = list_lines
        self._fail_login = fail_login
        self.logged_out = False

    def login(self, user, password):
        if self._fail_login:
            raise OSError("auth failed")
        return "OK", [b"logged in"]

    def list(self, *_a, **_k):
        return "OK", [ln.encode() for ln in self._lines]

    def logout(self):
        self.logged_out = True
        return "BYE", []


class FakeClient:
    """Fake EspoAdminClient tracking EmailAccount reads/writes."""

    def __init__(self, existing=None):
        self.existing = existing  # {"id":..., "emailAddress":...} or None
        self.created = None
        self.patched = None

    def list_records(self, entity, select=None, where=None, max_size=200, **kw):
        assert entity == "EmailAccount"
        if self.existing:
            return 200, {"total": 1, "list": [self.existing]}
        return 200, {"total": 0, "list": []}

    def create_record(self, entity, payload):
        self.created = (entity, payload)
        return 201, {"id": "new-acct-id", **payload}

    def patch_record(self, entity, record_id, payload):
        self.patched = (entity, record_id, payload)
        return 200, {"id": record_id, **payload}


_GMAIL_LIST = [
    r'(\HasNoChildren) "/" "INBOX"',
    r'(\HasNoChildren \Sent) "/" "[Gmail]/Sent Mail"',
    r'(\HasNoChildren \Trash) "/" "[Gmail]/Trash"',
    r'(\HasNoChildren \Drafts) "/" "[Gmail]/Drafts"',
]


def _factory(lines, **kw):
    return lambda host, port: FakeIMAP(lines, **kw)


# -- discovery ---------------------------------------------------------------


def test_discover_folders_from_imap():
    folders = eas.discover_folders(
        "imap.gmail.com", "u", "p", imap_factory=_factory(_GMAIL_LIST)
    )
    assert folders.sent == "[Gmail]/Sent Mail"
    assert folders.trash == "[Gmail]/Trash"
    assert folders.drafts == "[Gmail]/Drafts"


# -- provisioning: create ----------------------------------------------------


def test_creates_account_with_discovered_folders():
    client = FakeClient(existing=None)
    result = eas.configure_email_account(
        client,
        email_address="ops@example.org",
        imap_host="imap.gmail.com",
        imap_username="ops@example.org",
        imap_password="secret",
        account_fields={"host": "imap.gmail.com", "storeSentEmails": True},
        imap_factory=_factory(_GMAIL_LIST),
    )
    assert result.ok
    assert result.created and not result.updated
    assert result.account_id == "new-acct-id"
    entity, payload = client.created
    assert entity == "EmailAccount"
    assert payload["emailAddress"] == "ops@example.org"
    assert payload["sentFolder"] == "[Gmail]/Sent Mail"
    assert payload["trashFolder"] == "[Gmail]/Trash"
    assert payload["draftsFolder"] == "[Gmail]/Drafts"
    assert payload["storeSentEmails"] is True  # base fields preserved


# -- provisioning: idempotent update -----------------------------------------


def test_updates_existing_account():
    client = FakeClient(existing={"id": "acct-1", "emailAddress": "ops@example.org"})
    result = eas.configure_email_account(
        client,
        email_address="ops@example.org",
        imap_host="imap.gmail.com",
        imap_username="ops@example.org",
        imap_password="secret",
        imap_factory=_factory(_GMAIL_LIST),
    )
    assert result.ok
    assert result.updated and not result.created
    assert client.created is None
    entity, rec_id, payload = client.patched
    assert (entity, rec_id) == ("EmailAccount", "acct-1")
    assert payload["sentFolder"] == "[Gmail]/Sent Mail"


# -- never guess -------------------------------------------------------------


def test_refuses_to_write_when_a_folder_is_unresolved():
    # Provider only exposes a Sent folder — trash/drafts cannot be resolved.
    partial = [
        r'(\HasNoChildren) "/" "INBOX"',
        r'(\HasNoChildren \Sent) "/" "Sent"',
    ]
    client = FakeClient(existing=None)
    result = eas.configure_email_account(
        client,
        email_address="ops@example.org",
        imap_host="imap.example.org",
        imap_username="ops@example.org",
        imap_password="secret",
        imap_factory=_factory(partial),
    )
    assert not result.ok
    assert set(result.unresolved) == {"trash", "drafts"}
    # Nothing was written — the account is not created with guessed folders.
    assert client.created is None and client.patched is None


def test_imap_failure_is_reported_not_raised():
    client = FakeClient()
    result = eas.configure_email_account(
        client,
        email_address="ops@example.org",
        imap_host="imap.example.org",
        imap_username="ops@example.org",
        imap_password="secret",
        imap_factory=_factory(_GMAIL_LIST, fail_login=True),
    )
    assert not result.ok
    assert result.error and "IMAP" in result.error
    assert client.created is None
