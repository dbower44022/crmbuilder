"""API test fixtures: a TestClient bound to a fresh per-test database."""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client(v2_env):
    return TestClient(create_app())
