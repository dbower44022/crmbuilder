"""Tests for run worker orchestration with skip_deletes behavior.

These test the _run_full logic directly by mocking the API client,
without requiring a Qt event loop.
"""

from unittest.mock import MagicMock, patch

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.comparator import FieldComparator
from espo_impl.core.field_manager import AuthenticationError, FieldManager
from espo_impl.core.models import (
    DuplicateCheck,
    EntityAction,
    EntityDefinition,
    FieldDefinition,
    InstanceProfile,
    ProgramFile,
    SavedView,
    StepStatus,
)
from espo_impl.core.saved_view_manager import SavedViewManagerError
from espo_impl.workers.run_worker import RunWorker


def make_program(entities=None) -> ProgramFile:
    if entities is None:
        entities = []
    return ProgramFile(
        version="1.0",
        description="Test",
        entities=entities,
    )


def make_entity(
    name="TestEntity",
    action=EntityAction.DELETE_AND_CREATE,
    fields=None,
    **kwargs,
) -> EntityDefinition:
    defaults = {
        "type": "Base",
        "labelSingular": name,
        "labelPlural": f"{name}s",
    }
    defaults.update(kwargs)
    if fields is None:
        fields = [FieldDefinition(name="testField", type="varchar", label="Test")]
    return EntityDefinition(name=name, action=action, fields=fields, **defaults)


def run_worker_sync(program, skip_deletes=False, client=None):
    """Run the worker's _run_full synchronously with a mock client.

    :returns: Tuple of (client, output_log, report_or_none, error_or_none).
    """
    if client is None:
        client = MagicMock(spec=EspoAdminClient)
        client.profile = MagicMock(spec=InstanceProfile)
        client.profile.name = "Test"
        client.profile.url = "https://test.com"
        client.profile.api_url = "https://test.com/api/v1"
        client.check_entity_exists.return_value = (200, True)
        client.remove_entity.return_value = (200, {})
        client.create_entity.return_value = (200, {})
        client.rebuild.return_value = (200, {})
        client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    output_log: list[tuple[str, str]] = []

    comparator = FieldComparator()
    field_mgr = FieldManager(
        client, comparator, lambda m, c: output_log.append((m, c))
    )

    worker = RunWorker.__new__(RunWorker)
    worker.profile = client.profile
    worker.program = program
    worker.operation = "run"
    worker.skip_deletes = skip_deletes
    worker.output_line = MagicMock()
    worker.output_line.emit = lambda m, c: output_log.append((m, c))
    worker.finished_ok = MagicMock()
    worker.finished_error = MagicMock()

    worker._run_full(client, field_mgr)

    report = None
    error = None
    if worker.finished_ok.emit.called:
        report = worker.finished_ok.emit.call_args[0][0]
    if worker.finished_error.emit.called:
        error = worker.finished_error.emit.call_args[0][0]

    return client, output_log, report, error


def test_full_rebuild_deletes_and_creates():
    """Full rebuild mode: deletes entities, rebuilds, creates, rebuilds."""
    client = MagicMock(spec=EspoAdminClient)
    client.profile = MagicMock(spec=InstanceProfile)
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.profile.api_url = "https://test.com/api/v1"
    # Delete check: exists. Create check: doesn't exist (just deleted).
    client.check_entity_exists.side_effect = [
        (200, True),   # delete check
        (200, False),  # create check
    ]
    client.remove_entity.return_value = (200, {})
    client.create_entity.return_value = (200, {})
    client.rebuild.return_value = (200, {})
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    program = make_program([
        make_entity("Engagement", EntityAction.DELETE_AND_CREATE),
    ])

    client, output_log, report, error = run_worker_sync(
        program, skip_deletes=False, client=client
    )

    assert error is None
    client.remove_entity.assert_called_once()
    client.create_entity.assert_called_once()
    assert client.rebuild.call_count == 2
    messages = [m for m, _ in output_log]
    assert any("ENTITY DELETIONS" in m for m in messages)
    assert any("ENTITY CREATION" in m for m in messages)


def test_skip_deletes_no_delete_calls():
    """Skip deletes mode: no delete API calls, entities created if not exist."""
    client = MagicMock(spec=EspoAdminClient)
    client.profile = MagicMock(spec=InstanceProfile)
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.profile.api_url = "https://test.com/api/v1"
    # In skip mode, only create check happens — entity doesn't exist
    client.check_entity_exists.return_value = (200, False)
    client.create_entity.return_value = (200, {})
    client.rebuild.return_value = (200, {})
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    program = make_program([
        make_entity("Engagement", EntityAction.DELETE_AND_CREATE),
    ])

    client, output_log, report, error = run_worker_sync(
        program, skip_deletes=True, client=client
    )

    assert error is None
    client.remove_entity.assert_not_called()
    client.create_entity.assert_called_once()
    assert client.rebuild.call_count == 1
    messages = [m for m, _ in output_log]
    assert any("field-update mode" in m for m in messages)
    assert not any("ENTITY DELETIONS" in m for m in messages)


def test_skip_deletes_with_pure_delete_entity():
    """Skip deletes mode: action=delete entities are fully skipped."""
    client = MagicMock(spec=EspoAdminClient)
    client.profile = MagicMock(spec=InstanceProfile)
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.profile.api_url = "https://test.com/api/v1"
    client.check_entity_exists.return_value = (200, False)
    client.create_entity.return_value = (200, {})
    client.rebuild.return_value = (200, {})
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    program = make_program([
        make_entity("OldEntity", EntityAction.DELETE, fields=[]),
        make_entity("Engagement", EntityAction.DELETE_AND_CREATE),
    ])

    client, output_log, report, error = run_worker_sync(
        program, skip_deletes=True, client=client
    )

    assert error is None
    client.remove_entity.assert_not_called()
    # Only delete_and_create entity gets created, not the pure delete one
    client.create_entity.assert_called_once()


def test_skip_deletes_existing_entity_skips_create():
    """Skip deletes: if entity already exists, create is skipped."""
    program = make_program([
        make_entity("Engagement", EntityAction.DELETE_AND_CREATE),
    ])

    # Default mock: check_entity_exists returns (200, True)
    client, output_log, report, error = run_worker_sync(
        program, skip_deletes=True
    )

    assert error is None
    messages = [m for m, _ in output_log]
    assert any("ALREADY EXISTS" in m for m in messages)


def test_full_rebuild_field_operations_proceed():
    """Full rebuild: field operations run after entity operations."""
    client = MagicMock(spec=EspoAdminClient)
    client.profile = MagicMock(spec=InstanceProfile)
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.profile.api_url = "https://test.com/api/v1"
    client.check_entity_exists.side_effect = [
        (200, True),   # delete check
        (200, False),  # create check
    ]
    client.remove_entity.return_value = (200, {})
    client.create_entity.return_value = (200, {})
    client.rebuild.return_value = (200, {})
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    program = make_program([
        make_entity("Engagement", EntityAction.DELETE_AND_CREATE),
    ])

    client, output_log, report, error = run_worker_sync(
        program, skip_deletes=False, client=client
    )

    assert error is None
    assert report is not None
    messages = [m for m, _ in output_log]
    assert any("FIELD OPERATIONS" in m for m in messages)


# ───────────────────────────────────────────────────────────────────────
# Per-step isolation tests (Prompt B)
# ───────────────────────────────────────────────────────────────────────


def _make_default_client() -> MagicMock:
    """Build a permissive mock client used by the per-step isolation tests."""
    client = MagicMock(spec=EspoAdminClient)
    client.profile = MagicMock(spec=InstanceProfile)
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.profile.api_url = "https://test.com/api/v1"
    client.check_entity_exists.return_value = (200, True)
    client.remove_entity.return_value = (200, {})
    client.create_entity.return_value = (200, {})
    client.rebuild.return_value = (200, {})
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})
    return client


def _step_results_by_name(report) -> dict[str, "StepStatus"]:
    return {sr.step_name: sr.status for sr in report.step_results}


def test_run_full_all_steps_succeed_step_results_populated():
    """Successful run records OK or SKIPPED for every step."""
    program = make_program([
        make_entity("Engagement", EntityAction.NONE, fields=[
            FieldDefinition(name="testField", type="varchar", label="Test"),
        ]),
    ])

    client, _, report, error = run_worker_sync(
        program, skip_deletes=True
    )

    assert error is None
    assert report is not None
    by_name = _step_results_by_name(report)
    # Every canonical step name must appear.
    expected_steps = {
        "entity_deletions", "entity_creations", "entity_settings",
        "email_templates", "duplicate_checks", "saved_views", "fields",
        "layouts", "relationships", "workflows",
    }
    assert set(by_name.keys()) == expected_steps
    # No FAILED states.
    assert all(
        status in (StepStatus.OK, StepStatus.SKIPPED)
        for status in by_name.values()
    )
    # The "fields" step had work to do, so it should be OK (not SKIPPED).
    assert by_name["fields"] == StepStatus.OK


def test_run_full_saved_views_manager_error_contained():
    """A SavedViewManagerError marks that step FAILED but the run continues."""
    program = make_program([
        EntityDefinition(
            name="Engagement",
            action=EntityAction.NONE,
            type="Base",
            fields=[
                FieldDefinition(name="testField", type="varchar", label="Test"),
            ],
            saved_views=[
                SavedView(id="sv1", name="My View", columns=["testField"]),
            ],
        ),
    ])

    with patch(
        "espo_impl.workers.run_worker.SavedViewManager"
    ) as mock_sv_cls:
        mock_sv_cls.return_value.process_saved_views.side_effect = (
            SavedViewManagerError("Bad payload")
        )

        client, output_log, report, error = run_worker_sync(
            program, skip_deletes=True
        )

    assert error is None, "soft failures must not abort the run"
    assert report is not None
    by_name = _step_results_by_name(report)
    assert by_name["saved_views"] == StepStatus.FAILED
    # Subsequent steps still get a status.
    assert "fields" in by_name and by_name["fields"] == StepStatus.OK
    # Failure detail surfaced in the output.
    messages = [m for m, _ in output_log]
    assert any("[STEP FAILED] saved_views" in m for m in messages)
    assert any("Bad payload" in m for m in messages)


def test_run_full_unexpected_exception_contained():
    """An unexpected KeyError marks the step FAILED but the run continues."""
    program = make_program([
        EntityDefinition(
            name="Engagement",
            action=EntityAction.NONE,
            type="Base",
            fields=[
                FieldDefinition(name="testField", type="varchar", label="Test"),
            ],
            duplicate_checks=[
                DuplicateCheck(id="d1", fields=["testField"], onMatch="block"),
            ],
        ),
    ])

    with patch(
        "espo_impl.workers.run_worker.DuplicateCheckManager"
    ) as mock_dup_cls:
        mock_dup_cls.return_value.process_duplicate_checks.side_effect = (
            KeyError("foo")
        )

        client, output_log, report, error = run_worker_sync(
            program, skip_deletes=True
        )

    assert error is None
    assert report is not None
    by_name = _step_results_by_name(report)
    assert by_name["duplicate_checks"] == StepStatus.FAILED
    failed_entry = next(
        sr for sr in report.step_results if sr.step_name == "duplicate_checks"
    )
    assert "KeyError" in (failed_entry.error or "")
    # And later steps must still have fired (they have work).
    assert by_name["fields"] == StepStatus.OK


def test_run_full_authentication_error_aborts():
    """A direct AuthenticationError from a step terminates the run."""
    program = make_program([
        EntityDefinition(
            name="Engagement",
            action=EntityAction.NONE,
            type="Base",
            fields=[
                FieldDefinition(name="testField", type="varchar", label="Test"),
            ],
            saved_views=[
                SavedView(id="sv1", name="My View", columns=["testField"]),
            ],
        ),
    ])

    with patch(
        "espo_impl.workers.run_worker.SavedViewManager"
    ) as mock_sv_cls:
        mock_sv_cls.return_value.process_saved_views.side_effect = (
            AuthenticationError()
        )

        client, output_log, report, error = run_worker_sync(
            program, skip_deletes=True
        )

    assert error is not None
    assert report is None
    messages = [m for m, _ in output_log]
    assert any("[FATAL]" in m and "saved_views" in m for m in messages)


def test_run_full_401_message_promoted_to_fatal():
    """A manager error whose message contains '401' aborts the run."""
    program = make_program([
        EntityDefinition(
            name="Engagement",
            action=EntityAction.NONE,
            type="Base",
            fields=[
                FieldDefinition(name="testField", type="varchar", label="Test"),
            ],
            saved_views=[
                SavedView(id="sv1", name="My View", columns=["testField"]),
            ],
        ),
    ])

    with patch(
        "espo_impl.workers.run_worker.SavedViewManager"
    ) as mock_sv_cls:
        mock_sv_cls.return_value.process_saved_views.side_effect = (
            SavedViewManagerError("Authentication failed (HTTP 401)")
        )

        client, output_log, report, error = run_worker_sync(
            program, skip_deletes=True
        )

    assert error is not None
    assert report is None
    messages = [m for m, _ in output_log]
    assert any("[FATAL]" in m for m in messages)


def test_step_summary_emission():
    """Step summary block is emitted at the end of every full run."""
    program = make_program([
        make_entity("Engagement", EntityAction.NONE, fields=[
            FieldDefinition(name="testField", type="varchar", label="Test"),
        ]),
    ])

    _, output_log, report, error = run_worker_sync(
        program, skip_deletes=True
    )

    assert error is None
    assert report is not None
    messages = [m for m, _ in output_log]
    assert any("STEP SUMMARY" in m for m in messages)
    assert any("Run completed successfully" in m for m in messages)


def test_step_summary_lists_failure_count():
    """When a step fails, the summary footer reports the failure count."""
    program = make_program([
        EntityDefinition(
            name="Engagement",
            action=EntityAction.NONE,
            type="Base",
            fields=[
                FieldDefinition(name="testField", type="varchar", label="Test"),
            ],
            saved_views=[
                SavedView(id="sv1", name="My View", columns=["testField"]),
            ],
        ),
    ])

    with patch(
        "espo_impl.workers.run_worker.SavedViewManager"
    ) as mock_sv_cls:
        mock_sv_cls.return_value.process_saved_views.side_effect = (
            SavedViewManagerError("Bad payload")
        )

        _, output_log, report, error = run_worker_sync(
            program, skip_deletes=True
        )

    assert error is None
    messages = [m for m, _ in output_log]
    assert any(
        "Run completed with 1 step failure" in m for m in messages
    )


def test_configure_progress_yellow_on_step_failure():
    """ConfigureProgressDialog._on_worker_ok flags yellow when steps fail.

    Tests the outcome-derivation logic without spinning up a Qt dialog by
    invoking the bound method on a synthetic instance and inspecting the
    file_results / file_tooltips dicts it populates.
    """
    from automation.ui.deployment.configure_progress import (
        ConfigureProgressDialog,
    )
    from espo_impl.core.models import RunReport, StepResult

    # Build a synthetic dialog instance without running __init__.
    dlg = ConfigureProgressDialog.__new__(ConfigureProgressDialog)
    dlg._worker = object()
    dlg._file_results = {}
    dlg._file_tooltips = {}
    dlg._current_log_lines = []
    dlg._current_started_at = "2026-05-02T00:00:00"
    dlg._current_program = None
    dlg._current_file_hash = None
    dlg._conn = None
    dlg._instance = None
    file_info = MagicMock()
    file_info.path = "/tmp/foo.yaml"
    file_info.name = "foo.yaml"
    dlg._current_file_info = file_info
    dlg._append_log = lambda *args, **kwargs: None
    dlg._run_next = lambda: None

    report = RunReport(
        timestamp="2026-05-02T00:00:00",
        instance_name="Test",
        espocrm_url="https://test.com",
        program_file="foo.yaml",
        operation="run",
        step_results=[
            StepResult(step_name="fields", status=StepStatus.OK),
            StepResult(
                step_name="saved_views",
                status=StepStatus.FAILED,
                error="Bad payload",
            ),
        ],
    )

    dlg._on_worker_ok(report)

    outcome, _ts = dlg._file_results["/tmp/foo.yaml"]
    assert outcome == "partial"
    tooltip = dlg._file_tooltips["/tmp/foo.yaml"]
    assert "saved_views" in tooltip


def test_configure_progress_green_on_clean_run():
    """A run with no step failures keeps the success outcome and no tooltip."""
    from automation.ui.deployment.configure_progress import (
        ConfigureProgressDialog,
    )
    from espo_impl.core.models import RunReport, StepResult

    dlg = ConfigureProgressDialog.__new__(ConfigureProgressDialog)
    dlg._worker = object()
    dlg._file_results = {}
    dlg._file_tooltips = {}
    dlg._current_log_lines = []
    dlg._current_started_at = "2026-05-02T00:00:00"
    dlg._current_program = None
    dlg._current_file_hash = None
    dlg._conn = None
    dlg._instance = None
    file_info = MagicMock()
    file_info.path = "/tmp/clean.yaml"
    file_info.name = "clean.yaml"
    dlg._current_file_info = file_info
    dlg._append_log = lambda *args, **kwargs: None
    dlg._run_next = lambda: None

    report = RunReport(
        timestamp="2026-05-02T00:00:00",
        instance_name="Test",
        espocrm_url="https://test.com",
        program_file="clean.yaml",
        operation="run",
        step_results=[
            StepResult(step_name="fields", status=StepStatus.OK),
            StepResult(step_name="saved_views", status=StepStatus.SKIPPED),
        ],
    )

    dlg._on_worker_ok(report)

    outcome, _ts = dlg._file_results["/tmp/clean.yaml"]
    assert outcome == "success"
    assert "/tmp/clean.yaml" not in dlg._file_tooltips
