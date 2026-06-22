"""Publish-run history endpoint tests — PI-266 (PRJ-042 / REQ-293).

Read-only ``GET /publish-runs`` (list, newest-first, optional instance filter)
and ``GET /publish-runs/{id}`` (detail incl. the backup snapshot). Rows are
seeded through the repository, since they are written only by the publish path.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import publish_runs


def _seed(**kw):
    with session_scope() as s:
        return publish_runs.create_publish_run(s, **kw)


def test_list_publish_runs_newest_first(client):
    _seed(instance_identifier="INST-001", status="succeeded")
    _seed(instance_identifier="INST-002", status="failed")
    r = client.get("/publish-runs")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert [d["publish_run_identifier"] for d in data] == ["PUB-002", "PUB-001"]


def test_list_publish_runs_filtered_by_instance(client):
    _seed(instance_identifier="INST-001", status="succeeded")
    _seed(instance_identifier="INST-002", status="succeeded")
    r = client.get("/publish-runs?instance=INST-002")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["instance_identifier"] == "INST-002"


def test_get_publish_run_detail_includes_backup(client):
    _seed(
        instance_identifier="INST-001",
        status="succeeded",
        scope=["Contact.yaml"],
        backup={"entities": {"Contact": {"fields": {}}}},
        summary={"deployed": ["Contact.yaml"]},
    )
    r = client.get("/publish-runs/PUB-001")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["publish_run_scope"] == ["Contact.yaml"]
    assert data["publish_run_backup"]["entities"]["Contact"] == {"fields": {}}
    assert data["publish_run_summary"]["deployed"] == ["Contact.yaml"]


def test_get_unknown_publish_run_404(client):
    r = client.get("/publish-runs/PUB-999")
    assert r.status_code == 404
