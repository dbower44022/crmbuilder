"""PI-134 working demo — the reconciliation gate holds Develop, then releases.

Runs end-to-end against a **create_all SQLite DB** (a throwaway temp file, NOT
the live DB) via the in-process FastAPI app — real findings API, real edges. It
seeds a Planning Item with a Complete Design phase and a Ready Develop Work Task,
then shows (DEC-400):

1. with an **open blocking finding** related to the PI, the runtime REFUSES to
   dispatch the Develop Work Task (the gate holds it);
2. once the finding is **resolved**, the runtime dispatches it.

Run:  uv run python scripts/demo_pi134_reconciliation_gate.py
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime


def main() -> int:
    db = tempfile.mktemp(suffix=".db")
    os.environ["CRMBUILDER_V2_DB_PATH"] = db
    os.environ["CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED"] = "true"

    from crmbuilder_v2.access import engagement_scope
    from crmbuilder_v2.access.db import (
        bootstrap_database,
        get_session_factory,
        reset_engine_cache,
    )
    from crmbuilder_v2.access.models import EngagementRow
    from crmbuilder_v2.config import reset_settings_cache

    reset_settings_cache()
    reset_engine_cache()
    bootstrap_database()
    with get_session_factory()() as s:
        s.add(
            EngagementRow(
                engagement_identifier="ENG-001",
                engagement_code="DEMO",
                engagement_name="Demo",
                engagement_purpose="demo",
                engagement_status="active",
                engagement_created_at=datetime.now(UTC),
                engagement_updated_at=datetime.now(UTC),
            )
        )
        s.commit()
    engagement_scope.set_active_engagement("ENG-001")
    engagement_scope.set_enforcement(True)

    from fastapi.testclient import TestClient

    from crmbuilder_v2.api.main import create_app
    from crmbuilder_v2.scheduler import dispatcher, reconciliation
    from crmbuilder_v2.scheduler.parallel_scheduler import (
        ParallelCoordinatingScheduler,
        ParallelSchedulerConfig,
    )

    client = TestClient(create_app())
    client.headers.update({"X-Engagement": "ENG-001"})

    def _data(r):
        body = r.json()
        assert r.status_code < 300, body
        return body["data"]

    def _edge(src_t, src, tgt_t, tgt, rel):
        return _data(
            client.post(
                "/references",
                json={"source_type": src_t, "source_id": src, "target_type": tgt_t,
                      "target_id": tgt, "relationship": rel},
            )
        )

    # --- seed: PI with a Complete Design phase + a Ready Develop Work Task ---
    pi = _data(client.post("/planning-items", json={
        "title": "Demo PI", "item_type": "pending_work", "status": "Draft",
        "executive_summary": (
            "Demonstration planning item for the PI-134 reconciliation gate. It "
            "carries a Complete Design phase and a Ready Develop Work Task so the "
            "only thing that can withhold the Develop dispatch is an open blocking "
            "finding on the Planning Item's cross-area coherence check, which the "
            "runtime enforces before any Develop work begins."
        )}))["identifier"]
    design = _data(client.post("/workstreams", json={
        "workstream_phase_type": "Design", "workstream_title": "Design"}))["workstream_identifier"]
    develop = _data(client.post("/workstreams", json={
        "workstream_phase_type": "Develop", "workstream_title": "Develop"}))["workstream_identifier"]
    _edge("workstream", design, "planning_item", pi, "workstream_belongs_to_planning_item")
    _edge("workstream", develop, "planning_item", pi, "workstream_belongs_to_planning_item")
    for st in ("Scoping", "Ready", "In Progress", "Complete"):
        client.patch(f"/workstreams/{design}", json={"workstream_status": st})
    wtk = _data(client.post("/work-tasks", json={
        "work_task_title": "Build the thing", "work_task_area": "api"}))["work_task_identifier"]
    _edge("work_task", wtk, "workstream", develop, "work_task_belongs_to_workstream")
    client.patch(f"/work-tasks/{wtk}", json={"work_task_status": "Ready"})

    # An open blocking finding on the PI's reconciliation.
    fnd = _data(client.post("/findings", json={
        "finding_type": "conflict", "finding_severity": "blocking",
        "finding_summary": "two area specs disagree on the FK direction"}))["finding_identifier"]
    _edge("finding", fnd, "planning_item", pi, "finding_relates_to")

    print(f"Seeded: PI={pi}  Design={design}(Complete)  Develop={develop}  "
          f"Develop-task={wtk}(Ready)  finding={fnd}(blocking/open)\n")

    # --- route the runtime's API reads through the in-process TestClient ------
    def routed_get(api_base, path, eng):
        r = client.get(path)
        return r.json()["data"]

    dispatcher._get = routed_get  # reconciliation + pool both call dispatcher._get

    def routed_blockers(api_base, eng, tid):
        return []  # the Work Task has no blocked_by predecessors

    dispatcher._blocker_statuses = routed_blockers

    cfg = ParallelSchedulerConfig(target_work_tasks=[wtk], max_concurrent=2)
    rt = ParallelCoordinatingScheduler(config=cfg, log=lambda m: None)

    # Phase 1 — the gate holds the Develop task.
    decision = reconciliation.develop_gate("x", "ENG-001",
                                           routed_get("x", f"/work-tasks/{wtk}", "ENG-001"))
    dispatchable = rt._eligible_candidates()
    print("Phase 1 — open blocking finding")
    print(f"  gate decision : allow={decision.allow}  reason='{decision.reason}'")
    print(f"  dispatchable  : {dispatchable}  → Develop is {'HELD ✔' if not dispatchable else 'WRONGLY dispatchable'}")

    # Resolve the finding.
    client.patch(f"/findings/{fnd}", json={
        "finding_status": "resolved", "finding_resolution": "revised the Design spec",
        "finding_resolution_method": "revise"})
    print(f"\n  >>> resolved {fnd} (revised the Design spec)\n")

    # Phase 2 — the gate releases.
    decision2 = reconciliation.develop_gate("x", "ENG-001",
                                            routed_get("x", f"/work-tasks/{wtk}", "ENG-001"))
    dispatchable2 = rt._eligible_candidates()
    print("Phase 2 — finding resolved")
    print(f"  gate decision : allow={decision2.allow}  reason='{decision2.reason}'")
    print(f"  dispatchable  : {dispatchable2}  → Develop is {'DISPATCHED ✔' if dispatchable2 == [wtk] else 'WRONGLY held'}")

    ok = (not dispatchable) and dispatchable2 == [wtk]
    print(f"\n  DEMO {'PASSED ✔' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
