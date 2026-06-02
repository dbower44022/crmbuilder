"""API test fixtures: a TestClient bound to a fresh per-test database.

The TestClient carries a default ``X-Engagement`` header so the per-request
scope middleware (PI-123) resolves the default engagement on every call. The
engagement is resolved from the unified ``engagements`` table that ``v2_env``
seeds (``ENG-001``) — the meta DB is left clean so the ``/engagements``
registry-API tests start from an empty registry.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient

from tests.crmbuilder_v2.conftest import DEFAULT_ENGAGEMENT_ID


@pytest.fixture
def client(v2_env):
    test_client = TestClient(create_app())
    test_client.headers.update({"X-Engagement": DEFAULT_ENGAGEMENT_ID})
    return test_client
