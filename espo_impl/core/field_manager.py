"""Field check/create/update/verify orchestration logic."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.comparator import FieldComparator
from espo_impl.core.models import (
    EntityAction,
    FieldDefinition,
    FieldResult,
    FieldStatus,
    ProgramFile,
    RunReport,
    RunSummary,
)
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class AuthenticationError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class FieldManager:
    """Orchestrates field check/create/update/verify operations.

    :param client: EspoCRM admin API client.
    :param comparator: Field comparison engine.
    :param output_fn: Callback for emitting output messages (message, color).
    """

    def __init__(
        self,
        client: EspoAdminClient,
        comparator: FieldComparator,
        output_fn: OutputCallback,
    ) -> None:
        self.client = client
        self.comparator = comparator
        self.output_fn = output_fn

    def run(self, program: ProgramFile) -> RunReport:
        """Execute field operations: check -> act for each field.

        Skips entities with delete-only actions (no fields to process).
        Uses C-prefixed entity names for custom entities.

        :param program: Parsed and validated program file.
        :returns: Complete run report.
        """
        results: list[FieldResult] = []

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if not entity_def.fields:
                continue

            espo_name = get_espo_entity_name(entity_def.name)
            for field_def in entity_def.fields:
                try:
                    result = self._process_field(espo_name, field_def)
                except AuthenticationError:
                    self.output_fn(
                        "[ERROR] Authentication failed (HTTP 401) — aborting run",
                        "red",
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.ERROR,
                        error="Authentication failed (HTTP 401)",
                    ))
                    return self._build_report(program, "run", results)
                else:
                    results.append(result)

        self._emit_summary(results)
        return self._build_report(program, "run", results)

    def verify(self, program: ProgramFile) -> RunReport:
        """Read-only verification of all fields against spec.

        :param program: Parsed and validated program file.
        :returns: Complete verify report.
        """
        results: list[FieldResult] = []

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if not entity_def.fields:
                continue

            espo_name = get_espo_entity_name(entity_def.name)
            for field_def in entity_def.fields:
                prefix = f"{entity_def.name}.{field_def.name}"
                status_code, current, _ = self._get_field_resolved(
                    espo_name, field_def.name
                )

                if status_code == 401:
                    self.output_fn(
                        "[ERROR] Authentication failed (HTTP 401) — aborting verify",
                        "red",
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.ERROR,
                        error="Authentication failed (HTTP 401)",
                    ))
                    return self._build_report(program, "verify", results)

                if status_code == 404:
                    self.output_fn(
                        f"[VERIFY]  {prefix} ... NOT FOUND", "red"
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.VERIFICATION_FAILED,
                        error="Field does not exist",
                    ))
                    continue

                if status_code != 200 or current is None:
                    self.output_fn(
                        f"[ERROR]   {prefix} ... HTTP {status_code}", "red"
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.ERROR,
                        error=f"HTTP {status_code}",
                    ))
                    continue

                comparison = self.comparator.compare(field_def, current)

                if comparison.type_conflict:
                    self.output_fn(
                        f"[VERIFY]  {prefix} ... TYPE CONFLICT", "yellow"
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.VERIFICATION_FAILED,
                        error="Type conflict",
                    ))
                elif comparison.matches:
                    self.output_fn(
                        f"[VERIFY]  {prefix} ... VERIFIED", "green"
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.VERIFIED,
                        verified=True,
                    ))
                else:
                    diff_str = ", ".join(comparison.differences)
                    self.output_fn(
                        f"[VERIFY]  {prefix} ... DIFFERS ({diff_str})", "red"
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.VERIFICATION_FAILED,
                        changes=comparison.differences,
                        error=f"Differs: {diff_str}",
                    ))

        self._emit_summary(results)
        return self._build_report(program, "verify", results)

    def preview(self, program: ProgramFile) -> RunReport:
        """Read-only preview of what a run would do.

        Checks each field against the instance and reports whether it would
        be created, updated, or skipped — without making any changes.

        :param program: Parsed and validated program file.
        :returns: Complete preview report.
        """
        results: list[FieldResult] = []

        self.output_fn("", "white")
        self.output_fn("===========================================", "white")
        self.output_fn("PLANNED CHANGES", "white")
        self.output_fn("===========================================", "white")

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if not entity_def.fields:
                continue

            espo_name = get_espo_entity_name(entity_def.name)
            for field_def in entity_def.fields:
                prefix = f"{entity_def.name}.{field_def.name}"
                status_code, current, _ = self._get_field_resolved(
                    espo_name, field_def.name
                )

                if status_code == 401:
                    self.output_fn(
                        "[ERROR] Authentication failed (HTTP 401) — aborting",
                        "red",
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.ERROR,
                        error="Authentication failed (HTTP 401)",
                    ))
                    return self._build_report(program, "preview", results)

                if status_code < 0:
                    self.output_fn(
                        f"  {prefix} — ERROR (connection failed)", "red"
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.ERROR,
                        error="Connection error",
                    ))
                    continue

                if status_code == 403:
                    self.output_fn(
                        f"  {prefix} — ERROR (HTTP 403 Forbidden)", "red"
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.ERROR,
                        error="Forbidden (HTTP 403)",
                    ))
                    continue

                field_exists = status_code == 200 and current is not None

                if not field_exists:
                    self.output_fn(
                        f"  {prefix} — CREATE ({field_def.type}, "
                        f'"{field_def.label}")',
                        "green",
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.CREATED,
                    ))
                    continue

                comparison = self.comparator.compare(field_def, current)

                if comparison.type_conflict:
                    self.output_fn(
                        f"  {prefix} — SKIP (type conflict: "
                        f"spec={field_def.type}, "
                        f"current={current.get('type')})",
                        "yellow",
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.SKIPPED_TYPE_CONFLICT,
                    ))
                elif comparison.matches:
                    self.output_fn(
                        f"  {prefix} — no changes needed", "gray"
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.SKIPPED,
                    ))
                else:
                    diff_str = ", ".join(comparison.differences)
                    self.output_fn(
                        f"  {prefix} — UPDATE ({diff_str})", "yellow"
                    )
                    results.append(FieldResult(
                        entity=entity_def.name,
                        field=field_def.name,
                        status=FieldStatus.UPDATED,
                        changes=comparison.differences,
                    ))

        self.output_fn("===========================================", "white")

        # Emit a preview summary
        creates = sum(1 for r in results if r.status == FieldStatus.CREATED)
        updates = sum(1 for r in results if r.status == FieldStatus.UPDATED)
        skips = sum(
            1 for r in results
            if r.status in (FieldStatus.SKIPPED, FieldStatus.SKIPPED_TYPE_CONFLICT)
        )
        errors = sum(1 for r in results if r.status == FieldStatus.ERROR)

        self.output_fn(f"  To create : {creates}", "green" if creates else "white")
        self.output_fn(f"  To update : {updates}", "yellow" if updates else "white")
        self.output_fn(f"  No change : {skips}", "gray")
        if errors:
            self.output_fn(f"  Errors    : {errors}", "red")
        if program.relationships:
            self.output_fn("", "white")
            self.output_fn(
                f"  Note: {len(program.relationships)} relationships defined "
                f"— processed during Run, not shown in preview.",
                "white",
            )
        self.output_fn("===========================================", "white")

        return self._build_report(program, "preview", results)

    @staticmethod
    def _extract_field_name_from_409(body: dict[str, Any]) -> str | None:
        """Extract the actual field name from a 409 Conflict response.

        EspoCRM returns a messageTranslation with the existing field name:
        ``{'messageTranslation': {'data': {'field': 'cContactType'}}}``

        :param body: Response body from a 409 error.
        :returns: The actual field name, or None if not extractable.
        """
        try:
            return body["messageTranslation"]["data"]["field"]
        except (KeyError, TypeError):
            return None

    @staticmethod
    def _custom_field_name(name: str) -> str:
        """Return the EspoCRM custom field name (c-prefixed).

        EspoCRM stores custom fields with a 'c' prefix and the first letter
        capitalized: 'contactType' -> 'cContactType'.

        :param name: Original field name from the YAML spec.
        :returns: The c-prefixed field name.
        """
        return f"c{name[0].upper()}{name[1:]}"

    def _get_field_resolved(
        self, entity: str, field_name: str
    ) -> tuple[int, dict[str, Any] | None, str]:
        """GET a field, trying the c-prefixed name first, then raw.

        Custom fields in EspoCRM are stored with a 'c' prefix, so we
        try that first. Falls back to the raw name for system fields.

        :param entity: Entity name.
        :param field_name: Field name from the YAML spec.
        :returns: Tuple of (status_code, body, resolved_name).
        """
        # Try c-prefixed name first (custom fields)
        c_name = self._custom_field_name(field_name)
        status_code, body = self.client.get_field(entity, c_name)
        if status_code == 200 and body is not None:
            return status_code, body, c_name

        # Fall back to raw name (system fields)
        status_code2, body2 = self.client.get_field(entity, field_name)
        if status_code2 == 200 and body2 is not None:
            return status_code2, body2, field_name

        # Return the c-prefix failure (most likely case)
        return status_code, body, c_name

    def _process_field(
        self, entity: str, field_def: FieldDefinition
    ) -> FieldResult:
        """Three-phase cycle for a single field: CHECK -> ACT -> VERIFY.

        :param entity: Entity name.
        :param field_def: Field definition from the program.
        :returns: Result of processing this field.
        :raises AuthenticationError: If API returns 401.
        """
        prefix = f"{entity}.{field_def.name}"

        # Phase 1: CHECK
        self.output_fn(f"[CHECK]   {prefix} ... ", "white")
        status_code, current, resolved_name = self._get_field_resolved(
            entity, field_def.name
        )

        if status_code == 401:
            raise AuthenticationError()

        if status_code < 0:
            self.output_fn(f"[ERROR]   {prefix} ... CONNECTION ERROR", "red")
            return FieldResult(
                entity=entity,
                field=field_def.name,
                status=FieldStatus.ERROR,
                error="Connection error",
            )

        if status_code == 403:
            self.output_fn(f"[ERROR]   {prefix} ... FORBIDDEN (HTTP 403)", "red")
            return FieldResult(
                entity=entity,
                field=field_def.name,
                status=FieldStatus.ERROR,
                error="Forbidden (HTTP 403)",
            )

        field_exists = status_code == 200 and current is not None

        if field_exists:
            self.output_fn(f"[CHECK]   {prefix} ... EXISTS", "white")
            comparison = self.comparator.compare(field_def, current)

            if comparison.type_conflict:
                self.output_fn(
                    f"[SKIP]    {prefix} ... TYPE CONFLICT (skipped)", "yellow"
                )
                return FieldResult(
                    entity=entity,
                    field=field_def.name,
                    status=FieldStatus.SKIPPED_TYPE_CONFLICT,
                )

            if comparison.matches:
                self.output_fn(
                    f"[COMPARE] {prefix} ... MATCHES", "gray"
                )
                self.output_fn(
                    f"[SKIP]    {prefix} ... NO CHANGES NEEDED", "gray"
                )
                return FieldResult(
                    entity=entity,
                    field=field_def.name,
                    status=FieldStatus.SKIPPED,
                )

            # Phase 2: ACT (Update) — use the resolved name for the API
            diff_str = ", ".join(comparison.differences)
            self.output_fn(
                f"[COMPARE] {prefix} ... DIFFERS ({diff_str})", "yellow"
            )
            payload = self._build_payload(field_def)
            act_status, act_body = self.client.update_field(
                entity, resolved_name, payload
            )
            return self._handle_act_result(
                entity, field_def, act_status, act_body, "UPDATE",
                comparison.differences,
            )
        else:
            # Phase 2: ACT (Create)
            self.output_fn(f"[CHECK]   {prefix} ... NOT FOUND", "white")
            payload = self._build_payload(field_def)
            act_status, act_body = self.client.create_field(entity, payload)

            # Handle 409 Conflict — field already exists under c-prefixed name.
            # Extract the actual name and fall back to UPDATE.
            if act_status == 409 and act_body:
                actual_name = self._extract_field_name_from_409(act_body)
                if actual_name:
                    self.output_fn(
                        f"[CREATE]  {prefix} ... already exists as "
                        f"{actual_name}, updating instead",
                        "yellow",
                    )
                    act_status, act_body = self.client.update_field(
                        entity, actual_name, payload
                    )
                    return self._handle_act_result(
                        entity, field_def, act_status, act_body, "UPDATE", None
                    )

            return self._handle_act_result(
                entity, field_def, act_status, act_body, "CREATE", None
            )

    def _handle_act_result(
        self,
        entity: str,
        field_def: FieldDefinition,
        status_code: int,
        response_body: dict[str, Any] | None,
        action: str,
        changes: list[str] | None,
    ) -> FieldResult:
        """Handle the result of a create or update action.

        :param entity: Entity name.
        :param field_def: Field definition.
        :param status_code: HTTP status from the action.
        :param response_body: Response body from the action.
        :param action: "CREATE" or "UPDATE".
        :param changes: List of changed properties (for updates).
        :returns: FieldResult for this field.
        :raises AuthenticationError: If 401 received.
        """
        prefix = f"{entity}.{field_def.name}"

        if status_code == 401:
            raise AuthenticationError()

        if status_code < 0 or status_code >= 400:
            error_detail = f"HTTP {status_code}"
            self.output_fn(
                f"[{action}]  {prefix} ... ERROR ({error_detail})", "red"
            )
            # Log the response body for diagnostic detail
            if response_body:
                msg = response_body.get("message", "")
                if msg:
                    self.output_fn(f"          {msg}", "red")
                else:
                    self.output_fn(f"          {response_body}", "red")
            return FieldResult(
                entity=entity,
                field=field_def.name,
                status=FieldStatus.ERROR,
                changes=changes,
                error=error_detail,
            )

        result_status = (
            FieldStatus.CREATED if action == "CREATE" else FieldStatus.UPDATED
        )

        # The API returned 200 — treat as successful.
        # Inline verification is skipped because EspoCRM's cache may not
        # reflect the change immediately (can cause 500 on re-read).
        # Use the standalone Verify button to confirm after the cache settles.
        self.output_fn(f"[{action}]  {prefix} ... OK", "green")
        return FieldResult(
            entity=entity,
            field=field_def.name,
            status=result_status,
            verified=True,
            changes=changes,
        )

    def _build_payload(self, field_def: FieldDefinition) -> dict[str, Any]:
        """Convert a FieldDefinition to an API payload dict.

        :param field_def: Field definition from the program.
        :returns: Dict suitable for API POST/PUT.
        """
        payload: dict[str, Any] = {
            "name": field_def.name,
            "type": field_def.type,
            "label": field_def.label,
        }
        if field_def.required is not None:
            payload["required"] = field_def.required
        if field_def.default is not None:
            payload["default"] = field_def.default
        if field_def.readOnly is not None:
            payload["readOnly"] = field_def.readOnly
        if field_def.audited is not None:
            payload["audited"] = field_def.audited
        if field_def.copyToClipboard is not None:
            payload["copyToClipboard"] = field_def.copyToClipboard
        if field_def.options is not None:
            payload["options"] = field_def.options
        if field_def.translatedOptions is not None:
            payload["translatedOptions"] = field_def.translatedOptions
        if field_def.style is not None:
            payload["style"] = field_def.style
        if field_def.isSorted is not None:
            payload["isSorted"] = field_def.isSorted
        if field_def.displayAsLabel is not None:
            payload["displayAsLabel"] = field_def.displayAsLabel
        if field_def.min is not None:
            payload["min"] = field_def.min
        if field_def.max is not None:
            payload["max"] = field_def.max
        if field_def.maxLength is not None:
            payload["maxLength"] = field_def.maxLength
        return payload

    def _build_report(
        self,
        program: ProgramFile,
        operation: str,
        results: list[FieldResult],
    ) -> RunReport:
        """Build a RunReport from results.

        :param program: The program file that was processed.
        :param operation: "run" or "verify".
        :param results: Per-field results.
        :returns: Complete RunReport.
        """
        summary = RunSummary(total=len(results))
        for r in results:
            if r.status == FieldStatus.CREATED:
                summary.created += 1
            elif r.status == FieldStatus.UPDATED:
                summary.updated += 1
            elif r.status in (FieldStatus.SKIPPED, FieldStatus.SKIPPED_TYPE_CONFLICT):
                summary.skipped += 1
            elif r.status == FieldStatus.VERIFICATION_FAILED:
                summary.verification_failed += 1
            elif r.status == FieldStatus.ERROR:
                summary.errors += 1
            elif r.status == FieldStatus.VERIFIED:
                pass  # Counted in verify-only operations

        source_name = program.source_path.name if program.source_path else "unknown"

        return RunReport(
            timestamp=datetime.now(UTC).isoformat(),
            instance_name=self.client.profile.name,
            espocrm_url=self.client.profile.url,
            program_file=source_name,
            content_version=program.content_version,
            operation=operation,
            summary=summary,
            results=results,
        )

    def _emit_summary(self, results: list[FieldResult]) -> None:
        """Emit a summary block to the output.

        :param results: Per-field results.
        """
        summary = RunSummary(total=len(results))
        for r in results:
            if r.status == FieldStatus.CREATED:
                summary.created += 1
            elif r.status == FieldStatus.UPDATED:
                summary.updated += 1
            elif r.status in (FieldStatus.SKIPPED, FieldStatus.SKIPPED_TYPE_CONFLICT):
                summary.skipped += 1
            elif r.status == FieldStatus.VERIFICATION_FAILED:
                summary.verification_failed += 1
            elif r.status == FieldStatus.ERROR:
                summary.errors += 1
            elif r.status == FieldStatus.VERIFIED:
                pass

        self.output_fn("", "white")
        self.output_fn("===========================================", "white")
        self.output_fn("RUN SUMMARY", "white")
        self.output_fn("===========================================", "white")
        self.output_fn(f"Total fields processed : {summary.total}", "white")
        self.output_fn(f"  Created              : {summary.created}", "green")
        self.output_fn(f"  Updated              : {summary.updated}", "green")
        self.output_fn(f"  Skipped (no change)  : {summary.skipped}", "gray")
        self.output_fn(
            f"  Verification failed  : {summary.verification_failed}",
            "red" if summary.verification_failed > 0 else "white",
        )
        self.output_fn(
            f"  Errors               : {summary.errors}",
            "red" if summary.errors > 0 else "white",
        )
        self.output_fn("===========================================", "white")
