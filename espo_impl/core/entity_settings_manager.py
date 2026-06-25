"""Entity settings CHECK->ACT orchestration logic."""

import logging
from collections.abc import Callable

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
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
        self, program: ProgramFile, dry_run: bool = False
    ) -> list[SettingsResult]:
        """Apply entity settings for all entities in the program.

        :param program: Parsed and validated program file.
        :param dry_run: If True, log planned settings updates and return
            without issuing API writes.
        :returns: List of per-entity settings results.
        :raises EntitySettingsManagerError: On authentication failure.
        """
        results: list[SettingsResult] = []

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if entity_def.settings is None:
                continue

            results.extend(self._process_entity_settings(entity_def, dry_run))

        return results

    # Entity-option keys that live in clientDefs (vs entityDefs); their CHECK
    # needs a separate get_client_defs read (PI-313 / REQ-351).
    _CLIENT_DEF_OPTIONS = ("iconClass", "color", "kanbanViewMode", "statusField")

    def _process_entity_settings(
        self, entity_def: EntityDefinition, dry_run: bool = False
    ) -> list[SettingsResult]:
        """CHECK->ACT for a single entity's settings.

        Returns a list: the deployable-settings result (UPDATED / SKIPPED /
        ERROR), plus — when the entity declares ``multipleAssignedUsers`` and it
        differs from the live value — a NOT_SUPPORTED manual-config result, since
        that option has no REST write path (PI-313 / REQ-351).

        :param entity_def: Entity definition with settings.
        :param dry_run: If True, log the planned update and return
            without issuing the API write.
        :returns: One or two SettingsResults for this entity.
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
            return [SettingsResult(
                entity=entity_def.name,
                status=SettingsStatus.ERROR,
                error="Connection error",
            )]

        if status_code != 200 or meta is None:
            self.output_fn(
                f"[ERROR]   {prefix} settings ... HTTP {status_code}",
                "red",
            )
            return [SettingsResult(
                entity=entity_def.name,
                status=SettingsStatus.ERROR,
                error=f"HTTP {status_code}",
            )]

        # clientDefs CHECK only when an icon/color/kanban/statusField is declared.
        client_defs: dict = {}
        if any(getattr(settings, k) is not None for k in self._CLIENT_DEF_OPTIONS):
            c_status, cdefs = self.client.get_client_defs(espo_name)
            if c_status == 200 and isinstance(cdefs, dict):
                client_defs = cdefs

        # Compare desired vs current (deployable options only)
        changes = self._compute_changes(settings, meta, client_defs)
        results = [self._apply_deployable(entity_def, settings, changes, dry_run)]

        # multipleAssignedUsers: no REST write path -> manual-config when it drifts.
        mau = self._multiple_assigned_users_result(entity_def, meta)
        if mau is not None:
            results.append(mau)

        return results

    def _apply_deployable(
        self, entity_def, settings, changes: list[str], dry_run: bool
    ) -> SettingsResult:
        """Apply the deployable settings changes (or report SKIPPED)."""
        prefix = entity_def.name

        if not changes:
            self.output_fn(
                f"[SKIP]    {prefix} settings ... NO CHANGES NEEDED",
                "gray",
            )
            return SettingsResult(
                entity=entity_def.name,
                status=SettingsStatus.SKIPPED,
            )

        change_str = ", ".join(changes)
        self.output_fn(
            f"[UPDATE]  {prefix} settings ({change_str}) ...", "yellow"
        )

        if dry_run:
            self.output_fn(
                f"[UPDATE]  {prefix} settings ... would update (preview)",
                "gray",
            )
            return SettingsResult(
                entity=entity_def.name,
                status=SettingsStatus.UPDATED,
                changes=changes,
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
            self.output_fn(
                f"          {_format_error_detail(act_body)}", "red"
            )
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
    def _multiple_assigned_users_current(meta: dict) -> bool:
        """Whether the live entity has multiple-assignment enabled."""
        fields = meta.get("fields") or {}
        links = meta.get("links") or {}
        return "assignedUsers" in fields or "collaborators" in links

    def _multiple_assigned_users_result(
        self, entity_def, meta: dict
    ) -> SettingsResult | None:
        """Manual-config result when ``multipleAssignedUsers`` drifts.

        The toggle restructures the entity's assignment fields and has no
        updateEntity param (verified by the PI-313 probe), so a difference is
        surfaced as NOT_SUPPORTED manual-config rather than deployed or silently
        skipped (REQ-351). Returns ``None`` when undeclared or already matching.
        """
        desired = entity_def.settings.multipleAssignedUsers
        if desired is None:
            return None
        current = self._multiple_assigned_users_current(meta)
        if desired == current:
            return None
        self.output_fn(
            f"[NOT SUPPORTED] {entity_def.name}.settings.multipleAssignedUsers — "
            f"desired {desired}, current {current}; manual config required "
            "(no REST write path)",
            "yellow",
        )
        return SettingsResult(
            entity=entity_def.name,
            status=SettingsStatus.NOT_SUPPORTED,
            changes=["multipleAssignedUsers"],
        )

    @staticmethod
    def _compute_changes(settings, meta: dict, client_defs: dict | None = None) -> list[str]:
        """Compare desired settings against current metadata.

        :param settings: Desired EntitySettings.
        :param meta: Current entityDefs metadata from the API.
        :param client_defs: Current clientDefs metadata (icon/color/kanban/
            statusField live here); ``None`` treated as empty.
        :returns: List of deployable setting names that differ.

        Note: ``multipleAssignedUsers`` is intentionally NOT computed here — it
        has no REST write path and is handled separately as manual-config
        (PI-313 / REQ-351).
        """
        client_defs = client_defs or {}
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

        # Collection-level settings (PI-300 / REQ-340) live under
        # entityDefs.<Entity>.collection in the metadata payload.
        collection = meta.get("collection") or {}

        if settings.orderBy is not None:
            if collection.get("orderBy") != settings.orderBy:
                changes.append("orderBy")

        if settings.order is not None:
            if collection.get("order") != settings.order:
                changes.append("order")

        if settings.textFilterFields is not None:
            if collection.get("textFilterFields") != settings.textFilterFields:
                changes.append("textFilterFields")

        if settings.fullTextSearch is not None:
            current = collection.get("fullTextSearch", False)
            if current != settings.fullTextSearch:
                changes.append("fullTextSearch")

        if settings.fullTextSearchMinLength is not None:
            if (
                collection.get("fullTextSearchMinLength")
                != settings.fullTextSearchMinLength
            ):
                changes.append("fullTextSearchMinLength")

        # Entity-level options (PI-313 / REQ-346 + REQ-351). countDisabled and
        # optimisticConcurrencyControl live in entityDefs; iconClass / color /
        # kanbanViewMode / statusField in clientDefs. All deploy via the same
        # EntityManager updateEntity action (verified by the PI-313 probe).
        if settings.countDisabled is not None:
            if collection.get("countDisabled", False) != settings.countDisabled:
                changes.append("countDisabled")

        if settings.optimisticConcurrencyControl is not None:
            current = meta.get("optimisticConcurrencyControl", False)
            if current != settings.optimisticConcurrencyControl:
                changes.append("optimisticConcurrencyControl")

        if settings.iconClass is not None:
            if client_defs.get("iconClass") != settings.iconClass:
                changes.append("iconClass")

        if settings.color is not None:
            if client_defs.get("color") != settings.color:
                changes.append("color")

        if settings.kanbanViewMode is not None:
            if client_defs.get("kanbanViewMode", False) != settings.kanbanViewMode:
                changes.append("kanbanViewMode")

        if settings.statusField is not None:
            if client_defs.get("statusField") != settings.statusField:
                changes.append("statusField")

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

        # Collection-level settings (PI-300 / REQ-340). The Entity Manager
        # update action takes the default sort as sortBy/sortDirection
        # (mapped to collection.orderBy/order), and textFilterFields /
        # fullTextSearch / fullTextSearchMinLength directly.
        if settings.orderBy is not None:
            payload["sortBy"] = settings.orderBy
        if settings.order is not None:
            payload["sortDirection"] = settings.order
        if settings.textFilterFields is not None:
            payload["textFilterFields"] = settings.textFilterFields
        if settings.fullTextSearch is not None:
            payload["fullTextSearch"] = settings.fullTextSearch
        if settings.fullTextSearchMinLength is not None:
            payload["fullTextSearchMinLength"] = (
                settings.fullTextSearchMinLength
            )

        # Entity-level options (PI-313). Each is accepted by updateEntity at its
        # own key (verified by the PI-313 throwaway-entity probe); the action
        # routes entityDefs vs clientDefs keys internally.
        if settings.countDisabled is not None:
            payload["countDisabled"] = settings.countDisabled
        if settings.optimisticConcurrencyControl is not None:
            payload["optimisticConcurrencyControl"] = (
                settings.optimisticConcurrencyControl
            )
        if settings.iconClass is not None:
            payload["iconClass"] = settings.iconClass
        if settings.color is not None:
            payload["color"] = settings.color
        if settings.kanbanViewMode is not None:
            payload["kanbanViewMode"] = settings.kanbanViewMode
        if settings.statusField is not None:
            payload["statusField"] = settings.statusField

        return payload
