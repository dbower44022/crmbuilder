"""Tooltip check/update orchestration logic."""

import logging
from collections.abc import Callable

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.models import (
    EntityAction,
    EntityDefinition,
    TooltipResult,
    TooltipStatus,
)
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class TooltipManagerError(Exception):
    """Raised on fatal errors during tooltip import (e.g. HTTP 401)."""


class TooltipManager:
    """Orchestrates reading and writing field tooltips to EspoCRM.

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

    @staticmethod
    def _custom_field_name(name: str) -> str:
        """Return the EspoCRM custom field name (c-prefixed).

        :param name: Original field name from the YAML spec.
        :returns: The c-prefixed field name.
        """
        return f"c{name[0].upper()}{name[1:]}"

    def _get_field_resolved(
        self, entity: str, field_name: str
    ) -> tuple[int, dict | None, str]:
        """GET a field, trying c-prefixed name first, then raw.

        :param entity: EspoCRM entity name.
        :param field_name: Field name from YAML.
        :returns: Tuple of (status_code, body, resolved_name).
        """
        c_name = self._custom_field_name(field_name)
        status, body = self.client.get_field(entity, c_name)
        if status == 200 and body is not None:
            return status, body, c_name

        status2, body2 = self.client.get_field(entity, field_name)
        if status2 == 200 and body2 is not None:
            return status2, body2, field_name

        return status if status != 200 else status2, None, field_name

    def process_tooltips(
        self,
        entity_def: EntityDefinition,
        dry_run: bool = False,
    ) -> list[TooltipResult]:
        """Process tooltips for all fields in an entity that have a tooltip value.

        :param entity_def: Entity definition with fields.
        :param dry_run: If True, check only — do not write.
        :returns: List of TooltipResult, one per field.
        :raises TooltipManagerError: On HTTP 401.
        """
        if entity_def.action == EntityAction.DELETE:
            return []

        espo_name = get_espo_entity_name(entity_def.name)
        results: list[TooltipResult] = []

        for field_def in entity_def.fields:
            prefix = f"{entity_def.name}.{field_def.name}"

            # Skip fields with no tooltip
            if not field_def.tooltip:
                self.output_fn(
                    f"[TOOLTIP]  {prefix} ... SKIPPED (no tooltip)",
                    "gray",
                )
                results.append(TooltipResult(
                    entity=entity_def.name,
                    field=field_def.name,
                    status=TooltipStatus.SKIPPED,
                ))
                continue

            # CHECK — fetch current field definition
            self.output_fn(
                f"[TOOLTIP]  {prefix} ... CHECKING", "white"
            )
            status, current, resolved_name = self._get_field_resolved(
                espo_name, field_def.name
            )

            if status == 401:
                raise TooltipManagerError(
                    "Authentication failed (HTTP 401)"
                )

            if status < 0 or current is None:
                error_msg = f"HTTP {status}" if status > 0 else "connection error"
                self.output_fn(
                    f"[TOOLTIP]  {prefix} ... ERROR — {error_msg}",
                    "red",
                )
                results.append(TooltipResult(
                    entity=entity_def.name,
                    field=field_def.name,
                    status=TooltipStatus.ERROR,
                    error=error_msg,
                ))
                continue

            # Compare
            current_tooltip = current.get("tooltip") or ""
            if current_tooltip == field_def.tooltip:
                self.output_fn(
                    f"[TOOLTIP]  {prefix} ... NO CHANGE", "gray"
                )
                results.append(TooltipResult(
                    entity=entity_def.name,
                    field=field_def.name,
                    status=TooltipStatus.NO_CHANGE,
                ))
                continue

            self.output_fn(
                f"[TOOLTIP]  {prefix} ... DIFFERS", "white"
            )

            if dry_run:
                results.append(TooltipResult(
                    entity=entity_def.name,
                    field=field_def.name,
                    status=TooltipStatus.UPDATED,
                ))
                continue

            # ACT — update tooltip only
            update_status, update_body = self.client.update_field(
                espo_name, resolved_name, {"tooltip": field_def.tooltip}
            )

            if update_status == 401:
                raise TooltipManagerError(
                    "Authentication failed (HTTP 401)"
                )

            if update_status == 200:
                self.output_fn(
                    f"[TOOLTIP]  {prefix} ... UPDATED OK", "green"
                )
                results.append(TooltipResult(
                    entity=entity_def.name,
                    field=field_def.name,
                    status=TooltipStatus.UPDATED,
                ))
            else:
                error_msg = (
                    f"HTTP {update_status}: "
                    f"{_format_error_detail(update_body)}"
                )
                self.output_fn(
                    f"[TOOLTIP]  {prefix} ... ERROR — {error_msg}",
                    "red",
                )
                results.append(TooltipResult(
                    entity=entity_def.name,
                    field=field_def.name,
                    status=TooltipStatus.ERROR,
                    error=error_msg,
                ))

        return results
