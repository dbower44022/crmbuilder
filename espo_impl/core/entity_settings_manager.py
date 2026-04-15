"""Entity settings CHECK->ACT orchestration logic."""

import logging
from collections.abc import Callable

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.models import (
    EntityAction,
    EntityDefinition,
    ProgramFile,
    SettingsResult,
    SettingsStatus,
)
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class EntitySettingsManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class EntitySettingsManager:
    """Orchestrates entity settings CHECK->ACT operations.

    Reads current entity metadata from the CRM and applies any
    differences declared in the YAML ``settings:`` block.

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

    def process_settings(
        self, program: ProgramFile
    ) -> list[SettingsResult]:
        """Apply entity settings for all entities in the program.

        :param program: Parsed and validated program file.
        :returns: List of per-entity settings results.
        :raises EntitySettingsManagerError: On authentication failure.
        """
        results: list[SettingsResult] = []

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if entity_def.settings is None:
                continue

            result = self._process_entity_settings(entity_def)
            results.append(result)

        return results

    def _process_entity_settings(
        self, entity_def: EntityDefinition
    ) -> SettingsResult:
        """CHECK->ACT for a single entity's settings.

        :param entity_def: Entity definition with settings.
        :returns: SettingsResult for this entity.
        :raises EntitySettingsManagerError: On authentication failure.
        """
        espo_name = get_espo_entity_name(entity_def.name)
        prefix = f"{entity_def.name}"
        settings = entity_def.settings

        # Phase 1: CHECK — read current entity metadata
        self.output_fn(
            f"[CHECK]   {prefix} settings ...", "white"
        )
        status_code, meta = self.client.get_entity_full_metadata(espo_name)

        if status_code == 401:
            raise EntitySettingsManagerError(
                "Authentication failed (HTTP 401)"
            )

        if status_code < 0:
            self.output_fn(
                f"[ERROR]   {prefix} settings ... CONNECTION ERROR", "red"
            )
            return SettingsResult(
                entity=entity_def.name,
                status=SettingsStatus.ERROR,
                error="Connection error",
            )

        if status_code != 200 or meta is None:
            self.output_fn(
                f"[ERROR]   {prefix} settings ... HTTP {status_code}",
                "red",
            )
            return SettingsResult(
                entity=entity_def.name,
                status=SettingsStatus.ERROR,
                error=f"HTTP {status_code}",
            )

        # Compare desired vs current
        changes = self._compute_changes(settings, meta)

        if not changes:
            self.output_fn(
                f"[SKIP]    {prefix} settings ... NO CHANGES NEEDED",
                "gray",
            )
            return SettingsResult(
                entity=entity_def.name,
                status=SettingsStatus.SKIPPED,
            )

        # Phase 2: ACT — update entity settings
        change_str = ", ".join(changes)
        self.output_fn(
            f"[UPDATE]  {prefix} settings ({change_str}) ...", "yellow"
        )

        payload = self._build_payload(entity_def, settings)
        act_status, act_body = self.client.update_entity(payload)

        if act_status == 401:
            raise EntitySettingsManagerError(
                "Authentication failed (HTTP 401)"
            )

        if act_status < 0 or act_status >= 400:
            error_detail = f"HTTP {act_status}"
            self.output_fn(
                f"[ERROR]   {prefix} settings ... {error_detail}", "red"
            )
            if act_body:
                msg = act_body.get("message", "")
                if msg:
                    self.output_fn(f"          {msg}", "red")
            return SettingsResult(
                entity=entity_def.name,
                status=SettingsStatus.ERROR,
                changes=changes,
                error=error_detail,
            )

        self.output_fn(
            f"[UPDATE]  {prefix} settings ... OK", "green"
        )
        return SettingsResult(
            entity=entity_def.name,
            status=SettingsStatus.UPDATED,
            changes=changes,
        )

    @staticmethod
    def _compute_changes(settings, meta: dict) -> list[str]:
        """Compare desired settings against current metadata.

        :param settings: Desired EntitySettings.
        :param meta: Current entity metadata from the API.
        :returns: List of setting names that differ.
        """
        changes: list[str] = []

        if settings.stream is not None:
            current = meta.get("stream", False)
            if current != settings.stream:
                changes.append("stream")

        if settings.disabled is not None:
            current = meta.get("disabled", False)
            if current != settings.disabled:
                changes.append("disabled")

        # Labels are stored at the entity level in EspoCRM
        if settings.labelSingular is not None:
            current = meta.get("labelSingular")
            if current != settings.labelSingular:
                changes.append("labelSingular")

        if settings.labelPlural is not None:
            current = meta.get("labelPlural")
            if current != settings.labelPlural:
                changes.append("labelPlural")

        return changes

    @staticmethod
    def _build_payload(
        entity_def: EntityDefinition, settings
    ) -> dict:
        """Build the API payload for updating entity settings.

        :param entity_def: Entity definition.
        :param settings: Desired EntitySettings.
        :returns: Payload dict for update_entity().
        """
        espo_name = get_espo_entity_name(entity_def.name)
        payload: dict = {"name": espo_name}

        if settings.labelSingular is not None:
            payload["labelSingular"] = settings.labelSingular
        if settings.labelPlural is not None:
            payload["labelPlural"] = settings.labelPlural
        if settings.stream is not None:
            payload["stream"] = settings.stream
        if settings.disabled is not None:
            payload["disabled"] = settings.disabled

        return payload
