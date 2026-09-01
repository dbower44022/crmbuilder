"""Governed system settings CHECK->ACT orchestration (PI-406 / REQ-485).

Writes an instance's declared per-instance setting values into the carrier
record — the single-record custom entity chosen by DEC-927 (``CNetworkStandard``
on the live instances), whose ``settings`` field holds one mapping of governed
setting key to value. The read half lives in
``crmbuilder_v2.introspect.settings_read`` and deliberately uses the ordinary
credential; this writer runs inside the publish path with the admin credential,
like every other deploy manager.

Write semantics are per-key upsert, never wholesale replace: a governed setting
with no declared value for this instance is *not captured* (REQ-485) and the
applier must not invent, clear, or overwrite anything the design has not
declared. Keys the carrier holds beyond the declared set are the comparison's
business to report, not the applier's to remove.
"""

import logging
from collections.abc import Callable
from typing import Any

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.models import SettingsResult, SettingsStatus

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]

#: The single-record custom entity carrying an instance's governed values
#: (DEC-927). One carrier field rather than one field per setting, so the
#: governed set can grow without a schema change on every chapter's CRM.
SETTINGS_ENTITY = "CNetworkStandard"

#: The field on that record holding the governed mapping.
SETTINGS_FIELD = "settings"

#: The record name the applier uses when it must create the single carrier
#: record. EspoCRM requires ``name`` on record creation (the live proof: a
#: create without it 400s with a name/required validationFailure), and the
#: carrier is otherwise created by hand — this mirrors the entity's own name.
SETTINGS_RECORD_NAME = "Network Standard"

#: The design-version stamp fields on the same record (REQ-495 / DEC-974,
#: DEC-980): the frozen release the design was published under, and the
#: SHA-256 identity of the exact plan that was applied. The applier writes
#: them only after a complete, fully-successful apply — a partial apply
#: leaves the previous stamp untouched because this write never runs.
STANDARD_VERSION_FIELD = "standardVersion"
PLAN_FINGERPRINT_FIELD = "planFingerprint"


class SystemSettingsManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class SystemSettingsManager:
    """Orchestrates the governed-settings CHECK->ACT write.

    :param client: EspoCRM admin API client for the target instance.
    :param output_fn: Callback for emitting output messages (message, color).
    """

    def __init__(
        self,
        client: EspoAdminClient,
        output_fn: OutputCallback,
    ) -> None:
        self.client = client
        self.output_fn = output_fn

    def apply_values(
        self, declared: dict[str, Any], dry_run: bool = False
    ) -> SettingsResult:
        """CHECK the carrier record, ACT on the declared per-instance values.

        :param declared: Mapping of governed setting key (the name the CRM
            itself uses) to this instance's declared value. Only these keys
            are written; nothing else on the carrier is touched.
        :param dry_run: If True, log the planned write and return without
            issuing API writes.
        :returns: One :class:`SettingsResult` for the carrier entity.
        :raises SystemSettingsManagerError: On authentication failure.
        """
        prefix = f"{SETTINGS_ENTITY}.{SETTINGS_FIELD}"

        if not declared:
            # Nothing declared for this instance: not captured, never invented.
            self.output_fn(
                f"[CHECK]   {prefix} ... no declared values for this instance",
                "gray",
            )
            return SettingsResult(
                entity=SETTINGS_ENTITY, status=SettingsStatus.SKIPPED
            )

        self.output_fn(f"[CHECK]   {prefix} ...", "white")
        status, body = self.client.list_records(SETTINGS_ENTITY, max_size=1)

        if status == 401:
            raise SystemSettingsManagerError("Authentication failed (HTTP 401)")
        if status == 404:
            # The carrier entity does not exist on this instance. Creating it
            # is entity configuration (custom entity + field + role grant), not
            # a value write — surfaced as manual config, mirroring the other
            # managers' no-write-path outcomes.
            self.output_fn(
                f"[NOT SUPPORTED] {prefix} — carrier entity absent on this "
                "instance; create it (and grant the API role read) before "
                "governed settings can be applied",
                "yellow",
            )
            return SettingsResult(
                entity=SETTINGS_ENTITY,
                status=SettingsStatus.NOT_SUPPORTED,
                error=f"{SETTINGS_ENTITY} is not present on this instance",
            )
        if status < 0 or status >= 400 or not isinstance(body, dict):
            error_detail = f"HTTP {status}"
            self.output_fn(f"[ERROR]   {prefix} ... {error_detail}", "red")
            self.output_fn(f"          {_format_error_detail(body)}", "red")
            return SettingsResult(
                entity=SETTINGS_ENTITY,
                status=SettingsStatus.ERROR,
                error=error_detail,
            )

        records = body.get("list") or []
        current_record = records[0] if records else None
        current_raw = (
            current_record.get(SETTINGS_FIELD) if current_record else None
        )
        current = current_raw if isinstance(current_raw, dict) else {}

        changes = sorted(
            key for key, value in declared.items() if current.get(key) != value
        )
        if not changes:
            self.output_fn(
                f"[OK]      {prefix} ... all declared values already held",
                "green",
            )
            return SettingsResult(
                entity=SETTINGS_ENTITY, status=SettingsStatus.SKIPPED
            )

        change_str = ", ".join(changes)
        self.output_fn(f"[UPDATE]  {prefix} ({change_str}) ...", "yellow")

        if dry_run:
            self.output_fn(
                f"[UPDATE]  {prefix} ... would update (preview)", "gray"
            )
            return SettingsResult(
                entity=SETTINGS_ENTITY,
                status=SettingsStatus.UPDATED,
                changes=changes,
            )

        # Per-key upsert: merge the declared values over what the carrier
        # holds, so undeclared keys survive untouched.
        payload = {SETTINGS_FIELD: {**current, **declared}}
        if current_record is None:
            act_status, act_body = self.client.create_record(
                SETTINGS_ENTITY,
                {"name": SETTINGS_RECORD_NAME, **payload},
            )
        else:
            act_status, act_body = self.client.patch_record(
                SETTINGS_ENTITY, str(current_record.get("id")), payload
            )

        if act_status == 401:
            raise SystemSettingsManagerError("Authentication failed (HTTP 401)")
        if act_status < 0 or act_status >= 400:
            error_detail = f"HTTP {act_status}"
            self.output_fn(f"[ERROR]   {prefix} ... {error_detail}", "red")
            self.output_fn(f"          {_format_error_detail(act_body)}", "red")
            return SettingsResult(
                entity=SETTINGS_ENTITY,
                status=SettingsStatus.ERROR,
                changes=changes,
                error=error_detail,
            )

        self.output_fn(f"[UPDATE]  {prefix} ... OK", "green")
        return SettingsResult(
            entity=SETTINGS_ENTITY,
            status=SettingsStatus.UPDATED,
            changes=changes,
        )


    def write_stamp(
        self,
        *,
        standard_version: str,
        plan_fingerprint: str,
        dry_run: bool = False,
    ) -> SettingsResult:
        """Write the design-version stamp onto the carrier record (REQ-495).

        The caller guarantees the apply completed successfully in full and ran
        under a frozen release (DEC-980 / DEC-981) — this method only ever
        executes after that gate, which is what keeps a partial apply from
        touching the previous stamp.

        :param standard_version: the frozen release the design was published
            under — the readable design version (DEC-980).
        :param plan_fingerprint: the identity of the exact plan applied.
        :param dry_run: If True, log the planned write and return without
            issuing API writes.
        :raises SystemSettingsManagerError: On authentication failure.
        """
        prefix = f"{SETTINGS_ENTITY} stamp"
        desired = {
            STANDARD_VERSION_FIELD: standard_version,
            PLAN_FINGERPRINT_FIELD: plan_fingerprint,
        }
        self.output_fn(f"[CHECK]   {prefix} ...", "white")
        status, body = self.client.list_records(SETTINGS_ENTITY, max_size=1)

        if status == 401:
            raise SystemSettingsManagerError("Authentication failed (HTTP 401)")
        if status == 404:
            self.output_fn(
                f"[NOT SUPPORTED] {prefix} — carrier entity absent on this "
                "instance; create it before the stamp can be written",
                "yellow",
            )
            return SettingsResult(
                entity=SETTINGS_ENTITY,
                status=SettingsStatus.NOT_SUPPORTED,
                error=f"{SETTINGS_ENTITY} is not present on this instance",
            )
        if status < 0 or status >= 400 or not isinstance(body, dict):
            error_detail = f"HTTP {status}"
            self.output_fn(f"[ERROR]   {prefix} ... {error_detail}", "red")
            self.output_fn(f"          {_format_error_detail(body)}", "red")
            return SettingsResult(
                entity=SETTINGS_ENTITY,
                status=SettingsStatus.ERROR,
                error=error_detail,
            )

        records = body.get("list") or []
        current_record = records[0] if records else None
        changes = sorted(
            key
            for key, value in desired.items()
            if current_record is None or current_record.get(key) != value
        )
        if not changes:
            self.output_fn(
                f"[OK]      {prefix} ... already at {standard_version}", "green"
            )
            return SettingsResult(
                entity=SETTINGS_ENTITY, status=SettingsStatus.SKIPPED
            )

        self.output_fn(
            f"[UPDATE]  {prefix} -> {standard_version} ...", "yellow"
        )
        if dry_run:
            self.output_fn(
                f"[UPDATE]  {prefix} ... would update (preview)", "gray"
            )
            return SettingsResult(
                entity=SETTINGS_ENTITY,
                status=SettingsStatus.UPDATED,
                changes=changes,
            )

        if current_record is None:
            act_status, act_body = self.client.create_record(
                SETTINGS_ENTITY,
                {"name": SETTINGS_RECORD_NAME, **desired},
            )
        else:
            act_status, act_body = self.client.patch_record(
                SETTINGS_ENTITY, str(current_record.get("id")), desired
            )

        if act_status == 401:
            raise SystemSettingsManagerError("Authentication failed (HTTP 401)")
        if act_status < 0 or act_status >= 400:
            error_detail = f"HTTP {act_status}"
            self.output_fn(f"[ERROR]   {prefix} ... {error_detail}", "red")
            self.output_fn(f"          {_format_error_detail(act_body)}", "red")
            return SettingsResult(
                entity=SETTINGS_ENTITY,
                status=SettingsStatus.ERROR,
                changes=changes,
                error=error_detail,
            )

        self.output_fn(f"[UPDATE]  {prefix} ... OK", "green")
        return SettingsResult(
            entity=SETTINGS_ENTITY,
            status=SettingsStatus.UPDATED,
            changes=changes,
        )
