"""Tests for automation.workflow.graph — dependency graph construction."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.workflow.graph import (
    add_domain,
    add_entity,
    add_process,
    after_business_object_discovery_import,
    after_master_prd_import,
    create_project,
)


@pytest.fixture()
def conn(tmp_path):
    """Create a client database and return an open connection."""
    db_path = tmp_path / "test.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _get_work_item(conn, wid):
    """Return a WorkItem row as a dict."""
    conn.row_factory = None
    row = conn.execute(
        "SELECT id, item_type, status, domain_id, entity_id, process_id "
        "FROM WorkItem WHERE id = ?",
        (wid,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0], "item_type": row[1], "status": row[2],
        "domain_id": row[3], "entity_id": row[4], "process_id": row[5],
    }


def _get_deps(conn, wid):
    """Return the set of depends_on_id values for a work item."""
    rows = conn.execute(
        "SELECT depends_on_id FROM Dependency WHERE work_item_id = ?",
        (wid,),
    ).fetchall()
    return {r[0] for r in rows}


def _count_work_items(conn, item_type=None):
    """Count work items, optionally filtered by item_type."""
    if item_type:
        return conn.execute(
            "SELECT COUNT(*) FROM WorkItem WHERE item_type = ?",
            (item_type,),
        ).fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM WorkItem").fetchone()[0]


def _insert_domain(conn, name, code, is_service=False):
    """Insert a Domain and return its id."""
    cur = conn.execute(
        "INSERT INTO Domain (name, code, is_service) VALUES (?, ?, ?)",
        (name, code, is_service),
    )
    conn.commit()
    return cur.lastrowid


def _insert_entity(conn, name, code, entity_type="Base", is_native=False,
                    primary_domain_id=None):
    """Insert an Entity and return its id."""
    cur = conn.execute(
        "INSERT INTO Entity (name, code, entity_type, is_native, primary_domain_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, code, entity_type, is_native, primary_domain_id),
    )
    conn.commit()
    return cur.lastrowid


def _insert_process(conn, domain_id, name, code, sort_order):
    """Insert a Process and return its id."""
    cur = conn.execute(
        "INSERT INTO Process (domain_id, name, code, sort_order) VALUES (?, ?, ?, ?)",
        (domain_id, name, code, sort_order),
    )
    conn.commit()
    return cur.lastrowid


def _complete_work_item(conn, wid):
    """Set a work item's status to complete."""
    conn.execute(
        "UPDATE WorkItem SET status = 'complete', completed_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (wid,),
    )
    conn.commit()


class TestCreateProject:
    """Tests for create_project() — Section 9.4.1."""

    def test_creates_master_prd(self, conn):
        wid = create_project(conn)
        wi = _get_work_item(conn, wid)
        assert wi["item_type"] == "master_prd"
        assert wi["status"] == "ready"

    def test_master_prd_has_no_dependencies(self, conn):
        wid = create_project(conn)
        assert _get_deps(conn, wid) == set()

    def test_only_one_work_item_created(self, conn):
        create_project(conn)
        assert _count_work_items(conn) == 1


class TestAfterMasterPrdImport:
    """Tests for after_master_prd_import() — Section 9.4.2."""

    def test_creates_business_object_discovery(self, conn):
        master_id = create_project(conn)
        _complete_work_item(conn, master_id)
        after_master_prd_import(conn)
        assert _count_work_items(conn, "business_object_discovery") == 1

    def test_bod_depends_on_master_prd(self, conn):
        master_id = create_project(conn)
        _complete_work_item(conn, master_id)
        after_master_prd_import(conn)
        bod_row = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()
        assert _get_deps(conn, bod_row[0]) == {master_id}

    def test_bod_is_ready_when_master_complete(self, conn):
        master_id = create_project(conn)
        _complete_work_item(conn, master_id)
        after_master_prd_import(conn)
        bod = conn.execute(
            "SELECT status FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()
        assert bod[0] == "ready"

    def test_bod_not_started_when_master_not_complete(self, conn):
        create_project(conn)  # master is "ready" not "complete"
        after_master_prd_import(conn)
        bod = conn.execute(
            "SELECT status FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()
        assert bod[0] == "not_started"

    def test_raises_without_master_prd(self, conn):
        with pytest.raises(ValueError, match="master_prd work item not found"):
            after_master_prd_import(conn)


class TestAfterBusinessObjectDiscoveryImport:
    """Tests for after_business_object_discovery_import() — Section 9.4.3."""

    @pytest.fixture()
    def seeded_conn(self, conn):
        """Set up a database through BOD import with domains, entities, processes."""
        # Create domains
        d1 = _insert_domain(conn, "Mentoring", "MN")
        d2 = _insert_domain(conn, "Recruitment", "MR")
        # Create entities
        e1 = _insert_entity(conn, "Contact", "CON", primary_domain_id=d1)
        e2 = _insert_entity(conn, "Mentor", "MEN", primary_domain_id=d1)
        e3 = _insert_entity(conn, "Program", "PRG", primary_domain_id=d2)
        # Create processes
        p1 = _insert_process(conn, d1, "Intake", "MN-INTAKE", 1)
        p2 = _insert_process(conn, d1, "Matching", "MN-MATCH", 2)
        p3 = _insert_process(conn, d2, "Application", "MR-APP", 1)

        # Run graph construction
        master_id = create_project(conn)
        _complete_work_item(conn, master_id)
        after_master_prd_import(conn)
        bod_row = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()
        _complete_work_item(conn, bod_row[0])
        after_business_object_discovery_import(conn)

        return conn, {
            "domains": {"MN": d1, "MR": d2},
            "entities": {"CON": e1, "MEN": e2, "PRG": e3},
            "processes": {"MN-INTAKE": p1, "MN-MATCH": p2, "MR-APP": p3},
        }

    def test_entity_prds_created(self, seeded_conn):
        conn, ids = seeded_conn
        count = _count_work_items(conn, "entity_prd")
        assert count == 3  # one per entity

    def test_entity_prd_domain_id_set(self, seeded_conn):
        conn, ids = seeded_conn
        rows = conn.execute(
            "SELECT entity_id, domain_id FROM WorkItem WHERE item_type = 'entity_prd'"
        ).fetchall()
        entity_to_domain = {r[0]: r[1] for r in rows}
        # CON and MEN belong to MN, PRG to MR
        assert entity_to_domain[ids["entities"]["CON"]] == ids["domains"]["MN"]
        assert entity_to_domain[ids["entities"]["MEN"]] == ids["domains"]["MN"]
        assert entity_to_domain[ids["entities"]["PRG"]] == ids["domains"]["MR"]

    def test_entity_prds_ready_when_bod_complete(self, seeded_conn):
        conn, _ = seeded_conn
        statuses = conn.execute(
            "SELECT status FROM WorkItem WHERE item_type = 'entity_prd'"
        ).fetchall()
        assert all(s[0] == "ready" for s in statuses)

    def test_domain_overviews_created(self, seeded_conn):
        conn, _ = seeded_conn
        assert _count_work_items(conn, "domain_overview") == 2

    def test_domain_overview_depends_on_bod_and_entity_prds(self, seeded_conn):
        conn, ids = seeded_conn
        # MN domain overview should depend on BOD + entity_prds for CON, MEN
        do_row = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'domain_overview' AND domain_id = ?",
            (ids["domains"]["MN"],),
        ).fetchone()
        deps = _get_deps(conn, do_row[0])
        bod_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()[0]
        assert bod_id in deps
        # Should have entity_prds for CON and MEN
        entity_prd_ids = {
            r[0] for r in conn.execute(
                "SELECT id FROM WorkItem WHERE item_type = 'entity_prd' AND domain_id = ?",
                (ids["domains"]["MN"],),
            ).fetchall()
        }
        assert entity_prd_ids.issubset(deps)

    def test_process_definitions_created(self, seeded_conn):
        conn, _ = seeded_conn
        assert _count_work_items(conn, "process_definition") == 3

    def test_process_chain_within_domain(self, seeded_conn):
        conn, ids = seeded_conn
        # MN has Intake (sort_order=1) and Matching (sort_order=2)
        # Matching should depend on Intake
        intake_pd = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'process_definition' AND process_id = ?",
            (ids["processes"]["MN-INTAKE"],),
        ).fetchone()[0]
        match_pd = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'process_definition' AND process_id = ?",
            (ids["processes"]["MN-MATCH"],),
        ).fetchone()[0]
        assert intake_pd in _get_deps(conn, match_pd)

    def test_domain_reconciliation_created(self, seeded_conn):
        conn, _ = seeded_conn
        assert _count_work_items(conn, "domain_reconciliation") == 2

    def test_domain_recon_depends_on_all_process_defs(self, seeded_conn):
        conn, ids = seeded_conn
        recon_row = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'domain_reconciliation' AND domain_id = ?",
            (ids["domains"]["MN"],),
        ).fetchone()
        deps = _get_deps(conn, recon_row[0])
        pd_ids = {
            r[0] for r in conn.execute(
                "SELECT id FROM WorkItem WHERE item_type = 'process_definition' AND domain_id = ?",
                (ids["domains"]["MN"],),
            ).fetchall()
        }
        assert pd_ids.issubset(deps)

    def test_stakeholder_review_depends_on_recon(self, seeded_conn):
        conn, ids = seeded_conn
        sr = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'stakeholder_review' AND domain_id = ?",
            (ids["domains"]["MN"],),
        ).fetchone()
        recon = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'domain_reconciliation' AND domain_id = ?",
            (ids["domains"]["MN"],),
        ).fetchone()
        assert recon[0] in _get_deps(conn, sr[0])

    def test_yaml_gen_depends_on_stakeholder(self, seeded_conn):
        conn, ids = seeded_conn
        yg = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'yaml_generation' AND domain_id = ?",
            (ids["domains"]["MN"],),
        ).fetchone()
        sr = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'stakeholder_review' AND domain_id = ?",
            (ids["domains"]["MN"],),
        ).fetchone()
        assert sr[0] in _get_deps(conn, yg[0])

    def test_crm_selection_depends_on_all_yaml_gen(self, seeded_conn):
        conn, _ = seeded_conn
        crm_sel = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'crm_selection'"
        ).fetchone()
        yg_ids = {
            r[0] for r in conn.execute(
                "SELECT id FROM WorkItem WHERE item_type = 'yaml_generation'"
            ).fetchall()
        }
        assert yg_ids == _get_deps(conn, crm_sel[0])

    def test_singleton_chain(self, seeded_conn):
        conn, _ = seeded_conn
        crm_sel = conn.execute("SELECT id FROM WorkItem WHERE item_type = 'crm_selection'").fetchone()[0]
        crm_dep = conn.execute("SELECT id FROM WorkItem WHERE item_type = 'crm_deployment'").fetchone()[0]
        crm_cfg = conn.execute("SELECT id FROM WorkItem WHERE item_type = 'crm_configuration'").fetchone()[0]
        verif = conn.execute("SELECT id FROM WorkItem WHERE item_type = 'verification'").fetchone()[0]
        assert _get_deps(conn, crm_dep) == {crm_sel}
        assert _get_deps(conn, crm_cfg) == {crm_dep}
        assert _get_deps(conn, verif) == {crm_cfg}

    def test_total_work_item_count(self, seeded_conn):
        conn, _ = seeded_conn
        # 1 master_prd + 1 bod + 3 entity_prd + 2 domain_overview +
        # 3 process_def + 3 user_process_guide + 2 domain_recon +
        # 2 stakeholder + 2 yaml_gen + 1 crm_selection + 1 crm_deployment +
        # 1 crm_configuration + 1 verification = 23
        assert _count_work_items(conn) == 23


class TestMidProjectAdditions:
    """Tests for add_entity(), add_process(), add_domain() — Section 9.4.4."""

    @pytest.fixture()
    def base_conn(self, conn):
        """Set up a database through BOD import with one domain and one entity."""
        d1 = _insert_domain(conn, "Mentoring", "MN")
        e1 = _insert_entity(conn, "Contact", "CON", primary_domain_id=d1)
        p1 = _insert_process(conn, d1, "Intake", "MN-INTAKE", 1)

        master_id = create_project(conn)
        _complete_work_item(conn, master_id)
        after_master_prd_import(conn)
        bod_row = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()
        _complete_work_item(conn, bod_row[0])
        after_business_object_discovery_import(conn)

        return conn, {"domain": d1, "entity": e1, "process": p1}

    def test_add_entity_creates_entity_prd(self, base_conn):
        conn, ids = base_conn
        d1 = ids["domain"]
        new_entity = _insert_entity(conn, "Mentor", "MEN", primary_domain_id=d1)
        wid = add_entity(conn, new_entity)
        wi = _get_work_item(conn, wid)
        assert wi["item_type"] == "entity_prd"
        assert wi["entity_id"] == new_entity
        assert wi["domain_id"] == d1
        assert wi["status"] == "ready"

    def test_add_entity_depends_on_bod(self, base_conn):
        conn, ids = base_conn
        new_entity = _insert_entity(conn, "Mentor", "MEN", primary_domain_id=ids["domain"])
        wid = add_entity(conn, new_entity)
        bod_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()[0]
        assert bod_id in _get_deps(conn, wid)

    def test_add_process_creates_process_def(self, base_conn):
        conn, ids = base_conn
        new_proc = _insert_process(conn, ids["domain"], "Matching", "MN-MATCH", 2)
        wid = add_process(conn, new_proc)
        wi = _get_work_item(conn, wid)
        assert wi["item_type"] == "process_definition"
        assert wi["process_id"] == new_proc
        assert wi["domain_id"] == ids["domain"]

    def test_add_process_depends_on_domain_overview(self, base_conn):
        conn, ids = base_conn
        new_proc = _insert_process(conn, ids["domain"], "Matching", "MN-MATCH", 2)
        wid = add_process(conn, new_proc)
        do_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'domain_overview' AND domain_id = ?",
            (ids["domain"],),
        ).fetchone()[0]
        assert do_id in _get_deps(conn, wid)

    def test_add_process_chains_to_prior(self, base_conn):
        conn, ids = base_conn
        new_proc = _insert_process(conn, ids["domain"], "Matching", "MN-MATCH", 2)
        wid = add_process(conn, new_proc)
        # Prior process is MN-INTAKE
        prior_pd = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'process_definition' AND process_id = ?",
            (ids["process"],),
        ).fetchone()[0]
        assert prior_pd in _get_deps(conn, wid)

    def test_add_process_added_as_recon_dep(self, base_conn):
        conn, ids = base_conn
        new_proc = _insert_process(conn, ids["domain"], "Matching", "MN-MATCH", 2)
        wid = add_process(conn, new_proc)
        recon = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'domain_reconciliation' AND domain_id = ?",
            (ids["domain"],),
        ).fetchone()
        assert wid in _get_deps(conn, recon[0])

    def test_add_domain_creates_full_chain(self, base_conn):
        conn, _ = base_conn
        new_domain = _insert_domain(conn, "Training", "TR")
        created = add_domain(conn, new_domain)
        # Should create: domain_overview, domain_reconciliation,
        # stakeholder_review, yaml_generation (no processes)
        assert len(created) == 4
        types = [
            _get_work_item(conn, wid)["item_type"] for wid in created
        ]
        assert "domain_overview" in types
        assert "domain_reconciliation" in types
        assert "stakeholder_review" in types
        assert "yaml_generation" in types

    def test_add_domain_yaml_gen_added_to_crm_selection(self, base_conn):
        conn, _ = base_conn
        new_domain = _insert_domain(conn, "Training", "TR")
        add_domain(conn, new_domain)
        yg_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'yaml_generation' AND domain_id = ?",
            (new_domain,),
        ).fetchone()[0]
        crm_sel = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'crm_selection'"
        ).fetchone()[0]
        assert yg_id in _get_deps(conn, crm_sel)
