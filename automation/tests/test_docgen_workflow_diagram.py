"""Tests for automation.docgen.workflow_diagram — diagram path lookup."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.docgen.workflow_diagram import get_diagram_path


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _seed(conn):
    conn.execute(
        "INSERT INTO Domain (id, name, code, sort_order) VALUES (1, 'Mentoring', 'MN', 1)"
    )
    conn.execute(
        "INSERT INTO Process (id, domain_id, name, code, sort_order) "
        "VALUES (1, 1, 'Client Intake', 'MN-INTAKE', 1)"
    )
    conn.commit()


class TestGetDiagramPath:

    def test_returns_path_when_png_exists(self, conn, tmp_path):
        _seed(conn)
        png_dir = tmp_path / "PRDs" / "MN"
        png_dir.mkdir(parents=True)
        png_file = png_dir / "MN-INTAKE-workflow.png"
        png_file.write_bytes(b"PNG")

        result = get_diagram_path(conn, 1, tmp_path)
        assert result is not None
        assert result.name == "MN-INTAKE-workflow.png"

    def test_returns_none_when_missing(self, conn, tmp_path):
        _seed(conn)
        result = get_diagram_path(conn, 1, tmp_path)
        assert result is None

    def test_returns_none_for_invalid_process(self, conn, tmp_path):
        _seed(conn)
        result = get_diagram_path(conn, 999, tmp_path)
        assert result is None

    def test_subdomain_path(self, conn, tmp_path):
        _seed(conn)
        conn.execute(
            "INSERT INTO Domain (id, name, code, sort_order, parent_domain_id) "
            "VALUES (2, 'SubMentor', 'MN-SUB', 2, 1)"
        )
        conn.execute(
            "INSERT INTO Process (id, domain_id, name, code, sort_order) "
            "VALUES (2, 2, 'Sub Process', 'MN-SUB-PROC', 1)"
        )
        conn.commit()

        png_dir = tmp_path / "PRDs" / "MN" / "MN-SUB"
        png_dir.mkdir(parents=True)
        png_file = png_dir / "MN-SUB-PROC-workflow.png"
        png_file.write_bytes(b"PNG")

        result = get_diagram_path(conn, 2, tmp_path)
        assert result is not None
        assert "MN-SUB" in str(result)
