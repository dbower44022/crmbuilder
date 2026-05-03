"""Duplicate-check rule CHECK->ACT orchestration logic."""

import logging
from collections.abc import Callable
from typing import Any

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.models import (
    DuplicateCheck,
    DuplicateCheckResult,
    DuplicateCheckStatus,
    EntityAction,
    EntityDefinition,
    ProgramFile,
)
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class DuplicateCheckManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class DuplicateCheckManager:
    """Orchestrates duplicate-check rule CHECK->ACT operations.

    Reads current duplicate-check configuration from the CRM's
    clientDefs metadata and applies any differences declared in the
    YAML ``duplicateChecks:`` block.

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

    def process_duplicate_checks(
        self, program: ProgramFile
    ) -> list[DuplicateCheckResult]:
        """Apply duplicate-check rules for all entities in the program.

        :param program: Parsed and validated program file.
        :returns: List of per-rule results.
        :raises DuplicateCheckManagerError: On authentication failure.
        """
        results: list[DuplicateCheckResult] = []

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if not entity_def.duplicate_checks:
                continue

            entity_results = self._process_entity_checks(entity_def)
            results.extend(entity_results)

        return results

    def _process_entity_checks(
        self, entity_def: EntityDefinition
    ) -> list[DuplicateCheckResult]:
        """CHECK->ACT for all duplicate-check rules on one entity.

        :param entity_def: Entity definition with duplicate checks.
        :returns: List of results for each rule.
        :raises DuplicateCheckManagerError: On authentication failure.
        """
        espo_name = get_espo_entity_name(entity_def.name)
        prefix = entity_def.name

        # Phase 1: CHECK — read current clientDefs metadata
        self.output_fn(
            f"[CHECK]   {prefix} duplicateChecks ...", "white"
        )
        status_code, client_defs = self.client.get_client_defs(espo_name)

        if status_code == 401:
            raise DuplicateCheckManagerError(
                "Authentication failed (HTTP 401)"
            )

        if status_code < 0:
            self.output_fn(
                f"[ERROR]   {prefix} duplicateChecks ... CONNECTION ERROR",
                "red",
            )
            return [
                DuplicateCheckResult(
                    entity=entity_def.name,
                    rule_id=rule.id,
                    status=DuplicateCheckStatus.ERROR,
                    error="Connection error",
                )
                for rule in entity_def.duplicate_checks
            ]

        if client_defs is None:
            client_defs = {}

        # Extract existing rules from metadata
        existing_rules = self._extract_existing_rules(client_defs)
        results: list[DuplicateCheckResult] = []
        desired_ids: set[str] = set()

        for rule in entity_def.duplicate_checks:
            desired_ids.add(rule.id)
            result = self._process_rule(
                entity_def.name, espo_name, rule, existing_rules
            )
            results.append(result)

        # Drift detection: rules on CRM not in YAML
        for existing in existing_rules:
            eid = existing.get("id", "")
            if eid and eid not in desired_ids:
                self.output_fn(
                    f"[DRIFT]   {prefix}.duplicateChecks[{eid}] "
                    f"exists on CRM but not in YAML",
                    "yellow",
                )
                results.append(DuplicateCheckResult(
                    entity=entity_def.name,
                    rule_id=eid,
                    status=DuplicateCheckStatus.DRIFT,
                ))

        # Phase 2: ACT — write updated rules to metadata
        if any(
            r.status in (DuplicateCheckStatus.CREATED, DuplicateCheckStatus.UPDATED)
            for r in results
        ):
            write_ok = self._write_rules(
                entity_def.name, espo_name, entity_def.duplicate_checks,
                existing_rules, desired_ids,
            )
            if not write_ok:
                # Mark created/updated results as errors
                for r in results:
                    if r.status in (
                        DuplicateCheckStatus.CREATED,
                        DuplicateCheckStatus.UPDATED,
                    ):
                        r.status = DuplicateCheckStatus.ERROR
                        r.error = "Failed to write metadata"

        return results

    def _process_rule(
        self,
        entity_name: str,
        espo_name: str,
        rule: DuplicateCheck,
        existing_rules: list[dict],
    ) -> DuplicateCheckResult:
        """Compare a single rule against existing CRM state.

        :param entity_name: Natural entity name.
        :param espo_name: EspoCRM entity name (C-prefixed).
        :param rule: Desired duplicate-check rule.
        :param existing_rules: Current rules from the CRM.
        :returns: Result indicating create/update/skip.
        """
        prefix = f"{entity_name}.duplicateChecks[{rule.id}]"

        # Find existing rule by id
        existing = None
        for er in existing_rules:
            if er.get("id") == rule.id:
                existing = er
                break

        desired = self._rule_to_dict(rule)

        if existing is None:
            self.output_fn(
                f"[CREATE]  {prefix} ... NOT FOUND ON CRM", "white"
            )
            return DuplicateCheckResult(
                entity=entity_name,
                rule_id=rule.id,
                status=DuplicateCheckStatus.CREATED,
            )

        # Compare
        if self._rules_match(desired, existing):
            self.output_fn(
                f"[SKIP]    {prefix} ... MATCHES", "gray"
            )
            return DuplicateCheckResult(
                entity=entity_name,
                rule_id=rule.id,
                status=DuplicateCheckStatus.SKIPPED,
            )

        self.output_fn(
            f"[UPDATE]  {prefix} ... DIFFERS", "yellow"
        )
        return DuplicateCheckResult(
            entity=entity_name,
            rule_id=rule.id,
            status=DuplicateCheckStatus.UPDATED,
        )

    def _write_rules(
        self,
        entity_name: str,
        espo_name: str,
        desired_checks: list[DuplicateCheck],
        existing_rules: list[dict],
        desired_ids: set[str],
    ) -> bool:
        """Write the full set of duplicate-check rules to CRM metadata.

        Preserves existing rules that are not in the YAML (drift rules
        are reported but not deleted).

        :param entity_name: Natural entity name.
        :param espo_name: EspoCRM entity name.
        :param desired_checks: Desired rules from YAML.
        :param existing_rules: Current rules from CRM.
        :param desired_ids: Set of desired rule IDs.
        :returns: True if write succeeded.
        """
        # Build merged rule list: desired rules first, then preserved drift
        merged: list[dict] = [self._rule_to_dict(r) for r in desired_checks]
        for er in existing_rules:
            eid = er.get("id", "")
            if eid and eid not in desired_ids:
                merged.append(er)

        payload: dict[str, Any] = {
            "clientDefs": {
                espo_name: {
                    "duplicateCheck": {
                        "rules": merged,
                    },
                },
            },
            "recordDefs": {
                espo_name: {
                    "duplicateWhereClause": self._build_where_clauses(
                        merged
                    ),
                },
            },
        }

        self.output_fn(
            f"[WRITE]   {entity_name} duplicateChecks metadata ...",
            "white",
        )
        status_code, body = self.client.put_metadata(payload)

        if status_code == 401:
            raise DuplicateCheckManagerError(
                "Authentication failed (HTTP 401)"
            )

        if status_code < 0 or status_code >= 400:
            self.output_fn(
                f"[ERROR]   {entity_name} duplicateChecks metadata ... "
                f"HTTP {status_code}",
                "red",
            )
            self.output_fn(f"          {_format_error_detail(body)}", "red")
            return False

        self.output_fn(
            f"[WRITE]   {entity_name} duplicateChecks metadata ... OK",
            "green",
        )
        return True

    @staticmethod
    def _extract_existing_rules(client_defs: dict) -> list[dict]:
        """Extract duplicate-check rules from clientDefs metadata.

        :param client_defs: clientDefs dict from the API.
        :returns: List of rule dicts.
        """
        dup_check = client_defs.get("duplicateCheck", {})
        if not isinstance(dup_check, dict):
            return []
        rules = dup_check.get("rules", [])
        if not isinstance(rules, list):
            return []
        return rules

    @staticmethod
    def _rule_to_dict(rule: DuplicateCheck) -> dict:
        """Convert a DuplicateCheck model to a metadata dict.

        :param rule: DuplicateCheck instance.
        :returns: Dict suitable for CRM metadata.
        """
        d: dict[str, Any] = {
            "id": rule.id,
            "fields": rule.fields,
            "onMatch": rule.onMatch,
        }
        if rule.message is not None:
            d["message"] = rule.message
        if rule.normalize is not None:
            d["normalize"] = rule.normalize
        if rule.alertTemplate is not None:
            d["alertTemplate"] = rule.alertTemplate
        if rule.alertTo is not None:
            d["alertTo"] = rule.alertTo
        return d

    @staticmethod
    def _rules_match(desired: dict, existing: dict) -> bool:
        """Compare a desired rule dict against an existing one.

        :param desired: Rule dict from YAML.
        :param existing: Rule dict from CRM metadata.
        :returns: True if they match on all meaningful keys.
        """
        keys = {"id", "fields", "onMatch", "message", "normalize",
                "alertTemplate", "alertTo"}
        for key in keys:
            d_val = desired.get(key)
            e_val = existing.get(key)
            if d_val != e_val:
                return False
        return True

    @staticmethod
    def _build_where_clauses(rules: list[dict]) -> list[dict]:
        """Build EspoCRM duplicateWhereClause entries from rules.

        Each rule produces a where-clause entry that EspoCRM uses for
        server-side duplicate detection.

        :param rules: List of rule dicts.
        :returns: List of where-clause dicts.
        """
        clauses: list[dict] = []
        for rule in rules:
            fields = rule.get("fields", [])
            if not fields:
                continue
            clause: dict[str, Any] = {}
            for field_name in fields:
                clause[field_name] = {"type": "equals", "attribute": field_name}
            clauses.append(clause)
        return clauses
