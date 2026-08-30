"""Provider-credential repository tests — PI-419 (REQ-522, PRJ-111)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import provider_credentials as pc
from sqlalchemy import inspect


def test_table_shape(v2_env):
    cols = {c["name"] for c in inspect(get_engine()).get_columns("provider_credentials")}
    assert cols == {"id", "provider", "token_ref", "label", "created_at", "updated_at", "engagement_id"}


def test_upsert_replace_list_delete(v2_env):
    with session_scope() as s:
        row = pc.upsert_provider_credential(s, "digitalocean", token_ref="crmbuilder:a", label="CRMBuilder DO")
        assert row["provider"] == "digitalocean"
        assert row["token_ref"] == "crmbuilder:a"
        pc.upsert_provider_credential(s, "cloudflare", token_ref="crmbuilder:b")
        again = pc.upsert_provider_credential(s, "digitalocean", token_ref="crmbuilder:c", label=None)
        assert again["id"] == row["id"]
        assert again["token_ref"] == "crmbuilder:c"
        assert again["label"] is None
    with session_scope() as s:
        assert [r["provider"] for r in pc.list_provider_credentials(s)] == ["cloudflare", "digitalocean"]
        assert pc.get_provider_credential(s, "cloudflare")["token_ref"] == "crmbuilder:b"
        assert pc.delete_provider_credential(s, "cloudflare") == "crmbuilder:b"
        assert pc.get_provider_credential(s, "cloudflare") is None
        assert pc.delete_provider_credential(s, "cloudflare") is None


def test_rejects_unknown_provider_and_empty_ref(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            pc.upsert_provider_credential(s, "aws", token_ref="crmbuilder:x")
        with pytest.raises(UnprocessableError):
            pc.upsert_provider_credential(s, "cloudflare", token_ref="")
        with pytest.raises(UnprocessableError):
            pc.get_provider_credential(s, "aws")
