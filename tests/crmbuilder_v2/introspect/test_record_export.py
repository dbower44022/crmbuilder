"""Record-export engine tests — PI-234 (REQ-130, DEC-693)."""

from __future__ import annotations

from crmbuilder_v2.introspect.record_export import ARTIFACT_FORMAT, export_records


class _FakeRecords:
    def __init__(self, data, totals=None, status=200):
        self._data = data
        self._totals = totals or {}
        self._status = status

    def get_records(self, entity, *, max_size=200, offset=0):
        if self._status != 200:
            return (self._status, None)
        recs = self._data.get(entity, [])[:max_size]
        total = self._totals.get(entity, len(self._data.get(entity, [])))
        return (200, {"total": total, "list": recs})


def test_export_basic():
    client = _FakeRecords({
        "CMentorProfile": [{"id": "1", "name": "a"}, {"id": "2", "name": "b"}],
        "CDues": [{"id": "3", "amount": 100}],
    })
    art = export_records(client, entity_names=["CMentorProfile", "CDues"])
    assert art["format"] == ARTIFACT_FORMAT
    assert art["entities"]["CMentorProfile"]["count"] == 2
    assert art["entities"]["CMentorProfile"]["records"][0]["name"] == "a"
    assert art["entities"]["CDues"]["count"] == 1
    assert art["summary"]["record_count"] == 3
    assert art["summary"]["entity_count"] == 2
    assert art["summary"]["truncated"] is False


def test_export_truncation_flagged():
    client = _FakeRecords(
        {"Big": [{"id": str(i)} for i in range(50)]}, totals={"Big": 500})
    log = []
    art = export_records(
        client, entity_names=["Big"], max_size=10,
        progress=lambda m, lvl: log.append((m, lvl)))
    e = art["entities"]["Big"]
    assert e["count"] == 10 and e["truncated"] is True
    assert art["summary"]["truncated"] is True
    assert any("truncated" in m for m, lvl in log)


def test_export_read_error_continues():
    client = _FakeRecords({}, status=500)
    log = []
    art = export_records(
        client, entity_names=["X"], progress=lambda m, lvl: log.append((m, lvl)))
    assert art["entities"]["X"]["error"] == "HTTP 500"
    assert art["entities"]["X"]["count"] == 0
    assert any("could not read" in m for m, lvl in log)
