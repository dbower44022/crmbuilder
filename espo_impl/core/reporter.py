"""Log and JSON report generation."""

import json
import logging
from datetime import datetime
from pathlib import Path

from espo_impl.core.models import (
    DuplicateCheckResult,
    FieldResult,
    LayoutResult,
    RelationshipResult,
    RunReport,
    SettingsResult,
    TooltipResult,
)

logger = logging.getLogger(__name__)


class Reporter:
    """Generates .log and .json reports for run/verify operations.

    :param reports_dir: Directory to write report files.
    """

    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def write_report(self, report: RunReport) -> tuple[Path, Path]:
        """Write both .log and .json reports.

        :param report: Completed run report.
        :returns: Tuple of (log_path, json_path).
        """
        stem = self._generate_filename(report)
        log_path = self.reports_dir / f"{stem}.log"
        json_path = self.reports_dir / f"{stem}.json"

        self._write_log(report, log_path)
        self._write_json(report, json_path)

        logger.info("Reports written to: %s, %s", log_path, json_path)
        return log_path, json_path

    def _write_log(self, report: RunReport, path: Path) -> None:
        """Write human-readable .log report.

        :param report: Run report data.
        :param path: Output file path.
        """
        lines: list[str] = []
        lines.append("===========================================")
        lines.append(f"CRM Builder — {report.operation.upper()} Report")
        lines.append("===========================================")
        lines.append(f"Timestamp    : {report.timestamp}")
        lines.append(f"Instance     : {report.instance_name}")
        lines.append(f"URL          : {report.espocrm_url}")
        lines.append(f"Program File : {report.program_file}")
        lines.append(f"Version      : {report.content_version}")
        lines.append(f"Operation    : {report.operation}")
        lines.append("===========================================")
        lines.append("")

        for result in report.results:
            status_str = result.status.value.upper()
            line = f"  {result.entity}.{result.field} : {status_str}"
            if result.verified:
                line += " (verified)"
            if result.changes:
                line += f" [{', '.join(result.changes)}]"
            if result.error:
                line += f" — {result.error}"
            lines.append(line)

        if report.layout_results:
            lines.append("")
            for result in report.layout_results:
                status_str = result.status.value.upper()
                line = f"  {result.entity}.{result.layout_type} : {status_str}"
                if result.verified:
                    line += " (verified)"
                if result.error:
                    line += f" — {result.error}"
                lines.append(line)

        lines.append("")
        lines.append("===========================================")
        lines.append("SUMMARY")
        lines.append("===========================================")
        lines.append(f"Total fields processed : {report.summary.total}")
        lines.append(f"  Created              : {report.summary.created}")
        lines.append(f"  Updated              : {report.summary.updated}")
        lines.append(f"  Skipped (no change)  : {report.summary.skipped}")
        lines.append(f"  Verification failed  : {report.summary.verification_failed}")
        lines.append(f"  Errors               : {report.summary.errors}")

        if report.layout_results:
            lines.append("")
            total_layouts = len(report.layout_results)
            lines.append(f"Total layouts processed : {total_layouts}")
            lines.append(f"  Updated              : {report.summary.layouts_updated}")
            lines.append(f"  Skipped (no change)  : {report.summary.layouts_skipped}")
            lines.append(f"  Failed               : {report.summary.layouts_failed}")

        if report.relationship_results:
            lines.append("")
            for result in report.relationship_results:
                status_str = result.status.value.upper()
                line = (
                    f"  {result.entity} \u2192 {result.entity_foreign}"
                    f" ({result.link}) : {status_str}"
                )
                if result.verified:
                    line += " (verified)"
                if result.message:
                    line += f" \u2014 {result.message}"
                lines.append(line)
            lines.append("")
            total_rels = len(report.relationship_results)
            lines.append(f"Total relationships    : {total_rels}")
            lines.append(f"  Created              : {report.summary.relationships_created}")
            lines.append(f"  Skipped              : {report.summary.relationships_skipped}")
            lines.append(f"  Failed               : {report.summary.relationships_failed}")

        if report.tooltip_results:
            lines.append("")
            for result in report.tooltip_results:
                status_str = result.status.value.upper()
                line = f"  {result.entity}.{result.field} : {status_str}"
                if result.error:
                    line += f" \u2014 {result.error}"
                lines.append(line)
            lines.append("")
            total_tips = len(report.tooltip_results)
            lines.append(f"Total tooltips processed : {total_tips}")
            lines.append(f"  Updated               : {report.summary.tooltips_updated}")
            lines.append(f"  No change / skipped   : {report.summary.tooltips_skipped}")
            lines.append(f"  Failed                : {report.summary.tooltips_failed}")

        if report.settings_results:
            lines.append("")
            for result in report.settings_results:
                status_str = result.status.value.upper()
                line = f"  {result.entity} settings : {status_str}"
                if result.changes:
                    line += f" [{', '.join(result.changes)}]"
                if result.error:
                    line += f" \u2014 {result.error}"
                lines.append(line)
            lines.append("")
            total_settings = len(report.settings_results)
            lines.append(f"Total settings processed : {total_settings}")
            lines.append(f"  Updated               : {report.summary.settings_updated}")
            lines.append(f"  Skipped               : {report.summary.settings_skipped}")
            lines.append(f"  Failed                : {report.summary.settings_failed}")

        if report.duplicate_check_results:
            lines.append("")
            for result in report.duplicate_check_results:
                status_str = result.status.value.upper()
                line = f"  {result.entity}.duplicateChecks[{result.rule_id}] : {status_str}"
                if result.error:
                    line += f" \u2014 {result.error}"
                lines.append(line)
            lines.append("")
            total_dc = len(report.duplicate_check_results)
            lines.append(f"Total duplicate checks   : {total_dc}")
            lines.append(f"  Created               : {report.summary.duplicate_checks_created}")
            lines.append(f"  Updated               : {report.summary.duplicate_checks_updated}")
            lines.append(f"  Skipped               : {report.summary.duplicate_checks_skipped}")
            lines.append(f"  Drift                 : {report.summary.duplicate_checks_drift}")
            lines.append(f"  Failed                : {report.summary.duplicate_checks_failed}")

        lines.append("===========================================")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_json(self, report: RunReport, path: Path) -> None:
        """Write structured .json report.

        :param report: Run report data.
        :param path: Output file path.
        """
        data = {
            "run_metadata": {
                "timestamp": report.timestamp,
                "instance": report.instance_name,
                "espocrm_url": report.espocrm_url,
                "program_file": report.program_file,
                "content_version": report.content_version,
                "operation": report.operation,
            },
            "summary": {
                "total": report.summary.total,
                "created": report.summary.created,
                "updated": report.summary.updated,
                "skipped": report.summary.skipped,
                "verification_failed": report.summary.verification_failed,
                "errors": report.summary.errors,
            },
            "results": [self._result_to_dict(r) for r in report.results],
            "layout_results": [
                self._layout_result_to_dict(r) for r in report.layout_results
            ],
            "relationship_results": [
                self._relationship_result_to_dict(r)
                for r in report.relationship_results
            ],
            "tooltip_results": [
                self._tooltip_result_to_dict(r)
                for r in report.tooltip_results
            ],
            "settings_results": [
                self._settings_result_to_dict(r)
                for r in report.settings_results
            ],
            "duplicate_check_results": [
                self._duplicate_check_result_to_dict(r)
                for r in report.duplicate_check_results
            ],
        }
        path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )

    def _result_to_dict(self, result: FieldResult) -> dict:
        """Convert a FieldResult to a JSON-serializable dict.

        :param result: Single field result.
        :returns: Dict matching PRD Section 8.3 schema.
        """
        return {
            "entity": result.entity,
            "field": result.field,
            "status": result.status.value,
            "verified": result.verified,
            "changes": result.changes,
            "error": result.error,
        }

    def _layout_result_to_dict(self, result: LayoutResult) -> dict:
        """Convert a LayoutResult to a JSON-serializable dict.

        :param result: Single layout result.
        :returns: Dict for JSON report.
        """
        return {
            "entity": result.entity,
            "layout_type": result.layout_type,
            "status": result.status.value,
            "verified": result.verified,
            "error": result.error,
        }

    def _relationship_result_to_dict(self, result: RelationshipResult) -> dict:
        """Convert a RelationshipResult to a JSON-serializable dict.

        :param result: Single relationship result.
        :returns: Dict for JSON report.
        """
        return {
            "name": result.name,
            "entity": result.entity,
            "entity_foreign": result.entity_foreign,
            "link": result.link,
            "status": result.status.value,
            "verified": result.verified,
            "message": result.message,
        }

    def _tooltip_result_to_dict(self, result: TooltipResult) -> dict:
        """Convert a TooltipResult to a JSON-serializable dict.

        :param result: Single tooltip result.
        :returns: Dict for JSON report.
        """
        return {
            "entity": result.entity,
            "field": result.field,
            "status": result.status.value,
            "error": result.error,
        }

    def _settings_result_to_dict(self, result: SettingsResult) -> dict:
        """Convert a SettingsResult to a JSON-serializable dict.

        :param result: Single settings result.
        :returns: Dict for JSON report.
        """
        return {
            "entity": result.entity,
            "status": result.status.value,
            "changes": result.changes,
            "error": result.error,
        }

    def _duplicate_check_result_to_dict(
        self, result: DuplicateCheckResult
    ) -> dict:
        """Convert a DuplicateCheckResult to a JSON-serializable dict.

        :param result: Single duplicate-check result.
        :returns: Dict for JSON report.
        """
        return {
            "entity": result.entity,
            "rule_id": result.rule_id,
            "status": result.status.value,
            "error": result.error,
        }

    def _generate_filename(self, report: RunReport) -> str:
        """Generate a timestamped filename stem.

        :param report: Run report for metadata.
        :returns: Filename stem like 'cbm_production_run_20260321_143022'.
        """
        try:
            dt = datetime.fromisoformat(report.timestamp)
            ts = dt.strftime("%Y%m%d_%H%M%S")
        except (ValueError, TypeError):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        slug = report.instance_name.lower().replace(" ", "_").replace("-", "_")
        version_suffix = ""
        if report.content_version:
            version_suffix = f"_v{report.content_version.replace('.', '_')}"
        return f"{slug}_{report.operation}_{ts}{version_suffix}"
