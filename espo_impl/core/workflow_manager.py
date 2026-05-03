"""Workflow CHECK->ACT orchestration logic."""

import logging
from collections.abc import Callable
from typing import Any

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.condition_expression import render_condition
from espo_impl.core.models import (
    EntityAction,
    EntityDefinition,
    ProgramFile,
    Workflow,
    WorkflowResult,
    WorkflowStatus,
)
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class WorkflowManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class WorkflowManager:
    """Orchestrates workflow recognition and reporting.

    Workflows in EspoCRM are entity records exposed via
    ``/api/v1/Workflow`` (and require the Advanced Pack extension), not
    metadata writes. This manager recognizes YAML-declared workflows,
    emits a NOT SUPPORTED line for each, and returns ``NOT_SUPPORTED``
    results so the run worker can surface them in its MANUAL
    CONFIGURATION REQUIRED block.

    The legacy CHECK/WRITE private helpers below are retained as dead
    code so a future Workflow-record-CRUD reimplementation can
    resurrect them with a smaller diff.

    :param client: EspoCRM admin API client.
    :param output_fn: Callback for emitting output messages (message, color).
    """

    def __init__(
        self,
        client: EspoAdminClient,
        output_fn: OutputCallback,
    ) -> None:
        self.client = client
        self.output_fn = output_fn

    def process_workflows(
        self, program: ProgramFile
    ) -> list[WorkflowResult]:
        """Acknowledge workflows from the YAML; do not attempt API writes.

        EspoCRM has no public REST API for clientDefs metadata writes,
        and workflows are not metadata in the first place — they are
        entity records that require the Advanced Pack extension.
        Workflows must be configured manually via the EspoCRM admin UI.

        This method iterates every workflow declared in the YAML, emits
        a NOT SUPPORTED line per item, and returns results all marked
        ``WorkflowStatus.NOT_SUPPORTED``. The MANUAL CONFIGURATION
        REQUIRED block at the end of the run aggregates these for
        operator action.

        :param program: Parsed and validated program file.
        :returns: List of per-workflow results, each with status NOT_SUPPORTED.
        """
        results: list[WorkflowResult] = []

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if not entity_def.workflows:
                continue

            for wf in entity_def.workflows:
                self.output_fn(
                    f"[NOT SUPPORTED] {entity_def.name}.workflows"
                    f"[{wf.id}] — manual config required",
                    "yellow",
                )
                results.append(
                    WorkflowResult(
                        entity=entity_def.name,
                        workflow_id=wf.id,
                        status=WorkflowStatus.NOT_SUPPORTED,
                    )
                )

        return results

    def _process_entity_workflows(
        self, entity_def: EntityDefinition
    ) -> list[WorkflowResult]:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """CHECK->ACT for all workflows on one entity.

        :param entity_def: Entity definition with workflows.
        :returns: List of results for each workflow.
        :raises WorkflowManagerError: On authentication failure.
        """
        espo_name = get_espo_entity_name(entity_def.name)
        prefix = entity_def.name

        # Phase 1: CHECK — read current clientDefs metadata
        self.output_fn(
            f"[CHECK]   {prefix} workflows ...", "white"
        )
        status_code, client_defs = self.client.get_client_defs(espo_name)

        if status_code == 401:
            raise WorkflowManagerError(
                "Authentication failed (HTTP 401)"
            )

        if status_code < 0:
            self.output_fn(
                f"[ERROR]   {prefix} workflows ... CONNECTION ERROR",
                "red",
            )
            return [
                WorkflowResult(
                    entity=entity_def.name,
                    workflow_id=wf.id,
                    status=WorkflowStatus.ERROR,
                    error="Connection error",
                )
                for wf in entity_def.workflows
            ]

        if client_defs is None:
            client_defs = {}

        # Extract existing workflows from metadata
        existing_workflows = self._extract_existing_workflows(client_defs)
        results: list[WorkflowResult] = []
        desired_ids: set[str] = set()

        for wf in entity_def.workflows:
            desired_ids.add(wf.id)
            result = self._process_workflow(
                entity_def.name, espo_name, wf, existing_workflows
            )
            results.append(result)

        # Drift detection: workflows on CRM not in YAML
        for existing in existing_workflows:
            eid = existing.get("id", "")
            if eid and eid not in desired_ids:
                self.output_fn(
                    f"[DRIFT]   {prefix}.workflows[{eid}] "
                    f"exists on CRM but not in YAML",
                    "yellow",
                )
                results.append(WorkflowResult(
                    entity=entity_def.name,
                    workflow_id=eid,
                    status=WorkflowStatus.DRIFT,
                ))

        # Phase 2: ACT — write updated workflows to metadata
        if any(
            r.status in (WorkflowStatus.CREATED, WorkflowStatus.UPDATED)
            for r in results
        ):
            write_ok = self._write_workflows(
                entity_def.name, espo_name, entity_def.workflows,
                existing_workflows, desired_ids,
            )
            if not write_ok:
                for r in results:
                    if r.status in (
                        WorkflowStatus.CREATED,
                        WorkflowStatus.UPDATED,
                    ):
                        r.status = WorkflowStatus.ERROR
                        r.error = "Failed to write metadata"

        return results

    def _process_workflow(
        self,
        entity_name: str,
        espo_name: str,
        wf: Workflow,
        existing_workflows: list[dict],
    ) -> WorkflowResult:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """Compare a single workflow against existing CRM state.

        :param entity_name: Natural entity name.
        :param espo_name: EspoCRM entity name (C-prefixed).
        :param wf: Desired workflow.
        :param existing_workflows: Current workflows from the CRM.
        :returns: Result indicating create/update/skip.
        """
        prefix = f"{entity_name}.workflows[{wf.id}]"

        # Find existing workflow by id
        existing = None
        for ew in existing_workflows:
            if ew.get("id") == wf.id:
                existing = ew
                break

        desired = self._workflow_to_dict(wf)

        if existing is None:
            self.output_fn(
                f"[CREATE]  {prefix} ... NOT FOUND ON CRM", "white"
            )
            return WorkflowResult(
                entity=entity_name,
                workflow_id=wf.id,
                status=WorkflowStatus.CREATED,
            )

        # Compare
        if self._workflows_match(desired, existing):
            self.output_fn(
                f"[SKIP]    {prefix} ... MATCHES", "gray"
            )
            return WorkflowResult(
                entity=entity_name,
                workflow_id=wf.id,
                status=WorkflowStatus.SKIPPED,
            )

        self.output_fn(
            f"[UPDATE]  {prefix} ... DIFFERS", "yellow"
        )
        return WorkflowResult(
            entity=entity_name,
            workflow_id=wf.id,
            status=WorkflowStatus.UPDATED,
        )

    def _write_workflows(
        self,
        entity_name: str,
        espo_name: str,
        desired_workflows: list[Workflow],
        existing_workflows: list[dict],
        desired_ids: set[str],
    ) -> bool:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """Write the full set of workflows to CRM metadata.

        Preserves existing workflows that are not in the YAML (drift
        workflows are reported but not deleted).

        :param entity_name: Natural entity name.
        :param espo_name: EspoCRM entity name.
        :param desired_workflows: Desired workflows from YAML.
        :param existing_workflows: Current workflows from CRM.
        :param desired_ids: Set of desired workflow IDs.
        :returns: True if write succeeded.
        """
        merged: list[dict] = [
            self._workflow_to_dict(w) for w in desired_workflows
        ]
        for ew in existing_workflows:
            eid = ew.get("id", "")
            if eid and eid not in desired_ids:
                merged.append(ew)

        payload: dict[str, Any] = {
            "clientDefs": {
                espo_name: {
                    "workflows": merged,
                },
            },
        }

        self.output_fn(
            f"[WRITE]   {entity_name} workflows metadata ...",
            "white",
        )
        status_code, body = self.client.put_metadata(payload)

        if status_code == 401:
            raise WorkflowManagerError(
                "Authentication failed (HTTP 401)"
            )

        if status_code < 0 or status_code >= 400:
            self.output_fn(
                f"[ERROR]   {entity_name} workflows metadata ... "
                f"HTTP {status_code}",
                "red",
            )
            self.output_fn(f"          {_format_error_detail(body)}", "red")
            return False

        self.output_fn(
            f"[WRITE]   {entity_name} workflows metadata ... OK",
            "green",
        )
        return True

    @staticmethod
    def _extract_existing_workflows(client_defs: dict) -> list[dict]:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """Extract workflows from clientDefs metadata.

        :param client_defs: clientDefs dict from the API.
        :returns: List of workflow dicts.
        """
        workflows = client_defs.get("workflows", [])
        if not isinstance(workflows, list):
            return []
        return workflows

    @staticmethod
    def _workflow_to_dict(wf: Workflow) -> dict:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """Convert a Workflow model to a metadata dict.

        :param wf: Workflow instance.
        :returns: Dict suitable for CRM metadata.
        """
        d: dict[str, Any] = {
            "id": wf.id,
            "name": wf.name,
        }
        if wf.description is not None:
            d["description"] = wf.description
        if wf.trigger is not None:
            trigger_d: dict[str, Any] = {"event": wf.trigger.event}
            if wf.trigger.field is not None:
                trigger_d["field"] = wf.trigger.field
            if wf.trigger.from_values is not None:
                trigger_d["from"] = wf.trigger.from_values
            if wf.trigger.to_values is not None:
                trigger_d["to"] = wf.trigger.to_values
            d["trigger"] = trigger_d
        if wf.where is not None:
            d["where"] = render_condition(wf.where)
        if wf.actions:
            actions_list: list[dict] = []
            for action in wf.actions:
                act_d: dict[str, Any] = {"type": action.type}
                if action.field is not None:
                    act_d["field"] = action.field
                if action.value is not None:
                    act_d["value"] = action.value
                if action.template is not None:
                    act_d["template"] = action.template
                if action.to is not None:
                    act_d["to"] = action.to
                actions_list.append(act_d)
            d["actions"] = actions_list
        return d

    @staticmethod
    def _workflows_match(desired: dict, existing: dict) -> bool:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """Compare a desired workflow dict against an existing one.

        :param desired: Workflow dict from YAML.
        :param existing: Workflow dict from CRM metadata.
        :returns: True if they match on all meaningful keys.
        """
        keys = {
            "id", "name", "description", "trigger",
            "where", "actions",
        }
        for key in keys:
            d_val = desired.get(key)
            e_val = existing.get(key)
            if d_val != e_val:
                return False
        return True
