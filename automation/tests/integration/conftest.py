"""Fixtures for CBM integration tests.

Session-scoped fixtures so the import only runs once per test session.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from automation.cbm_import.importer import CBMImporter
from automation.db.migrations import run_client_migrations, run_master_migrations

FIXTURES = Path(__file__).parent.parent / "fixtures" / "cbm_subset"


@pytest.fixture(scope="session")
def cbm_db_paths(tmp_path_factory):
    """Create paths for the CBM databases."""
    base = tmp_path_factory.mktemp("cbm_integration")
    return {
        "client_db": str(base / "cbm-client.db"),
        "master_db": str(base / "master.db"),
    }


@pytest.fixture(scope="session")
def cbm_imported(cbm_db_paths):
    """Run the CBM importer against the fixture subset.

    Returns the import report. The databases remain available via cbm_db_paths.
    """
    # Create a fake repo structure with PRDs/ pointing at fixtures
    importer = CBMImporter(
        client_db_path=cbm_db_paths["client_db"],
        master_db_path=cbm_db_paths["master_db"],
        cbm_repo_path=FIXTURES.parent,  # Parent of cbm_subset
    )
    # Override _prds to point at the fixture subset directly
    importer._prds = FIXTURES
    report = importer.import_all()
    return report


@pytest.fixture(scope="session")
def cbm_client_conn(cbm_db_paths, cbm_imported):
    """Open a connection to the populated CBM client database."""
    conn = run_client_migrations(cbm_db_paths["client_db"])
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def cbm_master_conn(cbm_db_paths, cbm_imported):
    """Open a connection to the populated CBM master database."""
    conn = run_master_migrations(cbm_db_paths["master_db"])
    yield conn
    conn.close()


@pytest.fixture()
def temp_project_folder(tmp_path):
    """Temporary directory for document generation tests."""
    folder = tmp_path / "cbm_project"
    folder.mkdir()
    return folder
