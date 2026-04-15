"""Email-template CHECK->ACT orchestration logic."""

import logging
from collections.abc import Callable
from typing import Any

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.models import (
    EmailTemplate,
    EmailTemplateResult,
    EmailTemplateStatus,
    EntityAction,
    EntityDefinition,
    ProgramFile,
)
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class EmailTemplateManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class EmailTemplateManager:
    """Orchestrates email-template CHECK->ACT operations.

    Reads current email templates from the CRM and applies any
    differences declared in the YAML ``emailTemplates:`` block.

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

    def process_email_templates(
        self, program: ProgramFile
    ) -> list[EmailTemplateResult]:
        """Apply email templates for all entities in the program.

        :param program: Parsed and validated program file.
        :returns: List of per-template results.
        :raises EmailTemplateManagerError: On authentication failure.
        """
        results: list[EmailTemplateResult] = []

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if not entity_def.email_templates:
                continue

            entity_results = self._process_entity_templates(entity_def)
            results.extend(entity_results)

        return results

    def _process_entity_templates(
        self, entity_def: EntityDefinition
    ) -> list[EmailTemplateResult]:
        """CHECK->ACT for all email templates on one entity.

        :param entity_def: Entity definition with email templates.
        :returns: List of results for each template.
        :raises EmailTemplateManagerError: On authentication failure.
        """
        espo_name = get_espo_entity_name(entity_def.name)
        prefix = entity_def.name

        # Phase 1: CHECK — search for existing templates
        self.output_fn(
            f"[CHECK]   {prefix} emailTemplates ...", "white"
        )
        status_code, existing_list = self._get_existing_templates(espo_name)

        if status_code == 401:
            raise EmailTemplateManagerError(
                "Authentication failed (HTTP 401)"
            )

        if status_code < 0:
            self.output_fn(
                f"[ERROR]   {prefix} emailTemplates ... CONNECTION ERROR",
                "red",
            )
            return [
                EmailTemplateResult(
                    entity=entity_def.name,
                    template_id=tmpl.id,
                    status=EmailTemplateStatus.ERROR,
                    error="Connection error",
                )
                for tmpl in entity_def.email_templates
            ]

        # Build lookup of existing templates by name
        existing_by_name: dict[str, dict] = {}
        for et in existing_list:
            name = et.get("name", "")
            if name:
                existing_by_name[name] = et

        results: list[EmailTemplateResult] = []
        desired_names: set[str] = set()

        for tmpl in entity_def.email_templates:
            desired_names.add(tmpl.name)
            result = self._process_template(
                entity_def.name, espo_name, tmpl, existing_by_name
            )
            results.append(result)

        # Drift detection: templates on CRM not in YAML
        for et in existing_list:
            ename = et.get("name", "")
            if ename and ename not in desired_names:
                self.output_fn(
                    f"[DRIFT]   {prefix}.emailTemplates[{ename}] "
                    f"exists on CRM but not in YAML",
                    "yellow",
                )
                results.append(EmailTemplateResult(
                    entity=entity_def.name,
                    template_id=ename,
                    status=EmailTemplateStatus.DRIFT,
                ))

        return results

    def _process_template(
        self,
        entity_name: str,
        espo_name: str,
        tmpl: EmailTemplate,
        existing_by_name: dict[str, dict],
    ) -> EmailTemplateResult:
        """Compare a single template against existing CRM state.

        :param entity_name: Natural entity name.
        :param espo_name: EspoCRM entity name.
        :param tmpl: Desired email template.
        :param existing_by_name: Existing templates keyed by name.
        :returns: Result indicating create/update/skip.
        """
        prefix = f"{entity_name}.emailTemplates[{tmpl.id}]"
        existing = existing_by_name.get(tmpl.name)

        if existing is None:
            # Create
            self.output_fn(
                f"[CREATE]  {prefix} ... NOT FOUND ON CRM", "white"
            )
            payload = self._template_to_payload(tmpl, espo_name)
            status_code, body = self.client.create_record(
                "EmailTemplate", payload
            )

            if status_code == 401:
                raise EmailTemplateManagerError(
                    "Authentication failed (HTTP 401)"
                )

            if status_code < 0 or status_code >= 400:
                self.output_fn(
                    f"[ERROR]   {prefix} ... HTTP {status_code}", "red"
                )
                return EmailTemplateResult(
                    entity=entity_name,
                    template_id=tmpl.id,
                    status=EmailTemplateStatus.ERROR,
                    error=f"HTTP {status_code}",
                )

            self.output_fn(
                f"[CREATE]  {prefix} ... OK", "green"
            )
            return EmailTemplateResult(
                entity=entity_name,
                template_id=tmpl.id,
                status=EmailTemplateStatus.CREATED,
            )

        # Compare existing — check subject and body hash
        existing_subject = existing.get("subject", "")
        existing_body = existing.get("body", "")
        needs_update = False

        if tmpl.subject != existing_subject:
            needs_update = True
        if tmpl.body_content and tmpl.body_content != existing_body:
            needs_update = True

        if not needs_update:
            self.output_fn(
                f"[SKIP]    {prefix} ... MATCHES", "gray"
            )
            return EmailTemplateResult(
                entity=entity_name,
                template_id=tmpl.id,
                status=EmailTemplateStatus.SKIPPED,
            )

        # Update
        self.output_fn(
            f"[UPDATE]  {prefix} ... DIFFERS", "yellow"
        )
        record_id = existing.get("id", "")
        payload = self._template_to_payload(tmpl, espo_name)
        status_code, body = self.client.patch_record(
            "EmailTemplate", record_id, payload
        )

        if status_code == 401:
            raise EmailTemplateManagerError(
                "Authentication failed (HTTP 401)"
            )

        if status_code < 0 or status_code >= 400:
            self.output_fn(
                f"[ERROR]   {prefix} ... HTTP {status_code}", "red"
            )
            return EmailTemplateResult(
                entity=entity_name,
                template_id=tmpl.id,
                status=EmailTemplateStatus.ERROR,
                error=f"HTTP {status_code}",
            )

        self.output_fn(
            f"[UPDATE]  {prefix} ... OK", "green"
        )
        return EmailTemplateResult(
            entity=entity_name,
            template_id=tmpl.id,
            status=EmailTemplateStatus.UPDATED,
        )

    def _get_existing_templates(
        self, espo_name: str
    ) -> tuple[int, list[dict]]:
        """Fetch existing email templates for an entity from the CRM.

        :param espo_name: EspoCRM entity name.
        :returns: Tuple of (status_code, list of template records).
        """
        url = (
            f"{self.client.profile.api_url}/EmailTemplate"
            f"?where[0][type]=equals"
            f"&where[0][attribute]=entityType"
            f"&where[0][value]={espo_name}"
            f"&maxSize=200"
        )
        status_code, body = self.client._request("GET", url)
        if status_code == 200 and isinstance(body, dict):
            return status_code, body.get("list", [])
        return status_code, []

    @staticmethod
    def _template_to_payload(
        tmpl: EmailTemplate, espo_name: str
    ) -> dict[str, Any]:
        """Convert an EmailTemplate to an API payload.

        :param tmpl: EmailTemplate instance.
        :param espo_name: EspoCRM entity name.
        :returns: Dict suitable for CRM API.
        """
        payload: dict[str, Any] = {
            "name": tmpl.name,
            "subject": tmpl.subject,
            "entityType": espo_name,
            "isHtml": True,
        }
        if tmpl.body_content is not None:
            payload["body"] = tmpl.body_content
        return payload
