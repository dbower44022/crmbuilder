"""Tests for the pre-publish target backup capture (PI-262 — REQ-292)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.publish.backup import (
    BackupCaptureError,
    capture_target_backup,
)


class _FakeClient:
    """A minimal EspoAdminClient stand-in for backup capture."""

    def __init__(
        self,
        *,
        scopes_status=200,
        scopes=None,
        field_status=200,
        fields=None,
        link_status=200,
        links=None,
    ):
        self._scopes_status = scopes_status
        self._scopes = scopes if scopes is not None else {}
        self._field_status = field_status
        self._fields = fields if fields is not None else {}
        self._link_status = link_status
        self._links = links if links is not None else {}

    def get_all_scopes(self):
        return self._scopes_status, self._scopes

    def get_entity_field_list(self, _espo):
        return self._field_status, self._fields

    def get_all_links(self, _espo):
        return self._link_status, self._links


def test_capture_backup_success():
    client = _FakeClient(
        scopes={"Contact": {"type": "Person"}},
        fields={"name": {"type": "varchar"}, "nickName": {"type": "varchar"}},
        links={"account": {"type": "belongsTo"}},
    )
    snap = capture_target_backup(client, ["Contact"])
    assert snap["captured_for"] == ["Contact"]
    assert "Contact" in snap["entities"]
    assert snap["entities"]["Contact"]["fields"]["nickName"]["type"] == "varchar"
    assert snap["entities"]["Contact"]["links"]["account"]["type"] == "belongsTo"
    assert snap["scopes"]["Contact"] == {"type": "Person"}
    assert snap["warnings"] == []


def test_capture_backup_scopes_unreadable_raises():
    client = _FakeClient(scopes_status=500, scopes=None)
    with pytest.raises(BackupCaptureError):
        capture_target_backup(client, ["Contact"])


def test_capture_backup_unmapped_entity_warns():
    # Engagement is custom (would be CEngagement) — absent from scopes.
    client = _FakeClient(scopes={"Contact": {"type": "Person"}})
    snap = capture_target_backup(client, ["Contact", "Engagement"])
    assert "Contact" in snap["entities"]
    assert "Engagement" not in snap["entities"]
    assert any("Engagement" in w for w in snap["warnings"])


def test_capture_backup_field_read_failure_warns_not_fatal():
    client = _FakeClient(
        scopes={"Contact": {"type": "Person"}},
        field_status=500,
        fields=None,
    )
    snap = capture_target_backup(client, ["Contact"])
    # Entity still recorded, fields null, warning noted — not fatal.
    assert snap["entities"]["Contact"]["fields"] is None
    assert any("could not read fields" in w for w in snap["warnings"])
