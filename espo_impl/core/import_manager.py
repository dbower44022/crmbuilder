"""Business logic for data import CHECK and ACT operations."""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from espo_impl.core.api_client import EspoAdminClient

logger = logging.getLogger(__name__)


class ImportAction(Enum):
    """Action determined for a single record during CHECK."""

    CREATE = "create"
    UPDATE = "update"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class RecordPlan:
    """The plan for a single record determined during CHECK."""

    source_name: str
    email: str | None
    action: ImportAction
    espo_id: str | None = None
    fields_to_set: dict = field(default_factory=dict)
    fields_skipped: list = field(default_factory=list)
    error_message: str | None = None


@dataclass
class ImportResult:
    """The outcome of ACT for a single record."""

    source_name: str
    email: str | None
    action: ImportAction
    success: bool
    fields_set: list = field(default_factory=list)
    fields_skipped: list = field(default_factory=list)
    error_message: str | None = None


@dataclass
class ImportReport:
    """Complete report for an import operation."""

    timestamp: str
    instance_name: str
    entity: str
    source_file: str
    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    results: list[ImportResult] = field(default_factory=list)


class ImportManager:
    """Orchestrates CHECK and ACT for data import operations.

    :param client: Authenticated API client.
    :param emit_line: Optional callable(message, color) for live output.
    """

    def __init__(
        self,
        client: EspoAdminClient,
        emit_line: Callable[[str, str], None] | None = None,
    ) -> None:
        self.client = client
        self.emit_line = emit_line or (lambda msg, color: None)

    def _build_payload(
        self,
        record: dict,
        field_mapping: dict[str, str],
        fixed_values: dict[str, str],
    ) -> dict[str, Any]:
        """Build the EspoCRM payload for a single source record.

        :param record: Source record with a 'fields' dict.
        :param field_mapping: {json_key: espo_field_name}.
        :param fixed_values: {espo_field_name: value} applied to all records.
        :returns: Payload dict ready for EspoCRM.
        """
        payload: dict[str, Any] = {}
        fields = record.get("fields", {})

        for json_key, espo_field in field_mapping.items():
            if espo_field == "(skip)":
                continue
            value = fields.get(json_key, "")
            if value == "" or value is None:
                continue
            payload[espo_field] = value

        for espo_field, value in fixed_values.items():
            if value == "" or value is None:
                continue
            # Convert boolean strings
            if isinstance(value, str) and value.lower() in ("true", "false"):
                payload[espo_field] = value.lower() == "true"
            else:
                payload[espo_field] = value

        return payload

    def _find_email(
        self,
        record: dict,
        field_mapping: dict[str, str],
        fixed_values: dict[str, str],
    ) -> str | None:
        """Extract the email address from a record using the mapping.

        :param record: Source record.
        :param field_mapping: {json_key: espo_field_name}.
        :param fixed_values: {espo_field_name: value}.
        :returns: Email string or None.
        """
        # Check fixed values first
        if "emailAddress" in fixed_values:
            val = fixed_values["emailAddress"]
            if val:
                return val

        # Find which JSON key maps to emailAddress
        fields = record.get("fields", {})
        for json_key, espo_field in field_mapping.items():
            if espo_field == "emailAddress":
                val = fields.get(json_key, "")
                if val:
                    return val

        return None

    def check(
        self,
        entity: str,
        records: list[dict],
        field_mapping: dict[str, str],
        fixed_values: dict[str, str],
    ) -> list[RecordPlan]:
        """Determine the action for each record without making changes.

        :param entity: EspoCRM entity name.
        :param records: List of source records (each has a 'fields' dict).
        :param field_mapping: {json_field_key: espo_field_name}.
        :param fixed_values: {espo_field_name: value} applied to all records.
        :returns: List of RecordPlan, one per source record.
        """
        plans: list[RecordPlan] = []

        for i, record in enumerate(records):
            source_name = record.get("name", f"Record {i + 1}")
            payload = self._build_payload(record, field_mapping, fixed_values)
            email = self._find_email(record, field_mapping, fixed_values)

            self.emit_line(
                f"[CHECK]   {source_name} ... checking",
                "white",
            )

            if not email:
                plan = RecordPlan(
                    source_name=source_name,
                    email=None,
                    action=ImportAction.ERROR,
                    error_message="no email address found",
                )
                self.emit_line(
                    f"[CHECK]   {source_name} ... ERROR — no email address",
                    "red",
                )
                plans.append(plan)
                continue

            # Search for existing record by email
            status, matches = self.client.search_by_email(entity, email)
            if status == -1 or matches is None:
                plan = RecordPlan(
                    source_name=source_name,
                    email=email,
                    action=ImportAction.ERROR,
                    error_message="API connection error during search",
                )
                self.emit_line(
                    f"[CHECK]   {source_name} ... ERROR — connection error",
                    "red",
                )
                plans.append(plan)
                continue

            if len(matches) == 0:
                # CREATE — no existing record
                plan = RecordPlan(
                    source_name=source_name,
                    email=email,
                    action=ImportAction.CREATE,
                    fields_to_set=payload,
                )
                self.emit_line(
                    f"[CHECK]   {source_name} ({email}) ... CREATE",
                    "green",
                )
                plans.append(plan)
                continue

            # Existing record found
            if len(matches) >= 2:
                self.emit_line(
                    f"[CHECK]   WARNING — duplicate email {email} "
                    f"in EspoCRM, using first match",
                    "yellow",
                )

            existing = matches[0]
            espo_id = existing.get("id")

            # Fetch full record for field comparison
            get_status, full_record = self.client.get_record(entity, espo_id)
            if get_status != 200 or full_record is None:
                plan = RecordPlan(
                    source_name=source_name,
                    email=email,
                    action=ImportAction.ERROR,
                    error_message=f"failed to fetch record {espo_id}",
                )
                self.emit_line(
                    f"[CHECK]   {source_name} ... ERROR — "
                    f"could not fetch record",
                    "red",
                )
                plans.append(plan)
                continue

            # Compare: only set fields that are empty/null in EspoCRM
            fields_to_set: dict[str, Any] = {}
            fields_skipped: list[str] = []

            for field_name, value in payload.items():
                existing_value = full_record.get(field_name)
                if existing_value is None or existing_value == "":
                    fields_to_set[field_name] = value
                else:
                    fields_skipped.append(field_name)

            if not fields_to_set:
                plan = RecordPlan(
                    source_name=source_name,
                    email=email,
                    action=ImportAction.SKIP,
                    espo_id=espo_id,
                    fields_skipped=fields_skipped,
                )
                self.emit_line(
                    f"[CHECK]   {source_name} ({email}) ... SKIP "
                    f"(all fields have values)",
                    "gray",
                )
            else:
                plan = RecordPlan(
                    source_name=source_name,
                    email=email,
                    action=ImportAction.UPDATE,
                    espo_id=espo_id,
                    fields_to_set=fields_to_set,
                    fields_skipped=fields_skipped,
                )
                self.emit_line(
                    f"[CHECK]   {source_name} ({email}) ... UPDATE "
                    f"({len(fields_to_set)} fields)",
                    "green",
                )

            plans.append(plan)

        return plans

    def execute(
        self,
        entity: str,
        plans: list[RecordPlan],
    ) -> ImportReport:
        """Execute a list of RecordPlans produced by check().

        :param entity: EspoCRM entity name.
        :param plans: Plans from check().
        :returns: ImportReport with per-record results.
        """
        report = ImportReport(
            timestamp=datetime.now(datetime.UTC).isoformat(),
            instance_name=self.client.profile.name,
            entity=entity,
            source_file="",
            total=len(plans),
        )

        for plan in plans:
            if plan.action == ImportAction.SKIP:
                self.emit_line(
                    f"[IMPORT]  {plan.source_name} ... SKIP "
                    f"(all fields have values)",
                    "gray",
                )
                report.skipped += 1
                report.results.append(ImportResult(
                    source_name=plan.source_name,
                    email=plan.email,
                    action=ImportAction.SKIP,
                    success=True,
                    fields_skipped=list(plan.fields_skipped),
                ))
                continue

            if plan.action == ImportAction.ERROR:
                self.emit_line(
                    f"[IMPORT]  {plan.source_name} ... "
                    f"ERROR — {plan.error_message}",
                    "red",
                )
                report.errors += 1
                report.results.append(ImportResult(
                    source_name=plan.source_name,
                    email=plan.email,
                    action=ImportAction.ERROR,
                    success=False,
                    error_message=plan.error_message,
                ))
                continue

            if plan.action == ImportAction.CREATE:
                self.emit_line(
                    f"[IMPORT]  {plan.source_name} ... CREATING",
                    "white",
                )
                status, body = self.client.create_record(
                    entity, plan.fields_to_set
                )
                if status in (200, 201):
                    self.emit_line(
                        f"[IMPORT]  {plan.source_name} ... OK",
                        "green",
                    )
                    report.created += 1
                    report.results.append(ImportResult(
                        source_name=plan.source_name,
                        email=plan.email,
                        action=ImportAction.CREATE,
                        success=True,
                        fields_set=list(plan.fields_to_set.keys()),
                    ))
                else:
                    error_msg = f"HTTP {status}"
                    if isinstance(body, dict) and "message" in body:
                        error_msg = body["message"]
                    self.emit_line(
                        f"[IMPORT]  {plan.source_name} ... "
                        f"ERROR — {error_msg}",
                        "red",
                    )
                    report.errors += 1
                    report.results.append(ImportResult(
                        source_name=plan.source_name,
                        email=plan.email,
                        action=ImportAction.CREATE,
                        success=False,
                        error_message=error_msg,
                    ))
                continue

            if plan.action == ImportAction.UPDATE:
                self.emit_line(
                    f"[IMPORT]  {plan.source_name} ... "
                    f"UPDATE (patching {len(plan.fields_to_set)} fields)",
                    "white",
                )
                status, body = self.client.patch_record(
                    entity, plan.espo_id, plan.fields_to_set
                )
                if status == 200:
                    self.emit_line(
                        f"[IMPORT]  {plan.source_name} ... OK",
                        "green",
                    )
                    report.updated += 1
                    report.results.append(ImportResult(
                        source_name=plan.source_name,
                        email=plan.email,
                        action=ImportAction.UPDATE,
                        success=True,
                        fields_set=list(plan.fields_to_set.keys()),
                        fields_skipped=list(plan.fields_skipped),
                    ))
                else:
                    error_msg = f"HTTP {status}"
                    if isinstance(body, dict) and "message" in body:
                        error_msg = body["message"]
                    self.emit_line(
                        f"[IMPORT]  {plan.source_name} ... "
                        f"ERROR — {error_msg}",
                        "red",
                    )
                    report.errors += 1
                    report.results.append(ImportResult(
                        source_name=plan.source_name,
                        email=plan.email,
                        action=ImportAction.UPDATE,
                        success=False,
                        error_message=error_msg,
                    ))

        return report

    def write_report(
        self,
        report: ImportReport,
        reports_dir: Path,
        source_file: str = "",
    ) -> tuple[Path, Path]:
        """Write import report as .log and .json files.

        :param report: Completed import report.
        :param reports_dir: Directory to write reports to.
        :param source_file: Source JSON filename for the report.
        :returns: Tuple of (log_path, json_path).
        """
        report.source_file = source_file
        reports_dir.mkdir(parents=True, exist_ok=True)

        try:
            dt = datetime.fromisoformat(report.timestamp)
            ts = dt.strftime("%Y%m%d_%H%M%S")
        except (ValueError, TypeError):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        stem = f"import_{ts}"
        log_path = reports_dir / f"{stem}.log"
        json_path = reports_dir / f"{stem}.json"

        self._write_log(report, log_path)
        self._write_json(report, json_path)

        return log_path, json_path

    def _write_log(self, report: ImportReport, path: Path) -> None:
        """Write human-readable .log report.

        :param report: Import report data.
        :param path: Output file path.
        """
        lines: list[str] = []
        lines.append("========================================")
        lines.append("CRM Builder \u2014 Import Report")
        lines.append("========================================")
        lines.append(f"Timestamp     : {report.timestamp}")
        lines.append(f"Instance      : {report.instance_name}")
        lines.append(f"Entity        : {report.entity}")
        lines.append(f"Source File   : {report.source_file}")
        lines.append(f"Total Records : {report.total}")
        lines.append(f"  Created     : {report.created}")
        lines.append(f"  Updated     : {report.updated}")
        lines.append(f"  Skipped     : {report.skipped}")
        lines.append(f"  Errors      : {report.errors}")
        lines.append("========================================")
        lines.append("")

        for result in report.results:
            tag = result.action.value.upper()
            email_str = f" ({result.email})" if result.email else ""

            if result.action == ImportAction.CREATE and result.success:
                lines.append(f"[CREATED]  {result.source_name}{email_str}")
                if result.fields_set:
                    lines.append(
                        f"  Fields set: {', '.join(result.fields_set)}"
                    )
            elif result.action == ImportAction.UPDATE and result.success:
                lines.append(f"[UPDATED]  {result.source_name}{email_str}")
                if result.fields_set:
                    lines.append(
                        f"  Fields patched: {', '.join(result.fields_set)}"
                    )
                if result.fields_skipped:
                    lines.append(
                        f"  Fields skipped (had value): "
                        f"{', '.join(result.fields_skipped)}"
                    )
            elif result.action == ImportAction.SKIP:
                lines.append(f"[SKIPPED]  {result.source_name}{email_str}")
                if result.fields_skipped:
                    lines.append(
                        f"  All fields have values: "
                        f"{', '.join(result.fields_skipped)}"
                    )
            elif result.action == ImportAction.ERROR:
                lines.append(
                    f"[ERROR]    {result.source_name}{email_str}"
                    f" \u2014 {result.error_message}"
                )
            elif not result.success:
                lines.append(
                    f"[{tag}]  {result.source_name}{email_str}"
                    f" \u2014 FAILED: {result.error_message}"
                )

            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_json(self, report: ImportReport, path: Path) -> None:
        """Write structured .json report.

        :param report: Import report data.
        :param path: Output file path.
        """
        data = {
            "import_metadata": {
                "timestamp": report.timestamp,
                "instance": report.instance_name,
                "entity": report.entity,
                "source_file": report.source_file,
            },
            "summary": {
                "total": report.total,
                "created": report.created,
                "updated": report.updated,
                "skipped": report.skipped,
                "errors": report.errors,
            },
            "results": [
                {
                    "source_name": r.source_name,
                    "email": r.email,
                    "action": r.action.value,
                    "success": r.success,
                    "fields_set": r.fields_set,
                    "fields_skipped": r.fields_skipped,
                    "error_message": r.error_message,
                }
                for r in report.results
            ],
        }
        path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
