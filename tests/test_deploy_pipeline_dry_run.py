"""Dry-run (preview) mode of the deploy pipeline — PRJ-042 / PI-252 (REQ-289).

Proves the headline guarantee: with ``dry_run=True`` the pipeline performs NO
writes against the target (no create/update/delete, no cache rebuild) and the
report is a ``preview``. The managers still read current state to compute the
planned action.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.comparator import FieldComparator
from espo_impl.core.deploy_pipeline import deploy_pipeline
from espo_impl.core.field_manager import FieldManager
from espo_impl.core.models import (
    EntityAction,
    EntityDefinition,
    InstanceProfile,
    ProgramFile,
    StepStatus,
)


def _mock_client() -> MagicMock:
    client = MagicMock(spec=EspoAdminClient)
    client.profile = MagicMock(spec=InstanceProfile)
    client.profile.name = "Target"
    client.profile.url = "https://t.example.org"
    client.profile.api_url = "https://t.example.org/api/v1"
    # Reads: the entity does not exist yet -> it WOULD be created.
    client.check_entity_exists.return_value = (200, False)
    return client


def _program() -> ProgramFile:
    return ProgramFile(
        version="1.0",
        description="dry-run",
        entities=[
            EntityDefinition(
                name="Engagement",
                action=EntityAction.CREATE,
                type="Base",
                fields=[],
            )
        ],
    )


def test_dry_run_makes_no_writes_and_reports_preview():
    client = _mock_client()
    log: list[tuple[str, str]] = []
    out = lambda m, c: log.append((m, c))  # noqa: E731
    field_mgr = FieldManager(client, FieldComparator(), out)

    outcome = deploy_pipeline(
        _program(), client, field_mgr, out, dry_run=True
    )

    # The entity WOULD be created — the read happened...
    client.check_entity_exists.assert_called()
    # ...but nothing was written to the target, and no cache rebuild fired.
    client.create_entity.assert_not_called()
    client.remove_entity.assert_not_called()
    client.update_entity.assert_not_called()
    client.create_field.assert_not_called()
    client.update_field.assert_not_called()
    client.create_link.assert_not_called()
    client.save_layout.assert_not_called()
    client.rebuild.assert_not_called()

    # The report is a preview, and the entity-creation step is OK (planned).
    assert outcome.report.operation == "preview"
    by_name = {sr.step_name: sr.status for sr in outcome.report.step_results}
    assert by_name["entity_creations"] == StepStatus.OK
    assert any("would create (preview)" in m for m, _ in log)


def test_non_dry_run_still_writes():
    """Guard: with dry_run=False the create path still calls the write."""
    client = _mock_client()
    client.create_entity.return_value = (200, {"id": "x"})
    client.rebuild.return_value = (200, {})
    client.get_entity_full_metadata.return_value = (200, {"name": "Engagement"})
    log: list[tuple[str, str]] = []
    out = lambda m, c: log.append((m, c))  # noqa: E731
    field_mgr = FieldManager(client, FieldComparator(), out)

    deploy_pipeline(_program(), client, field_mgr, out, dry_run=False)
    client.create_entity.assert_called_once()
