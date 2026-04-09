"""Tests for automation.ui.browser.browser_logic and tree_model — pure Python."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.ui.browser.browser_logic import (
    create_record,
    delete_record,
    get_fk_options,
    get_table_columns,
    infer_fk_from_context,
    load_change_log,
    load_record,
    load_related_records,
    resolve_fk_label,
    save_record,
)
from automation.ui.browser.tree_model import (
    build_tree,
    filter_tree,
    find_node,
)


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


# ---------------------------------------------------------------------------
# tree_model tests
# ---------------------------------------------------------------------------


class TestBuildTree:

    def test_empty_database(self, conn):
        roots = build_tree(conn)
        assert roots == []

    def test_with_domain(self, conn):
        conn.execute(
            "INSERT INTO Domain (name, code, is_service) VALUES ('Sales', 'SLS', FALSE)"
        )
        conn.commit()
        roots = build_tree(conn)
        assert len(roots) >= 1
        domain_branch = roots[0]
        assert domain_branch.label == "Domains"
        assert domain_branch.child_count == 1

    def test_with_entity(self, conn):
        conn.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native) "
            "VALUES ('Contact', 'CONTACT', 'Person', FALSE)"
        )
        conn.commit()
        roots = build_tree(conn)
        entity_branch = next((r for r in roots if r.label == "Entities"), None)
        assert entity_branch is not None
        assert entity_branch.child_count == 1

    def test_with_persona(self, conn):
        conn.execute(
            "INSERT INTO Persona (name, code) VALUES ('Admin', 'ADM')"
        )
        conn.commit()
        roots = build_tree(conn)
        persona_branch = next((r for r in roots if r.label == "Personas"), None)
        assert persona_branch is not None
        assert persona_branch.child_count == 1


class TestFindNode:

    def test_find_existing(self, conn):
        conn.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native) "
            "VALUES ('Contact', 'CONTACT', 'Person', FALSE)"
        )
        conn.commit()
        roots = build_tree(conn)
        node = find_node(roots, "Entity", 1)
        assert node is not None
        assert node.record_id == 1

    def test_find_missing(self, conn):
        roots = build_tree(conn)
        node = find_node(roots, "Entity", 999)
        assert node is None


class TestFilterTree:

    def test_filter_matches(self, conn):
        conn.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native) "
            "VALUES ('Contact', 'CONTACT', 'Person', FALSE)"
        )
        conn.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native) "
            "VALUES ('Account', 'ACCOUNT', 'Company', FALSE)"
        )
        conn.commit()
        roots = build_tree(conn)
        filtered = filter_tree(roots, "Contact")
        # Should have Entities branch with only Contact
        assert len(filtered) >= 1

    def test_empty_search_returns_all(self, conn):
        conn.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native) "
            "VALUES ('Contact', 'CONTACT', 'Person', FALSE)"
        )
        conn.commit()
        roots = build_tree(conn)
        filtered = filter_tree(roots, "")
        assert len(filtered) == len(roots)


# ---------------------------------------------------------------------------
# browser_logic tests
# ---------------------------------------------------------------------------


class TestGetTableColumns:

    def test_returns_columns_for_entity(self, conn):
        cols = get_table_columns(conn, "Entity")
        col_names = [c.name for c in cols]
        assert "id" in col_names
        assert "name" in col_names
        assert "code" in col_names

    def test_fk_detection(self, conn):
        cols = get_table_columns(conn, "Field")
        entity_id_col = next(c for c in cols if c.name == "entity_id")
        assert entity_id_col.is_fk
        assert entity_id_col.fk_table == "Entity"

    def test_read_only_detection(self, conn):
        cols = get_table_columns(conn, "Entity")
        id_col = next(c for c in cols if c.name == "id")
        assert id_col.is_read_only


class TestLoadRecord:

    def test_load_existing_record(self, conn):
        conn.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native) "
            "VALUES ('Contact', 'CONTACT', 'Person', FALSE)"
        )
        conn.commit()
        record = load_record(conn, "Entity", 1)
        assert record is not None
        assert record.values["name"] == "Contact"

    def test_load_missing_record(self, conn):
        record = load_record(conn, "Entity", 999)
        assert record is None

    def test_load_non_browsable_table(self, conn):
        record = load_record(conn, "NonExistent", 1)
        assert record is None


class TestResolveFKLabel:

    def test_resolves_existing(self, conn):
        conn.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native) "
            "VALUES ('Contact', 'CONTACT', 'Person', FALSE)"
        )
        conn.commit()
        label = resolve_fk_label(conn, "Entity", 1)
        assert "Contact" in label

    def test_resolves_none(self, conn):
        label = resolve_fk_label(conn, "Entity", None)
        assert label == "—"

    def test_resolves_missing(self, conn):
        label = resolve_fk_label(conn, "Entity", 999)
        assert "not found" in label


class TestCreateRecord:

    def test_creates_and_logs(self, conn):
        new_id = create_record(conn, "Persona", {"name": "Admin", "code": "ADM"})
        assert new_id is not None

        # Verify record exists
        row = conn.execute("SELECT name FROM Persona WHERE id = ?", (new_id,)).fetchone()
        assert row[0] == "Admin"

        # Verify ChangeLog entry
        cl = conn.execute(
            "SELECT change_type FROM ChangeLog WHERE table_name = 'Persona' AND record_id = ?",
            (new_id,),
        ).fetchone()
        assert cl[0] == "insert"


class TestSaveRecord:

    def test_saves_and_logs(self, conn):
        conn.execute(
            "INSERT INTO Persona (name, code) VALUES ('Admin', 'ADM')"
        )
        conn.commit()

        save_record(conn, "Persona", 1, {"name": "Administrator"}, rationale="Renamed")

        row = conn.execute("SELECT name FROM Persona WHERE id = 1").fetchone()
        assert row[0] == "Administrator"

        cl = conn.execute(
            "SELECT change_type, rationale FROM ChangeLog "
            "WHERE table_name = 'Persona' AND record_id = 1 AND change_type = 'update'"
        ).fetchone()
        assert cl is not None
        assert cl[1] == "Renamed"


class TestDeleteRecord:

    def test_deletes_and_logs(self, conn):
        conn.execute(
            "INSERT INTO Persona (name, code) VALUES ('Admin', 'ADM')"
        )
        conn.commit()

        delete_record(conn, "Persona", 1, rationale="No longer needed")

        row = conn.execute("SELECT id FROM Persona WHERE id = 1").fetchone()
        assert row is None

        cl = conn.execute(
            "SELECT change_type FROM ChangeLog WHERE table_name = 'Persona' AND record_id = 1"
        ).fetchone()
        assert cl[0] == "delete"


class TestLoadChangeLog:

    def test_empty_history(self, conn):
        entries = load_change_log(conn, "Entity", 999)
        assert entries == []

    def test_returns_entries(self, conn):
        create_record(conn, "Persona", {"name": "Admin", "code": "ADM"})
        entries = load_change_log(conn, "Persona", 1)
        assert len(entries) == 1
        assert entries[0].change_type == "insert"
        assert entries[0].source_label == "Direct Edit"


class TestInferFKFromContext:

    def test_infers_entity_id_for_field(self):
        result = infer_fk_from_context("Field", "Entity", 5)
        assert result == {"entity_id": 5}

    def test_no_inference_without_context(self):
        result = infer_fk_from_context("Field", None, None)
        assert result == {}

    def test_no_match(self):
        result = infer_fk_from_context("Field", "Persona", 5)
        assert result == {}


class TestGetFKOptions:

    def test_returns_options(self, conn):
        conn.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native) "
            "VALUES ('Contact', 'CONTACT', 'Person', FALSE)"
        )
        conn.commit()
        options = get_fk_options(conn, "Entity")
        assert len(options) == 1
        assert options[0][0] == 1  # id
        assert "Contact" in options[0][1]


class TestLoadRelatedRecords:

    def test_finds_back_references(self, conn):
        conn.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native) "
            "VALUES ('Contact', 'CONTACT', 'Person', FALSE)"
        )
        conn.execute(
            "INSERT INTO Field (entity_id, name, label, field_type) "
            "VALUES (1, 'email', 'Email', 'email')"
        )
        conn.commit()

        groups = load_related_records(conn, "Entity", 1)
        # Should find Field records referencing this Entity
        field_group = next((g for g in groups if g.table_name == "Field"), None)
        assert field_group is not None
        assert len(field_group.records) == 1
